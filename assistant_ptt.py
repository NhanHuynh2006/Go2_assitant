#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant_ptt.py — GoVoice PUSH-TO-TALK (bam-de-noi), MIC ROBOT.

Khac assistant_realtime.py (nghe LIEN TUC): file nay CHI nghe khi ban BAM PHIM.
Bam phim -> noi 1 cau -> VAD tu ngat khi im lang -> STT -> nghi -> noi + hanh dong.
Xong, bam lan nua de noi cau tiep.

VI SAO CAN: mic robot nam ngay tren than may, nghe ca tieng quat/dong co cua chinh
no. Nghe LIEN TUC thi thinh thoang VAD+STT "bay" ra cau co nghia du KHONG ai noi
(do duoc bang mic_debug.py tren con B: 2/5 doan 5s im lang van ra cau tieng Viet).
PTT cat tan goc — mic chi mo dung luc ban bam phim.

Dung chung "bo nao" + robot + safety + VAD voi assistant_realtime (KHONG sua file do).

CHAY (can go2_audio_bridge.py chay san de cau mic robot -> UDP):
  # robot GIA (dry-run, an toan test logic):
  python3 assistant_ptt.py --config config_robot_mic.yaml --key space
  # robot THAT tren Jetson:
  python3 assistant_ptt.py --config config_robot_mic.yaml --key space --real
"""

import argparse
import socket
import sys
import time

from assistant_realtime import GoVoiceRT, load_config
from audio_io import FRAME_BYTES, get_listener, _den_on


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


class UdpCapture:
    """Thu 1 cau tu MIC ROBOT (UDP do go2_audio_bridge.py ban sang).

    Bridge ban UDP LIEN TUC, khong the "dong mic" giua cac lan bam. Nen giu socket
    mo suot, va ngay TRUOC moi lan thu thi VUT HET goi da don lai — khong lam vay
    se nghe lai am thanh cua luc CHUA bam phim, dung cai ma push-to-talk sinh ra
    de tranh.
    """

    def __init__(self, listener):
        self.seg = listener.seg
        self.den = listener.den
        self.addr = listener.addr
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(listener.addr)
        self.leftover = b""

    def _drain(self):
        self.sock.setblocking(False)
        try:
            while True:
                try:
                    self.sock.recv(65536)
                except (BlockingIOError, OSError):
                    break
        finally:
            self.sock.setblocking(True)
        self.leftover = b""

    def capture_one(self, max_wait_s=8.0):
        """Thu DUNG 1 cau roi thoi. None neu khong noi gi trong max_wait_s."""
        self.seg.reset()
        self._drain()
        t0 = time.time()
        self.sock.settimeout(0.3)
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                if not self.seg.recording and time.time() - t0 > max_wait_s:
                    return None
                continue
            self.leftover += data
            while len(self.leftover) >= FRAME_BYTES:
                frame = self.leftover[:FRAME_BYTES]
                self.leftover = self.leftover[FRAME_BYTES:]
                if _den_on(self.den):
                    frame = self.den.process_frame(frame)
                    if not frame:
                        continue
                utt = self.seg.feed(frame)
                if utt is not None:
                    return utt
            if not self.seg.recording and time.time() - t0 > max_wait_s:
                return None


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
    ap = argparse.ArgumentParser(
        description="GoVoice PUSH-TO-TALK (mic ROBOT, bam phim de noi)")
    ap.add_argument("--config", default="config_robot_mic.yaml")
    ap.add_argument("--real", action="store_true", help="dieu khien robot THAT")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--key", default="space",
                    help="phim kich hoat (mac dinh 'space'; hoac mot ky tu vd 't')")
    a = ap.parse_args()

    trigger = " " if a.key.lower() == "space" else a.key.lower()[:1]
    cfg = load_config(a.config)
    cfg_audio = cfg.get("audio", {})
    if (cfg_audio.get("backend") or "local").lower() != "udp":
        sys.exit(f"[ptt] config '{a.config}' khong dung mic ROBOT.\n"
                 f"  -> can 'audio.backend: udp' (vd config_robot_mic.yaml)")

    gv = GoVoiceRT(cfg, force_real=a.real, no_tts=a.no_tts)
    stt = build_stt(cfg)
    listener = get_listener(cfg_audio, mute=gv.mute)
    udp = UdpCapture(listener)

    key = _KeyReader()
    tname = "PHIM CACH" if trigger == " " else f"phim '{trigger.upper()}'"
    print("=" * 60)
    print(" GoVoice PUSH-TO-TALK — mic ROBOT")
    print(f"  • Bam {tname}  -> noi 1 cau (tu ngat khi ban dung noi)")
    print("  • Bam 'q' (hoac Ctrl+C) -> thoat")
    print(f"  • mic ROBOT qua UDP {udp.addr} (nho chay go2_audio_bridge.py)")
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
            utt = udp.capture_one()
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
