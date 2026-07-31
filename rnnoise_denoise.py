#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rnnoise_denoise.py — KHU NHIEU giong noi thoi gian thuc bang RNNoise.

RNNoise (xiph.org) = mang RNN nho + xu ly tin hieu co dien, huan luyen san tren
hang ngan gio nhieu -> khong can biet truoc loai nhieu. Chay o 48kHz, khung 480
mau (10ms), nhe (chay realtime tot tren Jetson/Pi). Dung librnnoise.so (lay tu goi
pip 'pyrnnoise', da copy vao du an cho doc lap voi cach import cua goi do).

Vi tri cam trong pipeline: mic 48kHz -> RNNoise (o 48k) -> resample 16k -> VAD -> STT.

Dung (streaming):
    dn = RnnoiseDenoiser(mix=1.0)
    clean48 = dn.process(x48_int16)      # cung do dai (tre toi da 1 khung 480)

mix (0..1): 1.0 = RNNoise thuan (khu manh nhat). <1.0 = tron lai 1 phan TIN HIEU
    GOC de tranh RNNoise "cat lem" giong (vd 0.85 giu 15% goc). Dung khi so mat chu.
"""
import ctypes
import os

import numpy as np

_SO_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "librnnoise.so"),
    "/home/unitree/.local/lib/python3.8/site-packages/pyrnnoise/librnnoise.so",
]


def _load_lib():
    last = None
    for p in _SO_CANDIDATES:
        if os.path.exists(p):
            lib = ctypes.CDLL(p)
            lib.rnnoise_create.argtypes = [ctypes.c_void_p]
            lib.rnnoise_create.restype = ctypes.c_void_p
            lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
            lib.rnnoise_get_frame_size.restype = ctypes.c_int
            lib.rnnoise_process_frame.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
            ]
            lib.rnnoise_process_frame.restype = ctypes.c_float
            return lib
        last = p
    raise OSError(f"khong tim thay librnnoise.so (vd: {last})")


class RnnoiseDenoiser:
    """Khu nhieu 48kHz int16 theo tung khoi (streaming). An toan: loi -> tra nguyen goc."""

    SAMPLE_RATE = 48000

    def __init__(self, mix: float = 1.0):
        self.lib = _load_lib()
        self.frame = int(self.lib.rnnoise_get_frame_size())     # 480 @48k
        self.state = self.lib.rnnoise_create(None)
        self.mix = max(0.0, min(1.0, float(mix)))
        self._buf = np.empty(0, dtype=np.int16)                 # phan du chua du 1 khung
        self.last_prob = 0.0

    def process(self, x_int16: np.ndarray) -> np.ndarray:
        """Nhan mau 48kHz int16 -> tra ve int16 da khu nhieu.

        Che theo boi so 480; phan du giu lai cho lan sau (tre <= 1 khung ~10ms).
        Mic doc block 1440 mau (30ms) = boi so cua 480 -> thuc te khong tre.
        """
        x = np.asarray(x_int16, dtype=np.int16)
        buf = np.concatenate([self._buf, x]) if self._buf.size else x
        n = (len(buf) // self.frame) * self.frame
        if n == 0:
            self._buf = buf.copy()
            return np.empty(0, dtype=np.int16)
        wet = buf[:n].astype(np.float32).copy()
        try:
            for i in range(0, n, self.frame):
                seg = wet[i:i + self.frame].copy()
                ptr = seg.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                self.last_prob = float(self.lib.rnnoise_process_frame(self.state, ptr, ptr))
                wet[i:i + self.frame] = seg
        except Exception:
            return buf[:n]                                       # loi -> nguyen goc, khoi vo tieng
        self._buf = buf[n:].copy()
        if self.mix < 1.0:
            dry = buf[:n].astype(np.float32)
            wet = self.mix * wet + (1.0 - self.mix) * dry
        return np.clip(wet, -32768, 32767).astype(np.int16)

    def close(self):
        try:
            self.lib.rnnoise_destroy(self.state)
        except Exception:
            pass


if __name__ == "__main__":
    # Test nhanh: khu nhieu 1 file wav 48kHz -> in muc RMS truoc/sau
    import sys
    import wave
    dn = RnnoiseDenoiser(mix=float(sys.argv[2]) if len(sys.argv) > 2 else 1.0)
    w = wave.open(sys.argv[1])
    assert w.getframerate() == 48000, "can file 48kHz"
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    y = dn.process(x)
    r = lambda a: float(np.sqrt(np.mean(a.astype(np.float32) ** 2)))
    print(f"RMS: truoc {r(x):.0f} -> sau {r(y):.0f} | frame_size={dn.frame}")
