"""Thoi gian 1 buoc ctrl.step (ms): venv/bin/python research/algo_timing.py seed cfg..."""
import os, sys, time; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fastsim, numpy as np, robot_ros
mk = robot_ros.RosRobotTools._make_ctrl
for cfg in sys.argv[2:]:
    ts = []
    def mk2(self):
        c = mk(self); st = c.step
        def step(*a, **k):
            t = time.perf_counter(); r = st(*a, **k); ts.append(time.perf_counter() - t); return r
        c.step = step; return c
    robot_ros.RosRobotTools._make_ctrl = mk2
    fastsim.run_episode(fastsim.gen_world(int(sys.argv[1])), cfg, 0)
    print(cfg, "C" if os.environ.get("GOVOICE_FAST_SO") else "numpy", "TB %.1f ms, p99 %.1f ms, max %.1f" % (1e3 * np.mean(ts), 1e3 * np.percentile(ts, 99), 1e3 * max(ts)))
