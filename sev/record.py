#!/usr/bin/env python3
"""SEV: ghi quy dao day du (robot, nguoi that, track) tung 0.1 s khi chay fastsim (BAN CHUP sev/snap) voi 1 cau hinh.
  ../venv/bin/python record.py 0 149 'mppi:ppl=32' rec/ppl32 JOB NJOBS"""
import os, sys, json, pickle
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "snap"))
import numpy as np
import fastsim
from fastsim import gen_world, run_episode

class RecSim(fastsim.Sim):
    cur = None
    def __init__(self, *a, **k):
        self.log = []
        RecSim.cur = self
        super().__init__(*a, **k)
    def check(self):
        C = self.crowd
        self.log.append((self.clock.t - self.t0, *self.x, *self.v, *self.cmd,
                         [(p["p"][0], p["p"][1], p["v"][0], p["v"][1], float(p["distracted"]), p["wait"], p["v0"]) for p in C.people],
                         [(float(t["p"][0]), float(t["p"][1]), float(t["v"][0]), float(t["v"][1]), self.clock.t - t["t"]) for t in self.r.tracker.movers()]))
        super().check()

if __name__ == "__main__":
    lo, hi, cfg, out, j, nj = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6])
    os.makedirs(out, exist_ok=True)
    assert 0 <= lo <= hi <= 999
    fastsim.Sim = RecSim
    for s in range(lo, hi + 1):
        if s % nj != j or os.path.exists(f"{out}/{s}.pkl"):
            continue
        W = gen_world(s)
        if not W["crowd"]:
            continue
        row = run_episode(W, cfg, 0)
        L = RecSim.cur.log
        d = dict(seed=s, cfg=cfg, row={k: v for k, v in row.items() if k != "traj"},
                 rob=np.array([l[:10] for l in L], np.float32), ppl=np.array([l[10] for l in L], np.float32),
                 trk=[l[11] for l in L], goal=W["goal"], boxes=W["boxes"], vsat=RecSim.cur.vsat, back=RecSim.cur.back, gain=RecSim.cur.gain)
        pickle.dump(d, open(f"{out}/{s}.tmp", "wb")); os.rename(f"{out}/{s}.tmp", f"{out}/{s}.pkl")
        print(s, row["success"], row["col"], row["cpu"], flush=True)
