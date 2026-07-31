#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo_voice_only.py — GoVoice ban DEMO cho con cho (Jetson): CHI NGHE -> NGHI -> NOI.

>>> HANH DONG BI KHOA CUNG <<<
Robot KHONG di chuyen, KHONG chay SportClient. An toan tuyet doi de test giong noi
trong khi model con dang hoan thien. Khi nao ban san sang cho robot lam that thi
chuyen sang assistant_main.py --real (sau khi fine-tune dat do chinh xac cao).

Luong: mic -> STT (PhoWhisper) -> [Reflex hoac LLM] -> chi IN lenh du dinh + NOI ra loa.

CHAY tren Jetson:
  python3 demo_voice_only.py                 # mic + loa cua may dang chay
  python3 demo_voice_only.py --mic-robot     # mic ROBOT qua go2_audio_bridge.py (UDP)
"""

import argparse
import time

import yaml

from reflex_matcher import ReflexMatcher, norm
from llm_planner import LLMPlanner
from stt_engine import STT
from tts_engine import TTS
from audio_io import get_listener


def describe(actions):
    """Doi list action thanh cau MO TA (KHONG chay) de in cho de hieu."""
    if not actions:
        return "(chi tra loi, khong co hanh dong)"
    parts = []
    for a in actions:
        tool = a.get("tool")
        args = a.get("args", {})
        if tool == "move":
            parts.append(f"move(vx={args.get('vx')}, vy={args.get('vy')}, "
                         f"vyaw={args.get('vyaw')}, {args.get('duration')}s)")
        elif tool == "action":
            parts.append(f"action({args.get('name')})")
        elif tool == "go_to":
            parts.append(f"go_to({args.get('location')})")
        elif tool == "stop":
            parts.append("stop()")
    return " -> ".join(parts)


def main():
    ap = argparse.ArgumentParser(description="GoVoice DEMO chi noi (khong hanh dong)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--mic-robot", action="store_true",
                    help="dung mic ROBOT qua UDP (chay go2_audio_bridge.py truoc)")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))

    # --- nap cac khoi (KHONG nap RobotTools — khoa hanh dong tu goc) ---
    reflex = ReflexMatcher()
    l = cfg.get("llm", {})
    llm = LLMPlanner(endpoint=l.get("endpoint", "http://127.0.0.1:8080"),
                     grammar_path="grammar.gbnf",
                     temperature=l.get("temperature", 0.2),
                     n_predict=l.get("n_predict", 200),
                     use_fewshot=l.get("fewshot", False))
    s = cfg.get("stt", {})
    stt = STT(model=s.get("model", "small"),
              fallback_model=s.get("fallback_model", "small"),
              device=s.get("device", "cpu"),
              compute_type=s.get("compute_type", "int8"),
              language=s.get("language", "vi"),
              beam_size=s.get("beam_size", 5),
              initial_prompt=s.get("initial_prompt"))
    t = cfg.get("tts", {})
    tts = TTS(t.get("voice"), enabled=t.get("enabled", True), output="local")

    # mic: robot (udp) hay may (local)
    acfg = dict(cfg.get("audio", {}))
    if args.mic_robot:
        acfg["backend"] = "udp"
    listener = get_listener(acfg)

    if not llm.health():
        print("\u26a0\ufe0f  llama-server chua chay (cau phuc tap se loi, lenh don van chay).")

    print("=" * 60)
    print(" GoVoice DEMO — CHI NGHE & NOI (hanh dong DA KHOA)")
    print("=" * 60)

    for audio in listener.listen():
        text, stt_ms = stt.transcribe(audio)
        if not text:
            continue
        print(f"\n\U0001F5E3\ufe0f  Nghe: {text}  ({stt_ms:.0f}ms)")
        print("   \U0001F914 dang nghi...", flush=True)

        # phanh khan cap chi de... noi (khong dung gi ca vi dang khoa)
        if any(w in norm(text) for w in ("dung lai", "stop", "ngung")):
            print("   [se la STOP — nhung dang khoa hanh dong]")

        t_brain = time.time()
        r = reflex.match(text)
        if r is None:
            r = llm.plan(text)
            tag = f"LLM {r.get('_ms', 0):.0f}ms"
        else:
            tag = f"Reflex:{r.get('intent')}"
        brain_ms = (time.time() - t_brain) * 1000

        say = r.get("say", "")
        actions = r.get("actions", []) or []
        print(f"   [{tag}]")
        print(f"\U0001F436 G\u00f4: {say}")
        print(f"   \U0001F512 (du dinh, KHONG chay): {describe(actions)}")
        print(f"   \u23F1\ufe0f  STT {stt_ms:.0f} + n\u00e3o {brain_ms:.0f} = {stt_ms + brain_ms:.0f}ms "
              f"(ch\u01b0a t\u00ednh n\u00f3i)")
        tts.speak(say)        # <-- chi NOI ra loa, khong dieu khien robot


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTam biet!")