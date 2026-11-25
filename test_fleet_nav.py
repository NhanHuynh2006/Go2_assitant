#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test offline (khong can ROS/sim) cho fleet.py va nav_local.py.

    python3 test_fleet_nav.py        # hoac: python3 -m pytest test_fleet_nav.py
"""

import math

import numpy as np

from fleet import FleetParser, parse_fleet_intent
from nav_local import OccGrid, lookahead, path_length, plan

R = ["go2_0", "go2_1"]
P = FleetParser(R, names={"go2_0": ["Mực"]})


def test_split_single_target():
    assert P.split("con một đi thẳng 1 mét") == [(["go2_0"], "đi thẳng 1 mét")]
    assert P.split("robot số 2 xoay trái") == [(["go2_1"], "xoay trái")]
    assert P.split("Mực lùi lại 1 mét") == [(["go2_0"], "lùi lại 1 mét")]


def test_split_all_and_none():
    assert P.split("cả hai chào đi") == [(R, "chào đi")]
    assert P.split("tất cả ngồi xuống") == [(R, "ngồi xuống")]
    assert P.split("đi thẳng 2 mét") == [(None, "đi thẳng 2 mét")]
    assert P.split("dừng lại") == [(None, "dừng lại")]


def test_split_two_jobs():
    assert P.split("con một ra cửa, còn con hai vào bếp") == [
        (["go2_0"], "ra cửa"), (["go2_1"], "vào bếp")]
    assert P.split("robot thứ nhất và robot thứ hai chào đi") == [(R, "chào đi")]


def test_number_words_not_robots():
    # "2 vòng", "cho 2" khong phai goi ten robot
    assert P.split("xoay cho 2 vòng") == [(None, "xoay cho 2 vòng")]
    assert P.split("đi thẳng 1 mét") == [(None, "đi thẳng 1 mét")]


def test_fleet_intents():
    assert parse_fleet_intent(P, "con một đang ở đâu") == ("where", ["go2_0"], None)
    assert parse_fleet_intent(P, "mày đang ở đâu") == ("where", None, None)
    assert parse_fleet_intent(P, "cả hai đổi chỗ") == ("swap", R, None)
    assert parse_fleet_intent(P, "con hai đi theo con một") == ("follow", ["go2_1"], "go2_0")
    assert parse_fleet_intent(P, "con hai lại chỗ con một") == ("goto_robot", ["go2_1"], "go2_0")
    assert parse_fleet_intent(P, "con một đi thẳng") is None


def test_single_robot_ignores_names():
    p1 = FleetParser(["go2"])
    assert p1.split("con hai đi thẳng") == [(None, "con hai đi thẳng")]


def test_plan_around_box():
    g = OccGrid()
    g.mark_box(0.0, -1.7, 0.6, 0.6)
    pts, why = plan(g, (0.0, 0.0), (0.0, -3.0))
    assert why == "ok" and pts
    # khong diem nao cua duong di qua vung cam quanh hop (0.3 hop + 0.3 lethal)
    for a, b in zip(pts, pts[1:]):
        for t in np.linspace(0, 1, 20):
            x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            assert not (abs(x) < 0.55 and abs(y + 1.7) < 0.55), (x, y)
    assert 3.0 < path_length(pts) < 4.5


def test_plan_blocked():
    g = OccGrid()
    for k in range(-30, 31):                       # tuong kin tu y=-3..3 o x=1
        g.mark_box(1.0, k * 0.1, 0.15, 0.12)
    g.mark_box(1.0, 0.0, 0.15, 12.0)
    g.mark_box(-1.0, 0.0, 0.15, 12.0)
    g.mark_box(0.0, 6.0, 2.2, 0.15)
    g.mark_box(0.0, -6.0, 2.2, 0.15)
    pts, why = plan(g, (0.0, 0.0), (3.0, 0.0))
    assert pts is None


def test_grid_needs_two_scans_and_clears():
    g = OccGrid()
    wall = np.array([[1.0, y] for y in np.linspace(-0.5, 0.5, 101)])
    g.integrate(0, 0, wall, free_pts=np.empty((0, 2)))
    assert g.occupied().sum() == 0                 # 1 quet = chua tin
    g.integrate(0, 0, wall, free_pts=np.empty((0, 2)))
    n = g.occupied().sum()
    assert n > 0
    # robot sat tuong: LiDAR khong tra ve gi -> KHONG duoc xoa tuong
    for _ in range(5):
        g.integrate(0.6, 0, np.empty((0, 2)), free_pts=np.empty((0, 2)))
    assert g.occupied().sum() == n
    # thay mat dat xuyen qua cho do -> xoa
    floor = np.array([[2.5 * math.cos(a), 2.5 * math.sin(a)] for a in np.linspace(-math.pi, math.pi, 720)])
    for _ in range(8):
        g.integrate(-2.0, 0, np.empty((0, 2)), free_pts=floor)
    assert g.occupied().sum() == 0


def test_fov_limits_clearing():
    g = OccGrid()
    g.mark_box(-1.0, 0.0, 0.2, 0.2, value=8)       # vat SAU lung camera
    floor = np.array([[3 * math.cos(a), 3 * math.sin(a)] for a in np.linspace(-math.pi, math.pi, 720)])
    for _ in range(10):
        g.integrate(0, 0, np.empty((0, 2)), free_pts=floor, fov=(0.0, math.radians(40)))
    assert g.occupied().sum() > 0                  # camera nhin ve +x: khong duoc xoa vat sau


def test_lookahead():
    path = [(0, 0), (1, 0), (1, 1)]
    (x, y), _ = lookahead(path, 0.0, 0.0, 0.5)
    assert (x, y) == (1, 0)
    (x, y), _ = lookahead(path, 1.0, 0.8, 0.5)
    assert (x, y) == (1, 1)


# ---------------- do vat + mau, quan he khong gian, gop lenh, theo doi nguoi ----------------
import os as _os
SDF = _os.path.expanduser("~/ros2_ws/install/unitree_go2_description/share/"
                          "unitree_go2_description/worlds/voice_house.sdf")


def test_color_names():
    from objects import color_name
    assert color_name(0.12, 0.12, 0.12) == "đen"
    assert color_name(0.95, 0.95, 0.95) == "trắng"
    assert color_name(0.90, 0.75, 0.20) == "vàng"
    assert color_name(0.20, 0.35, 0.60) == "xanh dương"
    assert color_name(0.15, 0.55, 0.20) == "xanh lá"
    assert color_name(0.45, 0.25, 0.45) == "tím"
    assert color_name(0.55, 0.33, 0.18) == "nâu"
    assert color_name(0.85, 0.25, 0.20) == "đỏ"


def test_object_catalog():
    if not _os.path.exists(SDF):
        return                                         # chua build sim: bo qua
    from objects import ObjectCatalog
    c = ObjectCatalog(SDF)
    d = lambda q: [c.describe(h) for h in c.find(q, near=(0, 0))]  # noqa: E731
    assert d("đi tới cái bàn màu đen") == ["bàn trà màu đen"]
    assert sorted(d("đi tới cái bàn")) == ["bàn trà màu đen", "bàn ăn màu nâu"]   # -> hoi lai
    assert d("lại cái hộp màu vàng") == ["hộp đồ chơi màu vàng"]
    assert d("ra cái ghế sofa xanh") == ["ghế sofa màu xanh dương"]
    assert d("đi tới cái bàn màu xanh") == []                                 # khong co
    assert c.find("đi thẳng 2 mét") is None
    it = c.find("tủ lạnh")[0]
    (gx, gy, gyaw), _ = c.approach(it, (0.0, 0.0))
    # dung ngoai mep tu lanh, khong chui vao trong
    assert math.hypot(gx - it["x"], gy - it["y"]) > max(it["sx"], it["sy"]) / 2


def test_spatial_relations():
    from spatial import parse_relation, parse_spatial, spatial_goal
    wps = {"ban an": {"pose": [-2.0, 2.2, 1.57], "obj": [-2.0, 3.25], "size": [1.4, 0.8]}}
    assert parse_spatial("đi tới bên trái cái bàn ăn", wps) == ("ban an", "trai", None)
    assert parse_spatial("lại cách bàn ăn 2 mét", wps) == ("ban an", "cach", 2.0)
    assert parse_relation("đứng phía sau cái ghế màu tím") == ("sau", None)
    gx, gy, _ = spatial_goal(wps["ban an"], "trai")
    assert gx < -2.7                                   # ben trai ban (nhin tu phong) = phia tay
    gx, gy, _ = spatial_goal(wps["ban an"], "cach", 2.0)
    assert abs(math.hypot(gx + 2.0, gy - 3.25) - 2.0) < 1e-6


def test_merge_moves():
    from fleet import merge_moves
    a = [{"tool": "move", "args": {"vx": 0.35, "vy": 0, "vyaw": 0, "duration": 6.0}},
         {"tool": "move", "args": {"vx": 0.35, "vy": 0, "vyaw": 0, "duration": 2.57}},
         {"tool": "move", "args": {"vx": 0, "vy": 0, "vyaw": 0.8, "duration": 1.96}}]
    m = merge_moves(a)
    assert [x["tool"] for x in m] == ["move_dist", "move"]
    assert abs(m[0]["args"]["duration"] - 8.57) < 1e-9


def test_tracker_and_cpa():
    from nav_local import BlobTracker, cpa
    tr = BlobTracker()
    wall = np.array([[3.0, y] for y in np.linspace(-2, 2, 80)])
    rng = np.random.default_rng(0)
    for k in range(20):
        person = np.array([1.5, -1.0 + 0.8 * k * 0.1]) + rng.normal(0, 0.03, (15, 2))
        tr.update(np.vstack([wall, person]), (0, 0), k * 0.1)
    m = tr.movers()
    assert len(m) == 1 and 0.5 < m[0]["v"][1] < 1.0     # nguoi 0.8 m/s, tuong bi bo
    t, d = cpa(np.array([2.0, 0.0]), np.array([-1.0, 0.0]))   # lao thang vao robot
    assert abs(t - 2.0) < 1e-9 and d < 1e-9
    t, d = cpa(np.array([2.0, 1.0]), np.array([0.0, 1.0]))    # dang di ra xa
    assert t == 0.0 and abs(d - math.hypot(2, 1)) < 1e-9


def test_grid_decay():
    g = OccGrid()
    g.mark_box(1.0, 0.0, 0.3, 0.3, value=6)
    for _ in range(3):
        g._last_decay = 0.0
        g.decay(period=0.0)
    assert g.occupied().sum() == 0                     # 6 -> 3 < nguong 4: vet da mo


if __name__ == "__main__":
    import sys
    fails = 0
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_")]
    for name, fn in tests:
        try:
            fn()
            print(f"OK   {name}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {name}: {e}")
    print(f"\nKET QUA: {len(tests) - fails}/{len(tests)} dat")
    sys.exit(1 if fails else 0)
