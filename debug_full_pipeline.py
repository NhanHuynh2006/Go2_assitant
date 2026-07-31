#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_full_pipeline.py — giong HET run_voice() nhung IN RA MOI utterance
(ke ca RONG) de biet VAD co cat cau khong VA STT co tra chu khong.

Chay:  python3 debug_full_pipeline.py
"""
import sys
import yaml
from audio_io import get_listener
from stt_transducer import STTTransducer

cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
s = cfg.get("stt", {})
stt = STTTransducer(
    s.get("transducer_model"),
    hotwords_file=s.get("hotwords_file"),
    hotwords_score=s.get("hotwords_score", 3.0),
    num_threads=s.get("num_threads", 4),
)
audio_cfg = dict(cfg.get("audio", {}))
audio_cfg["min_utterance_s"] = 0.05     # TAM thoi bo loc cau ngan de xem HET moi doan VAD cat ra
print(f"[cfg] audio={audio_cfg}")
listener = get_listener(audio_cfg, mute=None)
print("=" * 60)
print(" DEBUG PIPELINE — noi vai cau, xem KET QUA THAT (ke ca rong)")
print(" Ctrl+C de dung")
print("=" * 60)
n = 0
for audio in listener.listen():
    n += 1
    dur = len(audio) / 16000.0
    text, ms = stt.transcribe(audio)
    print(f"[utt#{n}] dai={dur:.2f}s  latency={ms:.0f}ms  text={text!r}")
