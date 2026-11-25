#!/usr/bin/env python3
"""fs_stats.py <thu muc fastsim> [--ref cfg] [--gazebo] : bang tong hop, so ghep cap, doi chieu Gazebo."""
import csv, glob, math, sys
from collections import defaultdict, Counter
from math import comb
d = sys.argv[1]
ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
rows = []
for f in sorted(glob.glob(d + "/w*.csv")):
    rows += list(csv.DictReader(open(f)))
exc = [r for r in rows if r["why"].startswith("EXC")]
rows = [r for r in rows if r["success"] != ""]
by = defaultdict(dict)
for r in rows:
    by[r["config"]][(r["world"], r["trial"])] = r
def wil(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c = (p + z * z / 2 / n) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / den
    return c - h, c + h
def mode(r):
    if r["success"] == "1": return "ok"
    if r["col"] == "static": return "va_tinh"
    if r["col"]: return "ng_robot" if r["fault"] == "1" else "ng_dam"
    return "het_gio" if "gio" in r["why"] else "ket"
S = lambda g: sum(r["success"] == "1" for r in g)
print(f"{len(rows)} luot, loi {len(exc)}")
for c, g in sorted(by.items(), key=lambda kv: -S(kv[1].values()) / len(kv[1])):
    R = list(g.values()); n = len(R); k = S(R); lo, hi = wil(k, n)
    m = Counter(mode(r) for r in R)
    nc = [r for r in R if int(r["npeople"]) == 0]; cr = [r for r in R if int(r["npeople"])]
    t = [float(r["time"]) for r in R if r["success"] == "1"]
    s = f"{c:30s} n={n:4d} {100*k/n:5.1f}% [{100*lo:.0f}-{100*hi:.0f}] tinh {100*S(nc)/max(1,len(nc)):3.0f} dong {100*S(cr)/max(1,len(cr)):3.0f} | va_tinh {100*m['va_tinh']/n:4.1f} ng_robot {100*m['ng_robot']/n:4.1f} ng_dam {100*m['ng_dam']/n:4.1f} ket {100*m['ket']/n:4.1f} gio {100*m['het_gio']/n:4.1f} t={sum(t)/max(1,len(t)):5.1f}"
    if ref and c != ref and ref in by:
        K = set(g) & set(by[ref])
        b = sum(int(g[q]["success"]) > int(by[ref][q]["success"]) for q in K)
        l = sum(int(g[q]["success"]) < int(by[ref][q]["success"]) for q in K)
        p = min(1, 2 * sum(comb(b + l, i) for i in range(min(b, l) + 1)) / 2 ** (b + l)) if b + l else 1
        s += f" | +{b}/-{l} p={p:.2g}"
    print(s)
if "--gazebo" in sys.argv:
    import numpy as np
    gz = defaultdict(list)
    for f in glob.glob("results/final_office_w[01]/trials.csv"):
        for r in csv.DictReader(open(f)): gz[(r["config"], r["task"])].append(int(r["success"]))
    X, Y, Xc, Yc = [], [], [], []
    for c, g in by.items():
        a = [r for r in g.values()]
        sx = [int(r["success"]) for r in a]
        gy = [v for (cc, t), vs in gz.items() if cc == c.replace("~v1","") for v in vs]
        if gy: X.append(np.mean(sx)); Y.append(np.mean(gy)); print(f"  {c:26s} fast {X[-1]*100:4.0f}%  gazebo {Y[-1]*100:4.0f}%")
    tasks = sorted({w for g in by.values() for (w, _) in g})
    for t in tasks:
        A = np.mean([int(r["success"]) for g in by.values() for (w, _), r in g.items() if w == t])
        B = np.mean([v for (c, tt), vs in gz.items() if tt == t and c + "~v1" in by for v in vs])
        print(f"  {t:26s} fast {A*100:4.0f}%  gazebo {B*100:4.0f}%")
    from scipy.stats import spearmanr, pearsonr
    print("  hang cau hinh: Spearman %.2f (p=%.3g), Pearson %.2f" % (*spearmanr(X, Y), pearsonr(X, Y)[0]))
