"""Do tan suat doi huong (RDP), phan bo goc, sai so CV, dung/khoi dong: nguoi that (THOR, ETH) vs Crowd mo phong.
Xuat data/hazard_<ten>.npz (rate[3 toc do], hist goc, dung, khoi dong) cho DP."""
import os, sys, pickle, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
from hazard_data import lp
wrap = lambda a: (a + np.pi) % (2 * np.pi) - np.pi

def rdp(P, eps):
    keep = [0, len(P) - 1]; st = [(0, len(P) - 1)]
    while st:
        a, b = st.pop()
        if b - a < 2: continue
        d = P[b] - P[a]; n = np.hypot(*d)
        q = P[a + 1:b] - P[a]
        e = np.abs(q[:, 0] * d[1] - q[:, 1] * d[0]) / n if n > 1e-6 else np.hypot(q[:, 0], q[:, 1])
        k = int(e.argmax())
        if e[k] > eps: keep.append(a + 1 + k); st += [(a, a + 1 + k), (a + 1 + k, b)]
    return sorted(keep)

BINS = [(0.3, 0.6), (0.6, 0.9), (0.9, 1.2), (1.2, 2.0)]
def stats(D, eps=0.12, amin=np.radians(20), verbose=True):
    time = np.zeros(4); turns = [[] for _ in BINS]; dh = {h: [] for h in (5, 10, 20, 30)}; cv = {h: [] for h in (10, 20, 30)}; lat = {h: [] for h in (10, 20, 30)}
    walk_t = stop_n = rest_t = start_n = 0.0; st_ang = []; sp_all = []
    for P in D:
        if len(P) < 40: continue
        V = np.gradient(P, 0.1, axis=0); sp = np.hypot(*V.T); hd = np.arctan2(V[:, 1], V[:, 0]); w = sp > 0.3
        sp_all.append(sp[w])
        for i, (a, b) in enumerate(BINS): time[i] += ((sp >= a) & (sp < b)).sum() * 0.1
        # dung / khoi dong (nguong co tre 0.2 / 0.4)
        s = None
        for k, v in enumerate(sp):
            if s is None: s = v > 0.3
            if s:
                walk_t += 0.1
                if v < 0.15: s = False; stop_n += 1; h0 = hd[max(k - 10, 0)]
            else:
                rest_t += 0.1
                if v > 0.35:
                    s = True; start_n += 1
                    if "h0" in dir() and h0 is not None and k + 5 < len(hd): st_ang.append(wrap(hd[min(k + 5, len(hd) - 1)] - h0))
        h0 = None
        # chia doan dang di
        idx = np.flatnonzero(w)
        for seg in (np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1) if len(idx) else []):
            if len(seg) < 15: continue
            Q = P[seg]; k = rdp(Q, eps)
            for a, b, c in zip(k[:-2], k[1:-1], k[2:]):
                u, v_ = Q[b] - Q[a], Q[c] - Q[b]
                ang = wrap(np.arctan2(v_[1], v_[0]) - np.arctan2(u[1], u[0]))
                if abs(ang) > amin:
                    s_ = sp[seg[max(b - 8, 0)]]                          # toc do TRUOC khi re 0.8 s
                    for i, (x, y) in enumerate(BINS):
                        if x <= s_ < y: turns[i].append(ang)
            for h in dh:
                if len(seg) > h:
                    d = wrap(hd[seg[h:]] - hd[seg[:-h]]); dh[h].append(d)
        for h in cv:
            if len(P) > h:
                m = w[:-h]; e = P[h:] - P[:-h] - V[:-h] * h * 0.1; e = e[m]
                n = np.stack([-V[:-h][m][:, 1], V[:-h][m][:, 0]], 1) / sp[:-h][m][:, None]
                cv[h].append(np.hypot(*e.T)); lat[h].append(np.abs((e * n).sum(1)))
    R = dict(time=time, rate=np.array([len(t) / max(x, 1e-9) for t, x in zip(turns, time)]), n=[len(t) for t in turns],
             ang=np.concatenate([np.abs(t) for t in turns]) if any(len(t) for t in turns) else np.zeros(0),
             ang_b=[np.abs(t) for t in turns], stop=stop_n / max(walk_t, 1e-9), start=start_n / max(rest_t, 1e-9), rest_frac=rest_t / (rest_t + walk_t),
             sp=np.concatenate(sp_all).mean(), dh={h: np.concatenate(x) for h, x in dh.items()}, cv={h: np.concatenate(x) for h, x in cv.items()},
             lat={h: np.concatenate(x) for h, x in lat.items()}, st_ang=np.array(st_ang))
    return R

if __name__ == "__main__":
    S = {}
    c = pickle.load(open(f"{HERE}/data/crowd_800_999.pkl", "rb"))
    S["crowd"] = [lp(q[1], 10.0) for q in c]
    th = pickle.load(open(f"{HERE}/data/thor.pkl", "rb"))
    S["thor"] = [q[1] for q in th]
    for e in ("Exp_1", "Exp_2", "Exp_3"): S["thor_" + e] = [q[1] for q in th if q[0].startswith(e)]
    S["eth"] = [q[1] for q in pickle.load(open(f"{HERE}/data/eth.pkl", "rb"))]
    rng = np.random.default_rng(0)
    for n, D in S.items():
        R = stats(D)
        # bootstrap theo quy dao cho tong tan suat re
        tot = sum(R["n"]) / R["time"].sum()
        print(f"\n== {n}: {len(D)} quy dao, {R['time'].sum()/60:.1f} phut di (v TB {R['sp']:.2f}), nghi {R['rest_frac']*100:.0f}%")
        print("  re/s (|goc|>20do) theo toc do", [f"{a}-{b}: {r:.3f} (n={k})" for (a, b), r, k in zip(BINS, R["rate"], R["n"])], f"tong {tot:.3f}")
        if len(R["ang"]): print("  goc re: trung vi %.0f do, p75 %.0f, p90 %.0f; >45: %.0f%% >90: %.0f%%" % (*np.degrees(np.quantile(R["ang"], [.5, .75, .9])), (R["ang"] > np.pi / 4).mean() * 100, (R["ang"] > np.pi / 2).mean() * 100))
        for h, x in R["dh"].items(): print(f"  doi huong {h/10:.1f} s: RMS {np.degrees(np.sqrt((x**2).mean())):.0f} do; P(>30) {np.mean(abs(x)>np.pi/6):.2f} P(>60) {np.mean(abs(x)>np.pi/3):.2f} P(>90) {np.mean(abs(x)>np.pi/2):.2f}", end="")
        print()
        for h, x in R["cv"].items(): print(f"  sai so CV {h/10:.0f} s: TB {x.mean():.2f} trung vi {np.median(x):.2f} p90 {np.quantile(x,.9):.2f} | lech ngang TB {R['lat'][h].mean():.2f} P(>0.4 m) {np.mean(R['lat'][h]>.4):.2f}")
        print(f"  dung {R['stop']:.3f}/s, khoi dong {R['start']:.3f}/s, goc khoi dong |.| trung vi {np.degrees(np.median(np.abs(R['st_ang']))) if len(R['st_ang']) else -1:.0f} (n={len(R['st_ang'])})")
        h = np.histogram(R["ang"], bins=np.radians(np.arange(22.5 - 7.5, 188, 15)))[0]
        np.savez(f"{HERE}/data/hazard_{n}.npz", rate=R["rate"], time=R["time"], n=R["n"], ang=R["ang"], stop=R["stop"], start=R["start"], st_ang=R["st_ang"], sp=R["sp"])
