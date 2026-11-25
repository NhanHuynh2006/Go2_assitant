#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sysid_real.py - kich ban DO dong hoc van toc Go2 that (SportClient cap cao, KHONG LowCmd).

  NGUOI DUNG tu chay, tay cam remote (L2+B = phanh). Xem HUONG_DAN_DO.md truoc.

  python3 sysid_real.py --sim --stage 1 --set fit --out /tmp/s1_fit.npz     # chay thu voi robot gia (khong can SDK)
  python3 sysid_real.py --check --iface eth0                                # chi doc, khong gui lenh nao
  python3 sysid_real.py --go --stage 1 --set fit  --iface eth0 --out ~/sysid/s1_fit.npz
  python3 sysid_real.py --go --stage 1 --set test --iface eth0 --out ~/sysid/s1_test.npz

Chay duoc tren Orin cua robot (Python 3.8, numpy, unitree_sdk2py). KHONG chay cung luc voi go2_hardware_bridge
--allow-motion, go2_auto, hay app dieu khien: hai nguon lenh lam hong ca phep do lan an toan.
"""
from __future__ import print_function
import argparse
import math
import os
import select
import signal
import sys
import threading
import time

import numpy as np

# ------------------------------------------------------------------ gioi han CUNG (khong co tuy chon noi rong)
STAGES = {1: (0.20, 0.15, 0.40), 2: (0.40, 0.25, 0.80), 3: (0.60, 0.40, 1.00)}    # |vx| |vy| |wz|
ABS_MAX = (0.60, 0.40, 1.00)
SEG_MAX = 3.0            # s, mot lenh giu toi da
RUN_MAX = 170.0          # s, tong thoi gian co lenh
FENCE = 2.2              # m, ban kinh hang rao (do bang odom nhan SAFE_SCALE)
SAFE_SCALE = 1.25        # odom tho do THIEU ~18 % (xem REPORT_DYN) -> nhan du khi tinh hang rao
STOP_DIST = 0.70         # m, vat tren LiDAR L1 gan hon (theo huong di) -> dung
T_REACT = 0.8            # s, du phong phan ung + quang duong phanh
RATE = 50.0              # Hz gui Move
BAT_MIN, TEMP_MAX, TILT = 35, 70, math.radians(12)
TILT_RUN = math.radians(20)
REMOTE_DB = 0.15

R_L1 = np.array([[0.52611, -0.81014, 0.25862], [-0.83867, -0.54464, 0.0], [0.14085, -0.21690, -0.96598]])
T_L1 = np.array([0.2822, 0.0, 0.0])


def schedule(stage, which):
    """Danh sach (ten, vx, vy, wz, giay). Cap +/- de quay ve gan cho cu. 'fit' va 'test' KHAC nhau han
    (test: muc lenh va do dai khac, ket hop nhieu truc) -> test la du lieu chua dung."""
    X, Y, W = STAGES[stage]
    out = []

    def pair(nm, u, T):
        for s in (1, -1):
            out.append((nm, s * u[0], s * u[1], s * u[2], T))
            out.append(("nghi", 0.0, 0.0, 0.0, 1.2))

    if which == "fit":
        for f in (0.5, 0.75, 1.0):
            pair("vx", (f * X, 0, 0), 1.7 if stage == 3 else 2.2)
        for f in (0.6, 1.0):
            pair("vy", (0, f * Y, 0), 2.0)
        for f in (0.4, 0.7, 1.0):
            pair("wz", (0, 0, f * W), 2.2)
        pair("xw", (.8 * X, 0, .7 * W), 2.0)
        pair("xy", (.7 * X, .7 * Y, 0), 2.0)
        for f in (0.35, 0.9):                                       # doi dau truc tiep -> tre / gia toc
            out.append(("dao", f * X, 0, 0, 1.0)); out.append(("dao", -f * X, 0, 0, 1.0))
            out.append(("nghi", 0, 0, 0, 1.0))
            out.append(("daow", 0, 0, f * W, .8)); out.append(("daow", 0, 0, -f * W, .8))
            out.append(("nghi", 0, 0, 0, 1.0))
    else:
        r = np.random.RandomState(100 + stage)
        for k in range(12):
            u = np.array([r.uniform(-.8, 1) * X, r.uniform(-1, 1) * Y * (r.rand() < .6), r.uniform(-1, 1) * W * (r.rand() < .6)])
            T = r.uniform(.6, 1.6)
            out.append(("ngau", u[0], u[1], u[2], T))
            if r.rand() < .5:
                out.append(("ngau", -u[0], -u[1], -u[2], T))
            if r.rand() < .4:
                out.append(("nghi", 0, 0, 0, 1.0))
        pair("vx", (.62 * X, 0, 0), 1.7)
        pair("wz", (0, 0, .85 * W), 1.5)
    out.append(("nghi", 0.0, 0.0, 0.0, 1.5))
    assert all(T <= SEG_MAX for *_, T in out) and sum(T for *_, T in out) < RUN_MAX
    for _, a, b, c, _ in out:
        assert abs(a) <= X + 1e-9 and abs(b) <= Y + 1e-9 and abs(c) <= W + 1e-9
    return out


# ------------------------------------------------------------------ nhat ky
class Log:
    def __init__(self):
        self.lock = threading.Lock()
        self.cmd, self.sport, self.odom, self.remote, self.ev = [], [], [], [], []
        self.cl_t, self.cl_p, self.cl_n = [], [], []

    def save(self, path, meta):
        with self.lock:
            d = dict(cmd=np.array(self.cmd, float).reshape(-1, 4), sport=np.array(self.sport, float),
                     odom=np.array(self.odom, float), remote=np.array(self.remote, float),
                     events=np.array([repr(e) for e in self.ev]), meta=np.array(repr(meta)),
                     cloud_t=np.array(self.cl_t, float).reshape(-1, 2), cloud_n=np.array(self.cl_n, int),
                     cloud_xyzt=(np.concatenate(self.cl_p) if self.cl_p else np.zeros((0, 4), np.float32)))
        np.savez_compressed(path, **d)
        print("da ghi", path, {k: v.shape for k, v in d.items()})


# cot sport: t_mono, t_wall, stamp, px,py,pz, vx,vy,vz, yaw_speed, qw,qx,qy,qz, gx,gy,gz, ax,ay,az, body_h, mode, gait,
#            foot0..3, range0..3, error_code
# cot odom : t_mono, t_wall, stamp, px,py,pz, qx,qy,qz,qw, vx,vy,vz, wx,wy,wz        (twist: he THAN, da kiem tra)
# cot cmd  : t_mono, vx, vy, wz   (moi lan goi Move)


class RealIO:
    """SportClient cap cao + dang ky trang thai. KHONG co LowCmd trong file nay."""

    def __init__(self, iface, log, full=False):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
        from unitree_sdk2py.go2.sport.sport_client import SportClient
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_, WirelessController_, LowState_
        from unitree_sdk2py.idl.nav_msgs.msg.dds_ import Odometry_
        from unitree_sdk2py.idl.sensor_msgs.msg.dds_ import PointCloud2_
        self.log = log
        self.st = dict(sport_t=0.0, odom_t=0.0, cloud_t=0.0, remote_t=0.0, near_t=0.0, low_t=0.0, near=None, batt=None, temp=None, odom=None)
        ChannelFactoryInitialize(0, iface)
        self.subs = []
        for topic, ty, cb in (("rt/sportmodestate" if full else "rt/lf/sportmodestate", SportModeState_, self.on_sport),
                              ("rt/utlidar/robot_odom", Odometry_, self.on_odom),
                              ("rt/wirelesscontroller", WirelessController_, self.on_remote),
                              ("rt/lf/lowstate", LowState_, self.on_low),
                              ("rt/utlidar/cloud", PointCloud2_, self.on_cloud)):
            s = ChannelSubscriber(topic, ty)
            s.Init(cb, 10)
            self.subs.append(s)
        self.client = SportClient()
        self.client.SetTimeout(1.0)
        self.client.Init()

    def on_sport(self, m):
        t, w = time.monotonic(), time.time()
        im = m.imu_state
        row = [t, w, m.stamp.sec + 1e-9 * m.stamp.nanosec] + list(m.position) + list(m.velocity) + [m.yaw_speed] + list(im.quaternion) + \
            list(im.gyroscope) + list(im.accelerometer) + [m.body_height, m.mode, m.gait_type] + list(m.foot_force) + list(m.range_obstacle) + [m.error_code]
        with self.log.lock:
            self.log.sport.append(row)
        self.st.update(sport_t=t, bh=m.body_height, mode=m.mode, rpy=list(im.rpy), feet=list(m.foot_force), err=m.error_code)

    def on_odom(self, m):
        t, w = time.monotonic(), time.time()
        p, q, v, o = m.pose.pose.position, m.pose.pose.orientation, m.twist.twist.linear, m.twist.twist.angular
        row = [t, w, m.header.stamp.sec + 1e-9 * m.header.stamp.nanosec, p.x, p.y, p.z, q.x, q.y, q.z, q.w, v.x, v.y, v.z, o.x, o.y, o.z]
        with self.log.lock:
            self.log.odom.append(row)
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.st.update(odom_t=t, odom=(p.x, p.y, yaw))

    def on_remote(self, m):
        t = time.monotonic()
        act = max(abs(m.lx), abs(m.ly), abs(m.rx), abs(m.ry)) > REMOTE_DB or m.keys != 0
        with self.log.lock:
            self.log.remote.append([t, m.lx, m.ly, m.rx, m.ry, m.keys])
        self.st["remote_seen"] = t
        if act:
            self.st["remote_t"] = t

    def on_low(self, m):
        self.st.update(low_t=time.monotonic(), batt=m.bms_state.soc, temp=max(m.motor_state[i].temperature for i in range(12)))

    def on_cloud(self, m):
        t, w = time.monotonic(), time.time()
        off = {f.name: f.offset for f in m.fields}
        raw = np.frombuffer(bytes(bytearray(m.data)), np.uint8)
        n = len(raw) // m.point_step
        raw = raw[:n * m.point_step].reshape(n, m.point_step)
        g = lambda k: raw[:, off[k]:off[k] + 4].copy().view(np.float32).ravel()
        p = np.stack([g("x"), g("y"), g("z"), g("time") if "time" in off else np.zeros(n, np.float32)], 1)
        p = p[np.isfinite(p).all(1) & (np.abs(p[:, :3]).sum(1) > .05)]
        with self.log.lock:
            self.log.cl_t.append([t, w]); self.log.cl_n.append(len(p)); self.log.cl_p.append(p.astype(np.float32))
        b = p[:, :3].astype(float) @ R_L1.T + T_L1
        m_ = (np.abs(b[:, 0]) < .45) & (np.abs(b[:, 1]) < .28) & (b[:, 2] < .15)          # than robot
        b = b[~m_ & (b[:, 2] > -.22) & (b[:, 2] < .5)]
        self.recent = (getattr(self, "recent", []) + [b[:, :2]])[-4:]           # ~0.25 s: mot vong L1 rat thua
        self.st.update(near=np.concatenate(self.recent), cloud_t=t)

    def move(self, u):
        self.client.Move(float(u[0]), float(u[1]), float(u[2]))

    def stop(self):
        self.client.StopMove()

    def prepare(self):
        self.client.BalanceStand()

    def now(self):
        return time.monotonic()

    def sleep(self, dt):
        time.sleep(dt)


class SimIO:
    """Robot gia de thu kich ban + fit_real (tham so THAT nam trong self.P, ghi vao meta)."""
    P = dict(gain=[.95, .9, .92], back=.9, sat=[.8, .5, 1.6], tau=[.25, .2, .15], delay=.10, amax=[2.0, 1.5, 5.0], xoff=.04,
             odom_scale=1 / 1.2, odom_lag=.01)

    def __init__(self, log, seed=0):
        self.log, self.t, self.x, self.v = log, 100.0, np.zeros(3), np.zeros(3)
        self.q, self.cmd, self.od, self.r = [], np.zeros(3), np.zeros(3), np.random.RandomState(seed)
        self.sw = np.zeros(3)
        self.st = dict(sport_t=100.0, odom_t=100.0, cloud_t=100.0, remote_t=0.0, remote_seen=100.0, low_t=100.0, near=np.array([[5., 0.]]),
                       batt=80, temp=40, bh=.32, mode=1, rpy=[0, 0, 0], feet=[40] * 4, err=0, odom=(0., 0., 0.))

    def move(self, u):
        self.q.append((self.t + self.P["delay"], np.array(u, float)))

    def stop(self):
        self.move((0, 0, 0))

    def prepare(self):
        pass

    def now(self):
        return self.t

    def sleep(self, dt):
        P = self.P
        for _ in range(max(1, int(round(dt / .005)))):
            h = .005
            self.t += h
            while self.q and self.q[0][0] <= self.t:
                self.cmd = self.q.pop(0)[1]
            g = np.array(P["gain"]) * [P["back"] if self.cmd[0] < 0 else 1.0, 1.0, 1.0]
            s = np.array(P["sat"]); ss = s * np.tanh(g * self.cmd / s)
            a = np.clip((ss - self.v) / np.array(P["tau"]), -np.array(P["amax"]), np.array(P["amax"]))
            self.v = self.v + h * a
            rho = math.exp(-h / .08)
            self.sw = rho * self.sw + math.sqrt(1 - rho ** 2) * self.r.normal(size=3) * np.array([.08, .07, .12]) * (np.abs(self.cmd).sum() > .02)
            vb = self.v + self.sw + np.array([0, P["xoff"] * self.v[2], 0])
            c, s_ = math.cos(self.x[2]), math.sin(self.x[2])
            dx = h * np.array([vb[0] * c - vb[1] * s_, vb[0] * s_ + vb[1] * c, vb[2]])
            self.x += dx; self.od += dx * [P["odom_scale"], P["odom_scale"], 1]
            if int(round(self.t / h)) % 2 == 0:
                y = self.x[2]
                k = P["odom_scale"]
                self.log.odom.append([self.t + P["odom_lag"], self.t, self.t, self.od[0], self.od[1], .3, 0, 0, math.sin(y / 2), math.cos(y / 2),
                                      k * vb[0], k * vb[1], 0, 0, 0, vb[2] + self.r.normal() * .02])
        t = self.t
        self.st.update(sport_t=t, odom_t=t, cloud_t=t, remote_seen=t, low_t=t, odom=(self.od[0], self.od[1], self.x[2]))


# ------------------------------------------------------------------ kiem tra an toan
def preflight(io, need_cloud=True):
    s, t, bad = io.st, io.now(), []
    if t - s.get("sport_t", 0) > .5: bad.append("khong co rt/sportmodestate")
    if t - s.get("odom_t", 0) > .3: bad.append("khong co rt/utlidar/robot_odom")
    if need_cloud and t - s.get("cloud_t", 0) > 1.0: bad.append("khong co rt/utlidar/cloud (LiDAR la may quet chong va, bat buoc)")
    if t - s.get("remote_seen", 0) > 1.0: bad.append("khong thay remote (rt/wirelesscontroller)")
    if t - s.get("low_t", 0) > 2.0 or s.get("batt") is None: bad.append("khong co rt/lf/lowstate")
    if bad: return bad
    if s["batt"] < BAT_MIN: bad.append("pin %d %% < %d" % (s["batt"], BAT_MIN))
    if s["temp"] > TEMP_MAX: bad.append("dong co nong %d C" % s["temp"])
    if s["bh"] < .25: bad.append("robot chua dung (body %.2f m)" % s["bh"])
    if max(abs(s["rpy"][0]), abs(s["rpy"][1])) > TILT: bad.append("nghieng")
    if s.get("err"): print("  (bao) error_code/trang thai firmware = %s (firmware moi dung truong nay lam ma che do; KHONG chan, da ghi nhat ky)" % s["err"])
    return bad


def danger(io, u, home):
    """Ly do phai dung NGAY, hoac None."""
    s, t = io.st, io.now()
    if t - s["sport_t"] > .5 or t - s["odom_t"] > .2: return "mat trang thai/odom"
    if t - s["cloud_t"] > .6: return "mat LiDAR"
    if t - s.get("remote_seen", 0) > 1.5: return "mat song remote"
    if t - s["remote_t"] < 1.0 and s["remote_t"] > 0: return "nguoi gat remote - nhuong"
    if max(abs(s["rpy"][0]), abs(s["rpy"][1])) > TILT_RUN: return "nghieng qua"
    if s["bh"] < .20: return "than thap"
    x, y, yaw = s["odom"]
    v = np.hypot(u[0], u[1]) * 1.25
    c, sn = math.cos(yaw), math.sin(yaw)
    d = np.array([c * u[0] - sn * u[1], sn * u[0] + c * u[1]]) * 1.25 * T_REACT
    p = (np.array([x, y]) - home) * SAFE_SCALE
    if np.hypot(*(p + d)) > FENCE and np.hypot(*(p + d)) > np.hypot(*p): return "hang rao %.1f m" % FENCE
    nr = s.get("near")
    if nr is not None and len(nr) and v > .02:
        dirn = np.array([u[0], u[1]]) / max(np.hypot(u[0], u[1]), 1e-6)
        al = nr @ dirn; la = np.abs(nr @ np.array([-dirn[1], dirn[0]]))
        # 0.38 = nua chieu dai than; loc nhieu: >= 5 diem trong hanh lang
        if ((al > .3) & (al < .38 + STOP_DIST + v * T_REACT * .5) & (la < .35)).sum() >= 5: return "vat can truoc mat"
    if nr is not None and len(nr) and abs(u[2]) > .05 and (np.hypot(*nr.T) < .55).sum() >= 8: return "vat sat than khi quay"
    return None


def key():
    try:
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.readline()
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=1, choices=(1, 2, 3))
    ap.add_argument("--set", default="fit", choices=("fit", "test"))
    ap.add_argument("--iface", default="eth0")
    ap.add_argument("--out", default="sysid.npz")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--go", action="store_true", help="GUI LENH THAT (mac dinh: chi in ke hoach)")
    g.add_argument("--check", action="store_true", help="chi doc trang thai 10 s")
    g.add_argument("--sim", action="store_true", help="robot gia")
    ap.add_argument("--tape", type=float, default=0.0, help="chi di thang vx nay 3 s (do thuoc day), <= muc stage")
    ap.add_argument("--full", action="store_true", help="rt/sportmodestate ~300 Hz (nang cho Python); mac dinh ban lf")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    sch = schedule(a.stage, a.set)
    if a.tape:
        assert 0 < a.tape <= STAGES[a.stage][0]
        sch = [("nghi", 0, 0, 0, 1.0), ("tape", a.tape, 0, 0, SEG_MAX), ("nghi", 0, 0, 0, 2.0)]
    tot = sum(s[-1] for s in sch)
    print("giai doan %d (%s): %d doan, %.0f s; gioi han vx %.2f vy %.2f wz %.2f" % ((a.stage, a.set, len(sch), tot) + STAGES[a.stage]))
    if not (a.go or a.check or a.sim):
        for s in sch: print("  %-5s vx %+.2f vy %+.2f wz %+.2f  %.1f s" % s)
        print("CHI IN KE HOACH. --sim de thu, --check de doc, --go de chay that.")
        return 0
    if a.go and a.stage > 1 and not a.tape:
        need = os.path.join(os.path.dirname(os.path.abspath(os.path.expanduser(a.out))), "stage%d_%s.ok" % (a.stage - 1, "fit"))
        if not os.path.exists(need):
            print("CHUA duoc chay giai doan %d: thieu %s (chay xong giai doan %d khong bi dung khan)" % (a.stage, need, a.stage - 1)); return 2
    out = os.path.abspath(os.path.expanduser(a.out))
    log = Log()
    io = SimIO(log, a.seed) if a.sim else RealIO(a.iface, log, a.full)
    io.sleep(2.0)
    if a.check:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 10:
            s = io.st
            print("pin %s nhiet %s than %.2f mode %s odom %s | L1 %d diem | loi: %s" % (
                s.get("batt"), s.get("temp"), s.get("bh", 0), s.get("mode"), np.round(s.get("odom") or 0, 2),
                0 if s.get("near") is None else len(s["near"]), preflight(io)), flush=True)
            time.sleep(1.0)
        print("tan so: sport %.0f Hz, odom %.0f Hz, cloud %.1f Hz, remote %.0f Hz" % tuple(len(x) / 12.0 for x in (log.sport, log.odom, log.cl_t, log.remote)))
        log.save(out, dict(kind="check")); return 0
    bad = preflight(io)
    if bad:
        print("KHONG CHAY:", "; ".join(bad)); return 2
    if a.go:
        print("\n1) San trong >= 6 x 6 m, khong nguoi/vat, san kho.  2) TAY CAM REMOTE.  3) Phim ENTER = dung, Ctrl-C = dung.  L2+B = phanh khan.")
        print("   Thu remote: gat nhe can trai trong 15 s de xac nhan co the gianh quyen...", flush=True)
        t0, io.st["remote_t"] = time.monotonic(), 0.0
        while time.monotonic() - t0 < 15 and not io.st["remote_t"]:
            time.sleep(.05)
        if not io.st["remote_t"]:
            print("KHONG thay remote -> khong chay."); return 2
        print("   OK. Tha remote."); time.sleep(2.0)
        if input("   Go dung chu  TOI CAM REMOTE  de bat dau: ").strip() != "TOI CAM REMOTE":
            print("huy"); return 2
        io.st["remote_t"] = 0.0
    halt = {"why": None}
    for sg in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sg, lambda *_: halt.update(why="tin hieu dung"))
    done = False
    try:
        io.prepare()                                  # BalanceStand; firmware bo Move ~1 s sau do
        io.sleep(2.0)
        home = np.array(io.st["odom"][:2])
        t_next = io.now(); t_run = io.now()
        for k, (nm, vx, vy, wz, T) in enumerate(sch):
            u = np.clip([vx, vy, wz], -np.array(ABS_MAX), ABS_MAX)
            log.ev.append((io.now(), "seg", k, nm, float(u[0]), float(u[1]), float(u[2]), T))
            t_end = io.now() + T
            skip = False
            while io.now() < t_end:
                why = halt["why"] or (None if not a.go else ("ENTER" if key() is not None else None)) or danger(io, u, home)
                if io.now() - t_run > RUN_MAX: why = "het gio"
                if why and (why.startswith("hang rao") or why.startswith("vat")):
                    log.ev.append((io.now(), "bo", k, why)); print("  bo doan", k, nm, why, flush=True)
                    skip = True
                    u = np.zeros(3)
                    io.move(u); log.cmd.append([io.now(), 0, 0, 0])
                    break
                if why:
                    raise RuntimeError(why)
                io.move(u)
                log.cmd.append([io.now(), u[0], u[1], u[2]])
                t_next = max(t_next + 1 / RATE, io.now() + .001)
                io.sleep(max(.001, t_next - io.now()))
                if io.now() - t_next > .15:
                    log.ev.append((io.now(), "tre vong lap", io.now() - t_next))
            if skip:
                te = io.now() + 1.0
                while io.now() < te:
                    if halt["why"] or (a.go and key() is not None): raise RuntimeError("nguoi dung")
                    io.move((0, 0, 0)); log.cmd.append([io.now(), 0, 0, 0]); io.sleep(1 / RATE)
        done = True
    except (RuntimeError, KeyboardInterrupt) as e:
        print("\nDUNG:", e); log.ev.append((io.now(), "DUNG", str(e)))
    finally:
        for _ in range(10):
            try:
                io.move((0, 0, 0)); log.cmd.append([io.now(), 0, 0, 0])
            except Exception as e:
                print("move0:", e)
            io.sleep(.02)
        try:
            io.stop()
        except Exception as e:
            print("StopMove:", e, " -> BAM L2+B")
        d = os.path.dirname(out)
        if d and not os.path.isdir(d): os.makedirs(d)
        log.save(out, dict(stage=a.stage, set=a.set, tape=a.tape, sim=a.sim, done=done, limits=STAGES[a.stage],
                           true=SimIO.P if a.sim else None))
        if done and not a.tape and not a.sim:
            open(os.path.join(d, "stage%d_%s.ok" % (a.stage, a.set)), "w").write(time.ctime())
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
