"""Gia dinh nao doi THU HANG? Tuong tac (hieu ghep cap duoi gia dinh - hieu o base), cung 40 the gioi; Holm."""
import sys, math
import numpy as np
from a10_results import load
from scipy.stats import norm
B = load("base"); K = sorted(set.intersection(*[set(v) for v in B.values()]))[:40]
out = []
for c in ("real", "cmd2", "dis6", "dis0", "seen2", "fast", "dense", "wob0", "real_body", "soft5", "slow"):
    R = load(c)
    for a, b in (("p2+turn", "mppi:ppl=32"), ("mppi:ppl=32", "mppi")):
        d = np.array([(int(R[a][k]["success"]) - int(R[b][k]["success"])) - (int(B[a][k]["success"]) - int(B[b][k]["success"])) for k in K]); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d))); out.append((2 * norm.sf(abs(z)), c, a, b, d.mean(), z))
out.sort(); m = len(out); run = 0
for i, (p, c, a, b, d, z) in enumerate(out[:8]): run = max(run, min(1, p * (m - i))); print("%-10s (%s - %s): doi hieu %+.0f diem, z=%.2f p=%.4f p_Holm=%.3f" % (c, a, b, 100 * d, z, p, run))
