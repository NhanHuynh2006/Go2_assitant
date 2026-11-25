#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
objects.py — DI TOI DO VAT THEO TEN + MAU: "đi tới cái bàn màu đen", "lại cái hộp vàng",
"ra cái ghế sofa xanh dương", "đứng bên trái cái ghế màu tím".

Danh muc do vat (vi tri, kich thuoc, MAU) doc thang tu file the gioi .sdf cua sim —
mau lay tu <diffuse> RGB va dat ten tieng Viet bang HSV. Tren robot that, danh muc nay
se do YOLO tren anh mau D435i (go2_perception) dien vao; giao dien giu nguyen.

Mo ho (vd "cái bàn" ma co bàn ăn nâu + bàn trà đen) -> tra ve NHIEU ung vien de robot
HOI LAI ("cái bàn ăn màu nâu hay cái bàn trà màu đen ạ?") — tinh than KnowNo (Ren et
al., CoRL 2023): khong chac thi hoi, khong doan bua.

Tat dinh, khong can LLM.
"""

import colorsys
import math
import re
import xml.etree.ElementTree as ET

from reflex_matcher import norm

# ten mo hinh trong .sdf -> (ten goi chinh, cac cach goi khac)
NOUNS = {
    "table":           ("bàn ăn", ["bàn ăn", "bàn ăn cơm", "bàn"]),
    "coffee_table":    ("bàn trà", ["bàn trà", "bàn uống nước", "bàn nước", "bàn"]),
    "chair":           ("ghế gỗ", ["ghế gỗ", "ghế ăn", "ghế"]),
    "armchair":        ("ghế bành", ["ghế bành", "ghế đơn", "ghế"]),
    "sofa":            ("ghế sofa", ["ghế sofa", "ghế sô pha", "sofa", "sô pha", "ghế"]),
    "kitchen_counter": ("quầy bếp", ["quầy bếp", "tủ bếp", "kệ bếp"]),
    "fridge":          ("tủ lạnh", ["tủ lạnh"]),
    "plant":           ("chậu cây", ["chậu cây", "cây cảnh", "cái cây", "cây"]),
    "plant_stand":     ("kệ cây", ["kệ cây", "kệ để cây", "kệ"]),
    "carton_box":      ("thùng carton", ["thùng carton", "thùng giấy", "thùng", "hộp giấy"]),
    "toy_box":         ("hộp đồ chơi", ["hộp đồ chơi", "hộp", "thùng đồ chơi"]),
    "low_step":        ("bậc chắn", ["bậc chắn", "bậc thềm", "bậc", "thanh chắn"]),
    "charger_post":    ("trạm sạc", ["trạm sạc", "cục sạc", "đế sạc"]),
    "window":          ("cửa sổ", ["cửa sổ"]),
    "rug":             ("tấm thảm", ["tấm thảm", "thảm"]),
    "door_mat":        ("thảm chùi chân", ["thảm chùi chân", "thảm cửa"]),
    # --- van phong + kho hang (voice_office.sdf)
    "desk":            ("bàn làm việc", ["bàn làm việc", "bàn văn phòng", "bàn"]),
    "meeting_table":   ("bàn họp", ["bàn họp", "bàn phòng họp", "bàn"]),
    "reception":       ("quầy lễ tân", ["quầy lễ tân", "quầy tiếp tân", "lễ tân", "quầy"]),
    "bench":           ("ghế dài", ["ghế dài", "ghế băng", "ghế"]),
    "pillar":          ("cột", ["cột", "cây cột", "cột nhà"]),
    "cabinet":         ("tủ hồ sơ", ["tủ hồ sơ", "tủ tài liệu", "tủ"]),
    "printer":         ("máy in", ["máy in", "máy photo"]),
    "water_cooler":    ("cây nước", ["cây nước", "bình nước", "máy lọc nước"]),
    "whiteboard":      ("bảng trắng", ["bảng trắng", "cái bảng", "bảng"]),
    "trash_bin":       ("thùng rác", ["thùng rác", "sọt rác"]),
    "shelf":           ("kệ hàng", ["kệ hàng", "giá hàng", "kệ kho", "kệ"]),
    "pallet":          ("pallet", ["pallet", "kiện hàng", "tấm pallet"]),
}

# tu chi mau (co the ghep): moi muc -> nhan mau chuan
COLOR_WORDS = [
    ("xanh la cay", "xanh lá"), ("xanh la", "xanh lá"), ("xanh nuoc bien", "xanh dương"),
    ("xanh duong", "xanh dương"), ("xanh bien", "xanh dương"), ("xanh da troi", "xanh dương"),
    ("nau nhat", "nâu"), ("nau dam", "nâu"), ("nau", "nâu"), ("den", "đen"),
    ("trang", "trắng"), ("xam", "xám"), ("bac", "xám"), ("ghi", "xám"), ("vang", "vàng"),
    ("do", "đỏ"), ("tim", "tím"), ("hong", "hồng"), ("cam", "cam"), ("xanh", "xanh"),
]


def color_name(r, g, b):
    """RGB (0-1) -> ten mau tieng Viet (dat theo HSV, nguong thu cong)."""
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h *= 360
    if v < 0.2:
        return "đen"
    if s < 0.15:
        return "trắng" if v > 0.85 else "xám"
    if h < 15 or h >= 345:
        return "đỏ"
    if h < 45:
        return "nâu" if (v < 0.6 or s < 0.6) else "cam"
    if h < 70:
        return "vàng"
    if h < 170:
        return "xanh lá"
    if h < 260:
        return "xanh dương"
    if h < 320:
        return "tím"
    return "hồng"


def _has_marks(text):
    """Cau co dau tieng Viet? (STT va ban phim thuong co dau)"""
    return norm(text) != text.lower().strip() and any(ord(c) > 127 for c in text)


def _accented_ok(text, noun, originals):
    """Cau CO DAU thi ten do vat cung phai dung dau: 'bạn hồng' khong phai 'bàn hồng'.
    Cau khong dau (go voi, STT bo dau) -> khop theo ban bo dau nhu cu."""
    if not originals or not _has_marks(text):
        return True
    low = text.lower()
    return any(re.search(rf"(?<!\w){re.escape(o)}(?!\w)", low) for o in originals)


def _color_ok(want, have):
    return want is None or want == have or (want == "xanh" and have.startswith("xanh"))


class ObjectCatalog:
    def __init__(self, sdf_path, nouns=None):
        self.nouns = nouns or NOUNS
        self.items = []
        for m in ET.parse(sdf_path).getroot().iter("model"):
            name = (m.get("name") or "").split("__")[0]        # "chair__3" -> "chair"
            if name not in self.nouns:
                continue
            size = m.find("./link/visual/geometry/box/size")
            diff = m.find("./link/visual/material/diffuse")
            if size is None:
                continue
            pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
            sx, sy, sz = (float(v) for v in size.text.split())
            rgb = [float(v) for v in diff.text.split()[:3]] if diff is not None else [0.5] * 3
            main, aliases = self.nouns[name]
            self.items.append(dict(model=name, label=main, aliases=[norm(a) for a in aliases],
                                   color=color_name(*rgb), x=pose[0], y=pose[1],
                                   sx=sx, sy=sy, sz=sz, yaw=pose[5]))
        self._alias = sorted({a for it in self.items for a in it["aliases"]}, key=len, reverse=True)
        self.pretty = {norm(a): a for _, (_, al) in self.nouns.items() for a in al}

    @classmethod
    def from_yaml(cls, path):
        """Danh muc do vat cho NHA THAT (khong co .sdf): moi muc
        - {label: bàn ăn, aliases: [bàn ăn, bàn], color: nâu, x: 1.2, y: 0.5, sx: 1.4, sy: 0.8}
        (sau nay YOLO + D435i dien tu dong; go2_perception/scene_graph.py)."""
        import yaml
        self = cls.__new__(cls)
        self.nouns, self.items = {}, []
        with open(path, encoding="utf-8") as f:
            for e in yaml.safe_load(f) or []:
                aliases = e.get("aliases") or [e["label"]]
                self.items.append(dict(model=e["label"], label=e["label"],
                                       aliases=[norm(a) for a in aliases],
                                       color=e.get("color", ""), x=float(e["x"]), y=float(e["y"]),
                                       sx=float(e.get("sx", 0.5)), sy=float(e.get("sy", 0.5)),
                                       sz=float(e.get("sz", 0.5)), yaw=float(e.get("yaw", 0.0))))
                self.nouns[e["label"]] = (e["label"], aliases)
        self._alias = sorted({a for it in self.items for a in it["aliases"]}, key=len, reverse=True)
        self.pretty = {norm(a): a for _, (_, al) in self.nouns.items() for a in al}
        return self

    def describe(self, it):
        return f"{it['label']} màu {it['color']}"

    def parse(self, text):
        """-> (danh tu, mau | None) hoac None neu cau khong nhac do vat nao."""
        t = norm(text)
        if not hasattr(self, "_accent"):
            self._accent = {}
            for _k, (_p, aliases) in NOUNS.items():
                for a in aliases:
                    self._accent.setdefault(norm(a), set()).add(a.lower())
            for it in self.items:
                self._accent.setdefault(norm(it["label"]), set()).add(it["label"].lower())
        noun = next((a for a in self._alias if re.search(rf"\b{re.escape(a)}\b", t)
                     and _accented_ok(text, a, self._accent.get(a))), None)
        if noun is None:
            return None
        rest = t[t.index(noun) + len(noun):]
        color = None
        for w, lab in COLOR_WORDS:
            if re.search(rf"^(?:\s+mau)?\s+{w}\b", rest) or re.search(rf"\bmau\s+{w}\b", t):
                color = lab
                break
        return noun, color

    def find(self, text, near=None):
        """-> list do vat khop (gan robot truoc). [] = noi ten nhung khong co mau do."""
        p = self.parse(text)
        if p is None:
            return None
        noun, color = p
        hits = [it for it in self.items if noun in it["aliases"] and _color_ok(color, it["color"])]
        # "cái bàn ăn" khop dung 1 mon -> uu tien ten chinh xac hon ten chung
        exact = [it for it in hits if norm(it["label"]) == noun or noun in it["aliases"][:1]]
        if exact and len(exact) < len(hits):
            hits = exact
        if near is not None:
            hits.sort(key=lambda it: math.hypot(it["x"] - near[0], it["y"] - near[1]))
        return hits

    def approach(self, it, robot_xy, clearance=0.55):
        """Cho dung truoc do vat, phia robot dang dung, mat huong vao no.
        -> (x, y, yaw), waypoint gia (de spatial.py tinh 'ben trai/phai/sau')."""
        dx, dy = robot_xy[0] - it["x"], robot_xy[1] - it["y"]
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        # nua kich thuoc hop xoay theo huong (ux, uy)
        c, s = math.cos(it["yaw"]), math.sin(it["yaw"])
        half = abs(ux * c + uy * s) * it["sx"] / 2 + abs(-ux * s + uy * c) * it["sy"] / 2
        d = half + clearance
        gx, gy = it["x"] + ux * d, it["y"] + uy * d
        yaw = math.atan2(it["y"] - gy, it["x"] - gx)
        wp = {"pose": [gx, gy, yaw], "obj": [it["x"], it["y"]],
              "size": [max(it["sx"], it["sy"]), min(it["sx"], it["sy"])]}
        return (gx, gy, yaw), wp


if __name__ == "__main__":
    import os
    sdf = os.path.expanduser("~/ros2_ws/install/unitree_go2_description/share/"
                             "unitree_go2_description/worlds/voice_house.sdf")
    cat = ObjectCatalog(sdf)
    for it in cat.items:
        print(f"  {it['model']:16} {cat.describe(it):28} ({it['x']:5.2f}, {it['y']:5.2f})")
    for q in ["đi tới cái bàn màu đen", "đi tới cái bàn", "lại cái hộp màu vàng", "ra cái ghế sofa xanh",
              "đi tới cái ghế màu tím", "tới cái ghế", "ra chỗ cái thùng", "đi tới tủ lạnh",
              "đi tới cái bàn màu xanh", "ra cái thảm đỏ", "đi thẳng 2 mét"]:
        hits = cat.find(q, near=(0, 0))
        print(f"{q:28} -> " + ("(khong nhac do vat)" if hits is None else
                               ", ".join(cat.describe(h) for h in hits) or "KHONG CO"))
