#!/bin/bash
set -e
R=/home/nhanhuynh/Documents/Go2_assitant
export OPENBLAS_NUM_THREADS=1 GOVOICE_FAST_SO=$R/results/frozen_C1/snap/research/algo_fast/fast.so
for r in champ champ2 go2; do
  sha256sum -c --quiet $R/results/frozen_C1/SHA256SUMS_SNAP || { echo SHA MISMATCH; exit 1; }
  O=$R/results/TESTSTATIC_$r; [ -e $O ] && { echo "$O exists"; exit 1; }
  nice -n 5 $R/venv/bin/python $R/research/coord_test_static.py $r $O > $O.log 2>&1
  echo "$(date +%T) done $r"
done
echo STATICDONE
