#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reflex_matcher.py — TANG 1 "PHAN XA" cua GoVoice.

Y tuong (diem nhan kien truc de viet bao):
  ~80% lenh thuc te la lenh don ("di thang", "ngoi xuong", "chao").
  Nhung lenh nay KHONG can LLM — match truc tiep bang luat -> ~0ms,
  robot phan ung TUC THI. Cau phuc tap moi day xuong Tang 2 (LLM).
  Giong he thong System-1 (phan xa) / System-2 (suy nghi) cua nao nguoi.

Quy tac an toan:
  - Cau > 6 tu  -> tra None (de LLM xu ly, tranh "cuop" cau phuc tap)
  - Lenh DUNG luon duoc uu tien check dau tien
"""

import math
import re
import unicodedata

# ---- Toc do mac dinh (se bi robot_tools clamp lai lan nua) ----
VX = 0.35      # m/s tien/lui
VY = 0.25      # m/s sang ngang
VYAW = 0.8     # rad/s xoay
DUR = 2.0      # giay mac dinh cho 1 lenh di chuyen


def strip_accents(s: str) -> str:
    """Bo dau tieng Viet: 'đi thẳng' -> 'di thang' (de match ke ca khi STT thieu dau)."""
    s = s.replace("\u0111", "d").replace("\u0110", "D")  # đ/Đ
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(s.lower())).strip()


# ---- TANG TU CHOI: hanh dong robot CHAC CHAN khong lam duoc ----
# DA BO DAU. Dung CUM da-am-tiet de tranh dung tu hop le khi mat dau:
#   "bay"~"bay(7)", "ban"~"ban(table)", "lai"~"lai(again)" -> nen ghep tu.
_REFUSE_KW = [
    "bay len", "bay qua", "bay vong", "bay cao",          # bay
    "boi qua", "boi loi", "tap boi", "lan xuong nuoc",     # boi/lan
    "leo len", "leo tuong", "leo cay", "leo mai", "treo len", "treo nguoc",  # leo treo
    "ca hat", "hat bai", "hat mot bai", "hat karaoke", "hat cho minh nghe",  # hat
    "nau an", "nau com", "pha ca phe", "pha tra", "lam banh",   # nau nuong
    "ban sung", "ban laser", "ban phao",                  # ban
    "phun nuoc", "phun lua",                              # phun
    "hut bui",                                           # hut bui
    "lai xe", "lai oto", "lai may bay",                   # lai
    "giat do", "rua chen", "rua bat", "quet nha", "lau nha", "don nha",  # viec nha
    "can nguoi", "can ai", "can chu",                     # can
    "len noc nha", "nhay len noc", "nhay len tuong", "nhay len mai",  # noc/tuong
    "100 cay so", "100 km", "chay 100", "1000 cay",       # toc do/quang duong vo ly
    "hat karaoke", "dong phim", "ve tranh", "danh dan",   # khac
]

_REFUSE_SAY = "Cái đó mình chưa làm được á, xin lỗi nha!"


# So bang chu (1-10) — chi nhan khi co don vi di kem (met/giay)
_WORD_NUM = {
    "mot": 1, "hai": 2, "ba": 3, "bon": 4, "nam": 5,
    "sau": 6, "bay": 7, "tam": 8, "chin": 9, "muoi": 10,
}


def _parse_amount(t: str):
    """Tim '2 met' / '3 giay' / 'hai met'... -> (value, unit) hoac (None, None)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(met|m|giay|s)\b", t)
    if m:
        return float(m.group(1).replace(",", ".")), m.group(2)
    m = re.search(r"\b(mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s*(met|m|giay|s)\b", t)
    if m:
        return float(_WORD_NUM[m.group(1)]), m.group(2)
    return None, None


def _move_with_amount(t, vx=0.0, vy=0.0, vyaw=0.0, say="Ok!"):
    dur = DUR
    val, unit = _parse_amount(t)
    if val is not None:
        if unit in ("met", "m"):
            speed = max(abs(vx), abs(vy), 0.1)
            dur = val / speed                    # quang duong -> tong thoi gian
        else:
            dur = val                            # giay
    dur = min(dur, 30.0)                         # tran tong the (an toan)
    # Che thanh tung lenh <= 6s de DI DU quang duong (khong cat cut)
    actions = []
    left = dur
    while left > 0.05:
        d = round(min(left, 6.0), 2)
        actions.append({"tool": "move",
                        "args": {"vx": vx, "vy": vy, "vyaw": vyaw, "duration": d}})
        left -= d
    return {"say": say, "actions": actions}


def _action(name, say):
    return {"say": say, "actions": [{"tool": "action", "args": {"name": name}}]}


# ---- Bang luat: (danh sach cum tu DA BO DAU, ham builder) ----
# Thu tu = do uu tien. DUNG LAI luon dau tien!
_RULES = [
    (["dung lai", "dung ngay", "ngung", "stop", "dung yen"],
     lambda t: {"say": "D\u1eebng li\u1ec1n!", "actions": [{"tool": "stop", "args": {}}]}),

    (["dung len", "dung day", "dung d\u1eady"],
     lambda t: _action("standup", "D\u1ea1, \u0111\u1ee9ng d\u1eady n\u00e8!")),

    (["nam xuong", "ngoi xuong", "nam nghi", "nam di", "nam ra"],
     lambda t: _action("standdown", "Ok, n\u1eb1m xu\u1ed1ng ngh\u1ec9 n\u00e8.")),

    (["di thang", "tien len", "di toi", "di len", "tien toi", "di ve phia truoc", "tien"],
     lambda t: _move_with_amount(t, vx=VX, say="\u0110i th\u1eb3ng n\u00e8!")),

    (["di lui", "lui lai", "lui ve", "di ve sau", "lui"],
     lambda t: _move_with_amount(t, vx=-VX * 0.8, say="L\u00f9i l\u1ea1i n\u00e8!")),

    (["sang trai", "qua trai", "di ben trai", "buoc sang trai", "di trai"],
     lambda t: _move_with_amount(t, vy=VY, say="Sang tr\u00e1i n\u00e8!")),

    (["sang phai", "qua phai", "di ben phai", "buoc sang phai", "di phai"],
     lambda t: _move_with_amount(t, vy=-VY, say="Sang ph\u1ea3i n\u00e8!")),

    (["xoay trai", "quay trai", "re trai", "quay ben trai"],
     lambda t: _move_with_amount(t, vyaw=VYAW, say="Xoay tr\u00e1i!")),

    (["xoay phai", "quay phai", "re phai", "quay ben phai"],
     lambda t: _move_with_amount(t, vyaw=-VYAW, say="Xoay ph\u1ea3i!")),

    (["chao", "bat tay", "hello", "vay tay"],
     lambda t: _action("hello", "Ch\u00e0o b\u1ea1n! G\u00e2u g\u00e2u!")),

    (["doi dieu", "nhay bai khac", "dieu so hai", "dieu so 2", "dance2"],
     lambda t: _action("dance2", "\u0110\u1ed5i \u0111i\u1ec7u li\u1ec1n!")),

    (["nhay mua", "nhay di", "nhay coi", "nhay dance", "dance", "nhay", "mua"],
     lambda t: _action("dance1", "Qu\u1ea9y l\u00ean n\u00e0o!")),

    (["vuon vai", "duoi nguoi", "gian co"],
     lambda t: _action("stretch", "V\u01b0\u01a1n vai c\u00e1i n\u00e0o!")),

    (["tha tim", "trai tim", "tim nao", "thuong"],
     lambda t: _action("heart", "Th\u01b0\u01a1ng b\u1ea1n nhi\u1ec1u!")),
]


class ReflexMatcher:
    """match(text) -> dict {say, actions} neu trung luat, nguoc lai None."""

    def __init__(self, max_words: int = 6):
        self.max_words = max_words

    def match(self, text: str):
        t = norm(text)
        if not t:
            return None
        # ---- UU TIEN 0: TU CHOI hanh dong bat kha thi (truoc moi luat, ke ca cau dai) ----
        # Tranh map nham "bay len troi" thanh 1 move hop le. Khop cum da-am-tiet -> an toan.
        if any(k in t for k in _REFUSE_KW):
            return {"intent": "refuse", "say": _REFUSE_SAY, "actions": []}
        # Cau dai -> nhuong cho LLM (tranh hieu nham cau phuc tap)
        # Ngoai le: PHANH TUONG MINH thi cau dai may cung phai bat!
        # ("dung yen" KHONG nam day — no chi bat o cau ngan, tranh cuop
        #  cau kieu "ra cho cai ban roi dung yen do cho minh")
        hard_stop = ("dung lai", "dung ngay", "stop", "ngung")
        is_stop = any(k in t for k in hard_stop)
        if len(t.split()) > self.max_words and not is_stop:
            return None

        # ---- UU TIEN 1: xoay theo DO ("sang trai 45 do", "xoay phai 90 do") ----
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*do\b", t)
        if not m:
            m2 = re.search(r"\b(mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s*do\b", t)
            if m2:
                deg = float(_WORD_NUM[m2.group(1)])
            else:
                deg = None
        else:
            deg = float(m.group(1).replace(",", "."))
        if deg is not None and ("trai" in t or "phai" in t):
            sgn = 1.0 if "trai" in t else -1.0
            total = deg * math.pi / 180.0 / VYAW
            actions = []
            left = min(total, 30.0)
            while left > 0.05:                    # che tung lenh <= 6s (du goc)
                d = round(min(left, 6.0), 2)
                actions.append({"tool": "move",
                                "args": {"vx": 0, "vy": 0, "vyaw": sgn * VYAW,
                                         "duration": d}})
                left -= d
            side_word = "tr\u00e1i" if sgn > 0 else "ph\u1ea3i"
            return {"intent": "xoay_do",
                    "say": f"Xoay {side_word} {deg:g} \u0111\u1ed9!",
                    "actions": actions}

        # ---- UU TIEN 2: xoay theo VONG ("xoay 2 vong", "xoay tai cho") ----
        has_spin_verb = ("xoay" in t) or ("quay" in t)
        mv_ = re.search(r"(\d+(?:[.,]\d+)?)\s*vong\b", t)
        if not mv_:
            mw = re.search(r"\b(mot|hai|ba|bon|nam)\s*vong\b", t)
            n_vong = float(_WORD_NUM[mw.group(1)]) if mw else None
        else:
            n_vong = float(mv_.group(1).replace(",", "."))
        if has_spin_verb and (n_vong is not None or "tai cho" in t):
            n = n_vong if n_vong is not None else 1.0
            sgn = -1.0 if "phai" in t else 1.0
            total = n * 2.0 * math.pi / VYAW          # tong thoi gian xoay
            actions = []
            left = total
            while left > 0.05:                        # che thanh tung lenh <= 6s
                d = round(min(left, 6.0), 2)
                actions.append({"tool": "move",
                                "args": {"vx": 0, "vy": 0, "vyaw": sgn * VYAW,
                                         "duration": d}})
                left -= d
            return {"intent": "xoay_vong",
                    "say": f"Xoay {n:g} v\u00f2ng n\u00e8, ch\u00f3ng m\u1eb7t lu\u00f4n!",
                    "actions": actions}

        for keywords, builder in _RULES:
            if any(k in t for k in keywords):
                out = builder(t)
                out["intent"] = keywords[0]
                return out
        return None


if __name__ == "__main__":
    m = ReflexMatcher()
    for s in ["\u0111i th\u1eb3ng 2 m\u00e9t", "xoay tr\u00e1i", "d\u1eebng l\u1ea1i", "n\u1eb1m xu\u1ed1ng",
              "ch\u00e0o \u0111i", "\u0111i t\u1edbi c\u00e1i c\u1eeda r\u1ed3i ch\u00e0o hai c\u00e1i nha"]:
        print(f"{s!r:50s} -> {m.match(s)}")
