#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/train_td3.py — FastTD3 (Seo et al. 2025, arXiv 2505.22642) cho bai ne vat can.

Cong thuc FastTD3 (rut gon, cung moi truong + phan thuong voi PPO de so sanh cong bang):
  * TD3 (Fujimoto et al. ICML 2018): 2 critic, lay min, tre cap nhat actor, lam muot
    hanh dong muc tieu
  * hang nghin moi truong song song, replay buffer tren GPU, batch lon (16384),
    2 lan cap nhat moi buoc moi truong
  * nhieu kham pha RIENG cho tung moi truong (std ngau nhien 0.001-0.4)
  * chuan hoa quan sat; khong coi het gio la ket thuc (van bootstrap)
  (Bo qua critic phan bo C51 cua FastTD3 - ghi ro khi bao cao.)

    venv/bin/python rl_nav/train_td3.py --minutes 20
Ket qua: rl_nav/runs/<ten>/{policy.npz, best.npz, log.csv} - cung dinh dang PPO.
"""

import argparse
import copy
import csv
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import NavEnv  # noqa: E402
from train_ppo import RunningNorm  # noqa: E402


def mlp(i, o, hid, out_act=None):
    layers, d = [], i
    for h in hid:
        layers += [nn.Linear(d, h), nn.LayerNorm(h), nn.ELU()]
        d = h
    layers.append(nn.Linear(d, o))
    if out_act:
        layers.append(out_act)
    return nn.Sequential(*layers)


class Actor(nn.Module):
    def __init__(self, od, ad=3):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(od, 512), nn.ELU(), nn.Linear(512, 256), nn.ELU(),
                                 nn.Linear(256, 128), nn.ELU(), nn.Linear(128, ad), nn.Tanh())

    def forward(self, o):
        return self.net(o)


class Critic(nn.Module):
    def __init__(self, od, ad=3):
        super().__init__()
        self.q1 = mlp(od + ad, 1, (1024, 512, 256))
        self.q2 = mlp(od + ad, 1, (1024, 512, 256))

    def forward(self, o, a):
        x = torch.cat([o, a], -1)
        return self.q1(x).squeeze(-1), self.q2(x).squeeze(-1)


def export(actor, norm, path, meta):
    lin = [m for m in actor.net if isinstance(m, nn.Linear)]
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
    ap.add_argument("--warmup", type=int, default=20, help="buoc ngau nhien ban dau (moi env)")
    ap.add_argument("--curriculum-steps", type=float, default=30e6)
    ap.add_argument("--curriculum-time", action="store_true",
                    help="mat do toi 1.0 o 60 %% thoi gian (TD3 cham hon PPO moi buoc)")
    ap.add_argument("--realistic", action="store_true", help="cam bien thuc te (vung mu, FOV, tre)")
    ap.add_argument("--name", default=time.strftime("td3_%Y%m%d_%H%M"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    dev = "cuda"
    env = NavEnv(n=a.envs, device=dev, seed=a.seed + 100, realistic=a.realistic)
    env.return_terminal = True
    od = env.obs_dim
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", a.name)
    os.makedirs(out, exist_ok=True)
    actor, critic = Actor(od).to(dev), Critic(od).to(dev)
    actor_t, critic_t = copy.deepcopy(actor), copy.deepcopy(critic)
    oa = torch.optim.AdamW(actor.parameters(), lr=a.lr, weight_decay=0.1)
    oc = torch.optim.AdamW(critic.parameters(), lr=a.lr, weight_decay=0.1)
    norm = RunningNorm(od, dev)
    meta = dict(n_rays=env.R, ray_max=env.ray_max, vmax=env.vmax.cpu().numpy(),
                vmin=env.vmin.cpu().numpy(), dt=env.dt)

    C = a.buffer
    B_o = torch.zeros(C, od, device=dev)
    B_o2 = torch.zeros(C, od, device=dev)
    B_a = torch.zeros(C, 3, device=dev)
    B_r = torch.zeros(C, device=dev)
    B_d = torch.zeros(C, device=dev)
    ptr, size = 0, 0
    noise_std = torch.empty(a.envs, 1, device=dev).uniform_(0.001, 0.4)

    obs = env.obs()
    ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    log = open(os.path.join(out, "log.csv"), "w", newline="")
    lw = csv.writer(log)
    lw.writerow(["iter", "steps", "density", "success", "collision", "timeout", "col_static",
                 "col_ped", "q", "fps", "wall_s"])
    t0, steps, it, best, n_upd = time.time(), 0, 0, -1e9, 0
    qlog = 0.0
    while time.time() - t0 < a.minutes * 60:
        it += 1
        if a.curriculum_time:                                    # cong bang voi PPO theo THOI GIAN
            env.density = min(1.0, 0.3 + 0.7 * (time.time() - t0) / (0.6 * a.minutes * 60))
        else:
            env.density = min(1.0, 0.3 + 0.7 * steps / a.curriculum_steps)
        norm.update(obs)
        with torch.no_grad():
            if it <= a.warmup:
                act = torch.empty(a.envs, 3, device=dev).uniform_(-1, 1)
            else:
                act = (actor(norm(obs)) + noise_std * torch.randn(a.envs, 3, device=dev)).clamp(-1, 1)
        obs2, r, done, info = env.step(act)
        nxt = torch.where(done[:, None], info["final_obs"], obs2)
        idx = (torch.arange(a.envs, device=dev) + ptr) % C
        B_o[idx], B_o2[idx], B_a[idx], B_r[idx] = obs, nxt, act, r
        B_d[idx] = info["terminal"].float()                     # het gio: van bootstrap
        ptr, size = (ptr + a.envs) % C, min(C, size + a.envs)
        # env xong -> doi muc nhieu kham pha
        noise_std[done] = torch.empty(int(done.sum()), 1, device=dev).uniform_(0.001, 0.4)
        obs = obs2
        steps += a.envs
        for k in ep:
            ep[k] += int(info[k].sum())
        if it > a.warmup:
            for _ in range(a.updates_per_step):
                j = torch.randint(0, size, (a.batch,), device=dev)
                o, o2 = norm(B_o[j]), norm(B_o2[j])
                with torch.no_grad():
                    na = (actor_t(o2) + (0.2 * torch.randn(a.batch, 3, device=dev)).clamp(-0.5, 0.5)).clamp(-1, 1)
                    q1t, q2t = critic_t(o2, na)
                    y = B_r[j] + a.gamma * (1 - B_d[j]) * torch.min(q1t, q2t)
                q1, q2 = critic(o, B_a[j])
                lc = ((q1 - y) ** 2).mean() + ((q2 - y) ** 2).mean()
                oc.zero_grad()
                lc.backward()
                nn.utils.clip_grad_norm_(critic.parameters(), 1.0)
                oc.step()
                n_upd += 1
                if n_upd % 2 == 0:                               # tre cap nhat actor
                    qa = critic(o, actor(o))[0]
                    la = -qa.mean()
                    oa.zero_grad()
                    la.backward()
                    nn.utils.clip_grad_norm_(actor.parameters(), 1.0)
                    oa.step()
                    qlog = float(qa.mean())
                    with torch.no_grad():
                        for p, pt in zip(actor.parameters(), actor_t.parameters()):
                            pt.lerp_(p, a.tau)
                with torch.no_grad():
                    for p, pt in zip(critic.parameters(), critic_t.parameters()):
                        pt.lerp_(p, a.tau)
        if it % 200 == 0:
            tot = max(1, ep["success"] + ep["collision"] + ep["timeout"])
            sr, cr, tr = ep["success"] / tot, ep["collision"] / tot, ep["timeout"] / tot
            fps = steps / (time.time() - t0)
            lw.writerow([it, steps, round(env.density, 2), round(sr, 3), round(cr, 3), round(tr, 3),
                         round(ep["col_static"] / tot, 3), round(ep["col_ped"] / tot, 3),
                         round(qlog, 3), int(fps), int(time.time() - t0)])
            log.flush()
            print(f"it {it:6d}  buoc {steps / 1e6:6.1f}M  mat do {env.density:.2f}  toi dich {sr * 100:5.1f}%  "
                  f"va cham {cr * 100:5.1f}% (vat {ep['col_static'] / tot * 100:.1f} nguoi "
                  f"{ep['col_ped'] / tot * 100:.1f})  het gio {tr * 100:4.1f}%  Q {qlog:6.2f}  "
                  f"{fps / 1000:.0f}k buoc/s  {(time.time() - t0) / 60:.1f} ph", flush=True)
            export(actor, norm, os.path.join(out, "policy.npz"), meta)
            score = sr - 2 * cr
            if env.density >= 0.99 and score > best:
                best = score
                export(actor, norm, os.path.join(out, "best.npz"), meta)
            ep = dict(success=0, collision=0, timeout=0, col_static=0, col_ped=0)
    export(actor, norm, os.path.join(out, "policy.npz"), meta)
    print(f"XONG -> {out}")


if __name__ == "__main__":
    main()
