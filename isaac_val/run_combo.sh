#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
source ~/isaac/env_isaaclab/bin/activate
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date +%T) WATCHDOG ram=$m giet $p" >> watchdog.log; done; fi; sleep 1; done ) & WD=$!
timeout 3000 taskset -c 13-15 nice -n 10 python sysid_isaac.py --headless --device cpu --policy rough --noise --test combo --num_envs 60 --reps 8 --seed 3 --out raw_rough_combo.npz > log_combo.log 2>&1
echo "rc=$? combo" >> run_done.log; kill $WD
