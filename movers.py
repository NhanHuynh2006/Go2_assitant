#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
movers.py — VAT CAN DONG trong sim: cho 1 model (mac dinh "person") di qua lai theo
lo trinh bang gz set_pose 20 Hz (gz-transport Python, ~10 ms / lan goi).

  python3 movers.py                                   # nguoi di cat ngang phong khach
  python3 movers.py --path "1,-0.5 1,2.8" --speed 0.5
  python3 movers.py --path "-3,1 3,1 3,-1.5" --loop   # di vong (khong quay dau)

Lich su su dung trong eval_sim.py: cac bai dyn:* chay Mover trong cung tien trinh de
biet CHINH XAC vi tri nguoi o moi thoi diem (cham khoang cach robot-nguoi).

"Lich su" nhu nguoi that: neu robot nao o gan hon `stop_near` (m) phia truoc mat thi
nguoi DUNG lai cho (khong dam vao robot dang dung yen) — bai thu do robot co NE
duoc nguoi di toi khong, chu khong phai nguoi co dam robot khong.
"""

import argparse
import math
import os
import threading
import time

os.environ.setdefault("GZ_IP", "127.0.0.1")


class Mover(threading.Thread):
    def __init__(self, path, speed=0.4, model="person", world="voice_house", hz=20.0,
                 loop=False, stop_near=0.0, robots=None, z=0.8, park=None):
        super().__init__(daemon=True)
        from gz.transport import Node
        from gz.msgs.boolean_pb2 import Boolean
        from gz.msgs.pose_pb2 import Pose
        self.Node, self.Pose, self.Boolean = Node, Pose, Boolean
        self.node = Node()
        self.path = [tuple(map(float, p)) for p in path]
        self.speed, self.model, self.hz, self.loop = speed, model, hz, loop
        self.service = f"/world/{world}/set_pose"
        self.stop_near = stop_near
        self.robots = robots or []          # doi tuong co .map_pose()
        self.z = z
        self.park = park                    # (x, y) dua ve khi dung
        self.pos = self.path[0]
        self.running = True
        self.waiting = 0.0

    def set(self, x, y, yaw=0.0):
        req = self.Pose()
        req.name = self.model
        req.position.x, req.position.y, req.position.z = x, y, self.z
        req.orientation.z, req.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self.node.request(self.service, req, self.Pose, self.Boolean, 500)
        self.pos = (x, y)

    def _blocked(self, x, y, hx, hy):
        """Co robot o gan phia truoc mat nguoi khong (de dung cho)."""
        for r in self.robots:
            p = r.map_pose() if r is not None else None
            if p is None:
                continue
            dx, dy = p[0] - x, p[1] - y
            d = math.hypot(dx, dy)
            if d < self.stop_near and (dx * hx + dy * hy) > 0:
                return True
        return False

    def run(self):
        pts = self.path + ([self.path[0]] if self.loop else [])
        seg, t = 0, 0.0
        forward = True
        dt = 1.0 / self.hz
        while self.running:
            a, b = pts[seg], pts[seg + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-6
            hx, hy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            if self.stop_near and self._blocked(x, y, hx, hy):
                self.waiting += dt
            else:
                t += self.speed * dt / L
            if t >= 1.0:
                t, seg = 0.0, seg + 1
                if seg >= len(pts) - 1:
                    if self.loop:
                        seg = 0
                    else:                                     # quay dau
                        pts = pts[::-1]
                        seg = 0
                        forward = not forward
            self.set(x, y, math.atan2(hy, hx))
            time.sleep(dt)
        if self.park:
            self.set(*self.park)

    def positions(self):
        return [self.pos]

    def stop(self):
        self.running = False


class Crowd(threading.Thread):
    """NGUOI DI BO GIONG THAT — Social Force Model (Helbing & Molnar, Phys. Rev. E 51, 1995;
    tham so CHINH TAY, khong trung mo hinh cong bo nao - xem REPORT_OSS muc 6). Moi nguoi:

      * tu chon diem muon toi (ngau nhien trong vung cho phep), di theo duong A* tren
        ban do that cua nha (khong xuyen do dac), toi noi thi dung 0.5-3 s roi di tiep
      * toc do mong muon rieng ~ N(0.9, 0.15) m/s (trong nha), quan tinh tau = 0.5 s
      * luc day tu tuong/do vat (A=2.0, B=0.12), tu nguoi khac (A=2.1, B=0.3), tu ROBOT
        (A=1.5, B=0.4) — nhung `distracted` (mac dinh 30 %) nguoi "mai dien thoai" KHONG ne
        robot: robot phai tu ne. Luc tu phia sau yeu hon (di huong, lambda = 0.35)
      * nhieu ngau nhien nho (lac lu) + gioi han toc do 1.3 x mong muon

    seed co dinh -> chay lai y het (dung cho eval_sim, so sanh cau hinh cong bang).
    """

    def __init__(self, models, region, world_sdf, robots=None, seed=0, hz=20.0,
                 distracted=0.3, world="voice_house", z=0.8, park=None):
        super().__init__(daemon=True)
        import random
        import numpy as np
        from gz.transport import Node
        from gz.msgs.boolean_pb2 import Boolean
        from gz.msgs.pose_pb2 import Pose
        from nav_local import OccGrid, plan
        self.np, self.plan = np, plan
        self.Pose, self.Boolean = Pose, Boolean
        self.node = Node()
        self.rng = random.Random(seed)
        self.models, self.region, self.robots = list(models), region, robots or []
        self.hz, self.service, self.z = hz, f"/world/{world}/set_pose", z
        self.park = park or [(20.0 + 2 * i, 20.0) for i in range(len(models))]
        self.boxes = [b for b in _sdf_boxes(world_sdf) if not b[0].startswith(("cart", "person"))]
        xs = [b[1] for b in self.boxes] or [0.0]
        ys = [b[2] for b in self.boxes] or [0.0]
        x0, y0 = min(-12.0, min(xs) - 2.0), min(-12.0, min(ys) - 2.0)
        self.grid = OccGrid(xmin=x0, ymin=y0, width=max(xs) + 2.0 - x0 if max(xs) + 2.0 - x0 > 24 else 24.0,
                            height=max(ys) + 2.0 - y0 if max(ys) + 2.0 - y0 > 24 else 24.0)
        for _, cx, cy, sx, sy, yaw in self.boxes:
            self.grid.mark_box(cx, cy, sx, sy, yaw)
        self.people = []
        for k, m in enumerate(self.models):
            p = self._free_point()
            self.people.append(dict(model=m, p=np.array(p, float), v=np.zeros(2),
                                    v0=min(1.2, max(0.6, self.rng.gauss(0.9, 0.15))),
                                    r=0.22, path=[], wait=self.rng.uniform(0, 2),
                                    distracted=self.rng.random() < distracted))
        self.running = True

    def positions(self):
        return [tuple(pp["p"]) for pp in self.people]

    def _free_point(self):
        (x0, x1), (y0, y1) = self.region
        for _ in range(200):
            x, y = self.rng.uniform(x0, x1), self.rng.uniform(y0, y1)
            if self._wall_dist(x, y)[0] > 0.5:
                return (x, y)
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    def _wall_dist(self, x, y):
        """(khoang cach toi do vat gan nhat, vector phap tuyen huong ra ngoai)."""
        np = self.np
        best, n = 1e9, np.zeros(2)
        for _, cx, cy, sx, sy, yaw in self.boxes:
            c, s = math.cos(-yaw), math.sin(-yaw)
            lx, ly = c * (x - cx) - s * (y - cy), s * (x - cx) + c * (y - cy)
            qx = max(-sx / 2, min(sx / 2, lx))
            qy = max(-sy / 2, min(sy / 2, ly))
            dx, dy = lx - qx, ly - qy
            d = math.hypot(dx, dy)
            if d < best:
                c2, s2 = math.cos(yaw), math.sin(yaw)
                if d > 1e-6:
                    n = np.array([c2 * dx - s2 * dy, s2 * dx + c2 * dy]) / d
                best = d
        return best, n

    def _set(self, model, x, y, yaw):
        req = self.Pose()
        req.name = model
        req.position.x, req.position.y, req.position.z = float(x), float(y), self.z
        req.orientation.z, req.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self.node.request(self.service, req, self.Pose, self.Boolean, 500)

    def _new_goal(self, pp):
        g = self._free_point()
        pts, _ = self.plan(self.grid, tuple(pp["p"]), g, lethal=0.3, soft=0.5, smooth_path=False)
        # dich trung o hien tai -> duong 1 diem -> [1:] rong -> IndexError giet ca luong dam dong (22/11)
        q = [self.np.array(q) for q in (pts or [g])]
        pp["path"] = q[1:] or q

    def step(self, dt):
        np = self.np
        robots = [r.map_pose() for r in self.robots if r is not None and r.map_pose() is not None]
        for i, pp in enumerate(self.people):
            if pp["wait"] > 0:
                pp["wait"] -= dt
                pp["v"] *= 0.5
                continue
            if not pp["path"]:
                self._new_goal(pp)
            tgt = pp["path"][0]
            to = tgt - pp["p"]
            dist = np.linalg.norm(to)
            if dist < 0.3:
                pp["path"].pop(0)
                if not pp["path"]:
                    pp["wait"] = self.rng.uniform(0.5, 3.0)
                continue
            e = to / (dist + 1e-9)
            f = (pp["v0"] * e - pp["v"]) / 0.5                       # luc muc tieu
            d, n = self._wall_dist(*pp["p"])
            f += 2.0 * math.exp((pp["r"] - d) / 0.12) * n           # tuong / do vat

            if d < pp["r"]:                                          # cham tuong: day ra
                f += 120.0 * (pp["r"] - d) * n

            def social(q, A, B, rq):
                diff = pp["p"] - q
                dd = np.linalg.norm(diff) + 1e-9
                nij = diff / dd
                cos = -float(np.dot(nij, e))
                w = 0.35 + 0.65 * (1 + cos) / 2                     # phia truoc manh hon
                out = A * math.exp((pp["r"] + rq - dd) / B) * nij * w
                if dd < pp["r"] + rq:                                # luc tiep xuc than
                    out = out + 120.0 * (pp["r"] + rq - dd) * nij   # (Helbing et al. 2000)
                return out
            for j, qq in enumerate(self.people):
                if j != i:
                    f += social(qq["p"], 2.1, 0.3, qq["r"])
            if not pp["distracted"]:
                for rp in robots:
                    f += social(np.array(rp[:2]), 1.5, 0.4, 0.35)
            f += np.array([self.rng.gauss(0, 0.15), self.rng.gauss(0, 0.15)])   # lac lu
            pp["v"] = pp["v"] + f * dt
            sp = np.linalg.norm(pp["v"])
            vmax = 1.3 * pp["v0"]
            if sp > vmax:
                pp["v"] *= vmax / sp
            pp["p"] = pp["p"] + pp["v"] * dt

    def run(self):
        dt = 1.0 / self.hz
        while self.running:
            t0 = time.monotonic()
            self.step(dt)
            for pp in self.people:
                v = pp["v"]
                yaw = math.atan2(v[1], v[0]) if self.np.linalg.norm(v) > 0.05 else 0.0
                self._set(pp["model"], pp["p"][0], pp["p"][1], yaw)
            time.sleep(max(0.0, dt - (time.monotonic() - t0)))
        for pp, (x, y) in zip(self.people, self.park):
            self._set(pp["model"], x, y, 0.0)

    def stop(self):
        self.running = False


def _sdf_boxes(path):
    import xml.etree.ElementTree as ET
    out = []
    for m in ET.parse(path).getroot().iter("model"):
        size = m.find("./link/collision/geometry/box/size")
        if size is None:
            continue
        pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
        sx, sy, _ = (float(v) for v in size.text.split())
        out.append((m.get("name"), pose[0], pose[1], sx, sy, pose[5]))
    return out


# Xe day hang trong kho (voice_office.sdf): chay qua lai, dung lai neu robot o sat truoc
CART_PATHS = {
    "cart__1": [(6.0, -9.3), (14.0, -9.3)],          # loi ngang phia nam kho
    "cart__2": [(6.0, 9.3), (14.0, 9.3)],            # loi ngang phia bac kho
    "cart__3": [(6.0, 1.7), (13.4, 1.7)],            # canh hanh lang slalom
}
OFFICE_PEOPLE = ["person"] + [f"person{k}" for k in range(2, 13)]
CART_PARK = [(40.0, 40.0), (40.0, 42.0), (40.0, 44.0)]      # cho cat xe khi khong dung


def carts(world="voice_office", robots=None, speed=0.45, stop_near=1.0):
    """3 xe day (Mover) — tra ve list da start()."""
    out = []
    for k, (name, path) in enumerate(sorted(CART_PATHS.items())):
        mv = Mover(path, speed, model=name, world=world, robots=robots, stop_near=stop_near,
                   z=0.45, park=CART_PARK[k])               # xong bai: dua xe ra ngoai ban do
        mv.start()
        out.append(mv)
    return out


def main():
    ap = argparse.ArgumentParser(description="vat can dong trong sim")
    ap.add_argument("--model", default="person")
    ap.add_argument("--path", default="1.0,-0.4 1.0,2.6",
                    help='cac diem "x,y x,y ..." (mac dinh: cat ngang phong khach)')
    ap.add_argument("--speed", type=float, default=0.4, help="m/s (nguoi di cham ~0.5-1.0)")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--world", default="voice_house")
    ap.add_argument("--crowd", type=int, default=0,
                    help="N nguoi di bo kieu Social Force (nha nho: 1-3, van phong: 1-12)")
    ap.add_argument("--carts", action="store_true", help="3 xe day hang chay trong kho (van phong)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.crowd or a.carts:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from run_sim import WORLDS, world_info
        w = world_info(a.world if a.world in WORLDS else "voice_house")
        threads = []
        if a.crowd:
            pool = OFFICE_PEOPLE if w["name"] == "voice_office" else ["person", "person2", "person3"]
            region = w.get("region") if w["name"] == "voice_office" else ((-3.5, 3.5), (-2.8, 2.8))
            c = Crowd(pool[:a.crowd], region, w["sdf_path"], seed=a.seed, world=w["name"])
            c.start()
            threads.append(c)
            print(f"{min(a.crowd, len(pool))} nguoi di bo (Social Force) trong {w['name']}")
        if a.carts and w["name"] == "voice_office":
            threads += carts(world=w["name"])
            print("3 xe day hang chay trong kho")
        print("Ctrl+C de dung")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            for t in threads:
                t.stop()
            for t in threads:
                t.join(2)
        return
    path = [p.split(",") for p in a.path.split()]
    m = Mover(path, a.speed, a.model, a.world, loop=a.loop, park=(-4.2, 2.6))
    m.start()
    print(f"{a.model} di theo {a.path} voi {a.speed} m/s — Ctrl+C de dung")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        m.stop()
        m.join(2)


if __name__ == "__main__":
    main()
