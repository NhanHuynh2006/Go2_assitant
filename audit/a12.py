import math, numpy as np
from a10_results import load
from scipy.stats import norm
B = load("base")
for c in ("mous", "helb"):
    R = load(c); K = sorted(set(R["p2+turn"]) & set(B["p2+turn"]) & set(R["mppi"]) & set(R["mppi:ppl=32"]) & set(B["mppi"]) & set(B["mppi:ppl=32"]))
    for a, b in (("p2+turn", "mppi:ppl=32"), ("mppi:ppl=32", "mppi"), ("p2+turn", "mppi")):
        d = np.array([(int(R[a][k]["success"]) - int(R[b][k]["success"])) - (int(B[a][k]["success"]) - int(B[b][k]["success"])) for k in K]); z = d.mean() / (d.std(ddof=1) / math.sqrt(len(d))); print(c, a, "-", b, "n=%d doi hieu %+.0f z=%.2f p=%.3f" % (len(K), 100 * d.mean(), z, 2 * norm.sf(abs(z))))
