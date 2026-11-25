"""Dam dong Gazebo: 5 'lan lap' co phai 5 mau doc lap? toc do that so voi v0 danh dinh."""
import sys, types, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for m in ("gz", "gz.transport", "gz.msgs", "gz.msgs.boolean_pb2", "gz.msgs.pose_pb2"):
    sys.modules[m] = types.ModuleType(m)
sys.modules["gz.transport"].Node = type("N", (), {"request": lambda *a: None})
sys.modules["gz.msgs.boolean_pb2"].Boolean = object; sys.modules["gz.msgs.pose_pb2"].Pose = object
import numpy as np, movers
from gz_load import load
SDF = os.path.expanduser("~/ros2_ws/src/unitree_go2_ros2/unitree_go2_description/worlds/voice_office.sdf")
R = load()
T = {"crowd:sanh_8_nguoi": (8, ((-4.5, 4.5), (-4.5, 4.5)), 21), "crowd:kho_xe_day": (4, ((5.5, 14.5), (-9.5, 9.5)), 22), "crowd:van_phong_dong": (6, ((-14.5, -5.5), (-9.5, 9.5)), 23)}
for t, (n, reg, sd) in T.items():
    c = movers.Crowd([str(i) for i in range(n)], reg, SDF, seed=sd)
    print("==", t, "v0:", [round(p["v0"], 2) for p in c.people], "distracted:", [int(p["distracted"]) for p in c.people])
    G = [r for r in R if r["task"] == t]
    P0 = np.array([r["person"][0, :2] for r in G])
    print("  vi tri nguoi 0 luc bat dau bai, %d luot (moi cau hinh, moi lan lap): sd = %.3f, %.3f m" % (len(G), *P0.std(0)))
    for s in (5, 10, 20, 30, 45):
        k = int(s / .104); q = np.array([r["person"][k, :2] for r in G if len(r["person"]) > k])
        print("   t=%2ds n=%3d: khoang cach trung vi tu trung vi cac luot = %.2f m" % (s, len(q), np.median(np.hypot(*(q - np.median(q, 0)).T))))
    # toc do that
    v = []
    for r in G:
        dt = (float(r["time_s"]) + .5) / len(r["traj"]); s = np.hypot(*np.diff(r["person"][::5, :2], axis=0).T) / (5 * dt); v += list(s[s > .3])
    print("  nguoi 0: v0 danh dinh %.2f; toc do that p75 %.2f" % (c.people[0]["v0"], np.percentile(v, 75)))
    # mo phong offline cung seed, khong robot, 100 s -> p75
    vv = []
    prev = None
    for k in range(2000):
        c.step(.05)
        if k % 10 == 0:
            p = c.people[0]["p"].copy()
            if prev is not None: vv.append(np.hypot(*(p - prev)) / .5)
            prev = p
    vv = np.array(vv); print("  mo phong offline (khong robot): p75 %.2f TB khi di %.2f | Gazebo TB khi di %.2f" % (np.percentile(vv[vv > .3], 75), vv[vv > .3].mean(), np.mean(v)))
