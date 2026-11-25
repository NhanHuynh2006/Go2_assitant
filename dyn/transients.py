#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transients.py - (khong co lenh) cac lan TANG/GIAM toc nhanh nhat trong ban ghi that: can tren cho tau, can duoi cho a_max.
Dung twist odom (than) x ti le LiDAR, trung binh truot 0.2 s (gan 1 nua chu ky buoc)."""
import sys, os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio
H = os.path.expanduser("~/go2_maps/")
for nm, f, tp, k in (("lab", "lab_20260911_160656_slim/lab_20260911_160656_slim_0.db3", "/utlidar/robot_odom", 1.215),
                     ("lab2", "lab2_20260915_175037/lab2_20260915_175037_0.db3", "/go2/odom", 1.215),
                     ("yard", "yard_20260916_104758/yard_20260916_104758_0.db3", "/go2/odom", 1.027)):
    M = np.array([(m[0], *m[5][:2], m[6][2]) for _, m in bagio.read(H + f, tp)])
    M = M[np.argsort(M[:, 0])]
    _, i = np.unique(M[:, 0], return_index=True); M = M[i]
    fs = 100.0
    t = np.arange(M[0, 0], M[-1, 0], 1 / fs)
    v = np.stack([np.interp(t, M[:, 0], M[:, j]) for j in (1, 2, 3)], 1) * [k, k, 1]
    n = int(.2 * fs); s = np.stack([np.convolve(v[:, j], np.ones(n) / n, "same") for j in range(3)], 1)
    print("==", nm, "T=%.0f s" % (t[-1] - t[0]), "bat dau/dung:")
    for ax, name, thr in ((0, "vx", .3), (2, "wz", .5)):
        for W in (.2, .4, .6):
            w = int(W * fs); d = (s[w:, ax] - s[:-w, ax]) / W
            print("  %s: gia toc tb tren cua so %.1f s: p99 +%.2f -%.2f | max +%.2f -%.2f" % (name, W, np.percentile(d, 99), -np.percentile(d, 1), d.max(), -d.min()))
        # khop bac 1 toan phan (nguoi + robot): suon tu 0 -> muc v, va v -> 0
        ev = []
        x = s[:, ax]
        j = 0
        while j < len(x) - int(1.5 * fs):
            a = x[j]; b = np.median(x[j + int(.9 * fs):j + int(1.3 * fs)])
            if abs(b - a) > thr and np.std(x[max(0, j - 30):j + 1]) < .08 * abs(b - a) + .02 and np.std(x[j + int(.9 * fs):j + int(1.3 * fs)]) < .2 * abs(b - a):
                y = (x[j:j + int(1.3 * fs)] - a) / (b - a)
                h = np.argmax(y > .1); e = np.argmax(y > .9)
                if 0 < h < 30 and e > h:
                    ev.append(((e - h) / fs, round(float(a), 2), round(float(b), 2)))
                    j += int(1.3 * fs); continue
            j += 5
        ev.sort()
        print("  %s: %d su kien 10-90 %%; nhanh nhat: %s" % (name, len(ev), ev[:6]))
