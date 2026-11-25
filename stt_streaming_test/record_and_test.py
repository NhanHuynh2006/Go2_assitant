#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
record_and_test.py — THU MIC THAT -> zipformer-transducer (hotwords).
Endpoint theo NANG LUONG (khong kest vi mic clip) + bo 0.3s pop dau stream.
Ben voi mic laptop nhieu/AGC. Chay:  python3 record_and_test.py
"""
import os
import sys
import time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stt_transducer import STTTransducer            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
HOTW = os.path.join(HERE, "hotwords.txt")

SR = 16000
FRAME = 480                # 30ms
WARMUP = 10                # bo 10 frame dau (~300ms) — pop luc mo stream
CALIB = 6                  # 6 frame do nen on
SIL_END = 12               # ~360ms im -> ket thuc cau
MAX_FR = 200               # ~6s toi da
LISTEN_TIMEOUT = 15


def rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float32) ** 2)) + 1e-6)


def record_one_utterance():
    """Endpoint theo nang luong. Tra ve float32 16k hoac None."""
    import sounddevice as sd
    from scipy.signal import resample_poly
    cap = SR
    try:
        di = sd.query_devices(None, "input")
        dsr = int(round(di.get("default_samplerate") or SR))
        if dsr != SR and dsr % SR == 0:
            cap = dsr
    except Exception:
        pass
    down = cap // SR
    block = FRAME * down

    buf, started, silence = [], False, 0
    noise, calib = [], 0
    t0 = time.time()
    with sd.RawInputStream(samplerate=cap, blocksize=block, dtype="int16", channels=1) as st:
        n_read = 0
        start_thr = 1500.0
        while time.time() - t0 < LISTEN_TIMEOUT:
            data, _ = st.read(block)
            x = np.frombuffer(bytes(data), dtype=np.int16)
            if down > 1:
                x = np.clip(resample_poly(x.astype(np.float32), SR, cap), -32768, 32767).astype(np.int16)
            x = x[:FRAME]
            n_read += 1
            if n_read <= WARMUP:                     # bo pop dau
                continue
            e = rms(x)
            if calib < CALIB:                        # do nen on
                noise.append(e); calib += 1
                if calib == CALIB:
                    nf = float(np.median(noise))
                    start_thr = max(nf * 3.0, 1200.0)
                continue
            if not started:
                if e > start_thr:
                    started = True; buf.append(x)
                continue
            buf.append(x)
            silence = silence + 1 if e < start_thr * 0.5 else 0
            if silence >= SIL_END or len(buf) >= MAX_FR:
                break
    if len(buf) < 8:                                 # < ~0.25s -> coi nhu khong noi
        return None
    return np.concatenate(buf).astype(np.float32) / 32768.0


def main():
    stt = STTTransducer(MODEL, hotwords_file=HOTW, hotwords_score=2.5)
    print("=" * 62)
    print(" THU MIC THAT (endpoint nang luong) -> Zipformer-VI + hotwords")
    print(" ENTER = san sang roi NOI (tu dung khi noi xong) | q = thoat")
    print("=" * 62)
    while True:
        cmd = input("\n[ENTER roi NOI / q de thoat] ")
        if cmd.strip().lower() == "q":
            break
        print("  🔴 san sang — NOI CAU LENH DI...")
        audio = record_one_utterance()
        if audio is None:
            print("  ⏱️  khong nghe thay gi — thu lai")
            continue
        peak = int(np.abs(audio).max() * 32768)
        text, ms = stt.transcribe(audio)
        clip = "  ⚠️ con clip (mic laptop)" if peak >= 30000 else "  ✓ am OK"
        print(f"  🔊 am {peak} · dai {len(audio)/SR:.1f}s{clip}")
        print(f"  🗣️  ({ms:.0f} ms): {text!r}")


if __name__ == "__main__":
    main()
