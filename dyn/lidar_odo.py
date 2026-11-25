#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lidar_odo.py - odometry LiDAR doc lap voi odom chan: ICP diem-mat phang 6 bac, quet -> ban do cuc bo
(KHONG dung tinh tien cua odom; chi lay quay tuong doi tu quaternion lam diem dau).
  python lidar_odo.py BAG.db3 CLOUD_TOPIC ODOM_TOPIC OUT.npz [--init cv|odom|zero] [--l1] [--dur S]
OUT: t (header), T (n,4,4) than trong the gioi LiDAR, eig_min/eig_max (do rang buoc tinh tien), rmse, frac.
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import argparse
import sys
import time

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rn, Slerp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio

R_L1 = np.array([[0.52611, -0.81014, 0.25862], [-0.83867, -0.54464, 0.0], [0.14085, -0.21690, -0.96598]])
T_L1 = np.array([0.2822, 0.0, 0.0])


def vox(p, s):
    if not len(p):
        return p
    _, i = np.unique(np.floor(p / s).astype(np.int64), axis=0, return_index=True)
    return p[i]


def normals(p, k=10):
    d, j = cKDTree(p).query(p, k=min(k, len(p)))
    q = p[j] - p[j].mean(1, keepdims=True)
    w, v = np.linalg.eigh(np.einsum("nki,nkj->nij", q, q))
    ok = (w[:, 0] < 0.05 * np.maximum(w[:, 1], 1e-9)) & (d[:, -1] < 2.0)
    return v[:, :, 0], ok


def expm(x):
    T = np.eye(4)
    T[:3, :3] = Rn.from_rotvec(x[3:]).as_matrix()
    T[:3, 3] = x[:3]
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag"); ap.add_argument("cloud"); ap.add_argument("odom"); ap.add_argument("out")
    ap.add_argument("--init", default="cv")
    ap.add_argument("--l1", action="store_true")
    ap.add_argument("--dur", type=float, default=1e9)
    ap.add_argument("--vmap", type=float, default=.2)
    ap.add_argument("--vsrc", type=float, default=.35)
    ap.add_argument("--rmax", type=float, default=25.0)
    a = ap.parse_args()
    od = [(m[0], *m[3], *m[4]) for _, m in bagio.read(a.bag, a.odom)]
    od = np.array(od); od = od[np.argsort(od[:, 0])]
    _, iu = np.unique(od[:, 0], return_index=True); od = od[iu]
    sl = Slerp(od[:, 0], Rn.from_quat(od[:, 4:8]))
    po = lambda t: np.array([np.interp(t, od[:, 0], od[:, k]) for k in (1, 2, 3)])

    def frames():
        if not a.l1:
            for _, (st, fr, c) in bagio.read(a.bag, a.cloud):
                yield st, np.stack([c["x"], c["y"], c["z"]], 1).astype(float)
            return
        # L1: gom ~0.25 s, bu chuyen dong trong cua so bang quay odom (tinh tien: bo qua o --init cv)
        buf, t0 = [], None
        for _, (st, fr, c) in bagio.read(a.bag, a.cloud):
            p = np.stack([c["x"], c["y"], c["z"]], 1).astype(float)
            p = p[np.linalg.norm(p, axis=1) > .05] @ R_L1.T + T_L1
            m = (np.abs(p[:, 0]) < .45) & (np.abs(p[:, 1]) < .28) & (p[:, 2] < .15) & (p[:, 2] > -.5)
            t0 = t0 or st
            buf.append((st, p[~m]))
            if st - t0 > .2:
                tm = .5 * (t0 + st)
                yield tm, np.concatenate([q for _, q in buf])
                buf, t0 = [], None

    T, ts, out, KF, last_kf = np.eye(4), [], [], [], None
    vel = np.zeros(3); tree = None; tprev = None; w0 = time.time()
    for st, p in frames():
        if st < od[0, 0] or st > od[-1, 0] or (ts and st - ts[0] > a.dur):
            continue
        r = np.linalg.norm(p, axis=1)
        p = p[(r > .6) & (r < a.rmax)]
        dense = vox(p, a.vmap)
        src = vox(dense, a.vsrc)
        if tprev is None:
            G = T.copy()
            G[:3, :3] = sl(st).as_matrix()               # can theo trong luc: xyz_the gioi ~ odom
            T = G
            q = (0, 1, 0, 0)
        else:
            dt = st - tprev
            dR = (sl(tprev).inv() * sl(st)).as_matrix()
            if a.init == "cv":
                dp = vel * dt
            elif a.init == "odom":
                dp = sl(tprev).inv().apply(po(st) - po(tprev))
            else:
                dp = np.zeros(3)
            G = T.copy(); G[:3, 3] = T[:3, 3] + T[:3, :3] @ dp; G[:3, :3] = T[:3, :3] @ dR
            for rad, it in ((1.2, 4), (.6, 4), (.35, 5)):
                for _ in range(it):
                    x = src @ G[:3, :3].T + G[:3, 3]
                    d, j = tree.query(x, distance_upper_bound=rad)
                    ok = np.isfinite(d)
                    x, m, n = x[ok], Mp[j[ok]], Mn[j[ok]]
                    e = ((x - m) * n).sum(1)
                    w = 1.0 / (1.0 + (e / .08) ** 2)
                    xc = x - G[:3, 3]
                    J = np.hstack([n, np.cross(xc, n)])
                    H = (J * w[:, None]).T @ J
                    dx = np.linalg.solve(H + 1e-6 * np.eye(6), -(J * w[:, None]).T @ e)
                    E = np.eye(4); E[:3, :3] = Rn.from_rotvec(dx[3:]).as_matrix()
                    G[:3, :3] = E[:3, :3] @ G[:3, :3]; G[:3, 3] += dx[:3]
                    if np.abs(dx).max() < 2e-4:
                        break
            Ht = (n * w[:, None]).T @ n
            ev = np.linalg.eigvalsh(Ht / max(w.sum(), 1e-9))
            # sai so chuan tinh tien doc than (theo H day du)
            C = np.linalg.inv(H + 1e-6 * np.eye(6)) * (w * e * e).sum() / max(len(e) - 6, 1)
            fx = G[:3, 0]
            q = (ev[0], ev[2], float(np.sqrt((w * e * e).sum() / max(w.sum(), 1e-9))), float(np.sqrt(fx @ C[:3, :3] @ fx)))
            # mocs LiDAR rung +-0.1 s -> van toc du doan lay tren 6 khung, khong tren 1 khung
            j0 = max(0, len(ts) - 6)
            vel = G[:3, :3].T @ (G[:3, 3] - out[j0][0][:3, 3]) / max(st - ts[j0], .08)
            T = G
        Ro, _ = np.linalg.qr(T[:3, :3]); T[:3, :3] = Ro * np.sign(np.diag(Ro.T @ T[:3, :3]))
        tprev = st; ts.append(st); out.append((T.copy(), q))
        if last_kf is None or np.linalg.norm(T[:3, 3] - last_kf[0]) > .4 or \
           Rn.from_matrix(last_kf[1].T @ T[:3, :3]).magnitude() > .2:
            nn, ok = normals(dense)
            KF.append((dense[ok] @ T[:3, :3].T + T[:3, 3], nn[ok] @ T[:3, :3].T))
            KF = KF[-30:]; last_kf = (T[:3, 3].copy(), T[:3, :3].copy())
            Mp = np.concatenate([k[0] for k in KF]); Mn = np.concatenate([k[1] for k in KF])
            _, i = np.unique(np.floor(Mp / a.vmap).astype(np.int64), axis=0, return_index=True)
            Mp, Mn = Mp[i], Mn[i]; tree = cKDTree(Mp)
        if len(ts) % 200 == 0:
            print(len(ts), "khung", round(time.time() - w0), "s; pos", np.round(T[:3, 3], 2), "map", len(Mp), "q", np.round(q, 4), flush=True)
    np.savez(a.out, t=np.array(ts), T=np.array([o[0] for o in out]), q=np.array([o[1] for o in out]), odom=od)


main()
