"""Doc quy dao nguoi: THOR (CC BY 4.0, Zenodo 3382145), ETH/BIWI (OpenTraj, khong ghi giay phep ro), Crowd cua ta (khong robot, seed 800-999).
Tra list (T,2) 10 Hz da lam min giong nhau."""
import os, sys, pickle, glob
import numpy as np
from scipy.signal import butter, sosfiltfilt
HERE = os.path.dirname(os.path.abspath(__file__))
FC = 0.8                                   # Hz: bo lac dau/buoc chan (~1.8 Hz)

def lp(x, fs, fc=FC):
    return sosfiltfilt(butter(2, fc, fs=fs, output="sos"), x, axis=0)

def thor():
    out = []
    for f in sorted(glob.glob(f"{HERE}/data/thor/*.tsv")):
        hd = open(f, errors="replace")
        for l in hd:
            if l.startswith("BODY_NAMES"):
                names = l.rstrip("\n").rstrip("\r").split("\t")[1:]
            if l.startswith("Frame"):
                cols = l.rstrip("\r\n").split("\t"); break
        ix = [i for i, c in enumerate(cols) if c.startswith("Helmet") and c.endswith("X")]
        rows = []
        for n, l in enumerate(hd):
            if n % 5: continue                       # 100 -> 20 Hz
            q = l.rstrip("\r\n").split("\t")
            rows.append([float(q[0])] + [float(q[i + k] or 0) if i + k < len(q) else 0.0 for i in ix for k in (0, 1)])
        A = np.array(rows)
        for j in range(len(ix)):
            p = A[:, 1 + 2 * j:3 + 2 * j] / 1000.0
            ok = (np.abs(p).sum(1) > 1e-6) & np.isfinite(p).all(1)
            # doan lien tuc >= 4 s, noi lo hong <= 0.25 s
            idx = np.flatnonzero(ok)
            if len(idx) < 80: continue
            cut = np.flatnonzero(np.diff(idx) > 5)
            for seg in np.split(idx, cut + 1):
                if len(seg) < 80: continue
                t = np.arange(seg[0], seg[-1] + 1)
                q = np.stack([np.interp(t, seg, p[seg, k]) for k in (0, 1)], 1)
                if np.hypot(*np.diff(q, axis=0).T).max() > 0.25: continue
                out.append((os.path.basename(f)[:11] + f"_h{j}", lp(q, 20.0)[::2]))
    return out

def eth():
    out = []
    for s in ("seq_eth", "seq_hotel"):
        A = np.loadtxt(f"{HERE}/data/eth/{s}.txt")
        fps = 15.0 if s == "seq_eth" else 25.0
        for pid in np.unique(A[:, 1]):
            q = A[A[:, 1] == pid]; q = q[np.argsort(q[:, 0])]
            t = q[:, 0] / fps
            if len(q) < 8 or np.diff(t).max() > 0.9: continue
            tt = np.arange(t[0], t[-1], 0.1)
            # noi suy bac 3 tu 2.5 Hz roi loc cung bo loc
            from scipy.interpolate import CubicSpline
            p = np.stack([CubicSpline(t, q[:, k])(tt) for k in (2, 4)], 1)
            if len(p) < 40: continue
            out.append((f"{s}_{int(pid)}", lp(p, 10.0)))
    return out

def crowd(lo=800, hi=999, dur=60.0):
    fn = f"{HERE}/data/crowd_{lo}_{hi}.pkl"
    if os.path.exists(fn): return pickle.load(open(fn, "rb"))
    sys.path.insert(0, f"{HERE}/snap")
    import fastsim
    from fastsim import gen_world, Boxes
    FC_ = fastsim.make_crowd_class()
    out = []
    for s in range(lo, hi + 1):
        W = gen_world(s)
        if not W["crowd"]: continue
        sim = type("S", (), {})(); sim.x = np.array([W["start"][0], W["start"][1], 0.0]); sim.boxes = Boxes(W["boxes"])
        sim.x[:2] = 99.0                                    # khong co robot
        C = FC_(W, sim, 0)
        tr = [[] for _ in C.people]
        for k in range(int((dur + 2) / 0.05)):
            C.step(0.05)
            if k >= 40 and k % 2 == 1:
                for q, p in zip(tr, C.people): q.append(p["p"].copy())
        out += [(f"c{s}_{i}", np.array(q), float(C.people[i]["distracted"])) for i, q in enumerate(tr)]
    pickle.dump(out, open(fn, "wb"))
    return out

if __name__ == "__main__":
    c = crowd(); t = thor(); e = eth()
    pickle.dump(t, open(f"{HERE}/data/thor.pkl", "wb")); pickle.dump(e, open(f"{HERE}/data/eth.pkl", "wb"))
    for n, d in (("crowd", c), ("thor", t), ("eth", e)): print(n, len(d), sum(len(q[1]) for q in d) * 0.1 / 60, "phut")
