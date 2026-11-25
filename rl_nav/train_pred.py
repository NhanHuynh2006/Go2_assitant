#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rl_nav/train_pred.py — train MDN nho (nav_pred.Predictor) tren du lieu pred_data.py.
  venv/bin/python rl_nav/train_pred.py --train a.npz [b.npz] --val v.npz --out x.npz [--ablate hist|rays|robot|ctx]"""
import argparse
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nav_pred import DT, KN, T  # noqa: E402

DEV = "cuda"
BLK = dict(hist=slice(0, 32), rays=slice(51, 75), robot=slice(35, 41), others=slice(41, 51))


def mask(x, ab):
    x = x.copy()
    for a in ab:
        if a == "ctx":
            x[:, :32] = 0
            x[:, 34:75] = 0
        else:
            x[:, BLK[a]] = 0
    return x


def load(paths, ab=()):
    X, Y, F = [], [], []
    for p in paths:
        z = np.load(p)
        fr = z["frame"]
        d = z["fut"] - fr[:, None, :2]
        c, s = np.cos(fr[:, 2])[:, None], np.sin(fr[:, 2])[:, None]
        Y.append(np.stack([c * d[..., 0] + s * d[..., 1], -s * d[..., 0] + c * d[..., 1]], -1))
        X.append(mask(z["x"], ab))
        F.append(fr)
    return np.concatenate(X), np.concatenate(Y).astype(np.float32), np.concatenate(F)


class Net(nn.Module):
    def __init__(self, dim, K, hid):
        super().__init__()
        self.K = K
        self.f = nn.Sequential(nn.Linear(dim, hid), nn.ELU(), nn.Linear(hid, hid), nn.ELU(),
                               nn.Linear(hid, K * (3 * len(KN) + 1)))
        with torch.no_grad():
            self.f[-1].weight *= .1
            b = torch.zeros(K, 3 * len(KN) + 1)
            a = torch.linspace(-.8, .8, K)
            kn = torch.tensor(KN, dtype=torch.float32)
            b[:, :len(KN)] = (torch.cos(a)[:, None] - 1) * kn * .5
            b[:, len(KN):2 * len(KN)] = torch.sin(a)[:, None] * kn * .5
            b[:, 2 * len(KN):3 * len(KN)] = torch.log(.15 + .25 * kn)
            self.f[-1].bias.copy_(b.ravel())
        # noi suy tuyen tinh nut -> 24 buoc (nut 0 = lech goc hoc duoc)
        self.register_buffer("M", torch.tensor(interp(), dtype=torch.float32))
        self.register_buffer("tt", torch.arange(1, T + 1) * DT)

    def forward(self, xn, sp):
        B, L = len(xn), len(KN)
        o = self.f(xn).view(B, self.K, 3 * L + 1)
        mx = o[..., :L] @ self.M.T + (sp[:, None] * self.tt)[:, None]
        my = o[..., L:2 * L] @ self.M.T
        ls = (o[..., 2 * L:3 * L] @ self.M.T).clamp(-3.5, 1.2)
        return torch.log_softmax(o[..., -1], -1), torch.stack([mx, my], -1), ls


def interp():
    tt = np.arange(1, T + 1) * DT
    M = np.zeros((T, len(KN)))
    for j in range(len(KN)):
        e = np.zeros(len(KN))
        e[j] = 1
        M[:, j] = np.interp(tt, KN, e)
    return M


def nll(lp, mu, ls, y):
    """-> (NLL bien tung buoc (B,T), NLL ca quy dao / T (B,))"""
    d2 = ((y[:, None] - mu) ** 2).sum(-1)
    c = -0.5 * d2 * torch.exp(-2 * ls) - 2 * ls - math.log(2 * math.pi)
    step = -torch.logsumexp(lp[..., None] + c, 1)
    traj = -torch.logsumexp(lp + c.sum(-1), 1) / T
    return step, traj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+")
    ap.add_argument("--val", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--K", type=int, default=5)
    ap.add_argument("--hid", type=int, default=128)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ep", type=int, default=60)
    ap.add_argument("--wd", type=float, default=1e-3)
    ap.add_argument("--traj", type=float, default=.2)
    ap.add_argument("--ablate", nargs="*", default=[])
    ap.add_argument("--mirror", type=int, default=1)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    X, Y, _ = load(a.train, a.ablate)
    Xv, Yv, _ = load(a.val, a.ablate)
    sp, spv = X[:, 32].copy(), Xv[:, 32].copy()
    mu, sd = X.mean(0), X.std(0) + 1e-3
    sd[X.std(0) < 1e-6] = 1.0
    t = lambda q: torch.tensor(q, device=DEV, dtype=torch.float32)
    X, Y, Xv, Yv, sp, spv, mu_, sd_ = map(t, (X, Y, Xv, Yv, sp, spv, mu, sd))
    net = Net(X.shape[1], a.K, a.hid).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=a.wd)
    B, n = 2048, len(X)
    steps = a.ep * (n // B)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    best, bs = 1e9, None
    # doi xung guong (trai/phai): nhan doi du lieu
    sg = torch.ones(X.shape[1], device=DEV)
    sg[1:32:4] = -1
    sg[[36, 38]] = -1
    sg[[42, 44, 47, 49]] = -1
    perm_r = torch.arange(X.shape[1], device=DEV)
    perm_r[51:75] = 51 + (-torch.arange(24, device=DEV)) % 24
    t0 = time.time()
    for e in range(a.ep):
        net.train()
        for j in torch.randperm(n, device=DEV).split(B):
            if len(j) < B:
                continue
            x, y, s = X[j], Y[j], sp[j]
            if a.mirror:
                m = torch.rand(len(j), device=DEV) < .5
                x = torch.where(m[:, None], (x * sg)[:, perm_r], x)
                y = torch.where(m[:, None, None], y * torch.tensor([1., -1.], device=DEV), y)
            st, tr = nll(*net(((x - mu_) / sd_).clamp(-6, 6), s), y)
            loss = st.mean() + a.traj * tr.mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            sch.step()
        net.eval()
        with torch.no_grad():
            st, _ = nll(*net(((Xv - mu_) / sd_).clamp(-6, 6), spv), Yv)
            v = st.mean().item()
        if v < best:
            best, bs = v, {k: q.clone() for k, q in net.state_dict().items()}
        if e % 20 == 19 or e == a.ep - 1:
            print(f"{os.path.basename(a.out)} ep {e} train {loss.item():.3f} val {v:.4f} best {best:.4f} {time.time()-t0:.0f}s", flush=True)
    net.load_state_dict(bs)
    lin = [m for m in net.f if isinstance(m, nn.Linear)]
    np.savez(a.out, **{f"W{i}": l.weight.detach().cpu().numpy().T for i, l in enumerate(lin)},
             **{f"b{i}": l.bias.detach().cpu().numpy() for i, l in enumerate(lin)}, mu=mu, sd=sd, K=a.K, val=best,
             ablate=np.array(a.ablate))


if __name__ == "__main__":
    main()
