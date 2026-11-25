"""Dung bang V: hazard sim (crowd 800-999) va THOR; 9 huong tuong; bang vong ho (27 hanh dong co dinh)."""
import sys, time; sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant")
import numpy as np, nav_sev as S
D = "/home/nhanhuynh/Documents/Go2_assitant/sev/data/"
def kern(n, scale=1.0, stop=None):
    z = np.load(D + f"hazard_{n}.npz", allow_pickle=True)
    # 3 lop toc do 0.6/0.9/1.2 <- cac khoang 0.3-0.6+0.6-0.9, 0.6-0.9+0.9-1.2, 0.9-1.2+1.2-2
    t, k = z["time"], z["n"]
    lam = [(k[0] + k[1]) / (t[0] + t[1]), (k[1] + k[2]) / (t[1] + t[2]), (k[2] + k[3]) / (t[2] + t[3])]
    lam = [l * scale for l in lam]
    print(n, "lam", np.round(lam, 3), "stop", z["stop"], "start", z["start"])
    return S.person_kernel(lam, z["ang"], float(z["stop"]), float(z["start"]), z["st_ang"], 0.21)
if __name__ == "__main__":
    for n in sys.argv[1:]:
        K = kern(n); t = time.time()
        V = np.stack([S.solve(K, wall=w).astype(np.float32) for w in range(9)])
        np.save(D + f"V_{n}.npy", V)
        # vong ho: giu nguyen hanh dong
        O = np.stack([S.solve(K, fixed=a) for a in range(len(S.actions()))]); np.save(D + f"O_{n}.npy", O)
        print(n, V.shape, O.shape, time.time() - t)
