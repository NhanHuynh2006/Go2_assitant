#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combo_matcher.py — TANG 1.5 "PHAN XA COMBO" cua GoVoice.

Y tuong (diem nhan kien truc cho bai bao — neuro-symbolic):
  Lenh phuc da phan la NHIEU lenh don noi bang tu noi ("roi/xong/sau do/
  tiep theo"). Moi VE thi Tang 1 (Reflex) da giai chinh xac tuyet doi.
  Vay: CHE cau theo tu noi -> giai tung ve bang Reflex (+ go_to theo
  tu vung dia diem da biet). Neu MOI ve giai duoc bang luat -> tra plan
  CHINH XAC, ~0ms, KHONG dung LLM. Chi can MOT ve khong giai duoc thi
  nhuong ca cau cho LLM (an toan, khong doan bừa).

Loi the so voi de LLM tu tinh:
  - Huong (vx/vy/vyaw) + duration (met/giay/do/vong) deu TINH TAT DINH
    -> diet han 2 loi pho bien nhat cua LLM 1.5B (sai truc, sai duration).
  - go_to khop theo TU VUNG dia diem huu han -> khong "bia" dia diem.
"""

import re
from reflex_matcher import ReflexMatcher, norm

# Tu noi tuan tu (DA BO DAU), DAI xep truoc NGAN (longest-match khi tach)
CONNECTIVES = ["roi sau do", "sau do", "tiep theo", "roi", "xong", "tiep"]

# Tu khoi dong go_to (DA BO DAU) — phai co it nhat 1 cai thi ve moi la go_to
GOTO_TRIGGERS = ["toi", "den", "ra", "lai", "ve", "chay toi", "di toi", "di ra"]

# Tu vung dia diem mac dinh = 9 diem trong gen_dataset (canonical CO DAU).
# Production: truyen waypoints.yaml keys vao de mo rong.
DEFAULT_LOCATIONS = ["cửa sổ", "cửa", "bàn", "ghế", "chỗ sạc", "góc phòng",
                     "bếp", "phòng khách", "chỗ cũ"]


def _split_clauses(text):
    """Tach cau theo tu noi tuan tu. Tra ve list cac VE (giu nguyen chu goc)."""
    # Tach tren ban DA NORM de bat ca ban mat dau, nhung cat tren index that.
    nt = norm(text)
    # build regex tu noi (bao quanh boi khoang trang/bien)
    pat = r"\s+(?:" + "|".join(re.escape(c) for c in CONNECTIVES) + r")\s+"
    # Tach normed text; do norm() chi bo dau + gom khoang trang, so tu PHAI
    # khop voi tach tren text goc da norm. Ta tach truc tiep tren normed.
    parts = re.split(pat, nt)
    return [p.strip() for p in parts if p.strip()]


def _strip_tail(clause):
    """Bo duoi tu dem. CHU Y: KHONG bo 'do' — no la don vi DO ('độ') chu khong
    phai 'đó'. Danh sach nay khop dung TAILS sinh trong gen_dataset.py."""
    tails = ["giup minh", "cho minh", "nha", "nhe", "di", "coi", "nao"]
    c = clause.strip()
    changed = True
    while changed:
        changed = False
        for tw in tails:
            if c.endswith(" " + tw):
                c = c[: -len(tw) - 1].strip()
                changed = True
    return c


class ComboMatcher:
    """match(text) -> {say, actions, intent} neu CHE & giai het bang luat,
    nguoc lai None (de nhuong LLM)."""

    def __init__(self, locations=None):
        self.reflex = ReflexMatcher()
        # canonical co dau, sap xep DAI truoc (longest-match)
        locs = list(locations) if locations else list(DEFAULT_LOCATIONS)
        self.locations = sorted(set(locs), key=lambda s: -len(norm(s)))

    def _match_goto(self, clause):
        """Neu ve la go_to (co trigger + ten dia diem da biet) -> action go_to."""
        c = norm(clause)
        if not any(re.search(r"\b" + re.escape(g) + r"\b", c) for g in GOTO_TRIGGERS):
            return None
        for loc in self.locations:                 # da sap dai-truoc
            if re.search(r"\b" + re.escape(norm(loc)) + r"\b", c):   # \b chong 'cho cu' lot vao 'cho cua'
                return {"tool": "go_to", "args": {"location": loc}}
        return None

    def _match_clause(self, clause):
        """Giai 1 ve -> list[action] hoac None. go_to uu tien hon move
        (vi 'di toi <dia diem>' khong phai di thang)."""
        clause = _strip_tail(clause)
        if not clause:
            return None
        g = self._match_goto(clause)
        if g is not None:
            return [g]
        r = self.reflex.match(clause)
        if r is not None and r.get("actions"):
            return list(r["actions"])
        return None

    def resolve_goto(self, text):
        """Lenh DON go_to ('ra chỗ cửa', 'đi tới góc phòng') -> plan go_to.
        Phai goi TRUOC Reflex vi Reflex hieu nham 'đi tới X' thanh di thang.
        Co cong dia diem nen khong cuop nham lenh move thuong."""
        if len(_split_clauses(text)) >= 2:
            return None                            # cau nhieu ve -> de combo/LLM lo (tranh DROP buoc)
        g = self._match_goto(_strip_tail(norm(text)))
        if g is None:
            return None
        # CHONG VA CHAM DAU: bo dau thi 'bạn'==bàn, 'của'==cửa, 'tôi'==tới... khien
        # cau CHAT ("bạn có yêu tôi không") bi hieu nham la go_to. Xac nhan: dia diem
        # VA it nhat 1 tu khoi dong phai xuat hien DUNG DAU trong cau goc.
        low = re.sub(r"\s+", " ", (text or "").lower()).strip()
        loc = str(g["args"]["location"]).lower()
        trig_acc = ["tới", "đến", "ra ", "lại", "về", "qua ", "chạy tới", "đi tới"]
        if loc not in low or not any(t.strip() and re.search(r"\b" + re.escape(t.strip()) + r"\b", low)
                                     for t in trig_acc):
            return None
        return {"intent": "go_to", "say": "Dạ tới đó liền!", "actions": [g]}

    def match(self, text):
        clauses = _split_clauses(text)
        if len(clauses) < 2:
            return None                            # khong phai combo -> luong thuong
        all_actions = []
        for c in clauses:
            acts = self._match_clause(c)
            if acts is None:
                return None                        # 1 ve khong giai duoc -> nhuong LLM
            all_actions += acts
        return {"intent": "combo_reflex",
                "say": "Dạ làm liền nè!",
                "actions": all_actions}


if __name__ == "__main__":
    cm = ComboMatcher()
    tests = [
        "qua trái rồi tiến lên 3 mét",
        "đi tới góc phòng rồi đi lùi 2 mét",
        "xoay phải 90 độ xong ra chỗ cửa",
        "chào mọi người sau đó tới cái bàn",
        "nhảy điệu số hai rồi xoay phải 2 giây",   # dance2 -> reflex khong co -> None
        "đi thẳng 2 mét",                          # 1 ve -> None (de luong thuong)
    ]
    for t in tests:
        r = cm.match(t)
        n = len(r["actions"]) if r else None
        print(f"{t!r:48s} -> {('%d actions' % n) if r else 'None (LLM)'}")
