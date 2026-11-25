import math, numpy as np
A, B = np.meshgrid(np.linspace(-.25, .32, 8), np.linspace(-.16, .16, 4)); A, B = A.ravel(), B.ravel()
def fp_dist(p, q):
    c, s = math.cos(p[2]), math.sin(p[2])
    return float(np.hypot(p[0] + c * A - s * B - q[0], p[1] + s * A + c * B - q[1]).min())
