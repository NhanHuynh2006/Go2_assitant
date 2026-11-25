"""Do tin cay phia Gazebo va fastsim-Gazebo trong noi bo nhom MPPI."""
import csv, glob, os, itertools, collections
import numpy as np
from scipy.stats import spearmanr, kendalltau
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
G = [r for f in glob.glob(HERE + "/results/final_office_w[01]/trials.csv") for r in csv.DictReader(open(f))]
cf = sorted({r["config"] for r in G}); tasks = sorted({r["task"] for r in G})
A = np.full((len(cf), len(tasks), 5), np.nan)
for r in G: A[cf.index(r["config"]), tasks.index(r["task"]), int(r["trial"]) - 1] = int(r["success"])
assert not np.isnan(A).any()
fam = [i for i, c in enumerate(cf) if c not in ("pp", "rl", "rl@sac", "rl@td3", "rl_ens", "rl_safe")]
print("nhom MPPI/DWA: %d cau hinh; SR Gazebo: %s" % (len(fam), {cf[i]: round(A[i].mean(), 2) for i in fam}))
rng = np.random.default_rng(0)
def het(B):   # phuong sai giua cau hinh cua SR
    return B.mean((1, 2)).var(ddof=1)
for nm, idx, tk in (("tat ca 24, 8 bai", range(len(cf)), range(8)), ("nhom MPPI, 8 bai", fam, range(8)), ("nhom MPPI, 3 bai nguoi", fam, [i for i, t in enumerate(tasks) if t.startswith("crowd")]), ("nhom MPPI, 5 bai tinh", fam, [i for i, t in enumerate(tasks) if t.startswith("clutter")])):
    B = A[np.ix_(list(idx), list(tk), range(5))]; obs = het(B); null = []
    for _ in range(4000):                                       # hoan vi cau hinh trong tung (bai, lan)
        C = np.empty_like(B)
        for t in range(B.shape[1]):
            for k in range(5): C[:, t, k] = rng.permutation(B[:, t, k])
        null.append(het(C))
    p = np.mean(np.array(null) >= obs)
    sh = []
    for _ in range(500):
        q = rng.permutation(5); sh.append(spearmanr(B[:, :, q[:2]].mean((1, 2)), B[:, :, q[2:4]].mean((1, 2)))[0])
    print("  %-24s sd SR giua cau hinh %.3f; sd do ngau nhien %.3f; p(khac nhau that)=%.3f; tin cay chia doi (2 vs 2 lan) Spearman %.2f" % (nm, np.sqrt(obs), np.sqrt(np.mean(null)), p, np.nanmean(sh)))
    print("       phuong sai THAT uoc luong (obs-null): sd=%.3f" % np.sqrt(max(0, obs - np.mean(null))))
# fastsim
F = collections.defaultdict(list)
for f in glob.glob(HERE + "/results/fs_calib/w*.csv"):
    for r in csv.DictReader(open(f)):
        if r["success"] != "": F[r["config"].replace("~v1", "")].append((r["world"], int(r["trial"]), int(r["success"])))
com = [c for c in cf if c in F]; mf = [c for c in com if cf.index(c) in fam]
for nm, L in (("12 cau hinh", com), ("RL/pp (5)", [c for c in com if c not in mf]), ("noi bo MPPI/DWA (%d)" % len(mf), mf)):
    x = [np.mean([s for _, _, s in F[c]]) for c in L]; y = [A[cf.index(c)].mean() for c in L]
    print("fastsim~Gazebo %-24s Spearman %.2f (p=%.2f) Kendall %.2f" % (nm, *spearmanr(x, y), kendalltau(x, y)[0]))
L = mf; x = {c: np.mean([s for _, _, s in F[c]]) for c in L}
for drop in L:
    q = [c for c in L if c != drop]; print("    bo %-22s Spearman %.2f" % (drop, spearmanr([x[c] for c in q], [A[cf.index(c)].mean() for c in q])[0]))
# bootstrap CI (theo luot)
bs = []
for _ in range(2000):
    xx = [np.mean(rng.choice([s for _, _, s in F[c]], len(F[c]))) for c in L]; yy = [np.mean(rng.choice(A[cf.index(c)].ravel(), 40)) for c in L]
    bs.append(spearmanr(xx, yy)[0])
print("    bootstrap 95%% CI Spearman noi bo MPPI: [%.2f, %.2f]" % tuple(np.nanpercentile(bs, [2.5, 97.5])))
# suc manh: gia su fastsim DUNG tuyet doi (corr that = 1), sd that s trong nhom MPPI
for s in (.03, .06, .10):
    hit = []
    for _ in range(3000):
        p = np.clip(.68 + s * rng.normal(size=7), .05, .95); hit.append(spearmanr(rng.binomial(32, p), rng.binomial(40, p))[1] < .05)
    print("    neu fastsim hoan hao va sd that=%.2f: P(phat hien tuong quan p<.05 voi 7 cau hinh) = %.0f%%; " % (s, 100 * np.mean(hit)), end="")
    hit = []
    for _ in range(1000):
        p = np.clip(.68 + s * rng.normal(size=18), .05, .95); hit.append(spearmanr(rng.binomial(40, p), rng.binomial(40, p))[1] < .05)
    print("voi 18 cau hinh = %.0f%%" % (100 * np.mean(hit)))
# cum: ICC trong cau hinh x bai (gia lap lai)
B = A[fam]; m = B.mean(2)
print("5 lan lap trong cung (cau hinh, bai): P(ca 5 giong nhau)=%.0f%%; neu doc lap voi p bai (hieu ung bai): ky vong %.0f%%" % (100 * np.mean((m == 0) | (m == 1)), 100 * np.mean([(p ** 5 + (1 - p) ** 5) for p in B.mean((0, 2))])))
for ti, t in enumerate(tasks): print("   %-26s SR nhom MPPI %.2f; phuong sai that giua cau hinh: %.3f (nhi thuc %.3f)" % (t, B[:, ti].mean(), m[:, ti].var(ddof=1), B[:, ti].mean() * (1 - B[:, ti].mean()) / 5))
# doc lap giua 2 sim
w = {}
for d in "01":
    q = [r for r in G if False]
