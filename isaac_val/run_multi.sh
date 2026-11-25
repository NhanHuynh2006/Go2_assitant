#!/bin/bash
# run_multi.sh TAG N "client args..."  : 1 server Isaac (N robot) + N client, tat ca trong 3 nhan 13-15, nice 10, cong RAM + watchdog 1 GB.
# GPU neu khong co python nao khac tren GPU (MODEL), nguoc lai PhysX CPU.
TAG=$1; N=$2; shift 2; ARGS="$*"
D=/home/nhanhuynh/Documents/Go2_assitant; cd $D/isaac_val
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 GATE_MB=5120
TS="taskset -c 13-15 nice -n 10"
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date +%T) WATCHDOG ram=$m giet $p" >> watchdog.log; done; fi; sleep 1; done ) & WD=$!
~/isaac/gate.sh 120 >> gate.log
G=$(nvidia-smi --query-compute-apps=name --format=csv,noheader | grep -ci python)
DEV=cuda:0; [ "$G" != 0 ] && DEV=cpu
S=/tmp/isaac_body_${TAG}_$$.sock
( source ~/isaac/env_isaaclab/bin/activate; exec $TS python body_server.py --headless --device $DEV --policy rough --noise --num_envs $N --sock $S ) > log_srv_$TAG.log 2>&1 & P=$!
( while sleep 5; do echo "$(date +%T) $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) $(ps -o rss= -p $P $(pgrep -P $P) 2>/dev/null | awk '{s+=$1} END{print int(s/1024)}')"; done ) > mon_$TAG.log & M=$!
for i in $(seq 300); do grep -q "san sang" log_srv_$TAG.log && break; kill -0 $P 2>/dev/null || break; sleep 2; done
if ! grep -q "san sang" log_srv_$TAG.log; then echo "$TAG SERVER FAIL $(date +%T)" >> $D/isaac_val/run_done.log; kill -9 $P $M $WD 2>/dev/null; exit 1; fi
T0=$(date +%s)
cd $D
for i in $(seq 0 $((N-1))); do
  $TS venv/bin/python isaac_val/isaac_sim.py --sock $S --shard $i/$N --out isaac_val/res_$TAG.csv $ARGS > isaac_val/log_cli_${TAG}_$i.log 2>&1 &
  sleep 1
done
wait $(jobs -p | grep -v -e "^$P$" -e "^$M$" -e "^$WD$") 2>/dev/null
for j in $(pgrep -f "isaac_sim.py --sock $S"); do wait $j 2>/dev/null; done
while pgrep -f "isaac_sim.py --sock $S" > /dev/null; do sleep 5; done
echo "$TAG N=$N dev=$DEV wall=$(( $(date +%s) - T0 )) s" >> $D/isaac_val/run_done.log
kill $P $M $WD 2>/dev/null; sleep 3; for q in $(pgrep -f "body_server.py .*--sock $S"); do kill -9 $q; done; sleep 3; rm -f $S
