#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_real_robot.py — CHAY THAT: robot HANH DONG theo lenh (async + safety day du).

>>> ROBOT SE DI CHUYEN THAT <<< Chi chay tren JETSON (co DDS eth0 toi robot).

An toan da tich hop:
  - SafetyGuard: clamp van toc, chan dong tac nguy hiem, tu dung day truoc khi di
  - EMERGENCY: noi "dung lai" bat ky luc nao = xoa hang doi + dung ngay
  - Async: robot vua lam vua nghe lenh ke

TRUOC KHI CHAY (BAT BUOC):
  [ ] TAT app Unitree (WebRTC/DDS chi 1 ket noi)
  [ ] Cam remote san — L2+B la phanh cung phan cung
  [ ] Khong gian thoang >= 2x2m
  [ ] Pin >= 50%
  [ ] export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds

CHAY:
  python3 run_real_robot.py --voice              # noi qua mic may
  python3 run_real_robot.py --voice --mic-robot  # noi qua MIC ROBOT (chay bridge truoc)
  python3 run_real_robot.py                       # go phim (test tay truoc cho chac)
"""

import argparse
import sys

from assistant_realtime import GoVoiceRT, load_config


CHECKLIST = """
============================================================
  \u26a0\ufe0f  CHE DO THAT — ROBOT SE DI CHUYEN
============================================================
  Kiem tra truoc khi tiep tuc:
    1. App Unitree DA TAT?
    2. Remote trong tay (L2+B = phanh cung)?
    3. Khong gian thoang >= 2x2m?
    4. Pin >= 50%?
    5. CYCLONEDDS_HOME da export?

  Go 'co' de tiep tuc, Enter de huy: """


def main():
    ap = argparse.ArgumentParser(description="GoVoice — chay THAT tren robot")
    ap.add_argument("--voice", action="store_true", help="noi qua mic (mac dinh: go phim)")
    ap.add_argument("--mic-robot", action="store_true",
                    help="dung mic ROBOT qua UDP (chay go2_audio_bridge.py truoc)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--yes", action="store_true", help="bo qua xac nhan checklist")
    a = ap.parse_args()

    # Xac nhan an toan
    if not a.yes:
        try:
            ans = input(CHECKLIST).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nDa huy.")
            sys.exit(0)
        if ans not in ("co", "co.", "yes", "y", "ok"):
            print("Da huy — chua xac nhan an toan.")
            sys.exit(0)

    cfg = load_config(a.config)
    if a.mic_robot:
        cfg.setdefault("audio", {})["backend"] = "udp"

    print("\n\U0001F415 CHE DO THAT — robot dieu khien that. Noi 'dung lai' = phanh khan.\n")
    gv = GoVoiceRT(cfg, force_real=True)   # force_real=True -> dieu khien that
    try:
        if a.voice:
            gv.run_voice()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.emergency_stop()   # dung robot khi thoat
        gv.executor.shutdown()
        print("\nDa dung robot. Tam biet!")


if __name__ == "__main__":
    main()
