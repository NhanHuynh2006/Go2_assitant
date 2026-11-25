#!/usr/bin/env python3
"""Xuat critic V(o) cua PPO (best.pt) ra numpy (.npz) cho AP-MPPI.
    venv/bin/python rl_nav/export_value.py rl_nav/runs/ppo_v2 rl_nav/value_nav.npz"""
import sys
import numpy as np
import torch

run, out = sys.argv[1], sys.argv[2]
sd = torch.load(f"{run}/best.pt", map_location="cpu")
ks = sorted({k.split(".")[1] for k in sd if k.startswith("vf.") and k.endswith(".weight")}, key=int)
np.savez(out, **{f"W{i}": sd[f"vf.{k}.weight"].numpy().T for i, k in enumerate(ks)},
         **{f"b{i}": sd[f"vf.{k}.bias"].numpy() for i, k in enumerate(ks)})
print("critic", [sd[f"vf.{k}.weight"].shape for k in ks], "->", out)
