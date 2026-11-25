"""Buoc 1 SEV: AUC 'se cham trong 3 s' (xem PREREG.md). python score.py <thu muc rec> <seedlo> <seedhi> [trk]"""
import sys, os, glob, pickle, math
sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant"); sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant/sev/snap")
import numpy as np
import nav_sev as S
from fastsim import Boxes
D = "/home/nhanhuynh/Documents/Go2_assitant/sev/data/"
rec, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); USE_TRK = "trk" in sys.argv
ACT = S.actions()
TAB = {n: np.load(D + f"V_{n}.npy", mmap_mode="r") for n in ("crowd", "thor", "crowd_x05", "crowd_x2") if os.path.exists(D + f"V_{n}.npy")}
ADV = np.load(D + "A3.npy")

def persons(d, k):
    if USE_TRK:
        q = d["trk"][k]
        out = [(a + c * g, b + e * g, c, e) for a, b, c, e, g in q]
        return np.array(out).reshape(-1, 4)
    return d["ppl"][k][:, :4]

def feats(d, k, bx):
    r = d["rob"][k]; x, y, yaw = r[1:4]; vx, vy, wz = r[4:7]
    P = persons(d, k)
    F = dict(adv3=-3.0, dist=-9.0, ttc=-9.0, dce=-9.0, pgif=0.0, turn=0.0, turn_const=0.0, turn_roll=0.0)
    for n in TAB: F.update({f"V_{n}": 0.0})
    if not len(P): return F
    c, s = math.cos(yaw), math.sin(yaw)
    e = P[:, :2] - [x, y]
    bx_, by_ = c * e[:, 0] + s * e[:, 1], -s * e[:, 0] + c * e[:, 1]
    vbx, vby = c * P[:, 2] + s * P[:, 3], -s * P[:, 2] + c * P[:, 3]
    sp = np.hypot(vbx, vby); psi = np.arctan2(vby, vbx)
    F["dist"] = -S.clearance(bx_, by_).min()
    tt = np.arange(1, 31) * 0.1
    th = wz * tt; h = 0.5 * th
    rx, ry = (vx * np.cos(h) - vy * np.sin(h)) * tt, (vx * np.sin(h) + vy * np.cos(h)) * tt
    qx, qy = bx_[:, None] + vbx[:, None] * tt - rx, by_[:, None] + vby[:, None] * tt - ry
    ct, st = np.cos(th), np.sin(th)
    cl = S.clearance(ct * qx + st * qy, -st * qx + ct * qy)
    F["dce"] = -cl.min()
    hit = cl.min(0) < 0
    F["ttc"] = -(tt[hit.argmax()] if hit.any() else 9.0)
    # PGIF: nguoi -> robot trong he nguoi
    g = 0.0; mv = sp > 0.2
    for j in range(len(P)):
        hx, hy = (math.cos(psi[j]), math.sin(psi[j])) if sp[j] > 0.05 else (1.0, 0.0)
        a, b = -(bx_[j] * hx + by_[j] * hy), (bx_[j] * hy - by_[j] * hx)
        sl = (1.2 + 0.5 * sp[j]) if a > 0 else 0.5
        g += math.exp(-0.5 * ((a / sl) ** 2 + (b / 0.6) ** 2))
    F["pgif"] = g
    def turn_at(px, py, vx_, vy_, bxr, byr, yaw_r, const=False):
        spp = math.hypot(vx_, vy_)
        if spp < 0.2: return 0.0
        rx, ry = bxr - px, byr - py
        dd = math.hypot(rx, ry) + 1e-6; hx, hy = rx / dd, ry / dd
        phi = math.acos(max(-1, min(1, (hx * vx_ + hy * vy_) / spp))); pr = math.exp(-phi ** 2 / (2 * 0.6 ** 2))
        nx, ny = -hy, hx
        cd = math.cos(yaw_r) * nx + math.sin(yaw_r) * ny; sd2 = max(1 - cd * cd, 0)
        half = 0.37 * abs(cd) + 0.16 * math.sqrt(sd2)
        ax, ay = 0.29, 0.29
        vn = 1 / math.sqrt(cd * cd / ax ** 2 + sd2 / ay ** 2); m = 0.25 + half + 0.05
        pts = np.array([[bxr + g_ * nx * m * fr, byr + g_ * ny * m * fr] for g_ in (1, -1) for fr in (.5, 1.0)])
        ok = bx.sd(pts).reshape(2, 2) > 0.22
        ok = ok.all(1).any()
        along = 0.37 * math.sqrt(sd2) + 0.16 * abs(cd)
        ttc = max(dd - 0.25 - along, 0) / spp
        need = 2.1 if const else (0.25 + m / vn if ok else 3.0)
        mar = max(-3.0, min(3.0, ttc - need))
        return pr * np.logaddexp(0, -(mar - 0.3) / 0.25) * 0.25
    F["turn"] = sum(turn_at(*p, x, y, yaw) for p in P)
    F["turn_const"] = sum(turn_at(*p, x, y, yaw, True) for p in P)
    L = []
    for i in (2, 5, 8, 11, 14, 17):
        t = (i + 1) * 0.1; hh = 0.5 * wz * t + yaw
        X = x + (vx * math.cos(hh) - vy * math.sin(hh)) * t; Y = y + (vx * math.sin(hh) + vy * math.cos(hh)) * t
        L.append(sum(turn_at(p[0] + p[2] * t, p[1] + p[3] * t, p[2], p[3], X, Y, yaw + wz * t) for p in P))
    F["turn_roll"] = float(np.mean(L))
    # tuong gan nhat (< 0.6 m) trong he than
    dw, nn = bx.normal(x, y)
    w = 0
    if dw < 0.6 and abs(nn).sum() > 0:
        aw = math.atan2(-nn[1], -nn[0]) - yaw
        w = int(round((aw % (2 * math.pi)) / (math.pi / 4))) % 8 + 1
    a_now = int(np.argmin(((ACT - np.array([vx, vy, wz])) ** 2 @ np.array([1, 1, .1]))))
    for n in TAB:
        v0 = S.Table(TAB[n] if TAB[n].ndim == 4 else TAB[n][0])(bx_, by_, psi, sp); F["V_" + n] = float(1 - np.prod(1 - np.clip(v0, 0, 1)))
    q = S.Table(ADV)(bx_, by_, psi, sp); far = (np.abs(bx_) > S.R_MAX) | (np.abs(by_) > S.R_MAX)
    q = np.where(far, 3.0, q); F["adv3"] = -float(q.min()); F["sp_all"] = float(sp.min())
    return F

rng = np.random.default_rng(123)
rows = []          # (seed, nhom, nhan, feats)
for s in range(lo, hi + 1):
    f = f"{rec}/{s}.pkl"
    if not os.path.exists(f): continue
    d = pickle.load(open(f, "rb")); R, P = d["rob"], d["ppl"]; T = len(R); bx = Boxes(d["boxes"])
    t = R[:, 0]; k0 = int(np.argmax(t >= 0))
    hit = d["row"]["col"] == "person"
    e = P[:, :, :2] - R[:, None, 1:3]; c, sn = np.cos(R[:, 3])[:, None], np.sin(R[:, 3])[:, None]
    cl = S.clearance(c * e[..., 0] + sn * e[..., 1], -sn * e[..., 0] + c * e[..., 1])      # (T,N)
    ctr = np.hypot(e[..., 0], e[..., 1]).min(1)
    if hit:
        for L in (20, 15):
            if T - 1 - L >= k0:
                jh = int(cl[-1].argmin()); rows.append((s, f"P{L}", 1, feats(d, T - 1 - L, bx))); rows[-1][3]["_sp"] = float(np.hypot(*P[T - 1 - L, jh, 2:4])); rows[-1][3]["_dist"] = float(P[T - 1, jh, 4])
                psi_j = P[T - 1 - L, jh, 2:4]; e_ = R[T - 1 - L, 1:3] - P[T - 1 - L, jh, :2]; rows[-1][3]["_hd"] = float(abs(np.angle(complex(*psi_j) / complex(*e_)))) if np.hypot(*psi_j) > .2 else -1.0
            if T - 1 - L >= k0: rows.append((s, f"H{L}", 1, rows[-1][3]))
    end = T - 1 if not hit else T - 1 - 30
    cand = [k for k in range(k0, end - 29) if ctr[k] < 4.0]
    pick = []
    for k in rng.permutation(cand):
        if all(abs(k - q) >= 10 for q in pick): pick.append(int(k))
        if len(pick) >= 4: break
    for k in pick:
        F = feats(d, k, bx)
        for L in (20, 15): rows.append((s, f"P{L}", 0, F))
    # H: cuc tieu cuc bo cua ho theo tung nguoi
    if 1:
        for j in range(P.shape[1]):
            q = cl[:, j]
            for k in range(max(k0 + 21, 1), T - 1 - (30 if hit else 0)):
                if 0 < q[k] < 0.6 and q[k] == q[max(0, k - 20):k + 21].min():
                    for L in (20, 15): rows.append((s, f"H{L}", 0, feats(d, k - L, bx)))
pickle.dump(rows, open(f"{D}score3.pkl", "wb"))

def auc(p, n):
    if not len(p) or not len(n): return np.nan
    a = np.concatenate([p, n]); o = np.argsort(a, kind="mergesort"); r = np.empty(len(a)); r[o] = np.arange(1, len(a) + 1)
    u, inv, cnt = np.unique(a, return_inverse=True, return_counts=True); cs = np.cumsum(cnt); r = (cs - (cnt - 1) / 2)[inv]
    return (r[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))
others = ["dist", "ttc", "dce", "pgif", "turn", "turn_const", "turn_roll"]
V_ = ["V_crowd", "V_thor", "V_crowd_x05", "V_crowd_x2", "adv3"]
for g in ("P20", "P15", "H20", "H15"):
    Q = [r for r in rows if r[1] == g]
    print("\n==", g)
    if g[0] == "P":
        pos = [r for r in Q if r[2]]
        print("  duong theo trang thai nguoi cham luc do: dung yen", sum(r[3]["_sp"] < .2 for r in pos), "di vao <0.5rad", sum(0 <= r[3]["_hd"] < .5 for r in pos), "di lech >0.5", sum(r[3]["_hd"] >= .5 for r in pos), "mai dien thoai", round(np.mean([r[3]["_dist"] for r in pos]), 2))
    for nm, f in (("tat ca", lambda r: True), ("dung yen", lambda r: r[2] == 0 or r[3].get("_sp", 9) < .2), ("dang di", lambda r: r[2] == 0 or r[3].get("_sp", 9) >= .2)):
        if g[0] == "H" and nm != "tat ca": continue
        z = [r for r in Q if f(r)]; y = np.array([r[2] for r in z]); sd = np.array([r[0] for r in z])
        if y.sum() < 5: continue
        keys = others + V_; A = {q: auc(np.array([r[3][q] for r in z])[y == 1], np.array([r[3][q] for r in z])[y == 0]) for q in keys}
        best = max(others, key=lambda q: A[q]); us = np.unique(sd); idx = {u: np.flatnonzero(sd == u) for u in us}; rb = np.random.default_rng(5); X = {q: np.array([r[3][q] for r in z]) for q in keys}
        dif = {q: [] for q in V_}
        for _ in range(1000):
            ii = np.concatenate([idx[u] for u in rb.choice(us, len(us))]); yy = y[ii]
            if 0 < yy.sum() < len(yy):
                b = auc(X[best][ii][yy == 1], X[best][ii][yy == 0])
                for q in V_: dif[q].append(auc(X[q][ii][yy == 1], X[q][ii][yy == 0]) - b)
        print(f"  {nm} (n+={int(y.sum())}): " + " ".join(f"{q} {A[q]:.3f}" for q in others), "| " + " ".join(f"{q} {A[q]:.3f} ({A[q]-A[best]:+.3f} [{np.quantile(dif[q],.025):+.3f},{np.quantile(dif[q],.975):+.3f}])" for q in V_), "best", best)
