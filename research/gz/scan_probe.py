#!/usr/bin/env python3
"""GAZEBO: do LECH THOI GIAN giua quet LiDAR va pose dung de chieu quet trong duong ROS (chi DOC, khong doi robot_ros).

  record: (sim dang chay, khong nguoi) lop con RosRobotTools ghi moi quet: stamp quet, stamp odom MOI NHAT ma
          robot_ros._on_cloud dung (map_pose), roll/pitch IMU; luu tin nhan goc; tracker v3 chay that; robot di theo mau
          dung / quay / thang / ngoan ngoeo.   venv/bin/python research/gz/scan_probe.py record OUT.pkl
  replay: phat lai OFFLINE cung _on_cloud that voi 2 bien the pose: A = pose luc callback (nhu hien tai),
          B = pose + roll/pitch noi suy tai stamp quet (de xuat sua). So nguoi ma.
          venv/bin/python research/gz/scan_probe.py replay OUT.pkl
"""
import math, os, pickle, sys, threading, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
START, PLAN_ARG = None, None
CFG = "mppi~t3~nl:ppl=100;ppl_len=0.5"          # chi de tracker.mode = v3 (track_and_filter doc chuoi nay)
BOUNDS = (-16.0, -11.0, 32.0, 22.0)             # voice_office (run_sim.WORLDS)


def st(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9


def record(out, dur):
    import robot_ros
    from rclpy.serialization import serialize_message
    robot_ros.configure_world(*BOUNDS)

    class R(robot_ros.RosRobotTools):
        def _on_odom(self, msg):
            p, q = msg.pose.pose.position, msg.pose.pose.orientation
            self.H["odom"].append((st(msg.header), p.x, p.y, robot_ros._yaw_of(q), time.monotonic()))
            self._odom_st = st(msg.header)
            super()._on_odom(msg)

        def _on_imu(self, msg):
            super()._on_imu(msg)
            self.H["imu"].append((st(msg.header), self.rp[0], self.rp[1], msg.angular_velocity.z, time.monotonic()))

        def _on_cloud(self, msg):
            now = time.monotonic()
            rec = dict(stamp=st(msg.header), arr=now, odom_st=getattr(self, "_odom_st", None),
                       pose=self.map_pose(), rp=self.rp, cnt=self._scan_count, raw=serialize_message(msg))
            super()._on_cloud(msg)
            rec["cb_ms"] = (time.monotonic() - now) * 1000
            rec["movers"] = [(round(float(t["p"][0]), 2), round(float(t["p"][1]), 2), id(t)) for t in self.tracker.movers()]
            self.H["scan"].append(rec)

    r = R.__new__(R)
    r.H = dict(odom=[], imu=[], scan=[])
    R.__init__(r, ns="", odom_topic="/gazebo/odom", cloud_topic="/velodyne_points/points",
               depth_topic="/d435i/depth_image", use_depth=True)
    r.controller = CFG
    if START:                                            # dua robot toi cho nhieu vat tinh (nhu luot smoke co ma)
        import subprocess
        x, y, yaw = START
        req = (f'name: "go2", position: {{x: {x}, y: {y}, z: 0.32}}, orientation: {{z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
        subprocess.run(["gz", "service", "-s", "/world/voice_office/set_pose", "--reqtype", "gz.msgs.Pose", "--reptype",
                        "gz.msgs.Boolean", "--timeout", "3000", "--req", req], capture_output=True, timeout=10)
        time.sleep(4)
    r.wait_ready(10)
    print("odom", r.map_pose(), "sensors", r.wait_sensors(10), flush=True)
    time.sleep(2)
    PLAN = PLAN_ARG or [(20, 0, 0), (15, 0, .4), (15, 0, -.4), (8, .25, 0), (8, -.15, 0), (16, .2, "sin"), (8, .25, 0), (15, 0, 0)]
    t0 = time.monotonic(); seg = []
    for d, vx, wz in PLAN:
        seg.append((time.monotonic() - t0, vx, wz))
        te = time.monotonic() + d
        while time.monotonic() < te:
            w = 0.4 * math.sin(2 * math.pi * (time.monotonic() - t0) / 4.0) if wz == "sin" else wz
            r._twist(vx, 0.0, w)
            time.sleep(0.1)
    r._halt()
    H = r.H
    H["lidar_tf"] = r._lidar_tf; H["seg"] = seg; H["t0"] = t0; H["base_height"] = r.base_height; H["body_box"] = r.body_box
    pickle.dump(H, open(out, "wb"))
    S = H["scan"]
    sk = np.array([(s["odom_st"] - s["stamp"]) * 1000 for s in S if s["odom_st"] is not None])
    print(f"{len(S)} quet; lech stamp odom dung - stamp quet: trung vi {np.median(sk):.0f} ms, p5 {np.percentile(sk, 5):.0f}, p95 {np.percentile(sk, 95):.0f}")
    from robot_ros import RosBus
    RosBus.get().shutdown()
    os._exit(0)


class Clock:
    t = 0.0

    def monotonic(self):
        return self.t


def interp_pose(O, ts):
    """odom (stamp, x, y, yaw) noi suy tai ts (goc unwrap)."""
    a = np.array([o[:4] for o in O])
    i = np.searchsorted(a[:, 0], ts)
    i = min(max(i, 1), len(a) - 1)
    t0_, t1_ = a[i - 1, 0], a[i, 0]
    f = 0.0 if t1_ == t0_ else (ts - t0_) / (t1_ - t0_)
    f = min(max(f, 0.0), 1.0)
    dy = math.atan2(math.sin(a[i, 3] - a[i - 1, 3]), math.cos(a[i, 3] - a[i - 1, 3]))
    return (a[i - 1, 1] + f * (a[i, 1] - a[i - 1, 1]), a[i - 1, 2] + f * (a[i, 2] - a[i - 1, 2]),
            math.atan2(math.sin(a[i - 1, 3] + f * dy), math.cos(a[i - 1, 3] + f * dy)))


def interp_rp(I, ts):
    a = np.array([o[:3] for o in I])
    return float(np.interp(ts, a[:, 0], a[:, 1])), float(np.interp(ts, a[:, 0], a[:, 2]))


def load_stream(path):
    """research/gz/eval_probe.py -> dang H nhu record(); chi giu quet tu lan ep_start CUOI (1 luot)."""
    H = dict(odom=[], imu=[], scan=[]); ep = None
    with open(path, "rb") as f:
        while True:
            try:
                k, v = pickle.load(f)
            except EOFError:
                break
            if k == "ep_start":
                ep = v; H["scan"] = []
            elif k == "scan":
                if ep is not None and v["arr"] >= ep:
                    H["scan"].append(v)
            else:
                H[k].append(v)
    s0 = H["scan"][0]
    H.update(lidar_tf=next((s["lidar_tf"] for s in H["scan"] if s["lidar_tf"] is not None), None), body_box=s0["body_box"],
             base_height=s0["base_height"], t0=ep, seg=[(0.0, "eval", "eval")])
    global CFG
    CFG = s0["ctrl"]
    return H


def replay(path):
    H = load_stream(path) if path.endswith(".stream") else pickle.load(open(path, "rb"))
    import robot_ros
    from nav_local import BlobTracker, OccGrid
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import PointCloud2
    robot_ros.FLEET.clear()
    S = H["scan"]
    # anh xa stamp sim -> monotonic (do tu odom: arr - stamp, lay phan vi 5 = it tre nhat)
    off = np.percentile([o[4] - o[0] for o in H["odom"]], 5)
    sk = np.array([(s["odom_st"] - s["stamp"]) * 1000 for s in S if s["odom_st"] is not None])
    arr_lag = np.array([(s["arr"] - off - s["stamp"]) * 1000 for s in S])
    print(f"{len(S)} quet. Lech stamp(odom duoc dung) - stamp(quet): trung vi {np.median(sk):.0f} ms, p5 {np.percentile(sk, 5):.0f}, p95 {np.percentile(sk, 95):.0f}, max {sk.max():.0f}")
    print(f"tre tin quet toi callback (so voi stamp): trung vi {np.median(arr_lag):.0f} ms, p95 {np.percentile(arr_lag, 95):.0f}; thoi gian callback trung vi {np.median([s['cb_ms'] for s in S]):.1f} ms")
    I = np.array([o[:4] for o in H["imu"]])
    print(f"lac than (IMU): |roll| p95 {np.degrees(np.percentile(np.abs(I[:, 1]), 95)):.1f} do, |pitch| p95 {np.degrees(np.percentile(np.abs(I[:, 2]), 95)):.1f} do, |wz_imu| p95 {np.percentile(np.abs(I[:, 3]), 95):.2f} rad/s")
    clk = Clock()
    real_mono = time.monotonic
    out = {}
    for var in ("live", "A", "B", "B_flat"):
        if var == "live":
            mv = [s["movers"] for s in S]
        else:
            r = robot_ros.RosRobotTools.__new__(robot_ros.RosRobotTools)
            bx = BOUNDS
            r.__dict__.update(label=var, controller=CFG, tracker=BlobTracker(), _scan_count=0, body_box=H["body_box"],
                              base_height=H["base_height"], body=(0, 0, 0, 0), rp=(0., 0.), _lidar_tf=H["lidar_tf"],
                              grid=OccGrid(xmin=bx[0], ymin=bx[1], width=bx[2], height=bx[3]),
                              depth_grid=OccGrid(xmin=bx[0], ymin=bx[1], width=bx[2], height=bx[3], hit=1, miss=1, occ_thresh=3),
                              cpu={"lidar_ms": 0.0, "depth_ms": 0.0}, local_obs=np.empty((0, 2)), local_t=0.0, odom=None, origin=(0., 0., 0.))
            mv = []
            time.monotonic = clk.monotonic
            try:
                for s in S:
                    msg = deserialize_message(s["raw"], PointCloud2)
                    if var == "A":                                   # nhu robot_ros hien tai (pose/rp luc callback)
                        pose, r.rp, clk.t = s["pose"], s["rp"], s["stamp"] + off
                    else:                                            # pose + roll/pitch TAI stamp quet
                        pose = interp_pose(H["odom"], s["stamp"])
                        r.rp = (0.0, 0.0) if var == "B_flat" else interp_rp(H["imu"], s["stamp"])
                        clk.t = s["stamp"] + off
                    r.map_pose = (lambda p=pose: p)
                    r._scan_count = s["cnt"]
                    robot_ros.RosRobotTools._on_cloud(r, msg)
                    mv.append([(round(float(t["p"][0]), 2), round(float(t["p"][1]), 2), id(t)) for t in r.tracker.movers()])
            finally:
                time.monotonic = real_mono
        # dem ma: vet moi + thoi gian ton tai, theo doan chuyen dong
        seg = H["seg"]; t0 = H["t0"]
        seen, life = {}, {}
        rows = []
        for s, m in zip(S, mv):
            ts = s["arr"] - t0
            k = max((i for i, g in enumerate(seg) if g[0] <= ts), default=-1)
            new = 0
            for x, y, i in m:
                if i not in seen:
                    seen[i] = ts; new += 1
                life[i] = ts - seen[i]
            rows.append((k, ts, new, len(m) > 0))
        out[var] = rows
        n_long = sum(1 for v in life.values() if v > 2.0)
        print(f"\n[{var}] vet ma xac nhan: {len(seen)}, ton tai > 2 s: {n_long}, dai nhat {max(life.values(), default=0):.1f} s; "
              f"ti le quet co ma: {100 * np.mean([r_[3] for r_ in rows]):.0f}%")
        for k, (ts0, vx, wz) in enumerate(seg):
            q = [r_ for r_ in rows if r_[0] == k]
            if q:
                dur = q[-1][1] - q[0][1] + 0.1
                print(f"   doan {k}: vx={vx} wz={wz}: ma moi {sum(r_[2] for r_ in q)} ({sum(r_[2] for r_ in q) / dur:.2f}/s), co ma {100 * np.mean([r_[3] for r_ in q]):.0f}% quet")


if __name__ == "__main__":
    if sys.argv[1] == "record":
        if len(sys.argv) > 5:
            START = tuple(float(v) for v in sys.argv[3:6])
            PLAN_ARG = [(10, 0, 0), (12, .2, "sin"), (10, 0, .4), (10, 0, -.4), (12, .2, 0), (12, -.15, 0), (12, .2, "sin"), (10, 0, 0)]
        record(sys.argv[2], 0)
    else:
        replay(sys.argv[2])
