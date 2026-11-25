"""POST-HOC, EXPLORATORY (not pre-registered): why is C1-B1 larger in Gazebo TEST (+15.0) than in fastsim (+8.4 / +12.2)?
Written 25/11 after the Gazebo primary result was known; nothing here changes the registered result.

Per episode (Gazebo TEST, results/GZ_TEST) from episodes.jsonl (per 0.1 s: robot pose, true pedestrians, tracker tracks):
  ghost step   : some track lies > GHOST_D from every true pedestrian AND within NEAR m of the robot
  miss step    : some true pedestrian within NEAR m of the robot has no track within MATCH_D
Questions:
  Q1 ghost / miss burden by config
  Q2 success by ghost-burden tercile (pooled cut points), C1-B1 gap per tercile
  Q3 worlds where fastsim (same world) succeeded but Gazebo failed: ghost burden vs worlds that succeeded in both
  Q4 failure types (person contact / static contact / no contact = stuck or timeout), Gazebo vs fastsim same worlds
"""
import csv, glob, json, math, os, statistics as st
from collections import defaultdict

GHOST_D, MATCH_D, NEAR = 1.0, 1.0, 3.0
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
B1 = "mppi~t3~nl:ppl=100;ppl_len=0.5"
N = {C1: "C1", B1: "B1"}

ep = {}  # (cfg, world) -> metrics
for f in sorted(glob.glob("results/GZ_TEST/s*/g*/episodes.jsonl")):
    for line in open(f):
        d = json.loads(line)
        cfg = d["config"]; w = int(d["seed"][0]) if isinstance(d["seed"], list) else int(d["seed"])
        R = d["robot"]["go2"]; P = d["people"]; T = d["trk"]["go2"]
        n = len(T); g = m = 0; gs = []
        for i in range(n):
            rx, ry = R[i][0], R[i][1]
            ppl = P[i] if i < len(P) else []
            trk = T[i]
            gh = False
            for tr in trk:
                tx, ty = tr[1], tr[2]
                if math.hypot(tx - rx, ty - ry) > NEAR:
                    continue
                if all(math.hypot(tx - p[0], ty - p[1]) > GHOST_D for p in ppl):
                    gh = True; break
            ms = False
            for p in ppl:
                if math.hypot(p[0] - rx, p[1] - ry) <= NEAR and all(math.hypot(tr[1] - p[0], tr[2] - p[1]) > MATCH_D for tr in trk):
                    ms = True; break
            g += gh; m += ms
        row = d["rows"][0]
        ci = row.get("col_info") or {}
        if isinstance(ci, str):
            try: ci = json.loads(ci)
            except Exception: ci = {}
        kind = "ok" if int(row["success"]) else ("person" if row.get("first_contact_t") not in ("", None) else
                                                 "static" if row.get("first_static_t") not in ("", None) else "no-contact")
        ep[(cfg, w)] = dict(ghost=g / max(1, n), miss=m / max(1, n), succ=int(row["success"]), kind=kind, n=n)

print(f"episodes: {len(ep)}  (GHOST_D {GHOST_D} m, MATCH_D {MATCH_D} m, NEAR {NEAR} m)")
worlds = sorted({w for (_, w) in ep if (C1, w) in ep and (B1, w) in ep})
print(f"paired worlds: {len(worlds)}")

print("\nQ1 burden (fraction of 0.1 s steps), mean / median")
for c in (C1, B1):
    gh = [ep[(c, w)]["ghost"] for w in worlds]; mi = [ep[(c, w)]["miss"] for w in worlds]
    print(f"  {N[c]}: ghost-near {st.mean(gh):.3f} / {st.median(gh):.3f}   missed-person-near {st.mean(mi):.3f} / {st.median(mi):.3f}")

# world-level ghost burden = mean of the two episodes (so terciles do not depend on the controller's own path)
wg = {w: (ep[(C1, w)]["ghost"] + ep[(B1, w)]["ghost"]) / 2 for w in worlds}
cuts = sorted(wg.values()); q1, q2 = cuts[len(cuts) // 3], cuts[2 * len(cuts) // 3]
print(f"\nQ2 success by WORLD ghost tercile (world burden = mean over C1,B1 episodes; cuts {q1:.3f}, {q2:.3f})")
for name, sel in (("low", lambda x: x <= q1), ("mid", lambda x: q1 < x <= q2), ("high", lambda x: x > q2)):
    ws = [w for w in worlds if sel(wg[w])]
    s1 = sum(ep[(C1, w)]["succ"] for w in ws); s2 = sum(ep[(B1, w)]["succ"] for w in ws)
    print(f"  {name:4s} N {len(ws):3d}: C1 {100*s1/len(ws):5.1f} %  B1 {100*s2/len(ws):5.1f} %  gap {100*(s1-s2)/len(ws):+5.1f}")
# own-episode burden (controller-dependent) for completeness
print("  (own-episode ghost burden, failures vs successes)")
for c in (C1, B1):
    a = [ep[(c, w)]["ghost"] for w in worlds if ep[(c, w)]["succ"]]; b = [ep[(c, w)]["ghost"] for w in worlds if not ep[(c, w)]["succ"]]
    print(f"   {N[c]}: success mean {st.mean(a):.3f} (n {len(a)})  failure mean {st.mean(b):.3f} (n {len(b)})")

fs = {}
for cell in ("champ_base", "champ2_base"):
    t = defaultdict(dict)
    for f in glob.glob(f"results/TEST_{cell}/w*.csv"):
        for r in csv.DictReader(open(f)):
            if r["world"].isdigit() and str(r.get("trial", "0")) == "0":
                t[r["config"]][int(r["world"])] = (int(r["success"]), r["why"])
    fs[cell] = t

print("\nQ3 fastsim-success worlds: Gazebo outcome vs ghost burden of that Gazebo episode")
for cell in ("champ_base", "champ2_base"):
    for c in (C1, B1):
        ok_ok = [ep[(c, w)]["ghost"] for w in worlds if fs[cell][c].get(w, (0,))[0] and ep[(c, w)]["succ"]]
        ok_bad = [ep[(c, w)]["ghost"] for w in worlds if fs[cell][c].get(w, (0,))[0] and not ep[(c, w)]["succ"]]
        bad_ok = sum(1 for w in worlds if w in fs[cell][c] and not fs[cell][c][w][0] and ep[(c, w)]["succ"])
        print(f"  {cell:11s} {N[c]}: fs ok->gz ok {len(ok_ok):3d} (ghost {st.mean(ok_ok):.3f})  fs ok->gz FAIL {len(ok_bad):3d} "
              f"(ghost {st.mean(ok_bad) if ok_bad else float('nan'):.3f})  fs fail->gz ok {bad_ok}")

print("\nQ4 failure types (same 680 worlds)")
for c in (C1, B1):
    k = defaultdict(int)
    for w in worlds: k[ep[(c, w)]["kind"]] += 1
    line = "  ".join(f"{x} {k[x]}" for x in ("ok", "person", "static", "no-contact"))
    for cell in ("champ_base", "champ2_base"):
        kk = defaultdict(int)
        for w in worlds:
            if w in fs[cell][c]: kk[fs[cell][c][w][1]] += 1
        line += f" | fastsim {cell}: " + ", ".join(f"{a} {b}" for a, b in sorted(kk.items()))
    print(f"  {N[c]} Gazebo: {line}")

print("\nQ5 ghost burden by Gazebo outcome kind")
for c in (C1, B1):
    k = defaultdict(list)
    for w in worlds: k[ep[(c, w)]["kind"]].append(ep[(c, w)]["ghost"])
    print(f"  {N[c]}: " + "  ".join(f"{x} n{len(v)} ghost {st.mean(v):.3f}" for x, v in sorted(k.items())))

import random
print("\nQ6 Gazebo gap minus fastsim gap on the same worlds (paired bootstrap 20000, 95 % CI)")
gzs = {c: {w: ep[(c, w)]["succ"] for w in worlds} for c in (C1, B1)}
for cell in ("champ_base", "champ2_base"):
    W = [w for w in worlds if w in fs[cell][C1] and w in fs[cell][B1]]
    d = [(gzs[C1][w] - gzs[B1][w]) - (fs[cell][C1][w][0] - fs[cell][B1][w][0]) for w in W]
    rng = random.Random(1); bs = sorted(sum(d[rng.randrange(len(W))] for _ in W) / len(W) for _ in range(20000))
    print(f"  {cell}: {100*sum(d)/len(W):+.1f} points [{100*bs[500]:.1f}, {100*bs[19500]:.1f}]  (N {len(W)})")
