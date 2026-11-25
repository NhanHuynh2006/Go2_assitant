#!/usr/bin/env python3
"""GAZEBO: chay eval_sim NGUYEN VAN + do lech thoi gian trong DUNG tien trinh eval_sim (chi GHI, khong doi hanh vi).
Boc `callback` cua subscription LiDAR / odom / IMU san co cua RosBus (ghi roi goi callback goc). Ghi dong vao <rec>.
  venv/bin/python research/gz/eval_probe.py <rec.stream> <cac tham so eval_sim...>
Phat lai: venv/bin/python research/gz/scan_probe.py replay_stream <rec.stream>
"""
import os, pickle, sys, threading, time
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
REC_PATH = sys.argv[1]
sys.argv = [os.path.join(HERE, "eval_sim.py")] + sys.argv[2:]
import eval_sim, robot_ros                                       # noqa: E402
from rclpy.serialization import serialize_message                 # noqa: E402
F = open(REC_PATH, "wb")
LK = threading.Lock()


def put(kind, rec):
    with LK:
        pickle.dump((kind, rec), F)
        F.flush()


def st(h):
    return h.stamp.sec + h.stamp.nanosec * 1e-9


orig_init = eval_sim.GoVoiceSim.__init__


def init(self, *a, **k):
    orig_init(self, *a, **k)
    node = robot_ros.RosBus.get().node
    r = next(iter(self.robots.values()))
    last = {"odom": None}
    for sub in list(node.subscriptions):
        t, cb = sub.topic_name, sub.callback
        if t.endswith("gazebo/odom"):
            def f(msg, cb=cb):
                p, q = msg.pose.pose.position, msg.pose.pose.orientation
                last["odom"] = st(msg.header)
                put("odom", (st(msg.header), p.x, p.y, robot_ros._yaw_of(q), time.monotonic()))
                cb(msg)
            sub.callback = f
        elif t.endswith("imu/data"):
            def f(msg, cb=cb):
                cb(msg)
                put("imu", (st(msg.header), r.rp[0], r.rp[1], msg.angular_velocity.z, time.monotonic()))
            sub.callback = f
        elif t.endswith("velodyne_points/points"):
            def f(msg, cb=cb):
                now = time.monotonic()
                rec = dict(stamp=st(msg.header), arr=now, odom_st=last["odom"], pose=r.map_pose(), rp=r.rp,
                           cnt=r._scan_count, raw=serialize_message(msg), ctrl=r.controller)
                cb(msg)
                rec.update(cb_ms=(time.monotonic() - now) * 1000, lidar_tf=r._lidar_tf, body_box=r.body_box,
                           base_height=r.base_height,
                           movers=[(round(float(q["p"][0]), 2), round(float(q["p"][1]), 2), id(q)) for q in r.tracker.movers()])
                put("scan", rec)
            sub.callback = f
    print("[probe] da boc subscription:", [s.topic_name for s in node.subscriptions], flush=True)


eval_sim.GoVoiceSim.__init__ = init
orig_ps = eval_sim.probe_start


def ps(r, seed):
    put("ep_start", time.monotonic())
    orig_ps(r, seed)


eval_sim.probe_start = ps
eval_sim.main()
