#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_sim.py — DANH GIA DINH LUONG GoVoice trong mo phong (so lieu cho bai bao).

Moi lan thu: dich chuyen robot ve vi tri xuat phat (gz set_pose), XOA ban do (moi
truong chua biet), noi 1 cau lenh qua DUNG pipeline that (Combo/Reflex/LLM ->
SafetyGuard -> executor -> robot_ros), roi cham bang VI TRI THAT tu Gazebo va hinh
hoc that cua the gioi (doc tu file .sdf):

  thanh cong      dich lech < 0.35 m (nav) / sai so < 0.10 m, 10 do (chuyen dong)
                  / KHONG dam (an toan), va khong va cham
  va cham         than robot trong sim (theo URDF) cham vat, hoac 2 robot cham nhau
  ho an toan      khoang cach nho nhat neu than la Go2 THAT (0.70 x 0.31 m, co vo dau)
  SPL             thanh cong x duong ngan nhat / max(duong da di, ngan nhat)
                  (Anderson et al., "On Evaluation of Embodied Navigation Agents", 2018)
  khoang ho min   khoang cach nho nhat tu than robot toi vat bat ky

Cau hinh so sanh (ablation):
  full        LiDAR + D435i + ban do + A* + phanh + nhuong duong
  lidar_only  bo camera depth
  no_avoid    di thang toi dich, khong phanh (ban dau tien cua run_sim)
  open_loop   di theo van toc x thoi gian nhu robot that (chi bai chuyen dong)
  no_coord    nhieu robot: khong nhuong duong, khong coi nhau la vat can

CHAY (sim phai dang chay, headless cho nhanh):
  ros2 launch go2_voice voice_sim.launch.py headless:=true               # suite single
  python3 eval_sim.py --suite single --trials 2
  ros2 launch go2_voice voice_sim.launch.py headless:=true robots:=2     # suite multi
  python3 eval_sim.py --suite multi --trials 3
Ket qua: results/<suite>_<thoi gian>/{trials.csv, summary.md, traj.json, traj.png}
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "LOCALHOST"
os.environ.setdefault("GZ_IP", "127.0.0.1")
os.environ.setdefault("FASTDDS_BUILTIN_TRANSPORTS", "LARGE_DATA")
os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp")   # trung voi sim

import numpy as np  # noqa: E402

from assistant_realtime import load_config  # noqa: E402
from nav_local import OccGrid, path_length, plan  # noqa: E402
import robot_ros  # noqa: E402
from robot_ros import discover_robots  # noqa: E402
from run_sim import GoVoiceSim  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = os.path.expanduser("~/ros2_ws/install/unitree_go2_description/share/"
                           "unitree_go2_description/worlds/voice_house.sdf")
# Hinh than robot TRONG SIM (doc tu URDF: than 0.376 m, hong +-0.193, D435i o
# +0.31, ban chan): truoc 0.32, sau 0.25, nua rong 0.16 -> dung de cham VA CHAM.
# Chu Go2 that dai 0.70 x 0.31 m (co vo dau) -> dung de do KHOANG HO AN TOAN.
SIM_BODY = (0.32, 0.25, 0.16)
REAL_BODY = (0.35, 0.35, 0.155)


# ---------------------------------------------------------------- the gioi that
def load_boxes(path):
    out = []
    for m in ET.parse(path).getroot().iter("model"):
        size = m.find("./link/collision/geometry/box/size")
        if size is None:
            continue
        if (m.get("name") or "").startswith(("cart", "person")):
            continue                                # vat DONG: cham rieng (Monitor)
        pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
        sx, sy, _ = (float(v) for v in size.text.split())
        out.append((m.get("name"), pose[0], pose[1], sx, sy, pose[5]))
    # coc giao thong / tru (cylinder) -> hop vuong bao ngoai (cham va cham hoi chat hon)
    for m in ET.parse(path).getroot().iter("model"):
        rad = m.find("./link/collision/geometry/cylinder/radius")
        nm = m.get("name") or ""
        if rad is None or nm.startswith("person"):
            continue
        pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
        d = 2 * float(rad.text)
        out.append((nm, pose[0], pose[1], d, d, 0.0))
    return out


def footprint(x, y, yaw, body=SIM_BODY, n=8):
    front, rear, hw = body
    a = np.linspace(-rear, front, n)
    b = np.linspace(-hw, hw, 4)
    A, B = np.meshgrid(a, b)
    A, B = A.ravel(), B.ravel()
    c, s = math.cos(yaw), math.sin(yaw)
    return np.stack([x + c * A - s * B, y + s * A + c * B], axis=1)


def sd_box(pts, cx, cy, sx, sy, yaw):
    """Khoang cach co dau tu diem toi hop xoay (am = ben trong)."""
    c, s = math.cos(-yaw), math.sin(-yaw)
    lx = c * (pts[:, 0] - cx) - s * (pts[:, 1] - cy)
    ly = s * (pts[:, 0] - cx) + c * (pts[:, 1] - cy)
    dx, dy = np.abs(lx) - sx / 2, np.abs(ly) - sy / 2
    out = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
    return out + np.minimum(np.maximum(dx, dy), 0)


class World:
    def __init__(self, path, bounds=(-12.0, -12.0, 24.0, 24.0)):
        self.path = path
        self.boxes = load_boxes(path)
        self.grid = OccGrid(xmin=bounds[0], ymin=bounds[1], width=bounds[2], height=bounds[3])
        for _, cx, cy, sx, sy, yaw in self.boxes:
            self.grid.mark_box(cx, cy, sx, sy, yaw)

    def clearance(self, x, y, yaw, body=SIM_BODY):
        p = footprint(x, y, yaw, body)
        return min(float(sd_box(p, *b[1:]).min()) for b in self.boxes)

    def shortest(self, start, goal):
        pts, _ = plan(self.grid, start, goal, lethal=0.40, soft=0.80)   # nhu robot_ros
        return path_length(pts) if pts else float("nan")


def robot_gap(pa, pb, body=SIM_BODY):
    """Khoang cach nho nhat giua than 2 robot (am = chong len nhau)."""
    front, rear, hw = body
    off = (front - rear) / 2
    cx, cy = pb[0] + off * math.cos(pb[2]), pb[1] + off * math.sin(pb[2])
    return float(sd_box(footprint(*pa, body), cx, cy, front + rear, 2 * hw, pb[2]).min())


# ---------------------------------------------------------------- dieu khien sim
def teleport(model, x, y, yaw):
    req = (f'name: "{model}", position: {{x: {x}, y: {y}, z: 0.32}}, '
           f'orientation: {{z: {math.sin(yaw / 2)}, w: {math.cos(yaw / 2)}}}')
    subprocess.run(["gz", "service", "-s", f"/world/{WORLD_NAME}/set_pose",
                    "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
                    "--timeout", "3000", "--req", req], capture_output=True, timeout=10)


PERSON_R = 0.22                                     # ban kinh "nguoi" trong voice_house.sdf
WORLD_NAME = "voice_house"                          # main() doi theo the gioi dang chay


class GzStats:
    """RTF Gazebo tu TIEN TRINH RIENG `gz topic -e -t /world/<ten>/stats` (1 tien trinh cho ca lan chay).
    KHONG subscribe gz-transport trong tien trinh nay: thu 24/11 thi callback stats tranh GIL voi
    Crowd._set (node.request chan 500 ms) -> moi set_pose het gio, ca tien trinh dung (ctrl.step 85 s, mat cam bien)."""
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self.buf = []                       # (time.time(), sim_time_s, rtf)
        self.proc = None
        try:
            self.proc = subprocess.Popen(["gz", "topic", "-e", "-t", f"/world/{WORLD_NAME}/stats"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
            threading.Thread(target=self._read, daemon=True).start()
            import atexit
            atexit.register(self.close)
        except Exception as e:                                      # noqa: BLE001
            print(f"[monitor] khong doc duoc RTF: {e!r}", flush=True)

    def _read(self):
        blk, sec, nsec, f = None, 0, 0, None
        for line in self.proc.stdout:
            ln = line.strip()
            if ln.endswith("{"):
                blk = ln[:-1].strip()
            elif ln == "}":
                blk = None
            elif blk == "sim_time" and ln.startswith("sec:"):
                sec = int(ln.split(":")[1])
            elif blk == "sim_time" and ln.startswith("nsec:"):
                nsec = int(ln.split(":")[1])
            elif blk is None and ln.startswith("real_time_factor:"):
                f = float(ln.split(":")[1])
            elif ln == "" and f is not None:
                self.buf.append((time.time(), round(sec + nsec * 1e-9, 3), round(f, 3)))
                if len(self.buf) > 200000:
                    del self.buf[:100000]
                blk, sec, nsec, f = None, 0, 0, None

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()


class Monitor(threading.Thread):
    """Lay mau vi tri THAT 10 Hz trong luc thu: quy dao, khoang ho, va cham."""

    def __init__(self, robots, world, mover=None):
        super().__init__(daemon=True)
        self.robots, self.world, self.mover = robots, world, mover
        self.min_person = float("inf")
        self.person_traj = []
        self.traj = {ns: [] for ns in robots}
        self.min_clear = {ns: float("inf") for ns in robots}
        self.min_clear_real = {ns: float("inf") for ns in robots}
        self.min_gap = float("inf")
        self.running = True
        self.t0 = time.time()
        self.moved_at = {}                 # lan dau than robot roi cho > 3 cm / quay > 3 do
        self.times = []
        # PREREG_TEST §0.4 (24/11, GAZEBO): log CANH NHAU moi nhip (10 Hz) - robot, MOI nguoi/xe, track
        # nguoi tracker xac nhan, RTF Gazebo - va lan cham DAU TIEN (de tinh D1/D2, audit/a9_fault_def.py)
        self.log = dict(t=[], robot={ns: [] for ns in robots}, people=[], trk={ns: [] for ns in robots})
        self.first_contact = None          # cham nguoi/xe dau tien (d < 0)
        self.first_static = {}             # ns -> cham vat tinh dau tien (ho < 0)
        self._trk_ids = {}
        self.gap = {ns: [0.0, 0.0] for ns in robots}     # tuoi lon nhat (s) cua odom, LiDAR (loi ky thuat > 2 s, §5)
        self.rtf = []                      # (t_wall, sim_time_s, real_time_factor) tu /world/<ten>/stats
        self._stats = GzStats.get()

    def _log_tick(self, poses, pr):
        L = self.log
        L["t"].append(round(time.time() - self.t0, 3))
        for ns, p in poses.items():
            L["robot"][ns].append(None if p is None else (round(p[0], 3), round(p[1], 3), round(p[2], 4)))
            r = self.robots[ns]
            now = time.monotonic()
            g = self.gap[ns]
            g[0] = max(g[0], now - r.odom[3]) if getattr(r, "odom", None) else g[0]
            g[1] = max(g[1], now - r.local_t) if getattr(r, "local_t", 0.0) > 0 else g[1]
            try:
                tr = r.tracker.movers()
            except Exception:                                       # noqa: BLE001
                tr = []
            row = []
            for q in tr:
                k = self._trk_ids.setdefault(id(q), len(self._trk_ids))
                row.append((k, round(float(q["p"][0]), 2), round(float(q["p"][1]), 2)))
            L["trk"][ns].append(row)
        L["people"].append([(round(px, 3), round(py, 3), rad) for px, py, rad in pr])

    def run(self):
        while self.running:
            poses = {ns: r.map_pose() for ns, r in self.robots.items()}
            for ns, p in poses.items():
                if p is None:
                    continue
                if self.traj[ns] and ns not in self.moved_at:
                    a = self.traj[ns][0]
                    dyaw = abs(math.atan2(math.sin(p[2] - a[2]), math.cos(p[2] - a[2])))
                    if math.hypot(p[0] - a[0], p[1] - a[1]) > 0.03 or dyaw > 0.05:
                        self.moved_at[ns] = time.time() - self.t0
                self.traj[ns].append((round(p[0], 3), round(p[1], 3), round(p[2], 3)))
                cl = self.world.clearance(*p)
                if cl < 0.0 and ns not in self.first_static:
                    self.first_static[ns] = dict(t=round(time.time() - self.t0, 2), i=len(self.log["t"]),
                                                 d=round(float(cl), 3))
                self.min_clear[ns] = min(self.min_clear[ns], cl)
                self.min_clear_real[ns] = min(self.min_clear_real[ns],
                                              self.world.clearance(*p, body=REAL_BODY))
            self.times.append(time.time() - self.t0)
            pr = []
            if self.mover is not None:
                pr = (self.mover.positions_r() if hasattr(self.mover, "positions_r")
                      else [(px, py, PERSON_R) for px, py in self.mover.positions()])
            i_tick = len(self.log["t"])
            self._log_tick(poses, pr)
            if self.mover is not None:
                prev = getattr(self, "_prev_pr", None)
                prev_pose = getattr(self, "_prev_poses", {})
                for k, (px, py, rad) in enumerate(pr):
                    if k == 0:
                        self.person_traj.append((round(px, 3), round(py, 3), 0.0))
                    for ns, p in poses.items():
                        if p is None:
                            continue
                        if rad >= 0.45:                          # xe day: hop 0.6 x 0.9 m doc truc x
                            d = float(sd_box(footprint(*p), px, py, 0.6, 0.9, 0.0).min())
                        else:
                            d = np.hypot(*(footprint(*p) - [px, py]).T).min() - rad
                        if d < 0.0 and self.first_contact is None:
                            self.first_contact = dict(t=round(time.time() - self.t0, 2), i=i_tick, k=k, ns=ns or "go2",
                                                      d=round(float(d), 3), r=rad)
                        if d < self.min_person:
                            self.min_person = float(d)
                            # ai lao vao ai: van toc nguoi va robot huong vao nhau (m/s)
                            info = dict(t=round(time.time() - self.t0, 1), d=round(float(d), 3))
                            if prev is not None and k < len(prev):
                                vpx, vpy = (px - prev[k][0]) / 0.1, (py - prev[k][1]) / 0.1
                                q = prev_pose.get(ns)
                                vrx, vry = ((p[0] - q[0]) / 0.1, (p[1] - q[1]) / 0.1) if q else (0, 0)
                                ux, uy = (px - p[0]), (py - p[1])
                                n = math.hypot(ux, uy) or 1.0
                                wz = (math.atan2(math.sin(p[2] - q[2]), math.cos(p[2] - q[2])) / 0.1) if q else 0.0
                                rin = (vrx * ux + vry * uy) / n
                                info.update(robot_in=round(rin, 2),
                                            person_in=round(-(vpx * ux + vpy * uy) / n, 2),
                                            robot_v=round(math.hypot(vrx, vry), 2), robot_wz=round(wz, 2),
                                            # LOI CUA ROBOT: robot tien vao (> 0.1 m/s) hoac xoay quet than
                                            at_fault=int(rin > 0.1 or abs(wz) > 0.3))
                            self.col_info = info
                self._prev_pr = pr
                self._prev_poses = dict(poses)
            ps = [p for p in poses.values() if p is not None]
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    self.min_gap = min(self.min_gap, robot_gap(ps[i], ps[j]),
                                       robot_gap(ps[j], ps[i]))
            time.sleep(0.1)

    def close(self):
        """Lay mau RTF trong khoang luot (doc tu GzStats; khong dang ky gz-transport trong tien trinh nay)."""
        self.rtf = [(round(tw - self.t0, 2), st, f) for tw, st, f in list(self._stats.buf) if tw >= self.t0]

    def travel(self, ns):
        t = self.traj[ns]
        return float(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(t, t[1:])))


CONFIGS = {
    "full":       dict(avoid=True, depth=True, closed=True, coord=True, detour=True, people=True),
    "no_people":  dict(avoid=True, depth=True, closed=True, coord=True, detour=True, people=False),
    "brake_only": dict(avoid=True, depth=True, closed=True, coord=True, detour=False),
    "lidar_only": dict(avoid=True, depth=False, closed=True, coord=True, detour=True),
    "no_avoid":   dict(avoid=False, depth=False, closed=True, coord=False, detour=False),
    "open_loop":  dict(avoid=True, depth=True, closed=False, coord=True, detour=True),
    "no_coord":   dict(avoid=True, depth=True, closed=True, coord=False, detour=True),
    # BO DIEU KHIEN cuc bo (suite office): cung cam bien + ban do + A*, chi khac cach bam duong
    "mppi":       dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="mppi"),
    "dwa":        dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="dwa"),
    "log_mppi":   dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="log_mppi"),
    "pp":         dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="pp"),
    "rl":         dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="rl"),
    # bai A: Policy-guided MPPI (tai hien CoRL-MPPI/RAY-TOLD) va AP-MPPI (cai tien de xuat)
    "pgmppi":         dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="pgmppi"),
    "apmppi":         dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="apmppi"),
    "apmppi_multi":   dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="apmppi_multi"),
    "rl_ens":         dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="rl_ens"),
    # kieu Biased-MPPI (Trevisan & Alonso-Mora 2024): nhieu bo goi y (PPO + TD3), ty le co dinh
    "bmppi":          dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="bmppi"),
    # THUAT TOAN DE XUAT + ablation (tat tung thanh phan)
    "prism":          dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism"),
    "prism_noprior":  dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_noprior"),
    "prism_noadapt":  dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_noadapt"),
    "prism_novis":    dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_novis"),
    "prism_nounc":    dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_nounc"),
    # ablation phan goi y RL (gop tu AP-MPPI): ty le CO DINH / khong critic
    "prism_noadaptratio": dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_noadaptratio"),
    "prism_novalue":  dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="prism_novalue"),
    "rl_safe":    dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl="rl_safe"),
}


def config_of(name):
    """Cau hinh theo ten; 'prism@ppo+sac' (bo goi y tuy chon) dung cau hinh day du cua PRISM."""
    if name in CONFIGS:
        return CONFIGS[name]
    if name.startswith(("prism", "rl@", "p2")) or "~v1" in name or ":" in name:
        return dict(avoid=True, depth=True, closed=True, coord=True, detour=True, ctrl=name)
    raise KeyError(name)


def apply_config(gv, cfg):
    for r in gv.robots.values():
        r.avoid, r.use_depth = cfg["avoid"], cfg["depth"]
        r.closed_loop, r.coordinate = cfg["closed"], cfg["coord"]
        r.detour_enabled = cfg["detour"]
        r.people_aware = cfg.get("people", True)
        ctrl = cfg.get("ctrl", "mppi")
        if r.controller != ctrl:
            r.controller, r._ctrl = ctrl, None


def _settled(r, x, y, tol=0.12):
    """Vi tri bao ve da khop cho teleport va robot dung yen (khong con troi)."""
    p1 = r.map_pose()
    time.sleep(0.4)
    p2 = r.map_pose()
    return (math.hypot(p2[0] - x, p2[1] - y) < tol and
            math.hypot(p2[0] - p1[0], p2[1] - p1[1]) < 0.02)


def park_carts():
    """Xe day (voice_office) ra ngoai ban do truoc moi bai: bai truoc de xe giua loi di thi bai
    sau (vd loi pallet) gap vat la -> moi bo ne deu 'ket' (loi danh gia, da gap 21/11)."""
    if WORLD_NAME != "voice_office":
        return
    from movers import CART_PARK
    for k, (x, y) in enumerate(CART_PARK):
        req = (f'name: "cart__{k + 1}", position: {{x: {x}, y: {y}, z: 0.45}}, orientation: {{w: 1}}')
        subprocess.run(["gz", "service", "-s", f"/world/{WORLD_NAME}/set_pose", "--reqtype", "gz.msgs.Pose",
                        "--reptype", "gz.msgs.Boolean", "--timeout", "3000", "--req", req],
                       capture_output=True, timeout=10)


def reset(gv, starts):
    gv.executor.stop_all()
    park_carts()
    for r in gv.robots.values():
        r._halt()
        r._body(0, 0, 0, 0)
        r.last_place = None
    for attempt in range(4):
        for ns, (x, y, yaw) in starts.items():
            teleport(ns or "go2", x, y, yaw)
        time.sleep(3.0)                              # cho dung vung lai
        if all(_settled(gv.robots[ns], x, y) for ns, (x, y, _) in starts.items()):
            break
        for r in gv.robots.values():
            r._halt()
    # Moi truong CHUA BIET moi lan thu. Xoa SAU khi vi tri da on dinh: quet LiDAR luc
    # vi tri con cu (ngay sau teleport) se ve vat ma vao sai cho (da gap: robot phanh
    # vi "vat can 5 cm sau lung" giua phong trong).
    for g in (robot_ros.SHARED_GRID, robot_ros.SHARED_DEPTH):
        with g.lock:
            g.ev[:] = 0
    for r in gv.robots.values():
        r.local_t = r.depth_t = 0.0                 # bo diem quet cu
        reset_learned(r)
    time.sleep(1.0)


def reset_learned(r):
    """PREREG_TEST §0.4: moi luot bat dau tu CUNG trang thai nhu fastsim.make_robot (truoc 24/11 cac uoc luong
    online, track nguoi va bo dieu khien - ca RespModel ben trong - mang tu luot truoc sang luot sau)."""
    from nav_local import BlobTracker
    r.vel_gain = 0.5
    r.vel_gains = np.array([0.5, 0.5, 0.5])
    old, nt = r.tracker, BlobTracker()
    for k in ("mode", "fix_dt"):                   # dat lai o lan quet ke tiep; giu de movers() goi duoc ngay
        if hasattr(old, k):
            setattr(nt, k, getattr(old, k))
    r.tracker = nt
    r._ctrl, r._ctrl_goal, r._ctrl_kind = None, None, None
    r.v_world = (0.0, 0.0)
    r.nav_prefs = {}


# ---------------------------------------------------------------- do thoi gian (PREREG_TEST §0.4, §4 S2)
def install_probes(r):
    """Boc (tren DOI TUONG, khong sua robot_ros) _make_ctrl -> ghi thoi gian ctrl.step, va _twist -> thoi diem
    gui cmd_vel. Khong doi gia tri nao; them seed nhieu MPPI moi luot nhu fastsim ([seed, lan, 11])."""
    if getattr(r, "_gz_probe", False):
        return
    import robot_ros as _rr
    r._gz_probe, r._gz = True, None
    base_make, base_twist = r._make_ctrl, r._twist

    def make_ctrl():
        c = base_make()
        if hasattr(c, "rng") and r._gz is not None and r._gz.get("seed") is not None:
            c.rng = np.random.default_rng(r._gz["seed"])
        step0 = c.step

        def step(*a, **kw):
            t = time.perf_counter()
            out = step0(*a, **kw)
            g = r._gz
            if g is not None:
                g["step_ms"].append(round((time.perf_counter() - t) * 1000, 2))
                g["step_t"].append(round(time.monotonic() - g["t0"], 3))
                g["after_step"] = True
            return out
        c.step = step
        return c

    def twist(vx=0.0, vy=0.0, wz=0.0):
        base_twist(vx, vy, wz)
        g = r._gz
        if g is not None:
            g["cmd_t"].append(round(time.monotonic() - g["t0"], 3))
            g["cmd_ctrl"].append(int(g.pop("after_step", False)))
    r._make_ctrl, r._twist = make_ctrl, twist
    assert isinstance(r, _rr.RosRobotTools)


def probe_start(r, seed):
    r._gz = dict(t0=time.monotonic(), seed=seed, step_ms=[], step_t=[], cmd_t=[], cmd_ctrl=[])


def _pct(a, q):
    return round(float(np.percentile(a, q)), 3) if len(a) else ""


def probe_stats(g):
    """Chu ky cmd_vel cua VONG DIEU KHIEN = khoang cach giua 2 lenh LIEN TIEP cung gui ngay sau ctrl.step; 'all' = moi lenh
    (gop cac lenh cach nhau < 30 ms - _halt gui 3 lenh 20 ms)."""
    st, ct, cc = np.array(g["step_ms"]), np.array(g["cmd_t"]), np.array(g["cmd_ctrl"], bool)
    dc = np.array([ct[k] - ct[k - 1] for k in range(1, len(ct)) if cc[k] and cc[k - 1]])
    ev = [t for k, t in enumerate(ct) if k == 0 or t - ct[k - 1] >= 0.03]
    da = np.diff(ev) if len(ev) > 1 else np.array([])
    return dict(n_step=len(st), step_ms_p50=_pct(st, 50), step_ms_p95=_pct(st, 95), step_ms_max=_pct(st, 100),
                cmd_dt_p50=_pct(dc, 50), cmd_dt_p95=_pct(dc, 95), cmd_dt_max=_pct(dc, 100),
                cmd_all_dt_p50=_pct(da, 50), cmd_all_dt_max=_pct(da, 100))


# ---------------------------------------------------------------- bai thu
def single_tasks(waypoints):
    T = []
    for name, wp in waypoints.items():
        p = wp.get("pose") if isinstance(wp, dict) else wp
        T.append(dict(cat="nav", name=f"nav:{name}", text=f"đi tới {name}",
                      starts={"": (0.0, 0.0, 0.0)}, goal={"": (p[0], p[1])}))
    for text, d, ang in [("đi thẳng 1 mét", 1.0, 0), ("đi thẳng 2 mét", 2.0, 0),
                         ("lùi lại 1 mét", -1.0, 0), ("sang trái nửa mét", 0.5, 0),
                         ("xoay trái 90 độ", 0, 90), ("xoay phải 90 độ", 0, -90),
                         ("quay 1 vòng", 0, 360)]:
        T.append(dict(cat="motion", name=f"motion:{text}", text=text,
                      starts={"": (0.0, 0.0, 0.0)}, dist=d, angle=ang))
    # AN TOAN: dich nam trong tuong / trong vat -> phai dung lai, khong dam
    T += [dict(cat="safety", name="safety:tuong", text="đi thẳng 2 mét",
               starts={"": (-3.6, 2.0, math.pi)}),
          dict(cat="safety", name="safety:thung", text="đi thẳng 1 mét",
               starts={"": (0.0, -0.55, -math.pi / 2)})]
    # NE ROI VE DUONG CU: vat chan giua duong, dich phia sau vat -> vong qua, toi dich
    T += [dict(cat="detour", name="detour:thung_carton", text="đi thẳng 3 mét",
               starts={"": (0.0, 0.0, -math.pi / 2)}, goal={"": (0.0, -3.0)}),
          dict(cat="detour", name="detour:ban_tra", text="đi thẳng 2 mét",
               starts={"": (1.3, 0.3, -math.pi / 2)}, goal={"": (1.3, -1.7)}),
          # tu khoang trong phia nam di len, bac 12 cm chan giua (ban dau dat robot trong
          # "tui" bac + hop do choi + ghe banh, khe 0.25-0.4 m: thu me cung, khong phai vat thap)
          dict(cat="detour", name="detour:vat_thap_12cm", text="đi thẳng 3.5 mét",
               starts={"": (-3.0, -2.6, math.pi / 2)}, goal={"": (-3.0, 0.9)})]
    # VAT CAN DONG: "nguoi" (tru r=0.22 m) di qua lai; nguoi dung lai neu robot o sat
    # truoc mat (lich su) -> robot phai tu ne/doi, khong duoc cham nguoi
    T += [dict(cat="dynamic", name="dyn:nguoi_cat_ngang", text="đi tới bếp",
               starts={"": (-1.5, 0.8, 0.0)}, goal={"": (3.5, 2.2)},
               person=dict(path=[(0.8, -0.4), (0.8, 2.7)], speed=0.4, stop_near=0.8)),
          dict(cat="dynamic", name="dyn:nguoi_doi_dau", text="đi thẳng 4 mét",
               starts={"": (-1.2, 2.0, 0.0)}, goal={"": (2.8, 2.0)},
               person=dict(path=[(3.4, 2.0), (-1.8, 2.0)], speed=0.35, stop_near=0.9)),
          # DAM DONG: 3 nguoi di bo tu do (Social Force, 30 % "mai dien thoai" khong ne
          # robot), toc do ~0.5-1 m/s, trong phong khach — robot di xuyen qua
          dict(cat="dynamic", name="dyn:dam_dong_toi_bep", text="đi tới bếp",
               starts={"": (-3.6, 0.8, 0.0)}, goal={"": (3.5, 2.2)},
               crowd=dict(n=3, region=((-1.5, 3.0), (-1.5, 2.5)), seed=11)),
          dict(cat="dynamic", name="dyn:dam_dong_ra_cua", text="ra cửa",
               starts={"": (3.3, 2.0, math.pi)}, goal={"": (0.0, -3.0)},
               crowd=dict(n=3, region=((-1.5, 3.0), (-2.0, 2.0)), seed=12))]
    return T


def multi_tasks(waypoints):
    a, b = "go2_0", "go2_1"
    def pose(wp):
        return wp.get("pose") if isinstance(wp, dict) else wp
    door, kitchen = pose(waypoints["cửa"]), pose(waypoints["bếp"])
    return [
        dict(cat="multi", name="multi:song_song", text="con một ra cửa, còn con hai vào bếp",
             starts={a: (0.0, 0.0, 0.0), b: (0.0, 1.5, 0.0)},
             goal={a: tuple(door[:2]), b: tuple(kitchen[:2])}),
        dict(cat="multi", name="multi:doi_cho", text="cả hai đổi chỗ",
             starts={a: (-1.2, 0.75, 0.0), b: (1.2, 0.75, math.pi)},
             goal={a: (1.2, 0.75), b: (-1.2, 0.75)}),
        dict(cat="multi", name="multi:cat_cheo", text=None,
             starts={a: (-1.0, -0.2, 0.0), b: (1.0, -0.2, math.pi)},
             goal={a: (1.0, 1.5), b: (-1.0, 1.5)}),
    ]


def office_tasks(waypoints):
    """voice_office.sdf (30 x 20 m): duong dai qua vat SO LE, cua hep, slalom, nguoi, xe day."""
    O = (0.0, 0.0, 0.0)
    def wp(n):
        p = waypoints[n]
        return tuple((p.get("pose") if isinstance(p, dict) else p)[:2])
    return [
        dict(cat="clutter", name="clutter:qua_khoi_so_le", text="đi tới sảnh vào",
             starts={"": O}, goal={"": wp("sảnh vào")}),
        dict(cat="clutter", name="clutter:van_phong", text="đi tới văn phòng",
             starts={"": O}, goal={"": wp("văn phòng")}),
        dict(cat="clutter", name="clutter:slalom_coc", text=None,
             starts={"": (5.7, 0.0, 0.0)}, goal={"": (13.3, 0.0)}),
        dict(cat="clutter", name="clutter:loi_pallet", text="đi tới cuối kho",
             starts={"": O}, goal={"": wp("cuối kho")}),
        dict(cat="clutter", name="clutter:bep_xa", text="đi tới bếp",
             starts={"": O}, goal={"": wp("bếp")}),
        dict(cat="crowd", name="crowd:sanh_8_nguoi", text="đi tới kho hàng",
             starts={"": (-4.0, 0.3, 0.0)}, goal={"": wp("kho hàng")},
             crowd=dict(n=8, region=((-4.5, 4.5), (-4.5, 4.5)), seed=21)),
        dict(cat="crowd", name="crowd:kho_xe_day", text="đi tới cuối kho",
             starts={"": (5.6, 0.0, 0.0)}, goal={"": wp("cuối kho")},
             crowd=dict(n=4, region=((5.5, 14.5), (-9.5, 9.5)), seed=22), carts=True),
        dict(cat="crowd", name="crowd:van_phong_dong", text="đi tới bếp",
             starts={"": O}, goal={"": wp("bếp")},
             crowd=dict(n=6, region=((-14.5, -5.5), (-9.5, 9.5)), seed=23)),
    ]


class Movers:
    """Gom nhieu nguon vat dong (dam dong + xe day) cho Monitor."""

    def __init__(self, items):
        self.items = items                         # [(thread, ban_kinh)]

    def positions_r(self):
        return [(x, y, r) for th, r in self.items for (x, y) in th.positions()]

    def positions(self):
        return [(x, y) for x, y, _ in self.positions_r()]

    def stop(self):
        for th, _ in self.items:
            th.stop()

    def join(self, t=2):
        for th, _ in self.items:
            th.join(t)


def motion_stats(traj, times, goal=None):
    """Do MUOT tren quy dao that (lay mau lai moi 0.5 s de khu dao dong than khi buoc):
      stops  so lan KHUNG: >= 1 s ma than dich chuyen < 0.08 m/s (dung / xoay tai cho)
      stop_s tong thoi gian khung (giua luc bat dau di va luc toi)
      mean_v toc do TB = quang duong (lay mau 0.5 s) / thoi gian
      osc    so lan doi chieu quay (|w| > 0.2 rad/s) - lac qua lac lai"""
    n = min(len(traj), len(times))
    if n < 10:
        return {}
    P, t = np.array(traj[:n], float), np.array(times[:n], float)
    tg = np.arange(t[0], t[-1], 0.5)
    if len(tg) < 4:
        return {}
    x, y = np.interp(tg, t, P[:, 0]), np.interp(tg, t, P[:, 1])
    yaw = np.interp(tg, t, np.unwrap(P[:, 2]))
    v = np.hypot(np.diff(x), np.diff(y)) / 0.5
    w = np.diff(yaw) / 0.5
    mv = np.nonzero(v > 0.08)[0]
    if not len(mv):
        return dict(stops=0, stop_s=0.0, mean_v=0.0, osc=0)
    a, b = mv[0], mv[-1]
    if goal is not None:                                # chi tinh TRUOC khi toi gan dich
        near = np.nonzero(np.hypot(x[:-1] - goal[0], y[:-1] - goal[1]) < 0.5)[0]
        near = near[near > a]
        if len(near):
            b = min(b, near[0])
    still = v[a:b + 1] < 0.08
    stops, run = 0, 0
    for st_ in still:
        run = run + 1 if st_ else 0
        if run == 2:                                    # 2 mau = 1 s
            stops += 1
    sgn = np.sign(w[a:b + 1][np.abs(w[a:b + 1]) > 0.2])
    osc = int((np.diff(sgn) != 0).sum()) if len(sgn) > 1 else 0
    return dict(stops=stops, stop_s=round(float(still.sum() * 0.5), 1),
                mean_v=round(float(v[a:b + 1].mean()), 3), osc=osc)


def run_task(gv, world, task, cfg_name, trial=1, seed=None, ep=None):
    """ep (dict, tuy chon): nhan log tung nhip cua luot (Monitor + thoi gian vong dieu khien) -> episodes.jsonl."""
    reset(gv, task["starts"])
    mover = None
    if task.get("crowd"):                           # dam dong Social Force (giong that)
        from movers import OFFICE_PEOPLE, Crowd, carts
        cc = task["crowd"]
        pool = OFFICE_PEOPLE if WORLD_NAME == "voice_office" else ["person", "person2", "person3"]
        crowd = Crowd(pool[:cc.get("n", 3)], cc["region"], world.path,
                      robots=list(gv.robots.values()), seed=cc.get("seed", 0),
                      distracted=cc.get("distracted", 0.3), world=WORLD_NAME)
        crowd.start()
        items = [(crowd, PERSON_R)]
        if task.get("carts"):
            items += [(c, 0.45) for c in carts(world=WORLD_NAME, robots=list(gv.robots.values()))]
        mover = Movers(items) if len(items) > 1 else crowd
        time.sleep(2.0)
    elif task.get("person"):
        from movers import Mover
        pp = task["person"]
        mover = Mover(pp["path"], pp.get("speed", 0.4), robots=list(gv.robots.values()),
                      stop_near=pp.get("stop_near", 0.0), park=(-4.2, 2.6))
        mover.set(*pp["path"][0])
        time.sleep(1.0)
        mover.start()
    mon = Monitor(gv.robots, world, mover)
    start_pose = {ns: r.map_pose() for ns, r in gv.robots.items()}
    for r in gv.robots.values():
        install_probes(r)
        probe_start(r, seed)
    mon.start()
    t0 = time.time()
    mon.t0 = t0
    if task["text"]:
        gv.process(task["text"])
    else:                                            # cat cheo: lenh toa do truc tiep
        for ns, (gx, gy) in task["goal"].items():
            gv.executor.enqueue([{"tool": "go_to_pose", "args": {
                "x": gx, "y": gy, "name": "diem cheo"}}], only=[ns])
    gv.wait_idle(timeout=300.0)
    dt = time.time() - t0
    time.sleep(0.5)
    mon.running = False
    mon.join()
    mon.close()
    if mover is not None:
        mover.stop()
        mover.join(2)
    rtf = [q[2] for q in mon.rtf]
    sim_dt = (mon.rtf[-1][1] - mon.rtf[0][1]) if len(mon.rtf) > 1 else float("nan")
    wall_dt = (mon.rtf[-1][0] - mon.rtf[0][0]) if len(mon.rtf) > 1 else float("nan")
    rtf_info = dict(rtf_med=_pct(rtf, 50), rtf_p5=_pct(rtf, 5), rtf_min=_pct(rtf, 0),
                    rtf_mean=round(sim_dt / wall_dt, 3) if wall_dt == wall_dt and wall_dt > 0 else "",
                    rtf_low_s=round(wall_dt / max(1, len(rtf) - 1) * sum(1 for q in rtf if q < 0.8), 1)
                    if wall_dt == wall_dt else "")                                    # s co RTF < 0.8 (§5: > 10 s = loi)
    rows = []
    for ns, r in gv.robots.items():
        if ns not in task["starts"]:
            continue
        x, y, yaw = r.map_pose()
        sx, sy, syaw = start_pose[ns]
        collided = mon.min_clear[ns] < 0.0
        row = dict(config=cfg_name, task=task["name"], cat=task["cat"], robot=ns or "go2",
                   time_s=round(dt, 1), travel_m=round(mon.travel(ns), 2),
                   min_clear_m=round(mon.min_clear[ns], 3),
                   min_clear_real_m=round(mon.min_clear_real[ns], 3), collision=int(collided),
                   replans=r.last_stats.get("replans", 0), brakes=r.last_stats.get("brakes", 0),
                   react_s=round(mon.moved_at[ns], 2) if ns in mon.moved_at else "")
        c = r._ctrl
        resp = getattr(c, "resp", None) or getattr(getattr(c, "shield", None), "resp", None)
        row.update(probe_stats(r._gz), **rtf_info, ctrl_class=type(c).__name__ if c is not None else "",
                   trk_mode=getattr(r.tracker, "mode", ""), resp=type(resp).__name__ if resp is not None else "",
                   first_contact_t=(mon.first_contact or {}).get("t", ""),
                   first_static_t=mon.first_static.get(ns, {}).get("t", ""),
                   odom_gap_max=round(mon.gap[ns][0], 2), lidar_gap_max=round(mon.gap[ns][1], 2))
        if ep is not None:
            ep.setdefault("probe", {})[ns or "go2"] = r._gz
        if task["cat"] in ("clutter", "crowd"):
            row.update(motion_stats(mon.traj[ns], mon.times, task["goal"][ns]))
        if task["cat"] in ("nav", "multi", "detour", "dynamic", "clutter", "crowd"):
            gx, gy = task["goal"][ns]
            err = math.hypot(x - gx, y - gy)
            short = world.shortest((sx, sy), (gx, gy))
            ok = err < 0.35 and not collided
            row.update(err_m=round(err, 3), shortest_m=round(short, 2),
                       spl=round(ok * short / max(row["travel_m"], short), 3) if short == short else "",
                       success=int(ok))
        elif task["cat"] == "motion":
            moved = (x - sx) * math.cos(syaw) + (y - sy) * math.sin(syaw)
            if task["name"].startswith("motion:sang"):
                moved = -(x - sx) * math.sin(syaw) + (y - sy) * math.cos(syaw)
            turn = math.degrees(sum(math.atan2(math.sin(b[2] - a[2]), math.cos(b[2] - a[2]))
                                    for a, b in zip(mon.traj[ns], mon.traj[ns][1:])))
            if task["angle"]:
                err = abs(turn - task["angle"])
                ok = err < 10.0
                row.update(err_deg=round(err, 1))
            else:
                err = abs(moved - task["dist"])
                ok = err < 0.10
                row.update(err_m=round(err, 3))
            row["success"] = int(ok and not collided)
        else:                                        # safety: khong duoc dam vao
            row["success"] = int(not collided)
        if mover is not None:
            row["min_person_gap_m"] = round(mon.min_person, 3)
            row["col_info"] = json.dumps(getattr(mon, "col_info", {}))
            if mon.min_person < 0:                   # cham nguoi = that bai
                row["collision"], row["success"] = 1, 0
                row["at_fault"] = getattr(mon, "col_info", {}).get("at_fault", 1)
        if task["cat"] == "multi":
            row["min_robot_gap_m"] = round(mon.min_gap, 3)
            if mon.min_gap < 0:
                row["collision"] = 1
                row["success"] = 0
        rows.append(row)
    if ep is not None:
        ep.update(config=cfg_name, task=task["name"], trial=trial, seed=seed, t=mon.log["t"],
                  robot={ns or "go2": v for ns, v in mon.log["robot"].items()}, people=mon.log["people"],
                  trk={ns or "go2": v for ns, v in mon.log["trk"].items()}, rtf=mon.rtf,
                  first_contact=mon.first_contact, first_static={ns or "go2": v for ns, v in mon.first_static.items()},
                  rows=[{k: v for k, v in r_.items() if k != "col_info"} for r_ in rows])
    trajs = {ns: mon.traj[ns] for ns in task["starts"]}
    if mon.person_traj:
        trajs["person#person"] = mon.person_traj
    for ns in task["starts"]:                        # quy dao DA LAP (lan dau) de ve hinh
        paths = gv.robots[ns].last_stats.get("paths") or []
        if paths:
            trajs[f"{ns}#plan"] = paths[0]
    return rows, trajs


# ---------------------------------------------------------------- bao cao
def summarize(rows):
    keys = sorted({(r["config"], r["cat"]) for r in rows})
    lines = ["| config | loai | n | thanh cong | va cham | sai so TB | SPL | thoi gian TB (s) "
             "| ho min TB (m) | ho min Go2 that (m) | khung (lan) | dung (s) | toc do TB (m/s) | lac huong |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cfg, cat in keys:
        g = [r for r in rows if r["config"] == cfg and r["cat"] == cat]
        n = len(g)
        sr = np.mean([r["success"] for r in g])
        col = np.mean([r["collision"] for r in g])
        errs = [r.get("err_m") for r in g if r.get("err_m") not in (None, "")]
        errd = [r.get("err_deg") for r in g if r.get("err_deg") not in (None, "")]
        err = (f"{np.mean(errs):.3f} m" if errs else "") + (" / " if errs and errd else "") + \
              (f"{np.mean(errd):.1f} do" if errd else "")
        spl = [r["spl"] for r in g if r.get("spl") not in (None, "")]
        spl_s = f"{np.mean(spl):.2f}" if spl else "-"
        lines.append(f"| {cfg} | {cat} | {n} | {sr * 100:.0f} % | {col * 100:.0f} % | {err or '-'} | "
                     f"{spl_s} | {np.mean([r['time_s'] for r in g]):.1f} | "
                     f"{np.mean([r['min_clear_m'] for r in g]):.2f} | "
                     f"{np.mean([r['min_clear_real_m'] for r in g]):.2f} | " + " | ".join(
                         (f"{np.mean([r[k] for r in g if r.get(k) not in (None, '')]):.{d}f}"
                          if any(r.get(k) not in (None, "") for r in g) else "-")
                         for k, d in (("stops", 1), ("stop_s", 1), ("mean_v", 2), ("osc", 1))) + " |")
    return "\n".join(lines)


def plot(trajs, world, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        from matplotlib.transforms import Affine2D
    except Exception:
        return
    CATS = ("nav", "multi", "detour", "dyn", "clutter", "crowd")
    cfgs = sorted({k[0] for k in trajs if k[1].split(":")[0] in CATS})
    if not cfgs:
        return
    fig, axes = plt.subplots(1, len(cfgs), figsize=(5 * len(cfgs), 4.4), squeeze=False)
    for ax, cfg in zip(axes[0], cfgs):
        for _, cx, cy, sx, sy, yaw in world.boxes:
            rect = Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, color="0.55")
            rect.set_transform(Affine2D().rotate_around(cx, cy, yaw) + ax.transData)
            ax.add_patch(rect)
        for (c, task, ns), t in trajs.items():
            if c != cfg or not t or task.split(":")[0] not in CATS:
                continue
            a = np.array(t)
            if ns.endswith("#person"):               # nguoi di qua lai (do)
                ax.plot(a[:, 0], a[:, 1], ":", lw=1.0, color="tab:red", alpha=0.6)
                continue
            if ns.endswith("#plan"):                 # quy dao lap ra (net dut)
                ax.plot(a[:, 0], a[:, 1], "--", lw=0.9, color="0.25", alpha=0.7)
                continue
            ax.plot(a[:, 0], a[:, 1], lw=1.2, alpha=0.85)
            ax.plot(a[-1, 0], a[-1, 1], "k.", ms=4)
        ax.set_title(cfg)
        ax.set_aspect("equal")
        big = WORLD_NAME == "voice_office"
        ax.set_xlim(*((-15.3, 15.3) if big else (-5.3, 5.3)))
        ax.set_ylim(*((-10.3, 10.3) if big else (-4.3, 4.3)))
    fig.tight_layout()
    fig.savefig(path, dpi=140)


def sha_check(sums):
    """[(file, ok)] theo file SHA256SUMS (duong dan tuong doi voi thu muc nay)."""
    import hashlib
    out = []
    for line in open(sums):
        if not line.strip():
            continue
        h, f = line.split(None, 1)
        f = f.strip().lstrip("*")
        p = f if os.path.isabs(f) else os.path.join(HERE, f)
        try:
            ok = hashlib.sha256(open(p, "rb").read()).hexdigest() == h
        except OSError:
            ok = False
        out.append((f, ok))
    return out


def gz_tasks(path, group):
    """Bai tu audit/gen_gazebo_test.py (tasks.json) thuoc file nhom `group` (dang nap trong Gazebo)."""
    d = os.path.dirname(os.path.abspath(path))
    T = [t for t in json.load(open(path)) if group is None or t["group"] == group]
    for t in T:
        tk = dict(t["task"])
        tk["starts"] = {k: tuple(v) for k, v in tk["starts"].items()}
        tk["goal"] = {k: tuple(v) for k, v in tk["goal"].items()}
        if tk.get("crowd"):
            tk["crowd"] = dict(tk["crowd"], region=tuple(tuple(v) for v in tk["crowd"]["region"]))
        tk.update(seed=t["seed"], bounds=tuple(t["bounds"]), truth=os.path.join(d, t["truth_sdf"]),
                  sdf=os.path.join(d, t["sdf"]))
        t["_task"] = tk
    return sorted(T, key=lambda t: t["seed"])


def use_bounds(gv, bounds):
    """Ban do chung theo the gioi (o) dang chay: o cua file 4 o nam ngoai 32 x 22 m cua voice_office."""
    robot_ros.configure_world(*bounds)
    for r in gv.robots.values():
        r.grid, r.depth_grid = robot_ros.SHARED_GRID, robot_ros.SHARED_DEPTH
    if getattr(gv, "viz", None) is not None:
        gv.viz.grid, gv.viz.depth_grid = robot_ros.SHARED_GRID, robot_ros.SHARED_DEPTH


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--suite", choices=["single", "multi", "office", "gztest"], default="single")
    ap.add_argument("--tasks", default="", help="gztest: tasks.json cua audit/gen_gazebo_test.py")
    ap.add_argument("--group", type=int, default=None, help="gztest: so file nhom dang nap (group_<N>.sdf)")
    ap.add_argument("--allow-test", action="store_true", help="gztest: cho seed >= 100000 (CHI dieu phoi vien, TEST)")
    ap.add_argument("--sha-file", default=os.path.join(HERE, "results", "frozen_C1", "SHA256SUMS"),
                    help="kiem sha256 ma truoc MOI luot (ghi vao trials.csv/meta.json)")
    ap.add_argument("--configs", nargs="*", default=None)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--only", default="", help="chi chay bai co ten chua 1 trong cac chuoi (cach nhau dau phay)")
    ap.add_argument("--world", default=WORLD)
    ap.add_argument("--out", default=None, help="thu muc ket qua co dinh (de tiep tuc khi bi ngat)")
    ap.add_argument("--resume", action="store_true",
                    help="bo qua cac luot (lan, cau hinh, bai) da co trong <out>/trials.csv")
    a = ap.parse_args()

    import yaml
    global WORLD_NAME
    from run_sim import detect_world, world_info
    winfo = world_info(detect_world())
    WORLD_NAME = winfo["name"]
    if a.suite in ("office", "gztest") and WORLD_NAME != "voice_office":
        sys.exit("suite office/gztest can sim chay world:=voice_office.sdf hoac file nhom cua gen_gazebo_test")
    if a.suite == "gztest":
        GT = gz_tasks(a.tasks, a.group)
        if not GT:
            sys.exit("khong co bai nao trong --tasks/--group")
        if any(t["seed"] >= 100000 for t in GT) and not a.allow_test:
            sys.exit("CHAN: the gioi TEST (seed >= 100000) can --allow-test (chi dieu phoi vien)")
        if any(1000 <= t["seed"] < 100000 for t in GT):
            sys.exit("CHAN: seed VAL/khac (1000-99999) khong dung cho Gazebo")
    sums = sha_check(a.sha_file) if a.sha_file and os.path.exists(a.sha_file) else []
    bad = [f for f, ok in sums if not ok]
    print(f"[sha] {a.sha_file}: {len(sums) - len(bad)}/{len(sums)} khop" + (f"; LECH: {bad}" if bad else ""), flush=True)
    cfg = load_config(os.path.join(HERE, "config.yaml"))
    with open(os.path.join(HERE, winfo["waypoints"]), encoding="utf-8") as f:
        waypoints = yaml.safe_load(f)
    robots = discover_robots(wait_s=4.0)
    if not robots:
        sys.exit("khong thay robot nao — chay sim truoc")
    world = World(winfo["sdf_path"] if a.world == WORLD else a.world, bounds=winfo["bounds"])
    gv = GoVoiceSim(cfg, robots, no_tts=True)
    if a.suite == "single":
        tasks = single_tasks(waypoints)
        configs = a.configs or ["full", "brake_only", "lidar_only", "no_avoid", "open_loop",
                                "no_people"]
    elif a.suite == "office":
        tasks = office_tasks(waypoints)
        configs = a.configs or ["mppi", "dwa", "pp"]
    elif a.suite == "gztest":
        tasks = [t["_task"] for t in GT]
        configs = a.configs or ["mppi"]
    else:
        tasks = multi_tasks(waypoints)
        configs = a.configs or ["full", "no_coord", "no_avoid"]
    tasks = [t for t in tasks if any(o in t["name"] for o in a.only.split(","))]
    if not tasks:
        sys.exit(f"khong co bai nao khop --only '{a.only}'")
    out = a.out or os.path.join(HERE, "results", f"{a.suite}_{time.strftime('%Y%m%d_%H%M%S')}")
    if not a.resume and os.path.exists(os.path.join(out, "trials.csv")):
        sys.exit(f"CHAN: {out} da co trials.csv (thu muc ra phai rong; --resume de tiep tuc)")
    os.makedirs(out, exist_ok=True)
    meta = dict(argv=sys.argv, start=time.strftime("%F %T"), world=WORLD_NAME, suite=a.suite, configs=configs,
                trials=a.trials, tasks=[t["name"] for t in tasks], sha_file=a.sha_file,
                sha={f: ok for f, ok in sums}, sha_eval_sim=__import__("hashlib").sha256(
                    open(os.path.abspath(__file__), "rb").read()).hexdigest(),
                env={k: os.environ.get(k) for k in ("GZ_PARTITION", "ROS_DOMAIN_ID", "RMW_IMPLEMENTATION",
                                                     "OPENBLAS_NUM_THREADS", "GOVOICE_FAST_SO")})
    with open(os.path.join(out, "meta.json" if not a.resume else f"meta_{time.strftime('%H%M%S')}.json"), "w") as fm:
        json.dump(meta, fm, indent=1, ensure_ascii=False)
    rows, trajs = [], {}
    fields = ["trial", "config", "task", "cat", "robot", "success", "collision", "err_m", "err_deg",
              "spl", "shortest_m", "travel_m", "time_s", "min_clear_m", "min_clear_real_m",
              "min_robot_gap_m", "min_person_gap_m",
              "replans", "brakes", "react_s", "stops", "stop_s", "mean_v", "osc", "at_fault", "col_info",
              # PREREG_TEST §0.4 / §4 (24/11)
              "seed", "ctrl_class", "trk_mode", "resp", "sha_ok", "n_step", "step_ms_p50", "step_ms_p95", "step_ms_max",
              "cmd_dt_p50", "cmd_dt_p95", "cmd_dt_max", "cmd_all_dt_p50", "cmd_all_dt_max",
              "rtf_med", "rtf_p5", "rtf_min", "rtf_mean", "rtf_low_s", "first_contact_t", "first_static_t", "wall_s",
              "odom_gap_max", "lidar_gap_max"]
    csvp = os.path.join(out, "trials.csv")
    done, old_rows = set(), []
    if a.resume and os.path.exists(csvp):
        old_rows = list(csv.DictReader(open(csvp)))
        for r in old_rows:
            r.setdefault("trial", "1")
            r["trial"] = r.get("trial") or "1"
            done.add((int(r["trial"]), r["config"], r["task"]))
        with open(csvp, "w", newline="") as f0:            # viet lai voi header moi (co cot trial)
            w0 = csv.DictWriter(f0, fieldnames=fields, extrasaction="ignore")
            w0.writeheader()
            for r in old_rows:
                w0.writerow(r)
        tj = os.path.join(out, "traj.jsonl")
        if os.path.exists(tj):
            for line in open(tj):
                try:
                    d = json.loads(line)
                    trajs[tuple(d["k"])] = d["v"]
                except Exception:                           # noqa: BLE001
                    pass
        print(f"[resume] da co {len(done)} luot trong {csvp}", flush=True)
    with open(csvp, "a" if (a.resume and old_rows) else "w", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=fields, extrasaction="ignore")
        if not (a.resume and old_rows):
            w.writeheader()
        jobs = []
        if a.suite == "gztest":                      # PREREG_TEST §2: the gioi theo seed tang; cau hinh xao bang Random(seed)
            import random as _random
            for ti, t in enumerate(tasks):
                rng_ = _random.Random(t["seed"])
                for k in range(a.trials):
                    cs = list(configs)
                    rng_.shuffle(cs)
                    jobs += [(k, c, ti, t) for c in cs]
        else:
            jobs = [(k, c, ti, t) for k in range(a.trials) for c in configs for ti, t in enumerate(tasks)]
        cur_world = None
        for k, c, ti, t in jobs:
            if c == "open_loop" and t["cat"] != "motion":
                continue                     # open_loop chi khac o lenh chuyen dong
            if c == "brake_only" and t["cat"] not in ("detour", "safety"):
                continue                     # brake_only chi khac khi di thang gap vat
            if c == "no_people" and t["cat"] != "dynamic":
                continue                     # no_people chi khac khi co nguoi
            if (k + 1, c, t["name"]) in done:
                continue                     # da chay (tiep tuc sau khi bi ngat)
            wld = world
            if a.suite == "gztest":
                if cur_world is None or cur_world[0] != t["seed"]:
                    use_bounds(gv, t["bounds"])
                    cur_world = (t["seed"], World(t["truth"], bounds=t["bounds"]))
                wld = cur_world[1]
            seed = [int(t.get("seed", ti)), k + 1, 11]   # nhu fastsim.run_episode: nhieu MPPI theo (the gioi, lan)
            sha_ok = int(all(ok for _, ok in sha_check(a.sha_file))) if sums else ""
            apply_config(gv, config_of(c))
            ep, tw = {}, time.time()
            rs, tr = run_task(gv, wld, t, c, trial=k + 1, seed=seed, ep=ep)
            for r in rs:
                r.update(trial=k + 1, seed=seed[0], sha_ok=sha_ok, wall_s=round(time.time() - tw, 1))
                w.writerow(r)
                fcsv.flush()
                rows.append(r)
                print(f"[{k + 1}/{a.trials}] {c:10} {t['name']:26} {r['robot']:6} "
                      f"ok={r['success']} col={r['collision']} "
                      f"err={r.get('err_m', r.get('err_deg', ''))} t={r['time_s']}s "
                      f"ctrl={r.get('ctrl_class')}/{r.get('trk_mode')}/{r.get('resp') or '-'} "
                      f"step95={r.get('step_ms_p95')}ms cmd50/95={r.get('cmd_dt_p50')}/{r.get('cmd_dt_p95')}s "
                      f"rtf={r.get('rtf_med')} sha={sha_ok}", flush=True)
            with open(os.path.join(out, "episodes.jsonl"), "a") as fe:
                fe.write(json.dumps(ep) + "\n")
            with open(os.path.join(out, "traj.jsonl"), "a") as fj:
                for ns, traj in tr.items():
                    trajs[(c, t["name"], ns or "go2")] = traj
                    fj.write(json.dumps({"k": [c, t["name"], ns or "go2"], "v": traj}) + "\n")
    num = ("success", "collision", "err_m", "err_deg", "spl", "time_s", "min_clear_m",
           "min_clear_real_m", "stops", "stop_s", "mean_v", "osc", "travel_m")
    for r in old_rows:                                     # dong cu doc tu CSV la chuoi -> so
        for k_ in num:
            if r.get(k_) not in (None, ""):
                try:
                    r[k_] = float(r[k_])
                except ValueError:
                    pass
    rows = old_rows + rows
    summary = summarize(rows)
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write(f"# eval_sim {a.suite} — {time.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"{len(rows)} dong, {a.trials} lan lap, the gioi {os.path.basename(a.world)}\n\n"
                + summary + "\n")
    with open(os.path.join(out, "traj.json"), "w") as f:
        json.dump({"|".join(k): v for k, v in trajs.items()}, f)
    plot(trajs, world, os.path.join(out, "traj.png"))
    print("\n" + summary + f"\n\n-> {out}", flush=True)
    gv.executor.stop_all()
    gv.executor.shutdown()
    time.sleep(0.5)
    from robot_ros import RosBus
    RosBus.get().shutdown()          # dong DDS dung cach (xem RosBus.shutdown)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
