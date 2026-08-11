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
        self.sport.SetTimeout(0.3)   # xem ghi chu trong go2_choreo.py: 10s = treo 10s khi rot phan hoi
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


def run_choreo(choreo, opts, t_local, dancer, stop_flag=None):
    """Diễn theo KỊCH BẢN của go2_choreo.py thay vì công thức "cứ N beat".

    Nhạc trưởng gửi nguyên cả kịch bản (đã phân tích phổ năng lượng bài nhạc từ
    trước), nên hai con dùng CHUNG một bản — khỏi lo mỗi con tự phân tích ra một
    kiểu. Ở đây chỉ việc chạy đúng phần vai của mình, lấy `t_local` (giờ địa
    phương đã bù lệch đồng hồ) làm giây 0 của bài.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "go2_audio"))
    import go2_choreo
    # KIEU SHOW: chay ban sao cua go2_show.py tren ca hai con.
    #
    # Chon o day chu khong o `go2_choreo.run` vi day la hai vong lap khac han
    # nhau: ban kich ban ban dong tac theo MOC GIAY da bien dao san, con ban
    # show quyet dinh theo CHI SO BEAT (i%16 / i%32 / i%64). Ban show tu dong
    # bo: cung `beat_times` + cung `t_local` la ra cung mot chuoi.
    if opts.get("kieu_show"):
        # Truyen qua bien moi truong vi go2_choreo doc no luc nap module.
        if opts.get("nhan"):
            go2_choreo.TEN_NHAN = [x.strip() for x in opts["nhan"].split(",")
                                   if x.strip()]
        if opts.get("cat_dance") is not None:
            os.environ["GO2_CAT_DANCE"] = str(opts["cat_dance"])
            go2_choreo.CAT_DANCE = float(opts["cat_dance"])
        return go2_choreo.run_show(
            choreo, opts["role"], latency=opts.get("latency", 0.15),
            dry=dancer.dry, iface=dancer.iface, t0=t_local,
            stunts=opts.get("stunts", True), special=opts.get("special", True),
            quiet=opts.get("quiet", True), already_up=not dancer.dry,
            stop_flag=stop_flag)
    go2_choreo.run(choreo, opts["role"], latency=opts.get("latency", 0.15),
                   dry=dancer.dry, iface=dancer.iface, t0=t_local,
                   travel=opts.get("travel", 1.0),
                   leash=opts.get("leash", go2_choreo.LEASH_R),
                   quiet=opts.get("quiet", True),
                   # `prepare` đã cho robot đứng dậy rồi. Không báo cho
                   # go2_choreo biết thì nó đứng dậy LẦN NỮA, tốn thêm 3 giây —
                   # và 3 giây đó rơi vào SAU khi nhạc đã bắt đầu, nên mất đúng
                   # đoạn mở bài (robot đứng ngơ rồi mới nhún).
                   already_up=not dancer.dry,
                   recenter=opts.get("recenter", True),
                   # ⚠️ PHAI TRUYEN stop_flag. Thieu no thi vong nhay ben
                   # go2_choreo khong co cach nao biet la da co lenh dung, va
                   # con cho cu nhay het bai du nhac truong da tat tu lau.
                   stop_flag=stop_flag)
    return len(choreo["parts"][opts["role"]])


def _canh_ket_noi(conn, stop_flag, ten):
    """Canh chung: nhac truong dut ket noi thi bat `stop_flag`.

    ⚠️ VI SAO CAN. Trong luc dien, agent nam TRON trong `run_choreo` — no khong
    doc socket duoc, nen lenh "stop" gui toi cung khong ai nghe. Duong dung duy
    nhat truoc day la `dien.sh` SSH sang tung con `kill -INT`, ma duong do phu
    thuoc wifi: rot mang mot cai la hai con nhay het bai trong khi nguoi dung da
    bam Ctrl+C tu lau va dang dung nhin.
    Doc mot byte kieu PEEK: khong lay mat du lieu cua ai, chi de biet dau ben kia
    con song hay khong. recv tra b"" = da dong.

    Tra ve mot Event — `set()` no de bao canh xong (khi bai ket thuc binh thuong).
    """
    xong = threading.Event()

    def _canh():
        while not xong.is_set() and not stop_flag.is_set():
            try:
                if not conn.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT):
                    print(f"[{ten}] MAT KET NOI toi nhac truong -> dung ngay")
                    stop_flag.set()
                    return
            except BlockingIOError:
                pass                      # con song, chua co gi de doc
            except OSError:
                print(f"[{ten}] socket hong -> dung ngay")
                stop_flag.set()
                return
            time.sleep(0.2)

    th = threading.Thread(target=_canh, daemon=True)
    th.start()
    return xong


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
    # ⚠️ Hang doi 4 la QUA IT. Moi cu do cong (hoac lan chay truoc chet nua
    # chung) deu chiem mot cho; day len la nhac truong THAT ket noi vao se bi
    # HET GIO — dung loi da gap: agent van song, cong van mo, ma conduct bao
    # TimeoutError.
    srv.listen(32)
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
        da_bat_tay = False          # da nhan duoc tin nhan hop le nao chua
        beats, opts = [], {}
        try:
            while True:
                # ⚠️ Tin nhan DAU TIEN phai toi nhanh (nhac truong gui `prepare`
                # ngay sau khi ket noi). Cho 600s ngay tu dau nghia la: chi can
                # MOT ket noi rac (phep do cong, lan chay truoc dut giua chung)
                # la agent ngoi im 10 PHUT, khong accept ai nua — nhac truong
                # that ket noi vao chi con nuoc het gio.
                # Sau khi da bat tay xong thi moi cho lau, vi con doi nguoi bam
                # Enter (MC gioi thieu bao lau khong biet truoc).
                msg = rd.recv(timeout=(600 if da_bat_tay else 15))
                if msg is None:
                    break
                cmd = msg.get("cmd")
                da_bat_tay = True

                if cmd == "ping":
                    # SNTP: t2 = lúc nhận, t3 = lúc trả lời (giờ ĐỊA PHƯƠNG)
                    t2 = time.time()
                    send_msg(conn, {"cmd": "pong", "t1": msg["t1"],
                                    "t2": t2, "t3": time.time()})

                elif cmd == "prepare":
                    beats = msg.get("beats", [])
                    opts = msg.get("opts", {})
                    choreo = msg.get("choreo")        # kịch bản từ go2_choreo.py
                    if choreo:
                        print(f"[{name}] nhan KICH BAN vai {opts.get('role')} "
                              f"({len(choreo['parts'][opts['role']])} cue) -> dung day...")
                    else:
                        print(f"[{name}] nhan {len(beats)} beat, "
                              f"pha={opts.get('phase')} -> dung day...")
                    try:
                        dancer.connect()
                        # ⚠️ KHÔNG cho đứng dậy ở đây khi diễn thật.
                        # Trên sân khấu, người ta điều khiển chó đi lên trước rồi
                        # mới chạy lệnh; MC còn giới thiệu vài phút. Nếu `prepare`
                        # cho đứng dậy luôn thì chó đứng chôn chân suốt lúc MC nói
                        # — vừa tốn pin vừa lộ. Giờ chỉ nối SportClient; đứng dậy
                        # để dành cho lệnh `stand` (bấm Enter mới gửi).
                        if opts.get("stand_now", True):
                            dancer.stand()
                        send_msg(conn, {"cmd": "ready", "name": name})
                        print(f"[{name}] SAN SANG"
                              + ("" if opts.get("stand_now", True) else " (chua dung day — cho lenh)"))
                    except Exception as e:
                        send_msg(conn, {"cmd": "error", "name": name, "msg": str(e)})
                        print(f"[{name}] LOI chuan bi: {e}")

                elif cmd == "stand":
                    # Đứng dậy NGAY (không canh giờ). Gửi khi người điều khiển đã
                    # bấm Enter; xong xuôi mới tính mốc khởi diễn cho cả hai con.
                    try:
                        print(f"[{name}] dung day...")
                        dancer.stand()
                        send_msg(conn, {"cmd": "stood", "name": name})
                        print(f"[{name}] DA DUNG")
                    except Exception as e:
                        send_msg(conn, {"cmd": "error", "name": name, "msg": str(e)})

                elif cmd == "go":
                    t_local = float(msg["t_local"])
                    wait = t_local - time.time()
                    print(f"[{name}] KHOI DIEN sau {wait*1000:.0f}ms "
                          f"(gio dia phuong {t_local:.3f})")
                    if wait > 0:
                        time.sleep(wait)
                    t_real = _real_clock()
                    print(f"[{name}] BAT DAU THAT luc {t_real:.4f} (dong ho THAT)")
                    if choreo:
                        # Canh cua so trong luc dang nhay: nhac truong tat
                        # (Ctrl+C tren laptop) thi socket dut -> bat stop_flag.
                        canh = _canh_ket_noi(conn, stop_flag, name)
                        try:
                            n = run_choreo(choreo, opts, t_local, dancer,
                                           stop_flag=stop_flag)
                        finally:
                            canh.set()
                        dancer.rest()
                    else:
                        n = dancer.dance(beats, t_local, opts, stop_flag)
                        dancer.rest()
                    print(f"[{name}] xong {n} beat")
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

    def measure_offset(self, rounds=20, can_it_nhat=3):
        """SNTP: lấy mẫu có RTT NHỎ NHẤT — mẫu đó ít bị wifi làm nhiễu nhất.

        ⚠️ MỘT GÓI MẤT KHÔNG ĐƯỢC PHÉP LÀM SẬP BUỔI DIỄN.
        Bản cũ gọi `recv(timeout=5)` trần: chỉ cần MỘT lần không có hồi đáp là
        ném TimeoutError ra ngoài và cả tiết mục dừng — đã xảy ra thật, đúng lúc
        wifi xấu (RTT vọt từ 0.3ms lên 31ms). Trên sân khấu thì đó là hỏng cả
        chương trình chỉ vì một gói tin.
        Giờ: gói nào mất thì bỏ qua gói đó, thử tiếp; chỉ báo lỗi khi KHÔNG thu
        nổi `can_it_nhat` mẫu tốt trong toàn bộ số vòng.
        """
        best = None
        tot = 0
        for _ in range(rounds):
            try:
                t1 = time.time()
                send_msg(self.sock, {"cmd": "ping", "t1": t1})
                m = self.rd.recv(timeout=2.0)
                t4 = time.time()
            except (socket.timeout, TimeoutError, OSError):
                continue                      # gói này mất -> thử gói sau
            if not m or m.get("cmd") != "pong":
                continue
            rtt = (t4 - t1) - (m["t3"] - m["t2"])
            off = ((m["t2"] - t1) + (m["t3"] - t4)) / 2.0
            tot += 1
            if best is None or rtt < best[0]:
                best = (rtt, off)
            time.sleep(0.02)
        if best is None or tot < can_it_nhat:
            raise RuntimeError(
                f"{self.name}: chi thu duoc {tot} mau dong ho (can >={can_it_nhat}). "
                f"Wifi qua yeu -> dua router lai gan, hoac doi kenh 5GHz.")
        if tot < rounds // 2:
            print(f"   ⚠️ {self.name}: mat {rounds - tot}/{rounds} goi — wifi yeu, "
                  f"nen kiem tra truoc khi dien that")
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


def run_conduct(addrs, music, opts, lead_s, play_here, dry, choreo_path=None,
                nhac_robot=None, nhac_jetson=None,
                wait_enter=False):
    choreo = None
    if choreo_path:
        with open(choreo_path, encoding="utf-8") as f:
            choreo = json.load(f)
        dur = float(choreo["duration"])
        roles = sorted(choreo["parts"])
        print(f"[nhac] dung KICH BAN {os.path.basename(choreo_path)} — "
              f"{choreo['tempo']:.0f} BPM · {dur:.0f}s · vai: {', '.join(roles)}")
        if len(addrs) > len(roles):
            sys.exit(f"kich ban chi co {len(roles)} vai ({', '.join(roles)}) "
                     f"nhung co {len(addrs)} con")
        beats = []
    else:
        beats, dur = detect_beats(music)
        roles = []

    robots = [Robot(a) for a in addrs]
    for i, r in enumerate(robots):
        print(f"[dan] ket noi {r.name} ...", end=" ", flush=True)
        r.connect()
        print("OK")
        o = dict(opts)
        o["phase"] = i                       # con thu 2 nhảy lệch pha
        msg = {"cmd": "prepare", "beats": beats, "opts": o}
        if choreo:
            o["role"] = roles[i]             # con dau vai A, con sau vai B
            msg["choreo"] = choreo
            print(f"   -> {r.name} nhan vai {o['role']}")
        send_msg(r.sock, msg)

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

    # ------------------------------------------------ CHỜ NGƯỜI BẤM ENTER
    # Trên sân khấu không thể để đồng hồ đếm ngược quyết định: MC còn giới
    # thiệu, dài ngắn không biết trước. Nên dừng ở đây, mọi thứ đã sẵn sàng
    # (đồng hồ đã đồng bộ, kịch bản đã nằm sẵn trong hai con), chỉ chờ một cú
    # Enter. Bấm xong: hai con đứng dậy, rồi nhạc + nhảy khởi động cùng lúc.
    if wait_enter:
        print("\n" + "=" * 60)
        print("  SAN SANG. Hai con dang NAM CHO, chua dung day.")
        print("  Doi MC gioi thieu xong roi bam ENTER de bat dau.")
        print("  (Ctrl+C de huy)")
        print("=" * 60)
        try:
            input("  >>> Bam ENTER de DUNG DAY + LEN NHAC: ")
        except EOFError:
            print("  (khong co ban phim -> chay luon)")

        # Đứng dậy TRƯỚC, chờ cả hai báo xong, rồi mới tính mốc khởi diễn.
        # Không gộp chung: đứng dậy mất ~3 giây, gộp vào thì nhạc chạy trong
        # lúc chó còn đang chống chân — mất luôn đoạn mở bài.
        print("\n[dan] hai con dung day...")
        for r in robots:
            send_msg(r.sock, {"cmd": "stand"})
        for r in robots:
            m = r.rd.recv(timeout=30)
            if not m or m.get("cmd") != "stood":
                sys.exit(f"❌ {r.name} khong dung day duoc: {m}")
            print(f"   ✅ {r.name} da dung")

    t_go = time.time() + lead_s
    for r in robots:
        send_msg(r.sock, {"cmd": "go", "t_local": t_go + r.offset})
    print(f"\n>>> KHOI DIEN sau {lead_s:.1f}s <<<")

    proc = None
    if nhac_jetson and not dry:
        # Nhac phat tu JETSON cua con <ip> ra ngo mac dinh cua no — tuc LOA BT
        # cua BTC neu da ghep. Khac han `nhac_robot`: cai kia di qua WebRTC toi
        # loa NHO gan tren than robot.
        # Phuong an nay dung khi LAPTOP khong noi duoc loa BTC, nhung con cho
        # thi noi duoc.
        time.sleep(max(0.0, t_go - time.time()))
        proc = subprocess.Popen(
            ["ssh", "-n", "-o", "BatchMode=yes", f"unitree@{nhac_jetson}",
             f"export XDG_RUNTIME_DIR=/run/user/$(id -u); "
             f"ffplay -nodisp -autoexit -loglevel quiet ~/NhanHuynh/"
             f"{os.path.basename(music)} 2>/dev/null || "
             f"paplay ~/NhanHuynh/{os.path.basename(music)}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[nhac] phat tu JETSON cho A -> loa Bluetooth ({nhac_jetson})")
    elif nhac_robot and not dry:
        # Nhac phat tu LOA CUA CHO A, khong phai tu may nay.
        # Bat o DUNG cho nay — cung noi va cung thoi diem voi phat o laptop —
        # de nhac va lenh nhay cung khoi dong tai t_go. Bat som hon (vd trong
        # bash truoc khi goi conduct) thi nhac chay truoc luc cho dung day.
        time.sleep(max(0.0, t_go - time.time()))
        proc = subprocess.Popen(
            ["ssh", "-n", "-o", "BatchMode=yes", f"unitree@{nhac_robot}",
             "export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH; "
             "cd ~/NhanHuynh/go2_audio && "
             f"python3 go2_speaker.py play ~/NhanHuynh/{os.path.splitext(os.path.basename(music))[0]}"
             f" --seconds {int(dur) + 5}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[nhac] phat tu LOA CHO A ({nhac_robot})")
    elif play_here and not dry:
        time.sleep(max(0.0, t_go - time.time()))
        proc = play_local(music)
    elif play_here or nhac_robot or nhac_jetson:
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
    c.add_argument("--choreo", default=None,
                   help="file kich ban cua go2_choreo.py (thay cho cong thuc N beat)")
    c.add_argument("--travel", type=float, default=1.0,
                   help="he so di chuyen khi dung --choreo (0 = dung yen tai cho)")
    c.add_argument("--nhan", default=None,
                   help="danh sach diem nhan ngan, cach nhau dau phay "
                        "(mac dinh Hello,Heart,Pose)")
    c.add_argument("--cat-dance", type=float, default=None,
                   help="cho Dance1/Dance2 chay bao nhieu giay roi moi chan "
                        "(bo doan quay dau o cuoi). Do bang do_dance.py truoc.")
    c.add_argument("--kieu-show", action="store_true",
                   help="chay ban sao go2_show.py tren ca hai con (dong tac bi "
                        "CAT NGAN ngay, khong giu — muot nhat, it troi nhat)")
    c.add_argument("--khong-bu-troi", dest="recenter", action="store_false",
                   default=True,
                   help="TAT hoan toan phan di ve cho cu. Giong het ban 1 con "
                        "(go2_show.py): khong bao gio khung, doi lai cho co the "
                        "troi/xoay dan sau moi dong tac.")
    c.add_argument("--nhac-jetson", dest="nhac_jetson", default=None, metavar="IP",
                   help="Phat nhac tu JETSON cua con <IP> ra ngo mac dinh cua no "
                        "(= loa Bluetooth neu da ghep). Dung khi LAPTOP khong noi "
                        "duoc loa BTC nhung con cho thi noi duoc.")
    c.add_argument("--nhac-robot", dest="nhac_robot", default=None, metavar="IP",
                   help="Phat nhac tu LOA CUA CON <IP> thay vi tu may nay. "
                        "Nho: loa robot NHO. Dung khi khong tien noi loa hoi truong.")
    c.add_argument("--cho-enter", dest="wait_enter", action="store_true",
                   help="Dung cho BAM ENTER roi moi dung day + len nhac. "
                        "Dung khi dien that: MC gioi thieu xong bao lau cung duoc, "
                        "cho nam cho, khong dung san tren san khau.")
    c.add_argument("--loud", action="store_true",
                   help="KHONG tat loa robot (mac dinh tat de khoi keu 'ne vat can')")

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
        if args.choreo and not os.path.isfile(args.choreo):
            sys.exit(f"khong thay file kich ban: {args.choreo}")
        opts = {"latency": args.latency, "special": args.special,
                "stunts": args.stunts, "travel": args.travel,
                "quiet": not args.loud,
                # KIEU SHOW: ban sao go2_show.py chay tren ca hai con. Chi can
                # cung `beat_times` + cung `t0` la hai con tu khop, vi moi quyet
                # dinh trong vong lap deu tinh tu CHI SO BEAT.
                "kieu_show": args.kieu_show,
                "cat_dance": args.cat_dance,
                "nhan": args.nhan,
                # chờ Enter thì ĐỪNG đứng dậy lúc prepare
                "stand_now": not args.wait_enter,
                "recenter": args.recenter}
        run_conduct([x.strip() for x in args.robots.split(",") if x.strip()],
                    args.music, opts, args.lead, args.play_here, args.dry,
                    choreo_path=args.choreo, wait_enter=args.wait_enter,
                    nhac_robot=args.nhac_robot,
                    nhac_jetson=args.nhac_jetson)


if __name__ == "__main__":
    main()
