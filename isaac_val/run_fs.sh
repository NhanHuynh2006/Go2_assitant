#!/bin/bash
# fastsim ghep cap cho pilot: tat ca trong nhan 13-15, nice 10, --jobs 2
cd /home/nhanhuynh/Documents/Go2_assitant
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
TS="taskset -c 13-15 nice -n 10"
P3='p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5'; TB='mppi~t3~nl:ppl=100;ppl_len=0.5'
# 1) kiem dung lai so cua ALGO: 2 cau hinh, the gioi 300-330 co nguoi, go2
$TS venv/bin/python fastsim.py --suite gen --seeds 300-330 --crowd-only --configs mppi:ppl=32 "$P3" --regime go2 --jobs 2 --out results/isaac_fs_chk_go2 > isaac_val/log_fs_chk.log 2>&1
echo "fs_chk done" >> isaac_val/run_done.log
$TS venv/bin/python fastsim.py --suite gen --seeds 300-439 --crowd-only --configs mppi dwa --regime go2 --jobs 2 --out results/isaac_fs_go2 > isaac_val/log_fs_go2.log 2>&1
$TS venv/bin/python fastsim.py --suite gen --seeds 300-439 --crowd-only --configs mppi dwa --regime champ2 --jobs 2 --out results/isaac_fs_champ2 > isaac_val/log_fs_champ2.log 2>&1
$TS venv/bin/python fastsim.py --suite gen --seeds 300-439 --crowd-only --configs mppi mppi:ppl=32 dwa "$TB" "$P3" --regime champ --jobs 2 --out results/isaac_fs_champ > isaac_val/log_fs_champ.log 2>&1
echo "FSDONE" >> isaac_val/run_done.log
