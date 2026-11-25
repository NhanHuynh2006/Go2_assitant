#!/usr/bin/env python3
"""Chay fastsim BAN CHUP (audit/snap, 22/11 23:01) voi tung GIA DINH bi doi, khong sua code goc.
  venv/bin/python audit/fs_audit.py --cond base --n 100 --lo 150 --configs mppi ... --jobs 3 --out audit/out/base
CHI DEV (seed < 1000)."""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ[_k] = "1"
import argparse, csv, json, math, pickle, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H + "/snap")
import numpy as np
import fastsim as fs, nav_local as nl, nav_prism2 as np2, robot_ros
assert fs.__file__.startswith(H + "/snap")
COND = dict(base={}, fast=dict(vscale=1.3), slow=dict(vscale=.7), dense=dict(dn=3), dis0=dict(dis=0.), dis6=dict(dis=.6),
            seen2=dict(seen=.2), cmd2=dict(cmd=.2), wob0=dict(wob=0.), wob2=dict(wob=2.), real_body=dict(body=(.35, .35, .155)),
            real=dict(regime="real"), soft5=dict(tol=.05), noresp=dict(dis=1.), mous=dict(pm='mous'), helb=dict(pm='helb'))
P = {}

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

def future_ctrl(base, tag, sim):
    """Tran: MPPI biet tuong lai nguoi. fstat: robot dung yen khi mo phong truoc (= oracle_ctrl); fplan: robot theo ke hoach hien tai;
    frng: nhu fplan nhung nhieu/diem den tiep theo lay rng khac; fcv: trang thai that, van toc khong doi."""
    import copy, random
    class Fut(nl.MPPI):
        def cost(s, U, Pp, Y, field, meta, path, s_path, i0, people, goal, u_prev):
            S, coll, dmin = super().cost(U, Pp, Y, field, meta, path, s_path, i0, [], goal, u_prev); T = Pp.shape[1]; cr = sim.crowd
            if cr is None: return S, coll, dmin
            if tag == "fcv": tr = [p["p"] + p["v"] * .1 * np.arange(1, T + 1)[:, None] for p in cr.people]
            else:
                c = copy.copy(cr); c.people = copy.deepcopy(cr.people); c.rng = copy.deepcopy(cr.rng)
                if tag == "frng": c.rng = random.Random(int(sim.clock.t * 1000))
                pl = nl.MPPI.rollout(s, s.U[None], sim.x, sim.v, .6)[0][0] if tag in ("fplan", "frng") else None
                now = [tuple(sim.x)]; c.robots = [type("R", (), {"map_pose": staticmethod(lambda: now[0])})()]; tr = [[] for _ in c.people]
                for k in range(2 * T):
                    if pl is not None: now[0] = (pl[k // 2][0], pl[k // 2][1], 0.)
                    c.step(.05)
                    if k % 2: [q.append(tuple(p["p"])) for q, p in zip(tr, c.people)]
                tr = [np.array(q) for q in tr]
            if sim.k % 20 == 0 or len(sim.pred) == 0 or sim.clock.t - sim.pred[-1][0] > .45: sim.pred.append((sim.clock.t, [(q[4], q[9], q[19]) for q in tr], [bool(p["distracted"]) for p in cr.people], [float(np.hypot(*(p["p"] - sim.x[:2]))) for p in cr.people]))
            for q in tr:
                d = s.ppl_dist(Pp, Y, q[None, :, 0], q[None, :, 1], .25)
                S += s.w["ppl"] * np.exp(-np.maximum(d, 0.) / s.ppl_len).sum(1) / T; S += s.w["col"] * .5 * (d < 0.).any(1)
            return S, coll, dmin
    c = Fut(vmax=tuple(base.vmax), vmin=tuple(base.vmin)); c.w = dict(base.w); c.people_cap = True; c.ppl_len = base.ppl_len; c.rng = base.rng
    return c

class Sim(fs.Sim):
    def __init__(s, W, config, trial, regime="champ", oracle=False, tmax=300.):
        s.ph = []; s.full = []
        W = dict(W)
        if W["crowd"] and ("dn" in P or "dis" in P):
            W["crowd"] = dict(W["crowd"]); W["crowd"]["n"] += P.get("dn", 0)
            if "dis" in P: W["crowd"]["distracted"] = P["dis"]
        s.cfgname = config
        super().__init__(W, config.split("#")[0], trial, P.get("regime", regime), oracle, tmax)
        s.wob = s.wob * P.get("wob", 1.); s.delay = P.get("cmd", s.delay)
        if s.crowd and "pm" in P:
            import types; s.crowd.step = types.MethodType(lambda c, dt: pm_step(c, dt, P["pm"]), s.crowd)
        if s.crowd and "vscale" in P:
            for p in s.crowd.people: p["v0"] *= P["vscale"]
    def people(s):
        if getattr(s, "_delayed", False) and s.ph:
            t = s.clock.t - P["seen"]; return min(s.ph, key=lambda q: abs(q[0] - t))[1]
        return super().people()
    def sense(s):
        if "seen" in P:
            s.ph.append((s.clock.t, fs.Sim.people(s))); s.ph = s.ph[-12:]; s._delayed = True
        try: super().sense()
        finally: s._delayed = False
    def check(s):
        s.full.append((s.clock.t - s.t0, tuple(s.x), [(q[0], q[1], q[2]) for q in fs.Sim.people(s)]))
        if "body" in P:                                               # tieu chi va cham khac
            f0 = fs.footprint; fs.footprint = lambda x, y, yaw, body=None, n=8: f0(x, y, yaw, P["body"], n)
            try: super().check()
            finally: fs.footprint = f0
        elif "tol" in P:                                              # cham nong < 5 cm bo qua
            r0 = fs.PERSON_R
            ppl = fs.Sim.people; s.people = lambda: [(a, b, r - P["tol"], c, d) for a, b, r, c, d in ppl(s)]
            try: super().check()
            finally: del s.people
        else: super().check()
fs_Sim_people = fs.Sim.people

# --------- bien the bo dieu khien chan doan (hau to #...)
STAT = {}
def patch_ctrl(ctrl, tag, r):
    import types
    if tag in ("fstat", "fplan", "frng", "fcv"): r.sim.pred = []; return future_ctrl(ctrl, tag, r.sim)
    if "lam" in tag:                                                  # lambda tinh tren mau KHONG va cham
        orig = np.median
        def med(S, *a, **k):
            S = np.asarray(S); ok = S < S.min() + 4000.
            return orig(S[ok]) if ok.any() else orig(S)
        st = ctrl.step
        def step(*a, **k):
            np.median = med
            try: return st(*a, **k)
            finally: np.median = orig
        ctrl.step = step
    if "gains" in tag or "sat" in tag or "true" in tag:
        ro = ctrl.rollout
        def rollout(U, x0, v0, gain):
            if "true" in tag:                                         # mo hinh dung tham so that (chan tren)
                g = r.sim.gain; A = np.minimum(1., ctrl.dt / r.sim.tau); vs, bk = r.sim.vsat, r.sim.back
                def f(u):
                    t = g * u; t[:, 0] = np.where(t[:, 0] > 0, vs * np.tanh(t[:, 0] / vs), t[:, 0] * bk); return t
            elif "sat" in tag:                                        # mo hinh SYSID trung binh (hang so)
                g = np.array([.95, .97, .85]); A = np.minimum(1., ctrl.dt / np.array([.15, .15, .25])); vs, bk = .29, 1.22
                def f(u):
                    t = g * u; t[:, 0] = np.where(t[:, 0] > 0, vs * np.tanh(t[:, 0] / vs), t[:, 0] * bk); return t
            else:
                g = r.vel_gains.copy(); A = min(1., ctrl.dt / ctrl.tau)
                def f(u): return g * u
            K, T = U.shape[:2]; x = np.repeat(np.asarray(x0, float)[None], K, 0); v = np.repeat(np.asarray(v0, float)[None], K, 0)
            Pp, Y, V = np.empty((K, T, 2)), np.empty((K, T)), np.empty((K, T, 3))
            for t in range(T):
                v = v + A * (f(U[:, t].copy()) - v); c, s = np.cos(x[:, 2]), np.sin(x[:, 2])
                x[:, 0] += (v[:, 0] * c - v[:, 1] * s) * ctrl.dt; x[:, 1] += (v[:, 0] * s + v[:, 1] * c) * ctrl.dt; x[:, 2] += v[:, 2] * ctrl.dt
                Pp[:, t], Y[:, t], V[:, t] = x[:, :2], x[:, 2], v
            return Pp, Y, V
        ctrl.rollout = rollout
    st0 = ctrl.step
    def stp(*a, **k):                                                 # thong ke ESS / lambda
        cap = {}; om = np.median
        def med(S, *aa, **kk):
            m = om(S, *aa, **kk); cap["r"] = float(m - np.min(S)); return m
        if "lam" not in tag:
            np.median = med
            try: out = st0(*a, **k)
            finally: np.median = om
        else: out = st0(*a, **k)
        if "r" in cap: r.sim.lamlog.append(cap["r"])
        return out
    ctrl.step = stp
    return ctrl

def run(W, cfg, trial):
    name, _, tag = cfg.partition("#")
    mk0 = fs.make_robot
    def mk(sim, config):
        r = mk0(sim, config); sim.lamlog = []
        m0 = r._make_ctrl
        r._make_ctrl = lambda: patch_ctrl(m0(), tag, r)
        run.last = sim
        return r
    fs.make_robot = mk; S0 = fs.Sim; fs.Sim = Sim
    try: row = fs.run_episode(W, name, trial, oracle=tag in ("fstat", "fplan", "frng", "fcv"))
    finally: fs.make_robot = mk0; fs.Sim = S0
    sim = run.last; L = np.array(sim.lamlog or [0.])
    row["extra"] = json.dumps(dict(steps=len(L), lam_sat=int((L > 2500).sum()), vg=round(float(sim.r.vel_gain), 3), vgs=[round(float(v), 3) for v in sim.r.vel_gains],
                                   g=[round(float(v), 3) for v in sim.gain], vsat=round(float(sim.vsat), 3), lam_last=[int(v > 2500) for v in L[-20:]]))
    if getattr(sim, "pred", None):                                  # sai so du doan tuong lai (m) theo 0.5/1/2 s, nguoi < 2 m
        err = {}
        T = {round(q[0], 1): q[2] for q in sim.full}
        for t, tr, dis, dd in sim.pred:
            for h, ix in ((.5, 0), (1., 1), (2., 2)):
                q = T.get(round(t - sim.t0 + h, 1))
                if q is None: continue
                for k in range(len(tr)):
                    if dd[k] < 2.: err.setdefault(f"{h}_{'mdt' if dis[k] else 'ne'}", []).append(round(float(np.hypot(tr[k][ix][0] - q[k][0], tr[k][ix][1] - q[k][1])), 2))
        e = json.loads(row["extra"]); e["pred"] = err; row["extra"] = json.dumps(e)
    row["full"] = sim.full[-80:]
    return row

F = fs.FIELDS + ["cond", "extra"]
def worker(a):
    P.update(COND[a.cond]); jobs = json.load(open(a.worker)); cache = {}
    f = open(a.outf, "a", newline=""); w = csv.DictWriter(f, F, extrasaction="ignore")
    for seed, trial, cfg in jobs:
        if seed not in cache: cache = {seed: fs.gen_world(seed)}
        W = cache[seed]
        try: row = run(W, cfg, trial)
        except Exception as e:
            import traceback; traceback.print_exc(); row = dict(success="", why="EXC " + repr(e)[:80])
        row.update(world=seed, kind=W["kind"], npeople=W["crowd"]["n"], trial=trial, config=cfg, cond=a.cond)
        w.writerow(row); f.flush()
        if row.get("col") == "person":
            with open(a.outf.replace(".csv", ".pkl"), "ab") as g: pickle.dump(dict(seed=seed, trial=trial, cfg=cfg, info=row["info"], full=row["full"]), g)

def main():
    ap = argparse.ArgumentParser(); A = ap.add_argument
    A("--cond", default="base"); A("--lo", type=int, default=150); A("--n", type=int, default=50); A("--trial", type=int, default=0)
    A("--configs", nargs="+"); A("--jobs", type=int, default=3); A("--out"); A("--worker"); A("--outf")
    a = ap.parse_args()
    if a.worker: return worker(a)
    assert a.jobs <= 3
    os.makedirs(a.out, exist_ok=True); seeds, s = [], a.lo
    while len(seeds) < a.n:
        assert s < 1000
        if fs.gen_world(s)["crowd"]: seeds.append(s)
        s += 1
    done = set()
    for fn in os.listdir(a.out):
        if fn.endswith(".csv"): done |= {(int(r["world"]), int(r["trial"]), r["config"]) for r in csv.DictReader(open(a.out + "/" + fn)) if r["success"] != ""}
    ch = [[] for _ in range(a.jobs)]
    for i, sd in enumerate(seeds):
        for c in a.configs:
            if (sd, a.trial, c) not in done: ch[i % a.jobs].append((sd, a.trial, c))
    ps = []
    for i, c in enumerate(ch):
        if not c: continue
        json.dump(c, open(f"{a.out}/job{i}.json", "w")); of = f"{a.out}/w{i}.csv"
        if not os.path.exists(of): csv.DictWriter(open(of, "w", newline=""), F).writeheader()
        ps.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--cond", a.cond, "--worker", f"{a.out}/job{i}.json", "--outf", of], stderr=open(f"{a.out}/err{i}.log", "a")))
    for p in ps: p.wait()
if __name__ == "__main__": main()
