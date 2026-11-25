"""Tong hop audit/out/*: lap lai DEV moi (150+), chan doan mo hinh/lambda, do nhay gia dinh."""
import csv, glob, json, os, itertools, math, sys
import numpy as np
from math import comb
H = os.path.dirname(os.path.abspath(__file__))
def load(c):
    by = {}
    for f in glob.glob(f"{H}/out/{c}/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["success"] != "": by.setdefault(r["config"], {})[int(r["world"])] = r
    return by
def wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / 2 / n) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / d; return c - h, c + h
def mcn(a, b): 
    n = a + b; return min(1, 2 * sum(comb(n, i) for i in range(min(a, b) + 1)) / 2 ** n) if n else 1
def line(by, c, ref, K):
    s = [int(by[c][k]["success"]) for k in K]; k = sum(s); lo, hi = wil(k, len(K)); t = ""
    if ref and ref != c:
        b = sum(int(by[c][q]["success"]) > int(by[ref][q]["success"]) for q in K); l = sum(int(by[c][q]["success"]) < int(by[ref][q]["success"]) for q in K); t = f"  vs {ref}: +{b}/-{l} p={mcn(b, l):.2g}"
    return f"{c:20s} {k}/{len(K)} {100*k/len(K):.0f}% [{100*lo:.0f}-{100*hi:.0f}]{t}"
if __name__ == "__main__":
    B = load("base"); K = sorted(set.intersection(*[set(v) for v in B.values()])); print("== base, DEV 150+ co nguoi, n=%d the gioi day du" % len(K))
    for c in sorted(B, key=lambda c: -sum(int(B[c][k]["success"]) for k in K)): print("  ", line(B, c, "mppi", K))
    if "mppi:ppl=32" in B: print("   -- so voi mppi:ppl=32"); [print("  ", line(B, c, "mppi:ppl=32", K)) for c in B if c in ("p2+turn", "mppi:ppl=32#gains", "mppi#gains")]
    if "mppi#gains" in B: print("  ", line(B, "p2+turn", "mppi#gains", K)); print("  ", line(B, "p2+turn", "mppi:ppl=32#gains", K))
    for c in B:
        E = [json.loads(B[c][k]["extra"]) for k in K]
        st = sum(e["steps"] for e in E); last = [sum(e["lam_last"][-10:]) / max(1, len(e["lam_last"][-10:])) for k, e in zip(K, E) if B[c][k]["col"] == "person"]
        print("   %-20s buoc co lambda bi phat-va-cham lan at: %.1f%%; trong 1 s truoc khi cham nguoi: %.0f%%; he so uoc luong TB vx %.2f vy %.2f wz %.2f (that: wz %.2f, vy %.2f), vel_gain %.2f" % (c, 100 * sum(e["lam_sat"] for e in E) / st, 100 * np.mean(last or [0]), *np.mean([e["vgs"] for e in E], 0), np.mean([e["g"][2] for e in E]), np.mean([e["g"][1] for e in E]), np.mean([e["vg"] for e in E])))
    print("== do nhay (cung 40 the gioi DEV dau tu seed 150)")
    for c in ("base", "real", "cmd2", "dis6", "dis0", "seen2", "fast", "dense", "wob0", "real_body", "soft5", "slow"):
        R = load(c); cf = ("mppi", "mppi:ppl=32", "p2+turn")
        if not all(q in R for q in cf): continue
        KK = sorted(set.intersection(*[set(R[q]) for q in cf])); KK = [k for k in KK if k in K[:40]]
        if len(KK) < 15: continue
        M = {q: np.array([int(R[q][k]["success"]) for k in KK]) for q in cf}
        o = []
        for a, b in (("p2+turn", "mppi"), ("p2+turn", "mppi:ppl=32"), ("mppi:ppl=32", "mppi")):
            d = M[a] - M[b]; o.append("%+.0f±%.0f" % (100 * d.mean(), 196 * d.std(ddof=1) / math.sqrt(len(d))))
        rank = sorted(cf, key=lambda q: -M[q].mean())
        print("  %-10s n=%d  mppi %3.0f  ppl32 %3.0f  p2+turn %3.0f | p2t-mppi %s, p2t-ppl32 %s, ppl32-mppi %s | hang: %s" % (c, len(KK), *[100 * M[q].mean() for q in cf], *o, " > ".join(rank)))

    print("== mo hinh nguoi thu hai (n = toi da 100, seed 150+)")
    for c in ("base", "mous", "helb"):
        R = load(c); cf = ("mppi", "mppi:ppl=32", "p2+turn")
        if not all(q in R for q in cf): continue
        KK = [k for k in K if all(k in R[q] for q in cf)]
        if not KK: continue
        print(" ", c, "n=%d" % len(KK)); [print("     ", line(R, q, "mppi", KK)) for q in cf]; print("     ", line(R, "p2+turn", "mppi:ppl=32", KK))
        v = [json.loads(R[q][k]["info"]) for q in cf for k in KK if R[q][k]["col"] == "person"]; print("      cham nguoi: %d, do nguoi mai dien thoai %.0f%%" % (len(v), 100 * np.mean([x.get("distracted", 0) for x in v])))
    R = load("future")
    if R:
        cf = sorted(R); KK = sorted(set.intersection(*[set(v) for v in R.values()])); print("== tran (future), n=%d" % len(KK))
        for q in sorted(cf): print("  ", line(R, q, "mppi:ppl=32#fstat", KK))
        print("   (cung the gioi, cam bien that, base mppi:ppl=32: %d/%d)" % (sum(int(B["mppi:ppl=32"][k]["success"]) for k in KK if k in B["mppi:ppl=32"]), len(KK)))
        for q in sorted(cf):
            e = {}
            for k in KK:
                for kk, vv in json.loads(R[q][k]["extra"]).get("pred", {}).items(): e.setdefault(kk, []).extend(vv)
            print("   sai so du doan (m, nguoi < 2 m) %-20s" % q, {kk: "TB %.2f p90 %.2f (n=%d)" % (np.mean(e[kk]), np.percentile(e[kk], 90), len(e[kk])) for kk in sorted(e)})
            v = [json.loads(R[q][k]["info"]) for k in KK if R[q][k]["col"] == "person"]; print("        cham nguoi %d (mdt %d)" % (len(v), sum(x.get("distracted", 0) for x in v)))
