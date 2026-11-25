#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""replay_perception.py (REALPREP, 25/11) - phat lai ban ghi THAT qua lop nhan thuc DONG BANG cua C1/B1.

Chay dung ma da bam sha256 (robot_ros.RosRobotTools._on_cloud -> track_and_filter -> BlobTracker v3 + OccGrid,
voi cac thong so cua robot_real.RealRobotTools: BODY_BOX, R_BASE_LIDAR, base_height 0.32). KHONG sua file dong bang:
chi tao doi tuong RealRobotTools bang object.__new__ (khong ROS), gan thuoc tinh nhu fastsim.make_robot, roi goi
_on_imu / _on_cloud that voi ban tin giai tu .db3 (dyn/bagio.py, chi doc, immutable).

C1 va B1 dung CHUNG nhan thuc (ca hai co ~t3), nen ket qua o day dung cho ca hai.

  python3 deploy/replay_perception.py BAG.db3 --cloud /go2/lidar/merged --odom /go2/odom --imu /go2/imu/data \
          [--odom-scale 1.19] [--tum ~/go2_maps/lab2.tum] --out results/REALPREP/lab2

Tren cho (Orin, Python 3.8, khong ROS) cung chay duoc: de do thoi gian CPU moi lan quet that su (--bench).

Do gi:
  * moi "nhip" = 1 lan cap nhat tracker (moi lan quet thu 2, ~5 Hz, nhu robot that);
  * vet "nguoi" da xac nhan = tracker.movers() (v3: tr['person']);
  * su that DOC LAP (chi khi co --tum, quy dao SLAM LiDAR cua chinh ban ghi): luoi "ben vung" 0.2 m trong khung ban do
    (o bi cham o >= 30 % so lan quet khi robot trong 6 m = vat tinh). Vet xac nhan la NGUOI THAT neu trong khung
    SLAM no di >= 1.0 m va trung vi do ben vung < 0.25; con lai = MA (vat tinh bi coi la nguoi).
  * CPU: perf_counter quanh _on_cloud (ca giai ma PointCloud2, loc than, can bang, tracker, ban do).
"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")

import argparse
import heapq
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dyn"))

import bagio  # noqa: E402

C1 = "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"

_CLOCK = [0.0]
_real_monotonic = time.monotonic


def _fake_monotonic():
    return _CLOCK[0]


class _F(object):
    def __init__(self, name, offset):
        self.name, self.offset = name, offset


class _H(object):
    def __init__(self, frame):
        self.frame_id = frame


class _Cloud(object):
    """Du truong cho robot_ros.cloud_xyz + _on_cloud (fields, point_step, width, height, data, header.frame_id)."""

    def __init__(self, a, frame):
        self.fields = [_F(n, a.dtype.fields[n][1]) for n in a.dtype.names]
        self.point_step = a.dtype.itemsize
        self.width, self.height = len(a), 1
        self.data = a.tobytes()
        self.header = _H(frame)


class _Q(object):
    def __init__(self, q):
        self.x, self.y, self.z, self.w = q


class _Imu(object):
    def __init__(self, q):
        self.orientation = _Q(q)


def _yaw(q):
    x, y, z, w = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def make_robot(controller, center, grid_half=12.0):
    """RealRobotTools KHONG ROS, cung thuoc tinh can cho _on_cloud/_on_imu (giong fastsim.make_robot)."""
    import robot_real
    from nav_local import BlobTracker, OccGrid
    r = object.__new__(robot_real.RealRobotTools)
    cx, cy = center
    r.__dict__.update(
        label="go2", ns="go2", controller=controller, origin=(0.0, 0.0, 0.0), odom=None, rp=(0.0, 0.0),
        base_height=0.32, body=(0.0, 0.0, 0.0, 0.0), body_box=robot_real.BODY_BOX, _lidar_tf=None, _cam_tf=None,
        local_obs=np.empty((0, 2)), local_t=0.0, local_depth=np.empty((0, 2)), depth_t=0.0, _scan_count=0,
        tracker=BlobTracker(), cpu={"lidar_ms": 0.0, "depth_ms": 0.0}, use_depth=False,
        grid=OccGrid(xmin=cx - grid_half, ymin=cy - grid_half, width=2 * grid_half, height=2 * grid_half),
        depth_grid=OccGrid(xmin=cx - grid_half, ymin=cy - grid_half, width=2 * grid_half, height=2 * grid_half,
                           hit=1, miss=1, occ_thresh=3))
    return r


def tum_load(path, bag=None, odom_topic=None, scale=1.0):
    """TUM (t x y z qx qy qz qw). path == 'odom': dung odom CUA BAN GHI lam tu the (chi hop le khi cho dung yen
    hoac doan ngan: odom troi ~1.9 do/phut va thieu ~18 % quang duong)."""
    if not path:
        return None
    if path == "odom":
        rows = [[st, scale * p[0], scale * p[1], p[2]] + list(q) for _, (st, fr, ch, p, q, v, w) in bagio.read(bag, odom_topic)]
        a = np.array(rows, float)
        return a[np.argsort(a[:, 0])]
    a = np.loadtxt(os.path.expanduser(path))
    return a                                        # t x y z qx qy qz qw


def tum_pose(T, t):
    """(x, y, yaw) SLAM tai thoi diem stamp t (lang gieng gan nhat; TUM co 1 tu the / lan quet)."""
    i = int(np.clip(np.searchsorted(T[:, 0], t), 1, len(T) - 1))
    if abs(T[i - 1, 0] - t) < abs(T[i, 0] - t):
        i -= 1
    return float(T[i, 1]), float(T[i, 2]), _yaw(T[i, 4:8]), abs(float(T[i, 0]) - t)


def persistence_map(bag, topic, T, res=0.2, rng=6.0, zlo=-0.1, zhi=1.3, every=1):
    """Luoi ben vung trong khung SLAM: ti le so lan quet o bi cham / so lan quet robot trong `rng` m."""
    hits, seen = {}, {}
    k = 0
    for tb, (st, fr, a) in bagio.read(bag, topic):
        k += 1
        if k % every:
            continue
        x0, y0, yw, dt = tum_pose(T, st)
        if dt > 0.05:
            continue
        p = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)
        p = p[np.isfinite(p).all(1)]
        if fr not in ("base_link", "go2/base_link"):            # L1 tho: utlidar -> base_link (robot_real)
            import robot_real
            p = p @ robot_real.R_BASE_LIDAR.T + robot_real.T_BASE_LIDAR
            (x0b, x1b), (y0b, y1b), (z0b, z1b) = robot_real.BODY_BOX
            p = p[~((p[:, 0] > x0b) & (p[:, 0] < x1b) & (p[:, 1] > y0b) & (p[:, 1] < y1b) & (p[:, 2] > z0b) & (p[:, 2] < z1b))]
        r = np.hypot(p[:, 0], p[:, 1])
        p = p[(r > 0.5) & (r < rng) & (p[:, 2] > zlo) & (p[:, 2] < zhi)]
        c, s = math.cos(yw), math.sin(yw)
        mx, my = x0 + c * p[:, 0] - s * p[:, 1], y0 + s * p[:, 0] + c * p[:, 1]
        cells = set(zip(np.floor(mx / res).astype(int).tolist(), np.floor(my / res).astype(int).tolist()))
        for q in cells:
            hits[q] = hits.get(q, 0) + 1
        n = int(rng / res)
        i0, j0 = int(math.floor(x0 / res)), int(math.floor(y0 / res))
        for i in range(i0 - n, i0 + n + 1):
            for j in range(j0 - n, j0 + n + 1):
                if (i - i0) ** 2 + (j - j0) ** 2 <= n * n:
                    seen[(i, j)] = seen.get((i, j), 0) + 1
    return {q: hits[q] / max(seen.get(q, 1), 1) for q in hits}, res


def pers_at(P, res, x, y):
    i, j = int(math.floor(x / res)), int(math.floor(y / res))
    return max(P.get((i + a, j + b), 0.0) for a in (-1, 0, 1) for b in (-1, 0, 1))


def replay(a):
    T = tum_load(a.tum, a.bag, a.odom, a.odom_scale)
    P = None
    if T is not None:
        t0 = _real_monotonic()
        P, pres = persistence_map(a.bag, a.cloud, T)
        print("persistence map: %d o, %.0f s" % (len(P), _real_monotonic() - t0), flush=True)
    time.monotonic = _fake_monotonic                       # dong ho = gio ban ghi (nhu fastsim: real_time.monotonic)
    import robot_ros                                       # noqa: F401  (sau khi va dong ho)
    streams = [((tb, 0, d) for tb, d in bagio.read(a.bag, a.odom)),
               ((tb, 1, d) for tb, d in bagio.read(a.bag, a.imu)),
               ((tb, 2, d) for tb, d in bagio.read(a.bag, a.cloud))]
    r, seg_t0 = None, None
    last_cloud = -1e9
    ticks, cpu_all, cpu_trk = [], [], []
    tracks = {}                                            # rid -> info
    rid = [0]
    nseg = 0
    pose_slam = None
    for tb, kind, d in heapq.merge(*streams, key=lambda z: (z[0], z[1])):
        _CLOCK[0] = tb
        if kind == 0:
            st, fr, ch, p, q, v, w = d
            od = (a.odom_scale * p[0], a.odom_scale * p[1], _yaw(q), tb)
            if r is None or tb - seg_t0 > a.segment:
                nseg += 1
                r = make_robot(a.controller, od[:2])
                seg_t0 = tb
            r.odom = od
            continue
        if r is None:
            continue
        if kind == 1:
            r._on_imu(_Imu(d[2]))
            continue
        st, fr, arr = d
        if tb - last_cloud < a.min_period - 1e-3:          # bridge --lidar-rate 10
            continue
        last_cloud = tb
        if "x" not in arr.dtype.names:
            continue
        xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1)
        ok = np.isfinite(xyz).all(1) & (np.linalg.norm(np.nan_to_num(xyz), axis=1) >= 0.05)   # bridge --min-radius
        arr = arr[ok]
        if r._lidar_tf is None:
            if fr in ("base_link", "go2/base_link"):
                r._lidar_tf = (np.eye(3), np.zeros(3))      # lidar_merge da o base_link (TF cung ra don vi)
            else:
                import robot_real
                r._lidar_tf = (robot_real.R_BASE_LIDAR, robot_real.T_BASE_LIDAR)
        msg = _Cloud(arr, fr)
        raw = None
        n_before = r._scan_count
        last_trk = r.tracker._last_t
        c0 = time.perf_counter()
        r._on_cloud(msg)
        ms = (time.perf_counter() - c0) * 1000
        cpu_all.append(ms)
        if r.tracker._last_t == last_trk or r._scan_count == n_before:
            continue
        cpu_trk.append(ms)
        x, y, yaw = r.local_pose
        R_, t_ = r._lidar_tf
        raw = r._level(np.stack([arr["x"], arr["y"], arr["z"]], 1).astype(np.float64) @ R_.T + t_)
        if T is not None:
            sx, sy, syaw, sdt = tum_pose(T, st)
            pose_slam = (sx, sy, syaw) if sdt < 0.05 else None
        conf, front = [], []
        for tr in r.tracker.tracks:
            if "_rid" not in tr:
                rid[0] += 1
                tr["_rid"] = rid[0]
                tr["_born"] = tb
            if not tr.get("person"):
                continue
            k = tr["_rid"]
            info = tracks.setdefault(k, dict(rid=k, seg=nseg, born=tr["_born"], t_conf=tb, n=0, pts_map=[],
                                             pers=[], d_robot=[], v=[], ztop=[], bear=[]))
            info["n"] += 1
            info["t_last"] = tb
            px, py = float(tr["p"][0]), float(tr["p"][1])
            dx, dy = px - x, py - y
            c, s = math.cos(-yaw), math.sin(-yaw)
            bx, by = c * dx - s * dy, s * dx + c * dy               # frame than
            info["d_robot"].append(math.hypot(bx, by))
            info["bear"].append(math.degrees(math.atan2(by, bx)))
            m = np.hypot(raw[:, 0] - bx, raw[:, 1] - by) < 0.30
            info["ztop"].append(float(raw[m, 2].max()) + r.base_height if m.any() else float("nan"))
            info["v"].append(float(np.hypot(*tr["v"])))
            if pose_slam is not None:
                sx, sy, syaw = pose_slam
                c2, s2 = math.cos(syaw), math.sin(syaw)
                mx, my = sx + c2 * bx - s2 * by, sy + s2 * bx + c2 * by
                info["pts_map"].append((tb, mx, my))
                info["pers"].append(pers_at(P, pres, mx, my))
            conf.append(k)
            if abs(math.atan2(by, bx)) < math.pi / 2 and math.hypot(bx, by) < 4.0:
                front.append(k)                             # nua truoc, < 4 m: noi bo dieu khien quan tam
        ticks.append((tb, conf, front))
    time.monotonic = _real_monotonic
    # ---- phan loai vet
    for info in tracks.values():
        pm = info.pop("pts_map")
        if pm:
            q = np.array([[u[1], u[2]] for u in pm])
            info["disp_map"] = round(float(np.max(np.hypot(q[:, 0] - q[0, 0], q[:, 1] - q[0, 1]))), 3)
            info["path_map"] = round(float(np.hypot(*np.diff(q, axis=0).T).sum()) if len(q) > 1 else 0.0, 3)
            info["pers_med"] = round(float(np.median(info["pers"])), 3)
            zt = np.array(info["ztop"])
            info["ztop_med"] = round(float(np.nanmedian(zt)), 2) if np.isfinite(zt).any() else None
            tall = info["ztop_med"] is not None and 1.2 <= info["ztop_med"] <= 2.1
            if info["pers_med"] >= 0.30:
                info["cls"] = "ghost"                       # ngoi tren vat tinh (nhu GAZEBO 5.1: < 0.3 m mat vat)
            elif info["disp_map"] >= 1.0 and tall:
                info["cls"] = "real"                        # di >= 1 m trong khung SLAM, cao nhu nguoi, khong tren vat tinh
            else:
                info["cls"] = "unsure"
            info["real"] = info["cls"] == "real"
        else:
            info["disp_map"] = info["path_map"] = info["pers_med"] = info["ztop_med"] = None
            info["real"], info["cls"] = None, None
        info["bear_med"] = round(float(np.median(info["bear"])), 0)
        info.pop("bear")
        info.pop("ztop")
        info.pop("pers")
        info["dur"] = round(info["t_last"] - info["t_conf"], 2)
        info["latency"] = round(info["t_conf"] - info["born"], 2)
        info["d_conf"] = round(info["d_robot"][0], 2)
        info["d_min"] = round(min(info["d_robot"]), 2)
        info["v_med"] = round(float(np.median(info["v"])), 2)
        info.pop("d_robot")
        info.pop("v")
    n = len(ticks)
    any_conf = sum(1 for t in ticks if t[1])
    ghost = sum(1 for t in ticks if any(tracks[k]["cls"] == "ghost" for k in t[1]))
    ghost_ub = sum(1 for t in ticks if any(tracks[k]["cls"] in ("ghost", "unsure") for k in t[1]))
    real_t = sum(1 for t in ticks if any(tracks[k]["real"] for k in t[1]))
    # nhip "tinh": khong co nguoi that nao trong +-3 s
    real_times = sorted(tb for tb, conf, _f in ticks if any(tracks[k]["real"] for k in conf))
    static = [t for t in ticks if not real_times or
              abs(real_times[min(np.searchsorted(real_times, t[0]), len(real_times) - 1)] - t[0]) > 3.0 and
              abs(real_times[max(np.searchsorted(real_times, t[0]) - 1, 0)] - t[0]) > 3.0]
    ghost_static = sum(1 for t in static if t[1])
    fr_any = sum(1 for t in ticks if t[2])
    fr_ghost = sum(1 for t in ticks if any(tracks[k]["cls"] == "ghost" for k in t[2]))
    fr_ub = sum(1 for t in ticks if any(tracks[k]["cls"] in ("ghost", "unsure") for k in t[2]))
    fr_real = sum(1 for t in ticks if any(tracks[k]["cls"] == "real" for k in t[2]))
    dur = (ticks[-1][0] - ticks[0][0]) if n > 1 else 0.0
    gt = [v for v in tracks.values() if v["cls"] == "ghost"]
    ut = [v for v in tracks.values() if v["cls"] == "unsure"]
    rt = [v for v in tracks.values() if v["real"]]
    S = dict(bag=a.bag, cloud=a.cloud, odom=a.odom, odom_scale=a.odom_scale, controller=a.controller,
             segments=nseg, segment_s=a.segment, ticks=n, duration_s=round(dur, 1),
             tick_any_person_pct=round(100.0 * any_conf / max(n, 1), 1),
             tick_ghost_pct=round(100.0 * ghost / max(n, 1), 1) if T is not None else None,
             tick_ghost_or_unsure_pct=round(100.0 * ghost_ub / max(n, 1), 1) if T is not None else None,
             n_unsure=len(ut),
             tick_real_pct=round(100.0 * real_t / max(n, 1), 1) if T is not None else None,
             static_ticks=len(static), tick_any_person_on_static_pct=round(100.0 * ghost_static / max(len(static), 1), 1),
             front4m_any_pct=round(100.0 * fr_any / max(n, 1), 1),
             front4m_ghost_pct=round(100.0 * fr_ghost / max(n, 1), 1) if T is not None else None,
             front4m_ghost_or_unsure_pct=round(100.0 * fr_ub / max(n, 1), 1) if T is not None else None,
             front4m_real_pct=round(100.0 * fr_real / max(n, 1), 1) if T is not None else None,
             n_confirmed=len(tracks), n_ghost=len(gt), n_real=len(rt),
             ghost_per_min=round(60.0 * len(gt) / max(dur, 1e-9), 2) if T is not None else None,
             confirmed_per_min=round(60.0 * len(tracks) / max(dur, 1e-9), 2),
             ghost_dur_med=round(float(np.median([v["dur"] for v in gt])), 2) if gt else None,
             ghost_dur_max=round(float(max([v["dur"] for v in gt])), 2) if gt else None,
             ghost_gt2s=sum(1 for v in gt if v["dur"] > 2.0),
             real_latency_med=round(float(np.median([v["latency"] for v in rt])), 2) if rt else None,
             real_dconf_med=round(float(np.median([v["d_conf"] for v in rt])), 2) if rt else None,
             cpu_scan_ms=dict(mean=round(float(np.mean(cpu_all)), 2), p50=round(float(np.percentile(cpu_all, 50)), 2),
                              p95=round(float(np.percentile(cpu_all, 95)), 2), max=round(float(np.max(cpu_all)), 2),
                              n=len(cpu_all)),
             cpu_tracker_scan_ms=dict(mean=round(float(np.mean(cpu_trk)), 2),
                                      p95=round(float(np.percentile(cpu_trk, 95)), 2), n=len(cpu_trk)) if cpu_trk else None,
             python=sys.version.split()[0], numpy=np.__version__)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(S, f, indent=1)
    with open(os.path.join(a.out, "tracks.json"), "w") as f:
        json.dump(sorted(tracks.values(), key=lambda v: v["rid"]), f, indent=0)
    print(json.dumps(S, indent=1))
    return S


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("bag")
    ap.add_argument("--cloud", default="/go2/lidar/merged")
    ap.add_argument("--odom", default="/go2/odom")
    ap.add_argument("--imu", default="/go2/imu/data")
    ap.add_argument("--odom-scale", type=float, default=1.0, help="1.19 neu odom THO (bridge nhan 1.19 khi trien khai)")
    ap.add_argument("--tum", default=None, help="quy dao SLAM cua chinh ban ghi -> su that doc lap (nguoi that / ma);"
                                               " 'odom' = dung odom (chi khi cho dung yen, vd ban ghi 10 phut trong ngay)")
    ap.add_argument("--controller", default=C1)
    ap.add_argument("--segment", type=float, default=60.0, help="s; ban do + tracker moi (nhu dau moi luot thu)")
    ap.add_argument("--min-period", type=float, default=0.1, help="s giua 2 lan quet (bridge --lidar-rate 10)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    a.bag = os.path.expanduser(a.bag)
    replay(a)


if __name__ == "__main__":
    main()
