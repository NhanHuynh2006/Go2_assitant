#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
go2_tts_speaker.py — CAU "LOA RA" cua GoVoice (2 che do).

Jetson trong robot KHONG co loa; loa o main board .161, chi ra tieng qua WebRTC.
Cau nay giu 1 phien WebRTC, nhan duong-dan-wav tu GoVoice (tts_engine output="robot")
qua UDP, roi phat ra LOA ROBOT.

  --mode stream  (MAC DINH, REAL-TIME nhu app "giu mic noi"):
      gan 1 AudioStreamTrack vao audio-sender (replaceTrack) -> day PCM thang ->
      robot phat NGAY, khong upload file. Cau dai cung khong tre.

  --mode upload  (du phong, chac chan chay nhung cau dai hoi tre):
      WebRTCAudioHub.enter_megaphone + upload_megaphone(file).

CHAY (Jetson robot, giu nen):
    export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH ; export GO2_IP=192.168.123.161
    python3 go2_tts_speaker.py                 # stream
    python3 go2_tts_speaker.py --mode upload   # neu stream khong ra tieng
"""

import os
import sys
import time
import fractions
import asyncio
import logging
import argparse

import numpy as np

logging.basicConfig(level=logging.WARNING)
ROBOT_IP = os.environ.get("GO2_IP", "192.168.123.161")

try:
    from unitree_webrtc_connect.webrtc_driver import (
        UnitreeWebRTCConnection, WebRTCConnectionMethod)
    from unitree_webrtc_connect.webrtc_audiohub import WebRTCAudioHub
except ImportError:
    sys.exit("Khong import duoc 'unitree_webrtc_connect' -> "
             "export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH")

try:
    from scipy.signal import resample_poly
except ImportError:
    resample_poly = None

OUT_SR = 48000                 # WebRTC/opus chuan 48kHz
FRAME_SAMPLES = OUT_SR * 20 // 1000     # 20ms = 960 mau


def _load_wav_48k(path):
    """Doc wav (bat ky SR) -> mono int16 48kHz."""
    import wave
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1).astype(np.int16)
    if sr != OUT_SR:
        if resample_poly is not None:
            x = resample_poly(x.astype(np.float32), OUT_SR, sr)
        else:                                   # fallback tho neu thieu scipy
            idx = (np.arange(int(len(x) * OUT_SR / sr)) * sr / OUT_SR).astype(int)
            x = x[np.clip(idx, 0, len(x) - 1)].astype(np.float32)
    return np.clip(x, -32768, 32767).astype(np.int16)


# ---------------- CHE DO STREAM (real-time) ----------------
async def run_stream(host, port, keep_files):
    from av import AudioFrame
    from aiortc.mediastreams import AudioStreamTrack

    class TTSTrack(AudioStreamTrack):
        """Sinh 20ms-frame lien tuc: co PCM thi phat, khong thi im lang."""
        def __init__(self):
            super().__init__()
            self.q = asyncio.Queue()
            self._t = None
            self._ts = 0

        async def recv(self):
            if self._t is None:
                self._t = time.time()
            else:
                self._ts += FRAME_SAMPLES
                wait = self._t + self._ts / OUT_SR - time.time()
                if wait > 0:
                    await asyncio.sleep(wait)
            try:
                s = self.q.get_nowait()
            except asyncio.QueueEmpty:
                s = np.zeros(FRAME_SAMPLES, dtype=np.int16)
            if len(s) < FRAME_SAMPLES:
                s = np.pad(s, (0, FRAME_SAMPLES - len(s)))
            f = AudioFrame.from_ndarray(s.reshape(1, -1), format="s16", layout="mono")
            f.sample_rate = OUT_SR
            f.pts = self._ts
            f.time_base = fractions.Fraction(1, OUT_SR)
            return f

    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    await conn.connect()
    print(f">>> WebRTC OK ({ROBOT_IP}) — CAU LOA RA [stream]")
    try:
        conn.audio.switchAudioChannel(True)
    except Exception as e:
        print(f"[tts-speaker] switchAudioChannel: {e}")

    track = TTSTrack()
    sender = None
    for t in conn.pc.getTransceivers():
        if t.kind == "audio":
            sender = t.sender
            break
    if sender is None:
        for s in conn.pc.getSenders():
            if getattr(s, "track", None) is None or s.track.kind == "audio":
                sender = s
                break
    if sender is None:
        print("!! Khong tim thay audio-sender -> robot khong cho gui audio track.\n"
              "   Thu lai voi: --mode upload")
        return
    sender.replaceTrack(track)        # aiortc: replaceTrack la HAM DONG BO (khong await)
    print(">>> da gan TTS track vao sender — phat REAL-TIME")

    loop = asyncio.get_event_loop()

    async def feed(path):
        if not os.path.exists(path):
            return
        try:
            pcm = _load_wav_48k(path)
            for i in range(0, len(pcm), FRAME_SAMPLES):
                track.q.put_nowait(pcm[i:i + FRAME_SAMPLES])
            print(f"   loa(stream): {os.path.basename(path)} ({len(pcm)/OUT_SR:.1f}s)")
        except Exception as e:
            print(f"[tts-speaker] loi nap wav: {e}")
        finally:
            if not keep_files:
                try:
                    os.remove(path)
                except Exception:
                    pass

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            p = data.decode("utf-8", "ignore").strip()
            if p:
                loop.create_task(feed(p))

    await loop.create_datagram_endpoint(_Proto, local_addr=(host, int(port)))
    print(f">>> nghe UDP {host}:{port} — san sang")
    await asyncio.Future()      # chay mai


# ---------------- CHE DO UPLOAD (fallback) ----------------
async def run_upload(host, port, keep_files):
    conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=ROBOT_IP)
    await conn.connect()
    hub = WebRTCAudioHub(conn)
    await hub.enter_megaphone()
    print(f">>> WebRTC OK ({ROBOT_IP}) — CAU LOA RA [upload/megaphone] — UDP {host}:{port}")
    loop = asyncio.get_event_loop()
    q: asyncio.Queue = asyncio.Queue()

    class _Proto(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            p = data.decode("utf-8", "ignore").strip()
            if p:
                loop.call_soon_threadsafe(q.put_nowait, p)

    await loop.create_datagram_endpoint(_Proto, local_addr=(host, int(port)))
    try:
        while True:
            path = await q.get()
            if not os.path.exists(path):
                continue
            try:
                await hub.upload_megaphone(path)
                print(f"   loa(upload): {os.path.basename(path)}")
            except Exception as e:
                print(f"[tts-speaker] loi phat: {e}")
            finally:
                if not keep_files:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
    finally:
        try:
            await hub.exit_megaphone()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="Cau phat tieng GoVoice ra LOA ROBOT (WebRTC).")
    ap.add_argument("--mode", choices=["stream", "upload"], default="stream")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=17891)
    ap.add_argument("--keep-files", action="store_true")
    a = ap.parse_args()
    fn = run_stream if a.mode == "stream" else run_upload
    try:
        asyncio.run(fn(a.host, a.port, a.keep_files))
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
