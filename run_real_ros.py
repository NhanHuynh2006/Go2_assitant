#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_real_ros.py — GoVoice tren Go2 THAT, DU chuc nang nhu sim:
noi chuyen, di/xoay vong kin, NE VAT CAN (L1 + D435i, vong qua roi ve duong cu),
di toi cho da day ("lưu chỗ này là bếp"), do vat theo mau (neu co objects_real.yaml),
quan he khong gian, hoi lai khi mo ho, SafetyGuard + EMERGENCY.

Khac run_real_robot.py (ban cu, SportClient truc tiep, KHONG ne vat can): ban nay lai
qua go2_hardware_bridge (/go2/cmd_vel) va doc cam bien qua ROS 2.

TREN JETSON (xem start_real.sh — no bat het cho ban):
  1) python3 go2_hardware_bridge.py --allow-motion        # (go2_bringup/scripts)
  2) ros2 launch realsense2_camera rs_launch.py ...        # D435i
  3) python3 run_real_ros.py --voice --mic-robot

An toan: remote trong tay (L2+B = phanh cung), noi "dừng lại" bat ky luc nao.
Bridge tu dung robot sau 0.5 s khong co lenh (tat chuong trinh = robot dung).
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import os
import sys

from run_sim import GoVoiceSim, HERE, load_config  # noqa: F401  (dat ROS_* truoc rclpy)


def main():
    ap = argparse.ArgumentParser(description="GoVoice — Go2 that, co ne vat can")
    ap.add_argument("--voice", action="store_true")
    ap.add_argument("--both", action="store_true", help="NOI va GO cung luc")
    ap.add_argument("--mic-robot", action="store_true")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--no-sport", action="store_true",
                    help="khong khoi tao SportClient (chi di chuyen, khong dong tac)")
    ap.add_argument("--yes", action="store_true", help="bo qua checklist an toan")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    a = ap.parse_args()

    if not a.yes:
        print("\n  CHE DO THAT: remote trong tay (L2+B)? cho thoang? pin >= 50%? "
              "bridge --allow-motion dang chay?\n  Go 'co' de tiep tuc: ", end="")
        if input().strip().lower() not in ("co", "yes", "y", "ok"):
            sys.exit("Da huy.")

    cfg = load_config(a.config)
    if a.mic_robot:
        cfg.setdefault("audio", {})["backend"] = "udp"
    real = cfg.get("real", {}) or {}

    sport = None
    if not a.no_sport:
        try:
            from robot_tools import RobotTools
            r = cfg.get("robot", {})
            sport = RobotTools(dry_run=False, iface=r.get("iface", "eth0"))
        except Exception as e:                                # noqa: BLE001
            print(f"[real] khong khoi tao duoc SportClient ({e}) -> chi di chuyen, khong dong tac")

    from robot_real import RealRobotTools
    gv = GoVoiceSim(cfg, [real.get("ns", "go2")], no_tts=a.no_tts, section="real",
                    backend=RealRobotTools, backend_kw={"cfg_real": real, "sport": sport})
    try:
        if a.both:
            gv.run_both()
        elif a.voice:
            gv.run_voice()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.stop_all()
        gv.executor.shutdown()
        print("\nDa dung robot.")
        from robot_ros import RosBus
        RosBus.get().shutdown()
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
