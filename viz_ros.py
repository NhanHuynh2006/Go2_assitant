#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
viz_ros.py — XEM TRUC TIEP robot "nghi" gi, trong RViz (frame "map"):

  /govoice/map       nav_msgs/OccupancyGrid   ban do robot TU VE tu LiDAR + D435i
                                              (100 = vat, 0 = da thay trong, -1 = chua biet)
  /govoice/markers   visualization_msgs/MarkerArray
        - than tung robot (hop 0.70 x 0.31 m) + ten "con 1"/"con 2" + dang lam gi
        - dich dang toi (co xanh) + duong da lap (cung co tren <ns>/govoice/path)
        - NGUOI dang theo doi (tru cam) + mui ten van toc, do khi robot dang nhuong
        - do vat trong danh muc (hop mau dung mau that + ten "bàn trà màu đen")
  <ns>/govoice/path  nav_msgs/Path            quy dao dang bam

Mo RViz da cau hinh san:  ros2 launch go2_voice voice_sim.launch.py rviz:=true
(hoac: rviz2 -d ~/ros2_ws/src/unitree_go2_ros2/go2_voice/rviz/voice_sim.rviz)
"""

import math
import threading
import time

import numpy as np

COLORS = {"đen": (0.1, 0.1, 0.1), "trắng": (0.95, 0.95, 0.95), "xám": (0.6, 0.6, 0.6),
          "đỏ": (0.9, 0.2, 0.2), "nâu": (0.55, 0.33, 0.18), "cam": (1.0, 0.55, 0.1),
          "vàng": (0.95, 0.8, 0.2), "xanh lá": (0.2, 0.7, 0.3), "xanh dương": (0.2, 0.4, 0.9),
          "tím": (0.6, 0.3, 0.7), "hồng": (1.0, 0.5, 0.7)}
ROBOT_COLORS = [(0.1, 0.5, 1.0), (1.0, 0.45, 0.1), (0.3, 0.8, 0.3), (0.8, 0.2, 0.8)]


class Visualizer:
    def __init__(self, bus, robots, labels, grid, depth_grid, catalog=None, hz=2.0):
        from nav_msgs.msg import OccupancyGrid
        from visualization_msgs.msg import Marker, MarkerArray
        self.OccupancyGrid, self.Marker, self.MarkerArray = OccupancyGrid, Marker, MarkerArray
        self.node = bus.node
        self.robots, self.labels = robots, labels
        self.grid, self.depth_grid, self.catalog = grid, depth_grid, catalog
        self.map_pub = self.node.create_publisher(OccupancyGrid, "/govoice/map", 1)
        self.mk_pub = self.node.create_publisher(MarkerArray, "/govoice/markers", 1)
        self.hz = hz
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        k = 0
        while self.running:
            try:
                self.publish_markers()
                if k % 2 == 0:
                    self.publish_map()
            except Exception as e:                     # noqa: BLE001
                print(f"[viz] {e!r}")
            k += 1
            time.sleep(1.0 / self.hz)

    def _stamp(self):
        return self.node.get_clock().now().to_msg()

    def publish_map(self):
        g = self.grid
        msg = self.OccupancyGrid()
        msg.header.frame_id = "map"
        msg.header.stamp = self._stamp()
        msg.info.resolution = float(g.res)
        msg.info.width, msg.info.height = g.nx, g.ny
        msg.info.origin.position.x, msg.info.origin.position.y = float(g.x0), float(g.y0)
        msg.info.origin.orientation.w = 1.0
        with g.lock:
            ev = g.ev.copy()
        with self.depth_grid.lock:
            evd = self.depth_grid.ev.copy()
        data = np.full(ev.shape, -1, np.int8)              # chua biet
        data[(ev < 0) | (evd < 0)] = 0                     # da thay trong
        data[(ev > 0) | (evd > 0)] = 50                    # nghi co vat (chua du chac)
        data[(ev >= g.thresh) | (evd >= self.depth_grid.thresh)] = 100
        msg.data = data.ravel().tolist()
        self.map_pub.publish(msg)

    def _mk(self, ns, mid, typ, rgba, scale, pose=(0, 0, 0, 0), text=""):
        m = self.Marker()
        m.header.frame_id = "map"
        m.header.stamp = self._stamp()
        m.ns, m.id, m.type, m.action = ns, mid, typ, self.Marker.ADD
        x, y, z, yaw = pose
        m.pose.position.x, m.pose.position.y, m.pose.position.z = float(x), float(y), float(z)
        m.pose.orientation.z, m.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        m.scale.x, m.scale.y, m.scale.z = (float(v) for v in scale)
        m.color.r, m.color.g, m.color.b, m.color.a = (float(v) for v in rgba)
        m.text = text
        m.lifetime.sec = 2
        return m

    def publish_markers(self):
        M = self.Marker
        arr = self.MarkerArray()
        mid = 0
        for i, (ns, r) in enumerate(self.robots.items()):
            p = r.map_pose()
            if p is None:
                continue
            c = ROBOT_COLORS[i % len(ROBOT_COLORS)]
            arr.markers.append(self._mk("robot", mid, M.CUBE, (*c, 0.8), (0.70, 0.31, 0.25),
                                        (p[0], p[1], 0.3, p[2])))
            mid += 1
            arr.markers.append(self._mk("robot", mid, M.ARROW, (*c, 1.0), (0.5, 0.06, 0.06),
                                        (p[0], p[1], 0.45, p[2])))
            mid += 1
            state = getattr(r, "state", "")
            arr.markers.append(self._mk("label", mid, M.TEXT_VIEW_FACING, (1, 1, 1, 1),
                                        (0, 0, 0.22), (p[0], p[1], 0.85, 0),
                                        f"{self.labels.get(ns, ns)}: {state}"))
            mid += 1
            if r.goal is not None:
                arr.markers.append(self._mk("goal", mid, M.CYLINDER, (0.1, 0.9, 0.2, 0.7),
                                            (0.25, 0.25, 0.6), (r.goal[0], r.goal[1], 0.3, 0)))
                mid += 1
            # nguoi dang theo doi (tracker cua robot nay)
            threat = r._threat() if r.avoid else None
            for tr in r.tracker.movers():
                danger = threat is not None and tr is threat[0]
                col = (1.0, 0.1, 0.1, 0.9) if danger else (1.0, 0.6, 0.2, 0.8)
                arr.markers.append(self._mk("people", mid, M.CYLINDER, col, (0.44, 0.44, 1.6),
                                            (tr["p"][0], tr["p"][1], 0.8, 0)))
                mid += 1
                v = tr["v"]
                sp = float(np.linalg.norm(v))
                if sp > 0.05:
                    arr.markers.append(self._mk("people", mid, M.ARROW, col, (sp, 0.08, 0.08),
                                                (tr["p"][0], tr["p"][1], 1.7,
                                                 math.atan2(v[1], v[0]))))
                    mid += 1
        if self.catalog:
            for it in self.catalog.items:
                rgb = COLORS.get(it["color"], (0.5, 0.5, 0.5))
                arr.markers.append(self._mk("objects", mid, M.CUBE, (*rgb, 0.35),
                                            (it["sx"], it["sy"], max(it["sz"], 0.02)),
                                            (it["x"], it["y"], it["sz"] / 2, it["yaw"])))
                mid += 1
                arr.markers.append(self._mk("objects", mid, M.TEXT_VIEW_FACING, (1, 1, 0.6, 1),
                                            (0, 0, 0.16), (it["x"], it["y"], it["sz"] + 0.25, 0),
                                            self.catalog.describe(it)))
                mid += 1
        self.mk_pub.publish(arr)

    def stop(self):
        self.running = False
