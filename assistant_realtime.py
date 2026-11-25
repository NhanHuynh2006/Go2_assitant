#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant_realtime.py — GoVoice REALTIME (async + hanh dong that + safety).

Khac assistant_main.py o cho: hanh dong chay BAT DONG BO (thread rieng) nen
vong chinh VUA cho robot lam VUA nghe + STT + nghi cau ke (ky thuat SmolVLA).
Kem SafetyGuard kiem duyet moi lenh + EMERGENCY uu tien tuyet doi.

Luong 1 cau:
  audio -> STT -> [EMERGENCY?] -> Reflex/LLM -> guard -> async queue -> robot lam
  (TTS noi song song voi luc robot dang lam)

CHAY:
  # Test tren laptop (robot gia, in [DRY]):
  python3 assistant_realtime.py --mode voice
  # Tren Jetson dieu khien robot THAT:
  python3 assistant_realtime.py --mode voice --real
  # Go phim thay vi noi (test logic):
  python3 assistant_realtime.py --mode text --real
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import threading
import time

import yaml

from reflex_matcher import ReflexMatcher, norm
from combo_matcher import ComboMatcher, DEFAULT_LOCATIONS
from robot_tools import RobotTools
from llm_planner import LLMPlanner
from safety_guard import SafetyGuard
from async_executor import AsyncExecutor

EMERGENCY_WORDS = ("dung lai", "dung ngay", "stop", "ngung", "khan cap")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class GoVoiceRT:
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
        self.guard = SafetyGuard(
            max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
            max_vyaw=r.get("max_vyaw", 1.0),
            max_duration=r.get("max_duration", 6.0),
            require_stand_before_move=r.get("require_stand_before_move", True))
        self.executor = AsyncExecutor(self.robot, self.guard, on_event=print)

        self.reflex = ReflexMatcher()
        # TANG 1.5: che combo theo tu noi -> giai tung ve bang luat (xem combo_matcher.py).
        # Dia diem go_to = waypoint tren map (neu co) gop voi danh sach mac dinh.
        import os
        wp = []
        try:
            wpf = r.get("waypoints_file")
            if wpf and os.path.exists(wpf):
                with open(wpf, encoding="utf-8") as _f:
                    wp = list((yaml.safe_load(_f) or {}).keys())
        except Exception:
            wp = []
        self.combo = ComboMatcher(locations=list(DEFAULT_LOCATIONS) + wp)
        l = cfg.get("llm", {})
        import os
        self.llm = LLMPlanner(
            endpoint=l.get("endpoint", "http://127.0.0.1:8080"),
            grammar_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "grammar.gbnf"),
            temperature=l.get("temperature", 0.2),
            n_predict=l.get("n_predict", 200),
            timeout_s=l.get("timeout_s", 60),
            use_fewshot=l.get("fewshot", False))

        t = cfg.get("tts", {})
        if no_tts:
            t = dict(t); t["enabled"] = False
        from tts_engine import TTS
        self.tts = TTS(t.get("voice"), enabled=t.get("enabled", True),
                       output=t.get("output", "local"),
                       wav_dir=t.get("wav_dir", "tts_out"),
                       piper_bin=t.get("piper_bin"),
                       robot_port=t.get("speaker_port", 17891))
        self.mute = threading.Event()

        if not self.llm.health():
            print("\u26a0\ufe0f  llama-server chua chay -> cau phuc tap se loi "
                  "(lenh don van chay qua Reflex).")
        print(f"[robot] che do: {'THAT (--real)' if not dry else 'GIA (dry-run)'}")

    def _speak_async(self, say):
        if not say or getattr(self, "tts_muted", False):    # Studio: tat loa
            return

        def _w():
            self.mute.set()
            try:
                self.tts.speak(say)
            finally:
                time.sleep(0.25)
                self.mute.clear()
        threading.Thread(target=_w, daemon=True).start()

    def process(self, text, stt_ms=0.0):
        t0 = time.time()
        text = (text or "").strip()
        if not text:
            return

        # 0) EMERGENCY — uu tien tuyet doi, chen ngang moi thu dang chay
        if any(w in norm(text) for w in EMERGENCY_WORDS):
            self.executor.emergency_stop()
            self._speak_async("D\u1eebng li\u1ec1n!")
            return

        # Dinh tuyen: 1.5) Combo (che + luat) -> 1) Reflex don -> 2) LLM
        r = self.combo.match(text) or self.combo.resolve_goto(text)
        if r is None and not self.combo.needs_llm(text):   # cau chi do vat cu the -> LLM
            r = self.reflex.match(text)
        from_llm = r is None
        if r is None:
            try:
                r = self.llm.plan(text)
                tag = f"LLM {r.get('_ms', 0):.0f}ms"
            except Exception:
                r = {"say": "M\u00ecnh ch\u01b0a k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c b\u1ed9 n\u00e3o, b\u1ea1n th\u1eed l\u1ea1i nh\u00e9?",
                     "actions": []}
                tag = "LLM loi (server?)"
        else:
            tag = f"Reflex:{r.get('intent')}"

        say = r.get("say", "")
        actions = r.get("actions", []) or []
        # 2b) KIEM CHUNG symbolic: bo action LLM "bia" (chi loc nhanh LLM)
        if from_llm and actions:
            from plan_verifier import verify_plan
            actions, dropped = verify_plan(text, actions)
            for d in dropped:
                print(f"   \U0001F9F9 verifier b\u1ecf: {d}")
        print(f"\U0001F436 G\u00f4: {say}   [{tag}]")

        # 3) NOI song song + DAY hanh dong vao hang doi async (khong chan)
        self._speak_async(say)
        self.executor.enqueue(actions)
        plan_ms = (time.time() - t0) * 1000 + stt_ms
        print(f"   \u23F1\ufe0f  STT {stt_ms:.0f} + len ke hoach {plan_ms - stt_ms:.0f} "
              f"= {plan_ms:.0f}ms (robot dang lam o thread rieng)")

    # ---------- 2 che do ----------
    def _submit(self, text, stt_ms=0.0):
        """Mot cua duy nhat cho ca loi noi lan chu go: hai luong khong chen nhau
        (process giu trang thai hoi lai 'con nao', 'cai nao'). RLock vi process
        cua run_sim tu goi lai chinh no."""
        lock = self.__dict__.setdefault("_proc_lock", threading.RLock())
        with lock:
            self.process(text, stt_ms=stt_ms)

    def run_text(self, banner=True):
        if banner:
            print("=" * 60)
            print(" GoVoice REALTIME — TEXT (go 'thoat' de dung)")
            print("=" * 60)
        while True:
            try:
                text = input("B\u1ea1n: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if norm(text) in ("thoat", "exit", "quit"):
                break
            self._submit(text)

    def run_both(self):
        """NOI va GO cung luc: mic chay o luong rieng, ban phim o luong chinh.
        Lenh nao toi truoc lam truoc; 'dung lai' (noi hay go) luon phanh ngay."""
        def voice():
            try:
                self.run_voice(banner=False)
            except Exception as e:                         # noqa: BLE001
                print(f"\n[voice] mic/STT loi ({e!r}) -> chi con go phim")
        threading.Thread(target=voice, daemon=True, name="voice").start()
        print("=" * 60)
        print(" GoVoice — NOI hoac GO deu duoc (go 'thoat' de dung)")
        print(" 'dung lai' (noi hay go) = phanh khan cap")
        print("=" * 60)
        self.run_text(banner=False)

    # Tu cua LENH, so CO DAU khi cau co dau (STT luon co dau): "tôi" khong phai "tới",
    # "bạn" khong phai "bàn". Cau tu mic khong chua tu nao -> coi la tieng nen.
    CMD_WORDS = ("đi", "tới", "đến", "ra", "lại", "về", "vào", "qua", "xoay", "quay", "rẽ",
                 "lùi", "tiến", "thẳng", "dừng", "đứng", "ngồi", "nằm", "chào", "nhảy", "múa",
                 "vươn", "theo", "lưu", "nhớ", "trái", "phải", "trước", "sau", "cạnh", "mét",
                 "độ", "giây", "con một", "con hai", "cả hai", "ở đâu", "có gì", "bắt tay",
                 "đổi chỗ", "stop", "gô", "robot ơi", "chó ơi")

    def _looks_like_command(self, text):
        import re
        low = text.lower()
        words = list(self.CMD_WORDS)
        for k in getattr(self, "place_names", {}).values():
            words.append(str(k).lower())
        cat = getattr(self, "catalog", None)
        if cat is not None:
            words += [it["label"].lower() for it in cat.items]
        if any(ord(c) > 127 for c in text):              # co dau -> so co dau
            return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low) for w in words)
        t = norm(text)                                   # khong dau -> so bo dau
        return any(re.search(rf"\b{re.escape(norm(w))}\b", t) for w in words)

    def _gate(self, text):
        """Loc tieng nen (TV, nguoi noi chuyen) truoc khi thanh lenh.
        - 'dung lai' luon qua (an toan).
        - Cau > max_words tu: gan nhu chac chan la tieng nen -> bo.
        - Neu co wake_words (vd ["go oi", "cho oi"]): chi nhan cau CO tu do, va cat no di."""
        s = self.cfg.get("stt", {}) or {}
        t = norm(text)
        if any(w in t for w in EMERGENCY_WORDS):
            return text
        if len(t.split()) > int(s.get("max_words", 25)):
            print("   \U0001F507 bo qua: cau qua dai, nghi la tieng nen")
            return None
        wakes = [norm(w) for w in (s.get("wake_words") or [])]
        if not wakes and s.get("command_gate", True) and not self._looks_like_command(text):
            print("   \U0001F507 bo qua: khong giong lenh (tieng TV/nguoi noi chuyen?)")
            return None
        if wakes:
            hit = next((w for w in wakes if w in t), None)
            if hit is None and time.time() < getattr(self, "_wake_until", 0.0):
                self._wake_until = 0.0                    # vua goi "gô ơi" -> cau nay la lenh
                return text
            if hit is None:
                print("   \U0001F507 bo qua: khong goi ten (wake word)")
                return None
            words, ww = text.split(), hit.split()
            for i in range(len(words) - len(ww) + 1):    # cat tu danh thuc khoi cau goc
                if norm(" ".join(words[i:i + len(ww)])).strip(",.!?") == hit:
                    text = " ".join(words[:i] + words[i + len(ww):]).strip(" ,.!?")
                    break
            if not text:
                self._wake_until = time.time() + 8.0      # chi goi ten -> cho lenh 8 s
                self._speak_async("Dạ?")
                return None
        return text

    def run_voice(self, banner=True):
        from audio_io import get_listener
        s = self.cfg.get("stt", {})
        # backend "transducer" (MOI, NHANH ~15-150ms): zipformer-VI qua sherpa-onnx + hotwords.
        # backend mac dinh "whisper": PhoWhisper qua faster-whisper (~1.8s).
        if (s.get("backend") or "whisper").lower() == "transducer":
            from stt_transducer import STTTransducer
            stt = STTTransducer(
                s.get("transducer_model",
                      "stt_streaming_test/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"),
                hotwords_file=s.get("hotwords_file"),
                hotwords_score=s.get("hotwords_score", 3.0),
                num_threads=s.get("num_threads", 4),
                use_gpu=(s.get("device", "cpu") == "cuda"))
        else:
            from stt_engine import STT
            stt = STT(model=s.get("model", "small"),
                      fallback_model=s.get("fallback_model", "small"),
                      device=s.get("device", "cuda"),
                      compute_type=s.get("compute_type", "int8_float16"),
                      language=s.get("language", "vi"),
                      beam_size=s.get("beam_size", 5),
                      initial_prompt=s.get("initial_prompt"))
        listener = get_listener(self.cfg.get("audio", {}), mute=self.mute)
        if banner:
            print("=" * 60)
            print(" GoVoice REALTIME — VOICE (Ctrl+C de dung)")
            print(" Noi 'dung lai' bat ky luc nao = phanh khan cap")
            print("=" * 60)
        else:
            print("\n[voice] mic san sang — cu noi, hoac go phim ben duoi")
        for audio in listener.listen():
            if not getattr(self, "voice_enabled", True):     # Studio: tat mic
                continue
            text, stt_ms = stt.transcribe(audio)
            if not text:
                continue
            print(f"\n\U0001F5E3\ufe0f  Nghe: {text}")
            text = self._gate(text)
            if text:
                self._submit(text, stt_ms=stt_ms)


def main():
    p = argparse.ArgumentParser(description="GoVoice REALTIME (async+safety)")
    p.add_argument("--mode", choices=["text", "voice", "both"], default="text")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--real", action="store_true", help="dieu khien robot THAT")
    p.add_argument("--no-tts", action="store_true")
    a = p.parse_args()
    cfg = load_config(a.config)
    gv = GoVoiceRT(cfg, force_real=a.real, no_tts=a.no_tts)
    try:
        if a.mode == "voice":
            gv.run_voice()
        elif a.mode == "both":
            gv.run_both()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.emergency_stop()
        gv.executor.shutdown()
        print("\nTam biet!")


if __name__ == "__main__":
    main()
