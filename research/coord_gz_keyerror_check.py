"""POST-HOC integrity check (25/11): tracker KeyError('x') at the start of each eval run (stale v2 tracks when the
controller switches to ~t3; REALPREP bug (a)). Finds the affected episode (first episode of each eval invocation that had
KeyErrors before it finished) and re-runs the primary comparison excluding affected worlds."""
import csv, glob, re, sys
from math import comb
from collections import defaultdict
ROOT = sys.argv[1] if len(sys.argv) > 1 else "results/GZ_TEST"
aff = set(); nerr = defaultdict(int)
for f in glob.glob(f"{ROOT}/s*/g*/eval.log"):
    k = 0
    for line in open(f, errors="ignore"):
        if line.startswith("[sha]"):
            k = 0
        elif "KeyError('x')" in line:
            k += 1
        elif line.startswith("[1/1]"):
            if k:
                m = re.match(r"\[1/1\] (\S+) gz:\S+?_(\d+)", line)
                aff.add((m.group(1), int(m.group(2)))); nerr[(m.group(1), int(m.group(2)))] = k
            k = 0
print(f"{ROOT}: affected episodes {len(aff)}; KeyErrors per affected episode: min {min(nerr.values())} max {max(nerr.values())}")
by = defaultdict(dict)
for f in glob.glob(f"{ROOT}/s*/g*/trials.csv"):
    for r in csv.DictReader(open(f)): by[r["config"]][int(r["seed"])] = int(r["success"])
for c, d in by.items():
    a = [d[w] for w in d if (c, w) in aff]; u = [d[w] for w in d if (c, w) not in aff]
    print(f"  {c[:22]:22s} affected {len(a)}: {100*sum(a)/max(1,len(a)):.1f} %   unaffected {len(u)}: {100*sum(u)/max(1,len(u)):.1f} %")
if len(sys.argv) > 2:
    sys.exit()
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"; B1 = "mppi~t3~nl:ppl=100;ppl_len=0.5"
W = [w for w in by[C1] if w in by[B1] and (C1, w) not in aff and (B1, w) not in aff]
b = sum(1 for w in W if by[C1][w] and not by[B1][w]); cc = sum(1 for w in W if not by[C1][w] and by[B1][w])
n = b + cc; p = min(1, 2 * sum(comb(n, i) for i in range(min(b, cc) + 1)) / 2 ** n)
print(f"  primary excluding affected worlds: N {len(W)}  C1 {100*sum(by[C1][w] for w in W)/len(W):.1f} %  B1 {100*sum(by[B1][w] for w in W)/len(W):.1f} %  discordant {b}/{cc}  p {p:.2g}")
