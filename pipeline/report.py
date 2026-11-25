#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline/report.py <final_dir> <cau_hinh_de_xuat> -> results/FINAL_REPORT.md
Bang tong hop + KTC 95 % (Wilson) + so sanh GHEP CAP voi thuat toan de xuat:
McNemar chinh xac cho thanh cong, Wilcoxon cho thoi gian (cac cap ca hai cung thanh cong)."""
import csv
import math
import os
import sys
from collections import defaultdict

from scipy.stats import wilcoxon

d, ours = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(os.path.join(d, "trials.csv"))))
f = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def mcnemar(b, c):
    n = b + c
    if not n:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


by = defaultdict(list)
for r in rows:
    by[r["config"]].append(r)
cfgs = sorted(by, key=lambda c: (c != ours, c))
L = [f"# KET QUA CHINH THUC — {os.path.basename(d)}", "",
     f"{len(rows)} luot; thuat toan de xuat: **{ours}**", "",
     "| cau hinh | n | thanh cong [KTC 95 %] | va cham | va do robot | thoi gian TB (s) | khung | lac huong | SPL |",
     "|---|---|---|---|---|---|---|---|---|"]
for c in cfgs:
    g = by[c]
    n = len(g)
    k = sum(int(r["success"]) for r in g)
    lo, hi = wilson(k, n)
    col = sum(int(r["collision"]) for r in g)
    # va do ROBOT = cham vat tinh (luon la loi robot) HOAC cham nguoi co at_fault = 1. Ban cu chi dem
    # at_fault -> bo sot va vat tinh (dinh chinh 22/11, RESEARCH_NOTES 7.9)
    af = sum(1 for r in g if (f(r, "min_clear_m") is not None and f(r, "min_clear_m") < 0)
             or (f(r, "min_person_gap_m") is not None and f(r, "min_person_gap_m") < 0
                 and r.get("at_fault") == "1"))
    ts = [f(r, "time_s") for r in g if int(r["success"])]
    st = [f(r, "stops") for r in g if f(r, "stops") is not None]
    osc = [f(r, "osc") for r in g if f(r, "osc") is not None]
    spl = [f(r, "spl") for r in g if f(r, "spl") is not None]
    m = lambda v: sum(v) / len(v) if v else float("nan")
    L.append(f"| {'**' + c + '**' if c == ours else c} | {n} | {k / n * 100:.0f} % [{lo * 100:.0f}–{hi * 100:.0f}] | "
             f"{col / n * 100:.0f} % | {af / n * 100:.0f} % | {m(ts):.1f} | {m(st):.1f} | {m(osc):.1f} | {m(spl):.2f} |")
L += ["", f"## So sanh ghep cap voi {ours} (cung bai, cung lan)", "",
      "| doi chung | ours thang / thua (thanh cong) | McNemar p | thoi gian ours vs doi chung (s) | Wilcoxon p |",
      "|---|---|---|---|---|"]
key = lambda r: (r.get("trial") or "1", r["task"])
O = {key(r): r for r in by[ours]}
for c in cfgs:
    if c == ours:
        continue
    B = {key(r): r for r in by[c]}
    common = set(O) & set(B)
    b = sum(1 for k_ in common if int(O[k_]["success"]) and not int(B[k_]["success"]))
    cc = sum(1 for k_ in common if not int(O[k_]["success"]) and int(B[k_]["success"]))
    both = [k_ for k_ in common if int(O[k_]["success"]) and int(B[k_]["success"])]
    to = [f(O[k_], "time_s") for k_ in both]
    tb = [f(B[k_], "time_s") for k_ in both]
    try:
        pw = wilcoxon(to, tb).pvalue if len(both) >= 6 else float("nan")
    except ValueError:
        pw = float("nan")
    L.append(f"| {c} | {b} / {cc} | {mcnemar(b, cc):.3g} | "
             f"{(sum(to) / len(to)) if to else float('nan'):.1f} vs {(sum(tb) / len(tb)) if tb else float('nan'):.1f} | {pw:.3g} |")
cats = sorted({r["cat"] for r in rows})
L += ["", "## Theo loai bai", "", "| cau hinh | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
for c in cfgs:
    cell = []
    for cat in cats:
        g = [r for r in by[c] if r["cat"] == cat]
        cell.append(f"{sum(int(r['success']) for r in g)}/{len(g)}" if g else "-")
    L.append(f"| {c} | " + " | ".join(cell) + " |")
out = os.path.join(os.path.dirname(os.path.abspath(d)), f"FINAL_REPORT_{os.path.basename(os.path.abspath(d))}.md")
open(out, "w").write("\n".join(L) + "\n")
print("->", out)
