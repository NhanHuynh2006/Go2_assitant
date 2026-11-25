#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant
export OPENBLAS_NUM_THREADS=1
taskset -c 13-15 nice -n 10 venv/bin/python isaac_val/isaac_sim.py --body go2 --seeds 302-439 --only crowd --n 100 \
  --configs "mppi,mppi:ppl=32,dwa" \
  --out isaac_val/res_fslog3_go2.csv > isaac_val/log_fslog3.log 2>&1
echo FSLOG3DONE >> isaac_val/run_done.log
