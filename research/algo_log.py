"""python3 research/algo_log.py <thu muc> <ghi chu> : ghi 1 dong LOG.csv / cau hinh (agent ALGO)."""
import csv, glob, sys, datetime, os
d, note = sys.argv[1], sys.argv[2]
only = set(sys.argv[3:])
R = {}
for f in glob.glob(d + "/w[0-9]*.csv"):
    for r in csv.DictReader(open(f)):
        if r["success"] != "":
            R.setdefault(r["config"], {})[(r["world"], r["trial"])] = int(r["success"])
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LOG.csv")
OLD = {(r[2], r[3].split("(")[0], r[4]) for r in csv.reader(open(P)) if len(r) > 5}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "LOG.csv"), "a", newline="") as f:
    w = csv.writer(f)
    for c, g in sorted(R.items()):
        if only and c not in only:
            continue
        if (c, os.path.basename(d), str(len(g))) in OLD:
            continue
        s = sorted(int(k[0]) for k in g)
        w.writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "ALGO", c, f"{os.path.basename(d)}(seed {s[0]}-{s[-1]} crowd-only)", len(g), sum(g.values()), note])
