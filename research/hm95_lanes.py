"""THAM DO (agent HM95): hanh lang NGUOC CHIEU tuan hoan theo x (L=40, W=10 m, mat do 0.3/m2, v0~N(1.34,0.26)), thuoc do lan =
muc phan tach |n+ - n-|/n theo dai ngang 0.5 m (so voi xao nhan 20 lan). Bien the: literal (=hm95 nhu fastsim), capw (w=v),
v0xK (V0*K), dt0[xK] (Delta t=0: tron, khoang cach tam), dt05 (Delta t=0.5 s), helbv (cong thuc helb vecto hoa, chi de kiem thuoc do).
Dung: python research/hm95_lanes.py BIEN_THE SEED T [snap.npy]"""
import sys, random, numpy as np, json
sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant")
import crowd_hm95 as H
variant, seed = sys.argv[1], int(sys.argv[2])
if variant.startswith("v0x"): H.V0 = 2.1 * float(variant[3:])
if variant.startswith("dt0"): H.DT_ELL = 0.0; H.V0 = 2.1 * float(variant[4:] or 1)
if variant == "dt05": H.DT_ELL = 0.5
if variant == "helbv":       # cong thuc helb (crowd_models) vecto hoa, khong nhieu: chi de kiem thuoc do lan
    import math
    def pf(r, y):
        d = np.maximum(np.hypot(r[:, 0], r[:, 1]), 1e-9); return (7. * np.exp((.44 - d) / .3) / d)[:, None] * r
    def wt(e, f):
        n = f / np.maximum(np.hypot(f[:, 0], f[:, 1]), 1e-9)[:, None]; return .35 + .65 * (1 - n @ e) / 2
    H.pair_force, H.weight, H.CONTACT = pf, wt, True
    H.wall_force = lambda d, n: 2. * math.exp((.22 - d) / .12) * n
L, W, dens, T = 40., 10., .3, float(sys.argv[3]) if len(sys.argv) > 3 else 120.
rr = random.Random(seed); N = int(dens * L * W); ppl = []
while len(ppl) < N:
    p = np.array([rr.uniform(0, L), rr.uniform(.4, W - .4)])
    if all(np.linalg.norm(p - q["p"]) > .6 for q in ppl):
        s = 1 if len(ppl) % 2 == 0 else -1
        ppl.append(dict(p=p, v=np.zeros(2), v0=max(.5, rr.gauss(1.34, .26)), r=.22, s=s, path=[np.array([p[0] + s * 1e4, p[1]])], wait=0, distracted=False))
def wd(x, y): return (y, np.array([0., 1.])) if y < W - y else (W - y, np.array([0., -1.]))
def lane_phi(P, S):
    bins = np.clip((P[:, 1] / .5).astype(int), 0, 19); v, n = 0., 0
    for b in range(20):
        m = bins == b
        if m.sum(): v += abs(S[m].sum()); n += m.sum()
    return v / n
out = []
for k in range(int(T / .05)):
    P = np.array([pp["p"] for pp in ppl]); V = np.array([pp["v"] for pp in ppl])
    g = (P[:, 0] < 8) | (P[:, 0] > L - 8)
    Q = np.concatenate([P[g] + [L, 0], P[g] - [L, 0]]); VQ = np.concatenate([V[g], V[g]])
    for pp in ppl: pp["path"][0][1] = pp["p"][1]
    if variant == "capw":
        for pp in ppl: pp["w"] = pp["v"].copy()
    H.step_people(ppl, [], wd, .05, rr, lambda pp: None, others=(Q, VQ, np.full(len(Q), .22)))
    for pp in ppl: pp["p"][0] %= L; pp["path"][0][0] = pp["p"][0] + pp["s"] * 1e4
    if k % 100 == 0:
        P = np.array([pp["p"] for pp in ppl]); S = np.array([pp["s"] for pp in ppl])
        null = np.mean([lane_phi(P, np.random.default_rng(j).permutation(S)) for j in range(20)])
        D = np.hypot(*(P[:, None] - P[None]).transpose(2, 0, 1)); ov = int(((D < .44) & (D > 0)).sum() // 2)
        vx = np.mean([pp["v"][0] * pp["s"] for pp in ppl])
        out.append((round(k * .05), round(lane_phi(P, S), 3), round(null, 3), ov, round(vx, 2)))
print(variant, seed, out)
np.save(sys.argv[4] if len(sys.argv) > 4 else "/dev/null", np.array([[*pp["p"], pp["s"]] for pp in ppl]))
