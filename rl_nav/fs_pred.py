#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/fs_pred.py — thu VONG KIN bo du doan nguoi (nav_pred) trong fastsim, KHONG sua nav_local / robot_ros / fastsim.
MPPI goc, chi thay phan chi phi NGUOI bang du doan (va ca doi chung "tuong lai that" = tran tren).

  FS_ROOT=<ban chup code> venv/bin/python rl_nav/fs_pred.py --seeds 0-149 --crowd-only --jobs 3 --out results/x \
      --configs "mppi:ppl=32" "mppi:pred=1;w_risk=100" "mppi:pred=3"
p3+geo-haz~t3~nl:net=1;wcv=0.0   PRISM3 cua ALGO, thay quat GeoFan bang mang (net=1) / mang khong ngu canh (net=2, can PRED_CTX)
pred=0 MPPI goc | 1 mang (nhieu mode) | 2 mang, chi mode manh nhat | 3 TUONG LAI THAT cua Social Force (robot dung yen) | 4 Kalman-kieu: CV + std
"""
import argparse
import copy
import csv
import json
import math
import os
import sys

for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_k] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("FS_ROOT") or os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(HERE))            # nav_pred (moi nhat)
sys.path.insert(0, ROOT)                              # code da chup, uu tien
import numpy as np  # noqa: E402

PATHS = os.environ.get("PRED_NPZ", os.path.join(HERE, "pred_nav.npz"))


def patch():
    import fastsim
    import nav_local
    import robot_ros
    import nav_pred
    from scipy.special import ndtr
    P_ = nav_pred.Predictor(PATHS) if os.path.exists(PATHS) else None
    TT = np.arange(1, 25) * .1

    class PredMPPI(nav_local.MPPI):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.pred, self.w_risk, self.r_len, self.soft = 0, 0.0, 0.3, 1.0
            self.smax = 9.0
            self.H = nav_pred.History()
            self.robot, self.modes = None, []

        def truth(self, mv):
            """tuong lai that: chay tiep ban sao dam dong 2.4 s (robot coi nhu dung yen)."""
            sim = self.robot.sim
            C = sim.crowd
            snap = [{**p, "p": p["p"].copy(), "v": p["v"].copy(), "path": list(p["path"])} for p in C.people]
            keep, st = C.people, C.rng.getstate()
            C.people = snap
            out = [[] for _ in snap]
            for k in range(48):
                C.step(.05)
                if k % 2:
                    for i, p in enumerate(snap):
                        out[i].append(p["p"].copy())
            C.people = keep
            C.rng.setstate(st)
            res = []
            now = sim.clock.t
            for tr in mv:
                q = tr["p"] + tr["v"] * (now - tr["t"])
                d = [math.hypot(*(p["p"] - q)) for p in keep]
                i = int(np.argmin(d))
                res.append([(1.0, np.array(out[i]), np.full(24, .05))] if d[i] < .6 else
                           nav_pred.constant_velocity([tr], now)[0])
            return res

        def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None, **kw):
            r = self.robot
            self.modes = []
            if self.pred and r is not None:
                now = nav_time()
                self.H.update(r.tracker.tracks, now)
                mv = r.tracker.movers()
                if mv:
                    if self.pred == 3:
                        M = self.truth(mv)
                    elif self.pred == 4:
                        M = nav_pred.constant_velocity(mv, now)
                    else:
                        M = P_.predict(mv, self.H, now, x0, r.v_world, field, meta)
                        if self.pred == 2:
                            M = [[(1.0, *max(m, key=lambda q: q[0])[1:])] for m in M]
                    self.modes = [[q for q in m if q[0] > .03] for m in M]
            return super().step(x0, v0, field, meta, path, s_path, goal, people=people, gain=gain, u_prev=u_prev)

        def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
            if not self.pred or not people:
                return super().cost(U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev)
            S, coll, dmin = super().cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
            w, (K, T) = self.w, P.shape[:2]
            for m in self.modes:
                z = sum(q[0] for q in m)
                for pr, mean, std in m:
                    d = self.ppl_dist(P, Y, mean[None, :T, 0], mean[None, :T, 1], 0.25)
                    S += pr / z * w["ppl"] * np.exp(-np.maximum(d, 0.0) / self.ppl_len).sum(1) / T
                    if self.w_risk > 0:                     # co rui ro: xac suat cham lon nhat doc quy dao
                        S += pr / z * self.w_risk * ndtr(-d / np.minimum(std, self.smax)[None, :T]).max(1)
                    else:
                        S += pr / z * w["col"] * 0.5 * (d < 0.0).any(1)
            return S, coll, dmin

    import nav_prism2
    P2_ = nav_pred.Predictor(os.environ["PRED_CTX"]) if os.environ.get("PRED_CTX") else None

    class NetP3(nav_prism2.PRISM3):
        """PRISM3.geo_cost y nguyen, chi doi TAP QUY DAO: 5 mode x 4 diem sigma (dung mo men bac 2) thay quat GeoFan."""

        def __init__(self, **kw):
            super().__init__(**kw)
            self.net, self.wcv, self.spread = 0, 0.0, 1.0
            self.H, self.robot = nav_pred.History(), None
            self.last_meta = None

        def observe_people(self, people, t):
            super().observe_people(people, t)
            if self.net:
                tk = self.robot.tracker
                self.H.update(tk.tracks, t, tk.movers())

        def geo_cost(self, P, Y, people, field, meta, x0, t):
            if not self.net:
                return super().geo_cost(P, Y, people, field, meta, x0, t)
            K, T = P.shape[:2]
            idx = np.arange(1, T, 3)
            idx = idx[idx < 24]
            tt = (idx + 1) * self.dt
            S = np.zeros(K)
            tk = self.robot.tracker
            mv = tk.movers()
            pl = self.H.people(tk.tracks, mv) if self.net < 3 else mv
            near = sorted(((math.hypot(q["p"][0] - x0[0], q["p"][1] - x0[1]), k) for k, q in enumerate(pl)))[:3]
            sel = [pl[k] for d, k in near if d < 4.5]
            if not sel:
                return S
            pr = P2_ if self.net == 2 else P_
            M = pr.predict(sel, self.H, t, x0, self.robot.v_world, field, meta, pl)
            c, s = np.cos(Y[:, idx]), np.sin(Y[:, idx])
            F = [((P[:, idx, 0] + o * c).astype(np.float32), (P[:, idx, 1] + o * s).astype(np.float32))
                 for o in (self.c_off, -self.c_off)]
            gam = np.exp(-tt / self.g_tau).astype(np.float32)
            R0 = 0.25 + self.r_body + 0.03
            for tr, modes in zip(sel, M):
                modes = [q for q in modes if q[0] > .03]
                z = sum(q[0] for q in modes)
                Q, w = [], []
                for p_, m, sd in modes:
                    for off in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        Q.append(m[idx] + math.sqrt(2) * self.spread * sd[idx, None] * np.array(off))
                        w.append((1 - self.wcv) * p_ / z / 4)
                if self.wcv > 0:
                    Q.append(tr["p"] + tr["v"] * (t - tr["t"] + tt)[:, None])
                    w.append(self.wcv)
                Q, w = np.array(Q, np.float32), np.array(w)
                lo = None
                for fx, fy in F:
                    ex, ey = fx[:, :, None] - Q[None, :, :, 0].transpose(0, 2, 1), fy[:, :, None] - Q[None, :, :, 1].transpose(0, 2, 1)
                    e = ex * ex + ey * ey
                    lo = e if lo is None else np.minimum(lo, e)
                d = np.sqrt(lo) - R0
                R = (np.where(d > 0, np.exp(-np.maximum(d, 0) / self.g_len), 1.0 - d) * gam[None, :, None]).max(1)
                S += R @ w
            return self.w_geo * S

    def nav_time():
        return fastsim.CLOCK.t
    orig = robot_ros.RosRobotTools._make_ctrl_base

    def base(self):
        if self.controller == "mppi":
            c = PredMPPI(vmax=(self.goto_speed * 1.7, 0.3, self.goto_turn * 1.25),
                         vmin=(-0.2, -0.3, -self.goto_turn * 1.25))
            c.robot = self
            return c
        c = orig(self)
        if type(c).__name__ == "PRISM3":
            n = NetP3(priors=c.priors, flags=c.flags, vmax=c.vmax, vmin=c.vmin)
            n.robot = self
            return n
        return c
    robot_ros.RosRobotTools._make_ctrl_base = base
    return fastsim


def work(a):
    jobs, out, i, regime, cm = a
    fastsim = patch()
    fastsim.CROWD_MODEL = cm
    f = open(os.path.join(out, f"w{i}.csv"), "a", newline="")
    w = csv.DictWriter(f, fastsim.FIELDS, extrasaction="ignore")
    if f.tell() == 0:
        w.writeheader()
    W, last = None, None
    for s, t, cfg in jobs:
        if last != s:
            W, last = fastsim.gen_world(s), s
        try:
            row = fastsim.run_episode(W, cfg, t, regime)
        except Exception as e:                                   # noqa: BLE001
            import traceback
            traceback.print_exc()
            row = dict(success="", why="EXC " + repr(e)[:80])
        row.update(world=str(s), kind=W["kind"], npeople=(W["crowd"] or {}).get("n", 0), trial=t, config=cfg)
        w.writerow(row)
        f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--configs", nargs="+")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument("--regime", default="champ")
    ap.add_argument("--crowd-only", action="store_true")
    ap.add_argument("--crowd-model", default="base", choices=["base", "helb", "mous"])
    a = ap.parse_args()
    lo, hi = (int(v) for v in a.seeds.split("-"))
    assert hi < 1000, "chi DEV"
    import fastsim
    import multiprocessing as mp
    import glob
    os.makedirs(a.out, exist_ok=True)
    json.dump(dict(suite="gen", seeds=a.seeds, regime=a.regime, oracle=False, crowd_model=a.crowd_model, crowd_only=a.crowd_only,
                   trials=1, pred=PATHS), open(os.path.join(a.out, "meta.json"), "w"))
    seeds = [s for s in range(lo, hi + 1) if not a.crowd_only or fastsim.gen_world(s)["crowd"]]
    done = {(r["world"], r["config"]) for f in glob.glob(a.out + "/w*.csv") for r in csv.DictReader(open(f))}
    ch = [[] for _ in range(a.jobs)]
    for k, s in enumerate(seeds):
        ch[k % a.jobs] += [(s, 0, c) for c in a.configs if (str(s), c) not in done]
    with mp.get_context("spawn").Pool(a.jobs) as p:
        p.map(work, [(c, a.out, i, a.regime, a.crowd_model) for i, c in enumerate(ch)])


if __name__ == "__main__":
    main()
