#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_real.py — SO SANH BO NE VAT CAN TREN GO2 THAT (cho bai bao).

So: bo ne CO SAN cua Unitree (firmware, ma dong) vs MPPI / DWA / PRISM / ... cua GoVoice,
tren CUNG duong chay, CUNG diem xuat phat, xen ke thu tu (xao ngau nhien moi vong).

    # tren Jetson cua cho, sau khi bat bridge --allow-motion + realsense (xem start_real.sh)
    python3 eval_real.py --course course_real.yaml --controllers unitree_path mppi prism --trials 5

course_real.yaml (dich TUONG DOI so voi tu the xuat phat: x toi, y trai, m):
    - name: so_le_4_thung        # 4 thung xep zic-zac, khe ~0.9 m
      goal: [6.0, 0.0]
    - name: nguoi_cat_ngang      # 1 nguoi di cat ngang o giua duong
      goal: [6.0, 0.0]
      people: true

Moi luot: nguoi van hanh dat cho o VACH XUAT PHAT (cung huong) -> Enter -> cho tu di ->
nguoi van hanh go 'c' neu cho CHAM vat/nguoi, Enter neu khong. Remote trong tay (L2+B).
Ket qua: results/real_<thoi gian>/trials.csv + summary.md (cung chi so voi eval_sim).

CHUA CHAY TREN ROBOT THAT. Lan dau: toc do thap (real.goto_speed 0.25), duong chay thoang.
"""

import os as _os
# Ma tran NHO (MPPI, policy RL): BLAS nhieu luong tranh CPU nhau -> cham 10-25 lan.
# Dat 1 luong TRUOC khi import numpy (do 21/11: forward MLP 37.6 ms -> 1.5 ms).
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import csv
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--course", default=os.path.join(HERE, "course_real.yaml"))
    ap.add_argument("--controllers", nargs="+", default=["unitree_path", "mppi", "prism"])
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    import yaml
    from run_sim import GoVoiceSim, load_config
    from eval_sim import motion_stats
    course = yaml.safe_load(open(a.course, encoding="utf-8"))
    cfg = load_config(os.path.join(HERE, "config.yaml"))
    real = cfg.get("real", {}) or {}
    print("\n  SO SANH TREN CHO THAT. Remote trong tay (L2+B)? Duong chay thoang? Pin >= 50 %?"
          "\n  Go 'co' de tiep tuc: ", end="")
    if input().strip().lower() not in ("co", "yes", "y"):
        sys.exit("Da huy.")
    from robot_tools import RobotTools
    from robot_real import RealRobotTools
    sport = RobotTools(dry_run=False, iface=cfg.get("robot", {}).get("iface", "eth0"))
    gv = GoVoiceSim(cfg, [real.get("ns", "go2")], no_tts=True, section="real",
                    backend=RealRobotTools, backend_kw={"cfg_real": real, "sport": sport})
    r = next(iter(gv.robots.values()))
    out = os.path.join(HERE, "results", f"real_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out, exist_ok=True)
    rng = random.Random(a.seed)
    fields = ["round", "controller", "task", "success", "collision", "err_m", "time_s", "travel_m",
              "stops", "stop_s", "mean_v", "osc", "min_clear_m", "brakes", "note"]
    rows = []
    with open(os.path.join(out, "trials.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for k in range(a.trials):
            for t in course:
                order = list(a.controllers)
                rng.shuffle(order)                         # xen ke thu tu: tranh thien lech
                for c in order:
                    input(f"\n[{k + 1}/{a.trials}] {t['name']} - bo ne: {c}. Dat cho o VACH XUAT "
                          f"PHAT, cung huong{', NGUOI SAN SANG' if t.get('people') else ''} -> Enter ")
                    r.controller, r._ctrl = c, None
                    x0, y0, th0 = r.map_pose()
                    dx, dy = t["goal"]
                    gx = x0 + dx * math.cos(th0) - dy * math.sin(th0)
                    gy = y0 + dx * math.sin(th0) + dy * math.cos(th0)
                    r.last_stats = {}
                    t0 = time.time()
                    traj, times, min_clear = [], [], 9.0
                    gv.executor.enqueue([{"tool": "go_to_pose", "args": {"x": gx, "y": gy, "name": t["name"]}}])
                    time.sleep(0.5)
                    while gv.executor.is_busy() and time.time() - t0 < 180:
                        p = r.map_pose()
                        traj.append(p)
                        times.append(time.time() - t0)
                        try:
                            min_clear = min(min_clear, min(r.free_distance(math.cos(a_), math.sin(a_))
                                                           for a_ in (0, 1.57, 3.14, -1.57)))
                        except Exception:                  # noqa: BLE001
                            pass
                        time.sleep(0.1)
                    gv.executor.stop_all()
                    dt = time.time() - t0
                    x, y, _ = r.map_pose()
                    err = math.hypot(x - gx, y - gy)
                    hit = input("  Cho co CHAM vat/nguoi khong? (c = co, Enter = khong): ").strip().lower() == "c"
                    note = input("  Ghi chu (Enter bo qua): ").strip()
                    row = dict(round=k + 1, controller=c, task=t["name"], success=int(err < 0.35 and not hit),
                               collision=int(hit), err_m=round(err, 3), time_s=round(dt, 1),
                               travel_m=round(r.last_stats.get("travel_m", 0.0), 2),
                               min_clear_m=round(min_clear, 3), brakes=r.last_stats.get("brakes", 0), note=note)
                    row.update(motion_stats(traj, times, (gx, gy)))
                    w.writerow({k_: row.get(k_, "") for k_ in fields})
                    f.flush()
                    rows.append(row)
                    print(f"  -> ok={row['success']} va={row['collision']} lech={row['err_m']} m "
                          f"t={row['time_s']} s khung={row.get('stops')}")
    lines = ["| bo ne | n | thanh cong | va cham | thoi gian TB (s) | khung (lan) | toc do TB |", "|---|---|---|---|---|---|---|"]
    for c in a.controllers:
        g = [x for x in rows if x["controller"] == c]
        if g:
            m = lambda k_: sum(float(x.get(k_) or 0) for x in g) / len(g)
            lines.append(f"| {c} | {len(g)} | {m('success') * 100:.0f} % | {m('collision') * 100:.0f} % | "
                         f"{m('time_s'):.1f} | {m('stops'):.1f} | {m('mean_v'):.2f} |")
    open(os.path.join(out, "summary.md"), "w").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines) + f"\n-> {out}")
    gv.executor.stop_all()


if __name__ == "__main__":
    main()
