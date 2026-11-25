#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nav_sev.py — SEV (Stochastic Evasion Value), thu nghiem cua agent SEV (xem research/REPORT_SEV.md).

V(p, psi, s) = P(nguoi cham than robot trong 3 s | robot ne TOI UU co hoi tiep, tre 1 chu ky 0.3 s)
  p    vi tri nguoi trong he THAN robot; psi huong nguoi tuong doi; s lop toc do (dung, 0.6, 0.9, 1.2 m/s)
Nguoi: qua trinh nhay huong (tan suat lam(s), phan bo goc) + lac + dung / khoi dong (do tu du lieu).
Tre: hanh dong cua chu ky k chon theo trang thai DAU chu ky, nguoi co the re NGAY luc do -> robot chi phan
ung o chu ky sau (0.3 s ~ 0.05 lenh + 0.1 chu ky + 0.15 tau).
Robot: tap van toc HOP (khong phai elip) do tu results/sysid.npz (sev/coupling.py): tien 0.28, lui 0.20,
ngang 0.28 (cheo 0.39 do duoc), quay 0.70 rad/s; lac than = sai so ho sigma 3 cm.
Tuong: 1 chieu tho 0..8 (0 = trong, 1..8 = huong tuong gan trong he than, buoc 45 do): cam thanh phan
van toc huong vao tuong.
"""
import math
import os

import numpy as np

DT, N, R_MAX, DR, NPSI = 0.3, 10, 4.5, 0.125, 24
SPEEDS = np.array([0.0, 0.6, 0.9, 1.2])
BODY = (0.32, 0.25, 0.16)
PR = 0.22
VF, VB, VL, WZ = 0.28, 0.20, 0.28, 0.70


def actions():
    out = []
    for ix in (1, 0, -1):
        for iy in (0, 1, -1):
            for iw in (0, 1, -1):
                out.append((VF if ix > 0 else (-VB if ix < 0 else 0.0), VL * iy, WZ * iw))
    return np.array(out, np.float32)


def clearance(px, py):
    """ho (m) tu nguoi (ban kinh PR) toi hinh chu nhat than, he than."""
    f, r, hw = BODY
    dx = np.maximum(np.maximum(px - f, -r - px), 0.0)
    dy = np.maximum(np.abs(py) - hw, 0.0)
    return np.hypot(dx, dy) - PR


def person_kernel(lam, ang, p_stop, p_start, st_ang, sig, dt=DT):
    """(NPSI*4, NPSI*4): xac suat (psi, s) -> (psi', s') dau moi chu ky. lam: 3 toc do (1/s); ang: mau |goc| (rad)."""
    A = NPSI
    dpsi = 2 * np.pi / A
    cent = (np.arange(A) + 0.0) * dpsi

    def circ(samples_abs):
        h = np.zeros(A)
        for s in (1, -1):
            x = (s * samples_abs) / dpsi
            lo = np.floor(x).astype(int)
            fr = x - lo
            np.add.at(h, lo % A, 1 - fr)
            np.add.at(h, (lo + 1) % A, fr)
        return h / h.sum()
    diff = np.zeros(A)
    d = (cent + np.pi) % (2 * np.pi) - np.pi
    # lac nho: 3 muc (giu ky vong phuong sai sig^2 * dt)
    q = min(0.4, sig ** 2 * dt / (2 * dpsi ** 2))
    diff[0], diff[1], diff[-1] = 1 - 2 * q, q, q
    turn = circ(np.asarray(ang)) if len(ang) else np.eye(A)[0]
    st = circ(np.abs(np.asarray(st_ang))) if len(st_ang) else np.ones(A) / A
    C = lambda h: np.stack([np.roll(h, i) for i in range(A)])            # hang i: psi=i -> psi'
    K = np.zeros((A * 4, A * 4))
    ps, pg = 1 - math.exp(-p_stop * dt), 1 - math.exp(-p_start * dt)
    for s in range(4):
        rr = slice(s * A, (s + 1) * A)
        if s == 0:
            K[rr, rr] += (1 - pg) * np.eye(A)
            for s2, w in ((1, .25), (2, .5), (3, .25)):
                K[rr, s2 * A:(s2 + 1) * A] += pg * w * C(st)
        else:
            pt = 1 - math.exp(-lam[s - 1] * dt)
            K[rr, 0:A] += ps * np.eye(A)
            K[rr, rr] += (1 - ps) * (pt * C(turn) + (1 - pt) * C(diff))
    return K.astype(np.float32)


def solve(K, wall=0, acts=None, n=N, fixed=None, sway=0.03, dr=DR, verbose=False):
    """DP lui. wall 0..8. fixed=i: chi 1 hanh dong (vong ho). -> V (G, G, NPSI, 4) float32"""
    A = actions() if acts is None else acts
    g = np.arange(-R_MAX, R_MAX + 1e-6, dr, dtype=np.float32)
    G = len(g)
    X, Y = np.meshgrid(g, g, indexing="ij")
    psi = np.arange(NPSI, dtype=np.float32) * 2 * np.pi / NPSI
    if wall:
        th = (wall - 1) * np.pi / 4
        w = np.array([math.cos(th), math.sin(th)])
        into = A[:, 0] * w[0] + A[:, 1] * w[1]
        A = A.copy()
        A[:, :2] -= np.maximum(into, 0)[:, None] * w[None]
        A = np.unique(np.round(A, 4), axis=0) if fixed is None else A
    ids = range(len(A)) if fixed is None else [fixed]
    # tien tinh cho moi (a, s): chi so noi suy + xac suat cham
    from scipy.special import ndtr
    pre = []
    for a in ids:
        vx, vy, wz = A[a]
        row = []
        for s, sp in enumerate(SPEEDS):
            PX = X[..., None] + np.zeros(NPSI, np.float32)
            PY = Y[..., None] + np.zeros(NPSI, np.float32)
            dmin = np.full(PX.shape, 9.0, np.float32)
            m = 3
            for k in range(1, m + 1):
                t = DT * k / m
                h = 0.5 * wz * t
                dx, dy = (vx * math.cos(h) - vy * math.sin(h)) * t, (vx * math.sin(h) + vy * math.cos(h)) * t
                ex = PX + sp * t * np.cos(psi) - dx
                ey = PY + sp * t * np.sin(psi) - dy
                c, sn = math.cos(wz * t), math.sin(wz * t)
                bx, by = c * ex + sn * ey, -sn * ex + c * ey
                dmin = np.minimum(dmin, clearance(bx, by))
            hit = ndtr(-dmin / sway).astype(np.float32)
            fx, fy = (bx + R_MAX) / dr, (by + R_MAX) / dr
            out = (fx < 0) | (fx > G - 1) | (fy < 0) | (fy > G - 1)
            fx, fy = np.clip(fx, 0, G - 1.001), np.clip(fy, 0, G - 1.001)
            ix, iy = fx.astype(np.int32), fy.astype(np.int32)
            fx, fy = (fx - ix).astype(np.float32), (fy - iy).astype(np.float32)
            fp = (psi - wz * DT) / (2 * np.pi / NPSI)
            ip = np.floor(fp).astype(np.int32)
            wp = (fp - ip).astype(np.float32)
            row.append((hit, ix, iy, fx, fy, ip % NPSI, (ip + 1) % NPSI, wp, out))
        pre.append(row)
    V = np.zeros((G, G, NPSI, 4), np.float32)
    h0 = ndtr(-clearance(X, Y) / sway).astype(np.float32)
    for k in range(n):
        best = None
        for row in pre:
            Q = np.empty((G, G, NPSI, 4), np.float32)
            for s in range(4):
                hit, ix, iy, fx, fy, i0, i1, wp, out = row[s]
                v = V[..., s].ravel()
                val = 0.0
                for ii, wpp in ((i0, 1 - wp), (i1, wp)):
                    base = (ix * G + iy) * NPSI + ii[None, None]
                    val = val + wpp * ((1 - fx) * (1 - fy) * v[base] + fx * (1 - fy) * v[base + G * NPSI]
                                       + (1 - fx) * fy * v[base + NPSI] + fx * fy * v[base + (G + 1) * NPSI])
                val = np.where(out, 0.0, val)
                Q[..., s] = hit + (1 - hit) * val
            E = (Q.transpose(0, 1, 3, 2).reshape(-1, NPSI * 4) @ K.T).reshape(G, G, 4, NPSI).transpose(0, 1, 3, 2)
            best = E if best is None else np.minimum(best, E)
        V = np.maximum(best, h0[..., None, None])
        if verbose:
            print("buoc", k, "V tb", float(V.mean()))
    return V


class Table:
    """Tra V tuyen tinh theo vi tri, tuyen tinh theo huong va toc do."""

    def __init__(self, V, dr=DR):
        self.V, self.dr = V, dr
        self.G = V.shape[-4]

    def __call__(self, bx, by, psi, sp, wall=None):
        V = self.V
        G = self.G
        fx = np.clip((bx + R_MAX) / self.dr, 0, G - 1.001)
        fy = np.clip((by + R_MAX) / self.dr, 0, G - 1.001)
        out = (np.abs(bx) > R_MAX) | (np.abs(by) > R_MAX)
        ix, iy = fx.astype(int), fy.astype(int)
        fx, fy = fx - ix, fy - iy
        fp = (psi % (2 * np.pi)) / (2 * np.pi / NPSI)
        ip = np.floor(fp).astype(int)
        wp = fp - ip
        s_ = np.clip(np.interp(sp, SPEEDS, np.arange(4)), 0, 2.9999)
        i_s = s_.astype(int)
        ws = s_ - i_s
        Vw = V if V.ndim == 4 else V[wall]
        val = 0.0
        for ds, w1 in ((0, 1 - ws), (1, ws)):
            for dp, w2 in ((0, 1 - wp), (1, wp)):
                for dx, w3 in ((0, 1 - fx), (1, fx)):
                    for dy, w4 in ((0, 1 - fy), (1, fy)):
                        idx = (ix + dx, iy + dy, (ip + dp) % NPSI, i_s + ds)
                        q = Vw[idx] if V.ndim == 4 else V[(wall,) + idx]
                        val = val + w1 * w2 * w3 * w4 * q
        return np.where(out, 0.0, val)
