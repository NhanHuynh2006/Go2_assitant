#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_io.py — "ONG TAI" cua GoVoice: lay audio mic + tu cat thanh tung CAU.

2 backend (chon trong config.yaml -> audio.backend):
  "local" — mic laptop qua sounddevice (giai doan test tren may)
  "udp"   — nhan PCM 16kHz mono int16 qua UDP tu go2_audio_bridge.py
            (bridge lay tu MIC ROBOT qua WebRTC) -> dung cho deploy len Jetson

VAD (webrtcvad) cat cau:
  - frame 30ms; bat dau ghi khi >=60% frame gan day la giong noi
  - ket thuc cau sau ~450ms im lang
  - cau < min_utterance_s bi bo (tieng on lat nhat)
"""

import collections
import socket

import numpy as np

SR = 16000
FRAME_MS = 30
FRAME_SAMPLES = SR * FRAME_MS // 1000      # 480 samples
FRAME_BYTES = FRAME_SAMPLES * 2            # int16 -> 960 bytes


class _VadSegmenter:
    """Nhan tung frame 30ms (bytes int16) -> tra ve ca CAU (np.float32) khi xong."""

    def __init__(self, aggressiveness=2, max_s=12, min_s=0.45,
                 silence_end_frames=9, trigger_ratio=0.6, ring=10):
        import webrtcvad
        self.vad = webrtcvad.Vad(int(aggressiveness))
        self.max_frames = int(max_s * 1000 / FRAME_MS)
        self.min_frames = int(min_s * 1000 / FRAME_MS)
        self.silence_end = silence_end_frames
        self.trigger_ratio = trigger_ratio
        self.ring = collections.deque(maxlen=ring)
        self.recording = False
        self.buf = []
        self.silence = 0

    def reset(self):
        """Xoa trang thai dang ghi (dung khi mute mic luc Go noi)."""
        self.ring.clear()
        self.recording = False
        self.buf = []
        self.silence = 0

    def feed(self, frame_bytes: bytes):
        if len(frame_bytes) != FRAME_BYTES:
            return None
        try:
            speech = self.vad.is_speech(frame_bytes, SR)
        except Exception:
            speech = False

        if not self.recording:
            self.ring.append((frame_bytes, speech))
            voiced = sum(1 for _, s in self.ring if s)
            if len(self.ring) == self.ring.maxlen and \
               voiced >= self.trigger_ratio * self.ring.maxlen:
                # Bat dau cau: lay ca phan dau trong ring de khoi mat chu dau
                self.recording = True
                self.buf = [f for f, _ in self.ring]
                self.ring.clear()
                self.silence = 0
            return None

        # dang ghi
        self.buf.append(frame_bytes)
        self.silence = 0 if speech else self.silence + 1
        if self.silence >= self.silence_end or len(self.buf) >= self.max_frames:
            frames = self.buf
            self.recording = False
            self.buf = []
            self.silence = 0
            if len(frames) < self.min_frames:
                return None                      # qua ngan -> bo
            pcm = b"".join(frames)
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            return audio
        return None


class LocalMic:
    """Mic laptop. Dung: for utterance in LocalMic(cfg).listen(): ..."""

    def __init__(self, vad_aggr=2, max_s=12, min_s=0.45, mute=None,
                 silence_end_frames=9, device=None):
        self.seg = _VadSegmenter(vad_aggr, max_s, min_s,
                                 silence_end_frames=silence_end_frames)
        self.mute = mute
        self.device = device          # None=mic mac dinh | so/ten = chon mic USB cu the

    def listen(self):
        import sounddevice as sd

        # Mic USB hay chi chay rate cao (vd 48k), khong cho mo 16k truc tiep.
        # -> thu o rate NATIVE roi resample ve SR (16k).
        cap_sr = SR
        try:
            di = sd.query_devices(self.device, "input")
            dsr = int(round(di.get("default_samplerate") or SR))
            if dsr != SR and dsr % SR == 0:
                cap_sr = dsr
        except Exception:
            pass
        down = cap_sr // SR
        blocksize = FRAME_SAMPLES * down

        # BLOCKING read (khong dung callback) — mot so USB ALSA (vd Jetson + hub)
        # KHONG goi callback cua RawInputStream (im lang, khong loi) -> doi sang
        # stream.read() da xac nhan hoat dong on dinh tren phan cung nay.
        with sd.RawInputStream(samplerate=cap_sr, blocksize=blocksize,
                               dtype="int16", channels=1,
                               device=self.device) as stream:
            dev = self.device if self.device is not None else "mac dinh"
            sr_note = f"@{cap_sr}Hz->16k" if cap_sr != SR else "@16k"
            print(f"\U0001F3A4 [mic local: {dev} {sr_note}] dang nghe... (Ctrl+C de thoat)")
            while True:
                data, _overflow = stream.read(blocksize)
                if cap_sr == SR:
                    frame = bytes(data)
                else:
                    x = np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32)
                    try:
                        from scipy.signal import resample_poly
                        y = resample_poly(x, SR, cap_sr)        # 48k -> 16k
                    except Exception:
                        y = x[::down]                            # fallback tho
                    frame = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
                if len(frame) != FRAME_BYTES:
                    continue
                if self.mute is not None and self.mute.is_set():
                    self.seg.reset()       # Go dang noi -> bo qua, khoi tu nghe minh
                    continue
                utt = self.seg.feed(frame)
                if utt is not None:
                    yield utt


class UdpMic:
    """Nhan PCM 16k mono int16 tu go2_audio_bridge.py (mic ROBOT)."""

    def __init__(self, host="127.0.0.1", port=17890, vad_aggr=2,
                 max_s=12, min_s=0.45, mute=None, silence_end_frames=9):
        self.addr = (host, int(port))
        self.seg = _VadSegmenter(vad_aggr, max_s, min_s,
                                 silence_end_frames=silence_end_frames)
        self.mute = mute

    def listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(self.addr)
        print(f"\U0001F3A4 [mic ROBOT/UDP] dang nghe tren {self.addr} ... "
              f"(nho chay go2_audio_bridge.py)")
        leftover = b""
        while True:
            data, _ = sock.recvfrom(4096)
            leftover += data
            while len(leftover) >= FRAME_BYTES:
                frame, leftover = leftover[:FRAME_BYTES], leftover[FRAME_BYTES:]
                if self.mute is not None and self.mute.is_set():
                    self.seg.reset()
                    continue
                utt = self.seg.feed(frame)
                if utt is not None:
                    yield utt


def get_listener(cfg_audio: dict, mute=None):
    backend = (cfg_audio.get("backend") or "local").lower()
    # silence_end_ms: cang nho -> phan hoi cang "lien" (nhung pause giua cau de bi cat).
    # 270ms (9 frame) la diem can; lenh ngan co the ha 210ms, doc cham nen de 360ms.
    sil_frames = max(3, round(cfg_audio.get("silence_end_ms", 270) / FRAME_MS))
    kw = dict(vad_aggr=cfg_audio.get("vad_aggressiveness", 2),
              max_s=cfg_audio.get("max_utterance_s", 12),
              min_s=cfg_audio.get("min_utterance_s", 0.45),
              silence_end_frames=sil_frames,
              mute=mute)
    if backend == "udp":
        return UdpMic(cfg_audio.get("udp_host", "127.0.0.1"),
                      cfg_audio.get("udp_port", 17890), **kw)
    return LocalMic(device=cfg_audio.get("input_device"), **kw)
