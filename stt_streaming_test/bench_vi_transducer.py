#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_vi_transducer.py — do latency + kiem chinh xac cua zipformer-transducer tieng Viet
(sherpa-onnx, offline 30M int8) — SO SANH voi PhoWhisper 1.8s.

Chay:  python3 bench_vi_transducer.py
"""
import time
import wave
import glob
import os
import numpy as np
import sherpa_onnx

MODEL = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
EXTRA_WAVS = ["../test_voice.wav", "../test_loa.wav"]   # audio that cua du an (22050Hz)


def read_wav_16k(path):
    """Doc wav -> float32 mono 16kHz [-1,1]. Tu resample neu can."""
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        n = w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, 16000)
        x = resample_poly(x, 16000 // g, sr // g)
    return x.astype(np.float32), 16000, len(x) / 16000.0


def build():
    t0 = time.time()
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{MODEL}/encoder.int8.onnx",
        decoder=f"{MODEL}/decoder.onnx",
        joiner=f"{MODEL}/joiner.int8.onnx",
        tokens=f"{MODEL}/tokens.txt",
        num_threads=4,
        decoding_method="greedy_search",
    )
    return rec, (time.time() - t0) * 1000


def transcribe(rec, samples, sr):
    s = rec.create_stream()
    s.accept_waveform(sr, samples)
    rec.decode_stream(s)
    return s.result.text


def bench_file(rec, path, runs=5):
    samples, sr, dur = read_wav_16k(path)
    # warmup
    txt = transcribe(rec, samples, sr)
    # do nhieu lan lay median
    ts = []
    for _ in range(runs):
        t0 = time.time()
        transcribe(rec, samples, sr)
        ts.append((time.time() - t0) * 1000)
    ts.sort()
    med = ts[len(ts) // 2]
    rtf = (med / 1000) / dur
    return txt, dur, med, rtf


def main():
    print("=" * 70)
    print(" BENCHMARK: Zipformer-Transducer tieng Viet (30M int8, CPU) vs PhoWhisper")
    print("=" * 70)
    rec, load_ms = build()
    print(f"[load] nap model: {load_ms:.0f} ms (chi 1 lan luc khoi dong)\n")

    files = sorted(glob.glob(f"{MODEL}/test_wavs/*.wav"))
    files += [p for p in EXTRA_WAVS if os.path.exists(p)]

    print(f"{'File':<26}{'Dai(s)':>8}{'Latency':>11}{'RTF':>8}   Ket qua")
    print("-" * 70)
    all_ms = []
    for f in files:
        txt, dur, ms, rtf = bench_file(rec, f)
        all_ms.append((dur, ms))
        name = os.path.basename(f)
        print(f"{name:<26}{dur:>7.1f}s{ms:>9.0f}ms{rtf:>8.3f}   {txt[:34]}")

    print("-" * 70)
    # uoc luong cho cau lenh ngan dien hinh ~2s
    print("\n>>> SO SANH (cau lenh robot dien hinh ~2-3s):")
    print(f"    PhoWhisper-small GPU (hien tai):   ~1800 ms")
    short = [ms for dur, ms in all_ms if dur <= 4.0]
    if short:
        avg_short = sum(short) / len(short)
        print(f"    Zipformer-VI 30M int8 (CPU laptop): ~{avg_short:.0f} ms")
        print(f"    => NHANH HON ~{1800/avg_short:.0f}x (va day moi la CPU, chua dung GPU!)")
    print("\n(Ghi chu: offline transducer — voi cau ngan latency da rat thap;")
    print(" ban streaming se cho ra chu NGAY trong luc noi, con thap hon nua.)")


if __name__ == "__main__":
    main()
