#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_echo_delay.py — DO độ trễ "Gô nói -> mic Gô nghe lại chính mình", để đặt
`tts.mute_lead_s` / `tts.mute_tail_s` cho ĐÚNG thay vì đoán.

TẠI SAO CẦN: loa robot phát qua WebRTC nên tiếng RA rất trễ, rồi lại vòng về mic
(cũng qua WebRTC). Nếu mở mic lại quá sớm, robot nghe đuôi câu của chính nó ->
STT ra 1-2 chữ -> tự trả lời -> VÒNG LẶP VÔ TẬN. Nhìn vào log thấy toàn câu cụt
kiểu "ĐẤY", "MỘT", "CẢM ƠN" thì gần như chắc chắn là bệnh này, không phải nhiễu.

    |<--- mute_lead --->|<------ dur ------>|<- tail ->|
    gửi câu            tiếng bắt đầu ra    hết tiếng   dự phòng

CHUẨN BỊ (2 tiến trình nền, ĐÚNG THỨ TỰ):
    export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH GO2_IP=192.168.123.161
    python3 go2_tts_speaker.py &          # LOA TRƯỚC, đợi thấy "san sang"
    python3 go2_audio_bridge.py --gain 2.5 &   # MIC SAU
    # (bật ngược lại -> loa chết vì NoSdpAnswerError)

CHẠY (tắt assistant_realtime.py trước, nó giữ cổng 17890):
    python3 test_echo_delay.py
    python3 test_echo_delay.py --repeat 3      # đo 3 lần lấy số ổn định

Xong nó in thẳng dòng config nên dán vào file config.
"""

import argparse
import socket
import threading
import time

import numpy as np

FRAME = 480          # 30ms @16k
PORT_MIC = 17890
VOICE = ("/home/unitree/NhanHuynh/go2_jetson_demo/models/piper/vi/vi_VN/"
         "vais1000/medium/vi_VN-vais1000-medium.onnx")
PIPER = "/home/unitree/piper/piper"


class MicTap:
    """Nghe ké luồng UDP từ go2_audio_bridge.py, ghi lại (thời điểm, RMS)."""

    def __init__(self, port=PORT_MIC):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("127.0.0.1", port))
        except OSError as e:
            raise SystemExit(
                f"khong chiem duoc cong {port}: {e}\n"
                "  -> tat assistant_realtime.py truoc (no dang giu cong nay).")
        self.sock.settimeout(0.5)
        self.frames = []
        self.run = True
        threading.Thread(target=self._rx, daemon=True).start()

    def _rx(self):
        buf = b""
        while self.run:
            try:
                d, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            buf += d
            while len(buf) >= FRAME * 2:
                f, buf = buf[:FRAME * 2], buf[FRAME * 2:]
                x = np.frombuffer(f, dtype=np.int16).astype(np.float32)
                self.frames.append((time.time(), float(np.sqrt(np.mean(x * x)))))

    def stop(self):
        self.run = False
        time.sleep(0.6)


def do_mot_lan(tap, tts, cau, base):
    n0 = len(tap.frames)
    t0 = time.time()
    tts.speak(cau)
    dur = float(getattr(tts, "last_audio_s", 0.0) or 0.0)
    time.sleep(dur + 8)

    seg = tap.frames[n0:]
    thr = max(base * 3.0, base + 300.0)
    on = [t for t, r in seg if r > thr]
    if not on:
        return None
    return {"dur": dur, "lead": on[0] - t0, "end": on[-1] - t0, "thr": thr}


def main():
    p = argparse.ArgumentParser(description="Do tre echo loa robot -> mic robot")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--port", type=int, default=PORT_MIC)
    p.add_argument("--say", default="Xin chào, mình là Gô, "
                                    "con chó bốn chân của phòng thí nghiệm.")
    a = p.parse_args()

    tap = MicTap(a.port)
    print("do nen yen 4s (dung noi gi ca)...")
    time.sleep(4)
    if len(tap.frames) < 50:
        tap.stop()
        raise SystemExit("khong nhan duoc goi UDP nao -> go2_audio_bridge.py "
                         "da chay chua?")
    base = float(np.median([r for _, r in tap.frames[-100:]]))
    print(f"nen on cua robot: RMS {base:.0f}\n")

    from tts_engine import TTS
    tts = TTS(VOICE, output="robot", piper_bin=PIPER)

    ket = []
    for i in range(a.repeat):
        print(f"--- lan {i+1}/{a.repeat}: dang phat & nghe ---")
        r = do_mot_lan(tap, tts, a.say, base)
        if r is None:
            print("   KHONG nghe thay gi -> loa robot co keu that khong? "
                  "(go2_tts_speaker.py con song?)")
            continue
        print(f"   audio dai {r['dur']:.2f}s | bat dau nghe +{r['lead']:.2f}s "
              f"| het +{r['end']:.2f}s")
        ket.append(r)
        time.sleep(1.5)
    tap.stop()

    if not ket:
        raise SystemExit("khong do duoc lan nao.")
    lead = max(r["lead"] for r in ket)
    tail = max(r["end"] - r["lead"] - r["dur"] for r in ket)

    print("\n" + "=" * 62)
    print(f"  TRE KHOI PHAT (lead) : {lead:.2f}s   <- gui xong bao lau moi ra tieng")
    print(f"  DUOI DU     (tail)   : {max(tail, 0):.2f}s")
    print("=" * 62)
    print("\nDan vao khoi `tts:` cua config dang dung:\n")
    print(f"  mute_lead_s: {lead + 0.15:.1f}")
    print(f"  mute_tail_s: {max(tail, 0) + 0.3:.1f}")
    print("\n(De DU ra mot chut con hon bi vong lap tu nghe. Doi lai la cau tra loi "
          "\nke tiep phai cho lau hon mot chut — danh doi xung dang.)")


if __name__ == "__main__":
    main()
