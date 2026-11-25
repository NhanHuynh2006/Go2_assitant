"""Tham do sau khi rot: gia tri XAU NHAT huu han tam (kieu CN-CBF: nguoi doi nghich |w|<=0.35, robot chon truoc), gia tri = ho nho nhat.
Dong thoi kiem so khang dinh 'robot 0.29 m/s luon bi bat' (OSS 0.2) bang tam 3/6/12 s. Luoi R=9 m khi kiem 12 s."""
import sys, time; sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant")
import numpy as np, nav_sev as S
OM = 0.35
def solve_adv(horizon, R, dr, speeds, om=OM):
    A = S.actions(); g = np.arange(-R, R + 1e-6, dr, dtype=np.float32); G = len(g); NP = S.NPSI
    X, Y = np.meshgrid(g, g, indexing="ij"); psi = np.arange(NP, dtype=np.float32) * 2 * np.pi / NP
    ps = psi[None, None]; X3, Y3 = X[..., None], Y[..., None]
    out_all = []
    for sp in speeds:
        C0 = S.clearance(X3, Y3).astype(np.float32) + 0 * ps
        V = C0.copy(); oms = (0.0,) if sp == 0 else (-om, 0.0, om)
        for k in range(int(round(horizon / S.DT))):
            best = None
            for vx, vy, wz in A:
                worst = None
                for w in oms:
                    cmin = None
                    for m in (1, 2, 3):
                        t = S.DT * m / 3; h = 0.5 * wz * t
                        dx, dy = (vx * np.cos(h) - vy * np.sin(h)) * t, (vx * np.sin(h) + vy * np.cos(h)) * t
                        ph = ps + 0.5 * w * t
                        ex, ey = X3 + sp * t * np.cos(ph) - dx, Y3 + sp * t * np.sin(ph) - dy
                        c, sn = np.cos(wz * t), np.sin(wz * t); bx, by = c * ex + sn * ey, -sn * ex + c * ey
                        q = S.clearance(bx, by); cmin = q if cmin is None else np.minimum(cmin, q)
                    fx, fy = (bx + R) / dr, (by + R) / dr; o = (fx < 0) | (fx > G - 1) | (fy < 0) | (fy > G - 1)
                    fx, fy = np.clip(fx, 0, G - 1.001), np.clip(fy, 0, G - 1.001); ix, iy = fx.astype(np.int32), fy.astype(np.int32)
                    fx, fy = (fx - ix).astype(np.float32), (fy - iy).astype(np.float32)
                    fp = (psi + (w - wz) * S.DT) / (2 * np.pi / NP); ip = np.floor(fp).astype(int); wp = (fp - ip).astype(np.float32)
                    v = V.ravel(); val = 0.0
                    for ii, w_ in ((ip % NP, 1 - wp), ((ip + 1) % NP, wp)):
                        b = (ix * G + iy) * NP + ii[None, None]
                        val = val + w_ * ((1 - fx) * (1 - fy) * v[b] + fx * (1 - fy) * v[b + G * NP] + (1 - fx) * fy * v[b + NP] + fx * fy * v[b + (G + 1) * NP])
                    val = np.minimum(np.where(o, np.maximum(cmin, 0.5), val), cmin)
                    worst = val if worst is None else np.minimum(worst, val)
                best = worst if best is None else np.maximum(best, worst)
            V = np.minimum(best, C0).astype(np.float32)
        out_all.append(V)
    return np.stack(out_all, -1), X, Y, psi
if __name__ == "__main__":
    D = "/home/nhanhuynh/Documents/Go2_assitant/sev/data/"
    t = time.time()
    V, X, Y, psi = solve_adv(3.0, S.R_MAX, S.DR, S.SPEEDS); np.save(D + "A3.npy", V); print("3s", V.shape, time.time() - t, flush=True)
    for H in (3.0, 6.0, 12.0):
        W, X, Y, psi = solve_adv(H, 9.0, 0.2, [0.9]); d = np.hypot(X, Y)
        hd = np.abs(((np.arctan2(-Y, -X)[..., None] - psi + np.pi) % (2 * np.pi)) - np.pi)      # lech huong so voi robot
        for lo, hi in ((1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 4.0)):
            m = (d >= lo) & (d < hi); f = [float((W[..., 0][m] < 0)[hd[m] < a].mean()) for a in (np.pi / 6, np.pi / 2, np.pi)]
            print(f"  tam {H:.0f} s, d {lo}-{hi} m: ti le trang thai bi bat (nguoi 0.9 m/s, xau nhat) huong vao <30do {f[0]:.2f}  <90do {f[1]:.2f}  moi huong {f[2]:.2f}", flush=True)
