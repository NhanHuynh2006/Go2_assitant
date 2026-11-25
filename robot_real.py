#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_real.py — "TAY CHAN" cho Go2 THAT, co NE VAT CAN (LiDAR L1 + D435i).

Cung thuat toan voi sim (robot_ros.RosRobotTools: ban do, A*, ne vong, phanh, ...),
chi khac cho doc/ghi:

  di chuyen   /go2/cmd_vel  -> go2_hardware_bridge.py --allow-motion -> SportClient.Move
              (bridge tu kep van toc, tu StopMove sau 0.5 s khong co lenh, nhuong remote)
  vi tri      /go2/odom     (rt/utlidar/robot_odom, bridge da nhan --odom-scale 1.19)
  LiDAR       /go2/lidar/points (L1, frame 'utlidar', gan NGUOC nghieng 15 do)
              + LOC THAN: L1 tren dau thay 2 chan truoc (BODY_BOX do tren robot 11/9)
  IMU         /go2/imu/data
  D435i       realsense-ros: <cam>/depth/image_rect_raw (16UC1, mm) + camera_info
              gan theo gia do: d435i_x / d435i_z / d435i_pitch (config.yaml -> real:)
  dong tac    SportClient truc tiep (Hello, Dance1, StandDown...) qua robot_tools.RobotTools

CHUA chay tren robot that (2026-11-20): da kiem tren sim bang cach tro topic. Lan dau
chay that: dat robot o cho thoang, cam remote (L2+B = phanh cung), bat dau bang
"đi thẳng 1 mét", roi moi thu ne vat can.
"""

import math
import time

import numpy as np

from nav_local import lookahead, plan
from robot_ros import SOFT, RosRobotTools, _clamp, _wrap

# base_link <- utlidar tren Go2 that (go2_localization/scan_match.py, residual 0.00000 m)
R_BASE_LIDAR = np.array([[0.52611, -0.81014, 0.25862],
                         [-0.83867, -0.54464, 0.0],
                         [0.14085, -0.21690, -0.96598]])
T_BASE_LIDAR = np.array([0.2822, 0.0, 0.0])
# than + chan robot trong base_link: ((x0,x1),(y0,y1),(z0,z1)), cung nguon
BODY_BOX = ((-0.45, 0.45), (-0.28, 0.28), (-0.50, 0.15))


class RealRobotTools(RosRobotTools):
    def __init__(self, cfg_real=None, sport=None, **kw):
        c = dict(cfg_real or {})
        ns = c.get("ns", "go2")
        cam = c.get("camera_ns", "/camera/camera")
        kw.setdefault("ns", ns)
        kw.setdefault("odom_topic", c.get("odom_topic", f"/{ns}/odom"))
        kw.setdefault("cloud_topic", c.get("cloud_topic", f"/{ns}/lidar/points"))
        kw.setdefault("imu_topic", c.get("imu_topic", f"/{ns}/imu/data"))
        kw.setdefault("depth_topic", c.get("depth_topic", f"{cam}/depth/image_rect_raw"))
        # robot that chieu cao than ~0.32 m khi dung (go2-motion-control-facts)
        kw.setdefault("base_height", float(c.get("base_height", 0.32)))
        # toc do that dat ~80 % lenh; ne vat can chay cham cho chac
        kw.setdefault("goto_speed", float(c.get("goto_speed", 0.3)))
        super().__init__(**kw)
        self.body_box = BODY_BOX
        x, z, pitch = (float(c.get(k, d)) for k, d in
                       (("d435i_x", 0.30), ("d435i_z", 0.05), ("d435i_pitch", 0.35)))
        cp, sp = math.cos(pitch), math.sin(pitch)
        # frame "camera huong toi" (x toi, y trai, z len) -> base_link: xoay pitch quanh y
        self._cam_mount = (np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]), np.array([x, 0.0, z]))
        self.sport = sport                   # robot_tools.RobotTools(dry_run=False) | None
        self.iface = c.get("iface", "eth0")

    # --- extrinsics: TF neu co, khong thi so do tay (robot that thuong khong co TF day du)
    def _lidar_to_base(self, frame):
        if self._lidar_tf is None:
            try:
                self._lidar_tf = self._tf_to_base(frame)
            except Exception:
                self._lidar_tf = (R_BASE_LIDAR, T_BASE_LIDAR)
        return self._lidar_tf

    def _on_depth(self, msg):
        # realsense-ros publish frame quang hoc; _depth_points da cho diem theo frame
        # "huong toi" (x toi) tu tia pixel, nen chi can gia do -> base_link.
        if self._cam_tf is None:
            self._cam_tf = self._cam_mount
        super()._on_depth(msg)

    # --- dong tac: SportClient that (body_pose cua CHAMP khong ton tai tren Go2)
    def action(self, name):
        if self.sport is None:
            return f"[{self.label}] (khong co SportClient) bo qua dong tac '{name}'"
        self._halt()
        return self.sport.action(name)

    # --- DOI CHUNG: bo ne vat can CO SAN cua Unitree (dich vu "obstacles_avoid" trong firmware,
    # ma nguon khong cong bo; SDK chi co client: unitree_sdk2py/go2/obstacles_avoid). Tai lieu
    # Unitree: ne dua tren radar (L1), CHI ne phia truoc.
    #   controller="unitree"       lai thang ve dich, firmware tu ne
    #   controller="unitree_path"  bam duong A* cua GoVoice, ne cuc bo do firmware (so cong bang
    #                              voi MPPI / PRISM: cung duong toan cuc, chi khac bo ne)
    def _oa(self):
        if getattr(self, "_oa_client", None) is None:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.obstacles_avoid.obstacles_avoid_client import ObstaclesAvoidClient
            if self.sport is None:                      # RobotTools da khoi tao kenh DDS neu co
                ChannelFactoryInitialize(0, self.iface or "eth0")
            c = ObstaclesAvoidClient()
            c.SetTimeout(3.0)
            c.Init()
            self._oa_client = c
        return self._oa_client

    def _navigate(self, gx, gy, tol=0.2, timeout=None, line=None):
        if self.controller not in ("unitree", "unitree_path"):
            return super()._navigate(gx, gy, tol=tol, timeout=timeout, line=line)
        oa = self._oa()
        for _ in range(20):
            if oa.SwitchGet()[1]:
                break
            oa.SwitchSet(True)
            time.sleep(0.1)
        oa.UseRemoteCommandFromApi(True)
        st = self.last_stats
        x, y, _ = self.map_pose()
        deadline = time.monotonic() + (timeout or 40.0 + 4.0 * math.hypot(gx - x, gy - y) / 0.1)
        path, t_plan, last = None, 0.0, (x, y)
        try:
            while not self._cancel.is_set():
                now = time.monotonic()
                if now > deadline:
                    return False, "het gio"
                x, y, yaw = self.map_pose()
                if not st.setdefault("traj", []) or now - st["traj"][-1][0] > 0.25:
                    st["traj"].append((now, x, y, yaw))
                st["travel_m"] = st.get("travel_m", 0.0) + math.hypot(x - last[0], y - last[1])
                last = (x, y)
                if math.hypot(gx - x, gy - y) < tol:
                    return True, "ok"
                tx, ty = gx, gy
                if self.controller == "unitree_path":
                    if path is None or now - t_plan > 2.0:
                        path, _ = plan(self.grid, (x, y), (gx, gy),
                                       layers=[self.depth_grid] if self.use_depth else [],
                                       lethal=0.32, soft=SOFT, line=line)
                        t_plan = now
                        if path:
                            self._publish_path(path)
                    if path:
                        (tx, ty), _ = lookahead(path, x, y, 0.6)
                err = _wrap(math.atan2(ty - y, tx - x) - yaw)
                wz = _clamp(1.5 * err, self.goto_turn)
                vx = 0.0 if abs(err) > 1.0 else min(self.goto_speed, 0.35) * math.cos(err)
                oa.Move(float(vx), 0.0, float(wz))      # firmware Unitree tu sua lenh de ne
                time.sleep(0.1)
            return False, "bi dung"
        finally:
            oa.Move(0.0, 0.0, 0.0)
            oa.UseRemoteCommandFromApi(False)

    def stop(self):
        out = super().stop()
        if self.sport is not None:
            try:
                self.sport.client.StopMove()
            except Exception:
                pass
        return out
