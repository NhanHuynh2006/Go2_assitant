#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_reflex.py — kiem tra Tang 1 Reflex khong can robot/LLM. Chay: python3 test_reflex.py"""

from reflex_matcher import ReflexMatcher

CASES = [
    ("\u0111i th\u1eb3ng", "move"),
    ("\u0111i th\u1eb3ng 2 m\u00e9t", "move"),
    ("ti\u1ebfn l\u00ean 3 gi\u00e2y", "move"),
    ("l\u00f9i l\u1ea1i", "move"),
    ("sang tr\u00e1i", "move"),
    ("xoay ph\u1ea3i", "move"),
    ("d\u1eebng l\u1ea1i", "stop"),
    ("n\u1eb1m xu\u1ed1ng", "action"),
    ("\u0111\u1ee9ng l\u00ean", "action"),
    ("ch\u00e0o \u0111i", "action"),
    ("nh\u1ea3y coi", "action"),
    ("th\u1ea3 tim", "action"),
]
COMPLEX = [
    "\u0111i t\u1edbi c\u00e1i c\u1eeda r\u1ed3i ch\u00e0o hai c\u00e1i nha",
    "h\u00f4m nay b\u1ea1n th\u1ea5y th\u1ebf n\u00e0o",
]

m = ReflexMatcher()
ok = 0
for text, expect_tool in CASES:
    r = m.match(text)
    got = r["actions"][0]["tool"] if r and r["actions"] else None
    mark = "\u2705" if got == expect_tool else "\u274c"
    ok += got == expect_tool
    print(f"{mark} {text!r:35s} -> {got} {r['actions'][0]['args'] if r and r['actions'] else ''}")
for text in COMPLEX:
    r = m.match(text)
    mark = "\u2705" if r is None else "\u274c"
    ok += r is None
    print(f"{mark} {text!r:35s} -> {'None (nhuong LLM, DUNG)' if r is None else 'BI REFLEX CUOP (SAI)'}")
total = len(CASES) + len(COMPLEX)
print(f"\nKET QUA: {ok}/{total} dat")
