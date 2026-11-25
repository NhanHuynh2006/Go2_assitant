#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rl_nav/eval_pred.py — so bo du doan nguoi voi van toc khong doi (CV) va Kalman (chinh tren tap val).
  venv/bin/python rl_nav/eval_pred.py <thu muc du lieu> ten=a.npz[,b.npz..] ... """
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nav_pred import DT, Predictor, T  # noqa: E402

TT = np.arange(1, T + 1) * DT


class D:
    def __init__(s, path):
        z = np.load(path)
        for k in z:
            setattr(s, k, z[k])
        s.n = len(s.x)
        s.false = (int(s.n_false), int(s.n_mov))
        # nhan theo SU THAT (khong theo mo hinh)
        v0 = s.cur[:, 2:]
        sp0 = np.hypot(*v0.T)
        dl = s.fut[:, 23] - s.fut[:, 15]                        # dich chuyen 1.6 -> 2.4 s
        spl = np.hypot(*dl.T) / .8
        ang = np.abs(np.angle(np.exp(1j * (np.arctan2(dl[:, 1], dl[:, 0]) - np.arctan2(v0[:, 1], v0[:, 0])))))
        mov = sp0 > .3
        s.lab = np.where(~mov, "dung_dau", np.where(spl < .15, "dung_lai", np.where(ang > math.radians(45), "re", "thang")))
        d = s.fut - (s.rob[:, None, :2] + s.rob[:, None, 2:] * TT[None, :, None])
        s.stand = s.x[:, 75] > 0                                # THAY DUOC: track dang dung (|v| < 0.2)
        s.go = np.hypot(*(s.fut[:, 23] - s.cur[:, :2]).T) > .5
        s.near = np.hypot(*(s.cur[:, :2] - s.rob[:, :2]).T) < 3.0
        s.hit = np.hypot(d[..., 0], d[..., 1]).min(1) < .55
        pc = s.p[:, None] + s.v[:, None] * (s.age[:, None] + TT[None])[..., None]
        dc = pc - (s.rob[:, None, :2] + s.rob[:, None, 2:] * TT[None, :, None])
        s.cvmin = np.hypot(dc[..., 0], dc[..., 1]).min(1)


def cv(d, par=(1.0, 1e9)):
    sc, tc = par
    tau = tc * (1 - np.exp(-TT / tc)) if tc < 1e6 else TT
    m = d.p[:, None] + d.v[:, None] * (d.age[:, None] + sc * tau[None])[..., None]
    return np.ones((d.n, 1)), m[:, None], None


def kalman(d, q=1.0, r=.08):
    n = d.n
    x, P = np.zeros((n, 4)), np.zeros((n, 3))                   # P: pp, pv, vv (2 truc nhu nhau)
    init, tl = np.zeros(n, bool), np.zeros(n)
    for k in range(d.hist.shape[1]):
        z = d.hist[:, k]
        ok = ~np.isnan(z[:, 0])
        dt = np.where(init, z[:, 2] - tl, 0.0)
        dt = np.nan_to_num(dt)
        # du doan
        xx = x.copy()
        xx[:, :2] += x[:, 2:] * dt[:, None]
        pp = P[:, 0] + 2 * dt * P[:, 1] + dt ** 2 * P[:, 2] + q * q * dt ** 3 / 3
        pv = P[:, 1] + dt * P[:, 2] + q * q * dt ** 2 / 2
        vv = P[:, 2] + q * q * dt
        S = pp + r * r
        kp, kv = pp / S, pv / S
        e = z[:, :2] - xx[:, :2]
        xu = np.concatenate([xx[:, :2] + kp[:, None] * e, xx[:, 2:] + kv[:, None] * e], 1)
        Pu = np.stack([pp * (1 - kp), pv * (1 - kp), vv - kv * pv], 1)
        new = ok & ~init
        upd = ok & init
        x = np.where(upd[:, None], xu, x)
        P = np.where(upd[:, None], Pu, P)
        x[new] = np.concatenate([z[new, :2], np.zeros((new.sum(), 2))], 1)
        P[new] = [r * r, 0.0, 1.0]
        tl = np.where(ok, z[:, 2], tl)
        init |= ok
    t = -tl[:, None] + TT[None]                                  # hist: t - now <= 0
    m = x[:, None, :2] + x[:, None, 2:] * t[..., None]
    var = P[:, 0:1] + 2 * t * P[:, 1:2] + t ** 2 * P[:, 2:3] + q * q * t ** 3 / 3
    return np.ones((n, 1)), m[:, None], np.sqrt(var)[:, None]


def net(d, paths):
    """ensemble = ghep mode (trung binh xac suat)"""
    Ps, Ms, Ss = [], [], []
    for p in paths:
        pr = Predictor(p)
        a, m, s = pr.raw(d.x)
        c, sn = np.cos(d.frame[:, 2]), np.sin(d.frame[:, 2])
        mw = np.stack([c[:, None, None] * m[..., 0] - sn[:, None, None] * m[..., 1],
                       sn[:, None, None] * m[..., 0] + c[:, None, None] * m[..., 1]], -1) + d.frame[:, None, None, :2]
        Ps.append(a / len(paths))
        Ms.append(mw)
        Ss.append(s)
    return np.concatenate(Ps, 1), np.concatenate(Ms, 1), np.concatenate(Ss, 1)


def fit_std(d, m):
    """do lech theo tam du doan, RIENG cho nguoi di / dung -> (2,T)"""
    e = ((d.fut - m[:, 0]) ** 2).sum(-1)
    return np.stack([np.sqrt(e[d.stand == g].mean(0) / 2) for g in (0, 1)])


def use_std(d, st):
    return st[d.stand.astype(int)][:, None]


def fan(d, par):
    """quat trac dia cua ALGO (GeoFan, 16 duong) + 1 van toc khong doi, trong so nhu PRISM3 (hoac chinh lai tren val)."""
    sa, sb, wm, ws = par
    f = d.fan.astype(float)
    bad = np.isnan(f[:, 0, 0, 0])
    c = (d.v[:, None] * (d.age[:, None] + TT[None])[..., None] + d.p[:, None] - d.frame[:, None, :2])[:, None]
    f = np.where(bad[:, None, None, None], c, f)
    M = np.concatenate([c, f], 1) + d.frame[:, None, None, :2]
    w = np.where(d.stand, ws, wm)
    P = np.concatenate([w[:, None], np.repeat((1 - w)[:, None] / 16, 16, 1)], 1)
    S = np.broadcast_to(sa + sb * TT, (d.n, 17, T))
    return P, M, S


def nll(d, P, M, S):
    d2 = ((d.fut[:, None] - M) ** 2).sum(-1)
    c = np.log(P + 1e-12)[..., None] - .5 * d2 / S ** 2 - 2 * np.log(S) - math.log(2 * math.pi)
    mx = c.max(1, keepdims=True)
    return -(mx[:, 0] + np.log(np.exp(c - mx).sum(1)))


def dens(y, P, m, s):
    """y (n,Q,2) -> log mat do (n,Q); m (n,K,2), s (n,K)"""
    d2 = ((y[:, :, None] - m[:, None]) ** 2).sum(-1)
    c = np.log(P + 1e-12)[:, None] - .5 * d2 / s[:, None] ** 2 - 2 * np.log(s)[:, None]
    mx = c.max(-1, keepdims=True)
    return mx[..., 0] + np.log(np.exp(c - mx).sum(-1))


def evaluate(d, P, M, S, rng):
    n = d.n
    top = P.argmax(1)
    err = np.linalg.norm(d.fut[:, None] - M, axis=-1)            # (n,K,T)
    e1 = err[np.arange(n), top]
    mean = (P[..., None, None] * M).sum(1)
    em = np.linalg.norm(d.fut - mean, axis=-1)
    NL = nll(d, P, M, S)
    cov = {}
    Q = 96
    for tname, ti in (("1.2", 11), ("2.4", 23)):
        k = (rng.random((n, Q))[..., None] > P.cumsum(1)[:, None]).sum(-1).clip(0, P.shape[1] - 1)
        ms = np.take_along_axis(M[:, :, ti], k[..., None], 1)
        ss = np.take_along_axis(S[:, :, ti], k, 1)
        smp = ms + ss[..., None] * rng.normal(size=(n, Q, 2))
        ls, ly = dens(smp, P, M[:, :, ti], S[:, :, ti]), dens(d.fut[:, None, ti], P, M[:, :, ti], S[:, :, ti])
        u = (ls > ly).mean(1)
        cov[tname] = u
    # nguy co cham robot: quy dao mau, lech chuan dung chung 1 z cho ca quy dao
    Q = 64
    k = (rng.random((n, Q))[..., None] > P.cumsum(1)[:, None]).sum(-1).clip(0, P.shape[1] - 1)
    z = rng.normal(size=(n, Q, 2))
    risk = np.zeros(n)
    rp = d.rob[:, None, :2] + d.rob[:, None, 2:] * TT[None, :, None]
    for q in range(Q):
        kk = k[:, q]
        tr = M[np.arange(n), kk] + S[np.arange(n), kk][..., None] * z[:, q, None]
        dd = tr - rp
        risk += np.hypot(dd[..., 0], dd[..., 1]).min(1) < .55
    risk = (risk + .5) / (Q + 1)
    return dict(ade1=e1.mean(1), fde1=e1[:, -1], ademean=em.mean(1), fdemean=em[:, -1], minfde=err[..., -1].min(1),
                nll=NL.mean(1), nll24=NL[:, -1], u12=cov["1.2"], u24=cov["2.4"], risk=risk)


def auc(y, s):
    if y.all() or not y.any():
        return float("nan")
    from scipy.stats import rankdata
    r = rankdata(s)
    n1 = y.sum()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))


def boot(dl, ep, B=500, seed=0):
    """CI 95 % cua trung binh (lay lai theo TAP = cum)."""
    u, inv = np.unique(ep, return_inverse=True)
    s, c = np.bincount(inv, dl), np.bincount(inv)
    rng = np.random.default_rng(seed)
    w = rng.multinomial(len(u), np.ones(len(u)) / len(u), B)
    q = (w @ s) / np.maximum(w @ c, 1)
    return np.percentile(q, [2.5, 97.5])


def main():
    root, models = sys.argv[1], dict(a.split("=") for a in sys.argv[2:])
    tr, va = D(f"{root}/train_default.npz"), D(f"{root}/val_default.npz")
    # ---- chinh baseline tren VAL (so lan thu ghi lai)
    trials = 0
    best = (9e9,)
    for sc in (.8, .85, .9, .95, 1.0):
        for tc in (1.0, 2.0, 4.0, 1e9):
            _, m, _ = cv(tr, (sc, tc))
            st = fit_std(tr, m)
            P, M, _ = cv(va, (sc, tc))
            v = nll(va, P, M, use_std(va, st)).mean()
            trials += 1
            best = min(best, (v, sc, tc))
    cvp = best[1:]
    bk = (9e9,)
    for q in (.2, .35, .5, .7, 1.0, 1.5):
        for r in (.04, .08, .12, .18):
            P, M, S = kalman(tr, q, r)
            z2 = ((tr.fut - M[:, 0]) ** 2).sum(-1) / 2 / S[:, 0] ** 2
            f = np.stack([np.sqrt(z2[tr.stand == g].mean(0)) for g in (0, 1)])
            P, M, S = kalman(va, q, r)
            v = nll(va, P, M, S * use_std(va, f)).mean()
            trials += 1
            bk = min(bk, (v, q, r, f.tolist()), key=lambda t: t[0])
    print(f"baseline chinh {trials} lan: CV tat dan val {best}, Kalman val {bk[:3]}")
    bf = (9e9,)
    if hasattr(va, "fan"):
        for sa in (.1, .15, .2):
            for sb in (.05, .1, .15, .2, .3):
                for wm in (.1, .3, .55):
                    for ws in (.2, .5):
                        v = nll(va, *fan(va, (sa, sb, wm, ws))).mean()
                        bf = min(bf, (v, sa, sb, wm, ws))
        print("GeoFan chinh 90 lan, val", bf)
    st0 = fit_std(tr, cv(tr)[1])
    st1 = fit_std(tr, cv(tr, cvp)[1])

    def preds(d):
        P, M, _ = cv(d)
        yield "CV", (P, M, use_std(d, st0))
        P, M, _ = cv(d, cvp)
        yield "CV_damp", (P, M, use_std(d, st1))
        P, M, S = kalman(d, *bk[1:3])
        yield "Kalman", (P, M, S * use_std(d, np.array(bk[3])))
        if hasattr(d, "fan"):
            yield "GeoFan", fan(d, bf[1:])
        for k, v in models.items():
            q = net(d, v.split(","))
            yield k, q
            if k == "net":                                       # 0.7 mang + 0.3 van toc khong doi (nhu wcv=0.3 vong kin)
                P, M, _ = cv(d)
                yield "net+cv", (np.concatenate([.7 * q[0], .3 * P], 1), np.concatenate([q[1], M], 1),
                                 np.concatenate([q[2], np.broadcast_to(use_std(d, st0), (d.n, 1, T))], 1))
    out = {}
    files = [f"{root}/val_default.npz"] if "--val" in os.environ.get("EP", "") else \
        sorted(glob.glob(f"{root}/test_*.npz"), key=lambda f: "default" not in f)
    for f in files:
        d = D(f)
        name = os.path.basename(f)[:-4]
        lab = {k: float((d.lab == k).mean().round(3)) for k in np.unique(d.lab)}
        print(f"\n== {name}: n={d.n} tap={len(np.unique(d.ep))} track nham {d.false[0]}/{d.false[1]} nhan {lab} cham {d.hit[d.near].mean():.3f}")
        R = {}
        for k, (P, M, S) in preds(d):
            R[k] = evaluate(d, P, M, S, np.random.default_rng(0))
        late = d.near & (d.cvmin > .8)
        for k, r in R.items():
            o = dict(ade=r["ade1"].mean(), fde=r["fde1"].mean(), fdeM=r["fdemean"].mean(), minfde=r["minfde"].mean(), nll=r["nll"].mean(),
                     cov50=(r["u24"] < .5).mean(), cov90=(r["u24"] < .9).mean(), cov90_12=(r["u12"] < .9).mean(),
                     fde_re=r["fde1"][d.lab == "re"].mean(), fdeM_re=r["fdemean"][d.lab == "re"].mean(),
                     nll_re=r["nll"][d.lab == "re"].mean(), cov90_re=(r["u24"] < .9)[d.lab == "re"].mean(),
                     nll_thang=r["nll"][d.lab == "thang"].mean(), fde_thang=r["fde1"][d.lab == "thang"].mean(),
                     nll_dung=r["nll"][d.lab == "dung_lai"].mean(),
                     brier=((r["risk"] - d.hit) ** 2)[d.near].mean(), auc=auc(d.hit[d.near], r["risk"][d.near]),
                     auc_late=auc(d.hit[late], r["risk"][late]))
            o = {a: float(b) for a, b in o.items()}
            dn = r["nll"] - R["Kalman"]["nll"]
            o["dnll_vs_kalman_ci"] = boot(dn, d.ep).round(3).tolist()
            o["dfdeM_re_vs_kalman_ci"] = boot((r["fdemean"] - R["Kalman"]["fdemean"])[d.lab == "re"], d.ep[d.lab == "re"]).round(3).tolist()
            o["dnll_vs_cvdamp_ci"] = boot(r["nll"] - R["CV_damp"]["nll"], d.ep).round(3).tolist()
            for t_, sel in (("all", d.near), ("stand", d.near & d.stand), ("late", late)):
                b_ = lambda z: ((z["risk"] - d.hit) ** 2)[sel]
                o["dbrier_vs_cv_ci_" + t_] = boot(b_(r) - b_(R["CV"]), d.ep[sel]).round(4).tolist()
                o["dbrier_vs_cvdamp_ci_" + t_] = boot(b_(r) - b_(R["CV_damp"]), d.ep[sel]).round(4).tolist()
            o["dfde_re_vs_cvdamp_ci"] = boot((r["fdemean"] - R["CV_damp"]["fdemean"])[d.lab == "re"], d.ep[d.lab == "re"]).round(3).tolist()
            o["n_late"], o["n_late_hit"] = int(late.sum()), int((late & d.hit).sum())
            out.setdefault(name, {})[k] = o
            g, h = d.stand, ~d.stand
            mv_p = np.zeros(d.n)
            o["dung_nll"], o["dung_fdeM"], o["dung_nll_di"] = [float(q) for q in (r["nll"][g].mean(), r["fdemean"][g].mean(), r["nll"][g & d.go].mean())]
            o["di_nll"], o["di_fdeM"] = float(r["nll"][h].mean()), float(r["fdemean"][h].mean())
            o["dung_cov90"] = float((r["u24"][g] < .9).mean())
            o["dung_auc"] = float(auc(d.hit[g & d.near], r["risk"][g & d.near]))
            o["dung_brier"] = float(((r["risk"] - d.hit) ** 2)[g & d.near].mean())
            o["dnll_vs_fan_ci"] = boot(r["nll"] - R["GeoFan"]["nll"], d.ep).round(3).tolist() if "GeoFan" in R else None
            db = ((r["risk"] - d.hit) ** 2 - (R[ref]["risk"] - d.hit) ** 2) if (ref := "GeoFan" if "GeoFan" in R else "Kalman") else 0
            o["dbrier_vs_ref_ci"] = boot(db[d.near], d.ep[d.near]).round(4).tolist()
            print(f"{k:10s} [dung n={int(g.sum())} di tiep {d.go[g].mean():.2f}: NLL {o['dung_nll']:+.2f} (di {o['dung_nll_di']:+.2f}) FDE {o['dung_fdeM']:.2f} phu90 {o['dung_cov90']:.2f} Brier {o['dung_brier']:.4f} AUC {o['dung_auc']:.3f}] "
                  f"dNLL-fan {o['dnll_vs_fan_ci']} dBrier-ref {o['dbrier_vs_ref_ci']}")
            print(f"{k:10s} ADE {o['ade']:.3f} FDE {o['fde']:.3f} (TB {o['fdeM']:.3f}, min {o['minfde']:.3f}) NLL {o['nll']:+.3f} "
                  f"phu50/90 {o['cov50']:.2f}/{o['cov90']:.2f} | RE: FDE {o['fde_re']:.3f} TB {o['fdeM_re']:.3f} NLL {o['nll_re']:+.3f} phu90 {o['cov90_re']:.2f} "
                  f"| thang FDE {o['fde_thang']:.3f} NLL {o['nll_thang']:+.3f} dung {o['nll_dung']:+.2f} | Brier {o['brier']:.4f} AUC {o['auc']:.3f} late {o['auc_late']:.3f} ({o['n_late_hit']}/{o['n_late']}) "
                  f"| dNLL-KF {o['dnll_vs_kalman_ci']} dFDE_re {o['dfdeM_re_vs_kalman_ci']}")
    json.dump(out, open(os.environ.get("OUT", "/tmp/pred_eval.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
