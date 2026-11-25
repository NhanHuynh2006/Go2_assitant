#!/usr/bin/env python3
"""GAZEBO: chan doan 'nguoi ma' (tracker v3 xac nhan vat tinh) tu results/GZ_smoke/*/episodes.jsonl (OFFLINE).
Ma = vet xac nhan cach moi nguoi that > 0.8 m (bai tinh: moi vet). Bao: khoang cach toi vat tinh, va ty le ma theo |wz|, toc do."""
import json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import xml.etree.ElementTree as ET
def boxes(path):
    out = []
    for m in ET.parse(path).getroot().iter("model"):
        nm = m.get("name") or ""
        if nm.startswith(("person", "cart", "ground")): continue
        pose = [float(v) for v in (m.findtext("pose") or "0 0 0 0 0 0").split()]
        s = m.find("./link/collision/geometry/box/size"); r = m.find("./link/collision/geometry/cylinder/radius")
        if s is not None:
            sx, sy, _ = (float(v) for v in s.text.split()); out.append((pose[0], pose[1], sx, sy, pose[5]))
        elif r is not None:
            d = 2 * float(r.text); out.append((pose[0], pose[1], d, d, 0.0))
    return out
def sd(px, py, B):
    best = 9e9
    for cx, cy, sx, sy, yaw in B:
        c, s = math.cos(-yaw), math.sin(-yaw); lx = c * (px - cx) - s * (py - cy); ly = s * (px - cx) + c * (py - cy)
        dx, dy = abs(lx) - sx / 2, abs(ly) - sy / 2
        best = min(best, math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0))
    return best
OFF = os.path.expanduser("~/ros2_ws/src/unitree_go2_ros2/unitree_go2_description/worlds/voice_office.sdf")
G = json.load(open(os.path.join(ROOT, "audit/out/gztest_dev/tasks.json")))
truth = {f"gz:{t['kind']}_{t['seed']}": os.path.join(ROOT, "audit/out/gztest_dev", t["truth_sdf"]) for t in G}
EPS = []
for d in ("results/GZ_smoke/office", "results/GZ_smoke/gz4/g000"):
    EPS += [json.loads(l) for l in open(os.path.join(ROOT, d, "episodes.jsonl"))]
Bc = {}
onset_d, life_d = [], []
bins_w = [0, .1, .2, .3, .5, .8, 9]; bins_v = [0, .05, .15, .25, 9]
T_w = np.zeros(len(bins_w) - 1); N_w = np.zeros(len(bins_w) - 1); P_w = np.zeros(len(bins_w) - 1)
T_v = np.zeros(len(bins_v) - 1); N_v = np.zeros(len(bins_v) - 1)
TT = np.zeros((len(bins_v) - 1, len(bins_w) - 1)); NN = np.zeros_like(TT)
for e in EPS:
    path = truth.get(e["task"], OFF)
    B = Bc.setdefault(path, boxes(path))
    t = np.array(e["t"]); R = e["robot"]["go2"]
    ok = np.array([p is not None for p in R])
    X = np.array([p if p is not None else (np.nan,) * 3 for p in R], float)
    yaw = X[:, 2].copy(); m = ~np.isnan(yaw); yaw[m] = np.unwrap(yaw[m])
    # |wz| va toc do lam muot 0.3 s (cua so giua), tranh nhieu lac than 0.1 s
    k = 3
    wz = np.full(len(t), np.nan); v = np.full(len(t), np.nan)
    for i in range(k, len(t) - k):
        dt = t[i + k] - t[i - k]
        if dt > 0: wz[i] = abs(yaw[i + k] - yaw[i - k]) / dt; v[i] = math.hypot(X[i + k, 0] - X[i - k, 0], X[i + k, 1] - X[i - k, 1]) / dt
    seen = set()
    for i, row in enumerate(e["trk"]["go2"]):
        if i == 0 or np.isnan(wz[i]): continue
        dt = t[i] - t[i - 1]
        ppl = e["people"][i] if e["people"] else []
        ghosts = [(kk, x, y) for kk, x, y in row if all(math.hypot(x - px, y - py) > 0.8 for px, py, _ in ppl)]
        new = [g for g in ghosts if g[0] not in seen]
        for g in ghosts: seen.add(g[0])
        for g in new: onset_d.append(sd(g[1], g[2], B))
        bw = np.searchsorted(bins_w, wz[i], "right") - 1; bv = np.searchsorted(bins_v, v[i], "right") - 1
        T_w[bw] += dt; N_w[bw] += len(new); P_w[bw] += dt * (len(ghosts) > 0)
        T_v[bv] += dt; N_v[bv] += len(new); TT[bv, bw] += dt; NN[bv, bw] += len(new)
od = np.array(onset_d)
print(f"so vet ma (lan dau xac nhan): {len(od)} trong {len(EPS)} luot")
print("khoang cach tam vet ma -> mat vat tinh gan nhat: trung vi %.2f m; <0.3 m: %.0f%%, <0.6 m: %.0f%%, >1.0 m: %.0f%%"
      % (np.median(od), 100 * np.mean(od < .3), 100 * np.mean(od < .6), 100 * np.mean(od > 1.0)))
print("\nty le ma moi theo |wz| (lam muot 0.3 s):")
for j in range(len(T_w)):
    print(f"  |wz| {bins_w[j]:.1f}-{bins_w[j+1]:.1f}: thoi gian {T_w[j]:7.0f} s, ma moi {N_w[j]:4.0f} -> {N_w[j]/max(T_w[j],1e-9):.3f}/s; co ma {100*P_w[j]/max(T_w[j],1e-9):.0f}% thoi gian")
print("\ntheo toc do |v|:")
for j in range(len(T_v)):
    print(f"  v {bins_v[j]:.2f}-{bins_v[j+1]:.2f}: thoi gian {T_v[j]:7.0f} s, ma moi {N_v[j]:4.0f} -> {N_v[j]/max(T_v[j],1e-9):.3f}/s")
print("\nma moi/s theo (v hang) x (|wz| cot), [thoi gian s]:")
for a in range(TT.shape[0]):
    print(f"  v {bins_v[a]:.2f}-{bins_v[a+1]:.2f}: " + "  ".join(f"{NN[a,b]/TT[a,b]:.2f}[{TT[a,b]:.0f}]" if TT[a,b] > 5 else "  -   " for b in range(TT.shape[1])))
