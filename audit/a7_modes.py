"""Kieu hong Gazebo vs fastsim (cung 8 bai, nhom MPPI)."""
import csv, glob, json, os, collections
import numpy as np
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = lambda x: float(x) if x not in ("", None) else None
G = [r for f in glob.glob(H + "/results/final_office_w[01]/trials.csv") for r in csv.DictReader(open(f))]
fam = ("mppi", "dwa", "log_mppi", "apmppi_multi", "prism@ppo+sac", "prism_nounc@ppo+sac", "prism_noprior")
def mg(r):
    if r["success"] == "1": return "ok"
    if F(r["min_clear_m"]) < 0: return "va_tinh"
    if F(r["min_person_gap_m"]) is not None and F(r["min_person_gap_m"]) < 0: return "cham_nguoi"
    return "het_gio" if F(r["time_s"]) > 295 else "ket"
def ms(r): return "ok" if r["success"] == "1" else "va_tinh" if r["col"] == "static" else "cham_nguoi" if r["col"] else "het_gio" if "gio" in r["why"] else "ket"
S = [r for f in glob.glob(H + "/results/fs_calib/w*.csv") for r in csv.DictReader(open(f)) if r["success"] != ""]
for cat in ("clutter", "crowd"):
    g = [r for r in G if r["config"] in fam and r["cat"] == cat]; s = [r for r in S if r["config"].replace("~v1", "") in fam and r["world"].startswith(cat)]
    for nm, q, m in (("Gazebo", g, mg), ("fastsim", s, ms)):
        c = collections.Counter(map(m, q)); print(cat, nm, "n=%d" % len(q), {k: "%.0f%%" % (100 * v / len(q)) for k, v in sorted(c.items())})
print("khong tinh prism_noprior:")
for cat in ("clutter",):
    g = [r for r in G if r["config"] in fam[:-1] and r["cat"] == cat]; s = [r for r in S if r["config"].replace("~v1", "") in fam[:-1] and r["world"].startswith(cat)]
    for nm, q, m in (("Gazebo", g, mg), ("fastsim", s, ms)):
        c = collections.Counter(map(m, q)); print(" ", cat, nm, "n=%d" % len(q), {k: "%.0f%%" % (100 * v / len(q)) for k, v in sorted(c.items())})
print("van toc TB (quang duong / thoi gian, luot dat, bai tinh): Gazebo %.3f, fastsim %.3f m/s" % (np.mean([F(r["travel_m"]) / F(r["time_s"]) for r in G if r["config"] in fam and r["cat"] == "clutter" and r["success"] == "1"]), np.mean([F(r["travel"]) / F(r["time"]) for r in S if r["config"].replace("~v1", "") in fam and r["world"].startswith("clutter") and r["success"] == "1"])))
print("(travel gom ca lac than) toc do tien that: shortest/time")
for t in sorted({r["task"] for r in G if r["cat"] == "clutter"}):
    a = [F(r["time_s"]) for r in G if r["config"] in fam and r["task"] == t and r["success"] == "1"]; b = [F(r["time"]) for r in S if r["config"].replace("~v1", "") in fam and r["world"] == t and r["success"] == "1"]
    print("   %-26s thoi gian dat: Gazebo %.0f s (n=%d) fastsim %.0f s (n=%d)" % (t, np.median(a), len(a), np.median(b), len(b)))
v = [(float(np.hypot(1, 0)) , r) for r in []]
print("va tinh Gazebo theo bai (18 cau hinh MPPI):")
fam2 = {r["config"] for r in G} - {"pp", "rl", "rl@sac", "rl@td3", "rl_ens", "rl_safe"}
for t in sorted({r["task"] for r in G}):
    q = [r for r in G if r["task"] == t and r["config"] in fam2]; c = collections.Counter(map(mg, q)); print("   %-26s" % t, dict(c))
# do sau va tinh
d = [F(r["min_clear_m"]) for r in G if r["config"] in fam2 and F(r["min_clear_m"]) < 0]; print("do sau va tinh: median %.3f; so luot < 3 cm: %d/%d; < 5 cm %d" % (np.median(d), sum(x > -.03 for x in d), len(d), sum(x > -.05 for x in d)))
d = [F(r["min_person_gap_m"]) for r in G if r["config"] in fam2 and F(r["min_person_gap_m"]) is not None and F(r["min_person_gap_m"]) < 0]; print("do sau cham nguoi: median %.3f; nong hon 5 cm: %d/%d" % (np.median(d), sum(x > -.05 for x in d), len(d)))
# EXC dev1
E = [r for f in glob.glob(H + "/results/dev1/w*.csv") for r in csv.DictReader(open(f)) if r["why"].startswith("EXC")]
print("EXC dev1:", collections.Counter((r["world"], r["why"]) for r in E))
