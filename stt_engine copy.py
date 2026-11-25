#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stt_engine.py — "TAI" cua GoVoice (v2 — chong nghe sai + chong bia chuyen).

3 nang cap so voi v1:
  1. initial_prompt: "mom" tu vung lenh robot cho Whisper
     -> nghieng ve nghe dung cac tu lenh ("xoay vong" thay vi "xay vong").
  2. Loc HALLUCINATION: Whisper hay "bia" van thoi su khi thu phai tieng on/TV.
     Loc bang no_speech_prob + avg_logprob cua tung segment.
  3. beam_size doc tu config (de 5 tren GPU: chinh xac hon, van nhanh).
"""

import os
import time
import numpy as np

# Tu vung "mom" cho model — chinh la cac lenh robot hay dung
DEFAULT_PROMPT = ("\u0110\u00e2y l\u00e0 l\u1ec7nh \u0111i\u1ec1u khi\u1ec3n robot: "
                  "\u0111i th\u1eb3ng, \u0111i l\u00f9i, sang tr\u00e1i, sang ph\u1ea3i, "
                  "xoay tr\u00e1i, xoay ph\u1ea3i, xoay v\u00f2ng, d\u1eebng l\u1ea1i, "
                  "ch\u00e0o, nh\u1ea3y, n\u1eb1m xu\u1ed1ng, \u0111\u1ee9ng d\u1eady, "
                  "th\u1ea3 tim, v\u01b0\u01a1n vai, \u0111i t\u1edbi c\u00e1i c\u1eeda, "
                  "ra ch\u1ed7 c\u00e1i b\u00e0n, m\u00e9t, gi\u00e2y, \u0111\u1ed9, v\u00f2ng.")


class STT:
    def __init__(self, model="models/phowhisper-small-ct2", fallback_model="small",
                 device="cuda", compute_type="int8_float16",
                 language="vi", beam_size=5, initial_prompt=None):
        from faster_whisper import WhisperModel
        self.language = language
        self.beam_size = beam_size
        self.initial_prompt = initial_prompt if initial_prompt is not None else DEFAULT_PROMPT
        try:
            if not os.path.isdir(model):
                raise FileNotFoundError
            self.model = WhisperModel(model, device=device, compute_type=compute_type)
            print(f"[stt] da nap model local: {model} ({device}/{compute_type}, beam={beam_size})")
        except Exception:
            print(f"[stt] khong thay '{model}', dung fallback '{fallback_model}' "
                  f"(se tu tai ve lan dau)")
            self.model = WhisperModel(fallback_model, device=device,
                                      compute_type=compute_type)

    def transcribe(self, audio_f32_16k: np.ndarray) -> tuple:
        """audio float32 mono 16kHz -> (text, ms). Text rong neu nghi la bia/nhieu."""
        t0 = time.time()
        segments, _info = self.model.transcribe(
            audio_f32_16k,
            language=self.language,
            beam_size=self.beam_size,
            condition_on_previous_text=False,
            initial_prompt=self.initial_prompt,
            vad_filter=False,
        )
        kept = []
        for s in segments:
            # ---- LOC HALLUCINATION ----
            # no_speech_prob cao = doan nay nhieu kha nang KHONG phai tieng noi
            # avg_logprob qua thap = model tu biet minh doan bua
            if getattr(s, "no_speech_prob", 0.0) > 0.6:
                continue
            if getattr(s, "avg_logprob", 0.0) < -1.0:
                continue
            txt = s.text.strip()
            if txt:
                kept.append(txt)
        text = " ".join(kept).strip()
        return text, round((time.time() - t0) * 1000.0, 1)


if __name__ == "__main__":
    import sys
    import wave
    if len(sys.argv) < 2:
        print("Cach dung: python3 stt_engine.py <file.wav 16kHz mono>")
        sys.exit(0)
    with wave.open(sys.argv[1], "rb") as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1, \
            "Can WAV 16kHz mono"
        audio = np.frombuffer(wf.readframes(wf.getnframes()),
                              dtype=np.int16).astype(np.float32) / 32768.0
    stt = STT()
    text, ms = stt.transcribe(audio)
    print(f"({ms} ms) -> {text}")
