"""Phan tich ban ghi sysid_isaac -> bang gain/tre/tau/lac. venv/bin/python isaac_val/analyze.py raw_flat_steps.npz [...]"""
import sys, json
import numpy as np
H = 50
AX = ["vx", "vy", "wz"]


def segs(d):
    """Cac doan lenh (env, k0, cmd) cua bai steps: 1.5 s dung, 4 s lenh, 2 s dung; bo doan co nga."""
    rec = d["rec"]
    L = int(1.5 * H) + 4 * H + 2 * H
    out, falls = [], []
    for r in range(len(rec) // L):
        for e in range(rec.shape[1]):
            s = rec[r * L:(r + 1) * L, e]
            u = s[int(1.5 * H) + 5, 9:12]
            if s[:, 12].any():
                falls.append(u)
                continue
            out.append((u, s))
    return out, falls


def fopdt(y, u, dt=.02, n=int(2.0 * H)):
    """y: dap ung trung binh nhieu lan (buoc lenh bat dau o mau 0). Fit K, tau, tre."""
    y = y[:n]
    t = (np.arange(n) + 1) * dt
    best = (1e9,)
    for d in np.arange(0, .31, .01):
        for tau in np.arange(.02, .81, .01):
            s = np.where(t > d, 1 - np.exp(-(t - d).clip(0) / tau), 0)
            K = float(s @ y / (s @ s + 1e-12))
            e = float(((y - K * s) ** 2).mean())
            if e < best[0]:
                best = (e, K, tau, d)
    return best[1] / u, best[2], best[3], best[0] ** .5


def detr(a):
    t = np.arange(len(a))
    return a - np.polyval(np.polyfit(t, a, 2), t)


def main(files):
    allout = {}
    for f in files:
        d = np.load(f, allow_pickle=True)
        S, falls = segs(d)
        name = f.split("/")[-1].replace("raw_", "").replace(".npz", "")
        print(f"\n### {name}  (n doan {len(S)}, nga {len(falls)}; khoi luong {d['mass'].min():.1f}-{d['mass'].max():.1f} kg)")
        k1, k2 = int(1.5 * H), int(5.5 * H)
        rows = []
        print("| truc | lenh | n | v on dinh tb [p10,p90] | gain | troi truc khac (vx,vy,wz) | tau | tre | t63 | t90 | quang dung sau stop |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for ax in range(3):
            us = sorted({round(float(u[ax]), 3) for u, _ in S if abs(u[ax]) > 0 and np.abs(np.delete(u, ax)).sum() == 0})
            for u in us:
                G = np.array([s for c, s in S if abs(c[ax] - u) < 1e-3 and np.abs(np.delete(c, ax)).sum() == 0])
                y = G[:, k1:k2, 6 + ax]
                ss = y[:, 2 * H:].mean(1)
                cross = G[:, k1 + 2 * H:k2, 6:9].mean((0, 1))
                m = y.mean(0)
                K, tau, dl, rm = fopdt(m, u)
                fin = ss.mean()
                ms = np.convolve(m, np.ones(5) / 5, "same")
                t63 = next((i * .02 + .02 for i in range(len(ms)) if ms[i] / fin > .632), np.nan) if abs(fin) > .02 else np.nan
                t90 = next((i * .02 + .02 for i in range(len(ms)) if ms[i] / fin > .9), np.nan) if abs(fin) > .02 else np.nan
                stop = G[:, k2:k2 + 2 * H, 6 + ax].sum(1) * .02
                rows.append(dict(ax=AX[ax], u=u, n=len(G), ss=float(fin), p10=float(np.percentile(ss, 10)), p90=float(np.percentile(ss, 90)),
                                 gain=float(fin / u), tau=float(tau), delay=float(dl), t63=float(t63), t90=float(t90),
                                 cross=[float(c) for c in cross], stop=float(np.median(stop))))
                print(f"| {AX[ax]} | {u:+.2f} | {len(G)} | {fin:+.3f} [{np.percentile(ss, 10):+.3f},{np.percentile(ss, 90):+.3f}] | {fin / u:.2f} | "
                      f"{cross[0]:+.3f},{cross[1]:+.3f},{cross[2]:+.3f} | {tau:.2f} | {dl:.2f} | {t63:.2f} | {t90:.2f} | {np.median(stop):+.3f} |")
        wob = {}
        for lab, lo, hi in (("dung", -1, .01), ("di<=.2", .01, .21), (".2-.5", .21, .51), (">.5", .51, 9)):
            xs = []
            for u, s in S:
                if not lo < np.hypot(u[0], u[1]) <= hi:
                    continue
                if lab == "dung" and abs(u[2]) > 0:
                    continue
                q = s[k1 + H:k2] if lab != "dung" else s[k1 + H:k2]
                c, sn = np.cos(q[:, 5]), np.sin(q[:, 5])
                yw = detr(np.unwrap(q[:, 5]))
                h = np.unwrap(q[:, 5]).mean()
                fx = q[:, 0] * np.cos(h) + q[:, 1] * np.sin(h)
                fy = -q[:, 0] * np.sin(h) + q[:, 1] * np.cos(h)
                xs.append([detr(fx).std(), detr(fy).std(), yw.std(), q[:, 3].std(), q[:, 4].std(), q[:, 2].std(), q[:, 6].std(), q[:, 7].std(), q[:, 8].std()])
            if xs:
                wob[lab] = [float(x) for x in np.median(xs, 0)]
        for u, s in S[:0]:
            pass
        z = np.array([s[25:75] for _, s in S])
        print("\nLac than (trung vi do lech chuan sau khi bo xu huong bac 2): x m, y m, yaw rad, roll rad, pitch rad, z m, vx, vy, wz")
        for k, v in wob.items():
            print("  ", k, " ".join(f"{x:.3f}" for x in v))
        print("   luc lenh 0 (truoc buoc): |v| tb", np.round(np.abs(z[:, :, 6:9]).mean((0, 1)), 4))
        allout[name] = dict(rows=rows, wob=wob, n=len(S), falls=len(falls), fall_cmds=[[float(x) for x in u] for u in falls])
    json.dump(allout, open(__file__.replace("analyze.py", "sysid_isaac.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
