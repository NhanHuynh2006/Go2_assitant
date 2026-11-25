import os, sys, types, json, csv, glob
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H + "/snap")
import numpy as np, fastsim as fs
C = fs.make_crowd_class()
tot, n, W = 0, 0, 0; has = []
for s in range(0, 300):
    w = fs.gen_world(s)
    if not w["crowd"]: continue
    sim = types.SimpleNamespace(boxes=fs.Boxes(w["boxes"]), x=np.array(w["start"], float))
    c = C(w, sim, 0); d = [p["distracted"] for p in c.people]; tot += sum(d); n += len(d); has.append((s, sum(d), len(d)))
print("fastsim DEV 0-299: %d the gioi, %d nguoi, mai dien thoai %.3f (danh dinh .30); the gioi KHONG co ai mai dien thoai: %.0f%%" % (len(has), n, tot / n, 100 * np.mean([h[1] == 0 for h in has])))
A = {h[0]: h for h in has}
R = [r for f in glob.glob(H + "/../results/dev3/w*.csv") for r in csv.DictReader(open(f)) if r["config"] in ("mppi", "mppi:ppl=32", "p2+turn")]
for c in ("mppi", "mppi:ppl=32", "p2+turn"):
    for lab, f in (("0 nguoi mdt", lambda h: h[1] == 0), (">=1", lambda h: h[1] > 0)):
        q = [int(r["success"]) for r in R if r["config"] == c and f(A[int(r["world"])])]; print("  ", c, lab, "n=%d SR %.2f" % (len(q), np.mean(q)))
    v = [json.loads(r["info"]) for r in R if r["config"] == c and r["col"] == "person"]; print("     cham do nguoi mai dien thoai: %d/%d" % (sum(x.get("distracted", 0) for x in v), len(v)))
