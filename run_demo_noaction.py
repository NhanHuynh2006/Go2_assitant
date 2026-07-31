#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_demo_noaction.py — CHAY DEMO: chi NGHE -> NGHI -> NOI. KHONG hanh dong.

>>> ROBOT KHONG NHUC NHICH <<< An toan tuyet doi de test giao tiep giong noi.
Khac ban Jetson demo o cho: day la ban day du (async + safety van nap san
de test logic), chi khac la robot chay o che do GIA (dry-run) nen moi "hanh dong"
chi IN ra man hinh chu khong dieu khien chan robot.

CHAY:
  python3 run_demo_noaction.py              # go phim (test logic, khong can mic)
  python3 run_demo_noaction.py --voice      # noi qua mic
  python3 run_demo_noaction.py --voice --mic-robot   # noi qua MIC ROBOT (UDP bridge)

Mac dinh dung config.yaml. Robot LUON o che do gia du config ghi gi.
"""

import argparse
import sys

from assistant_realtime import GoVoiceRT, load_config


def main():
    ap = argparse.ArgumentParser(description="GoVoice DEMO — chi noi, khong hanh dong")
    ap.add_argument("--voice", action="store_true", help="noi qua mic (mac dinh: go phim)")
    ap.add_argument("--mic-robot", action="store_true",
                    help="dung mic ROBOT qua UDP (chay go2_audio_bridge.py truoc)")
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()

    cfg = load_config(a.config)
    # ÉP robot ve che do GIA (du config ghi dry_run: false) — KHONG hanh dong
    cfg.setdefault("robot", {})["dry_run"] = True
    if a.mic_robot:
        cfg.setdefault("audio", {})["backend"] = "udp"

    print("\U0001F512 CHE DO DEMO — robot KHONG hanh dong, chi nghe & noi.\n")
    gv = GoVoiceRT(cfg, force_real=False)   # force_real=False -> luon gia
    try:
        if a.voice:
            gv.run_voice()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.shutdown()
        print("\nTam biet!")


if __name__ == "__main__":
    main()
