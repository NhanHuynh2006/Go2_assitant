"""So the gioi TEST cho fastsim: chenh gop theo the gioi (TB 5 o), sd lay tu algo_W* (vong 2) va algo_Y* (vong 3)."""
import csv, glob, os, math, sys
import numpy as np
from scipy.stats import norm, t as tdist
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
REF = {"B1": "mppi~t3~nl:ppl=100;ppl_len=0.5", "PGIF": "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000", "DRA": "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05", "B0": "mppi:ppl=32"}
CELLS = ["champ_base", "champ2_base", "go2_base", "champ2_helb", "go2_helb"]
def cellmap(pfx):
    out = {}
    for c in CELLS:
        S = {}
        for f in glob.glob(f"{H}/results/algo_{pfx}{c}/w*.csv"):
            for r in csv.DictReader(open(f)):
                if r["success"] != "": S[(r["config"], int(r["world"]))] = int(r["success"])
        out[c] = S
    return out
res = {}
for pfx in ("W", "Y"):
    M = cellmap(pfx)
    for nm, ref in REF.items():
        W = sorted(set.intersection(*[{w for (c, w) in M[cl] if c == C1} & {w for (c, w) in M[cl] if c == ref} for cl in CELLS]))
        if not W: continue
        d = np.array([np.mean([M[cl][(C1, w)] - M[cl][(ref, w)] for cl in CELLS]) for w in W])
        res.setdefault(nm, []).append(d)
        print("%s %-4s n=%d  chenh %+.2f diem  sd/the gioi %.3f  P(d=0) %.2f  cell-level disc %.2f" % (pfx, nm, len(W), 100 * d.mean(), d.std(ddof=1), np.mean(d == 0), np.mean([np.mean([M[cl][(C1, w)] != M[cl][(ref, w)] for w in W]) for cl in CELLS])))
def n_need(delta, sd, alpha, pw):
    return math.ceil(((norm.ppf(1 - alpha / 2) + norm.ppf(pw)) * sd / delta) ** 2)
print("\nso the gioi can (xap xi chuan cho phep hoan vi dau; sd gop W+Y):")
for nm, delta in (("B1", .065), ("PGIF", .052), ("DRA", .03), ("DRA", .025), ("DRA", .02)):
    sd = np.concatenate(res[nm]).std(ddof=1)
    print("  %-4s delta=%.1f sd=%.3f | alpha .05: 80%% %d, 90%% %d | alpha .0167 (Holm buoc 1): 80%% %d, 90%% %d" % (nm, 100 * delta, sd, n_need(delta, sd, .05, .8), n_need(delta, sd, .05, .9), n_need(delta, sd, .0167, .8), n_need(delta, sd, .0167, .9)))
# mo phong suc manh dung phep hoan vi dau, bootstrap the gioi tu du lieu W+Y (giu cau truc phan phoi)
rng = np.random.default_rng(0)
def signflip_p(d, B=4000):
    obs = abs(d.mean()); s = rng.choice([-1, 1], size=(B, len(d))); return (np.abs((s * d).mean(1)) >= obs).mean()
for nm in ("DRA", "B1"):
    pool = np.concatenate(res[nm])
    for n in (400, 600, 800, 1000):
        hits = [signflip_p(rng.choice(pool, n)) for _ in range(300)]
        print("  bootstrap %s (chenh that = TB W+Y %+.1f), n=%d: P(p<.05)=%.2f, P(p<.0167)=%.2f" % (nm, 100 * pool.mean(), n, np.mean(np.array(hits) < .05), np.mean(np.array(hits) < .0167)))
# Gazebo: 1 o (champ base), McNemar; ti le bat dong cap o champ_base
print("\n== o champ_base (gan Gazebo nhat):")
sys.path.insert(0, H + "/audit"); from a6_power import power, need
for pfx in ("W", "Y"):
    M = cellmap(pfx)["champ_base"]
    for nm in ("B1", "DRA", "PGIF"):
        W = sorted({w for (c, w) in M if c == C1} & {w for (c, w) in M if c == REF[nm]})
        a = np.array([M[(C1, w)] for w in W]); b = np.array([M[(REF[nm], w)] for w in W])
        print("  %s %-4s n=%d C1 %.1f ref %.1f chenh %+.1f bat dong %.2f" % (pfx, nm, len(W), 100 * a.mean(), 100 * b.mean(), 100 * (a - b).mean(), np.mean(a != b)))
for d in (.20, .30, .40):
    print("  McNemar 80%%/90%%: d=%.2f +6: %d/%d  +4: %d/%d  +3: %d/%d" % (d, need(.06, d), need(.06, d, .9), need(.04, d), need(.04, d, .9), need(.03, d), need(.03, d, .9)))
