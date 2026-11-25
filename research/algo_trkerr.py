"""Sai so tracker so voi su that (DEV): venv/bin/python research/algo_trkerr.py <cfg> <seeds,..> [regime] [sig_a sig_m]"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fastsim, numpy as np, nav_local
cfg = sys.argv[1]; seeds = [int(v) for v in sys.argv[2].split(",")]; reg = sys.argv[3] if len(sys.argv) > 3 else "champ"
if len(sys.argv) > 5:
    nav_local.BlobTracker.sig_a, nav_local.BlobTracker.sig_m = float(sys.argv[4]), float(sys.argv[5])
E, miss, gh, seen = [], {}, [0, 0], {}
o = fastsim.Sim.check
def chk(self):
    now = self.clock.t
    if self.k % 2 == 0 and now - self.t0 > 1:
        x, y, yaw = self.x
        lx, ly = x + .2 * math.cos(yaw), y + .2 * math.sin(yaw)
        mv = self.r.tracker.movers(); ppl = self.people()
        Q = [(tr["p"] + tr["v"] * min(.4, now - tr["t"] + .05), tr["v"]) for tr in mv]
        for q, v in Q:
            gh[0] += 1; gh[1] += min([math.hypot(q[0] - p[0], q[1] - p[1]) for p in ppl] or [9]) > .6
        for i, p in enumerate(ppl):
            d = math.hypot(p[0] - lx, p[1] - ly); b = math.atan2(p[1] - ly, p[0] - lx); w = math.asin(min(1, .18 / max(d, .2)))
            vis = d < 3.5 and (self.boxes.cast(lx, ly, np.array([b, b - w, b + w]), 6.0) > d - .25).any()
            if not vis:
                seen.pop(i, None); continue
            seen.setdefault(i, now)
            k = "mu" if d < .75 else ("dung" if math.hypot(p[3], p[4]) < .15 else ("moi<.6s" if now - seen[i] < .6 else "khac"))
            m = miss.setdefault(k, [0, 0]); m[0] += 1
            if Q:
                j = min(range(len(Q)), key=lambda j: math.hypot(Q[j][0][0] - p[0], Q[j][0][1] - p[1]))
                e = math.hypot(Q[j][0][0] - p[0], Q[j][0][1] - p[1])
                if e < .6:
                    if k == "khac":
                        E.append((e, math.hypot(Q[j][1][0] - p[3], Q[j][1][1] - p[4])))
                    continue
            m[1] += 1
    o(self)
fastsim.Sim.check = chk
for s in seeds:
    seen.clear(); fastsim.run_episode(fastsim.gen_world(s), cfg, 0, reg)
E = np.array(E)
print(cfg, reg, sys.argv[4:6], "n=%d pos TB %.3f p90 %.3f | vel TB %.3f p90 %.3f | bong ma %.1f%% | sot: %s" % (len(E), E[:, 0].mean(), np.percentile(E[:, 0], 90), E[:, 1].mean(), np.percentile(E[:, 1], 90), 100 * gh[1] / max(1, gh[0]), {k: "%d/%d" % (v[1], v[0]) for k, v in miss.items()}))
