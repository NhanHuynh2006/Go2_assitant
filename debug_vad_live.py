#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_vad_live.py — xem TRUC TIEP mic + VAD dang lam gi, dung DUNG code path
nhu LocalMic (audio_io.py) de bat dung nguyen nhan vi sao khong "nghe" duoc cau.

Chay:  python3 debug_vad_live.py [ten_mic]   (mac dinh "CS202"), noi thu ~8s.
In moi frame 30ms: nang luong RMS + VAD co coi la "speech" khong + trang thai recording.
"""
import sys
import time
import collections
import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import resample_poly

SR = 16000
FRAME_MS = 30
FRAME_SAMPLES = SR * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2

device = sys.argv[1] if len(sys.argv) > 1 else "CS202"
vad = webrtcvad.Vad(2)

di = sd.query_devices(device, "input")
cap_sr = int(round(di.get("default_samplerate") or SR))
down = cap_sr // SR if cap_sr % SR == 0 else 1
blocksize = FRAME_SAMPLES * down
print(f"[info] device={device!r}  cap_sr={cap_sr}  down={down}  blocksize={blocksize}")

ring = collections.deque(maxlen=10)
recording = False
silence = 0
t_start = time.time()
n = 0

with sd.RawInputStream(samplerate=cap_sr, blocksize=blocksize, dtype="int16",
                       channels=1, device=device) as stream:
    print(">>> NOI THU trong ~8 giay (Ctrl+C de dung som)...")
    while time.time() - t_start < 8:
        data, overflow = stream.read(blocksize)
        x = np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32)
        if down > 1:
            y = resample_poly(x, SR, cap_sr)
            frame = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
        else:
            frame = bytes(data)
        if len(frame) != FRAME_BYTES:
            print(f"  [!] frame size sai: {len(frame)} != {FRAME_BYTES} (bo qua)")
            continue
        rms = float(np.sqrt(np.mean((np.frombuffer(frame, dtype=np.int16).astype(np.float32))**2)))
        try:
            speech = vad.is_speech(frame, SR)
        except Exception as e:
            speech = False
            print("  [!] vad loi:", e)

        if not recording:
            ring.append(speech)
            voiced = sum(ring)
            tag = "RING" if len(ring) < ring.maxlen else ("TRIGGER!" if voiced >= 0.6*ring.maxlen else "ring")
            if n % 3 == 0 or speech:
                print(f"  t={time.time()-t_start:4.1f}s rms={rms:6.0f} speech={speech}  {tag}({voiced}/{len(ring)})")
            if len(ring) == ring.maxlen and voiced >= 0.6 * ring.maxlen:
                recording = True
                ring.clear()
                silence = 0
                print("  >>> BAT DAU GHI CAU (recording=True)")
        else:
            silence = 0 if speech else silence + 1
            print(f"  t={time.time()-t_start:4.1f}s rms={rms:6.0f} speech={speech}  RECORDING silence={silence}/9")
            if silence >= 9:
                print("  >>> KET THUC CAU (utterance yielded!) <<<")
                recording = False
        n += 1

print("\n[done] neu KHONG thay 'BAT DAU GHI CAU' -> VAD khong nhan dien duoc giong noi (rms qua thap hoac vad qua khat khe)")
print("       neu thay 'BAT DAU GHI' nhung KHONG thay 'KET THUC CAU' -> khong bao gio im du lau de cat cau")
