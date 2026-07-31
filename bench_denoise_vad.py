#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_denoise_vad.py — CHAM DIEM tung cau hinh khu nhieu tren CA HAI mat cung luc:

  (1) BAO DONG NHAM: nhieu lot cong -> STT che ra cau rac  (cang IT cang tot)
  (2) BAT DUOC CAU:  nguoi noi that -> he thong co nghe khong, doc co dung khong

Chi do 1 trong 2 la BAY: khu nhieu that manh thi het rac nhung cung diec luon;
gate that long thi bat het cau nhung ngap rac.

CACH LAM (khong dung nhieu tong hop — dung TIENG ON THAT cua robot):
  - Nen  : file ghi 30s tu mic robot trong phong yen  (--noise)
  - Giong: cau tieng Viet do Piper doc         (--say), tron vao nen o --snr dB
  - Chay qua ĐUNG _VadSegmenter + noise-gate cua audio_io.py, roi qua STT that

CHAY:
  # 1. ghi nen on that (robot dang bat, terminal khac KHONG can chay gi):
  export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH GO2_IP=192.168.123.161
  python3 go2_audio_bridge.py --record 30 --gain 2.5
  mv robot_mic_test.wav robot_mic_noise30s.wav

  # 2. cham diem:
  python3 bench_denoise_vad.py --noise robot_mic_noise30s.wav
"""

import argparse
import os
import subprocess
import tempfile
import unicodedata
import wave

import numpy as np

SR = 16000
PIPER = "/home/unitree/piper/piper"
VOICE = ("/home/unitree/NhanHuynh/go2_jetson_demo/models/piper/vi/vi_VN/"
         "vais1000/medium/vi_VN-vais1000-medium.onnx")
GTCRN = "models/denoiser/gtcrn_simple.onnx"

SENTENCES = [
    "đi thẳng ba mét",
    "quay sang phải chín mươi độ",
    "chào mọi người đi Gô",
    "bạn tên là gì",
    "lùi lại hai mét rồi dừng",
    "nhảy một điệu đi",
]


def read_wav16k(path):
    w = wave.open(path)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    sr = w.getframerate()
    if sr != SR:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g)
    return x.astype(np.float32)


def tts(text):
    f = tempfile.mktemp(suffix=".wav")
    subprocess.run([PIPER, "-m", VOICE, "-f", f], input=text.encode(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    x = read_wav16k(f)
    os.unlink(f)
    return x


def strip_accents(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def wer(ref, hyp):
    r, h = strip_accents(ref).split(), strip_accents(hyp).split()
    if not r:
        return 1.0
    d = np.zeros((len(r) + 1, len(h) + 1), dtype=np.int32)
    d[:, 0] = np.arange(len(r) + 1)
    d[0, :] = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1,
                          d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r), len(h)] / len(r)


def build_track(noise, snr_db, seed=0):
    """Rai cac cau vao nen on THAT o muc SNR cho truoc. Tra ve (tin hieu, danh sach cau)."""
    rng = np.random.default_rng(seed)
    n_rms = float(np.sqrt(np.mean(noise ** 2)))
    parts, truth = [], []
    gap = int(1.6 * SR)
    parts.append(np.zeros(gap, dtype=np.float32))
    for s in SENTENCES:
        v = tts(s)
        v_rms = float(np.sqrt(np.mean(v ** 2))) or 1e-9
        v = v * (n_rms * (10 ** (snr_db / 20.0)) / v_rms)
        truth.append(s)
        parts.append(v.astype(np.float32))
        parts.append(np.zeros(gap + int(rng.integers(0, SR)), dtype=np.float32))
    speech = np.concatenate(parts)
    reps = int(np.ceil(len(speech) / len(noise)))
    nz = np.tile(noise, reps)[:len(speech)]
    return np.clip(speech + nz, -1.0, 1.0).astype(np.float32), truth


def run_chain(x, den, gate_rms, gate_factor):
    from audio_io import _VadSegmenter, FRAME_SAMPLES
    seg = _VadSegmenter(2, 12, 0.5, silence_end_frames=8,
                        noise_gate=gate_rms, noise_gate_factor=gate_factor)
    i16 = np.clip(x * 32768.0, -32768, 32767).astype(np.int16)
    out = []
    for i in range(0, len(i16) - FRAME_SAMPLES, FRAME_SAMPLES):
        f = i16[i:i + FRAME_SAMPLES].tobytes()
        if den is not None:
            f = den.process_frame(f)
            if not f:
                continue
        u = seg.feed(f)
        if u is not None:
            out.append(u)
    return out


def score(utts, truth, stt):
    """Ghep moi cau doc duoc voi cau goc GAN NHAT; WER<=0.5 tinh la BAT DUOC."""
    texts = [stt.transcribe(a)[0].strip() for a in utts]
    texts = [t for t in texts if t]
    remaining = list(truth)
    hits, wers, junk = 0, [], 0
    for t in texts:
        if not remaining:
            junk += 1
            continue
        ws = [wer(r, t) for r in remaining]
        k = int(np.argmin(ws))
        if ws[k] <= 0.5:
            hits += 1
            wers.append(ws[k])
            remaining.pop(k)
        else:
            junk += 1
    return hits, junk, (float(np.mean(wers)) if wers else 1.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--noise", default="robot_mic_noise30s.wav",
                   help="file ghi TIENG ON THAT tu mic robot")
    p.add_argument("--snr", type=float, nargs="+", default=[10, 5],
                   help="cac muc SNR (dB) de thu")
    p.add_argument("--gate-rms", type=int, default=130)
    p.add_argument("--gate-factor", type=float, default=3.5)
    p.add_argument("--stt-model", default="models/zipformer-vi-30M")
    a = p.parse_args()

    noise = read_wav16k(a.noise)
    print(f"nen on: {a.noise} — {len(noise)/SR:.0f}s, RMS "
          f"{20*np.log10(float(np.sqrt(np.mean(noise**2))) + 1e-12):.1f} dBFS")

    from denoiser import StreamDenoiser
    from stt_transducer import STTTransducer
    stt = STTTransducer(a.stt_model, hotwords_file="hotwords.txt", hotwords_score=3.0)

    def cfgs():
        yield "khong khu nhieu", lambda: None
        for m in (1.0, 0.9, 0.85, 0.7):
            yield f"gtcrn mix={m}", (lambda m=m: StreamDenoiser("gtcrn", GTCRN, mix=m))
        yield "rnnoise", lambda: StreamDenoiser("rnnoise")

    # do rieng ty le BAO DONG NHAM tren nen on THUAN (khong co giong)
    print("\n### A. BAO DONG NHAM — 30s nen on THUAN, khong ai noi "
          "(cang it cang tot)")
    print(f"{'cau hinh':<20} {'so cau rac':>11}")
    print("-" * 33)
    fa = {}
    for name, mk in cfgs():
        u = run_chain(noise, mk(), a.gate_rms, a.gate_factor)
        t = [x for x in (stt.transcribe(s)[0].strip() for s in u) if x and x != "<"]
        fa[name] = len(t)
        print(f"{name:<20} {len(t):>11}")

    # do kha nang BAT DUOC CAU o tung SNR
    for snr in a.snr:
        x, truth = build_track(noise, snr)
        print(f"\n### B. SNR {snr:g} dB — {len(truth)} cau noi that, "
              f"{len(x)/SR:.0f}s (bat duoc bao nhieu / doc dung khong)")
        print(f"{'cau hinh':<20} {'bat duoc':>9} {'WER':>7} {'rac':>5}")
        print("-" * 45)
        for name, mk in cfgs():
            u = run_chain(x, mk(), a.gate_rms, a.gate_factor)
            hits, junk, w = score(u, truth, stt)
            print(f"{name:<20} {hits:>4}/{len(truth):<4} {w*100:6.1f}% {junk:>5}")

    print("\nDoc bang: chon cau hinh co 'bat duoc' CAO, 'WER' THAP, 'rac' THAP.")


if __name__ == "__main__":
    main()
