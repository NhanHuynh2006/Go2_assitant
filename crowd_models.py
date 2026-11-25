# -*- coding: utf-8 -*-
"""Mo hinh nguoi THU HAI (kiem chung do vung). Trich tu audit/fs_audit.py (agent AUDIT), chua doi chieu PDF goc:
helb = the nang Helbing-Molnar 1995 dang tron, bien do 7; mous = Moussaid 2009. Dung: fastsim --crowd-model helb|mous."""
import math
import numpy as np


def pm_step(self, dt, pm):
    """movers.Crowd.step voi luc xa hoi khac. mous: Moussaid et al. 2009 (A 4.5, gamma .35, n 2, n' 3, lambda 2);
    helb: the nang Helbing-Molnar 1995 dang tron, bien do V0/sigma = 2.1/.3 = 7. Luc tuong, muc tieu, tiep xuc, nhieu: giu nguyen."""
    robots = [(np.array(r.map_pose()[:2]), np.zeros(2)) for r in self.robots]
    for q, (rp, rv) in zip([0], robots): robots[0] = (rp, np.array(self.sim.v[:2]) @ np.array([[math.cos(self.sim.x[2]), math.sin(self.sim.x[2])], [-math.sin(self.sim.x[2]), math.cos(self.sim.x[2])]]))
    for i, pp in enumerate(self.people):
        if pp["wait"] > 0:
            pp["wait"] -= dt; pp["v"] = pp["v"] * .5; continue
        if not pp["path"]: self._new_goal(pp)
        to = pp["path"][0] - pp["p"]; dist = np.linalg.norm(to)
        if dist < .3:
            pp["path"].pop(0)
            if not pp["path"]: pp["wait"] = self.rng.uniform(.5, 3.)
            continue
        e = to / (dist + 1e-9); f = (pp["v0"] * e - pp["v"]) / .5
        d, n = self._wall_dist(*pp["p"]); f = f + 2. * math.exp((pp["r"] - d) / .12) * n
        if d < pp["r"]: f = f + 120. * (pp["r"] - d) * n
        def social(q, vq, rq):
            diff = pp["p"] - q; dd = np.linalg.norm(diff) + 1e-9; nij = diff / dd
            if pm == "helb":
                w = .35 + .65 * (1 - float(np.dot(nij, e))) / 2; out = 7. * math.exp((pp["r"] + rq - dd) / .3) * nij * w
            else:
                eij = -nij; D = 2. * (pp["v"] - vq) + eij; Dn = np.linalg.norm(D) + 1e-9; t = D / Dn
                th = math.atan2(t[0] * eij[1] - t[1] * eij[0], float(t @ eij)); Bq = .35 * Dn; nl_ = np.array([-t[1], t[0]])
                k = 1. if th > 0 else -1. if th < 0 else 0.
                fv = -math.exp(-dd / Bq - (3. * Bq * th) ** 2); fa = -k * math.exp(-dd / Bq - (2. * Bq * th) ** 2); out = 4.5 * (fv * t + fa * nl_)
            if dd < pp["r"] + rq: out = out + 120. * (pp["r"] + rq - dd) * nij
            return out
        for j, qq in enumerate(self.people):
            if j != i: f = f + social(qq["p"], qq["v"], qq["r"])
        if not pp["distracted"]:
            for rp, rv in robots: f = f + social(rp, rv, .35)
        f = f + np.array([self.rng.gauss(0, .15), self.rng.gauss(0, .15)]); pp["v"] = pp["v"] + f * dt; sp = np.linalg.norm(pp["v"])
        if sp > 1.3 * pp["v0"]: pp["v"] = pp["v"] * 1.3 * pp["v0"] / sp
        pp["p"] = pp["p"] + pp["v"] * dt

