#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/eval2d.py — so sanh cac policy RL tren CUNG bo thu 2D co dinh (seed rieng, khong trung
luc train), mat do vat can day du, 4096 tap.

    venv/bin/python rl_nav/eval2d.py rl_nav/runs/ppo_v2/best.npz rl_nav/runs/td3_v1/best.npz

In: toi dich / va vat / va nguoi / het gio / thoi gian TB / khoang 95 % (Wilson).
"""

import math
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import NavEnv  # noqa: E402


def load(path, dev):
    z = np.load(path)
    W = [torch.tensor(z[f"W{i}"], device=dev) for i in range(10) if f"W{i}" in z]
    b = [torch.tensor(z[f"b{i}"], device=dev) for i in range(10) if f"b{i}" in z]
    mu, sd = torch.tensor(z["obs_mean"], device=dev), torch.tensor(z["obs_std"], device=dev)
    out = str(z["out"]) if "out" in z else "clip"

    def f(o):
        x = ((o - mu) / sd).clamp(-8, 8)
        for k in range(len(W)):
            x = x @ W[k] + b[k]
            if k < len(W) - 1:
                x = torch.nn.functional.elu(x)
        return torch.tanh(x) if out == "tanh" else x.clamp(-1, 1)
    return f


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def evaluate(path, episodes=4096, seed=12345, realistic=False, dyn="linear"):
    dev = "cuda"
    if "+" in path:                                   # "a.npz+b.npz": trung binh hanh dong (ensemble)
        pols = [load(p_, dev) for p_ in path.split("+")]
        pol = lambda o: torch.stack([f(o) for f in pols]).mean(0)
    else:
        pol = load(path, dev)
    env = NavEnv(n=episodes, device=dev, seed=seed, realistic=realistic, dyn=dyn)
    env.density = 1.0
    env.reset(torch.arange(episodes, device=dev))
    obs = env.obs()
    done_once = torch.zeros(episodes, dtype=torch.bool, device=dev)
    res = {k: torch.zeros(episodes, dtype=torch.bool, device=dev)
           for k in ("success", "col_static", "col_ped", "timeout")}
    steps = torch.zeros(episodes, device=dev)
    with torch.no_grad():
        for t in range(env.max_steps + 1):
            obs, r, done, info = env.step(pol(obs))
            new = done & ~done_once
            for k in res:
                res[k] |= new & info[k]
            steps = torch.where(new, torch.full_like(steps, t + 1), steps)
            done_once |= done
            if done_once.all():
                break
    n = episodes
    out = {k: int(v.sum()) for k, v in res.items()}
    out["time_s"] = float((steps[res["success"]] * env.dt).mean()) if out["success"] else float("nan")
    return out, n


if __name__ == "__main__":
    print(f"{'policy':34s} {'toi dich':>16s} {'va vat':>8s} {'va nguoi':>9s} {'het gio':>8s} {'t TB':>6s}")
    real = "--realistic" in sys.argv
    dyn = ([x.split("=")[1] for x in sys.argv if x.startswith("--dyn=")] or ["linear"])[0]   # linear|measured|champ|real
    for p in [x for x in sys.argv[1:] if not x.startswith("--")]:
        o, n = evaluate(p, realistic=real, dyn=dyn)
        lo, hi = wilson(o["success"], n)
        print(f"{p[-34:]:34s} {o['success'] / n * 100:5.1f}% [{lo * 100:4.1f}-{hi * 100:4.1f}] "
              f"{o['col_static'] / n * 100:7.1f}% {o['col_ped'] / n * 100:8.1f}% "
              f"{o['timeout'] / n * 100:7.1f}% {o['time_s']:6.1f}")
