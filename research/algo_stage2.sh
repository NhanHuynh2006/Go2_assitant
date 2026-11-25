#!/bin/bash
cd "$(dirname "$0")"
export J=10
mapfile -t CF < algo_r2b_cfgs.txt
EXTRA="--regime champ" ./algo_run.sh algo_Dchamp 0-149 "${CF[@]}"
EXTRA="--regime go2" ./algo_run_oracle.sh algo_Pgo2 0-149 "p3+geo-haz+gcv~oca~nl:ppl=32;ppl_len=0.5" "p3+geo-haz+gcv~ocb~nl:ppl=32;ppl_len=0.5"
