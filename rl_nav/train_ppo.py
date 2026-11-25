#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/train_ppo.py — train policy NE VAT CAN bang PPO (Schulman et al. 2017) tren NavEnv.

    venv/bin/python rl_nav/train_ppo.py --updates 400            # ~50 M buoc
    venv/bin/python rl_nav/train_ppo.py --envs 1024 --updates 50 # thu nhanh

Ket qua: rl_nav/runs/<ten>/{policy.npz, best.npz, log.csv}
policy.npz = trong so MLP + chuan hoa quan sat -> nav_local.RLPolicy (numpy, khong can torch
tren robot / Jetson).
"""

import argparse
import csv
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import NavEnv  # noqa: E402


class RunningNorm:
    def __init__(self, dim, dev):
        self.mean = torch.zeros(dim, device=dev)
        self.var = torch.ones(dim, device=dev)
        self.count = 1e-4

    def update(self, x):
        bm, bv, bc = x.mean(0), x.var(0, unbiased=False), x.shape[0]
        d = bm - self.mean
        tot = self.count + bc
        self.mean = self.mean + d * bc / tot
        self.var = (self.var * self.count + bv * bc + d ** 2 * self.count * bc / tot) / tot
        self.count = tot

    def __call__(self, x):
        return ((x - self.mean) / torch.sqrt(self.var + 1e-8)).clamp(-8, 8)


class ActorCritic(nn.Module):
    def __init__(self, obs_dim, act_dim=3, hid=256):
        super().__init__()
        self.pi = nn.Sequential(nn.Linear(obs_dim, hid), nn.ELU(), nn.Linear(hid, hid), nn.ELU(),
                                nn.Linear(hid, 128), nn.ELU(), nn.Linear(128, act_dim))
        self.vf = nn.Sequential(nn.Linear(obs_dim, hid), nn.ELU(), nn.Linear(hid, hid), nn.ELU(),
                                nn.Linear(hid, 1))
        self.log_std = nn.Parameter(torch.full((act_dim,), -0.5))
        nn.init.orthogonal_(self.pi[-1].weight, 0.01)
        nn.init.zeros_(self.pi[-1].bias)

    def dist(self, o):
        mu = self.pi(o)
        return torch.distributions.Normal(mu, self.log_std.exp().expand_as(mu))


def export(model, norm, path, meta):
    lin = [m for m in model.pi if isinstance(m, nn.Linear)]
    np.savez(path, **{f"W{i}": l.weight.detach().cpu().numpy().T for i, l in enumerate(lin)},
             **{f"b{i}": l.bias.detach().cpu().numpy() for i, l in enumerate(lin)},
             obs_mean=norm.mean.cpu().numpy(), obs_std=torch.sqrt(norm.var + 1e-8).cpu().numpy(),
             act="elu", out="clip", **{k: np.array(v) for k, v in meta.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=2048)
    ap.add_argument("--horizon", type=int, default=64)
    ap.add_argument("--updates", type=int, default=100000)
    ap.add_argument("--minutes", type=float, default=20.0, help="ngan sach thoi gian (so cong bang voi TD3)")
    ap.add_argument("--curriculum-steps", type=float, default=30e6)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--ent", type=float, default=0.003)
    ap.add_argument("--realistic", action="store_true", help="cam bien thuc te (vung mu, FOV, tre)")
    ap.add_argument("--dyn", default="linear", choices=["linear", "measured", "union"], help="dong hoc (env.py)")
    ap.add_argument("--name", default=time.strftime("ppo_%Y%m%d_%H%M"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    env = NavEnv(n=a.envs, device=dev, seed=a.seed, realistic=a.realistic, dyn=a.dyn)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", a.name)
    os.makedirs(out, exist_ok=True)
    model = ActorCritic(env.obs_dim).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, eps=1e-5)
    norm = RunningNorm(env.obs_dim, dev)
    meta = dict(n_rays=env.R, ray_max=env.ray_max, vmax=env.vmax.cpu().numpy(),
                vmin=env.vmin.cpu().numpy(), dt=env.dt)

    N, H = a.envs, a.horizon
    obs = env.obs()
    buf_o = torch.zeros(H, N, env.obs_dim, device=dev)
    buf_a = torch.zeros(H, N, 3, device=dev)
    buf_lp, buf_r, buf_d, buf_v = (torch.zeros(H, N, device=dev) for _ in range(4))
    ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    best, t0, steps = -1e9, time.time(), 0
    log = open(os.path.join(out, "log.csv"), "w", newline="")
    lw = csv.writer(log)
    lw.writerow(["update", "steps", "density", "success", "collision", "timeout", "col_static",
                 "col_ped", "reward", "fps", "wall_s"])
    for upd in range(1, a.updates + 1):
        if time.time() - t0 > a.minutes * 60:
            break
        # curriculum: mat do vat can 0.3 -> 1.0 trong 30 M buoc dau (giong TD3)
        env.density = min(1.0, 0.3 + 0.7 * steps / a.curriculum_steps)
        frac = (time.time() - t0) / (a.minutes * 60)
        for g in opt.param_groups:                                # lr giam tuyen tinh theo thoi gian
            g["lr"] = a.lr * max(0.1, 1.0 - frac)
        rsum = 0.0
        with torch.no_grad():
            for t in range(H):
                norm.update(obs)
                o = norm(obs)
                dist = model.dist(o)
                act = dist.sample()
                buf_o[t], buf_a[t] = o, act
                buf_lp[t] = dist.log_prob(act).sum(-1)
                buf_v[t] = model.vf(o).squeeze(-1)
                obs, r, done, info = env.step(act)
                buf_r[t], buf_d[t] = r, done.float()
                rsum += r.mean().item()
                for k in ep:
                    ep[k] += int(info[k].sum())
            last_v = model.vf(norm(obs)).squeeze(-1)
            adv = torch.zeros(H, N, device=dev)
            gae = torch.zeros(N, device=dev)
            for t in reversed(range(H)):
                nv = last_v if t == H - 1 else buf_v[t + 1]
                delta = buf_r[t] + a.gamma * nv * (1 - buf_d[t]) - buf_v[t]
                gae = delta + a.gamma * a.lam * (1 - buf_d[t]) * gae
                adv[t] = gae
            ret = adv + buf_v
        steps += N * H
        B = N * H
        fo, fa, flp = buf_o.reshape(B, -1), buf_a.reshape(B, 3), buf_lp.reshape(B)
        fadv, fret = adv.reshape(B), ret.reshape(B)
        fadv = (fadv - fadv.mean()) / (fadv.std() + 1e-8)
        for _ in range(a.epochs):
            perm = torch.randperm(B, device=dev)
            for i in range(0, B, a.minibatch):
                j = perm[i:i + a.minibatch]
                d = model.dist(fo[j])
                lp = d.log_prob(fa[j]).sum(-1)
                ratio = (lp - flp[j]).exp()
                pg = -torch.min(ratio * fadv[j], ratio.clamp(1 - a.clip, 1 + a.clip) * fadv[j]).mean()
                vl = 0.5 * ((model.vf(fo[j]).squeeze(-1) - fret[j]) ** 2).mean()
                loss = pg + 0.5 * vl - a.ent * d.entropy().sum(-1).mean()
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
        if upd % 5 == 0:
            tot = max(1, ep["success"] + ep["collision"] + ep["timeout"])
            sr, cr, tr = ep["success"] / tot, ep["collision"] / tot, ep["timeout"] / tot
            fps = steps / (time.time() - t0)
            lw.writerow([upd, steps, round(env.density, 2), round(sr, 3), round(cr, 3), round(tr, 3),
                         round(ep["col_static"] / tot, 3), round(ep["col_ped"] / tot, 3),
                         round(rsum / H, 4), int(fps), int(time.time() - t0)])
            log.flush()
            print(f"upd {upd:4d}  buoc {steps / 1e6:6.1f}M  mat do {env.density:.2f}  "
                  f"toi dich {sr * 100:5.1f}%  va cham {cr * 100:5.1f}% (vat {ep['col_static'] / tot * 100:.1f} "
                  f"nguoi {ep['col_ped'] / tot * 100:.1f})  het gio {tr * 100:4.1f}%  "
                  f"{fps / 1000:.0f}k buoc/s", flush=True)
            export(model, norm, os.path.join(out, "policy.npz"), meta)
            score = sr - 2 * cr
            if env.density >= 0.99 and score > best:              # tot nhat o mat do day du
                best = score
                export(model, norm, os.path.join(out, "best.npz"), meta)
                torch.save(model.state_dict(), os.path.join(out, "best.pt"))
            ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    export(model, norm, os.path.join(out, "policy.npz"), meta)
    print(f"XONG -> {out}")


if __name__ == "__main__":
    main()
