#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_steps.py (REALPREP, 25/11) - do thoi gian ctrl.step cua C1 / B1 / C1~cs tren MAY NAY (vd Orin cua cho).

Khong ROS, khong chuyen dong: chay fastsim (dong bang) regime go2 tren N the gioi DEV co nguoi (seed 0-39), boc
_make_ctrl trong tien trinh de bam gio ctrl.step. Ket qua dieu huong KHONG dung de chon gi (chi do thoi gian).
Ngan sach that: vong dieu khien 10 Hz (robot_ros: sleep(max(0, 0.1 - step))) -> p95 nen < 60 ms de con cho LiDAR.
  python3 deploy/bench_steps.py 4            # Python thuan (mac dinh trien khai)
  GOVOICE_FAST_SO=$PWD/research/algo_fast/fast_aarch64.so python3 deploy/bench_steps.py 4
"""
import os
import sys
import time
import json
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np          # noqa: E402
import fastsim              # noqa: E402
import robot_ros            # noqa: E402

perf = time.perf_counter
REC = []
_orig = robot_ros.RosRobotTools._make_ctrl


def _mk(self):
    c = _orig(self)
    s0 = c.step

    def step(*a, **k):
        t = perf()
        o = s0(*a, **k)
        REC.append((perf() - t) * 1000)
        return o
    c.step = step
    return c


robot_ros.RosRobotTools._make_ctrl = _mk
CFGS = {"C1": "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5", "B1": "mppi~t3~nl:ppl=100;ppl_len=0.5",
        "C1cs": "p3+geo-haz+gcv~t3~nl~cs:ppl=32;ppl_len=0.5"}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    seeds = [s for s in range(0, 40) if fastsim.gen_world(s)["crowd"]][:n]
    out, outcomes = {}, {}
    for name, cfg in CFGS.items():
        del REC[:]
        t0 = perf()
        outcomes[name] = []
        for s in seeds:
            res = fastsim.run_episode(fastsim.gen_world(s), cfg, 0, regime="go2")
            outcomes[name].append([s, res["success"], res["time"], res["err"]])
        a = np.array(REC)
        out[name] = dict(n=len(a), p50=round(float(np.percentile(a, 50)), 2), p95=round(float(np.percentile(a, 95)), 2),
                         p99=round(float(np.percentile(a, 99)), 2), max=round(float(a.max()), 2),
                         wall_s=round(perf() - t0, 1))
    import hashlib
    dig = hashlib.sha256(json.dumps(outcomes, sort_keys=True).encode()).hexdigest()[:16]
    # digest giong nhau giua 2 may = cung so hoc tung bit. Khac nhau la BINH THUONG khi khac numpy/CPU (da do: py3.8+numpy1.24
    # vs py3.14+numpy2.5 cho quy dao khac nhau); khi do chi so thoi gian la quan trong.
    print(json.dumps(dict(fast_so=os.environ.get("GOVOICE_FAST_SO", ""), seeds=seeds, steps=out, outcomes=outcomes,
                          outcome_digest=dig, python=sys.version.split()[0], numpy=np.__version__,
                          machine=os.uname()[4])))


if __name__ == "__main__":
    main()
