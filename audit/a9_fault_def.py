"""So sanh dinh nghia at_fault + do ben voi lac than. Du lieu: fastsim (moi nguoi deu biet quy dao) va Gazebo (chi phan robot)."""
import glob, pickle, json, math, sys, os
import numpy as np
from eval_fp import A, B
def body(p):
    c, s = math.cos(p[2]), math.sin(p[2]); return np.stack([p[0] + c * A - s * B, p[1] + s * A + c * B], 1)
def near_i(p, q): return int(np.hypot(*(body(p) - q).T).argmin())
def wrap(a): return math.atan2(math.sin(a), math.cos(a))
def D0(X, Q):                                              # hien tai (Gazebo): vi phan 0.1 s, huong tam-tam
    v = (X[-1, :2] - X[-2, :2]) / .1; u = Q[-1] - X[-1, :2]; u = u / np.hypot(*u); return int(v @ u > .1 or abs(wrap(X[-1, 2] - X[-2, 2]) / .1) > .3)
def D05(X, Q, L=5):                                        # hien tai nhung trung binh 0.5 s
    v = (X[-1, :2] - X[-1 - L, :2]) / (.1 * L); u = Q[-1] - X[-1, :2]; u = u / np.hypot(*u); return int(v @ u > .1 or abs(wrap(X[-1, 2] - X[-1 - L, 2]) / (.1 * L)) > .3)
def closing(X, Q, L=5):                                    # van toc DIEM THAN cham (gom xoay) theo phap tuyen, TB 0.5 s; va cua nguoi
    Xs = smooth(X); i = near_i(Xs[-1], Q[-1]); b1 = body(Xs[-1])[i]; n = Q[-1] - b1; n = n / max(np.hypot(*n), 1e-6)
    return float((b1 - body(Xs[-1 - L])[i]) @ n) / (.1 * L), float(-(Q[-1] - Q[-1 - L]) @ n) / (.1 * L)
def D1(X, Q): return int(closing(X, Q)[0] > .1)
def D1s(X, Q): r, p = closing(X, Q); return int(r > .1 and r > .25 * (max(p, 0) + r))   # robot gop >= 25 % toc do ap sat
def D2(X, Q, L=10):                                        # phan thuc te: robot DUNG YEN tu 1 s truoc -> nguoi (quy dao that + 0.5 s van toc deu) co cham khong
    Xs = smooth(X); p = Xs[-1 - L]; v = (Q[-1] - Q[-4]) / .3; path = list(Q[-L:]) + [Q[-1] + v * .1 * k for k in range(1, 6)]
    return int(min(np.hypot(*(body(p) - q).T).min() for q in path) - .22 > 0)
def smooth(X, w=5):                                        # trung vi/TB truot 0.5 s (cua so can giua, hep dan o dau)
    Y = X.copy(); Y[:, 2] = np.unwrap(X[:, 2])
    return np.array([Y[max(0, i - w // 2 - (w // 2 if i + w // 2 >= len(Y) else 0)):i + w // 2 + 1].mean(0) for i in range(len(Y))])
DEF = dict(D0=D0, D05=D05, D1=D1, D1s=D1s, D2=D2)
if __name__ == "__main__":
    rng = np.random.default_rng(0); P = []
    for f in glob.glob("out/base/*.pkl"):
        with open(f, "rb") as g:
            while True:
                try: P.append(pickle.load(g))
                except EOFError: break
    rows = []
    for p in P:
        fu = p["full"]
        if len(fu) < 25: continue
        X = np.array([q[1] for q in fu], float); X[:, 2] = np.unwrap(X[:, 2]); k = int(np.argmin([min(np.hypot(*(body(X[-1]) - q[:2]).T)) - q[2] for q in fu[-1][2]]))
        Q = np.array([q[2][k][:2] for q in fu], float); inf = json.loads(p["info"])
        r = dict(cfg=p["cfg"], dis=inf.get("distracted", 0), fs=inf["at_fault"], rc=closing(X, Q)); r.update({n: f(X, Q) for n, f in DEF.items()})
        S = smooth(X); fl = {n: [] for n in DEF}                # ve lai lac than 40 lan (OU, 1.5 cm / 0.057 rad, tau .15)
        for _ in range(40):
            e = np.zeros((len(S), 3)); rho = math.exp(-.1 / .15); z = rng.normal(size=3)
            for t in range(len(S)): z = rho * z + math.sqrt(1 - rho ** 2) * rng.normal(size=3); e[t] = z * [.015, .015, .057]
            for n, f in DEF.items(): fl[n].append(f(S + e, Q))
        r["flip"] = {n: float(2 * np.mean(v) * (1 - np.mean(v))) for n, v in fl.items()}; r["base"] = {n: f(S, Q) for n, f in DEF.items()}; r["pm"] = {n: float(np.mean(v)) for n, v in fl.items()}
        rows.append(r)
    print("n = %d lan cham nguoi (fastsim, DEV 150+)" % len(rows)); print("at_fault fastsim (van toc lenh loc, khong lac): %.0f%%" % (100 * np.mean([r["fs"] for r in rows])))
    for n in DEF: print("  %-4s loi robot %.0f%% | khong lac %.0f%% | P(nhan bi doi khi ve lai lac than) %.2f | khong lac=0 ma co lac=1: %.0f%% | nguoi mdt %.0f%% vs khong %.0f%%" % (n, 100 * np.mean([r[n] for r in rows]), 100 * np.mean([r["base"][n] for r in rows]), np.mean([r["flip"][n] for r in rows]), 100 * np.mean([r["pm"][n] for r in rows if r["base"][n] == 0] or [0]), 100 * np.mean([r[n] for r in rows if r["dis"]]), 100 * np.mean([r[n] for r in rows if not r["dis"]])))
    print("  dong thuan D1-D2: %.0f%%" % (100 * np.mean([r["D1"] == r["D2"] for r in rows])))
    print("  van toc ap sat TB 0.5 s: robot %.2f, nguoi %.2f m/s" % tuple(np.mean([r["rc"] for r in rows], 0)))
    for c in sorted({r["cfg"] for r in rows}): q = [r for r in rows if r["cfg"] == c]; print("   %-20s n=%d " % (c, len(q)), {n: "%.0f%%" % (100 * np.mean([r[n] for r in q])) for n in ("D0", "D1", "D2")})
    # Gazebo: chi phan robot
    from gz_load import load
    G = [r for r in load() if r["cat"] == "crowd" and r["min_person_gap_m"] and float(r["min_person_gap_m"]) < 0]; T = np.zeros((2, 2), int); only = [0, 0]
    for r in G:
        i = json.loads(r["col_info"]); k = int(round(i["t"] / .104)); tr = r["traj"]
        if k < 8 or k >= len(tr): continue
        w5 = abs(wrap(tr[k, 2] - tr[k - 5, 2])) / .52; a = int(abs(i["robot_wz"]) > .3); T[a, int(w5 > .3)] += 1
        if a and i["robot_in"] <= .1: only[int(w5 > .3)] += 1
    print("Gazebo: |wz 0.1 s|>.3 (hang) x |wz TB 0.5 s|>.3 (cot):", T.tolist(), " -> trong %d luot bi quy loi CHI vi wz: %d (%.0f%%) khong con khi lay TB 0.5 s" % (sum(only), only[0], 100 * only[0] / max(1, sum(only))))
