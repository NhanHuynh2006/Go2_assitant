#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/env.py — moi truong RL NE VAT CAN cho Go2, chay SONG SONG tren GPU (PyTorch).

Hang nghin "phong" 12 x 12 m chay cung luc (mac dinh 2048), moi phong ngau nhien:
  - 10 tru tron + 8 hop chu nhat (so le, khe hep), tuong bao quanh
  - 5 nguoi di bo 0.3-1.2 m/s toi diem ngau nhien: 70 % TU NE robot (luc day kieu Social
    Force), 30 % "mai dien thoai" di thang khong ne - giong movers.Crowd trong Gazebo
  - mat do vat can tang dan theo chuong trinh hoc (curriculum)
Robot: CUNG mo hinh dong hoc voi nav_local.MPPI (lenh than vx, vy, wz; do tre tau;
he so van toc thuc/lenh `gain` ngau nhien 0.4-1.0 -> phu ca gait CHAMP lan Go2 that).
Than = 2 hinh tron (0.74 x 0.40 m) nhu MPPI.

Quan sat (93 so) — LAY DUOC Y HET luc chay that (nav_local.RLPolicy):
  72 tia khoang cach 360 do (toi 4 m)  <- tu ban do chiem cho LiDAR + D435i
  dich (khoang cach, sin, cos) trong khung than  <- diem 'ca rot' tren duong A*
  van toc do duoc (3) + lenh truoc (3)
  3 nguoi gan nhat: vi tri + van toc tuong doi (12)  <- BlobTracker
Hanh dong: (vx, vy, wz) trong [-1, 1] -> gioi han nhu MPPI, 10 Hz.
Phan thuong (theo ABS - He et al. RSS 2024, DRL-VO - Xie & Dames T-RO 2023):
  +10 x tien do, +15 toi dich, -15 va cham, -0.01/buoc, phat sat vat / sat nguoi,
  phat giat lenh, phat lui va di ngang nhieu.
"""

import math

import torch

TWO_PI = 2 * math.pi


class NavEnv:
    def __init__(self, n=2048, device="cuda", n_circ=10, n_rect=8, n_ped=5, n_rays=72,
                 ray_max=4.0, arena=6.0, dt=0.1, max_steps=400, seed=0, realistic=False,
                 dyn="linear"):
        """dyn: "linear"   dong hoc cu (1 he so 0.4-1.0, tau 0.15-0.35, than khong lac, van toc biet chinh xac)
                "measured" dong hoc DO DUOC (results/sysid.npz 22/11: vx bao hoa 0.29, lui 1.26, vy 0.97, wz 0.85,
                           tau 0.15/0.15/0.25, than lac) + ngau nhien hoa phu ca CHAMP lan Go2 that (~0.9 tuyen tinh);
                           van toc quan sat = sai phan vi tri (co lac) loc 0.5 nhu robot_ros._navigate_mpc
                "champ"/"real" giong fastsim regime (chi de DANH GIA 2D, khong dung train)"""
        #       "union"    hop cua CHAMP do duoc va Go2 that theo dyn/go2_params.yaml (gain, tre 0.04-0.2, gioi han gia toc)
        #       "go2"      chi dai go2_params.yaml (danh gia)
        assert dyn in ("linear", "measured", "champ", "real", "union", "go2")
        if dyn in ("union", "go2"):
            import os
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from dyn.go2_params import load
            y = load()
            self.go2 = dict(y["domain_randomization"], wob0=y["body_wobble"]["fastsim_wob"]["v"])
        self.dyn = dyn
        if dyn != "linear" and max_steps == 400:
            max_steps = 600                        # robot cham hon (0.29 m/s) -> can them gio
        self.n, self.dev = n, torch.device(device)
        self.nc, self.nr, self.np_, self.R = n_circ, n_rect, n_ped, n_rays
        self.ray_max, self.A, self.dt, self.max_steps = ray_max, arena, dt, max_steps
        self.g = torch.Generator(device=self.dev).manual_seed(seed)
        self.vmax = torch.tensor([0.6, 0.3, 1.0], device=self.dev)
        self.vmin = torch.tensor([-0.2, -0.3, -1.0], device=self.dev)
        self.ang = torch.arange(n_rays, device=self.dev) * (TWO_PI / n_rays)
        self.r_body, self.c_off = 0.20, 0.17
        # CAM BIEN THUC TE (Go2: LiDAR L1 mu < 0.45 m, D435i chi nhin +-43 do phia truoc,
        # ban do/tracker tre 0.1-0.2 s, tracker doi khi mat nguoi, nhieu + mat tia)
        self.realistic = realistic
        self.blind_r, self.cam_half = 0.45, math.radians(43)
        self.density = 0.3                         # curriculum: ti le vat can bat
        self.return_terminal = False
        self.auto_reset = True
        self.frozen = torch.zeros(n, dtype=torch.bool, device=self.dev)
        self.obs_dim = n_rays + 3 + 3 + 3 + 12
        z = lambda *s: torch.zeros(*s, device=self.dev)
        self.pose, self.v, self.goal = z(n, 3), z(n, 3), z(n, 2)
        self.cc, self.cr = z(n, n_circ, 2), z(n, n_circ)
        self.con = torch.zeros(n, n_circ, dtype=torch.bool, device=self.dev)
        self.rc, self.rh, self.ron = z(n, n_rect, 2), z(n, n_rect, 2), torch.zeros(n, n_rect, dtype=torch.bool, device=self.dev)
        self.pp, self.pv, self.ptgt = z(n, n_ped, 2), z(n, n_ped, 2), z(n, n_ped, 2)
        self.pon = torch.zeros(n, n_ped, dtype=torch.bool, device=self.dev)
        self.prush = torch.zeros(n, n_ped, dtype=torch.bool, device=self.dev)
        self.pspeed = z(n, n_ped)
        self.gain, self.tau = z(n), z(n)
        # dong hoc do duoc (chi dung khi dyn != linear)
        self.mgain, self.mtau, self.vsat, self.back = z(n, 3), z(n, 3), z(n), z(n)
        self.wob, self.sway, self.vobs, self.ucur = z(n, 3), z(n, 3), z(n, 3), z(n, 3)
        self.uold, self.acc = z(n, 3), z(n, 3) + 1e9
        self.delay = torch.zeros(n, dtype=torch.long, device=self.dev)
        self.steps = torch.zeros(n, dtype=torch.long, device=self.dev)
        self.prev_a, self.prev_d = z(n, 3), z(n)
        self.reset(torch.arange(n, device=self.dev))

    # ------------------------------------------------------------------ ngau nhien
    def _u(self, *shape, lo=0.0, hi=1.0):
        return lo + (hi - lo) * torch.rand(*shape, generator=self.g, device=self.dev)

    def reset(self, idx):
        k = len(idx)
        if k == 0:
            return
        A = self.A
        self.pose[idx, :2] = self._u(k, 2, lo=-A + 1.0, hi=A - 1.0)
        self.pose[idx, 2] = self._u(k, lo=-math.pi, hi=math.pi)
        self.v[idx] = 0.0
        d = self._u(k, lo=1.0, hi=7.0)
        th = self._u(k, lo=-math.pi, hi=math.pi)
        g = self.pose[idx, :2] + torch.stack([d * torch.cos(th), d * torch.sin(th)], 1)
        self.goal[idx] = g.clamp(-A + 0.8, A - 0.8)
        # tru tron
        self.cc[idx] = self._u(k, self.nc, 2, lo=-A, hi=A)
        self.cr[idx] = self._u(k, self.nc, lo=0.12, hi=0.5)
        self.con[idx] = self._u(k, self.nc) < self.density
        # hop
        self.rc[idx] = self._u(k, self.nr, 2, lo=-A, hi=A)
        hw = torch.stack([self._u(k, self.nr, lo=0.15, hi=1.3), self._u(k, self.nr, lo=0.15, hi=0.45)], -1)
        flip = self._u(k, self.nr) < 0.5
        self.rh[idx] = torch.where(flip[..., None], hw.flip(-1), hw)
        self.ron[idx] = self._u(k, self.nr) < self.density
        # khong dat vat len robot / dich
        for pt in (self.pose[idx, :2], self.goal[idx]):
            dc = (self.cc[idx] - pt[:, None]).norm(dim=-1) - self.cr[idx]
            self.con[idx] &= dc > 0.7
            q = (self.rc[idx] - pt[:, None]).abs() - self.rh[idx]
            dr = q.clamp(min=0).norm(dim=-1) + q.max(-1).values.clamp(max=0)
            self.ron[idx] &= dr > 0.7
        # nguoi
        self.pp[idx] = self._u(k, self.np_, 2, lo=-A + 0.5, hi=A - 0.5)
        if not hasattr(self, "pp_lag"):
            self.pp_lag = self.pp.clone()
        self.pp_lag[idx] = self.pp[idx]
        far = (self.pp[idx] - self.pose[idx, None, :2]).norm(dim=-1) > 2.0
        self.pon[idx] = (self._u(k, self.np_) < self.density * 0.8) & far
        self.prush[idx] = self._u(k, self.np_) < 0.30            # "mai dien thoai": khong ne
        self.pspeed[idx] = self._u(k, self.np_, lo=0.3, hi=1.2)
        self.ptgt[idx] = self._u(k, self.np_, 2, lo=-A + 0.5, hi=A - 0.5)
        self.gain[idx] = self._u(k, lo=0.4, hi=1.0)
        self.tau[idx] = self._u(k, lo=0.15, hi=0.35)
        if self.dyn != "linear":
            self._reset_dyn(idx, k)
        self.steps[idx] = 0
        self.prev_a[idx] = 0.0
        self.prev_d[idx] = (self.goal[idx] - self.pose[idx, :2]).norm(dim=-1)

    def _reset_dyn(self, idx, k):
        """Boc ngau nhien dong hoc cho k phong. champ/real = dung khoang cua fastsim.Sim."""
        U = lambda lo, hi, *s: self._u(k, *s, lo=lo, hi=hi)
        st = lambda *a: torch.stack(a, -1)
        tau = st(U(.12, .2), U(.12, .2), U(.2, .3))
        champ = dict(g=st(U(.88, 1.02), U(.9, 1.03), U(.75, .95)), sat=U(.26, .32), back=U(1.1, 1.35),
                     wob=U(1.0, 1.0)[:, None] * torch.tensor([.02, .02, .06], device=self.dev))
        real = dict(g=st(U(.85, 1.0), U(.8, 1.0), U(.85, 1.0)), sat=U(9.0, 9.0), back=U(1.0, 1.0),
                    wob=U(1.0, 1.0)[:, None] * torch.tensor([.006, .006, .015], device=self.dev))
        if self.dyn in ("champ", "real"):
            m = champ if self.dyn == "champ" else real
            g, sat, back, wob = m["g"], m["sat"], m["back"], m["wob"]
            dl = torch.zeros(k, dtype=torch.long, device=self.dev)
        elif self.dyn in ("union", "go2"):
            R = self.go2
            g2 = st(*(U(*R["gain"][a]) for a in "xyw"))
            t2 = st(*(U(*R["tau"][a]) for a in "xyw"))
            a2 = st(*(U(*R["acc"][a]) for a in "xyw"))
            s2, b2 = U(*R["vsat"]), U(*R["back"])
            w2 = U(*R["wob_scale"])[:, None] * torch.tensor(R["wob0"], device=self.dev)
            d2 = torch.round(U(*R["delay"]) / 0.05).long()                           # 1..4 buoc con 0.05 s
            c = self._u(k) < (0.5 if self.dyn == "union" else 0.0)                   # 50 % CHAMP (noi rong)
            pick = lambda a, b: torch.where(c if a.dim() == 1 else c[:, None], a, b)
            g = pick(st(U(.80, 1.05), U(.80, 1.10), U(.65, 1.0)), g2)
            sat, back = pick(U(.20, .40), s2), pick(U(1.0, 1.45), b2)
            wob = pick(U(.5, 1.3)[:, None] * torch.tensor([.02, .02, .06], device=self.dev), w2)
            tau = pick(st(U(.10, .25), U(.10, .25), U(.15, .35)), t2)
            dl = pick(torch.randint(0, 3, (k,), generator=self.g, device=self.dev), d2)
            self.acc[idx] = pick(torch.full_like(a2, 1e9), a2)
        else:                                                   # measured: phu rong quanh CA HAI
            champ = self._u(k) < 0.6
            pick = lambda a, b: torch.where(champ if a.dim() == 1 else champ[:, None], a, b)
            g = pick(st(U(.80, 1.05), U(.80, 1.10), U(.65, 1.0)), st(U(.70, 1.05), U(.65, 1.05), U(.70, 1.05)))
            sat = pick(U(.20, .40), U(.5, 3.0))                 # 0.29 +- va gan nhu tuyen tinh
            back = pick(U(1.0, 1.45), U(.85, 1.15))
            wob = pick(U(.5, 1.3), U(.1, .8))[:, None] * torch.tensor([.02, .02, .06], device=self.dev)
            tau = st(U(.10, .30), U(.10, .30), U(.15, .40))
            dl = torch.randint(0, 3, (k,), generator=self.g, device=self.dev)
        self.mgain[idx], self.vsat[idx], self.back[idx], self.wob[idx], self.mtau[idx] = g, sat, back, wob, tau
        self.delay[idx] = dl                                    # tre chap hanh 0 / 0.05 / 0.10 s
        self.sway[idx] = 0.0
        self.vobs[idx] = 0.0
        self.ucur[idx] = 0.0
        self.uold[idx] = 0.0

    def _move_measured(self, u):
        """2 buoc con 0.05 s: bao hoa vx (tanh), lui manh hon, tre tung truc, than lac OU 0.15 s."""
        h = 0.5 * self.dt
        alpha = (h / self.mtau).clamp(max=1.0)
        p0 = self.pose.clone()
        rho = math.exp(-h / 0.15)
        for sub in (0, 1):
            cmd = torch.where((sub < self.delay)[:, None], self.ucur, u)
            cmd = torch.where((sub + 2 < self.delay)[:, None], self.uold, cmd)
            tgt = self.mgain * cmd
            fx = torch.where(tgt[:, 0] > 0, self.vsat * torch.tanh(tgt[:, 0] / self.vsat), tgt[:, 0] * self.back)
            tgt = torch.cat([fx[:, None], tgt[:, 1:]], 1)
            self.v = self.v + torch.maximum(torch.minimum(alpha * (tgt - self.v), self.acc * h), -self.acc * h)
            moving = (cmd.abs().sum(-1, keepdim=True) > 0.02).float()
            eps = torch.randn(self.n, 3, generator=self.g, device=self.dev)
            sw = rho * self.sway + math.sqrt(1 - rho * rho) * eps * self.wob * moving
            d, self.sway = sw - self.sway, sw
            c, s = torch.cos(self.pose[:, 2]), torch.sin(self.pose[:, 2])
            self.pose = self.pose + d + h * torch.stack(
                [self.v[:, 0] * c - self.v[:, 1] * s, self.v[:, 0] * s + self.v[:, 1] * c, self.v[:, 2]], -1)
        self.uold, self.ucur = self.ucur, u
        self.pose[:, 2] = torch.remainder(self.pose[:, 2] + math.pi, TWO_PI) - math.pi
        # van toc DO DUOC nhu robot_ros: sai phan vi tri (ca lac than), loc EMA 0.5
        w = (self.pose - p0) / self.dt
        w[:, 2] = (torch.remainder(self.pose[:, 2] - p0[:, 2] + math.pi, TWO_PI) - math.pi) / self.dt
        c, s = torch.cos(self.pose[:, 2]), torch.sin(self.pose[:, 2])
        vb = torch.stack([c * w[:, 0] + s * w[:, 1], -s * w[:, 0] + c * w[:, 1], w[:, 2]], -1)
        self.vobs = 0.5 * self.vobs + 0.5 * vb

    # ------------------------------------------------------------------ hinh hoc
    def _sdf(self, p):
        """Khoang cach co dau tu diem p (n, M, 2) toi vat TINH gan nhat (tru, hop, tuong)."""
        big = torch.tensor(99.0, device=self.dev)
        dc = (p[:, :, None] - self.cc[:, None]).norm(dim=-1) - self.cr[:, None]
        dc = torch.where(self.con[:, None], dc, big).min(-1).values
        q = (p[:, :, None] - self.rc[:, None]).abs() - self.rh[:, None]
        dr = q.clamp(min=0).norm(dim=-1) + q.max(-1).values.clamp(max=0)
        dr = torch.where(self.ron[:, None], dr, big).min(-1).values
        dw = self.A - p.abs().max(-1).values
        return torch.minimum(torch.minimum(dc, dr), dw)

    def _rays(self):
        """72 tia tu tam robot, khoang cach toi be mat gan nhat (tru, hop, nguoi, tuong)."""
        n, R = self.n, self.R
        o = self.pose[:, None, :2]                                   # (n,1,2)
        th = self.pose[:, 2:3] + self.ang[None]                      # (n,R)
        d = torch.stack([torch.cos(th), torch.sin(th)], -1)          # (n,R,2)
        inf = torch.full((n, R), self.ray_max, device=self.dev)

        def circles(c, r, on):                                       # c (n,K,2)
            oc = c[:, None] - o[:, :, None]                          # (n,1,K,2)
            tca = (oc * d[:, :, None]).sum(-1)                       # (n,R,K)
            d2 = (oc ** 2).sum(-1) - tca ** 2
            r2 = r[:, None] ** 2
            hit = (d2 < r2) & on[:, None]
            t = tca - torch.sqrt((r2 - d2).clamp(min=0))
            inside = (oc ** 2).sum(-1) < r2
            t = torch.where(inside & on[:, None], torch.zeros_like(t), t)
            t = torch.where(hit & (t >= 0) | (inside & on[:, None]), t, torch.full_like(t, 99.0))
            return t.min(-1).values

        t = torch.minimum(inf, circles(self.cc, self.cr, self.con))
        t = torch.minimum(t, circles(self._ped_pos(), torch.full_like(self.pspeed, 0.25), self._ped_seen()))
        # hop (slab)
        lo = self.rc - self.rh
        hi = self.rc + self.rh
        inv = 1.0 / torch.where(d.abs() < 1e-6, torch.full_like(d, 1e-6), d)   # (n,R,2)
        t1 = (lo[:, None] - o[:, :, None]) * inv[:, :, None]         # (n,R,K,2)
        t2 = (hi[:, None] - o[:, :, None]) * inv[:, :, None]
        tn = torch.minimum(t1, t2).max(-1).values
        tf = torch.maximum(t1, t2).min(-1).values
        ok = (tn <= tf) & (tf > 0) & self.ron[:, None]
        tr = torch.where(ok, tn.clamp(min=0), torch.full_like(tn, 99.0)).min(-1).values
        t = torch.minimum(t, tr)
        # tuong bao
        tw = torch.where(d > 0, (self.A - o) / d.clamp(min=1e-6), (-self.A - o) / d.clamp(max=-1e-6))
        t = torch.minimum(t, tw.min(-1).values)
        return t.clamp(0, self.ray_max)

    def _ped_pos(self):
        """Vi tri nguoi ma CAM BIEN thay (thuc te: tre 1 buoc ~0.1 s)."""
        return self.pp_lag if self.realistic else self.pp

    def _ped_seen(self):
        """Nguoi nao cam bien thay duoc: ngoai vung mu LiDAR, hoac trong goc nhin camera."""
        if not self.realistic:
            return self.pon
        rel = self._ped_pos() - self.pose[:, None, :2]
        d = rel.norm(dim=-1)
        ang = torch.atan2(rel[..., 1], rel[..., 0]) - self.pose[:, 2:3]
        ang = torch.atan2(torch.sin(ang), torch.cos(ang))
        in_cam = (ang.abs() < self.cam_half) & (d > 0.2)
        return self.pon & ((d > self.blind_r) | in_cam)

    def _body_circles(self):
        c, s = torch.cos(self.pose[:, 2]), torch.sin(self.pose[:, 2])
        off = torch.stack([c, s], -1) * self.c_off
        p = self.pose[:, :2]
        return torch.stack([p + off, p - off], 1)                    # (n,2,2)

    # ------------------------------------------------------------------ quan sat
    def obs(self):
        rays = self._rays()
        if self.realistic:
            rays = rays + 0.03 * torch.randn(rays.shape, generator=self.g, device=self.dev)
            drop = torch.rand(rays.shape, generator=self.g, device=self.dev) < 0.02
            rays = torch.where(drop, torch.full_like(rays, self.ray_max), rays).clamp(0, self.ray_max)
        else:
            rays = rays + 0.02 * torch.randn(rays.shape, generator=self.g, device=self.dev)
        c, s = torch.cos(self.pose[:, 2]), torch.sin(self.pose[:, 2])
        rel = self.goal - self.pose[:, :2]
        gx, gy = c * rel[:, 0] + s * rel[:, 1], -s * rel[:, 0] + c * rel[:, 1]
        dist = torch.hypot(gx, gy)
        goal = torch.stack([dist.clamp(max=5.0) / 5.0, gy / dist.clamp(min=1e-3), gx / dist.clamp(min=1e-3)], -1)
        # 3 nguoi gan nhat (khung than)
        pr = self._ped_pos() - self.pose[:, None, :2]
        seen = self._ped_seen()
        if self.realistic:                                       # tracker mat nguoi 10 %
            seen = seen & (torch.rand(seen.shape, generator=self.g, device=self.dev) > 0.1)
        dd = torch.where(seen, pr.norm(dim=-1), torch.full_like(self.pspeed, 99.0))
        idx = dd.argsort(-1)[:, :3]
        sel = lambda x: torch.gather(x, 1, idx[..., None].expand(-1, -1, 2))
        prs, pvs = sel(pr), sel(self.pv)
        vis = (torch.gather(dd, 1, idx) < 4.0).float()[..., None]
        rot = lambda v: torch.stack([c[:, None] * v[..., 0] + s[:, None] * v[..., 1],
                                     -s[:, None] * v[..., 0] + c[:, None] * v[..., 1]], -1)
        ped = torch.cat([rot(prs) / 4.0, rot(pvs)], -1) * vis      # (n,3,4)
        return torch.cat([rays / self.ray_max, goal, self.v if self.dyn == "linear" else self.vobs,
                          self.prev_a, ped.reshape(self.n, 12)], -1)

    # ------------------------------------------------------------------ buoc
    def step(self, a):
        a = a.clamp(-1, 1)
        u = self.vmin + (a + 1) * 0.5 * (self.vmax - self.vmin)
        if self.dyn != "linear":
            self._move_measured(u)
        else:
            alpha = (self.dt / self.tau).clamp(max=1.0)[:, None]
            self.v = self.v + alpha * (self.gain[:, None] * u - self.v)
            c, s = torch.cos(self.pose[:, 2]), torch.sin(self.pose[:, 2])
            self.pose[:, 0] += (self.v[:, 0] * c - self.v[:, 1] * s) * self.dt
            self.pose[:, 1] += (self.v[:, 0] * s + self.v[:, 1] * c) * self.dt
            self.pose[:, 2] = torch.remainder(self.pose[:, 2] + self.v[:, 2] * self.dt + math.pi, TWO_PI) - math.pi
        # nguoi: di toi diem dich; nguoi binh thuong NE robot (luc day giam theo khoang cach,
        # A=1.5, B=0.4 nhu movers.Crowd), nguoi "mai dien thoai" (prush) khong ne
        self.pp_lag = self.pp.clone()
        dv = self.ptgt - self.pp
        dn = dv.norm(dim=-1, keepdim=True).clamp(min=1e-3)
        want = dv / dn * self.pspeed[..., None]
        rel = self.pp - self.pose[:, None, :2]
        dr = rel.norm(dim=-1, keepdim=True).clamp(min=1e-3)
        push = 1.5 * torch.exp(-(dr - 0.6) / 0.4) * rel / dr * (~self.prush)[..., None]
        v = want + push
        sp = v.norm(dim=-1, keepdim=True).clamp(min=1e-3)
        self.pv = v / sp * torch.minimum(sp, 1.3 * self.pspeed[..., None])
        self.pp = (self.pp + self.pv * self.dt * self.pon[..., None]).clamp(-self.A + 0.3, self.A - 0.3)
        arrived = dn[..., 0] < 0.3
        new = self._u(self.n, self.np_, 2, lo=-self.A + 0.5, hi=self.A - 0.5)
        self.ptgt = torch.where(arrived[..., None], new, self.ptgt)
        # va cham / khoang ho
        clr = self._sdf(self._body_circles()).min(-1).values - self.r_body
        dped = torch.where(self.pon, (self.pp - self.pose[:, None, :2]).norm(dim=-1), torch.full_like(self.pspeed, 99.0)).min(-1).values
        col_s, col_p = clr < 0.0, dped < 0.25 + 0.3
        col = col_s | col_p
        dist = (self.goal - self.pose[:, :2]).norm(dim=-1)
        succ = dist < 0.25
        self.steps += 1
        tout = self.steps >= self.max_steps
        prog = self.prev_d - dist
        r = (10.0 * prog - 0.01 + 15.0 * succ.float() - 15.0 * col.float()
             - 0.3 * torch.exp(-clr.clamp(min=0) / 0.15) * (clr < 0.4).float()
             - 0.5 * torch.exp(-(dped - 0.55).clamp(min=0) / 0.25) * (dped < 1.5).float()
             - 0.05 * ((a - self.prev_a) ** 2).sum(-1)
             - 0.05 * (-u[:, 0]).clamp(min=0) - 0.02 * u[:, 1].abs())
        self.prev_d, self.prev_a = dist, a
        done = succ | col | tout
        info = dict(success=succ, collision=col, timeout=tout & ~succ & ~col,
                    col_static=col_s, col_ped=col_p & ~col_s, terminal=succ | col)
        if self.return_terminal:                       # TD3: can obs CUOI truoc khi reset
            info["final_obs"] = self.obs()
        if self.auto_reset:
            idx = torch.nonzero(done).flatten()
            self.reset(idx)
        else:                                          # danh gia ghep cap: dong bang tap da xong
            self.frozen = self.frozen | done
            self.v[self.frozen] = 0.0
        return self.obs(), r, done, info
