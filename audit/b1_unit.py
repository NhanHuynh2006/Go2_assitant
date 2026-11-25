"""Tai hien loi don vi (khong can mo phong). venv/bin/python audit/b1_unit.py"""
import os, sys, types, threading
for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ[k] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, math
import nav_local as nl, nav_prism2 as np2, robot_ros
print("[1] BlobTracker: nguoi di deu 0.9 m/s, quet 5 Hz, mat 1-2 lan quet giua chung")
for miss in (0, 1, 2):
    tr = nl.BlobTracker(); vmax = 0; t = 10.0; log = []
    for k in range(14):
        t += .2; x = 1.0 + .9 * .2 * k
        pts = np.array([[x + dx, dy] for dx in np.linspace(-.15, .15, 6) for dy in np.linspace(-.15, .15, 6)])
        far = np.array([[-3.0, 3.0], [-3.0, 2.95]])                      # van con diem khac trong tam -> khong _age
        seen = not (8 <= k < 8 + miss)
        tr.update(np.concatenate([pts, far]) if seen else far, (0, 0), t)
        if tr.tracks:
            q = max(tr.tracks, key=lambda z: np.linalg.norm(z["v"])); log.append(round(float(np.linalg.norm(q["v"])), 2))
    print("   mat %d lan quet -> |v| theo lan quet: %s" % (miss, log[6:]))
print("    (b) mat TOAN BO diem (near rong -> _age, _last_t khong doi):")
tr = nl.BlobTracker(); t = 10.; log = []
for k in range(12):
    t += .2; x = 1 + .18 * k
    pts = np.array([[x + dx, dy] for dx in np.linspace(-.15, .15, 6) for dy in np.linspace(-.15, .15, 6)])
    tr.update(pts if k != 8 else None, (0, 0), t); log.append(round(float(np.linalg.norm(tr.tracks[0]["v"])), 2))
print("       ", log)
print("[2] cu phap 'ten:k=v' co tac dung that khong?")
class R(robot_ros.RosRobotTools):
    def __init__(s, c): s.controller = c; s.goto_speed = .35; s.goto_turn = .8
def mk(c): return R(c)._make_ctrl()
for c in ("mppi:ppl_len=0.6", "mppi:K=300", "mppi:T=30", "mppi:tau=0.2", "mppi:sigma=0.3", "dwa:K=2000", "dwa:T=30", "prism@ppo+sac:ppl_len=0.6", "prism@ppo+sac:obs=12", "p2+tunr", "p2-Evade", "p2+turn:w_ev=12", "p2@ppo+sac+turn", "p2+turn@ppo+sac", "rl:ppl=32", "mppi:near_goal=0"):
    try:
        ct = mk(c); f = np.zeros((100, 100), np.float32) + 9; P = np.stack([np.linspace(0, 3, 31), np.zeros(31)], 1)
        kw = dict(gains=np.array([.5] * 3)) if isinstance(ct, (nl.PRISM, np2.PRISM2)) else {}
        u, i = ct.step(np.zeros(3), np.zeros(3), f, (.1, -5., -5.), P, np.linspace(0, 3, 31), (3., 0.), people=[(1.5, .2, -.5, 0, .25)], **kw)
        print("   %-28s OK  K=%s T=%s ppl_len=%s w[obs]=%s flags=%s priors=%d" % (c, getattr(ct, "K", None), getattr(ct, "T", None), getattr(ct, "ppl_len", None), getattr(ct, "w", {}).get("obs") if hasattr(ct, "w") else None, {k: v for k, v in getattr(ct, "flags", {}).items() if k in ("evade", "turn", "mode", "prior")} , len(getattr(ct, "priors", []))))
    except Exception as e: print("   %-28s LOI %r" % (c, e))
print("[3] prism:ppl_len thuc su doi ket qua? (cung rng)")
for c in ("prism@ppo", "prism@ppo:ppl_len=1.2", "prism@ppo:obs=60", "mppi", "mppi:ppl_len=1.2", "mppi:obs=60"):
    ct = mk(c); f = np.zeros((100, 100), np.float32) + .7; P = np.stack([np.linspace(0, 3, 31), np.zeros(31)], 1)
    kw = dict(gains=np.array([.5] * 3)) if isinstance(ct, nl.PRISM) else {}
    u, i = ct.step(np.zeros(3), np.zeros(3), f, (.1, -5., -5.), P, np.linspace(0, 3, 31), (3., 0.), people=[(1.2, .5, -.5, 0, .25)], **kw)
    print("   %-24s u=%s" % (c, np.round(u, 4)))
print("[4] lambda = 0.08*(median-min): khi > 50%% mau va cham (phat 1e4 / 5e3)")
for nm, ppl in (("khong nguoi", []), ("nguoi dung 0.8 m truoc mat", [(.8, 0, 0, 0, .25)]), ("nguoi 1.6 m di toi 0.9 m/s", [(1.6, 0., -.9, 0, .25)]), ("nguoi 2.2 m di toi 0.9 m/s", [(2.2, 0., -.9, 0, .25)]), ("nguoi 1.2 m cat ngang", [(1.2, 1.0, 0, -.9, .25)])):
    ct = nl.MPPI(vmax=(.595, .3, 1.), vmin=(-.2, -.3, -1.)); ct.people_cap = True
    f = np.zeros((100, 100), np.float32) + 9; P = np.stack([np.linspace(0, 3, 31), np.zeros(31)], 1)
    for _ in range(6): u, i = ct.step(np.zeros(3), np.array([.25, 0, 0]), f, (.1, -5., -5.), P, np.linspace(0, 3, 31), (3., 0.), people=ppl)
    print("   %-28s ESS=%5.0f / 600   u=%s" % (nm, i["ess"], np.round(u, 2)))
print("[5] people_cost cua p2 == phan nguoi cua MPPI.cost (cap)?")
m = nl.MPPI(); m.people_cap = True; p = np2.PRISM2(); rng = np.random.default_rng(0)
U = rng.normal(size=(50, 24, 3)) * .3; Pp, Y, V = m.rollout(U, np.zeros(3), np.zeros(3), .5); ppl = [(1., .2, -.5, .1, .25), (.5, -.6, .3, .6, .25)]
f = np.zeros((100, 100), np.float32) + 9
a = m.cost(U, Pp, Y, f, (.1, -5., -5.), None, None, 0, ppl, (3., 0), np.zeros(3))[0] - m.cost(U, Pp, Y, f, (.1, -5., -5.), None, None, 0, [], (3., 0), np.zeros(3))[0]
print("   chenh toi da:", np.abs(a - p.people_cost(Pp, Y, ppl)).max())
