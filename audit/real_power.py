#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""real_power.py (REALPREP, 25/11) - luc thong ke TRUNG THUC cho thi nghiem cho that (audit/REAL_PREREG.md).

Phep thu: McNemar CHINH XAC 2 phia (= kiem dau nhi thuc tren cac cap bat dong), alpha 0.05.
Ti le bat dong lay tu ket qua DA CONG BO (khong chon): fastsim TEST go2_base +112/-51 tren 1000, go2_helb +61/-43,
Isaac v3 tham do 100 the gioi DEV +20/-6, Isaac pilot nlcs (~cs) +9/-4 (REPORT_ISAAC 11.2).
Cac bai thu that de hon the gioi fastsim (1-2 nguoi, duong 6 m) -> ti le bat dong co the NHO hon nhieu: kich ban "de".
  python3 audit/real_power.py
"""
import math

from scipy.stats import binom


def mcnemar_exact_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * binom.cdf(min(b, c), n, 0.5))


def power(n_pairs, p10, p01, alpha=0.05):
    """P(bac bo H0) khi moi cap: C1 thang/B1 thua p10, nguoc lai p01 (da thuc 3 loai)."""
    pd = p10 + p01
    if pd <= 0:
        return 0.0
    q = p10 / pd
    tot = 0.0
    # vung bac bo cho moi so cap bat dong m
    for m in range(0, n_pairs + 1):
        pm = binom.pmf(m, n_pairs, pd)
        if pm < 1e-12:
            continue
        rej = 0.0
        for b in range(0, m + 1):
            if mcnemar_exact_p(b, m - b) <= alpha and b > m - b:      # chi dem bac bo theo huong C1 tot hon
                rej += binom.pmf(b, m, q)
        tot += pm * rej
    return tot


def min_disc(n_disc, alpha=0.05):
    """So cap C1-thang toi thieu (trong n_disc cap bat dong) de p <= alpha."""
    for b in range(n_disc + 1):
        if mcnemar_exact_p(b, n_disc - b) <= alpha and b > n_disc - b:
            return b
    return None


PROFILES = [("fastsim TEST go2_base", 112 / 1000, 51 / 1000),
            ("fastsim TEST go2_helb", 61 / 1000, 43 / 1000),
            ("Isaac v3 tham do (DEV)", 20 / 100, 6 / 100),
            ("Isaac pilot ~cs (DEV)", 9 / 100, 4 / 100),
            ("de: 1/2 bat dong cua go2_base", 56 / 1000, 25.5 / 1000)]

if __name__ == "__main__":
    Ns = [20, 40, 60, 80, 100, 150, 200]
    print("Luc (power) McNemar chinh xac 2 phia, alpha 0.05, theo so CAP:")
    print("%-34s" % "ho so bat dong (p10/p01)" + "".join("%7d" % n for n in Ns))
    for name, p10, p01 in PROFILES:
        print("%-34s" % ("%s (%.3f/%.3f)" % (name, p10, p01)) + "".join("%7.2f" % power(n, p10, p01) for n in Ns))
    print("\nSo cap C1-thang toi thieu trong k cap bat dong de p <= 0.05:")
    print("  " + ", ".join("k=%d: %s" % (k, min_disc(k)) for k in (5, 6, 8, 10, 12, 15, 20, 25, 30)))
    print("\nVi du 60 cap (S2-S4), ho so go2_base: so cap bat dong ky vong = %.1f" % (60 * (112 + 51) / 1000))
