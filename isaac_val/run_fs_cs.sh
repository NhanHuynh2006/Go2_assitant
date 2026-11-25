#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant
until grep -q FSLOG2DONE isaac_val/run_done.log; do sleep 30; done
export OPENBLAS_NUM_THREADS=1
taskset -c 13-15 nice -n 10 venv/bin/python isaac_val/isaac_sim.py --body go2 --shaper --seeds 302-439 --only crowd --n 100 \
  --configs "mppi~t3~nl:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5" --out isaac_val/res_fscs_go2.csv > isaac_val/log_fscs.log 2>&1
echo FSCSDONE >> isaac_val/run_done.log
