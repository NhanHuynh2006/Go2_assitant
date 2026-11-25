#!/usr/bin/env python3
"""So fastsim truoc/sau tung dong (bo cot cpu): python3 research/gz/ident_cmp.py before after"""
import csv, glob, os, sys
B, A = sys.argv[1], sys.argv[2]
tot, diff = 0, 0
for cell in ("champ_base", "champ2_base", "go2_base", "champ2_helb", "go2_helb"):
    def load(tag):
        rows = []
        for f in sorted(glob.glob(f"results/GZ_ident/{tag}_{cell}/w*.csv")):
            rows += [r for r in csv.DictReader(open(f))]
        return {(r["world"], r["trial"], r["config"]): tuple((k, v) for k, v in r.items() if k != "cpu") for r in rows}
    b, a = load(B), load(A)
    d = [k for k in b if b[k] != a.get(k)] + [k for k in a if k not in b]
    exc = sum(1 for v in b.values() if dict(v)["why"].startswith("EXC"))
    print(f"{cell:12} truoc {len(b)} sau {len(a)} dong; khac {len(d)}; EXC {exc}")
    tot += len(b); diff += len(d)
print("TONG", tot, "dong, khac", diff, "->", "TRUNG TUNG DONG" if diff == 0 and tot else "KHAC")
