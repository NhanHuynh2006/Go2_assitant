import csv, glob, sys
def L(t):
    out = {}
    for r in csv.DictReader(open(f"res_{t}.csv")):
        if r["world"].isdigit(): out[int(r["world"])] = r
    return out
tags = sys.argv[1:]
D = {t: L(t) for t in tags}
K = ["success", "why", "err", "time", "travel", "min_person", "min_static", "foot", "foot_t"]
ref = D[tags[0]]
for t in tags:
    d = D[t]; ws = sorted(d)
    simt = sum(float(d[w]["time"] or 0) for w in ws); wall = sum(float(d[w]["wall"]) for w in ws)
    same = sum(all(d[w][k] == ref[w][k] for k in K) for w in ws if w in ref)
    print(f"{t}: n={len(ws)} thanh cong {sum(d[w]['success']=='1' for w in ws)}  sim {simt:.0f} s, tong wall-client {wall:.0f} s -> {simt/wall:.2f} s mo phong / s may / robot; giong het {tags[0]}: {same}/{len(ws)}")
    for w in ws:
        if w in ref and not all(d[w][k] == ref[w][k] for k in K):
            print("   khac", w, [(k, ref[w][k], d[w][k]) for k in K if d[w][k] != ref[w][k]])
