"""Kiem logic an toan cua sysid_real.py bang trang thai gia (khong can robot)."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, sysid_real as S
io = S.SimIO(S.Log()); io.sleep(.02); H = np.zeros(2); u = np.array([.3, 0, 0])
def chk(name, want, u=u, home=H, **kw):
    old = dict(io.st); io.st.update(kw); r = S.danger(io, u, home); io.st = old
    print("%-28s -> %s" % (name, r)); assert (r is None) == (want is None) and (want is None or want in r), (name, r)
t = io.now(); far = np.array([[5., 0.]])
chk("binh thuong", None)
chk("mat odom", "odom", odom_t=t - .3); chk("mat sport", "trang thai", sport_t=t - .6); chk("mat lidar", "LiDAR", cloud_t=t - 1)
chk("mat remote", "remote", remote_seen=t - 2); chk("gat remote", "nhuong", remote_t=t - .2)
chk("nghieng", "nghieng", rpy=[.5, 0, 0]); chk("than thap", "than thap", bh=.1)
chk("ngoai hang rao", "hang rao", odom=(1.9, 0., 0.)); chk("dang ve trong rao", None, odom=(1.9, 0., 0.), u=np.array([-.3, 0, 0]))
chk("rao theo huong than", "hang rao", odom=(0., 1.9, np.pi / 2)); chk("rao: home dich", None, odom=(5., 0., 0.), home=np.array([5., 0.]))
near = np.array([[.9, y] for y in np.linspace(-.1, .1, 8)])
chk("vat truoc mat", "vat can", near=near); chk("vat truoc, di lui", None, near=near, u=np.array([-.3, 0, 0]))
chk("vat ben, di ngang", "vat can", near=near[:, ::-1], u=np.array([0, .2, 0])); chk("quay gan vat", "vat sat", near=near * .5, u=np.array([0, 0, .5]))
io2 = S.SimIO(S.Log()); io2.sleep(.02)
assert S.preflight(io2) == []; io2.st["batt"] = 10; assert S.preflight(io2); io2.st.update(batt=80, bh=.1); assert S.preflight(io2)
for st in (1, 2, 3):
    for w in ("fit", "test"):
        for nm, a, b, c, T in S.schedule(st, w):
            assert abs(a) <= .6 and abs(b) <= .4 and abs(c) <= 1 and T <= S.SEG_MAX
src = open(S.__file__).read()
assert "LowCmd_" not in src and "rt/lowcmd" not in src and "Damp(" not in src
print("OK tat ca")
