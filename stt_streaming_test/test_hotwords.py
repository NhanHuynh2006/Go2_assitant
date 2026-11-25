#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_hotwords.py — so sanh Zipformer-VI CO va KHONG hotwords (moi tu vung lenh).
Muc tieu: xem contextual biasing co sua duoc cac lenh quan trong (dung lai, quay trai...) khong.
"""
import io
import time
import os
import wave
import numpy as np
import sherpa_onnx
from piper import PiperVoice

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(BASE, "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
VOICE = os.path.join(BASE, "..", "models/piper/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx")
HOTWORDS = os.path.join(BASE, "hotwords.txt")

COMMANDS = [
    "đi thẳng ba mét", "lùi lại hai mét", "xoay phải chín mươi độ",
    "quay trái hai vòng", "sang trái hai bước", "nằm xuống nghỉ đi",
    "dừng lại ngay", "đứng dậy đi", "đi tới cái bàn rồi chào mọi người",
]


def mk(hot=False):
    kw = dict(
        encoder=f"{MODEL}/encoder.int8.onnx", decoder=f"{MODEL}/decoder.onnx",
        joiner=f"{MODEL}/joiner.int8.onnx", tokens=f"{MODEL}/tokens.txt",
        num_threads=4)
    if hot:
        kw.update(decoding_method="modified_beam_search",
                  modeling_unit="bpe", bpe_vocab=f"{MODEL}/bpe.vocab",
                  hotwords_file=HOTWORDS, hotwords_score=2.0)
    else:
        kw.update(decoding_method="greedy_search")
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kw)


def synth(voice, text):
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
    return x.astype(np.float32)


def rec_text(rec, samples):
    s = rec.create_stream()
    s.accept_waveform(16000, samples)
    rec.decode_stream(s)
    return s.result.text


def main():
    voice = PiperVoice.load(VOICE)
    audios = [(c, synth(voice, c)) for c in COMMANDS]
    print("Nap 2 recognizer (greedy vs hotwords)...")
    r_plain = mk(hot=False)
    try:
        r_hot = mk(hot=True)
    except Exception as e:
        print(f"[!] Hotwords khong tao duoc: {e}")
        r_hot = None

    print("=" * 92)
    print(f"{'Cau noi (goc)':<40}{'KHONG hotwords':<28}{'CO hotwords'}")
    print("-" * 92)
    for cmd, samples in audios:
        a = rec_text(r_plain, samples)
        b = rec_text(r_hot, samples) if r_hot else "(n/a)"
        print(f"{cmd:<40}{a:<28}{b}")
    print("-" * 92)
    print("Ky vong: cot phai (hotwords) sua duoc 'dung lai', 'quay trai'... ve dung.")


if __name__ == "__main__":
    main()
