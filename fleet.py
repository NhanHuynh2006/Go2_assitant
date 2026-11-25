#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fleet.py — DIEU KHIEN NHIEU ROBOT bang 1 cau noi.

  "con một đi thẳng 1 mét"                    -> chi con 1
  "con hai xoay trái"                         -> chi con 2
  "cả hai chào đi" / "tất cả ngồi xuống"      -> moi con
  "con một ra cửa, còn con hai vào bếp"       -> moi con 1 viec, CHAY SONG SONG
  "đi thẳng" (khong goi ten)                  -> con vua duoc goi gan nhat
                                                 (luc dau: tat ca)
  "dừng lại" (khong goi ten)                  -> dung TAT CA (an toan truoc)

Phan con lai cua cau (sau khi bo ten robot) di qua pipeline cu y nguyen:
Combo -> Reflex -> LLM -> verifier -> SafetyGuard -> AsyncExecutor rieng tung con.
"""

import copy
import re

from reflex_matcher import strip_accents

_NUM = {"1": 1, "mot": 1, "nhat": 1, "dau": 1, "dau tien": 1,
        "2": 2, "hai": 2, "nhi": 2,
        "3": 3, "ba": 3, "4": 4, "bon": 4, "tu": 4}
_NUM_RE = "|".join(sorted(map(re.escape, _NUM), key=len, reverse=True))

# "con 1", "con số hai", "con thứ nhất", "robot 2", "go2 số 1", "chó số hai"
# ("chó" chi khi co "số/thứ": "cho" tran con la "cho/de" — "xoay cho 2 vòng")
_ONE = re.compile(rf"\b(?:(?:con|robot|go\s?2)\s+(?:so\s+|thu\s+)?|cho\s+(?:so|thu)\s+)"
                  rf"({_NUM_RE})\b")
# "cả hai", "cả 2 con", "tất cả", "hai con", "cả đội", "mọi con"
_ALL = re.compile(r"\b(?:ca\s+(?:hai|2|ba|3|bon|4|doi|nhom|bay)(?:\s+con)?"
                  r"|tat\s+ca(?:\s+cac\s+con)?|hai\s+con|moi\s+con)\b")
# tu noi bi bo o ria moi ve: "..., còn con hai ...", "... và con hai ..."
_EDGE = re.compile(r"^(?:[\s,.;:!?]|\b(?:va|con|roi|nhe|nha|thi)\b)+"
                   r"|(?:[\s,.;:!?]|\b(?:va|con|roi|thi)\b)+$")


def _fold(text):
    """Ban 'bo dau + chu thuong' cua text, kem map vi tri -> vi tri goc."""
    out, idx = [], []
    for i, ch in enumerate(text.lower()):
        for c in strip_accents(ch):
            out.append(c)
            idx.append(i)
    idx.append(len(text))
    return "".join(out), idx


class FleetParser:
    def __init__(self, robots, names=None):
        """robots: list namespace theo thu tu (con 1 = robots[0]).
        names: {ns: ["mực", "đen"]} — ten rieng tuy chon cho tung con."""
        self.robots = list(robots)
        self.names = []
        for ns, words in (names or {}).items():
            for w in words:
                f, _ = _fold(w)
                self.names.append((re.compile(rf"\b{re.escape(f.strip())}\b"), ns))

    def _mentions(self, folded):
        found = []
        for m in _ALL.finditer(folded):
            found.append((m.start(), m.end(), list(self.robots)))
        for m in _ONE.finditer(folded):
            k = _NUM[m.group(1)]
            if 1 <= k <= len(self.robots):
                found.append((m.start(), m.end(), [self.robots[k - 1]]))
        for rx, ns in self.names:
            for m in rx.finditer(folded):
                found.append((m.start(), m.end(), [ns]))
        found.sort()
        keep, end = [], -1          # bo cac match chong lan nhau
        for s, e, t in found:
            if s >= end:
                keep.append((s, e, t))
                end = e
        return keep

    def split(self, text):
        """-> [(targets | None, phan_cau_lenh)]; None = khong goi ten ai."""
        if len(self.robots) <= 1:
            return [(None, text)]
        folded, idx = _fold(text)
        ms = self._mentions(folded)
        if not ms:
            return [(None, text)]
        segs = []
        for k, (s, e, targets) in enumerate(ms):
            stop = ms[k + 1][0] if k + 1 < len(ms) else len(folded)
            body = text[idx[e]:idx[stop]]
            if k == 0 and s > 0:                 # "đi thẳng đi con hai" -> lenh dung truoc ten
                body = text[:idx[s]] + " " + body
            body_f, bidx = _fold(body)
            m = _EDGE.search(body_f)
            while m and m.group(0):              # cat tu noi o 2 dau
                body = body[:bidx[m.start()]] + body[bidx[m.end()]:]
                body_f, bidx = _fold(body)
                m = _EDGE.search(body_f)
            segs.append((targets, body.strip()))
        # "con một và con hai chào đi": ve rong -> gop ten vao ve sau
        out, carry = [], []
        for k, (targets, body) in enumerate(segs):
            targets = carry + [t for t in targets if t not in carry]
            if not body and k + 1 < len(segs):
                carry = targets
                continue
            carry = []
            out.append((targets, body))
        return out


_WHERE = re.compile(r"\b(?:dang\s+)?o\s+(?:dau|cho\s+nao)\b")
_SWAP = re.compile(r"\bdoi\s+cho\b")
_FOLLOW = re.compile(r"\b(?:di|chay)\s+theo\b|\btheo\s+sau\b")
_TO = re.compile(r"\b(?:lai|toi|den|ra|ve)\s*(?:cho|gan|canh|ben)?\s*$")


def parse_fleet_intent(parser, text):
    """Lenh GIUA CAC ROBOT (khong qua Reflex/LLM vi chung can vi tri robot khac):
      "con một đang ở đâu"            -> ("where",  [con1], None)
      "cả hai đổi chỗ"                -> ("swap",   [con1, con2], None)
      "con hai đi theo con một"       -> ("follow", [con2], con1)
      "con hai lại chỗ con một"       -> ("goto_robot", [con2], con1)
    actors = None nghia la 'con vua goi'. -> None neu khong phai lenh fleet."""
    folded, _ = _fold(text)
    ms = parser._mentions(folded)
    if _WHERE.search(folded):
        return ("where", ms[0][2] if ms else None, None)
    if len(parser.robots) < 2:
        return None
    if _SWAP.search(folded):
        actors = [t for m in ms for t in m[2]] or list(parser.robots[:2])
        actors = list(dict.fromkeys(actors))
        return ("swap", actors[:2] if len(actors) >= 2 else list(parser.robots[:2]), None)
    f = _FOLLOW.search(folded)
    if f:
        after = [m for m in ms if m[0] >= f.end()]
        before = [m for m in ms if m[1] <= f.start()]
        if after and len(after[0][2]) == 1:
            return ("follow", before[0][2] if before else None, after[0][2][0])
    for k, m in enumerate(ms):
        if k and len(m[2]) == 1 and _TO.search(folded[ms[k - 1][1]:m[0]]):
            return ("goto_robot", ms[k - 1][2], m[2][0])
    if len(ms) == 1 and len(ms[0][2]) == 1 and _TO.search(folded[:ms[0][0]]):
        return ("goto_robot", None, ms[0][2][0])           # "lại chỗ con một"
    return None


def merge_moves(actions):
    """Gop cac 'move' lien tiep CUNG van toc thanh 1 'move_dist' (tong thoi gian).
    Reflex chia "đi thẳng 3 mét" thanh 2.1 + 0.9 m (robot that: <= 6 s moi lenh, theo
    thoi gian). Trong sim di VONG KIN theo met, va de NE VAT can biet DIEM CUOI that:
    doan 2.1 m dung ngay sau lung thung -> robot vong toi cho ket (da gap)."""
    out = []
    for a in actions or []:
        if a.get("tool") == "move" and out and out[-1].get("tool") in ("move", "move_dist"):
            p, q = out[-1]["args"], a.get("args") or {}
            same = all(abs(float(p.get(k, 0.0)) - float(q.get(k, 0.0))) < 1e-6
                       for k in ("vx", "vy", "vyaw"))
            if same:
                out[-1] = {"tool": "move_dist", "args": dict(
                    p, duration=float(p.get("duration", 0.0)) + float(q.get("duration", 0.0)))}
                continue
        out.append(dict(a))
    return out


class FleetExecutor:
    """Gia lap 1 AsyncExecutor nhung phat lenh toi cac robot dang duoc chon."""

    def __init__(self, executors):
        self.ex = dict(executors)           # ns -> AsyncExecutor
        self.targets = list(self.ex)
        self.explicit = False

    def enqueue(self, actions, only=None):
        actions = merge_moves(actions)
        for ns in (only or self.targets):
            self.ex[ns].enqueue(copy.deepcopy(actions))

    def emergency_stop(self):
        # khong goi ten ai -> dung HET (an toan truoc)
        for ns in (self.targets if self.explicit else list(self.ex)):
            self.ex[ns].emergency_stop()

    def stop_all(self):
        for e in self.ex.values():
            e.emergency_stop()

    def is_busy(self):
        return any(e.is_busy() for e in self.ex.values())

    def shutdown(self):
        for e in self.ex.values():
            e.shutdown()


if __name__ == "__main__":
    p = FleetParser(["go2_0", "go2_1"], names={"go2_0": ["Mực"]})
    for t in ["con một đi thẳng 1 mét", "con hai xoay trái 90 độ", "cả hai chào đi",
              "con một ra cửa, còn con hai vào bếp", "đi thẳng 2 mét", "dừng lại",
              "con số 2 nhảy đi", "tất cả ngồi xuống", "Mực lùi lại 1 mét",
              "con 1 đi thẳng 2 mét rồi con 2 đi thẳng 1 mét", "con hai", "xoay 2 vòng",
              "robot thứ nhất và robot thứ hai chào đi"]:
        print(f"{t!r:55} -> {p.split(t)}")
    for t in ["con một đang ở đâu", "cả hai đổi chỗ", "con hai đi theo con một",
              "con hai lại chỗ con một", "lại gần con hai", "mày đang ở đâu", "đổi chỗ đi",
              "con một đi thẳng"]:
        print(f"{t!r:55} -> {parse_fleet_intent(p, t)}")
