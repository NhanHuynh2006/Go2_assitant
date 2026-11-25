"""Suc manh McNemar ghep cap. Ti le bat dong d lay tu du lieu that. """
import csv, glob, itertools, collections, os, math
import numpy as np
from scipy.stats import binom
from a4_paired import load
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def disc(a, b): return np.mean([x != y for x, y in zip(a, b)])
by = load("dev3"); W = sorted(set.intersection(*[set(v) for v in by.values()]), key=int)
for a, b in (("mppi", "p2+turn"), ("mppi:ppl=32", "p2+turn"), ("mppi:ppl=32", "mppi:ppl=16;ppl_len=0.6"), ("mppi", "mppi:ppl=32"), ("mppi", "dwa")):
    x = [int(by[a][w]["success"]) for w in W]; y = [int(by[b][w]["success"]) for w in W]
    print("fastsim dev3 %-14s vs %-26s bat dong %.2f; hieu %+.3f" % (a, b, disc(x, y), np.mean(y) - np.mean(x)))
G = [r for f in glob.glob(HERE + "/results/final_office_w[01]/trials.csv") for r in csv.DictReader(open(f)) if r["cat"] == "crowd"]
S = collections.defaultdict(dict)
for r in G: S[r["config"]][(r["task"], r["trial"])] = int(r["success"])
C = [c for c in S if c not in ("pp", "rl", "rl@sac", "rl@td3", "rl_ens", "rl_safe")]
dd = [disc([S[a][k] for k in S[a]], [S[b][k] for k in S[a]]) for a, b in itertools.combinations(C, 2)]
print("Gazebo crowd: bat dong ghep (bai,lan) giua cap cau hinh nhom MPPI: TB %.2f; neu ghep NGAU NHIEN (khac lan): " % np.mean(dd), end="")
dr = []
rng = np.random.default_rng(0)
for a, b in itertools.combinations(C, 2):
    ks = list(S[a]); dr.append(np.mean([S[a][k] != S[b][(k[0], str(rng.integers(1, 6)))] for k in ks]))
print("%.2f -> ghep theo lan co ich? %s" % (np.mean(dr), "khong" if np.mean(dd) > np.mean(dr) - .02 else "co"))
def power(n, delta, d, alpha=.05):
    p10, p01 = (d + delta) / 2, (d - delta) / 2
    if p01 < 0: return float("nan")
    m = np.arange(0, n + 1); pm = binom.pmf(m, n, d); tot = 0
    for mm in m[pm > 1e-9]:
        if mm == 0: continue
        k = np.arange(0, mm + 1); pv = np.minimum(1, 2 * binom.cdf(np.minimum(k, mm - k), mm, .5)); tot += pm[mm] * binom.pmf(k, mm, p10 / d)[pv <= alpha].sum()
    return tot
def need(delta, d, goal=.8, alpha=.05):
    lo, hi = 20, 6000
    while hi - lo > 4:
        mid = (lo + hi) // 2
        if power(mid, delta, d, alpha) >= goal: hi = mid
        else: lo = mid
    return hi
print("so CAP can cho suc manh 80%% / 90%% (McNemar chinh xac, 2 phia, alpha=.05)")
for d in (.20, .26, .32, .40, .48):
    print("  bat dong d=%.2f: +10 diem: %d / %d ; +5 diem: %d / %d ; (alpha Holm 4: +10 %d)" % (d, need(.1, d), need(.1, d, .9), need(.05, d), need(.05, d, .9), need(.1, d, .8, .0125)))
print("suc manh hien co: n=101,d=.28: +10 -> %.0f%%, +5 -> %.0f%% | VAL n=285,d=.28: +10 %.0f%%, +5 %.0f%% | Gazebo cu n=15 crowd d=.45 +10: %.0f%%; n=40: %.0f%%" % tuple(100 * power(*q) for q in ((101, .1, .28), (101, .05, .28), (285, .1, .28), (285, .05, .28), (15, .1, .45), (40, .1, .45))))
# loi nhuan nguoi thang cuoc (winner's curse): 19 cau hinh cung that 58 %, chon max tren 101 cap
best = []
M = np.array([[int(by[c][w]["success"]) for w in W] for c in by]); t = M.mean(0)
for _ in range(4000):                                # null: moi cau hinh co cung xac suat theo the gioi
    q = rng.random((len(by), len(W))) < t; best.append(q.mean(1).max() - q.mean())
print("winner's curse: neu 19 cau hinh BANG nhau, cau hinh cao nhat tren dev3 hon trung binh TB +%.1f diem (p95 +%.1f); quan sat: +%.1f" % (100 * np.mean(best), 100 * np.percentile(best, 95), 100 * (M.mean(1).max() - M.mean())))
sdn = np.std([ (rng.random((len(by), len(W))) < t).mean(1).std(ddof=1) for _ in range(500)])
nul = [(rng.random((len(by), len(W))) < t).mean(1).std(ddof=1) for _ in range(3000)]
print("sd giua 19 cau hinh: %.3f; neu bang nhau: %.3f (p=%.3f)" % (M.mean(1).std(ddof=1), np.mean(nul), np.mean(np.array(nul) >= M.mean(1).std(ddof=1))))
