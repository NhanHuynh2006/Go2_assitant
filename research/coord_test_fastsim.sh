#!/bin/bash
# TEST fastsim (audit/PREREG_TEST.md §1): chay tu ban chup chi-doc, kiem sha truoc MOI o, thu muc ra phai rong.
set -e
R=/home/nhanhuynh/Documents/Go2_assitant
SNAP=$R/results/frozen_C1/snap
if [ ! -d $SNAP ]; then mkdir -p $SNAP && tar xzf $R/results/frozen_C1/code.tgz -C $SNAP && cp -a $R/venv $SNAP/venv 2>/dev/null || true; fi
cd $SNAP
export OPENBLAS_NUM_THREADS=1 GOVOICE_FAST_SO=$SNAP/research/algo_fast/fast.so
C=('p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' 'mppi~t3~nl:ppl=100;ppl_len=0.5' 'pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000' 'dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05' 'mppi:ppl=32' 'dwa~t3~nl:ppl=100;ppl_len=0.3' 'log_mppi~t3~nl:ppl=100;ppl_len=0.5')
SEEDS=${SEEDS:?dat SEEDS=100000-1xxxxx cho 1000 the gioi co nguoi dau tien}
for cell in "champ base" "champ2 base" "go2 base" "champ2 helb" "go2 helb"; do
  set -- $cell
  sha256sum -c --quiet $R/results/frozen_C1/SHA256SUMS_SNAP || { echo "SHA MISMATCH"; exit 1; }
  O=$R/results/TEST_${1}_$2; [ -e $O ] && { echo "$O da ton tai"; exit 1; }
  nice -n 5 $R/venv/bin/python fastsim.py --suite gen --seeds $SEEDS --crowd-only --configs "${C[@]}" --regime $1 --crowd-model $2 --out $O --jobs ${J:-14} > $O.log 2>&1
  echo "$(date +%T) done $cell"
done
echo TESTDONE
