#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
go2_audio_bridge.py — CAU NOI mic ROBOT (WebRTC) -> UDP 16kHz (BAN v2 — CHONG RE/MEO).

Sua tan goc hien tuong "re/meo/u" cua mic con cho:
  1. RESAMPLE dung chuan (scipy polyphase 48k->16k) thay vi "trung binh 3 mau"
     -> het aliasing (nguon gay re/meo chinh).
  2. DC-removal (high-pass) -> het "u" tan so thap (tieng dong co/quat).
  3. CHUAN HOA am luong (normalize) -> mic xa tieng nho -> keo len du to cho STT.
  4. (tuy chon) --denoise: loc on bang noisereduce neu da cai.

CHAY (tren Jetson):
  export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
  export GO2_IP=192.168.123.161
  python3 go2_audio_bridge.py                 # gui UDP cho assistant
  python3 go2_audio_bridge.py --record 5      # GHI 5s ra robot_mic_test.wav de NGHE THU
  python3 go2_audio_bridge.py --denoise       # bat loc on (can: pip install noisereduce)
  python3 go2_audio_bridge.py --gain 2.0      # khuech dai them neu tieng qua nho

TAT app Unitree truoc (WebRTC 1 ket noi).
"""

import os
import sys
import socket
import asyncio
import logging
import argparse
import wave

import numpy as np

logging.basicConfig(level=logging.FATAL)

ROBOT_IP = os.environ.get("GO2_IP", "192.168.123.161")
SRC_SR = 48000
DST_SR = 16000
FRAME_BYTES = 960   # 30ms @16kHz int16 mono

try:
    from unitree_webrtc_connect.webrtc_driver import (
        UnitreeWebRTCConnection,
        WebRTCConnectionMethod,
    )
except ImportError:
    sys.exit("Khong import duoc 'unitree_webrtc_connect'.\n"
             "  -> export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH")

try:
    from scipy.signal import resample_poly
    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False


class AudioProc:
    def __init__(self, gain=1.0, denoise=False, highpass=True, hp_cut=150.0, gate=0.0):
        self.gain = gain
        self.highpass = highpass
        self.gate = gate                  # nguong noise-gate (RMS chuan hoa 0..1); 0 = tat
        self._hp_b = self._hp_a = self._hp_zi = None
        if highpass and _HAVE_SCIPY:
            from scipy.signal import butter, lfilter_zi
            # butter bac 2 cat hp_cut Hz @ DST_SR -> giet hum/ù ~100Hz manh hon 1-pole
            self._hp_b, self._hp_a = butter(2, hp_cut / (DST_SR / 2.0), btype="high")
            self._hp_zi = lfilter_zi(self._hp_b, self._hp_a) * 0.0
        self._hp_prev_in = 0.0
        self._hp_prev_out = 0.0
        self._nr = None
        if denoise:
            try:
                import noisereduce as nr
                self._nr = nr
                print("[bridge] da bat loc on (noisereduce)")
            except ImportError:
                print("[bridge] chua cai noisereduce -> bo qua --denoise "
                      "(pip install noisereduce)")

    def _highpass(self, x):
        if self._hp_b is not None:                    # butter bac 2 (co scipy)
            from scipy.signal import lfilter
            y, self._hp_zi = lfilter(self._hp_b, self._hp_a, x, zi=self._hp_zi)
            return y
        out = np.empty_like(x)                          # fallback 1-pole
        prev_in, prev_out = self._hp_prev_in, self._hp_prev_out
        for i in range(x.size):
            s = x[i]
            y = 0.94 * (prev_out + s - prev_in)
            out[i] = y
            prev_in, prev_out = s, y
        self._hp_prev_in, self._hp_prev_out = prev_in, prev_out
        return out

    def process(self, mono_f32: np.ndarray, src_sr: int = SRC_SR) -> bytes:
        x = mono_f32.astype(np.float32)
        # resample src_sr -> DST_SR (dung dung ty le tu frame, KHONG cung 48k)
        if int(src_sr) != DST_SR:
            if _HAVE_SCIPY:
                from math import gcd
                g = gcd(int(src_sr), DST_SR)
                x = resample_poly(x, up=DST_SR // g, down=int(src_sr) // g)
            else:
                step = src_sr / DST_SR
                idx = (np.arange(int(x.size / step)) * step).astype(int)
                x = x[np.clip(idx, 0, x.size - 1)]
        if self.highpass:
            x = self._highpass(x)
        if self._nr is not None:
            try:
                x = self._nr.reduce_noise(y=x, sr=DST_SR, stationary=True)
            except Exception:
                pass
        if self.gate > 0:                     # noise-gate: frame qua nho (giua tu) -> ha
            rms = float(np.sqrt(np.mean(x * x)))
            if rms < self.gate:
                x = x * 0.1
        # GAIN co dinh + clip — KHONG chuan hoa tung frame (tranh keo nhieu len to)
        x = np.clip(x * self.gain, -1.0, 1.0)
        return (x * 32767).astype(np.int16).tobytes()


async def run(args):
    proc = AudioProc(gain=args.gain, denoise=args.denoise,
                     hp_cut=args.hp_cut, gate=args.gate)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (args.host, args.port)
    state = {"buf": b"", "pkts": 0, "t0": None, "n_out": 0, "da_bao": False,
             "da_canh_bao": False,
             "rec": [] if args.record else None,
             "rec_left": int(args.record * DST_SR) if args.record else 0}

    async def on_audio(frame):
        arr = frame.to_ndarray()
        # --- SO KENH: tinh tu SO MAU, khong hoi frame.layout ---
        # BAY DA DINH: PyAV >=12 tra frame.layout.channels la TUPLE cac AudioChannel,
        # KHONG phai so nguyen. Nen `arr.shape[0] == ch` va `ch == 2` LUON False ->
        # frame STEREO (packed, shape (1, 960) cho 480 mau/kenh) bi coi la mono va
        # lay het 960 mau -> audio DAI GAP DOI, cao do tut mot quang tam.
        # Trieu chung: ghi 25s ra file 50s, giong nghe "vang vang, chu keo dai",
        # STT khong doc ra chu nao. frame.samples = so mau MOI KENH -> chia ra la chac.
        n = int(getattr(frame, "samples", 0) or 0)
        if n > 0 and arr.size % n == 0:
            ch = max(1, arr.size // n)
        else:                                        # frame la -> doan an toan
            ch = arr.shape[0] if arr.ndim == 2 and arr.shape[0] <= 8 else 1
            n = arr.size // ch
        if arr.ndim == 2 and arr.shape[0] == ch and ch > 1:
            mono = arr.astype(np.float32).mean(axis=0)            # planar (ch, n)
        elif ch > 1:
            mono = arr.reshape(-1).astype(np.float32).reshape(n, ch).mean(axis=1)  # packed
        else:
            mono = arr.reshape(-1).astype(np.float32)
        if not state.get("da_bao"):                  # in 1 lan de biet dang doc dung gi
            state["da_bao"] = True
            print(f"\n[bridge] frame: {frame.sample_rate}Hz, {ch} kenh, "
                  f"{n} mau/kenh (arr {tuple(arr.shape)})")
        if mono.size == 0:
            return
        mono = mono / 32768.0
        src_sr = int(getattr(frame, "sample_rate", SRC_SR) or SRC_SR)
        pcm16 = proc.process(mono, src_sr)

        if state["rec"] is not None:
            arr = np.frombuffer(pcm16, dtype=np.int16)
            take = min(arr.size, state["rec_left"])
            state["rec"].append(arr[:take])
            state["rec_left"] -= take
            print(f"\r[bridge] dang ghi... con {state['rec_left']/DST_SR:.1f}s",
                  end="", flush=True)
            if state["rec_left"] <= 0:
                out = np.concatenate(state["rec"])
                with wave.open("robot_mic_test.wav", "wb") as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(DST_SR)
                    wf.writeframes(out.tobytes())
                print("\n[bridge] DA GHI robot_mic_test.wav — nghe: aplay robot_mic_test.wav")
                os._exit(0)
            return

        # TU KIEM TRA: so mau sinh ra phai khop dong ho. Lech >10% = doc frame sai
        # (chinh la bug stereo o tren). Bao ngay thay vi de nguoi dung tu mo.
        if state["t0"] is None:
            state["t0"] = __import__("time").time()
        state["n_out"] += len(pcm16) // 2
        _thuc = __import__("time").time() - state["t0"]
        if _thuc > 8 and not state["da_canh_bao"]:
            _ty = (state["n_out"] / DST_SR) / _thuc
            if not (0.9 < _ty < 1.1):
                state["da_canh_bao"] = True
                print(f"\n[bridge] \u26a0\ufe0f  SINH RA {_ty:.2f}x so voi thoi gian thuc "
                      f"-> audio bi {'GIAN' if _ty > 1 else 'NEN'}! Doc frame dang sai.")

        state["buf"] += pcm16
        while len(state["buf"]) >= FRAME_BYTES:
            pkt, state["buf"] = state["buf"][:FRAME_BYTES], state["buf"][FRAME_BYTES:]
            sock.sendto(pkt, addr)
            state["pkts"] += 1
            if state["pkts"] % 100 == 0:
                print(f"\r[bridge] da gui {state['pkts']} goi "
                      f"(~{state['pkts']*0.03:.0f}s)", end="", flush=True)

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    await conn.connect()
    mode = f"GHI {args.record}s ra file" if args.record else f"gui udp://{args.host}:{args.port}"
    print(f">>> WebRTC OK ({ROBOT_IP}) — {mode}")
    print(f">>> resample: {'scipy polyphase (tot)' if _HAVE_SCIPY else 'numpy mean (co ban)'}"
          f" | highpass: ON | gain: {args.gain} | denoise: {args.denoise}")
    conn.audio.switchAudioChannel(True)
    conn.audio.add_track_callback(on_audio)
    while True:
        await asyncio.sleep(1.0)


def main():
    p = argparse.ArgumentParser(description="Mic robot Go2 -> UDP 16kHz (v2)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=17890)
    p.add_argument("--gain", type=float, default=1.0)
    p.add_argument("--denoise", action="store_true")
    p.add_argument("--hp-cut", type=float, default=150.0,
                   help="tan so cat highpass (Hz) — nang len ~180 neu con ù")
    p.add_argument("--gate", type=float, default=0.0,
                   help="noise-gate (0..1, vd 0.02) — ha frame giua tu; 0=tat")
    p.add_argument("--record", type=float, default=0,
                   help="ghi N giay ra robot_mic_test.wav roi thoat")
    a = p.parse_args()
    try:
        asyncio.run(run(a))
    except KeyboardInterrupt:
        print("\n[bridge] dung.")


if __name__ == "__main__":
    main()
