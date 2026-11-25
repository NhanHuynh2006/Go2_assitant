#!/bin/bash
# VAL (coordinator): seed 2000-2399, 5 o, cau hinh dong bang research/FROZEN.md
cd "$(dirname "$0")/.."
sha256sum -c --quiet results/frozen_C1/SHA256SUMS || { echo "SHA MISMATCH"; exit 1; }
export OPENBLAS_NUM_THREADS=1 GOVOICE_FAST_SO=$PWD/research/algo_fast/fast.so
C=('p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' 'mppi~t3~nl:ppl=100;ppl_len=0.5' 'pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000' 'dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05' 'mppi:ppl=32' 'dwa~t3~nl:ppl=100;ppl_len=0.3' 'log_mppi~t3~nl:ppl=100;ppl_len=0.5')
for cell in "champ base" "champ2 base" "go2 base" "champ2 helb" "go2 helb"; do
  set -- $cell
  nice -n 5 venv/bin/python fastsim.py --suite gen --seeds 2000-2399 --crowd-only --configs "${C[@]}" --regime $1 --crowd-model $2 --out results/VAL_${1}_$2 --jobs 14 > results/VAL_${1}_$2.log 2>&1
  echo "$(date +%T) done $cell"
done
echo VALDONE
