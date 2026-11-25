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
    def __init__(self, priors=(), flags=None, prior_frac=0.3, hold=6, w_value=0.3, w_ev=6.0, **kw):
        super().__init__(**kw)
        self.priors = list(priors)
        self.flags = dict(cap=True, lat=True, dyn=True, evade=True, turn=False, mode=False,
                          prior=bool(self.priors), value=False, rate=True, adapt=True, vis=False)
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

    def __init__(self, flags=None, **kw):
        fl = dict(evade=False, turn=False, mode=False, rate=False, prim=True, grad=True, haz=True, rest=True,
                  hyp=False, cvar=False, commit=False, slow=False, path=False)
        fl.update(flags or {})
        super().__init__(flags=fl, **kw)
        self.w_hz, self.s0, self.q0, self.hz_scale, self.hz_slack, self.hz_floor = 20.0, 0.25, 0.35, 0.25, 0.1, 0.10
        self.w["ppl"], self.ppl_len = 16.0, 0.3
        self.c_hit = 300.0
        self.w_risk, self.beta = 30.0, 0.5
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
             seen=None, tentative=(), gains=None, obs_fn=None, now=None):
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
        if self.flags["hyp"] and ppl:
            S = S + self.hyp_cost(P, Y, ppl)
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
