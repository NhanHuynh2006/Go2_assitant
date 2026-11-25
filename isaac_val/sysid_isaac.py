"""Nhan dang dong hoc van toc Go2 (Isaac Lab + policy chinh thuc). Headless.
  source ~/isaac/env_isaaclab/bin/activate
  python sysid_isaac.py --headless --device cpu --policy flat --test steps --num_envs 64 --reps 12 --out raw_flat_steps.npz
--test smoke: chi do RTF/VRAM vai giay."""
import argparse, time, sys
from isaaclab.app import AppLauncher
ap = argparse.ArgumentParser()
ap.add_argument("--policy", default="flat")
ap.add_argument("--test", default="smoke")
ap.add_argument("--num_envs", type=int, default=1)
ap.add_argument("--reps", type=int, default=12)
ap.add_argument("--dur", type=float, default=120)
ap.add_argument("--out", default="")
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--noise", action="store_true")
ap.add_argument("--nomass", action="store_true")
AppLauncher.add_app_launcher_args(ap)
a = ap.parse_args()
t0 = time.time()
app = AppLauncher(a).app
print("[T] kit khoi dong", round(time.time() - t0, 1), "s", flush=True)
import numpy as np, torch
import isaaclab.utils.math as mu
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from go2_env import make_env, load_actor
dev = a.device
env = make_env(a.policy, a.num_envs, dev, a.seed, not a.nomass, a.noise)
net = load_actor(a.policy, dev)
print("[T] tao env", round(time.time() - t0, 1), "s; step_dt", env.step_dt, "obs", env.observation_manager.group_obs_dim, flush=True)
rob = env.scene["robot"]
cmdt = env.command_manager.get_term("base_velocity")
obs, _ = env.reset()
N = a.num_envs
H = 50                                                          # Hz

GV = [.05, .1, .15, .2, .25, .3, .35, .4, .5, .6, .8, 1.0]
GRID = []
for s in (1, -1):
    GRID += [(s * v, 0, 0) for v in GV] + [(0, s * v, 0) for v in (.05, .1, .15, .2, .25, .3, .4, .5, .6, .8)]
    GRID += [(0, 0, s * w) for w in (.1, .2, .3, .4, .5, .6, .8, 1.0, 1.3)]
GRID = np.array(GRID)


def schedule():
    rng = np.random.default_rng(a.seed + 5)
    if a.test == "smoke":
        S = np.zeros((int(a.dur * H), N, 3)); S[H:, :, 0] = .5
        return S
    if a.test == "steps":                                       # 1.5 s dung, 4 s lenh, 2 s dung
        rows = []
        order = np.concatenate([rng.permutation(len(GRID)) for _ in range((N * a.reps) // len(GRID) + 1)])[:N * a.reps].reshape(a.reps, N)
        for r in range(a.reps):
            z, u = np.zeros((1, N, 3)), GRID[order[r]][None]
            rows += [np.repeat(z, int(1.5 * H), 0), np.repeat(u, 4 * H, 0), np.repeat(z, 2 * H, 0)]
        return np.concatenate(rows)
    if a.test == "combo":                                       # ban do nga: lenh ket hop vx x vy x wz, giu 4 s
        G = np.array([(vx, vy, wz) for vx in (-.2, -.1, 0., .1, .2, .4) for vy in (0., .25) for wz in (0., .5, -.5, 1., -1.)])
        rows = []
        order = np.concatenate([rng.permutation(len(G)) for _ in range((N * a.reps) // len(G) + 1)])[:N * a.reps].reshape(a.reps, N)
        for r in range(a.reps):
            z, u = np.zeros((1, N, 3)), G[order[r]][None]
            rows += [np.repeat(z, int(1.5 * H), 0), np.repeat(u, 4 * H, 0), np.repeat(z, 2 * H, 0)]
        return np.concatenate(rows)
    if a.test == "random":                                      # y het pipeline/sysid.py
        T = int(a.dur * H)
        S = np.zeros((T, N, 3))
        for e in range(N):
            k = 0
            while k < T:
                m = rng.choice(["vx", "vx", "vy", "wz", "all", "all", "stop"])
                u = np.zeros(3)
                if m in ("vx", "all"): u[0] = rng.uniform(-.2, .6)
                if m in ("vy", "all"): u[1] = rng.uniform(-.3, .3)
                if m in ("wz", "all"): u[2] = rng.uniform(-1, 1)
                L = int(rng.uniform(1.2, 2.2) * H)
                S[k:k + L, e] = u
                k += L
        return S
    raise SystemExit(a.test)


S = schedule()
T = len(S)
St = torch.tensor(S, dtype=torch.float32, device=dev)
rec = np.zeros((T, N, 14), np.float32)      # x y z roll pitch yaw | vx vy wz (khung yaw) | cmd3 | done | vz
ts = time.time()
with torch.inference_mode():
    for k in range(T):
        cmdt.vel_command_b[:] = St[k]
        o = obs["policy"].clone()
        o[:, 9:12] = St[k]                  # lenh co hieu luc NGAY tai buoc nay
        act = net(o)
        obs, _, term, trunc, _ = env.step(act)
        p = rob.data.root_link_pos_w - env.scene.env_origins
        q = rob.data.root_link_quat_w
        r, pt, y = mu.euler_xyz_from_quat(q)
        v = mu.quat_apply_inverse(mu.yaw_quat(q), rob.data.root_link_lin_vel_w)
        w = rob.data.root_link_ang_vel_w[:, 2]
        rec[k] = torch.stack([p[:, 0], p[:, 1], p[:, 2], mu.wrap_to_pi(r), mu.wrap_to_pi(pt), mu.wrap_to_pi(y), v[:, 0], v[:, 1], w,
                              St[k, :, 0], St[k, :, 1], St[k, :, 2], (term | trunc).float(), v[:, 2]], 1).cpu().numpy()
        if k == 49:
            ts2 = time.time()
        if k % 1000 == 0:
            print("[T] buoc", k, "/", T, round(time.time() - ts, 1), "s nga", int(rec[:k + 1, :, 12].sum()), flush=True)
el = time.time() - ts2
print(f"[KQ] policy={a.policy} N={N} dev={dev}: {T - 50} buoc ({(T - 50) / H:.1f} s mo phong) trong {el:.1f} s -> RTF {((T - 50) / H) / el:.2f}x/env, "
      f"{N * (T - 50) / H / el:.1f}x tong; nga {int(rec[:, :, 12].sum())}", flush=True)
try:
    print("[KQ] torch VRAM MB", torch.cuda.max_memory_allocated() / 1e6)
except Exception:
    pass
if a.out:
    m = rob.root_physx_view.get_masses().cpu().numpy().sum(1)
    np.savez_compressed(a.out, rec=rec, hz=H, policy=a.policy, test=a.test, mass=m, seed=a.seed, noise=a.noise)
    print("[KQ] luu", a.out, rec.shape, "khoi luong", m.min().round(2), m.max().round(2), flush=True)
import os
sys.stdout.flush()
os._exit(0)
