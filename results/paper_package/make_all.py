#!/usr/bin/env python3
"""GoVoice paper package: regenerate EVERY table (CSV + LaTeX) and figure (PDF + PNG) from the raw result files.

    cd ~/Documents/Go2_assitant
    OPENBLAS_NUM_THREADS=1 nice -n 19 venv/bin/python results/paper_package/make_all.py

* Read-only on all inputs. Writes only inside results/paper_package/{tables,figures,checks}.
* Deterministic: every random procedure has a fixed seed. The primary family, the static arm, the ablation and the
  round-3 non-inferiority analysis replicate, draw for draw, the coordinator/ALGO scripts that produced the numbers
  quoted in research/*.txt (research/coord_val_analyze.py, algo_confirm.py, algo_noninf.py). checks/CHECKS.txt
  compares every such number with the coordinator's text output and the script exits with status 1 on any mismatch.
* Single core: numpy BLAS is forced to 1 thread. Runtime ~1 min.
No new experiment is run; nothing here touches the robot, the network or frozen code.
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import sys, csv, glob, json, math, re, hashlib, collections, io, contextlib
from math import comb, sqrt
import numpy as np
from scipy.stats import binomtest, spearmanr, kendalltau
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TAB, FIG, CHK = (os.path.join(HERE, d) for d in ("tables", "figures", "checks"))
for d in (TAB, FIG, CHK):
    os.makedirs(d, exist_ok=True)
P = lambda *a: os.path.join(ROOT, *a)
INPUTS = set()          # every raw file read -> checks/INPUT_SHA256SUMS
CHECK_LINES, MISMATCH = [], []


def note_input(f):
    INPUTS.add(os.path.relpath(os.path.abspath(f), ROOT))
    return f


def check(name, mine, ref, tol=0.0):
    """Record a reproduction check. Strings compared exactly, numbers within tol."""
    ok = (mine == ref) if isinstance(ref, str) else (abs(float(mine) - float(ref)) <= tol + 1e-12)
    CHECK_LINES.append(f"{'OK ' if ok else 'MISMATCH'}  {name}: package={mine}  reference={ref}")
    if not ok:
        MISMATCH.append(name)


# ----------------------------------------------------------------------------------------------- configurations
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
B1 = "mppi~t3~nl:ppl=100;ppl_len=0.5"
PGIF = "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000"
DRA = "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"
B0 = "mppi:ppl=32"
DWA = "dwa~t3~nl:ppl=100;ppl_len=0.3"
LOG = "log_mppi~t3~nl:ppl=100;ppl_len=0.5"
# same insertion order as research/coord_val_analyze.py (NAMES) -> identical RNG stream
NAMES = {B1: "B1", PGIF: "PGIF*", DRA: "DRA*", B0: "B0", DWA: "DWA", LOG: "log-MPPI", C1: "C1"}
SHOW = [C1, DRA, PGIF, B1, DWA, LOG, B0]                    # display order
LONG = {C1: "C1 (proposed)", B1: "B1 MPPI, tuned", PGIF: "PGIF-MPPI* (reimpl.)", DRA: "DRA-MPPI* (reimpl.)",
        B0: "B0 MPPI, original tracker", DWA: "DWA, tuned", LOG: "log-MPPI, tuned"}
FAMILY = [B1, PGIF, DRA]
CELLS = ["champ_base", "champ2_base", "go2_base", "champ2_helb", "go2_helb"]
CELL_LAB = {"champ_base": "CHAMP / base", "champ2_base": "CHAMP2 / base", "go2_base": "Go2 / base",
            "champ2_helb": "CHAMP2 / Helbing", "go2_helb": "Go2 / Helbing"}
SEED = 20261124                                              # seed of the pre-registered analysis script
WHY = [("ok", "success"), ("va nguoi", "person collision"), ("va vat", "static collision"), ("ket", "stuck"),
       ("het gio", "timeout"), ("khong co duong", "no path")]

# Okabe-Ito (colour-blind safe); identity is ALSO carried by marker shape / hatch so figures survive grayscale.
OI = dict(blue="#0072B2", orange="#E69F00", green="#009E73", pink="#CC79A7", sky="#56B4E9", verm="#D55E00",
          black="#000000", grey="#7F7F7F")
STYLE = {C1: (OI["black"], "o"), DRA: (OI["blue"], "s"), PGIF: (OI["orange"], "^"), B1: (OI["verm"], "D"),
         DWA: (OI["green"], "v"), LOG: (OI["pink"], "P"), B0: (OI["grey"], "X")}
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.linewidth": 0.6, "axes.spines.top": False,
                     "axes.spines.right": False, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 300, "lines.linewidth": 1.2,
                     "svg.hashsalt": "govoice", "hatch.linewidth": 0.6})


# ----------------------------------------------------------------------------------------------- helpers
def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n; q = 1 + z * z / n; c = (p + z * z / 2 / n) / q
    h = z * sqrt(p * (1 - p) / n + z * z / 4 / n / n) / q
    return c - h, c + h


def holm(ps):
    """Holm step-down, same implementation as the coordinator scripts. Returns adjusted p in input order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i]); m = len(ps); out = [0.0] * m; prev = 0
    for r, i in enumerate(order):
        prev = max(prev, min(1, ps[i] * (m - r))); out[i] = prev
    return out


def mcnemar_exact(up, dn):
    return binomtest(up, up + dn).pvalue if up + dn else 1.0


def g2(x):
    return "%.2g" % x


def load_cells(dirmap, cfgs):
    """dirmap: cell -> result dir. Coordinator EXC rule (FROZEN.md addendum / PREREG_TEST §5): a (world, cell) whose every
    config is EXC is dropped; EXC in only some configs counts as failure. Returns S[(cell, w)][cfg] -> 0/1, rows, exc."""
    S, R, exc = {}, {}, collections.Counter()
    for c, d in dirmap.items():
        Rw = collections.defaultdict(dict)
        for f in sorted(glob.glob(P(d, "w*.csv"))):
            note_input(f)
            for r in csv.DictReader(open(f)):
                Rw[r["world"]][r["config"]] = r
        for w, v in Rw.items():
            if all(v.get(k, {}).get("success", "") == "" for k in cfgs):
                exc["drop " + c] += 1; continue
            for k in cfgs:
                r = v.get(k)
                s = 0 if (r is None or r["success"] == "") else int(r["success"])
                if r is None or r["success"] == "":
                    exc[k] += 1
                S.setdefault((c, w), {})[k] = s
                R.setdefault((c, w), {})[k] = r
    return S, R, exc


def worlds_all(S, cells):
    return sorted({w for (c, w) in S if all((cc, w) in S for cc in cells)}, key=int)


def primary_family(S, cells, worlds, baselines, seed=SEED, nperm=200000, nboot=10000):
    """Exact replica of research/coord_val_analyze.py 'HO CHINH': world-level paired difference d_w (mean over cells),
    two-sided sign-flip permutation (nperm), percentile bootstrap over worlds (nboot), Holm over the family."""
    rng = np.random.default_rng(seed); res = []
    for k in baselines:
        d = np.array([np.mean([S[(c, w)][C1] - S[(c, w)][k] for c in cells]) for w in worlds])
        obs = d.sum(); null = np.empty(nperm)
        for i in range(0, nperm, 20000):
            sg = rng.choice([-1, 1], (20000, len(d))); null[i:i + 20000] = sg @ d
        p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (len(null) + 1)
        bs = [d[rng.integers(0, len(d), len(d))].mean() * 100 for _ in range(nboot)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        res.append(dict(base=k, d=d.mean() * 100, lo=lo, hi=hi, p=p, n=len(d)))
    for r, h in zip(res, holm([r["p"] for r in res])):
        r["holm"] = h
    return res


def boot_ci(d, rng, nboot=10000):
    bs = [d[rng.integers(0, len(d), len(d))].mean() * 100 for _ in range(nboot)]
    return tuple(np.percentile(bs, [2.5, 97.5]))


# ----------------------------------------------------------------------------------------------- table writers
def tex_escape(s):
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"),
                 ("~", r"\textasciitilde{}"), ("^", r"\^{}"), ("$", r"\$"), ("{", r"\{"), ("}", r"\}")):
        if a == "{" or a == "}":
            continue
        s = s.replace(a, b)
    return s.replace("−", "$-$").replace("±", r"$\pm$").replace("≥", r"$\geq$").replace("≤", r"$\leq$") \
            .replace("×", r"$\times$").replace("τ", r"$\tau$").replace("ρ", r"$\rho$").replace("Δ", r"$\Delta$") \
            .replace("≈", r"$\approx$").replace("→", r"$\rightarrow$").replace("∞", r"$\infty$").replace("|", r"$|$") \
            .replace("…", r"\ldots{}").replace("′", "'") \
            .replace("α", r"$\alpha$").replace("⟦", "[[").replace("⟧", "]]")


def write_table(name, header, rows, caption, label=None, colspec=None, notes=None, raw_csv_rows=None):
    with open(os.path.join(TAB, name + ".csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header)
        for r in (raw_csv_rows if raw_csv_rows is not None else rows):
            w.writerow(r)
    colspec = colspec or ("l" * 1 + "r" * (len(header) - 1))
    L = [r"% generated by results/paper_package/make_all.py -- do not edit by hand; needs booktabs + graphicx", r"\begin{table*}[t]", r"\centering",
         r"\caption{" + tex_escape(caption) + "}", r"\label{" + (label or "tab:" + name) + "}", r"\scriptsize",
         r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{" + colspec + "}", r"\toprule", " & ".join(tex_escape(h) for h in header) + r" \\", r"\midrule"]
    for r in rows:
        if r == "MID":
            L.append(r"\midrule"); continue
        L.append(" & ".join(tex_escape(x) for x in r) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}}"]
    if notes:
        L.append(r"\par\smallskip\parbox{0.95\textwidth}{\footnotesize " + tex_escape(notes) + "}")
    L.append(r"\end{table*}")
    open(os.path.join(TAB, name + ".tex"), "w").write("\n".join(L) + "\n")


def savefig(fig, name):
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None,
                                                                                    "Producer": None, "Creator": None})
    fig.savefig(os.path.join(FIG, name + ".png"), bbox_inches="tight", dpi=300, metadata={"Software": None})
    plt.close(fig)


pct = lambda x: "%.1f" % x
sgn = lambda x: "%+.2f" % x

# =============================================================================================== 1. TEST (primary)
ALL7 = list(NAMES)
TEST_DIRS = {c: "results/TEST_" + c for c in CELLS}
S, R, EXC = load_cells(TEST_DIRS, ALL7)
W = worlds_all(S, CELLS)
nW = len(W)
check("TEST worlds per cell", nW, 1000)
check("TEST EXC count", sum(EXC.values()), 0)
fam = primary_family(S, CELLS, W, FAMILY)

# reproduction check against research/TEST_fastsim_results.txt (coordinator)
ref = open(note_input(P("research/TEST_fastsim_results.txt"))).read()
for r in fam:
    line = "C1 - %-6s %+5.2f diem  KTC95 [%+.2f; %+.2f]  p=%.2g  Holm=%.2g" % (NAMES[r["base"]], r["d"], r["lo"], r["hi"], r["p"], r["holm"])
    check("TEST primary " + NAMES[r["base"]], line, line if line in ref else "<line not found in coordinator file>")
for k in ALL7:
    row = [np.mean([S[(c, w)][k] for w in W]) * 100 for c in CELLS]
    gop = np.mean([S[(c, w)][k] for c in CELLS for w in W]) * 100
    m = re.search(r"^%s\s+(.*)$" % re.escape({"DWA": "dwa", "log-MPPI": "log_mppi"}.get(NAMES[k], NAMES[k])), ref, re.M)
    refv = [float(x) for x in m.group(1).split()] if m else []
    check("TEST success row " + NAMES[k], " ".join("%.1f" % x for x in row + [gop]), " ".join("%.1f" % x for x in refv))

# ---- T1 main results
T1rows, T1csv = [], []
rng_pool = np.random.default_rng(SEED + 1)
POOLED = {}
for k in SHOW:
    out, outc = [LONG[k]], [NAMES[k]]
    for c in CELLS:
        kk = sum(S[(c, w)][k] for w in W); lo, hi = wilson(kk, nW)
        out.append("%.1f [%.1f, %.1f]" % (100 * kk / nW, 100 * lo, 100 * hi)); outc += [kk, nW, round(100 * kk / nW, 2), round(100 * lo, 2), round(100 * hi, 2)]
    K = sum(S[(c, w)][k] for c in CELLS for w in W); N = nW * len(CELLS); lo, hi = wilson(K, N)
    dw = np.array([np.mean([S[(c, w)][k] for c in CELLS]) for w in W])
    blo, bhi = boot_ci(dw, rng_pool)
    tt = [float(R[(c, w)][k]["time"]) for c in CELLS for w in W if S[(c, w)][k] == 1]
    POOLED[k] = (100 * K / N, blo, bhi)
    out += ["%.1f [%.1f, %.1f]" % (100 * K / N, 100 * lo, 100 * hi), "[%.1f, %.1f]" % (blo, bhi), "%.1f" % np.mean(tt)]
    outc += [K, N, round(100 * K / N, 2), round(100 * lo, 2), round(100 * hi, 2), round(blo, 2), round(bhi, 2), round(float(np.mean(tt)), 2)]
    T1rows.append(out); T1csv.append(outc)
hdr = ["Planner"] + [CELL_LAB[c] for c in CELLS] + ["Pooled (Wilson)", "Pooled (world bootstrap)", "Time to goal, s"]
hdr_csv = ["config"] + [f"{c}_{x}" for c in CELLS for x in ("k", "n", "pct", "wilson_lo", "wilson_hi")] + \
          ["pooled_k", "pooled_n", "pooled_pct", "pooled_wilson_lo", "pooled_wilson_hi", "pooled_boot_lo", "pooled_boot_hi", "mean_time_success_s"]
with open(os.path.join(TAB, "T1_main_TEST.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(hdr_csv); wr.writerows(T1csv)
write_table("T1_main_TEST", hdr, T1rows,
            f"Fastsim TEST (pre-registered, seeds 100000-101386, the first {nW} worlds containing people, one episode per world "
            "and cell, 0 excluded episodes). Success = goal reached with no collision of any kind, % with Wilson 95 % CI "
            f"(n = {nW} per cell, {nW*5} pooled). Pooled Wilson treats episodes as independent; the world-bootstrap CI "
            "(10 000 resamples of worlds, each world keeps its 5 cells) respects pairing. Time to goal: mean over successful episodes.",
            label="tab:main", colspec="l" + "c" * 8,
            raw_csv_rows=None)
# overwrite csv with the machine-readable version (write_table wrote the display rows first)
with open(os.path.join(TAB, "T1_main_TEST.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(hdr_csv); wr.writerows(T1csv)

# ---- T2 primary family
T2rows, T2csv = [], []
for r in fam:
    k = r["base"]; concl = "C1 better" if (r["holm"] < 0.05 and r["d"] > 0) else "not shown"
    T2rows.append([f"C1 − {NAMES[k]}", str(r["n"]), pct(POOLED[C1][0]), pct(POOLED[k][0]), sgn(r["d"]),
                   "[%+.2f, %+.2f]" % (r["lo"], r["hi"]), g2(r["p"]), g2(r["holm"]), concl])
    T2csv.append([NAMES[k], r["n"], round(POOLED[C1][0], 3), round(POOLED[k][0], 3), round(r["d"], 4), round(r["lo"], 4),
                  round(r["hi"], 4), r["p"], r["holm"], concl, "primary (Holm 3)"])
T2rows.append("MID")
rng_desc = np.random.default_rng(SEED + 2)
for k in (B0, DWA, LOG):
    d = np.array([np.mean([S[(c, w)][C1] - S[(c, w)][k] for c in CELLS]) for w in W])
    lo, hi = boot_ci(d, rng_desc)
    line = "  C1 - %-8s %+5.2f diem (khong kiem dinh)" % ({"DWA": "dwa", "log-MPPI": "log_mppi"}.get(NAMES[k], NAMES[k]), d.mean() * 100)
    check("TEST descriptive " + NAMES[k], line, line if line in ref else "<not found>")
    T2rows.append([f"C1 − {NAMES[k]}", str(nW), pct(POOLED[C1][0]), pct(POOLED[k][0]), sgn(d.mean() * 100),
                   "[%+.2f, %+.2f]" % (lo, hi), "–", "–", "descriptive only"])
    T2csv.append([NAMES[k], nW, round(POOLED[C1][0], 3), round(POOLED[k][0], 3), round(d.mean() * 100, 4), round(lo, 4), round(hi, 4),
                  "", "", "descriptive only (not pre-registered for inference)", "secondary"])
write_table("T2_primary_family", ["Comparison", "Worlds", "C1 %", "Baseline %", "Δ (points)", "95 % CI", "p (perm.)", "p (Holm)", "Conclusion"],
            T2rows,
            "Pre-registered primary family on fastsim TEST. Δ = world-level paired difference in success (mean over the 5 cells), "
            "percentage points. CI: percentile bootstrap over worlds (10 000). p: two-sided sign-flip permutation over worlds "
            "(200 000; the smallest attainable value is 1/200 001 ≈ 5e-6). Holm over the 3 primary comparisons. "
            "Rows below the rule are descriptive (no test was pre-registered); their CIs come from a separate fixed-seed bootstrap.",
            label="tab:primary", colspec="lrrrrcrrl")
with open(os.path.join(TAB, "T2_primary_family.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["baseline", "n_worlds", "C1_pct", "base_pct", "diff_pts", "ci_lo", "ci_hi", "p_perm", "p_holm", "conclusion", "family"]); wr.writerows(T2csv)

# ---- T3 per-cell McNemar (+ bootstrap CI of the per-cell difference, used by F2)
rows3 = []
for k in FAMILY:
    for c in CELLS:
        a = np.array([S[(c, w)][C1] for w in W]); b = np.array([S[(c, w)][k] for w in W])
        up, dn = int(((a == 1) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
        rows3.append(dict(base=k, cell=c, up=up, dn=dn, p=mcnemar_exact(up, dn), a=a.mean() * 100, b=b.mean() * 100, d=(a - b).astype(float)))
for r, h in zip(rows3, holm([r["p"] for r in rows3])):
    r["holm"] = h
rng3 = np.random.default_rng(SEED + 3)
for r in rows3:
    r["lo"], r["hi"] = boot_ci(r["d"], rng3)
    line = "  C1 vs %-6s %-12s +%d/-%d p=%.3g Holm=%.3g" % (NAMES[r["base"]], r["cell"], r["up"], r["dn"], r["p"], r["holm"])
    check(f"TEST McNemar {NAMES[r['base']]} {r['cell']}", line, line if line in ref else "<not found>")
write_table("T3_percell_mcnemar",
            ["Comparison", "Cell", "C1 %", "Baseline %", "Δ (points)", "95 % CI", "C1 only / base only", "p (exact)", "p (Holm 15)"],
            [[f"C1 vs {NAMES[r['base']]}", CELL_LAB[r["cell"]], pct(r["a"]), pct(r["b"]), "%+.1f" % (r["a"] - r["b"]),
              "[%+.1f, %+.1f]" % (r["lo"], r["hi"]), f"{r['up']} / {r['dn']}", "%.3g" % r["p"], "%.3g" % r["holm"]] for r in rows3],
            f"Secondary, per-cell paired comparison on fastsim TEST (n = {nW} worlds per cell). Exact two-sided McNemar test on "
            "discordant pairs; Holm over the 15 cell-level tests. The CI of the per-cell difference is a percentile bootstrap over "
            "worlds (10 000, fixed seed); it is not part of the pre-registration.",
            label="tab:percell", colspec="llrrrcrrr",
            raw_csv_rows=[[NAMES[r["base"]], r["cell"], nW, round(r["a"], 2), round(r["b"], 2), round(r["a"] - r["b"], 2), round(r["lo"], 2),
                           round(r["hi"], 2), r["up"], r["dn"], r["p"], r["holm"]] for r in rows3])
with open(os.path.join(TAB, "T3_percell_mcnemar.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["baseline", "cell", "n", "C1_pct", "base_pct", "diff_pts", "boot_lo", "boot_hi", "c1_only", "base_only", "p_exact", "p_holm15"])
    wr.writerows([[NAMES[r["base"]], r["cell"], nW, round(r["a"], 2), round(r["b"], 2), round(r["a"] - r["b"], 2), round(r["lo"], 2),
                   round(r["hi"], 2), r["up"], r["dn"], r["p"], r["holm"]] for r in rows3])


# ---- T4 failure breakdown
def breakdown(Rows, keys, k):
    cnt = collections.Counter(); fault = [0, 0]
    for key in keys:
        r = Rows[key][k]
        why = "EXC" if (r is None or r["success"] == "") else r["why"]
        cnt[why if why in dict(WHY) or why == "EXC" else "other"] += 1
        if r is not None and r["why"] == "va nguoi":
            fault[1] += 1; fault[0] += r["fault"] == "1"
    n = len(keys)
    return {w: 100 * cnt[w] / n for w, _ in WHY + [("EXC", "EXC"), ("other", "other")]}, fault, n


T4rows, T4csv, FAIL = [], [], {}
for k in SHOW:
    for c in CELLS + ["pooled"]:
        keys = [(c, w) for w in W] if c != "pooled" else [(cc, w) for cc in CELLS for w in W]
        b, fault, n = breakdown(R, keys, k)
        FAIL[(k, c)] = b
        T4csv.append([NAMES[k], c, n] + [round(b[w], 2) for w, _ in WHY] + [round(b["EXC"], 2), round(b["other"], 2), fault[0], fault[1]])
        if c == "pooled" or True:
            T4rows.append([NAMES[k] if c == CELLS[0] else "", CELL_LAB.get(c, "Pooled")] + ["%.1f" % b[w] for w, _ in WHY] +
                          ["%d/%d" % tuple(fault)])
    T4rows.append("MID")
T4rows = T4rows[:-1]
write_table("T4_failure_breakdown", ["Planner", "Cell"] + [lab for _, lab in WHY] + ["at-fault / person coll."], T4rows,
            f"Outcome of every fastsim TEST episode, % of episodes (n = {nW} per cell, {5*nW} pooled). An episode ends at the first "
            "contact. 'Stuck' = no progress (the shared tracker v3 does not count waiting for a tracked person as stuck); "
            "'no path' = global planner found no path. at-fault = robot moving towards the person at contact (fastsim flag); "
            "it is a secondary, noisy indicator (AUDIT: |wz| > 0.3 in 63 % of walking samples) and is reported only as a count.",
            label="tab:failures", colspec="llrrrrrrr")
with open(os.path.join(TAB, "T4_failure_breakdown.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["config", "cell", "n"] + [w.replace(" ", "_") for _, w in WHY] + ["EXC", "other", "person_at_fault", "person_collisions"]); wr.writerows(T4csv)

# =============================================================================================== 2. static-only arm (T5)
SCELLS = ["champ", "champ2", "go2"]
SS, SR, SEXC = load_cells({c: "results/TESTSTATIC_" + c for c in SCELLS}, ALL7)
SW = worlds_all(SS, SCELLS)
check("STATIC worlds", len(SW), 387)
check("STATIC EXC", sum(SEXC.values()), 0)
np_cnt = collections.Counter(SR[(c, w)][k]["npeople"] for c in SCELLS for w in SW for k in ALL7)
check("STATIC npeople all zero", json.dumps(dict(np_cnt)), json.dumps({"0": len(SW) * 3 * 7}))
sref = open(note_input(P("research/TEST_static_results.txt"))).read()
T5rows, T5csv, STAT = [], [], {}
# The coordinator's static-arm script was not saved. Its CIs are reproduced exactly by ONE shared stream
# default_rng(SEED), 20 000 world resamples per comparison, in the order B1, PGIF*, DRA*, B0 (then DWA, log-MPPI here).
# Monte-Carlo error of a bound at this n is about +-0.1 point (a 10 000-draw variant gives B0 [-3.27, -1.03]).
rngS = np.random.default_rng(SEED); SCI = {}
for k in (B1, PGIF, DRA, B0, DWA, LOG):
    d = np.array([np.mean([SS[(c, w)][C1] - SS[(c, w)][k] for c in SCELLS]) for w in SW])
    SCI[k] = (d.mean() * 100, *boot_ci(d, rngS, 20000))
for k in SHOW:
    vals = []
    for c in SCELLS:
        kk = sum(SS[(c, w)][k] for w in SW); vals.append(100 * kk / len(SW))
    K = sum(SS[(c, w)][k] for c in SCELLS for w in SW); N = len(SW) * 3; lo, hi = wilson(K, N)
    b, _, _ = breakdown(SR, [(c, w) for c in SCELLS for w in SW], k)
    STAT[k] = b
    m = re.search(r"^%s\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+gop\s+([\d.]+)" % re.escape({"DWA": "dwa", "log-MPPI": "log_mppi"}.get(NAMES[k], NAMES[k])), sref, re.M)
    check("STATIC row " + NAMES[k], " ".join("%.1f" % x for x in vals + [100 * K / N]), " ".join(m.groups()) if m else "<not found>")
    if k == C1:
        dtxt = ("–", "–")
    else:
        dm, blo, bhi = SCI[k]
        dtxt = ("%+.2f" % dm, "[%+.2f, %+.2f]" % (blo, bhi))
        if k in (B1, PGIF, DRA, B0):
            line = "C1-%-6s %+.2f [%+.2f; %+.2f]" % (NAMES[k], dm, blo, bhi)
            check("STATIC C1-" + NAMES[k], line, line if line in sref else "<not found>")
    verdict = ""
    if k == B1:
        verdict = "non-inferior (margin −2): " + ("met" if blo > -2 else "NOT met")
    T5rows.append([LONG[k]] + ["%.1f" % v for v in vals] + ["%.1f [%.1f, %.1f]" % (100 * K / N, 100 * lo, 100 * hi),
                   "%.1f" % b["ket"], "%.1f" % b["va vat"], "%.1f" % b["het gio"], dtxt[0], dtxt[1], verdict])
    T5csv.append([NAMES[k]] + [round(v, 2) for v in vals] + [round(100 * K / N, 2), round(100 * lo, 2), round(100 * hi, 2),
                  round(b["ket"], 2), round(b["va vat"], 2), round(b["het gio"], 2), dtxt[0], dtxt[1], verdict])
write_table("T5_static_only", ["Planner", "CHAMP", "CHAMP2", "Go2", "Pooled [Wilson]", "Stuck %", "Static coll. %", "Timeout %",
                               "C1 − X", "95 % CI", "Test"], T5rows,
            f"Static-only arm (pre-registered addendum #2 of PREREG_TEST): all {len(SW)} seeds in 100000-101386 WITHOUT people "
            "(complement of the TEST set), 3 dynamics regimes, one episode each. C1 − X: world-level paired difference (points), "
            "percentile bootstrap over worlds (20 000). Only C1 vs B1 was pre-registered, as a non-inferiority test with margin −2 points; "
            "other differences are descriptive.", label="tab:static", colspec="lrrrcrrrrcl")
with open(os.path.join(TAB, "T5_static_only.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["config", "champ_pct", "champ2_pct", "go2_pct", "pooled_pct", "wilson_lo", "wilson_hi", "stuck_pct",
                                     "static_collision_pct", "timeout_pct", "C1_minus_X_pts", "boot_ci", "test"]); wr.writerows(T5csv)

# =============================================================================================== 3. ablation (T6)
ABL = [("p3+geo-haz+gcv-grad~t3~nl:ppl=32;ppl_len=0.5", "− grad (temperature fix)"),
       ("p3+geo-haz+gcv-prim~t3~nl:ppl=32;ppl_len=0.5", "− prim (evasive primitive samples)"),
       ("p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5;g_tau=99", "− time discount (τ = ∞)"),
       ("p3+geo-haz+gcv~nl:ppl=32;ppl_len=0.5", "− tracker v3 (use v2)"),
       ("p3+geo-haz+gcv~t3:ppl=32;ppl_len=0.5", "− RespModel (~nl)"),
       ("p3-haz~t3~nl:ppl=32;ppl_len=0.5", "geo risk → plain people cost")]
ACELLS = {"champ": "results/algo_Wchamp_base", "champ2": "results/algo_Wchamp2_base", "go2": "results/algo_Wgo2_base"}


def algo_confirm(refs, cands, cells, nlog):
    """Replica of research/algo_confirm.py (rng 0, 100 000 sign flips, Holm over all tests, Bonferroni over LOG rows)."""
    D = {}
    for n, d in cells.items():
        for f in sorted(glob.glob(P(d, "w*.csv"))):
            note_input(f)
            for r in csv.DictReader(open(f)):
                if r["success"] != "":
                    D.setdefault((n, r["config"]), {})[r["world"]] = r
    T, tab = [], {}
    for c in cands + refs:
        tab[c] = {}
        for n in cells:
            g = D[(n, c)]; k = sum(int(r["success"]) for r in g.values()); m = len(g)
            col = sum(1 for r in g.values() if r["col"]); t = np.mean([float(r["time"]) for r in g.values() if r["success"] == "1"])
            tab[c][n] = (k, m, col, t)
    rng = np.random.default_rng(0); pooled = {}
    for c in cands:
        for b in refs:
            diff = {}
            for n in cells:
                A, Bq = D[(n, c)], D[(n, b)]; ks = sorted(set(A) & set(Bq))
                x = sum(int(A[q]["success"]) > int(Bq[q]["success"]) for q in ks); y = sum(int(A[q]["success"]) < int(Bq[q]["success"]) for q in ks)
                p = min(1, 2 * sum(comb(x + y, i) for i in range(min(x, y) + 1)) / 2 ** (x + y)) if x + y else 1
                T.append((p, ("cell", c, b, n, len(ks), x, y)))
                for q in ks:
                    diff[q] = diff.get(q, 0) + int(A[q]["success"]) - int(Bq[q]["success"])
            v = np.array(list(diff.values()), float)
            s = abs(v.sum()); sg = rng.choice([-1., 1.], size=(100000, len(v)))
            p = (1 + (np.abs(sg @ v) >= s - 1e-9).sum()) / 100001
            nn = sum(len(set(D[(n, c)]) & set(D[(n, b)])) for n in cells)
            T.append((p, ("pool", c, b, len(v), 100 * v.sum() / nn)))
            pooled[(c, b)] = (p, 100 * v.sum() / nn, v)
    T.sort(key=lambda t: t[0]); m = len(T); mx = 0; out = []
    for i, (p, info) in enumerate(T):
        mx = max(mx, min(1, p * (m - i))); out.append((p, mx, min(1, p * nlog), info))
    return tab, out, pooled


tabA, outA, poolA = algo_confirm([a for a, _ in ABL], [C1], ACELLS, 533)
aref = open(note_input(P("research/algo_ablation2.txt"))).read()
for p, h, bf, info in outA:
    if info[0] == "pool":
        s = f"p={p:.2g} Holm={h:.2g} Bonf(533)={bf:.2g} {info[1]} vs {info[2]} [GOP {info[3]} the gioi] {info[4]:+.1f} diem"
    else:
        _, c, b, n, nk, x, y = info
        s = f"p={p:.2g} Holm={h:.2g} Bonf(533)={bf:.2g} {c} vs {b} [{n}] n={nk} +{x}/-{y} ({100*(x-y)/nk:+.1f} diem)"
    check("ABLATION " + s[:60], s, s if s in aref else "<not found>")
holmA = {(info[2]): (p, h) for p, h, bf, info in outA if info[0] == "pool"}
rngA = np.random.default_rng(SEED + 4)
T6rows, T6csv, ABLPLOT = [], [], []
for cfg, lab in [(C1, "C1 (full)")] + ABL:
    t = tabA[cfg]; cellv = [100 * t[n][0] / t[n][1] for n in ACELLS]
    K = sum(t[n][0] for n in ACELLS); N = sum(t[n][1] for n in ACELLS)
    if cfg == C1:
        T6rows.append([lab] + ["%.1f" % x for x in cellv] + ["%.1f" % (100 * K / N), "–", "–", "–", "–"])
        T6csv.append([lab, cfg] + [round(x, 2) for x in cellv] + [round(100 * K / N, 2), "", "", "", "", ""]); continue
    p, h = holmA[cfg]; _, dd, v = poolA[(C1, cfg)]
    lo, hi = boot_ci(-v / len(ACELLS), rngA)                     # ablated − C1, per world mean over 3 cells
    ABLPLOT.append((lab, -dd, lo, hi, h))
    T6rows.append([lab] + ["%.1f" % x for x in cellv] + ["%.1f" % (100 * K / N), "%+.1f" % (-dd), "[%+.1f, %+.1f]" % (lo, hi), g2(p), g2(h)])
    T6csv.append([lab, cfg] + [round(x, 2) for x in cellv] + [round(100 * K / N, 2), round(-dd, 3), round(lo, 3), round(hi, 3), p, h])
# part B: round-3 simplification candidates (non-inferiority, research/algo_noninf.py replica)
YC = {"champ": "results/algo_Ychamp_base", "champ2": "results/algo_Ychamp2_base", "go2": "results/algo_Ygo2_base",
      "champ2h": "results/algo_Ychamp2_helb", "go2h": "results/algo_Ygo2_helb"}
NONINF = [("p3-haz-grad~t3:ppl=64;ppl_len=0.5", "C4: MPPI + prim, no RespModel"),
          ("p3-haz-grad~t3~nl:ppl=100;ppl_len=0.5", "C4': MPPI + prim + RespModel"),
          ("p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5;g_tau=99", "C5: C1 − grad − discount − RespModel")]
Dn = {}
for n, d in YC.items():
    for f in sorted(glob.glob(P(d, "w*.csv"))):
        note_input(f)
        for r in csv.DictReader(open(f)):
            if r["success"] != "":
                Dn.setdefault(r["config"], {})[(n, r["world"])] = int(r["success"])
rngN = np.random.default_rng(0)
nref = open(note_input(P("research/algo_noninf3.txt"))).read()
T6rows.append("MID")
for cfg, lab in NONINF:
    Kk = sorted(set(Dn[cfg]) & set(Dn[C1])); Wn = sorted({w for _, w in Kk})
    s_ = {w: [0, 0] for w in Wn}
    for (n, w) in Kk:
        s_[w][0] += Dn[cfg][(n, w)] - Dn[C1][(n, w)]; s_[w][1] += 1
    d = np.array([s_[w][0] for w in Wn], float); m = np.array([s_[w][1] for w in Wn], float)
    est = 100 * d.sum() / m.sum(); Bi = rngN.integers(0, len(Wn), size=(20000, len(Wn))); bs = 100 * d[Bi].sum(1) / m[Bi].sum(1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    line = f"{cfg} - {C1}: {est:+.2f} diem [{lo:+.2f}; {hi:+.2f}]  (the gioi {len(Wn)}, cap {int(m.sum())})"
    check("NONINF " + lab, line, line if line in nref else "<not found>")
    succ = 100 * sum(Dn[cfg].values()) / len(Dn[cfg])
    T6rows.append([lab + " [round 3, 5 cells]", "", "", "", "%.1f" % succ, "%+.2f" % est, "[%+.2f, %+.2f]" % (lo, hi), "–",
                   "non-inferior: " + ("yes" if lo > -2 else "no")])
    T6csv.append([lab, cfg, "", "", "", round(succ, 2), round(est, 3), round(lo, 3), round(hi, 3), "", "noninf_margin_-2:" + ("yes" if lo > -2 else "no")])
write_table("T6_ablation", ["Variant", "CHAMP", "CHAMP2", "Go2", "Pooled %", "Δ vs C1", "95 % CI", "p (perm.)", "p (Holm 24) / test"], T6rows,
            "Ablation (confirmation round 2, seeds 1000-1499, 348 worlds with people per cell, base crowd, three regimes; run once). "
            "Each row removes one component from C1. Δ = variant − C1, pooled over cells (points); p: two-sided sign-flip permutation over "
            "worlds (100 000); Holm over the 24 tests of that round (6 pooled + 18 per-cell). CI: percentile bootstrap over worlds (10 000, "
            "fixed seed; added here, not in the original analysis). Below the rule: round-3 simplification candidates (seeds 1500-1999, 357 worlds x 5 cells), "
            "pre-registered non-inferiority rule: lower CI bound of Δ > −2 points (bootstrap 20 000). No candidate passed, so C1 was frozen.",
            label="tab:ablation", colspec="lrrrrrcrl")
with open(os.path.join(TAB, "T6_ablation.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["variant", "config", "champ_pct", "champ2_pct", "go2_pct", "pooled_pct", "diff_vs_C1_pts", "ci_lo", "ci_hi", "p_perm", "p_holm24_or_test"]); wr.writerows(T6csv)

# =============================================================================================== 4. timing (T7)
trows, tcsv = [], []
for line in open(note_input(P("research/algo_timing.txt"))):
    m = re.match(r"(\S+) (numpy|C) TB ([\d.]+) ms, p99 ([\d.]+) ms, max ([\d.]+)", line.strip())
    if m:
        cfg, impl, mean, p99, mx = m.groups(); nm = NAMES.get(cfg, "C3 (C1 + occlusion, rejected)" if "occ" in cfg else cfg)
        tcsv.append(["fastsim (dev laptop, seed 93)", nm, impl, mean, "", p99, mx, "research/algo_timing.txt"])
gz = open(note_input(P("results/GZ_smoke/smoke_check.txt"))).read()
for nm, key in (("C1", "p3\\+geo-haz\\+gcv"), ("B1", "mppi")):
    m = re.search(key + r": cmd_vel p50 ([\d.]+) s p95 ([\d.]+) s.*?ctrl\.step p50 ([\d.]+) p95 ([\d.]+) max ([\d.]+) ms \(n=(\d+)\)", gz)
    tcsv.append(["Gazebo smoke test (DEV worlds, 40 episodes)", nm, "C (fast.so)", "", m.group(3), m.group(4) + " (p95)", m.group(5),
                 f"results/GZ_smoke/smoke_check.txt; n={m.group(6)} steps; cmd_vel period p50 {m.group(1)} s, p95 {m.group(2)} s"])
for r in tcsv:
    trows.append([r[0], r[1], r[2], r[3] or "–", r[4] or "–", r[5], r[6]])
write_table("T7_compute_time", ["Setting", "Planner", "Implementation", "Mean (ms)", "Median (ms)", "p99 / p95 (ms)", "Max (ms)"], trows,
            "Planner computation time per control step (10 Hz loop, budget 100 ms; project limit 40 ms). fastsim rows: one DEV episode "
            "(seed 93) on the development laptop with background load ~5-9 (research/algo_timing.txt); 'C' = optional C kernels for A* and argmin "
            "(bit-identical output). The DRA* maximum is the one-off construction of the non-central chi-square lookup table at the first step. "
            "Gazebo rows: ctrl.step wall time during the 40-episode Gazebo smoke test (S2). Not yet measured on the robot's Jetson Orin.",
            label="tab:timing", colspec="llllrrr", raw_csv_rows=tcsv)
with open(os.path.join(TAB, "T7_compute_time.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["setting", "planner", "implementation", "mean_ms", "median_ms", "p99_or_p95_ms", "max_ms", "source"]); wr.writerows(tcsv)

# =============================================================================================== 5. dynamics (T8)
src = open(note_input(P("pipeline/sysid_fit2.py"))).read()
note_input(P("results/sysid.npz"))
g = {"__file__": P("pipeline/sysid_fit2.py"), "__name__": "sysid_fit2_prefix"}
exec(src.split('for nm, m in (("ly tuong"')[0], g)                    # definitions + data only (no grid search)
E2 = {nm: g["err"](g[key], g["runs"], 2)[:, 0].mean() for nm, key in (("ideal", "ideal"), ("champ", "old"), ("champ2", "new"))}
check("sysid_fit2 2 s error ideal", round(E2["ideal"], 3), 0.169, 0.0005)
check("sysid_fit2 2 s error champ(old)", round(E2["champ"], 3), 0.088, 0.0005)
check("sysid_fit2 2 s error champ2(new)", round(E2["champ2"], 3), 0.062, 0.0005)
tr = open(note_input(P("isaac_val/tables_random.md"))).read()
blocks = {}
for blk in re.split(r"^### ", tr, flags=re.M)[1:]:
    title = blk.split("\n")[0]
    gains = dict((a.strip(), tuple(float(x) for x in b.split(","))) for a, b in re.findall(r"^\| (.+?) \| gain, CI95, n: \((.+?)\) \|", blk, re.M))
    pred = dict((a.strip(), [float(x) for x in b.split(",")]) for a, b in re.findall(r"^\| du doan (.+?) \| 1 s: \[.+?\] \| 2 s: \[(.+?)\]", blk, re.M))
    blocks[title.split(" so doan")[0]] = (gains, pred)
fl, ro, ch = blocks["flat_random"], blocks["rough_random"], blocks["CHAMP Gazebo"]
dyn = yaml.safe_load(open(note_input(P("dyn/go2_params.yaml"))))["command_response"]
fmtg = lambda t: "%.2f [%.2f, %.2f]" % t[:3]
FLAG = {"do_that": "measured", "gian_tiep": "indirect", "tai_lieu": "literature", "gia_dinh": "assumed"}
dv = lambda key: "%.2f (%.2f–%.2f) [%s]" % (dyn[key]["c"], dyn[key]["lo"], dyn[key]["hi"], FLAG[dyn[key]["flag"]])
T8 = [["Gain vx, |cmd| 0.05–0.2", fmtg(ch[0]["vx 0.05-0.2"]), "0.88–1.02, tanh sat. 0.26–0.32 m/s", "1.0 (0.92–1.06), clip 0.30", fmtg(ro[0]["vx 0.05-0.2"]), fmtg(fl[0]["vx 0.05-0.2"]), dv("gain_x")],
      ["Gain vx, |cmd| 0.2–0.4", fmtg(ch[0]["vx .2-.4"]), "tanh saturation", "clip 0.30", fmtg(ro[0]["vx .2-.4"]), fmtg(fl[0]["vx .2-.4"]), "as above"],
      ["Gain vx, |cmd| 0.4–0.6", fmtg(ch[0]["vx .4-.6"]), "saturates ≈0.29 m/s", "clipped at 0.30 m/s", fmtg(ro[0]["vx .4-.6"]), fmtg(fl[0]["vx .4-.6"]), "no saturation seen up to 1.4 m/s [measured]"],
      ["Gain vx, reverse ≤ 0.2", fmtg(ch[0]["vx lui"]), "×1.10–1.35", "1.0 + drift −0.04…−0.065 m/s", fmtg(ro[0]["vx lui"]), fmtg(fl[0]["vx lui"]), dv("back_x")],
      ["Gain vy, |cmd| 0.15–0.3", fmtg(ch[0]["vy |.15-.3|"]), "0.90–1.03", "0.92–1.06, clip 0.25", fmtg(ro[0]["vy |.15-.3|"]), fmtg(fl[0]["vy |.15-.3|"]), dv("gain_y")],
      ["Gain wz, turning in place", fmtg(ch[0]["wz tai cho"]), "0.75–0.95", "0.95–1.15, clip 0.5", fmtg(ro[0]["wz tai cho"]), fmtg(fl[0]["wz tai cho"]), dv("gain_w")],
      ["Gain wz, while |v| > 0.25", fmtg(ch[0]["wz khi |v|>.25"]), "as above", "as above", fmtg(ro[0]["wz khi |v|>.25"]), fmtg(fl[0]["wz khi |v|>.25"]), "as above"],
      ["Time constant τ x / y / wz (s)", "–", "0.12–0.20 / 0.12–0.20 / 0.20–0.30", "0.08–0.16 / 0.08–0.16 / 0.06–0.14", "0.12–0.24 (vx 0.4–1.0)", "0.06–0.22 (vx 0.4–1.0)",
       "%.2f / %.2f / %.2f [%s / %s / %s]" % (dyn["tau_x"]["c"], dyn["tau_y"]["c"], dyn["tau_w"]["c"], FLAG[dyn["tau_x"]["flag"]], FLAG[dyn["tau_y"]["flag"]], FLAG[dyn["tau_w"]["flag"]])],
      ["Command delay (s)", "–", "0.05", "0–0.05", "0.00–0.05 (lower bound)", "0.00–0.05", dv("delay_s")],
      ["Stop: distance / v0 (s)", "–", "–", "–", "–", "–", "%.2f (%.2f–%.2f) [measured, upper bound]" % (dyn["stop_distance_over_v0_s"]["c"], dyn["stop_distance_over_v0_s"]["lo"], dyn["stop_distance_over_v0_s"]["hi"])],
      ["2-s open-loop error on CHAMP log (m)", "ideal v=cmd %.3f" % E2["ideal"], "%.3f" % E2["champ"], "%.3f" % E2["champ2"], "–", "–", "–"],
      ["2-s open-loop error on Isaac rough / flat (m)", "–", "%.3f / %.3f" % (ro[1]["fastsim champ (giua)"][0], fl[1]["fastsim champ (giua)"][0]),
       "%.3f / %.3f" % (ro[1]["fastsim champ2 (giua)"][0], fl[1]["fastsim champ2 (giua)"][0]),
       "ideal %.3f; go2 %.3f" % (ro[1]["ly tuong (v=lenh)"][0], ro[1]["fastsim go2/DYN (giua)"][0]),
       "ideal %.3f; go2 %.3f" % (fl[1]["ly tuong (v=lenh)"][0], fl[1]["fastsim go2/DYN (giua)"][0]), "–"]]
write_table("T8_dynamics", ["Quantity", "CHAMP in Gazebo (measured)", "fastsim champ", "fastsim champ2", "Isaac Lab rough policy", "Isaac Lab flat policy", "Real Go2 (DYN)"], T8,
            "Velocity-command dynamics. CHAMP/Isaac gains: steady-state v/cmd with bootstrap 95 % CI over segments, same code for all bodies "
            "(isaac_val/tables_random.md; CHAMP from results/sysid.npz, 150 segments; Isaac 16 robots x 120 s, ~1134 segments, observation noise off). "
            "fastsim columns: per-episode sampling ranges in the frozen fastsim.py (lines 258-282). champ2 = gait.yaml command clipping 0.30/0.25/0.50 "
            "plus a ~0.053 m/s backward drift while stepping (pipeline/sysid_fit2.py). 2-s error: mean position error of open-loop prediction from "
            "commands (CHAMP log: 121 non-overlapping windows, recomputed here; Isaac: 400 windows, from tables_random.md). "
            "Real Go2: dyn/go2_params.yaml; flags: measured (own logs, LiDAR odometry as reference) / indirect / literature / assumed. "
            "The available real-dog logs contain NO velocity commands, so gain, delay and τ of the real dog are literature values or assumptions.",
            label="tab:dynamics", colspec="lllllll")

# =============================================================================================== 6. fidelity + Isaac (T9)
Gz = list(csv.DictReader(open(note_input(P("results/final_office_merged/trials.csv")))))
gz_by = collections.defaultdict(list); gz_task = collections.defaultdict(list)
for r in Gz:
    gz_by[r["config"]].append(int(r["success"])); gz_task[(r["config"], r["task"])].append(int(r["success"]))
FS = {}
for reg in ("champ", "champ2"):
    F = collections.defaultdict(list); Ft = collections.defaultdict(list)
    for f in sorted(glob.glob(P(f"results/coord_fid_{reg}/w*.csv"))):
        note_input(f)
        for r in csv.DictReader(open(f)):
            c = r["config"].replace("~v1", ""); F[c].append(int(r["success"])); Ft[(c, r["world"])].append(int(r["success"]))
    FS[reg] = (F, Ft)
cfgF = sorted(FS["champ"][0]); tasks = sorted({t for (_, t) in gz_task})
rho = {}
for reg in ("champ", "champ2"):
    x = [np.mean(FS[reg][0][c]) for c in cfgF]; y = [np.mean(gz_by[c]) for c in cfgF]
    rho[reg] = (spearmanr(x, y)[0], kendalltau(x, y)[0])
check("fidelity Spearman champ", round(rho["champ"][0], 2), 0.90, 0.005)
check("fidelity Spearman champ2", round(rho["champ2"][0], 2), 0.59, 0.005)
rngF = np.random.default_rng(SEED + 5); bsd = []
for _ in range(5000):                                   # bootstrap over the 8 tasks (same tasks for both regimes and Gazebo)
    tk = rngF.integers(0, len(tasks), len(tasks)); rr = []
    for reg in ("champ", "champ2"):
        x = [np.mean([s for i in tk for s in FS[reg][1][(c, tasks[i])]]) for c in cfgF]
        y = [np.mean([s for i in tk for s in gz_task[(c, tasks[i])]]) for c in cfgF]
        rr.append(spearmanr(x, y)[0])
    bsd.append(rr[0] - rr[1])
dlo, dhi = np.nanpercentile(bsd, [2.5, 97.5])
dmean = float(np.nanmean(bsd))
CHECK_LINES.append(f"INFO  fidelity Δρ(champ−champ2) bootstrap over tasks (this package, seed {SEED+5}, 5000): {rho['champ'][0]-rho['champ2'][0]:+.2f} [{dlo:+.2f}, {dhi:+.2f}], bootstrap mean {dmean:+.2f}; "
                   "coordinator (RESEARCH_NOTES 7.12, script not saved): 'chenh 0.14 [−0.12, +0.41]' = bootstrap MEAN, not the point estimate (+0.31). DISCREPANCY (conclusion unchanged).")


# Isaac pilot (replica of isaac_val/pilot_stats.py)
def kendall_noties(a, b):
    n = len(a); s = t = 0
    for i in range(n):
        for j in range(i + 1, n):
            x, y = a[i] - a[j], b[i] - b[j]
            if x == 0 or y == 0:
                continue
            t += 1; s += 1 if x * y > 0 else -1
    return s / t if t else float("nan")


def load_fs(dirs):
    out = {}
    for d in dirs:
        for f in sorted(glob.glob(P(d, "w*.csv"))):
            note_input(f)
            for r in csv.DictReader(open(f)):
                if r["success"] == "" or r.get("trial", "0") != "0":
                    continue
                out[(r["config"], int(r["world"]))] = r
    return out


def load_isaac(name):
    out = {}
    for r in csv.DictReader(open(note_input(P("isaac_val", name + ".csv")))):
        if r["success"] in ("", "success"):
            continue
        out[(r["config"], int(r["world"]))] = r
    return out


ICFG = ["mppi", "mppi:ppl=32", "dwa", B1, C1]
ILAB = {"mppi": "MPPI (default)", "mppi:ppl=32": "B0", "dwa": "DWA (default)", B1: "B1", C1: "C1"}
iso = load_isaac("res_pilot")
bodies = {"Isaac rough+noise": iso, "fastsim go2": load_fs(["results/isaac_fs_go2", "results/algo_Vgo2_base"]),
          "fastsim champ2": load_fs(["results/isaac_fs_champ2", "results/algo_Vchamp2_base"]), "fastsim champ": load_fs(["results/isaac_fs_champ"])}
seeds = sorted({w for (c, w) in iso})
SR_I = {}
for b, Dd in bodies.items():
    for c in ICFG:
        gg = [Dd[(c, w)] for w in seeds if (c, w) in Dd]; SR_I[(b, c)] = (sum(r["success"] == "1" for r in gg), len(gg))
tau = {b: kendall_noties([SR_I[("Isaac rough+noise", c)][0] for c in ICFG], [SR_I[(b, c)][0] for c in ICFG]) for b in list(bodies)[1:]}
check("Isaac tau go2", round(tau["fastsim go2"], 2), 1.0); check("Isaac tau champ2", round(tau["fastsim champ2"], 2), 0.8)
check("Isaac tau champ", round(tau["fastsim champ"], 2), 1.0)
check("Isaac pilot C1 success", SR_I[("Isaac rough+noise", C1)][0], 83); check("Isaac pilot B1 success", SR_I[("Isaac rough+noise", B1)][0], 75)
T9 = [["A. fastsim vs Gazebo (8 office tasks x 4-5 trials, 12 planners)", "", "", "", ""],
      ["fastsim champ vs Gazebo CHAMP", "Spearman ρ = %.2f; Kendall τ-b = %.2f" % rho["champ"], "12 planners", "results/coord_fid_champ; results/final_office_merged", ""],
      ["fastsim champ2 vs Gazebo CHAMP", "Spearman ρ = %.2f; Kendall τ-b = %.2f" % rho["champ2"], "12 planners", "results/coord_fid_champ2", ""],
      ["Difference ρ(champ) − ρ(champ2)", "%+.2f, task-bootstrap 95 %% CI [%+.2f, %+.2f] (bootstrap mean %+.2f)" % (rho["champ"][0] - rho["champ2"][0], dlo, dhi, dmean), "8 tasks", "this package", "inconclusive (CI contains 0)"],
      "MID", ["B. Isaac Lab cross-check, pilot (100 DEV worlds 302-439, base crowd)", "", "", "", ""]]
for b in bodies:
    T9.append([b, "; ".join("%s %d/%d" % (ILAB[c], *SR_I[(b, c)]) for c in ICFG),
               ("Kendall τ vs Isaac = %+.2f" % tau[b]) if b in tau else "reference", "isaac_val/res_pilot.csv" if b.startswith("Isaac") else "results/isaac_fs_*, algo_V*", ""])
falls = {c: sum(r["why"] == "nga" for (cc, w), r in iso.items() if cc == c) for c in ICFG}
T9.append(["Isaac falls (counted as failure)", "; ".join("%s %d" % (ILAB[c], falls[c]) for c in ICFG), "", "isaac_val/res_pilot.csv", "falls only exist in Isaac"])
T9 += ["MID", ["C. Isaac v3 (reproducible server), C1 vs B1 on the same 100 worlds", "", "", "", ""]]
IV3 = [("res_nl", "~t3~nl (as frozen), tilted rays", B1, C1), ("res_t3", "without ~nl", "mppi~t3:ppl=100;ppl_len=0.5", "p3+geo-haz+gcv~t3:ppl=32;ppl_len=0.5"),
       ("res_nlnotilt", "~t3~nl, flat rays", B1, C1), ("res_nlcs", "~t3~nl + command shaper ~cs (deployment option, not part of C1)", B1, C1)]
T9csv = []
for name, lab, bb, cc in IV3:
    Dd = load_isaac(name); ws = sorted({w for (_, w) in Dd})
    a = np.array([Dd[(cc, w)]["success"] == "1" for w in ws]); b_ = np.array([Dd[(bb, w)]["success"] == "1" for w in ws])
    up, dn = int((a & ~b_).sum()), int((~a & b_).sum())
    fa = sum(Dd[(cc, w)]["why"] == "nga" for w in ws); fb = sum(Dd[(bb, w)]["why"] == "nga" for w in ws)
    T9.append([f"Isaac {name[4:]}: {lab}", "C1 %d/%d (falls %d); B1 %d/%d (falls %d)" % (a.sum(), len(ws), fa, b_.sum(), len(ws), fb),
               "McNemar +%d/−%d, p = %.2g" % (up, dn, mcnemar_exact(up, dn)), f"isaac_val/{name}.csv", ""])
    T9csv.append([name, lab, int(a.sum()), int(b_.sum()), len(ws), fa, fb, up, dn, mcnemar_exact(up, dn)])
write_table("T9_fidelity_isaac", ["Comparison", "Result", "Statistic", "Source", "Note"], T9,
            "Simulator fidelity and Isaac Lab cross-check. (A) Rank agreement of success rates between fastsim (virtual clock, same planner code) "
            "and 960 Gazebo/CHAMP episodes on 8 office tasks (development tasks, all 12 then-existing planners). The task-bootstrap CI of the "
            "difference is recomputed here with a fixed seed. (B) Isaac Lab 5.1 official Go2 rough-terrain policy with observation noise as an "
            "independent body (rays/crowd/tracker are still fastsim code), 100 DEV worlds, one episode each; Kendall τ ignores tied pairs "
            "(isaac_val/pilot_stats.py). Pilot episodes are not replayable individually (server v1/v2). (C) Re-runs with the deterministic v3 server.",
            label="tab:fidelity", colspec="lllll")
with open(os.path.join(TAB, "T9_isaac_v3.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["run", "variant", "C1_success", "B1_success", "n", "C1_falls", "B1_falls", "C1_only", "B1_only", "p_mcnemar"]); wr.writerows(T9csv)

# =============================================================================================== 7. replication (T10)
ROUNDS = [("R1 confirm (seeds 300-799)", "algo_V", [B1], [B1, B0, C1]),
          ("R2 confirm (seeds 1000-1499)", "algo_W", FAMILY, [B1, PGIF, DRA, B0, C1]),
          ("R3 confirm (seeds 1500-1999)", "algo_Y", FAMILY, [B1, PGIF, DRA, C1]),
          ("VAL (seeds 2000-2399)", "VAL_", FAMILY, ALL7),
          ("TEST (seeds 100000-101386)", "TEST_", FAMILY, ALL7)]
REPORTED = {("R1 confirm (seeds 300-799)", B1): "5.7", ("R2 confirm (seeds 1000-1499)", B1): "6.6", ("R2 confirm (seeds 1000-1499)", PGIF): "5.2",
            ("R2 confirm (seeds 1000-1499)", DRA): "3.2", ("R3 confirm (seeds 1500-1999)", B1): "7.2", ("R3 confirm (seeds 1500-1999)", PGIF): "6.1",
            ("R3 confirm (seeds 1500-1999)", DRA): "2.8", ("VAL (seeds 2000-2399)", B1): "9.08", ("VAL (seeds 2000-2399)", PGIF): "6.22",
            ("VAL (seeds 2000-2399)", DRA): "4.51", ("TEST (seeds 100000-101386)", B1): "6.96", ("TEST (seeds 100000-101386)", PGIF): "4.98",
            ("TEST (seeds 100000-101386)", DRA): "2.66"}
REPSRC = {"R1": "RESEARCH_NOTES 7.14", "R2": "research/algo_confirm2.txt", "R3": "research/algo_confirm3_C1.txt", "VAL": "research/VAL_results.txt", "TEST": "research/TEST_fastsim_results.txt"}
vref = open(note_input(P("research/VAL_results.txt"))).read()
T10rows, T10csv, REP = [], [], {}
for lab, pre, famk, cfgs in ROUNDS:
    Sx, _, ex = load_cells({c: f"results/{pre}{c}" for c in CELLS}, cfgs)
    Wx = worlds_all(Sx, CELLS)
    res = primary_family(Sx, CELLS, Wx, famk)
    for r in res:
        rep = REPORTED[(lab, r["base"])]
        check(f"T10 point estimate {lab} {NAMES[r['base']]}", "%.*f" % (len(rep.split(".")[1]), r["d"]), rep)
        if pre == "VAL_":
            line = "C1 - %-6s %+5.2f diem  KTC95 [%+.2f; %+.2f]  p=%.2g  Holm=%.2g" % (NAMES[r["base"]], r["d"], r["lo"], r["hi"], r["p"], r["holm"])
            check("VAL primary " + NAMES[r["base"]], line, line if line in vref else "<not found>")
        REP[(lab, r["base"])] = r
        T10rows.append([lab, len(Wx), "C1 − " + NAMES[r["base"]], "%+.2f" % r["d"], "[%+.2f, %+.2f]" % (r["lo"], r["hi"]), g2(r["p"]), g2(r["holm"]),
                        "+%s (%s)" % (rep, REPSRC[lab.split()[0]])])
        T10csv.append([lab, len(Wx), NAMES[r["base"]], round(r["d"], 4), round(r["lo"], 4), round(r["hi"], 4), r["p"], r["holm"], rep, REPSRC[lab.split()[0]], len(famk)])
    if B0 in cfgs:
        d = np.array([np.mean([Sx[(c, w)][C1] - Sx[(c, w)][B0] for c in CELLS]) for w in Wx])
        T10rows.append([lab, len(Wx), "C1 − B0 (descriptive)", "%+.2f" % (d.mean() * 100), "–", "–", "–", ""])
        T10csv.append([lab, len(Wx), "B0", round(d.mean() * 100, 4), "", "", "", "", "", "descriptive", ""])
    T10rows.append("MID")
T10rows = T10rows[:-1]
write_table("T10_replication", ["Seed set", "Worlds", "Comparison", "Δ (points)", "95 % CI", "p (perm.)", "p (Holm)", "Originally reported"], T10rows,
            "Replication of the C1 advantage on five disjoint seed sets with people (all 5 cells; one episode per world and cell). "
            "Every row is recomputed here with the TEST procedure (world-level paired difference, 200 000 sign flips, 10 000 bootstrap, "
            "Holm within the round over the available paper baselines). R1-R3 were confirmation rounds during development (each run once, "
            "after the candidate was locked); R1 predates the PGIF*/DRA* reimplementations. Only TEST is confirmatory; VAL is supporting evidence "
            "and TEST/VAL are not pooled (PREREG_TEST §6). Rounds R1-R3 originally used a different permutation/bootstrap implementation, so "
            "p values and CIs differ slightly from the round reports; point estimates are identical.",
            label="tab:replication", colspec="lrlrcrrl")
with open(os.path.join(TAB, "T10_replication.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["seed_set", "n_worlds", "baseline", "diff_pts", "ci_lo", "ci_hi", "p_perm", "p_holm", "reported_diff", "reported_source", "family_size"]); wr.writerows(T10csv)

# =============================================================================================== 8. Gazebo TEST + Isaac TEST (T11, T11b)
import subprocess
GZ_DIR, GZ_DRA_DIR = "results/GZ_TEST", "results/GZ_TEST_DRA"


def load_gz(root):
    by_ = collections.defaultdict(dict); files = sorted(glob.glob(P(root, "s*", "g*", "trials.csv")))
    for f in files:
        for r in csv.DictReader(open(f)):
            by_[r["config"]][int(r["seed"])] = r
    return by_, files


gz, gz_files = load_gz(GZ_DIR)
for f in gz_files:
    note_input(f)
gpair = sorted(set(gz[C1]) & set(gz[B1]))
check("GZ pairs (registered 680)", len(gpair), 680)
check("GZ sha_ok all rows", sum(str(r.get("sha_ok")) == "1" for d in (gz[C1], gz[B1]) for r in d.values()), 1360)
gzs = {k: sum(int(gz[k][w]["success"]) for w in gpair) for k in (C1, B1)}
gz_up = sum(1 for w in gpair if int(gz[C1][w]["success"]) and not int(gz[B1][w]["success"]))
gz_dn = sum(1 for w in gpair if not int(gz[C1][w]["success"]) and int(gz[B1][w]["success"]))
gz_p = mcnemar_exact(gz_up, gz_dn)
rtf = sorted(float(r["rtf_mean"]) for k in (C1, B1) for r in gz[k].values() if r.get("rtf_mean"))


def gz_mode(r):
    if r["success"] == "1":
        return "ok"
    tp = float(r["first_contact_t"]) if r.get("first_contact_t") else None
    ts = float(r["first_static_t"]) if r.get("first_static_t") else None
    if tp is not None and (ts is None or tp <= ts):
        return "person"
    if ts is not None or str(r["collision"]) == "1":
        return "static"
    return "timeout" if float(r["time_s"] or 0) >= 299 else "stuck/other"


# reproduction check: run the HASHED coordinator script (sha verified first) and compare formatted lines
gz_script = P("research/coord_gz_test_analyze.py")
want = [l.split()[0] for l in open(note_input(P("results/frozen_C1/SHA256SUMS_GZ_ANALYSIS"))) if "coord_gz_test_analyze.py" in l][0]
check("sha256 coord_gz_test_analyze.py", hashlib.sha256(open(gz_script, "rb").read()).hexdigest(), want)
gz_ref = subprocess.run([sys.executable, gz_script, GZ_DIR], cwd=ROOT, capture_output=True, text=True).stdout
for k in (C1, B1):
    n = len(gpair); s = gzs[k]; lo, hi = wilson(s, n)
    col = sum(1 for w in gpair if str(gz[k][w]["collision"]) == "1"); af = sum(1 for w in gpair if str(gz[k][w].get("at_fault", "")) == "1")
    line = f"  {NAMES[k]:5s} success {s}/{n} = {100*s/n:.1f} % [{100*lo:.1f}, {100*hi:.1f}]  collision {col}  at_fault {af}"
    check("GZ row " + NAMES[k], line, line if line in gz_ref else "<not found>")
line = (f"  C1 - B1 = {100*(gzs[C1]-gzs[B1])/len(gpair):+.1f} points; discordant C1-only {gz_up}, B1-only {gz_dn}; exact McNemar p = {gz_p:.3g}")
check("GZ primary McNemar", line, line if line in gz_ref else "<not found>")
line = f"rtf_mean: median {rtf[len(rtf)//2]:.3f}  min {rtf[0]:.3f}  n<0.8: {sum(x < 0.8 for x in rtf)}"
check("GZ RTF", line, line if line in gz_ref else "<not found>")
# fastsim on the same worlds
GZFS = {}
for cell in ("champ_base", "champ2_base"):
    fsd = {k: {int(w): S[(cell, w)][k] for w in W} for k in (C1, B1)}
    agree = {k: 100 * np.mean([fsd[k][w] == int(gz[k][w]["success"]) for w in gpair]) for k in (C1, B1)}
    dfs = 100 * np.mean([fsd[C1][w] - fsd[B1][w] for w in gpair])
    GZFS[cell] = (dfs, agree)
    line = f"  C1-B1: fastsim {dfs:+.1f}  Gazebo {100*(gzs[C1]-gzs[B1])/len(gpair):+.1f} points (N {len(gpair)})"
    check(f"GZ vs fastsim {cell}", line, line if line in gz_ref.split(cell)[1] else "<not found>")
T11rows, T11csv = [], []
for k in (C1, B1):
    n = len(gpair); s = gzs[k]; lo, hi = wilson(s, n)
    m = collections.Counter(gz_mode(gz[k][w]) for w in gpair)
    af = sum(1 for w in gpair if str(gz[k][w].get("at_fault", "")) == "1")
    tt = [float(gz[k][w]["time_s"]) for w in gpair if gz[k][w]["success"] == "1"]
    T11rows.append([LONG[k], f"{s}/{n}", "%.1f [%.1f, %.1f]" % (100 * s / n, 100 * lo, 100 * hi), str(m["person"]), str(m["static"]),
                    str(m["stuck/other"]), str(m["timeout"]), str(af), "%.1f" % np.mean(tt)])
    T11csv.append([NAMES[k], s, n, round(100 * s / n, 2), round(100 * lo, 2), round(100 * hi, 2), m["person"], m["static"], m["stuck/other"],
                   m["timeout"], af, round(float(np.mean(tt)), 2)])
# DRA* (gated, exploratory): only once >= 340 worlds are complete; never read a partial run into the tables
gzd, gzd_files = load_gz(GZ_DRA_DIR) if os.path.isdir(P(GZ_DRA_DIR)) else ({}, [])
dra_w = sorted(set(gzd.get(DRA, {})) & set(gpair))
if len(dra_w) >= 340:
    for f in gzd_files:
        note_input(f)
    dra_w = [w for w in gpair[:340] if w in gzd[DRA]]
    s = sum(int(gzd[DRA][w]["success"]) for w in dra_w); n = len(dra_w); lo, hi = wilson(s, n)
    u2 = sum(1 for w in dra_w if int(gz[C1][w]["success"]) and not int(gzd[DRA][w]["success"]))
    d2 = sum(1 for w in dra_w if not int(gz[C1][w]["success"]) and int(gzd[DRA][w]["success"]))
    c1s = sum(int(gz[C1][w]["success"]) for w in dra_w)
    T11rows.append([LONG[DRA] + " (gated, exploratory; first 340 worlds)", f"{s}/{n}", "%.1f [%.1f, %.1f]" % (100 * s / n, 100 * lo, 100 * hi),
                    "–", "–", "–", "–", "–", "C1 on same worlds %d/%d; McNemar +%d/−%d, p = %.3g" % (c1s, n, u2, d2, mcnemar_exact(u2, d2))])
    T11csv.append(["DRA*", s, n, round(100 * s / n, 2), round(100 * lo, 2), round(100 * hi, 2), "", "", "", "", "", ""])
    GZ_DRA_STATUS = "complete"
else:
    T11rows.append([LONG[DRA] + " (gated, exploratory; first 340 worlds)", "⟦running⟧", "⟦…⟧", "", "", "", "", "", ""])
    GZ_DRA_STATUS = f"running ({len(dra_w)} of 340 worlds present at build time; not read into tables)"
CHECK_LINES.append("INFO  Gazebo DRA* gated arm: " + GZ_DRA_STATUS)
write_table("T11_gazebo_TEST", ["Planner", "Success", "% [Wilson 95 %]", "Person coll.", "Static coll.", "Stuck/other", "Timeout", "At-fault", "Time to goal, s"],
            T11rows,
            f"Gazebo TEST (pre-registered separate family, PREREG_TEST §2): first {len(gpair)} fastsim-TEST worlds with people, Gazebo Harmonic + CHAMP gait, "
            "movers crowd (base), one episode per world and planner, both planners on the same simulator instance in random order; 0 worlds dropped, "
            f"code hashes verified before every group (1360/1360). Primary test: C1 vs B1 exact two-sided McNemar, C1 only {gz_up} / B1 only {gz_dn}, "
            f"p = {gz_p:.2g} (pass at α = 0.05). Real-time factor per episode: median {rtf[len(rtf)//2]:.3f}, min {rtf[0]:.3f}. "
            "Must be read with smoke-test failure S4 (ghost person tracks on static objects caused by CHAMP body wobble; deviation #1). "
            "Outcome categories from first-contact logs; at-fault is a noisy secondary flag. DRA* was run only because the gate opened and is exploratory.",
            label="tab:gazebo", colspec="lrcrrrrrr")
with open(os.path.join(TAB, "T11_gazebo_TEST.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["config", "success", "n", "pct", "wilson_lo", "wilson_hi", "person_coll", "static_coll", "stuck_other", "timeout", "at_fault", "mean_time_success_s"])
    wr.writerows(T11csv)
    wr.writerow([]); wr.writerow(["primary", "C1_only", gz_up, "B1_only", gz_dn, "p_mcnemar", gz_p])
    for cell, (dfs, ag) in GZFS.items():
        wr.writerow(["fastsim_same_worlds", cell, "C1-B1_fastsim", round(dfs, 2), "agree_C1", round(ag[C1], 1), "agree_B1", round(ag[B1], 1)])
open(os.path.join(TAB, "T11_gazebo_TEST_PLACEHOLDER.md"), "w").write(
    "# T11 placeholder — SUPERSEDED\n\nReplaced on 2026-11-25 by generated `T11_gazebo_TEST.{csv,tex}` (make_all.py). "
    "Only the gated DRA* row may still be pending.\n")

# ---- Isaac TEST (T11b), replica of isaac_val/test_stats.py (hashed in SHA256SUMS_ISAAC_TEST)
ISA_C = {"C1": C1, "B1": B1, "PGIF*": PGIF, "DRA*": DRA}; isa_inv = {v: k for k, v in ISA_C.items()}
ib = collections.defaultdict(dict)
for r in csv.DictReader(open(note_input(P("results/ISAAC_TEST/res.csv")))):
    if r.get("world", "").isdigit() and r.get("config") in isa_inv:
        ib[int(r["world"])][isa_inv[r["config"]]] = r
ifull = {w: d for w, d in ib.items() if len(d) == 4}
iW = sorted(w for w, d in ifull.items() if not all(x["why"].startswith("EXC") for x in d.values()))
check("Isaac TEST worlds", len(iW), 600)
iok = lambda r: r["success"] == "1"


def imode(r):
    if iok(r): return "ok"
    if r["why"] == "nga": return "fall"
    if r["why"].startswith("EXC"): return "exc"
    if r["col"] == "static": return "static"
    if r["col"]: return "person"
    return "timeout" if "gio" in r["why"] else "stuck"


istats = open(note_input(P("results/ISAAC_TEST/stats.txt"))).read()
ips = []
for k in ("B1", "PGIF*", "DRA*"):
    b_ = sum(iok(ifull[w]["C1"]) and not iok(ifull[w][k]) for w in iW); l_ = sum(not iok(ifull[w]["C1"]) and iok(ifull[w][k]) for w in iW)
    ips.append([k, b_, l_, mcnemar_exact(b_, l_)])
for r, h in zip(ips, holm([r[3] for r in ips])):
    r.append(h)
    line = f"  C1 vs {r[0]}: C1 thang {r[1]}, thua {r[2]}, chenh {100*(r[1]-r[2])/len(iW):+.1f} diem; p = {r[3]:.3g}; Holm = {h:.3g}"
    check("Isaac TEST " + r[0], line, line if line in istats else "<not found>")
T11b, T11bcsv, ISA_NOFALL = [], [], {}
for k in ISA_C:
    g_ = [ifull[w][k] for w in iW]; n = len(g_); s = sum(map(iok, g_)); m = collections.Counter(map(imode, g_)); lo, hi = wilson(s, n)
    line = f"| {k} | {s}/{n} = {100*s/n:.1f} % [{100*lo:.1f}, {100*hi:.1f}] | {m['fall']} ({100*m['fall']/n:.1f} %) | {m['person']} | {m['static']} | {m['stuck']+m['timeout']} | {m['exc']} |"
    check("Isaac TEST row " + k, line, line if line in istats else "<not found>")
    t = [r for r in ips if r[0] == k]
    T11b.append([LONG[ISA_C[k]], f"{s}/{n}", "%.1f [%.1f, %.1f]" % (100 * s / n, 100 * lo, 100 * hi), "%d (%.1f %%)" % (m["fall"], 100 * m["fall"] / n),
                 str(m["person"]), str(m["static"]), str(m["stuck"] + m["timeout"]),
                 ("%+.1f; %d/%d; Holm %.2g" % (100 * (t[0][1] - t[0][2]) / n, t[0][1], t[0][2], t[0][4])) if t else "–"])
    T11bcsv.append([k, s, n, round(100 * s / n, 2), round(100 * lo, 2), round(100 * hi, 2), m["fall"], m["person"], m["static"], m["stuck"] + m["timeout"]] +
                   ([round(100 * (t[0][1] - t[0][2]) / n, 2), t[0][1], t[0][2], t[0][3], t[0][4]] if t else ["", "", "", "", ""]))
# rank agreement with fastsim TEST on the same 600 worlds (Kendall without ties, as test_stats.py)
ITAU = []
for c in CELLS:
    fs_ = {k: np.mean([S[(c, str(w))][ISA_C[k]] for w in iW]) for k in ISA_C}
    is_ = {k: np.mean([iok(ifull[w][k]) for w in iW]) for k in ISA_C}
    tau_ = kendall_noties([is_[k] for k in ISA_C], [fs_[k] for k in ISA_C])
    ITAU.append((c, tau_, 100 * (fs_["C1"] - fs_["B1"]), 100 * (is_["C1"] - is_["B1"])))
    m_ = re.search(r"TEST_%s \(n=600\).*?Kendall tau ([+-][\d.]+) \| C1-B1 fastsim ([+-][\d.]+)" % c, istats)
    check(f"Isaac TEST tau/diff vs fastsim {c}", "%+.2f %+.1f" % (tau_, 100 * (fs_["C1"] - fs_["B1"])), " ".join(m_.groups()) if m_ else "<not found>")
write_table("T11b_isaac_TEST", ["Planner", "Success", "% [Wilson 95 %]", "Falls", "Person coll.", "Static coll.", "Stuck/timeout", "C1 − X; C1 only/X only; p (Holm 3)"], T11b,
            f"Isaac Lab TEST (pre-registered separate exploratory family, PREREG_TEST §3 with deviations #3–#4): first {len(iW)} TEST worlds with people, "
            "base crowd, official Isaac Lab Go2 rough-terrain policy with observation noise as the body (rays, pedestrians and tracker are the fastsim code, "
            "so only the body dynamics are independent), 4 robots in lock-step (N = 4 throughout), falls count as failures. Exact McNemar, Holm over 3. "
            "Rank agreement with the five fastsim TEST cells on the same worlds: Kendall τ = " +
            ", ".join("%s %+.2f" % (CELL_LAB[c], t) for c, t, _, _ in ITAU) + " (τ < 1 only because B1 and PGIF* swap). Falls are a property of the learned "
            "Isaac policy, not of the Unitree controller.", label="tab:isaac", colspec="lrcrrrrl")
with open(os.path.join(TAB, "T11b_isaac_TEST.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["config", "success", "n", "pct", "wilson_lo", "wilson_hi", "falls", "person_coll", "static_coll", "stuck_timeout",
                                     "C1_minus_X_pts", "C1_only", "X_only", "p_mcnemar", "p_holm3"]); wr.writerows(T11bcsv)
    wr.writerow([])
    for k in ("B1", "PGIF*", "DRA*"):                               # descriptive: drop pairs where either side fell
        ws = [w for w in iW if ifull[w]["C1"]["why"] != "nga" and ifull[w][k]["why"] != "nga"]
        b_ = sum(iok(ifull[w]["C1"]) and not iok(ifull[w][k]) for w in ws); l_ = sum(not iok(ifull[w]["C1"]) and iok(ifull[w][k]) for w in ws)
        ISA_NOFALL[k] = (b_, l_, len(ws))
        wr.writerow(["descriptive_no_fall_pairs", k, "C1_only", b_, "X_only", l_, "n", len(ws)])
    for c, t, dfs, dis in ITAU:
        wr.writerow(["fastsim_same_worlds", c, "kendall_tau", round(t, 3), "C1-B1_fastsim", round(dfs, 2), "C1-B1_isaac", round(dis, 2)])

# ---- F6: example Gazebo TEST trajectory (C1 success, B1 person collision), first such world in seed order
f6_w = next((w for w in gpair if gz[C1][w]["success"] == "1" and gz[B1][w]["success"] == "0" and gz[B1][w].get("first_contact_t")), None)

# =============================================================================================== 8b. placeholders
open(os.path.join(TAB, "T12_real_dog_PLACEHOLDER.md"), "w").write(
    "# T12 Real Unitree Go2 experiment - PLACEHOLDER (not run)\n\nNo real-robot navigation experiment has been run with C1. "
    "Prerequisites: dyn/HUONG_DAN_DO.md command-response measurement (gain, delay, tau), Jetson Orin timing, a safety protocol "
    "(remote-control kill switch; reverse + slow turning tested separately), and a pre-registration like PREREG_TEST.\n\n"
    "| Planner | Runs | Success | Person contacts | Min. distance to person | Time | Notes |\n|---|---|---|---|---|---|---|\n"
    "| C1 | TBD | TBD | TBD | TBD | TBD | |\n| B1 | TBD | TBD | TBD | TBD | TBD | |\n| Unitree obstacles_avoid | TBD | TBD | TBD | TBD | TBD | |\n")

# =============================================================================================== 9. figures
SHORT_CELL = {"champ_base": "CHAMP\nbase", "champ2_base": "CHAMP2\nbase", "go2_base": "Go2\nbase", "champ2_helb": "CHAMP2\nHelbing", "go2_helb": "Go2\nHelbing"}
CELL_MK = {"champ_base": "o", "champ2_base": "s", "go2_base": "^", "champ2_helb": "v", "go2_helb": "D"}

# F1 pooled success with CI + per-cell markers
fig, ax = plt.subplots(figsize=(3.5, 3.0))
order = sorted(SHOW, key=lambda k: POOLED[k][0])
for i, k in enumerate(order):
    col, mk = STYLE[k]; m, lo, hi = POOLED[k]
    for j, c in enumerate(CELLS):
        ax.scatter(100 * np.mean([S[(c, w)][k] for w in W]), i + (j - 2) * 0.09, marker=CELL_MK[c], s=9, facecolor="white",
                   edgecolor="#555555", linewidth=0.5, zorder=2)
    ax.errorbar(m, i, xerr=[[m - lo], [hi - m]], fmt=mk, color=col, ms=6, mec="white", mew=0.8, capsize=2, lw=1.2, zorder=3)
    ax.text(99.5, i, "%.1f" % m, va="center", ha="right", fontsize=7, color="#222222")
ax.set_yticks(range(len(order))); ax.set_yticklabels([NAMES[k] for k in order])
ax.set_xlabel("Success without any collision (%)"); ax.set_xlim(55, 100)
ax.grid(axis="x", color="#dddddd", lw=0.5); ax.set_axisbelow(True)
from matplotlib.lines import Line2D
ax.legend([Line2D([], [], ls="", marker=CELL_MK[c], mfc="white", mec="#555555", ms=4) for c in CELLS] +
          [Line2D([], [], ls="", marker="o", color="black", ms=5)],
          [CELL_LAB[c] for c in CELLS] + ["pooled, 95 % world-bootstrap CI"], fontsize=5.5, loc="upper center",
          bbox_to_anchor=(0.45, -0.17), ncol=3, frameon=False, handletextpad=0.2, columnspacing=0.8)
ax.set_title(f"Fastsim TEST, {nW} worlds × 5 cells", fontsize=8)
savefig(fig, "F1_pooled_success")

# F2 forest plot per cell
fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.6), sharey=True)
famd = {r["base"]: r for r in fam}
for ax, k in zip(axs, FAMILY):
    col, mk = STYLE[k]
    rr = [r for r in rows3 if r["base"] == k]
    for i, r in enumerate(rr):
        y = len(rr) - i
        ax.errorbar(r["a"] - r["b"], y, xerr=[[r["a"] - r["b"] - r["lo"]], [r["hi"] - (r["a"] - r["b"])]], fmt=mk, color=col, ms=5, mec="white", mew=0.6, capsize=2)
        ax.text(24.5, y, ("Holm %.2g" % r["holm"]), va="center", ha="right", fontsize=5.5, color="#333333")
    f_ = famd[k]
    ax.errorbar(f_["d"], 0, xerr=[[f_["d"] - f_["lo"]], [f_["hi"] - f_["d"]]], fmt="D", color="black", ms=6, capsize=2)
    ax.text(24.5, 0, "Holm %.2g" % f_["holm"], va="center", ha="right", fontsize=5.5, fontweight="bold")
    ax.axvline(0, color="#888888", lw=0.7, ls="--")
    ax.set_title("C1 − " + NAMES[k], fontsize=8); ax.set_xlim(-4, 25); ax.set_xticks([0, 5, 10, 15]); ax.set_xlabel("Δ success (points)")
    ax.grid(axis="x", color="#eeeeee", lw=0.5); ax.set_axisbelow(True)
axs[0].set_yticks(range(0, 6)); axs[0].set_yticklabels(["Pooled\n(primary)"] + [CELL_LAB[c] for c in CELLS[::-1]], fontsize=6.5)
fig.tight_layout()
savefig(fig, "F2_percell_forest")

# F3 replication
fig, ax = plt.subplots(figsize=(4.6, 2.6))
rl = [lab for lab, *_ in ROUNDS]
for j, k in enumerate(FAMILY):
    col, mk = STYLE[k]; xs, ys, lo, hi = [], [], [], []
    for i, lab in enumerate(rl):
        if (lab, k) in REP:
            r = REP[(lab, k)]; xs.append(i + (j - 1) * 0.17); ys.append(r["d"]); lo.append(r["d"] - r["lo"]); hi.append(r["hi"] - r["d"])
    ax.errorbar(xs, ys, yerr=[lo, hi], fmt=mk, ls=[":", "--", "-"][j], color=col, ms=5, mec="white", mew=0.6, capsize=2, lw=0.9, label="C1 − " + NAMES[k])
ax.axhline(0, color="#888888", lw=0.7)
ax.set_xticks(range(len(rl))); ax.set_xticklabels(["R1\n300–799", "R2\n1000–1499", "R3\n1500–1999", "VAL\n2000–2399", "TEST\n≥100000"], fontsize=6.5)
ax.axvspan(3.5, 4.5, color="#f0f0f0", zorder=0); ax.text(4, 11.3, "confirmatory", ha="center", fontsize=6)
ax.set_ylabel("Δ success (points), 95 % CI"); ax.set_ylim(-1, 12); ax.legend(fontsize=6.5, frameon=False, loc="upper left", ncol=3)
ax.set_title("Replication across disjoint seed sets (pooled over 5 cells)", fontsize=8)
savefig(fig, "F3_replication")

# F4 failure stacked bars: TEST (crowd) and static-only arm
FT = [("va nguoi", "person collision", "#D55E00", "////"), ("va vat", "static collision", "#E69F00", "...."),
      ("ket", "stuck", "#0072B2", "\\\\\\\\"), ("het gio", "timeout", "#56B4E9", "xx"), ("khong co duong", "no path", "#7F7F7F", "")]
fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.5), gridspec_kw=dict(width_ratios=[1.5, 1]))
for ax, src_, title in ((axs[0], {k: FAIL[(k, "pooled")] for k in SHOW}, f"Crowd TEST ({5*nW} episodes / planner)"),
                        (axs[1], STAT, f"Static-only arm ({3*len(SW)} episodes / planner)")):
    left = np.zeros(len(SHOW))
    for why, lab, colr, hatch in FT:
        v = np.array([src_[k][why] for k in SHOW])
        ax.barh(range(len(SHOW)), v, left=left, color=colr, hatch=hatch, edgecolor="white", linewidth=0.8, label=lab, height=0.7)
        left += v
    for i, k in enumerate(SHOW):
        ax.text(left[i] + 0.3, i, "%.1f" % left[i], va="center", fontsize=6)
    ax.set_yticks(range(len(SHOW))); ax.set_yticklabels([NAMES[k] for k in SHOW]); ax.invert_yaxis()
    ax.set_xlabel("Failed episodes (%)"); ax.set_title(title, fontsize=8)
    ax.set_xlim(0, max(left) * 1.15)
fig.tight_layout()
fig.legend(*axs[0].get_legend_handles_labels(), fontsize=6.5, frameon=False, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 0.02))
savefig(fig, "F4_failure_types")

# F5 ablation
fig, ax = plt.subplots(figsize=(4.0, 2.3))
ab = sorted(ABLPLOT, key=lambda t: t[1])
for i, (lab, d, lo, hi, h) in enumerate(ab):
    sig = h < 0.05
    ax.errorbar(d, i, xerr=[[d - lo], [hi - d]], fmt="o" if sig else "o", mfc="black" if sig else "white", mec="black", color="black", ms=5, capsize=2)
    ax.text(2.7, i, "Holm %.2g" % h, va="center", fontsize=6)
ax.axvline(0, color="#888888", lw=0.7, ls="--")
ax.set_yticks(range(len(ab))); ax.set_yticklabels([t[0] for t in ab], fontsize=6.5)
ax.set_xlabel("Δ success vs full C1 (points), 95 % CI"); ax.set_xlim(-9, 4.8); ax.set_xticks([-8, -6, -4, -2, 0, 2])
ax.set_title("Ablation, round 2 (348 worlds × 3 base cells); filled: Holm < 0.05", fontsize=7)
savefig(fig, "F5_ablation")

# F6 example trajectory from Gazebo TEST (stored episode logs; no new run)
import xml.etree.ElementTree as _ET
if f6_w is not None:
    tasks = {t["seed"]: t for t in json.load(open(note_input(P("results/gztest/tasks.json"))))}
    tk = tasks[f6_w]; gdir = P(GZ_DIR, "s%d" % (tk["group"] % 2), "g%03d" % tk["group"])
    eps = {}
    for l in open(note_input(os.path.join(gdir, "episodes.jsonl"))):
        d = json.loads(l)
        if d["task"] == tk["task"]["name"] and d["config"] in (C1, B1):
            eps[d["config"]] = d
    boxes = []
    for m in _ET.parse(note_input(P("results/gztest", tk["truth_sdf"]))).getroot().iter("model"):
        p_, b_ = m.find("pose"), m.find(".//collision/geometry/box/size")
        if p_ is None or b_ is None or m.get("name", "").startswith("cart"):
            continue
        x, y, _, _, _, yaw = map(float, p_.text.split()); sx, sy, _ = map(float, b_.text.split()); boxes.append((x, y, yaw, sx, sy))
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.0), sharex=True, sharey=True)
    for ax, k in zip(axs, (C1, B1)):
        d = eps[k]; rob = np.array(d["robot"]["go2"]); tt = np.array(d["t"])
        for (x, y, yaw, sx, sy) in boxes:
            c, s = math.cos(yaw), math.sin(yaw)
            cr = np.array([[-sx / 2, -sy / 2], [sx / 2, -sy / 2], [sx / 2, sy / 2], [-sx / 2, sy / 2], [-sx / 2, -sy / 2]])
            ax.fill(x + cr[:, 0] * c - cr[:, 1] * s, y + cr[:, 0] * s + cr[:, 1] * c, color="#BBBBBB", lw=0)
        ppl = d["people"]; npp = max(len(q) for q in ppl)
        for j in range(npp):
            pj = np.array([q[j][:2] for q in ppl if len(q) > j])
            ax.plot(pj[:, 0], pj[:, 1], color=OI["sky"], lw=0.8, ls=":", zorder=2)
            ax.plot(pj[-1, 0], pj[-1, 1], "o", ms=3.5, mfc="white", mec=OI["blue"], zorder=3)
        col, mk = STYLE[k]
        ax.plot(rob[:, 0], rob[:, 1], color=col, lw=1.6, ls="-" if k == C1 else "--", zorder=4)
        ax.plot(*tk["task"]["starts"][""][:2], "s", color="black", ms=4); ax.plot(*tk["task"]["goal"][""], "*", color="black", ms=8)
        for ti in range(0, len(tt), 200):                          # time stamps every ~20 s
            ax.text(rob[ti, 0], rob[ti, 1] + 0.25, "%d" % round(tt[ti] - tt[0]), fontsize=5, color=col, ha="center")
        out = "goal reached, %.0f s" % float(gz[k][f6_w]["time_s"]) if gz[k][f6_w]["success"] == "1" else \
              "person contact at %.1f s" % float(gz[k][f6_w]["first_contact_t"])
        fc = d.get("first_contact")
        if fc:                                                     # Gazebo logs the first contact; the episode itself continues
            i_ = int(fc["i"]); ax.plot(rob[i_, 0], rob[i_, 1], "X", color=col, ms=9, mec="black", mew=0.6, zorder=6)
            pk = ppl[i_][int(fc["k"])]; ax.plot(pk[0], pk[1], "o", ms=6, mfc=OI["blue"], mec="black", mew=0.5, zorder=6)
        ax.set_title("%s — %s" % (NAMES[k], out), fontsize=7.5); ax.set_aspect("equal"); ax.set_xlabel("x (m)")
    axs[0].set_ylabel("y (m)")
    b0 = tk["bounds"]
    fig.suptitle(f"Gazebo TEST world {f6_w} ({tk['kind']}, {tk['npeople']} pedestrians). Dotted: pedestrian paths in that episode; numbers: seconds;\n"
                 f"X: first person contact (filled dot: the pedestrian); Gazebo logs the first contact and the run continues",
                 fontsize=7, y=1.02)
    fig.tight_layout()
    savefig(fig, "F6_gazebo_example")
    open(os.path.join(FIG, "F6_SKIPPED.txt"), "w").write(
        f"SUPERSEDED (2026-11-25): F6 is now produced from the stored Gazebo TEST episode logs (figures/F6_gazebo_example.*), world {f6_w}, "
        "chosen by a fixed rule: the first world in seed order where C1 succeeded and B1 had a person contact. Illustrative only, not a statistic.\n")

import importlib.util as _ilu                                                  # F0 method figure (separate script)
_spec = _ilu.spec_from_file_location("make_method_figure", os.path.join(HERE, "make_method_figure.py"))
_mf = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mf); _mf.main()

# =============================================================================================== 10. manifests
with open(os.path.join(CHK, "INPUT_SHA256SUMS"), "w") as f:
    for rel in sorted(INPUTS):
        f.write("%s  %s\n" % (hashlib.sha256(open(P(rel), "rb").read()).hexdigest(), rel))
outs = sorted(glob.glob(os.path.join(TAB, "*")) + glob.glob(os.path.join(FIG, "*")))
with open(os.path.join(CHK, "OUTPUT_SHA256SUMS"), "w") as f:
    for o in outs:
        f.write("%s  %s\n" % (hashlib.sha256(open(o, "rb").read()).hexdigest(), os.path.relpath(o, ROOT)))
with open(os.path.join(CHK, "CHECKS.txt"), "w") as f:
    f.write("Reproduction checks against coordinator/agent outputs (make_all.py)\n")
    f.write("\n".join(CHECK_LINES) + "\n")
    f.write("\nSUMMARY: %d checks, %d mismatches%s\n" % (sum(1 for l in CHECK_LINES if not l.startswith("INFO")), len(MISMATCH),
                                                       (": " + "; ".join(MISMATCH)) if MISMATCH else ""))
print("checks: %d, mismatches: %d" % (sum(1 for l in CHECK_LINES if not l.startswith("INFO")), len(MISMATCH)))
for m_ in MISMATCH:
    print("  MISMATCH", m_)
print("inputs hashed:", len(INPUTS), "| outputs:", len(outs))
sys.exit(1 if MISMATCH else 0)
