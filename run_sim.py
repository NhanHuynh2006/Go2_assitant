#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_sim.py — GoVoice dieu khien Go2 MO PHONG (Gazebo), 1 hoac nhieu con.

Cung 1 pipeline voi run_real_robot.py (Combo -> Reflex -> LLM -> verifier ->
SafetyGuard -> AsyncExecutor); chi thay "tay chan" SportClient bang ROS 2
(robot_ros.py). Test xong o day roi chay run_real_robot.py tren Jetson.

TRUOC TIEN (terminal 1, workspace ROS):
  ros2 launch go2_voice voice_sim.launch.py               # 1 con
  ros2 launch go2_voice voice_sim.launch.py robots:=2     # 2 con

ROI (terminal 2, thu muc nay):
  source /opt/ros/lyrical/setup.bash && source venv/bin/activate
  python3 run_sim.py                  # go phim
  python3 run_sim.py --voice          # noi qua mic laptop
  python3 run_sim.py --cmd "con một đi thẳng 1 mét" --cmd "cả hai chào đi"   # chay kich ban

Noi chuyen voi 2 con: "con một ...", "con hai ...", "cả hai ...", "tất cả ...",
hoac 2 viec 1 cau: "con một ra cửa, còn con hai vào bếp". Khong goi ten =
con vua goi gan nhat. "Dừng lại" khong goi ten = dung TAT CA.
Lenh giua cac con: "con một đang ở đâu", "cả hai đổi chỗ",
"con hai đi theo con một", "con hai lại chỗ con một".
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import math
import os
import time

import yaml

# Sim chay het tren laptop nay: tim node chi qua localhost (khop voice_sim.launch.py
# localhost:=true). Qua Wi-Fi thi doi IP/DHCP giua chung la mat het robot.
if "--network" not in os.sys.argv:
    os.environ["ROS_AUTOMATIC_DISCOVERY_RANGE"] = "LOCALHOST"
# Fast DDS: voi transport mac dinh (va ca UDPv4 thuan), tin LON (LiDAR ~1 MB, anh depth)
# luc nhan luc khong — tien trinh moi doi khi khong nhan duoc gi (da gap: robot dung vi
# "mat cam bien" ca bai thu; /dev/shm/fastdds_* do tien trinh bi tat ngang de lai).
# LARGE_DATA (TCP + SHM cho du lieu, UDP chi de tim nhau) nhan du 10/15/49 Hz on dinh.
os.environ.setdefault("FASTDDS_BUILTIN_TRANSPORTS", "LARGE_DATA")
# ...va tot nhat la khong dung Fast DDS: voice_sim.launch.py chay sim bang CycloneDDS
# (nhu Go2 that); trung RMW thi on dinh nhat. Dat RMW_IMPLEMENTATION truoc de doi.
os.environ.setdefault("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp")

from assistant_realtime import GoVoiceRT, load_config  # noqa: E402
from async_executor import AsyncExecutor  # noqa: E402
from fleet import FleetExecutor, FleetParser, parse_fleet_intent  # noqa: E402
from reflex_matcher import norm  # noqa: E402
from robot_ros import RosBus, RosRobotTools, discover_robots  # noqa: E402
from safety_guard import SafetyGuard  # noqa: E402
from objects import ObjectCatalog  # noqa: E402
from spatial import parse_relation, parse_spatial, spatial_goal  # noqa: E402

WORLD_DIR = os.path.expanduser("~/ros2_ws/install/unitree_go2_description/share/"
                               "unitree_go2_description/worlds")
WORLD_SDF = os.path.join(WORLD_DIR, "voice_house.sdf")
# Moi the gioi: file .sdf (do vat, cham va cham), file diem den, vung ban do (xmin, ymin, w, h)
WORLDS = {
    "voice_house":  dict(sdf="voice_house.sdf", waypoints="waypoints_sim.yaml",
                         bounds=(-12.0, -12.0, 24.0, 24.0), region=((-4.5, 4.5), (-3.5, 3.5))),
    "voice_office": dict(sdf="voice_office.sdf", waypoints="waypoints_office.yaml",
                         bounds=(-16.0, -11.0, 32.0, 22.0), region=((-14.5, 14.5), (-9.5, 9.5))),
}


def detect_world(default="voice_house"):
    """The gioi Gazebo dang chay (doc ten tu dich vu /world/<ten>/set_pose)."""
    import subprocess
    w = os.environ.get("GOVOICE_WORLD")
    if w:
        return w
    try:
        out = subprocess.run(["gz", "service", "-l"], capture_output=True, text=True,
                             timeout=8).stdout
        for line in out.splitlines():
            if line.startswith("/world/") and line.endswith("/set_pose"):
                name = line.split("/")[2]
                if name in WORLDS:
                    return name
    except Exception:                                          # noqa: BLE001
        pass
    return default


def world_info(name):
    w = dict(WORLDS.get(name, WORLDS["voice_house"]))
    w["name"] = name if name in WORLDS else "voice_house"
    w["sdf_path"] = os.path.join(WORLD_DIR, w["sdf"])
    return w

HERE = os.path.dirname(os.path.abspath(__file__))


class SimGuard(SafetyGuard):
    """SafetyGuard + 2 tool chi co trong sim (di toi toa do / di theo robot khac)."""

    def check(self, act):
        tool = (act.get("tool") or "").lower()
        if tool in ("go_to_pose", "follow") and not self.emergency:
            return act, "fleet tool (ne vat can lo an toan)"
        if tool == "move_dist":
            # cung kiem/kep van toc nhu 'move'; tong thoi gian toi da 60 s (vong kin theo met)
            args = dict(act.get("args") or {})
            dur = args.get("duration", 2.0)
            safe, note = super().check({"tool": "move", "args": dict(args, duration=1.0)})
            if safe is None:
                return None, note
            try:
                dur = float(dur)
            except (TypeError, ValueError):
                return None, "duration khong phai so"
            if not math.isfinite(dur):
                return None, "duration NaN/inf"
            safe = {"tool": "move_dist", "args": dict(safe["args"], duration=min(max(dur, 0.1), 60.0))}
            return safe, note
        return super().check(act)


class GoVoiceSim(GoVoiceRT):
    def __init__(self, cfg, robots, no_tts=False, avoid=None, closed_loop=None,
                 backend=RosRobotTools, backend_kw=None, section="sim"):
        cfg = dict(cfg)
        s = dict(cfg.get(section, {}) or {})
        r = dict(cfg.get("robot", {}))
        if section == "sim":                   # the gioi dang chay: nha nho / van phong lon
            self.world = world_info(detect_world())
            s.setdefault("world_sdf", self.world["sdf_path"])
            if "waypoints_file" not in s or self.world["name"] != "voice_house":
                s["waypoints_file"] = self.world["waypoints"]
            import robot_ros as _rr
            _rr.configure_world(*self.world["bounds"])
            print(f"[sim] the gioi: {self.world['name']} ({self.world['bounds'][2]:.0f} x "
                  f"{self.world['bounds'][3]:.0f} m)")
        else:
            self.world = None
        wp_file = os.path.join(HERE, s.get("waypoints_file", "waypoints_sim.yaml"))
        self.wp_file = wp_file
        r["waypoints_file"] = wp_file          # de Combo biet ten cac diem trong nha sim
        cfg["robot"] = r
        super().__init__(cfg, force_real=False, no_tts=no_tts)
        self.executor.shutdown()               # bo executor dry-run cua lop cha

        with open(wp_file, encoding="utf-8") as f:
            waypoints = yaml.safe_load(f) or {}
        self.place_names = {norm(str(k)): str(k) for k in waypoints}
        self.places = {norm(str(k)): v for k, v in waypoints.items()}
        # Hoi lai "con nao a?" khi co >= 2 robot ma chua goi ten con nao (sim.ask_who)
        self.ask_who = s.get("ask_who", True)
        self.pending = None                 # cau lenh dang cho biet "con nao"
        self.pending_obj = None             # (targets, quan_he, ung_vien) dang cho "cai nao"
        sdf = os.path.expanduser(s.get("world_sdf", WORLD_SDF))
        obj_yaml = s.get("objects_file")
        if obj_yaml and os.path.exists(os.path.join(HERE, obj_yaml)):
            self.catalog = ObjectCatalog.from_yaml(os.path.join(HERE, obj_yaml))
        else:
            self.catalog = ObjectCatalog(sdf) if os.path.exists(sdf) else None
        if self.catalog:
            print(f"[sim] {len(self.catalog.items)} do vat trong nha (go \"có gì\" de xem lai)")
        self.addressed_at = 0.0             # lan cuoi nguoi dung goi ten robot
        spawn = s.get("spawn", {}) or {}
        names = s.get("names", {}) or {}
        avoid = s.get("avoid", True) if avoid is None else avoid
        closed_loop = s.get("closed_loop", True) if closed_loop is None else closed_loop
        self.labels, self.robots, exs = {}, {}, {}
        for i, ns in enumerate(robots):
            label = f"con {i + 1}" if len(robots) > 1 else "go2"
            # gazebo/odom (OdometryPublisher) da la TOA DO WORLD = map, ke ca con spawn o
            # (0, 1.5): goc = 0. (Ban dau cong them cho spawn -> con 2 lech 1.5 m moi
            # lan go_to.) sim.spawn chi can khi dung nguon odom bat dau tu 0 (EKF, robot that).
            origin = spawn.get(ns, [0.0, 0.0, 0.0])
            pre = f"/{ns}" if ns else ""
            robot = backend(
                **(backend_kw or {}),
                ns=ns, label=label, waypoints=waypoints, origin=origin,
                odom_topic=s.get("odom_topic", "{ns}/gazebo/odom").format(ns=pre),
                cloud_topic=s.get("cloud_topic", "{ns}/velodyne_points/points").format(ns=pre),
                depth_topic=s.get("depth_topic", "{ns}/d435i/depth_image").format(ns=pre),
                use_depth=s.get("depth", True),
                max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
                max_vyaw=r.get("max_vyaw", 1.0), max_duration=r.get("max_duration", 6.0),
                closed_loop=closed_loop, avoid=avoid, priority=i,
                shared_map=s.get("shared_map", True),
                notify=lambda t, l=label: self._notify(l, t))
            guard = SimGuard(
                max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
                max_vyaw=r.get("max_vyaw", 1.0), max_duration=r.get("max_duration", 6.0),
                require_stand_before_move=r.get("require_stand_before_move", True))
            guard.mark_standing(True)           # CHAMP spawn la dang dung san
            exs[ns] = AsyncExecutor(robot, guard,
                                    on_event=lambda m, l=label: print(f"   [{l}] {m.strip()}"))
            self.labels[ns], self.robots[ns] = label, robot
            robot.resolver = self._resolve_object
            ok = robot.wait_ready(5.0)
            sens = robot.wait_sensors(10.0) if avoid else False
            print(f"[sim] {label}: ns='{ns or '/'}' odom={'OK' if ok else 'CHUA CO'} "
                  f"LiDAR/D435i={'OK' if sens else 'CHUA CO'} origin={origin} "
                  f"ne_vat_can={'BAT' if avoid else 'TAT'}")
        self.executor = FleetExecutor(exs)
        self.parser = FleetParser(robots, names=names)
        self._viz_cfg = s.get("viz", True)
        self.viz = None
        if self._viz_cfg:                    # RViz: /govoice/map, /govoice/markers (viz_ros.py)
            from viz_ros import Visualizer
            r0 = next(iter(self.robots.values()))
            self.viz = Visualizer(RosBus.get(), self.robots, self.labels, r0.grid,
                                  r0.depth_grid, self.catalog)
            print("[sim] RViz: rviz2 -d ~/ros2_ws/src/unitree_go2_ros2/go2_voice/rviz/"
                  "voice_sim.rviz  (hoac launch voice_sim rviz:=true)")
        self.last_targets = list(robots)
        print("[sim] Robot biet nhung cho nay (hoi \"trong phòng có gì\" bat ky luc nao):")
        self.print_inventory()

    def _notify(self, label, text):
        print(f"   \U0001F4E2 [{label}] {text}")
        self._speak_async(text if len(self.labels) == 1 else f"{label.capitalize()}: {text}")

    def _say(self, text):
        print(f"\U0001F436 Gô: {text}   [Fleet]")
        self._speak_async(text)

    def _place(self, ns):
        key, d = self.robots[ns].nearest_place()
        name = self.place_names.get(key, key)
        return f"ở {name}" if d < 0.8 else f"gần {name}, cách khoảng {d:.1f} mét"

    def _fleet(self, text):
        it = parse_fleet_intent(self.parser, text)
        if it is None:
            return False
        kind, actors, other = it
        actors = actors or self.last_targets
        if kind == "where":
            self._say(". ".join(f"{self.labels[a].capitalize() if len(self.labels) > 1 else 'Mình'} "
                                f"đang {self._place(a)}" for a in actors))
            return True
        if kind == "swap":
            a, b = actors
            pa, pb = self.robots[a].map_pose(), self.robots[b].map_pose()
            self._say(f"{self.labels[a].capitalize()} và {self.labels[b]} đổi chỗ nè!")
            self.executor.enqueue([{"tool": "go_to_pose", "args": {
                "x": pb[0], "y": pb[1], "yaw": pb[2], "name": f"chỗ {self.labels[b]}",
                "tol": 0.35}}], only=[a])
            self.executor.enqueue([{"tool": "go_to_pose", "args": {
                "x": pa[0], "y": pa[1], "yaw": pa[2], "name": f"chỗ {self.labels[a]}",
                "tol": 0.35}}], only=[b])
            return True
        actors = [a for a in actors if a != other]
        if not actors:
            return False
        self.last_targets = actors
        if kind == "follow":
            self._say(f"Dạ, đi theo {self.labels[other]}!")
            self.executor.enqueue([{"tool": "follow", "args": {"leader": other}}], only=actors)
            return True
        if kind == "goto_robot":
            ox, oy, _ = self.robots[other].map_pose()
            self._say(f"Dạ, tới chỗ {self.labels[other]}!")
            for a in actors:
                x, y, _ = self.robots[a].map_pose()
                d = math.hypot(ox - x, oy - y) or 1.0
                k = max(0.0, (d - 0.9) / d)                  # dung cach 0.9 m
                self.executor.enqueue([{"tool": "go_to_pose", "args": {
                    "x": x + k * (ox - x), "y": y + k * (oy - y),
                    "name": f"chỗ {self.labels[other]}", "tol": 0.3}}], only=[a])
            return True
        return False

    INVENTORY_Q = ("co gi", "co nhung gi", "co cai gi", "co do gi", "co nhung cho nao",
                   "di duoc dau", "di duoc nhung dau", "liet ke", "danh sach", "giup do", "huong dan")

    def inventory_text(self):
        """Ten diem + do vat robot biet, nhom theo loai (de in va de doc)."""
        places = sorted({self.place_names.get(k, k) for k in self.places})
        objs = [self.catalog.describe(it) for it in self.catalog.items] if self.catalog else []
        return places, objs

    def print_inventory(self):
        places, objs = self.inventory_text()
        print("   📍 Địa điểm: " + ", ".join(places))
        if objs:
            print("   🪑 Đồ vật:  " + ", ".join(objs))
        print("   💡 Ví dụ: \"đi tới bếp\", \"đi tới cái bàn màu đen\", \"ra bên trái ghế sofa\", "
              "\"cách tủ lạnh 1 mét\", \"lưu chỗ này là góc đọc sách\"")

    def _inventory(self, text):
        """'trong phòng có gì?', 'đi được đâu?', 'help' -> doc ten diem + do vat."""
        t = norm(text).strip(" ?.!")
        if t not in ("help", "?", "h", "tro giup") and not any(q in t for q in self.INVENTORY_Q):
            return False
        if any(w in t for w in ("di toi", "di den", "chay toi")):   # "đi tới chỗ có gì đó": lenh
            return False
        places, objs = self.inventory_text()
        self.print_inventory()
        say = f"Mình đi được tới {len(places)} chỗ: " + ", ".join(places[:8])
        if objs:
            say += f". Trong nhà có {len(objs)} món đồ, ví dụ " + ", ".join(objs[:4])
        self._say(say + ". Danh sách đầy đủ in trên màn hình.")
        return True

    def _unknown(self, text):
        """'đi tới cái giường' ma nha KHONG co giuong -> noi ro, khong di bua (truoc day
        Reflex hieu 'đi tới' = di thang)."""
        import re
        t = norm(text)
        m = re.search(r"\b(?:toi|den|lai|ra|qua|vao|ve)\s+(?:cho\s+|gan\s+)?(?:cai|chiec)\s+(.+)$", t)
        if not m:
            return False
        what = re.sub(r"\s+(a|nha|nhe|di|nao|coi|giup minh|cho minh)$", "", m.group(1)).strip()
        if not what or any(what.startswith(norm(k)) for k in self.places) or \
                (self.catalog and self.catalog.parse(what)):
            return False
        words = [w.strip(" ?.!,") for w in text.split()]
        idx = max(i for i, w in enumerate(words) if norm(w) in ("cai", "chiec"))
        tail = words[idx + 1:]
        while tail and norm(tail[-1]) in ("a", "nha", "nhe", "di", "nao", "coi", "minh", "giup", "cho"):
            tail.pop()
        orig = " ".join(tail) or what
        places, objs = self.inventory_text()
        self._say(f"Trong nhà mình không thấy {orig.strip(' ?.!,')} ạ. Mình biết: "
                  + ", ".join(places[:6]) + (f", và {len(objs)} món đồ như "
                                              + ", ".join(objs[:3]) if objs else "")
                  + ". Hỏi \"trong phòng có gì\" để nghe hết.")
        return True

    def _teach(self, text):
        """'lưu chỗ này là bếp' / 'nhớ chỗ này là phòng ngủ' -> ghi vi tri hien tai vao
        file waypoints. Robot that khong co ban do dat ten san: day bang giong noi."""
        import re
        t = norm(text)
        m = re.search(r"\b(?:luu|nho|danh dau|ghi nho)\s+(?:cho|vi tri|diem)?\s*(?:nay|nay)?"
                      r"\s*(?:la|ten la|lam)\s+(.+)$", t)
        if not m:
            return False
        # lay ten CO DAU tu cau goc (cung vi tri ky tu sau khi bo dau)
        from fleet import _fold
        folded, idx = _fold(text)
        name = text[idx[m.start(1)]:].strip(" .!?,").strip()
        if not name:
            return False
        targets = self.last_targets[:1]
        x, y, yaw = self.robots[targets[0]].map_pose()
        self.add_place(name, x, y, yaw, how="day bang giong noi")
        self._say(f"Dạ, nhớ rồi: đây là {name}.")
        return True

    def add_place(self, name, x, y, yaw, how="cham tren ban do"):
        """Them 1 diem co ten (giong noi 'lưu chỗ này là X' hoac cham tren ban do Studio)."""
        entry = [round(float(x), 2), round(float(y), 2), round(float(yaw), 2)]
        # ghi them 1 dong (giu nguyen chu thich cu); trung ten thi dong sau thang (YAML)
        with open(self.wp_file, "a", encoding="utf-8") as f:
            f.write(f"{name}: {entry}   # {how} {time.strftime('%Y-%m-%d %H:%M')}\n")
        key = norm(name)
        self.places[key] = entry
        self.place_names[key] = name
        for r in self.robots.values():
            r.waypoints[key] = entry
        self.combo.locations = sorted(set(self.combo.locations) | {name},
                                      key=lambda w: -len(norm(w)))   # dai truoc (combo_matcher)
        return entry

    def _resolve_object(self, location, pose):
        """go_to(location) tu LLM: 'bàn màu đen' -> toa do (chon mon gan nhat)."""
        if not self.catalog or pose is None:
            return None
        hits = self.catalog.find(location, near=pose[:2])
        if not hits:
            return None
        (gx, gy, gyaw), _ = self.catalog.approach(hits[0], pose[:2])
        return gx, gy, gyaw, self.catalog.describe(hits[0])

    def _object(self, text):
        """'đi tới cái bàn màu đen', 'bên trái cái ghế tím' -> go_to_pose. Hoi lai neu mo ho."""
        if not self.catalog:
            return False
        segs = self.parser.split(text)
        if len(segs) != 1:
            return False
        targets, part = segs[0]
        if self.pending_obj is not None:               # dang cho tra loi "cai nao"
            t0, rel, cands = self.pending_obj
            p = self.catalog.parse(part)
            color = p[1] if p else None
            words = norm(part)
            pick = [c for c in cands if (color and c["color"] == color) or
                    norm(c["label"]) in words or (color is None and norm(c["color"]) in words)]
            if len(pick) == 1:
                self.pending_obj = None
                return self._go_object(t0, rel, pick[0])
            self.pending_obj = None                    # tra loi khong khop: bo cau hoi
        p = self.catalog.parse(part)
        if p is None:
            return False
        noun, color = p
        if color is None and noun in self.places:      # "ra bàn" = diem dat ten (giu nhu cu)
            return False
        targets = targets or self._who(text)
        if targets is None:
            return True
        here = self.robots[targets[0]].map_pose()
        hits = self.catalog.find(part, near=here[:2])
        rel = parse_relation(part)
        if not hits:
            same = [it for it in self.catalog.items if noun in it["aliases"]]
            have = ", ".join(sorted({it["color"] for it in same}))
            pn = self.catalog.pretty.get(noun, noun)
            self._say(f"Trong nhà không có {pn if not color else pn + ' màu ' + color} ạ."
                      + (f" Chỉ có màu {have} thôi." if have else ""))
            return True
        if len(hits) > 1:
            self.pending_obj = (targets, rel, hits[:3])
            opts = " hay ".join(self.catalog.describe(h) for h in hits[:3])
            self._say(f"Dạ, {opts} ạ?")
            return True
        return self._go_object(targets, rel, hits[0])

    def _go_object(self, targets, rel, it):
        here = self.robots[targets[0]].map_pose()
        (gx, gy, gyaw), wp = self.catalog.approach(it, here[:2])
        label = self.catalog.describe(it)
        if rel is not None:
            gx, gy, gyaw = spatial_goal(wp, rel[0], rel[1])
            words = {"trai": "bên trái", "phai": "bên phải", "canh": "bên cạnh", "sau": "phía sau",
                     "truoc": "phía trước", "cach": f"cách {rel[1] or 1:g} mét"}
            label = f"{words[rel[0]]} {label}"
        self._say(f"Dạ, tới {label}!")
        self.executor.enqueue([{"tool": "go_to_pose", "args": {
            "x": gx, "y": gy, "yaw": gyaw, "name": label}}], only=targets)
        return True

    def _spatial(self, text):
        """'bên trái cái bàn', 'sau ghế', 'cách cửa 1 mét' -> go_to_pose (y tuong VLMaps)."""
        segs = self.parser.split(text)
        if len(segs) != 1:
            return False
        targets, part = segs[0]
        sp = parse_spatial(part, self.places)
        if sp is None:
            return False
        name, rel, dist = sp
        gx, gy, gyaw = spatial_goal(self.places[name], rel, dist)
        targets = targets or self._who(text)
        if targets is None:
            return True
        words = {"trai": "bên trái", "phai": "bên phải", "canh": "bên cạnh", "sau": "phía sau",
                 "truoc": "phía trước", "cach": f"cách {dist or 1:g} mét"}
        label = f"{words[rel]} {self.place_names.get(name, name)}"
        self._say(f"Dạ, ra {label}!")
        self.executor.enqueue([{"tool": "go_to_pose", "args": {
            "x": gx, "y": gy, "yaw": gyaw, "name": label}}], only=targets)
        return True

    def _who(self, text):
        """Chua goi ten ai: 1 con -> no; nhieu con -> hoi lai (hoac con vua goi)."""
        if len(self.labels) == 1:
            return list(self.labels)
        if not self.ask_who or time.time() - self.addressed_at < 120.0:
            return self.last_targets
        self.pending = text
        names = ", ".join(self.labels[n] for n in self.labels)
        self._say(f"Dạ, {names} hay cả hai ạ?")
        return None

    # Tu chinh CACH NE trong cau lenh (PRISM 'lang'): ap dung cho lenh nay
    PREF_WORDS = [
        (("đi chậm", "chậm thôi", "chậm lại", "từ từ", "chầm chậm"), ("di cham", "cham thoi", "cham lai", "tu tu"),
         {"speed": 0.6}),
        (("đi nhanh", "nhanh lên", "nhanh nhanh"), ("di nhanh", "nhanh len"), {"speed": 1.2}),
        (("tránh xa người", "né người", "tránh người", "cẩn thận"), ("tranh xa nguoi", "ne nguoi", "tranh nguoi", "can than"),
         {"people_margin": 0.4, "caution": 1.5}),
    ]

    def _set_prefs(self, text):
        low, t = text.lower(), norm(text)
        prefs = {}
        has_marks = any(ord(ch) > 127 for ch in text)
        for acc, plain, val in self.PREF_WORDS:
            if (has_marks and any(w in low for w in acc)) or (not has_marks and any(w in t for w in plain)):
                prefs.update(val)
        for r in self.robots.values():
            r.nav_prefs = prefs
        if prefs:
            print(f"   🎛  cach ne theo lenh: {prefs}")

    def process(self, text, stt_ms=0.0):
        text = text or ""
        self._set_prefs(text)
        from assistant_realtime import EMERGENCY_WORDS
        if any(w in norm(text) for w in EMERGENCY_WORDS) and not self.parser.split(text)[0][0]:
            self.pending = None
            self.executor.explicit = False                  # dung TAT CA, khong hoi lai
            return super().process(text, stt_ms=stt_ms)
        if (self._inventory(text) or self._teach(text) or self._fleet(text)
                or self._object(text) or self._spatial(text) or self._unknown(text)):
            return
        for targets, part in self.parser.split(text):
            explicit = targets is not None
            if explicit:
                self.last_targets = targets
                self.addressed_at = time.time()
                if not part.strip() and self.pending:      # tra loi "con nao": "con hai"
                    part, self.pending = self.pending, None
                    print(f"   🎯 -> {', '.join(self.labels[n] for n in targets)}: {part}")
                    return self.process(" ".join(
                        ["con " + str(list(self.labels).index(n) + 1) for n in targets][:1]
                        if len(targets) == 1 else ["cả hai"]) + " " + part, stt_ms)
            elif len(self.labels) > 1 and self._who(part) is None:
                return
            self.executor.targets = targets if explicit else self.last_targets
            self.executor.explicit = explicit
            who = ", ".join(self.labels[n] for n in self.executor.targets)
            if not part.strip():
                print(f"   \U0001F3AF chon {who}")
                self._speak_async("Dạ!")
                continue
            if len(self.labels) > 1:
                print(f"   \U0001F3AF -> {who}: {part}")
            super().process(part, stt_ms=stt_ms)

    def wait_idle(self, timeout=300.0):
        t0 = time.time()
        while time.time() - t0 < 1.5 and not self.executor.is_busy():
            time.sleep(0.05)                     # cho worker nhan viec (tranh bao 'xong' som)
        t_end = time.time() + timeout
        while time.time() < t_end and self.executor.is_busy():
            time.sleep(0.1)


def main():
    ap = argparse.ArgumentParser(description="GoVoice — dieu khien Go2 mo phong")
    ap.add_argument("--voice", action="store_true", help="noi qua mic (mac dinh: go phim)")
    ap.add_argument("--both", action="store_true", help="NOI va GO cung luc (mic + ban phim)")
    ap.add_argument("--wake", action="append", default=None, metavar="TU",
                    help='chi nghe cau co goi ten, vd --wake "gô ơi" (go phim thi khong can)')
    ap.add_argument("--mic-robot", action="store_true", help="mic robot qua UDP bridge")
    ap.add_argument("--robots", nargs="*", default=None,
                    help="namespace cac robot (mac dinh: tu tim; '' = 1 con khong namespace)")
    ap.add_argument("--cmd", action="append", default=[],
                    help="chay lan luot cac cau lenh nay roi thoat (lap lai duoc)")
    ap.add_argument("--no-avoid", action="store_true", help="tat ne vat can (de so sanh)")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--network", action="store_true",
                    help="tim node qua mang (mac dinh chi localhost; dung khi sim launch localhost:=false)")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    a = ap.parse_args()

    cfg = load_config(a.config)
    if a.wake:
        cfg.setdefault("stt", {})["wake_words"] = a.wake
    if a.mic_robot:
        cfg.setdefault("audio", {})["backend"] = "udp"

    robots = a.robots if a.robots is not None else discover_robots(wait_s=3.0)
    if not robots:
        print("Khong thay Go2 nao (khong co topic */body_pose). Da chay sim chua?\n"
              "  ros2 launch go2_voice voice_sim.launch.py [robots:=2]")
        return
    print(f"[sim] tim thay {len(robots)} robot: {[r or '/' for r in robots]}")

    gv = GoVoiceSim(cfg, robots, no_tts=a.no_tts, avoid=False if a.no_avoid else None)
    try:
        if a.cmd:
            for c in a.cmd:
                print(f"\nBạn: {c}")
                gv.process(c)
                gv.wait_idle()
        elif a.both:
            gv.run_both()
        elif a.voice:
            gv.run_voice()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.stop_all()
        gv.executor.shutdown()
        RosBus.get().shutdown()
        print("\nDa dung robot. Tam biet!")


if __name__ == "__main__":
    main()
