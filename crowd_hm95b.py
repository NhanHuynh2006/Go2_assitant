# -*- coding: utf-8 -*-
"""Mo hinh nguoi 'hm95b' (agent HM95, 25/11/2026, THAM DO; yeu cau coordinator 18:50). Giong crowd_hm95.py (khong sua file do,
sha da ghi o results/hm95_code.sha256) TRU:
  * ELL = "desired": trong (4) dung v_b dt e_b voi e_b = HUONG MONG MUON cua b (toi diem duong di ke tiep) va v_b = TOC DO MONG
    MUON v0_b, dung chu cua bai bao. Nguoi dang cho / chua co duong: buoc = 0 (dung yen). Robot (khong co huong mong muon): van toc thuc.
  * NOISE: do lech chuan (m/s^2 moi truc) cua nhieu gauss cong vao F (bien the (c)); 0 = khong nhieu (bien the (a)/(b)).
Bien the duoc chon cho TEST (hm95b) dat qua bien moi truong HM95B_NOISE trong research/hm95b_fastsim.py; xem ghi chu bao cao §8."""
import math
import numpy as np
import crowd_hm95 as H

ELL = "desired"
NOISE = 0.0
STATS = H.STATS


def desired_step(pp):
    if pp["wait"] > 0 or not pp["path"]:
        return np.zeros(2)
    to = pp["path"][0] - pp["p"]; dist = float(np.linalg.norm(to))
    return np.zeros(2) if dist < 1e-9 else pp["v0"] * to / dist


def step_people(people, robots, wall_dist, dt, rng, new_goal, others=None):
    STATS["steps"] += 1
    P = np.array([pp["p"] for pp in people], float).reshape(-1, 2)
    if ELL == "desired":
        V = np.array([desired_step(pp) for pp in people], float).reshape(-1, 2)
    else:
        V = np.array([pp["v"] for pp in people], float).reshape(-1, 2)
    Rr = np.array([pp["r"] for pp in people], float)
    idx = np.arange(len(people))
    for i, pp in enumerate(people):
        if "w" not in pp:
            pp["w"] = np.array(pp["v"], float)
        if pp["wait"] > 0:
            pp["wait"] -= dt; pp["w"] = pp["w"] * .5; pp["v"] = pp["v"] * .5; continue
        if not pp["path"]: new_goal(pp)
        to = pp["path"][0] - pp["p"]; dist = np.linalg.norm(to)
        if dist < .3:
            pp["path"].pop(0)
            if not pp["path"]: pp["wait"] = rng.uniform(.5, 3.)
            continue
        e = to / (dist + 1e-9)
        f = (pp["v0"] * e - pp["v"]) / H.TAU
        d, n = wall_dist(*pp["p"])
        STATS["wall_checks"] += 1
        if d < pp["r"]: STATS["wall_pen"] += 1
        if d < 1e-6: STATS["centre_inside"] += 1
        f = f + H.wall_force(d, n)
        m = idx != i
        f = f + H.social_from(pp["p"], e, P[m], V[m], Rr[m], pp["r"])
        if others is not None:
            f = f + H.social_from(pp["p"], e, *others, pp["r"])
        if not pp["distracted"]:
            for rp, rv in robots:
                f = f + H.social_from(pp["p"], e, np.asarray(rp, float)[None], np.asarray(rv, float)[None], np.array([.35]), pp["r"])
        if NOISE > 0:
            f = f + np.array([rng.gauss(0, NOISE), rng.gauss(0, NOISE)])
        w = pp["w"] + f * dt
        if not np.all(np.isfinite(w)):
            STATS["nonfinite"] += 1; w = np.zeros(2)
        pp["w"] = w
        sp = float(np.linalg.norm(w)); vmax = H.VMAX_K * pp["v0"]
        pp["v"] = w * (vmax / sp) if sp > vmax else w.copy()
        pp["p"] = pp["p"] + pp["v"] * dt


def pm_step_hm95b(self, dt):
    robots = []
    if self.robots:
        rp = np.array(self.robots[0].map_pose()[:2])
        c, s = math.cos(self.sim.x[2]), math.sin(self.sim.x[2])
        rv = np.array(self.sim.v[:2]) @ np.array([[c, s], [-s, c]])
        robots = [(rp, rv)]
    step_people(self.people, robots, self._wall_dist, dt, self.rng, self._new_goal)
