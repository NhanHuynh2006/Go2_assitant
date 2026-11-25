#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_bags.py - rut tu ban ghi THAT (khong co lenh): ti le odom so voi LiDAR, phan bo van toc / gia toc,
than lac, tre mocs thoi gian.  python analyze_bags.py NAME BAG LIDAR.npz [--odom T --imu T --unitree-stamps]"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import argparse
import json
import sys

import numpy as np
from scipy.signal import butter, sosfiltfilt, welch
from scipy.spatial.transform import Rotation as Rn, Slerp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio


def yaw(q):
    x, y, z, w = np.asarray(q).T
    return np.unwrap(np.arctan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def uniq(a):
    a = a[np.argsort(a[:, 0])]
    _, i = np.unique(a[:, 0], return_index=True)
    return a[i]


def lp(x, fs, fc, o=2):
    return sosfiltfilt(butter(o, fc, fs=fs, output="sos"), x, axis=0)


def hp(x, fs, fc, o=2):
    return sosfiltfilt(butter(o, fc, "high", fs=fs, output="sos"), x, axis=0)


def lag(ta, a, tb, b, w=.6, fs=100):
    """tre cua b so voi a (giay, >0: b tre hon), do tuong quan cheo."""
    t = np.arange(max(ta[0], tb[0]) + 1, min(ta[-1], tb[-1]) - 1, 1 / fs)
    ls = np.arange(-w, w + 1e-9, .005)
    A = np.interp(t, ta, a)
    c = [np.corrcoef(A, np.interp(t + l, tb, b))[0, 1] for l in ls]
    i = int(np.argmax(c))
    return round(float(ls[i]), 3), round(float(c[i]), 3)


def boot(x, f, n=400, blk=8, seed=0):
    """bootstrap khoi -> (2.5, 97.5 %)"""
    r = np.random.default_rng(seed)
    m = len(x)
    if m < 2 * blk:
        return [float("nan")] * 2
    o = []
    for _ in range(n):
        s = r.integers(0, m - blk, size=m // blk)
        o.append(f(x[np.concatenate([np.arange(k, k + blk) for k in s])]))
    return [round(float(v), 4) for v in np.percentile(o, [2.5, 97.5])]


ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("bag"); ap.add_argument("lidar")
ap.add_argument("--odom", default="/go2/odom"); ap.add_argument("--imu", default="/go2/ouster/imu")
ap.add_argument("--scale", type=float, default=1.0, help="ti le da nhan san trong odom cua ban ghi")
a = ap.parse_args()
O = {"name": a.name}
raw = [(tb, m) for tb, m in bagio.read(a.bag, a.odom)]
od = uniq(np.array([(m[0], *m[3], *m[4], *m[5], *m[6]) for _, m in raw]))
O["odom_hz"] = round(len(od) / (od[-1, 0] - od[0, 0]), 1)
O["odom_gap_p99_max_s"] = [round(float(v), 3) for v in (np.percentile(np.diff(od[:, 0]), 99), np.diff(od[:, 0]).max())]
t, P, Q, V, W = od[:, 0], od[:, 1:4], od[:, 4:8], od[:, 8:11], od[:, 11:14]
Y = yaw(Q)
im = uniq(np.array([(m[0], *m[3], *m[4]) for _, m in bagio.read(a.bag, a.imu)]))
Lz = np.load(a.lidar)
tl, Tl = Lz["t"], Lz["T"]
Yl = np.unwrap(np.arctan2(Tl[:, 1, 0], Tl[:, 0, 0]))
fs = 50.0
tg = np.arange(max(t[0], tl[0]) + .5, min(t[-1], tl[-1]) - .5, 1 / fs)
p = np.stack([np.interp(tg, t, P[:, k]) for k in range(3)], 1)
yo = np.interp(tg, t, Y)
# van toc than tu sai phan vi tri odom (loc 2 Hz) so voi twist -> he truc cua twist
pf = lp(p, fs, 2.0); dv = np.gradient(pf, 1 / fs, axis=0); yf = lp(yo, fs, 2.0)
c, s = np.cos(yf), np.sin(yf)
vb = np.stack([c * dv[:, 0] + s * dv[:, 1], -s * dv[:, 0] + c * dv[:, 1]], 1)
tw = np.stack([lp(np.interp(tg, t, V[:, k]), fs, 2.0) for k in range(2)], 1)
mv = np.hypot(*vb.T) > .25
# RMSE mo hinh k*v rieng tung truc
for nm, ref in (("than", vb), ("odom(the gioi)", dv[:, :2])):
    k = (tw[mv] * ref[mv]).sum() / (ref[mv] ** 2).sum()
    O["twist_vs_" + nm] = dict(k=round(float(k), 3), rmse=round(float(np.sqrt(((tw[mv] - k * ref[mv]) ** 2).mean())), 3))
wz_o = np.gradient(yf, 1 / fs)
# tre: gyro IMU (truc z) vs odom yaw rate vs lidar yaw rate
gz = im[:, 3]
sgn = np.sign(np.corrcoef(np.interp(tg, im[:, 0], gz), wz_o)[0, 1])
gz = gz * sgn
O["gyro_sign"] = int(sgn)
gzf = np.interp(tg, im[:, 0], gz)
O["lag_odom_twistwz_vs_imu"] = lag(im[:, 0], gz, t, W[:, 2])
O["lag_odom_yawrate_vs_imu"] = lag(tg, lp(gzf, fs, 2.0), tg, wz_o)
wl = np.gradient(Yl, tl)
O["lag_lidar_vs_imu"] = lag(tg, lp(gzf, fs, 2.0), tl, wl)
L = O["lag_lidar_vs_imu"][0] - O["lag_odom_yawrate_vs_imu"][0]        # LiDAR tre hon odom
tl2 = tl - L
O["gyro_vs_lidar_yaw_total_deg"] = None
g0 = np.median(gz[:150])
# ---- ti le: dich chuyen trong cua so 1.5 s, he truc than dau cua so
D = 1.5
ts = np.arange(tg[0], tg[-1] - D, D / 2)
def rel(tt, X, Yw, a0):
    x0 = np.array([np.interp(a0, tt, X[:, k]) for k in (0, 1)]); x1 = np.array([np.interp(a0 + D, tt, X[:, k]) for k in (0, 1)])
    y0, y1 = np.interp(a0, tt, Yw), np.interp(a0 + D, tt, Yw)
    d = x1 - x0; c, s = np.cos(y0), np.sin(y0)
    return np.stack([c * d[0] + s * d[1], -s * d[0] + c * d[1], y1 - y0], 1)
ro, rl = rel(t, P, Y, ts), rel(tl2, Tl[:, :2, 3], Yl, ts)
ser = np.interp(ts + D / 2, tl, Lz["q"][:, 3]); eig = np.interp(ts + D / 2, tl, Lz["q"][:, 0] / Lz["q"][:, 1])
# goc gan lech giua khung LiDAR (than, gan OS1) va odom: uoc luong khi di thang
st = (np.abs(ro[:, 2]) < .12) & (np.hypot(ro[:, 0], ro[:, 1]) > .4)
M = np.hstack([ro, rl, ser[:, None], eig[:, None]])
f = lambda m: np.median(np.hypot(m[:, 3], m[:, 4]) / np.hypot(m[:, 0], m[:, 1]))
O["n_window"] = int(len(M)); O["n_straight"] = int(st.sum())
O["mount_yaw_deg"] = round(float(np.degrees(np.median(np.arctan2(rl[st, 1], rl[st, 0]) - np.arctan2(ro[st, 1], ro[st, 0])))), 2)
O["scale_straight_median"] = round(float(f(M[st])), 4); O["scale_straight_ci"] = boot(M[st], f)
g = lambda m: np.hypot(m[:, 3], m[:, 4]).sum() / np.hypot(m[:, 0], m[:, 1]).sum()
O["scale_straight_sum"] = round(float(g(M[st])), 4); O["scale_straight_sum_ci"] = boot(M[st], g)
allm = np.hypot(ro[:, 0], ro[:, 1]) > .3
O["scale_all_sum"] = round(float(g(M[allm])), 4)
O["path_len_odom_lidar_m"] = [round(float(np.hypot(*np.diff(X[::k, :2], axis=0).T).sum()), 1) for X, k in ((P, 75), (Tl[:, :3, 3], 15))]
O["scale_by_speed"] = {}
sp = np.hypot(rl[:, 0], rl[:, 1]) / D
for lo, hi in ((.2, .4), (.4, .6), (.6, .8), (.8, 1.0), (1.0, 1.3), (1.3, 2.0)):
    m = allm & (sp >= lo) & (sp < hi)
    if m.sum() >= 5:
        O["scale_by_speed"]["%.1f-%.1f" % (lo, hi)] = [int(m.sum()), round(float(g(M[m])), 3), round(float(np.std(np.hypot(*rl[m, :2].T) / np.hypot(*ro[m, :2].T))), 3)]
rat = np.hypot(rl[:, 0], rl[:, 1]) / np.maximum(np.hypot(ro[:, 0], ro[:, 1]), 1e-6)
bad = allm & (np.abs(rat / np.median(rat[st]) - 1) > .15)
O["odom_glitch_windows(>15%)"] = [int(bad.sum()), int(allm.sum()), [[round(float(ts[i] - ts[0]), 1), round(float(rat[i]), 2), round(float(rl[i, 2]), 2)] for i in np.nonzero(bad)[0][:12]]]
turn = np.abs(rl[:, 2]) > .4
if turn.sum() > 4:
    A = ro[turn, 2]; O["yaw_scale_lidar_over_odom"] = [int(turn.sum()), round(float((A * rl[turn, 2]).sum() / (A * A).sum()), 4)]
# gyro yaw scale
cg = np.concatenate([[0], np.cumsum(.5 * (gz[1:] + gz[:-1] - 2 * g0) * np.diff(im[:, 0]))])
rg = np.interp(ts + D, im[:, 0], cg) - np.interp(ts, im[:, 0], cg)
if turn.sum() > 4:
    O["yaw_scale_lidar_over_gyro"] = round(float((rg[turn] * rl[turn, 2]).sum() / (rg[turn] ** 2).sum()), 4)
# ngang (vy): cua so co |dy_o|
lat = np.abs(ro[:, 1] - 0) > .15
O["n_lateral_windows"] = int((lat & (np.abs(ro[:, 2]) < .2)).sum())
O["weak_windows_eig<0.1"] = round(float((eig < .1).mean()), 3)
# ---- phan bo van toc (LiDAR cho tinh tien, odom*k cho dong luc hoc muot)
k = O["scale_straight_median"]
vx, vy, wz = vb[:, 0] * k, vb[:, 1] * k, wz_o
mv = (np.hypot(vx, vy) > .1) | (np.abs(wz) > .15)
def pct(x, q=(1, 5, 25, 50, 75, 95, 99)):
    return [round(float(v), 3) for v in np.percentile(x, q)]
O["moving_frac"] = round(float(mv.mean()), 3)
O["vx_pct(1,5,25,50,75,95,99)"], O["vy_pct"], O["wz_pct"] = pct(vx[mv]), pct(vy[mv]), pct(wz[mv])
O["max_fwd_lat_wz"] = [round(float(v), 2) for v in (vx.max(), np.abs(vy).max(), np.abs(wz).max())]
v1 = lp(np.stack([vx, vy, wz], 1), fs, 1.0); ac = np.gradient(v1, 1 / fs, axis=0)
O["ax_1Hz_pct"], O["ay_1Hz_pct"], O["awz_1Hz_pct"] = [pct(ac[mv, i], (1, 5, 50, 95, 99)) for i in range(3)]
O["acc_max_abs_1Hz"] = [round(float(v), 2) for v in np.abs(ac).max(0)]
# ---- than lac (bo phan < 0.8 Hz), khi di / dung, theo toc do
P50 = np.stack([np.interp(tg, t, P[:, i]) for i in range(3)], 1)
yh = hp(yo, fs, .8)
# van toc lac lay tu TWIST (vi tri odom bi nhieu moc thoi gian cua cau noi: 1 m/s x 20 ms = 2 cm)
lv = hp(np.stack([np.interp(tg, t, V[:, i]) for i in range(3)], 1), fs, .8) * k
lh = hp(np.cumsum(lv, 0) / fs, fs, .8)
eu = Rn.from_quat(np.stack([np.interp(tg, t, Q[:, i]) for i in range(4)], 1)).as_euler("ZYX")
eu = np.unwrap(eu, axis=0); rph = hp(eu, fs, .8)
G = np.stack([np.interp(tg, im[:, 0], im[:, j]) for j in (1, 2, 3)], 1); Gh = hp(G, fs, .8)
vtot = np.hypot(v1[:, 0], v1[:, 1])
O["wobble"] = {}
for nm, m in (("dung", (vtot < .05) & (np.abs(v1[:, 2]) < .05)), ("0.2-0.5", (vtot > .2) & (vtot < .5)), ("0.5-0.9", (vtot >= .5) & (vtot < .9)),
              ("0.9-1.5", (vtot >= .9)), ("thang>0.3", (vtot > .3) & (np.abs(v1[:, 2]) < .15)), ("quay>0.3", np.abs(v1[:, 2]) > .3)):
    if m.sum() < 100:
        continue
    r = lambda x: round(float(x[m].std()), 4)
    O["wobble"][nm] = dict(n_s=round(m.sum() / fs, 1), pos_xyz_m=[r(lh[:, i]) for i in range(3)], vel_xyz=[r(lv[:, i]) for i in range(3)],
                           yaw_rad=r(yh), roll=r(rph[:, 2]), pitch=r(rph[:, 1]), gyro_xyz=[r(Gh[:, i]) for i in range(3)])
# lac do bang LiDAR (10 Hz, can tren: co ca nhieu ICP): du so voi da thuc bac 2 cua so 1.1 s
from scipy.signal import savgol_filter
tu = np.arange(tl[0], tl[-1], .1)
ux, uy, uw = np.interp(tu, tl, Tl[:, 0, 3]), np.interp(tu, tl, Tl[:, 1, 3]), np.interp(tu, tl, Yl)
sx, sy, sw = [savgol_filter(z, 11, 2) for z in (ux, uy, uw)]
cc, ss = np.cos(sw), np.sin(sw)
el = -ss * (ux - sx) + cc * (uy - sy)
vv = np.hypot(np.gradient(sx, .1), np.gradient(sy, .1)); ww = np.gradient(sw, .1)
O["lidar_wobble_lat_yaw"] = {n: [round(float(1.4826 * np.median(np.abs(z[m]))), 4) for z in (el, uw - sw)] for n, m in
                              (("dung", vv < .05), ("di", (vv > .3) & (np.abs(ww) < .15)))}
# tan so buoc tu gyro
m = vtot > .3
fr = 1 / np.median(np.diff(im[:, 0])); ti = np.arange(im[0, 0], im[-1, 0], 1 / 100)
gg = np.stack([np.interp(ti, im[:, 0], im[:, j]) for j in (1, 2, 3)], 1)
mm = np.interp(ti, tg, m.astype(float)) > .5
F, S = welch(gg[mm], 100, nperseg=512, axis=0)
O["gyro_spec_top_hz(x,y,z)"] = []
for j in range(3):
    z = S[:, j] * (F > .8); pk = [i for i in range(1, len(F) - 1) if z[i] > z[i - 1] and z[i] > z[i + 1]]
    O["gyro_spec_top_hz(x,y,z)"].append([round(float(F[i]), 1) for i in sorted(pk, key=lambda i: -z[i])[:4]])
O["imu_hz"] = round(fr, 1)
# ---- khoi hanh / dung: suon len 10-90 % cua |v| (LiDAR-scaled, loc 2 Hz): NGUOI + robot
v2 = np.hypot(vx, vy); ev = {"rise": [], "fall": []}
i = 0
while i < len(v2) - 1:
    if v2[i] < .08 and v2[min(i + int(1.5 * fs), len(v2) - 1)] > .35:
        j = i + int(3 * fs); seg = v2[i:j]; top = np.median(seg[-25:])
        if top > .3:
            a1 = np.argmax(seg > .1 * top); a9 = np.argmax(seg > .9 * top); ev["rise"].append((a9 - a1) / fs); i = j; continue
    if v2[i] > .3 and len(v2) > i + int(2.5 * fs) and v2[i + int(1.5 * fs):i + int(2.5 * fs)].max() < .08 and v2[i] >= v2[i:i + 10].mean():
        seg = v2[i:i + int(2.5 * fs)]; top = v2[i]
        a9 = np.argmax(seg < .9 * top); a1 = np.argmax(seg < .1 * top); ev["fall"].append((a1 - a9) / fs); i += int(2.5 * fs); continue
    i += 1
O["rise_10_90_s"] = [len(ev["rise"]), [round(v, 2) for v in ev["rise"]]]
O["fall_90_10_s"] = [len(ev["fall"]), [round(v, 2) for v in ev["fall"]]]
print(json.dumps(O, indent=1, ensure_ascii=False))
