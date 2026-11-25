"""mppi 'cung ten' o hai ban code (chup 23:01 va hien tai): buoc dieu khien va ket qua co giong khong?"""
import os, sys, importlib.util, csv, glob
for k in ("OPENBLAS_NUM_THREADS",): os.environ[k] = "1"
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
def imp(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
a, b = imp(H + "/snap/nav_local.py", "a_nl"), imp(H + "/../nav_local.py", "b_nl")
rng = np.random.default_rng(0); E = []
for t in range(60):
    yy, xx = np.mgrid[0:100, 0:100]; f = np.full((100, 100), 9., np.float32)
    for _ in range(6): c = rng.uniform(-4, 4, 2); f = np.minimum(f, np.maximum(np.hypot(xx * .1 - 5 - c[0], yy * .1 - 5 - c[1]) - .3, 0)).astype(np.float32)
    P = np.stack([np.linspace(0, 4, 41), np.sin(np.linspace(0, 4, 41)) * rng.uniform(-1, 1)], 1); ppl = [(*rng.uniform(-2, 2, 2), *rng.uniform(-1, 1, 2), .25) for _ in range(3)]; us = []
    for m in (a, b):
        q = m.MPPI(seed=t, vmax=(.595, .3, 1.), vmin=(-.2, -.3, -1.)); q.people_cap = True; q.w["ppl"] = 32
        for _ in range(3): u, _i = q.step(np.zeros(3), np.array([.2, 0, 0]), f, (.1, -5., -5.), P, np.linspace(0, 4, 41), (4., 0.), people=ppl)
        us.append(u)
    E.append(np.abs(us[0] - us[1]).max())
E = np.array(E); print("lech lenh sau 3 buoc MPPI (60 tinh huong): =0: %d; max %.2g; >1e-6: %d" % ((E == 0).sum(), E.max(), (E > 1e-6).sum()))
g = a.OccGrid(); gb = b.OccGrid(); rr = np.random.default_rng(2); d = 0
for k in range(40):
    x = rr.uniform(-8, 8, 4)
    for q in (g, gb): q.mark_box(x[0], x[1], abs(x[2]) / 8 + .2, abs(x[3]) / 8 + .2, 0.)
for k in range(30):
    s, e = rr.uniform(-9, 9, 2), rr.uniform(-9, 9, 2); d += a.plan(g, s, e)[0] != b.plan(gb, s, e)[0]
print("A*/plan khac nhau: %d/30" % d)
def L(d): return {(r["world"], r["config"]): r for f in glob.glob(f"{H}/../results/{d}/w*.csv") for r in csv.DictReader(open(f)) if r["success"] != ""}
A, B = L("dev3"), L("ceil1")
for c in ("mppi", "mppi:ppl=32"):
    K = [k for k in A if k[1] == c and k in B]; up = sum(int(B[k]["success"]) > int(A[k]["success"]) for k in K); dn = sum(int(B[k]["success"]) < int(A[k]["success"]) for k in K)
    print(c, "dev3 %d -> ceil1 %d / %d; doi ket qua +%d/-%d (%.0f%%)" % (sum(int(A[k]["success"]) for k in K), sum(int(B[k]["success"]) for k in K), len(K), up, dn, 100 * (up + dn) / len(K)))
