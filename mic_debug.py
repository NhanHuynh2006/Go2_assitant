#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mic_debug.py — GHI LẠI mọi thứ mic robot thu được + LÝ DO vì sao VAD bỏ câu.

Dùng khi: "nói mà robot không nghe gì hết". Thay vì đoán, tool này ghi lại toàn bộ
và chỉ ra chính xác chỗ tắc nằm ở đâu trong chuỗi:

    mic robot → bridge → [khử nhiễu] → cổng biên độ → VAD → gom câu → STT

Với MỖI khung 30ms nó ghi: RMS thô, RMS sau khử nhiễu, nền nhiễu ước lượng,
ngưỡng cổng đang áp, và VAD có coi là tiếng nói không.

CHUẨN BỊ: bridge phải đang chạy, và PHẢI TẮT assistant_realtime.py (nó giữ cổng 17890).

CHẠY:
    python3 mic_debug.py --seconds 25

Trong lúc nó đếm ngược, hãy nói theo yêu cầu trên màn hình (nói gần / xa / to / thường).
Xong nó in bảng chẩn đoán + lưu file để nghe lại:
    mic_debug/raw.wav        — y hệt cái robot gửi về (CHƯA khử nhiễu)
    mic_debug/denoised.wav   — sau khử nhiễu (cái mà VAD/STT thực sự nhìn)
    mic_debug/frames.csv     — số liệu từng khung, mở bằng Excel nếu muốn vẽ
"""

import argparse
import os
import socket
import threading
import time
import wave

import numpy as np

FRAME = 480                     # 30ms @ 16k
OUT = "mic_debug"


def save_wav(path, x_int16, sr=16000):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.asarray(x_int16, dtype=np.int16).tobytes())


def bar(v, lo, hi, width=28):
    if hi <= lo:
        return " " * width
    n = int(np.clip((v - lo) / (hi - lo), 0, 1) * width)
    return "█" * n + "·" * (width - n)


def main():
    p = argparse.ArgumentParser(description="Soi mic robot: vi sao khong nghe duoc")
    p.add_argument("--seconds", type=float, default=25)
    p.add_argument("--port", type=int, default=17890)
    p.add_argument("--config", default="config_robot_mic.yaml")
    p.add_argument("--no-stt", action="store_true")
    p.add_argument("--wav", help="phan tich file wav 16k da ghi san, khong thu moi")
    a = p.parse_args()

    import yaml
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    ca = cfg["audio"]
    gate_rms = float(ca.get("noise_gate_rms", 0))
    gate_fac = float(ca.get("noise_gate_factor", 3.0))
    vad_aggr = int(ca.get("vad_aggressiveness", 2))
    min_s = float(ca.get("min_utterance_s", 0.45))
    sil_ms = float(ca.get("silence_end_ms", 270))

    if a.wav:                       # che do phan tich lai file da co
        w = wave.open(a.wav)
        x_raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        print(f"phan tich lai {a.wav}: {len(x_raw)/16000:.1f}s")
        moc = [(0.0, "toan bo file")]
        return _phan_tich(x_raw, moc, a, cfg, ca, gate_rms, gate_fac,
                          vad_aggr, len(x_raw) / 16000.0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", a.port))
    except OSError as e:
        raise SystemExit(f"khong chiem duoc cong {a.port}: {e}\n"
                         "  -> TAT assistant_realtime.py truoc (no dang giu cong nay).")
    sock.settimeout(0.5)

    raw = []
    run = True

    def rx():
        buf = b""
        while run:
            try:
                d, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            buf += d
            while len(buf) >= FRAME * 2:
                f, buf = buf[:FRAME * 2], buf[FRAME * 2:]
                raw.append(np.frombuffer(f, dtype=np.int16))

    threading.Thread(target=rx, daemon=True).start()

    print(f"⏺  ghi {a.seconds:.0f}s. LAM THEO HUONG DAN ben duoi.\n")
    kich_ban = [
        (0.0,  "…im lặng (đo nền ồn), ĐỪNG nói gì"),
        (5.0,  "NÓI SÁT robot (~20cm), giọng bình thường: 'bạn tên là gì'"),
        (10.0, "NÓI CÁCH ~1 MÉT, giọng bình thường: 'bạn học ở trường nào'"),
        (15.0, "NÓI CÁCH ~1 MÉT, NÓI TO: 'bạn làm được những gì'"),
        (20.0, "NÓI CÁCH ~2 MÉT, NÓI TO: 'đi thẳng ba mét'"),
    ]
    t0 = time.time()
    moc = []
    for t_at, huong in kich_ban:
        if t_at >= a.seconds:
            break
        while time.time() - t0 < t_at:
            time.sleep(0.05)
        moc.append((t_at, huong))
        print(f"  [{t_at:4.0f}s] ▶ {huong}")
    while time.time() - t0 < a.seconds:
        time.sleep(0.1)
    run = False
    time.sleep(0.6)

    if len(raw) < 50:
        raise SystemExit("khong nhan duoc goi UDP nao -> go2_audio_bridge.py chay chua?")

    x_raw = np.concatenate(raw)
    print(f"\n✅ thu duoc {len(x_raw)/16000:.1f}s\n")
    return _phan_tich(x_raw, moc, a, cfg, ca, gate_rms, gate_fac, vad_aggr, a.seconds)


def _phan_tich(x_raw, moc, a, cfg, ca, gate_rms, gate_fac, vad_aggr, tong_s):
    # ---- chay lai DUNG chuoi xu ly cua audio_io ----
    from denoiser import from_config
    import webrtcvad
    den = from_config(ca)
    vad = webrtcvad.Vad(vad_aggr)

    rows = []
    floor = None
    for i in range(0, len(x_raw) - FRAME, FRAME):
        fr = x_raw[i:i + FRAME]
        rms_raw = float(np.sqrt(np.mean(fr.astype(np.float32) ** 2)))
        b = fr.tobytes()
        if den is not None and den.enabled:
            b = den.process_frame(b)
            if not b:
                continue
        fd = np.frombuffer(b, dtype=np.int16)
        rms_dn = float(np.sqrt(np.mean(fd.astype(np.float32) ** 2)))
        # SAO Y NGUYEN _VadSegmenter.feed() trong audio_io.py — neu lech thi chan
        # doan sai. Nen CHI cap nhat khi VAD bao "khong phai tieng noi".
        is_v = vad.is_speech(b, 16000)
        if floor is None:
            floor = rms_dn
        elif not is_v:
            k = 0.05 if rms_dn > floor else 0.3
            floor = (1.0 - k) * floor + k * rms_dn
        thr = max(gate_rms, floor * gate_fac)
        qua = is_v and rms_dn >= thr           # = bien `speech` trong ban that
        rows.append((i / 16000.0, rms_raw, rms_dn, floor, thr, is_v, qua))

    ts = np.array([r[0] for r in rows])
    r_raw = np.array([r[1] for r in rows])
    r_dn = np.array([r[2] for r in rows])
    fl = np.array([r[3] for r in rows])
    th = np.array([r[4] for r in rows])
    vd = np.array([r[5] for r in rows])
    qa = np.array([r[6] for r in rows])

    os.makedirs(OUT, exist_ok=True)
    save_wav(f"{OUT}/raw.wav", x_raw)
    dn2 = from_config(ca)
    y = []
    for i in range(0, len(x_raw) - FRAME, FRAME):
        b = x_raw[i:i + FRAME].tobytes()
        if dn2 is not None and dn2.enabled:
            b = dn2.process_frame(b)
        if b:
            y.append(np.frombuffer(b, dtype=np.int16))
    if y:
        save_wav(f"{OUT}/denoised.wav", np.concatenate(y))
    with open(f"{OUT}/frames.csv", "w") as f:
        f.write("t,rms_raw,rms_denoised,noise_floor,threshold,vad_speech\n")
        for r in rows:
            f.write(f"{r[0]:.3f},{r[1]:.0f},{r[2]:.0f},{r[3]:.0f},{r[4]:.0f},{int(r[5])}\n")

    # ---- bang chan doan theo tung doan kich ban ----
    print("=" * 88)
    print(f"{'đoạn':<34} {'RMS thô':>8} {'sau khử':>8} {'ngưỡng':>8} "
          f"{'lọt cổng':>9} {'VAD nói':>8}")
    print("-" * 88)
    moc2 = moc + [(tong_s, "")]
    for k in range(len(moc)):
        t1, ten = moc2[k][0], moc2[k][1]
        t2 = moc2[k + 1][0]
        m = (ts >= t1 + 0.7) & (ts < t2)      # bỏ 0.7s đầu (lúc đọc hướng dẫn)
        if m.sum() == 0:
            continue
        pct_thr = 100.0 * float(np.mean(qa[m]))   # VAD noi VA vuot nguong
        pct_vad = 100.0 * float(np.mean(vd[m]))
        nhan = ten[:33] if ten else f"{t1:.0f}-{t2:.0f}s"
        print(f"{nhan:<34} {np.percentile(r_raw[m],90):8.0f} "
              f"{np.percentile(r_dn[m],90):8.0f} {np.median(th[m]):8.0f} "
              f"{pct_thr:8.0f}% {pct_vad:7.0f}%")
    print("=" * 88)

    print("\nBIEN DO theo thoi gian (█ = sau khử nhiễu, | = ngưỡng cổng):")
    lo, hi = 0.0, float(max(np.percentile(r_dn, 99), np.median(th) * 2))
    step = max(1, len(rows) // 46)
    for i in range(0, len(rows), step):
        t, _, d, _, tt, v, q = rows[i]
        mark = "|" if d < tt else "█"
        print(f"  {t:5.1f}s {bar(d, lo, hi)} {d:6.0f} "
              f"{'NGUONG=' + str(int(tt)):>12} {'VAD' if v else '   '} "
              f"{'<== TINH LA TIENG NOI' if q else ''}")

    # ---- ket luan ----
    print("\n" + "=" * 88)
    im = (ts < 4.5)
    nen = float(np.percentile(r_dn[im], 50)) if im.sum() else 0.0
    noi = (ts >= 5.7)
    dinh = float(np.percentile(r_dn[noi], 95)) if noi.sum() else 0.0
    print(f"  Nền ồn (lúc im, sau khử) : {nen:.0f}")
    print(f"  Đỉnh lúc bạn nói         : {dinh:.0f}")
    if nen > 0:
        print(f"  => Tỉ số tiếng/ồn        : {dinh/max(nen,1):.1f} lần "
              f"(cần > {gate_fac:.1f} lần mới lọt cổng)")
    print(f"  Cổng đang đòi            : max({gate_rms:.0f}, nền × {gate_fac:.1f})")
    print("=" * 88)
    print(f"\nNGHE LAI:  aplay {OUT}/raw.wav      (robot gửi về, chưa khử nhiễu)")
    print(f"           aplay {OUT}/denoised.wav (cái VAD/STT thực sự nhìn)")

    if not a.no_stt:
        try:
            from stt_transducer import STTTransducer
            s = cfg["stt"]
            stt = STTTransducer(s["transducer_model"],
                                hotwords_file=s.get("hotwords_file"),
                                hotwords_score=s.get("hotwords_score", 3.0))
            print("\nSTT doc CA DOAN (bo qua VAD, xem tai nghe co ra chu khong):")
            for k in range(len(moc)):
                t1 = moc2[k][0]
                t2 = moc2[k + 1][0]
                seg = np.concatenate(y)[int(t1 * 16000):int(t2 * 16000)] if y else None
                if seg is None or seg.size < 8000:
                    continue
                txt, _ = stt.transcribe(seg.astype(np.float32) / 32768.0)
                print(f"   [{t1:4.0f}-{t2:.0f}s] {txt!r}")
        except Exception as e:
            print(f"(bo qua STT: {e})")


if __name__ == "__main__":
    main()
