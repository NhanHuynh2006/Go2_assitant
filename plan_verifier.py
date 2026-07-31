#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan_verifier.py — BO KIEM CHUNG SYMBOLIC: chan LLM "bia" hanh dong.

Van de thuc te da quan sat: baseline hay bia action khong ai nhac toi
(vd cau "xoay phai 90 do roi tha tim" -> model phun ra Stretch!).

Nguyen tac (giong cac he neuro-symbolic): hanh dong DAC THU (action/go_to)
chi duoc giu lai neu trong cau noi CO TU KICH HOAT tuong ung.
  - action "stretch" ma cau khong he co "vuon vai/duoi nguoi" -> BO
  - go_to "bep" ma cau khong nhac "bep" -> BO
  - move/stop: cho qua (da co grammar + SafetyGuard clamp lo)

Verifier CHI BO, KHONG THEM -> khong bao gio tu y tao hanh dong moi.
Day la lop "dung nhat" chay kem lop "nhanh nhat", chi phi ~0ms.
"""

from reflex_matcher import norm

# Tu kich hoat (DA BO DAU) cho tung action — khop ACTION_MAP cua robot_tools
ACTION_TRIGGERS = {
    "hello":     ["chao", "bat tay", "vay tay", "hello", "hi "],
    "dance1":    ["nhay", "mua", "dance", "quay clip"],
    "dance2":    ["nhay", "mua", "dance"],
    "stretch":   ["vuon vai", "duoi nguoi", "gian co", "stretch"],
    "heart":     ["tim", "thuong", "yeu"],
    "standup":   ["dung len", "dung day", "day di", "dung thang"],
    "standdown": ["nam", "ngoi", "nghi"],
    "balance":   ["can bang", "dung yen", "giu thang bang"],
}


def verify_plan(user_text: str, actions: list):
    """Loc danh sach action theo cau noi goc.
    Tra ve (actions_sach, ghi_chu_da_bo: list[str])."""
    t = norm(user_text)
    kept, dropped = [], []
    for a in actions or []:
        tool = (a.get("tool") or "").lower()
        args = a.get("args") or {}

        if tool == "action":
            name = str(args.get("name", "")).lower()
            trigs = ACTION_TRIGGERS.get(name)
            if trigs is None:
                dropped.append(f"action '{name}' (khong co trong danh muc)")
                continue
            if not any(k in t for k in trigs):
                dropped.append(f"action '{name}' (cau noi khong nhac toi -> nghi LLM bia)")
                continue
            kept.append(a)

        elif tool == "go_to":
            loc = norm(str(args.get("location", "")))
            if loc and loc in t:
                kept.append(a)
            else:
                dropped.append(f"go_to '{args.get('location')}' (dia diem khong co trong cau)")

        else:
            # move / stop: grammar + SafetyGuard da lo phan nay
            kept.append(a)
    return kept, dropped


if __name__ == "__main__":
    # Tai hien dung cac ca LLM bia da quan sat trong test cua ban:
    cases = [
        ("\u0111i t\u1edbi tr\u01b0\u1edbc 2 m\u00e9t r\u1ed3i xoay ph\u1ea3i 90 \u0111\u1ed9 r\u1ed3i th\u1ea3 tim",
         [{"tool": "move", "args": {"vx": 0.35, "duration": 2.9}},
          {"tool": "action", "args": {"name": "stretch"}},      # <- LLM bia
          {"tool": "action", "args": {"name": "heart"}}]),
        ("ch\u00e0o xong nh\u1ea3y m\u1ed9t b\u00e0i",
         [{"tool": "action", "args": {"name": "hello"}},
          {"tool": "action", "args": {"name": "dance1"}}]),     # ca dung -> giu het
        ("ra ch\u1ed7 c\u00e1i b\u00e0n",
         [{"tool": "go_to", "args": {"location": "b\u1ebfp"}}]),  # <- bia dia diem
    ]
    for text, acts in cases:
        kept, dropped = verify_plan(text, acts)
        print(f"\n\U0001F5E3\ufe0f {text}")
        print(f"   giu  : {[a['args'] for a in kept]}")
        print(f"   bo   : {dropped}")
