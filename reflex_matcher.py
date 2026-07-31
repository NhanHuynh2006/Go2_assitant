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

# ---- Toc do mac dinh (se bi robot_tools/guard clamp lai theo config) ----
VX = 0.5       # m/s tien/lui (cu 0.35) — di dut khoat hon
VY = 0.3       # m/s sang ngang (cu 0.25)
VYAW = 1.2     # rad/s xoay (cu 0.8) — xoay nhanh hon
DUR = 2.0      # giay mac dinh cho 1 lenh di chuyen (khong co so met/giay)
# Moi lenh di duoc gui LIEN TUC trong 1 khuc dai (khong che nho) -> robot di MUOT,
# khong StopMove giua chung. Guard/robot_tools van clamp theo max_duration cua config.
MAX_CHUNK_S = 30.0


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
        d = round(min(left, MAX_CHUNK_S), 2)
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

    # --- ACROBATIC (dat TRUOC dance/di-thang de bat dung y) ---
    # Trong chuoi = dung 2 chan TRUOC (check truoc walkupright vi cung chua '2 chan')
    (["trong chuoi", "chong chuoi", "trong cay chuoi", "hai chan truoc", "2 chan truoc",
      "dung bang chan truoc", "dung chan truoc", "chong hai tay", "dung bang tay", "dung nguoc"],
     lambda t: _action("handstand", "Xem m\u00ecnh tr\u1ed3ng chu\u1ed1i n\u00e8!")),
    # Dung/di bang 2 chan SAU (nhu nguoi)
    (["dung hai chan", "dung 2 chan", "dung bang hai chan", "dung bang 2 chan", "hai chan sau",
      "2 chan sau", "chan sau", "di bang hai chan", "di 2 chan", "dung thang nguoi",
      "dung nhu nguoi", "dung len nhu nguoi"],
     lambda t: _action("walkupright", "M\u00ecnh \u0111\u1ee9ng b\u1eb1ng hai ch\u00e2n n\u00e8, oai kh\u00f4ng!")),
    # Bat VE PHIA TRUOC (khac nhay mua Dance1)
    (["bat ve phia truoc", "bat len phia truoc", "nhay ve phia truoc", "nhay ve truoc",
      "bat ve truoc", "bat toi truoc", "nhay toi truoc", "phong ve phia truoc",
      "bat nhay ve truoc", "nhay ra phia truoc", "bat ra phia truoc"],
     lambda t: _action("frontjump", "B\u1eadt t\u1edbi n\u00e0o!")),

    (["di thang", "tien len", "di toi", "di len", "tien toi", "di ve phia truoc", "tien"],
     lambda t: _move_with_amount(t, vx=VX, say="\u0110i th\u1eb3ng n\u00e8!")),

    (["di lui", "lui lai", "lui ve", "di ve sau", "lui"],
     lambda t: _move_with_amount(t, vx=-VX * 0.8, say="L\u00f9i l\u1ea1i n\u00e8!")),

    (["sang trai", "qua trai", "di ben trai", "buoc sang trai", "di trai"],
     lambda t: _move_with_amount(t, vy=VY, say="Sang tr\u00e1i n\u00e8!")),

    (["sang phai", "qua phai", "di ben phai", "buoc sang phai", "di phai"],
     lambda t: _move_with_amount(t, vy=-VY, say="Sang ph\u1ea3i n\u00e8!")),

    (["xoay trai", "quay trai", "re trai", "quay ben trai", "xoay ben trai", "xoay qua trai"],
     lambda t: _move_with_amount(t, vyaw=VYAW, say="Xoay tr\u00e1i!")),

    (["xoay phai", "quay phai", "re phai", "quay ben phai", "xoay ben phai", "xoay qua phai"],
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


# ============================================================================
#  CHAT / HOI-DAP: cau hoi giao tiep thuong gap -> tra loi SAN, KHONG qua LLM.
#  M\u1ed7i entry: (danh_sach_tu_khoa DA BO DAU, cau_tra_loi CO DAU, ten_dong_tac|None).
#  Dung cum >=2 tu de tranh dinh nham lenh dieu khien. Persona: "G\u00f4" - cho robot Go2.
# ============================================================================
_CHAT_RULES = [
    # --- Danh tinh / ten ---
    (["ban la ai", "la ai vay", "con la ai", "ban la con gi", "cau la ai",
      "may la ai", "la ai do", "la ai the"],
     "M\u00ecnh l\u00e0 G\u00f4, ch\u00fa ch\u00f3 robot Go2 c\u1ee7a lab ISLab, Tr\u01b0\u1eddng \u0110\u1ea1i h\u1ecdc C\u00f4ng ngh\u1ec7 "
     "K\u1ef9 thu\u1eadt Th\u00e0nh ph\u1ed1 H\u1ed3 Ch\u00ed Minh. R\u1ea5t vui \u0111\u01b0\u1ee3c g\u1eb7p b\u1ea1n, g\u00e2u g\u00e2u!", None),
    (["ten gi", "ten la gi", "ten ban", "may ten", "gioi thieu", "ten cau",
      "ten la j", "ban ten"],
     "M\u00ecnh t\u00ean l\u00e0 G\u00f4, ch\u00fa ch\u00f3 robot Go2 d\u1ec5 th\u01b0\u01a1ng \u0111\u00e2y! G\u00e2u g\u00e2u!", None),
    # --- Kha nang ---
    (["lam duoc gi", "biet lam gi", "lam nhung gi", "co the lam gi", "lam gi duoc",
      "biet nhung gi", "lam duoc nhung gi", "co the lam nhung gi", "biet gi khong"],
     "M\u00ecnh bi\u1ebft \u0111i t\u1edbi \u0111i l\u00f9i, xoay tr\u00e1i ph\u1ea3i, nh\u1ea3y m\u00faa, ch\u00e0o, th\u1ea3 tim, v\u01b0\u01a1n vai, "
     "\u0111\u1ee9ng b\u1eb1ng hai ch\u00e2n, tr\u1ed3ng chu\u1ed1i v\u00e0 b\u1eadt t\u1edbi tr\u01b0\u1edbc n\u1eefa. C\u1ee9 ra l\u1ec7nh l\u00e0 m\u00ecnh l\u00e0m li\u1ec1n!", None),
    # --- Suc khoe / cam xuc ---
    (["khoe khong", "co khoe khong", "the nao roi", "dao nay sao", "on khong"],
     "M\u00ecnh kh\u1ecfe re, pin \u0111\u1ea7y, s\u1eb5n s\u00e0ng qu\u1eady! G\u00e2u g\u00e2u!", None),
    # --- Cam on ---
    (["cam on", "cam on nhe", "cam on go", "cam on nha", "cam on ban"],
     "Kh\u00f4ng c\u00f3 chi, m\u00ecnh vui l\u1eafm n\u00e8!", None),
    # --- Tuoi ---
    (["bao nhieu tuoi", "may tuoi", "tuoi may", "sinh nam nao", "tuoi gi"],
     "M\u00ecnh l\u00e0 robot n\u00ean tr\u1ebb ho\u00e0i \u00e0, kh\u00f4ng c\u00f3 gi\u00e0 \u0111\u00e2u! G\u00e2u g\u00e2u!", None),
    # --- Ai tao ra / cua ai ---
    (["ai tao ra", "ai lam ra", "ai che tao", "ai san xuat", "ban cua ai",
      "chu cua ban", "ai so huu", "ai lap trinh"],
     "M\u00ecnh \u0111\u01b0\u1ee3c c\u00e1c anh ch\u1ecb \u1edf lab ISLab - Intelligent System Lab, d\u01b0\u1edbi s\u1ef1 h\u01b0\u1edbng "
     "d\u1eabn c\u1ee7a th\u1ea7y Ph\u00f3 Gi\u00e1o S\u01b0 Ti\u1ebfn S\u0129 L\u00ea M\u1ef9 H\u00e0, l\u1eadp tr\u00ecnh n\u00ean \u0111\u00f3!", None),
    # --- Den tu dau ---
    (["den tu dau", "tu dau toi", "que o dau", "que quan", "o dau den"],
     "M\u00ecnh \u0111\u1ebfn t\u1eeb lab ISLab, Tr\u01b0\u1eddng \u0110\u1ea1i h\u1ecdc C\u00f4ng ngh\u1ec7 K\u1ef9 thu\u1eadt Th\u00e0nh ph\u1ed1 H\u1ed3 Ch\u00ed "
     "Minh, t\u00ean c\u0169 l\u00e0 \u0110\u1ea1i h\u1ecdc S\u01b0 ph\u1ea1m K\u1ef9 thu\u1eadt \u0111\u00f3!", None),
    # --- Dang lam gi ---
    (["dang lam gi", "lam gi do", "dang lam chi", "lam chi do"],
     "M\u00ecnh \u0111ang \u0111\u1ee9ng ch\u1edd l\u1ec7nh c\u1ee7a b\u1ea1n n\u00e8, ra l\u1ec7nh \u0111i!", None),
    # --- Cho that hay robot ---
    (["cho that khong", "co phai cho that", "la cho that", "cho hay nguoi",
      "nguoi hay cho", "robot hay cho", "cho robot a", "cho gia"],
     "M\u00ecnh l\u00e0 ch\u00f3 ROBOT nha, kh\u00f4ng ph\u1ea3i ch\u00f3 th\u1eadt, nh\u01b0ng d\u1ec5 th\u01b0\u01a1ng y chang \u0111\u00fang kh\u00f4ng? G\u00e2u g\u00e2u!", None),
    # --- Yeu / thuong (kem tha tim) ---
    (["co yeu", "yeu toi khong", "yeu minh khong", "co thuong toi", "yeu ban"],
     "Th\u01b0\u01a1ng b\u1ea1n nhi\u1ec1u l\u1eafm n\u00e8!", "heart"),
    # --- Tam biet ---
    (["tam biet", "chao tam biet", "bye bye", "hen gap lai", "minh ve day"],
     "T\u1ea1m bi\u1ec7t b\u1ea1n, h\u1eb9n g\u1eb7p l\u1ea1i nha! G\u00e2u g\u00e2u!", None),
    # --- Khen ---
    (["gioi lam", "gioi qua", "hay lam", "hay qua", "tuyet voi", "gioi ghe",
      "dinh qua", "lam tot lam", "gioi that"],
     "H\u00ed h\u00ed, c\u1ea3m \u01a1n b\u1ea1n, m\u00ecnh s\u1ebd c\u1ed1 g\u1eafng n\u1eefa n\u00e8!", None),
    # --- So thich ---
    (["thich gi", "so thich", "thich lam gi"],
     "M\u00ecnh th\u00edch ch\u1ea1y nh\u1ea3y v\u00e0 bi\u1ec3u di\u1ec5n cho m\u1ecdi ng\u01b0\u1eddi xem! G\u00e2u g\u00e2u!", None),
    # --- Gioi tinh ---
    (["trai hay gai", "con trai hay", "gioi tinh", "nam hay nu", "la nam hay"],
     "M\u00ecnh l\u00e0 robot n\u00ean kh\u00f4ng c\u00f3 trai hay g\u00e1i \u0111\u00e2u, c\u1ee9 g\u1ecdi m\u00ecnh l\u00e0 G\u00f4 l\u00e0 \u0111\u01b0\u1ee3c! G\u00e2u g\u00e2u!", None),
    # --- Biet noi ---
    (["biet noi khong", "noi duoc khong", "biet noi tieng viet", "noi tieng gi"],
     "M\u00ecnh n\u00f3i \u0111\u01b0\u1ee3c ti\u1ebfng Vi\u1ec7t n\u00e8, \u0111ang tr\u00f2 chuy\u1ec7n v\u1edbi b\u1ea1n \u0111\u00e2y th\u00f4i! G\u00e2u g\u00e2u!", None),
    # --- Sua / keu ---
    (["sua di", "sua nghe", "biet sua khong", "keu di", "sua mot cai", "sua coi"],
     "G\u00e2u g\u00e2u g\u00e2u! M\u00ecnh s\u1ee7a \u0111\u01b0\u1ee3c n\u00e8, hay kh\u00f4ng?", None),
    # --- Doi / an ---
    (["co doi khong", "doi bung khong", "an com chua", "an gi chua", "doi khong"],
     "M\u00ecnh ch\u1ea1y b\u1eb1ng pin ch\u1ee9 kh\u00f4ng \u0103n c\u01a1m \u0111\u00e2u, nh\u01b0ng c\u1ea3m \u01a1n b\u1ea1n \u0111\u00e3 quan t\u00e2m n\u00e8!", None),
    # --- May gio ---
    (["may gio roi", "gio gi roi", "biet may gio", "gio nao roi"],
     "M\u00ecnh kh\u00f4ng \u0111eo \u0111\u1ed3ng h\u1ed3 n\u00ean ch\u1ecbu, h\u1ecfi \u0111i\u1ec7n tho\u1ea1i gi\u00f9m m\u00ecnh nha! G\u00e2u g\u00e2u!", None),
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
                d = round(min(left, MAX_CHUNK_S), 2)
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
                d = round(min(left, MAX_CHUNK_S), 2)
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

        # ---- CHAT/HOI-DAP: tra loi san cho cau giao tiep (khong qua LLM) ----
        # Cau co "mui" truong/lab/thay -> KHONG dung chat chung chung, nhuong FAQ
        # (knowledge.yaml) tra loi chinh xac (vd 'truong ban ten gi' != 'ban ten gi').
        _topic = ("truong", "lab", "islab", "thay", "nghien cuu", "sinh vien",
                  "hieu truong", "khoa", "nganh")
        if not any(w in t for w in _topic):
            for kws, say, action_name in _CHAT_RULES:
                if any(k in t for k in kws):
                    acts = ([{"tool": "action", "args": {"name": action_name}}]
                            if action_name else [])
                    return {"intent": "chat", "say": say, "actions": acts}
        return None


if __name__ == "__main__":
    m = ReflexMatcher()
    for s in ["\u0111i th\u1eb3ng 2 m\u00e9t", "xoay tr\u00e1i", "d\u1eebng l\u1ea1i", "n\u1eb1m xu\u1ed1ng",
              "ch\u00e0o \u0111i", "\u0111i t\u1edbi c\u00e1i c\u1eeda r\u1ed3i ch\u00e0o hai c\u00e1i nha"]:
        print(f"{s!r:50s} -> {m.match(s)}")
