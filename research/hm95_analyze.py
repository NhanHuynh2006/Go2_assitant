"""THAM DO (agent HM95): phan tich TEST_hm95_{go2,champ2} giong research/coord_val_analyze.py (quy tac EXC, McNemar chinh xac,
Holm), Holm trong 3 phep so MOI o; them phep hoan vi dau gop 2 o (tham khao) va do dong thuan tung the gioi voi o helb/base da co.
Dung: venv/bin/python research/hm95_analyze.py [tien_to=results/TEST_]"""
import csv, glob, collections, sys
import numpy as np
from scipy.stats import binomtest
pre = sys.argv[1] if len(sys.argv) > 1 else "results/TEST_"
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
NAMES = {C1: "C1", "mppi~t3~nl:ppl=100;ppl_len=0.5": "B1", "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000": "PGIF*",
         "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05": "DRA*"}
cfgs = list(NAMES); BASES = cfgs[1:]
REG = (sys.argv[2] if len(sys.argv) > 2 else "go2,champ2").split(",")


def load(cell):
    R = collections.defaultdict(dict)
    for f in glob.glob(pre + cell + "/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["config"] in NAMES: R[r["world"]][r["config"]] = r
    S, exc, drop, why = {}, collections.Counter(), 0, collections.defaultdict(collections.Counter)
    for w, v in R.items():
        if all(v.get(k, {}).get("success", "") == "" for k in cfgs):
            drop += 1; continue
        for k in cfgs:
            r = v.get(k)
            bad = r is None or r["success"] == ""
            if bad: exc[NAMES[k]] += 1
            S.setdefault(w, {})[k] = 0 if bad else int(r["success"])
            if not bad and r["success"] == "0":
                why[NAMES[k]][r["col"] or "khong_va(" + r["why"][:10] + ")"] += 1
    return S, exc, drop, why


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def holm(ps):
    o = np.argsort(ps); m = len(ps); out = np.empty(m); prev = 0
    for i, j in enumerate(o):
        prev = max(prev, min(1, ps[j] * (m - i))); out[j] = prev
    return out


D = {}
for g in REG:
    for cm in ("hm95", "helb", "base"):
        D[(g, cm)] = load(f"hm95_{g}" if cm == "hm95" else f"{g}_{cm}")
for g in REG:
    S, exc, drop, why = D[(g, "hm95")]
    print(f"\n=== {g} / hm95 (THAM DO) : n the gioi = {len(S)}, bo (EXC o moi cau hinh) = {drop}, EXC le = {dict(exc)}")
    n = len(S)
    for k in cfgs:
        s = sum(S[w][k] for w in S)
        print("  %-6s %4d/%d = %5.1f %%  Wilson95 [%.1f; %.1f]   that bai: %s" % (NAMES[k], s, n, 100 * s / n, *wilson(s, n), dict(why[NAMES[k]])))
    ws = sorted(S, key=int); rows = []
    for k in BASES:
        a = np.array([S[w][C1] for w in ws]); b = np.array([S[w][k] for w in ws])
        up, dn = int(((a == 1) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
        rows.append((NAMES[k], (a.mean() - b.mean()) * 100, up, dn, binomtest(up, up + dn).pvalue if up + dn else 1.))
    hh = holm(np.array([r[4] for r in rows]))
    for r, h in zip(rows, hh):
        print("  C1 vs %-6s %+5.1f diem  +%d/-%d  McNemar p=%.3g  Holm(3)=%.3g" % (*r, h))
# gop 2 o hm95: hoan vi dau theo the gioi (nhu ho chinh, nhung CHI tham khao)
common = sorted(set.intersection(*[set(D[(g, "hm95")][0]) for g in REG]), key=int)
rng = np.random.default_rng(20261125); res = []
for k in BASES:
    d = np.array([np.mean([D[(g, "hm95")][0][w][C1] - D[(g, "hm95")][0][w][k] for g in REG]) for w in common])
    sg = np.concatenate([rng.choice([-1, 1], (20000, len(d))) @ d for _ in range(10)])
    p = (np.sum(np.abs(sg) >= abs(d.sum())) + 1) / (len(sg) + 1)
    bs = [d[rng.integers(0, len(d), len(d))].mean() * 100 for _ in range(10000)]
    res.append((NAMES[k], d.mean() * 100, *np.percentile(bs, [2.5, 97.5]), p))
hh = holm(np.array([r[4] for r in res]))
print(f"\n=== gop {'+'.join(REG)} hm95 (THAM DO, hoan vi dau 200k), n = {len(common)}")
for r, h in zip(res, hh):
    print("  C1 - %-6s %+5.2f diem KTC95 [%+.2f; %+.2f] p=%.2g Holm(3)=%.2g" % (*r, h))
# dong thuan tung the gioi voi helb / base (cung the gioi, cung cau hinh)
print("\n=== dong thuan tung the gioi (success) hm95 vs o da co")
for g in REG:
    H = D[(g, "hm95")][0]
    for cm in ("helb", "base"):
        O = D[(g, cm)][0]; ws = [w for w in H if w in O]
        parts = []
        for k in cfgs:
            a = np.array([H[w][k] for w in ws]); b = np.array([O[w][k] for w in ws])
            po = (a == b).mean(); pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()); kap = (po - pe) / (1 - pe)
            parts.append("%s %.1f%% k=%.2f (%s %.1f%%)" % (NAMES[k], 100 * po, kap, cm, 100 * b.mean()))
        da = np.array([H[w][C1] - H[w][BASES[0]] for w in ws]); db = np.array([O[w][C1] - O[w][BASES[0]] for w in ws])
        print(f"  {g} vs {cm} (n={len(ws)}): " + "; ".join(parts))
        for k in BASES:
            da = np.array([H[w][C1] - H[w][k] for w in ws]); db = np.array([O[w][C1] - O[w][k] for w in ws])
            print("     chenh C1-%-6s: hm95 %+5.1f  %s %+5.1f  tuong quan tung the gioi r=%.2f" % (NAMES[k], 100 * da.mean(), cm, 100 * db.mean(), np.corrcoef(da, db)[0, 1]))
    for cm in ("helb", "base"):                       # nhac lai McNemar cua o cu tren CUNG tap the gioi (de doi chieu dau)
        O = D[(g, cm)][0]; ws = sorted([w for w in H if w in O], key=int); rows = []
        for k in BASES:
            a = np.array([O[w][C1] for w in ws]); b = np.array([O[w][k] for w in ws])
            up, dn = int(((a == 1) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
            rows.append((NAMES[k], (a.mean() - b.mean()) * 100, up, dn, binomtest(up, up + dn).pvalue if up + dn else 1.))
        hh = holm(np.array([r[4] for r in rows]))
        print(f"  [doi chieu] {g}/{cm}: " + "; ".join("C1-%s %+.1f (+%d/-%d) p=%.3g Holm=%.3g" % (*r, h) for r, h in zip(rows, hh)))
