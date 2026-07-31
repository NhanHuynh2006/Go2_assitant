#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_speaker.py — LOA HOI TRUONG cho GoVoice.  ⚠️ CHAY TREN **LAPTOP**, KHONG phai Jetson.

VAN DE: bieu dien truoc hoi nghi dong nguoi thi loa cua con robot qua nho, ma Jetson
trong con Go2 **khong co Bluetooth va khong co jack 3.5** (chi co HDMI). Mua USB BT
dongle thi duoc, nhung Bluetooth trong hoi truong dong nguoi rat de rot ket noi.

CACH NAY KHONG TON TIEN: laptop cua ban DA CO san Bluetooth + jack 3.5 va dang noi
day LAN voi robot. Jetson gui thang audio sang laptop, laptop phat ra loa to.

    JETSON (192.168.123.18)                 LAPTOP (192.168.123.99)
    tts_engine output="pa"  ── TCP :17892 ──► pc_speaker.py
                                                 │
                                                 ▼ dau ra MAC DINH cua laptop
                                        loa Bluetooth  HOAC  day jack 3.5 ra mixer
                                        (chon trong Settings > Sound cua laptop)

CHUAN BI TREN LAPTOP:
  1. Ket noi laptop voi loa hoi truong TRUOC (Bluetooth ghep doi, hoac cam day jack).
  2. Settings > Sound > Output: chon dung loa do. Thu phat nhac cho chac.
  3. pip install sounddevice soundfile      (neu chua co; khong co cung chay duoc,
                                             se tu dung paplay/aplay/ffplay)
  4. python3 pc_speaker.py

TREN JETSON — them vao config dang dung:
    tts:
      output: pa                    # hoac "robot+pa" neu muon ra CA loa robot lan loa to
      pa_host: 192.168.123.99       # IP LAPTOP (doi cho dung)
      pa_port: 17892

KIEM TRA TRUOC BUOI DIEN (chay tren Jetson):
    python3 pc_speaker.py --test 192.168.123.99
"""

import argparse
import io
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import wave

PORT = 17892


# --------------------------------------------------------------- phat tieng
def _play_sounddevice(wav_bytes):
    import numpy as np
    import sounddevice as sd
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    if ch > 1:
        x = x.reshape(-1, ch)
    sd.play(x, sr, blocking=True)


def _play_external(wav_bytes):
    """Du phong: ghi file tam roi goi trinh phat co san cua he thong."""
    path = tempfile.mktemp(suffix=".wav")
    with open(path, "wb") as f:
        f.write(wav_bytes)
    try:
        for cmd in (["paplay", path], ["aplay", "-q", path],
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
            try:
                subprocess.run(cmd, check=True)
                return
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        print("[loa] KHONG co trinh phat nao (paplay/aplay/ffplay) — "
              "cai: sudo apt install pulseaudio-utils")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def play(wav_bytes, gain=1.0):
    if gain != 1.0:
        wav_bytes = _apply_gain(wav_bytes, gain)
    try:
        _play_sounddevice(wav_bytes)
    except Exception:
        _play_external(wav_bytes)


def _apply_gain(wav_bytes, gain):
    import numpy as np
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        p = wf.getparams()
        x = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    y = np.clip(x.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setparams(p)
        wf.writeframes(y.tobytes())
    return out.getvalue()


# --------------------------------------------------------------- may chu
def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        c = conn.recv(min(65536, n - len(buf)))
        if not c:
            return None
        buf += c
    return buf


def serve(host, port, gain):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(8)
    print(f"🔊 LOA HOI TRUONG san sang — dang nghe {host}:{port}")
    print("   Nho: dat dau ra am thanh cua LAPTOP dung vao loa to "
          "(Settings > Sound > Output).")
    print("   Ctrl+C de thoat.\n")

    # hang doi 1 luong phat: cau den lien tiep khong chong tieng len nhau
    lock = threading.Lock()

    def handle(conn, addr):
        try:
            head = recv_exact(conn, 4)
            if not head:
                return
            n = int.from_bytes(head, "big")
            if not (0 < n <= 50 * 1024 * 1024):
                print(f"[loa] do dai la ({n}) tu {addr[0]} -> bo qua")
                return
            data = recv_exact(conn, n)
            if not data:
                print(f"[loa] mat ket noi giua chung tu {addr[0]}")
                return
        finally:
            conn.close()
        secs = 0.0
        try:
            with wave.open(io.BytesIO(data), "rb") as wf:
                secs = wf.getnframes() / float(wf.getframerate() or 1)
        except Exception:
            pass
        print(f"[loa] {time.strftime('%H:%M:%S')} nhan {len(data)/1024:.0f}KB "
              f"({secs:.1f}s) tu {addr[0]} -> phat")
        with lock:
            play(data, gain)

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


# --------------------------------------------------------------- tu kiem tra
def send_test(host, port, text):
    """Chay TREN JETSON: tong hop 1 cau roi ban sang laptop de thu duong truyen."""
    piper = "/home/unitree/piper/piper"
    voice = ("/home/unitree/NhanHuynh/go2_jetson_demo/models/piper/vi/vi_VN/"
             "vais1000/medium/vi_VN-vais1000-medium.onnx")
    f = tempfile.mktemp(suffix=".wav")
    subprocess.run([piper, "-m", voice, "-f", f], input=text.encode(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    data = open(f, "rb").read()
    os.unlink(f)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((host, port))
    s.sendall(len(data).to_bytes(4, "big") + data)
    s.close()
    print(f"✅ da gui {len(data)/1024:.0f}KB sang {host}:{port} — "
          f"LOA HOI TRUONG phai kêu ngay bay gio.")
    print("   Khong nghe gi? -> kiem tra dau ra am thanh cua laptop, "
          "va tuong lua cho phep cong 17892.")


def main():
    p = argparse.ArgumentParser(
        description="Loa hoi truong cho GoVoice (chay tren LAPTOP)")
    p.add_argument("--host", default="0.0.0.0", help="dia chi lang nghe")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--gain", type=float, default=1.0,
                   help="khuech dai them (1.5 neu hoi truong on)")
    p.add_argument("--test", metavar="IP_LAPTOP",
                   help="CHAY TREN JETSON: ban 1 cau thu sang laptop")
    p.add_argument("--say", default="Xin chào hội nghị, tôi là Gô, "
                                    "chó bốn chân của phòng thí nghiệm ISLab.")
    a = p.parse_args()
    if a.test:
        send_test(a.test, a.port, a.say)
        return
    try:
        serve(a.host, a.port, a.gain)
    except KeyboardInterrupt:
        print("\n[loa] dung.")
    except OSError as e:
        sys.exit(f"khong mo duoc cong {a.port}: {e}")


if __name__ == "__main__":
    main()
