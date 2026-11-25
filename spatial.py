#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spatial.py — DICH THEO QUAN HE KHONG GIAN (y tuong VLMaps, Huang et al. 2023):

  "đi tới bên trái cái bàn"      -> dung ben trai ban (nhin tu phia phong), mat huong vao ban
  "ra phía sau cái ghế"          -> sau ghe
  "đứng trước cửa"               -> truoc cua
  "lại cách cửa sổ 2 mét"        -> tren duong nhin vao cua so, cach no 2 m

Waypoint thuong la CHO DUNG nhin vao do vat (x, y, yaw). Vi tri do vat lay tu truong
`obj` neu co, khong thi uoc = waypoint + 0.9 m theo huong yaw. "Trai/phai" tinh theo
nguoi dung o waypoint nhin vao do vat — giong cach nguoi trong phong noi.

Tat dinh, ~0 ms, khong can LLM: cung tinh than tang Reflex/Combo.
"""

import math
import re

from reflex_matcher import norm

_NUM = {"mot": 1.0, "hai": 2.0, "ba": 3.0, "bon": 4.0, "nam": 5.0, "nua": 0.5, "ruoi": 1.5}
_REL = [("trai", r"ben\s+trai(?:\s+cua)?"), ("phai", r"ben\s+phai(?:\s+cua)?"),
        ("sau", r"(?:phia\s+)?sau(?:\s+lung)?(?:\s+cua)?"),
        ("truoc", r"(?:phia\s+|dang\s+)?truoc(?:\s+mat)?(?:\s+cua)?"),
        ("canh", r"(?:ben\s+)?canh")]
_DIST = re.compile(r"cach\s+(.+?)\s+((?:\d+(?:[.,]\d+)?)|mot|hai|ba|bon|nam|nua)\s*(?:met|m)\b")
_ARTICLE = r"(?:\s+(?:cai|chiec|con|cho|cua))?"


def _place_pose(wp):
    pose = wp.get("pose") if isinstance(wp, dict) else wp
    x, y = float(pose[0]), float(pose[1])
    yaw = float(pose[2]) if len(pose) > 2 else 0.0
    if isinstance(wp, dict) and wp.get("obj"):
        ox, oy = float(wp["obj"][0]), float(wp["obj"][1])
    else:
        ox, oy = x + 0.9 * math.cos(yaw), y + 0.9 * math.sin(yaw)
    return (x, y, yaw), (ox, oy)


def parse_spatial(text, places):
    """places: {ten_khong_dau: waypoint}. -> (ten, quan_he, khoang_cach) | None."""
    t = norm(text)
    names = sorted(places, key=len, reverse=True)        # 'cua so' truoc 'cua'
    m = _DIST.search(t)
    if m:
        target, num = m.group(1), m.group(2).replace(",", ".")
        for n in names:
            if re.search(rf"\b{re.escape(n)}\b", target):
                d = _NUM.get(num) or float(num)
                return n, "cach", d
    for rel, pat in _REL:
        for n in names:
            if re.search(rf"\b{pat}{_ARTICLE}\s+{re.escape(n)}\b", t):
                return n, rel, None
    return None


def parse_relation(text):
    """Chi tim quan he (khong can ten cho): -> (quan_he, khoang_cach) | None.
    Dung cho do vat: "bên trái cái ghế màu tím", "cách cái bàn đen 1 mét"."""
    t = norm(text)
    m = re.search(r"cach\s+.+?\s+((?:\d+(?:[.,]\d+)?)|mot|hai|ba|bon|nam|nua)\s*(?:met|m)\b", t)
    if m:
        num = m.group(1).replace(",", ".")
        return "cach", _NUM.get(num) or float(num)
    for rel, pat in _REL:
        if re.search(rf"\b{pat}{_ARTICLE}\b", t):
            return rel, None
    return None


def spatial_goal(wp, rel, dist=None, clearance=0.55):
    """-> (x, y, yaw) dich, mat huong vao do vat.
    `size: [rong, sau]` cua do vat (neu co trong waypoint) de dung ngoai mep no;
    ben trai/phai lui ve phia phong 0.45 m de khong dung sat tuong (cua, cua so)."""
    (vx, vy, vyaw), (ox, oy) = _place_pose(wp)
    size = wp.get("size", [0.6, 0.6]) if isinstance(wp, dict) else [0.6, 0.6]
    half_w, half_d = float(size[0]) / 2, float(size[1]) / 2
    fx, fy = ox - vx, oy - vy                            # huong tu cho dung toi do vat
    L = math.hypot(fx, fy) or 1.0
    fx, fy = fx / L, fy / L
    lx, ly = -fy, fx                                     # ben trai (nhin tu cho dung)
    side = half_w + clearance
    if rel == "trai":
        gx, gy = ox + side * lx - 0.45 * fx, oy + side * ly - 0.45 * fy
    elif rel in ("phai", "canh"):
        gx, gy = ox - side * lx - 0.45 * fx, oy - side * ly - 0.45 * fy
    elif rel == "sau":
        gx, gy = ox + (half_d + clearance) * fx, oy + (half_d + clearance) * fy
    elif rel == "truoc":
        gx, gy = ox - (half_d + clearance) * fx, oy - (half_d + clearance) * fy
    else:                                                # "cach X d met"
        d = max(0.5, float(dist or 1.0))
        gx, gy = ox - d * fx, oy - d * fy
    return gx, gy, math.atan2(oy - gy, ox - gx)


if __name__ == "__main__":
    wps = {"ban": {"pose": [-2.0, 2.2, 1.57], "obj": [-2.0, 3.25], "size": [1.4, 0.8]},
           "cua": [0.0, -3.0, -1.57], "cua so": [2.25, 3.0, 1.57]}
    for s in ["đi tới bên trái cái bàn", "ra phía sau cái bàn", "đứng trước cửa",
              "lại cách cửa sổ 2 mét", "cách cửa nửa mét", "ra cửa", "bên cạnh cửa sổ"]:
        p = parse_spatial(s, wps)
        g = spatial_goal(wps[p[0]], p[1], p[2]) if p else None
        print(f"{s:28} -> {p} -> {tuple(round(v, 2) for v in g) if g else None}")
