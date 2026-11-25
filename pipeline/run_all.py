#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline/run_all.py — CHAY HET phan nghien cuu con lai, TU TIEP TUC sau khi tat/mo may.

Duoc systemd (user) goi qua run_all.sh moi khi dang nhap. Moi giai doan ghi dau "xong" vao
pipeline/state.json; giai doan danh gia tiep tuc tung luot (eval_sim --resume); train RL tiep
tuc tung lan train (moi lan 20 phut, lan dang do thi train lai).

Giai doan:
  1 screen   sang loc 17 cau hinh x 8 bai (Gazebo, van phong 30x20 m)
  2 train    PPO / FastTD3 / FastSAC x 3 seed x 20 phut, cam bien thuc te (tat sim de khong tranh GPU)
  3 analyze  eval2d + phan tich bu tru -> results/RL_ANALYSIS.md (CHI SO LIEU)
     >> TRAM CHO 'rl', 'select_configs': CLAUDE doc so lieu va TU DANH GIA, ghi pipeline/decisions.json
  4 select   chay cac cau hinh PRISM Claude chon (Gazebo, 2 lan lap)
     >> TRAM CHO 'final': Claude xem ket qua, chon PRISM cuoi + danh sach so sanh + so lan lap
  5 final    luot CHINH THUC theo danh sach do
  6 report   bang so lieu + KTC + kiem dinh -> results/FINAL_REPORT_*.md; Claude viet ket luan
  (Nguoi dung yeu cau 21/11: KHONG de script tu chon - Claude danh gia bang suy xet.)

Xem tien do: pipeline/STATUS.md   nhat ky: pipeline/pipeline.log
Dung tay:    systemctl --user stop govoice-pipeline
"""

import csv
import glob
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = "/home/nhanhuynh/Documents/Go2_assitant"
P = os.path.join(ROOT, "pipeline")
STATE = os.path.join(P, "state.json")
LOG = os.path.join(P, "pipeline.log")
PY = os.path.join(ROOT, "venv", "bin", "python")
TASKS = 8
os.environ.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                  RMW_IMPLEMENTATION="rmw_cyclonedds_cpp", ROS_AUTOMATIC_DISCOVERY_RANGE="LOCALHOST",
                  GZ_IP="127.0.0.1", PYTHONUNBUFFERED="1")

SCREEN = ["prism", "mppi", "apmppi_multi", "pgmppi", "bmppi", "rl", "rl_ens", "rl_safe", "dwa",
          "log_mppi", "prism_noprior", "prism_noadaptratio", "prism_novalue", "prism_noadapt",
          "prism_novis", "prism_nounc", "pp"]
ABL = ["prior", "adaptratio", "value", "adapt", "vis", "unc"]
CHILD = []


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def load():
    try:
        return json.load(open(STATE))
    except Exception:                                          # noqa: BLE001
        return {}


import threading as _th
_SAVE_LOCK = _th.Lock()


def save(st):
    """GOP vao trang thai dang co (2 luong: sang loc + train cung ghi) - khong ghi de mat dau 'xong'."""
    with _SAVE_LOCK:
        cur = load()
        cur.update(st)
        st.update(cur)
        tmp = STATE + ".tmp"
        json.dump(cur, open(tmp, "w"), indent=2, ensure_ascii=False)
        os.replace(tmp, STATE)


def status(st, stage, detail, eta_h):
    order = ["screen", "train", "analyze", "select", "final", "report"]
    lines = [f"# Tien do pipeline GoVoice — cap nhat {time.strftime('%Y-%m-%d %H:%M')}", "",
             f"**Dang lam:** {stage} — {detail}", "",
             f"**Uoc tinh con lai:** ~{eta_h:.1f} gio (xong khoang "
             f"{time.strftime('%H:%M ngay %d/%m', time.localtime(time.time() + eta_h * 3600))})", "",
             "| Giai doan | Trang thai |", "|---|---|"]
    for s_ in order:
        lines.append(f"| {s_} | {'✅ xong' if st.get(s_ + '_done') else ('⏳ dang chay' if s_ == stage else '…')} |")
    if st.get("decision"):
        lines += ["", f"**Quyet dinh RL:** {st['decision']}"]
    if st.get("selected"):
        lines += [f"**Bo goi y PRISM da chon:** {st['selected']}"]
    open(os.path.join(P, "STATUS.md"), "w").write("\n".join(lines) + "\n")


def run(cmd, logname, timeout=None, env=None):
    """Chay lenh trong nhom tien trinh rieng; tra ve ma thoat (None neu het gio)."""
    with open(os.path.join(P, logname), "a") as lf:
        lf.write(f"\n===== {time.strftime('%F %T')} $ {' '.join(cmd)}\n")
        lf.flush()
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True,
                             env=env)
        CHILD.append(p)
        try:
            return p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGINT)
            time.sleep(5)
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return None
        finally:
            CHILD.remove(p)


# ------------------------------------------------------------------ mo phong
def sim_ready():
    try:
        out = subprocess.run(["gz", "service", "-l"], capture_output=True, text=True, timeout=10).stdout
        return "/world/voice_office/set_pose" in out
    except Exception:                                          # noqa: BLE001
        return False


def kill_sim():
    for pat in ["eval_[s]im.py", "ros2 launch go2_voice voice[_]sim", "gz[ ]sim", "gz-sim-[m]ain",
                "ros_gz_[b]ridge", "parameter_[b]ridge", "quadruped_[c]ontroller", "state_[e]stimation",
                "ekf_[n]ode", "robot_state_[p]ublisher", "controller_[m]anager", "static_transform_[p]ublisher",
                "movers[.]py"]:
        subprocess.call(["pkill", "-9", "-f", pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)


def start_sim():
    if sim_ready() and subprocess.call(["pgrep", "-f", "quadruped_[c]ontroller"], stdout=subprocess.DEVNULL) == 0:
        return True
    kill_sim()
    log("bat mo phong voice_office (headless)")
    lf = open(os.path.join(P, "sim.log"), "a")
    p = subprocess.Popen(["ros2", "launch", "go2_voice", "voice_sim.launch.py", "headless:=true",
                          "rviz:=false", "world:=voice_office.sdf"], cwd=os.path.expanduser("~/ros2_ws"),
                         stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
    CHILD.append(p)
    t0 = time.time()
    while time.time() - t0 < 240:
        if sim_ready():
            time.sleep(30)                                     # cho robot dung day, controller len
            return True
        time.sleep(3)
    log("mo phong KHONG len trong 4 phut")
    return False


def rows_done(out):
    f = os.path.join(out, "trials.csv")
    if not os.path.exists(f):
        return 0, 0.0
    rows = list(csv.DictReader(open(f)))
    keys = {(r.get("trial") or "1", r["config"], r["task"]) for r in rows}
    ts = [float(r["time_s"]) for r in rows if r.get("time_s")]
    return len(keys), (sum(ts) / len(ts) if ts else 90.0)


def eval_stage(st, key, configs, trials, out, stage, eta_after_h):
    expected = len(configs) * TASKS * trials
    for attempt in range(6):
        n, avg = rows_done(out)
        if n >= expected:
            return True
        per = avg + 25.0
        status(st, stage, f"{n}/{expected} luot", (expected - n) * per / 3600 + eta_after_h)
        if not start_sim():
            kill_sim()
            continue
        log(f"[{stage}] chay eval {n}/{expected} -> {out} (lan thu {attempt + 1})")
        code = run([PY, "-u", "eval_sim.py", "--suite", "office", "--configs", *configs,
                    "--trials", str(trials), "--out", out, "--resume"], f"{key}.log",
                   timeout=int((expected - n) * 400 + 1800))
        n2, _ = rows_done(out)
        log(f"[{stage}] eval thoat (ma {code}), {n2}/{expected} luot")
        if n2 < expected:                                      # sim treo / robot nga: bat lai
            kill_sim()
    return rows_done(out)[0] >= expected


# ------------------------------------------------------------------ 2 sim SONG SONG (tang toc)
# May: 16 luong, 14 GB RAM, RTX 4060 8 GB - 1 sim dung ~3.5 luong + 0.5 GB VRAM. Moi sim mot
# kenh rieng (GZ_PARTITION + ROS_DOMAIN_ID): da thu 22/11 - dich chuyen robot sim nay khong anh
# huong sim kia. Cau hinh chia luot nhau cho 2 sim -> 2 ben cung chiu tai nhu nhau (cong bang).
WORKERS = [dict(id=0, part="gvw0", dom="21"), dict(id=1, part="gvw1", dom="22")]


def wenv(w):
    e = os.environ.copy()
    e["GZ_PARTITION"], e["ROS_DOMAIN_ID"] = w["part"], w["dom"]
    return e


def kill_worker(w):
    subprocess.call([sys.executable, os.path.join(P, "kill_partition.py"), w["part"]],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


def worker_ready(w, world):
    try:
        out = subprocess.run(["gz", "service", "-l"], capture_output=True, text=True, timeout=10,
                             env=wenv(w)).stdout
        return f"/world/{world}/set_pose" in out
    except Exception:                                          # noqa: BLE001
        return False


def start_worker(w, world):
    kill_worker(w)
    log(f"[sim {w['part']}] bat {world} (headless)")
    lf = open(os.path.join(P, f"sim_{w['part']}.log"), "a")
    p = subprocess.Popen(["ros2", "launch", "go2_voice", "voice_sim.launch.py", "headless:=true",
                          "rviz:=false", f"world:={world}.sdf"], cwd=os.path.expanduser("~/ros2_ws"),
                         stdout=lf, stderr=subprocess.STDOUT, start_new_session=True, env=wenv(w))
    CHILD.append(p)
    t0 = time.time()
    while time.time() - t0 < 240:
        if worker_ready(w, world):
            time.sleep(30)
            return True
        time.sleep(3)
    return False


def eval_worker(w, suite, configs, trials, out, world, only=None):
    tasks_per = TASKS if suite == "office" else (only_count(only) if only else 24)
    expected = len(configs) * tasks_per * trials
    for attempt in range(6):
        n, _ = rows_done(out)
        if n >= expected:
            return True
        if not start_worker(w, world):
            kill_worker(w)
            continue
        log(f"[sim {w['part']}] eval {suite} {n}/{expected} -> {out} (lan {attempt + 1})")
        cmd = [PY, "-u", "eval_sim.py", "--suite", suite, "--configs", *configs, "--trials", str(trials),
               "--out", out, "--resume"] + (["--only", only] if only else [])
        code = run(cmd, f"eval_{w['part']}.log", timeout=int((expected - n) * 400 + 1800), env=wenv(w))
        n2, _ = rows_done(out)
        log(f"[sim {w['part']}] eval thoat (ma {code}), {n2}/{expected}")
        if n2 < expected:
            kill_worker(w)
    kill_worker(w)
    return rows_done(out)[0] >= expected


HOUSE_ONLY = "nav:,safety:,detour:,dyn:"                    # bai co dung bo ne (bo motion: khong phu thuoc)


def only_count(only):
    return {HOUSE_ONLY: 17}.get(only, 24)


def eval_parallel(st, key, suite, configs, trials, outbase, world, stage, eta_after_h, only=None):
    """Chia cau hinh luan phien cho 2 sim; moi sim ghi <outbase>_w<id>/trials.csv."""
    groups = [configs[i::len(WORKERS)] for i in range(len(WORKERS))]
    per = TASKS if suite == "office" else only_count(only)
    total = len(configs) * per * trials
    res = {}

    def job(w, cfgs):
        res[w["id"]] = eval_worker(w, suite, cfgs, trials, f"{outbase}_w{w['id']}", world, only)
    ths = [_th.Thread(target=job, args=(w, g), daemon=True) for w, g in zip(WORKERS, groups) if g]
    for t in ths:
        t.start()
    while any(t.is_alive() for t in ths):
        n = sum(rows_done(f"{outbase}_w{w['id']}")[0] for w in WORKERS)
        status(st, stage, f"{n}/{total} luot (2 sim song song)", (total - n) * 100 / 3600 / 2 + eta_after_h)
        time.sleep(60)
    return all(res.get(w["id"], True) for w, g in zip(WORKERS, groups) if g)


# ------------------------------------------------------------------ cac giai doan
def stage_screen(st):
    out = st.setdefault("screen_dir", os.path.join(ROOT, "results", "office_20261121_164514"))
    save(st)
    if eval_stage(st, "screen", SCREEN, 1, out, "screen", 3.2 + 0.2 + 2.0 + 11.5):
        st["screen_done"] = True
        save(st)


def stage_train(st, concurrent=False):
    if not concurrent:
        kill_sim()                                             # chay mot minh: danh GPU cho train
    jobs = [(a, s) for s in (0, 1, 2) for a in ("ppo", "td3", "sac")]
    for i, (algo, seed) in enumerate(jobs):
        name = f"{algo}_r_s{seed}"
        d = os.path.join(ROOT, "rl_nav", "runs", name)
        if os.path.exists(os.path.join(d, "DONE")):
            continue
        shutil.rmtree(d, ignore_errors=True)                   # lan train dang do: train lai
        status(st, "train", f"{name} ({i + 1}/{len(jobs)})", (len(jobs) - i) * 21 / 60 + 0.2 + 2.0 + 11.5)
        log(f"[train] {name}")
        script = {"ppo": "train_ppo.py", "td3": "train_td3.py", "sac": "train_sac.py"}[algo]
        extra = ["--curriculum-time"] if algo == "td3" else []
        code = run([PY, "-u", f"rl_nav/{script}", "--minutes", "20", "--realistic", "--seed", str(seed),
                    "--name", name, *extra], "train.log", timeout=40 * 60)
        if code == 0 and os.path.exists(os.path.join(d, "policy.npz")):
            open(os.path.join(d, "DONE"), "w").write(time.strftime("%F %T"))
        else:
            log(f"[train] {name} LOI (ma {code}) - se thu lai lan sau")
            return
    st["train_done"] = True
    save(st)


def _eval2d(path):
    out = subprocess.run([PY, "rl_nav/eval2d.py", path, "--realistic"], cwd=ROOT, capture_output=True,
                         text=True, timeout=1800).stdout
    m = re.search(r"\s([\d.]+)% \[", out)
    return float(m.group(1)) if m else -1.0, out


DECISIONS = os.path.join(P, "decisions.json")


def decisions():
    try:
        return json.load(open(DECISIONS))
    except Exception:                                          # noqa: BLE001
        return {}


def wait_for(st, key, what):
    """TRAM CHO: Claude doc so lieu, TU DANH GIA va ghi quyet dinh vao pipeline/decisions.json
    (nguoi dung yeu cau: khong de script tu chon). Trong luc cho: tat sim, bao thong bao."""
    if key in decisions():
        return decisions()[key]
    kill_sim()
    msg = f"CHO CLAUDE DANH GIA: {what} -> ghi '{key}' vao pipeline/decisions.json"
    status(st, "cho danh gia", msg, 0.0)
    log(msg)
    subprocess.call(["notify-send", "-u", "critical", "GoVoice: can Claude danh gia", what])
    while key not in decisions():
        time.sleep(300)
    log(f"da co quyet dinh '{key}': {decisions()[key]}")
    return decisions()[key]


def stage_analyze(st):
    """CHI THU SO LIEU (khong tu chon): eval2d tung seed (cam bien thuc te + hoan hao) va phan tich
    bu tru giua seed tot nhat moi thuat toan. Claude doc results/RL_ANALYSIS.md roi quyet."""
    status(st, "analyze", "eval2d + bu tru (thu so lieu)", 2.2 + 11.5)
    report = ["# So lieu RL (4096 tinh huong / lan danh gia) - de Claude danh gia", ""]
    best = {}
    for algo in ("ppo", "td3", "sac"):
        scores = []
        for seed in (0, 1, 2):
            d = os.path.join(ROOT, "rl_nav", "runs", f"{algo}_r_s{seed}")
            f = os.path.join(d, "best.npz") if os.path.exists(os.path.join(d, "best.npz")) else os.path.join(d, "policy.npz")
            if not os.path.exists(f):
                continue
            for real in (True, False):
                out = subprocess.run([PY, "rl_nav/eval2d.py", f] + (["--realistic"] if real else []), cwd=ROOT,
                                     capture_output=True, text=True, timeout=1800).stdout
                line = [l for l in out.splitlines() if "%" in l and "[" in l]
                report.append(f"- {algo} s{seed} {'thuc te ' if real else 'hoan hao'}: {line[0].strip() if line else out[-200:]}")
                m = re.search(r"\s([\d.]+)% \[", out)
                if real and m:
                    scores.append((float(m.group(1)), f))
        if scores:
            best[algo] = max(scores)[1]
    args = [f"{a}={f}" for a, f in best.items()]
    out = subprocess.run([PY, "rl_nav/complement.py", *args, "--realistic"], cwd=ROOT, capture_output=True,
                         text=True, timeout=3600).stdout
    report += ["", "## Bu tru giua seed tot nhat moi thuat toan (ghep cap, cam bien thuc te)", "```", out.strip(), "```",
               "", "Log train: rl_nav/runs/<algo>_r_s<seed>/log.csv"]
    open(os.path.join(ROOT, "results", "RL_ANALYSIS.md"), "w").write("\n".join(report) + "\n")
    st["analyze_done"] = True
    save(st)


def stage_select(st):
    """Cai dat policy theo quyet dinh cua Claude, roi CHAY cac cau hinh PRISM Claude muon so
    (2 lan lap). Khong tu chon."""
    rl = wait_for(st, "rl", "doc results/RL_ANALYSIS.md, chon policy/ghep")
    if not st.get("rl_installed"):
        os.makedirs(os.path.join(ROOT, "rl_nav", "old"), exist_ok=True)
        dst = {"ppo": "policy_nav.npz", "td3": "policy_nav_td3.npz", "sac": "policy_nav_sac.npz"}
        for algo, f in (rl.get("install") or {}).items():
            tgt = os.path.join(ROOT, "rl_nav", dst[algo])
            if os.path.exists(tgt):
                shutil.copy(tgt, os.path.join(ROOT, "rl_nav", "old", time.strftime("%m%d_") + dst[algo]))
            shutil.copy(f, tgt)
        if rl.get("value_from"):
            run([PY, "rl_nav/export_value.py", rl["value_from"], "rl_nav/value_nav.npz"], "analyze.log")
        st["rl_installed"] = True
        save(st)
    cfgs = wait_for(st, "select_configs", "chon cac cau hinh PRISM can thu")
    out = st.setdefault("select_dir", os.path.join(ROOT, "results", "select_prism_priors"))
    save(st)
    kill_sim()                                                  # sim sang loc (kenh mac dinh) khong can nua
    if eval_parallel(st, "select", "office", cfgs, 2, out, "voice_office", "select", 9.0):
        st["select_done"] = True
        save(st)


def stage_final(st):
    """Luot CHINH THUC voi danh sach cau hinh + so lan lap Claude da chon sau khi xem buoc select."""
    fin = wait_for(st, "final", "xem results/select_prism_priors_w*, chon PRISM cuoi + danh sach so sanh")
    out = st.setdefault("final_dir", os.path.join(ROOT, "results", "final_office"))
    st["final_configs"] = fin["configs"]
    save(st)
    kill_sim()
    ok = eval_parallel(st, "final", "office", fin["configs"], int(fin.get("trials", 5)), out,
                       "voice_office", "final", 2.5)
    # THEM: bo bai NHA NHO (nav, an toan, ne vong, nguoi) cho cac thuat toan chinh -> 2 moi truong
    hc = fin.get("house_configs") or []
    if ok and hc:
        ok = eval_parallel(st, "final_house", "single", hc, int(fin.get("house_trials", 3)),
                           out + "_house", "voice_house", "final (nha nho)", 0.1, only=HOUSE_ONLY)
    if ok:
        st["final_done"] = True
        save(st)


def merge_dirs(outbase, dst):
    """Gop <outbase>_w*/trials.csv (2 sim) thanh <dst>/trials.csv."""
    os.makedirs(dst, exist_ok=True)
    rows, fields = [], None
    for f in sorted(glob.glob(outbase + "_w*/trials.csv")):
        r = list(csv.DictReader(open(f)))
        if r:
            fields = fields or list(r[0].keys())
            rows += r
    if fields:
        with open(os.path.join(dst, "trials.csv"), "w", newline="") as fo:
            w = csv.DictWriter(fo, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
    return dst


def stage_report(st):
    kill_sim()
    for w in WORKERS:
        kill_worker(w)
    fd = merge_dirs(st["final_dir"], st["final_dir"] + "_merged")
    run([PY, os.path.join(P, "report.py"), fd, st["final_configs"][0]], "report.log", timeout=1800)
    if glob.glob(st["final_dir"] + "_house_w*/trials.csv"):
        hd = merge_dirs(st["final_dir"] + "_house", st["final_dir"] + "_house_merged")
        run([PY, os.path.join(P, "report.py"), hd, st["final_configs"][0]], "report.log", timeout=1800)
    st["report_done"] = True
    save(st)
    status(st, "xong", "DA CHAY XONG - so lieu o results/FINAL_REPORT_*.md, cho Claude danh gia ket luan", 0.0)
    subprocess.call(["notify-send", "-u", "critical", "GoVoice: da chay xong",
                     "So lieu o results/FINAL_REPORT_*.md - mo Claude de danh gia va chon"])
    log("XONG TAT CA")
    subprocess.call(["systemctl", "--user", "disable", "govoice-pipeline"])   # khong tu chay nua


def main():
    def stop(*_):
        log("nhan tin hieu dung (tat may?) - dung cac tien trinh con, lan sau se tiep tuc")
        for p in list(CHILD):
            try:
                os.killpg(p.pid, signal.SIGINT)
            except Exception:                                  # noqa: BLE001
                pass
        time.sleep(3)
        kill_sim()
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    st = load()
    log("=== pipeline bat dau / tiep tuc ===")
    # TANG TOC: train RL (GPU + 1 luong CPU) SONG SONG voi sang loc Gazebo (may con du: 16 luong,
    # GPU ~40 %). Ca 9 lan train cung chiu tai nen nhu nhau -> van cong bang voi nhau.
    import threading
    def train_bg():
        while not load().get("train_done"):
            stage_train(load(), concurrent=True)
            if not load().get("train_done"):
                time.sleep(60)
    tb = threading.Thread(target=train_bg, daemon=True)
    if not st.get("train_done"):
        tb.start()
    while not st.get("screen_done"):
        stage_screen(st)
        st = load()
        if not st.get("screen_done"):
            time.sleep(120)
    if tb.is_alive():
        log("sang loc xong - cho train RL xong")
        tb.join()
    st = load()
    for name, fn in (("screen", stage_screen), ("train", stage_train), ("analyze", stage_analyze),
                     ("select", stage_select), ("final", stage_final), ("report", stage_report)):
        while not st.get(name + "_done"):
            fn(st)
            st = load()
            if not st.get(name + "_done"):
                log(f"[{name}] chua xong - doi 2 phut roi thu lai")
                time.sleep(120)
    log("pipeline: khong con viec")


if __name__ == "__main__":
    main()
