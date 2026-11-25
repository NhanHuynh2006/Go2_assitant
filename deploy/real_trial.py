#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""real_trial.py (REALPREP, 25/11) - chay thi nghiem C1 vs B1 tren Go2 THAT theo lich DANG KY TRUOC (audit/REAL_PREREG.md).

CHAY TREN ORIN CUA CHO (Foxy, Python 3.8), KHONG qua Wi-Fi. Xem deploy/DEPLOY.md.

Khac eval_real.py (de nguyen, khong sua):
  * KHONG khoi tao SportClient/SDK trong tien trinh nay: chuyen dong CHI qua /go2/cmd_vel -> go2_hardware_bridge
    (bridge kep toc do --max-vx/--max-vy/--max-wz, StopMove khi mat lenh, nhuong remote). Khong LowCmd.
  * goi THANG RealRobotTools.go_to_pose (dung duong ma da bam sha: _navigate_mpc), giong eval_sim/Gazebo TEST;
    dat lai moi luot y nhu eval_sim.reset + reset_learned (ban do trong, tracker moi, vel_gain 0.5, bo dieu khien moi),
    gieo nhieu MPPI theo so thu tu luot nhu eval_sim.install_probes.
  * moi luot: ghi rosbag rieng, ghi su kien JSON tren /realprep/events, tu bat "nguoi gianh remote" tu /go2/status,
    canh gac toc do (odom) va hang rao (ra ngoai duong chay) -> dung; nguoi van hanh danh dau cham.
  * cau hinh (C1/B1) KHONG in ra man hinh trong luc chay (mu cho nguoi van hanh va nguoi di bo).

  python3 deploy/real_trial.py --make-schedule --seed 20261125 --pairs 20 --out ~/realprep/session1
  python3 deploy/real_trial.py --run --out ~/realprep/session1 --cloud /go2/lidar/merged [--cs] [--no-depth]
  python3 deploy/real_trial.py --dry --out /tmp/x            # in lich + kiem import, khong ROS, khong chuyen dong
"""
from __future__ import print_function

import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import csv
import json
import math
import os
import random
import select
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# Cau hinh DONG BANG (research/FROZEN.md). ~cs (nan lenh) la lop trien khai, them GIONG NHAU cho ca hai neu --cs.
CONFIGS = {"C1": "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5",
           "B1": "mppi~t3~nl:ppl=100;ppl_len=0.5"}

# Kich ban (audit/REAL_PREREG.md §2). goal: dich TUONG DOI tu vach xuat phat (x toi, y trai, m).
SCENARIOS = [
    ("S1", "vat_tinh", (6.0, 0.0), 0, "3 thung 50 cm so le: x=2.0 y=+0.35, x=3.5 y=-0.35, x=5.0 y=+0.35"),
    ("S2", "1_nguoi_cat_ngang", (6.0, 0.0), 1, "nguoi di cat ngang (trai->phai) tai x=3.5, xuat phat khi cho qua vach x=1.5"),
    ("S3", "1_nguoi_doi_dau", (6.0, 0.0), 1, "nguoi di nguoc chieu tu x=7.5 tren truc y=0, xuat phat khi cho qua x=1.0"),
    ("S4", "2_nguoi", (6.0, 0.0), 2, "S2 + S3 cung luc (1 cat ngang tai x=4.0, 1 doi dau lech y=+0.4)"),
    ("S5", "lui_xoay_cham", (-3.0, 0.0), 0, "tui hep: cho dung MAT vao hang thung o x=+0.9, hai ben thung y=+-0.7 tu x=-0.3 toi 0.9;"
                                            " dich o SAU LUNG 3 m -> phai lui + xoay cham trong 1.4 m (ca nga Isaac)"),
]

FIELDS = ["idx", "scenario", "pair", "order", "label", "config", "t_start", "time_s", "reached", "err_m",
          "why", "contact_person", "contact_obstacle", "takeover", "estop", "safety_stop", "timeout", "fall",
          "infra_abort", "success", "travel_m", "brakes", "backups", "replans", "max_speed", "max_tilt_deg",
          "min_person_m", "step_ms_p50", "step_ms_p95", "step_ms_max", "cs_n", "cs_cap", "cs_rate", "bag", "note"]


def make_schedule(a):
    """Lich: kich ban theo DO KHO TANG DAN (an toan); trong moi kich ban `pairs` cap, thu tu C1/B1 trong cap xao
    bang random.Random(seed), CAN BANG (moi kich ban dung pairs/2 cap C1 truoc). Ghi schedule.csv + sha256 cua no (dan vao REAL_PREREG truoc khi chay)."""
    rng = random.Random(a.seed)
    rows, idx = [], 0
    keep = set(a.scenarios.split(",")) if a.scenarios else None
    for sc, name, goal, npl, desc in SCENARIOS:
        if keep is not None and sc not in keep:
            continue
        first = ["C1"] * (a.pairs // 2) + ["B1"] * (a.pairs - a.pairs // 2)
        rng.shuffle(first)                                     # can bang: dung pairs/2 cap moi thu tu, xao vi tri
        for p in range(1, a.pairs + 1):
            order = [first[p - 1], "B1" if first[p - 1] == "C1" else "C1"]
            for k, lab in enumerate(order):
                idx += 1
                rows.append(dict(idx=idx, scenario=sc, pair=p, order=k + 1, label=lab, name=name,
                                 gx=goal[0], gy=goal[1], people=npl))
    os.makedirs(a.out, exist_ok=True)
    fn = os.path.join(a.out, "schedule.csv")
    if os.path.exists(fn) and not a.force:
        sys.exit("da co %s (dung --force neu that su muon tao lai TRUOC phien)" % fn)
    with open(fn, "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    import hashlib
    h = hashlib.sha256(open(fn, "rb").read()).hexdigest()
    open(fn + ".sha256", "w").write("%s  schedule.csv\n" % h)
    print("%d luot -> %s\nsha256 %s (ghi vao audit/REAL_PREREG.md §9 TRUOC luot dau)" % (len(rows), fn, h))


def read_schedule(out):
    return list(csv.DictReader(open(os.path.join(out, "schedule.csv"))))


def done_idx(out):
    fn = os.path.join(out, "trials.csv")
    if not os.path.exists(fn):
        return set()
    return {int(r["idx"]) for r in csv.DictReader(open(fn)) if r.get("infra_abort") != "1"}


class Session(object):
    def __init__(self, a):
        import numpy as np
        self.np = np
        self.a = a
        import robot_ros
        from robot_real import RealRobotTools
        self.robot_ros = robot_ros
        real = dict(ns="go2", odom_topic="/go2/odom", cloud_topic=a.cloud, imu_topic="/go2/imu/data",
                    depth_topic=a.depth_topic, base_height=0.32)
        # goto_speed / goto_turn = gia tri cua fastsim.make_robot (dong bang): vmax bo dieu khien 0.595 m/s, wz 1.0;
        # gioi han THAT do bridge kep (--max-vx ...), giong CHAMP kep 0.3/0.25/0.5 trong Gazebo TEST.
        os.environ["GOVOICE_CONTROLLER"] = CONFIGS["C1"]           # tracker v3 ngay tu dau (khong lan vet v2)
        self.r = RealRobotTools(cfg_real=real, sport=None, goto_speed=0.35, goto_turn=0.8,
                                use_depth=not a.no_depth, shared_map=True)
        if a.cloud.endswith("merged"):
            # lidar_merge da o base_link; RosRobotTools hoi TF go2/base_link<-base_link (khong co) roi ROI ve
            # R_BASE_LIDAR cua L1 -> sai. Dat san don vi (khong sua file dong bang).
            self.r._lidar_tf = (np.eye(3), np.zeros(3))
        node = robot_ros.RosBus.get().node
        from std_msgs.msg import String
        self.String = String
        self.ev_pub = node.create_publisher(String, "/realprep/events", 10)
        self.status = {}
        self.status_t = 0.0
        node.create_subscription(String, "/go2/status", self._on_status, 10)
        self.seed_base = a.seed
        self._wrap_make_ctrl()

    # -- trang thai bridge (battery, tilt, 'blocked': remote / lying / tilted ...)
    def _on_status(self, msg):
        try:
            self.status = json.loads(msg.data)
            self.status_t = time.monotonic()
        except ValueError:
            pass

    def event(self, **kw):
        kw["t_wall"] = time.time()
        m = self.String()
        m.data = json.dumps(kw)
        self.ev_pub.publish(m)

    def _wrap_make_ctrl(self):
        """Nhu eval_sim.install_probes: boc tren DOI TUONG (khong sua robot_ros) -> do thoi gian ctrl.step + gieo rng."""
        r, np = self.r, self.np
        base = r._make_ctrl
        self.step_ms = []
        self.cur_seed = None

        def make_ctrl():
            c = base()
            if hasattr(c, "rng") and self.cur_seed is not None:
                c.rng = np.random.default_rng([self.cur_seed, 0, 11])
            s0 = c.step

            def step(*aa, **kk):
                t = time.perf_counter()
                o = s0(*aa, **kk)
                self.step_ms.append((time.perf_counter() - t) * 1000)
                return o
            c.step = step
            return c
        r._make_ctrl = make_ctrl

    def reset(self, idx, cfg):
        """= eval_sim.reset + reset_learned; khung 'map' = tu the xuat phat cua luot nay.
        Dat controller TRUOC khi tao tracker moi: neu tracker o che do v2 (controller mac dinh 'mppi') tao vet kieu v2
        roi chuyen sang ~t3 thi _update_v3 loi KeyError('x') O MOI LAN QUET va ban do ngung cap nhat (da gap khi kiem khoi)."""
        np, r, rr = self.np, self.r, self.robot_ros
        from nav_local import BlobTracker
        r._halt()
        r.controller = cfg
        x, y, yaw, _ = r.odom
        c, s = math.cos(-yaw), math.sin(-yaw)
        r.origin = (-(c * x - s * y), -(s * x + c * y), -yaw)       # map_pose(start) = (0, 0, 0)
        time.sleep(0.3)
        for g in (rr.SHARED_GRID, rr.SHARED_DEPTH):
            with g.lock:
                g.ev[:] = 0
        r.local_t = r.depth_t = 0.0
        r.vel_gain = 0.5
        r.vel_gains = np.array([0.5, 0.5, 0.5])
        nt = BlobTracker()
        nt.mode = "v3" if "~t3" in cfg else "v2"                     # = track_and_filter
        nt.fix_dt = "~dt" in cfg
        r.tracker = nt
        r._ctrl, r._ctrl_goal, r._ctrl_kind = None, None, None
        r.v_world = (0.0, 0.0)
        r.nav_prefs = {}
        r._shaper = None
        self.step_ms = []
        self.cur_seed = self.seed_base * 1000 + idx
        time.sleep(1.0)                                              # cam bien ve lai ban do (nhu eval_sim)

    def perception_stale(self, max_age=2.0):
        """Ban do LiDAR chi decay() SAU khi integrate() thanh cong -> neu qua max_age s khong decay = ong nhan thuc hong."""
        g = self.robot_ros.SHARED_GRID
        return time.monotonic() - getattr(g, "_last_decay", 0.0) > max_age or time.monotonic() - self.r.local_t > 0.6

    def preflight(self):
        r, st = self.r, self.status
        bad = []
        now = time.monotonic()
        if not r.odom_fresh(0.3):
            bad.append("odom cu > 0.3 s")
        if now - r.local_t > 0.4:
            bad.append("LiDAR (%s) cu > 0.4 s" % self.a.cloud)
        if not self.a.no_depth and now - r.depth_t > 0.6:
            bad.append("D435i depth cu > 0.6 s (hoac chay --no-depth cho CA phien)")
        if now - self.status_t > 2.0:
            bad.append("khong co /go2/status (bridge?)")
        else:
            if (st.get("battery_pct") or 0) < self.a.min_battery:
                bad.append("pin %s %% < %d" % (st.get("battery_pct"), self.a.min_battery))
            if st.get("blocked"):
                bad.append("bridge chan: %s" % st.get("blocked"))
            if (st.get("motor_temp_max") or 0) > 70:
                bad.append("nhiet dong co %s > 70" % st.get("motor_temp_max"))
            bh = st.get("body_height")
            if bh is not None and bh < 0.27:
                bad.append("than thap %.2f (chua dung?)" % bh)
        return bad


def ask(prompt, timeout=None):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if timeout is None:
        return sys.stdin.readline().strip()
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    return sys.stdin.readline().strip() if r else None


def run(a):
    sched = read_schedule(a.out)
    done = done_idx(a.out)
    S = Session(a)
    r, np = S.r, S.np
    print("\n  PHIEN THAT: remote trong tay nguoi giu (L2+B)? nguoi di bo da nghe huong dan? san trong? pin >= %d %%?" % a.min_battery)
    print("  cloud=%s depth=%s cs=%s  cap bridge (go lai dung so khi bat bridge): " % (a.cloud, not a.no_depth, a.cs), end="")
    cap = ask("vx vy wz = ")
    try:
        caps = [float(v) for v in cap.split()]
        assert len(caps) == 3 and caps[0] <= 0.35 and caps[1] <= 0.30 and caps[2] <= 0.80
    except (ValueError, AssertionError):
        sys.exit("cap khong hop le (toi da 0.35 0.30 0.80 theo REAL_PREREG)")
    if ask("  go 'co' de bat dau: ").lower() not in ("co", "yes"):
        sys.exit("da huy")
    if not r.wait_ready(5.0) or not r.wait_sensors(10.0):
        print("  CANH BAO: cam bien chua du (odom/LiDAR/depth) - kiem lai truoc luot dau")
    fn = os.path.join(a.out, "trials.csv")
    new = not os.path.exists(fn)
    f = open(fn, "a", newline="")
    w = csv.DictWriter(f, FIELDS)
    if new:
        w.writeheader()
    hup = {"hit": False}
    pid_dir = os.path.expanduser("~/realprep/pids")
    if not os.path.isdir(pid_dir):
        os.makedirs(pid_dir)
    open(os.path.join(pid_dir, "real_trial.pid"), "w").write(str(os.getpid()))   # deploy/estop.sh dung PID nay

    def on_hup(*_):                                    # SSH rot: dung robot, thoat (bridge tu StopMove sau 0.5-2 s)
        hup["hit"] = True
        r.stop()
    signal.signal(signal.SIGHUP, on_hup)
    try:
        for row in sched:
            idx = int(row["idx"])
            if idx in done or idx < a.start:
                continue
            if hup["hit"]:
                break
            sc, npl = row["scenario"], int(row["people"])
            gx, gy = float(row["gx"]), float(row["gy"])
            desc = [d for s_, _n, _g, _p, d in SCENARIOS if s_ == sc][0]
            while True:
                print("\n================ LUOT %d / %d   %s cap %s ================" % (idx, len(sched), sc, row["pair"]))
                print("  %s" % desc)
                bad = S.preflight()
                if bad:
                    print("  CHUA DAT: " + "; ".join(bad))
                k = ask("  Dat cho o VACH (cung huong)%s. Enter = chay, r = kiem lai, p = nghi (thoat), x = bo luot (ghi ly do): "
                        % (", NGUOI vao vi tri" if npl else ""))
                if k == "r":
                    continue
                break
            if k == "p":
                break
            cfg = CONFIGS[row["label"]]
            if a.cs:
                name, _, kv = cfg.partition(":")
                cfg = name + "~cs" + (":" + kv if kv else "")
            out = dict(idx=idx, scenario=sc, pair=row["pair"], order=row["order"], label=row["label"], config=cfg)
            if k == "x":
                out.update(infra_abort=1, note="bo luot: " + ask("  ly do: "))
                w.writerow(out)
                f.flush()
                continue
            if S.preflight():
                print("  -> van CHUA DAT; luot khong chay.")
                continue
            S.reset(idx, cfg)
            if S.perception_stale():
                print("  -> LiDAR/ban do khong cap nhat sau khi dat lai (xem log '[go2] loi xu ly LiDAR'); luot khong chay.")
                continue
            bagdir = os.path.join(a.out, "bags", "t%03d" % idx)
            if not os.path.isdir(os.path.dirname(bagdir)):
                os.makedirs(os.path.dirname(bagdir))
            topics = ["/go2/odom", "/go2/imu/data", a.cloud, "/go2/cmd_vel", "/go2/status", "/realprep/events",
                      "/go2/govoice/path"]
            if a.bag_depth and not a.no_depth:
                topics.append(a.depth_topic)
            bag = None
            if not a.no_bag:
                # Foxy: chu de la doi so vi tri; ban moi (Jazzy+/Lyrical): --topics
                cmd = ["ros2", "bag", "record", "-o", bagdir] + (topics if os.environ.get("ROS_DISTRO") == "foxy"
                                                                 else ["--topics"] + topics)
                bag = subprocess.Popen(cmd,
                                       stdout=open(bagdir + ".log", "w"), stderr=subprocess.STDOUT,
                                       preexec_fn=os.setsid)
                time.sleep(1.5)
            S.event(ev="start", idx=idx, scenario=sc, pair=row["pair"])
            print("  >>> LUOT %d BAT DAU (Enter = DUNG KHAN CAP) <<<" % idx)
            res = {}
            th = threading.Thread(target=lambda: res.update(msg=r.go_to_pose(gx, gy, name=sc, tol=0.2)), daemon=True)
            t0 = time.monotonic()
            th.start()
            flags = dict(takeover=0, estop=0, safety_stop=0, timeout=0, fall=0)
            vmax, tilt, min_p, why_stop = 0.0, 0.0, 9.0, ""
            lp = None
            while th.is_alive():
                k = ask("", timeout=0.05)
                now = time.monotonic()
                if k is not None:
                    flags["estop"] = 1
                    why_stop = "estop phim"
                    r.stop()
                    break
                st = S.status
                if st.get("blocked") and "remote" in str(st.get("blocked")):
                    flags["takeover"] = 1
                    why_stop = "remote"
                    r.stop()
                    break
                rp = max(abs(st.get("roll_deg") or 0.0), abs(st.get("pitch_deg") or 0.0))
                tilt = max(tilt, rp)
                if rp > 20 or (st.get("blocked") and ("tilted" in str(st.get("blocked")) or "lying" in str(st.get("blocked")))):
                    flags["fall"] = 1
                    why_stop = "nghieng/nam %s" % st.get("blocked")
                    r.stop()
                    break
                p = r.map_pose()
                if lp is not None and now - lp[3] > 0.2:
                    v = math.hypot(p[0] - lp[0], p[1] - lp[1]) / (now - lp[3])
                    vmax = max(vmax, v)
                    lp = (p[0], p[1], p[2], now)
                    if v > math.hypot(caps[0], caps[1]) + a.overspeed:
                        flags["safety_stop"] = 1
                        why_stop = "qua toc %.2f m/s" % v
                        r.stop()
                        break
                elif lp is None:
                    lp = (p[0], p[1], p[2], now)
                if (abs(p[1]) > abs(gy) + a.fence_y or p[0] < min(0.0, gx) - a.fence_back
                        or p[0] > max(0.0, gx) + a.fence_front):
                    flags["safety_stop"] = 1
                    why_stop = "ra ngoai hang rao (%.2f, %.2f)" % (p[0], p[1])
                    r.stop()
                    break
                if now - t0 > 2.5 and S.perception_stale():
                    flags["safety_stop"] = 1
                    why_stop = "nhan thuc ngung (LiDAR cu / ban do khong cap nhat)"
                    r.stop()
                    break
                for tr in r.tracker.movers():
                    min_p = min(min_p, math.hypot(tr["p"][0] - p[0], tr["p"][1] - p[1]))
                if now - t0 > a.timeout:
                    flags["timeout"] = 1
                    why_stop = "het %d s" % a.timeout
                    r.stop()
                    break
            th.join(5.0)
            r._halt()
            dt = time.monotonic() - t0
            S.event(ev="end", idx=idx, why=why_stop or str(res.get("msg", ""))[:120])
            if bag is not None:
                time.sleep(1.0)
                try:
                    os.killpg(os.getpgid(bag.pid), signal.SIGINT)
                    bag.wait(10)
                except Exception:                                       # noqa: BLE001
                    pass
            x, y, _ = r.map_pose()
            err = math.hypot(x - gx, y - gy)
            ls = r.last_stats
            print("  ket thuc: %s (%.1f s, lech %.2f m)" % (why_stop or ls.get("why", "ok"), dt, err))
            cp = ask("  Cham NGUOI? (c = co, Enter = khong): ").lower() == "c"
            co = ask("  Cham VAT? (c = co, Enter = khong): ").lower() == "c"
            inf = ask("  Loi HA TANG khong do bo dieu khien (ssh rot, bridge chet, mat cam bien, Orin treo)? (i = co, Enter = khong): ").lower() == "i"
            note = ask("  Ghi chu (Enter bo qua): ")
            sm = np.array(S.step_ms) if S.step_ms else np.zeros(1)
            sh = getattr(r, "_shaper", None)
            reached = int(err < 0.35)
            fail = cp or co or any(flags.values())
            out.update(t_start=round(time.time() - dt, 1), time_s=round(dt, 1), reached=reached, err_m=round(err, 3),
                       why=why_stop or ls.get("why", "ok" if ls.get("ok") else ""), contact_person=int(cp),
                       contact_obstacle=int(co), infra_abort=int(inf), success=int(reached and not fail and not inf),
                       travel_m=round(ls.get("travel_m", 0.0), 2), brakes=ls.get("brakes", 0), backups=ls.get("backups", 0),
                       replans=ls.get("replans", 0), max_speed=round(vmax, 2), max_tilt_deg=round(tilt, 1),
                       min_person_m=round(min_p, 2), step_ms_p50=round(float(np.percentile(sm, 50)), 1),
                       step_ms_p95=round(float(np.percentile(sm, 95)), 1), step_ms_max=round(float(sm.max()), 1),
                       cs_n=getattr(sh, "n", ""), cs_cap=getattr(sh, "n_cap", ""), cs_rate=getattr(sh, "n_rate", ""),
                       bag=bagdir if bag is not None else "", note=note, **flags)
            w.writerow(out)
            f.flush()
            if inf:
                print("  -> luot ghi la LOI HA TANG; se chay lai (toi da 2 lan, REAL_PREREG §6).")
            if cp:
                print("\n  !!! CHAM NGUOI: DUNG PHIEN theo quy tac an toan R1 (REAL_PREREG §8). Xem video truoc khi tiep tuc.")
                break
            if flags["fall"]:
                print("\n  !!! NGA/NGHIENG: DUNG PHIEN theo quy tac R3.")
                break
    finally:
        r._halt()
        f.close()
        print("\n  Da dung robot. Ket qua: %s" % fn)
        sys.stdout.flush()
        try:
            S.robot_ros.RosBus.get().shutdown()
        except Exception:                                               # noqa: BLE001
            pass
        os._exit(0)                                                     # nhu run_real_ros.py (tranh treo/segfault khi tat rclpy)


def dry(a):
    """Kiem import + lich, khong ROS, khong chuyen dong (chay duoc tren laptop va tren cho)."""
    import robot_ros  # noqa: F401
    import robot_real  # noqa: F401
    from nav_prism2 import PRISM3  # noqa: F401
    from isaac_val.cmd_shaper import CmdShaper  # noqa: F401
    if not os.path.exists(os.path.join(a.out, "schedule.csv")):
        a.force = True
        make_schedule(a)
    s = read_schedule(a.out)
    print("import OK; %d luot; %s" % (len(s), {k: sum(1 for r in s if r["scenario"] == k) for k, *_ in SCENARIOS}))
    for lab, cfg in CONFIGS.items():
        print("  %s = %s  (+~cs: %s)" % (lab, cfg, cfg.split(":")[0] + "~cs:" + cfg.split(":")[1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--make-schedule", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--dry", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261125)
    ap.add_argument("--pairs", type=int, default=20)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--scenarios", default="", help="vd S1,S2 (chay thu); mac dinh ca 5 theo REAL_PREREG")
    ap.add_argument("--start", type=int, default=1, help="bat dau tu luot so (bo qua luot da xong trong trials.csv)")
    ap.add_argument("--cloud", default="/go2/lidar/merged", help="/go2/lidar/merged (L1+OS1) hoac /go2/lidar/points (chi L1)")
    ap.add_argument("--depth-topic", default="/camera/camera/depth/image_rect_raw")
    ap.add_argument("--no-depth", action="store_true", help="khong dung D435i (phai giong nhau CA phien)")
    ap.add_argument("--cs", action="store_true", help="them ~cs (nan lenh) cho CA C1 va B1 (REAL_PREREG §3)")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--overspeed", type=float, default=0.15, help="m/s tren cap vx -> dung (canh gac doc lap bang odom)")
    ap.add_argument("--fence-y", type=float, default=1.8)
    ap.add_argument("--fence-back", type=float, default=1.5)
    ap.add_argument("--fence-front", type=float, default=1.5)
    ap.add_argument("--min-battery", type=int, default=30)
    ap.add_argument("--no-bag", action="store_true")
    ap.add_argument("--bag-depth", action="store_true", help="ghi ca anh depth (nang, ~6 MB/s)")
    a = ap.parse_args()
    a.out = os.path.expanduser(a.out)
    if a.make_schedule:
        make_schedule(a)
    elif a.dry:
        dry(a)
    else:
        run(a)


if __name__ == "__main__":
    main()
