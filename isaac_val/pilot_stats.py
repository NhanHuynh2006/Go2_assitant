"""Bang pilot kiem cheo: Isaac (rough+noise) vs fastsim champ/champ2/go2 tren CUNG 100 the gioi DEV (302-439 co nguoi, trial 0, crowd base).
   venv/bin/python isaac_val/pilot_stats.py"""
import csv, glob, math, os, sys, json
from math import comb
from collections import defaultdict
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = ["mppi", "mppi:ppl=32", "dwa", "mppi~t3~nl:ppl=100;ppl_len=0.5", "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"]
BASE = "mppi~t3~nl:ppl=100;ppl_len=0.5"
SEEDS = None


def load_fs(dirs):
    out = {}
    for d in dirs:
        for f in glob.glob(os.path.join(R, d, "w*.csv")):
            for r in csv.DictReader(open(f)):
                if r["success"] == "" or r.get("trial", "0") != "0":
                    continue
                out[(r["config"], int(r["world"]))] = r
    return out


def wil(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; den = 1 + z * z / n; c = (p + z * z / 2 / n) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / den
    return c - h, c + h


def mcn(b, l):
    return min(1, 2 * sum(comb(b + l, i) for i in range(min(b, l) + 1)) / 2 ** (b + l)) if b + l else 1.0


def kendall(a, b):
    n = len(a); s = 0; t = 0
    for i in range(n):
        for j in range(i + 1, n):
            x, y = a[i] - a[j], b[i] - b[j]
            if x == 0 or y == 0: continue
            t += 1; s += 1 if x * y > 0 else -1
    return s / t if t else float("nan")


iso = {}
for f in glob.glob(os.path.join(R, "isaac_val", "res_pilot*.csv")):
    for r in csv.DictReader(open(f)):
        if r["success"] in ("", "success"): continue
        iso[(r["config"], int(r["world"]))] = r
bodies = {"isaac": iso,
          "go2": load_fs(["results/isaac_fs_go2", "results/algo_Vgo2_base"]),
          "champ2": load_fs(["results/isaac_fs_champ2", "results/algo_Vchamp2_base"]),
          "champ": load_fs(["results/isaac_fs_champ"])}
seeds = sorted({w for (c, w) in iso})
key = lambda key_: key_
print(f"the gioi Isaac: {len(seeds)}; luot Isaac {len(iso)}; loi {sum(1 for r in iso.values() if r['why'].startswith('EXC'))}")
S = {}
print("\n| than | " + " | ".join(CFG) + " |\n|---|" + "---|" * len(CFG))
for b, D in bodies.items():
    cells = []
    for c in CFG:
        g = [D[(c, w)] for w in seeds if (c, w) in D]
        k = sum(r["success"] == "1" for r in g); n = len(g); lo, hi = wil(k, n)
        S[(b, c)] = (k / n if n else float("nan"))
        cells.append(f"{k}/{n} {100*k/max(n,1):.0f}% [{100*lo:.0f}-{100*hi:.0f}]")
    print(f"| {b} | " + " | ".join(cells) + " |")
print("\nGhep cap voi baseline chinh", BASE, "(McNemar 2 phia; Holm trong moi than, 4 so sanh)")
for b, D in bodies.items():
    ps = []
    for c in CFG:
        if c == BASE: continue
        K = [w for w in seeds if (c, w) in D and (BASE, w) in D]
        bb = sum(D[(c, w)]["success"] == "1" and D[(BASE, w)]["success"] != "1" for w in K)
        ll = sum(D[(c, w)]["success"] != "1" and D[(BASE, w)]["success"] == "1" for w in K)
        ps.append((mcn(bb, ll), c, bb, ll, len(K)))
    ps.sort(); m = len(ps)
    for i, (p, c, bb, ll, n) in enumerate(ps):
        print(f"  {b:7s} {c:42s} +{bb}/-{ll} (n={n}) p={p:.3g} Holm={min(1, p*(m-i)):.3g}")
print("\nKendall tau thu hang 5 cau hinh (ti le thanh cong):")
for b in ("go2", "champ2", "champ"):
    print(f"  isaac vs {b}: {kendall([S[('isaac', c)] for c in CFG], [S[(b, c)] for c in CFG]):+.2f}")
print("\nDong y tung luot isaac vs fastsim (cung the gioi, cung cau hinh): ty le ket qua giong nhau")
for b in ("go2", "champ2", "champ"):
    a = [(iso[k]["success"] == "1") == (bodies[b][k]["success"] == "1") for k in iso if k in bodies[b]]
    print(f"  {b}: {sum(a)}/{len(a)} = {100*sum(a)/max(1,len(a)):.0f}%")
print("\nVa bang chan vs khung 2D (Isaac):")
for c in CFG:
    g = [iso[(c, w)] for w in seeds if (c, w) in iso]
    fp = sum(r["col"] not in ("", "fall") for r in g); ft = sum(r["foot"] != "" for r in g)
    only_f = sum(r["foot"] != "" and r["col"] in ("",) for r in g); fall = sum(r["why"] == "nga" for r in g)
    sf = sum(r["succ_foot"] == "1" for r in g)
    print(f"  {c:42s} va khung {fp}, cham chan {ft} (chi chan, khung khong va {only_f}), nga {fall}; thanh cong 2D {sum(r['success']=='1' for r in g)} -> tinh ca chan {sf}")
