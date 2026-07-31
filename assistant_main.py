#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant_main.py — CHUONG TRINH CHINH cua GoVoice.

Kien truc 2 tang:
  [audio] -> STT -> TANG 1 Reflex (~0ms)  -> robot lam ngay
                 -> TANG 2 LLM (~1-2s)    -> ke hoach nhieu buoc -> robot lam
  + TTS dap loi. Moi cau deu LOG do tre tung khau ra CSV (so lieu viet bao).

CACH CHAY:
  python3 assistant_main.py --mode text     # go lenh, KHONG can mic (test logic)
  python3 assistant_main.py --mode voice    # noi qua mic (local hoac robot, theo config)
  them --real de dieu khien robot THAT (mac dinh theo config robot.dry_run)
"""

import csv
import os
import sys
import time
import argparse
import threading

import yaml

from reflex_matcher import ReflexMatcher, norm
from robot_tools import RobotTools
from llm_planner import LLMPlanner

EMERGENCY_WORDS = ("dung lai", "dung ngay", "stop", "ngung")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class GoVoice:
    def __init__(self, cfg, force_real=False, no_tts=False):
        self.cfg = cfg
        r = cfg.get("robot", {})
        dry = False if force_real else bool(r.get("dry_run", True))
        self.robot = RobotTools(
            dry_run=dry, iface=r.get("iface", "eth0"),
            waypoints_file=r.get("waypoints_file"),
            max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
            max_vyaw=r.get("max_vyaw", 1.0),
            max_duration=r.get("max_duration", 6.0))
        self.reflex = ReflexMatcher()
        l = cfg.get("llm", {})
        self.llm = LLMPlanner(endpoint=l.get("endpoint", "http://127.0.0.1:8080"),
                              grammar_path=os.path.join(
                                  os.path.dirname(os.path.abspath(__file__)),
                                  "grammar.gbnf"),
                              temperature=l.get("temperature", 0.2),
                              n_predict=l.get("n_predict", 200),
                              timeout_s=l.get("timeout_s", 60),
                              use_fewshot=l.get("fewshot", True))
        t = cfg.get("tts", {})
        if no_tts:
            t = dict(t); t["enabled"] = False
        from tts_engine import TTS
        self.tts = TTS(t.get("voice"), enabled=t.get("enabled", True),
                       output=t.get("output", "local"),
                       wav_dir=t.get("wav_dir", "tts_out"))
        self.mute = threading.Event()   # bat khi Go dang noi -> mic bo qua (chong tu nghe minh)
        self.csv_path = cfg.get("logging", {}).get("csv", "latency_log.csv")
        self._init_csv()
        if not self.llm.health():
            print("\u26a0\ufe0f  llama-server CHUA chay -> cau phuc tap se loi. "
                  "(Lenh don gian van chay qua Reflex.) Xem HUONG_DAN.md A1.")

    def _init_csv(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    ["ts", "path", "stt_ms", "brain_ms", "exec_ms",
                     "total_ms", "text"])

    def _log(self, path, stt_ms, brain_ms, exec_ms, total_ms, text):
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [time.strftime("%H:%M:%S"), path, stt_ms, brain_ms,
                 round(exec_ms, 1), round(total_ms, 1), text])

    def _speak_async(self, say: str):
        """Noi o thread rieng -> robot HANH DONG NGAY trong luc noi.
        Dong thoi bat mute de mic khong nghe nham giong cua chinh Go."""
        if not say:
            return

        def _worker():
            self.mute.set()
            try:
                self.tts.speak(say)
            finally:
                time.sleep(0.25)        # duoi am thanh con vang
                self.mute.clear()

        threading.Thread(target=_worker, daemon=True).start()

    # ---------------- xu ly 1 cau lenh ----------------
    def process(self, text: str, stt_ms: float = 0.0):
        t0 = time.time()
        text = text.strip()
        if not text:
            return
        # 0) PHANH KHAN CAP truoc moi thu
        if any(w in norm(text) for w in EMERGENCY_WORDS):
            print(self.robot.stop())
            self._speak_async("D\u1eebng li\u1ec1n!")
            self._log("emergency", stt_ms, 0, 0,
                      (time.time() - t0) * 1000 + stt_ms, text)
            return

        # 1) TANG 1 — Reflex
        r = self.reflex.match(text)
        path = "reflex"
        brain_ms = 0.0
        if r is None:
            # 2) TANG 2 — LLM
            path = "llm"
            r = self.llm.plan(text)
            brain_ms = r.get("_ms", 0.0)
            tps = r.get("_tps", 0)
            print(f"\U0001F9E0 [LLM {brain_ms:.0f}ms, {tps} tok/s]")
        else:
            print(f"\u26A1 [Reflex: {r.get('intent')}]")

        say = r.get("say", "")
        actions = r.get("actions", []) or []
        if say:
            print(f"\U0001F436 G\u00f4: {say}")

        # 3) NOI SONG SONG voi HANH DONG (realtime: khong doi noi xong moi lam)
        self._speak_async(say)
        t_exec = time.time()
        for act in actions:
            print("   ->", self.robot.execute(act))
        exec_ms = (time.time() - t_exec) * 1000
        total = (time.time() - t0) * 1000 + stt_ms
        print(f"\u23F1\ufe0f  STT {stt_ms:.0f} | n\u00e3o {brain_ms:.0f} | "
              f"l\u00e0m {exec_ms:.0f} | T\u1ed4NG {total:.0f} ms  [{path}]\n")
        self._log(path, stt_ms, brain_ms, exec_ms, total, text)

    # ---------------- 2 che do chay ----------------
    def run_text(self):
        print("=" * 60)
        print(" GoVoice — TEXT MODE (go 'thoat' de dung)")
        print("=" * 60)
        while True:
            try:
                text = input("B\u1ea1n: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if norm(text) in ("thoat", "exit", "quit"):
                break
            self.process(text)

    def run_voice(self):
        from audio_io import get_listener
        from stt_engine import STT
        s = self.cfg.get("stt", {})
        stt = STT(model=s.get("model", "small"),
                  fallback_model=s.get("fallback_model", "small"),
                  device=s.get("device", "cuda"),
                  compute_type=s.get("compute_type", "int8_float16"),
                  language=s.get("language", "vi"),
                  beam_size=s.get("beam_size", 5),
                  initial_prompt=s.get("initial_prompt"))
        listener = get_listener(self.cfg.get("audio", {}), mute=self.mute)
        print("=" * 60)
        print(" GoVoice — VOICE MODE (Ctrl+C de dung)")
        print("=" * 60)
        for audio in listener.listen():
            text, stt_ms = stt.transcribe(audio)
            if not text:
                continue
            print(f"\U0001F5E3\ufe0f  Nghe \u0111\u01b0\u1ee3c: {text}")
            self.process(text, stt_ms=stt_ms)


def main():
    p = argparse.ArgumentParser(description="GoVoice — tro ly giong noi cho Go2")
    p.add_argument("--mode", choices=["text", "voice"], default="text")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--real", action="store_true",
                   help="dieu khien robot THAT (ghi de dry_run)")
    p.add_argument("--no-tts", action="store_true", help="tat tieng noi dap")
    a = p.parse_args()
    cfg = load_config(a.config)
    gv = GoVoice(cfg, force_real=a.real, no_tts=a.no_tts)
    if a.mode == "voice":
        gv.run_voice()
    else:
        gv.run_text()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTam biet!")
        sys.exit(0)
