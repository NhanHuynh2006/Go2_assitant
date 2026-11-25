"""CI bootstrap theo quy dao (THOR: theo nguoi+luot; crowd: theo the gioi) cho tan suat re & P(doi huong>60 trong 2 s), vai eps RDP."""
import pickle, numpy as np
from hazard import stats, HERE
from hazard_data import lp
c = pickle.load(open(f"{HERE}/data/crowd_800_999.pkl", "rb")); th = pickle.load(open(f"{HERE}/data/thor.pkl", "rb")); et = pickle.load(open(f"{HERE}/data/eth.pkl", "rb"))
G = {"crowd": [(n.split("_")[0], lp(p, 10.0)) for n, p, _ in c], "crowd_phone": [(n.split("_")[0], lp(p, 10.0)) for n, p, d in c if d > 0], "thor": [(n, p) for n, p in th], "eth": et}
def key(n, g): return n
rng = np.random.default_rng(0)
for nm, L in G.items():
    byk = {}
    for k, p in L: byk.setdefault(k, []).append(p)
    ks = list(byk); per = {k: stats(byk[k], verbose=False) if sum(len(p) >= 40 for p in byk[k]) and any((np.hypot(*np.gradient(p, 0.1, axis=0).T) > .3).sum() > 40 for p in byk[k]) else None for k in ks}
    ks = [k for k in ks if per[k] is not None and len(per[k]["dh"][20])]
    n = np.array([sum(per[k]["n"]) for k in ks]); t = np.array([per[k]["time"].sum() for k in ks])
    h = np.array([(abs(per[k]["dh"][20]) > np.pi / 3).sum() for k in ks]); hn = np.array([len(per[k]["dh"][20]) for k in ks])
    lat = np.array([(per[k]["lat"][20] > .4).sum() for k in ks]); ln = np.array([len(per[k]["lat"][20]) for k in ks])
    # chi 0.6-1.2 m/s
    n2 = np.array([sum(per[k]["n"][1:3]) for k in ks]); t2 = np.array([per[k]["time"][1:3].sum() for k in ks])
    B = [(n[i].sum() / t[i].sum(), n2[i].sum() / t2[i].sum(), h[i].sum() / hn[i].sum(), lat[i].sum() / ln[i].sum()) for i in (rng.integers(0, len(ks), len(ks)) for _ in range(1000))]
    q = np.quantile(B, [.025, .975], axis=0)
    print(f"{nm}: cum {len(ks)}; re/s {n.sum()/t.sum():.3f} [{q[0,0]:.3f},{q[1,0]:.3f}]; re/s o 0.6-1.2 m/s {n2.sum()/t2.sum():.3f} [{q[0,1]:.3f},{q[1,1]:.3f}]; P(doi huong>60do,2s) {h.sum()/hn.sum():.3f} [{q[0,2]:.3f},{q[1,2]:.3f}]; P(lech ngang CV>0.4m,2s) {lat.sum()/ln.sum():.3f} [{q[0,3]:.3f},{q[1,3]:.3f}]")
