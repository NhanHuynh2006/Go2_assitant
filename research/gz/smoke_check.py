#!/usr/bin/env python3
"""GAZEBO: cham kiem khoi PREREG_TEST §4 (S1-S6) tu ket qua eval_sim (trials.csv + episodes.jsonl + log).

  venv/bin/python research/gz/smoke_check.py results/GZ_smoke/office results/GZ_smoke/gz4 [--c1 CFG --b1 CFG]
In bang S1-S6 (markdown) + so lieu chi tiet; D1/D2 tinh bang dung ham cua audit/a9_fault_def.py.
"""
import argparse, csv, glob, json, math, os, re, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "audit"))
from a9_fault_def import D1, D2, closing                                      # noqa: E402
C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
B1 = "mppi~t3~nl:ppl=100;ppl_len=0.5"


def rs(t, X, tg):
    """Noi suy log (t, X) len luoi tg (0.1 s); goc unwrap."""
    X = np.array(X, float)
    out = np.stack([np.interp(tg, t, X[:, j]) for j in range(X.shape[1])], 1)
    return out


def d1d2(ep):
    fc = ep.get("first_contact")
    if not fc:
        return None
    t = np.array(ep["t"], float)
    R = ep["robot"][fc["ns"]]
    ok = [i for i, p in enumerate(R) if p is not None and i <= fc["i"]]
    if len(ok) < 12:
        return dict(err="it hon 12 nhip truoc cham")
    tt = t[ok]
    X = np.array([R[i] for i in ok], float); X[:, 2] = np.unwrap(X[:, 2])
    Q = np.array([ep["people"][i][fc["k"]][:2] for i in ok], float)
    tg = np.arange(tt[-1] - 0.1 * (min(len(ok), 30) - 1), tt[-1] + 1e-9, 0.1)
    Xg, Qg = rs(tt, X, tg), rs(tt, Q, tg)
    rc, pc = closing(Xg, Qg)
    return dict(D1=D1(Xg, Qg), D2=D2(Xg, Qg), robot_close=round(rc, 3), person_close=round(pc, 3),
                dt_log=round(float(np.median(np.diff(tt))), 3), n=len(tg))


def track_life(trk, t):
    """Thoi gian ton tai (s) cua tung track nguoi da xac nhan: tu lan dau toi lan cuoi xuat hien."""
    seen = {}
    for ti, row in zip(t, trk):
        for k, *_ in row:
            a = seen.setdefault(k, [ti, ti])
            a[1] = ti
    return {k: round(b - a, 2) for k, (a, b) in seen.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--c1", default=C1)
    ap.add_argument("--b1", default=B1)
    a = ap.parse_args()
    rows, eps, logs = [], [], []
    for d in a.dirs:
        rr = list(csv.DictReader(open(os.path.join(d, "trials.csv"))))
        for r in rr:
            r["_dir"] = os.path.basename(d.rstrip("/"))
        rows += rr
        E = [json.loads(l) for l in open(os.path.join(d, "episodes.jsonl"))]
        for e in E:
            e["_dir"] = os.path.basename(d.rstrip("/"))
        eps += E
        logs += glob.glob(os.path.join(d, "*.log"))
    key = lambda o: (o["_dir"], str(o["trial"]), o["config"], o["task"])
    epk = {key(e): e for e in eps}
    print(f"{len(rows)} luot, {len(eps)} episode log, log: {logs}")
    res = {}
    # ---- S1
    tb = []
    for lf in logs:
        txt = open(lf, errors="replace").read()
        tb += [(os.path.basename(lf), m) for m in re.findall(r"(Traceback.*|.*Error:.*|.*loi xu ly.*)", txt)]
    cls = {}
    for r in rows:
        cls.setdefault(r["config"], set()).add((r["ctrl_class"], r["trk_mode"], r["resp"]))
    sha = {r["sha_ok"] for r in rows}
    s1 = (not tb and cls.get(a.c1) == {("PRISM3", "v3", "RespModel")} and cls.get(a.b1) == {("MPPI", "v3", "RespModel")}
          and sha == {"1"})
    res["S1"] = (s1, f"traceback/loi: {len(tb)} {tb[:3]}; lop: { {k: sorted(v) for k, v in cls.items()} }; sha_ok: {sorted(sha)}")
    # ---- S2
    det = []
    s2 = True
    for c in (a.c1, a.b1):
        st = np.concatenate([np.array(e["probe"]["go2"]["step_ms"], float) for e in eps if e["config"] == c] or [np.zeros(0)])
        dc = []
        for e in eps:
            if e["config"] != c:
                continue
            g = e["probe"]["go2"]; ct, cc = g["cmd_t"], g["cmd_ctrl"]
            dc += [ct[k] - ct[k - 1] for k in range(1, len(ct)) if cc[k] and cc[k - 1]]
        dc = np.array(dc)
        p50, p95 = np.percentile(dc, 50), np.percentile(dc, 95)
        s95 = np.percentile(st, 95)
        ok = p50 <= 0.11 and p95 <= 0.15 and (c != a.c1 or s95 <= 80)
        s2 &= bool(ok)
        worst = max((float(r["cmd_dt_p95"]) for r in rows if r["config"] == c and r["cmd_dt_p95"]), default=float("nan"))
        det.append(f"{c.split('~')[0]}: cmd_vel p50 {p50:.3f} s p95 {p95:.3f} s (luot xau nhat p95 {worst:.3f}); "
                   f"ctrl.step p50 {np.percentile(st, 50):.1f} p95 {s95:.1f} max {st.max():.0f} ms (n={len(st)})")
    res["S2"] = (s2, "; ".join(det))
    # ---- S3
    rt = [(r["_dir"], r["task"], r["config"], float(r["rtf_med"])) for r in rows if r["rtf_med"]]
    miss = len(rows) - len(rt)
    lo = [x for x in rt if x[3] < 0.9]
    res["S3"] = (not lo and not miss, f"RTF trung vi moi luot: min {min(x[3] for x in rt):.3f}, trung vi {np.median([x[3] for x in rt]):.3f}; "
                 f"< 0.9: {len(lo)} {lo[:4]}; thieu RTF: {miss}; theo thu muc: " +
                 ", ".join(f"{d} {np.median([x[3] for x in rt if x[0] == d]):.3f}" for d in sorted({x[0] for x in rt})))
    # ---- S4
    bad4, info4 = [], []
    for e in eps:
        r = next(x for x in rows if key(x) == key(e))
        life = track_life(e["trk"]["go2"], e["t"])
        npeo = len(e["people"][0]) if e["people"] else 0
        if r["cat"] == "crowd":
            if not life:
                bad4.append(("khong xac nhan nguoi", e["task"], e["config"], e["trial"]))
            info4.append(len(life))
        else:
            long = {k: v for k, v in life.items() if v > 2.0}
            if long:
                bad4.append(("nguoi ma > 2 s", e["task"], e["config"], e["trial"], long))
    res["S4"] = (not bad4, f"bai co nguoi: so track xac nhan/luot TB {np.mean(info4) if info4 else 0:.1f} (min {min(info4) if info4 else 0}); vi pham: {bad4[:6]}")
    # ---- S5 (chi suite office: 8 bai x 2 lan = 16 cap)
    off = [r for r in rows if r["task"].startswith(("clutter:", "crowd:")) and not r["task"].startswith("gz:")]
    c1s = [r for r in off if r["config"] == a.c1 and r["cat"] == "clutter"]
    tot = {c: sum(int(r["success"]) for r in off if r["config"] == c) for c in (a.c1, a.b1)}
    s5 = sum(int(r["success"]) for r in c1s) >= 7 and len(c1s) == 10 and tot[a.c1] >= tot[a.b1] - 4
    gz = {c: (sum(int(r["success"]) for r in rows if r["config"] == c and r["task"].startswith("gz:")),
              sum(1 for r in rows if r["config"] == c and r["task"].startswith("gz:"))) for c in (a.c1, a.b1)}
    res["S5"] = (s5, f"C1 bai tinh {sum(int(r['success']) for r in c1s)}/{len(c1s)}; tong office C1 {tot[a.c1]} vs B1 {tot[a.b1]} "
                 f"(/{sum(1 for r in off if r['config'] == a.c1)}); file 4 o: C1 {gz[a.c1][0]}/{gz[a.c1][1]}, B1 {gz[a.b1][0]}/{gz[a.b1][1]}")
    # ---- S6
    bad6, dd = [], []
    for r in rows:
        e = epk.get(key(r))
        if e is None:
            bad6.append(("thieu episode", r["task"], r["config"]))
            continue
        nt = len(e["t"])
        if any(len(e[k]) != nt for k in ("people",)) or len(e["robot"]["go2"]) != nt:
            bad6.append(("log lech do dai", r["task"]))
        if r["cat"] == "crowd":
            n_exp = len(e["people"][0]) if nt else 0
            if n_exp == 0:
                bad6.append(("khong co nguoi trong log", r["task"]))
        dtl = np.diff(e["t"]) if nt > 1 else [0]
        gap = r.get("min_person_gap_m")
        if gap not in (None, "") and float(gap) < 0:
            x = d1d2(e)
            if x is None or "err" in (x or {}):
                bad6.append(("khong tinh duoc D1/D2", r["task"], r["config"], x))
            else:
                dd.append((r["task"], r["config"].split("~")[0], r["trial"], e["first_contact"]["t"], x))
        if np.median(dtl) > 0.13:
            bad6.append(("nhip log cham", r["task"], float(np.median(dtl))))
    ncon = sum(1 for r in rows if r.get("min_person_gap_m") not in (None, "") and float(r["min_person_gap_m"]) < 0)
    res["S6"] = (not bad6 and len(eps) == len(rows),
                 f"{len(eps)}/{len(rows)} luot co log; cham nguoi {ncon}, tinh D1/D2 duoc {len(dd)}; nhip log trung vi "
                 f"{np.median(np.concatenate([np.diff(e['t']) for e in eps if len(e['t']) > 1])):.3f} s; loi: {bad6[:4]}")
    print("\n| | dat? | so lieu |\n|---|---|---|")
    for k in sorted(res):
        print(f"| {k} | {'DAT' if res[k][0] else 'TRUOT'} | {res[k][1]} |")
    print("\nD1/D2 tung lan cham:")
    for x in dd:
        print("  ", x)
    print("\nTung luot:")
    for r in rows:
        print(f"  {r['_dir']:8} {r['trial']} {r['config'].split('~')[0]:4} {r['task']:26} ok={r['success']} col={r['collision']} "
              f"gap={r.get('min_person_gap_m', '')} t={r['time_s']} step95={r['step_ms_p95']} cmd95={r['cmd_dt_p95']} rtf={r['rtf_med']}")
    print("\nTONG:", "DAT" if all(v[0] for v in res.values()) else "TRUOT")


if __name__ == "__main__":
    main()
