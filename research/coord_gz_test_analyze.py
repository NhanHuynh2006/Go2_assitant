"""Gazebo TEST analysis exactly as PREREG_TEST §2/§5 (written 25/11 ~13:25, BEFORE any per-config look at Gazebo TEST data).

Primary (Gazebo family): C1 vs B1, exact two-sided McNemar, alpha 0.05, on every world with BOTH configs present.
Secondary/descriptive: per-config success with Wilson 95 % CI, collisions, at-fault collisions, timeouts,
per-world agreement with fastsim TEST champ_base (and champ2_base) on the same worlds, sha_ok and RTF checks.
DRA* gate: printed only (DRA* runs on the first 340 worlds iff C1 vs B1 passes).
Usage: python3 research/coord_gz_test_analyze.py [results/GZ_TEST]
"""
import csv, glob, json, math, os, sys
from collections import defaultdict
from math import comb

ROOT = sys.argv[1] if len(sys.argv) > 1 else "results/GZ_TEST"
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
B1 = "mppi~t3~nl:ppl=100;ppl_len=0.5"
DRA = "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"
NAME = {C1: "C1", B1: "B1", DRA: "DRA*"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


rows = []
for f in sorted(glob.glob(os.path.join(ROOT, "s*", "g*", "trials.csv"))):
    for r in csv.DictReader(open(f)):
        r["_file"] = f
        rows.append(r)

by = defaultdict(dict)       # config -> world -> row (last one wins; report duplicates)
dups = 0
for r in rows:
    w = int(r["seed"])
    if w in by[r["config"]]:
        dups += 1
    by[r["config"]][w] = r

print(f"files: {len(set(r['_file'] for r in rows))}  rows: {len(rows)}  duplicate (config,world): {dups}")
for cfg, d in by.items():
    print(f"  {NAME.get(cfg, cfg)}: {len(d)} worlds")
bad_sha = [r for r in rows if str(r.get("sha_ok", "1")) not in ("1", "True", "true")]
print(f"rows with sha_ok != 1: {len(bad_sha)}")
rtf = [float(r["rtf_mean"]) for r in rows if r.get("rtf_mean")]
if rtf:
    rtf.sort()
    print(f"rtf_mean: median {rtf[len(rtf)//2]:.3f}  min {rtf[0]:.3f}  n<0.8: {sum(x < 0.8 for x in rtf)}")

pair = sorted(set(by[C1]) & set(by[B1]))
miss = sorted((set(by[C1]) | set(by[B1])) - set(pair))
print(f"\nPRIMARY family: worlds with both C1 and B1: N = {len(pair)} (registered 680); incomplete pairs dropped: {miss}")


def describe(cfg, worlds):
    d = by[cfg]; n = len(worlds)
    s = sum(int(d[w]["success"]) for w in worlds)
    col = sum(1 for w in worlds if str(d[w]["collision"]) == "1")
    af = sum(1 for w in worlds if str(d[w].get("at_fault", "")) == "1")
    lo, hi = wilson(s, n)
    print(f"  {NAME[cfg]:5s} success {s}/{n} = {100*s/n:.1f} % [{100*lo:.1f}, {100*hi:.1f}]  collision {col}  at_fault {af}")
    return s


sc1 = describe(C1, pair); sb1 = describe(B1, pair)
b = sum(1 for w in pair if int(by[C1][w]["success"]) and not int(by[B1][w]["success"]))
c = sum(1 for w in pair if not int(by[C1][w]["success"]) and int(by[B1][w]["success"]))
p = mcnemar(b, c)
print(f"  C1 - B1 = {100*(sc1-sb1)/len(pair):+.1f} points; discordant C1-only {b}, B1-only {c}; exact McNemar p = {p:.3g}"
      f"  -> {'PASS (alpha 0.05)' if p < 0.05 and b > c else 'NOT significant / not in favour of C1'}")
print(f"  DRA* gate: {'OPEN (run DRA* on first 340 worlds, exploratory)' if p < 0.05 and b > c else 'CLOSED'}")

if DRA in by and by[DRA]:
    dw = sorted(set(by[DRA]) & set(pair))
    print(f"\nDRA* (exploratory, gated): N = {len(dw)}")
    describe(C1, dw); describe(DRA, dw)
    b2 = sum(1 for w in dw if int(by[C1][w]["success"]) and not int(by[DRA][w]["success"]))
    c2 = sum(1 for w in dw if not int(by[C1][w]["success"]) and int(by[DRA][w]["success"]))
    print(f"  C1 vs DRA*: {b2}/{c2}, exact McNemar p = {mcnemar(b2, c2):.3g}")

# agreement with fastsim TEST on the same worlds (descriptive)
for cell in ("champ_base", "champ2_base"):
    fs = defaultdict(dict)
    for f in glob.glob(f"results/TEST_{cell}/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["world"].isdigit() and str(r.get("trial", "0")) == "0":
                fs[r["config"]][int(r["world"])] = int(r["success"])
    if C1 not in fs:
        continue
    print(f"\nfastsim TEST {cell} on the same worlds (descriptive):")
    for cfg in (C1, B1):
        ws = [w for w in pair if w in fs[cfg]]
        agree = sum(fs[cfg][w] == int(by[cfg][w]["success"]) for w in ws)
        sf = sum(fs[cfg][w] for w in ws)
        print(f"  {NAME[cfg]}: N {len(ws)}  fastsim {100*sf/max(1,len(ws)):.1f} %  per-world agreement {100*agree/max(1,len(ws)):.1f} %")
    ws = [w for w in pair if w in fs[C1] and w in fs[B1]]
    d_fs = sum(fs[C1][w] - fs[B1][w] for w in ws) / max(1, len(ws))
    d_gz = sum(int(by[C1][w]["success"]) - int(by[B1][w]["success"]) for w in ws) / max(1, len(ws))
    print(f"  C1-B1: fastsim {100*d_fs:+.1f}  Gazebo {100*d_gz:+.1f} points (N {len(ws)})")
