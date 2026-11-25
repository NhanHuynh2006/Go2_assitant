"""Lac than: Gazebo (traj 10 Hz that) vs fastsim (full 10 Hz truoc khi cham)."""
import glob, pickle, os, json, sys
import numpy as np
from gz_load import load
def st(trs, dt):
    W, L, Wr, R, Vv = [], [], [], [], []
    for t in trs:
        t = np.asarray(t, float)
        if len(t) < 60: continue
        yaw = np.unwrap(t[:, 2]); w = np.diff(yaw) / dt; v1 = np.hypot(*(t[10:, :2] - t[:-10, :2]).T) / (10 * dt)
        ker = np.ones(11) / 11; rs = yaw[5:-5] - np.convolve(yaw, ker, "valid")
        mv = v1 > .12; W += list(w[5:5 + len(v1)][mv]); Wr += list(rs[:len(v1)][mv]); Vv += list(v1[mv])
        p5 = np.hypot(*np.diff(t[::5, :2], axis=0).T).sum(); p1 = np.hypot(*np.diff(t[:(len(t) - 1) // 5 * 5 + 1, :2], axis=0).T).sum(); R.append(p1 / max(p5, 1e-3))
    W = np.array(W); return dict(n=len(W), P_wz_gt03=round(np.mean(np.abs(W) > .3), 2), sd_wz01=round(W.std(), 2), sd_yaw_res=round(np.std(Wr), 3), path01_over_path05=round(np.mean(R), 3), v_1s=round(np.mean(Vv), 3))
R = load()
fam = ("mppi", "dwa", "log_mppi")
print("Gazebo  tinh mppi/dwa/log", st([r["traj"] for r in R if r["cat"] == "clutter" and r["config"] in fam], .1033))
print("Gazebo  dong mppi/dwa/log", st([r["traj"] for r in R if r["cat"] == "crowd" and r["config"] in fam], .104))
P = []
for f in glob.glob("out/base/*.pkl"):
    with open(f, "rb") as g:
        while True:
            try: P.append(pickle.load(g))
            except EOFError: break
print("fastsim dong (8 s truoc cham, %d luot)" % len(P), st([[q[1] for q in p["full"]] for p in P], .1))
