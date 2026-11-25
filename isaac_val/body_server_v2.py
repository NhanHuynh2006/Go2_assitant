"""May chu THAN ROBOT (Isaac Lab, Go2 + policy chinh thuc): N robot tren san phang, moi client (tien trinh fastsim) 1 cho.
Buoc khoa (lockstep) 0.02 s: chi buoc khi MOI client dang ket noi deu da gui lenh -> dong ho ao, khong phu thuoc may nhanh/cham.
  python body_server.py --headless --device cpu --policy flat --num_envs 2 --sock /tmp/.../body.sock
Giao thuc (pickle, do dai 4 byte): ("reset", seed, dmass) -> trang thai; ("step", (vx,vy,wz)) -> trang thai.
v2 (23/11): reset TAT DINH (tu the/khop co dinh, khoi luong than = mac dinh + dmass, nhieu quan sat bang Generator rieng moi
cho gieo tu seed) -> ket qua 1 robot khong phu thuoc robot khac / thu tu reset. Nhieu = Unoise cua Isaac Lab (velocity_env_cfg).
Trang thai: dict(x,y,yaw so voi luc reset, z, roll, pitch, v=(vx,vy,wz) khung than, fallen, feet=[(x,y,z)*4] khung the gioi cua env)."""
import argparse, os, pickle, select, socket, struct, sys, time
from isaaclab.app import AppLauncher
ap = argparse.ArgumentParser()
ap.add_argument("--policy", default="flat")
ap.add_argument("--num_envs", type=int, default=1)
ap.add_argument("--sock", required=True)
ap.add_argument("--noise", action="store_true")
AppLauncher.add_app_launcher_args(ap)
a = ap.parse_args()
app = AppLauncher(a).app
import torch
import isaaclab.utils.math as mu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from go2_env import make_env, load_actor
env = make_env(a.policy, a.num_envs, a.device, 0, False, False)   # khoi luong + nhieu: tu lam, tat dinh
net = load_actor(a.policy, a.device)
rob = env.scene["robot"]
cmdt = env.command_manager.get_term("base_velocity")
obs, _ = env.reset()
feet, _ = rob.find_bodies(".*_foot")
BASE = rob.find_bodies("base")[0][0]
M0 = rob.root_physx_view.get_masses().clone()                  # cpu
OD = obs["policy"].shape[1]
NS = torch.tensor([.1] * 3 + [.2] * 3 + [.05] * 3 + [0.] * 3 + [.01] * 12 + [1.5] * 12 + [0.] * 12 + [.1] * (OD - 48), device=a.device)
GEN = [torch.Generator(device=a.device) for _ in range(a.num_envs)]
N = a.num_envs
cmd = torch.zeros(N, 3, device=a.device)
base = torch.zeros(N, 3, device=a.device)                       # x0, y0, yaw0 luc reset
fell = torch.zeros(N, dtype=torch.bool, device=a.device)


def send(c, o):
    b = pickle.dumps(o)
    c.sendall(struct.pack("I", len(b)) + b)


def recvn(c, n):
    b = b""
    while len(b) < n:
        q = c.recv(n - len(b))
        if not q:
            raise ConnectionError
        b += q
    return b


def recv(c):
    return pickle.loads(recvn(c, struct.unpack("I", recvn(c, 4))[0]))


def state(i):
    p = rob.data.root_link_pos_w[i]
    q = rob.data.root_link_quat_w[i:i + 1]
    r, pt, y = (float(mu.wrap_to_pi(t)[0]) for t in mu.euler_xyz_from_quat(q))
    v = mu.quat_apply_inverse(mu.yaw_quat(q), rob.data.root_link_lin_vel_w[i:i + 1])[0]
    import math
    x0, y0, w0 = (float(t) for t in base[i])
    dx, dy = float(p[0]) - x0, float(p[1]) - y0
    c, s = math.cos(w0), math.sin(w0)

    def loc(X, Y):
        X, Y = X - x0, Y - y0
        return c * X + s * Y, -s * X + c * Y
    ft = [(*loc(float(f[0]), float(f[1])), float(f[2])) for f in rob.data.body_link_pos_w[i, feet]]
    return dict(x=c * dx + s * dy, y=-s * dx + c * dy, yaw=math.atan2(math.sin(y - w0), math.cos(y - w0)), z=float(p[2]), roll=r, pitch=pt,
                v=(float(v[0]), float(v[1]), float(rob.data.root_link_ang_vel_w[i, 2])), fallen=bool(fell[i]), feet=ft)


def step():
    global obs
    cmdt.vel_command_b[:] = cmd
    o = obs["policy"].clone()
    o[:, 9:12] = cmd
    if a.noise:
        for i in range(N):
            o[i] += (torch.rand(OD, generator=GEN[i], device=a.device) * 2 - 1) * NS
        if OD > 48:
            o[:, 48:] = o[:, 48:].clamp(-1, 1)
    obs, _, term, trunc, _ = env.step(net(o))
    fell.logical_or_(term | trunc)


def mark(i):
    p = rob.data.root_link_pos_w[i]
    base[i] = torch.stack([p[0], p[1], mu.euler_xyz_from_quat(rob.data.root_link_quat_w[i:i + 1])[2][0]])


if os.path.exists(a.sock):
    os.unlink(a.sock)
srv = socket.socket(socket.AF_UNIX)
srv.bind(a.sock)
srv.listen(16)
slot, free, pend = {}, list(range(N)), {}
print("[SRV] san sang", a.sock, flush=True)
nst, t0 = 0, time.time()
with torch.inference_mode():
    while True:
        rd, _, _ = select.select([srv] + list(slot), [], [], 5.0)
        for c in rd:
            if c is srv:
                k, _ = srv.accept()
                if free:
                    slot[k] = free.pop(0)
                else:
                    k.close()
                continue
            try:
                m = recv(c)
            except (ConnectionError, OSError):
                free.append(slot.pop(c)); pend.pop(c, None); c.close()
                continue
            if m[0] == "quit":
                os._exit(0)
            pend[c] = m
        if slot and len(pend) == len(slot):
            rs = [c for c, m in pend.items() if m[0] == "reset"]
            if rs:
                ids = torch.tensor([slot[c] for c in rs], device=a.device)
                env._reset_idx(ids)
                rst = rob.data.default_root_state[ids].clone()
                rst[:, :3] += env.scene.env_origins[ids]
                rob.write_root_state_to_sim(rst, ids)
                rob.write_joint_state_to_sim(rob.data.default_joint_pos[ids], rob.data.default_joint_vel[ids], env_ids=ids)
                ms = rob.root_physx_view.get_masses().clone()
                for c in rs:
                    i, sd, dm = slot[c], int(pend[c][1]), float(pend[c][2])
                    ms[i, BASE] = M0[i, BASE] + dm
                    GEN[i].manual_seed(sd)
                cid = torch.tensor([slot[c] for c in rs])
                rob.root_physx_view.set_masses(ms, cid)
                env.scene.write_data_to_sim(); env.sim.forward()
                cmd[ids] = 0.0
                obs = env.observation_manager.compute()
                fell[ids] = False
            # client dang reset cung dung 1 buoc voi lenh 0 (cac client khac khong bi cham)
            for c, m in pend.items():
                cmd[slot[c]] = torch.tensor(m[1] if m[0] == "step" else (0., 0., 0.), device=a.device)
            step(); nst += 1
            for c in rs:
                mark(slot[c])
            for c in list(pend):
                try:
                    send(c, state(slot[c]))
                except OSError:
                    free.append(slot.pop(c)); c.close()
            pend.clear()
            if nst % 5000 == 0:
                print(f"[SRV] {nst} buoc, RTF {nst * .02 / (time.time() - t0):.1f}", flush=True)
