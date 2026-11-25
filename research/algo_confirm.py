"""python3 research/algo_confirm.py <ref1,ref2,..> <cand1,cand2,..> ten=thu_muc ... : Wilson, McNemar ghep cap tung o, gop (hoan vi theo THE GIOI),
Holm trong ho cac phep so o day + Bonferroni theo TONG so dong LOG."""
import csv, glob, sys, os
import numpy as np
from math import comb, sqrt
H = os.path.dirname(os.path.abspath(__file__))
refs, cands = sys.argv[1].split(","), sys.argv[2].split(",")
cells = dict(a.split("=", 1) for a in sys.argv[3:])
D = {}
for n, d in cells.items():
    for f in glob.glob(f"{H}/../results/{d}/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["success"] != "":
                D.setdefault((n, r["config"]), {})[r["world"]] = r
def wil(k, n, z=1.96):
    p = k / n; q = 1 + z * z / n; c = (p + z * z / 2 / n) / q; h = z * sqrt(p * (1 - p) / n + z * z / 4 / n / n) / q
    return 100 * (c - h), 100 * (c + h)
print("cau hinh | " + " | ".join(cells) + " | gop")
for c in cands + refs:
    out = []; K = N = 0
    for n in cells:
        g = D.get((n, c))
        if not g: out.append("-"); continue
        k = sum(int(r["success"]) for r in g.values()); m = len(g); K += k; N += m
        col = sum(1 for r in g.values() if r["col"]); t = np.mean([float(r["time"]) for r in g.values() if r["success"] == "1"])
        out.append("%d/%d=%.1f [%.0f-%.0f] va %.1f t%.0f" % (k, m, 100 * k / m, *wil(k, m), 100 * col / m, t))
    print(c, "|", " | ".join(out), "|", "%d/%d=%.1f" % (K, N, 100 * K / max(1, N)))
T = []
rng = np.random.default_rng(0)
for c in cands:
    for b in refs:
        diff = {}
        for n in cells:
            A, B = D.get((n, c)), D.get((n, b))
            if not A or not B: continue
            ks = sorted(set(A) & set(B))
            x = sum(int(A[q]["success"]) > int(B[q]["success"]) for q in ks); y = sum(int(A[q]["success"]) < int(B[q]["success"]) for q in ks)
            p = min(1, 2 * sum(comb(x + y, i) for i in range(min(x, y) + 1)) / 2 ** (x + y)) if x + y else 1
            T.append((p, f"{c} vs {b} [{n}] n={len(ks)} +{x}/-{y} ({100*(x-y)/len(ks):+.1f} diem)"))
            for q in ks: diff[q] = diff.get(q, 0) + int(A[q]["success"]) - int(B[q]["success"])
        v = np.array(list(diff.values()), float)
        s = abs(v.sum()); sg = rng.choice([-1., 1.], size=(100000, len(v)))
        p = (1 + (np.abs(sg @ v) >= s - 1e-9).sum()) / 100001
        nn = sum(len(set(D.get((n, c), {})) & set(D.get((n, b), {}))) for n in cells)
        T.append((p, f"{c} vs {b} [GOP {len(v)} the gioi] {100*v.sum()/nn:+.1f} diem"))
tot = sum(1 for _ in open(H + "/LOG.csv")) - 1
try: tot += sum(1 for _ in open(H + "/../audit/LOG_AUDIT_rows.csv")) - 1
except OSError: pass
T.sort(); m = len(T); mx = 0
print(f"\nHo phep so: {m}; tong dong LOG (ca AUDIT): {tot}")
for i, (p, s) in enumerate(T):
    mx = max(mx, min(1, p * (m - i)))
    print(f"p={p:.2g} Holm={mx:.2g} Bonf({tot})={min(1, p*tot):.2g} {s}")
