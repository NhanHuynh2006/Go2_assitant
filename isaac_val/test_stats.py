"""Phan tich nhanh Isaac TEST dung PREREG_TEST §3: thanh cong (nga = hong), Wilson, McNemar chinh xac, Holm 3 (C1 vs B1, PGIF*, DRA*),
ty le nga theo cau hinh, tach theo N (4/8), dong thu hang voi fastsim TEST tren cung the gioi.  python3 isaac_val/test_stats.py"""
import csv, glob, json, math, os
from collections import Counter, defaultdict
from math import comb
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
O = R + "/results/ISAAC_TEST"
C = {"C1": "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5", "B1": "mppi~t3~nl:ppl=100;ppl_len=0.5",
     "PGIF*": "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000", "DRA*": "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"}
inv = {v: k for k, v in C.items()}


def rd(f, N):
    out = []
    if os.path.exists(f):
        for r in csv.DictReader(open(f)):
            if r.get("world", "").isdigit() and r.get("config") in inv:
                r["N"] = N; out.append(r)
    return out


rows = rd(O + "/res_n4.csv", 4) if os.path.exists(O + "/res_n4.csv") else rd(O + "/res.csv", 4)
rows += rd(O + "/res_n8.csv", 8)
by = defaultdict(dict)
for r in rows:
    by[int(r["world"])][inv[r["config"]]] = r
full = {w: d for w, d in by.items() if len(d) == 4}
infra = [w for w, d in full.items() if all(x["why"].startswith("EXC") for x in d.values())]
W = sorted(w for w in full if w not in infra)
print(f"luot {len(rows)}; the gioi du 4 cau hinh {len(full)}; bo vi EXC o moi cau hinh {len(infra)}; dung {len(W)}")
print(f"  N=4: {sum(1 for w in W if full[w]['C1']['N'] == 4)} the gioi, N=8: {sum(1 for w in W if full[w]['C1']['N'] == 8)}")
ok = lambda r: r["success"] == "1"


def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d
    return 100 * (c - h), 100 * (c + h)


def mcn(b, l):
    return min(1, 2 * sum(comb(b + l, i) for i in range(min(b, l) + 1)) / 2 ** (b + l)) if b + l else 1.0


def mode(r):
    if ok(r): return "ok"
    if r["why"] == "nga": return "nga"
    if r["why"].startswith("EXC"): return "exc"
    if r["col"] == "static": return "va_tinh"
    if r["col"]: return "va_nguoi"
    return "het_gio" if "gio" in r["why"] else "ket"


S = {}
print("\n| cau hinh | thanh cong (Wilson 95 %) | nga | va nguoi | va tinh | ket/het gio | EXC |\n|---|---|---|---|---|---|---|")
for k in C:
    g = [full[w][k] for w in W]; n = len(g); s = sum(map(ok, g)); m = Counter(map(mode, g)); S[k] = s / n
    lo, hi = wil(s, n)
    print(f"| {k} | {s}/{n} = {100*s/n:.1f} % [{lo:.1f}, {hi:.1f}] | {m['nga']} ({100*m['nga']/n:.1f} %) | {m['va_nguoi']} | {m['va_tinh']} | {m['ket']+m['het_gio']} | {m['exc']} |")
print("\nPhep chinh (McNemar chinh xac 2 phia, Holm trong 3):")
ps = []
for k in ("B1", "PGIF*", "DRA*"):
    b = sum(ok(full[w]["C1"]) and not ok(full[w][k]) for w in W); l = sum(not ok(full[w]["C1"]) and ok(full[w][k]) for w in W)
    ps.append((mcn(b, l), k, b, l))
srt = sorted(ps)
holm = {}
run = 0.0
for i, (p, k, b, l) in enumerate(srt):
    run = max(run, min(1.0, p * (3 - i))); holm[k] = run
for p, k, b, l in ps:
    print(f"  C1 vs {k}: C1 thang {b}, thua {l}, chenh {100*(b-l)/len(W):+.1f} diem; p = {p:.3g}; Holm = {holm[k]:.3g}")
print("\nTach theo N (kiem tinh hop ly):")
for N in (4, 8):
    ws = [w for w in W if full[w]["C1"]["N"] == N]
    if ws:
        print(f"  N={N} (n={len(ws)}): " + ", ".join(f"{k} {100*sum(ok(full[w][k]) for w in ws)/len(ws):.1f} % (nga {sum(full[w][k]['why']=='nga' for w in ws)})" for k in C))
# fastsim cung the gioi
print("\nDong thu hang voi fastsim TEST (cung the gioi):")
def kendall(a, b):
    s = t = 0; ks = list(a)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            x, y = a[ks[i]] - a[ks[j]], b[ks[i]] - b[ks[j]]
            if x == 0 or y == 0: continue
            t += 1; s += 1 if x * y > 0 else -1
    return s / t if t else float("nan")
for d in sorted(glob.glob(R + "/results/TEST_*_*")):
    if not os.path.isdir(d) or "STATIC" in d: continue
    F = {}
    for f in glob.glob(d + "/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["config"] in inv and r["world"].isdigit(): F[(inv[r["config"]], int(r["world"]))] = r
    ws = [w for w in W if all((k, w) in F for k in C)]
    if not ws: continue
    fs = {k: sum(F[(k, w)]["success"] == "1" for w in ws) / len(ws) for k in C}
    isa = {k: sum(ok(full[w][k]) for w in ws) / len(ws) for k in C}
    agree = sum((F[("C1", w)]["success"] == "1") == ok(full[w]["C1"]) for w in ws) / len(ws)
    print(f"  {os.path.basename(d)} (n={len(ws)}): fastsim " + ", ".join(f"{k} {100*fs[k]:.1f}" for k in C) +
          f" | Kendall tau {kendall(isa, fs):+.2f} | C1-B1 fastsim {100*(fs['C1']-fs['B1']):+.1f} vs Isaac {100*(isa['C1']-isa['B1']):+.1f} | C1 tung luot giong {100*agree:.0f} %")
json.dump(dict(S=S, n=len(W), holm=holm), open(O + "/stats.json", "w"))
