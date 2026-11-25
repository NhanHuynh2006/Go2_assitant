"""Khong-kem (non-inferiority) gop theo THE GIOI: python3 research/algo_noninf.py <ref> <cand,...> ten=thu_muc ...
-> chenh lech gop (diem %), KTC 95 % bootstrap 20 000 lan theo the gioi (moi the gioi giu nguyen ca 5 o)."""
import csv, glob, sys, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
ref, cands = sys.argv[1], sys.argv[2].split(",")
cells = dict(a.split("=", 1) for a in sys.argv[3:])
D = {}
for n, d in cells.items():
    for f in glob.glob(f"{H}/../results/{d}/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["success"] != "":
                D.setdefault(r["config"], {})[(n, r["world"])] = int(r["success"])
rng = np.random.default_rng(0)
for c in cands:
    K = sorted(set(D.get(c, {})) & set(D.get(ref, {})))
    W = sorted({w for _, w in K})
    s = {w: [0, 0] for w in W}
    for (n, w) in K:
        s[w][0] += D[c][(n, w)] - D[ref][(n, w)]; s[w][1] += 1
    d = np.array([s[w][0] for w in W], float); m = np.array([s[w][1] for w in W], float)
    est = 100 * d.sum() / m.sum()
    B = rng.integers(0, len(W), size=(20000, len(W)))
    bs = 100 * d[B].sum(1) / m[B].sum(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"{c} - {ref}: {est:+.2f} diem [{lo:+.2f}; {hi:+.2f}]  (the gioi {len(W)}, cap {int(m.sum())})")
