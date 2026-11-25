"""Khop lai dong hoc CHAMP (23/11): cat lenh theo gait.yaml (0.3/0.25/0.5) + troi lui hang so khi co buoc chan.
So voi mo hinh cu cua fastsim (tanh 0.29, lui x1.22, wz x0.85). Chia doi ban ghi: khop nua dau, cham nua sau va nguoc lai.
   venv/bin/python pipeline/sysid_fit2.py"""
import os, itertools
import numpy as np
H = 50
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = np.load(R + "/results/sysid.npz"); L, seg = d["log"], d["seg"]
ed = [0] + list(seg) + [len(L)]
runs = []
for a, b in zip(ed[::2], ed[1::2]):
    q = L[a:b]; t = q[:, 1]; k = np.r_[True, np.diff(t) > 1e-6]; q, t = q[k], t[k]
    if len(q) < 200 or t[-1] - t[0] < 4: continue
    T = np.arange(t[0], t[-1], 1 / H)
    i = np.searchsorted(t, T, "right") - 1
    runs.append(dict(x=np.interp(T, t, q[:, 2]), y=np.interp(T, t, q[:, 3]), yaw=np.interp(T, t, np.unwrap(q[:, 4])), u=q[i, 5:8]))


def cur(u, m):
    t = np.array(m["g"]) * u
    if "vsat" in m:
        t[..., 0] = np.where(t[..., 0] > 0, m["vsat"] * np.tanh(t[..., 0] / m["vsat"]), t[..., 0] * m["back"])
    if "lim" in m:
        t = np.clip(t, -np.array(m["lim"]), m["lim"])
    if "off" in m:
        t[..., 0] += m["off"] * (np.abs(u).sum(-1) > .02)
    return t


def err(m, rs, sec):
    n = int(sec * H); dd = int(round(m["d"] * H)); E = []
    for r in rs:
        tg = cur(r["u"].copy(), m); a = np.minimum(1, (1 / H) / np.array(m["tau"]))
        N = len(r["x"]); V = np.zeros((N, 3))
        for k in range(1, N):
            V[k] = V[k - 1] + a * (tg[max(0, k - dd)] - V[k - 1])
        # cua so khong chong, dan do tu k voi van toc mo hinh (trang thai an)
        for k in range(25, N - n, n):
            h0 = r["yaw"][max(0, k - 10):k + 10].mean(); p = np.array([0., 0., h0])
            for j in range(k, k + n):
                c, s = np.cos(p[2]), np.sin(p[2]); p = p + np.array([V[j, 0] * c - V[j, 1] * s, V[j, 0] * s + V[j, 1] * c, V[j, 2]]) / H
            E.append([np.hypot(p[0] - r["x"][k + n] + r["x"][k], p[1] - r["y"][k + n] + r["y"][k]),
                      abs(p[2] - r["yaw"][max(0, k + n - 10):k + n + 10].mean())])
    return np.array(E)


old = dict(g=(.95, .965, .85), tau=(.16, .16, .25), d=.05, vsat=.29, back=1.22)
new = dict(g=(1, 1, 1), lim=(.3, .25, .5), off=-.053, tau=(.16, .16, .25), d=.05)
ideal = dict(g=(1, 1, 1), tau=(.02,) * 3, d=0.)
for nm, m in (("ly tuong", ideal), ("cu (tanh)", old), ("cu, bo troi lui", dict(old, back=1.0)), ("moi: cat + troi", new), ("chi cat", dict(new, off=0.))):
    print("%-18s" % nm, *["%gs: %.3f m p90 %.3f, yaw %.3f (n=%d)" % (s, *(lambda e: (e[:, 0].mean(), np.percentile(e[:, 0], 90), e[:, 1].mean(), len(e)))(err(m, runs, s))) for s in (1, 2)])
# khop tau/tre/troi/gain wz: kiem cheo 2 nua
half = (runs[::2], runs[1::2])
grid = [dict(new, tau=(a, a, w), d=dl, off=o, g=(gx, gx, gw)) for a, w, dl, o, gx, gw in
        itertools.product((.08, .12, .16, .22), (.08, .15, .25), (0, .04, .08), (-.045, -.06), (1., .95), (1., 1.1))]
for tr, te in (half, half[::-1]):
    sc = [(lambda e: e[:, 0].mean() + .3 * e[:, 1].mean())(err(m, tr, 1)) for m in grid]
    b = grid[int(np.argmin(sc))]
    print("khop:", {k: b[k] for k in ("g", "tau", "d", "off")}, "| nua kia:", *["%s %.3f/%.3f" % (nm, *err(m, te, 1).mean(0)) for nm, m in (("khop", b), ("moi", new), ("cu", old))])
