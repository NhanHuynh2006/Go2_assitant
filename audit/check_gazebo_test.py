"""Kiem dau ra gen_gazebo_test (seed DEV): XML hop le, hop = gen_world, va cham/diem dau/dich, nguoi dung ten model, SDF parse."""
import json, math, os, sys, xml.etree.ElementTree as ET, collections, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import numpy as np, fastsim
from gen_gazebo_test import stub_gz; stub_gz(); import movers
d = sys.argv[1]; T = json.load(open(d + "/tasks.json")); assert all(t["seed"] < 1000 for t in T)
bad = 0
for t in T:
    w = fastsim.gen_world(t["seed"]); tr = movers._sdf_boxes(f"{d}/{t['truth_sdf']}")
    tr = [b for b in tr if not b[0].startswith(("person", "cart"))]; assert len(tr) == len(w["boxes"]), (t["seed"], len(tr), len(w["boxes"]))
    ox, oy = t["bounds"][0] - w["bounds"][0], t["bounds"][1] - w["bounds"][1]
    for b, q in zip(tr, w["boxes"]): assert max(abs(b[1] - ox - q[0]), abs(b[2] - oy - q[1]), abs(b[3] - q[2]), abs(b[4] - q[3]), abs(b[5] - q[4])) < 1e-3
    B = fastsim.Boxes([b[1:] for b in fastsim_boxes] if False else [(b[1], b[2], b[3], b[4], b[5]) for b in tr])
    s, g = t["task"]["starts"][""], t["task"]["goal"][""]
    c = float(B.sd(fastsim.footprint(*s)).min()); gc = float(B.sd(np.array([g]))[0])
    x0, y0, W, H = t["bounds"]; inb = all(x0 < p[0] < x0 + W and y0 < p[1] < y0 + H for p in (s, g))
    m = [x.get("name") for x in ET.parse(f"{d}/{t['sdf']}").getroot().iter("model")]
    assert len(m) == len(set(m)), "trung ten model"; assert all(p in m for p in movers.OFFICE_PEOPLE) and all(f"cart__{k}" in m for k in (1, 2, 3)); assert all(p in m for p in t["models"])
    assert ET.parse(f"{d}/{t['sdf']}").getroot().find("world").get("name") == "voice_office"
    if t["npeople"]:
        cc = t["task"]["crowd"]; cr = movers.Crowd(t["models"], cc["region"], f"{d}/{t['truth_sdf']}", seed=cc["seed"]); dd = min(math.hypot(p["p"][0] - s[0], p["p"][1] - s[1]) for p in cr.people)
        assert dd > 1.2; wl = min(float(B.sd(np.array([p["p"]]))[0]) for p in cr.people)
    else: wl = 9
    ok = c > .1 and gc > .4 and inb and wl > .3; bad += not ok
    if not ok: print("  !", t["seed"], t["kind"], "ho luc dau %.2f, dich %.2f, trong ban do %s, nguoi-tuong %.2f" % (c, gc, inb, wl))
print(len(T), "bai;", bad, "bai co van de;", collections.Counter(t["kind"] for t in T), "nguoi 'mai dien thoai': %.2f" % np.mean(sum((t.get("distracted", []) for t in T), [])))
for f in sorted(x for x in os.listdir(d) if x.endswith(".sdf"))[:2]:
    try:
        r = subprocess.run(["gz", "sdf", "-k", f"{d}/{f}"], capture_output=True, text=True, timeout=60); print("gz sdf -k", f, "->", (r.stdout + r.stderr).strip()[-200:])
    except Exception as e: print("khong co gz sdf:", e)
