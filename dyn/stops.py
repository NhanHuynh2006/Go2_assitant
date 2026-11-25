#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stops.py - cac lan DUNG tu nhien trong ban ghi (nguoi nha can remote): khop v = v0 exp(-(t-t0)/tau) + quang duong dung.
tau gom ca nguoi nha can + loc remote cua firmware -> CAN TREN cho tau robot (chieu giam toc). Khong cho biet tre."""
import os, sys
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bagio
H = os.path.expanduser("~/go2_maps/")
out = []
for nm, f, tp, k in (("lab", "lab_20260911_160656_slim/lab_20260911_160656_slim_0.db3", "/utlidar/robot_odom", 1.215),
                     ("lab2", "lab2_20260915_175037/lab2_20260915_175037_0.db3", "/go2/odom", 1.215),
                     ("yard", "yard_20260916_104758/yard_20260916_104758_0.db3", "/go2/odom", 1.027)):
    M = np.array([(m[0], *m[3][:2], *m[5][:2]) for _, m in bagio.read(H + f, tp)])
    M = M[np.argsort(M[:, 0])]; _, i = np.unique(M[:, 0], return_index=True); M = M[i]
    t = np.arange(M[0, 0], M[-1, 0], .02)
    sp = np.hypot(np.interp(t, M[:, 0], M[:, 3]), np.interp(t, M[:, 0], M[:, 4])) * k
    P = np.stack([np.interp(t, M[:, 0], M[:, j]) for j in (1, 2)], 1) * k
    s = np.convolve(sp, np.ones(15) / 15, "same")
    i = 60
    while i < len(t) - 120:
        # dung han: >=1 s duoi 0.06 va truoc do 1.5 s dang di >0.3
        if s[i:i + 45].max() < .06 and s[i - 1] >= .06 and s[max(0, i - 75):i - 35].max() > .3:
            seg = slice(i - 75, i + 30); tt = t[seg] - t[i - 75]; y = sp[seg]
            fn = lambda q: np.where(tt < q[1], q[0], q[0] * np.exp(-(tt - q[1]) / q[2])) - y
            b = min((least_squares(fn, [y[:30].mean(), g, .3], bounds=([.05, .0, .03], [2, 1.6, 2])) for g in (.2, .6, 1.0)), key=lambda r: r.cost)
            v0, t0, tau = b.x
            j = i - 75 + int(t0 / .02); d = float(np.hypot(*(P[min(i + 30, len(P) - 1)] - P[j])))
            out.append((nm, v0, tau, d)); print("%s t=%.1f v0=%.2f tau=%.2f  quang duong tu luc bat dau giam = %.2f m (%.2f s x v0), rms %.2f" % (nm, t[i] - t[0], v0, tau, d, d / v0, np.sqrt(2 * b.cost / len(y))))
            i += 100
        i += 1
q = np.array([o[2] for o in out if o[1] > .3]); e = np.array([o[3] / o[1] for o in out if o[1] > .3])
print("n=%d  tau trung vi %.2f (min %.2f max %.2f);  d/v0 trung vi %.2f s (min %.2f max %.2f)" % (len(q), np.median(q), q.min(), q.max(), np.median(e), e.min(), e.max()))
