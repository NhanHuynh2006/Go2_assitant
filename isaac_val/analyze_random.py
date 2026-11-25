"""Bai random (giong pipeline/sysid.py): gain co dieu kien + sai so du doan vong ho cua cac mo hinh fastsim tren ban ghi Isaac va CHAMP.
   venv/bin/python isaac_val/analyze_random.py raw_flat_random.npz raw_rough_random.npz"""
import sys, json
import numpy as np
H = 50


def load_isaac(f):
    r = np.load(f)["rec"]
    return [dict(x=r[:, e, 0], y=r[:, e, 1], yaw=np.unwrap(r[:, e, 5]), u=r[:, e, 9:12], v=r[:, e, 6:9], bad=r[:, e, 12] > 0) for e in range(r.shape[1])]


def load_champ(f="../results/sysid.npz"):
    d = np.load(f); L, seg = d["log"], d["seg"]
    out = []
    ed = [0] + list(seg) + [len(L)]
    for a, b in zip(ed[::2], ed[1::2]):
        q = L[a:b]
        if len(q) < 200:
            continue
        # moc thoi gian mo phong (cot 1) -> noi suy deu 50 Hz
        t = q[:, 1]; k = np.r_[True, np.diff(t) > 1e-6]; q, t = q[k], t[k]
        T = np.arange(t[0], t[-1], 1 / H)
        x, y, w = (np.interp(T, t, c) for c in (q[:, 2], q[:, 3], np.unwrap(q[:, 4])))
        i = np.searchsorted(t, T, "right") - 1
        u = q[i, 5:8]
        out.append(dict(x=x, y=y, yaw=w, u=u, v=None, bad=np.zeros(len(T), bool)))
    return out


def gains(runs):
    rows = []
    for r in runs:
        u = r["u"]; ch = np.r_[0, np.where(np.abs(np.diff(u, axis=0)).sum(1) > 0)[0] + 1, len(u)]
        for a, b in zip(ch[:-1], ch[1:]):
            if b - a < 50 or r["bad"][a:b].any():
                continue
            c, d = b - 30, b - 1                                   # 0.6 s cuoi doan
            dt = (d - c) / H; h = r["yaw"][c:b].mean()
            dx, dy = r["x"][d] - r["x"][c], r["y"][d] - r["y"][c]
            v = [(dx * np.cos(h) + dy * np.sin(h)) / dt, (-dx * np.sin(h) + dy * np.cos(h)) / dt, (r["yaw"][d] - r["yaw"][c]) / dt]
            rows.append([*u[a], *v])
    return np.array(rows)


def slope(u, v):
    if len(u) < 8:
        return None
    k = float(u @ v / (u @ u))
    rng = np.random.default_rng(0); n = len(u)
    bs = []
    for _ in range(500):
        i = rng.integers(0, n, n); bs.append(float(u[i] @ v[i] / (u[i] @ u[i])))
    return round(k, 2), round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2), n


MODELS = {
    "ly tuong (v=lenh)": dict(g=(1, 1, 1), tau=(.02, .02, .02), d=.0),
    "fastsim champ (giua)": dict(g=(.95, .965, .85), tau=(.16, .16, .25), d=.05, vsat=.29, back=1.22),
    "fastsim go2/DYN (giua)": dict(g=(.95, .95, .90), tau=(.28, .22, .15), d=.10),
    "fastsim champ2 (giua)": dict(g=(.99, .99, 1.05), tau=(.12, .12, .10), d=.025, lim=(.3, .25, .5), off=-.0525),
}


def rollout(m, x, yaw, v0, U, n):
    """bac 1 + tre; U: lenh tu k0 - 15 mau. Tra vi tri sau n buoc."""
    p = np.array([0., 0., 0.]); v = v0.copy(); dd = int(round(m["d"] * H))
    for k in range(n):
        u = U[15 + k - dd]
        t = np.array(m["g"]) * u
        if "vsat" in m and u[0] > 0: t[0] = m["vsat"] * np.tanh(t[0] / m["vsat"])
        if u[0] < 0: t[0] *= m.get("back", 1.0)
        if "lim" in m: t = np.clip(t, -np.array(m["lim"]), m["lim"])
        if "off" in m and np.abs(u).sum() > .02: t[0] += m["off"]
        v = v + np.minimum(1, (1 / H) / np.array(m["tau"])) * (t - v)
        c, s = np.cos(p[2]), np.sin(p[2])
        p = p + np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2]]) / H
    return p


def pred(runs, m, sec, nmax=400):
    rng = np.random.default_rng(1); E = []; n = int(sec * H)
    for _ in range(nmax):
        r = runs[rng.integers(len(runs))]
        if len(r["x"]) < n + 60:
            continue
        k = rng.integers(20, len(r["x"]) - n - 1)
        if r["bad"][k - 16:k + n].any():
            continue
        h = r["yaw"][k - 10:k + 1].mean(); dt = 10 / H
        v0 = np.array([((r["x"][k] - r["x"][k - 10]) * np.cos(h) + (r["y"][k] - r["y"][k - 10]) * np.sin(h)) / dt,
                       (-(r["x"][k] - r["x"][k - 10]) * np.sin(h) + (r["y"][k] - r["y"][k - 10]) * np.cos(h)) / dt, (r["yaw"][k] - r["yaw"][k - 10]) / dt])
        p = rollout(m, 0, 0, v0, r["u"][k - 15:k + n + 1], n)
        c, s = np.cos(r["yaw"][k]), np.sin(r["yaw"][k])
        dx, dy = r["x"][k + n] - r["x"][k], r["y"][k + n] - r["y"][k]
        q = np.array([c * dx + s * dy, -s * dx + c * dy, r["yaw"][k + n] - r["yaw"][k]])
        E.append([np.hypot(*(p - q)[:2]), abs(p[2] - q[2])])
    E = np.array(E)
    return [round(float(x), 3) for x in (E[:, 0].mean(), np.percentile(E[:, 0], 90), E[:, 1].mean())] + [len(E)]


out = {}
for name, runs in [(f.replace("raw_", "").replace(".npz", ""), load_isaac(f)) for f in sys.argv[1:]] + [("CHAMP Gazebo", load_champ())]:
    R = gains(runs)
    s = np.hypot(R[:, 0], R[:, 1])
    L = {"vx 0.05-0.2": (0, (R[:, 0] > .05) & (R[:, 0] <= .2)), "vx .2-.4": (0, (R[:, 0] > .2) & (R[:, 0] <= .4)), "vx .4-.6": (0, R[:, 0] > .4),
         "vx lui": (0, R[:, 0] < -.05), "vy |.05-.15|": (1, (abs(R[:, 1]) > .05) & (abs(R[:, 1]) <= .15)), "vy |.15-.3|": (1, abs(R[:, 1]) > .15),
         "wz tai cho": (2, (s < .05) & (abs(R[:, 2]) > .2)), "wz khi |v|>.25": (2, (s > .25) & (abs(R[:, 2]) > .2))}
    print("\n###", name, "so doan", len(R))
    g = {}
    for k, (ax, mk) in L.items():
        g[k] = slope(R[mk, ax], R[mk, 3 + ax]); print(f"| {k} | gain, CI95, n: {g[k]} |")
    pe = {}
    for mn, m in MODELS.items():
        pe[mn] = {h: pred(runs, m, h) for h in (1.0, 2.0)}
        print(f"| du doan {mn} | 1 s: {pe[mn][1.0]} | 2 s: {pe[mn][2.0]} |  (tb m, p90 m, yaw rad, n)")
    out[name] = dict(gain=g, pred=pe)
json.dump(out, open("sysid_random.json", "w"), indent=1)
