#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_nav/complement.py — CO DANG TRON NHIEU POLICY KHONG? (phan tich bu tru, danh gia GHEP CAP)

Moi policy chay tren CUNG 4096 tinh huong (khong tu reset -> nguoi, nhieu, vat giong het).
In ra:
  - tung policy: toi dich / va vat / va nguoi
  - ma tran "A hong ma B lam duoc" (%), kiem dinh McNemar (exact) tung cap
  - ORACLE: neu moi tinh huong chon dung policy tot nhat -> tran tren loi ich khi tron
QUY TAC (dat truoc khi co so lieu, PLAN.md):
  oracle - tot nhat < 1 diem %  -> dung 1 policy
  nguoc lai                     -> ghep tham lam trong PRISM (Gazebo), giu cai co y nghia

    venv/bin/python rl_nav/complement.py ppo=rl_nav/runs/ppo_r_s0/best.npz td3=... sac=... [--realistic]
"""
import itertools
import math
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env import NavEnv  # noqa: E402
from eval2d import load  # noqa: E402


def run(path, n, seed, realistic):
    dev = "cuda"
    pol = load(path, dev)
    env = NavEnv(n=n, device=dev, seed=seed, realistic=realistic)
    env.density, env.auto_reset = 1.0, False
    env.reset(torch.arange(n, device=dev))
    obs = env.obs()
    res = {k: torch.zeros(n, dtype=torch.bool, device=dev) for k in ("success", "col_static", "col_ped")}
    done_once = torch.zeros(n, dtype=torch.bool, device=dev)
    with torch.no_grad():
        for _ in range(env.max_steps + 1):
            obs, r, done, info = env.step(pol(obs))
            new = done & ~done_once
            for k in res:
                res[k] |= new & info[k]
            done_once |= done
            if done_once.all():
                break
    return {k: v.cpu() for k, v in res.items()}


def mcnemar_p(b, c):
    """McNemar chinh xac (nhi thuc 2 phia) cho b = A dung B sai, c = A sai B dung."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


if __name__ == "__main__":
    real = "--realistic" in sys.argv
    items = [a.split("=", 1) for a in sys.argv[1:] if "=" in a]
    n, seed = 4096, 777
    R = {name: run(p, n, seed, real) for name, p in items}
    print(f"{'policy':8s} {'toi dich':>9s} {'va vat':>7s} {'va nguoi':>9s}   (cam bien {'thuc te' if real else 'hoan hao'}, {n} tinh huong ghep cap)")
    for k, r in R.items():
        print(f"{k:8s} {r['success'].float().mean() * 100:8.1f}% {r['col_static'].float().mean() * 100:6.1f}% "
              f"{r['col_ped'].float().mean() * 100:8.1f}%")
    names = list(R)
    print("\nA hong ma B lam duoc (% tinh huong), McNemar p:")
    for a, b in itertools.permutations(names, 2):
        fa, sb = ~R[a]["success"], R[b]["success"]
        x = int((fa & sb).sum())
        y = int((R[a]["success"] & ~sb).sum())
        print(f"  {a:6s} hong, {b:6s} duoc: {x / n * 100:5.2f}%   (p = {mcnemar_p(x, y):.3g})")
    best = max(names, key=lambda k: R[k]["success"].float().mean())
    best_sr = R[best]["success"].float().mean() * 100
    print("\nORACLE (moi tinh huong chon dung policy):")
    for m in range(2, len(names) + 1):
        for combo in itertools.combinations(names, m):
            orc = torch.stack([R[k]["success"] for k in combo]).any(0).float().mean() * 100
            print(f"  {'+'.join(combo):18s} {orc:5.1f}%   (+{orc - best_sr:.1f} diem so voi {best})")
    allorc = torch.stack([R[k]["success"] for k in names]).any(0).float().mean() * 100
    print(f"\nKET LUAN: tot nhat {best} {best_sr:.1f}%; tran tren khi tron tat ca {allorc:.1f}% "
          f"(+{allorc - best_sr:.1f}). " + ("-> DUNG 1 POLICY (tron khong dang)" if allorc - best_sr < 1.0
                                          else "-> THU GHEP THAM LAM TRONG PRISM (Gazebo)"))
