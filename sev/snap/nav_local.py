#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nav_local.py — NE VAT CAN cho go_to: ban do tu LiDAR + A* + bam duong pure pursuit.

Khong dung ban do co san: robot tu ve ban do chuong ngai tu LiDAR khi di, va lap
ke hoach voi GIA THIET KHONG GIAN TRONG cho phan chua thay (free-space assumption,
Koenig & Likhachev, D* Lite, 2002/2005) — gap vat moi thi ve len ban do va lap lai.

  OccGrid      luoi chiem cho 2D (0.1 m), cap nhat bang tia LiDAR: diem cham +3,
               o tren duong tia -1 (xoa duoc vat da di chuyen, vd robot khac).
  plan()       A* 8 huong tren chi phi = vung cam (ban kinh robot) + vung mem
               (cang gan vat cang dat) — kieu costmap inflation cua Nav2.
  shortcut()   rut gon duong bang kiem tra tam nhin (line-of-sight), tranh zig-zag.
  lookahead()  diem dich pure pursuit (Coulter, CMU-RI-TR-92-01, 1992).

Thuan numpy + scipy, khong phu thuoc ROS -> test duoc offline (xem __main__).
"""

import heapq
import math
import threading

import numpy as np
from scipy.ndimage import distance_transform_edt

SQ2 = math.sqrt(2.0)


class OccGrid:
    def __init__(self, res=0.1, xmin=-12.0, ymin=-12.0, width=24.0, height=24.0,
                 hit=2, miss=1, occ_thresh=4, ev_max=12, ev_min=-6):
        self.res, self.x0, self.y0 = res, xmin, ymin
        self.nx, self.ny = int(round(width / res)), int(round(height / res))
        self.ev = np.zeros((self.ny, self.nx), np.int16)        # bang chung chiem cho
        self.seen_t = np.full((self.ny, self.nx), -1e9, np.float64)   # lan cuoi cam bien thay o nay
        self.hit, self.miss, self.thresh = hit, miss, occ_thresh
        self.ev_max, self.ev_min = ev_max, ev_min
        self.lock = threading.Lock()

    # ---- toa do ----
    def cell(self, x, y):
        return (np.floor((np.asarray(y) - self.y0) / self.res).astype(int),
                np.floor((np.asarray(x) - self.x0) / self.res).astype(int))

    def center(self, r, c):
        return self.x0 + (c + 0.5) * self.res, self.y0 + (r + 0.5) * self.res

    def inside(self, r, c):
        return (r >= 0) & (r < self.ny) & (c >= 0) & (c < self.nx)

    # ---- cap nhat tu 1 lan quet ----
    def integrate(self, ox, oy, pts, max_range=5.0, bins=360, clear_range=4.0, fov=None,
                  free_pts=None):
        """ox, oy: vi tri cam bien (map). pts: (N, 2) diem VAT CAN trong frame map
        (da loc theo do cao). Tia khong cham gi duoc xoa toi clear_range.
        fov=(huong_giua, nua_goc) rad trong map: cam bien hep (camera depth) chi
        duoc XOA trong vung no nhin thay — ngoai vung do no khong biet gi.
        free_pts: (M, 2) diem KHONG phai vat (mat dat, tran) — bang chung "trong toi
        day". Neu dua vao, huong KHONG co diem nao thi KHONG xoa: LiDAR im lang o
        huong do co the vi vat da vao duoi tam toi thieu (0.5 m), khong phai vi trong.
        (Da gap: tuong bi xoa khoi ban do dung luc robot sat tuong nhat.)"""
        if pts is None:
            pts = np.empty((0, 2))
        d = pts - [ox, oy]
        rng = np.hypot(d[:, 0], d[:, 1])
        keep = rng < max_range
        d, rng, pts = d[keep], rng[keep], pts[keep]
        ang = np.arctan2(d[:, 1], d[:, 0])
        b = ((ang + math.pi) / (2 * math.pi) * bins).astype(int) % bins
        r_bin = np.full(bins, clear_range)
        np.minimum.at(r_bin, b, rng)                            # vat gan nhat moi huong
        if free_pts is not None:
            has_obs = np.zeros(bins, bool)
            has_obs[b] = True
            fd = free_pts - [ox, oy]
            frng = np.minimum(np.hypot(fd[:, 0], fd[:, 1]), clear_range)
            fb = ((np.arctan2(fd[:, 1], fd[:, 0]) + math.pi) / (2 * math.pi) * bins
                  ).astype(int) % bins
            r_free = np.zeros(bins)
            np.maximum.at(r_free, fb, frng)
            # co vat: xoa toi vat. Khong vat: chi xoa toi diem "trong" xa nhat thay duoc.
            r_bin = np.where(has_obs, r_bin, r_free)
        # xoa: cac o tren tia, truoc vat (hoac toi clear_range)
        steps = np.arange(0.25, max(clear_range, max_range), self.res * 0.8)
        th = -math.pi + (np.arange(bins) + 0.5) * 2 * math.pi / bins
        S, T = np.meshgrid(steps, th)                           # (bins, steps)
        free = S < (r_bin[:, None] - self.res * 1.5)
        if fov is not None:
            seen = np.abs(np.arctan2(np.sin(th - fov[0]), np.cos(th - fov[0]))) <= fov[1]
            free &= seen[:, None]
        fx = ox + S[free] * np.cos(T[free])
        fy = oy + S[free] * np.sin(T[free])
        fr, fc = self.cell(fx, fy)
        ok = self.inside(fr, fc)
        hr, hc = self.cell(pts[:, 0], pts[:, 1])
        hok = self.inside(hr, hc)
        # tia ben canh van di qua o vua cham -> khong duoc xoa chinh o do
        hit_ids = np.unique(hr[hok] * self.nx + hc[hok])
        keep = ~np.isin(fr * self.nx + fc, hit_ids)
        ok &= keep
        # moi o tinh 1 lan / lan quet: 1 quet = 1 bang chung, du co 50 diem roi vao
        # cung o. Vay o chi thanh "chiem" sau >= 2 lan quet (occ_thresh / hit).
        free_ids = np.unique(fr[ok] * self.nx + fc[ok])
        import time as _t
        now = _t.monotonic()
        with self.lock:
            fl = self.ev.reshape(-1)
            fl[free_ids] -= self.miss
            fl[hit_ids] += self.hit
            np.clip(self.ev, self.ev_min, self.ev_max, out=self.ev)
            st = self.seen_t.reshape(-1)
            st[free_ids] = now
            st[hit_ids] = now

    def decay(self, period=1.0, amount=1):
        """Quen dan theo thoi gian: moi `period` giay, o 'chiem' bot `amount` bang chung.
        Vat tinh duoc thay lai lien tuc nen van con; VET cua vat dong (nguoi di qua) mo
        trong vai giay — ke ca khi bi che (nguoi dung giua robot va cho cu cua no).
        Goi duoc tu nhieu robot: chi tru khi da du `period` ke tu lan truoc."""
        import time as _t
        now = _t.monotonic()
        if now - getattr(self, "_last_decay", 0.0) < period:
            return
        self._last_decay = now
        with self.lock:
            m = self.ev > 0
            self.ev[m] -= amount

    def forget(self, x, y, radius=2.5):
        """Quen ban do quanh (x, y): phuc hoi khi bi 'nhot' boi vat ma (Nav2 clear costmap)."""
        r0, c0 = self.cell(x, y)
        n = int(radius / self.res)
        with self.lock:
            win = self.ev[max(r0 - n, 0):r0 + n + 1, max(c0 - n, 0):c0 + n + 1]
            win[win > 0] = 0

    def occupied(self):
        with self.lock:
            return self.ev >= self.thresh

    def mark_box(self, cx, cy, sx, sy, yaw=0.0, value=None):
        """Ve 1 hop chu nhat (dung cho ban do 'su that' khi danh gia, hoac test)."""
        value = self.ev_max if value is None else value
        rr, cc = np.mgrid[0:self.ny, 0:self.nx]
        x, y = self.center(rr, cc)
        c, s = math.cos(-yaw), math.sin(-yaw)
        lx, ly = c * (x - cx) - s * (y - cy), s * (x - cx) + c * (y - cy)
        m = (np.abs(lx) <= sx / 2) & (np.abs(ly) <= sy / 2)
        with self.lock:
            self.ev[m] = value


def cost_map(occ, res, lethal=0.30, soft=0.65, soft_weight=6.0, discs=()):
    """occ: bool grid. discs: [(r, c, radius_m)] vat tam thoi (robot khac).
    -> (cost float32, inf = cam), khoang cach toi vat (m)."""
    occ = occ.copy()
    if discs:
        rr, cc = np.ogrid[0:occ.shape[0], 0:occ.shape[1]]
        for r0, c0, rad in discs:
            occ |= (rr - r0) ** 2 + (cc - c0) ** 2 <= (rad / res) ** 2
    if occ.any():
        dist = distance_transform_edt(~occ) * res
    else:
        dist = np.full(occ.shape, 1e3, np.float32)
    cost = 1.0 + soft_weight * np.clip((soft - dist) / max(soft - lethal, 1e-3), 0, 1) ** 2
    cost = cost.astype(np.float32)
    cost[dist < lethal] = np.inf
    return cost, dist


def _nearest_free(cost, r, c, max_cells):
    if np.isfinite(cost[r, c]):
        return r, c
    best = None
    for rad in range(1, max_cells + 1):
        r0, r1 = max(r - rad, 0), min(r + rad + 1, cost.shape[0])
        c0, c1 = max(c - rad, 0), min(c + rad + 1, cost.shape[1])
        win = cost[r0:r1, c0:c1]
        ok = np.argwhere(np.isfinite(win))
        if len(ok):
            d = (ok[:, 0] + r0 - r) ** 2 + (ok[:, 1] + c0 - c) ** 2
            k = int(np.argmin(d))
            best = (int(ok[k, 0] + r0), int(ok[k, 1] + c0))
            break
    return best


def astar(cost, start, goal, pad=40):
    """A* 8 huong trong cua so bao quanh start/goal. -> list (r, c) hoac None."""
    (sr, sc), (gr, gc) = start, goal
    r0 = max(min(sr, gr) - pad, 0)
    r1 = min(max(sr, gr) + pad + 1, cost.shape[0])
    c0 = max(min(sc, gc) - pad, 0)
    c1 = min(max(sc, gc) + pad + 1, cost.shape[1])
    win = cost[r0:r1, c0:c1]
    H, W = win.shape
    s, g = (sr - r0, sc - c0), (gr - r0, gc - c0)
    gbest = np.full((H, W), np.inf)
    parent = -np.ones((H, W), np.int64)
    gbest[s] = 0.0
    nbr = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
           (-1, -1, SQ2), (-1, 1, SQ2), (1, -1, SQ2), (1, 1, SQ2)]

    def h(r, c):
        dr, dc = abs(r - g[0]), abs(c - g[1])
        return (dr + dc) + (SQ2 - 2) * min(dr, dc)          # octile

    openq = [(h(*s), 0.0, s[0], s[1])]
    while openq:
        f, gc_, r, c = heapq.heappop(openq)
        if (r, c) == g:
            path = []
            k = r * W + c
            while k >= 0:
                rr, cc = divmod(int(k), W)
                path.append((rr + r0, cc + c0))
                k = parent[rr, cc]
            return path[::-1]
        if gc_ > gbest[r, c]:
            continue
        for dr, dc, step in nbr:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < H and 0 <= nc < W):
                continue
            w = win[nr, nc]
            if not np.isfinite(w):
                continue
            if dr and dc and not (np.isfinite(win[r, nc]) and np.isfinite(win[nr, c])):
                continue                                       # khong cat goc vat
            ng = gc_ + step * 0.5 * (w + win[r, c])
            if ng < gbest[nr, nc]:
                gbest[nr, nc] = ng
                parent[nr, nc] = r * W + c
                heapq.heappush(openq, (ng + h(nr, nc), ng, nr, nc))
    return None


def _line_ok(cost, a, b, max_cost):
    (r0, c0), (r1, c1) = a, b
    n = int(max(abs(r1 - r0), abs(c1 - c0))) + 1
    rr = np.round(np.linspace(r0, r1, n)).astype(int)
    cc = np.round(np.linspace(c0, c1, n)).astype(int)
    v = cost[rr, cc]
    return bool(np.all(np.isfinite(v)) and np.all(v <= max_cost))


def shortcut(cost, path, max_cost=2.5):
    """Bo bot diem: noi thang 2 diem neu doan noi khong qua vung cam/vung qua gan vat."""
    if not path or len(path) < 3:
        return path
    out, i = [path[0]], 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and not _line_ok(cost, path[i], path[j], max_cost):
            j -= 1
        out.append(path[j])
        i = j
    return out


def line_cost(grid, line, weight=2.0, reach=1.0):
    """Chi phi them cho o cach doan thang `line` (ax, ay, bx, by): duong vong se BAM
    duong cu va quay ve no ngay khi qua vat (lenh 'di thang 3 met' gap vat)."""
    ax, ay, bx, by = line
    rr, cc = np.mgrid[0:grid.ny, 0:grid.nx]
    x, y = grid.center(rr, cc)
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy or 1e-9
    t = np.clip(((x - ax) * vx + (y - ay) * vy) / L2, 0.0, 1.0)
    d = np.hypot(ax + t * vx - x, ay + t * vy - y)
    return (weight * np.minimum(d, reach) / reach).astype(np.float32)


def smooth(path, cost, iters=2, max_cost=2.5):
    """Lam muot duong gap khuc (Chaikin): cat goc 1/4-3/4, chi giu neu doan moi khong
    di qua vung cam / vung qua gan vat -> quy dao cong, robot di em hon."""
    pts = [tuple(p) for p in path]
    for _ in range(iters):
        if len(pts) < 3:
            break
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            q = (0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1])
            r = (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])
            out += [q, r]
        out.append(pts[-1])
        pts = out
    return pts


def plan(grid, start_xy, goal_xy, discs=(), lethal=0.30, soft=0.65, layers=(), line=None,
         line_weight=2.0, smooth_path=True):
    """layers: cac OccGrid khac cung kich thuoc (vd lop camera depth), gop bang OR.
    line: (ax, ay, bx, by) — uu tien di sat doan thang nay (ne vat roi ve duong cu).
    -> (list diem (x, y) trong map | None, ly do)."""
    occ = grid.occupied()
    for lay in layers:
        occ = occ | lay.occupied()
    cost, _ = cost_map(occ, grid.res, lethal=lethal, soft=soft, discs=discs)
    if line is not None:
        cost = cost + line_cost(grid, line, line_weight)
    s = tuple(int(v) for v in grid.cell(*start_xy))
    g = tuple(int(v) for v in grid.cell(*goal_xy))
    if not (grid.inside(*s) and grid.inside(*g)):
        return None, "ngoai ban do"
    # robot dang sat vat (vd vua dung lai truoc vat): cho phep thoat ra khoi vung cam
    if not np.isfinite(cost[s]):
        rr, cc = np.ogrid[0:cost.shape[0], 0:cost.shape[1]]
        near = (rr - s[0]) ** 2 + (cc - s[1]) ** 2 <= (lethal / grid.res + 1) ** 2
        cost = cost.copy()
        cost[near & ~np.isfinite(cost)] = 20.0
    g2 = _nearest_free(cost, *g, max_cells=int(0.6 / grid.res))
    if g2 is None:
        return None, "dich nam trong vat can"
    cells = astar(cost, s, g2)
    if cells is None:
        cells = astar(cost, s, g2, pad=max(cost.shape))
    if cells is None:
        return None, "khong co duong"
    # line: rut gon chi khi doan noi khong lech xa duong cu (chi phi <= 1 + nua trong so)
    cells = shortcut(cost, cells, max_cost=2.5 if line is None else 1.0 + 0.5 * line_weight)
    pts = [grid.center(r, c) for r, c in cells]
    pts[-1] = goal_xy if g2 == g else pts[-1]
    if smooth_path and len(pts) > 2:
        sm = smooth(pts, cost)
        ok = all(_line_ok(cost, tuple(int(v) for v in grid.cell(*a)),
                          tuple(int(v) for v in grid.cell(*b)), np.inf)
                 for a, b in zip(sm, sm[1:]))
        if ok:
            pts = sm
    return pts, "ok"


def path_length(pts):
    return float(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])))


def lookahead(path, x, y, dist=0.5):
    """Diem tren duong cach robot ~dist (pure pursuit); bo cac doan da qua."""
    if not path:
        return None, 0
    # doan gan robot nhat
    best, k_best = 1e9, 0
    for k in range(len(path) - 1):
        (ax, ay), (bx, by) = path[k], path[k + 1]
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy or 1e-9
        t = max(0.0, min(1.0, ((x - ax) * vx + (y - ay) * vy) / L2))
        d = math.hypot(ax + t * vx - x, ay + t * vy - y)
        if d < best:
            best, k_best = d, k
    # di doc duong tu doan do toi khi du dist
    for k in range(k_best, len(path) - 1):
        bx, by = path[k + 1]
        if math.hypot(bx - x, by - y) >= dist:
            return (bx, by), k
    return path[-1], len(path) - 2


class BlobTracker:
    """THEO DOI VAT DONG tu diem LiDAR (khong can hoc may, ~1 ms):
      1. ve diem vat can trong ban kinh 4 m len luoi 0.1 m, gom cum bang lien thong
         (scipy.ndimage.label); bo cum lon hon 0.9 m (tuong, do dac dai) va qua nho
      2. tam cum -> ghep voi track cu gan nhat (< 0.6 m), van toc loc EMA
      3. track co toc do > 0.2 m/s la VAT DONG (nguoi, robot khac)
    Dung cho: du doan diem gap gan nhat (CPA) de nhuong duong / lui lai, va de lap duong
    tranh cho nguoi SAP di toi (kieu 'social layer' trong costmap)."""

    def __init__(self, res=0.1, reach=4.0, max_size=0.9, gate=0.6, alpha=0.5):
        self.res, self.reach, self.max_size, self.gate, self.alpha = res, reach, max_size, gate, alpha
        self.tracks = []            # dict(p=np(2), v=np(2), t=time, hits=int)
        self._last_t = None

    def update(self, pts_world, robot_xy, t, grid=None):
        from scipy.ndimage import label
        if self.mode == "v3":
            return self._update_v3(pts_world, robot_xy, t, grid)
        if pts_world is None or not len(pts_world):
            self._age(t)
            return self.tracks
        d = pts_world - np.asarray(robot_xy)
        near = pts_world[np.hypot(d[:, 0], d[:, 1]) < self.reach]
        if not len(near):
            self._age(t)
            return self.tracks
        o = np.floor((near - np.asarray(robot_xy) + self.reach) / self.res).astype(int)
        n = int(2 * self.reach / self.res) + 1
        o = np.clip(o, 0, n - 1)
        img = np.zeros((n, n), bool)
        img[o[:, 1], o[:, 0]] = True
        lab, k = label(img, structure=np.ones((3, 3)))
        cents = []
        for i in range(1, k + 1):
            ys, xs = np.nonzero(lab == i)
            if len(xs) < 2:
                continue
            ext = max(xs.max() - xs.min(), ys.max() - ys.min()) * self.res
            if ext > self.max_size:
                continue
            cx = (xs.mean() + 0.5) * self.res - self.reach + robot_xy[0]
            cy = (ys.mean() + 0.5) * self.res - self.reach + robot_xy[1]
            cents.append(np.array([cx, cy]))
        dt = (t - self._last_t) if self._last_t else 0.1
        self._last_t = t
        used, new = set(), []
        for tr in self.tracks:
            pred = tr["p"] + tr["v"] * dt
            best, bj = self.gate, None
            for j, c in enumerate(cents):
                dd = float(np.linalg.norm(c - pred))
                if j not in used and dd < best:
                    best, bj = dd, j
            if bj is None:
                if t - tr["t"] < 0.5:
                    new.append(tr)                      # giu them 0.5 s (bi che tam thoi)
                continue
            used.add(bj)
            c = cents[bj]
            v = (c - tr["p"]) / max(dt, 1e-3)
            tr["v"] = self.alpha * v + (1 - self.alpha) * tr["v"]
            tr["p"], tr["t"], tr["hits"] = c, t, tr["hits"] + 1
            tr["dyn"] = min(5.0, tr.get("dyn", 0.0) + 1.0) if self._was_free(grid, c) \
                else max(0.0, tr.get("dyn", 0.0) - 0.34)
            new.append(tr)
        for j, c in enumerate(cents):
            if j not in used:
                new.append(dict(p=c, v=np.zeros(2), t=t, hits=1, p0=c.copy(),
                                dyn=1.0 if self._was_free(grid, c) else 0.0))
        self.tracks = new
        return self.tracks

    def _age(self, t):
        self.tracks = [tr for tr in self.tracks if t - tr["t"] < 0.5]

    mode = "v1"

    @staticmethod
    def _was_free(grid, c):
        """Tam cum nam o o ma ban do (TRUOC lan quet nay) da biet chac la TRONG -> co vat vua di vao."""
        if grid is None:
            return False
        r, k = grid.cell(c[0], c[1])
        return bool(grid.inside(r, k) and grid.ev[int(r), int(k)] <= -2)

    # ------------------------------------------------------------------ v3 (ALGO 22/11)
    reach3, sig_a, sig_m, coast, rest_s = 5.5, 2.0, 0.06, 1.5, 20.0

    def _update_v3(self, pts, robot_xy, t, grid):
        """Nhu v2 nhung (moi muc do tu mot loi quan sat tren DEV):
          - tam 5.5 m (v2: 4 m); tru nen: bo diem nam trong o ban do da CHAC la vat tinh -> nguoi
            di sat ban/tuong khong bi dinh cum voi vat
          - bang chung dong theo TUNG DIEM (ty le diem roi vao o da biet trong), khong theo tam cum
          - loc Kalman van toc khong doi (v2: EMA 0.5, van toc nhieu +-0.3 m/s va tre)
          - bu tam cum lech ve phia robot (LiDAR chi thay mat truoc): day ra 0.64 x ban kinh cum
          - xac nhan sau 2 lan quet (v2: 3); NGUOI DUNG LAI van la nguoi (v2: bien thanh vat tinh,
            den khi di tiep moi thay -> ~6/16 lan cham); giu khi bi che / vao vung mu LiDAR."""
        from scipy.ndimage import label
        rx, ry = float(robot_xy[0]), float(robot_xy[1])
        dt = float(np.clip((t - self._last_t) if self._last_t else 0.2, 0.02, 1.0))
        self._last_t = t
        pts = np.empty((0, 2)) if pts is None else pts
        rng = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        ang = np.arctan2(pts[:, 1] - ry, pts[:, 0] - rx)
        near = pts[rng < self.reach3]
        fresh = np.zeros(len(near), bool)
        if grid is not None and len(near):
            r, c = grid.cell(near[:, 0], near[:, 1])
            ok = grid.inside(r, c)
            ev = np.zeros(len(near), int)
            ev[ok] = grid.ev[r[ok], c[ok]]
            fresh = ev <= -2
            st = (ev >= 8)
            for q in self.tracks:                                  # quanh nguoi da biet: khong coi la nen
                if q.get("person"):
                    st &= np.hypot(near[:, 0] - q["p"][0], near[:, 1] - q["p"][1]) > 0.45
            near, fresh = near[~st], fresh[~st]
        cl = []
        if len(near):
            o = np.floor((near - [rx, ry] + self.reach3) / self.res).astype(int)
            n = int(2 * self.reach3 / self.res) + 1
            o = np.clip(o, 0, n - 1)
            img = np.zeros((n, n), bool)
            img[o[:, 1], o[:, 0]] = True
            lab, k = label(img, structure=np.ones((3, 3)))
            lb = lab[o[:, 1], o[:, 0]]
            for i in range(1, k + 1):
                m = lb == i
                if m.sum() < 2:
                    continue
                q = near[m]
                ext = float(max(np.ptp(q[:, 0]), np.ptp(q[:, 1])))
                if ext > self.max_size:
                    continue
                cc = q.mean(0)
                u = cc - [rx, ry]
                u = u / (np.linalg.norm(u) + 1e-9)
                w = float(np.ptp(q @ np.array([-u[1], u[0]])))      # be rong nhin thay
                cl.append((cc + u * 0.64 * min(max(w / 2, 0.10), 0.28), float(fresh[m].mean()), ext))
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        g = np.array([dt * dt / 2, dt])
        Q = np.kron(np.outer(g, g), np.eye(2)) * self.sig_a ** 2
        for tr in self.tracks:
            tr["x"] = F @ tr["x"]
            tr["P"] = F @ tr["P"] @ F.T + Q
        cand = sorted((float(np.hypot(*(c[0] - tr["x"][:2]))), i, j)
                      for i, tr in enumerate(self.tracks) for j, c in enumerate(cl))
        ui, uj = set(), set()
        H = np.eye(2, 4)
        for dd, i, j in cand:
            if dd > self.gate or i in ui or j in uj:
                continue
            tr, (c, fr, ext) = self.tracks[i], cl[j]
            if dd > 0.35 and ext > 0.6 and tr.get("person"):
                continue
            ui.add(i)
            uj.add(j)
            K = tr["P"] @ H.T @ np.linalg.inv(H @ tr["P"] @ H.T + np.eye(2) * self.sig_m ** 2)
            tr["x"] = tr["x"] + K @ (c - tr["x"][:2])
            tr["P"] = (np.eye(4) - K @ H) @ tr["P"]
            tr["hits"] += 1
            tr["seen"] = t
            tr["dyn"] = min(5.0, tr["dyn"] + 1.0) if fr > 0.5 else max(0.0, tr["dyn"] - 0.34)
            sp = float(np.hypot(*tr["x"][2:]))
            if sp > 0.25:
                tr["moved"] = t
            if not tr.get("person") and tr["hits"] >= 2 and tr["dyn"] >= 2.0 and sp > 0.2 \
                    and np.hypot(*(c - tr["p0"])) > 0.10:
                tr["person"], tr["moved"] = True, t
        keep = []
        for i, tr in enumerate(self.tracks):
            if i not in ui:
                p = tr["x"][:2]
                d = float(np.hypot(p[0] - rx, p[1] - ry))
                lost = t - tr["seen"]
                if not tr.get("person"):
                    if lost > 0.45:
                        continue
                else:
                    b = math.atan2(p[1] - ry, p[0] - rx)
                    occl = bool(((np.abs(np.angle(np.exp(1j * (ang - b)))) < 0.05) & (rng < d - 0.3)).any())
                    if lost > (self.coast if (occl or d < 0.85) else 0.45):
                        continue
                    if lost > 0.5:
                        tr["x"][2:] *= 0.8
            if tr.get("person") and t - tr.get("moved", t) > self.rest_s:
                tr["person"] = False
            keep.append(tr)
        for j, (c, fr, ext) in enumerate(cl):
            if j not in uj:
                keep.append(dict(x=np.array([c[0], c[1], 0.0, 0.0]), P=np.diag([0.005, 0.005, 1.0, 1.0]), hits=1,
                                 p0=c.copy(), seen=t, dyn=1.0 if fr > 0.5 else 0.0))
        for tr in keep:
            tr["p"], tr["v"], tr["t"] = tr["x"][:2].copy(), tr["x"][2:].copy(), t
        self.tracks = keep
        return self.tracks

    def movers(self, min_speed=0.2, min_hits=3, min_travel=0.5):
        if self.mode == "v3":
            return [tr for tr in self.tracks if tr.get("person")]
        if self.mode == "v2":
            # vat tinh khong bao gio nam o o da biet trong -> het 'nguoi ma'; nguoi that duoc
            # xac nhan sau ~0.6 s (3 lan quet) thay vi phai di 0.5 m
            return [tr for tr in self.tracks if tr["hits"] >= 3 and tr.get("dyn", 0.0) >= 2.0
                    and np.linalg.norm(tr["v"]) > 0.15]
        return self._movers_v1(min_speed, min_hits, min_travel)

    def _movers_v1(self, min_speed=0.2, min_hits=3, min_travel=0.5):
        """Vat DONG that: du nhanh VA da di duoc >= min_travel m tu luc thay lan dau.
        (Hop dung yen: khi robot di vong quanh, mat nhin thay doi lam tam cum 'nhay'
        0.2-0.4 m -> truoc day bi coi la nguoi, robot cu nhuong/khung.)"""
        return [tr for tr in self.tracks
                if tr["hits"] >= min_hits and np.linalg.norm(tr["v"]) > min_speed
                and np.linalg.norm(tr["p"] - tr.get("p0", tr["p"])) >= min_travel]


def cpa(p_rel, v_rel, horizon=2.0):
    """Diem gap gan nhat (closest point of approach) cua vat so voi robot.
    p_rel = vi tri vat - robot, v_rel = van toc vat - robot. -> (t*, d*)."""
    vv = float(np.dot(v_rel, v_rel))
    t = 0.0 if vv < 1e-9 else float(np.clip(-np.dot(p_rel, v_rel) / vv, 0.0, horizon))
    return t, float(np.linalg.norm(p_rel + v_rel * t))


# =============================================================================
#  BO DIEU KHIEN CUC BO MUOT: MPPI (+ DWA de so sanh)
# =============================================================================
def obstacle_field(grid, layers=()):
    """Khoang cach (m) tu moi o toi vat can gan nhat (LiDAR + cac lop khac, vd D435i).
    O chua biet coi la trong (giong A*: gia dinh khong gian trong, D* Lite)."""
    occ = grid.occupied()
    for g in layers:
        occ = occ | g.occupied()
    if not occ.any():
        return np.full(occ.shape, 99.0, np.float32)
    return (distance_transform_edt(~occ) * grid.res).astype(np.float32)


def _resample(path, step=0.1):
    """Duong A* (it diem) -> diem cach deu `step` m + do dai cung tich luy."""
    P = np.asarray(path, float)
    if len(P) < 2:
        return P.reshape(-1, 2), np.zeros(len(P))
    seg = np.hypot(*np.diff(P, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    ss = np.arange(0.0, s[-1] + 1e-9, step)
    if ss[-1] < s[-1]:
        ss = np.append(ss, s[-1])
    return np.stack([np.interp(ss, s, P[:, 0]), np.interp(ss, s, P[:, 1])], 1), ss


class RespModel:
    """DAP UNG BAO HOA hoc online: moi truc v_on_dinh = s*tanh(g*u/s), bac 1 (tau). Giu luoi (g, s), chay
    song song bo loc bac 1 voi lenh that, tich luy sai so (quen dan) -> hau nghiem -> bang tra trung binh.
    Khong biet truoc robot; tien nghiem rong (g ~ 0.8, s rong). 4 bo: vx tien, vx lui, vy, wz."""

    def __init__(self, tau=0.2):
        g = np.linspace(0.2, 1.4, 13)
        self.tau = tau
        self.ug = [np.linspace(-.6, .6, 49), np.linspace(-.4, .4, 33), np.linspace(-1.2, 1.2, 49)]
        self.S = [np.array([.2, .24, .28, .32, .4, .5, .7, 1., 3.])] * 2 + [np.array([.5, .7, .9, 1.2, 3.])]
        self.noise = (0.10, 0.10, 0.40)
        self.cand = [np.array([(a, b) for a in g for b in S_]) for S_ in self.S]
        self.E = {k: 0.5 * ((self.cand[k[0]][:, 0] - 0.8) / 0.35) ** 2 for k in ((0, 1), (0, -1), (1, 1), (2, 1))}
        self.vh = {k: np.zeros(len(self.cand[k[0]])) for k in self.E}
        self.ve = {k: np.zeros(len(self.cand[k[0]])) for k in self.E}
        self.v_est = np.zeros(3)
        self._tables()

    def _tables(self):
        self.tab, self.mean = [], {}
        for ax in range(3):
            u = self.ug[ax]
            out = np.zeros(len(u))
            for sg in ((1, -1) if ax == 0 else (1,)):
                c = self.cand[ax]
                e = self.E[(ax, sg)]
                p = np.exp(-(e - e.min()))
                p /= p.sum()
                m = (np.sign(u) == sg) if ax == 0 else np.ones(len(u), bool)
                out[m] = (p[:, None] * c[:, 1:2] * np.tanh(c[:, 0:1] * u[m][None] / c[:, 1:2])).sum(0)
                self.mean[(ax, sg)] = p
            self.tab.append(out)

    def update(self, u, v_meas, dt):
        a = min(1.0, dt / self.tau)
        for (ax, sg), e in self.E.items():
            c = self.cand[ax]
            act = (u[ax] * sg >= 0) if ax == 0 else True
            tgt = c[:, 1] * np.tanh(c[:, 0] * (u[ax] if act else 0.0) / c[:, 1])
            self.vh[(ax, sg)] += a * (tgt - self.vh[(ax, sg)])
            self.ve[(ax, sg)] = 0.5 * self.ve[(ax, sg)] + 0.5 * self.vh[(ax, sg)]      # cung bo loc voi v_meas
            if act and abs(u[ax]) > (0.05 if ax < 2 else 0.15):
                e *= 0.998
                e += 0.5 * np.minimum(((v_meas[ax] - self.ve[(ax, sg)]) / self.noise[ax]) ** 2, 9.0) * 0.4
        self._tables()
        for ax in range(3):
            self.v_est[ax] += a * (np.interp(u[ax], self.ug[ax], self.tab[ax]) - self.v_est[ax])

    def map(self, U):
        return np.stack([np.interp(U[..., k], self.ug[k], self.tab[k]) for k in range(3)], -1)


class MPPI:
    """Model Predictive Path Integral control (Williams et al., ICRA 2016; T-RO 2018) —
    ban holonomic cho Go2 (vx, vy, wz), cung y tuong voi Nav2 MPPI controller
    (Macenski et al., RAS 2023):

      moi chu ky (0.1 s): lay K chuoi dieu khien = chuoi tot nhat lan truoc + nhieu CO
      TUONG QUAN THEO THOI GIAN (muot, kieu SMPPI), mo phong T buoc bang mo hinh dong hoc
      co do tre + he so van toc thuc/lenh (gait CHAMP chi dat ~40-50 % van toc lenh),
      cham diem tung quy dao, roi lay TRUNG BINH CO TRONG SO exp(-cost/lambda).

    Cost (cang nho cang tot):
      vat can     2 hinh tron phu than Go2 (0.74 x 0.40 m) tren truong khoang cach EDT;
                  cham = phat nang, gan = phat mem -> tu luon cach vat, KHONG can phanh
      nguoi       vi tri du doan van toc khong doi theo tung buoc -> ne truoc khi toi
      bam duong   khoang cach toi duong A* (duong toan cuc) + tien do toi diem 'ca rot'
      huong       uu tien di toi, mat nhin theo huong duong; phat lui va di ngang nhieu
      muot        phat thay doi dieu khien giua cac buoc
    Khong co buoc 'dung lai quay mat' nao: quay va tien cung luc, co ca di ngang."""

    def __init__(self, K=600, T=24, dt=0.1, vmax=(0.6, 0.3, 1.0), vmin=(-0.2, -0.3, -1.0),
                 sigma=(0.22, 0.14, 0.55), tau=0.25, seed=0, log_noise=False):
        self.K, self.T, self.dt, self.tau = K, T, dt, tau
        # log-MPPI (Mohamed et al. 2022): nhieu = normal x log-normal -> loi nho hon, duoi dai
        # hon (thinh thoang thu buoc xa) -> it ket o cuc tieu dia phuong hon
        self.log_noise = log_noise
        self.vmax, self.vmin = np.array(vmax, float), np.array(vmin, float)
        self.sigma = np.array(sigma, float)
        self.rng = np.random.default_rng(seed)
        self.U = np.zeros((T, 3))
        self.w = dict(goal=4.0, path=2.5, obs=6.0, col=1e4, ppl=8.0, fwd=1.0, lat=0.6,
                      ang=1.2, smooth=2.0)
        self.r_body, self.c_off, self.margin = 0.20, 0.17, 0.08
        # Nav2 MPPI ObstaclesCritic.near_goal_distance (mac dinh 0.5 m): gan dich thi BO luc day
        # mem (van giu phat va cham cung) - neu khong, dich sat vat (vd coc slalom cach 0.4 m) tao
        # cuc tieu dia phuong: luc day = luc keo dich o ~0.45 m -> robot dung, bao "ket" (sang loc
        # 22/11: ca ho MPPI that bai slalom_coc vi ly do nay, DWA/RL toi duoc khong va).
        self.near_goal = 0.5
        self.ppl_len = 0.3
        self.lam_q, self.lam_c = 0.5, 0.08       # nhiet do: lam_c * (phan vi lam_q - min)
        self.w_pen = 0.0                         # >0: phat theo DO LUN vao nguoi (khi moi mau deu cham)
        self.resp = None                         # RespModel (tag ~nl): dap ung bao hoa hoc online
        self.people_cap = False                  # True: khoang cach nguoi tinh theo than dai (2 vong tron)
        self.last = {}

    def reset(self):
        self.U[:] = 0.0

    # ---------------------------------------------------------------- mo phong
    def rollout(self, U, x0, v0, gain):
        """U (K,T,3) lenh than -> vi tri (K,T,2), yaw (K,T), van toc thuc (K,T,3)."""
        K, T = U.shape[:2]
        a = min(1.0, self.dt / self.tau)
        x = np.repeat(np.asarray(x0, float)[None], K, 0)           # (K,3)
        v = np.repeat(np.asarray(v0, float)[None], K, 0)
        P, Y, V = np.empty((K, T, 2)), np.empty((K, T)), np.empty((K, T, 3))
        G = self.resp.map(U) if self.resp is not None else None
        for t in range(T):
            v = v + a * ((gain * U[:, t] if G is None else G[:, t]) - v)
            c, s = np.cos(x[:, 2]), np.sin(x[:, 2])
            x[:, 0] += (v[:, 0] * c - v[:, 1] * s) * self.dt
            x[:, 1] += (v[:, 0] * s + v[:, 1] * c) * self.dt
            x[:, 2] += v[:, 2] * self.dt
            P[:, t], Y[:, t], V[:, t] = x[:, :2], x[:, 2], v
        return P, Y, V

    def ppl_dist(self, P, Y, qx, qy, rad):
        """(K,T) khoang ho than robot - nguoi. people_cap: 2 vong tron mui/duoi (nhu vat tinh)."""
        if not self.people_cap:
            return np.hypot(P[..., 0] - qx, P[..., 1] - qy) - rad - 0.3
        d = None
        for off in (self.c_off, -self.c_off):
            e = np.hypot(P[..., 0] + off * np.cos(Y) - qx, P[..., 1] + off * np.sin(Y) - qy)
            d = e if d is None else np.minimum(d, e)
        return d - rad - self.r_body - self.margin

    # ---------------------------------------------------------------- cham diem
    def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
        w = self.w
        K, T = P.shape[:2]
        res, x0, y0 = meta
        S = np.zeros(K)
        p_now = P[:, 0].mean(0)                                       # ~ vi tri robot hien tai
        repel = math.hypot(goal[0] - p_now[0], goal[1] - p_now[1]) >= self.near_goal
        # --- vat can: 2 hinh tron (mui, duoi) tren truong khoang cach
        coll = np.zeros(K, bool)
        dmin = np.full(K, 99.0)
        for off in (self.c_off, -self.c_off):
            cx = P[..., 0] + off * np.cos(Y)
            cy = P[..., 1] + off * np.sin(Y)
            c = np.clip(((cx - x0) / res).astype(int), 0, field.shape[1] - 1)
            r = np.clip(((cy - y0) / res).astype(int), 0, field.shape[0] - 1)
            d = field[r, c] - self.r_body                             # khoang ho cua hinh tron
            dmin = np.minimum(dmin, d.min(1))
            coll |= (d < self.margin).any(1)
            if repel:
                S += w["obs"] * np.exp(-np.maximum(d - self.margin, 0.0) / 0.15).sum(1) / T
        S += w["col"] * coll
        # --- nguoi / robot khac: du doan van toc khong doi
        tt = (np.arange(1, T + 1) * self.dt)[None, :]
        for (px, py, vx, vy, rad) in people:
            qx, qy = px + vx * tt, py + vy * tt
            d = self.ppl_dist(P, Y, qx, qy, rad)
            S += w["ppl"] * np.exp(-np.maximum(d, 0.0) / self.ppl_len).sum(1) / T
            S += w["col"] * 0.5 * (d < 0.0).any(1)
            if self.w_pen:
                S += self.w_pen * np.maximum(-d, 0.0).max(1)
        # --- bam duong + ca rot
        if path is not None and len(path) > 1:
            j1 = min(len(path), i0 + int(4.0 / 0.1) + 1)
            seg = path[max(i0 - 3, 0):j1]
            dd = np.hypot(P[..., 0, None] - seg[None, None, :, 0],
                          P[..., 1, None] - seg[None, None, :, 1])     # (K,T,M)
            near = dd.min(2)
            S += w["path"] * np.maximum(near - 0.1, 0.0).mean(1)
            jt = dd.argmin(2) + max(i0 - 3, 0)                         # chi so duong gan nhat
            nxt = np.minimum(jt + 3, len(path) - 1)
            tang = np.arctan2(path[nxt, 1] - path[jt, 1], path[nxt, 0] - path[jt, 0])
            far = np.hypot(goal[0] - P[..., 0], goal[1] - P[..., 1]) > 0.5
            S += w["ang"] * ((1 - np.cos(Y - tang)) * far).mean(1)
            # ca rot: diem tren duong cach ~ (van toc toi da x horizon) phia truoc
            carrot = path[min(len(path) - 1, i0 + int(self.vmax[0] * T * self.dt / 0.1 * 0.6) + 2)]
        else:
            carrot = goal
        dg = np.hypot(goal[0] - P[:, -1, 0], goal[1] - P[:, -1, 1])
        dc = np.hypot(carrot[0] - P[:, -1, 0], carrot[1] - P[:, -1, 1])
        S += w["goal"] * np.where(dg < 1.0, dg, dc)
        # --- uu tien di toi, it di ngang, muot
        S += w["fwd"] * np.maximum(-U[..., 0], 0.0).mean(1) * 4
        S += w["lat"] * np.abs(U[..., 1]).mean(1)
        dU = np.diff(np.concatenate([np.broadcast_to(u_prev, (K, 1, 3)), U], 1), axis=1)
        S += w["smooth"] * (dU ** 2).sum(2).mean(1)
        return S, coll, dmin

    def temperature(self, S, smin):
        q = np.median(S) if self.lam_q == 0.5 else np.quantile(S, self.lam_q)
        return max(1e-3, self.lam_c * (q - smin))

    def set_param(self, k, v):
        """Dat tham so tu ten cau hinh 'ten:k=v;k=v' (chinh dinh baseline va thuat toan moi nhu nhau)."""
        if k in self.w:
            self.w[k] = v
        elif k == "sig":                                              # nhan ca 3 sigma
            self.sigma = self.sigma * v
        elif k in ("sigx", "sigy", "sigw"):
            self.sigma[("sigx", "sigy", "sigw").index(k)] = v
        elif k in ("T", "K"):
            setattr(self, k, int(v))
            self.U = np.zeros((self.T, 3))
        else:
            setattr(self, k, type(getattr(self, k))(v))

    # ---------------------------------------------------------------- 1 buoc
    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None):
        """-> (lenh (vx, vy, wz), info). info['blocked'] = moi quy dao deu va cham."""
        K, T = self.K, self.T
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        eps = self.rng.normal(size=(K, T, 3)) * self.sigma
        if self.log_noise:
            eps *= 0.7 * self.rng.lognormal(0.0, 0.6, size=(K, T, 3))
        for t in range(1, T):                                         # nhieu muot theo thoi gian
            eps[:, t] = 0.7 * eps[:, t - 1] + 0.45 * eps[:, t]
        U = np.clip(self.U[None] + eps, self.vmin, self.vmax)
        U[0] = self.U                                                 # chuoi cu (khong nhieu)
        U[1] = 0.0                                                    # dung yen (luon co)
        if path is not None and len(path) > 1:                        # 'di thang theo duong'
            i0 = self._nearest(path, x0)
            a = path[min(i0 + 6, len(path) - 1)]
            hd = math.atan2(a[1] - x0[1], a[0] - x0[0]) - x0[2]
            hd = math.atan2(math.sin(hd), math.cos(hd))
            U[2] = np.clip([0.45 * math.cos(hd), 0.0, 1.2 * hd], self.vmin, self.vmax)
        else:
            i0 = 0
        P, Y, V = self.rollout(U, x0, v0, gain)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev)
        smin = S.min()
        lam = self.temperature(S, smin)
        wgt = np.exp(-(S - smin) / lam)
        wgt /= wgt.sum()
        newU = (wgt[:, None, None] * U).sum(0)
        newU[1:-1] = (newU[:-2] + 2 * newU[1:-1] + newU[2:]) / 4.0     # loc nhe
        self.U = newU
        best = int(S.argmin())
        u = self.U[0].copy()
        blocked = bool(coll.all())
        if coll[best] and not blocked:
            u = U[best, 0].copy()
        # quy dao trung binh (de ve / kiem tra)
        Pm, Ym, _ = self.rollout(self.U[None], x0, v0, gain)
        self.U = np.roll(self.U, -1, 0)
        self.U[-1] = self.U[-2]
        self.last = dict(best_cost=float(smin), blocked=blocked, ess=float(1.0 / (wgt ** 2).sum()),
                         traj=Pm[0], clear=float(dmin[best]), i0=i0)
        return (u if not blocked else np.zeros(3)), self.last

    @staticmethod
    def _nearest(path, x0):
        return int(np.argmin(np.hypot(path[:, 0] - x0[0], path[:, 1] - x0[1])))


class DWA(MPPI):
    """Dynamic Window Approach (Fox, Burgard, Thrun, IEEE RAM 1997) de SO SANH: thu mot
    luoi van toc KHONG DOI trong cua so gia toc, cung mo hinh va cung ham cost voi MPPI,
    chon cai re nhat. Don gian, nhanh, nhung 'can thi' (1 van toc cho ca horizon)."""

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None):
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        acc = np.array([0.5, 0.4, 1.5]) * 0.5                          # cua so dong (0.5 s)
        lo, hi = np.maximum(self.vmin, u_prev - acc), np.minimum(self.vmax, u_prev + acc)
        grid = np.stack(np.meshgrid(np.linspace(lo[0], hi[0], 9), np.linspace(lo[1], hi[1], 5),
                                    np.linspace(lo[2], hi[2], 11), indexing="ij"), -1).reshape(-1, 3)
        U = np.repeat(grid[:, None], self.T, 1)
        i0 = self._nearest(path, x0) if path is not None and len(path) > 1 else 0
        P, Y, V = self.rollout(U, x0, v0, gain)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev)
        best = int(S.argmin())
        blocked = bool(coll.all())
        self.last = dict(best_cost=float(S[best]), blocked=blocked, traj=P[best],
                         clear=float(dmin[best]), i0=i0)
        return (U[best, 0].copy() if not blocked else np.zeros(3)), self.last


class PRISM(MPPI):
    """PRISM — MPPI cho cho 4 chan dieu khien bang giong noi (thuat toan DE XUAT).

    Moi thanh phan lap 1 khoang trong da do duoc (tat duoc rieng de lam ablation, `flags`):

      prior  MAU TU POLICY RL: 20 % so mau gieo quanh hanh dong cua policy PPO (phan xa
             nhanh voi nguoi), 80 % quanh chuoi MPPI cu (giu kha nang lap ke hoach).
             Ty le theo CoRL-MPPI (2025) / RAY-TOLD (2026).
      adapt  MO HINH GAIT THICH NGHI: he so van toc thuc/lenh RIENG tung truc (vx, vy, wz)
             uoc luong online -> du doan dung duong robot that se di (gait CHAMP ~0.4-0.5,
             Go2 that ~0.9; xoay va di ngang lech khac nhau).
      vis    NHAN BIET VUNG MU: phat chuyen dong vao vung sat than ma cam bien khong nhin
             thay gan day (LiDAR mu < 0.5 m, D435i chi nhin phia truoc) - ban do luu thoi
             diem moi o duoc thay lan cuoi (OccGrid.seen_t).
      unc    DU DOAN NGUOI CO BAT DINH: ban kinh nguoi lon dan theo thoi gian du doan,
             va tinh ca nguoi "nghi la dang di" (chua du 0.5 m) voi trong so thap -> phan
             ung som ma khong khung vi bong ma.
      lang   LENH GIONG NOI CHINH CACH NE: "đi chậm", "tránh xa người", "cẩn thận" ->
             doi gioi han toc do / khoang cach nguoi / trong so vat can (nav_prefs).
    """

    def __init__(self, policy=None, prior_frac=0.2, flags=None, priors=None, hold=6, w_value=0.3, **kw):
        super().__init__(**kw)
        self.policy = policy
        self.prior_frac = prior_frac
        # Goi y RL DAY DU (gop tu AP-MPPI): nhieu policy (vd PPO + TD3) chay VONG KIN tren mo hinh,
        # ty le mau RIENG tung policy tu dieu chinh, critic PPO lam chi phi cuoi quy dao
        self.priors = list(priors or [])
        self.ratios = [prior_frac / max(1, len(self.priors))] * len(self.priors)
        self.hold, self.w_value = hold, w_value
        self.flags = dict(prior=True, adapt=True, vis=True, unc=True, lang=True,
                          adaptratio=True, value=True)
        self.flags.update(flags or {})
        self.w.update(vis=4.0, path=4.0, smooth=4.0, ang=1.8)
        self.vmax0, self.vmin0 = self.vmax.copy(), self.vmin.copy()
        # gioi han thay doi lenh moi 0.1 s (chong rung - MPPI goc lac huong gap 2-4 lan DWA)
        self.du_max = np.array([0.08, 0.08, 0.22])
        self.prefs = {}

    def _apply_prefs(self):
        p = self.prefs if self.flags["lang"] else {}
        k = float(p.get("speed", 1.0))
        self.vmax = self.vmax0 * np.array([k, k, 1.0])
        self.vmin = self.vmin0 * np.array([k, k, 1.0])
        self.ppl_extra = float(p.get("people_margin", 0.0))
        self.w["obs"] = 6.0 * float(p.get("caution", 1.0))

    def cost(self, U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev):
        S, coll, dmin = super().cost(U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev)
        if self.flags["vis"] and self._seen is not None:
            res, x0, y0 = meta
            seen_t, now, rx, ry = self._seen
            V = np.diff(np.concatenate([np.broadcast_to(self._x0[:2], (P.shape[0], 1, 2)), P], 1), axis=1)
            sp = np.hypot(V[..., 0], V[..., 1]) / self.dt
            ux = V[..., 0] / np.maximum(sp * self.dt, 1e-6)
            uy = V[..., 1] / np.maximum(sp * self.dt, 1e-6)
            lx, ly = P[..., 0] + 0.35 * ux, P[..., 1] + 0.35 * uy        # diem than sap toi
            near = np.hypot(lx - rx, ly - ry) < 0.8                      # chi vung sat than
            c = np.clip(((lx - x0) / res).astype(int), 0, field.shape[1] - 1)
            r = np.clip(((ly - y0) / res).astype(int), 0, field.shape[0] - 1)
            stale = (now - seen_t[r, c]) > 2.5
            S += self.w["vis"] * (stale & near & (sp > 0.05) * 1).astype(float).mean(1) \
                * (1.0 + np.abs(U[..., 1]).mean(1) * 2)
        return S, coll, dmin

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None,
             seen=None, tentative=(), gains=None, obs_fn=None):
        self._apply_prefs()
        self._x0 = np.asarray(x0, float)
        self._seen = seen
        g = np.asarray(gains if (gains is not None and self.flags["adapt"]) else [gain] * 3, float)
        ppl = []
        for (px, py, vx, vy, rad) in people:
            ppl.append((px, py, vx, vy, rad + self.ppl_extra))
        if self.flags["unc"]:
            ppl += [(px, py, vx, vy, rad + self.ppl_extra) for (px, py, vx, vy, rad) in tentative]
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        # ---- lay mau: 80 % quanh chuoi MPPI, 20 % quanh hanh dong policy RL
        K, T = self.K, self.T
        eps = self.rng.normal(size=(K, T, 3)) * self.sigma
        for t in range(1, T):
            eps[:, t] = 0.7 * eps[:, t - 1] + 0.45 * eps[:, t]
        base = np.repeat(self.U[None], K, 0)
        spans = []
        use_multi = self.flags["prior"] and self.priors
        if self.flags["prior"] and self.policy is not None and not self.priors:
            a_rl, _ = self.policy.step(x0, v0, field, meta, path, s_path, goal, ppl, float(g.mean()), u_prev)
            Kp = int(self.prior_frac * K)
            seed = self.U.copy()
            seed[:10] = a_rl                                          # giu hanh dong RL ~1 s
            base[3:3 + Kp] = seed
            eps[3:3 + Kp] *= 0.5
        U = np.clip(base + eps, self.vmin, self.vmax)
        if use_multi:
            pol0 = self.priors[0]
            a_prev = 2 * (u_prev - pol0.vmin) / (pol0.vmax - pol0.vmin) - 1
            ks = [int(round(r_ * K)) for r_ in self.ratios]
            j = K - sum(ks)
            for pl, kk in zip(self.priors, ks):
                if kk > 0:
                    U[j:j + kk] = PolicyMPPI._policy_rollouts(self, x0, v0, field, meta, path, goal, ppl,
                                                              g, a_prev, kk, pol=pl)
                spans.append((j, j + kk))
                j += kk
        U[0] = np.clip(self.U, self.vmin, self.vmax)
        U[1] = 0.0
        i0 = self._nearest(path, x0) if path is not None and len(path) > 1 else 0
        if path is not None and len(path) > 1:
            a = path[min(i0 + 6, len(path) - 1)]
            hd = math.atan2(a[1] - x0[1], a[0] - x0[0]) - x0[2]
            hd = math.atan2(math.sin(hd), math.cos(hd))
            U[2] = np.clip([0.45 * math.cos(hd), 0.0, 1.2 * hd], self.vmin, self.vmax)
        P, Y, V = self.rollout(U, x0, v0, g)
        # nguoi: ban kinh lon dan theo thoi gian (bat dinh du doan)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, [], goal, u_prev)
        if ppl:
            tt = (np.arange(1, T + 1) * self.dt)[None, :]
            for (px, py, vx, vy, rad) in ppl:
                # bat dinh tang theo thoi gian, ty le voi toc do nguoi (nguoi dung yen: khong phong)
                grow = 0.10 * tt * min(1.0, math.hypot(vx, vy) / 0.5) if self.flags["unc"] else 0.0 * tt
                d = self.ppl_dist(P, Y, px + vx * tt, py + vy * tt, rad) - grow
                S += self.w["ppl"] * np.exp(-np.maximum(d, 0.0) / 0.3).sum(1) / T
                S += self.w["col"] * 0.5 * (d[:, :12] < -grow[:, :12] if self.flags["unc"] else d[:, :12] < 0).any(1)
        if use_multi and self.flags["value"] and getattr(self.priors[0], "VW", None) is not None:
            pol0 = self.priors[0]                                     # critic PPO: chi phi cuoi
            top = np.argsort(S)[:96]
            XT = np.concatenate([P[top, -1], Y[top, -1:]], 1)
            OT = pol0.observe_batch(XT, V[top, -1], field, meta, path, goal,
                                    [(px + vx * T * self.dt, py + vy * T * self.dt, vx, vy, r)
                                     for (px, py, vx, vy, r) in ppl], np.repeat(a_prev[None], len(top), 0))
            val = pol0.value_batch(OT)
            S[top] -= self.w_value * (val - val.max())
            S[np.setdiff1d(np.arange(K), top)] += self.w_value * (val.max() - val.min())
        smin = S.min()
        lam = max(1e-3, 0.08 * (np.median(S) - smin))
        wgt = np.exp(-(S - smin) / lam)
        wgt /= wgt.sum()
        if use_multi and self.flags["adaptratio"]:                   # ty le tung policy tu dieu chinh
            lo = 0.05 / len(self.priors)
            for i, (a_, b_) in enumerate(spans):
                r_ = self.ratios[i]
                share = float(wgt[a_:b_].sum())
                self.ratios[i] = float(np.clip(r_ * math.exp(0.3 * (share / max(r_, 1e-3) - 1)), lo, 0.3))
            tot = sum(self.ratios)
            if tot > 0.3:                                  # tong <= 30 % (CoRL-MPPI 30 %, RAY-TOLD <= 20 %)
                self.ratios = [r_ * 0.3 / tot for r_ in self.ratios]
        newU = (wgt[:, None, None] * U).sum(0)
        newU[1:-1] = (newU[:-2] + 2 * newU[1:-1] + newU[2:]) / 4.0
        self.U = newU
        best = int(S.argmin())
        u = self.U[0].copy()
        blocked = bool(coll.all())
        if coll[best] and not blocked:
            u = U[best, 0].copy()
        Pm_now = self.rollout(self.U[None], x0, v0, g)[0][0]
        # nguoi SAP VA trong 1 s toi (theo chuoi dang theo)? -> bo gioi han thay doi lenh de ne gap
        urgent = False
        if ppl:
            tt1 = (np.arange(1, 11) * self.dt)
            for (px, py, vx, vy, rad) in ppl:
                dd = np.hypot(Pm_now[:10, 0] - (px + vx * tt1), Pm_now[:10, 1] - (py + vy * tt1)) - rad
                if (dd < 0.55).any():
                    urgent = True
                    break
        if not blocked and not urgent:
            u = u_prev + np.clip(u - u_prev, -self.du_max, self.du_max)
            if dmin[best] < 0.03:                                     # sat vat: cho phep phanh gap
                u = U[best, 0].copy() if not coll[best] else np.zeros(3)
        Pm, _, _ = self.rollout(self.U[None], x0, v0, g)
        self.U = np.roll(self.U, -1, 0)
        self.U[-1] = self.U[-2]
        self.last = dict(best_cost=float(smin), blocked=blocked, ess=float(1.0 / (wgt ** 2).sum()),
                         traj=Pm[0], clear=float(dmin[best]), i0=i0, ratios=list(self.ratios))
        return (u if not blocked else np.zeros(3)), self.last


class EnsemblePolicy:
    """Doi chung RL TRON: trung binh hanh dong cua nhieu policy (vd PPO + TD3), khong MPPI."""

    def __init__(self, policies):
        self.policies = policies
        self.last = {}

    def reset(self):
        pass

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None):
        us = [p.step(x0, v0, field, meta, path, s_path, goal, people, gain, u_prev)[0] for p in self.policies]
        info = dict(self.policies[0].last)
        info.update(blocked=False, source="ensemble")
        self.last = info
        return np.mean(us, 0), info


class PolicyMPPI(MPPI):
    """MPPI CO MAU TU POLICY RL.

    mode="pg"  TAI HIEN y tuong CoRL-MPPI (arXiv 2511.09331, 2025) / RAY-TOLD (arXiv
               2604.27450, 2026): mot ty le CO DINH (30 %) mau la quy dao policy chay VONG KIN
               tren mo hinh (moi 4 buoc hoi lai policy voi quan sat tai trang thai du doan,
               co nhieu), 70 % mau MPPI thuong.
    mode="ap"  AP-MPPI (DE XUAT, bai A) - 2 cai tien:
               (1) ty le mau policy TU DIEU CHINH online theo phan trong so quan trong ma mau
                   policy gianh duoc (multiplicative weights): policy dang dung -> dung nhieu
                   mau hon; policy sai (vd ngo cut) -> giam ve 5 %
               (2) chi phi CUOI quy dao = -critic V(o_T) cua PPO (nhu TD-MPC2, ICLR 2024):
                   uoc luong 'con bao xa/kho' sau tam 2.4 s -> bot can thi."""

    def __init__(self, policy, mode="pg", ratio=0.3, hold=6, w_value=0.3, extra_policies=(), **kw):
        kw.setdefault("K", 600)                                     # BANG MPPI/PRISM (cu: 400, khong cong bang)
        super().__init__(**kw)
        self.policy, self.mode, self.hold = policy, mode, hold
        self.w_value = w_value
        # NHIEU POLICY GOI Y (vd PPO + TD3): moi policy 1 ty le rieng, tu dieu chinh (mode "ap")
        self.policies = [policy] + list(extra_policies)
        self.ratios = [ratio / len(self.policies)] * len(self.policies)
        self.ratio = sum(self.ratios)
        self.ratio_log = []

    def _policy_rollouts(self, x0, v0, field, meta, path, goal, people, gain, a_prev, n, pol=None):
        X = np.repeat(np.asarray(x0, float)[None], n, 0)
        Vv = np.repeat(np.asarray(v0, float)[None], n, 0)
        A = np.repeat(a_prev[None], n, 0)
        Up = np.zeros((n, self.T, 3))
        alpha = min(1.0, self.dt / self.tau)
        pol = pol or self.policy
        for t0 in range(0, self.T, self.hold):
            ppl = [(px + vx * t0 * self.dt, py + vy * t0 * self.dt, vx, vy, r) for (px, py, vx, vy, r) in people]
            O = pol.observe_batch(X, Vv, field, meta, path, goal, ppl, A)
            a = np.clip(pol.forward_batch(O) + 0.15 * self.rng.normal(size=(n, 3)), -1, 1)
            u = pol.vmin + (a + 1) * 0.5 * (pol.vmax - pol.vmin)
            u = np.clip(u, self.vmin, self.vmax)
            for k in range(t0, min(self.T, t0 + self.hold)):
                Vv = Vv + alpha * (gain * u - Vv)
                c, s = np.cos(X[:, 2]), np.sin(X[:, 2])
                X[:, 0] += (Vv[:, 0] * c - Vv[:, 1] * s) * self.dt
                X[:, 1] += (Vv[:, 0] * s + Vv[:, 1] * c) * self.dt
                X[:, 2] += Vv[:, 2] * self.dt
                Up[:, k] = u
            A = a
        return Up

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None):
        K, T = self.K, self.T
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        pol = self.policy
        a_prev = 2 * (u_prev - pol.vmin) / (pol.vmax - pol.vmin) - 1
        ks = [int(round(r_ * K)) for r_ in self.ratios]              # so mau cua tung policy
        Kp = sum(ks)
        eps = self.rng.normal(size=(K, T, 3)) * self.sigma
        for t in range(1, T):
            eps[:, t] = 0.7 * eps[:, t - 1] + 0.45 * eps[:, t]
        U = np.clip(self.U[None] + eps, self.vmin, self.vmax)
        spans, j = [], K - Kp
        for pl, kk in zip(self.policies, ks):
            if kk > 0:
                U[j:j + kk] = self._policy_rollouts(x0, v0, field, meta, path, goal, people, gain,
                                                    a_prev, kk, pol=pl)
            spans.append((j, j + kk))
            j += kk
        U[0] = self.U
        U[1] = 0.0
        i0 = self._nearest(path, x0) if path is not None and len(path) > 1 else 0
        P, Y, V = self.rollout(U, x0, v0, gain)
        S, coll, dmin = self.cost(U, P, Y, field, meta, path, s_path, i0, people, goal, u_prev)
        if self.mode == "ap" and getattr(pol, "VW", None) is not None:
            top = np.argsort(S)[:96]                                   # critic cho 96 mau tot nhat
            XT = np.concatenate([P[top, -1], Y[top, -1:]], 1)
            OT = pol.observe_batch(XT, V[top, -1], field, meta, path, goal,
                                   [(px + vx * T * self.dt, py + vy * T * self.dt, vx, vy, r)
                                    for (px, py, vx, vy, r) in people],
                                   np.repeat(a_prev[None], len(top), 0))
            val = pol.value_batch(OT)
            S[top] -= self.w_value * (val - val.max())                 # chi lech tuong doi
            S[np.setdiff1d(np.arange(K), top)] += self.w_value * (val.max() - val.min())
        smin = S.min()
        lam = max(1e-3, 0.08 * (np.median(S) - smin))
        wgt = np.exp(-(S - smin) / lam)
        wgt /= wgt.sum()
        if self.mode == "ap" and Kp > 0:                               # (1) ty le tu dieu chinh, TUNG policy
            lo = 0.05 / len(self.policies)
            for i, (a_, b_) in enumerate(spans):
                share = float(wgt[a_:b_].sum())
                r_ = self.ratios[i]
                self.ratios[i] = float(np.clip(r_ * math.exp(0.3 * (share / max(r_, 1e-3) - 1)), lo, 0.3))
            tot = sum(self.ratios)
            if tot > 0.3:                                  # tong <= 30 % (CoRL-MPPI 30 %, RAY-TOLD <= 20 %)
                self.ratios = [r_ * 0.3 / tot for r_ in self.ratios]
            self.ratio = sum(self.ratios)
            self.ratio_log.append(list(self.ratios))
        newU = (wgt[:, None, None] * U).sum(0)
        newU[1:-1] = (newU[:-2] + 2 * newU[1:-1] + newU[2:]) / 4.0
        self.U = newU
        best = int(S.argmin())
        u = self.U[0].copy()
        blocked = bool(coll.all())
        if coll[best] and not blocked:
            u = U[best, 0].copy()
        Pm, _, _ = self.rollout(self.U[None], x0, v0, gain)
        self.U = np.roll(self.U, -1, 0)
        self.U[-1] = self.U[-2]
        self.last = dict(best_cost=float(smin), blocked=blocked, traj=Pm[0], clear=float(dmin[best]),
                         i0=i0, ratio=self.ratio, policy_share=float(wgt[K - Kp:].sum()) if Kp else 0.0)
        return (u if not blocked else np.zeros(3)), self.last


class RLPolicy:
    """Policy NE VAT CAN hoc bang PPO (rl_nav/train_ppo.py), chay bang numpy (khong can
    torch -> chay duoc tren Jetson cua cho). Cung giao dien voi MPPI.step().

    Quan sat dung hinh thuc nhu luc train (rl_nav/env.py):
      72 tia: do tren truong khoang cach cua ban do chiem cho (sphere tracing)
      dich: diem 'ca rot' cach 3 m tren duong A* (hoac dich cuoi neu gan hon)
      van toc do duoc + lenh truoc + 3 nguoi gan nhat (BlobTracker)
    shield: neu truyen 1 MPPI -> che do 'rl_safe': lenh RL giu nguyen 1.2 s ma du doan va
    cham (vat hoac nguoi) thi dung lenh MPPI (kieu 'safety filter' cua ABS, RSS 2024)."""

    def __init__(self, path, shield=None):
        z = np.load(path)
        self.W = [z[f"W{i}"] for i in range(10) if f"W{i}" in z]
        self.b = [z[f"b{i}"] for i in range(10) if f"b{i}" in z]
        self.mu, self.sd = z["obs_mean"].astype(np.float32), z["obs_std"].astype(np.float32)
        self.W = [w.astype(np.float32) for w in self.W]                # float32: nhanh gap doi
        self.b = [b.astype(np.float32) for b in self.b]
        self.R, self.ray_max = int(z["n_rays"]), float(z["ray_max"])
        self.vmax, self.vmin = z["vmax"].astype(float), z["vmin"].astype(float)
        self.ang = np.arange(self.R) * (2 * math.pi / self.R)
        self.out = str(z["out"]) if "out" in z else "clip"          # PPO: clip, TD3: tanh
        self.shield = shield
        self.last = {}
        self.overrides = 0
        self.steps = 0

    def reset(self):
        if self.shield is not None:
            self.shield.reset()

    def load_value(self, path):
        """Critic V(o) cua PPO (rl_nav/export_value.py) - dung lam chi phi cuoi cho AP-MPPI."""
        z = np.load(path)
        self.VW = [z[f"W{i}"].astype(np.float32) for i in range(10) if f"W{i}" in z]
        self.Vb = [z[f"b{i}"].astype(np.float32) for i in range(10) if f"b{i}" in z]

    def value_batch(self, O):
        x = np.clip((np.asarray(O, np.float32) - self.mu) / self.sd, -8, 8)
        for k, (W, b) in enumerate(zip(self.VW, self.Vb)):
            x = x @ W + b
            if k < len(self.VW) - 1:
                x = np.where(x > 0, x, np.expm1(np.minimum(x, 0)))
        return x[:, 0]

    def forward_batch(self, O):
        return self._forward(O)

    def rays_batch(self, X, field, meta, iters=22):
        """Sphere tracing cho B x 72 tia (float32, tra cuu phang) - ~4x nhanh hon ban 2D."""
        res, gx0, gy0 = meta
        H, W = field.shape
        flat = field.ravel()
        th = (X[:, 2:3] + self.ang[None]).astype(np.float32)
        dx = (np.cos(th) / res).astype(np.float32)
        dy = (np.sin(th) / res).astype(np.float32)
        ox = ((X[:, 0:1] - gx0) / res).astype(np.float32)
        oy = ((X[:, 1:2] - gy0) / res).astype(np.float32)
        t = np.zeros(th.shape, np.float32)
        half = np.float32(0.5 * res)
        for _ in range(iters):
            c = (ox + t * dx).astype(np.int32)
            r = (oy + t * dy).astype(np.int32)
            ok = (c >= 0) & (c < W) & (r >= 0) & (r < H)
            d = np.where(ok, flat[np.clip(r, 0, H - 1) * W + np.clip(c, 0, W - 1)] - half, 9.0)
            step = np.where((d < 0.03) | (t >= self.ray_max), 0.0, np.maximum(d, 0.05))
            if not step.any():
                break
            t += step
        return np.clip(t, 0.0, self.ray_max).astype(float)

    def observe_batch(self, X, V, field, meta, path, goal, people, A_prev):
        """Quan sat cho B trang thai du doan (B,3) - giong observe() nhung vector hoa."""
        B = len(X)
        tgt = np.repeat(np.asarray(goal, float)[None], B, 0)
        if path is not None and len(path) > 1:
            d = np.hypot(path[None, :, 0] - X[:, 0, None], path[None, :, 1] - X[:, 1, None])
            car = path[np.minimum(d.argmin(1) + 30, len(path) - 1)]
            dg = np.hypot(goal[0] - X[:, 0], goal[1] - X[:, 1])
            dc = np.hypot(car[:, 0] - X[:, 0], car[:, 1] - X[:, 1])
            tgt = np.where((dg > dc)[:, None], car, tgt)
        c, s = np.cos(X[:, 2]), np.sin(X[:, 2])
        rx, ry = tgt[:, 0] - X[:, 0], tgt[:, 1] - X[:, 1]
        gx, gy = c * rx + s * ry, -s * rx + c * ry
        dist = np.maximum(np.hypot(gx, gy), 1e-3)
        ped = np.zeros((B, 3, 4))
        if len(people):
            Pp = np.array([[q[0], q[1]] for q in people])
            Pv = np.array([[q[2], q[3]] for q in people])
            rel = Pp[None] - X[:, None, :2]                           # (B,N,2)
            dd = np.hypot(rel[..., 0], rel[..., 1])
            order = np.argsort(dd, 1)[:, :3]
            for k in range(min(3, len(people))):
                j = order[:, k]
                rr = rel[np.arange(B), j]
                vv = Pv[j]
                vis = (dd[np.arange(B), j] < 4.0)
                ped[:, k, 0] = (c * rr[:, 0] + s * rr[:, 1]) / 4.0 * vis
                ped[:, k, 1] = (-s * rr[:, 0] + c * rr[:, 1]) / 4.0 * vis
                ped[:, k, 2] = (c * vv[:, 0] + s * vv[:, 1]) * vis
                ped[:, k, 3] = (-s * vv[:, 0] + c * vv[:, 1]) * vis
        return np.concatenate([self.rays_batch(X, field, meta) / self.ray_max,
                               np.minimum(dist, 5.0)[:, None] / 5.0, (gy / dist)[:, None],
                               (gx / dist)[:, None], V, A_prev, ped.reshape(B, 12)], 1)

    def _forward(self, o):
        x = np.clip((np.asarray(o, np.float32) - self.mu) / self.sd, -8, 8)
        for k, (W, b) in enumerate(zip(self.W, self.b)):
            x = x @ W + b
            if k < len(self.W) - 1:
                x = np.where(x > 0, x, np.expm1(np.minimum(x, 0)))      # ELU
        return np.tanh(x) if self.out == "tanh" else np.clip(x, -1, 1)

    def rays(self, x0, field, meta):
        res, gx0, gy0 = meta
        th = x0[2] + self.ang
        dx, dy = np.cos(th), np.sin(th)
        t = np.zeros(self.R)
        done = np.zeros(self.R, bool)
        H, W = field.shape
        for _ in range(48):                                           # sphere tracing
            px, py = x0[0] + t * dx, x0[1] + t * dy
            c = ((px - gx0) / res).astype(int)
            r = ((py - gy0) / res).astype(int)
            inside = (c >= 0) & (c < W) & (r >= 0) & (r < H)
            d = np.where(inside, field[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)] - 0.5 * res, 99.0)
            done |= (d < 0.03) | (t >= self.ray_max)
            t = np.where(done, t, t + np.maximum(d, 0.04))
            if done.all():
                break
        return np.clip(t, 0.0, self.ray_max)

    def observe(self, x0, v0, field, meta, path, goal, people, u_prev):
        i0 = 0
        tgt = np.asarray(goal, float)
        if path is not None and len(path) > 1:
            i0 = int(np.argmin(np.hypot(path[:, 0] - x0[0], path[:, 1] - x0[1])))
            car = path[min(len(path) - 1, i0 + 30)]
            if math.hypot(goal[0] - x0[0], goal[1] - x0[1]) > math.hypot(car[0] - x0[0], car[1] - x0[1]):
                tgt = car
        c, s = math.cos(x0[2]), math.sin(x0[2])
        rx, ry = tgt[0] - x0[0], tgt[1] - x0[1]
        gx, gy = c * rx + s * ry, -s * rx + c * ry
        dist = max(math.hypot(gx, gy), 1e-3)
        ped = np.zeros((3, 4))
        near = sorted(people, key=lambda q: math.hypot(q[0] - x0[0], q[1] - x0[1]))[:3]
        for k, q in enumerate(near):
            px, py = q[0] - x0[0], q[1] - x0[1]
            if math.hypot(px, py) < 4.0:
                ped[k] = [(c * px + s * py) / 4.0, (-s * px + c * py) / 4.0,
                          c * q[2] + s * q[3], -s * q[2] + c * q[3]]
        a_prev = 2 * (np.asarray(u_prev, float) - self.vmin) / (self.vmax - self.vmin) - 1
        o = np.concatenate([self.rays(x0, field, meta) / self.ray_max,
                            [min(dist, 5.0) / 5.0, gy / dist, gx / dist],
                            np.asarray(v0, float), a_prev, ped.ravel()])
        return o, i0

    def step(self, x0, v0, field, meta, path, s_path, goal, people=(), gain=0.5, u_prev=None):
        u_prev = np.zeros(3) if u_prev is None else np.asarray(u_prev, float)
        o, i0 = self.observe(x0, v0, field, meta, path, goal, people, u_prev)
        a = self._forward(o)
        u = self.vmin + (a + 1) * 0.5 * (self.vmax - self.vmin)
        self.steps += 1
        info = dict(blocked=False, i0=i0, clear=float(o[:self.R].min() * self.ray_max), source="rl")
        if self.shield is not None:
            m = self.shield
            U = np.repeat(u[None, None], m.T, 1)
            P, Y, _ = m.rollout(U, x0, v0, gain)
            res, gx0, gy0 = meta
            k = 12                                                     # 1.2 s phia truoc
            bad = False
            for off in (m.c_off, -m.c_off):
                cx = P[0, :k, 0] + off * np.cos(Y[0, :k])
                cy = P[0, :k, 1] + off * np.sin(Y[0, :k])
                cc = np.clip(((cx - gx0) / res).astype(int), 0, field.shape[1] - 1)
                rr = np.clip(((cy - gy0) / res).astype(int), 0, field.shape[0] - 1)
                bad |= bool((field[rr, cc] - m.r_body < 0.05).any())
            tt = np.arange(1, k + 1) * m.dt
            for (px, py, vx, vy, rad) in people:
                if (np.hypot(P[0, :k, 0] - (px + vx * tt), P[0, :k, 1] - (py + vy * tt)) < rad + 0.35).any():
                    bad = True
            um, mi = m.step(x0, v0, field, meta, path, s_path, goal, people, gain, u_prev)
            if bad:
                self.overrides += 1
                info.update(source="mppi", blocked=mi["blocked"], traj=mi["traj"])
                self.last = info
                return um, info
            info["traj"] = P[0]
        else:
            info["traj"] = np.array([x0[:2]])
        self.last = info
        return u, info


if __name__ == "__main__":
    import time
    g = OccGrid()
    g.mark_box(0.0, -1.7, 0.6, 0.6)                 # thung giua duong ra cua
    g.mark_box(0.0, -4.0, 4.0, 0.15)                # mot doan tuong
    t = time.time()
    p, why = plan(g, (0.0, 0.0), (0.0, -3.0))
    print(f"{why}: {len(p or [])} diem, dai {path_length(p or []):.2f} m, "
          f"{(time.time() - t) * 1000:.0f} ms")
    print([(round(a, 2), round(b, 2)) for a, b in p])
    # gia lap 1 lan quet: robot o (0,0), vat o (1.0, 0)
    pts = np.array([[1.0, y] for y in np.linspace(-0.3, 0.3, 61)])
    g2 = OccGrid()
    g2.integrate(0.0, 0.0, pts)
    print("o chiem sau 1 quet:", int(g2.occupied().sum()), "(phai = 0)")
    g2.integrate(0.0, 0.0, pts)
    print("o chiem sau 2 quet:", int(g2.occupied().sum()), "(phai > 0)")
    for _ in range(4):
        g2.integrate(0.0, 0.0, np.empty((0, 2)))
    print("sau 4 quet khong con vat:", int(g2.occupied().sum()), "(phai = 0)")
