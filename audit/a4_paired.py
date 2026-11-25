import csv, glob, itertools, math, collections, sys, os
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(d):
    R = [r for f in glob.glob(f"{HERE}/results/{d}/w*.csv") for r in csv.DictReader(open(f)) if r["success"] != ""]
    by = collections.defaultdict(dict)
    for r in R:
        if int(r["npeople"]): by[r["config"]][r["world"]] = r
    return by
D = {d: load(d) for d in ("dev1", "dev2", "dev3")}
print("== cung cau hinh, cung seed, KHAC thu muc chay (kiem tat dinh / doi code)")
for c in ("mppi", "p2", "dwa", "p2-evade"):
    for a, b in itertools.combinations(D, 2):
        if c in D[a] and c in D[b]:
            K = set(D[a][c]) & set(D[b][c]); s = [(int(D[a][c][k]["success"]), int(D[b][c][k]["success"])) for k in K]
            same = sum(abs(float(D[a][c][k]["time"]) - float(D[b][c][k]["time"])) < .01 and D[a][c][k]["travel"] == D[b][c][k]["travel"] for k in K)
            print(f"  {c:10s} {a}-{b} n={len(K)} {sum(x for x,_ in s)} vs {sum(y for _,y in s)}; lech ket qua {sum(x!=y for x,y in s)}; trung khit (time,travel) {same}")
by = D["dev3"]; cf = sorted(by); W = sorted(set.intersection(*[set(by[c]) for c in cf]), key=int)
M = np.array([[int(by[c][w]["success"]) for w in W] for c in cf])
t = M.mean(0)
print("== dev3: %d the gioi x %d cau hinh; moi cau hinh deu hong: %d (%.0f%%); deu dat: %d" % (len(W), len(cf), (t == 0).sum(), 100 * (t == 0).mean(), (t == 1).sum()))
disc = [(np.mean(M[i] != M[j])) for i, j in itertools.combinations(range(len(cf)), 2)]
print("   ti le cap BAT DONG giua 2 cau hinh: TB %.2f (%.2f-%.2f)" % (np.mean(disc), min(disc), max(disc)))
print("   hiep bien trong the gioi (ICC) ~ %.2f" % ((t.var() - (t * (1 - t)).mean() / (len(cf) - 1)) / (t.mean() * (1 - t.mean()))))
for c, m in sorted(zip(cf, M.mean(1)), key=lambda q: -q[1])[:3]: print("   ", c, m)
