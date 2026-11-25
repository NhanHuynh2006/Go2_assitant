"""Phan tich them tu score_gt_*.pkl: (a) V tb tren ca duong theo -2/-1.5 (b) thong tin gia tang: logistic L2 5-fold theo luot
voi/khong co V tren cac diem thanh phan (c) AUC theo nhom V cao."""
import sys, pickle, numpy as np
fn = sys.argv[1]
rows = pickle.load(open(fn, "rb"))
others = ["dist", "ttc", "dce", "pgif", "turn", "turn_const", "turn_roll"]
def auc(p, n):
    a = np.concatenate([p, n]); u, inv, cnt = np.unique(a, return_inverse=True, return_counts=True); cs = np.cumsum(cnt); r = (cs - (cnt - 1) / 2)[inv]
    return (r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))
def logit(X, y, l2=1.0, it=400):
    w = np.zeros(X.shape[1]); b = 0.0
    n1, n0 = y.sum(), (1 - y).sum(); sw = np.where(y == 1, 0.5 / n1, 0.5 / n0) * len(y)
    for _ in range(it):
        p = 1 / (1 + np.exp(-(X @ w + b))); g = (p - y) * sw
        w -= 0.3 * ((X * g[:, None]).mean(0) + l2 * w / len(y)); b -= 0.3 * g.mean()
    return w, b
for g in ("P20", "P15", "H20", "H15"):
    Q = [r for r in rows if r[1] == g]; y = np.array([r[2] for r in Q]); sd = np.array([r[0] for r in Q])
    if y.sum() < 10: print(g, "it mau", y.sum()); continue
    print(f"\n{g}: V_crowd tb duong {np.mean([r[3]['V_crowd'] for r in Q if r[2]]):.3f} trung vi {np.median([r[3]['V_crowd'] for r in Q if r[2]]):.3f}; am {np.mean([r[3]['V_crowd'] for r in Q if not r[2]]):.3f};  Vol {np.mean([r[3]['Vol_crowd'] for r in Q if r[2]]):.3f}/{np.mean([r[3]['Vol_crowd'] for r in Q if not r[2]]):.3f}")
    us = np.unique(sd); fold = {u: i % 5 for i, u in enumerate(np.random.default_rng(1).permutation(us))}; fo = np.array([fold[s] for s in sd])
    res = {}
    for name, keys in (("others", others), ("others+V", others + ["V_crowd"]), ("others+Vol", others + ["Vol_crowd"]), ("others+V+Vol", others + ["V_crowd", "Vol_crowd"])):
        X = np.array([[r[3][k] for k in keys] for r in Q]); X = np.c_[X, np.maximum(X[:, :1], -1.5) ** 2]
        o = np.zeros(len(y))
        for f in range(5):
            tr = fo != f; mu, sg = X[tr].mean(0), X[tr].std(0) + 1e-9
            w, b = logit((X[tr] - mu) / sg, y[tr]); o[~tr] = (X[~tr] - mu) / sg @ w + b
        res[name] = o; print(f"   {name:14s} AUC CV {auc(o[y == 1], o[y == 0]):.3f}")
    rb = np.random.default_rng(0); idx = {u: np.flatnonzero(sd == u) for u in us}; D = []
    for _ in range(1000):
        ii = np.concatenate([idx[u] for u in rb.choice(us, len(us))]); yy = y[ii]
        if 0 < yy.sum() < len(yy):
            D.append(auc(res["others+V"][ii][yy == 1], res["others+V"][ii][yy == 0]) - auc(res["others"][ii][yy == 1], res["others"][ii][yy == 0]))
    print(f"   dAUC (others+V - others) CI [{np.quantile(D,.025):+.3f},{np.quantile(D,.975):+.3f}]")
