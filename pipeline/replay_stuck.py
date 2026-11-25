import os, sys, pickle, copy, math, glob
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant")
import numpy as np
fs = sorted(glob.glob(sys.argv[1] + "/stuck_*.pkl"))
for f in fs:
    d = pickle.load(open(f, "rb"))
    x0, goal = d["x0"], d["goal"]
    print("==", os.path.basename(f), "pose", np.round(x0, 2), "goal", goal, "d", round(math.hypot(goal[0]-x0[0], goal[1]-x0[1]), 2),
          "v0", np.round(d["v0"], 2), "gains", np.round(d["extra"].get("gains"), 2), "u_prev", np.round(d["u_prev"], 2),
          "tent", len(d["extra"].get("tentative", [])), "people", len(d["people"]))
    print("   ctrl.last:", {k: (np.round(v, 3) if isinstance(v, float) else v) for k, v in d["ctrl"].last.items() if k != "traj"})
    variants = [("full", {})] + [(f"no_{k}", {k: False}) for k in ("vis", "value", "prior", "adapt", "unc", "adaptratio")]
    for name, fl in variants:
        us = []
        for rep in range(15):
            c = copy.deepcopy(d["ctrl"]); c.flags.update(fl); c.rng = np.random.default_rng(rep)
            x, v, u = d["x0"].copy(), d["v0"].copy(), d["u_prev"].copy()
            for k in range(20):                                     # 2 s vong kin tren mo hinh
                u, info = c.step(x, v, d["field"], d["meta"], d["P"], d["S"], goal, people=d["people"],
                                 gain=d["gain"], u_prev=u, **d["extra"])
                g = np.asarray(d["extra"]["gains"])
                v = v + min(1, 0.1 / c.tau) * (g * u - v)
                cth, sth = math.cos(x[2]), math.sin(x[2])
                x = x + np.array([(v[0]*cth - v[1]*sth)*0.1, (v[0]*sth + v[1]*cth)*0.1, v[2]*0.1])
            us.append(math.hypot(goal[0]-x[0], goal[1]-x[1]))
        print(f"   {name:14s} khoang cach toi dich sau 2 s (mo hinh): TB {np.mean(us):.2f}  min {np.min(us):.2f}  info.clear={info['clear']:.2f} blocked={info['blocked']}")
