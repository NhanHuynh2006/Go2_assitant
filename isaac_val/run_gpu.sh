#!/bin/bash
# 23/11 b2: cong RAM 5.0 GB (dinh Isaac do duoc 3.3 GB), watchdog giet Isaac neu MemAvailable < 1.0 GB, nice 10
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
source ~/isaac/env_isaaclab/bin/activate
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1 GATE_MB=5120
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date +%T) WATCHDOG ram=$m giet $p" >> watchdog.log; done; fi; sleep 1; done ) & WD=$!
run() { n=$1; shift; ~/isaac/gate.sh 120 >> gate.log
 ( while sleep 2; do echo "$(date +%T) $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits|tr -d ,) $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) $(ps -eo rss,args | grep 'sysid_isaa[c]' | sort -rn | head -1 | awk '{print int($1/1024)}')"; done > mon_$n.log ) & M=$!
 timeout 2400 nice -n 10 python sysid_isaac.py --headless "$@" > log_$n.log 2>&1; echo "rc=$? $n" >> run_done.log; kill $M; sleep 5; }
run flat_noise --device cuda:0 --policy flat --test steps --num_envs 62 --reps 6 --noise --seed 1 --out raw_flat_noise_steps.npz
run rough_noise --device cuda:0 --policy rough --test steps --num_envs 62 --reps 6 --noise --seed 1 --out raw_rough_noise_steps.npz
echo ALLDONE >> run_done.log
# thu giao dien IsaacSim (chuc nang, KHONG ket luan): 1 robot rough, PhysX CPU, 3 seed DEV
~/isaac/gate.sh 120 >> gate.log
S=/tmp/isaac_body_$$.sock
timeout 2400 nice -n 10 python body_server.py --headless --device cpu --policy rough --num_envs 1 --sock $S > log_server.log 2>&1 & P=$!
for i in $(seq 120); do grep -q "san sang" log_server.log && break; sleep 2; done
deactivate; cd ..
rm -f isaac_val/smoke_nav.csv
timeout 1800 nice -n 10 venv/bin/python isaac_val/isaac_sim.py --sock $S --seeds 0-2 --configs mppi --out isaac_val/smoke_nav.csv > isaac_val/log_nav.log 2>&1
for b in champ champ2 real; do timeout 900 nice -n 10 venv/bin/python isaac_val/isaac_sim.py --sock x --body $b --seeds 0-2 --configs mppi --out isaac_val/smoke_nav.csv >> isaac_val/log_nav.log 2>&1; done
kill $P; echo NAVDONE >> isaac_val/run_done.log; kill $WD
