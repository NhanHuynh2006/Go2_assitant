"""Nap final_office_w[01]: trials.csv ghep voi traj.jsonl (theo thu tu ghi)."""
import csv, json, os
from collections import defaultdict
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(dirs=("final_office_w0", "final_office_w1")):
    out = []
    for d in dirs:
        p = os.path.join(HERE, "results", d)
        rows = list(csv.DictReader(open(p + "/trials.csv")))
        seq = defaultdict(lambda: defaultdict(list))
        for l in open(p + "/traj.jsonl"):
            o = json.loads(l); c, t, ns = o["k"]
            seq[(c, t)][ns].append(o["v"])
        cnt = defaultdict(int)
        for r in rows:
            k = (r["config"], r["task"]); i = cnt[k]; cnt[k] += 1
            r["sim"] = d[-1]; s = seq[k]
            r["traj"] = np.array(s["go2"][i], float) if i < len(s["go2"]) else None
            pt = s.get("person#person", [])
            r["person"] = np.array(pt[i], float) if i < len(pt) else None
            r["n_traj_mismatch"] = len(s["go2"])
            out.append(r)
    return out
if __name__ == "__main__":
    R = load()
    print(len(R), "luot;", "traj thieu:", sum(r["traj"] is None for r in R), "; so lan lap traj khac 5:", sum(r["n_traj_mismatch"] != 5 for r in R))
    # 1) chu ky lay mau that cua Monitor
    dts = np.array([(float(r["time_s"]) + .5) / len(r["traj"]) for r in R])
    for cat in ("clutter", "crowd"):
        q = np.array([d for d, r in zip(dts, R) if r["cat"] == cat]); print(cat, "chu ky Monitor: TB %.3f s, p5 %.3f p95 %.3f (code chia 0.1)" % (q.mean(), *np.percentile(q, [5, 95])))
    for t in sorted({r["task"] for r in R}):
        q = [d for d, r in zip(dts, R) if r["task"] == t]; print("   ", t, round(np.mean(q), 4))
    # travel khop khong
    tr = [abs(float(r["travel_m"]) - np.hypot(*np.diff(r["traj"][:, :2], axis=0).T).sum()) for r in R]
    print("sai travel_m vs traj (kiem tra ghep):", round(np.mean(tr), 3), "max", round(max(tr), 2))
    # 2) toc do nguoi (person = k=0) theo chu ky that
    for t in sorted({r["task"] for r in R if r["cat"] == "crowd"}):
        v, vmax = [], []
        for r in R:
            if r["task"] == t and r["person"] is not None and len(r["person"]) > 30:
                dt = (float(r["time_s"]) + .5) / len(r["traj"])
                s = np.hypot(*np.diff(r["person"][::5, :2], axis=0).T) / (5 * dt)
                v += list(s[s > .2]); vmax.append(np.percentile(s, 90))
        print(t, "toc do nguoi khi di: TB %.2f median %.2f p95 %.2f" % (np.mean(v), np.median(v), np.percentile(v, 95)))
