#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fastsim.py — mo phong 2D NHANH, DONG HO AO, chay DUNG CODE THAT cua robot:
robot_ros._navigate_mpc + OccGrid + BlobTracker + A* + bo dieu khien (khong viet lai vong dieu
khien -> sua thuat toan o dau thi do ngay o do). Chi thay: cam bien (tia 2D), than robot (dong hoc
bac 1 + he so + tre), nguoi (movers.Crowd.step that), dong ho.

Dung de PHAT TRIEN va phan tich loi (nghin luot/gio). Ket luan cuoi van phai do trong Gazebo.

  venv/bin/python fastsim.py --suite office --configs mppi dwa --trials 10 --out results/fs_x --jobs 12
  venv/bin/python fastsim.py --suite gen --seeds 0-99 --configs mppi ... --out ...
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_k] = "1"
import argparse
import csv
import json
import math
import random
import subprocess
import sys
import time as real_time
import types
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SDF_OFFICE = os.path.expanduser("~/ros2_ws/src/unitree_go2_ros2/unitree_go2_description/worlds/voice_office.sdf")
SIM_BODY = (0.32, 0.25, 0.16)                     # nhu eval_sim
PERSON_R = 0.22


# ------------------------------------------------------------------ the gioi
def load_boxes(path):
    out = []
    for m in ET.parse(path).getroot().iter("model"):
        nm = m.get("name") or ""
        if nm.startswith(("cart", "person")):
            continue
        pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
        size = m.find("./link/collision/geometry/box/size")
        rad = m.find("./link/collision/geometry/cylinder/radius")
        if size is not None:
            sx, sy, sz = (float(v) for v in size.text.split())
            if sz > 0.02 and pose[2] + sz / 2 > 0.08:            # bo san / tham
                out.append((pose[0], pose[1], sx, sy, pose[5]))
        elif rad is not None:
            d = 2 * float(rad.text)
            out.append((pose[0], pose[1], d, d, 0.0))
    return out


class Boxes:
    def __init__(self, boxes):
        b = np.array(boxes, float)
        self.b = b
        self.c, self.s = np.cos(b[:, 4]), np.sin(b[:, 4])

    def sd(self, pts):
        """khoang cach co dau tu (N,2) -> (N,) toi hop gan nhat"""
        dx = pts[:, 0:1] - self.b[None, :, 0]
        dy = pts[:, 1:2] - self.b[None, :, 1]
        lx, ly = self.c * dx + self.s * dy, -self.s * dx + self.c * dy
        qx, qy = np.abs(lx) - self.b[:, 2] / 2, np.abs(ly) - self.b[:, 3] / 2
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
        return d.min(1)

    def normal(self, x, y):
        dx, dy = x - self.b[:, 0], y - self.b[:, 1]
        lx, ly = self.c * dx + self.s * dy, -self.s * dx + self.c * dy
        qx = np.clip(lx, -self.b[:, 2] / 2, self.b[:, 2] / 2)
        qy = np.clip(ly, -self.b[:, 3] / 2, self.b[:, 3] / 2)
        ex, ey = lx - qx, ly - qy
        d = np.hypot(ex, ey)
        k = int(d.argmin())
        if d[k] < 1e-6:
            return 0.0, np.zeros(2)
        n = np.array([self.c[k] * ex[k] - self.s[k] * ey[k], self.s[k] * ex[k] + self.c[k] * ey[k]]) / d[k]
        return float(d[k]), n

    def cast(self, ox, oy, th, rmax):
        """tia (N,) goc the gioi -> khoang cach (slab)"""
        near = np.hypot(self.b[:, 0] - ox, self.b[:, 1] - oy) < rmax + np.hypot(self.b[:, 2], self.b[:, 3]) / 2
        b, c, s = self.b[near], self.c[near], self.s[near]
        if not len(b):
            return np.full(len(th), rmax)
        dx, dy = ox - b[:, 0], oy - b[:, 1]
        lx, ly = c * dx + s * dy, -s * dx + c * dy
        ct, st = np.cos(th)[:, None], np.sin(th)[:, None]
        ux, uy = c * ct + s * st, -s * ct + c * st
        with np.errstate(divide="ignore", invalid="ignore"):
            ux = np.where(np.abs(ux) < 1e-9, 1e-9, ux)
            uy = np.where(np.abs(uy) < 1e-9, 1e-9, uy)
            tx1, tx2 = (-b[:, 2] / 2 - lx) / ux, (b[:, 2] / 2 - lx) / ux
            ty1, ty2 = (-b[:, 3] / 2 - ly) / uy, (b[:, 3] / 2 - ly) / uy
        t0 = np.maximum(np.minimum(tx1, tx2), np.minimum(ty1, ty2))
        t1 = np.minimum(np.maximum(tx1, tx2), np.maximum(ty1, ty2))
        t = np.where((t1 >= np.maximum(t0, 0)), np.maximum(t0, 0), rmax)
        return np.minimum(t.min(1), rmax)


def cast_circles(ox, oy, th, circ, rmax):
    """circ: list (x, y, r)"""
    out = np.full(len(th), rmax)
    for x, y, r in circ:
        dx, dy = x - ox, y - oy
        if math.hypot(dx, dy) > rmax + r:
            continue
        b = dx * np.cos(th) + dy * np.sin(th)
        disc = b * b - (dx * dx + dy * dy - r * r)
        m = (disc > 0) & (b > 0)
        out[m] = np.minimum(out[m], np.maximum(b[m] - np.sqrt(disc[m]), 0.0))
    return out


def footprint(x, y, yaw, body=SIM_BODY, n=8):
    f, r, hw = body
    A, B = np.meshgrid(np.linspace(-r, f, n), np.linspace(-hw, hw, 4))
    A, B = A.ravel(), B.ravel()
    c, s = math.cos(yaw), math.sin(yaw)
    return np.stack([x + c * A - s * B, y + s * A + c * B], 1)


# ------------------------------------------------------------------ ban do sinh ngau nhien
def gen_world(seed):
    """Ban do ngau nhien giai duoc. Ho: van phong / kho / sanh / hanh lang + cua / bua bon.
    -> dict(boxes, start, goal, crowd, carts, bounds, kind). Cung seed -> cung ban do."""
    from nav_local import OccGrid, plan
    for attempt in range(60):
        rng = random.Random(seed * 1000 + attempt)
        U = rng.uniform
        kind = ["office", "warehouse", "lobby", "corridor", "clutter"][seed % 5]
        W, H = U(12, 18), U(9, 14)
        B = [(0, H / 2, W, .2, 0), (0, -H / 2, W, .2, 0), (W / 2, 0, .2, H, 0), (-W / 2, 0, .2, H, 0)]
        if kind == "office":
            x = -W / 2 + U(2.2, 3.0)
            while x < W / 2 - 2:
                y = -H / 2 + U(1.0, 1.6)
                while y < H / 2 - 1.0:
                    if rng.random() < .75:
                        B.append((x, y, .75, 1.4, U(-.05, .05)))
                        if rng.random() < .8:
                            B.append((x + U(.65, .95) * rng.choice([-1, 1]), y + U(-.4, .4), .45, .45, U(0, 3)))
                    y += U(2.1, 2.9)
                x += U(2.6, 3.4)
            for _ in range(rng.randint(2, 6)):
                B.append((U(-W / 2, W / 2), U(-H / 2, H / 2), U(.25, .5), U(.25, .5), U(0, 3)))
        elif kind == "warehouse":
            y = -H / 2 + U(1.6, 2.2)
            while y < H / 2 - 1.2:
                gap = U(-W / 4, W / 4)
                for sx0, sx1 in ((-W / 2 + 1.5, gap - .9), (gap + .9, W / 2 - 1.5)):
                    if sx1 - sx0 > 1.0:
                        B.append(((sx0 + sx1) / 2, y, sx1 - sx0, .6, 0))
                for _ in range(rng.randint(1, 3)):
                    B.append((U(-W / 2 + 1.5, W / 2 - 1.5), y + rng.choice([-1, 1]) * U(.55, .9), U(.5, .9), U(.4, .7), 0))
                y += U(2.2, 3.0)
        elif kind == "lobby":
            for _ in range(rng.randint(5, 10)):
                B.append((U(-W / 2 + 1, W / 2 - 1), U(-H / 2 + 1, H / 2 - 1), U(.4, 1.8), U(.4, .8), U(0, 3)))
        elif kind == "corridor":
            for xk in (-W / 6, W / 6):
                gy = U(-H / 2 + 1.5, H / 2 - 1.5)
                g = U(.95, 1.4)
                lo, hi = gy - g / 2, gy + g / 2
                B.append((xk, (-H / 2 + lo) / 2, .2, lo + H / 2, 0))
                B.append((xk, (H / 2 + hi) / 2, .2, H / 2 - hi, 0))
            for _ in range(rng.randint(5, 10)):
                B.append((U(-W / 2 + 1, W / 2 - 1), U(-H / 2 + 1, H / 2 - 1), U(.3, 1.2), U(.3, .7), U(0, 3)))
        else:
            for _ in range(int(W * H * U(.12, .19))):
                B.append((U(-W / 2, W / 2), U(-H / 2, H / 2), U(.25, .9), U(.25, .7), U(0, 3)))
        s = (-W / 2 + U(.9, 1.5), U(-H / 2 + 1.2, H / 2 - 1.2))
        g = (W / 2 - U(.9, 1.5), U(-H / 2 + 1.2, H / 2 - 1.2))
        B = B[:4] + [b for b in B[4:] if min(math.hypot(b[0] - q[0], b[1] - q[1]) - math.hypot(b[2], b[3]) / 2
                                             for q in (s, g)) > .75]
        if Boxes(B).sd(np.array([s, g])).min() < .75:
            continue
        gr = OccGrid(xmin=-W / 2 - 1, ymin=-H / 2 - 1, width=W + 2, height=H + 2)
        for b in B:
            gr.mark_box(*b)
        pts, _ = plan(gr, s, g, lethal=.40, soft=.80)
        if pts:
            n = rng.choice([0, 0, 2, 3, 4, 5, 6])
            return dict(boxes=B, start=(*s, U(-3.1, 3.1)), goal=g, kind=kind, seed=seed,
                        crowd=dict(n=n, region=((-W / 2 + .8, W / 2 - .8), (-H / 2 + .8, H / 2 - .8)), seed=seed) if n else None,
                        carts=[], bounds=(-W / 2 - 1, -H / 2 - 1, W + 2, H + 2))
    raise RuntimeError(f"seed {seed}: khong sinh duoc")


def office_task(name, trial):
    """8 bai van phong (nhu eval_sim.office_tasks); trial doi seed dam dong nhe qua thoi diem bat dau."""
    import yaml
    wp = {k: tuple((v.get("pose") if isinstance(v, dict) else v)[:2]) for k, v in
          yaml.safe_load(open(os.path.join(HERE, "waypoints_office.yaml"))).items()}
    O = (0.0, 0.0, 0.0)
    T = {"clutter:qua_khoi_so_le": (O, wp["sảnh vào"], None, []),
         "clutter:van_phong": (O, wp["văn phòng"], None, []),
         "clutter:slalom_coc": ((5.7, 0.0, 0.0), (13.3, 0.0), None, []),
         "clutter:loi_pallet": (O, wp["cuối kho"], None, []),
         "clutter:bep_xa": (O, wp["bếp"], None, []),
         "crowd:sanh_8_nguoi": ((-4.0, .3, 0.0), wp["kho hàng"], dict(n=8, region=((-4.5, 4.5), (-4.5, 4.5)), seed=21), []),
         "crowd:kho_xe_day": ((5.6, 0.0, 0.0), wp["cuối kho"], dict(n=4, region=((5.5, 14.5), (-9.5, 9.5)), seed=22),
                              [[(6.0, -9.3), (14.0, -9.3)], [(6.0, 9.3), (14.0, 9.3)], [(6.0, 1.7), (13.4, 1.7)]]),
         "crowd:van_phong_dong": (O, wp["bếp"], dict(n=6, region=((-14.5, -5.5), (-9.5, 9.5)), seed=23), [])}
    s, g, c, carts = T[name]
    return dict(boxes=load_boxes(SDF_OFFICE), start=s, goal=g, crowd=c, carts=carts,
                bounds=(-16.0, -11.0, 32.0, 22.0), kind=name.split(":")[0], seed=trial)


OFFICE = ["clutter:qua_khoi_so_le", "clutter:van_phong", "clutter:slalom_coc", "clutter:loi_pallet",
          "clutter:bep_xa", "crowd:sanh_8_nguoi", "crowd:kho_xe_day", "crowd:van_phong_dong"]


# ------------------------------------------------------------------ mo phong
class Clock:
    """Thay time.monotonic / time.sleep cho ca tien trinh: sleep = day mo phong."""

    def __init__(self):
        self.t, self.sim = 100.0, None

    def monotonic(self):
        return self.t

    def sleep(self, dt):
        if self.sim is not None and dt > 0:
            self.sim.advance(dt)
        else:
            self.t += max(dt, 0.0)


class SyncThread:
    def __init__(self, target=None, args=(), daemon=None, **kw):
        self.f, self.a = target, args

    def start(self):
        self.f(*self.a)


class EpisodeEnd(Exception):
    pass


class Sim:
    DT = 0.05

    def __init__(self, W, config, trial, regime="champ", oracle=False, tmax=300.0):
        self.W, self.tmax, self.oracle = W, tmax, oracle
        self.boxes = Boxes(W["boxes"])
        # moi luot: seed nhieu rieng, KHONG phu thuoc cau hinh -> ghep cap duoc giua cac cau hinh
        ss = np.random.SeedSequence([W["seed"], trial, 7])
        self.rng = np.random.default_rng(ss)
        u = self.rng.uniform
        if regime == "champ":                           # gait CHAMP trong Gazebo
            self.gain = np.array([u(.48, .66), u(.5, .75), u(.6, .85)])
        else:                                           # Go2 that (SportClient)
            self.gain = np.array([u(.85, 1.0), u(.8, 1.0), u(.85, 1.0)])
        self.tau, self.delay = u(.18, .32), 0.05
        self.x = np.array(W["start"], float)
        self.v = np.zeros(3)
        self.cmd, self.cmdq = np.zeros(3), []
        self.clock = CLOCK
        self.t0 = self.clock.t
        self.k = 0
        self.traj, self.times = [], []
        self.col = None
        self.min_static, self.min_person = 9.0, 9.0
        self.prev_people = None
        self.crowd = None
        if W["crowd"]:
            self.crowd = FastCrowd(W, self, trial)
            for _ in range(int(2.0 / self.DT)):
                self.crowd.step(self.DT)
        self.carts = [FastCart(p, self) for p in W["carts"]]
        self.r = make_robot(self, config)
        self.clock.sim = self

    # -- nguoi: (x, y, r, vx, vy)
    def people(self):
        out = []
        if self.crowd:
            out += [(p["p"][0], p["p"][1], PERSON_R, p["v"][0], p["v"][1]) for p in self.crowd.people]
        out += [(c.pos[0], c.pos[1], .45, c.v[0], c.v[1]) for c in self.carts]
        return out

    def advance(self, dt):
        end = self.clock.t + dt
        while self.clock.t < end - 1e-6:
            h = min(self.DT, end - self.clock.t)
            self.substep(h)

    def substep(self, h):
        now = self.clock.t = self.clock.t + h
        while self.cmdq and self.cmdq[0][0] <= now:
            self.cmd = self.cmdq.pop(0)[1]
        a = min(1.0, h / self.tau)
        w = self.v + a * (self.gain * self.cmd - self.v)
        if np.abs(self.cmd).sum() > .02:
            w = w + self.rng.normal(size=3) * [.015, .015, .04] * math.sqrt(h / .05)
        self.v = w
        c, s = math.cos(self.x[2]), math.sin(self.x[2])
        self.x = self.x + h * np.array([w[0] * c - w[1] * s, w[0] * s + w[1] * c, w[2]])
        if self.crowd:
            self.crowd.step(h)
        for cc in self.carts:
            cc.step(h)
        self.k += 1
        if self.k % 2 == 0:
            self.sense()
            self.check()
        self.r.odom = (self.x[0], self.x[1], self.x[2], now)
        if now - self.t0 > self.tmax:
            raise EpisodeEnd("het gio")

    def sense(self):
        r, now = self.r, self.clock.t
        x, y, yaw = self.x
        c, s = math.cos(yaw), math.sin(yaw)
        circ = [(p[0], p[1], p[2]) for p in self.people()]
        rot = np.array([[c, s], [-s, c]])
        # LiDAR 360 tia, dat truoc 0.2 m, mu < 0.5 m
        lx, ly = x + .2 * c, y + .2 * s
        th = np.linspace(-math.pi, math.pi, 360, endpoint=False)
        d = np.minimum(self.boxes.cast(lx, ly, th, 6.0), cast_circles(lx, ly, th, circ, 6.0))
        dm = d + self.rng.normal(size=len(d)) * .01
        drop = self.rng.random(len(d)) < .02
        hit = (d < 5.99) & (d > .5) & ~drop
        pts = np.stack([lx + dm[hit] * np.cos(th[hit]), ly + dm[hit] * np.sin(th[hit])], 1)
        pb = (pts - [x, y]) @ rot.T
        rr = np.hypot(pb[:, 0], pb[:, 1])
        ok = rr > .42
        r.local_obs, r.local_t = pb[ok], now
        wpts = pts[ok]
        if self.k % 4 == 0:
            fm = (d >= 5.99) & ~drop
            free = np.stack([lx + 4.2 * np.cos(th[fm]), ly + 4.2 * np.sin(th[fm])], 1)
            r.tracker.update(wpts, (x, y), now)
            r.grid.integrate(lx, ly, wpts, free_pts=free)
            r.grid.decay(period=1.0)
            r.depth_grid.decay(period=1.0)
        # D435i: +-43 do, 0.3-4 m
        cx, cy = x + .3 * c, y + .3 * s
        thd = yaw + np.linspace(-.75, .75, 140)
        dd = np.minimum(self.boxes.cast(cx, cy, thd, 4.0), cast_circles(cx, cy, thd, circ, 4.0))
        h = (dd < 3.99) & (dd > .12)
        pd = np.stack([cx + dd[h] * np.cos(thd[h]), cy + dd[h] * np.sin(thd[h])], 1)
        pbd = (pd - [x, y]) @ rot.T
        ok = np.hypot(pbd[:, 0], pbd[:, 1]) > .40
        r.local_depth, r.depth_t = pbd[ok], now
        if self.k % 4 == 0:
            fr = np.stack([cx + dd * np.cos(thd), cy + dd * np.sin(thd)], 1)[~h]
            r.depth_grid.integrate(cx, cy, pd[ok], max_range=3.5, clear_range=2.5, fov=(yaw, math.radians(40)),
                                   free_pts=fr)

    def check(self):
        now = self.clock.t - self.t0
        x, y, yaw = self.x
        fp = footprint(x, y, yaw)
        self.traj.append((x, y, yaw))
        self.times.append(now)
        ds = float(self.boxes.sd(fp).min())
        self.min_static = min(self.min_static, ds)
        ppl = self.people()
        for k, (px, py, rad, vx, vy) in enumerate(ppl):
            if rad >= .45:
                d = float(np.hypot(np.maximum(np.abs(fp[:, 0] - px) - .3, 0), np.maximum(np.abs(fp[:, 1] - py) - .45, 0)).min())
                d = d if d > 0 else -.01
            else:
                d = float(np.hypot(fp[:, 0] - px, fp[:, 1] - py).min() - rad)
            if d < self.min_person:
                self.min_person = d
            if d < 0 and self.col is None:
                ux, uy = px - x, py - y
                n = math.hypot(ux, uy) or 1
                wx, wy = self.v[0] * math.cos(yaw) - self.v[1] * math.sin(yaw), self.v[0] * math.sin(yaw) + self.v[1] * math.cos(yaw)
                rin, pin = (wx * ux + wy * uy) / n, -(vx * ux + vy * uy) / n
                self.col = dict(kind="cart" if rad >= .45 else "person", t=round(now, 1), robot_in=round(rin, 2),
                                person_in=round(pin, 2), robot_v=round(math.hypot(wx, wy), 2), wz=round(float(self.v[2]), 2),
                                bearing=round(math.degrees(math.atan2(math.sin(math.atan2(uy, ux) - yaw), math.cos(math.atan2(uy, ux) - yaw)))),
                                at_fault=int(rin > .1 or abs(self.v[2]) > .3))
                raise EpisodeEnd("va nguoi")
        if ds < 0 and self.col is None:
            self.col = dict(kind="static", t=round(now, 1), robot_v=round(float(np.hypot(*self.v[:2])), 2),
                            wz=round(float(self.v[2]), 2), at_fault=1)
            raise EpisodeEnd("va vat")


def make_crowd_class():
    import movers

    class _Crowd(movers.Crowd):
        def __init__(self, W, sim, trial):                # bo phan gz cua lop cha
            from nav_local import OccGrid, plan
            cc = W["crowd"]
            self.np, self.plan, self.sim = np, plan, sim
            self.rng = random.Random(cc["seed"] * 7919 + trial)
            self.region = cc["region"]
            self.robots = [types.SimpleNamespace(map_pose=lambda: tuple(sim.x))]
            bx = W["bounds"]
            key = id(W)
            self.grid = OccGrid(xmin=bx[0], ymin=bx[1], width=bx[2], height=bx[3])
            for b in W["boxes"]:
                self.grid.mark_box(*b)
            self.bx = sim.boxes
            self.people = []
            for k in range(cc["n"]):
                for _ in range(50):
                    p = self._free_point()
                    if math.hypot(p[0] - sim.x[0], p[1] - sim.x[1]) > 1.2:
                        break
                self.people.append(dict(model=str(k), p=np.array(p, float), v=np.zeros(2),
                                        v0=min(1.2, max(.6, self.rng.gauss(.9, .15))), r=.22, path=[],
                                        wait=self.rng.uniform(0, 2), distracted=self.rng.random() < cc.get("distracted", .3)))

        def _wall_dist(self, x, y):
            return self.bx.normal(x, y)
    return _Crowd


class FastCart:
    def __init__(self, path, sim, speed=.45, stop_near=1.0):
        self.pts, self.sim, self.speed, self.stop = list(path), sim, speed, stop_near
        self.seg_t, self.pos, self.v = 0.0, path[0], (0.0, 0.0)

    def step(self, dt):
        a, b = self.pts
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        hx, hy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        dx, dy = self.sim.x[0] - self.pos[0], self.sim.x[1] - self.pos[1]
        if math.hypot(dx, dy) < self.stop and dx * hx + dy * hy > 0:
            self.v = (0.0, 0.0)
            return
        self.seg_t += self.speed * dt / L
        if self.seg_t >= 1:
            self.seg_t, self.pts = 0.0, self.pts[::-1]
            a, b = self.pts
            hx, hy = -hx, -hy
        self.pos = (a[0] + self.seg_t * (b[0] - a[0]), a[1] + self.seg_t * (b[1] - a[1]))
        self.v = (hx * self.speed, hy * self.speed)


def make_robot(sim, config):
    import threading
    import robot_ros
    from nav_local import BlobTracker, OccGrid
    robot_ros.threading.Thread = SyncThread
    bx = sim.W["bounds"]

    class R(robot_ros.RosRobotTools):
        def __init__(self):
            pass

        def _twist(self, vx=0.0, vy=0.0, wz=0.0):
            self.sim.cmdq.append((self.sim.clock.t + self.sim.delay, np.array([vx, vy, wz], float)))

        def _publish_path(self, pts):
            self.last_path = [(float(a), float(b)) for a, b in pts]

        def notify(self, text):
            pass

        def _body(self, *a):
            pass
    r = R()
    r.sim = sim
    r.__dict__.update(
        label="go2", ns="", limits=(.6, .4, 1.0, 6.0), closed_loop=True, avoid=True, goto_speed=.35, goto_turn=.8,
        origin=(0., 0., 0.), priority=0, use_depth=True, detour_enabled=True, evade_enabled=True, people_aware=True,
        state="", coordinate=True, controller=config, vel_gain=.5, vel_gains=np.array([.5, .5, .5]), nav_prefs={},
        v_world=(0., 0.), local_traj=[], _ctrl=None, _ctrl_goal=None, odom=(*sim.x, sim.clock.t), rp=(0., 0.),
        local_obs=np.empty((0, 2)), local_t=0.0, local_depth=np.empty((0, 2)), depth_t=0.0, body=(0, 0, 0, 0),
        goal=None, navigating=True, last_stats={"travel_m": 0.0, "replans": 0, "brakes": 0, "yield_s": 0., "backups": 0},
        _cancel=threading.Event(), tracker=BlobTracker(),
        grid=OccGrid(xmin=bx[0], ymin=bx[1], width=bx[2], height=bx[3]),
        depth_grid=OccGrid(xmin=bx[0], ymin=bx[1], width=bx[2], height=bx[3], hit=1, miss=1, occ_thresh=3))
    if sim.oracle:                                        # cam bien NGUOI hoan hao (chan doan: loi o dau?)
        class OT:
            def update(self, *a):
                pass

            def movers(self, **kw):
                return [dict(p=np.array(p[:2]), v=np.array(p[3:]), hits=9) for p in sim.people()
                        if math.hypot(p[3], p[4]) > .05 or True]
        r.tracker = OT()
    return r


CLOCK = Clock()
FastCrowd = None


def run_episode(W, config, trial, regime="champ", oracle=False):
    global FastCrowd
    if FastCrowd is None:
        FastCrowd = make_crowd_class()
    import nav_local
    real0 = real_time.perf_counter()
    CLOCK.sim, CLOCK.t = None, 100.0
    real_time.monotonic, real_time.sleep = CLOCK.monotonic, CLOCK.sleep
    sim = Sim(W, config, trial, regime, oracle)
    why = "?"
    # seed bo dieu khien theo (the gioi, luot): khong de may man co dinh cua seed=0
    orig = nav_local.np.random.default_rng
    try:
        sim.advance(1.0)                                  # cam bien len hinh 1 s nhu Gazebo
        sim.r._ctrl = sim.r._make_ctrl()
        sim.r._ctrl_kind = config
        if hasattr(sim.r._ctrl, "rng"):
            sim.r._ctrl.rng = np.random.default_rng([W["seed"], trial, 11])
        sim.t0 = sim.clock.t
        ok, why = sim.r._navigate(*W["goal"], tol=.2)
    except EpisodeEnd as e:
        why = str(e)
    finally:
        CLOCK.sim = None
        nav_local.np.random.default_rng = orig
    err = math.hypot(sim.x[0] - W["goal"][0], sim.x[1] - W["goal"][1])
    P = np.array(sim.traj) if sim.traj else np.zeros((1, 3))
    trav = float(np.hypot(*np.diff(P[:, :2], axis=0).T).sum()) if len(P) > 1 else 0.0
    col = sim.col
    return dict(success=int(err < .35 and col is None), why=why, err=round(err, 3), time=round(sim.clock.t - sim.t0, 1),
                travel=round(trav, 2), col=(col or {}).get("kind", ""), fault=(col or {}).get("at_fault", ""),
                min_static=round(sim.min_static, 3), min_person=round(sim.min_person, 3),
                info=json.dumps(col or {}), cpu=round(real_time.perf_counter() - real0, 1),
                traj=[(round(a, 2), round(b, 2), round(c, 2)) for a, b, c in P[::5]])


FIELDS = ["world", "kind", "npeople", "trial", "config", "success", "why", "err", "time", "travel", "col", "fault",
          "min_static", "min_person", "info", "cpu"]


def worker(a):
    jobs = json.load(open(a.worker))
    f = open(a.out, "a", newline="")
    w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
    cache = {}
    for kind, name, trial, cfg in jobs:
        key = (kind, name, trial if kind == "office" else 0)
        if key not in cache:
            cache = {key: office_task(name, trial) if kind == "office" else gen_world(int(name))}
        W = cache[key]
        try:
            row = run_episode(W, cfg, trial, a.regime, a.oracle)
        except Exception as e:                                  # noqa: BLE001
            import traceback
            traceback.print_exc()
            row = dict(success="", why="EXC " + repr(e)[:80])
        row.update(world=name, kind=W["kind"], npeople=(W["crowd"] or {}).get("n", 0) + len(W["carts"]), trial=trial, config=cfg)
        w.writerow(row)
        f.flush()
        if a.traj and row.get("traj"):
            with open(a.out.replace(".csv", ".jsonl"), "a") as g:
                g.write(json.dumps(dict(k=[name, trial, cfg], v=row["traj"])) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="gen")
    ap.add_argument("--seeds", default="0-49")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--configs", nargs="+", default=["mppi"])
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--out", default="results/fs_test")
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--regime", default="champ")
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--traj", action="store_true")
    ap.add_argument("--worker")
    a = ap.parse_args()
    if a.worker:
        return worker(a)
    os.makedirs(a.out, exist_ok=True)
    if a.suite == "office":
        worlds = [("office", n) for n in OFFICE if not a.tasks or any(t in n for t in a.tasks.split(","))]
    else:
        lo, hi = (int(v) for v in a.seeds.split("-"))
        worlds = [("gen", str(s)) for s in range(lo, hi + 1)]
    jobs = [(k, n, t, c) for k, n in worlds for t in range(a.trials) for c in a.configs]
    done = set()
    for fn in os.listdir(a.out):
        if fn.endswith(".csv"):
            done |= {(r["world"], int(r["trial"]), r["config"]) for r in csv.DictReader(open(os.path.join(a.out, fn)))}
    jobs = [j for j in jobs if (j[1], j[2], j[3]) not in done]
    # xoay vong theo (the gioi, luot) -> moi tien trinh giu nguyen 1 the gioi, moi cau hinh rai deu
    chunks = [[] for _ in range(a.jobs)]
    keys = sorted({(j[1], j[2]) for j in jobs}, key=lambda q: (q[1], q[0]))
    idx = {q: i % a.jobs for i, q in enumerate(keys)}
    for j in jobs:
        chunks[idx[(j[1], j[2])]].append(j)
    ps = []
    for i, ch in enumerate(chunks):
        if not ch:
            continue
        jf = os.path.join(a.out, f"job_{i}.json")
        json.dump(ch, open(jf, "w"))
        of = os.path.join(a.out, f"w{i}.csv")
        if not os.path.exists(of):
            csv.DictWriter(open(of, "w", newline=""), FIELDS).writeheader()
        cmd = [sys.executable, os.path.abspath(__file__), "--worker", jf, "--out", of, "--regime", a.regime]
        cmd += ["--oracle"] if a.oracle else []
        cmd += ["--traj"] if a.traj else []
        ps.append(subprocess.Popen(cmd, stderr=open(os.path.join(a.out, f"err_{i}.log"), "a")))
    for p in ps:
        p.wait()


if __name__ == "__main__":
    main()
