#!/bin/bash
# THAM DO (agent HM95): 4 cau hinh tren CUNG 1000 the gioi TEST fastsim (seed 100000-101386, crowd-only) voi nguoi hm95.
# Chay tu ban chup chi-doc qua research/hm95_fastsim.py; kiem sha ban chup truoc MOI o; thu muc ra phai rong.
# CPU: chi loi 10,11,14,15 (Gazebo chiem loi khac), nice 19, toi da 4 job.
set -e
R=/home/nhanhuynh/Documents/Go2_assitant
SNAP=$R/results/frozen_C1/snap
export OPENBLAS_NUM_THREADS=1 GOVOICE_FAST_SO=$SNAP/research/algo_fast/fast.so
C=('p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' 'mppi~t3~nl:ppl=100;ppl_len=0.5' 'pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000' 'dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05')
sha256sum $R/crowd_hm95.py $R/research/hm95_fastsim.py > $R/results/hm95_code.sha256
for g in go2 champ2; do
  (cd $SNAP && sha256sum -c --quiet $R/results/frozen_C1/SHA256SUMS_SNAP) || { echo "SHA MISMATCH"; exit 1; }
  sha256sum -c --quiet $R/results/hm95_code.sha256 || { echo "HM95 CODE CHANGED"; exit 1; }
  O=$R/results/TEST_hm95_$g; [ -e $O ] && { echo "$O da ton tai"; exit 1; }
  HM95_STATS=$O.stats.jsonl nice -n 19 taskset -c 10,11,14,15 $R/venv/bin/python $R/research/hm95_fastsim.py --suite gen --seeds 100000-101386 \
    --crowd-only --configs "${C[@]}" --regime $g --crowd-model hm95 --out $O --jobs 4 > $O.log 2>&1
  echo "$(date +%T) done $g"
done
(cd $SNAP && sha256sum -c --quiet $R/results/frozen_C1/SHA256SUMS_SNAP) && echo "SHA sau khi chay: OK"
echo HM95DONE
