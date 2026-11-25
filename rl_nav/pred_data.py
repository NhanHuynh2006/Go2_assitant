#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/pred_data.py — sinh du lieu cho BO DU DOAN NGUOI ngan han (nav_pred.py).

Nguoi: luat Social Force cua movers.Crowd (tham so doi duoc de thu NGOAI phan bo), cam bien + BlobTracker
+ ban do THAT cua fastsim.Sim (nhieu, che khuat, tre, dut track y nhu luc chay). Robot chay kich ban
(pure pursuit toi cac diem ngau nhien), KHONG dung bo ne nao -> du lieu khong phu thuoc bo ne.

Seed nguoi = 5000 + k (khong trung DEV 0-999, VAL 2000-2399; TEST >= 100000 CAM).
Ban do gen_world: train 300-799, val 800-999, test 0-299.

  venv/bin/python rl_nav/pred_data.py --set train --variant default --eps 700 --seed0 5000 --out .../train_default.npz
"""
import argparse
import math
import os
import sys
import types

for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_k] = "1"
import numpy as np

ROOT = os.environ.get("PRED_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # nav_pred
sys.path.insert(0, ROOT)                                                             # code da chup: uu tien
import fastsim  # noqa: E402
import random  # noqa: E402

DEFAULT = dict(Aw=2.0, Bw=.12, Ap=2.1, Bp=.3, Ar=1.5, Br=.4, tau=.5, noise=.15, lam=.35, v0=.9, sv=.15, vlo=.6,
               vhi=1.2, wlo=.5, whi=3.0, distracted=.3, plan="astar", hazard=0.0, model="sf")
# bien the NGOAI phan bo (chi test). "train_rand": ngau nhien hoa vua phai (khong trum cac muc o duoi)
VARIANTS = {
    "default": {},
    "fast": dict(v0=1.4, sv=.1, vlo=1.25, vhi=1.6),
    "slow": dict(v0=.45, sv=.05, vlo=.35, vhi=.55),
    "distracted1": dict(distracted=1.0),
    "distracted0": dict(distracted=0.0, Ar=4.0, Br=.6),          # ai cung ne robot manh
    "AB_strong": dict(Aw=4.0, Bw=.25, Ap=4.5, Bp=.5),
    "AB_weak": dict(Aw=1.0, Bw=.06, Ap=.7, Bp=.15),
    "agile": dict(tau=.2, noise=.4),                             # doi huong gan nhu tuc thi, lac
    "straight": dict(plan="straight"),                           # dich gan, di thang (khong A*)
    "orca": dict(model="orca"),                                  # mo hinh KHAC han (ORCA, giai bang lay mau)
    "mous2009": dict(model="mous"),                              # Moussaid et al. 2009, tham so cong bo
    "helb2000": dict(model="helb"),                              # Helbing-Farkas-Vicsek 2000: 25 m/s2, B 0.08, tuong 25/0.08
    "wander": dict(model="wander"),                              # khong dich, khong A*: huong OU + lat huong ngau nhien
    "sudden": dict(hazard=.35),                                  # doi y bat chot giua duong: ~0.35 lan/s
}


def rand_params(rng):
    u = rng.uniform
    return dict(DEFAULT, Aw=u(1.5, 2.6), Bw=u(.09, .16), Ap=u(1.4, 2.9), Bp=u(.2, .4), Ar=u(.8, 2.4), Br=u(.25, .5),
                tau=u(.35, .65), noise=u(.08, .25), lam=u(.2, .5), v0=u(.7, 1.1), vlo=.5, vhi=1.25, distracted=u(.1, .6),
                hazard=rng.choice([0, 0, .05, .12]))


def make_crowd(base):
    class C(base):
        def set_params(self, q):
            self.q = q
            for p in self.people:
                p["v0"] = min(q["vhi"], max(q["vlo"], self.rng.gauss(q["v0"], q["sv"])))
                p["distracted"] = self.rng.random() < q["distracted"]

        def _new_goal(self, pp):
            if self.q["plan"] == "astar":
                return super()._new_goal(pp)
            for _ in range(40):                                  # dich nhin thay duoc, cach 1.5-5 m
                g = np.array(self._free_point())
                d = g - pp["p"]
                L = np.linalg.norm(d)
                if 1.5 < L < 5.0 and self.bx.sd(pp["p"] + d * np.linspace(.1, 1, 12)[:, None]).min() > .3:
                    break
            pp["path"] = [g]

        # ------------------------------------------------ cac mo hinh nguoi KHAC (khong bao gio dung de train)
        def _walk(self, pp, dt):
            """muc tieu chung: tra ve (huong e) hoac None neu dang nghi / vua toi"""
            q = self.q
            if pp["wait"] > 0:
                pp["wait"] -= dt
                pp["v"] = pp["v"] * .5
                return None
            if not pp["path"]:
                self._new_goal(pp)
            to = pp["path"][0] - pp["p"]
            dist = math.hypot(*to)
            if dist < .3:
                pp["path"].pop(0)
                if not pp["path"]:
                    pp["wait"] = self.rng.uniform(q["wlo"], q["whi"])
                return None
            return to / (dist + 1e-9)

        def step_other(self, dt):
            q = self.q
            m = q["model"]
            rp = np.array(self.sim.x[:2])
            c, s = math.cos(self.sim.x[2]), math.sin(self.sim.x[2])
            vb = getattr(self.sim, "v", np.zeros(3))
            rv = np.array([c * vb[0] - s * vb[1], s * vb[0] + c * vb[1]])
            for i, pp in enumerate(self.people):
                d, n = self._wall_dist(*pp["p"])
                if m == "wander":
                    if pp["wait"] > 0:
                        pp["wait"] -= dt
                        pp["v"] = pp["v"] * .5
                        continue
                    if self.rng.random() < .06 * dt:
                        pp["wait"] = self.rng.uniform(.5, 3)
                    h = pp.setdefault("h", self.rng.uniform(-3.1, 3.1))
                    h += self.rng.gauss(0, .5) * math.sqrt(dt)
                    if self.rng.random() < .25 * dt:
                        h += self.rng.uniform(-2, 2)
                    e = np.array([math.cos(h), math.sin(h)])
                    if d < .6 and e @ n < 0:                       # gap tuong: truot doc tuong roi quay ra
                        t = np.array([-n[1], n[0]])
                        t = t if t @ e > 0 else -t
                        e = t + .4 * n
                        e /= math.hypot(*e)
                        h = math.atan2(e[1], e[0])
                    pp["h"] = h
                else:
                    e = self._walk(pp, dt)
                    if e is None:
                        continue
                nb = [(o["p"], o["v"], o["r"]) for j, o in enumerate(self.people) if j != i]
                if not pp["distracted"]:
                    nb = nb + [(rp, rv, .35)]
                if m == "orca":
                    pp["v"] = self._orca(pp, e, nb, d, n, dt)
                    pp["p"] = pp["p"] + pp["v"] * dt
                    continue
                f = (pp["v0"] * e - pp["v"]) / .5
                Aw, Bw = dict(mous=(10., .2), helb=(25., .08), wander=(2., .12))[m]
                f = f + Aw * math.exp((pp["r"] - d) / Bw) * n + (120. * (pp["r"] - d) * n if d < pp["r"] else 0)
                for (qp, qv, qr) in nb:
                    diff = pp["p"] - qp
                    dd = math.hypot(*diff) + 1e-9
                    nij = diff / dd
                    if m == "mous":
                        eij = -nij
                        D = 2. * (pp["v"] - qv) + eij
                        Dn = math.hypot(*D) + 1e-9
                        t = D / Dn
                        th = math.atan2(t[0] * eij[1] - t[1] * eij[0], float(t @ eij))
                        B = .35 * Dn
                        f = f + 4.5 * (-math.exp(-dd / B - (3 * B * th) ** 2) * t
                                       - np.sign(th) * math.exp(-dd / B - (2 * B * th) ** 2) * np.array([-t[1], t[0]]))
                    elif m == "helb":
                        f = f + min(60., 25. * math.exp((pp["r"] + qr - dd) / .08)) * nij
                    else:
                        f = f + 2.1 * math.exp((pp["r"] + qr - dd) / .3) * nij
                    if dd < pp["r"] + qr:
                        f = f + 120. * (pp["r"] + qr - dd) * nij
                f = f + np.array([self.rng.gauss(0, .15), self.rng.gauss(0, .15)])
                pp["v"] = pp["v"] + f * dt
                sp = math.hypot(*pp["v"])
                if sp > 1.3 * pp["v0"]:
                    pp["v"] = pp["v"] * 1.3 * pp["v0"] / sp
                pp["p"] = pp["p"] + pp["v"] * dt

        def _orca(self, pp, e, nb, d, n, dt, tau=2.0):
            """ORCA (van den Berg 2011): nua mat phang cho tung lang gieng (trach nhiem 1/2) + tuong; QP giai bang lay mau."""
            v = pp["v"]
            vmax = 1.3 * pp["v0"]
            pref = pp["v0"] * e
            th = np.arange(32) * (2 * math.pi / 32)
            C = np.concatenate([[pref, v * .9, [0., 0.]]] + [s_ * pp["v0"] * np.stack([np.cos(th), np.sin(th)], 1)
                                                             for s_ in (.35, .7, 1.0, 1.25)])
            viol = np.zeros(len(C))
            for (qp, qv, qr) in nb:
                p = qp - pp["p"]
                D = math.hypot(*p)
                r = pp["r"] + qr + .05
                if D > 5.0:
                    continue
                w = (v - qv) - p / tau
                rel = v - qv
                if D <= r:
                    nn, u = -p / (D + 1e-9), (r - D) / .3 * (-p / (D + 1e-9))
                else:
                    wl = math.hypot(*w) + 1e-9
                    dot = float(w @ p)
                    if dot < 0 and dot * dot > r * r * wl * wl:              # vong tron cat
                        nn = w / wl
                        u = (r / tau - wl) * nn
                    else:                                                     # hai canh hinh non
                        leg = math.sqrt(D * D - r * r)
                        if p[0] * w[1] - p[1] * w[0] > 0:
                            dr = np.array([p[0] * leg - p[1] * r, p[0] * r + p[1] * leg]) / (D * D)
                        else:
                            dr = -np.array([p[0] * leg + p[1] * r, -p[0] * r + p[1] * leg]) / (D * D)
                        u = float(rel @ dr) * dr - rel
                        nn = u / (math.hypot(*u) + 1e-9)
                        nn = np.array([-dr[1], dr[0]])
                viol += np.maximum(-((C - (v + .5 * u)) @ nn), 0)
            viol += 3 * np.maximum(-(C @ n) - max(d - pp["r"], 0) / .7, 0)
            k = int((np.hypot(*(C - pref).T) + 20 * viol).argmin())
            nv = C[k] + np.array([self.rng.gauss(0, .03), self.rng.gauss(0, .03)])
            dv = nv - v
            a = math.hypot(*dv)
            return v + dv * min(1.0, 4.0 * dt / (a + 1e-9))

        def step(self, dt):                                      # = movers.Crowd.step voi tham so self.q
            q = self.q
            if q["model"] != "sf":
                return self.step_other(dt)
            robots = [r.map_pose() for r in self.robots]
            for i, pp in enumerate(self.people):
                if pp["wait"] > 0:
                    pp["wait"] -= dt
                    pp["v"] *= 0.5
                    continue
                if not pp["path"]:
                    self._new_goal(pp)
                elif q["hazard"] and self.rng.random() < q["hazard"] * dt:
                    self._new_goal(pp)
                tgt = pp["path"][0]
                to = tgt - pp["p"]
                dist = math.hypot(*to)
                if dist < 0.3:
                    pp["path"].pop(0)
                    if not pp["path"]:
                        pp["wait"] = self.rng.uniform(q["wlo"], q["whi"])
                    continue
                e = to / (dist + 1e-9)
                f = (pp["v0"] * e - pp["v"]) / q["tau"]
                d, n = self._wall_dist(*pp["p"])
                f = f + q["Aw"] * math.exp((pp["r"] - d) / q["Bw"]) * n
                if d < pp["r"]:
                    f = f + 120.0 * (pp["r"] - d) * n

                def social(o, A, B, rq):
                    diff = pp["p"] - o
                    dd = math.hypot(*diff) + 1e-9
                    nij = diff / dd
                    w = q["lam"] + (1 - q["lam"]) * (1 - float(nij @ e)) / 2
                    out = A * math.exp((pp["r"] + rq - dd) / B) * nij * w
                    if dd < pp["r"] + rq:
                        out = out + 120.0 * (pp["r"] + rq - dd) * nij
                    return out
                for j, qq in enumerate(self.people):
                    if j != i:
                        f = f + social(qq["p"], q["Ap"], q["Bp"], qq["r"])
                if not pp["distracted"]:
                    for rp in robots:
                        f = f + social(np.array(rp[:2]), q["Ar"], q["Br"], 0.35)
                f = f + np.array([self.rng.gauss(0, q["noise"]), self.rng.gauss(0, q["noise"])])
                pp["v"] = pp["v"] + f * dt
                sp = math.hypot(*pp["v"])
                if sp > 1.3 * pp["v0"]:
                    pp["v"] *= 1.3 * pp["v0"] / sp
                pp["p"] = pp["p"] + pp["v"] * dt
    return C


class RecSim(fastsim.Sim):
    """fastsim.Sim nhung khong dung khi cham, robot chay kich ban."""

    def check(self):
        pass


def geofan(G, o, v, field, meta, rob, now):
    """Quat y dinh trac dia cua ALGO (nav_prism2.GeoFan, nhu PRISM3.geo_cost) -> (16,24,2) | None. Chi de so sanh."""
    tt = np.arange(1, 25) * .1
    sp = math.hypot(*v)
    G.build(field, meta, rob, now)
    if sp < .2:
        return G.fan(tuple(o), None, .8, np.maximum(tt - .7, 0))
    past = None
    for L in (1.0, .6):
        past = (o[0] - L * v[0] / sp, o[1] - L * v[1] / sp)
        if G.node(*past) is not None:
            break
    return G.fan(tuple(o), past, max(sp, .5), tt)


def feats(tr, hist, now, robot, rv, others, field, meta, last):
    """Dac trung THO cua 1 track (dung chung luc chay that: nav_pred.features)."""
    import nav_pred
    return nav_pred.features(tr, hist, now, robot, rv, others, field, meta, last)


def episode(wseed, pseed, q, T=40.0, rng=None, trk3=False, fan=False):
    import nav_pred
    from nav_local import obstacle_field, plan
    W = dict(fastsim.gen_world(wseed))
    bx = W["bounds"]
    reg = ((bx[0] + 1.8, bx[0] + bx[2] - 1.8), (bx[1] + 1.8, bx[1] + bx[3] - 1.8))
    W["crowd"] = dict(n=rng.randint(2, 7), region=reg, seed=pseed, distracted=q["distracted"])
    W["seed"] = pseed                                              # nhieu cam bien rieng
    fastsim.CLOCK.sim, fastsim.CLOCK.t = None, 100.0
    sim = RecSim(W, "mppi~t3" if trk3 else "mppi", 0)
    C = sim.crowd
    C.robots = [types.SimpleNamespace(map_pose=lambda: tuple(sim.x))]
    C.set_params(q)
    for _ in range(60):
        C.step(.05)
    r = sim.r
    vmx, polite = rng.uniform(.2, .6), rng.random() < .5
    path, pause, store = [], 0.0, nav_pred.History()
    n_tick, truth, samples = int(T / .1), [], []
    field = meta = None
    from nav_prism2 import GeoFan
    G = GeoFan()
    prevx = sim.x.copy()
    vest = np.zeros(2)
    n_mov = n_false = 0
    last_s = {}
    for k in range(n_tick):
        # ---- robot kich ban
        if pause > 0:
            pause -= .1
            sim.cmd = np.zeros(3)
        else:
            if not path:
                g = C._free_point()
                pts, _ = plan(C.grid, tuple(sim.x[:2]), g, lethal=.4, soft=.7, smooth_path=False)
                path = [np.array(p) for p in (pts or [])][1:]
                if not path:
                    pause = .5
            else:
                d = path[0] - sim.x[:2]
                if math.hypot(*d) < .3:
                    path.pop(0)
                    if not path and rng.random() < .5:
                        pause = rng.uniform(0, 3)
                else:
                    e = math.atan2(d[1], d[0]) - sim.x[2]
                    e = math.atan2(math.sin(e), math.cos(e))
                    sim.cmd = np.array([vmx * max(0, math.cos(e)) ** 2, 0, np.clip(1.5 * e, -1, 1)])
                    if polite and any(math.hypot(*(p["p"] - sim.x[:2])) < .9 for p in C.people):
                        sim.cmd = np.zeros(3)
        sub = []
        for _ in range(2):                                         # 2 x 0.05 s, ghi su that 20 Hz
            sim.advance(.05)
            sub.append(np.array([[*p["p"], *p["v"]] for p in C.people]))
        truth += sub
        now = sim.clock.t
        vest = .7 * vest + .3 * (sim.x[:2] - prevx[:2]) / .1
        prevx = sim.x.copy()
        mov = r.tracker.movers()
        store.update(r.tracker.tracks, now, mov)
        if k % 2 == 0:
            field = obstacle_field(r.grid, [r.depth_grid])
            meta = (r.grid.res, r.grid.x0, r.grid.y0)
        ppl = store.people(r.tracker.tracks, mov)
        for tr in ppl:
            n_mov += 1
            # su that: nguoi gan nhat tam track luc THAY (tr.t)
            cur = truth[-1]
            dd = np.hypot(*(cur[:, :2] - (tr["p"] + tr["v"] * (now - tr["t"]))).T)
            j = int(dd.argmin())
            if dd[j] > .6:
                n_false += 1
                continue
            if now - last_s.get(id(tr), -9) < .25 or math.hypot(*(cur[j, :2] - sim.x[:2])) < .5:
                continue
            last_s[id(tr)] = now
            oth = [o for o in ppl if o is not tr]
            fq = None
            if fan:
                o_ = tr["p"] + tr["v"] * min(now - tr["t"], .5)
                fq = geofan(G, o_, tr["v"], field, meta, sim.x[:2], now)
                fq = np.full((16, 24, 2), np.nan) if fq is None else np.asarray(fq) - o_
            samples.append((len(truth) - 1, j, dict(p=tr["p"].copy(), v=tr["v"].copy(), t=tr["t"], now=now),
                            feats(tr, store.get(tr), now, sim.x, vest, oth, field, meta, store.meta(tr)), sim.x[:2].copy(), vest.copy(),
                            store.get(tr)[-12:].copy(), fq))
    truth = np.array(truth)                                         # (N,20Hz,P,4)
    out = []
    H = nav_pred.T * 2                                              # 2.4 s = 48 buoc 20 Hz
    for k, j, tr, f, rx, rv, hist, fq in samples:
        if k + H >= len(truth) or k < 10:
            continue
        fut = truth[k + 2:k + H + 1:2, j]                          # (24,4) 0.1 s
        h = np.full((12, 3), np.nan)
        h[-len(hist):] = hist
        out.append(dict(x=f["x"], frame=f["frame"], fut=fut[:, :2], futv=fut[:, 2:], cur=truth[k, j], p=tr["p"], v=tr["v"],
                        age=tr["now"] - tr["t"], rob=np.r_[rx, rv], hist=h - np.array([0, 0, tr["now"]])
                        if len(hist) else h))
        if fq is not None:
            out[-1]["fan"] = fq
    return out, n_mov, n_false


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", default="300-799")
    ap.add_argument("--variant", default="default", help="ten trong VARIANTS hoac rand")
    ap.add_argument("--eps", type=int, default=100)
    ap.add_argument("--seed0", type=int, default=5000)
    ap.add_argument("--T", type=float, default=40.0)
    ap.add_argument("--fan", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    assert a.seed0 >= 5000 and a.seed0 + a.eps < 100000
    fastsim.FastCrowd = make_crowd(fastsim.make_crowd_class())
    fastsim.FastCrowd.q = DEFAULT                                    # buoc khoi dong trong Sim.__init__
    lo, hi = (int(v) for v in a.worlds.split("-"))
    assert hi < 1000
    allr, nm, nf = [], 0, 0
    real_mono = fastsim.real_time.time()
    for e in range(a.eps):
        ps = a.seed0 + e
        rng = random.Random(ps * 31 + 7)
        q = rand_params(rng) if a.variant == "rand" else dict(DEFAULT, **VARIANTS[a.variant])
        fastsim.FastCrowd.q = q
        w = lo + (ps * 7) % (hi - lo + 1)
        try:
            s, m, f = episode(w, ps, q, a.T, rng, trk3=ps % 2 == 1, fan=a.fan)        # 1/2 tracker v2, 1/2 v3
        except Exception as ex:                                      # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("loi", w, ps, repr(ex))
            continue
        for d in s:
            d["ep"], d["world"], d["trk3"] = ps, w, ps % 2
        allr += s
        nm, nf = nm + m, nf + f
        if e % 50 == 0:
            print(a.out, e, len(allr), f"nham {nf}/{nm}", round(fastsim.real_time.time() - real_mono), "s", flush=True)
    keys = allr[0].keys()
    np.savez_compressed(a.out, **{k: np.array([d[k] for d in allr], np.float16 if k == "fan" else np.float32 if k not in ("ep", "world", "trk3") else int)
                                  for k in keys}, n_mov=nm, n_false=nf)
    print("XONG", a.out, len(allr), f"nham {nf}/{nm}")


if __name__ == "__main__":
    main()
