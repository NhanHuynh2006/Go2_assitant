"""Chan doan (dieu phoi vien): MPPI BIET TRUOC tuong lai cua nguoi (mo phong truoc dam dong 2.4 s, robot dung yen).
Chi de do MUC TRAN, khong phai thuat toan chay that."""
import copy, math
import numpy as np
from nav_local import MPPI


class FutureMPPI(MPPI):
    people_cap = True
    sim = None

    def futures(self):
        s = self.sim
        T = self.T
        out = []
        if s.crowd:
            c = copy.copy(s.crowd)
            c.people = copy.deepcopy(s.crowd.people)
            c.rng = copy.deepcopy(s.crowd.rng)
            x = tuple(s.x)
            c.robots = [type("R", (), {"map_pose": staticmethod(lambda x=x: x)})()]
            tr = [[] for _ in c.people]
            for k in range(2 * T):
                c.step(0.05)
                if k % 2:
                    for q, p in zip(tr, c.people):
                        q.append(tuple(p["p"]))
            out = [np.array(q) for q in tr]
        return out

    def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
        S, coll, dmin = super().cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        T = P.shape[1]
        for tr in self.futures():
            qx, qy = tr[None, :, 0], tr[None, :, 1]
            d = self.ppl_dist(P, Y, qx, qy, 0.25)
            S += self.w["ppl"] * np.exp(-np.maximum(d, 0.0) / self.ppl_len).sum(1) / T
            S += self.w["col"] * 0.5 * (d < 0.0).any(1)
        return S, coll, dmin
