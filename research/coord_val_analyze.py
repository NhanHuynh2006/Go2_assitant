"""Phan tich VAL theo dang ky truoc (research/FROZEN.md)."""
import csv, glob, collections, sys
import numpy as np
from scipy.stats import binomtest
pre = sys.argv[1] if len(sys.argv) > 1 else "results/VAL_"
cells = ["champ_base", "champ2_base", "go2_base", "champ2_helb", "go2_helb"]
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
NAMES = {"mppi~t3~nl:ppl=100;ppl_len=0.5": "B1", "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000": "PGIF*",
         "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05": "DRA*", "mppi:ppl=32": "B0",
         "dwa~t3~nl:ppl=100;ppl_len=0.3": "dwa", "log_mppi~t3~nl:ppl=100;ppl_len=0.5": "log_mppi", C1: "C1"}
D, exc = {}, collections.Counter()
for c in cells:
    R = collections.defaultdict(dict)
    for f in glob.glob(pre + c + "/w*.csv"):
        for r in csv.DictReader(open(f)):
            R[r["world"]][r["config"]] = r
    D[c] = R
cfgs = list(NAMES)
# quy tac EXC: EXC o moi cau hinh cua 1 the gioi -> bo the gioi (trong o do); EXC o 1 cau hinh -> that bai
S = {}
for c, R in D.items():
    for w, v in R.items():
        if all(v.get(k, {}).get("success", "") == "" for k in cfgs):
            exc["drop " + c] += 1; continue
        for k in cfgs:
            r = v.get(k)
            s = 0 if (r is None or r["success"] == "") else int(r["success"])
            if r is None or r["success"] == "": exc[NAMES[k]] += 1
            S.setdefault((c, w), {})[k] = s
print("EXC:", dict(exc))
print("%-9s" % "", *["%12s" % c for c in cells], "     gop")
for k in cfgs:
    row = [np.mean([S[(c, w)][k] for (cc, w) in S if cc == c]) * 100 for c in cells]
    n = len([1 for (cc, w) in S if cc == cells[0]])
    print("%-9s" % NAMES[k], *["%12.1f" % x for x in row], "  %6.1f" % np.mean([S[key][k] for key in S]) * 1 if False else "  %6.1f" % (np.mean([S[key][k] for key in S]) * 100))
print("n the gioi/o:", {c: sum(1 for (cc, w) in S if cc == c) for c in cells})
worlds = sorted({w for (c, w) in S if all((cc, w) in S for cc in cells)}, key=int)
rng = np.random.default_rng(20261124)
res = []
for k in cfgs[:3]:
    if k == C1: continue
for k in [x for x in cfgs if NAMES[x] in ("B1", "PGIF*", "DRA*")]:
    d = np.array([np.mean([S[(c, w)][C1] - S[(c, w)][k] for c in cells]) for w in worlds])
    obs = d.sum()
    null = np.empty(200000)
    for i in range(0, 200000, 20000):
        sg = rng.choice([-1, 1], (20000, len(d))); null[i:i + 20000] = sg @ d
    p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (len(null) + 1)
    bs = [d[rng.integers(0, len(d), len(d))].mean() * 100 for _ in range(10000)]
    res.append([NAMES[k], d.mean() * 100, *np.percentile(bs, [2.5, 97.5]), p])
res.sort(key=lambda r: r[4]); m = len(res); prev = 0
print("\nHO CHINH (Holm 3), n the gioi =", len(worlds))
for i, r in enumerate(res):
    h = max(prev, min(1, r[4] * (m - i))); prev = h
    print("C1 - %-6s %+5.2f diem  KTC95 [%+.2f; %+.2f]  p=%.2g  Holm=%.2g" % (*r, h))
print("\nPHU (tung o, McNemar chinh xac; Holm trong 15):")
rows = []
for k in [x for x in cfgs if NAMES[x] in ("B1", "PGIF*", "DRA*")]:
    for c in cells:
        a = np.array([S[(c, w)][C1] for w in worlds]); b = np.array([S[(c, w)][k] for w in worlds])
        up, dn = int(((a == 1) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
        rows.append((NAMES[k], c, up, dn, binomtest(up, up + dn).pvalue if up + dn else 1))
rows.sort(key=lambda r: r[4]); prev = 0
for i, r in enumerate(rows):
    h = max(prev, min(1, r[4] * (15 - i))); prev = h
    print("  C1 vs %-6s %-12s +%d/-%d p=%.3g Holm=%.3g" % (*r, h))
for k in [x for x in cfgs if NAMES[x] in ("B0", "dwa", "log_mppi")]:
    d = np.array([np.mean([S[(c, w)][C1] - S[(c, w)][k] for c in cells]) for w in worlds])
    print("  C1 - %-8s %+5.2f diem (khong kiem dinh)" % (NAMES[k], d.mean() * 100))
