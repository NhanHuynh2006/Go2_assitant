#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoVoice Studio — backend.

Mot tien trinh Python nho (FastAPI + WebSocket) dung giua giao dien va GoVoice:
  - bat / tat mo phong Gazebo (ros2 launch go2_voice voice_sim.launch.py) va llama-server
  - chay CHINH pipeline GoVoice (Combo/Reflex/LLM -> SafetyGuard -> executor -> robot)
    trong tien trinh nay: go phim tu app, noi qua mic, E-STOP
  - day trang thai 5 lan/giay: vi tri robot, duong di, nguoi, he thong (CPU/GPU/RAM)
  - ban do robot tu ve (LiDAR + D435i) thanh anh PNG 1 lan/giay

Giao dien (studio/web) chi VE, khong tinh gi nang -> mo bang cua so app, trinh duyet
laptop hay dien thoai deu duoc.

    # can ROS da source (rclpy); app desktop tu lam viec nay
    python3 studio/server.py --port 8765               # mo phong tren laptop
    python3 studio/server.py --real --host 0.0.0.0     # chay TREN CHO (Jetson), app noi tu xa

Viet tuong thich Python 3.8 (Jetson Foxy).
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import collections
import io
import json
import math
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.request

STUDIO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("GOVOICE_HOME") or os.path.dirname(STUDIO)
WEB = os.path.join(STUDIO, "web")
sys.path.insert(0, ROOT)
os.chdir(ROOT)                        # config.yaml dung duong dan tuong doi (models/piper, ...)

CONF_DIR = os.path.expanduser("~/.config/govoice-studio")
VERSION = "0.3.0"


# --------------------------------------------------------------------------- nhat ky
class Feed:
    """Moi dong in ra cua GoVoice (Ban:, Go:, Nghe:, ✅ ...) -> giao dien doc theo seq."""

    def __init__(self, maxlen=3000):
        self.lines = collections.deque(maxlen=maxlen)
        self.seq = 0
        self.lock = threading.Lock()

    def add(self, src, text):
        with self.lock:
            self.seq += 1
            self.lines.append({"seq": self.seq, "t": time.time(), "src": src, "text": text})

    def since(self, seq, limit=200):
        with self.lock:
            out = [l for l in self.lines if l["seq"] > seq]
        return out[-limit:]


FEED = Feed()


class Tee(io.TextIOBase):
    def __init__(self, orig, feed, src="app"):
        self.orig, self.feed, self.src = orig, feed, src
        self.buf = ""
        self.lock = threading.Lock()

    def write(self, s):
        try:
            self.orig.write(s)
        except Exception:                                     # noqa: BLE001
            pass
        with self.lock:
            self.buf += s
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                if line.strip():
                    self.feed.add(self.src, line.rstrip())
        return len(s)

    def flush(self):
        try:
            self.orig.flush()
        except Exception:                                     # noqa: BLE001
            pass


# --------------------------------------------------------------------------- tien trinh con
def _pkill(patterns):
    """pkill theo mau co ngoac [] -> khong bao gio tu giet chinh lenh pkill/shell nay."""
    for p in patterns:
        subprocess.call(["pkill", "-9", "-f", p], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)


def _pgrep(pattern):
    try:
        return subprocess.call(["pgrep", "-f", pattern], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0
    except Exception:                                         # noqa: BLE001
        return False


SIM_LEFTOVERS = ["gz[ ]sim", "gz-sim-[m]ain", "ros_gz_[b]ridge", "parameter_[b]ridge",
                 "quadruped_[c]ontroller", "state_[e]stimation_node", "ekf_[n]ode",
                 "robot_state_[p]ublisher", "controller_[m]anager", "static_transform_[p]ublisher",
                 "ros2 launch go2_voice voice[_]sim"]


class Proc:
    def __init__(self, name, external_pattern=None):
        self.name = name
        self.p = None
        self.tail = collections.deque(maxlen=400)
        self.started_at = None
        self.args = {}
        self.external_pattern = external_pattern

    def running(self):
        return self.p is not None and self.p.poll() is None

    def external(self):
        return (not self.running() and self.external_pattern is not None
                and _pgrep(self.external_pattern))

    def start(self, cmd, args=None, env=None):
        if self.running():
            return False
        self.tail.clear()
        self.tail.append("$ " + " ".join(cmd))
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, start_new_session=True,
                                  env=env or os.environ.copy(), cwd=ROOT)
        self.started_at = time.time()
        self.args = dict(args or {})
        threading.Thread(target=self._read, daemon=True).start()
        FEED.add("sys", f"Đã bật {self.name}")
        return True

    def _read(self):
        p = self.p
        for raw in iter(p.stdout.readline, b""):
            self.tail.append(raw.decode("utf-8", "replace").rstrip())
        code = p.wait()
        if p is self.p:
            FEED.add("sys", f"{self.name} đã dừng (mã {code})")

    def stop(self, leftovers=()):
        p = self.p
        if p is not None and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGINT)
                p.wait(timeout=10)
            except Exception:                                 # noqa: BLE001
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:                             # noqa: BLE001
                    pass
        if leftovers:
            _pkill(leftovers)
        self.p = None
        return True

    def info(self):
        return {"running": self.running(), "external": self.external(),
                "uptime": (time.time() - self.started_at) if self.running() else 0,
                "args": self.args}


def _first(paths):
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            return p
    return None


def llama_bin():
    return _first([os.environ.get("GOVOICE_LLAMA", ""),
                   os.path.join(ROOT, "NhanHuynh/go2_jetson_demo/llama.cpp/build-cuda/bin/llama-server"),
                   os.path.join(ROOT, "NhanHuynh/go2_jetson_demo/llama.cpp/build/bin/llama-server"),
                   "~/llama.cpp/build-cuda/bin/llama-server", "~/llama.cpp/build/bin/llama-server"])


def list_models():
    out = []
    for d in (os.path.join(ROOT, "finetune"), os.path.join(ROOT, "NhanHuynh/go2_jetson_demo"),
              os.path.expanduser("~/models")):
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".gguf") and "f16" not in f:
                    p = os.path.join(d, f)
                    out.append({"path": p, "name": f, "mb": round(os.path.getsize(p) / 1e6)})
    out.sort(key=lambda m: ("v2" not in m["name"], "govoice" not in m["name"], m["name"]))
    return out


def llm_healthy(port=8080):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.4) as r:
            return b"ok" in r.read()
    except Exception:                                         # noqa: BLE001
        return False


# --------------------------------------------------------------------------- ban do quet
MAP_DIR = os.path.join(ROOT, "maps")


class ScanMap:
    """Ban do QUET, khong phai dan.

    Ban do song cua robot (nav_local.OccGrid) co y quen dan: vet nguoi di qua phai mat
    sau vai giay de robot khong ne bong ma. Nhung nhu vay quet xong thi tuong o xa cung mo
    mat. Lop nay gom ban do song moi giay thanh 1 ban do BEN: o thay la vat thi +1, thay
    trong thi -0.4. Tuong (thay lai lien tuc) dung mai; vet nguoi bi xoa khi robot thay
    cho do trong tro lai. Dung de VE, KIEM TRA diem cham, va LUU file (dinh dang ROS
    map_server: .pgm + .yaml, mo duoc bang RViz/Nav2)."""

    WALL = 2.0

    def __init__(self):
        self.L = None
        self.meta = None
        self.lock = threading.Lock()
        self.name = None

    def _ensure(self, g):
        import numpy as np
        meta = {"res": float(g.res), "x0": float(g.x0), "y0": float(g.y0),
                "nx": int(g.nx), "ny": int(g.ny)}
        if self.L is None or self.meta != meta:
            self.L = np.full((g.ny, g.nx), np.nan, np.float32)
            self.meta = meta

    def update(self, g, d):
        import numpy as np
        with g.lock:
            ev = g.ev.copy()
        with d.lock:
            evd = d.ev.copy()
        occ = (ev >= g.thresh) | (evd >= d.thresh)
        free = ((ev < 0) | (evd < 0)) & ~occ
        with self.lock:
            self._ensure(g)
            L = self.L
            new = np.isnan(L) & (occ | free)
            L[new] = 0.0
            L[occ] += 1.0
            L[free] -= 0.4
            np.clip(L, -4.0, 8.0, out=L)

    def cell(self, x, y):
        m = self.meta
        return int((y - m["y0"]) // m["res"]), int((x - m["x0"]) // m["res"])

    def state_at(self, x, y, radius=0.0):
        """'wall' | 'free' | 'unknown' | 'outside' quanh (x, y)."""
        import numpy as np
        with self.lock:
            if self.L is None:
                return "unknown"
            r, c = self.cell(x, y)
            m = self.meta
            if not (0 <= r < m["ny"] and 0 <= c < m["nx"]):
                return "outside"
            n = int(math.ceil(radius / m["res"]))
            win = self.L[max(r - n, 0):r + n + 1, max(c - n, 0):c + n + 1]
            if np.any(win >= self.WALL):
                return "wall"
            v = self.L[r, c]
            return "unknown" if np.isnan(v) else ("free" if v < self.WALL else "wall")

    def clear(self):
        with self.lock:
            self.L = None
            self.name = None

    def save(self, name):
        import numpy as np
        os.makedirs(MAP_DIR, exist_ok=True)
        safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_ ").strip().replace(" ", "_")
        if not safe:
            raise ValueError("tên bản đồ trống")
        with self.lock:
            if self.L is None:
                raise ValueError("chưa có bản đồ (robot chưa quét)")
            L, m = self.L.copy(), dict(self.meta)
        img = np.full(L.shape, 205, np.uint8)                       # chua biet
        img[~np.isnan(L) & (L < self.WALL)] = 254                    # trong
        img[~np.isnan(L) & (L >= self.WALL)] = 0                     # vat
        img = img[::-1]                                              # hang 0 = y lon nhat
        base = os.path.join(MAP_DIR, safe)
        with open(base + ".pgm", "wb") as f:
            f.write(f"P5\n# GoVoice Studio\n{img.shape[1]} {img.shape[0]}\n255\n".encode())
            f.write(img.tobytes())
        with open(base + ".yaml", "w") as f:
            f.write(f"image: {safe}.pgm\nmode: trinary\nresolution: {m['res']}\n"
                    f"origin: [{m['x0']}, {m['y0']}, 0.0]\nnegate: 0\n"
                    f"occupied_thresh: 0.65\nfree_thresh: 0.25\n")
        np.savez_compressed(base + ".npz", L=L, **{k: v for k, v in m.items()})
        self.name = safe
        return safe

    def load(self, name, g):
        """Nap ban do da luu (cung do phan giai) vao dung toa do; phan ngoai luoi bo qua."""
        import numpy as np
        z = np.load(os.path.join(MAP_DIR, name + ".npz"))
        if abs(float(z["res"]) - float(g.res)) > 1e-6:
            raise ValueError("bản đồ khác độ phân giải")
        with self.lock:
            self._ensure(g)
            L = np.full_like(self.L, np.nan)
            src = z["L"]
            dc = int(round((float(z["x0"]) - self.meta["x0"]) / g.res))
            dr = int(round((float(z["y0"]) - self.meta["y0"]) / g.res))
            r0, c0 = max(dr, 0), max(dc, 0)
            r1, c1 = min(dr + src.shape[0], L.shape[0]), min(dc + src.shape[1], L.shape[1])
            if r1 > r0 and c1 > c0:
                L[r0:r1, c0:c1] = src[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
            self.L = L
            self.name = name

    @staticmethod
    def list():
        if not os.path.isdir(MAP_DIR):
            return []
        out = []
        for f in sorted(os.listdir(MAP_DIR)):
            if f.endswith(".npz"):
                p = os.path.join(MAP_DIR, f)
                out.append({"name": f[:-4], "t": os.path.getmtime(p)})
        return sorted(out, key=lambda m: -m["t"])


SCAN = ScanMap()


# --------------------------------------------------------------------------- tro ly
def _free_ahead(r, p):
    """Khoang trong phia truoc mui robot (m) - so lieu 'rada' cho the robot."""
    if p is None:
        return None
    try:
        d = float(r.free_distance(math.cos(p[2]), math.sin(p[2])))
        return round(min(d, 9.9), 2) if math.isfinite(d) else 9.9   # JSON khong co Infinity
    except Exception:                                         # noqa: BLE001
        return None


def _sim_vy_cap():
    """CHI demo trong sim (Studio): kep |vy| <= GOVOICE_SIM_VY_CAP (mac dinh 0.15 m/s), giong bridge chó thật
    (REAL_PREREG sua doi #1). Va trong tien trinh Studio, KHONG sua robot_ros.py (dong bang). 0 = tat."""
    import robot_ros
    cap = float(os.environ.get("GOVOICE_SIM_VY_CAP", "0.15"))
    cls = robot_ros.RosRobotTools
    if cap <= 0 or getattr(cls, "_vy_capped", False):
        return
    orig = cls._twist

    def _twist(self, vx=0.0, vy=0.0, wz=0.0):
        return orig(self, vx, max(-cap, min(cap, float(vy))), wz)

    cls._twist, cls._vy_capped = _twist, True
    print(f"[studio] sim: kep |vy| <= {cap} m/s (giong chó thật)")


class Assistant:
    def __init__(self, real=False):
        self.real = real
        self.gv = None
        self.status = "chưa kết nối"
        self.busy = False
        self.voice_thread = None
        self.error = ""

    def connect(self, wake=None, tts=True):
        if self.busy or self.gv is not None:
            return
        self.busy = True
        self.status = "đang tìm robot…"
        threading.Thread(target=self._connect, args=(wake, tts), daemon=True).start()

    def _connect(self, wake, tts):
        try:
            from run_sim import GoVoiceSim, load_config     # dat ROS_* truoc rclpy
            cfg = load_config(os.path.join(ROOT, "config.yaml"))
            if wake:
                cfg.setdefault("stt", {})["wake_words"] = list(wake)
            if self.real:
                real = cfg.get("real", {}) or {}
                sport = None
                try:
                    from robot_tools import RobotTools
                    sport = RobotTools(dry_run=False, iface=cfg.get("robot", {}).get("iface", "eth0"))
                except Exception as e:                        # noqa: BLE001
                    print(f"[studio] khong co SportClient ({e}) -> chi di chuyen")
                from robot_real import RealRobotTools
                gv = GoVoiceSim(cfg, [real.get("ns", "go2")], no_tts=not tts, section="real",
                                backend=RealRobotTools,
                                backend_kw={"cfg_real": real, "sport": sport})
            else:
                from robot_ros import discover_robots
                _sim_vy_cap()                                  # demo sim: kep vy nhu bridge cho that
                robots = []
                for _ in range(10):
                    robots = discover_robots(wait_s=3.0)
                    if robots:
                        break
                    self.status = "chưa thấy robot — mô phỏng đã chạy chưa?"
                if not robots:
                    self.status = "không thấy robot"
                    return
                self.status = f"đang nối {len(robots)} robot…"
                gv = GoVoiceSim(cfg, robots, no_tts=not tts)
            gv.voice_enabled = False
            gv.tts_muted = not tts
            self.gv = gv
            self.status = "sẵn sàng"
            FEED.add("sys", "Trợ lý sẵn sàng: " + ", ".join(gv.labels.values()))
        except Exception as e:                                # noqa: BLE001
            import traceback
            traceback.print_exc()
            self.error = repr(e)
            self.status = "lỗi: " + repr(e)[:120]
        finally:
            self.busy = False

    def say(self, text):
        gv = self.gv
        if gv is None:
            return False
        print(f"Bạn: {text}")
        threading.Thread(target=gv._submit, args=(text,), daemon=True).start()
        return True

    def set_voice(self, on):
        gv = self.gv
        if gv is None:
            return False
        gv.voice_enabled = bool(on)
        if on and (self.voice_thread is None or not self.voice_thread.is_alive()):
            def run():
                try:
                    gv.run_voice(banner=False)
                except Exception as e:                        # noqa: BLE001
                    gv.voice_enabled = False
                    print(f"[voice] mic/STT loi: {e!r}")
            self.voice_thread = threading.Thread(target=run, daemon=True, name="voice")
            self.voice_thread.start()
        return True

    def estop(self):
        gv = self.gv
        if gv is None:
            return False
        gv.executor.stop_all()
        print("🛑 E-STOP từ Studio: dừng tất cả robot")
        return True

    def check_point(self, x, y):
        """Cho cham co di duoc khong: tuong/vat (ban do quet + ban do song), chua quet, ngoai."""
        gv = self.gv
        st = SCAN.state_at(x, y, radius=0.22)
        if gv is not None and st != "outside":
            r0 = next(iter(gv.robots.values()))
            try:
                occ = r0.grid.occupied() | r0.depth_grid.occupied()
                rr, cc = r0.grid.cell(x, y)
                n = int(math.ceil(0.22 / r0.grid.res))
                if occ[max(rr - n, 0):rr + n + 1, max(cc - n, 0):cc + n + 1].any():
                    st = "wall"
            except Exception:                                 # noqa: BLE001
                pass
        msg = {"wall": "Chỗ đó là vật cản hoặc sát tường",
               "outside": "Ngoài vùng bản đồ",
               "unknown": "Chưa quét chỗ này — robot sẽ vừa đi vừa dò",
               "free": "Trống, đi được"}[st]
        return {"state": st, "ok": st in ("free", "unknown"), "msg": msg}

    def _preempt(self, ns):
        """Bo viec dang lam (nhe nhang, khong phai E-STOP): xoa hang doi + huy di chuyen."""
        import queue as _q
        ex = self.gv.executor.ex.get(ns)
        if ex is not None:
            try:
                while True:
                    ex.q.get_nowait()
            except _q.Empty:
                pass
        r = self.gv.robots.get(ns)
        if r is not None and getattr(r, "goal", None) is not None:
            r.preempted = True                # robot_ros: im lang, khong bao "khong toi duoc"
            r._cancel.set()
            t0 = time.time()
            while getattr(r, "goal", None) is not None and time.time() - t0 < 1.5:
                time.sleep(0.05)

    def _target(self, ns):
        gv = self.gv
        if gv is None:
            return None
        if ns in gv.robots:
            return ns
        return next(iter(gv.robots)) if len(gv.robots) == 1 else None

    def goto_xy(self, ns, x, y, yaw=None, name=None):
        gv = self.gv
        ns = self._target(ns)
        if ns is None:
            return {"ok": False, "msg": "Chọn robot trước"}
        chk = self.check_point(x, y)
        if not chk["ok"]:
            return {"ok": False, "msg": chk["msg"]}
        p = gv.robots[ns].map_pose() or (x, y, 0.0)
        if yaw is None:
            yaw = math.atan2(y - p[1], x - p[0])
        name = name or f"điểm ({x:.1f}, {y:.1f})"
        self._preempt(ns)                     # cham diem moi = DOI dich, khong xep hang sau
        print(f"Bạn: [{gv.labels[ns]}] đi tới {name} (chấm trên bản đồ)")
        gv.executor.enqueue([{"tool": "go_to_pose", "args": {
            "x": float(x), "y": float(y), "yaw": float(yaw), "name": name}}], only=[ns])
        return {"ok": True, "msg": chk["msg"]}

    def route(self, ns, pts, loop=False):
        """Lo trinh nhieu diem (cham lan luot): di het theo thu tu; loop = di tuan lap lai 3 vong."""
        gv = self.gv
        ns = self._target(ns)
        if ns is None:
            return {"ok": False, "msg": "Chọn robot trước"}
        bad = [i + 1 for i, q in enumerate(pts) if not self.check_point(q[0], q[1])["ok"]]
        if bad:
            return {"ok": False, "msg": "Điểm " + ", ".join(map(str, bad)) + " nằm trên vật cản"}
        acts = []
        for _ in range(3 if loop else 1):
            for i, q in enumerate(pts):
                nxt = pts[i + 1] if i + 1 < len(pts) else (pts[0] if loop else None)
                yaw = q[2] if len(q) > 2 and q[2] is not None else (
                    math.atan2(nxt[1] - q[1], nxt[0] - q[0]) if nxt else None)
                a = {"x": float(q[0]), "y": float(q[1]), "name": f"điểm {i + 1}/{len(pts)}"}
                if yaw is not None:
                    a["yaw"] = float(yaw)
                acts.append({"tool": "go_to_pose", "args": a})
        self._preempt(ns)
        print(f"Bạn: [{gv.labels[ns]}] đi lộ trình {len(pts)} điểm" + (" (tuần tra 3 vòng)" if loop else ""))
        gv.executor.enqueue(acts, only=[ns])
        return {"ok": True, "msg": f"Đi {len(pts)} điểm" + (" × 3 vòng" if loop else "")}

    def add_place(self, name, x, y, yaw):
        gv = self.gv
        if gv is None or not name.strip():
            return {"ok": False, "msg": "Chưa có tên"}
        gv.add_place(name.strip(), x, y, yaw if yaw is not None else 0.0, how="cham tren Studio")
        print(f"📍 Đã lưu điểm “{name.strip()}” tại ({x:.2f}, {y:.2f}) — nói “đi tới {name.strip()}” để tới")
        return {"ok": True, "msg": f"Đã lưu “{name.strip()}”"}

    def stop(self):
        gv = self.gv
        if gv is None:
            return
        try:
            gv.executor.stop_all()
            gv.executor.shutdown()
            from robot_ros import RosBus
            RosBus.get().shutdown()
        except Exception:                                     # noqa: BLE001
            pass

    # -- trang thai cho giao dien
    def snapshot(self):
        gv = self.gv
        if gv is None:
            return {"status": self.status, "ready": False, "robots": [], "people": []}
        robots, people = [], []
        for i, (ns, r) in enumerate(gv.robots.items()):
            p = r.map_pose()
            ex = gv.executor.ex.get(ns)
            robots.append({
                "ns": ns or "/", "key": ns, "label": gv.labels.get(ns, ns), "i": i,
                "pose": [round(p[0], 3), round(p[1], 3), round(p[2], 3)] if p else None,
                "state": getattr(r, "state", ""), "goal": list(r.goal) if r.goal else None,
                "local": [[round(a, 2), round(b, 2)] for a, b in (getattr(r, "local_traj", None) or [])]
                if r.goal else [],
                "path": [[round(a, 2), round(b, 2)] for a, b in (getattr(r, "last_path", None) or [])]
                if r.goal else [],
                "busy": bool(ex.is_busy()) if ex else False,
                "free": _free_ahead(r, p),
            })
            try:
                for tr in r.tracker.movers():
                    people.append({"x": round(float(tr["p"][0]), 2), "y": round(float(tr["p"][1]), 2),
                                   "vx": round(float(tr["v"][0]), 2), "vy": round(float(tr["v"][1]), 2)})
            except Exception:                                 # noqa: BLE001
                pass
        r0 = next(iter(gv.robots.values()))
        return {"status": self.status, "ready": True, "robots": robots, "people": people,
                "controller": getattr(r0, "controller", "pp"),
                "world": (gv.world or {}).get("name") if getattr(gv, "world", None) else None,
                "voice": bool(getattr(gv, "voice_enabled", False)),
                "tts": not getattr(gv, "tts_muted", False),
                "wake": list((gv.cfg.get("stt", {}) or {}).get("wake_words") or [])}

    def scene(self):
        gv = self.gv
        if gv is None:
            return {"places": [], "objects": []}
        places = []
        for k, v in gv.places.items():
            pose = v.get("pose") if isinstance(v, dict) else v
            if pose and len(pose) >= 2:
                places.append({"name": gv.place_names.get(k, k), "x": pose[0], "y": pose[1]})
        objects = []
        if gv.catalog:
            for it in gv.catalog.items:
                objects.append({"label": it["label"], "color": it["color"],
                                "desc": gv.catalog.describe(it),
                                "x": it["x"], "y": it["y"], "sx": it["sx"], "sy": it["sy"],
                                "yaw": it["yaw"]})
        return {"places": places, "objects": objects}

    def map_png(self):
        """Ban do QUET (ben) lam nen + ban do SONG chong len: nghi co (cam), chi camera thay
        (xanh), vat dang thay (trang). Cap nhat ban do quet o day (1 lan/giay)."""
        gv = self.gv
        if gv is None:
            return None, None
        import numpy as np
        from PIL import Image
        r0 = next(iter(gv.robots.values()))
        g, d = r0.grid, r0.depth_grid
        SCAN.update(g, d)
        with g.lock:
            ev = g.ev.copy()
        with d.lock:
            evd = d.ev.copy()
        with SCAN.lock:
            L = SCAN.L.copy()
        img = np.zeros(ev.shape + (4,), np.uint8)                 # trong suot = chua biet
        known = ~np.isnan(L)
        img[known & (L < SCAN.WALL)] = (34, 50, 66, 170)           # da quet, trong
        img[known & (L >= SCAN.WALL)] = (200, 210, 220, 210)       # da quet, vat/tuong
        maybe = ((ev > 0) | (evd > 0)) & ~(known & (L >= SCAN.WALL))
        occ = (ev >= g.thresh) | (evd >= d.thresh)
        img[maybe] = (240, 170, 60, 150)
        img[occ] = (245, 248, 250, 245)
        img[(evd >= d.thresh) & ~(ev >= g.thresh)] = (90, 200, 255, 235)   # chi camera thay
        im = Image.fromarray(img[::-1], "RGBA")                   # hang 0 = y lon nhat (anh)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=False, compress_level=3)
        meta = {"res": float(g.res), "x0": float(g.x0), "y0": float(g.y0),
                "nx": int(g.nx), "ny": int(g.ny)}
        return buf.getvalue(), meta


# --------------------------------------------------------------------------- he thong
class SysStats:
    def __init__(self):
        import psutil
        self.ps = psutil
        self.nv = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nv = (pynvml, pynvml.nvmlDeviceGetHandleByIndex(0))
        except Exception:                                     # noqa: BLE001
            self.nv = None
        self.ps.cpu_percent(None)
        self.last = {}
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            s = {"cpu": self.ps.cpu_percent(None), "ram": self.ps.virtual_memory().percent,
                 "ram_gb": round(self.ps.virtual_memory().used / 1e9, 1)}
            try:
                temps = self.ps.sensors_temperatures()
                for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "thermal_zone0"):
                    if key in temps and temps[key]:
                        s["temp"] = round(max(t.current for t in temps[key]), 0)
                        break
            except Exception:                                 # noqa: BLE001
                pass
            if self.nv:
                nv, h = self.nv
                try:
                    u = nv.nvmlDeviceGetUtilizationRates(h)
                    m = nv.nvmlDeviceGetMemoryInfo(h)
                    s["gpu"] = u.gpu
                    s["vram"] = round(100.0 * m.used / m.total, 1)
                    s["vram_gb"] = round(m.used / 1e9, 1)
                    s["gpu_temp"] = nv.nvmlDeviceGetTemperature(h, 0)
                except Exception:                             # noqa: BLE001
                    pass
            self.last = s
            time.sleep(1.0)


# --------------------------------------------------------------------------- app
def make_app(args):
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles

    os.makedirs(CONF_DIR, exist_ok=True)
    tok_file = os.path.join(CONF_DIR, "token")
    if not os.path.exists(tok_file):
        with open(tok_file, "w") as f:
            f.write(secrets.token_urlsafe(12))
        os.chmod(tok_file, 0o600)
    TOKEN = open(tok_file).read().strip()

    assistant = Assistant(real=args.real)
    sim = Proc("mô phỏng", external_pattern="gz[ ]sim")
    llm = Proc("LLM", external_pattern="llama[-]server")
    movers = Proc("người & xe đẩy", external_pattern="movers[.]py")
    stats = SysStats()
    cache = {"png": None, "meta": None, "ver": 0, "t": 0.0}
    app = FastAPI(title="GoVoice Studio", version=VERSION)

    def _local(host):
        return host in ("127.0.0.1", "::1", "localhost")

    @app.middleware("http")
    async def auth(request: Request, call_next):
        host = request.client.host if request.client else ""
        if request.url.path.startswith("/api") and not _local(host):
            t = request.headers.get("x-token") or request.query_params.get("token")
            if t != TOKEN:
                return JSONResponse({"error": "sai token"}, status_code=401)
        return await call_next(request)

    def ros_env():
        env = os.environ.copy()
        env.setdefault("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp")
        env.setdefault("ROS_AUTOMATIC_DISCOVERY_RANGE", "LOCALHOST")
        env.setdefault("GZ_IP", "127.0.0.1")
        return env

    @app.get("/api/info")
    def info():
        return {"version": VERSION, "mode": "real" if args.real else "sim", "root": ROOT,
                "models": list_models(), "llama": llama_bin(),
                "ros": os.environ.get("ROS_DISTRO", ""), "token_needed_remote": True}

    @app.post("/api/sim/start")
    async def sim_start(request: Request):
        b = await request.json()
        n = max(1, min(4, int(b.get("robots", 1))))
        gui = bool(b.get("gui", False))
        world = b.get("world") or "voice_house"
        if world not in ("voice_house", "voice_office"):
            world = "voice_house"
        cmd = ["ros2", "launch", "go2_voice", "voice_sim.launch.py", f"robots:={n}",
               f"headless:={'false' if gui else 'true'}", f"world:={world}.sdf",
               f"rviz:={'true' if b.get('rviz') else 'false'}"]
        if sim.external():
            return {"ok": False, "msg": "Mô phỏng đang chạy ngoài app — tắt nó trước"}
        return {"ok": sim.start(cmd, {"robots": n, "gui": gui, "world": world}, env=ros_env())}

    @app.post("/api/sim/stop")
    def sim_stop():
        assistant.estop()
        movers.stop()
        sim.stop(leftovers=SIM_LEFTOVERS)          # ke ca sim bat tu terminal (ngoai app)
        return {"ok": True}

    @app.post("/api/movers/start")
    async def movers_start(request: Request):
        """Nguoi di bo (Social Force) + xe day hang (van phong) - vat can DONG."""
        b = await request.json()
        from run_sim import detect_world
        w = detect_world()
        n = max(0, min(12 if w == "voice_office" else 3, int(b.get("n", 6))))
        py = os.path.join(ROOT, "venv", "bin", "python")
        cmd = [py if os.path.exists(py) else sys.executable, "-u", os.path.join(ROOT, "movers.py"),
               "--world", w, "--crowd", str(n), "--seed", str(int(time.time()) % 1000)]
        if b.get("carts", True) and w == "voice_office":
            cmd.append("--carts")
        ok = movers.start(cmd, {"n": n, "world": w, "carts": "--carts" in cmd}, env=ros_env())
        return {"ok": ok, "msg": f"{n} người" + (" + 3 xe đẩy" if "--carts" in cmd else "") + " đang đi lại"}

    @app.post("/api/movers/stop")
    def movers_stop():
        movers.stop()
        return {"ok": True}

    @app.post("/api/controller")
    async def controller(request: Request):
        b = await request.json()
        name = b.get("name", "mppi")
        gv = assistant.gv
        paper = ("p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5", "p3+geo-haz+gcv~t3~nl~cs:ppl=32;ppl_len=0.5", "mppi~t3~nl:ppl=100;ppl_len=0.5",
                 "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05")      # C1, B1, DRA* (bai bao)
        if gv is None or name not in ("mppi", "dwa", "pp", "rl", "rl_safe") + paper:
            return {"ok": False}
        from nav_local import BlobTracker
        for r in gv.robots.values():
            r.controller, r._ctrl = name, None
            r.tracker = BlobTracker()          # vet cu (kieu v2/v3) khong hop bo dieu khien moi -> KeyError('x')
        print(f"[studio] bo dieu khien: {name.upper()}")
        return {"ok": True}

    @app.post("/api/restart")
    def restart():
        """Doi the gioi -> tro ly phai nap lai (danh muc do vat, diem den, kich thuoc ban do).
        Khoi dong lai CHINH backend nay; sim/LLM (tien trinh rieng) van chay."""
        def later():
            time.sleep(0.4)
            try:
                assistant.stop()
            except Exception:                                 # noqa: BLE001
                pass
            os.execv(sys.executable, [sys.executable] + sys.argv)
        threading.Thread(target=later, daemon=True).start()
        return {"ok": True}

    @app.post("/api/llm/start")
    async def llm_start(request: Request):
        b = await request.json()
        exe = llama_bin()
        models = list_models()
        model = b.get("model") or (models[0]["path"] if models else None)
        if not exe or not model:
            return {"ok": False, "msg": "Không tìm thấy llama-server hoặc file .gguf"}
        if llm_healthy():
            return {"ok": False, "msg": "LLM đã chạy sẵn (cổng 8080)"}
        ngl = str(b.get("ngl", 99))
        env = os.environ.copy()
        if ngl == "0":
            env["CUDA_VISIBLE_DEVICES"] = ""
        cmd = [exe, "-m", model, "-ngl", ngl, "-c", "2048", "--port", "8080", "-t", "8"]
        return {"ok": llm.start(cmd, {"model": os.path.basename(model), "ngl": ngl}, env=env)}

    @app.post("/api/llm/stop")
    def llm_stop():
        llm.stop()
        return {"ok": True}

    @app.post("/api/assistant/connect")
    async def a_connect(request: Request):
        b = await request.json()
        wake = [w.strip() for w in (b.get("wake") or "").split(",") if w.strip()]
        assistant.connect(wake=wake, tts=bool(b.get("tts", True)))
        return {"ok": True}

    @app.post("/api/say")
    async def say(request: Request):
        b = await request.json()
        text = (b.get("text") or "").strip()
        if not text:
            return {"ok": False}
        return {"ok": assistant.say(text)}

    @app.post("/api/estop")
    def estop():
        return {"ok": assistant.estop()}

    @app.post("/api/voice")
    async def voice(request: Request):
        b = await request.json()
        return {"ok": assistant.set_voice(b.get("on", False))}

    @app.post("/api/tts")
    async def tts(request: Request):
        b = await request.json()
        gv = assistant.gv
        if gv is not None:
            gv.tts_muted = not bool(b.get("on", True))
        return {"ok": gv is not None}

    @app.post("/api/wake")
    async def wake(request: Request):
        b = await request.json()
        gv = assistant.gv
        if gv is None:
            return {"ok": False}
        words = [w.strip() for w in (b.get("wake") or "").split(",") if w.strip()]
        gv.cfg.setdefault("stt", {})["wake_words"] = words
        print(f"[studio] tu danh thuc: {words or 'tat'}")
        return {"ok": True}

    @app.post("/api/goto_xy")
    async def goto_xy(request: Request):
        b = await request.json()
        yaw = b.get("yaw")
        return assistant.goto_xy(b.get("ns", ""), float(b["x"]), float(b["y"]),
                                 None if yaw is None else float(yaw), b.get("name"))

    @app.get("/api/check")
    def check(x: float, y: float):
        return assistant.check_point(x, y)

    @app.post("/api/route")
    async def route(request: Request):
        b = await request.json()
        pts = [[float(q[0]), float(q[1])] + ([float(q[2])] if len(q) > 2 and q[2] is not None else [])
               for q in b.get("points", [])]
        if not pts:
            return {"ok": False, "msg": "Lộ trình trống"}
        return assistant.route(b.get("ns", ""), pts, bool(b.get("loop")))

    @app.post("/api/place")
    async def place(request: Request):
        b = await request.json()
        yaw = b.get("yaw")
        return assistant.add_place(b.get("name", ""), float(b["x"]), float(b["y"]),
                                   None if yaw is None else float(yaw))

    @app.get("/api/maps")
    def maps():
        return {"maps": ScanMap.list(), "current": SCAN.name}

    @app.post("/api/map/save")
    async def map_save(request: Request):
        b = await request.json()
        try:
            name = SCAN.save(b.get("name") or time.strftime("ban_do_%Y%m%d_%H%M"))
            print(f"💾 Đã lưu bản đồ “{name}” → maps/{name}.pgm/.yaml (mở được bằng RViz/Nav2)")
            return {"ok": True, "msg": f"Đã lưu bản đồ “{name}”", "name": name}
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    @app.post("/api/map/load")
    async def map_load(request: Request):
        b = await request.json()
        gv = assistant.gv
        if gv is None:
            return {"ok": False, "msg": "Kết nối trợ lý trước"}
        try:
            SCAN.load(b["name"], next(iter(gv.robots.values())).grid)
            print(f"📂 Đã mở bản đồ “{b['name']}”")
            return {"ok": True, "msg": f"Đã mở “{b['name']}”"}
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    @app.post("/api/map/clear")
    def map_clear():
        SCAN.clear()
        print("🧹 Đã xoá bản đồ quét — quét lại từ đầu")
        return {"ok": True, "msg": "Đã xoá bản đồ, quét lại từ đầu"}

    @app.get("/api/scene")
    def scene():
        return assistant.scene()

    @app.get("/api/logs/{name}")
    def logs(name: str):
        p = {"sim": sim, "llm": llm}.get(name)
        return {"lines": list(p.tail)[-200:] if p else []}

    @app.get("/api/map.png")
    def map_png():
        if cache["png"] is None:
            return Response(status_code=204)
        return Response(cache["png"], media_type="image/png",
                        headers={"Cache-Control": "no-store"})

    def map_loop():
        while True:
            try:
                png, meta = assistant.map_png()
                if png is not None:
                    cache["png"], cache["meta"] = png, meta
                    cache["ver"] += 1
            except Exception as e:                            # noqa: BLE001
                print(f"[studio] map: {e!r}")
            time.sleep(1.0)
    threading.Thread(target=map_loop, daemon=True).start()

    wcache = {"t": 0.0, "w": None}

    def _world_cached():
        """The gioi Gazebo dang chay (hoi gz moi 5 s - lenh ~1 s, khong goi moi khung)."""
        if time.time() - wcache["t"] > 5.0:
            wcache["t"] = time.time()

            def q():
                try:
                    from run_sim import detect_world
                    wcache["w"] = detect_world(default=None) if (sim.running() or sim.external()) else None
                except Exception:                             # noqa: BLE001
                    wcache["w"] = None
            threading.Thread(target=q, daemon=True).start()
        return wcache["w"]

    def state(seq):
        s = assistant.snapshot()
        return {
            "t": time.time(), "mode": "real" if args.real else "sim",
            "procs": {"sim": sim.info(), "llm": dict(llm.info(), healthy=llm_healthy()),
                      "movers": movers.info(), "world": _world_cached()},
            "assistant": {k: s[k] for k in s if k not in ("robots", "people")},
            "robots": s["robots"], "people": s["people"],
            "sys": stats.last, "map": {"ver": cache["ver"], "meta": cache["meta"], "name": SCAN.name},
            "feed": FEED.since(seq),
        }

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        import asyncio
        host = sock.client.host if sock.client else ""
        if not _local(host) and sock.query_params.get("token") != TOKEN:
            await sock.close(code=4401)
            return
        await sock.accept()
        seq = max(0, FEED.seq - 150)
        try:
            while True:
                msg = state(seq)
                if msg["feed"]:
                    seq = msg["feed"][-1]["seq"]
                await sock.send_text(json.dumps(msg, ensure_ascii=False))
                await asyncio.sleep(0.2)
        except (WebSocketDisconnect, RuntimeError):
            return
        except Exception:                                     # noqa: BLE001
            return

    @app.post("/api/shutdown")
    def shutdown():
        """App dong cua so: tat nhung gi app da bat (khong dung toi sim bat tu ngoai)."""
        assistant.estop()
        movers.stop()
        if sim.running():
            sim.stop(leftovers=SIM_LEFTOVERS)
        if llm.running():
            llm.stop()
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(os.path.join(WEB, "index.html"),
                            headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=WEB), name="web")
    app.state.cleanup = lambda: (assistant.stop(), sim.running() and sim.stop(SIM_LEFTOVERS),
                                 llm.running() and llm.stop())
    if args.autoconnect:
        assistant.connect(tts=not args.no_tts)
    return app


def main():
    ap = argparse.ArgumentParser(description="GoVoice Studio backend")
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 de app/dien thoai noi tu may khac (can token)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--real", action="store_true", help="chay tren Go2 that (Jetson)")
    ap.add_argument("--autoconnect", action="store_true", help="noi tro ly ngay khi mo")
    ap.add_argument("--no-tts", action="store_true")
    args = ap.parse_args()

    sys.stdout = Tee(sys.stdout, FEED)
    import uvicorn
    app = make_app(args)
    if args.host not in ("127.0.0.1", "localhost"):
        tok = open(os.path.join(CONF_DIR, "token")).read().strip()
        print(f"[studio] mo tu may khac: http://<ip-may-nay>:{args.port}/?token={tok}")
    print(f"[studio] GoVoice Studio {VERSION} — http://{args.host}:{args.port}  goc: {ROOT}")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    finally:
        try:
            app.state.cleanup()
        except Exception:                                     # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
