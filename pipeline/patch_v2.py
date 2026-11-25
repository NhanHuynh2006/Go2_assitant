"""Va loi nen (ap dung CHO MOI thuat toan) + dang ky PRISM-E. Chay SAU khi pipeline 22/11 xong.
Ten cau hinh co hau to '~v1' -> cam bien/hinh hoc nhu luot 960 (de tai lap)."""
import re
R = "/home/nhanhuynh/Documents/Go2_assitant/"


def sub(s, old, new, n=1):
    assert s.count(old) >= 1, old[:80]
    return s.replace(old, new, n)


# ---------------------------------------------------------------- nav_local
p = R + "nav_local.py"
s = open(p, encoding="utf-8").read()
# (2) ngan sach mau bang nhau
s = sub(s, '        kw.setdefault("K", 400)\n        super().__init__(**kw)\n        self.policy, self.mode, self.hold',
        '        kw.setdefault("K", 600)                                     # BANG MPPI/PRISM (cu: 400, khong cong bang)\n        super().__init__(**kw)\n        self.policy, self.mode, self.hold')
# (3) nguoi: than dai (2 vong tron) thay vi tam + 0.3 m
s = sub(s, '''        self.near_goal = 0.5
        self.last = {}''', '''        self.near_goal = 0.5
        self.people_cap = False                  # True: khoang cach nguoi tinh theo than dai (2 vong tron)
        self.last = {}''')
s = sub(s, '''    # ---------------------------------------------------------------- cham diem
    def cost(self, U, P, Y,''', '''    def ppl_dist(self, P, Y, qx, qy, rad):
        """(K,T) khoang ho than robot - nguoi. people_cap: 2 vong tron mui/duoi (nhu vat tinh)."""
        if not self.people_cap:
            return np.hypot(P[..., 0] - qx, P[..., 1] - qy) - rad - 0.3
        d = None
        for off in (self.c_off, -self.c_off):
            e = np.hypot(P[..., 0] + off * np.cos(Y) - qx, P[..., 1] + off * np.sin(Y) - qy)
            d = e if d is None else np.minimum(d, e)
        return d - rad - self.r_body - self.margin

    # ---------------------------------------------------------------- cham diem
    def cost(self, U, P, Y,''')
s = sub(s, "            d = np.hypot(P[..., 0] - qx, P[..., 1] - qy) - rad - 0.3\n            S += w[\"ppl\"]",
        "            d = self.ppl_dist(P, Y, qx, qy, rad)\n            S += w[\"ppl\"]")
s = sub(s, "                d = np.hypot(P[..., 0] - (px + vx * tt), P[..., 1] - (py + vy * tt)) - rad - 0.3 - grow",
        "                d = self.ppl_dist(P, Y, px + vx * tt, py + vy * tt, rad) - grow")
# (4) tracker: bang chung 'vao cho tung TRONG' (free-space violation)
s = sub(s, "    def update(self, pts_world, robot_xy, t):\n        from scipy.ndimage import label",
        "    def update(self, pts_world, robot_xy, t, grid=None):\n        from scipy.ndimage import label")
s = sub(s, "            tr[\"p\"], tr[\"t\"], tr[\"hits\"] = c, t, tr[\"hits\"] + 1\n",
        "            tr[\"p\"], tr[\"t\"], tr[\"hits\"] = c, t, tr[\"hits\"] + 1\n"
        "            tr[\"dyn\"] = min(5.0, tr.get(\"dyn\", 0.0) + 1.0) if self._was_free(grid, c) \\\n"
        "                else max(0.0, tr.get(\"dyn\", 0.0) - 0.34)\n")
s = sub(s, "new.append(dict(p=c, v=np.zeros(2), t=t, hits=1, p0=c.copy()))",
        "new.append(dict(p=c, v=np.zeros(2), t=t, hits=1, p0=c.copy(),\n"
        "                                dyn=1.0 if self._was_free(grid, c) else 0.0))")
s = sub(s, "    def movers(self, min_speed=0.2, min_hits=3, min_travel=0.5):", '''    mode = "v1"

    @staticmethod
    def _was_free(grid, c):
        """Tam cum nam o o ma ban do (TRUOC lan quet nay) da biet chac la TRONG -> co vat vua di vao."""
        if grid is None:
            return False
        r, k = grid.cell(c[0], c[1])
        return bool(grid.inside(r, k) and grid.ev[int(r), int(k)] <= -2)

    def movers(self, min_speed=0.2, min_hits=3, min_travel=0.5):
        if self.mode == "v2":
            # vat tinh khong bao gio nam o o da biet trong -> het 'nguoi ma'; nguoi that duoc
            # xac nhan sau ~0.6 s (3 lan quet) thay vi phai di 0.5 m
            return [tr for tr in self.tracks if tr["hits"] >= 3 and tr.get("dyn", 0.0) >= 2.0
                    and np.linalg.norm(tr["v"]) > 0.15]
        return self._movers_v1(min_speed, min_hits, min_travel)

    def _movers_v1(self, min_speed=0.2, min_hits=3, min_travel=0.5):''')
open(p, "w", encoding="utf-8").write(s)

# ---------------------------------------------------------------- robot_ros
p = R + "robot_ros.py"
s = open(p, encoding="utf-8").read()
s = sub(s, "            self.tracker.update(w, (x, y), time.monotonic())\n",
        "            w = self.track_and_filter(w, (x, y), time.monotonic())\n")
s = sub(s, "    def odom_fresh(self, max_age=1.0):", '''    def track_and_filter(self, w, xy, now):
        """Cap nhat bo bam; tra ve diem KHONG thuoc vat dong (vat dong khong ve vao ban do tinh)."""
        if "~v1" in self.controller:
            self.tracker.mode = "v1"
            self.tracker.update(w, xy, now)
            return w
        self.tracker.mode = "v2"
        self.tracker.update(w, xy, now, grid=self.grid)
        return self.drop_dynamic(w, now)

    def drop_dynamic(self, w, now):
        if "~v1" in self.controller or not len(w):
            return w
        keep = np.ones(len(w), bool)
        for tr in self.tracker.movers():
            q = tr["p"] + tr["v"] * (now - tr["t"])
            keep &= np.hypot(w[:, 0] - q[0], w[:, 1] - q[1]) > 0.40
        return w[keep]

    def odom_fresh(self, max_age=1.0):''')
s = sub(s, "            self.depth_grid.integrate(sx, sy, w, max_range=3.5",
        "            w = self.drop_dynamic(w, time.monotonic())\n            self.depth_grid.integrate(sx, sy, w, max_range=3.5")
old = '''                people = [(float(tr["p"][0]), float(tr["p"][1]), float(tr["v"][0]),
                           float(tr["v"][1]), 0.25) for tr in self.tracker.movers()]
            if self.coordinate:'''
new = '''                v1 = "~v1" in self.controller                  # v2: bu tuoi track + tre chap hanh
                people = [(float(tr["p"][0] + (0 if v1 else tr["v"][0] * min(0.4, now - tr["t"] + 0.05))),
                           float(tr["p"][1] + (0 if v1 else tr["v"][1] * min(0.4, now - tr["t"] + 0.05))),
                           float(tr["v"][0]), float(tr["v"][1]), 0.25)
                          for tr in self.tracker.movers()]
            if self.coordinate:'''
s = sub(s, old, new)
s = sub(s, "                if self.people_aware and self.avoid:\n                    known =",
        "                if self.people_aware and self.avoid and \"~v1\" in self.controller:\n                    known =")
s = sub(s, "            if isinstance(ctrl, PRISM):\n                ctrl.prefs = self.nav_prefs",
        "            if isinstance(ctrl, PRISM2):\n                ctrl.prefs = self.nav_prefs\n"
        "                extra = dict(gains=self.vel_gains.copy())\n"
        "            if isinstance(ctrl, PRISM):\n                ctrl.prefs = self.nav_prefs")
s = sub(s, "from reflex_matcher import norm\n", "from nav_prism2 import PRISM2\nfrom reflex_matcher import norm\n")
s = sub(s, "    def _make_ctrl(self):\n", '''    def _make_ctrl(self):
        """Bo dieu khien theo ten; hau to ~v1 = hinh hoc/cam bien cu (luot 960, 22/11)."""
        full = self.controller
        try:
            self.controller = full.replace("~v1", "")
            c = self._make_ctrl_base()
        finally:
            self.controller = full
        for m in (c, getattr(c, "shield", None)):
            if isinstance(m, MPPI):
                m.people_cap = "~v1" not in full
        return c

    def _make_ctrl_base(self):
''')
s = sub(s, "        if self.controller == \"dwa\":\n            return DWA(**lim)", '''        if self.controller.startswith("p2"):
            # p2[-cap-evade-prior-value-rate-adapt][+value][@ppo+sac]: PRISM-E va ablation
            import re as _re
            name, _, sel = self.controller.partition("@")
            d = os.path.dirname(self.RL_POLICY)
            files = {"ppo": self.RL_POLICY, "td3": os.path.join(d, "policy_nav_td3.npz"),
                     "sac": os.path.join(d, "policy_nav_sac.npz")}
            pri = [RLPolicy(files[k]) for k in sel.split("+")] if sel else []
            vp = os.path.join(d, "value_nav.npz")
            if pri and os.path.exists(vp) and sel.startswith("ppo"):
                pri[0].load_value(vp)
            fl = {m.group(2): m.group(1) == "+" for m in _re.finditer(r"([-+])([a-z]+)", name[2:])}
            return PRISM2(priors=pri, flags=fl, **lim)
        if self.controller == "dwa":
            return DWA(**lim)''')
s = sub(s, '''    def _navigate(self, gx, gy, tol=0.2, timeout=None, line=None):
        if self.controller in (''', '''    def _navigate(self, gx, gy, tol=0.2, timeout=None, line=None):
        if self.controller.replace("~v1", "") in (''')
s = sub(s, 'self.controller.startswith(("prism", "rl@"))', 'self.controller.startswith(("prism", "rl@", "p2"))')
open(p, "w", encoding="utf-8").write(s)

# ---------------------------------------------------------------- eval_sim + fastsim
p = R + "eval_sim.py"
s = open(p, encoding="utf-8").read()
s = sub(s, '    if name.startswith(("prism", "rl@")):', '    if name.startswith(("prism", "rl@", "p2")) or "~v1" in name:')
open(p, "w", encoding="utf-8").write(s)
p = R + "fastsim.py"
s = open(p, encoding="utf-8").read()
s = sub(s, "            r.tracker.update(wpts, (x, y), now)\n", "            wpts = r.track_and_filter(wpts, (x, y), now)\n")
s = sub(s, "r.depth_grid.integrate(cx, cy, pd[ok], max_range", "r.depth_grid.integrate(cx, cy, r.drop_dynamic(pd[ok], now), max_range")
open(p, "w", encoding="utf-8").write(s)
print("patch v2 ok")
