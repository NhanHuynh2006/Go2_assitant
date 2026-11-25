#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nav_prism2.py — PRISM-E: MPPI co BIEN NE (evasion margin) cho cho 4 chan cham hon nguoi.

Moi thanh phan bat/tat duoc (flags) va xuat phat tu mot loi DA DO o 960 luot Gazebo (22/11):
  cap    thang nguoi tinh theo THAN DAI (2 vong tron mui/duoi, nhu vat tinh). Ban cu tinh tu TAM voi
         0.3 m trong khi mui vuon 0.32-0.37 m: 42/55 lan cham nguoi do robot xay ra luc than dang XOAY.
  lat    bu TRE cam bien: tracker 5 Hz + tre chap hanh -> nguoi 0.9 m/s lech 0.2-0.3 m. Day vi tri nguoi
         toi luc lenh co hieu luc (robot_ros dua tuoi cua track vao).
  dyn    diem LiDAR cua vat dong KHONG ve vao ban do tinh (bong ma lam duong bi chan) - o robot_ros.
  evade  BIEN NE: voi moi trang thai du doan va moi nguoi dang tien toi, so sanh
             TTC (nguoi toi noi)  voi  thoi gian can de LACH ra khoi hanh lang cua nguoi
         theo KHA NANG TUNG TRUC do online (gx*vx_max, gy*vy_max: di ngang yeu hon di thang -> huong than
         quyet dinh co lach kip khong) va PHIA lach phai trong (truong khoang cach). Khac Contingency-MPPI
         (Jung et al. L4DC 2025, lay mau long nhau) va SCRAMPPI (2026, ham gia tri HJ): dong, giai tich.
  prior  mau tu policy RL (nhu PRISM)
  value  critic PPO lam chi phi cuoi
  rate   gioi han thay doi lenh
"""
import math

import numpy as np

from nav_local import MPPI, PolicyMPPI


class PRISM2(MPPI):
    UNUSED = frozenset(("w_pen",))

    def __init__(self, priors=(), flags=None, prior_frac=0.3, hold=6, w_value=0.3, w_ev=6.0, **kw):
        super().__init__(**kw)
        self.priors = list(priors)
        self.flags = dict(cap=True, lat=True, dyn=True, evade=True, turn=False, mode=False,
                          prior=bool(self.priors), value=False, rate=True, adapt=True, vis=False)
        bad = set(flags or {}) - set(self.flags) - set(getattr(self, "FLAGS3", ()))
        if bad:
            raise ValueError(f"co la khong ton tai: {sorted(bad)}")
        self.flags.update(flags or {})
        self.ratios = [prior_frac / max(1, len(self.priors))] * len(self.priors)
        self.hold, self.w_value, self.w_ev = hold, w_value, w_ev
        self.du_max = np.array([0.08, 0.08, 0.22])
        self.prefs = {}
        self.sig_turn, self.ev_slack, self.ev_scale = 0.6, 0.3, 0.25      # rad, s, s
        self._side = 0

    # ------------------------------------------------------------- bien ne CO XET RE
    def turn_cost(self, P, Y, people, field, meta, gains):
        """Voi moi trang thai du doan: NEU nguoi j re thang ve phia robot ngay luc do, robot con kip lach
        ngang (theo kha nang tung truc do online, than dai, phia trong) truoc khi nguoi toi noi khong?
        Trong so = do hop ly cua goc re can thiet exp(-phi^2 / 2 sig^2). Nguoi dang dung: bo qua.
        (Do 22/11: truoc khi cham 2 s chi 21 % nguoi dang huong vao robot -> du doan di thang deu hong.)"""
        K, T = P.shape[:2]
        S = np.zeros(K)
        mv = [p for p in people if math.hypot(p[2], p[3]) > 0.2]
        if not mv:
            return S
        res, gx0, gy0 = meta
        H, W = field.shape
        idx = np.arange(2, min(T, 20), 3)                                   # toi 2 s
        Px, Py, Yw = P[:, idx, 0], P[:, idx, 1], Y[:, idx]
        tt = (idx + 1) * self.dt
        ax = max(0.08, float(gains[0]) * self.vmax[0])
        ay = max(0.05, float(gains[1]) * self.vmax[1])
        for (px, py, vx, vy, rad) in mv:
            sp = math.hypot(vx, vy)
            rx, ry = Px - (px + vx * tt)[None], Py - (py + vy * tt)[None]
            d = np.hypot(rx, ry) + 1e-6
            hx, hy = rx / d, ry / d                                        # huong nguoi -> robot
            cphi = np.clip((hx * vx + hy * vy) / sp, -1, 1)
            phi = np.arccos(cphi)
            pr = np.exp(-phi ** 2 / (2 * self.sig_turn ** 2))
            nx, ny = -hy, hx
            cd = np.cos(Yw) * nx + np.sin(Yw) * ny
            sd2 = np.maximum(1.0 - cd ** 2, 0)
            half = 0.37 * np.abs(cd) + 0.16 * np.sqrt(sd2)
            vn = 1.0 / np.sqrt(cd ** 2 / ax ** 2 + sd2 / ay ** 2)
            m = rad + half + 0.05
            ok = np.zeros_like(d, bool)
            for sgn in (1.0, -1.0):
                f = None
                for fr in (0.5, 1.0):
                    c = np.clip(((Px + sgn * nx * m * fr - gx0) / res).astype(int), 0, W - 1)
                    r = np.clip(((Py + sgn * ny * m * fr - gy0) / res).astype(int), 0, H - 1)
                    q = field[r, c] > 0.22
                    f = q if f is None else f & q
                ok |= f
            along = 0.37 * np.sqrt(sd2) + 0.16 * np.abs(cd)
            ttc = np.maximum(d - rad - along, 0.0) / sp
            need = np.where(ok, self.tau + m / vn, 3.0)
            margin = np.clip(ttc - need, -3.0, 3.0)
            S += (pr * np.logaddexp(0.0, -(margin - self.ev_slack) / self.ev_scale) * self.ev_scale).mean(1)
        return self.w_ev * S

    # ------------------------------------------------------------- nguoi
    def people_cost(self, P, Y, people, U=None):
        K, T = P.shape[:2]
        S = np.zeros(K)
        if not people:
            return S
        w = self.w
        Q = np.array([[p[0], p[1]] for p in people])
        Vp = np.array([[p[2], p[3]] for p in people])
        R = np.array([p[4] for p in people]) + float(self.prefs.get("people_margin", 0.0))
        tt = (np.arange(1, T + 1) * self.dt)
        q = Q[:, None] + Vp[:, None] * tt[None, :, None]                      # (N,T,2)
        if self.flags["cap"]:
            c, s = np.cos(Y), np.sin(Y)
            d = np.full((K, T, len(people)), 9.0)
            for off in (self.c_off, -self.c_off):
                cx, cy = P[..., 0] + off * c, P[..., 1] + off * s
                d = np.minimum(d, np.hypot(cx[..., None] - q[None, ..., 0].transpose(0, 2, 1),
                                           cy[..., None] - q[None, ..., 1].transpose(0, 2, 1)))
            d = d - R[None, None] - self.r_body - self.margin
        else:
            d = np.hypot(P[..., 0, None] - q[None, ..., 0].transpose(0, 2, 1),
                         P[..., 1, None] - q[None, ..., 1].transpose(0, 2, 1)) - R[None, None] - 0.3
        S += w["ppl"] * np.exp(-np.maximum(d, 0.0) / self.ppl_len).sum(1).sum(1) / T
        S += w["col"] * 0.5 * (d < 0.0).any(1).sum(1)
        return S

    # ------------------------------------------------------------- bien ne
    def evasion_cost(self, P, Y, people, field, meta, gains):
        """(K,) chi phi: con du thoi gian LACH khoi hanh lang cua nguoi dang tien toi khong."""
        K, T = P.shape[:2]
        S = np.zeros(K)
        mv = [p for p in people if math.hypot(p[2], p[3]) > 0.2]
        if not mv:
            return S
        res, gx0, gy0 = meta
        H, W = field.shape
        idx = np.arange(3, T, 4)
        Px, Py, Yw = P[:, idx, 0], P[:, idx, 1], Y[:, idx]
        tt = (idx + 1) * self.dt
        ax = max(0.08, float(gains[0]) * self.vmax[0])                        # kha nang that tung truc
        ay = max(0.05, float(gains[1]) * self.vmax[1])
        for (px, py, vx, vy, rad) in mv:
            sp = math.hypot(vx, vy)
            hx, hy = vx / sp, vy / sp
            qx, qy = px + vx * tt, py + vy * tt
            rx, ry = Px - qx[None], Py - qy[None]
            a = rx * hx + ry * hy                                             # robot o phia truoc nguoi bao xa
            b = -rx * hy + ry * hx                                            # lech ngang co dau (trai +)
            nx, ny = -hy, hx                                                  # phap tuyen trai
            cd = np.cos(Yw) * nx + np.sin(Yw) * ny                            # |cos| goc giua than va huong lach
            sd2 = 1.0 - cd ** 2
            half = 0.37 * np.abs(cd) + 0.16 * np.sqrt(np.maximum(sd2, 0))     # be rong than chieu len phap tuyen
            vn = 1.0 / np.sqrt(cd ** 2 / ax ** 2 + np.maximum(sd2, 0) / ay ** 2)   # van toc lach toi da (elip)
            Rs = rad + half + 0.10
            need_l, need_r = Rs - b, Rs + b                                   # lach sang trai / phai
            best = np.full_like(b, 9.0)
            for sgn, need in ((1.0, need_l), (-1.0, need_r)):
                m = np.maximum(need, 0.0)
                ex, ey = Px + sgn * nx * m, Py + sgn * ny * m                 # noi phai toi
                c = np.clip(((ex - gx0) / res).astype(int), 0, W - 1)
                r = np.clip(((ey - gy0) / res).astype(int), 0, H - 1)
                cm = np.clip(((Px + sgn * nx * m * .5 - gx0) / res).astype(int), 0, W - 1)
                rm = np.clip(((Py + sgn * ny * m * .5 - gy0) / res).astype(int), 0, H - 1)
                free = (field[r, c] > 0.22) & (field[rm, cm] > 0.22)
                t_need = np.where(need <= 0, 0.0, self.tau + m / vn)
                best = np.minimum(best, np.where(free | (need <= 0), t_need, 9.0))
            ttc = np.maximum(a - 0.37 - rad, 0.0) / sp
            on = (a > -0.1) & (ttc < 3.0)
            margin = np.clip(ttc - best, -2.0, 2.0)
            S += (on * np.logaddexp(0.0, -(margin - 0.3) / 0.25) * 0.25).mean(1)
        return self.w_ev * S

    def mode_mask(self, P, S, x0, ppl, lam):
        """Chia mau theo PHIA lach (trai/phai) so voi nguoi nguy nhat; chi giu phia tot nhat (co tre) ->
        MPPI khong trung binh hai kieu ne nguoc nhau."""
        K = len(S)
        best, tb = None, 9.0
        for p in ppl:
            sp = math.hypot(p[2], p[3])
            d = math.hypot(p[0] - x0[0], p[1] - x0[1])
            if sp > 0.2 and d / sp < tb and ((x0[0] - p[0]) * p[2] + (x0[1] - p[1]) * p[3]) > 0:
                best, tb = p, d / sp
        if best is None or tb > 4.0:
            self._side = 0
            return np.ones(K)
        sp = math.hypot(best[2], best[3])
        nx, ny = -best[3] / sp, best[2] / sp
        k = min(P.shape[1] - 1, max(4, int(tb / self.dt)))
        lat = (P[:, k, 0] - best[0]) * nx + (P[:, k, 1] - best[1]) * ny
        L, R = lat >= 0, lat < 0
        if not L.any() or not R.any():
            return np.ones(K)
        sl, sr = S[L].min(), S[R].min()
        if self._side > 0:
            sl -= 2.0 * lam + 0.2
        elif self._side < 0:
            sr -= 2.0 * lam + 0.2
        self._side = 1 if sl <= sr else -1
        return (L if self._side > 0 else R).astype(float)

    # ------------------------------------------------------------- 1 buoc
    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None,
             seen=None, tentative=(), gains=None, obs_fn=None):
        K, T = self.K, self.T
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        g = np.asarray(gains if (gains is not None and self.flags["adapt"]) else [gain] * 3, float)
        ppl = list(people)
        eps = self.rng.normal(size=(K, T, 3)) * self.sigma
        for t in range(1, T):
            eps[:, t] = 0.7 * eps[:, t - 1] + 0.45 * eps[:, t]
        U = np.clip(self.U[None] + eps, self.vmin, self.vmax)
        spans = []
        use = self.flags["prior"] and self.priors
        a_prev = None
        if self.priors:
            pol0 = self.priors[0]
            a_prev = 2 * (u_prev - pol0.vmin) / (pol0.vmax - pol0.vmin) - 1
        if use:
            ks = [int(round(r_ * K)) for r_ in self.ratios]
            j = K - sum(ks)
            for pl, kk in zip(self.priors, ks):
                if kk > 0:
                    U[j:j + kk] = PolicyMPPI._policy_rollouts(self, x0, v0, field, meta, path, goal, ppl, g,
                                                              a_prev, kk, pol=pl)
                spans.append((j, j + kk))
                j += kk
        U[0] = self.U
        U[1] = 0.0
        i0 = 0
        if path is not None and len(path) > 1:
            i0 = self._nearest(path, x0)
            a = path[min(i0 + 6, len(path) - 1)]
            hd = math.atan2(a[1] - x0[1], a[0] - x0[0]) - x0[2]
            hd = math.atan2(math.sin(hd), math.cos(hd))
            U[2] = np.clip([0.45 * math.cos(hd), 0.0, 1.2 * hd], self.vmin, self.vmax)
        P, Y, V = self.rollout(U, x0, v0, g)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        S = S + self.people_cost(P, Y, ppl)
        if self.flags["evade"]:
            S = S + self.evasion_cost(P, Y, ppl, field, meta, g)
        if self.flags["turn"]:
            S = S + self.turn_cost(P, Y, ppl, field, meta, g)
        if self.flags["value"] and self.priors and getattr(self.priors[0], "VW", None) is not None:
            pol0 = self.priors[0]
            top = np.argsort(S)[:96]
            XT = np.concatenate([P[top, -1], Y[top, -1:]], 1)
            OT = pol0.observe_batch(XT, V[top, -1], field, meta, path, goal,
                                    [(px + vx * T * self.dt, py + vy * T * self.dt, vx, vy, r)
                                     for (px, py, vx, vy, r) in ppl], np.repeat(a_prev[None], len(top), 0))
            val = pol0.value_batch(OT)
            S[top] -= self.w_value * (val - val.max())
            S[np.setdiff1d(np.arange(K), top)] += self.w_value * (val.max() - val.min())
        smin = S.min()
        lam = self.temperature(S, smin)
        wgt = np.exp(-(S - smin) / lam)
        if self.flags["mode"] and ppl:
            wgt = wgt * self.mode_mask(P, S, x0, ppl, lam)
        wgt /= wgt.sum()
        newU = (wgt[:, None, None] * U).sum(0)
        newU[1:-1] = (newU[:-2] + 2 * newU[1:-1] + newU[2:]) / 4.0
        self.U = newU
        best = int(S.argmin())
        u = self.U[0].copy()
        blocked = bool(coll.all())
        if coll[best] and not blocked:
            u = U[best, 0].copy()
        Pm, Ym, _ = self.rollout(self.U[None], x0, v0, g)
        if self.flags["rate"] and not blocked:
            urgent = False
            tt1 = np.arange(1, 11) * self.dt
            for (px, py, vx, vy, rad) in ppl:
                if (np.hypot(Pm[0, :10, 0] - (px + vx * tt1), Pm[0, :10, 1] - (py + vy * tt1)) - rad < 0.75).any():
                    urgent = True
                    break
            if not urgent:
                u = u_prev + np.clip(u - u_prev, -self.du_max, self.du_max)
                if dmin[best] < 0.03:
                    u = U[best, 0].copy() if not coll[best] else np.zeros(3)
        self.U = np.roll(self.U, -1, 0)
        self.U[-1] = self.U[-2]
        self.last = dict(best_cost=float(smin), blocked=blocked, traj=Pm[0], clear=float(dmin[best]), i0=i0)
        return (u if not blocked else np.zeros(3)), self.last


class GeoFan:
    """QUAT Y DINH TRAC DIA: nguoi di toi mot dich CHUA BIET theo duong gan ngan nhat tren ban do (cua robot).
    Dijkstra tu vi tri hien tai va tu vi tri 0.6 s truoc -> moi o dich g co do hop ly
    exp(-(da_di + D_nay(g) - D_truoc(g)) / sigma) (di thang toi g thi = 0); lay mau M dich theo phan vi, lan nguoc
    duong -> M quy dao tuong lai biet RE o goc tuong / cua (van toc khong doi xuyen tuong, khong biet re)."""

    OFF = [(0, 1), (1, 0), (1, 1), (1, -1), (1, 2), (2, 1), (1, -2), (2, -1)]

    def __init__(self, M=16, reach=6.0, sigma=0.10, clear=0.28):
        self.M, self.reach, self.sigma, self.clear = M, reach, sigma, clear
        self.t = -9.0
        self.G = None

    def build(self, field, meta, xy, t):
        if t - self.t < 0.5 and self.G is not None:
            return
        from scipy.sparse import csr_matrix
        self.t = t
        res, gx0, gy0 = meta
        n = int(self.reach / res)
        r0 = int((xy[1] - gy0) / res) - n
        c0 = int((xy[0] - gx0) / res) - n
        rr = np.arange(max(r0, 0), min(r0 + 2 * n, field.shape[0]), 2)
        cc = np.arange(max(c0, 0), min(c0 + 2 * n, field.shape[1]), 2)
        f = np.minimum(field[rr][:, cc], 5.0)
        self.h, self.w = f.shape
        self.step, self.ox, self.oy = 2 * res, gx0 + (cc[0] + .5) * res, gy0 + (rr[0] + .5) * res
        free = f > self.clear
        wt = 1.0 + 2.0 * np.clip((0.55 - f) / 0.25, 0, 1)
        idx = np.arange(self.h * self.w).reshape(self.h, self.w)
        I, J, D = [], [], []
        for dr, dc in self.OFF:
            a = (slice(0, self.h - dr), slice(max(0, -dc), self.w - max(0, dc)))
            b = (slice(dr, self.h), slice(max(0, dc), self.w - max(0, -dc)))
            ok = free[a] & free[b]
            I.append(idx[a][ok])
            J.append(idx[b][ok])
            D.append((0.5 * (wt[a] + wt[b]) * math.hypot(dr, dc) * self.step)[ok])
        I, J, D = np.concatenate(I), np.concatenate(J), np.concatenate(D)
        self.G = csr_matrix((D, (I, J)), shape=(self.h * self.w,) * 2)
        self.free = free.ravel()
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        self.cx = (self.ox + xx * self.step).ravel()
        self.cy = (self.oy + yy * self.step).ravel()

    def node(self, x, y):
        c = int(round((x - self.ox) / self.step))
        r = int(round((y - self.oy) / self.step))
        best = None
        for dr in (0, -1, 1, -2, 2):
            for dc in (0, -1, 1, -2, 2):
                a, b = r + dr, c + dc
                if 0 <= a < self.h and 0 <= b < self.w and self.free[a * self.w + b]:
                    d = dr * dr + dc * dc
                    if best is None or d < best[0]:
                        best = (d, a * self.w + b)
        return None if best is None else best[1]

    def fan(self, p, past, sp, tt):
        """-> (M, len(tt), 2) quy dao mau can bang trong so, hoac None."""
        from scipy.sparse.csgraph import dijkstra
        a = self.node(*p)
        if a is None:
            return None
        src = [a]
        b = self.node(*past) if past is not None else None
        if b is not None and b != a:
            src.append(b)
        D, pre = dijkstra(self.G, directed=False, indices=src, return_predecessors=True, limit=9.0)
        d = D[0]
        e = np.hypot(self.cx - p[0], self.cy - p[1])
        ok = np.isfinite(d) & (e > 1.0)
        if len(src) > 1:
            with np.errstate(invalid="ignore"):
                ex = D[1][a] + d - D[1]                               # >= 0 (bat dang thuc tam giac); 0 = di thang toi g
            ok &= np.isfinite(ex)
            w = np.where(ok, np.exp(-np.maximum(np.where(ok, ex, 9.0), 0) / self.sigma), 0.0)
            k = np.where(ok)[0]
        else:
            w = ok.astype(float)
            k = np.where(ok)[0]
        if not len(k) or w[k].sum() <= 1e-12:
            return None
        ang = np.arctan2(self.cy[k] - p[1], self.cx[k] - p[0])
        if past is not None:
            h = math.atan2(p[1] - past[1], p[0] - past[0])
            ang = np.angle(np.exp(1j * (ang - h)))
        o = np.argsort(ang, kind="stable")
        cw = np.cumsum(w[k][o])
        q = (np.arange(self.M) + 0.5) / self.M * cw[-1]
        g = k[o][np.minimum(np.searchsorted(cw, q), len(k) - 1)]
        out = np.empty((self.M, len(tt), 2))
        L = sp * np.asarray(tt)
        cache = {}
        for i, gi in enumerate(g):
            if gi in cache:
                out[i] = out[cache[gi]]
                continue
            cache[gi] = i
            path, n = [], int(gi)
            while n != a and n >= 0:
                path.append(n)
                n = int(pre[0][n])
            path = np.array(path[::-1])
            X = np.concatenate([[p[0]], self.cx[path]])
            Y = np.concatenate([[p[1]], self.cy[path]])
            s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(X), np.diff(Y)))])
            if len(s) > 4:                                            # lam tron rang cua
                for _ in range(2):
                    X[1:-1] = (X[:-2] + 2 * X[1:-1] + X[2:]) / 4
                    Y[1:-1] = (Y[:-2] + 2 * Y[1:-1] + Y[2:]) / 4
                s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(X), np.diff(Y)))])
            out[i, :, 0] = np.interp(L, s, X)
            out[i, :, 1] = np.interp(L, s, Y)
        return out


class PRISM3(PRISM2):
    """p3: MPPI + RUI RO CO HIEU CHINH (hazard) cua nguoi doi huong, co xet kha nang ne (recourse).
    Cac co (bat/tat tu ten 'p3-prim+hyp...'):
      prim   them mau 'ne nguyen thuy' (16 huong x 3 kieu quay, ca horizon hoac 1.2 s dau): nhieu MPPI co
             do lech chuan ben vung ~0.09 m/s nen gan nhu khong bao gio lay mau 'lach het toc do 1.5 s'
      grad   nhiet do tu phan vi thap + phat theo do lun: khi > 50 % mau cham nguoi, trung vi = 5e3 ->
             lambda ~ 400 -> trung binh deu moi mau (robot xoay / do du dung luc nguy hiem)
      haz    hazard: P(nguoi doi huong ve phia robot) x P(khong kip lach); goc doi huong ~ N(0, s0^2 + q t),
             q hoc online tu lich su huong cua CHINH cac track (chung cho moi nguoi, co tien nghiem)
      rest   nguoi dang dung co the di bat ky huong nao (hazard deu huong)
      hyp    du doan da gia thuyet (thang, re +-30/60 do, dung) ; cvar: them CVaR 80 %
      commit tre khi chon ben lach (mode_mask)
    """

    FLAGS3 = ("prim", "grad", "haz", "rest", "hyp", "cvar", "geo", "gcv", "ggs", "commit", "occ")
    UNUSED = frozenset(("w_pen", "w_ev", "du_max"))

    def __init__(self, flags=None, **kw):
        fl = dict(evade=False, turn=False, mode=False, rate=False, prim=True, grad=True, haz=True, rest=True,
                  hyp=False, cvar=False, geo=False, gcv=False, ggs=False, commit=False, occ=False)
        fl.update(flags or {})
        super().__init__(flags=fl, **kw)
        self.w_hz, self.s0, self.q0, self.hz_scale, self.hz_slack, self.hz_floor = 20.0, 0.25, 0.35, 0.25, 0.1, 0.10
        self.w["ppl"], self.ppl_len = 16.0, 0.3
        self.c_hit = 300.0
        self.w_risk, self.beta = 30.0, 0.5
        self.w_geo, self.g_tau, self.g_len, self.alpha = 40.0, 1.2, 0.12, 0.3
        self.fan = GeoFan()
        self.w_occ, self.occ_jump, self.occ_reach, self.occ_n, self.occ_v = 0.3, 0.8, 4.0, 4, 0.0
        self.phantoms = []
        self.q_turn, self._hd, self.walk = None, {}, 0.8
        self._qn, self._qs = 8.0, 8.0 * self.q0
        self.n_prim = 96
        th = np.linspace(-math.pi, math.pi, 16, endpoint=False)
        pr = []
        for wz in (0.0, 0.7, -0.7):
            for a in th:
                c, s = math.cos(a), math.sin(a)
                f = min((self.vmax[0] if c > 0 else -self.vmin[0]) / max(abs(c), 1e-6), self.vmax[1] / max(abs(s), 1e-6))
                pr.append((c * f, s * f, wz))
        self._prim = np.array(pr)                                              # 48
        if self.flags["grad"]:
            self.lam_q, self.lam_c = 0.15, 0.3

    # ------------------------------------------------------------ hoc online toc do doi huong cua nguoi
    def observe_people(self, people, t):
        new = {}
        for p in people:
            sp = math.hypot(p[2], p[3])
            h = math.atan2(p[3], p[2])
            best = None
            for k, (x, y, hh, tt, ss) in self._hd.items():
                dt = t - tt
                if 0 < dt < 0.5 and math.hypot(p[0] - x, p[1] - y) < 0.4 and (best is None or dt < best[1]):
                    best = (k, dt)
            if sp > 0.35:
                if best is not None:
                    x, y, hh, tt, ss = self._hd[best[0]]
                    if ss > 0.35:
                        dh = math.atan2(math.sin(h - hh), math.cos(h - hh))
                        self._qs = 0.999 * self._qs + min(dh * dh, 1.0)
                        self._qn = 0.999 * self._qn + best[1]
                self.walk = 0.99 * self.walk + 0.01 * sp
            new[len(new)] = (p[0], p[1], h, t, sp)
        self._hd = new

    @property
    def q_rate(self):
        return float(np.clip(self._qs / max(self._qn, 1e-3), 0.1, 1.5))

    def _cap(self, gains):
        if self.resp is not None:
            m = self.resp
            vx = np.interp([self.vmax[0], self.vmin[0]], m.ug[0], m.tab[0])
            vy = np.interp(self.vmax[1], m.ug[1], m.tab[1])
            return max(0.08, float(vx[0])), max(0.06, float(-vx[1])), max(0.05, float(vy))
        return (max(0.08, float(gains[0]) * self.vmax[0]),) * 2 + (max(0.05, float(gains[1]) * self.vmax[1]),)

    def hazard_cost(self, P, Y, people, field, meta, gains):
        K, T = P.shape[:2]
        S = np.zeros(K)
        if not people:
            return S
        res, gx0, gy0 = meta
        H, W = field.shape
        idx = np.arange(1, min(T, 22), 4)                                   # 0.2 .. 2.2 s
        Px, Py, Yw = P[:, idx, 0], P[:, idx, 1], Y[:, idx]
        cY, sY = np.cos(Yw), np.sin(Yw)
        tt = (idx + 1) * self.dt
        ax, ab, ay = self._cap(gains)
        ax = 0.5 * (ax + ab)
        logs = np.zeros((K, len(idx)))
        for (px, py, vx, vy, rad) in people:
            sp = math.hypot(vx, vy)
            rest = sp < 0.2
            if rest and not self.flags["rest"]:
                continue
            if math.hypot(Px[0, 0] - px, Py[0, 0] - py) > 5.0:
                continue
            qx, qy = (px, py) if rest else (px + vx * tt, py + vy * tt)
            rx, ry = Px - qx, Py - qy
            d = np.hypot(rx, ry) + 1e-6
            hx, hy = rx / d, ry / d
            nx, ny = -hy, hx
            cd = cY * nx + sY * ny
            sd2 = np.maximum(1.0 - cd ** 2, 0)
            half = 0.37 * np.abs(cd) + 0.16 * np.sqrt(sd2)
            vn = 1.0 / np.sqrt(cd ** 2 / ax ** 2 + sd2 / ay ** 2)
            m = rad + half + 0.05
            cone = 2 * np.arcsin(np.minimum(1.0, m / d))
            if rest:
                pr = np.minimum(1.0, cone / (2 * math.pi)) * 0.7
                s_ = max(self.walk, 0.6)
                t0 = 0.5                                                       # thoi gian tang toc
            else:
                phi = np.arccos(np.clip((hx * vx + hy * vy) / sp, -1, 1))
                sg2 = self.s0 ** 2 + self.q_rate * tt
                pr = np.minimum(1.0, cone * (np.exp(-phi ** 2 / (2 * sg2)) / np.sqrt(2 * math.pi * sg2)
                                             + self.hz_floor / (2 * math.pi)))
                s_, t0 = max(sp, 0.5), 0.0
            ok = np.zeros_like(d, bool)
            for sgn in (1.0, -1.0):
                f = None
                for fr in (0.5, 1.0):
                    c = np.clip(((Px + sgn * nx * m * fr - gx0) / res).astype(int), 0, W - 1)
                    r = np.clip(((Py + sgn * ny * m * fr - gy0) / res).astype(int), 0, H - 1)
                    q = field[r, c] > 0.22
                    f = q if f is None else f & q
                ok |= f
            along = 0.37 * np.sqrt(sd2) + 0.16 * np.abs(cd)
            ttc = np.maximum(d - rad - along, 0.0) / s_ + t0
            need = np.where(ok, self.tau + m / vn, 3.0)
            mg = np.clip((ttc - need - self.hz_slack) / self.hz_scale, -12, 12)
            # phan khong kip ne + phan "cang gan cang te" (giu gradient khi da khong kip)
            fail = 1.0 / (1.0 + np.exp(mg)) + 0.3 * np.clip(-mg * self.hz_scale / 2.0, 0, 1)
            logs += pr * fail
        return self.w_hz * logs.mean(1)

    def hyp_cost(self, P, Y, people):
        K, T = P.shape[:2]
        idx = np.arange(1, T, 2)
        tt = (idx + 1) * self.dt
        S = np.zeros(K)
        c, s = np.cos(Y[:, idx]), np.sin(Y[:, idx])
        F = [(P[:, idx, 0] + o * c, P[:, idx, 1] + o * s) for o in (self.c_off, -self.c_off)]
        sg = math.sqrt(self.q_rate) * 0.8
        for (px, py, vx, vy, rad) in people:
            sp = math.hypot(vx, vy)
            if math.hypot(P[0, 0, 0] - px, P[0, 0, 1] - py) > 4.5:
                continue
            h = math.atan2(vy, vx)
            if sp < 0.2:
                hyps = [(0.0, 0.0, 0.3)] + [(self.walk * math.cos(a), self.walk * math.sin(a), 0.7 / 8)
                                            for a in np.linspace(-math.pi, math.pi, 8, endpoint=False)]
            else:
                hyps = [(vx, vy, 0.36), (0.0, 0.0, 0.08)]
                for k, w in ((1.0, 0.17), (2.0, 0.08)):
                    for q in (1, -1):
                        hyps.append((sp * math.cos(h + q * k * sg), sp * math.sin(h + q * k * sg), w * 1.0))
                z = sum(x[2] for x in hyps)
                hyps = [(a, b, w / z) for a, b, w in hyps]
            R = np.empty((len(hyps), K))
            for i, (hx, hy, w) in enumerate(hyps):
                d = None
                for (fx, fy) in F:
                    e = np.hypot(fx - (px + hx * tt), fy - (py + hy * tt))
                    d = e if d is None else np.minimum(d, e)
                d = d - rad - self.r_body - 0.03
                R[i] = (np.exp(-np.maximum(d, 0) / 0.15)).max(1) + np.maximum(-d, 0).max(1)
            ws = np.array([x[2] for x in hyps])
            r = (ws[:, None] * R).sum(0)
            if self.flags["cvar"]:
                o = np.argsort(-R, 0)
                cw = np.cumsum(ws[o], 0)
                take = np.clip(0.2 - (cw - ws[o]), 0, ws[o])
                r = (1 - self.beta) * r + self.beta * (take * np.take_along_axis(R, o, 0)).sum(0) / 0.2
            S += r
        return self.w_risk * S

    def geo_cost(self, P, Y, people, field, meta, x0, t):
        """Rui ro = trung binh (va CVaR) theo M quy dao y dinh cua max_t gamma(t) * va_cham(d). gamma = exp(-t/g_tau):
        xap xi viec SE duoc lap ke hoach lai khi biet them (recourse)."""
        K, T = P.shape[:2]
        idx = np.arange(1, T, 3)
        tt = (idx + 1) * self.dt
        S = np.zeros(K)
        self.fan.build(field, meta, x0, t)
        c, s = np.cos(Y[:, idx]), np.sin(Y[:, idx])
        Fx = np.stack([P[:, idx, 0] + o * c for o in (self.c_off, -self.c_off)], 0).astype(np.float32)   # (2,K,t)
        Fy = np.stack([P[:, idx, 1] + o * s for o in (self.c_off, -self.c_off)], 0).astype(np.float32)
        gam = np.exp(-tt / self.g_tau).astype(np.float32)
        near = sorted((math.hypot(p[0] - x0[0], p[1] - x0[1]), p) for p in people)[:3]
        for dist, (px, py, vx, vy, rad) in near:
            if dist > 4.5:
                continue
            sp = math.hypot(vx, vy)
            rest = sp < 0.2
            past = None
            if not rest:
                for L in (1.0, 0.6):                                  # diem phia sau theo huong di
                    past = (px - L * vx / sp, py - L * vy / sp)
                    if self.fan.node(*past) is not None:
                        break
            if self.flags["gcv"]:                                     # ablation: chi van toc khong doi
                Q = None
            elif self.flags["ggs"] and not rest:                      # ablation: quat Gauss huong (khong ban do)
                z = np.array([-1.86, -1.32, -1.01, -.78, -.58, -.4, -.24, -.08, .08, .24, .4, .58, .78, 1.01, 1.32, 1.86])
                a = math.atan2(vy, vx) + z * math.sqrt(self.s0 ** 2 + self.q_rate)
                Q = np.stack([px + max(sp, .5) * np.cos(a)[:, None] * tt, py + max(sp, .5) * np.sin(a)[:, None] * tt], -1)
            elif rest:
                Q = self.fan.fan((px, py), None, self.walk, np.maximum(tt - 0.7, 0.0))
            else:
                Q = self.fan.fan((px, py), past, max(sp, 0.5), tt)
            cv = np.stack([px + vx * tt, py + vy * tt], -1)[None]
            if Q is None:
                Q, w = cv, np.ones(1)
            else:
                M = len(Q)
                wc = 0.5 if rest else 0.55                              # dung yen / di thang
                Q = np.concatenate([cv, Q], 0)
                w = np.r_[wc, np.full(M, (1 - wc) / M)]
            Q = Q.astype(np.float32)
            R0 = rad + self.r_body + 0.03
            lo = None
            for f in range(2):
                ex = Fx[f][:, :, None] - Q[None, :, :, 0].transpose(0, 2, 1)      # (K,t,M)
                ey = Fy[f][:, :, None] - Q[None, :, :, 1].transpose(0, 2, 1)
                e = ex * ex + ey * ey
                lo = e if lo is None else np.minimum(lo, e)
            d = np.sqrt(lo) - R0
            r = np.where(d > 0, np.exp(-np.maximum(d, 0) / self.g_len), 1.0 - d) * gam[None, :, None]
            R = r.max(1)                                                  # (K,M)
            m = R @ w
            if self.flags["cvar"]:
                o = np.argsort(-R, 1)
                ws = w[o]
                cw = np.cumsum(ws, 1)
                take = np.clip(self.alpha - (cw - ws), 0, ws)
                m = (1 - self.beta) * m + self.beta * (take * np.take_along_axis(R, o, 1)).sum(1) / self.alpha
            S += m
        return self.w_geo * S

    def occ_phantoms(self, scan, x0, people, field, meta):
        """'NGUOI CO THE CO' o mep vung khuat: tu lan quet (diem than, 1 do / bin) tim cap tia ke nhau co tam nhay
        > occ_jump m, mep gan < occ_reach m; dat nguoi ao ngay SAU mep (lech 0.3 m ve phia khuat, 0.25 m ra xa), di
        thang toi robot voi toc do di bo hoc duoc. Bo neu trong vat can tinh hoac trung nguoi da bam."""
        pts = scan
        if pts is None or not len(pts):
            return []
        a = np.arctan2(pts[:, 1], pts[:, 0])
        r = np.hypot(pts[:, 0], pts[:, 1])
        b = ((a + math.pi) / (2 * math.pi) * 360).astype(int) % 360
        rb = np.full(360, np.inf)
        np.minimum.at(rb, b, r)
        miss = ~np.isfinite(rb)
        for k in (1, 2):                                                     # lap lo 1-2 tia (rot tia, diem bi loc)
            lo, hi = np.roll(rb, k), np.roll(rb, -k)
            fill = miss & np.isfinite(lo) & np.isfinite(hi)
            rb[fill] = np.maximum(lo[fill], hi[fill])
            miss = ~np.isfinite(rb)
        rb[miss] = 6.0
        res, gx0, gy0 = meta
        H, W = field.shape
        c0, s0 = math.cos(x0[2]), math.sin(x0[2])
        out = []
        for i in range(360):
            j = (i + 1) % 360
            ri, rj = rb[i], rb[j]
            if abs(ri - rj) < self.occ_jump or min(ri, rj) > self.occ_reach:
                continue
            n, f = (i, j) if ri < rj else (j, i)
            m2 = (2 * n - f) % 360                                           # lang gieng con lai cua mep gan
            f2 = (2 * f - n) % 360
            if rb[f2] - rb[n] < self.occ_jump:                               # phia xa phai xa that (>= 2 tia)
                continue
            if abs(rb[m2] - rb[n]) * 3.0 > abs(rb[f] - rb[n]):              # tuong nhin xien: khoang cach tang deu, khong phai mep
                continue
            th = -math.pi + (n + 0.5) * 2 * math.pi / 360
            tf = -math.pi + (f + 0.5) * 2 * math.pi / 360
            rn = rb[n]
            side = math.atan2(math.sin(tf - th), math.cos(tf - th))
            ex, ey = rn * math.cos(th), rn * math.sin(th)                    # mep (than)
            tx, ty = -math.sin(th) * np.sign(side), math.cos(th) * np.sign(side)
            bx, by = ex + 0.3 * tx + 0.25 * math.cos(th), ey + 0.3 * ty + 0.25 * math.sin(th)
            wx, wy = x0[0] + c0 * bx - s0 * by, x0[1] + s0 * bx + c0 * by
            cc = int((wx - gx0) / res)
            rr = int((wy - gy0) / res)
            if not (0 <= rr < H and 0 <= cc < W) or field[rr, cc] < 0.25:
                continue
            if any(math.hypot(wx - p[0], wy - p[1]) < 0.7 for p in people):
                continue
            if any(math.hypot(wx - q[0], wy - q[1]) < 0.5 for q in out):
                continue
            out.append((wx, wy, math.hypot(wx - x0[0], wy - x0[1])))
        out = sorted(out, key=lambda q: q[2])[:self.occ_n]
        sp = max(self.walk, 0.6) if not self.occ_v else self.occ_v
        res_ = []
        for (wx, wy, d) in out:
            ux, uy = (x0[0] - wx) / max(d, 1e-3), (x0[1] - wy) / max(d, 1e-3)
            res_.append((wx, wy, sp * ux, sp * uy, 0.25))
        return res_

    def occ_cost(self, P, Y, phantoms):
        K, T = P.shape[:2]
        if not phantoms:
            return np.zeros(K)
        idx = np.arange(1, T, 3)
        tt = (idx + 1) * self.dt
        gam = np.exp(-tt / self.g_tau)
        c, s = np.cos(Y[:, idx]), np.sin(Y[:, idx])
        S = np.zeros(K)
        for (px, py, vx, vy, rad) in phantoms:
            d = None
            for o in (self.c_off, -self.c_off):
                e = np.hypot(P[:, idx, 0] + o * c - (px + vx * tt), P[:, idx, 1] + o * s - (py + vy * tt))
                d = e if d is None else np.minimum(d, e)
            d = d - rad - self.r_body - 0.03
            r = np.where(d > 0, np.exp(-np.maximum(d, 0) / self.g_len), 1.0 - d) * gam[None]
            S += r.max(1)
        return self.w_occ * self.w_geo * S

    def people_cost(self, P, Y, people, U=None):
        K, T = P.shape[:2]
        S = np.zeros(K)
        tt = np.arange(1, T + 1) * self.dt
        for (px, py, vx, vy, rad) in people:
            d = self.ppl_dist(P, Y, px + vx * tt, py + vy * tt, rad)
            S += self.w["ppl"] * np.exp(-np.maximum(d, 0.0) / self.ppl_len).sum(1) / T
            if self.flags["grad"]:
                hit = d < 0.0
                first = np.where(hit.any(1), hit.argmax(1), T) / T             # cham cang som cang nang
                S += self.c_hit * (1.0 - first) + 0.5 * self.c_hit * np.maximum(-d, 0.0).max(1) / 0.3
            else:
                S += self.w["col"] * 0.5 * (d < 0.0).any(1)
        return S

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None,
             seen=None, tentative=(), gains=None, obs_fn=None, now=None, scan=None):
        K, T = self.K, self.T
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        g = np.asarray(gains if (gains is not None and self.flags["adapt"]) else [gain] * 3, float)
        ppl = list(people)
        if now is not None:
            self.observe_people(ppl, now)
        self.people_cap = True
        eps = self.rng.normal(size=(K, T, 3)) * self.sigma
        for t in range(1, T):
            eps[:, t] = 0.7 * eps[:, t - 1] + 0.45 * eps[:, t]
        U = np.clip(self.U[None] + eps, self.vmin, self.vmax)
        j = K
        if self.flags["prior"] and self.priors:
            a_prev = 2 * (u_prev - self.priors[0].vmin) / (self.priors[0].vmax - self.priors[0].vmin) - 1
            for pl, r_ in zip(self.priors, self.ratios):
                kk = int(round(r_ * K))
                if kk > 0:
                    j -= kk
                    U[j:j + kk] = PolicyMPPI._policy_rollouts(self, x0, v0, field, meta, path, goal, ppl, g, a_prev, kk, pol=pl)
        near = any(math.hypot(p[0] - x0[0], p[1] - x0[1]) < 4.0 for p in ppl)
        if self.flags["prim"] and near:
            n = len(self._prim)
            U[j - n:j] = self._prim[:, None]
            U[j - 2 * n:j - n, :12] = self._prim[:, None]
            U[j - 2 * n:j - n, 12:] = self.U[None, 12:]
        U[0] = self.U
        U[1] = 0.0
        i0 = 0
        if path is not None and len(path) > 1:
            i0 = self._nearest(path, x0)
            a = path[min(i0 + 6, len(path) - 1)]
            hd = math.atan2(a[1] - x0[1], a[0] - x0[0]) - x0[2]
            hd = math.atan2(math.sin(hd), math.cos(hd))
            U[2] = np.clip([0.45 * math.cos(hd), 0.0, 1.2 * hd], self.vmin, self.vmax)
        P, Y, V = self.rollout(U, x0, v0, g)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        S = S + self.people_cost(P, Y, ppl)
        if self.flags["haz"]:
            S = S + self.hazard_cost(P, Y, ppl, field, meta, g)
        if self.flags["turn"]:
            S = S + self.turn_cost(P, Y, [p for p in ppl], field, meta, g)
        if self.flags["geo"] and ppl:
            S = S + self.geo_cost(P, Y, ppl, field, meta, x0, 0.0 if now is None else now)
        if self.flags["hyp"] and ppl:
            S = S + self.hyp_cost(P, Y, ppl)
        if self.flags["occ"]:
            self.phantoms = self.occ_phantoms(scan, x0, ppl, field, meta)
            S = S + self.occ_cost(P, Y, self.phantoms)
        smin = S.min()
        lam = self.temperature(S, smin)
        wgt = np.exp(-(S - smin) / lam)
        if self.flags["commit"] and ppl:
            wgt = wgt * self.mode_mask(P, S, x0, ppl, lam)
        wgt /= wgt.sum()
        newU = (wgt[:, None, None] * U).sum(0)
        newU[1:-1] = (newU[:-2] + 2 * newU[1:-1] + newU[2:]) / 4.0
        self.U = newU
        best = int(S.argmin())
        u = self.U[0].copy()
        blocked = bool(coll.all())
        if coll[best] and not blocked:
            u = U[best, 0].copy()
        Pm, Ym, _ = self.rollout(self.U[None], x0, v0, g)
        self.U = np.roll(self.U, -1, 0)
        self.U[-1] = self.U[-2]
        self.last = dict(best_cost=float(smin), blocked=blocked, traj=Pm[0], clear=float(dmin[best]), i0=i0,
                         ess=float(1.0 / (wgt ** 2).sum()))
        return (u if not blocked else np.zeros(3)), self.last


# =============================================================================
#  BASELINE cai lai tu CONG THUC bai bao (khong chep ma). Dung chung MPPI, tracker, ~nl voi p3.
# =============================================================================
class PGIFMPPI(MPPI):
    """PGIF-MPPI (Mundane et al., arXiv 2608.08323, Eq. 10-16): truong tuong tac Gauss di huong quanh vi tri
    nguoi du doan van toc khong doi o MOI buoc tau, cong theo nguoi va theo thoi gian, khong chiet khau, khong phat
    va cham cung voi nguoi (chi chi phi mem):
        C = sum_tau sum_i exp(-1/2 [(d_par/s_par)^2 + (d_perp/s_perp)^2]),
        s_par = 1.2 + 0.5 s (phia truoc, d_par >= 0) | 0.5 (phia sau), s_perp = 0.6 m.
    Khac ban goc (ghi trong bao cao): robot o day la 2 dia (bai: diem tam); trong so tuong doi theo chi phi MPPI cua ta
    (bai: w_human 1e6 so goal 1e3 voi lambda 1000) -> w_h la tham so chinh; 'hard' = them phat va cham cung kieu MPPI."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.w_h, self.s_par0, self.s_park, self.s_back, self.s_perp = 30.0, 1.2, 0.5, 0.5, 0.6
        self.hard = 0.0
        self.sig_scale = 1.0

    def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
        S, coll, dmin = super().cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        K, T = P.shape[:2]
        tt = np.arange(1, T + 1) * self.dt
        for (px, py, vx, vy, rad) in people:
            sp = math.hypot(vx, vy)
            ux, uy = (vx / sp, vy / sp) if sp > 1e-3 else (1.0, 0.0)
            rx, ry = P[..., 0] - (px + vx * tt), P[..., 1] - (py + vy * tt)
            dpar = rx * ux + ry * uy
            dper = -rx * uy + ry * ux
            spar = np.where(dpar >= 0, self.s_par0 + self.s_park * sp, self.s_back) * self.sig_scale
            S += self.w_h * np.exp(-0.5 * ((dpar / spar) ** 2 + (dper / (self.s_perp * self.sig_scale)) ** 2)).sum(1) / T
            if self.hard:
                d = self.ppl_dist(P, Y, px + vx * tt, py + vy * tt, rad)
                S += self.hard * (d < 0).any(1)
        return S, coll, dmin


class DRAMPPI(MPPI):
    """DRA-MPPI (Trevisan, Mustafa et al., arXiv 2506.21205, Eq. 8-14): XAC SUAT VA moi buoc
    P_t = 1 - prod_o (1 - P_t^o), P_t^o = tich phan Gauss N(mu_t, s_t^2 I) cua nguoi tren dia ban kinh r (robot+nguoi)
    quanh robot; chi phi C = w_soft * P + w_hard * [P > p_thr] cong theo buoc. Bai uoc luong P bang Monte Carlo 20 000
    diem; o day TINH DUNG bang CDF chi-binh-phuong lech tam (Rice) qua bang tra theo (t, d) -> cung dai luong, re hon.
    Bat dinh: van toc nguoi + nhieu N(0, sig_w^2) moi buoc -> s_t = sig_w * dt * sqrt(t/dt) (mo hinh mo phong cua bai,
    sig_w = 0.3). Robot 2 dia: P_robot = 1 - (1-P_mui)(1-P_duoi) (xap xi doc lap)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.w_soft, self.w_hard, self.p_thr, self.sig_w, self.sig0 = 100.0, 20000.0, 0.05, 0.3, 0.05
        self.r_extra = 0.0
        self._tab = None

    def _table(self, rad):
        from scipy.stats import ncx2
        key = (rad, self.sig_w, self.sig0, self.r_extra, self.T, self.dt)
        if self._tab is not None and self._tab[0] == key:
            return self._tab[1], self._tab[2]
        T = self.T
        tt = np.arange(1, T + 1) * self.dt
        s = np.sqrt(self.sig0 ** 2 + (self.sig_w ** 2) * self.dt * tt)          # = sig_w*dt*sqrt(n) khi sig0 = 0
        r = self.r_body + rad + self.r_extra
        dg = np.linspace(0, 4.0, 401)
        tab = np.array([ncx2.cdf((r / st) ** 2, 2, (dg / st) ** 2) for st in s])   # (T, 401)
        self._tab = (key, dg, tab)
        return dg, tab

    def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
        S, coll, dmin = super().cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        if not people:
            return S, coll, dmin
        K, T = P.shape[:2]
        tt = np.arange(1, T + 1) * self.dt
        free = np.ones((K, T))
        cY, sY = np.cos(Y), np.sin(Y)
        for (px, py, vx, vy, rad) in people:
            dg, tab = self._table(rad)
            qx, qy = px + vx * tt, py + vy * tt
            for off in (self.c_off, -self.c_off):
                d = np.hypot(P[..., 0] + off * cY - qx, P[..., 1] + off * sY - qy)
                k = np.clip(d / dg[-1] * (len(dg) - 1), 0, len(dg) - 1.001)
                i = k.astype(int)
                f = k - i
                rows = np.arange(T)[None]
                p = tab[rows, i] * (1 - f) + tab[rows, i + 1] * f
                free *= 1.0 - p
        Pt = 1.0 - free
        S += (self.w_soft * Pt + self.w_hard * (Pt > self.p_thr)).sum(1) / T
        return S, coll, dmin
