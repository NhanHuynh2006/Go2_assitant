#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_commands.py — sinh audio CAU LENH ROBOT bang Piper roi cho zipformer-transducer
tieng Viet nhan dang lai. Kiem tra model co hieu dung tu vung lenh khong + do latency.
(TTS->STT la phep thu tong hop; giong Piper sach hon mic that, nhung du de kiem tu vung.)
"""
import io
import time
import wave
import numpy as np
import sherpa_onnx
from piper import PiperVoice

MODEL = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
VOICE = "../models/piper/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"

COMMANDS = [
    "đi thẳng ba mét",
    "lùi lại hai mét",
    "xoay phải chín mươi độ",
    "quay trái hai vòng",
    "sang trái hai bước",
    "đi tới cái bàn rồi chào mọi người",
    "nằm xuống nghỉ đi",
    "dừng lại ngay",
    "đi thẳng năm mét rồi xoay phải sau đó về chỗ sạc",
]


def synth(voice, text):
    """Piper -> float32 mono 16k (resample tu sample_rate cua Piper)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav(text, wf)
    buf.seek(0)
    with wave.open(buf, "rb") as wf:
        sr = wf.getframerate()
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if sr != 16000:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, 16000)
        x = resample_poly(x, 16000 // g, sr // g)
    return x.astype(np.float32), len(x) / 16000.0


def main():
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{MODEL}/encoder.int8.onnx", decoder=f"{MODEL}/decoder.onnx",
        joiner=f"{MODEL}/joiner.int8.onnx", tokens=f"{MODEL}/tokens.txt",
        num_threads=4, decoding_method="greedy_search")
    voice = PiperVoice.load(VOICE)

    print("=" * 78)
    print(" KIEM TRA TU VUNG LENH: Piper (sinh audio) -> Zipformer-VI transducer (nhan dang)")
    print("=" * 78)
    print(f"{'Cau noi (goc)':<44}{'Latency':>9}   Nhan dang lai")
    print("-" * 78)
    lat = []
    for cmd in COMMANDS:
        samples, dur = synth(voice, cmd)
        s = rec.create_stream()
        s.accept_waveform(16000, samples)
        t0 = time.time()
        rec.decode_stream(s)
        ms = (time.time() - t0) * 1000
        lat.append(ms)
        print(f"{cmd:<44}{ms:>7.0f}ms   {s.result.text}")
    print("-" * 78)
    print(f"Latency trung binh: {sum(lat)/len(lat):.0f} ms (CPU) — vs PhoWhisper ~1800ms")


if __name__ == "__main__":
    main()
