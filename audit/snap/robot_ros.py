#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_ros.py — "TAY CHAN" ROS 2 cua GoVoice: CUNG interface voi RobotTools
(execute / move / action / stop / go_to) nhung lai robot qua topic ROS 2
thay vi SportClient. Dung cho MO PHONG Gazebo (unitree_go2_sim / CHAMP).

Moi robot = 1 namespace ("" cho 1 con, "go2_0", "go2_1"... cho nhieu con):
  <ns>/cmd_vel                 geometry_msgs/Twist   -> CHAMP buoc di
  <ns>/body_pose               geometry_msgs/Pose    -> CHAMP nghieng/ha than (dong tac)
  <ns>/gazebo/odom             nav_msgs/Odometry     <- vi tri (vong kin)
  <ns>/velodyne_points/points  sensor_msgs/PointCloud2 <- LiDAR (ne vat can)
  <ns>/imu/data                sensor_msgs/Imu       <- roll/pitch de loc mat dat

Khac RobotTools:
  1. move() chay VONG KIN tren odom (gait CHAMP chi dat ~41% van toc lenh), va
     PHANH khi LiDAR thay vat can tren huong di.
  2. action() (chao, nhay, ngoi...) bang tu the than qua /body_pose.
  3. go_to() NE VAT CAN: ban do tu LiDAR (nav_local.OccGrid, chia se giua cac
     robot), A* + pure pursuit, lap lai ke hoach moi 1 s, phanh phan xa, lui lai
     khi ket. Nhieu robot: robot khac la vat can dong + luat nhuong duong
     (con nao GAN DICH hon thi duoc di truoc; doi qua lau thi tu nang uu tien).
"""

import math
import threading
import time

import numpy as np

import os

from nav_local import (DWA, MPPI, PRISM, BlobTracker, EnsemblePolicy, OccGrid, PolicyMPPI,
                       RLPolicy, _resample, cpa, lookahead, obstacle_field, path_length, plan)
from nav_prism2 import PRISM2
from reflex_matcher import norm

BODY_HALF_L, BODY_HALF_W = 0.35, 0.16      # Go2: ~0.70 x 0.31 m
LETHAL, SOFT = 0.40, 0.80                   # vung cam / vung ngai quanh vat khi lap duong
FLEET = []                                  # moi RosRobotTools dang chay (de thay nhau)
SHARED_GRID = OccGrid()                     # ban do chung (lop LiDAR): con nay thay, con kia biet
# lop camera depth D435i (xoa chi trong FOV). Can 3 khung lien tiep moi tin (hit=1,
# thresh=3): nhieu depth va than lac de ra vat ma 1-2 khung.
SHARED_DEPTH = OccGrid(hit=1, miss=1, occ_thresh=3)


def configure_world(xmin, ymin, width, height):
    """Doi kich thuoc ban do chung cho the gioi lon (vd voice_office 30 x 20 m).
    Goi TRUOC khi tao robot (robot lay SHARED_GRID luc khoi tao)."""
    global SHARED_GRID, SHARED_DEPTH
    SHARED_GRID = OccGrid(xmin=xmin, ymin=ymin, width=width, height=height)
    SHARED_DEPTH = OccGrid(xmin=xmin, ymin=ymin, width=width, height=height,
                           hit=1, miss=1, occ_thresh=3)
DEPTH_HALF_FOV = math.radians(40.0)         # D435i: 87 do ngang, bot mep cho chac


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def _clamp(v, lim):
    return max(-lim, min(lim, v))


def _yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def _quat_matrix(x, y, z, w):
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def cloud_xyz(msg):
    """PointCloud2 -> (N, 3) float32, bo NaN/inf. Khong can sensor_msgs_py."""
    off = {f.name: f.offset for f in msg.fields}
    dt = np.dtype({"names": ["x", "y", "z"], "formats": ["<f4"] * 3,
                   "offsets": [off["x"], off["y"], off["z"]], "itemsize": msg.point_step})
    n = msg.width * msg.height
    a = np.frombuffer(msg.data, dtype=dt, count=n)
    p = np.stack([a["x"], a["y"], a["z"]], axis=1)
    return p[np.isfinite(p).all(axis=1)]


class RosBus:
    """1 node rclpy dung chung cho moi robot, spin o thread nen."""
    _inst = None
    _lock = threading.Lock()

    @classmethod
    def get(cls):
        with cls._lock:
            if cls._inst is None:
                cls._inst = cls()
            return cls._inst

    def __init__(self):
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        import tf2_ros
        if not rclpy.ok():
            rclpy.init()
        self.rclpy = rclpy
        self.node = rclpy.create_node("govoice_sim")
        self.tf_buffer = tf2_ros.Buffer()
        # static_only: chi can moc gan cam bien (co dinh). Nghe ca /tf (moi khop chan,
        # hang tram tin/giay) trong Python chiem GIL va lam vong dieu khien dung tung giay.
        try:
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node,
                                                         static_only=True)
        except TypeError:                     # Foxy (robot that): chua co static_only
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self.node)
        # SingleThreaded: do tren may nay, MultiThreadedExecutor cua rclpy chi nhan
        # odom 5-15 Hz (le ra 50) va LiDAR tre toi 2.5 s; don luong nhan du 49/98/10/15 Hz
        # (odom/IMU/LiDAR/depth). Moi callback chi ~1-3 ms nen 1 luong la du.
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        threading.Thread(target=self.executor.spin, daemon=True).start()
        import atexit
        import signal
        atexit.register(self.shutdown)
        prev = signal.getsignal(signal.SIGTERM)

        def _term(signum, frame):
            self.shutdown()
            if callable(prev):
                prev(signum, frame)
            raise SystemExit(0)
        try:
            signal.signal(signal.SIGTERM, _term)
        except ValueError:                   # khong o luong chinh
            pass

    def topics(self):
        return dict(self.node.get_topic_names_and_types())

    def shutdown(self):
        """Dong DDS DUNG CACH. Thoat ngang (os._exit, kill -9) lam bridge cua sim ngung gui
        tin lon (LiDAR, depth) cho moi tien trinh sau — da do: 0 Hz cho toi khi khoi dong
        lai sim. Goi tu atexit + SIGTERM nen Ctrl+C / kill thuong deu an toan."""
        if getattr(self, "_closed", False):
            return
        self._closed = True
        try:
            self.executor.shutdown(timeout_sec=1.0)
        except Exception:
            pass
        try:
            self.node.destroy_node()
        except Exception:
            pass
        try:
            if self.rclpy.ok():
                self.rclpy.shutdown()
        except Exception:
            pass


def discover_robots(wait_s=2.0):
    """Tim namespace cac Go2 dang chay: moi '<ns>/body_pose' la 1 con."""
    bus = RosBus.get()
    t_end = time.time() + wait_s

    def scan():
        return sorted(t[:-len("body_pose")].strip("/")
                      for t in bus.topics() if t.endswith("/body_pose"))
    found = []
    while time.time() < t_end:
        found = scan()
        if found:
            time.sleep(0.3)      # cho them chut de thay du con thu 2
            return scan()
        time.sleep(0.2)
    return found


# Dong tac = chuoi khung hinh (t, z, roll, pitch, yaw) noi suy tuyen tinh.
# z la do lech so voi chieu cao dung (0.225 m); pitch > 0 = chui dau xuong.
_CHOREO = {
    "standup":   [(0.0, None), (1.0, (0, 0, 0, 0))],
    "balance":   [(0.0, None), (0.6, (0, 0, 0, 0))],
    "standdown": [(0.0, None), (1.5, (-0.10, 0, 0, 0))],
    "hello":     [(0.0, None), (0.6, (-0.02, 0, -0.25, 0)),
                  (1.0, (-0.02, 0.20, -0.25, 0)), (1.4, (-0.02, -0.20, -0.25, 0)),
                  (1.8, (-0.02, 0.20, -0.25, 0)), (2.2, (-0.02, -0.20, -0.25, 0)),
                  (2.8, (0, 0, 0, 0))],
    "stretch":   [(0.0, None), (1.0, (-0.04, 0, 0.30, 0)), (2.0, (-0.04, 0, 0.30, 0)),
                  (3.0, (-0.02, 0, -0.20, 0)), (3.8, (0, 0, 0, 0))],
    "dance1":    [(0.0, None)] + [(0.5 * (i + 1), (-0.04 * (i % 2), 0.25 * (1 if i % 2 else -1), 0, 0))
                                  for i in range(8)] + [(4.6, (0, 0, 0, 0))],
    "dance2":    [(0.0, None)] + [(0.5 * (i + 1), (-0.03, 0, 0.12 * (1 if i % 2 else -1),
                                                   0.35 * (1 if (i // 2) % 2 else -1)))
                                  for i in range(8)] + [(4.6, (0, 0, 0, 0))],
    "heart":     [(0.0, None)] + [(0.25 * (i + 1), (0, 0.15 * math.cos(i * math.pi / 4),
                                                    0.15 * math.sin(i * math.pi / 4), 0))
                                  for i in range(16)] + [(4.4, (0, 0, 0, 0))],
}


class RosRobotTools:
    def __init__(self, ns="", label=None, odom_topic=None, waypoints=None,
                 origin=(0.0, 0.0, 0.0), max_vx=0.6, max_vy=0.4, max_vyaw=1.0,
                 max_duration=6.0, closed_loop=True, goto_speed=0.35, goto_turn=0.8,
                 avoid=True, cloud_topic=None, imu_topic=None, shared_map=True,
                 base_height=0.24, priority=0, notify=None, depth_topic=None, use_depth=True):
        from geometry_msgs.msg import Pose, Twist
        from nav_msgs.msg import Odometry
        from rclpy.qos import qos_profile_sensor_data as SENSOR_QOS
        from sensor_msgs.msg import CameraInfo, Image, Imu, PointCloud2
        self.Twist, self.Pose = Twist, Pose
        self.ns = ns.strip("/")
        self.label = label or (self.ns or "go2")
        pre = f"/{self.ns}" if self.ns else ""
        self.base_frame = f"{self.ns}/base_link" if self.ns else "base_link"
        self.bus = RosBus.get()
        node = self.bus.node
        self.cmd_pub = node.create_publisher(Twist, f"{pre}/cmd_vel", 10)
        from nav_msgs.msg import Path
        self.Path = Path
        # quy dao dang di (xem bang RViz: Add -> Path, topic nay, Fixed Frame = map)
        self.path_pub = node.create_publisher(Path, f"{pre}/govoice/path", 1)
        self.pose_pub = node.create_publisher(Pose, f"{pre}/body_pose", 1)
        self.odom_topic = odom_topic or f"{pre}/gazebo/odom"
        node.create_subscription(Odometry, self.odom_topic, self._on_odom, SENSOR_QOS)
        self.limits = (max_vx, max_vy, max_vyaw, max_duration)
        self.closed_loop, self.avoid = closed_loop, avoid
        self.goto_speed, self.goto_turn = goto_speed, goto_turn
        self.origin = tuple(float(v) for v in origin)      # odom cua con nay trong frame map
        self.waypoints = {norm(str(k)): v for k, v in (waypoints or {}).items()}
        self.priority = priority
        self.use_depth = use_depth          # tat duoc luc chay (ablation: chi LiDAR)
        self.detour_enabled = True          # di thang gap vat: vong qua (False = chi phanh)
        self.resolver = None                # (location, pose) -> (x, y, yaw, nhan) | None
        # loc diem LiDAR roi vao THAN/CHAN cua chinh minh (base_link). Sim cung can: chan
        # sau vung ra sau ~0.3-0.45 m, LiDAR thay -> "lui lai 1 met" phanh ngay (da gap)
        self.body_box = ((-0.45, 0.42), (-0.24, 0.24), (-0.5, 0.2))
        self.tracker = BlobTracker()        # vat DONG (nguoi) tu LiDAR: vi tri + van toc
        self.evade_enabled = True           # nguoi lao toi -> ne ngang / lui (False = chi dung)
        self.people_aware = True            # dung tracker (du doan nguoi) — ablation tat duoc
        self.state = "chờ lệnh"             # hien len RViz (viz_ros.py)
        self.coordinate = True              # nhuong duong + coi robot khac la vat can
        # BO DIEU KHIEN khi di toi dich: "mppi" (muot, mac dinh) | "dwa" | "pp" (ban cu:
        # pure pursuit + dung lai quay mat + phanh phan xa — giu de so sanh)
        self.controller = os.environ.get("GOVOICE_CONTROLLER", "mppi")
        self.vel_gain = 0.5                 # van toc thuc / lenh (uoc luong online; CHAMP ~0.4-0.5)
        self.vel_gains = np.array([0.5, 0.5, 0.5])   # rieng tung truc vx, vy, wz (PRISM)
        self.nav_prefs = {}                 # tu cau lenh: speed / people_margin / caution
        self.v_world = (0.0, 0.0)           # van toc do duoc (map) - robot khac dung de du doan
        self.local_traj = []                # quy dao MPPI du doan (Studio ve)
        self._ctrl, self._ctrl_goal = None, None
        self._notify_cb = notify or (lambda text: None)
        self._last_note = ("", 0.0)
        self.base_height = base_height
        self.odom = None            # (x, y, yaw, t_mono) trong frame odom
        self.rp = (0.0, 0.0)        # roll, pitch tu IMU
        self.local_obs = np.empty((0, 2))   # vat can quanh robot, frame than (da can bang)
        self.local_t = 0.0
        self.grid = SHARED_GRID if shared_map else OccGrid(xmin=SHARED_GRID.x0, ymin=SHARED_GRID.y0, width=SHARED_GRID.nx * SHARED_GRID.res, height=SHARED_GRID.ny * SHARED_GRID.res)
        self.depth_grid = SHARED_DEPTH if shared_map else OccGrid(hit=1, miss=1, occ_thresh=3)
        self.local_depth = np.empty((0, 2))  # vat can tu camera, frame than (can bang)
        self.depth_t = 0.0
        self._lidar_tf = None
        self._cam_tf = None
        self._depth_count = 0
        self._rays = None                    # huong tia cua cac pixel da chon (frame camera)
        self._K = None                       # (fx, fy, cx, cy) tu camera_info
        self.cpu = {"lidar_ms": 0.0, "depth_ms": 0.0}
        self.body = (0.0, 0.0, 0.0, 0.0)
        self.last_place = None      # cho "cho cu"
        self.goal = None            # dich dang toi (map), cho luat nhuong duong
        self.navigating = False
        self.last_stats = {}
        self._cancel = threading.Event()
        self._motion = threading.Lock()
        self._scan_count = 0
        if avoid:
            # best effort: voi reliable + tin lon, ben gui cho ben nhan va du lieu den tre
            node.create_subscription(PointCloud2, cloud_topic or f"{pre}/velodyne_points/points",
                                     self._on_cloud, SENSOR_QOS)
            node.create_subscription(Imu, imu_topic or f"{pre}/imu/data", self._on_imu, SENSOR_QOS)
            if use_depth:
                # anh depth (400 kB) thay vi PointCloud2 (3.2 MB/khung): o 15 Hz, giai ma
                # point cloud trong Python an het CPU, ca vong dieu khien bi dung tung giay
                # va robot phanh tre (da do: tuoi du lieu depth 0.6-1.2 s).
                depth_topic = depth_topic or f"{pre}/d435i/depth_image"
                node.create_subscription(Image, depth_topic, self._on_depth, SENSOR_QOS)
                # intrinsics that (realsense-ros: .../depth/camera_info); sim: cung co
                info = depth_topic.rsplit("/", 1)[0] + "/camera_info"
                node.create_subscription(CameraInfo, info, self._on_cam_info, SENSOR_QOS)
        FLEET.append(self)
        # CHAMP KHONG co timeout lenh van toc: tien trinh truoc bi tat giua chung thi
        # robot cu di mai voi lenh cuoi. Gui lenh dung ngay khi khoi dong.
        # (robot that thi go2_hardware_bridge tu StopMove sau 0.5 s khong co lenh)
        threading.Timer(1.0, self._halt).start()

    def notify(self, text):
        """Bao bang loi (TTS); khong nhac lai cung 1 cau trong 4 s."""
        if text == self._last_note[0] and time.monotonic() - self._last_note[1] < 4.0:
            return
        self._last_note = (text, time.monotonic())
        self._notify_cb(text)

    # ---------------- cam bien ----------------
    def _on_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.odom = (p.x, p.y, _yaw_of(q), time.monotonic())

    def _on_imu(self, msg):
        q = msg.orientation
        roll = math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y))
        pitch = math.asin(max(-1.0, min(1.0, 2 * (q.w * q.y - q.z * q.x))))
        self.rp = (roll, pitch)

    def _tf_to_base(self, frame):
        t = self.bus.tf_buffer.lookup_transform(self.base_frame, frame,
                                                self.bus.rclpy.time.Time())
        q, tr = t.transform.rotation, t.transform.translation
        return _quat_matrix(q.x, q.y, q.z, q.w), np.array([tr.x, tr.y, tr.z])

    def _lidar_to_base(self, frame):
        if self._lidar_tf is None:
            try:
                self._lidar_tf = self._tf_to_base(frame)
            except Exception:
                # Velodyne trong unitree_go2_description: (0.2, 0, ~0.12) so voi base_link
                return np.eye(3), np.array([0.2, 0.0, 0.12])
        return self._lidar_tf

    def _level(self, pb):
        """Diem trong base_link -> frame than 'can bang' (bo roll/pitch theo IMU)."""
        roll, pitch = self.rp
        cr, sr, cp, sp = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch)
        Rl = np.array([[cp, sp * sr, sp * cr], [0, cr, -sr], [-sp, cp * sr, cp * cr]])
        return pb @ Rl.T

    def _on_cam_info(self, msg):
        if self._K is None and msg.k[0] > 0:
            self._K = (msg.k[0], msg.k[4], msg.k[2], msg.k[5])
            self._rays = None                     # tinh lai tia theo intrinsics that

    def _depth_rays(self, w, h, step=3, hfov=1.518):
        """Tia (x toi, y trai, z len) cho moi pixel thu `step`, mo hinh pinhole.
        Dung camera_info neu co; khong thi hfov = 87 do cua D435i."""
        if self._K is not None:
            fx, fy, cx, cy = self._K
        else:
            fx = fy = (w / 2) / math.tan(hfov / 2)
            cx, cy = (w - 1) / 2, (h - 1) / 2
        v, u = np.mgrid[0:h:step, 0:w:step]
        self._pix = (v.ravel(), u.ravel())
        x = np.ones(v.size)
        y = -(u.ravel() - cx) / fx
        z = -(v.ravel() - cy) / fy
        self._rays = np.stack([x, y, z], axis=1)

    def _depth_points(self, msg):
        """sensor_msgs/Image 32FC1 (m, do sau doc truc quang) -> (N, 3) frame camera."""
        if msg.encoding not in ("32FC1", "16UC1"):
            return np.empty((0, 3))
        if self._rays is None:
            self._depth_rays(msg.width, msg.height)
        dt = np.float32 if msg.encoding == "32FC1" else np.uint16
        img = np.frombuffer(msg.data, dtype=dt).reshape(msg.height, -1)[:, :msg.width]
        d = img[self._pix].astype(np.float32)
        if msg.encoding == "16UC1":
            d *= 0.001
        ok = np.isfinite(d) & (d > 0.1) & (d < 4.0)
        return self._rays[ok] * d[ok, None]

    def _on_depth(self, msg):
        """D435i: phu vung mu cua LiDAR (0.35 m truoc mat) va vat thap duoi tia LiDAR."""
        self._depth_count += 1
        if not self.use_depth:
            return
        pose = self.map_pose()
        if pose is None:
            return
        t_cpu = time.perf_counter()
        try:
            if self._cam_tf is None:
                try:
                    self._cam_tf = self._tf_to_base(msg.header.frame_id)
                except Exception:
                    return                                # TF chua toi (vua khoi dong)
            R, t = self._cam_tf
            p = self._depth_points(msg)                     # ~11k pixel (1/9 anh 424x240)
            pl = self._level(p @ R.T + t)
            z = pl[:, 2] + self.base_height + self.body[0]   # body[0]: ha than khi 'ngoi'
            r = np.hypot(pl[:, 0], pl[:, 1])
            # Nguong do cao tang theo r: camera chui 20 do nhin san o 0.5-1 m, than lac
            # +-3 do khi di -> san bi doc thanh "vat 5-8 cm" (vat ma ngay cua ra vao, robot
            # phanh mai khong toi dich). 0.06 + 0.05 r: vat thap 12 cm van thay trong ~1.2 m.
            near = (r > 0.40) & (r < 4.0)
            is_obs = (z > 0.06 + 0.05 * r) & (z < 0.9) & near
            obs = pl[is_obs][:, :2]
            self.local_depth, self.depth_t = obs, time.monotonic()
            if self._depth_count % 2:
                return
            x, y, yaw = pose
            c, s = math.cos(yaw), math.sin(yaw)
            rot = np.array([[c, s], [-s, c]])
            w = obs @ rot + [x, y]
            free = pl[near & ~is_obs][::4, :2] @ rot + [x, y]
            for o in FLEET:
                if o is not self and o.odom is not None:
                    ox, oy, _ = o.map_pose()
                    w = w[np.hypot(w[:, 0] - ox, w[:, 1] - oy) > 0.55]
            sx, sy = x + c * t[0] - s * t[1], y + s * t[0] + c * t[1]
            w = self.drop_dynamic(w, time.monotonic())
            self.depth_grid.integrate(sx, sy, w, max_range=3.5, clear_range=2.5,
                                      fov=(yaw, DEPTH_HALF_FOV), free_pts=free)
        except Exception as e:                                # noqa: BLE001
            print(f"[{self.label}] loi xu ly depth: {e!r}")
        finally:
            ms = (time.perf_counter() - t_cpu) * 1000
            self.cpu["depth_ms"] = 0.9 * self.cpu["depth_ms"] + 0.1 * ms

    def _on_cloud(self, msg):
        self._scan_count += 1
        pose = self.map_pose()
        if pose is None:
            return
        t_cpu = time.perf_counter()
        try:
            p = cloud_xyz(msg)
            R, t = self._lidar_to_base(msg.header.frame_id)
            pb = p @ R.T + t
            if self.body_box is not None:                     # L1 that nhin thay chan minh
                (x0, x1), (y0, y1), (z0, z1) = self.body_box
                inside = ((pb[:, 0] > x0) & (pb[:, 0] < x1) & (pb[:, 1] > y0) &
                          (pb[:, 1] < y1) & (pb[:, 2] > z0) & (pb[:, 2] < z1))
                pb = pb[~inside]
            pl = self._level(pb)                             # than robot da "can bang"
            z = pl[:, 2] + self.base_height + self.body[0]   # body[0]: ha than khi 'ngoi'                  # do cao so voi mat dat
            r = np.hypot(pl[:, 0], pl[:, 1])
            # nguong do cao TANG theo tam xa: CHAMP lac than +-3 do khi di, nen tia
            # cham dat o 1.3 m bi doc thanh "vat cao 7 cm" -> ve ra cac vong cung ma
            # tren ban do (da gap: robot ket 'khong co duong' sau vai lan go_to).
            zmin = 0.06 + 0.06 * r
            near = (r > 0.42) & (r < 6.0)
            is_obs = (z > zmin) & (z < 0.9) & near
            obs = pl[is_obs][:, :2]
            self.local_obs, self.local_t = obs, time.monotonic()
            if self._scan_count % 2:                          # ban do: 5 Hz la du
                return
            x, y, yaw = pose
            c, s = math.cos(yaw), math.sin(yaw)
            rot = np.array([[c, s], [-s, c]])
            w = obs @ rot + [x, y]
            free = pl[near & ~is_obs][::4, :2] @ rot + [x, y]  # dat / tran: "trong toi day"
            # robot khac khong phai vat co dinh: khong ve len ban do
            for o in FLEET:
                if o is not self and o.odom is not None:
                    ox, oy, _ = o.map_pose()
                    w = w[np.hypot(w[:, 0] - ox, w[:, 1] - oy) > 0.55]
            w = self.track_and_filter(w, (x, y), time.monotonic())
            sx, sy = x + c * t[0] - s * t[1], y + s * t[0] + c * t[1]
            self.grid.integrate(sx, sy, w, free_pts=free)
            self.grid.decay(period=1.0)          # vet vat dong mo dan (vat tinh duoc thay lai)
            self.depth_grid.decay(period=1.0)
        except Exception as e:                                # noqa: BLE001
            print(f"[{self.label}] loi xu ly LiDAR: {e!r}")
        finally:
            ms = (time.perf_counter() - t_cpu) * 1000
            self.cpu["lidar_ms"] = 0.9 * self.cpu["lidar_ms"] + 0.1 * ms

    def track_and_filter(self, w, xy, now):
        """Cap nhat bo bam; tra ve diem KHONG thuoc vat dong (vat dong khong ve vao ban do tinh)."""
        if "~v1" in self.controller:
            self.tracker.mode = "v1"
            self.tracker.update(w, xy, now)
            return w
        self.tracker.mode = "v2"
        self.tracker.update(w, xy, now, grid=self.grid)
        return self.drop_dynamic(w, now)

    def drop_dynamic(self, w, now):
        if "~v1" in self.controller or not len(w):
            return w
        keep = np.ones(len(w), bool)
        for tr in self.tracker.movers():
            q = tr["p"] + tr["v"] * (now - tr["t"])
            keep &= np.hypot(w[:, 0] - q[0], w[:, 1] - q[1]) > 0.40
        return w[keep]

    def odom_fresh(self, max_age=1.0):
        return self.odom is not None and time.monotonic() - self.odom[3] < max_age

    def wait_ready(self, timeout=5.0):
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end and not self.odom_fresh():
            time.sleep(0.05)
        return self.odom_fresh()

    def wait_sensors(self, timeout=10.0):
        """Cho LiDAR (va depth neu bat) toi lan dau — tim nhau qua DDS mat vai giay."""
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            lidar = time.monotonic() - self.local_t < 1.0
            depth = not self.use_depth or time.monotonic() - self.depth_t < 1.0
            if lidar and depth:
                return True
            time.sleep(0.1)
        return False

    def map_pose(self):
        """Vi tri robot trong frame map (= frame cua Gazebo world)."""
        if self.odom is None:
            return None
        x, y, yaw, _ = self.odom
        ox, oy, oyaw = self.origin
        c, s = math.cos(oyaw), math.sin(oyaw)
        return ox + c * x - s * y, oy + s * x + c * y, _wrap(oyaw + yaw)

    def free_distance(self, ux, uy, margin=0.08):
        """Khoang trong (m) tu mep than robot theo huong (ux, uy) trong frame than.
        Gop 3 nguon: LiDAR (360 do, mu < 0.5 m), D435i (phia truoc, thay sat mat)
        va TRI NHO ban do (vat da thay nhung gio nam trong vung mu cua ca hai)."""
        now = time.monotonic()
        if now - self.local_t > 0.6 and (not self.use_depth or now - self.depth_t > 0.6):
            # MAT CAM BIEN -> coi nhu bi chan (fail-safe). Truoc day tra 0.6 m: robot van
            # di cham va dam vao thung khi LiDAR/D435i chua ket noi (da gap trong test).
            self.notify("Mình mất cảm biến, dừng lại cho an toàn.")
            return 0.0
        half_l = BODY_HALF_L * abs(ux) + BODY_HALF_W * abs(uy)
        half_w = BODY_HALF_W * abs(ux) + BODY_HALF_L * abs(uy) + margin
        best = float("inf")
        srcs = [self.local_obs] if now - self.local_t < 0.6 else []
        if self.use_depth and now - self.depth_t < 0.6:
            srcs.append(self.local_depth)
        for p in srcs:
            if not len(p):
                continue
            along = p @ np.array([ux, uy])
            lat = np.abs(p @ np.array([-uy, ux]))
            m = (along > 0) & (lat < half_w)
            if m.any():
                best = min(best, float(along[m].min() - half_l))
        return min(best, self._memory_distance(ux, uy, half_l, half_w - margin))

    def _memory_distance(self, ux, uy, half_l, half_w, reach=0.45):
        """Vat tren ban do trong 0.45 m truoc mep than (vung LiDAR khong thay)."""
        pose = self.map_pose()
        if pose is None:
            return float("inf")
        x, y, yaw = pose
        a = np.arange(0.0, reach, self.grid.res / 2)
        b = np.linspace(-half_w, half_w, 5)
        A, B = np.meshgrid(a + half_l, b)
        bx, by = A * ux - B * uy, A * uy + B * ux            # frame than
        c, s = math.cos(yaw), math.sin(yaw)
        mx, my = x + c * bx - s * by, y + s * bx + c * by
        r, cc = self.grid.cell(mx, my)
        ok = self.grid.inside(r, cc)
        occ = np.zeros_like(ok)
        occ[ok] = self.grid.occupied()[r[ok], cc[ok]]
        if self.use_depth:
            occ[ok] |= self.depth_grid.occupied()[r[ok], cc[ok]]
        if not occ.any():
            return float("inf")
        return float((A - half_l)[occ].min())

    # ---------------- gui lenh ----------------
    def _twist(self, vx=0.0, vy=0.0, wz=0.0):
        t = self.Twist()
        t.linear.x, t.linear.y, t.angular.z = float(vx), float(vy), float(wz)
        self.cmd_pub.publish(t)

    def _halt(self):
        for _ in range(3):
            self._twist()
            time.sleep(0.02)

    def _body(self, z, roll, pitch, yaw):
        self.body = (z, roll, pitch, yaw)
        p = self.Pose()
        p.position.z = float(z)
        cr, sr = math.cos(roll / 2), math.sin(roll / 2)
        cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
        cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
        p.orientation.w = cr * cp * cy + sr * sp * sy
        p.orientation.x = sr * cp * cy - cr * sp * sy
        p.orientation.y = cr * sp * cy + sr * cp * sy
        p.orientation.z = cr * cp * sy - sr * sp * cy
        self.pose_pub.publish(p)

    # ---------------- API chinh (giong RobotTools) ----------------
    def execute(self, act: dict) -> str:
        tool = (act.get("tool") or "").lower()
        args = act.get("args") or {}
        try:
            if tool == "move":
                return self.move(
                    float(args.get("vx", 0.0)), float(args.get("vy", 0.0)),
                    float(args.get("vyaw", 0.0)), float(args.get("duration", 2.0)))
            if tool == "move_dist":                       # nhieu doan move gop lai (fleet.merge_moves)
                return self.move(
                    float(args.get("vx", 0.0)), float(args.get("vy", 0.0)),
                    float(args.get("vyaw", 0.0)), float(args.get("duration", 2.0)), max_dur=60.0)
            if tool == "action":
                return self.action(str(args.get("name", "")))
            if tool == "stop":
                return self.stop()
            if tool == "go_to":
                return self.go_to(str(args.get("location", "")))
            if tool == "go_to_pose":
                return self.go_to_pose(float(args["x"]), float(args["y"]), args.get("yaw"),
                                       name=args.get("name", "diem do"),
                                       tol=float(args.get("tol", 0.2)))
            if tool == "follow":
                return self.follow(args.get("leader"), float(args.get("gap", 0.9)),
                                   float(args.get("timeout", 90.0)))
            return f"[{self.label}] tool la: {tool} (bo qua)"
        except Exception as e:
            self._halt()
            return f"[{self.label}] LOI khi chay {tool}: {e}"

    def stop(self) -> str:
        self._cancel.set()          # cat ngang move/go_to/dong tac dang chay
        self._halt()
        return f"[{self.label}] Da dung."

    def move(self, vx=0.0, vy=0.0, vyaw=0.0, duration=2.0, max_dur=None) -> str:
        if not all(math.isfinite(v) for v in (vx, vy, vyaw, duration)):
            return f"[{self.label}] tu choi move NaN/inf"      # min(lim, nan) = lim!
        mvx, mvy, mvyaw, mdur = self.limits
        mdur = max_dur or mdur
        vx, vy, vyaw = _clamp(vx, mvx), _clamp(vy, mvy), _clamp(vyaw, mvyaw)
        duration = max(0.1, min(mdur, duration))
        self._cancel.clear()
        lin = math.hypot(vx, vy)
        pure = lin < 1e-3 or abs(vyaw) < 1e-3
        with self._motion:
            if self.closed_loop and pure and self.wait_ready(2.0):
                if lin >= 1e-3:
                    return self._translate(vx, vy, lin * duration)
                return self._rotate(vyaw, vyaw * duration)
            return self._timed(vx, vy, vyaw, duration)

    def _timed(self, vx, vy, vyaw, duration):
        t_end = time.monotonic() + duration
        while time.monotonic() < t_end and not self._cancel.is_set():
            self._twist(vx, vy, vyaw)
            time.sleep(0.05)
        self._halt()
        return f"[{self.label}] Da di theo thoi gian ({duration:.1f}s)"

    def _publish_path(self, pts):
        from geometry_msgs.msg import PoseStamped
        self.last_path = [(float(x), float(y)) for x, y in pts]   # cho GoVoice Studio
        msg = self.Path()
        msg.header.frame_id = "map"
        msg.header.stamp = self.bus.node.get_clock().now().to_msg()
        for x, y in pts:
            ps = PoseStamped()
            ps.header = msg.header
            ps.pose.position.x, ps.pose.position.y = float(x), float(y)
            ps.pose.orientation.w = 1.0
            msg.poses.append(ps)
        self.path_pub.publish(msg)

    def _detour(self, sx, sy, syaw, ux, uy, dist, done):
        """Vat chan duong di thang: SINH QUY DAO vong qua vat, BAM va QUAY VE duong
        thang cu (chi phi lech duong trong nav_local.line_cost), roi di tiep toi DUNG
        diem dich ban dau. Dich nam trong vat/tuong thi tra ve False (phanh nhu cu)."""
        c, s = math.cos(syaw), math.sin(syaw)
        wx, wy = c * ux - s * uy, s * ux + c * uy        # huong di trong map
        gx, gy = sx + wx * dist, sy + wy * dist
        # Dich bi chan co the chi la NGUOI DANG DI QUA (vat dong): cho toi 5 s xem no co
        # di khoi khong, roi moi ket luan "dich trong tuong/vat" (da gap: nguoi di doi dau
        # vua di ngang qua dich -> robot tu choi ngay).
        t_wait = time.monotonic() + 5.0
        while self._goal_blocked(gx, gy):
            if time.monotonic() > t_wait or self._cancel.is_set():
                return False, "dich nam trong vat/tuong", (gx, gy)
            self._halt()
            time.sleep(0.4)
        # Duong vong phai NGAN: dich sau tuong (vung chua thay = coi la trong) khien A*
        # tim duong ra ngoai qua cua chinh — robot "di thang 2 met" thanh di vong ca nha.
        x, y, _ = self.map_pose()
        pts, why = plan(self.grid, (x, y), (gx, gy), discs=self._discs((gx, gy)),
                        layers=[self.depth_grid] if self.use_depth else [],
                        lethal=LETHAL, soft=SOFT, line=(sx, sy, gx, gy))
        straight = math.hypot(gx - x, gy - y)
        # 2x + 2 m: bac thap + hop do choi + ghe banh tao thanh hang rao dai, duong vong
        # that ~5 m cho 2 m thang (1.6x + 1.5 tu choi nham ca 2 lan danh gia)
        if pts is None or path_length(pts) > 2.0 * straight + 2.0:
            return False, ("khong co duong" if pts is None else
                           f"duong vong qua dai ({path_length(pts):.1f} m)"), (gx, gy)
        st = self.last_stats
        st.update(travel_m=done, replans=0, brakes=0, yield_s=0.0, backups=0, detour=True)
        self.notify("Có vật cản, mình đi vòng qua nha.")
        self.goal, self.navigating = (gx, gy), True
        self.state = "đi vòng qua vật"
        try:
            ok, why = self._navigate(gx, gy, tol=0.2, line=(sx, sy, gx, gy))
        finally:
            self.navigating, self.goal = False, None
            self.state = "chờ lệnh"
        if ok:
            self._face(syaw)
            self._settle(gx, gy, syaw)
        return ok, why, (gx, gy)

    def _goal_blocked(self, gx, gy, r=0.35):
        """Dich 'di thang N met' roi vao trong vat / sat tuong -> khong vong, phanh."""
        occ = self.grid.occupied()
        if self.use_depth:
            occ = occ | self.depth_grid.occupied()
        r0, c0 = self.grid.cell(gx, gy)
        n = int(r / self.grid.res)
        win = occ[max(r0 - n, 0):r0 + n + 1, max(c0 - n, 0):c0 + n + 1]
        return bool(win.any())

    def _translate(self, vx, vy, dist):
        x0, y0, yaw0, _ = self.odom
        sx, sy, syaw = self.map_pose()
        speed = math.hypot(vx, vy)
        ux, uy = vx / speed, vy / speed            # huong di trong frame than robot
        t_end = time.monotonic() + dist / 0.06 + 5.0
        done, blocked = 0.0, None
        cw, sw = math.cos(yaw0), math.sin(yaw0)
        wx, wy = cw * ux - sw * uy, sw * ux + cw * uy      # huong di trong frame odom
        while not self._cancel.is_set() and time.monotonic() < t_end:
            x, y, yaw, _ = self.odom
            # chieu len huong di (ne ngang tranh nguoi khong tinh la "da di")
            done = max(0.0, (x - x0) * wx + (y - y0) * wy)
            left = dist - done
            if left <= 0.02:
                break
            if self.avoid:
                free = self.free_distance(ux, uy)
                # vat chan TRUOC dich (khong phai dich nam ngay truoc vat): vong qua.
                # Chi khi di toi (ux > 0.7): lui / di ngang thi phanh nhu cu.
                if (self.detour_enabled and ux > 0.7 and free < 0.55
                        and left > free + 0.25):
                    self._halt()
                    ok, why, (gx, gy) = self._detour(sx, sy, syaw, ux, uy, dist, done)
                    x, y, _ = self.map_pose()
                    err = math.hypot(x - gx, y - gy)
                    self.last_stats.update(done_m=dist if ok else done, target_m=dist,
                                           blocked=not ok, err_m=err)
                    if ok:
                        return (f"[{self.label}] Ne vat can va ve lai duong cu, toi dich "
                                f"(lech {err:.2f} m, di {self.last_stats.get('travel_m', 0):.1f} m)")
                    self.notify("Không có đường vòng, mình dừng lại nha.")
                    return f"[{self.label}] Khong vong qua duoc ({why}), dung lai"
                if free < 0.22:                         # PHANH: vat can tren huong di
                    blocked = free
                    break
            th = self._threat() if self.avoid else None
            if th is not None:                       # nguoi lao toi: ne roi di tiep
                if not (self.evade_enabled and self._evade(th[0])):
                    self._halt()
                time.sleep(0.05)
                t_end += 0.05                        # thoi gian nhuong khong tinh vao han
                continue
            k = max(0.35, min(1.0, left / 0.25))     # cham dan khi gan toi
            if self.avoid and free < 0.7:
                k = min(k, max(0.3, (free - 0.22) / 0.48))
            wz = _clamp(-1.5 * _wrap(yaw - yaw0), 0.4)  # giu huong (CHAMP hay troi)
            self._twist(ux * speed * k, uy * speed * k, wz)
            time.sleep(0.05)
        self._halt()
        self.last_stats = {"done_m": done, "target_m": dist, "blocked": blocked is not None}
        if blocked is not None:
            self.notify("Có vật cản phía trước, mình dừng lại nha.")
            return (f"[{self.label}] PHANH vi vat can cach {max(blocked, 0):.2f} m "
                    f"(da di {done:.2f}/{dist:.2f} m)")
        if self._cancel.is_set():
            return f"[{self.label}] Bi dung giua chung ({done:.2f}/{dist:.2f} m)"
        return f"[{self.label}] Da di {done:.2f} m (muc tieu {dist:.2f} m)"

    def _rotate(self, vyaw, angle):
        last = self.odom[2]
        turned = 0.0
        t_end = time.monotonic() + abs(angle) / 0.15 + 5.0
        while not self._cancel.is_set() and time.monotonic() < t_end:
            yaw = self.odom[2]
            turned += _wrap(yaw - last)
            last = yaw
            left = abs(angle) - abs(turned)
            if left <= 0.03:
                break
            k = max(0.35, min(1.0, left / 0.35))
            self._twist(0.0, 0.0, vyaw * k)
            time.sleep(0.05)
        self._halt()
        self.last_stats = {"turned_rad": turned, "target_rad": angle}
        if self._cancel.is_set():
            return f"[{self.label}] Bi dung giua chung ({math.degrees(turned):.0f} do)"
        return (f"[{self.label}] Da xoay {math.degrees(turned):.0f} do "
                f"(muc tieu {math.degrees(angle):.0f})")

    def action(self, name: str) -> str:
        key = name.lower().strip()
        frames = _CHOREO.get(key)
        if frames is None:
            return f"[{self.label}] khong biet dong tac '{name}'"
        self._cancel.clear()
        frames = [(t, p if p is not None else self.body) for t, p in frames]
        t0 = time.monotonic()
        with self._motion:
            self._halt()
            while not self._cancel.is_set():
                t = time.monotonic() - t0
                if t >= frames[-1][0]:
                    self._body(*frames[-1][1])
                    break
                for (ta, pa), (tb, pb) in zip(frames, frames[1:]):
                    if ta <= t < tb:
                        a = (t - ta) / (tb - ta)
                        self._body(*[u + a * (v - u) for u, v in zip(pa, pb)])
                        break
                time.sleep(1 / 30)
        return f"[{self.label}] Da lam: {key}"

    # ---------------- go_to ----------------
    def nearest_place(self):
        """(ten diem gan nhat, khoang cach m) — cho cau hoi 'dang o dau'."""
        here = self.map_pose()
        best = (None, float("inf"))
        for name, wp in self.waypoints.items():
            p = wp.get("pose") if isinstance(wp, dict) else wp
            d = math.hypot(here[0] - float(p[0]), here[1] - float(p[1]))
            if d < best[1]:
                best = (name, d)
        return best

    def go_to(self, location: str) -> str:
        key = norm(location)
        if key == "cho cu":
            if not self.last_place:
                return f"[{self.label}] chua co 'cho cu' de quay ve"
            pts, goal = [], self.last_place
        else:
            wp = self.waypoints.get(key)
            if wp is None and self.resolver is not None:
                # khong phai diem dat ten -> thu do vat theo ten + mau ("bàn màu đen")
                got = self.resolver(location, self.map_pose())
                if got is not None:
                    gx, gy, gyaw, label = got
                    return self.go_to_pose(gx, gy, gyaw, name=label)
            if wp is None:
                known = ", ".join(self.waypoints) or "(chua co waypoint nao)"
                return f"[{self.label}] khong tim thay diem '{location}'. Cac diem: {known}"
            if isinstance(wp, dict):
                goal, pts = wp.get("pose"), [tuple(v) for v in wp.get("via") or []]
            else:
                goal, pts = wp, []
        return self.go_to_pose(float(goal[0]), float(goal[1]),
                               float(goal[2]) if len(goal) > 2 else None,
                               name=location, via=pts)

    def go_to_pose(self, gx, gy, gyaw=None, name="diem do", via=(), tol=0.2):
        if not self.wait_ready(2.0):
            return f"[{self.label}] chua nhan odom tu {self.odom_topic}"
        here = self.map_pose()
        self.last_place = here
        self._cancel.clear()
        t0 = time.monotonic()
        self.last_stats = {"travel_m": 0.0, "replans": 0, "brakes": 0, "yield_s": 0.0,
                           "backups": 0}
        with self._motion:
            self.goal = (gx, gy)
            self.navigating = True
            self.state = f"đi tới {name}"
            try:
                for p in list(via) + [(gx, gy)]:
                    last = p == (gx, gy)
                    ok, why = (self._navigate(*p, tol=tol if last else 0.35) if self.avoid
                               else self._drive_to(*p, tol=tol if last else 0.35))
                    if not ok:
                        self.last_stats.update(ok=False, why=why, time_s=time.monotonic() - t0)
                        if getattr(self, "preempted", False):   # Studio cham dich moi: khong phai loi
                            self.preempted = False
                            return f"[{self.label}] bo '{name}', doi sang dich moi"
                        self._halt()
                        self.notify(f"Mình không tới được {name} được rồi.")
                        return f"[{self.label}] go_to '{name}' THAT BAI: {why}"
                if gyaw is not None:
                    self._face(float(gyaw))
                self._settle(gx, gy, gyaw)
            finally:
                self.navigating = False
                self.goal = None
                self.state = "chờ lệnh"
        self._halt()
        x, y, _ = self.map_pose()
        err = math.hypot(x - gx, y - gy)
        self.last_stats.update(ok=True, err_m=err, time_s=time.monotonic() - t0)
        s = self.last_stats
        return (f"[{self.label}] Da toi '{name}' (lech {err:.2f} m, {s['time_s']:.0f} s, "
                f"di {s['travel_m']:.1f} m, lap lai {s['replans']} lan)")

    # --- dieu khien co ne vat can ---
    def _others(self):
        return [o for o in FLEET if o is not self and o.odom is not None]

    def _discs(self, goal=None):
        """Robot khac thanh vat can tron. Bo qua con dang dung o DICH cua minh
        (doi cho / toi chỗ con kia): no se di khoi, va phanh phan xa van con do."""
        out = []
        for o in self._others():
            ox, oy, _ = o.map_pose()
            if goal is not None and math.hypot(ox - goal[0], oy - goal[1]) < 0.9:
                continue
            r, c = self.grid.cell(ox, oy)
            out.append((int(r), int(c), 0.45))
        # nguoi dang di: chan ca cho ho SAP toi (1 s nua) — duong di tranh truoc
        for tr in (self.tracker.movers() if self.people_aware else []):
            for k in (0.0, 0.5, 1.0):
                px, py = tr["p"] + tr["v"] * k
                r, c = self.grid.cell(px, py)
                out.append((int(r), int(c), 0.40))
        return out

    def _threat(self, robot_v=(0.0, 0.0)):
        """Vat dong sap toi gan robot (CPA < 0.75 m trong 2 s)? -> (track, t*, d*) | None."""
        pose = self.map_pose()
        if pose is None or not self.people_aware:
            return None
        here = np.array(pose[:2])
        worst = None
        for tr in self.tracker.movers():
            t_star, d_star = cpa(tr["p"] - here, tr["v"] - np.asarray(robot_v), 2.0)
            if d_star < 0.75 and (worst is None or d_star < worst[2]):
                worst = (tr, t_star, d_star)
        return worst

    def _evade(self, tr, st=None):
        """Nguoi dang lao toi: NE NGANG (Go2 di ngang duoc) hoac LUI, phia con trong.
        Neu khong con cho trong thi dung yen (nguoi that se tu ne robot dung yen)."""
        x, y, yaw = self.map_pose()
        rel = tr["p"] - np.array([x, y])
        v = tr["v"] / (np.linalg.norm(tr["v"]) + 1e-9)
        side = np.array([-v[1], v[0]])                       # vuong goc huong nguoi di
        if np.dot(side, -rel) < 0:
            side = -side                                     # chon phia xa nguoi
        best = None
        for e in (side, -rel / (np.linalg.norm(rel) + 1e-9), -side):
            c, s_ = math.cos(-yaw), math.sin(-yaw)
            bx, by = c * e[0] - s_ * e[1], s_ * e[0] + c * e[1]   # huong ne trong frame than
            n = math.hypot(bx, by) or 1.0
            bx, by = bx / n, by / n
            if self.free_distance(bx, by) > 0.35:
                best = (bx, by)
                break
        if best is None:
            self._halt()
            return False
        self._twist(0.25 * best[0], 0.25 * best[1], 0.0)
        if st is not None:
            st["evade_s"] = st.get("evade_s", 0.0) + 0.05
        return True

    def _robot_near(self, p, r=0.9):
        return any(math.hypot(o.map_pose()[0] - p[0], o.map_pose()[1] - p[1]) < r
                   for o in self._others())

    def _rank(self):
        """Nho hon = uu tien hon: con nao GAN DICH hon duoc di truoc."""
        if not self.navigating or self.goal is None:
            return (float("inf"), self.priority)
        x, y, _ = self.map_pose()
        return (round(math.hypot(self.goal[0] - x, self.goal[1] - y), 1), self.priority)

    def _must_yield(self):
        if not self.coordinate:
            return None
        x, y, yaw = self.map_pose()
        for o in self._others():
            if not o.navigating:
                continue                                 # dung yen -> lap ke hoach vong qua
            ox, oy, _ = o.map_pose()
            d = math.hypot(ox - x, oy - y)
            if d > 1.4:
                continue
            bearing = abs(_wrap(math.atan2(oy - y, ox - x) - yaw))
            if bearing < 1.3 and o._rank() < self._rank():
                return o
        return None

    RL_POLICY = os.environ.get("GOVOICE_RL_POLICY",
                               os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "rl_nav", "policy_nav.npz"))

    def _make_ctrl(self):
        """Bo dieu khien theo ten; hau to ~v1 = hinh hoc/cam bien cu (luot 960, 22/11)."""
        full = self.controller
        try:
            self.controller = full.split(":")[0].replace("~v1", "")      # "ten:k=v;k=v" -> dat tham so
            c = self._make_ctrl_base()
        finally:
            self.controller = full
        for m in (c, getattr(c, "shield", None)):
            if isinstance(m, MPPI):
                m.people_cap = "~v1" not in full
                for kv in (full.split(":", 1)[1].split(";") if ":" in full else []):
                    k, v = kv.split("=")
                    if k in m.w:
                        m.w[k] = float(v)
                    else:
                        setattr(m, k, type(getattr(m, k))(float(v)))
        return c

    def _make_ctrl_base(self):
        lim = dict(vmax=(self.goto_speed * 1.7, 0.3, self.goto_turn * 1.25),
                   vmin=(-0.2, -0.3, -self.goto_turn * 1.25))
        if self.controller.startswith("p2"):
            # p2[-cap-evade-prior-value-rate-adapt][+value][@ppo+sac]: PRISM-E va ablation
            import re as _re
            name, _, sel = self.controller.partition("@")
            d = os.path.dirname(self.RL_POLICY)
            files = {"ppo": self.RL_POLICY, "td3": os.path.join(d, "policy_nav_td3.npz"),
                     "sac": os.path.join(d, "policy_nav_sac.npz")}
            pri = [RLPolicy(files[k]) for k in sel.split("+")] if sel else []
            vp = os.path.join(d, "value_nav.npz")
            if pri and os.path.exists(vp) and sel.startswith("ppo"):
                pri[0].load_value(vp)
            fl = {m.group(2): m.group(1) == "+" for m in _re.finditer(r"([-+])([a-z]+)", name[2:])}
            return PRISM2(priors=pri, flags=fl, **lim)
        if self.controller == "dwa":
            return DWA(**lim)
        if self.controller == "log_mppi":
            return MPPI(log_noise=True, **lim)
        td3 = os.path.join(os.path.dirname(self.RL_POLICY), "policy_nav_td3.npz")
        if self.controller.startswith("rl@"):                         # RL thuan, chon thuat toan
            algo = self.controller.split("@")[1]
            d = os.path.dirname(self.RL_POLICY)
            return RLPolicy({"ppo": self.RL_POLICY, "td3": td3,
                             "sac": os.path.join(d, "policy_nav_sac.npz")}[algo])
        if self.controller == "rl_ens":
            return EnsemblePolicy([RLPolicy(self.RL_POLICY), RLPolicy(td3)])
        if self.controller == "bmppi":                              # kieu Biased-MPPI: nhieu goi y, TY LE CO DINH
            return PolicyMPPI(RLPolicy(self.RL_POLICY), mode="pg", ratio=0.3,
                              extra_policies=[RLPolicy(td3)], **lim)
        if self.controller == "apmppi_multi":                       # PPO + TD3 cung goi y
            pol = RLPolicy(self.RL_POLICY)
            vpath = os.path.join(os.path.dirname(self.RL_POLICY), "value_nav.npz")
            if os.path.exists(vpath):
                pol.load_value(vpath)
            return PolicyMPPI(pol, mode="ap", ratio=0.3, extra_policies=[RLPolicy(td3)], **lim)
        if self.controller in ("pgmppi", "apmppi"):
            pol = RLPolicy(self.RL_POLICY)
            vpath = os.path.join(os.path.dirname(self.RL_POLICY), "value_nav.npz")
            if self.controller == "apmppi" and os.path.exists(vpath):
                pol.load_value(vpath)
            return PolicyMPPI(pol, mode="ap" if self.controller == "apmppi" else "pg",
                              ratio=0.3 if self.controller == "pgmppi" else 0.2, **lim)
        if self.controller.startswith("prism"):
            # prism | prism_noprior | prism_noadapt | prism_novis | prism_nounc | prism_nolang
            # prism | prism_no{prior,adapt,vis,unc,adaptratio,value} | prism@ppo+td3+sac (chon bo goi y)
            name, _, sel = self.controller.partition("@")
            off = name.split("_no")[1] if "_no" in name else None
            flags = {off: False} if off else {}
            d = os.path.dirname(self.RL_POLICY)
            files = {"ppo": self.RL_POLICY, "td3": td3, "sac": os.path.join(d, "policy_nav_sac.npz")}
            want = sel.split("+") if sel else ["ppo", "td3"]
            priors = []
            if off != "prior":
                priors = [RLPolicy(files[k]) for k in want if k in files and os.path.exists(files[k])]
                vpath = os.path.join(d, "value_nav.npz")
                if priors and os.path.exists(vpath):
                    priors[0].load_value(vpath)              # critic PPO lam chi phi cuoi (doc lap bo goi y)
            return PRISM(priors=priors, prior_frac=0.3, flags=flags, **lim)
        if self.controller in ("rl", "rl_safe"):
            return RLPolicy(self.RL_POLICY, shield=MPPI(**lim) if self.controller == "rl_safe" else None)
        return MPPI(**lim)

    def _navigate(self, gx, gy, tol=0.2, timeout=None, line=None):
        if self.controller.split(":")[0].replace("~v1", "") in ("mppi", "log_mppi", "dwa", "rl", "rl_safe", "pgmppi", "apmppi",
                               "rl_ens", "apmppi_multi", "bmppi") or \
                self.controller.startswith(("prism", "rl@", "p2")):
            return self._navigate_mpc(gx, gy, tol=tol, timeout=timeout, line=line)
        return self._navigate_pp(gx, gy, tol=tol, timeout=timeout, line=line)

    def _navigate_mpc(self, gx, gy, tol=0.2, timeout=None, line=None):
        """Di toi (gx, gy) MUOT: A* toan cuc (luong rieng, giu duong cu neu con tot) +
        MPPI cuc bo 10 Hz (hoac DWA). Khong dung de quay mat, khong phanh tung nhip:
        ne vat/nguoi nam san trong ham cost. Phanh cung chi con la lop an toan cuoi."""
        x, y, yaw = self.map_pose()
        dist0 = math.hypot(gx - x, gy - y)
        deadline = time.monotonic() + (timeout or 40.0 + 4.0 * dist0 / 0.1)
        st = self.last_stats
        if self._ctrl is None or getattr(self, "_ctrl_kind", None) != self.controller:
            self._ctrl = self._make_ctrl()
            self._ctrl_kind = self.controller
        ctrl = self._ctrl
        if self._ctrl_goal is None or math.hypot(gx - self._ctrl_goal[0], gy - self._ctrl_goal[1]) > 1.0:
            ctrl.reset()
        self._ctrl_goal = (gx, gy)
        ps = {"busy": False, "t": 0.0, "new": None, "why": None, "fails": 0}

        def replan(sx, sy):
            def job():
                try:
                    p, why = plan(self.grid, (sx, sy), (gx, gy),
                                  discs=self._discs((gx, gy)) if self.coordinate else (),
                                  layers=[self.depth_grid] if self.use_depth else [],
                                  lethal=0.32, soft=SOFT, line=line)
                except Exception as e:                          # noqa: BLE001
                    p, why = None, repr(e)
                ps.update(new=p, why=why, busy=False, t=time.monotonic())
            ps["busy"] = True
            st["replans"] = st.get("replans", 0) + 1
            threading.Thread(target=job, daemon=True).start()

        path = P = S = None
        field, t_field = None, 0.0
        meta = (self.grid.res, self.grid.x0, self.grid.y0)
        u = np.zeros(3)
        v_meas = np.zeros(3)
        lp = (x, y, yaw, time.monotonic())
        prog = (x, y, time.monotonic())
        stuck, blocked_since = 0, None
        wait_since, no_yield_until = None, 0.0
        last_xy = (x, y)
        replan(x, y)
        while not self._cancel.is_set():
            now = time.monotonic()
            if now > deadline:
                self._halt()
                return False, "het gio"
            x, y, yaw = self.map_pose()
            # van toc do duoc (than) + he so van toc thuc/lenh
            dtp = now - lp[3]
            if dtp > 0.04:
                wx, wy = (x - lp[0]) / dtp, (y - lp[1]) / dtp
                wz = _wrap(yaw - lp[2]) / dtp
                c, s_ = math.cos(yaw), math.sin(yaw)
                v_meas = 0.5 * v_meas + 0.5 * np.array([c * wx + s_ * wy, -s_ * wx + c * wy, wz])
                self.v_world = (0.5 * self.v_world[0] + 0.5 * wx, 0.5 * self.v_world[1] + 0.5 * wy)
                lp = (x, y, yaw, now)
                cmd = math.hypot(u[0], u[1])
                if cmd > 0.15:
                    g_obs = math.hypot(v_meas[0], v_meas[1]) / cmd
                    self.vel_gain = float(np.clip(0.97 * self.vel_gain + 0.03 * g_obs, 0.25, 1.2))
                for ax, lo in ((0, 0.12), (1, 0.08), (2, 0.25)):         # tung truc (PRISM adapt)
                    if abs(u[ax]) > lo and np.sign(v_meas[ax]) == np.sign(u[ax]):
                        g_ax = float(np.clip(v_meas[ax] / u[ax], 0.15, 1.3))
                        self.vel_gains[ax] = 0.96 * self.vel_gains[ax] + 0.04 * g_ax
            if not st.setdefault("traj", []) or now - st["traj"][-1][0] > 0.25:
                st["traj"].append((now, x, y, yaw))
            st["travel_m"] = st.get("travel_m", 0.0) + math.hypot(x - last_xy[0], y - last_xy[1])
            last_xy = (x, y)
            d_goal = math.hypot(gx - x, gy - y)
            if d_goal < tol:
                self._halt()
                self.local_traj = []
                return True, "ok"
            # ---- duong toan cuc (A* chay o luong rieng: vong dieu khien khong bao gio cho)
            if ps["why"] is not None:
                newp, why = ps["new"], ps["why"]
                ps["why"] = ps["new"] = None
                if newp is None:
                    if why == "dich nam trong vat can" and self._robot_near((gx, gy)):
                        pass                                    # robot khac dang o dich: doi
                    else:
                        ps["fails"] += 1
                        if ps["fails"] == 3:                    # kieu Nav2 "clear costmap"
                            self.grid.forget(x, y, radius=2.5)
                            self.depth_grid.forget(x, y, radius=2.5)
                            st["clears"] = st.get("clears", 0) + 1
                        if ps["fails"] >= 6:
                            self._halt()
                            self._dump_debug(gx, gy, why)
                            return False, why
                else:
                    ps["fails"] = 0
                    NP, NS = _resample(newp)
                    keep = (P is not None and not self._path_blocked(P, ctrl, field)
                            and (S[-1] - S[ctrl.last.get("i0", 0)] if len(S) else 0) < 1.18 * NS[-1] + 0.3)
                    if not keep:                                # tre: giu duong cu neu con tot
                        path, P, S = newp, NP, NS
                        self._publish_path(newp)
                        st.setdefault("paths", []).append([(round(a, 2), round(b, 2)) for a, b in newp])
            if not ps["busy"] and (now - ps["t"] > 1.5 or P is None):
                replan(x, y)
            if P is None:
                self._halt()
                time.sleep(0.05)
                continue
            # ---- luat nhuong duong giua cac robot (giu nguyen: chong ket doi dau)
            other = self._must_yield() if now > no_yield_until else None
            if other is not None:
                wait_since = wait_since or now
                if now - wait_since > 6.0:
                    no_yield_until, wait_since = now + 6.0, None
                else:
                    self._halt()
                    u[:] = 0.0
                    st["yield_s"] = st.get("yield_s", 0.0) + 0.1
                    time.sleep(0.1)
                    continue
            else:
                wait_since = None
            # ---- MPPI / DWA
            if field is None or now - t_field > 0.2:
                field = obstacle_field(self.grid, [self.depth_grid] if self.use_depth else [])
                t_field = now
            people = []
            if self.people_aware and self.avoid:
                v1 = "~v1" in self.controller                  # v2: bu tuoi track + tre chap hanh
                people = [(float(tr["p"][0] + (0 if v1 else tr["v"][0] * min(0.4, now - tr["t"] + 0.05))),
                           float(tr["p"][1] + (0 if v1 else tr["v"][1] * min(0.4, now - tr["t"] + 0.05))),
                           float(tr["v"][0]), float(tr["v"][1]), 0.25)
                          for tr in self.tracker.movers()]
            if self.coordinate:
                for o in self._others():
                    ox, oy, _ = o.map_pose()
                    if math.hypot(ox - gx, oy - gy) < 0.9:
                        continue
                    ov = getattr(o, "v_world", (0.0, 0.0))
                    people.append((ox, oy, ov[0], ov[1], 0.35))
            extra = {}
            if isinstance(ctrl, PRISM2):
                ctrl.prefs = self.nav_prefs
                extra = dict(gains=self.vel_gains.copy())
            if isinstance(ctrl, PRISM):
                ctrl.prefs = self.nav_prefs
                tent = []
                if self.people_aware and self.avoid and "~v1" in self.controller:
                    known = {id(tr) for tr in self.tracker.movers()}
                    # G3b: ca vat CO NGUOI di CHAM (0.08-0.3 m/s) - khong du dung yen de vao ban do,
                    # khong du nhanh de la 'nguoi dang di' -> truoc day lot khe ca hai co che
                    # min_travel 0.3 (22/11): tam cum cua vat DUNG YEN nhay 0.2-0.4 m theo goc nhin -> voi 0
                    # thi coc/thung thanh 'nguoi nghi' (bai slalom KHONG co nguoi ma co 9) -> PRISM ket.
                    # 0.3 m van som hon nguoi xac nhan (0.5 m) ~0.7 s voi nguoi di 0.3 m/s.
                    tent = [(float(tr["p"][0]), float(tr["p"][1]), float(tr["v"][0]),
                             float(tr["v"][1]), 0.2)
                            for tr in self.tracker.movers(min_speed=0.08, min_hits=3,
                                                          min_travel=0.0 if "~t0" in self.controller else 0.3)
                            if id(tr) not in known and math.hypot(tr["p"][0] - x, tr["p"][1] - y) < 3.5]
                extra = dict(seen=(np.maximum(self.grid.seen_t, self.depth_grid.seen_t)
                                   if self.use_depth else self.grid.seen_t, time.monotonic(), x, y),
                             tentative=tent, gains=self.vel_gains.copy())
            u, info = ctrl.step(np.array([x, y, yaw]), v_meas, field, meta, P, S, (gx, gy),
                                people=people, gain=self.vel_gain, u_prev=u, **extra)
            self.local_traj = [(float(a), float(b)) for a, b in info["traj"][::2]]
            if info["blocked"]:
                self.state = "kẹt: tìm đường khác"
                blocked_since = blocked_since or now
                st["brakes"] = st.get("brakes", 0) + 1
                if now - blocked_since > 2.5:
                    self._backup(0.3)
                    st["backups"] = st.get("backups", 0) + 1
                    self.grid.forget(x, y, radius=1.2)
                    self.depth_grid.forget(x, y, radius=1.2)
                    P = None
                    blocked_since = None
                    ctrl.reset()
            else:
                blocked_since = None
                if self.state.startswith(("kẹt", "phanh", "nhường")):
                    self.state = "đi tiếp"
            # ---- lop an toan cuoi: vat SAT theo dung huong lenh
            sp = math.hypot(u[0], u[1])
            if sp > 0.03 and self.avoid:
                free = self.free_distance(u[0] / sp, u[1] / sp)
                if free < 0.09:
                    u[0] = u[1] = 0.0
                    st["brakes"] = st.get("brakes", 0) + 1
                    self.state = "phanh: có vật sát"
            self._twist(float(u[0]), float(u[1]), float(u[2]))
            # ---- ket: 4 s khong tien duoc 0.15 m
            if now - prog[2] > 4.0:
                if math.hypot(x - prog[0], y - prog[1]) < 0.15 and d_goal > tol:
                    stuck += 1
                    st["stuck"] = stuck
                    if os.environ.get("GOVOICE_DEBUG_DIR"):            # chan doan: luu du de phat lai ctrl.step
                        try:
                            import pickle
                            dd = os.environ["GOVOICE_DEBUG_DIR"]
                            os.makedirs(dd, exist_ok=True)
                            with open(os.path.join(dd, f"stuck_{self.controller}_{int(time.time())}.pkl"), "wb") as fo:
                                pickle.dump(dict(x0=np.array([x, y, yaw]), v0=v_meas.copy(), field=field, meta=meta,
                                                 P=P, S=S, goal=(gx, gy), people=people, gain=self.vel_gain,
                                                 u_prev=u.copy(), extra=extra, ctrl=ctrl), fo)
                        except Exception as e:                       # noqa: BLE001
                            print("dump loi", e)
                    self.grid.forget(x, y, radius=1.5)
                    self.depth_grid.forget(x, y, radius=1.5)
                    P = None
                    ctrl.reset()
                    if stuck >= 4:
                        self._halt()
                        return False, "ket"
                prog = (x, y, now)
            time.sleep(max(0.0, 0.1 - (time.monotonic() - now)))
        self._halt()
        self.local_traj = []
        return False, "bi dung"

    def _path_blocked(self, P, ctrl, field):
        """Doan duong 3 m phia truoc con trong (ho >= than robot)?"""
        if field is None or P is None or not len(P):
            return False
        i0 = ctrl.last.get("i0", 0)
        seg = P[i0:i0 + 30]
        r, c = self.grid.cell(seg[:, 0], seg[:, 1])
        ok = self.grid.inside(r, c)
        return bool((field[r[ok], c[ok]] < 0.22).any())

    def _navigate_pp(self, gx, gy, tol=0.2, timeout=None, line=None):
        x, y, _ = self.map_pose()
        deadline = time.monotonic() + (timeout or 40.0 + 4.0 * math.hypot(gx - x, gy - y) / 0.1)
        path, t_plan, fails = None, 0.0, 0
        blocked_since, wait_since, no_yield_until = None, None, 0.0
        last_xy = (x, y)
        st = self.last_stats
        while not self._cancel.is_set():
            now = time.monotonic()
            if now > deadline:
                return False, "het gio"
            x, y, yaw = self.map_pose()
            if not st.setdefault("traj", []) or now - st["traj"][-1][0] > 0.25:
                st["traj"].append((now, x, y, yaw))
            st["travel_m"] = st.get("travel_m", 0.0) + math.hypot(x - last_xy[0], y - last_xy[1])
            last_xy = (x, y)
            d_goal = math.hypot(gx - x, gy - y)
            if d_goal < tol:
                return True, "ok"
            if path is None or now - t_plan > 1.0:
                # lethal 0.40: ban kinh quet khi quay tai cho cua Go2 that
                # (hypot(0.35, 0.155) = 0.38). Voi 0.30, goc truoc quet vao vat khi xoay.
                path, why = plan(self.grid, (x, y), (gx, gy),
                                 discs=self._discs((gx, gy)) if self.coordinate else (),
                                 layers=[self.depth_grid] if self.use_depth else [],
                                 lethal=LETHAL, soft=SOFT, line=line)
                t_plan = now
                st["replans"] = st.get("replans", 0) + 1
                if path is None:
                    if why == "dich nam trong vat can" and self._robot_near((gx, gy)):
                        self._halt()                       # robot khac dang dung o dich: doi
                        time.sleep(0.5)
                        continue
                    fails += 1
                    self._halt()
                    if fails == 3:                         # kieu Nav2 "clear costmap"
                        self.grid.forget(x, y, radius=2.5)
                        self.depth_grid.forget(x, y, radius=2.5)
                        st["clears"] = st.get("clears", 0) + 1
                    if fails >= 6:
                        self._dump_debug(gx, gy, why)
                        return False, why
                    time.sleep(0.5)
                    continue
                fails = 0
                self._publish_path(path)
                st.setdefault("paths", []).append([(round(a, 2), round(b, 2)) for a, b in path])
            # luat nhuong duong giua cac robot
            other = self._must_yield() if now > no_yield_until else None
            if other is not None:
                wait_since = wait_since or now
                if now - wait_since > 6.0:                  # doi lau qua: tu nang uu tien
                    no_yield_until, wait_since = now + 6.0, None
                else:
                    self._halt()
                    st["yield_s"] = st.get("yield_s", 0.0) + 0.1
                    time.sleep(0.1)
                    continue
            else:
                wait_since = None
            th = self._threat() if self.avoid else None
            if th is not None:                               # NGUOI LAO TOI: nhuong
                self.state = "nhường người"
                if not (self.evade_enabled and self._evade(th[0], st)):
                    self._halt()
                st["people_s"] = st.get("people_s", 0.0) + 0.05
                path = None                                  # qua roi thi lap duong moi
                time.sleep(0.05)
                continue
            if self.state == "nhường người" or self.state.startswith("phanh"):
                self.state = "đi tiếp"
            (lx, ly), _ = lookahead(path, x, y, 0.5)
            err = _wrap(math.atan2(ly - y, lx - x) - yaw)
            wz = _clamp(2.0 * err, self.goto_turn)
            if abs(err) > 0.6:
                vx = 0.0                                     # quay mat truoc
            else:
                vx = min(self.goto_speed, 0.8 * d_goal + 0.08) * math.cos(err)
            free = self.free_distance(1.0, 0.0)
            if vx > 0 and free < 0.22:                       # phanh phan xa
                self.state = "phanh: có vật sát trước"
                self._halt()
                st["brakes"] = st.get("brakes", 0) + 1
                blocked_since = blocked_since or now
                path = None                                  # lap ke hoach ngay (ban do da co vat)
                if now - blocked_since > 3.0:                # ket: lui lai 0.3 m roi thu lai
                    self._backup(0.3)
                    st["backups"] = st.get("backups", 0) + 1
                    blocked_since = None
                time.sleep(0.1)
                continue
            blocked_since = None
            if vx > 0 and free < 0.7:
                vx *= max(0.3, (free - 0.22) / 0.48)
            self._twist(vx, 0.0, wz)
            time.sleep(0.05)
        return False, "bi dung"

    def _dump_debug(self, gx, gy, why):
        d = os.environ.get("GOVOICE_DEBUG_DIR")
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"fail_{self.label.replace(' ', '')}_{int(time.time())}.npz")
        np.savez_compressed(f, ev=self.grid.ev, ev_depth=self.depth_grid.ev,
                            pose=np.array(self.map_pose()),
                            goal=np.array([gx, gy]), why=why,
                            others=np.array([o.map_pose() for o in self._others()]))
        print(f"[{self.label}] luu ban do loi -> {f}")

    def _settle(self, gx, gy, gyaw=None, tol=0.2):
        """Xoay tai cho lam CHAMP troi 10-20 cm: lech > tol thi tien lai dung cho (ngan,
        tranh vat nhu thuong) roi xoay lai 1 lan."""
        x, y, _ = self.map_pose()
        if math.hypot(x - gx, y - gy) <= tol or self._cancel.is_set():
            return
        ok, _ = self._navigate(gx, gy, tol=0.12, timeout=12.0) if self.avoid else \
            self._drive_to(gx, gy, tol=0.12)
        if ok and gyaw is not None:
            self._face(float(gyaw), tol=0.1)

    def _backup(self, dist):
        if self.free_distance(-1.0, 0.0) < dist + 0.1:
            return
        x0, y0, _, _ = self.odom
        t_end = time.monotonic() + 4.0
        while time.monotonic() < t_end and not self._cancel.is_set():
            x, y, _, _ = self.odom
            if math.hypot(x - x0, y - y0) >= dist:
                break
            self._twist(-0.2, 0.0, 0.0)
            time.sleep(0.05)
        self._halt()

    def _drive_to(self, mx, my, tol=0.15):
        """Ban cu (khong ne vat can): quay mat -> di thang. Giu lai de so sanh (ablation)."""
        x, y, _ = self.map_pose()
        t_end = time.monotonic() + 2.5 * math.hypot(mx - x, my - y) / 0.1 + 15.0
        last = (x, y)
        while not self._cancel.is_set() and time.monotonic() < t_end:
            x, y, yaw = self.map_pose()
            self.last_stats["travel_m"] += math.hypot(x - last[0], y - last[1])
            last = (x, y)
            d = math.hypot(mx - x, my - y)
            if d < tol:
                return True, "ok"
            err = _wrap(math.atan2(my - y, mx - x) - yaw)
            wz = _clamp(1.8 * err, self.goto_turn)
            vx = 0.0 if abs(err) > 0.5 else min(self.goto_speed, 0.8 * d) * math.cos(err)
            self._twist(vx, 0.0, wz)
            time.sleep(0.05)
        return False, "het gio" if not self._cancel.is_set() else "bi dung"

    def _face(self, myaw, tol=0.06):
        t_end = time.monotonic() + 15.0
        while not self._cancel.is_set() and time.monotonic() < t_end:
            err = _wrap(myaw - self.map_pose()[2])
            if abs(err) < tol:
                break
            self._twist(0.0, 0.0, _clamp(1.8 * err, self.goto_turn))
            time.sleep(0.05)

    # ---------------- di theo robot khac ----------------
    def follow(self, leader_ns, gap=0.9, timeout=90.0):
        leader = next((o for o in FLEET if o.ns == leader_ns), None)
        if leader is None or leader is self:
            return f"[{self.label}] khong co robot '{leader_ns}' de di theo"
        self._cancel.clear()
        t_end = time.monotonic() + timeout
        self.notify(f"Mình đi theo {leader.label} nè.")
        with self._motion:
            while not self._cancel.is_set() and time.monotonic() < t_end:
                lx, ly, _ = leader.map_pose()
                x, y, _ = self.map_pose()
                d = math.hypot(lx - x, ly - y)
                if d <= gap + 0.35:
                    self._halt()
                    time.sleep(0.2)
                    continue
                k = (d - gap) / d
                self.goal, self.navigating = (x + k * (lx - x), y + k * (ly - y)), True
                self._navigate(*self.goal, tol=0.3, timeout=1.5)
            self.navigating, self.goal = False, None
        self._halt()
        return f"[{self.label}] Thoi di theo {leader.label}"


if __name__ == "__main__":
    # Thu nhanh khi sim dang chay:  python3 robot_ros.py [ns]
    import sys
    ns = sys.argv[1] if len(sys.argv) > 1 else ""
    r = RosRobotTools(ns=ns)
    print("odom:", "OK" if r.wait_ready(5) else "KHONG CO", r.map_pose())
    time.sleep(2.0)
    print("vat can quanh robot:", len(r.local_obs), "diem; truoc mat trong",
          f"{r.free_distance(1, 0):.2f} m")
    print(r.execute({"tool": "move", "args": {"vx": 0.35, "duration": 2.86}}))
