"""BlobTracker: van toc sai khi mat dau 1-2 lan quet (dt chi la 1 chu ky). venv/bin/python audit/b2_tracker.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, nav_local as nl
blob = lambda x: np.array([[x + a, b] for a in np.linspace(-.15, .15, 6) for b in np.linspace(-.15, .15, 6)])
for miss in (0, 1, 2):
    for sp in (.6, .9, 1.2):
        tr = nl.BlobTracker(); t = 10.; V = []
        for k in range(14):
            t += .2; x = -1.2 + sp * .2 * k; far = np.array([[-2., 2.], [-2., 2.15], [-2, 2.25]])
            tr.update(np.concatenate([blob(x), far]) if not (8 <= k < 8 + miss) else far, (0, 0), t)
            q = [z for z in tr.tracks if abs(z["p"][1]) < .5]; V.append(round(max([float(np.linalg.norm(z["v"])) for z in q] or [-1]), 2))
        print("that %.1f m/s, mat %d quet -> |v| truoc %s | sau khi thay lai %s%s" % (sp, miss, V[6:8], V[8 + miss:], "  (track moi, v=0)" if 0. in V[8:] else ""))
