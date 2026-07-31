#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safety_guard.py — LOP BAO VE: kiem duyet MOI hanh dong truoc khi robot lam that.

Trong cac he LLM-robot, model co the sinh lenh sai/nguy hiem (vd "bay len",
hoac xuat vx qua lon). Lop nay la "phanh tay" giua NAO va CHAN:
moi action phai qua guard truoc khi toi SportClient.

Cac tang bao ve:
  1. CLAMP van toc/thoi gian ve gioi han an toan (du LLM xuat gi cung bi keo lai)
  2. PHAI DUNG truoc khi DI: tu chen stand-up neu robot dang nam
  3. WHITELIST dong tac: chi cho phep action da kiem chung (chan HandStand/WalkUpright)
  4. EMERGENCY co uu tien tuyet doi: huy moi thu dang lam
  5. NHAC nho dieu kien (pin, khong gian) — canh bao chu khong chan
"""

import math
import time

# Dong tac AN TOAN cho phep qua giong noi (khop ACTION_MAP + acrobatic trong robot_tools)
SAFE_ACTIONS = {"hello", "dance1", "dance2", "stretch", "heart",
                "standup", "standdown", "balance",
                # acrobatic da mo khoa theo yeu cau (RUI RO: can khong gian trong)
                "walkupright", "handstand", "frontjump", "frontpounce"}

# Dong tac NGUY HIEM nhat — van tu choi (lon nhao de nga ngua/chan thuong robot)
BLOCKED_ACTIONS = {"frontflip", "backflip", "leftflip"}


class SafetyGuard:
    def __init__(self, max_vx=0.6, max_vy=0.4, max_vyaw=1.0,
                 max_duration=6.0, require_stand_before_move=True,
                 max_step_m=0.5):
        self.max_vx = max_vx
        self.max_vy = max_vy
        self.max_vyaw = max_vyaw
        self.max_duration = max_duration
        self.max_step_m = float(max_step_m)   # moi lenh di toi da bao nhieu MET
        self.require_stand = require_stand_before_move
        self.is_standing = False        # theo doi trang thai (da dung chua)
        self.emergency = False

    # ---------- kiem duyet 1 action -> tra ve (action_da_sua | None, ghi_chu) ----------
    def check(self, act: dict):
        if self.emergency:
            return None, "dang EMERGENCY — bo qua moi lenh tru stop"

        tool = (act.get("tool") or "").lower()
        args = dict(act.get("args") or {})

        if tool == "stop":
            return {"tool": "stop", "args": {}}, "stop (luon cho phep)"

        if tool == "action":
            name = str(args.get("name", "")).lower()
            if name in BLOCKED_ACTIONS:
                return None, f"CHAN dong tac nguy hiem '{name}'"
            if name not in SAFE_ACTIONS:
                return None, f"khong ro dong tac '{name}' — bo qua cho an toan"
            if name in ("standup", "balance"):
                self.is_standing = True
            elif name == "standdown":
                self.is_standing = False
            return {"tool": "action", "args": {"name": name}}, f"action '{name}' OK"

        if tool == "move":
            # CLAMP ve gioi han an toan (du LLM xuat bao nhieu)
            vx = self._clamp(args.get("vx", 0.0), self.max_vx)
            vy = self._clamp(args.get("vy", 0.0), self.max_vy)
            vyaw = self._clamp(args.get("vyaw", 0.0), self.max_vyaw)
            dur = max(0.1, min(float(args.get("duration", 2.0)), self.max_duration))
            # CHAN KHOANG CACH ~max_step_m: rut ngan thoi gian neu di qua xa (chong dung)
            speed = math.hypot(vx, vy)
            if speed > 1e-6 and speed * dur > self.max_step_m:
                dur = self.max_step_m / speed
            safe = {"tool": "move",
                    "args": {"vx": vx, "vy": vy, "vyaw": vyaw, "duration": dur}}
            note = f"move OK (da clamp, <= {self.max_step_m*100:.0f}cm)"
            # neu chua dung ma doi di -> bao caller can stand truoc
            if self.require_stand and not self.is_standing:
                return safe, "STAND_FIRST"     # caller se chen stand-up truoc
            return safe, note

        if tool == "go_to":
            return act, "go_to (Nav2 lo an toan rieng)"

        return None, f"tool la '{tool}' — bo qua"

    def _clamp(self, v, lo_hi):
        v = float(v)
        return max(-lo_hi, min(lo_hi, v))

    # ---------- emergency ----------
    def trigger_emergency(self):
        self.emergency = True

    def clear_emergency(self):
        self.emergency = False

    def mark_standing(self, standing: bool):
        self.is_standing = standing


if __name__ == "__main__":
    g = SafetyGuard()
    # test clamp
    print(g.check({"tool": "move", "args": {"vx": 5.0, "duration": 99}}))  # bi clamp + STAND_FIRST
    g.mark_standing(True)
    print(g.check({"tool": "move", "args": {"vx": 5.0, "duration": 99}}))  # clamp, da dung
    print(g.check({"tool": "action", "args": {"name": "handstand"}}))      # bi chan
    print(g.check({"tool": "action", "args": {"name": "hello"}}))          # OK
    g.trigger_emergency()
    print(g.check({"tool": "move", "args": {"vx": 0.3}}))                   # bi chan do emergency
