# -*- coding: utf-8 -*-
"""Mo hinh nguoi 'hm95': Helbing & Molnar 1995 (Phys. Rev. E 51, 4282; arXiv cond-mat/9805244) cai TRUNG THANH.
Agent HM95, 25/11/2026. NHANH THAM DO (exploratory robustness arm), KHONG thay ket qua da dang ky nao.
Khong sua file dong bang: crowd_models.py / fastsim.py giu nguyen; chay qua research/hm95_fastsim.py.

Theo bai bao (da doc toan van PDF arXiv):
  (2)  F0 = (v0 e - v) / tau,                      tau = 0.5 s
  (3)  f_ab = -grad_{r_ab} V_ab[b(r_ab)]
  (4)  2b = sqrt((|r_ab| + |r_ab - v_b dt e_b|)^2 - (v_b dt)^2),  dt = 2 s   (khoang cach TAM, khong tru ban kinh)
  (5)  F_aB = -grad U_aB(|r_aB|), r_aB = r_a - (diem gan nhat cua vat)
  (7)  w(e, f) = 1 neu e.f >= |f| cos(phi), c neu khong;  2 phi = 200 deg, c = 0.5
  (8)  F_ab = w(e_a, -f_ab) f_ab
  (10)-(12) dw/dt = F (KHONG nhieu), v = w * min(1, vmax/|w|), vmax = 1.3 v0
  (13) V = V0 exp(-b/sigma), V0 = 2.1 m^2/s^2, sigma = 0.3 m;  U = U0 exp(-|r_aB|/R), U0 = 10 m^2/s^2, R = 0.2 m
Lua chon cai dat (bai bao khong noi ro / khong ap dung duoc):
  * v_b dt e_b: dung VECTO VAN TOC THUC cua b (v_b * dt). Bai bao viet v_b e_b voi e_b la huong mong muon; robot khong co
    'huong mong muon' nen dung van toc thuc cho moi b (nguoi di khong bi can thi hai cach trung nhau).
  * Tuong: khong nhan trong so w (cong thuc (5) khong phu thuoc e; (8) chi dinh nghia w cho F_ab va F_ai).
  * Luc tiep xuc cung (120 k x do chong) cua ban 'helb': TAT mac dinh (HM95 khong co). Xem REPORT_HM95.md muc 'tiep xuc'.
  * Phan con lai giong duong helb cua crowd_models.pm_step: logic dich/duong di, cho (wait), nguoi 'distracted' khong ne robot,
    robot la mot b voi van toc rieng (ban kinh robot chi dung de phat hien va cham trong fastsim, khong vao luc).
  * Tich phan Euler nua an nhu ban cu (w += F dt; v = cap(w); p += v dt), dt = 0.05 s cua fastsim.
"""
import math
import numpy as np

V0, SIGMA, DT_ELL = 2.1, 0.3, 2.0
U0, RW = 10.0, 0.2
TAU, VMAX_K = 0.5, 1.3
PHI = math.radians(100.0)        # 2 phi = 200 deg
COS_PHI = math.cos(PHI)
C_OUT = 0.5
CONTACT = False                  # luc tiep xuc cung kieu helb (chi bat neu can cho on dinh so; mac dinh TAT)
STATS = dict(steps=0, pp_pairs=0, pp_overlap=0, wall_checks=0, wall_pen=0, centre_inside=0, nonfinite=0)


def semi_minor_b(r, y):
    """b cua (4). r: (M,2) = r_a - r_b; y: (M,2) = v_b * dt (vecto buoc cua b)."""
    a = np.hypot(r[:, 0], r[:, 1])
    c = np.hypot(r[:, 0] - y[:, 0], r[:, 1] - y[:, 1])
    s = np.hypot(y[:, 0], y[:, 1])
    return 0.5 * np.sqrt(np.maximum((a + c) ** 2 - s ** 2, 0.0))


def potential(r, y):
    return V0 * np.exp(-semi_minor_b(r, y) / SIGMA)


def pair_force(r, y):
    """f_ab = -grad_r V(b(r)) giai tich (3),(4),(13). db/dr = (a+c)(r/a + (r-y)/c) / (4b)."""
    a = np.maximum(np.hypot(r[:, 0], r[:, 1]), 1e-9)
    ry = r - y
    c = np.maximum(np.hypot(ry[:, 0], ry[:, 1]), 1e-9)
    s = np.hypot(y[:, 0], y[:, 1])
    b = 0.5 * np.sqrt(np.maximum((a + c) ** 2 - s ** 2, 0.0))
    g = ((a + c) / (4.0 * np.maximum(b, 1e-6)))[:, None] * (r / a[:, None] + ry / c[:, None])
    return (V0 / SIGMA) * np.exp(-b / SIGMA)[:, None] * g


def weight(e, f):
    """(7)-(8): w(e_a, -f_ab). 1 neu huong toi b (= -f) nam trong goc nhin 2 phi = 200 deg, c neu khong."""
    nf = np.hypot(f[:, 0], f[:, 1])
    return np.where(-(f @ e) >= nf * COS_PHI, 1.0, C_OUT)


def wall_force(d, n):
    """(5),(13): -grad U0 exp(-|r_aB|/R) = (U0/R) exp(-d/R) n, d = khoang cach TAM -> diem vat gan nhat."""
    return (U0 / RW) * math.exp(-d / RW) * n


def social_from(p, e, Q, VQ, RQ, r_self):
    """Tong luc xa hoi len nguoi o p (huong mong muon e) tu cac b o Q (M,2) van toc VQ (M,2) ban kinh RQ (M,)."""
    if not len(Q):
        return np.zeros(2)
    r = p[None, :] - Q
    f = pair_force(r, VQ * DT_ELL)
    f = f * weight(e, f)[:, None]
    dd = np.hypot(r[:, 0], r[:, 1])
    ov = dd < r_self + RQ
    STATS["pp_pairs"] += len(Q); STATS["pp_overlap"] += int(ov.sum())
    if CONTACT and ov.any():                                   # y het ban helb (chi khi bat CONTACT)
        nij = r / np.maximum(dd, 1e-9)[:, None]
        f = f + (120. * (r_self + RQ - dd) * ov)[:, None] * nij
    return f.sum(0)


def step_people(people, robots, wall_dist, dt, rng, new_goal, others=None):
    """Mot buoc HM95 cho danh sach nguoi (dict p, v, v0, r, path, wait, distracted[, w]).
    robots: list (p(2,), v(2,)) cac b khong phai nguoi. Logic dich/cho y het crowd_models.pm_step.
    others: (Q, VQ, RQ) b phu (chi dung trong kiem tra hop ly: anh tuan hoan); fastsim khong dung."""
    STATS["steps"] += 1
    P = np.array([pp["p"] for pp in people], float).reshape(-1, 2)
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
        f = (pp["v0"] * e - pp["v"]) / TAU                                    # (2)
        d, n = wall_dist(*pp["p"])                                            # (5)
        STATS["wall_checks"] += 1
        if d < pp["r"]: STATS["wall_pen"] += 1
        if d < 1e-6: STATS["centre_inside"] += 1
        f = f + wall_force(d, n)
        if CONTACT and d < pp["r"]: f = f + 120. * (pp["r"] - d) * n
        m = idx != i                                                          # (3),(4),(7),(8)
        f = f + social_from(pp["p"], e, P[m], V[m], Rr[m], pp["r"])
        if others is not None:
            f = f + social_from(pp["p"], e, *others, pp["r"])
        if not pp["distracted"]:
            for rp, rv in robots:
                f = f + social_from(pp["p"], e, np.asarray(rp, float)[None], np.asarray(rv, float)[None], np.array([.35]), pp["r"])
        w = pp["w"] + f * dt                                                  # (10), khong nhieu
        if not np.all(np.isfinite(w)):
            STATS["nonfinite"] += 1; w = np.zeros(2)
        pp["w"] = w
        sp = float(np.linalg.norm(w)); vmax = VMAX_K * pp["v0"]               # (11),(12)
        pp["v"] = w * (vmax / sp) if sp > vmax else w.copy()
        pp["p"] = pp["p"] + pp["v"] * dt


def pm_step_hm95(self, dt):
    """Thay crowd_models.pm_step(self, dt, 'hm95') cho lop FastCrowd cua fastsim (robot = b voi van toc the gioi)."""
    robots = []
    if self.robots:
        rp = np.array(self.robots[0].map_pose()[:2])
        c, s = math.cos(self.sim.x[2]), math.sin(self.sim.x[2])
        rv = np.array(self.sim.v[:2]) @ np.array([[c, s], [-s, c]])         # than -> the gioi, nhu crowd_models
        robots = [(rp, rv)]
    step_people(self.people, robots, self._wall_dist, dt, self.rng, self._new_goal)
