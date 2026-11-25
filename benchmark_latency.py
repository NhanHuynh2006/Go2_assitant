#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_latency.py — DO DO TRE 2 tang (so lieu cho bang ket qua trong bao).
Chay: python3 benchmark_latency.py   (can llama-server dang chay; robot khong can)
Ket qua: in bang + ghi benchmark_results.csv
"""

import csv
import time
import statistics as st

from reflex_matcher import ReflexMatcher
from llm_planner import LLMPlanner

REFLEX_CMDS = ["\u0111i th\u1eb3ng", "l\u00f9i l\u1ea1i", "xoay tr\u00e1i", "d\u1eebng l\u1ea1i",
               "ch\u00e0o \u0111i", "n\u1eb1m xu\u1ed1ng"]
LLM_CMDS = ["\u0111i t\u1edbi tr\u01b0\u1edbc 2 m\u00e9t r\u1ed3i ch\u00e0o m\u1ecdi ng\u01b0\u1eddi",
            "xoay m\u1ed9t v\u00f2ng xong nh\u1ea3y m\u1ed9t b\u00e0i",
            "ra ch\u1ed7 c\u00e1i c\u1eeda r\u1ed3i n\u1eb1m xu\u1ed1ng ngh\u1ec9",
            "b\u1ea1n l\u00e0 ai v\u1eady?"]
REPS = 3

reflex = ReflexMatcher()
llm = LLMPlanner()
rows = [("path", "command", "rep", "ms")]

print("== TANG 1: Reflex ==")
ref_ms = []
for c in REFLEX_CMDS:
    for i in range(REPS):
        t0 = time.time()
        reflex.match(c)
        ms = (time.time() - t0) * 1000
        ref_ms.append(ms)
        rows.append(("reflex", c, i, round(ms, 3)))
print(f"  trung binh: {st.mean(ref_ms):.2f} ms | p95: "
      f"{sorted(ref_ms)[int(0.95*len(ref_ms))-1]:.2f} ms  (n={len(ref_ms)})")

print("\n== TANG 2: LLM (llama.cpp + grammar) ==")
if not llm.health():
    print("  (bo qua — llama-server chua chay)")
else:
    llm_ms, tps = [], []
    # warm-up 1 lan de nap KV cache system prompt
    llm.plan("xin chao")
    for c in LLM_CMDS:
        for i in range(REPS):
            r = llm.plan(c)
            llm_ms.append(r["_ms"])
            tps.append(r["_tps"])
            rows.append(("llm", c, i, r["_ms"]))
        print(f"  {c[:40]:42s} {st.mean(llm_ms[-REPS:]):7.0f} ms")
    print(f"  trung binh: {st.mean(llm_ms):.0f} ms | p95: "
          f"{sorted(llm_ms)[int(0.95*len(llm_ms))-1]:.0f} ms | "
          f"toc do sinh: {st.mean(tps):.1f} tok/s")

with open("benchmark_results.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
print("\n\u2705 Da ghi benchmark_results.csv (dem vao bang so lieu cua bao)")
