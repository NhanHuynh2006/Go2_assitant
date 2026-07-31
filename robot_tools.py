#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tools.py — "TAY CHAN" cua GoVoice: thuc thi hanh dong len robot Go2.

2 che do:
  dry_run=True  (laptop): chi IN lenh ra man hinh -> test an toan khong can robot.
  dry_run=False (Jetson): goi SportClient that qua DDS (eth0 noi bo robot).

Tool ho tro:
  move(vx, vy, vyaw, duration)  — di chuyen co gioi han an toan
  action(name)                  — hello/dance1/dance2/stretch/heart/standup/standdown
  stop()                        — dung khan cap
  go_to(location)               — gui goal Nav2 toi waypoint da dat ten (waypoints.yaml)
"""

import os
import time
import math
import threading

# Cac dong tac SportClient DA XAC MINH tren Go2 cua ban.
# (Co y KHONG dua HandStand/WalkUpright vao voice — nguy hiem khi kich hoat bang loi noi)
ACTION_MAP = {
    "hello": "Hello",
    "dance1": "Dance1",
    "dance2": "Dance2",
    "stretch": "Stretch",
    "heart": "Heart",
    "standup": "StandUp",
    "standdown": "StandDown",
    "balance": "BalanceStand",
}

# ---- Dong tac ACROBATIC (dung 2 chan / bat nhay) ----
# RUI RO: robot de MAT THANG BANG/NGA. Can KHONG GIAN TRONG + nen phang, va robot
# phai o che do AI sport (advanced) thi SDK moi thuc thi. Firmware KHONG cho cat
# giua chung -> 'dung lai' se doi lam xong dong tac moi dung han.
_ACRO_ONESHOT = {                       # 1-phat, khong tham so
    "frontjump": "FrontJump",           # bat VE PHIA TRUOC
    "frontpounce": "FrontPounce",       # chom/vo ve phia truoc
}
_ACRO_TOGGLE = {                        # nhan flag bool: bat True -> giu -> ha xuong
    "walkupright": ("WalkUpright", 4.0),  # dung/di bang 2 chan SAU (nhu nguoi)
    "handstand":   ("HandStand", 4.0),    # trong chuoi: dung bang 2 chan TRUOC
}


class RobotTools:
    def __init__(self, dry_run=True, iface="eth0", waypoints_file=None,
                 max_vx=0.6, max_vy=0.4, max_vyaw=1.0, max_duration=6.0,
                 max_step_m=0.5, motion_mode=None):
        self.dry_run = dry_run
        self.iface = iface
        self.limits = (max_vx, max_vy, max_vyaw, max_duration)
        self.max_step_m = float(max_step_m)   # moi lenh di toi da bao nhieu MET (chong dung)
        # Che do dong co: "ai" = mo khoa acrobatic (WalkUpright/HandStand/FrontJump...);
        # "normal" = co dien; None = khong tu chuyen (giu nguyen mode robot dang o).
        self.motion_mode = motion_mode
        # Co huy khan cap: emergency_stop() bat co -> vong move() dang chay
        # thoat trong ~0.1s thay vi di het duration. enqueue() lenh moi se xoa co.
        self.abort = threading.Event()
        self.client = None
        self.waypoints = self._load_waypoints(waypoints_file)
        if not dry_run:
            self._init_sdk()

    # ---------------- SDK that (chay tren Jetson) ----------------
    def _init_sdk(self):
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.go2.sport.sport_client import SportClient
        ChannelFactoryInitialize(0, self.iface)
        self.client = SportClient()
        self.client.SetTimeout(10.0)
        self.client.Init()
        print(f"[robot] SportClient OK (iface={self.iface})")
        # TU CHUYEN che do dong co (khoi phai bat trong app dien thoai moi lan).
        # 'ai' -> mo khoa dong tac acrobatic (dung 2 chan/trong chuoi/bat toi...).
        if self.motion_mode:
            try:
                from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import \
                    MotionSwitcherClient
                msc = MotionSwitcherClient()
                msc.SetTimeout(5.0)
                msc.Init()
                ret = msc.SelectMode(self.motion_mode)
                print(f"[robot] chuyen che do dong co -> '{self.motion_mode}' (ret={ret}) "
                      f"— cho ~3s controller san sang...")
                time.sleep(3.0)
            except Exception as e:
                print(f"[robot] ⚠️  khong chuyen duoc che do '{self.motion_mode}' "
                      f"(acrobatic co the loi): {e}")

    def _load_waypoints(self, path):
        if not path or not os.path.exists(path):
            return {}
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {str(k).lower(): v for k, v in data.items()}
        except Exception as e:
            print(f"[robot] khong doc duoc waypoints: {e}")
            return {}

    # ---------------- API chinh: execute 1 action dict ----------------
    def execute(self, act: dict) -> str:
        tool = (act.get("tool") or "").lower()
        args = act.get("args") or {}
        try:
            if tool == "move":
                return self.move(
                    float(args.get("vx", 0.0)), float(args.get("vy", 0.0)),
                    float(args.get("vyaw", 0.0)), float(args.get("duration", 2.0)))
            if tool == "action":
                return self.action(str(args.get("name", "")))
            if tool == "stop":
                return self.stop()
            if tool == "go_to":
                return self.go_to(str(args.get("location", "")))
            return f"[robot] tool la: {tool} (bo qua)"
        except Exception as e:
            return f"[robot] LOI khi chay {tool}: {e}"

    # ---------------- Cac tool ----------------
    def move(self, vx=0.0, vy=0.0, vyaw=0.0, duration=2.0) -> str:
        mvx, mvy, mvyaw, mdur = self.limits
        vx = max(-mvx, min(mvx, vx))
        vy = max(-mvy, min(mvy, vy))
        vyaw = max(-mvyaw, min(mvyaw, vyaw))
        duration = max(0.1, min(mdur, duration))
        # CHAN KHOANG CACH: quang duong = toc do x thoi gian. Neu vuot max_step_m
        # (vd 0.5m) thi RUT NGAN thoi gian lai -> robot chi di dung ~50cm roi dung,
        # du LLM/reflex co xuat toc do/thoi gian lon the nao (so dung do vat).
        speed = math.hypot(vx, vy)
        if speed > 1e-6 and speed * duration > self.max_step_m:
            duration = self.max_step_m / speed
        if self.dry_run:
            dist = speed * duration
            return (f"[DRY] Move vx={vx:.2f} vy={vy:.2f} vyaw={vyaw:.2f} "
                    f"trong {duration:.1f}s (~{dist*100:.0f}cm)")
        # Lenh van toc phai gui lien tuc ~10Hz trong suot thoi gian di.
        # Moi vong kiem tra co abort -> "dung lai" cat duoc giua chung trong ~0.1s
        # (truoc day StopMove cua emergency bi chinh vong nay gui Move de len).
        if self.abort.is_set():
            return "Da huy (emergency)"
        t_end = time.time() + duration
        while time.time() < t_end:
            if self.abort.is_set():
                self.client.StopMove()
                return "🛑 Da dung giua chung (emergency)"
            self.client.Move(vx, vy, vyaw)
            time.sleep(0.1)
        self.client.StopMove()
        return f"Da di xong ({duration:.1f}s)"

    def stop(self) -> str:
        if self.dry_run:
            return "[DRY] StopMove + BalanceStand"
        try:
            self.client.StopMove()
            self.client.BalanceStand()
        except Exception:
            pass
        return "Da dung."

    def action(self, name: str) -> str:
        key = name.lower().strip()
        known = key in ACTION_MAP or key in _ACRO_TOGGLE or key in _ACRO_ONESHOT
        if not known:
            return f"[robot] khong biet dong tac '{name}'"
        # dong tac dong goi / acrobatic khong the cat giua chung -> chan neu dang emergency
        if self.abort.is_set() and key not in ("standup", "balance"):
            return "Da huy (emergency)"

        # --- ACROBATIC dung 2 chan (WalkUpright/HandStand): bat -> giu -> ha an toan ---
        if key in _ACRO_TOGGLE:
            method, hold = _ACRO_TOGGLE[key]
            if self.dry_run:
                return f"[DRY] {method}(True) giu {hold:.0f}s roi ha xuong (RecoveryStand)"
            try:
                self.client.BalanceStand(); time.sleep(0.5)   # dung vung truoc da
                getattr(self.client, method)(True)            # dung len 2 chan
                time.sleep(hold)
                getattr(self.client, method)(False); time.sleep(0.3)
                self.client.RecoveryStand()                   # ve tu the an toan
            except Exception as e:
                try:
                    self.client.RecoveryStand()
                except Exception:
                    pass
                return f"[robot] loi {method} (robot co o che do AI sport khong?): {e}"
            return f"Da lam: {method}"

        # --- ACROBATIC 1-phat (FrontJump/FrontPounce) ---
        if key in _ACRO_ONESHOT:
            method = _ACRO_ONESHOT[key]
            if self.dry_run:
                return f"[DRY] SportClient.{method}()"
            try:
                getattr(self.client, method)()
            except Exception as e:
                return f"[robot] loi {method} (robot co o che do AI sport khong?): {e}"
            return f"Da lam: {method}"

        # --- dong tac thuong ---
        method = ACTION_MAP[key]
        if self.dry_run:
            return f"[DRY] SportClient.{method}()"
        getattr(self.client, method)()
        # Dung day xong nen ve trang thai can bang de di duoc ngay
        if key == "standup":
            time.sleep(1.0)
            self.client.BalanceStand()
        return f"Da lam: {method}"

    def go_to(self, location: str) -> str:
        """Gui goal toi Nav2 (/goal_pose). Can he Nav2 + map dang chay (xem HUONG_DAN.md)."""
        if self.abort.is_set():
            return "Da huy (emergency)"
        loc = location.lower().strip()
        wp = self.waypoints.get(loc)
        if not wp:
            known = ", ".join(self.waypoints.keys()) or "(chua co waypoint nao)"
            return f"[robot] khong tim thay diem '{location}'. Cac diem da luu: {known}"
        x, y, yaw = float(wp[0]), float(wp[1]), float(wp[2]) if len(wp) > 2 else 0.0
        if self.dry_run:
            return f"[DRY] Nav2 goal -> '{loc}' (x={x}, y={y}, yaw={yaw})"
        return self._send_nav2_goal(x, y, yaw, loc)

    def _send_nav2_goal(self, x, y, yaw, name) -> str:
        try:
            import rclpy
            from geometry_msgs.msg import PoseStamped
            if not rclpy.ok():
                rclpy.init()
            node = rclpy.create_node("govoice_goal")
            pub = node.create_publisher(PoseStamped, "/goal_pose", 10)
            msg = PoseStamped()
            msg.header.frame_id = "map"
            msg.header.stamp = node.get_clock().now().to_msg()
            msg.pose.position.x = x
            msg.pose.position.y = y
            msg.pose.orientation.z = math.sin(yaw / 2.0)
            msg.pose.orientation.w = math.cos(yaw / 2.0)
            # publish vai lan cho chac (latch kieu thu cong)
            for _ in range(5):
                pub.publish(msg)
                rclpy.spin_once(node, timeout_sec=0.1)
            node.destroy_node()
            return f"Da gui goal Nav2 toi '{name}'"
        except Exception as e:
            return f"[robot] go_to can ROS2+Nav2 dang chay. Loi: {e}"


if __name__ == "__main__":
    r = RobotTools(dry_run=True, waypoints_file="waypoints.yaml")
    print(r.execute({"tool": "move", "args": {"vx": 0.4, "duration": 2}}))
    print(r.execute({"tool": "action", "args": {"name": "hello"}}))
    print(r.execute({"tool": "go_to", "args": {"location": "cua"}}))
    print(r.execute({"tool": "stop", "args": {}}))
