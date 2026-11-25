#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiem fit_real.py: du lieu tong hop tu DUNG fastsim.Sim.substep (tham so biet truoc), lenh = lich sysid_real that,
odom 50 Hz nhan 1/1.22, rung moc nhan. So tham so khop voi tham so that + do phu CI.
  python test_fit.py OUTDIR N"""
import os, sys
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import json, types
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import fastsim, sysid_real, fit_real
K = 1.22


def gen(rng, P, stage, which, path):
    s = fastsim.Sim.__new__(fastsim.Sim)
    s.DT, s.rng = .005, rng
    s.gain, s.vsat, s.back, s.wob = np.array(P["gain"]), P["vsat"], P["back"], np.array(P["wob"])
    s.tau, s.delay = np.array(P["tau"]), P["delay"]
    s.sway, s.x, s.v, s.cmd, s.cmdq = np.zeros(3), np.zeros(3), np.zeros(3), np.zeros(3), []
    s.clock = types.SimpleNamespace(t=0.0); s.t0, s.k, s.tmax, s.crowd, s.carts = 0.0, 0, 1e9, None, []
    s.r = types.SimpleNamespace(); s.sense = s.check = lambda: None
    cmd, od, px = [], [], s.x.copy()
    for nm, *u, T in sysid_real.schedule(stage, which):
        for _ in range(int(round(T / .02))):
            cmd.append([s.clock.t, *u]); s.cmdq.append((s.clock.t + s.delay - 1e-9, np.array(u, float)))
            for _k in range(4):
                s.substep(.005)
            d = s.x - px; px = s.x.copy(); y = s.x[2]
            c, sn = np.cos(y), np.sin(y)
            # twist: than, gom than lac (sai phan cua tu the that) -> dung nhu odom that
            vb = np.array([c * d[0] + sn * d[1], -sn * d[0] + c * d[1], d[2]]) / .02
            t = s.clock.t - .01                                    # twist = trung binh buoc -> moc giua buoc
            od.append([t + abs(rng.normal() * .004), t, t, s.x[0] / K, s.x[1] / K, .3, 0, 0, np.sin(y / 2), np.cos(y / 2), vb[0] / K, vb[1] / K, 0, 0, 0, vb[2]])
    np.savez(path, cmd=np.array(cmd), odom=np.array(od))


if __name__ == "__main__":
    out, N = sys.argv[1], int(sys.argv[2])
    os.makedirs(out, exist_ok=True)
    rows = []
    for i in range(N):
        rng = np.random.default_rng(1000 + i); u = rng.uniform
        # regime go2 cua fastsim nhung tau/tre/bao hoa rong hon (bao ca truong hop xau)
        P = dict(gain=[u(.75, 1.2), u(.7, 1.2), u(.8, 1.1)], vsat=u(.5, 2.0), back=u(.8, 1.2), tau=[u(.12, .45), u(.12, .4), u(.08, .3)],
                 delay=float(rng.choice([.04, .08, .12, .16, .2])), wob=[.006, .006, .015])
        fs = []
        for st in (1, 2, 3):
            for w in ("fit", "test"):
                p = "%s/syn%d_s%d_%s.npz" % (out, i, st, w); gen(rng, P, st, w, p); fs.append(p)
        print("== ", i, {k: np.round(v, 3).tolist() for k, v in P.items()}, flush=True)
        R = fit_real.main(["--fit"] + fs[0::2] + ["--test"] + fs[1::2] + ["--scale", str(K), "--full", "--quick"])
        # fastsim Euler bac 1 h=.005 -> tau tuong duong; lenh tac dung tu dau buoc -> tre hieu dung = delay - h
        tr = dict(gx=P["gain"][0], gy=P["gain"][1], gw=P["gain"][2], back=P["back"], d=P["delay"] - .005, cx=1 / P["vsat"])
        for k, n in enumerate(("taux", "tauy", "tauw")):
            tr[n] = -.005 / np.log(1 - .005 / P["tau"][k])
        for n, v in tr.items():
            q = R["params"][n]
            rows.append((n, v, q["value"], q["ci95"][0] <= v <= q["ci95"][1]))
    print("\nTHAM SO  n  sai so tuyet doi: trung vi  p90 | sai so tuong doi trung vi | CI95 phu")
    for n in ("gx", "gy", "gw", "taux", "tauy", "tauw", "d", "back", "cx"):
        r = [x for x in rows if x[0] == n]; e = np.array([abs(x[2] - x[1]) for x in r]); rel = np.array([abs(x[2] / x[1] - 1) for x in r])
        print("%-5s %2d  %.4f  %.4f | %.1f %% | %d/%d" % (n, len(r), np.median(e), np.percentile(e, 90), 100 * np.median(rel), sum(x[3] for x in r), len(r)))
    json.dump(rows, open(out + "/test_fit.json", "w"), default=str)
