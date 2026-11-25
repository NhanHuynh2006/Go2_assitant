#!/bin/bash
# Lech #3 bo sung: khi Gazebo TEST xong -> dung lo N=4 (bo the gioi dang do dang), chay phan con lai voi N=8, khong ghim, nice 10.
D=/home/nhanhuynh/Documents/Go2_assitant; O=$D/results/ISAAC_TEST; G=$O/guard.log; cd $D
log() { echo "$(date '+%F %T') $*" >> $G; }
gzdone() { ! pgrep -f run_gz_groups > /dev/null && grep -q GROUPSDONE results/GZ_TEST_s0.log && grep -q GROUPSDONE results/GZ_TEST_s1.log; }
until gzdone || grep -q "XONG" $G; do sleep 300; done
if grep -q "XONG" $G && ! gzdone; then log "lo N=4 xong truoc Gazebo: khong can chuyen"; exit 0; fi
if grep -q "XONG" $G; then log "lo N=4 da xong het; khong con gi cho N=8"; exit 0; fi
read P C0 C1 C2 C3 < $O/pids
log "Gazebo TEST xong -> chuyen sang N=8 (dung lo N=4)"
kill -CONT $P $C0 $C1 $C2 $C3 2>/dev/null
kill $C0 $C1 $C2 $C3 2>/dev/null
until grep -q "XONG" $G; do sleep 10; done                 # run_test_arm.sh don server + sha cuoi
python3 - <<'P'
import csv, json, collections
O = "/home/nhanhuynh/Documents/Go2_assitant/results/ISAAC_TEST"
T = json.load(open("/home/nhanhuynh/Documents/Go2_assitant/isaac_val/test_worlds.json"))
rows = [r for r in csv.DictReader(open(O + "/res.csv")) if r["world"].isdigit()]
n = collections.Counter(int(r["world"]) for r in rows)
done = {w for w, k in n.items() if k >= 4}
part = sorted(w for w, k in n.items() if k < 4)
keep = [r for r in rows if int(r["world"]) in done]
with open(O + "/res_n4.csv", "w", newline="") as f:
    w = csv.DictWriter(f, list(rows[0].keys()) if rows else ["world"]); w.writeheader(); w.writerows(keep)
rest = [w for w in T if w not in done]
json.dump(rest, open("/home/nhanhuynh/Documents/Go2_assitant/isaac_val/test_worlds_rest.json", "w"))
json.dump(dict(n4_worlds=sorted(done), dropped_partial=part, n8_worlds=rest), open(O + "/split_N.json", "w"))
print(len(done), len(part), len(rest))
P
log "N=4: $(python3 -c "import json;d=json.load(open('$O/split_N.json'));print(len(d['n4_worlds']),'the gioi xong; bo do dang',d['dropped_partial'],'; con',len(d['n8_worlds']))")"
sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > $O/sha_n8_start.txt 2>&1 || { log "SHA LECH -> khong chay N=8"; exit 1; }
log "sha OK truoc N=8; test_arm_rest.py $(sha256sum isaac_val/test_arm_rest.py | cut -c1-16) rest.json $(sha256sum isaac_val/test_worlds_rest.json | cut -c1-16)"
export OMNI_KIT_ACCEPT_EULA=YES TERM=xterm OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
TS="nice -n 10"
( while true; do m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$m" -lt 1024 ]; then for p in $(pgrep -f "python[^ ]* (sysid_isaac|body_server)\.py"); do kill -9 $p; echo "$(date '+%F %T') WATCHDOG ram=$m giet $p" >> $G; done; fi; sleep 1; done ) & WD=$!
GP=$(nvidia-smi --query-compute-apps=name --format=csv,noheader | grep -ci python); DEV=cuda:0; [ "$GP" != 0 ] && DEV=cpu
S=/tmp/isaac_body_TEST8_$$.sock
( cd $D/isaac_val; source ~/isaac/env_isaaclab/bin/activate; exec $TS python body_server.py --headless --device $DEV --policy rough --noise --num_envs 8 --expect 8 --sock $S ) > $O/server_n8.log 2>&1 & P=$!
for i in $(seq 300); do grep -q "san sang" $O/server_n8.log && break; kill -0 $P 2>/dev/null || break; sleep 2; done
grep -q "san sang" $O/server_n8.log || { log "SERVER N=8 FAIL"; kill -9 $P $WD; exit 1; }
CFG="p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5,mppi~t3~nl:ppl=100;ppl_len=0.5,pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000,dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"
CP=""
for i in 0 1 2 3 4 5 6 7; do
  $TS venv/bin/python isaac_val/test_arm_rest.py --sock $S --shard $i/8 --configs "$CFG" --out $O/res_n8.csv > $O/client_n8_$i.log 2>&1 &
  CP="$CP $!"; sleep 1
done
echo "$P $CP" > $O/pids_n8; log "N=8 server $DEV $P, client$CP"
k=0; for q in $CP; do while kill -0 $q 2>/dev/null; do sleep 30; k=$((k+1)); [ $((k % 30)) = 0 ] && { sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > /dev/null 2>&1 || { log "SHA LECH giua chung N=8 -> dung"; kill -STOP $P $CP; }; log "N=8: $(grep -c '^isaac' $O/res_n8.csv) luot"; }; done; done
kill -9 $P $WD 2>/dev/null; rm -f $S
sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC > $O/sha_n8_end.txt 2>&1 && log "sha cuoi N=8 OK" || log "SHA CUOI N=8 LECH"
log "XONG N8: $(grep -c '^isaac' $O/res_n8.csv) luot"
