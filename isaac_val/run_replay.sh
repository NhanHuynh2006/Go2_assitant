#!/bin/bash
# phat lai 6 lan nga cua res_nl: chi shard 2 (toi vi tri 10), 5 (9), 7 (7); server van N=8 (5 cho con lai dung yen), cho du 3 client.
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
until grep -q FALLDONE run_done.log; do sleep 30; done
D=/home/nhanhuynh/Documents/Go2_assitant
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1 GATE_MB=5120
TS="taskset -c 13-15 nice -n 10"
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date +%T) WATCHDOG ram=$m giet $p" >> watchdog.log; done; fi; sleep 1; done ) & WD=$!
~/isaac/gate.sh 120 >> gate.log
S=/tmp/isaac_body_replay_$$.sock
rm -f res_nlfall.csv res_nlfall_*.jsonl
( source ~/isaac/env_isaaclab/bin/activate; exec $TS python body_server.py --headless --device cuda:0 --policy rough --noise --num_envs 8 --expect 3 --sock $S ) > log_srv_replay.log 2>&1 & P=$!
for i in $(seq 300); do grep -q "san sang" log_srv_replay.log && break; sleep 2; done
cd $D
NL="mppi~t3~nl:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
for sp in 2:10 5:9 7:7; do i=${sp%:*}; u=${sp#*:}
  $TS venv/bin/python isaac_val/isaac_sim.py --sock $S --seeds 302-439 --only crowd --n 100 --shard $i/8 --upto $u --configs "$NL" --out isaac_val/res_nlfall.csv > isaac_val/log_cli_replay_$i.log 2>&1 &
  sleep 1; done
while pgrep -f "isaac_sim.py --sock $S" > /dev/null; do sleep 5; done
kill -9 $P $WD 2>/dev/null; rm -f $S
echo REPLAYDONE >> isaac_val/run_done.log
