"""Tach nguyen nhan khoang trong CAM NHAN: thay tracker bang oracle TUNG PHAN, chon bang tag trong ten cau hinh:
  ~oca  hoan hao (moi nguoi, xuyen tuong)           ~ocb  chi nguoi NHIN THAY (khong bi che) trong 5.5 m
  ~occ  nhu b nhung tam 4 m                          ~ocd  nhu b nhung bo nguoi DUNG YEN (v<0.15) (chung thanh vat tinh)
  ~oce  nhu b + tre xac nhan 0.6 s sau khi lo ra     ~ocf  nhu b + nhieu vi tri 0.07 lech 0.1 ve robot, van toc tre EMA 0.5
  ~ocg  nhu b + mu < 0.75 m tu LiDAR (mat han khi vao gan)
Dung nhu fastsim.py (cung tham so)."""
import os, sys, math, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import fastsim
import numpy as np
fastsim.__file__ = os.path.abspath(__file__)
mk0 = fastsim.make_robot


class OT:
    def __init__(self, sim, kind):
        self.sim, self.kind = sim, kind
        self.first, self.est, self.last = {}, {}, {}
        self.rng = np.random.default_rng([sim.W["seed"], 5])
        self.tracks = []
        self.mode = ""

    def update(self, pts, xy, t, grid=None):
        s, k = self.sim, self.kind
        x, y, yaw = s.x
        lx, ly = x + .2 * math.cos(yaw), y + .2 * math.sin(yaw)
        out = []
        for i, p in enumerate(s.people()):
            pp, v = np.array(p[:2]), np.array(p[3:], float)
            if k != "a":
                d = math.hypot(pp[0] - lx, pp[1] - ly)
                b = math.atan2(pp[1] - ly, pp[0] - lx)
                w = math.asin(min(1, .18 / max(d, .2)))
                vis = (s.boxes.cast(lx, ly, np.array([b, b - w, b + w]), 6.0) > d - .25).any()
                if d > (4.0 if k == "c" else 5.5) or not vis:
                    if t - self.last.get(i, -9) > 0.5:
                        self.first.pop(i, None)
                        self.est.pop(i, None)
                    continue
                self.first.setdefault(i, t)
                self.last[i] = t
                if k == "d" and np.hypot(*v) < .15:
                    continue
                if k == "e" and t - self.first[i] < .6:
                    continue
                if k == "g" and d < .75:
                    continue
                if k == "f":
                    m = pp - .1 * np.array([math.cos(b), math.sin(b)]) + self.rng.normal(size=2) * .07
                    e = self.est.get(i)
                    if e is None:
                        e = [m, np.zeros(2), t]
                    else:
                        e = [m, .5 * e[1] + .5 * (m - e[0]) / max(t - e[2], .05), t]
                    self.est[i] = e
                    pp, v = e[0], e[1]
            out.append(dict(p=pp, v=v, hits=9, t=t))
        self.tracks = out

    def movers(self, **kw):
        return self.tracks


def mk(sim, config):
    r = mk0(sim, config)
    m = re.search(r"~oc([a-z])", config)
    if m:
        r.tracker = OT(sim, m.group(1))
    return r


fastsim.make_robot = mk
if __name__ == "__main__":
    fastsim.main()
