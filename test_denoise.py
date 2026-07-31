#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_denoise.py — DO XEM khu nhieu co that su giup KHONG (A/B, khong doan mo).

3 kieu dung:

1) GHI THU tu mic ROBOT roi so sanh  (nho chay go2_audio_bridge.py o terminal khac):
       python3 test_denoise.py --record-udp 6 --say "đi thẳng ba mét rồi chào"
2) GHI THU tu mic USB dang cam:
       python3 test_denoise.py --record-local 6 --say "đi thẳng ba mét rồi chào"
3) So sanh tren file wav 16kHz da co:
       python3 test_denoise.py --wav robot_mic_test.wav --say "..."

Ket qua in ra:
  - RTF (chi phi CPU) cua tung backend
  - RMS truoc/sau + uoc luong do GIAM NEN NHIEU (do tren doan im lang nhat)
  - Cau STT doc duoc cua tung bien the -> so voi --say de biet cai nao dung hon
  - File wav xuat ra thu muc denoise_ab/ de TU NGHE bang tai:
        aplay denoise_ab/00_goc.wav ; aplay denoise_ab/01_gtcrn.wav

--say la CAU BAN THUC SU NOI (khong bat buoc). Co no thi script cham luon
ti le tu dung (WER don gian) de khoi phai tu nhin.
"""

import argparse
import os
import socket
import time
import unicodedata
import wave

import numpy as np

SR = 16000
FRAME = 480
OUTDIR = "denoise_ab"


# ---------------------------------------------------------------- lay audio
def read_wav(path):
    w = wave.open(path)
    if w.getnchannels() != 1:
        raise SystemExit("can wav MONO")
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    sr = w.getframerate()
    if sr != SR:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g)
    return x


def record_udp(seconds, host="127.0.0.1", port=17890):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(10.0)
    sock.bind((host, int(port)))
    print(f"⏺  dang doi goi UDP tu go2_audio_bridge.py o {host}:{port} ...")
    need = int(seconds * SR) * 2
    buf = b""
    t0 = None
    try:
        while len(buf) < need:
            data, _ = sock.recvfrom(4096)
            if t0 is None:
                t0 = time.time()
                print(f"🎙  CO TIN HIEU — NOI DI, ghi {seconds:.0f}s...")
            buf += data
            print(f"\r   {len(buf)/2/SR:.1f}/{seconds:.0f}s", end="", flush=True)
    except socket.timeout:
        raise SystemExit("\nkhong nhan duoc goi UDP nao. Chay bridge truoc:\n"
                         "  export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH\n"
                         "  export GO2_IP=192.168.123.161\n"
                         "  python3 go2_audio_bridge.py")
    print()
    return np.frombuffer(buf[:need], dtype=np.int16).astype(np.float32) / 32768.0


def record_local(seconds, device="auto", mic_gain=35):
    import sounddevice as sd
    from audio_io import resolve_input_device, ensure_capture_gain
    dev = resolve_input_device(device)
    ensure_capture_gain(dev, mic_gain)
    cap_sr = SR
    try:
        info = sd.query_devices(dev, "input")
        d = int(round(info.get("default_samplerate") or SR))
        if d != SR and d % SR == 0:
            cap_sr = d
    except Exception:
        pass
    print(f"🎙  ghi {seconds:.0f}s tu mic {dev!r} @{cap_sr}Hz — NOI DI...")
    rec = sd.rec(int(seconds * cap_sr), samplerate=cap_sr, channels=1, dtype="float32",
                 device=dev)
    sd.wait()
    x = rec[:, 0]
    if cap_sr != SR:
        from scipy.signal import resample_poly
        x = resample_poly(x, SR, cap_sr)
    return x.astype(np.float32)


# ---------------------------------------------------------------- do dac
def rms(a):
    return float(np.sqrt(np.mean(a.astype(np.float64) ** 2))) if a.size else 0.0


def noise_rms(a, win=0.3):
    """RMS cua 10% cua so YEN NHAT — xap xi 'nen nhieu' cua ban ghi."""
    n = int(win * SR)
    if a.size < n * 3:
        return rms(a)
    vals = np.array([rms(a[i:i + n]) for i in range(0, a.size - n, n)])
    return float(np.percentile(vals, 10))


def db(x):
    return 20 * np.log10(max(x, 1e-9))


def strip_accents(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def wer(ref, hyp):
    """WER don gian tren tu KHONG DAU (STT hay sai dau -> cham the nay cong bang hon)."""
    r, h = strip_accents(ref).split(), strip_accents(hyp).split()
    if not r:
        return None
    d = np.zeros((len(r) + 1, len(h) + 1), dtype=np.int32)
    d[:, 0] = np.arange(len(r) + 1)
    d[0, :] = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1,
                          d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r), len(h)] / len(r)


def save(name, x):
    os.makedirs(OUTDIR, exist_ok=True)
    p = os.path.join(OUTDIR, name)
    with wave.open(p, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.clip(x * 32768.0, -32768, 32767).astype(np.int16).tobytes())
    return p


# ---------------------------------------------------------------- chay
def main():
    p = argparse.ArgumentParser(description="A/B khu nhieu cho mic robot / mic USB")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--wav", help="file wav mono co san")
    g.add_argument("--record-udp", type=float, metavar="GIAY",
                   help="ghi tu mic ROBOT qua go2_audio_bridge.py")
    g.add_argument("--record-local", type=float, metavar="GIAY",
                   help="ghi tu mic USB dang cam")
    p.add_argument("--say", default="", help="cau ban THUC SU noi (de cham WER)")
    p.add_argument("--device", default="auto", help="mic cho --record-local")
    p.add_argument("--mic-gain", type=int, default=35)
    p.add_argument("--udp-port", type=int, default=17890)
    p.add_argument("--model", default="models/denoiser/gtcrn_simple.onnx")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--stt-model", default="models/zipformer-vi-30M")
    p.add_argument("--no-stt", action="store_true", help="chi do tin hieu, bo qua STT")
    a = p.parse_args()

    if a.wav:
        x = read_wav(a.wav)
    elif a.record_udp:
        x = record_udp(a.record_udp, port=a.udp_port)
    else:
        x = record_local(a.record_local, a.device, a.mic_gain)
    print(f"\n== nguon: {x.size / SR:.1f}s @16kHz | RMS {db(rms(x)):.1f}dBFS "
          f"| dinh {db(float(np.abs(x).max())):.1f}dBFS ==\n")

    from denoiser import StreamDenoiser
    variants = [("00_goc", None, {})]
    variants.append(("01_gtcrn", "gtcrn", dict(model=a.model, num_threads=a.threads)))
    variants.append(("02_gtcrn_mix85", "gtcrn",
                     dict(model=a.model, num_threads=a.threads, mix=0.85)))
    if os.path.exists("librnnoise.so") or os.path.exists(
            "/home/unitree/.local/lib/python3.8/site-packages/pyrnnoise/librnnoise.so"):
        variants.append(("03_rnnoise", "rnnoise", {}))

    stt = None
    if not a.no_stt:
        try:
            from stt_transducer import STTTransducer
            stt = STTTransducer(a.stt_model, hotwords_file="hotwords.txt",
                                hotwords_score=3.0)
        except Exception as e:
            print(f"⚠️  khong nap duoc STT ({e}) -> chi do tin hieu\n")

    n0 = noise_rms(x)
    rows = []
    for name, backend, kw in variants:
        if backend is None:
            y, rtf = x, 0.0
        else:
            try:
                dn = StreamDenoiser(backend=backend, **kw)
            except Exception as e:
                print(f"[{name}] BO QUA: {e}")
                continue
            t0 = time.perf_counter()
            y = dn.process_array(x)
            rtf = (time.perf_counter() - t0) / (x.size / SR)
        path = save(name + ".wav", y)
        nr = noise_rms(y)
        txt, ms = ("", 0.0)
        if stt is not None and y.size:
            txt, ms = stt.transcribe(y)
        w = wer(a.say, txt) if (a.say and txt) else None
        rows.append((name, rtf, db(rms(y)), db(nr), db(nr) - db(n0), txt, ms, w, path))

    print(f"{'bien the':<16} {'RTF':>6} {'RMS dB':>8} {'nen nhieu dB':>13} {'Δnhieu':>8} "
          f"{'STT ms':>7} {'WER':>6}  cau doc duoc")
    print("-" * 118)
    for name, rtf, r_, nrd, dn_, txt, ms, w, path in rows:
        ws = f"{w * 100:5.1f}%" if w is not None else "    -"
        print(f"{name:<16} {rtf:6.3f} {r_:8.1f} {nrd:13.1f} {dn_:+8.1f} "
              f"{ms:7.0f} {ws}  {txt}")
    print("-" * 118)
    if a.say:
        print(f"cau goc  : {a.say}")
    print(f"\nfile de NGHE THU nam trong ./{OUTDIR}/ — vd:  aplay {OUTDIR}/01_gtcrn.wav")
    print("Doc bang: 'Δnhieu' cang AM cang khu manh; WER cang THAP cang dung.")
    print("Neu WER khu nhieu CAO hon goc -> dang bi cat lem giong: dung mix 0.85 "
          "hoac tang denoise.gain.")


if __name__ == "__main__":
    main()
