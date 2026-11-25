#!/usr/bin/env python3
"""gen_gazebo_test.py — xuat the gioi fastsim.gen_world(seed) thanh .sdf cho Gazebo + danh sach bai.

  venv/bin/python audit/gen_gazebo_test.py --seeds 0-20 --out audit/out/gztest_dev            # thu cu phap (DEV)
  venv/bin/python audit/gen_gazebo_test.py --seeds 100000-100599 --crowd-only --max-worlds 320 \
        --allow-test --out results/gztest                     # CHI DIEU PHOI VIEN, 1 LAN, sau khi da dang ky truoc

Ra:  <out>/group_000.sdf        file nap vao Gazebo (--tiles the gioi dat canh nhau, mac dinh 4 = 2x2, tuong kin)
     <out>/truth/w<seed>.sdf    'su that' cua RIENG the gioi do, CUNG toa do voi group -> truyen cho eval_sim.World va
                                movers.Crowd (khong lay tuong cua o ben canh)
     <out>/tasks.json           [{seed, group, sdf, truth_sdf, bounds, kind, task:{cat,name,text,starts,goal,crowd}, ...}]
     <out>/MANIFEST.txt         sha256 tung file + sha256 cua code sinh (de chung minh khong doi sau dang ky)

Tuong thich: world name giu "voice_office" (dich vu /world/voice_office/set_pose, OFFICE_PEOPLE, park_carts chay nguyen);
header (vat ly, plugin, den, san) va person, person2..12, cart__1..3 CHEP NGUYEN tu voice_office.sdf (do ngoai ban do).
`task` dung duoc truc tiep cho eval_sim.run_task(gv, World(truth_sdf, bounds), task, cfg): text=None -> go_to_pose.
TRUOC moi the gioi phai goi robot_ros.configure_world(*bounds) (ban do 24x24 mac dinh se cat mat o ngoai bien).
Seed TEST (>= 100000) bi CHAN neu khong co --allow-test. Seed VAL/khac (1000-99999) bi chan han.
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ[_k] = "1"
import argparse, copy, hashlib, json, math, sys, types
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SDF = os.path.expanduser("~/ros2_ws/src/unitree_go2_ros2/unitree_go2_description/worlds/voice_office.sdf")
WALL_H, BOX_H, MIN_SPAWN = 1.0, 1.0, 1.2        # tuong 1.0 m nhu voice_office; hop 1.0 m: LiDAR + D435i deu thay (nhu fastsim)


def stub_gz():
    for m in ("gz", "gz.transport", "gz.msgs", "gz.msgs.boolean_pb2", "gz.msgs.pose_pb2"):
        sys.modules.setdefault(m, types.ModuleType(m))
    sys.modules["gz.transport"].Node = type("Node", (), {})
    sys.modules["gz.msgs.boolean_pb2"].Boolean = type("B", (), {}); sys.modules["gz.msgs.pose_pb2"].Pose = type("P", (), {})


def box_model(name, x, y, sx, sy, sz, yaw, rgb):
    f = lambda v: f"{v:.4f}"
    m = ET.Element("model", name=name)
    ET.SubElement(m, "static").text = "true"
    ET.SubElement(m, "pose").text = f"{f(x)} {f(y)} {f(sz / 2)} 0 0 {f(yaw)}"
    ln = ET.SubElement(m, "link", name="link")
    for tag, nm in (("collision", "c"), ("visual", "v")):
        e = ET.SubElement(ln, tag, name=nm)
        ET.SubElement(ET.SubElement(ET.SubElement(e, "geometry"), "box"), "size").text = f"{f(sx)} {f(sy)} {f(sz)}"
        if tag == "visual":
            mt = ET.SubElement(e, "material")
            for c in ("ambient", "diffuse"): ET.SubElement(mt, c).text = rgb + " 1"
    return m


def base_world():
    t = ET.parse(SDF); w = t.getroot().find("world")
    keep = lambda n: n == "ground_plane" or n.startswith(("person", "cart__"))
    for m in list(w.findall("model")):
        if not keep(m.get("name") or ""): w.remove(m)
        elif (m.get("name") or "").startswith("cart__"):             # xe day ra cho cat (movers.CART_PARK)
            k = int(m.get("name")[-1]) - 1
            p = m.find("pose").text.split(); m.find("pose").text = f"40.0 {40.0 + 2 * k} {p[2]} 0 0 0"
    return t, w


def write(t, path):
    ET.indent(t, space="  "); t.write(path, encoding="unicode", xml_declaration=True)


def crowd_seed(truth, cc, start, base):
    """eval_sim tao Crowd KHONG kiem khoang cach toi robot (fastsim co: > 1.2 m) -> chon seed nho nhat thoa,
    bang CHINH movers.Crowd (khong chay Gazebo)."""
    import movers
    for j in range(200):
        c = movers.Crowd(movers.OFFICE_PEOPLE[:cc["n"]], cc["region"], truth, seed=base + j)
        if min(math.hypot(p["p"][0] - start[0], p["p"][1] - start[1]) for p in c.people) > MIN_SPAWN:
            return base + j, j, [int(p["distracted"]) for p in c.people], [round(float(p["v0"]), 3) for p in c.people]
    raise RuntimeError("khong tim duoc seed dam dong")


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter); A = ap.add_argument
    A("--seeds", default="0-20"); A("--out", default=os.path.join(HERE, "out", "gztest_dev")); A("--tiles", type=int, default=4)
    A("--crowd-only", action="store_true"); A("--max-worlds", type=int, default=0); A("--allow-test", action="store_true")
    a = ap.parse_args()
    lo, hi = (int(v) for v in a.seeds.split("-"))
    if hi >= 1000 and not (lo >= 100000 and a.allow_test):
        sys.exit("CHAN: chi DEV (0-999), hoac TEST (>=100000) kem --allow-test (dieu phoi vien, dung 1 lan)")
    if lo >= 100000 and os.path.exists(os.path.join(a.out, "tasks.json")):
        sys.exit("CHAN: bo TEST da sinh roi (tasks.json ton tai)")
    if a.tiles not in (1, 2, 4): sys.exit("--tiles phai la 1, 2 hoac 4 (giu toa do trong +-22 m)")
    stub_gz(); sys.path.insert(0, ROOT)
    import fastsim, movers                                                            # noqa: F401
    os.makedirs(os.path.join(a.out, "truth"), exist_ok=True)
    W = []
    for s in range(lo, hi + 1):
        w = fastsim.gen_world(s)
        if a.crowd_only and not w["crowd"]: continue
        W.append(w)
        if a.max_worlds and len(W) >= a.max_worlds: break
    OFF = {1: [(0., 0.)], 2: [(-10., 0.), (10., 0.)], 4: [(-10., -8.), (10., -8.), (-10., 8.), (10., 8.)]}[a.tiles]
    tasks, files = [], []
    for g in range(0, len(W), a.tiles):
        t, root = base_world(); gp = os.path.join(a.out, f"group_{g // a.tiles:03d}.sdf")
        for (ox, oy), w in zip(OFF, W[g:g + a.tiles]):
            s, tt = w["seed"], base_world()
            for k, (x, y, sx, sy, yaw) in enumerate(w["boxes"]):
                wall = k < 4
                m = box_model(f"w{s}_{'wall' if wall else 'box'}_{k}", x + ox, y + oy, sx, sy, WALL_H if wall else BOX_H, yaw,
                              "0.92 0.9 0.85" if wall else "0.55 0.45 0.35")
                root.append(m); tt[1].append(copy.deepcopy(m))
            tp = os.path.join(a.out, "truth", f"w{s}.sdf"); write(tt[0], tp); files.append(tp)
            sx0, sy0, yaw0 = w["start"]; st = (round(sx0 + ox, 3), round(sy0 + oy, 3), round(yaw0, 4))
            gl = (round(w["goal"][0] + ox, 3), round(w["goal"][1] + oy, 3))
            bx = w["bounds"]; task = dict(cat="crowd" if w["crowd"] else "clutter", name=f"gz:{w['kind']}_{s}", text=None, starts={"": st}, goal={"": gl})
            extra = {}
            if w["crowd"]:
                (x0, x1), (y0, y1) = w["crowd"]["region"]; reg = ((x0 + ox, x1 + ox), (y0 + oy, y1 + oy))
                cs, tries, dis, v0 = crowd_seed(tp, dict(n=w["crowd"]["n"], region=reg), st, s * 1000)
                task["crowd"] = dict(n=w["crowd"]["n"], region=reg, seed=cs, distracted=.3)
                extra = dict(crowd_tries=tries, distracted=dis, v0=v0)
            tasks.append(dict(seed=s, kind=w["kind"], group=g // a.tiles, sdf=os.path.basename(gp), truth_sdf=f"truth/w{s}.sdf",
                              bounds=[bx[0] + ox, bx[1] + oy, bx[2], bx[3]], npeople=(w["crowd"] or {}).get("n", 0), models=movers.OFFICE_PEOPLE[:(w["crowd"] or {}).get("n", 0)],
                              carts=[], task=task, **extra))
        write(t, gp); files.append(gp)
    json.dump(tasks, open(os.path.join(a.out, "tasks.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(a.out, "MANIFEST.txt"), "w") as f:
        for p in sorted(files) + [os.path.join(a.out, "tasks.json"), os.path.abspath(__file__), os.path.join(ROOT, "fastsim.py"), os.path.join(ROOT, "movers.py"), os.path.join(ROOT, "nav_local.py"), SDF]:
            f.write(f"{sha(p)}  {p}\n")
    print(f"{len(W)} the gioi ({sum(1 for w in W if w['crowd'])} co nguoi) -> {a.out}: {len(files)} file sdf, tasks.json")


if __name__ == "__main__":
    main()
