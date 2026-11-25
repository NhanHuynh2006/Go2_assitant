#!/bin/bash
# Nhanh Isaac TEST (PREREG_TEST §3 + Lech #3): 4 robot, nice 19, nhan 10-15, server v3, rough + nhieu, 600 the gioi x 4 cau hinh.
D=/home/nhanhuynh/Documents/Go2_assitant; O=$D/results/ISAAC_TEST; cd $D
[ -e $O ] && [ -n "$(ls -A $O)" ] && { echo "thu muc ra khong rong: $O"; exit 1; }
mkdir -p $O; G=$O/guard.log
log() { echo "$(date '+%F %T') $*" >> $G; }
sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > $O/sha_start.txt 2>&1 || { log "SHA LECH -> khong chay"; exit 1; }
log "sha OK ($(grep -c ': OK' $O/sha_start.txt) tep); test_arm.py $(sha256sum isaac_val/test_arm.py | cut -c1-16) test_worlds.json $(sha256sum isaac_val/test_worlds.json | cut -c1-16)"
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
TS="taskset -c 10-15 nice -n 19"
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date '+%F %T') WATCHDOG ram=$m giet $p" >> $G; done; fi; sleep 1; done ) & WD=$!
GP=$(nvidia-smi --query-compute-apps=name --format=csv,noheader | grep -ci python); DEV=cuda:0; [ "$GP" != 0 ] && DEV=cpu
S=/tmp/isaac_body_TEST_$$.sock
( cd $D/isaac_val; source ~/isaac/env_isaaclab/bin/activate; exec $TS python body_server.py --headless --device $DEV --policy rough --noise --num_envs 4 --expect 4 --sock $S ) > $O/server.log 2>&1 & P=$!
for i in $(seq 300); do grep -q "san sang" $O/server.log && break; kill -0 $P 2>/dev/null || break; sleep 2; done
grep -q "san sang" $O/server.log || { log "SERVER FAIL"; kill -9 $P $WD; exit 1; }
log "server $DEV pid $P"
CFG="p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5,mppi~t3~nl:ppl=100;ppl_len=0.5,pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000,dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"
CP=""
for i in 0 1 2 3; do
  $TS venv/bin/python isaac_val/test_arm.py --sock $S --shard $i/4 --configs "$CFG" --out $O/res.csv > $O/client_$i.log 2>&1 &
  CP="$CP $!"; sleep 1
done
echo "$P $CP" > $O/pids
log "client$CP"
# canh RTF Gazebo + sha moi 15 phut; dung/tiep Isaac bang SIGSTOP/SIGCONT theo PID
( paused=0; t_p=0
  while true; do
    alive=0; for q in $CP; do kill -0 $q 2>/dev/null && alive=1; done; [ $alive = 0 ] && break
    sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > /dev/null 2>&1 || { log "SHA LECH giua chung -> dung"; kill -STOP $P $CP; }
    if [ $paused = 0 ]; then
      read med mean n tm <<< "$(python3 isaac_val/gz_rtf.py 4)"
      log "rtf Gazebo 4 luot moi nhat: med $med mean $mean (n $n); isaac $(grep -c '^isaac' $O/res.csv 2>/dev/null) luot"
      if python3 -c "import sys; sys.exit(0 if (float('$med')<0.9 or float('$mean')<0.9) else 1)" 2>/dev/null; then
        kill -STOP $P $CP; paused=1; t_p=$(date +%s); log "TAM DUNG Isaac (SIGSTOP $P$CP)"; fi
      sleep 900
    else
      read med mean n tm <<< "$(python3 isaac_val/gz_rtf.py 4 $t_p)"
      if [ "$n" -ge 2 ] && python3 -c "import sys; sys.exit(0 if (float('$med')>=0.9 and float('$mean')>=0.9) else 1)"; then
        kill -CONT $P $CP; paused=0; log "TIEP TUC Isaac: $n luot Gazebo moi sau khi dung, med $med mean $mean"
      else log "van dung: $n luot moi, med $med mean $mean"; fi
      sleep 120
    fi
  done ) &
GU=$!
for q in $CP; do while kill -0 $q 2>/dev/null; do sleep 20; done; done
log "client xong: $(grep -c '^isaac' $O/res.csv) luot"
kill $GU 2>/dev/null; kill -9 $P $WD 2>/dev/null; rm -f $S
sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > $O/sha_end.txt 2>&1 && log "sha cuoi OK" || log "SHA CUOI LECH"
log "XONG"
