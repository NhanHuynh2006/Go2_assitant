"""IsaacSim: giong fastsim.Sim nhung DONG HOC THAN lay tu Isaac (body_server.py). Cam bien tia 2D, nguoi (movers.Crowd), dong ho ao,
bo dieu khien: dung y nguyen fastsim (ke thua). Khong sua fastsim.py.
  venv/bin/python isaac_val/isaac_sim.py --sock S --seeds 0-9 --configs mppi,p2 --out isaac_val/x.csv      (chi seed DEV 0-999)"""
import argparse, csv, math, os, pickle, socket, struct, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import fastsim as F

Q = 0.02
SOCK = None
CONN = None


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


class IsaacSim(F.Sim):
    def __init__(self, W, config, trial, regime="isaac", oracle=False, tmax=300.0):
        self._qacc, self.vlp, self.tilt, self.feet, self.fell = 0.0, np.zeros(3), (0.0, 0.0), [], False
        super().__init__(W, config, trial, "real", oracle, tmax)
        self.start = np.array(W["start"], float)
        rpc(("reset",))
        for _ in range(50):                                    # 1 s dung yen cho chan on dinh
            s = rpc(("step", (0., 0., 0.)))
        # lay lai goc toa do sau khi on dinh
        self.off = (s["x"], s["y"], s["yaw"])
        self._pose(s)

    def _pose(self, s):
        ox, oy, ow = self.off
        c, sn = math.cos(ow), math.sin(ow)
        dx, dy = s["x"] - ox, s["y"] - oy
        lx, ly, lw = c * dx + sn * dy, -sn * dx + c * dy, s["yaw"] - ow
        X, Y, W = self.start
        c, sn = math.cos(W), math.sin(W)
        yaw = math.atan2(math.sin(W + lw), math.cos(W + lw))
        self.x = np.array([X + c * lx - sn * ly, Y + sn * lx + c * ly, yaw])
        self.v_raw = np.array(s["v"])
        a = Q / .25                                            # loc 0.25 s: bo lac theo nhip chan khi cham loi / at_fault
        self.vlp = self.vlp + a * (self.v_raw - self.vlp)
        self.v = self.vlp
        self.tilt = (s["roll"], s["pitch"])
        self.fell = s["fallen"]

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


def main():
    global SOCK
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", required=True)
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--configs", default="mppi")
    ap.add_argument("--out", default="")
    ap.add_argument("--trial", type=int, default=0)
    ap.add_argument("--only", default="", help="crowd: chi ban do co nguoi")
    ap.add_argument("--body", default="isaac", help="isaac | champ | real (hai cai sau = fastsim goc, de so ghep cap)")
    a = ap.parse_args()
    SOCK = a.sock
    lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
    lo, hi = int(lo), int(hi)
    assert 0 <= lo <= hi <= 999, "PROTOCOL: chi DEV 0-999"
    if a.body == "isaac":
        F.Sim = IsaacSim
    f = open(a.out, "a", newline="") if a.out else sys.stdout
    w = csv.DictWriter(f, ["body"] + F.FIELDS, extrasaction="ignore")
    if a.out and os.path.getsize(a.out) == 0:
        w.writeheader()
    for seed in range(lo, hi + 1):
        W = F.gen_world(seed)
        if a.only == "crowd" and not W["crowd"]:
            continue
        for cfg in a.configs.split(","):
            try:
                row = F.run_episode(W, cfg, a.trial, a.body if a.body != "isaac" else "real")
            except Exception as e:                             # noqa: BLE001
                import traceback
                traceback.print_exc()
                row = dict(success="", why="EXC " + repr(e)[:80])
            row.update(body=a.body, world=seed, kind=W["kind"], npeople=(W["crowd"] or {}).get("n", 0), trial=a.trial, config=cfg)
            w.writerow(row)
            f.flush()


if __name__ == "__main__":
    main()
