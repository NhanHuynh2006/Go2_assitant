"""THAM DO (agent HM95, yeu cau coordinator 18:50): kiem tra LANE cho crowd_hm95b (e_b, v_b = huong/toc do MONG MUON, Delta t = 2 s).
Bien the (dinh truoc khi chay):
  a: hanh lang tuan hoan theo x (L=40, W=10), khong nhieu
  b: nhu a nhung hanh lang MO, nguoi ra khoi 1 dau vao lai dau kia o y ngau nhien (nhu HM); Phi tinh tren x trong [5, 35]
  ctrl: doi chung duong cho thuoc do (nhu a, Delta t = 0), KHONG phai ung vien
  c: nhu a + nhieu gauss sigma = 0.15 m/s^2 moi truc (= muc nhieu cua helb/movers), pha doi xung
Mat do 0.3/m^2, v0 ~ N(1.34, 0.26) (>=0.5), dt 0.05 s, T 120 s, Phi trung binh t in [30, 120] s (moi 5 s),
Phi = sum_bins |n+ - n-| / n (dai ngang 0.5 m), null = Phi voi nhan huong xao 20 lan.
Dung: python research/hm95b_lanes.py a|b|c SEED [snap.npy]"""
import sys, os, random, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import crowd_hm95b as HB
variant, seed = sys.argv[1], int(sys.argv[2])
HB.ELL, HB.NOISE = "desired", (0.15 if variant == "c" else 0.0)
if variant == "ctrl":                      # DOI CHUNG duong (khong phai ung vien): nhu a nhung Delta t = 0 (tron)
    HB.H.DT_ELL = 0.0
L, W, dens, T = 40., 10., .3, 120.
periodic = variant in ("a", "c", "ctrl")
rr = random.Random(seed); N = int(dens * L * W); ppl = []
while len(ppl) < N:
    p = np.array([rr.uniform(0, L), rr.uniform(.4, W - .4)])
    if all(np.linalg.norm(p - q["p"]) > .6 for q in ppl):
        s = 1 if len(ppl) % 2 == 0 else -1
        ppl.append(dict(p=p, v=np.zeros(2), v0=max(.5, rr.gauss(1.34, .26)), r=.22, s=s, path=[np.array([p[0] + s * 1e4, p[1]])],
                        wait=0, distracted=False))


def wd(x, y):
    return (y, np.array([0., 1.])) if y < W - y else (W - y, np.array([0., -1.]))


def lane_phi(P, S):
    bins = np.clip((P[:, 1] / .5).astype(int), 0, 19); v = 0.
    for b in range(20):
        m = bins == b
        if m.sum(): v += abs(S[m].sum())
    return v / len(S)


out = []
for k in range(int(T / .05)):
    for pp in ppl:
        pp["path"][0][:] = (pp["p"][0] + pp["s"] * 1e4, pp["p"][1])
    others = None
    if periodic:
        P = np.array([pp["p"] for pp in ppl]); g = (P[:, 0] < 8) | (P[:, 0] > L - 8)
        Vd = np.array([[pp["v0"] * pp["s"], 0.] for pp in ppl])            # buoc MONG MUON cua anh tuan hoan
        others = (np.concatenate([P[g] + [L, 0], P[g] - [L, 0]]), np.concatenate([Vd[g], Vd[g]]), np.full(2 * int(g.sum()), .22))
    HB.step_people(ppl, [], wd, .05, rr, lambda pp: None, others=others)
    for pp in ppl:
        if periodic:
            pp["p"][0] %= L
        elif (pp["s"] > 0 and pp["p"][0] > L) or (pp["s"] < 0 and pp["p"][0] < 0):
            pp["p"] = np.array([0. if pp["s"] > 0 else L, rr.uniform(.4, W - .4)]); pp["v"] = np.zeros(2); pp["w"] = np.zeros(2)
    if k % 100 == 0 and k * .05 >= 30:
        P = np.array([pp["p"] for pp in ppl]); S = np.array([pp["s"] for pp in ppl])
        m = np.ones(len(P), bool) if periodic else (P[:, 0] > 5) & (P[:, 0] < L - 5)
        D = np.hypot(*(P[:, None] - P[None]).transpose(2, 0, 1)); ov = int(((D < .44) & (D > 0)).sum() // 2)
        out.append((lane_phi(P[m], S[m]), np.mean([lane_phi(P[m], np.random.default_rng(j).permutation(S[m])) for j in range(20)]), ov,
                    float(np.mean([pp["v"][0] * pp["s"] for pp in ppl]))))
o = np.array(out)
res = dict(variant=variant, seed=seed, phi=round(o[:, 0].mean(), 3), null=round(o[:, 1].mean(), 3), diff=round(o[:, 0].mean() - o[:, 1].mean(), 3),
           overlap_pairs=round(o[:, 2].mean(), 1), v_dir=round(o[:, 3].mean(), 2))
print(json.dumps(res))
if len(sys.argv) > 3:
    np.save(sys.argv[3], np.array([[*pp["p"], pp["s"]] for pp in ppl]))
