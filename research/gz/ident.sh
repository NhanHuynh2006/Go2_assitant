#!/bin/bash
# GAZEBO: kiem fastsim bit-identical truoc/sau sua ha tang eval_sim (PREREG_TEST §0.4, §4)
# bash research/gz/ident.sh <tag>   -> results/GZ_ident/<tag>_<regime>_<crowd>/
cd "$(dirname "$0")/../.."
TAG=$1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 GOVOICE_FAST_SO=$PWD/research/algo_fast/fast.so
sha256sum -c --quiet results/frozen_C1/SHA256SUMS || { echo "SHA MISMATCH"; exit 1; }
C=('p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' 'mppi~t3~nl:ppl=100;ppl_len=0.5' 'pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000' 'dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05' 'mppi:ppl=32' 'dwa~t3~nl:ppl=100;ppl_len=0.3' 'log_mppi~t3~nl:ppl=100;ppl_len=0.5')
for cell in "champ base" "champ2 base" "go2 base" "champ2 helb" "go2 helb"; do
  set -- $cell
  O=results/GZ_ident/${TAG}_${1}_$2
  [ -e "$O" ] && { echo "$O ton tai -> bo qua (thu muc ra phai rong)"; continue; }
  nice -n 5 venv/bin/python fastsim.py --suite gen --seeds 0-20 --configs "${C[@]}" --regime $1 --crowd-model $2 --out $O --jobs ${JOBS:-2} > $O.log 2>&1
  echo "$(date +%T) done $TAG $cell"
done
echo IDENTDONE $TAG
