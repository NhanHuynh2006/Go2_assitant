"""Kiem tra hop ly cho crowd_hm95.py (agent HM95, THAM DO). Chay: OPENBLAS_NUM_THREADS=1 venv/bin/python research/hm95_sanity.py OUTDIR
1) gradient giai tich vs sai phan trung tam; 2) 2 nguoi doi dau hanh lang 10 m; 3) hanh lang nguoc chieu -> lan (thong ke thu tu lan).
Dung CHINH step_people cua crowd_hm95 (cung code chay trong fastsim). So sanh 'helb' bang crowd_models.pm_step dong bang (chi import)."""
import sys, os, math, random, json, types
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, R)
import numpy as np
import crowd_hm95 as H
import crowd_models as CM
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
os.makedirs(OUT, exist_ok=True)
res = {}

# 1) gradient
rng = np.random.default_rng(0)
r = rng.uniform(-3, 3, (2000, 2)); y = rng.uniform(-2, 2, (2000, 2)) * rng.uniform(0, 1, (2000, 1))
b = H.semi_minor_b(r, y); keep = b > 0.05                      # tranh diem ky di b=0 (a nam tren doan buoc cua b)
r, y = r[keep], y[keep]
h = 1e-5; fd = np.zeros_like(r)
for k in range(2):
    dp = np.zeros(2); dp[k] = h
    fd[:, k] = -(H.potential(r + dp, y) - H.potential(r - dp, y)) / (2 * h)
an = H.pair_force(r, y)
rel = np.abs(an - fd).max(1) / np.maximum(np.abs(fd).max(1), 1e-8)
res["grad"] = dict(n=int(len(r)), max_abs_err=float(np.abs(an - fd).max()), max_rel_err=float(rel.max()), median_rel=float(np.median(rel)))
st = H.pair_force(np.array([[1.0, 0.0]]), np.zeros((1, 2)))[0]
res["grad"]["static_check"] = [float(st[0]), float(7.0 * math.exp(-1 / .3))]   # y=0 -> b=|r|, |f| = V0/sigma e^{-d/sigma}
assert rel.max() < 1e-4, res["grad"]


def corridor_wall(W):
    def wd(x, yy):
        return (yy, np.array([0., 1.])) if yy < W - yy else (W - yy, np.array([0., -1.]))
    return wd


class Stub:            # gia lap FastCrowd cho crowd_models.pm_step (helb): khong robot
    def __init__(self, people, W, rng):
        self.people, self.robots, self.rng = people, [], rng
        self._wall_dist = corridor_wall(W)
        self.sim = types.SimpleNamespace(x=np.zeros(3), v=np.zeros(3))

    def _new_goal(self, pp):
        pp["path"] = [pp["goal"].copy()]


def step(model, st, dt):
    if model == "hm95":
        H.step_people(st.people, [], st._wall_dist, dt, st.rng, st._new_goal)
    else:
        CM.pm_step(st, dt, model)


# 2) doi dau: hanh lang dai 10 m, rong 10 m (HM: walkway 10 m), nguoi o x=0.5 va 9.5
def headon(model, dy, v0=1.2, L=10., W=10., T=20.):
    rr = random.Random(1)
    ppl = [dict(p=np.array([.5, W / 2]), v=np.zeros(2), v0=v0, r=.22, goal=np.array([L + 50, W / 2]), path=[], wait=0, distracted=False),
           dict(p=np.array([L - .5, W / 2 + dy]), v=np.zeros(2), v0=v0, r=.22, goal=np.array([-50, W / 2 + dy]), path=[], wait=0, distracted=False)]
    for pp in ppl: pp["path"] = [pp["goal"].copy()]
    st = Stub(ppl, W, rr); dmin, lat, tpass = 9., 0., None
    for k in range(int(T / .05)):
        step(model, st, .05)
        d = float(np.linalg.norm(ppl[0]["p"] - ppl[1]["p"])); dmin = min(dmin, d)
        lat = max(lat, abs(ppl[0]["p"][1] - W / 2), abs(ppl[1]["p"][1] - W / 2 - dy))
        if tpass is None and ppl[0]["p"][0] > ppl[1]["p"][0]: tpass = (k + 1) * .05
    return dict(min_centre_dist=round(dmin, 3), min_surface_gap=round(dmin - .44, 3), max_lateral_dev=round(lat, 3),
                passed=tpass is not None, t_pass=tpass, x_final=[round(float(ppl[0]["p"][0]), 2), round(float(ppl[1]["p"][0]), 2)])


res["headon"] = {m: {str(dy): headon(m, dy) for dy in (0.0, 0.05, 0.3)} for m in ("hm95", "helb")}


# 3) hanh lang nguoc chieu: L=40, W=10, mat do 0.3/m^2 (HM Fig. 3), v0 ~ N(1.34, 0.26), vao lai o dau hanh lang vi tri ngau nhien
def lanes(model, seed, L=40., W=10., dens=.3, T=90., snap=None):
    rr = random.Random(seed); N = int(dens * L * W); ppl = []
    while len(ppl) < N:
        p = np.array([rr.uniform(0, L), rr.uniform(.4, W - .4)])
        if all(np.linalg.norm(p - q["p"]) > .6 for q in ppl):
            s = 1 if len(ppl) % 2 == 0 else -1
            ppl.append(dict(p=p, v=np.zeros(2), v0=max(.5, rr.gauss(1.34, .26)), r=.22, s=s, goal=np.array([L / 2 + s * 1e4, 0.]),
                            path=[], wait=0, distracted=False))
    for pp in ppl:
        pp["goal"][1] = pp["p"][1]; pp["path"] = [pp["goal"].copy()]
    st = Stub(ppl, W, rr); phis, nulls, ov = [], [], 0
    for k in range(int(T / .05)):
        for pp in ppl:                                  # huong mong muon = doc hanh lang (diem dich xa o cung y)
            pp["path"][0][1] = pp["p"][1]
        step(model, st, .05)
        for pp in ppl:                                  # ra khoi hanh lang -> vao lai dau kia, y ngau nhien (HM: 'enter at random positions')
            if (pp["s"] > 0 and pp["p"][0] > L) or (pp["s"] < 0 and pp["p"][0] < 0):
                pp["p"] = np.array([0. if pp["s"] > 0 else L, rr.uniform(.4, W - .4)]); pp["v"] = np.zeros(2); pp["w"] = np.zeros(2)
        if k % 20 == 0:
            P = np.array([pp["p"] for pp in ppl]); S = np.array([pp["s"] for pp in ppl])
            D = np.hypot(*(P[:, None] - P[None]).transpose(2, 0, 1)); ov += int(((D < .44) & (D > 0)).sum() // 2)
            mid = (P[:, 0] > 5) & (P[:, 0] < L - 5)

            def phi(S_):
                v = []
                for i in np.where(mid)[0]:
                    nb = (np.abs(P[:, 1] - P[i, 1]) < .4) & (np.abs(P[:, 0] - P[i, 0]) < 5) & (np.arange(len(P)) != i)
                    if nb.sum(): v.append(((S_[nb] == S_[i]).sum() - (S_[nb] != S_[i]).sum()) / nb.sum())
                return float(np.mean(np.square(v))) if v else np.nan
            if k * .05 >= 30:
                phis.append(phi(S)); nulls.append(np.mean([phi(np.random.default_rng(k + j).permutation(S)) for j in range(5)]))
        if snap is not None and abs(k * .05 - T + .05) < 1e-6:
            snap.append((np.array([pp["p"] for pp in ppl]), np.array([pp["s"] for pp in ppl])))
    return float(np.nanmean(phis)), float(np.nanmean(nulls)), ov


snaps = {}
res["lanes"] = {}
for m in ("hm95", "helb"):
    rows = []
    for sd in range(3):
        sn = [] if sd == 0 else None
        rows.append(lanes(m, sd, snap=sn))
        if sn: snaps[m] = sn[0]
    res["lanes"][m] = dict(phi=[round(a, 3) for a, _, _ in rows], phi_null=[round(b, 3) for _, b, _ in rows],
                           overlap_pairs_per_frame=[round(c / 90., 2) for _, _, c in rows])
res["stats_hm95"] = dict(H.STATS)
json.dump(res, open(os.path.join(OUT, "hm95_sanity.json"), "w"), indent=1)
print(json.dumps(res, indent=1))
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(10, 5.5))
    for a, m in zip(ax, ("hm95", "helb")):
        P, S = snaps[m]
        a.scatter(P[S > 0, 0], P[S > 0, 1], s=14, c="k", label="-> phai"); a.scatter(P[S < 0, 0], P[S < 0, 1], s=14, facecolors="none", edgecolors="r", label="<- trai")
        a.set_xlim(0, 40); a.set_ylim(0, 10); a.set_aspect("equal"); a.set_title(f"{m}: t = 90 s, mat do 0.3/m^2 (THAM DO)")
    ax[0].legend(loc="upper right", fontsize=7); fig.tight_layout(); fig.savefig(os.path.join(OUT, "hm95_lanes.png"), dpi=110)
except Exception as ex:                                  # noqa: BLE001
    print("plot fail", ex)
