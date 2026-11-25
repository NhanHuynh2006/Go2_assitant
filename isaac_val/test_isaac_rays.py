"""Kiem tia: goc nghieng 0 -> IsaacSim.sense y het fastsim.Sim.sense; nghieng thi mat tia dung cho.
   OPENBLAS_NUM_THREADS=1 venv/bin/python isaac_val/test_isaac_rays.py"""
import copy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import isaac_sim as I
F = I.F


def make(seed):
    F.real_time.monotonic, F.real_time.sleep = F.CLOCK.monotonic, F.CLOCK.sleep      # nhu run_episode
    W = F.gen_world(seed)
    F.CLOCK.sim, F.CLOCK.t = None, 100.0
    if F.FastCrowd is None:
        F.FastCrowd = F.make_crowd_class()
    return W, F.Sim(W, "mppi", 0, "real")


def snap(sim):
    r = sim.r
    return [r.local_obs.copy(), r.local_depth.copy(), r.grid.ev.copy(), r.grid.seen_t.copy(), r.depth_grid.ev.copy(), r.depth_grid.seen_t.copy()]


def eq(a, b):
    if isinstance(a, dict):
        return all(eq(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(eq(x, y) for x, y in zip(a, b))
    if isinstance(a, np.ndarray):
        return a.shape == b.shape and np.array_equal(a, b)
    try:
        return a == b
    except Exception:
        return True


def test_zero_tilt_cast():
    rng = np.random.default_rng(0)
    for seed in (302, 305, 310):
        W = F.gen_world(seed)
        bx = F.Boxes(W["boxes"])
        for _ in range(20):
            ox, oy, yaw = W["start"][0] + rng.normal(), W["start"][1] + rng.normal(), rng.uniform(-3, 3)
            th = np.linspace(-math.pi, math.pi, 360, endpoint=False)
            d = bx.cast(ox, oy, th, 6.0)
            assert np.array_equal(I.tilt_filter(d, th, yaw, 0.0, 0.0, .42, 1.0, 6.0), d)
            assert np.allclose(I.tilt_filter(d, th, yaw, 1e-12, -1e-12, .42, 1.0, 6.0), d)
    print("ok zero_tilt_cast")


def test_zero_tilt_sense():
    """hai Sim dung giong het nhau tu cung seed; mot ben goi fastsim.Sim.sense, mot ben IsaacSim.sense (tilt 0) qua nhieu buoc."""
    for seed in (302, 311, 320):
        _, A = make(seed)
        _, B = make(seed)
        for s in (A, B):
            s.tilt, s.zb = (0.0, 0.0), .32
        for k in range(1, 13):
            A.k = B.k = k
            F.Sim.sense(A)
            I.IsaacSim.sense(B)
            for x, y in zip(snap(A), snap(B)):
                assert eq(x, y), (seed, k)
            m1, m2 = A.r.tracker.movers(), B.r.tracker.movers()
            assert len(m1) == len(m2) and all(np.array_equal(p["p"], q["p"]) for p, q in zip(m1, m2))
            A.crowd and A.crowd.step(.1); B.crowd and B.crowd.step(.1)
    print("ok zero_tilt_sense (sense day du + tracker, 3 the gioi x 12 buoc)")


def test_tilt_effects():
    th = np.array([0.0, math.pi])                          # truoc, sau
    d = np.array([5.0, 5.0])
    # chui dau 0.1 rad: tia truoc cham san o .42/tan(.1) ~ 4.2 m < 5 -> mat; tia sau ngoc len, o 5 m cao .42+.5=.92 < 1.0 -> con
    out = I.tilt_filter(d, th, 0.0, 0.0, 0.1, .42, 1.0, 6.0)
    assert out[0] == 6.0 and out[1] == 5.0, out
    out = I.tilt_filter(np.array([3.0, 3.0]), th, 0.0, 0.0, 0.1, .42, 1.0, 6.0)
    assert out[0] == 3.0 and out[1] == 3.0, out            # gan hon diem cham san -> van thay
    out = I.tilt_filter(np.array([5.0]), np.array([math.pi / 2]), 0.0, 0.2, 0.0, .42, 1.0, 6.0)   # lan phai: tia trai ngoc len 5 m -> qua dinh 1 m
    assert out[0] == 6.0, out
    # yaw: tia the gioi goc yaw = tia truoc cua than
    out = I.tilt_filter(np.array([5.0]), np.array([1.0]), 1.0, 0.0, 0.1, .42, 1.0, 6.0)
    assert out[0] == 6.0
    _, A = make(302)
    orig = F.cast_circles
    A.tilt, A.zb, A.k = (0.05, -0.08), .32, 4
    F.Sim = I.IsaacSim                                     # nhu main(): khong duoc de quy
    try:
        I.IsaacSim.sense(A)
    finally:
        F.Sim = I._FSim
    assert F.cast_circles is orig and "cast" not in A.boxes.__dict__
    print("ok tilt_effects (+ tra lai ham goc sau sense nghieng)")


if __name__ == "__main__":
    test_zero_tilt_cast(); test_zero_tilt_sense(); test_tilt_effects()
