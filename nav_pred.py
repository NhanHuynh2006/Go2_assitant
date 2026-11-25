#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nav_pred.py — DU DOAN NGUOI ngan han (2.4 s, 24 buoc 0.1 s) nhieu mode, chi can numpy.

    H = History()                       # giu trong robot
    H.update(tracker.tracks, now, tracker.movers())       # moi nhip dieu khien
    P = Predictor()                     # rl_nav/pred_nav.npz
    tracks = H.people(tracker.tracks, tracker.movers())   # dang di + nguoi da tung di, nay DUNG
    modes = P.predict(tracks, H, now, robot_xyyaw, robot_vxy, field, meta)
    # -> moi track 1 list [(xac suat, mean (24,2) khung ban do, std (24,)), ...]

tracks: dict cua BlobTracker (p, v, t, hits). Khong co mo hinh / loi -> van toc khong doi (1 mode).
"""
import math
import os

import numpy as np

T, DT = 24, 0.1
N_HIST, N_RAY, RAY_MAX = 8, 24, 3.0
_ANG = np.arange(N_RAY) * (2 * math.pi / N_RAY)


class History:
    """Lich su vi tri THAY DUOC cua tung track (BlobTracker khong luu) + huong di cuoi + co 'da tung la nguoi di'.
    Giu tham chieu dict -> id() an toan."""

    def __init__(self, keep=1.7):
        self.h, self.keep = {}, keep

    def update(self, tracks, now, movers=()):
        mv = {id(m) for m in movers}
        new = {}
        for tr in tracks:
            old = self.h.get(id(tr))
            o = old if old is not None and old["tr"] is tr else dict(tr=tr, L=[], yaw=None, tm=-9.0, person=False)
            L = o["L"]
            if not L or tr["t"] > L[-1][2] + 1e-6:
                L.append((float(tr["p"][0]), float(tr["p"][1]), float(tr["t"])))
            while L and now - L[0][2] > self.keep:
                L.pop(0)
            if id(tr) in mv:
                o["person"] = True
                v = tr["v"]
                if math.hypot(v[0], v[1]) > 0.3:
                    o["yaw"], o["tm"] = math.atan2(v[1], v[0]), now
            new[id(tr)] = o
        self.h = new

    def get(self, tr):
        o = self.h.get(id(tr))
        return np.array(o["L"], float).reshape(-1, 3) if o is not None else np.zeros((0, 3))

    def meta(self, tr):
        o = self.h.get(id(tr))
        return (None, -9.0) if o is None else (o["yaw"], o["tm"])

    def people(self, tracks, movers):
        mv = {id(m) for m in movers}
        return list(movers) + [tr for tr in tracks if id(tr) not in mv and id(tr) in self.h and self.h[id(tr)]["person"]
                               and math.hypot(tr["v"][0], tr["v"][1]) < 0.3]


def rays(p, yaw, field, meta, start=0.35):
    """24 tia tu nguoi (khung huong di), khoang cach toi vat TINH tren truong khoang cach."""
    if field is None:
        return np.full(N_RAY, RAY_MAX)
    res, gx0, gy0 = meta
    H, W = field.shape
    th = yaw + _ANG
    dx, dy = np.cos(th) / res, np.sin(th) / res
    ox, oy = (p[0] - gx0) / res, (p[1] - gy0) / res
    t = np.full(N_RAY, start)
    for _ in range(14):
        c, r = (ox + t * dx).astype(int), (oy + t * dy).astype(int)
        ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
        d = np.where(ok, field[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)] - 0.5 * res, 9.0)
        st = np.where((d < 0.06) | (t >= RAY_MAX), 0.0, np.maximum(d, 0.08))
        if not st.any():
            break
        t = t + st
    return np.minimum(t, RAY_MAX)


def features(tr, hist, now, robot, rv, others, field, meta, last=(None, -9.0)):
    """-> dict(x (DIM,), frame (ox, oy, yaw, speed)). Khung: goc = p + v*tuoi, truc x = huong van toc track."""
    age = min(now - tr["t"], 0.5)
    v = np.asarray(tr["v"], float)
    sp = math.hypot(v[0], v[1])
    o = np.asarray(tr["p"], float) + v * age
    stand = sp < 0.2
    if stand:                                            # huong di CUOI; chua tung di: huong toi robot
        yaw = last[0] if last[0] is not None else math.atan2(robot[1] - o[1], robot[0] - o[0])
    else:
        yaw = math.atan2(v[1], v[0])
    c, s = math.cos(yaw), math.sin(yaw)
    sp = c * v[0] + s * v[1]
    R = np.array([[c, s], [-s, c]])
    hx = np.zeros((N_HIST, 4))
    h = hist[-N_HIST:]
    if len(h):
        q = (h[:, :2] - o) @ R.T
        hx[N_HIST - len(h):, 0:2] = q
        hx[N_HIST - len(h):, 2] = now - h[:, 2]
        hx[N_HIST - len(h):, 3] = 1.0
    rr = R @ (np.asarray(robot[:2], float) - o)
    rvv = R @ np.asarray(rv[:2], float)
    dr = math.hypot(rr[0], rr[1])
    rob = np.r_[rr / 3.0, rvv, math.exp(-dr), 1.0 / (0.5 + dr)]
    oth = np.zeros((2, 5))
    if others:
        L = sorted(others, key=lambda q: float(np.hypot(*(q["p"] - o))))[:2]
        for k, q in enumerate(L):
            e = R @ (np.asarray(q["p"]) + np.asarray(q["v"]) * min(now - q["t"], .5) - o)
            if math.hypot(e[0], e[1]) < 4.0:
                oth[k] = [e[0] / 3, e[1] / 3, *(R @ np.asarray(q["v"])), 1.0]
    ry = rays(o, yaw, field, meta) / RAY_MAX
    x = np.r_[hx.ravel(), sp, age, min(tr.get("hits", 3), 12) / 12.0, rob, oth.ravel(), ry, float(stand), min(now - last[1], 5.0) / 5.0 if stand else 0.0]
    return dict(x=x.astype(np.float32), frame=np.array([o[0], o[1], yaw, sp]))


KN = np.array([0.0, .3, .6, .9, 1.2, 1.6, 2.0, 2.4])                    # nut thoi gian cua dau ra
_M = np.stack([np.interp(np.arange(1, T + 1) * DT, KN, np.eye(len(KN))[j]) for j in range(len(KN))], 1)
DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rl_nav", "pred_nav.npz")


class Predictor:
    def __init__(self, path=DEFAULT_PATH):
        z = np.load(path)
        self.W = [z[f"W{i}"].astype(np.float32) for i in range(3)]
        self.b = [z[f"b{i}"].astype(np.float32) for i in range(3)]
        self.mu, self.sd, self.K = z["mu"].astype(np.float32), z["sd"].astype(np.float32), int(z["K"])
        ab = [str(a) for a in z["ablate"]] if "ablate" in z else []
        self.zero = np.ones(len(self.mu), np.float32)
        for a in ab:
            if a == "ctx":
                self.zero[:32] = 0
                self.zero[34:75] = 0
            else:
                self.zero[dict(hist=slice(0, 32), rays=slice(51, 75), robot=slice(35, 41), others=slice(41, 51))[a]] = 0

    def raw(self, X):
        """X (B,77) -> prob (B,K), mean (B,K,24,2) khung nguoi, std (B,K,24)."""
        X = np.asarray(X, np.float32) * self.zero
        x = np.clip((X - self.mu) / self.sd, -6, 6)
        for k in range(3):
            x = x @ self.W[k] + self.b[k]
            if k < 2:
                x = np.where(x > 0, x, np.expm1(np.minimum(x, 0)))
        L = len(KN)
        o = x.reshape(len(X), self.K, 3 * L + 1)
        lp = o[..., -1] - o[..., -1].max(-1, keepdims=True)
        p = np.exp(lp)
        p /= p.sum(-1, keepdims=True)
        M = _M.T.astype(np.float32)
        mx = o[..., :L] @ M + X[:, None, 32:33] * (np.arange(1, T + 1) * DT)
        my = o[..., L:2 * L] @ M
        return p, np.stack([mx, my], -1), np.exp(np.clip(o[..., 2 * L:3 * L] @ M, -3.5, 1.2))

    def predict(self, tracks, hist, now, robot, rv=(0.0, 0.0), field=None, meta=None, all_tracks=None):
        if not tracks:
            return []
        pool = tracks if all_tracks is None else all_tracks
        F = [features(tr, hist.get(tr), now, robot, rv, [o for o in pool if o is not tr], field, meta,
                      hist.meta(tr)) for tr in tracks]
        p, m, s = self.raw(np.stack([f["x"] for f in F]))
        out = []
        for i, f in enumerate(F):
            ox, oy, yaw, _ = f["frame"]
            c, sn = math.cos(yaw), math.sin(yaw)
            R = np.array([[c, sn], [-sn, c]])
            out.append([(float(p[i, k]), m[i, k] @ R + [ox, oy], s[i, k]) for k in range(self.K)])
        return out


def constant_velocity(tracks, now, std=(0.12, 0.25)):
    """Doi chung / du phong: 1 mode di thang deu."""
    tt = np.arange(1, T + 1) * DT
    return [[(1.0, tr["p"] + tr["v"] * (now - tr["t"] + tt)[:, None], std[0] + std[1] * tt)] for tr in tracks]
