#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fit_real.py - khop mo hinh dong hoc van toc tu du lieu sysid_real.py va so du doan tren tap CHUA DUNG.

  python fit_real.py --fit s1_fit.npz s2_fit.npz --test s1_test.npz s2_test.npz --scale 1.215 --out fit.yaml
  (--lidar f.npz: quy dao lidar_odo.py cung thu tu voi --test: so quang duong voi LiDAR thay vi odom x scale)

Mo hinh moi truc i:  v_ss = s_i tanh(g_i u_i / s_i)  (x lui: g nhan 'back', s rieng 1/cxb; |u|<db -> 0)
                     dv/dt = clip((v_ss - v)/tau_i, +-a_i);   u tre d giay;   vy_do = vy + xoff*wz
Thang mo hinh M0..M5; CHON bang kiem cheo trong tap fit, BAO so tren tap test.
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import argparse
import json
import math

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import butter, sosfiltfilt

H = .02
FC = 3.0            # Hz: loc pha khong, AP DUNG GIONG NHAU cho do va mo phong
NAMES = ["gx", "gy", "gw", "taux", "tauy", "tauw", "d", "back", "cx", "cy", "cw", "ax", "ay", "aw", "xoff", "dbx", "cxb"]
#                                                                  c = 1/s
DEF = dict(gx=1, gy=1, gw=1, taux=1e-3, tauy=1e-3, tauw=1e-3, d=0.0, back=1, cx=0, cy=0, cw=0, ax=50, ay=50, aw=100, xoff=0, dbx=0, cxb=0)
LO = dict(gx=.2, gy=.2, gw=.2, taux=.01, tauy=.01, tauw=.01, d=0, back=.4, cx=0, cy=0, cw=0, ax=.4, ay=.3, aw=.8, xoff=-.3, dbx=0, cxb=0)
HI = dict(gx=2, gy=2, gw=2, taux=1.2, tauy=1.2, tauw=1.2, d=.45, back=2.2, cx=5, cy=6, cw=3, ax=12, ay=12, aw=30, xoff=.3, dbx=.12, cxb=5)
X0 = dict(gx=.9, gy=.9, gw=.9, taux=.25, tauy=.25, tauw=.2, d=.1, back=1, cx=.3, cy=.5, cw=.2, ax=4, ay=4, aw=10, xoff=0, dbx=.01, cxb=.3)
LADDER = {"M0 v=lenh": [], "M1 he so": ["gx", "gy", "gw"], "M2 +bac1": ["gx", "gy", "gw", "taux", "tauy", "tauw"],
          "M3 +tre": ["gx", "gy", "gw", "taux", "tauy", "tauw", "d"],
          "M4 +bao hoa,lui,xoff": ["gx", "gy", "gw", "taux", "tauy", "tauw", "d", "back", "cx", "cxb", "cy", "cw", "xoff"],
          "M5 +gia toc": ["gx", "gy", "gw", "taux", "tauy", "tauw", "d", "back", "cx", "cxb", "cy", "cw", "xoff", "ax", "ay", "aw"],
          "M6 +vung chet": ["gx", "gy", "gw", "taux", "tauy", "tauw", "d", "back", "cx", "cxb", "cy", "cw", "xoff", "ax", "ay", "aw", "dbx"]}
W = np.array([1 / .05, 1 / .05, 1 / .10])
SOS = butter(2, FC, fs=1 / H, output="sos")


class Run:
    def __init__(self, path, scale, t_cut=None):
        Z = np.load(path, allow_pickle=False)
        c, o = Z["cmd"], Z["odom"]
        o = o[np.argsort(o[:, 0])]
        o = o[np.concatenate([[True], np.diff(o[:, 0]) > 1e-6])]
        # thoi gian odom: dung dau thoi gian NHAN (cung dong ho voi lenh), khu rung bang khop voi stamp cua robot
        st = o[:, 2]; off = o[:, 0] - st
        base = np.percentile(off, 5)
        if np.std(off) < 5 and abs(np.polyfit(st - st[0], off, 1)[0]) < 1e-3:
            drift = np.polyfit(st - st[0], off, 1)
            to = st + base + drift[0] * (st - st[0])
        else:
            to = o[:, 0]
        o = o[np.concatenate([[True], np.diff(to) > 1e-6])]; to = to[np.concatenate([[True], np.diff(to) > 1e-6])]
        self.path, self.name = path, os.path.basename(path)
        t0, t1 = max(c[0, 0], to[0]) - .0, min(c[-1, 0], to[-1])
        self.t = np.arange(t0 + .5, t1, H)
        v = np.stack([np.interp(self.t, to, o[:, j]) for j in (10, 11, 15)], 1) * [scale, scale, 1]
        yaw = np.unwrap(np.arctan2(2 * (o[:, 9] * o[:, 8] + o[:, 6] * o[:, 7]), 1 - 2 * (o[:, 7] ** 2 + o[:, 8] ** 2)))
        self.pose = np.stack([np.interp(self.t, to, o[:, 3]) * scale, np.interp(self.t, to, o[:, 4]) * scale, np.interp(self.t, to, yaw)], 1)
        self.v = sosfiltfilt(SOS, v, axis=0)
        # tich phan lenh (giu bac 0) -> trung binh tren [t-H-d, t-d]; muot theo d
        tc = np.concatenate([c[:, 0], [c[-1, 0] + 60]])
        self.tc, self.I = np.concatenate([[tc[0] - 60], tc]), np.vstack([np.zeros((2, 3)), np.cumsum(c[:, 1:] * np.diff(tc)[:, None], 0)])
        self.vraw = v

    def ucmd(self, d):
        f = lambda x: np.stack([np.interp(x, self.tc, self.I[:, k]) for k in range(3)], 1)
        return (f(self.t - d) - f(self.t - H - d)) / H


def sim(run, TH, v0=None, idx=None):
    """TH: (B,17) -> (T,B,3) van toc DO DUOC du doan. idx=(i0,n): chay tu i0, n buoc voi v0 (B,3)."""
    B = len(TH)
    q = {n: TH[:, k] for k, n in enumerate(NAMES)}
    ds, inv = np.unique(q["d"], return_inverse=True)
    U = np.stack([run.ucmd(x) for x in ds], 1)[:, inv]                          # (T,B,3)
    if idx is not None:
        U = U[idx[0]:idx[0] + idx[1]]
    g = np.stack([q["gx"], q["gy"], q["gw"]], 1); c = np.stack([q["cx"], q["cy"], q["cw"]], 1)
    tau = np.stack([q["taux"], q["tauy"], q["tauw"]], 1); a = np.stack([q["ax"], q["ay"], q["aw"]], 1)
    G = np.where(U[..., :1] < 0, 1, 0) * (q["back"] - 1)[None, :, None] + 1
    Ux = U.copy()
    Ux[..., 0] = np.sign(U[..., 0]) * np.maximum(np.abs(U[..., 0]) - q["dbx"], 0)
    z = g * Ux; z[..., 0] *= G[..., 0]
    C = np.broadcast_to(c, z.shape).copy()
    C[..., 0] = np.where(U[..., 0] < 0, q["cxb"], C[..., 0])           # bao hoa lui rieng
    cz = np.maximum(C, 1e-6)
    ss = np.where(C < 1e-4, z, np.tanh(cz * z) / cz)
    al = 1 - np.exp(-H / tau); lim = a * H
    v = np.zeros((B, 3)) if v0 is None else v0.copy()
    out = np.empty_like(ss)
    for k in range(len(ss)):
        v = v + np.clip(al * (ss[k] - v), -lim, lim)
        out[k] = v
    out[..., 1] += q["xoff"] * out[..., 2]
    return out


def vec(free, x):
    th = np.array([DEF[n] for n in NAMES], float)
    for n, val in zip(free, x):
        th[NAMES.index(n)] = val
    return th


def residual(runs, free, X):
    """X (B, nf) -> (N, B)"""
    TH = np.stack([vec(free, x) for x in X])
    return [np.transpose(((sosfiltfilt(SOS, sim(r, TH), axis=0) - r.v[:, None]) * W), (0, 2, 1))[::3] for r in runs]   # list (T',3,B)


def fit(runs, free, x0=None):
    if not free:
        r = np.concatenate([q.reshape(-1, q.shape[-1]) for q in residual(runs, free, [[]])])
        return np.zeros(0), r[:, 0], None
    lo, hi = np.array([LO[n] for n in free]), np.array([HI[n] for n in free])
    x0 = np.array([X0[n] for n in free]) if x0 is None else x0
    flat = lambda X: np.concatenate([q.reshape(-1, q.shape[-1]) for q in residual(runs, free, X)])
    hstep = np.maximum(1e-3, 1e-3 * (hi - lo))

    def jac(x):
        s = np.where(x + hstep > hi, -hstep, hstep)
        R = flat(np.vstack([x] + [x + s[k] * np.eye(len(x))[k] for k in range(len(x))]))
        return (R[:, 1:] - R[:, :1]) / s

    best = None
    for k in range(3 if "d" in free else 1):                     # nhieu diem dau theo tre
        xs = x0.copy()
        if "d" in free:
            xs[free.index("d")] = (.05, .15, .28)[k]
        s = least_squares(lambda x: flat([x])[:, 0], xs, jac=jac, bounds=(lo, hi), loss="soft_l1", x_scale=hi - lo, max_nfev=40)
        if best is None or s.cost < best.cost:
            best = s
    return best.x, flat([best.x])[:, 0], jac(best.x)


def ci(runs, free, x, nb=300, blk=3.0, seed=0):
    """bootstrap theo khoi 3 s, mot buoc Gauss-Newton quanh nghiem (tuyen tinh hoa)."""
    lo, hi = np.array([LO[n] for n in free]), np.array([HI[n] for n in free])
    hs = np.maximum(1e-3, 1e-3 * (hi - lo)); s = np.where(x + hs > hi, -hs, hs)
    R = residual(runs, free, np.vstack([x] + [x + s[k] * np.eye(len(x))[k] for k in range(len(x))]))
    A, b = [], []
    n = int(blk / (3 * H))
    for q in R:
        for k in range(0, len(q) - n // 2, n):
            Q = q[k:k + n].reshape(-1, q.shape[-1]); J = (Q[:, 1:] - Q[:, :1]) / s; r = Q[:, 0]
            w = 1 / np.sqrt(1 + r * r)
            A.append((J * w[:, None]).T @ J); b.append((J * w[:, None]).T @ r)
    A, b = np.array(A), np.array(b)
    rg = np.random.default_rng(seed); out = []
    reg = np.diag(1e-3 / (hi - lo) ** 2)
    for _ in range(nb):
        i = rg.integers(0, len(A), len(A))
        out.append(np.clip(x - np.linalg.solve(A[i].sum(0) + reg, b[i].sum(0)), lo, hi))
    return np.percentile(out, [2.5, 97.5], axis=0)


def openloop(run, th, horizons=(1.0, 2.0, 3.0), ref=None):
    """du doan ho: tu v do (da loc) tai t0, lenh that -> dich chuyen than sau h giay; so voi pose do."""
    P = run.pose if ref is None else ref
    n = int(max(horizons) / H)
    E = {h: [] for h in horizons}
    for i in range(int(1 / H), len(run.t) - n - 1, int(.5 / H)):
        if np.abs(run.ucmd(0.0)[i:i + n]).sum() * H < .05:
            continue
        v0 = run.v[i].copy(); v0[1] -= th[NAMES.index("xoff")] * v0[2]
        # trang thai tre: lenh truoc do duoc ucmd(d) lo san
        v = sim(run, th[None], v0[None], (i, n))[:, 0]
        x = np.zeros(3)
        for k in range(n):
            c, s = math.cos(x[2]), math.sin(x[2])
            x = x + H * np.array([c * v[k, 0] - s * v[k, 1], s * v[k, 0] + c * v[k, 1], v[k, 2]])
            for h in horizons:
                if k == int(h / H) - 1:
                    d = P[i + k + 1] - P[i]; c0, s0 = math.cos(P[i, 2]), math.sin(P[i, 2])
                    E[h].append((x[0] - (c0 * d[0] + s0 * d[1]), x[1] - (-s0 * d[0] + c0 * d[1]), x[2] - d[2]))
    return {h: np.array(e).reshape(-1, 3) for h, e in E.items()}


def summ(E):
    p = np.hypot(E[:, 0], E[:, 1])
    return dict(n=len(E), pos_rmse_m=round(float(np.sqrt((p ** 2).mean())), 4), pos_p95_m=round(float(np.percentile(p, 95)), 4),
                yaw_rmse_rad=round(float(np.sqrt((E[:, 2] ** 2).mean())), 4))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", nargs="+", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--lidar", nargs="*", default=[])
    ap.add_argument("--scale", type=float, default=1.215, help="m that / m odom tho (do tu LiDAR/thuoc)")
    ap.add_argument("--full", action="store_true", help="bao tham so M5 bat ke kiem cheo (de kiem bo khop)")
    ap.add_argument("--quick", action="store_true", help="chi M0, M1, M3, M5")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if set(os.path.realpath(f) for f in a.fit) & set(os.path.realpath(f) for f in a.test):
        raise SystemExit("tap test trung tap fit")
    F, T = [Run(f, a.scale) for f in a.fit], [Run(f, a.scale) for f in a.test]
    # kiem cheo trong tap fit: 2 nua thoi gian cua moi ban ghi
    def half(r, k):
        q = Run.__new__(Run); q.__dict__.update(r.__dict__); m = len(r.t) // 2; s = slice(0, m) if k == 0 else slice(m, None)
        q.t, q.v, q.pose = r.t[s], r.v[s], r.pose[s]; return q
    A, B = [half(r, 0) for r in F], [half(r, 1) for r in F]
    res, xp = {}, None
    for name, free in LADDER.items():
        if a.quick and name[:2] not in ("M0", "M1", "M3", "M5"):
            continue
        x0 = None if xp is None else np.array([dict(zip(*xp)).get(n, X0[n]) for n in free])
        cv = 0
        for tr, te in ((A, B), (B, A)):
            x, _, _ = fit(tr, free, x0)
            rr = np.concatenate([q.reshape(-1) for q in residual(te, free, [x])]); cv += float((rr ** 2).mean()) / 2
        x, r, _ = fit(F, free, x0)
        th = vec(free, x)
        rt = np.concatenate([q[:, :, 0] for q in residual(T, free, [x])])
        E = {h: np.concatenate([openloop(q, th)[h] for q in T]) for h in (1.0, 2.0, 3.0)}
        res[name] = dict(free=free, x=x, cv=cv, fit_rmse=float(np.sqrt((r ** 2).mean())),
                         test_v_rmse=[round(float(v), 4) for v in np.sqrt((rt ** 2).mean(0)) / W], open={h: summ(e) for h, e in E.items()})
        if free:
            xp = (free, x)
        print("%-22s cv %.3f | v test RMSE (x y w) %s | du doan ho test 1/2/3 s: %s m, yaw %s rad" % (
            name, cv, res[name]["test_v_rmse"], [res[name]["open"][h]["pos_rmse_m"] for h in (1., 2., 3.)], [res[name]["open"][h]["yaw_rmse_rad"] for h in (1., 2., 3.)]), flush=True)
    best = min(res, key=lambda k: res[k]["cv"])
    # don gian nhat trong vong 1 % cua tot nhat
    ch = next(k for k in res if res[k]["cv"] <= 1.01 * res[best]["cv"])
    if a.full:
        ch = "M5 +gia toc"
    R = res[ch]
    C = ci(F, R["free"], R["x"]) if R["free"] else None
    print("CHON:", ch)
    P = {}
    for k, n in enumerate(R["free"]):
        at = "  <- CHAM BIEN, khong nhan dang duoc" if min(abs(R["x"][k] - LO[n]), abs(R["x"][k] - HI[n])) < 1e-3 * (HI[n] - LO[n]) else ""
        if C[1, k] - C[0, k] < 1e-6:
            at = "  <- du lieu khong cham toi (dao ham 0), khong nhan dang duoc"
        wide = "  <- CI rong" if (C[1, k] - C[0, k]) > .5 * (HI[n] - LO[n]) else ""
        P[n] = dict(value=round(float(R["x"][k]), 4), ci95=[round(float(v), 4) for v in C[:, k]])
        print("  %-5s %.3f  [%.3f, %.3f]%s%s" % (n, R["x"][k], C[0, k], C[1, k], at, wide))
    # nen nhieu (lac than): do lech van toc tho sau khi tru du doan khi dang di
    W_ = []
    for r in T:
        pr = sim(r, vec(R["free"], R["x"])[None])[:, 0]
        W_.append(r.vraw - pr)
    W_ = np.concatenate(W_).std(0)
    print("du tho (gom lac than) std vx vy wz:", np.round(W_, 3))
    out = dict(model=ch, scale=a.scale, params=P, residual_std=[round(float(v), 4) for v in W_],
               ladder={k: dict(cv=round(v["cv"], 4), test_v_rmse=v["test_v_rmse"], open={str(h): e for h, e in v["open"].items()}) for k, v in res.items()})
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)
    return out


if __name__ == "__main__":
    main()
