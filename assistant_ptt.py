#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant_ptt.py — GoVoice PUSH-TO-TALK (bam-de-noi).

Khac assistant_realtime.py (nghe LIEN TUC): file nay CHI nghe khi ban BAM PHIM 'T'.
Bam T -> noi 1 cau -> VAD tu ngat khi im lang -> STT -> nghi -> noi + hanh dong.
Xong, bam T lan nua de noi cau tiep. Dung cho NGOAI TROI on ao (mic khong tu nghe
tap am xung quanh, chi mo mic dung luc ban bam).

Dung chung "bo nao" + robot + safety + VAD voi assistant_realtime (KHONG sua file do).

CHAY:
  # robot GIA (dry-run, an toan test logic):
  python3 assistant_ptt.py
  # robot THAT tren Jetson:
  python3 assistant_ptt.py --real
  # doi phim kich hoat (mac dinh 't'):
  python3 assistant_ptt.py --key space
"""

import argparse
import sys
import time

import numpy as np

from assistant_realtime import GoVoiceRT, load_config
from audio_io import (SR, FRAME_SAMPLES, FRAME_BYTES, get_listener,
                      resolve_input_device, ensure_capture_gain)


def build_stt(cfg):
    """Giong het cach assistant_realtime.run_voice dung STT (transducer / whisper)."""
    s = cfg.get("stt", {})
    if (s.get("backend") or "whisper").lower() == "transducer":
        from stt_transducer import STTTransducer
        return STTTransducer(
            s.get("transducer_model",
                  "stt_streaming_test/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"),
            hotwords_file=s.get("hotwords_file"),
            hotwords_score=s.get("hotwords_score", 3.0),
            num_threads=s.get("num_threads", 4),
            use_gpu=(s.get("device", "cpu") == "cuda"))
    from stt_engine import STT
    return STT(model=s.get("model", "small"),
               fallback_model=s.get("fallback_model", "small"),
               device=s.get("device", "cuda"),
               compute_type=s.get("compute_type", "int8_float16"),
               language=s.get("language", "vi"),
               beam_size=s.get("beam_size", 5),
               initial_prompt=s.get("initial_prompt"))


def capture_one(device, seg, max_wait_s=8.0, stall_s=1.5, mic_gain=25):
    """Mo mic, thu DUNG 1 cau roi dong. VAD (seg) tu ngat khi im lang.
    Tra ve audio float32 16k, hoac None neu: khong noi gi trong max_wait_s,
    hoac mic treo (khong ra du lieu) qua stall_s."""
    import sounddevice as sd
    try:
        from scipy.signal import resample_poly
    except Exception:
        resample_poly = None

    device = resolve_input_device(device)     # "auto"/ten sai -> tu tim mic USB
    ensure_capture_gain(device, mic_gain)     # hub hay reset gain -> dat lai muc chuan (25%)
    cap_sr = SR
    try:
        di = sd.query_devices(device, "input")
        dsr = int(round(di.get("default_samplerate") or SR))
        if dsr != SR and dsr % SR == 0:
            cap_sr = dsr
    except Exception:
        pass
    down = cap_sr // SR
    blocksize = FRAME_SAMPLES * down

    seg.reset()
    t0 = time.time()
    last_ok = t0
    with sd.RawInputStream(samplerate=cap_sr, blocksize=blocksize,
                           dtype="int16", channels=1, device=device) as stream:
        while True:
            if stream.read_available < blocksize:
                time.sleep(0.005)
                now = time.time()
                # chua noi gi ma qua han cho -> thoi (bam T lai)
                if not seg.recording and now - t0 > max_wait_s:
                    return None
                # mic treo giua chung -> bo, tranh dung mai
                if now - last_ok > stall_s:
                    return None
                continue
            data, _overflow = stream.read(blocksize)
            last_ok = time.time()
            if cap_sr == SR:
                frame = bytes(data)
            else:
                x = np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32)
                if resample_poly is not None:
                    y = resample_poly(x, SR, cap_sr)
                else:
                    y = x[::down]
                frame = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
            if len(frame) != FRAME_BYTES:
                continue
            utt = seg.feed(frame)          # tu gom + tu ngat khi im lang
            if utt is not None:
                return utt


class _KeyReader:
    """Doc 1 phim khong can Enter (termios). Neu khong phai terminal -> dung Enter."""

    def __init__(self):
        self.raw = sys.stdin.isatty()

    def get(self) -> str:
        if not self.raw:
            return sys.stdin.readline().strip()[:1] or "\n"
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch


def main():
    ap = argparse.ArgumentParser(description="GoVoice PUSH-TO-TALK (bam T de noi)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--real", action="store_true", help="dieu khien robot THAT")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--key", default="t",
                    help="phim kich hoat (mac dinh 't'; dung 'space' cho phim cach)")
    a = ap.parse_args()

    trigger = " " if a.key.lower() == "space" else a.key.lower()[:1]
    cfg = load_config(a.config)
    gv = GoVoiceRT(cfg, force_real=a.real, no_tts=a.no_tts)
    stt = build_stt(cfg)

    # Tai dung mic + VAD tu config (device, do nhay, thoi gian ngat...) — nhung TU doc.
    listener = get_listener(cfg.get("audio", {}), mute=gv.mute)
    device = getattr(listener, "device", cfg.get("audio", {}).get("input_device"))
    seg = listener.seg

    key = _KeyReader()
    tname = "PHIM CACH" if trigger == " " else f"phim '{trigger.upper()}'"
    print("=" * 60)
    print(" GoVoice PUSH-TO-TALK — bam de noi")
    print(f"  • Bam {tname}  -> noi 1 cau (tu ngat khi im lang)")
    print("  • Bam 'q' (hoac Ctrl+C) -> thoat")
    print("=" * 60)

    try:
        while True:
            print(f"\n[⏸  cho] bam {tname} de noi...", end="", flush=True)
            ch = key.get()
            if ch in ("q", "Q", "\x03", "\x04"):      # q / Ctrl+C / Ctrl+D
                break
            if ch != trigger:
                continue

            # Doi Go noi xong (neu con) de mic khong tu nghe chinh minh
            while gv.mute.is_set():
                time.sleep(0.02)

            print("\r🎤 [nghe] noi di... (tu ngat khi ban dung noi)        ", flush=True)
            utt = capture_one(device, seg, mic_gain=getattr(listener, "mic_gain", 25))
            if utt is None:
                print("   (khong nghe thay gi — bam de noi lai)")
                continue
            text, stt_ms = stt.transcribe(utt)
            if not text:
                print("   (khong ro cau — bam de noi lai)")
                continue
            print(f"🗣️  Nghe: {text}")
            gv.process(text, stt_ms=stt_ms)
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.emergency_stop()
        gv.executor.shutdown()
        print("\nTam biet!")


if __name__ == "__main__":
    main()
