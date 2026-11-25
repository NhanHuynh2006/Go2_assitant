"""IsaacSim: giong fastsim.Sim nhung DONG HOC THAN lay tu Isaac (body_server.py). Cam bien tia 2D, nguoi (movers.Crowd), dong ho ao,
bo dieu khien: dung y nguyen fastsim (ke thua). Khong sua fastsim.py.
v2 (23/11): (1) va bang CHAN that (4 ban chan tu Isaac, ban kinh 0.022 m) ghi RIENG, khong dung luot -> so voi va khung 2D tren cung luot;
(2) tia LiDAR nghieng theo roll/pitch (nen: tia cham san truoc vat thi mat, vuot qua dinh vat thi mat); goc 0 -> y het fastsim (test_isaac_rays.py);
(3) reset tat dinh: seed + khoi luong than lay tu (the gioi, luot).
  venv/bin/python isaac_val/isaac_sim.py --sock S --seeds 302-439 --only crowd --configs mppi --out isaac_val/x.csv   (chi DEV 0-999)"""
import argparse, csv, json, math, os, pickle, socket, struct, sys, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import fastsim as F

Q = 0.02
SOCK = None
CONN = None
FOOT_R = 0.022             # ban kinh ban chan Go2 (URDF foot sphere ~0.022)
LIDAR_DZ = 0.10            # LiDAR cao hon tam than (GIA DINH; L1/OS1 ~0.40-0.45 m khoi san)
BOX_H = 1.0                # chieu cao vat tinh (GIA DINH: fastsim khong co chieu cao)
PERSON_H = 1.75
TILT = True


def rpc(m):
    global CONN
    if CONN is None:
        CONN = socket.socket(socket.AF_UNIX)
        CONN.connect(SOCK)
    b = pickle.dumps(m)
    CONN.sendall(struct.pack("I", len(b)) + b)

    def rn(n):
        o = b""
        while len(o) < n:
            q = CONN.recv(n - len(o))
            if not q:
                raise RuntimeError("mat ket noi server Isaac")
            o += q
        return o
    return pickle.loads(rn(struct.unpack("I", rn(4))[0]))


def slope(th_body, roll, pitch):
    """do doc (dz / d ngang) cua tia nam ngang trong khung than o goc th_body sau khi than nghieng roll/pitch (R = Ry(pitch) Rx(roll))."""
    c, s = np.cos(th_body), np.sin(th_body)
    y1, z1 = s * math.cos(roll), s * math.sin(roll)
    x2 = c * math.cos(pitch) + z1 * math.sin(pitch)
    z2 = -c * math.sin(pitch) + z1 * math.cos(pitch)
    return z2 / np.hypot(x2, y1)


def tilt_filter(d, th_world, yaw, roll, pitch, h, top, rmax):
    """d: khoang cach ngang 2D toi vat; tra lai rmax neu tia cham san truoc (bo loc chieu cao cua pointcloud_to_scan bo diem san)
    hoac di qua tren dinh vat (cao top)."""
    if roll == 0.0 and pitch == 0.0:
        return d
    k = slope(th_world - yaw, roll, pitch)
    out = d.copy()
    hit = d < rmax - 1e-9
    with np.errstate(divide="ignore"):
        floor = np.where(k < 0, h / np.maximum(-k, 1e-12), np.inf)
    z = h + d * k
    out[hit & ((floor < d) | (z > top))] = rmax
    return out


_FSim = F.Sim                 # lop goc (main() thay F.Sim = IsaacSim)


class IsaacSim(_FSim):
    last = None

    def __init__(self, W, config, trial, regime="isaac", oracle=False, tmax=300.0):
        self._qacc, self.vlp, self.tilt, self.feet, self.fell = 0.0, np.zeros(3), (0.0, 0.0), [], False
        self.zb, self.foot_col, self.foot_n = 0.32, None, 0
        IsaacSim.last = self
        super().__init__(W, config, trial, "real", oracle, tmax)
        self.start = np.array(W["start"], float)
        rr = np.random.default_rng(np.random.SeedSequence([W["seed"], trial, 99]))
        rpc(("reset", int(rr.integers(2 ** 31)), float(rr.uniform(-1.0, 3.0))))   # dmass nhu cau hinh train rough
        for _ in range(50):                                    # 1 s dung yen cho chan on dinh
            s = rpc(("step", (0., 0., 0.)))
        self.off = (s["x"], s["y"], s["yaw"])
        self._pose(s)

    def _w(self, lx, ly):
        ox, oy, ow = self.off
        c, sn = math.cos(ow), math.sin(ow)
        dx, dy = lx - ox, ly - oy
        ax, ay = c * dx + sn * dy, -sn * dx + c * dy
        X, Y, W = self.start
        c, sn = math.cos(W), math.sin(W)
        return X + c * ax - sn * ay, Y + sn * ax + c * ay

    def _pose(self, s):
        x, y = self._w(s["x"], s["y"])
        lw = s["yaw"] - self.off[2]
        W = self.start[2]
        self.x = np.array([x, y, math.atan2(math.sin(W + lw), math.cos(W + lw))])
        self.v_raw = np.array(s["v"])
        self.vlp = self.vlp + Q / .25 * (self.v_raw - self.vlp)  # loc 0.25 s cho at_fault / log
        self.v = self.vlp
        self.tilt, self.zb, self.fell = (s["roll"], s["pitch"]), s["z"], s["fallen"]
        self.feet = [self._w(fx, fy) for fx, fy, _ in s["feet"]]

    def _foot_check(self):
        if self.foot_col is not None:
            return
        P = np.array(self.feet)
        ds = float(self.boxes.sd(P).min()) - FOOT_R
        kind = "static" if ds < 0 else None
        if kind is None:
            for px, py, rad, vx, vy in self.people():
                if rad >= .45:
                    d = float(np.hypot(np.maximum(np.abs(P[:, 0] - px) - .3, 0), np.maximum(np.abs(P[:, 1] - py) - .45, 0)).min()) - FOOT_R
                else:
                    d = float(np.hypot(P[:, 0] - px, P[:, 1] - py).min()) - rad - FOOT_R
                if d < 0:
                    kind = "cart" if rad >= .45 else "person"
                    break
        if kind:
            self.foot_col = dict(kind=kind, t=round(self.clock.t - self.t0, 2))

    def substep(self, h):
        now = self.clock.t = self.clock.t + h
        while self.cmdq and self.cmdq[0][0] <= now:
            self.cmd = self.cmdq.pop(0)[1]
        self._qacc += h
        while self._qacc >= Q - 1e-9:
            self._qacc -= Q
            s = rpc(("step", tuple(float(u) for u in self.cmd)))
            self._pose(s)
            if self.fell:
                self.col = dict(kind="fall", t=round(now - self.t0, 1), at_fault=1)
                raise F.EpisodeEnd("nga")
            if self.r is not None and getattr(self, "t0", None) is not None:
                self._foot_check()
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
            raise F.EpisodeEnd("het gio")

    def sense(self):
        """fastsim.Sim.sense voi tia LiDAR (rmax 6) loc theo do nghieng than; camera (rmax 4) giu nguyen."""
        roll, pitch = self.tilt if TILT else (0.0, 0.0)
        if roll == 0.0 and pitch == 0.0:
            return _FSim.sense(self)
        yaw, h = self.x[2], self.zb + LIDAR_DZ
        bcast, ccast = self.boxes.cast, F.cast_circles

        def bc(ox, oy, th, rmax):
            d = bcast(ox, oy, th, rmax)
            return tilt_filter(d, th, yaw, roll, pitch, h, BOX_H, rmax) if rmax == 6.0 else d

        def cc(ox, oy, th, circ, rmax):
            d = ccast(ox, oy, th, circ, rmax)
            return tilt_filter(d, th, yaw, roll, pitch, h, PERSON_H, rmax) if rmax == 6.0 else d
        self.boxes.cast, F.cast_circles = bc, cc
        try:
            return _FSim.sense(self)
        finally:
            del self.boxes.cast
            F.cast_circles = ccast


def worlds(lo, hi, only, nmax):
    out = []
    for seed in range(lo, hi + 1):
        W = F.gen_world(seed)
        if only == "crowd" and not W["crowd"]:
            continue
        out.append(seed)
        if nmax and len(out) >= nmax:
            break
    return out


def main():
    global SOCK, TILT
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", default="")
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--configs", default="mppi")
    ap.add_argument("--out", default="")
    ap.add_argument("--trial", type=int, default=0)
    ap.add_argument("--only", default="", help="crowd: chi ban do co nguoi")
    ap.add_argument("--n", type=int, default=0, help="so ban do toi da (sau loc)")
    ap.add_argument("--shard", default="0/1", help="i/k: chia ban do cho k client")
    ap.add_argument("--notilt", action="store_true")
    ap.add_argument("--body", default="isaac", help="isaac | champ | champ2 | real/go2 (fastsim goc, de so ghep cap)")
    a = ap.parse_args()
    SOCK, TILT = a.sock, not a.notilt
    lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
    lo, hi = int(lo), int(hi)
    assert 0 <= lo <= hi <= 999 or 2000 <= lo <= hi <= 2399, "PROTOCOL: chi DEV 0-999 / VAL 2000-2399"
    if a.body == "isaac":
        F.Sim = IsaacSim
    seeds = worlds(lo, hi, a.only, a.n)
    i, k = map(int, a.shard.split("/"))
    seeds = seeds[i::k]
    f = open(a.out, "a", newline="") if a.out else sys.stdout
    fields = ["body", "tilt"] + F.FIELDS + ["foot", "foot_t", "succ_foot", "wall"]
    w = csv.DictWriter(f, fields, extrasaction="ignore")
    if a.out and os.path.getsize(a.out) == 0:
        w.writeheader()
    for seed in seeds:
        W = F.gen_world(seed)
        for cfg in a.configs.split(","):
            t0 = time.time()
            IsaacSim.last = None
            try:
                row = F.run_episode(W, cfg, a.trial, a.body if a.body != "isaac" else "real")
            except Exception as e:                             # noqa: BLE001
                import traceback
                traceback.print_exc()
                row = dict(success="", why="EXC " + repr(e)[:80])
            s = IsaacSim.last
            if a.body == "isaac" and s is not None:
                fc = s.foot_col if (s.foot_col and (s.col is None or s.foot_col["t"] <= (s.col.get("t") or 1e9))) else None
                row.update(foot=(fc or {}).get("kind", ""), foot_t=(fc or {}).get("t", ""),
                           succ_foot=int(bool(row.get("success")) and fc is None))
            row.update(body=a.body, tilt=int(TILT and a.body == "isaac"), world=seed, kind=W["kind"], npeople=(W["crowd"] or {}).get("n", 0),
                       trial=a.trial, config=cfg, wall=round(time.time() - t0, 1))
            w.writerow(row)
            f.flush()


if __name__ == "__main__":
    main()
