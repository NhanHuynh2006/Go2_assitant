#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/train_sac.py — SAC (Haarnoja et al. ICML 2018) kieu "FastSAC" (song song + batch lon,
nhu FastTD3 / Seo et al. 2025) cho bai ne vat can. CUNG moi truong, phan thuong, ngan sach thoi
gian voi PPO va TD3 -> so sanh cong bang 3 ho RL chuan:
  PPO (on-policy) | TD3 (off-policy, tat dinh) | SAC (off-policy, entropy cuc dai)

    venv/bin/python rl_nav/train_sac.py --minutes 20 --seed 0 --name sac_s0
Xuat policy.npz/best.npz cung dinh dang (actor tra MEAN, qua tanh) -> nav_local.RLPolicy.
"""

import argparse
import copy
import csv
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import NavEnv  # noqa: E402
from train_ppo import RunningNorm  # noqa: E402
from train_td3 import Critic, mlp  # noqa: E402


class GaussActor(nn.Module):
    def __init__(self, od, ad=3):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(od, 512), nn.ELU(), nn.Linear(512, 256), nn.ELU(),
                                 nn.Linear(256, 128), nn.ELU())
        self.mu = nn.Linear(128, ad)
        self.ls = nn.Linear(128, ad)

    def forward(self, o):
        h = self.net(o)
        return self.mu(h), self.ls(h).clamp(-5, 1)

    def sample(self, o):
        mu, ls = self(o)
        std = ls.exp()
        z = mu + std * torch.randn_like(mu)
        a = torch.tanh(z)
        logp = (-0.5 * ((z - mu) / std) ** 2 - ls - 0.5 * math.log(2 * math.pi)).sum(-1)
        logp -= torch.log(1 - a ** 2 + 1e-6).sum(-1)
        return a, logp


def export(actor, norm, path, meta):
    lin = [m for m in actor.net if isinstance(m, nn.Linear)] + [actor.mu]
    np.savez(path, **{f"W{i}": l.weight.detach().cpu().numpy().T for i, l in enumerate(lin)},
             **{f"b{i}": l.bias.detach().cpu().numpy() for i, l in enumerate(lin)},
             obs_mean=norm.mean.cpu().numpy(), obs_std=torch.sqrt(norm.var + 1e-8).cpu().numpy(),
             act="elu", out="tanh", **{k: np.array(v) for k, v in meta.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=1024)
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--buffer", type=int, default=1_500_000)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--updates-per-step", type=int, default=2)
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--tau", type=float, default=0.1)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--realistic", action="store_true", help="cam bien thuc te (vung mu, FOV, tre)")
    ap.add_argument("--name", default=time.strftime("sac_%Y%m%d_%H%M"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    dev = "cuda"
    env = NavEnv(n=a.envs, device=dev, seed=a.seed + 200, realistic=a.realistic)
    env.return_terminal = True
    od = env.obs_dim
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", a.name)
    os.makedirs(out, exist_ok=True)
    actor, critic = GaussActor(od).to(dev), Critic(od).to(dev)
    critic_t = copy.deepcopy(critic)
    log_alpha = torch.tensor(math.log(0.1), device=dev, requires_grad=True)
    target_ent = -3.0
    oa = torch.optim.AdamW(actor.parameters(), lr=a.lr, weight_decay=0.1)
    oc = torch.optim.AdamW(critic.parameters(), lr=a.lr, weight_decay=0.1)
    oal = torch.optim.Adam([log_alpha], lr=a.lr)
    norm = RunningNorm(od, dev)
    meta = dict(n_rays=env.R, ray_max=env.ray_max, vmax=env.vmax.cpu().numpy(),
                vmin=env.vmin.cpu().numpy(), dt=env.dt)
    C = a.buffer
    B_o, B_o2 = torch.zeros(C, od, device=dev), torch.zeros(C, od, device=dev)
    B_a, B_r, B_d = torch.zeros(C, 3, device=dev), torch.zeros(C, device=dev), torch.zeros(C, device=dev)
    ptr, size = 0, 0
    obs = env.obs()
    ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    log = open(os.path.join(out, "log.csv"), "w", newline="")
    lw = csv.writer(log)
    lw.writerow(["iter", "steps", "density", "success", "collision", "timeout", "col_static",
                 "col_ped", "alpha", "fps", "wall_s"])
    t0, steps, it, best, n_upd = time.time(), 0, 0, -1e9, 0
    while time.time() - t0 < a.minutes * 60:
        it += 1
        env.density = min(1.0, 0.3 + 0.7 * (time.time() - t0) / (0.6 * a.minutes * 60))
        norm.update(obs)
        with torch.no_grad():
            act = (torch.empty(a.envs, 3, device=dev).uniform_(-1, 1) if it <= a.warmup
                   else actor.sample(norm(obs))[0])
        obs2, r, done, info = env.step(act)
        nxt = torch.where(done[:, None], info["final_obs"], obs2)
        idx = (torch.arange(a.envs, device=dev) + ptr) % C
        B_o[idx], B_o2[idx], B_a[idx], B_r[idx] = obs, nxt, act, r
        B_d[idx] = info["terminal"].float()
        ptr, size = (ptr + a.envs) % C, min(C, size + a.envs)
        obs = obs2
        steps += a.envs
        for k in ep:
            ep[k] += int(info[k].sum())
        if it > a.warmup:
            for _ in range(a.updates_per_step):
                j = torch.randint(0, size, (a.batch,), device=dev)
                o, o2 = norm(B_o[j]), norm(B_o2[j])
                alpha = log_alpha.exp().detach()
                with torch.no_grad():
                    a2, lp2 = actor.sample(o2)
                    q1t, q2t = critic_t(o2, a2)
                    y = B_r[j] + a.gamma * (1 - B_d[j]) * (torch.min(q1t, q2t) - alpha * lp2)
                q1, q2 = critic(o, B_a[j])
                lc = ((q1 - y) ** 2).mean() + ((q2 - y) ** 2).mean()
                oc.zero_grad()
                lc.backward()
                nn.utils.clip_grad_norm_(critic.parameters(), 1.0)
                oc.step()
                n_upd += 1
                if n_upd % 2 == 0:
                    an, lp = actor.sample(o)
                    q = torch.min(*critic(o, an))
                    la = (alpha * lp - q).mean()
                    oa.zero_grad()
                    la.backward()
                    nn.utils.clip_grad_norm_(actor.parameters(), 1.0)
                    oa.step()
                    lal = -(log_alpha * (lp.detach() + target_ent)).mean()
                    oal.zero_grad()
                    lal.backward()
                    oal.step()
                with torch.no_grad():
                    for p, pt in zip(critic.parameters(), critic_t.parameters()):
                        pt.lerp_(p, a.tau)
        if it % 200 == 0:
            tot = max(1, ep["success"] + ep["collision"] + ep["timeout"])
            sr, cr = ep["success"] / tot, ep["collision"] / tot
            fps = steps / (time.time() - t0)
            lw.writerow([it, steps, round(env.density, 2), round(sr, 3), round(cr, 3),
                         round(ep["timeout"] / tot, 3), round(ep["col_static"] / tot, 3),
                         round(ep["col_ped"] / tot, 3), round(float(log_alpha.exp()), 4), int(fps),
                         int(time.time() - t0)])
            log.flush()
            print(f"it {it:6d}  buoc {steps / 1e6:6.1f}M  mat do {env.density:.2f}  toi dich {sr * 100:5.1f}%  "
                  f"va cham {cr * 100:5.1f}%  alpha {float(log_alpha.exp()):.3f}  {fps / 1000:.0f}k buoc/s  "
                  f"{(time.time() - t0) / 60:.1f} ph", flush=True)
            export(actor, norm, os.path.join(out, "policy.npz"), meta)
            if env.density >= 0.99 and sr - 2 * cr > best:
                best = sr - 2 * cr
                export(actor, norm, os.path.join(out, "best.npz"), meta)
            ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    export(actor, norm, os.path.join(out, "policy.npz"), meta)
    print(f"XONG -> {out}")


if __name__ == "__main__":
    main()
