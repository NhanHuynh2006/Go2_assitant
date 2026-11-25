"""at_fault tren du lieu Gazebo 960 luot: nen |wz|>0.3 do lac than, thoi diem cham sau nhat vs cham dau, quan tinh sau va."""
import json, sys, os
import numpy as np
from gz_load import load
R = load()
F = lambda x: float(x) if x not in ("", None) else None
def feats(tr, dt):
    v = np.diff(tr[:, :2], axis=0) / .1; yaw = np.unwrap(tr[:, 2]); w = np.diff(yaw) / .1
    return v, w
print("== ti le nen |wz|>0.3 (cua so 1 mau = 0.1 s, nhu Monitor), bai KHONG nguoi, robot dang di")
for mode in ("tat ca", "di thang (|wz TB 1 s| < 0.1)", "than dung yen (|v 1 s|<0.03, |wz 1 s|<0.05)"):
    n = k = 0
    for r in R:
        if r["cat"] != "clutter": continue
        tr = r["traj"]
        if len(tr) < 40: continue
        v, w = feats(tr, .1); yaw = np.unwrap(tr[:, 2])
        w1 = (yaw[10:] - yaw[:-10]) / 1.0; v1 = np.hypot(*(tr[10:, :2] - tr[:-10, :2]).T)
        ww = w[5:5 + len(w1)]
        m = np.ones(len(w1), bool) if mode == "tat ca" else (np.abs(w1) < .1) if mode.startswith("di thang") else ((v1 < .03) & (np.abs(w1) < .05))
        if mode.startswith("di thang"): m &= v1 > .1
        n += m.sum(); k += (np.abs(ww[m]) > .3).sum()
    print("   %-45s n=%6d  P(|wz|>.3) = %.0f%%" % (mode, n, 100 * k / max(n, 1)))
C = []
for r in R:
    if r["cat"] == "crowd" and F(r["min_person_gap_m"]) is not None and F(r["min_person_gap_m"]) < 0:
        i = json.loads(r["col_info"]); i["r"] = r; C.append(i)
print("== %d luot cham nguoi; at_fault=1: %d" % (len(C), sum(c.get("at_fault", 1) for c in C)))
rin = np.array([c["robot_in"] for c in C]); wz = np.array([abs(c["robot_wz"]) for c in C]); pin = np.array([c["person_in"] for c in C])
print("   chi do rin>.1: %d | chi do |wz|>.3: %d | ca hai: %d | khong: %d" % (((rin > .1) & (wz <= .3)).sum(), ((rin <= .1) & (wz > .3)).sum(), ((rin > .1) & (wz > .3)).sum(), ((rin <= .1) & (wz <= .3)).sum()))
print("   do sau nhat luc cham: median %.3f m; min %.3f" % (np.median([c["d"] for c in C]), min(c["d"] for c in C)))
# thoi gian tu cham dau toi cham sau nhat, voi nguoi 0
res = []
from eval_fp import fp_dist
for c in C:
    r = c["r"]; n = min(len(r["traj"]), len(r["person"]))
    g = np.array([fp_dist(r["traj"][k], r["person"][k]) for k in range(n)]) - .22
    if g.min() > 0: continue
    kf, kd = int(np.argmax(g < 0)), int(g.argmin())
    if abs(g[kd] - c["d"]) > .03: continue
    tr = r["traj"]; yaw = np.unwrap(tr[:, 2])
    def wz_at(k): return abs(yaw[k] - yaw[k - 1]) / .1
    def rin_at(k, L=1):
        u = r["person"][k, :2] - tr[k, :2]; u /= np.hypot(*u); return float((tr[k, :2] - tr[k - L, :2]) @ u / (.1 * L))
    def pin_at(k, L=1):
        u = r["person"][k, :2] - tr[k, :2]; u /= np.hypot(*u); return float(-(r["person"][k, :2] - r["person"][k - L, :2]) @ u / (.1 * L))
    # cham dau: 0.5 s truoc, lam muot (chua bi day)
    if kf < 8: continue
    res.append(dict(cfg=r["config"], task=r["task"], lag=(kd - kf) * .104, f_deep=c["at_fault"], f_first=int(rin_at(kf) > .1 or wz_at(kf) > .3),
                    f_pre=int(rin_at(kf - 1, 5) > .1 or abs(yaw[kf - 1] - yaw[kf - 6]) / .5 > .3), rin5=rin_at(kf - 1, 5), pin5=pin_at(kf - 1, 5), wz5=abs(yaw[kf - 1] - yaw[kf - 6]) / .5, k=kf, r=r))
print("== tap con cham nguoi so 0 (biet quy dao): n=%d" % len(res))
L = np.array([q["lag"] for q in res]); print("   tre cham dau -> cham sau nhat: median %.2f s, p90 %.2f; >0.3 s: %d" % (np.median(L), np.percentile(L, 90), (L > .3).sum()))
for a, b in (("f_deep", "f_first"), ("f_deep", "f_pre"), ("f_first", "f_pre")):
    M = np.zeros((2, 2), int)
    for q in res: M[q[a], q[b]] += 1
    print("   bang %s (hang) x %s (cot): %s  bat dong %d/%d" % (a, b, M.tolist(), M[0, 1] + M[1, 0], len(res)))
