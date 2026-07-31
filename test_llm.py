#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_llm.py — kiem tra Tang 2 LLM (can llama-server dang chay). Chay: python3 test_llm.py"""

import json
from llm_planner import LLMPlanner

p = LLMPlanner()
if not p.health():
    raise SystemExit("\u274c llama-server chua chay. Mo terminal khac chay server "
                     "(HUONG_DAN.md phan A1) roi thu lai.")

TESTS = [
    "\u0111i t\u1edbi tr\u01b0\u1edbc 2 m\u00e9t r\u1ed3i xoay tr\u00e1i 90 \u0111\u1ed9 r\u1ed3i ch\u00e0o m\u1ecdi ng\u01b0\u1eddi",
    "ra ch\u1ed7 c\u00e1i c\u1eeda gi\u00fap m\u00ecnh nh\u00e9",
    "b\u1ea1n t\u00ean g\u00ec v\u1eady?",
    "nh\u1ea3y m\u1ed9t b\u00e0i xong n\u1eb1m xu\u1ed1ng ngh\u1ec9 \u0111i",
]

for q in TESTS:
    r = p.plan(q)
    print("\n\U0001F5E3\ufe0f ", q)
    print(f"\u23F1\ufe0f  {r.get('_ms')} ms | {r.get('_tps')} tok/s")
    print(json.dumps({k: v for k, v in r.items() if not k.startswith('_')},
                     ensure_ascii=False, indent=2))
print("\n\u2705 Neu JSON tren hop le + actions dung thu tu -> Tang 2 OK!")
