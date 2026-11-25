"""Dieu tra nga: ty le doi lenh |du|/s theo cau hinh/than, 2 s truoc nga, RespModel hoc gi.  venv/bin/python isaac_val/fall_stats.py"""
import csv, glob, json, os, sys
import numpy as np
from collections import defaultdict
D = os.path.dirname(os.path.abspath(__file__))
from math import comb


def rows(tag):
    out = {}
    for r in csv.DictReader(open(f"{D}/res_{tag}.csv")):
        if r["world"].isdigit():
            out[(r["config"], int(r["world"]))] = r
    return out


def jl(tag):
    out = {}
    for f in sorted(glob.glob(f"{D}/res_{tag}_*.jsonl")):
        for l in open(f):
            j = json.loads(l); out[(j["config"], j["world"])] = j
    return out


def short(c):
    return c.replace("p3+geo-haz+gcv", "cand").replace("mppi~t3~nl:ppl=100;ppl_len=0.5", "base~t3~nl").replace("mppi~t3:ppl=100;ppl_len=0.5", "base~t3") \
            .replace(":ppl=32;ppl_len=0.5", "")


def mcn(b, l):
    return min(1, 2 * sum(comb(b + l, i) for i in range(min(b, l) + 1)) / 2 ** (b + l)) if b + l else 1.0


tags = [t for t in sys.argv[1:]] or ["pilotlog", "t3only", "notilt", "fslog_go2"]
R = {t: rows(t) for t in tags if os.path.exists(f"{D}/res_{t}.csv")}
J = {t: jl(t) for t in R}
# 0) tat dinh: pilotlog vs pilot
if "pilotlog" in R:
    P = rows("pilot"); Q = R["pilotlog"]
    K = ["success", "why", "time", "travel", "min_person", "min_static", "foot_t"]
    same = sum(all(P[k][x] == Q[k][x] for x in K) for k in Q if k in P)
    fp = sorted(k for k in P if P[k]["why"] == "nga"); fq = sorted(k for k in Q if Q[k]["why"] == "nga")
    print(f"lap lai pilot: {same}/{len(Q)} luot giong het; nga pilot {len(fp)}, lap lai {len(fq)}, chung {len(set(fp) & set(fq))}")
print("\n| chay | cau hinh | n | ok | nga | va nguoi | va tinh | |du| p95 vx, vy, wz (1/s, gop) | max wz-rate p99 | doi dau wz / 10 s |")
print("|---|---|---|---|---|---|---|---|---|---|")
for t, RR in R.items():
    by = defaultdict(list)
    for (c, w), r in RR.items():
        by[c].append((r, J[t].get((c, w), {})))
    for c, L in by.items():
        n = len(L); ok = sum(r["success"] == "1" for r, _ in L); fall = sum(r["why"] == "nga" for r, _ in L)
        vp = sum(r["col"] == "person" for r, _ in L); vs = sum(r["col"] == "static" for r, _ in L)
        rt = np.array([x for _, j in L for x in j.get("rates", [])]) if L else np.zeros((0, 3))
        p95 = np.percentile(rt, 95, axis=0) if len(rt) else [np.nan] * 3
        p99w = np.percentile(rt[:, 2], 99) if len(rt) else np.nan
        tt = sum(float(r["time"] or 0) for r, _ in L)
        fl = sum(int(r["wz_flip"] or 0) for r, _ in L)
        print(f"| {t} | {short(c)} | {n} | {ok} | {fall} | {vp} | {vs} | {p95[0]:.2f}, {p95[1]:.2f}, {p95[2]:.2f} | {p99w:.2f} | {10 * fl / max(tt, 1):.2f} |")
# 1) 2 s truoc nga
for t in R:
    F = [(k, j) for k, j in J[t].items() if j.get("fall")]
    if not F:
        continue
    print(f"\n### {t}: {len(F)} lan nga (2 s cuoi; cot: t, u(3), v(3), roll, pitch, z)")
    S = []
    for (c, w), j in sorted(F):
        A = np.array(j["fall"]["ring"])
        last = A[A[:, 0] >= A[-1, 0] - 2.0]
        u, v = last[:, 1:4], last[:, 4:7]
        du = np.abs(np.diff(u, axis=0)).max(0) / 0.02 if len(u) > 1 else np.zeros(3)
        rs = j["fall"]["resp"]
        S.append(dict(c=short(c), w=w, t=A[-1, 0], umax=np.abs(u).max(0).round(2).tolist(), u_end=u[-1].round(2).tolist(),
                      wz_lim=float((np.abs(u[:, 2]) > .95).mean()), back=float((u[:, 0] < -0.02).mean()), flips=int(((u[1:, 2] * u[:-1, 2]) < -1e-3).sum()),
                      v_end=v[-1].round(2).tolist(), tilt_max=float(np.abs(last[:, 7:9]).max()), effw=rs.get("effw"), effx=rs.get("effx")))
    for s in S:
        print(f"  {s['c']:18s} w{s['w']} t={s['t']:.1f}s |u|max={s['umax']} u_cuoi={s['u_end']} wz@lim {100*s['wz_lim']:.0f}% lui {100*s['back']:.0f}% doi dau wz {s['flips']} "
              f"v_cuoi={s['v_end']} nghieng max {s['tilt_max']:.2f} | effw={s['effw']} effx(.1,.2,-.1)={None if not s['effx'] else [s['effx'].get(k) for k in ('0.1','0.2','-0.1')]}")
# 2) RespModel hoc gi (cuoi luot, trung vi theo than)
print("\nRespModel cuoi luot (trung vi): g/s moi bo; gain hieu dung")
for t in R:
    for c in sorted({c for c, _ in J[t]}):
        L = [j["resp"] for (cc, _), j in J[t].items() if cc == c and j.get("resp")]
        if not L:
            continue
        med = lambda f: round(float(np.median([f(x) for x in L])), 2)
        print(f"  {t:9s} {short(c):18s} n={len(L)} g x+ {med(lambda x: x['x+'][0])} x- {med(lambda x: x['x-'][0])} y {med(lambda x: x['y+'][0])} w {med(lambda x: x['w+'][0])}"
              f" | eff vx .1/.3/.6 {med(lambda x: x['effx']['0.1'])}/{med(lambda x: x['effx']['0.3'])}/{med(lambda x: x['effx']['0.6'])}"
              f" lui .1 {med(lambda x: x['effx']['-0.1'])} | eff wz .2/.6/1.0 {med(lambda x: x['effw']['0.2'])}/{med(lambda x: x['effw']['0.6'])}/{med(lambda x: x['effw']['1.0'])}")
