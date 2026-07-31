#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
go2_troupe.py — ĐOÀN MÚA: cho NHIỀU con Go2 nhảy CÙNG MỘT BÀI, KHỚP NHỊP.

Bài toán: 2 con chó, 2 Jetson riêng, mỗi con một mạng LAN 192.168.123.x RIÊNG
(bridge chung là ĐỤNG IP: cả hai main board đều .161, cả hai Jetson đều .18).
Cắm USB WiFi cho mỗi Jetson -> cả hai có thêm 1 địa chỉ trên CÙNG một wifi ->
nói chuyện được với nhau. Xem HAI_CON_CHO.md.

    ROUTER WIFI 5GHz
      │        │              │
   ┌──┴───┐ ┌──┴───┐   ┌──────┴──────┐
   │CHÓ A │ │CHÓ B │   │   LAPTOP    │
   │agent │ │agent │   │  conduct    │──► nhạc ra LOA HỘI TRƯỜNG
   └──────┘ └──────┘   └─────────────┘

VÌ SAO NHẠC PHÁT TỪ LAPTOP CHỨ KHÔNG TỪ LOA CHÓ:
  Loa chó nhỏ, và 2 con phát cùng lúc thì lệch nhau vài trăm ms -> nghe dội như
  vọng âm. Một nguồn nhạc duy nhất (loa hội trường) vừa to vừa hết lệch. Hai con
  chỉ việc NHẢY theo cùng một bản đồ beat đã tính sẵn.

ĐỒNG BỘ ĐỒNG HỒ: KHÔNG cần internet/NTP. Nhạc trưởng đo độ lệch đồng hồ với từng
con bằng bắt tay kiểu SNTP (T1..T4, lấy mẫu RTT nhỏ nhất), rồi ra lệnh "khởi động
lúc <giờ RIÊNG của mày>". Sai số thực đo trên wifi: vài ms.

------------------------------------------------------------------------------
CHẠY — TRÊN MỖI CON CHÓ (mỗi Jetson một lần):
    export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
    export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds
    python3 go2_troupe.py agent --name A          # con kia: --name B

CHẠY — TRÊN LAPTOP (nhạc trưởng):
    python3 go2_troupe.py conduct \
        --robots 10.42.0.11,10.42.0.12 \
        --music ~/dance.mp3 --play-here

DIỄN TẬP KHÔNG CẦN CHÓ (kiểm tra sai số đồng bộ):
    python3 go2_troupe.py agent --name A --port 18800 --dry &
    python3 go2_troupe.py agent --name B --port 18801 --dry &
    python3 go2_troupe.py conduct --robots 127.0.0.1:18800,127.0.0.1:18801 \
        --music ~/dance.mp3 --dry
------------------------------------------------------------------------------
⚠️ AN TOÀN: tắt app Unitree; mỗi con ≥2×2m riêng (≥3×3m nếu --special/--stunts);
   pin ≥60%; MỖI CON một người cầm remote (L2+B dừng khẩn).
"""

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import threading
import time

PORT = 18800
PROTO = 1

_real_clock = time.time      # giu tham chieu dong ho THAT (truoc khi --clock-skew de len)


# ============================================================ khung tin nhắn
def send_msg(sock, obj):
    """1 tin nhắn = 1 dòng JSON. Đơn giản, dễ soi bằng mắt khi sự cố trên sân khấu."""
    sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))


class LineReader:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def recv(self, timeout=None):
        self.sock.settimeout(timeout)
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                return None
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))


# ============================================================ PHÍA CON CHÓ
class Dancer:
    """Điều khiển SportClient của CHÍNH con chó này (qua LAN nội bộ .123.x)."""

    def __init__(self, dry=False, iface=None):
        self.dry = dry
        self.iface = iface or os.environ.get("GO2_IFACE", "eth0")
        self.sport = None

    def connect(self):
        if self.dry:
            print("[nhay] CHE DO DIEN TAP (--dry): khong dung toi robot")
            return
        os.environ.setdefault(
            "CYCLONEDDS_HOME",
            os.path.expanduser("/home/unitree/cyclonedds_ws/install/cyclonedds"))
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.go2.sport.sport_client import SportClient
        ChannelFactoryInitialize(0, self.iface)
        self.sport = SportClient()
        self.sport.SetTimeout(10.0)
        self.sport.Init()

    def stand(self):
        if self.dry:
            time.sleep(0.5)
            return
        self.sport.StandUp()
        time.sleep(2)
        self.sport.BalanceStand()
        time.sleep(1)

    def rest(self):
        if self.dry:
            return
        try:
            self.sport.StopMove()
            self.sport.BalanceStand()
            time.sleep(1)
            self.sport.StandDown()
        except Exception:
            pass

    def dance(self, beats, t_start, opts, stop_flag):
        """Nhảy theo bản đồ beat. t_start = giờ ĐỊA PHƯƠNG của máy này (time.time()).

        `phase` cho phép 2 con nhảy LỆCH PHA nhau (đối xứng, nhìn đẹp hơn là
        y hệt nhau): phase=0 con A, phase=1 con B -> động tác nhấn so le.
        """
        latency = float(opts.get("latency", 0.15))
        special = bool(opts.get("special"))
        stunts = bool(opts.get("stunts"))
        phase = int(opts.get("phase", 0))
        s = self.sport
        accents = [] if self.dry else [s.Hello, s.Heart, s.Stretch]

        done = 0
        for i, bt in enumerate(beats):
            if stop_flag.is_set():
                break
            dt = (t_start + bt - latency) - time.time()
            if dt > 0:
                time.sleep(dt)
            elif dt < -0.35:
                continue                      # trễ quá thì bỏ beat, khỏi dồn cục
            done += 1
            if self.dry:
                continue
            try:
                k = i + phase * 8             # lệch pha giữa 2 con
                if stunts and i > 0 and i % 64 == 0:
                    if (k // 64) % 2 == 0:
                        s.WalkUpright(True); time.sleep(3); s.WalkUpright(False)
                    else:
                        s.HandStand(True); time.sleep(3); s.HandStand(False)
                    time.sleep(1); s.BalanceStand(); time.sleep(1)
                elif special and i > 0 and i % 32 == 0:
                    (s.Dance1 if (k // 32) % 2 == 0 else s.Dance2)()
                    s.BalanceStand()
                elif i > 0 and i % 16 == 0:
                    accents[(k // 16) % len(accents)]()
                    s.BalanceStand()
                else:
                    sgn = 1.0 if phase == 0 else -1.0      # 2 con lắc ngược chiều
                    s.Euler(sgn * 0.20 * math.sin(i * 0.9),
                            0.12 * math.cos(i * 0.7),
                            sgn * 0.18 * math.sin(i * 0.5))
            except Exception as e:
                print(f"[nhay] loi beat {i}: {e}")
        return done


def run_agent(name, host, port, dry, iface, clock_skew=0.0):
    """Chạy trên Jetson của MỖI con chó. Chờ nhạc trưởng sai bảo.

    clock_skew (chỉ để DIỄN TẬP): giả vờ đồng hồ máy này lệch N giây, để kiểm
    chứng phần bù lệch có thật sự hoạt động. Ngoài đời không dùng.
    """
    if clock_skew:
        real_time = time.time
        time.time = lambda: real_time() + clock_skew        # noqa: F811
        print(f"[{name}] ⚠️ DIEN TAP: gia vo dong ho lech {clock_skew:+.3f}s")
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(4)
    print(f"🐕 CHO '{name}' san sang — nghe tai {host}:{port}"
          f"{' [DIEN TAP]' if dry else ''}")
    print("   Cho nhac truong ket noi. Ctrl+C de thoat.\n")

    dancer = Dancer(dry=dry, iface=iface)
    stop_flag = threading.Event()

    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"[{name}] nhac truong {addr[0]} da ket noi")
        rd = LineReader(conn)
        stop_flag.clear()
        beats, opts = [], {}
        try:
            while True:
                msg = rd.recv(timeout=600)
                if msg is None:
                    break
                cmd = msg.get("cmd")

                if cmd == "ping":
                    # SNTP: t2 = lúc nhận, t3 = lúc trả lời (giờ ĐỊA PHƯƠNG)
                    t2 = time.time()
                    send_msg(conn, {"cmd": "pong", "t1": msg["t1"],
                                    "t2": t2, "t3": time.time()})

                elif cmd == "prepare":
                    beats = msg["beats"]
                    opts = msg.get("opts", {})
                    print(f"[{name}] nhan {len(beats)} beat, pha={opts.get('phase')} "
                          f"-> dung day...")
                    try:
                        dancer.connect()
                        dancer.stand()
                        send_msg(conn, {"cmd": "ready", "name": name})
                        print(f"[{name}] SAN SANG")
                    except Exception as e:
                        send_msg(conn, {"cmd": "error", "name": name, "msg": str(e)})
                        print(f"[{name}] LOI chuan bi: {e}")

                elif cmd == "go":
                    t_local = float(msg["t_local"])
                    wait = t_local - time.time()
                    print(f"[{name}] KHOI DIEN sau {wait*1000:.0f}ms "
                          f"(gio dia phuong {t_local:.3f})")
                    if wait > 0:
                        time.sleep(wait)
                    t_real = _real_clock()
                    print(f"[{name}] BAT DAU THAT luc {t_real:.4f} (dong ho THAT)")
                    n = dancer.dance(beats, t_local, opts, stop_flag)
                    print(f"[{name}] xong {n} beat")
                    dancer.rest()
                    send_msg(conn, {"cmd": "done", "name": name, "beats": n})

                elif cmd == "stop":
                    stop_flag.set()
                    print(f"[{name}] DUNG theo lenh")

                elif cmd == "bye":
                    break
        except (ConnectionError, socket.timeout, json.JSONDecodeError) as e:
            print(f"[{name}] mat ket noi: {e}")
            stop_flag.set()
            dancer.rest()
        finally:
            conn.close()
            print(f"[{name}] cho nhac truong lan sau...\n")


# ============================================================ PHÍA NHẠC TRƯỞNG
class Robot:
    def __init__(self, addr):
        host, _, port = addr.partition(":")
        self.host = host
        self.port = int(port or PORT)
        self.name = addr
        self.sock = None
        self.rd = None
        self.offset = 0.0     # giờ_nó - giờ_mình (giây)
        self.rtt = 0.0
        self.ready = False

    def connect(self, timeout=8.0):
        self.sock = socket.create_connection((self.host, self.port), timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.rd = LineReader(self.sock)

    def measure_offset(self, rounds=15):
        """SNTP: lấy mẫu có RTT NHỎ NHẤT — mẫu đó ít bị wifi làm nhiễu nhất."""
        best = None
        for _ in range(rounds):
            t1 = time.time()
            send_msg(self.sock, {"cmd": "ping", "t1": t1})
            m = self.rd.recv(timeout=5)
            t4 = time.time()
            if not m or m.get("cmd") != "pong":
                continue
            rtt = (t4 - t1) - (m["t3"] - m["t2"])
            off = ((m["t2"] - t1) + (m["t3"] - t4)) / 2.0
            if best is None or rtt < best[0]:
                best = (rtt, off)
            time.sleep(0.02)
        if best is None:
            raise RuntimeError(f"{self.name}: khong do duoc lech dong ho")
        self.rtt, self.offset = best
        return self.rtt, self.offset


def detect_beats(path):
    import librosa
    print(f"[nhac] phan tich beat: {os.path.basename(path)} ...")
    y, sr = librosa.load(path, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = [float(t) for t in librosa.frames_to_time(frames, sr=sr)]
    dur = float(librosa.get_duration(y=y, sr=sr))
    print(f"[nhac] ~{float(tempo):.0f} BPM · {len(beats)} beat · dai {dur:.1f}s")
    return beats, dur


def play_local(path):
    """Phát nhạc ở MÁY NÀY (laptop) -> ra loa hội trường."""
    for cmd in (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                ["paplay", path], ["aplay", "-q", path], ["mpv", "--no-video", path]):
        try:
            return subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            continue
    print("[nhac] ⚠️ khong co trinh phat (ffplay/paplay/aplay/mpv) -> KHONG co nhac")
    return None


def run_conduct(addrs, music, opts, lead_s, play_here, dry):
    beats, dur = detect_beats(music)

    robots = [Robot(a) for a in addrs]
    for i, r in enumerate(robots):
        print(f"[dan] ket noi {r.name} ...", end=" ", flush=True)
        r.connect()
        print("OK")
        o = dict(opts)
        o["phase"] = i                       # con thu 2 nhảy lệch pha
        send_msg(r.sock, {"cmd": "prepare", "beats": beats, "opts": o})

    print("\n[dan] cho tat ca dung day...")
    for r in robots:
        m = r.rd.recv(timeout=60)
        if not m or m.get("cmd") != "ready":
            sys.exit(f"❌ {r.name} khong san sang: {m}")
        r.ready = True
        print(f"   ✅ {r.name} san sang")

    print("\n[dan] do lech dong ho...")
    for r in robots:
        rtt, off = r.measure_offset()
        print(f"   {r.name}: RTT {rtt*1000:6.2f}ms | lech {off*1000:+8.2f}ms")

    worst = max(r.rtt for r in robots) / 2.0
    print(f"\n[dan] sai so dong bo du kien: ~{worst*1000:.1f}ms "
          f"({'TOT' if worst < 0.02 else 'HOI CAO — wifi yeu?'})")

    t_go = time.time() + lead_s
    for r in robots:
        send_msg(r.sock, {"cmd": "go", "t_local": t_go + r.offset})
    print(f"\n>>> KHOI DIEN sau {lead_s:.1f}s <<<")

    proc = None
    if play_here and not dry:
        time.sleep(max(0.0, t_go - time.time()))
        proc = play_local(music)
    elif play_here:
        time.sleep(max(0.0, t_go - time.time()))
        print("[nhac] (dien tap: bo qua phat nhac)")

    print(">>> DANG DIEN <<<  (Ctrl+C de dung khan)")
    try:
        for r in robots:
            m = r.rd.recv(timeout=dur + 90)
            print(f"   🏁 {r.name}: {m}")
    except KeyboardInterrupt:
        print("\n[dan] DUNG KHAN — bao ca doan")
        for r in robots:
            try:
                send_msg(r.sock, {"cmd": "stop"})
            except Exception:
                pass
    finally:
        if proc:
            proc.terminate()
        for r in robots:
            try:
                send_msg(r.sock, {"cmd": "bye"})
                r.sock.close()
            except Exception:
                pass
    print("\n>>> HET TIET MUC <<<")


# ============================================================ CLI
def main():
    p = argparse.ArgumentParser(description="Cho NHIEU con Go2 nhay khop nhip.")
    sub = p.add_subparsers(dest="role", required=True)

    a = sub.add_parser("agent", help="chay tren Jetson CUA MOI CON CHO")
    a.add_argument("--name", default="A")
    a.add_argument("--host", default="0.0.0.0")
    a.add_argument("--port", type=int, default=PORT)
    a.add_argument("--iface", default=None, help="iface DDS toi robot (mac dinh eth0)")
    a.add_argument("--dry", action="store_true", help="dien tap, khong dung toi robot")
    a.add_argument("--clock-skew", type=float, default=0.0,
                   help="CHI DE DIEN TAP: gia vo dong ho may nay lech N giay")

    c = sub.add_parser("conduct", help="chay tren LAPTOP (nhac truong)")
    c.add_argument("--robots", required=True,
                   help="danh sach IP[:port] cach nhau dau phay")
    c.add_argument("--music", required=True)
    c.add_argument("--play-here", action="store_true",
                   help="phat nhac o may nay -> LOA HOI TRUONG (nen dung)")
    c.add_argument("--latency", type=float, default=0.15)
    c.add_argument("--special", action="store_true")
    c.add_argument("--stunts", action="store_true")
    c.add_argument("--lead", type=float, default=3.0, help="dem nguoc truoc khi dien")
    c.add_argument("--dry", action="store_true")

    args = p.parse_args()
    if args.role == "agent":
        try:
            run_agent(args.name, args.host, args.port, args.dry, args.iface,
                      args.clock_skew)
        except KeyboardInterrupt:
            print("\n[agent] thoat.")
    else:
        if not os.path.isfile(args.music):
            sys.exit(f"khong thay file nhac: {args.music}")
        opts = {"latency": args.latency, "special": args.special,
                "stunts": args.stunts}
        run_conduct([x.strip() for x in args.robots.split(",") if x.strip()],
                    args.music, opts, args.lead, args.play_here, args.dry)


if __name__ == "__main__":
    main()
