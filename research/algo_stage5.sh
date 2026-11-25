#!/bin/bash
# XAC NHAN VONG 3: seed 1500-1999, chay MOT lan
cd "$(dirname "$0")"
export J=10
CF=("p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5" "p3-haz-grad~t3:ppl=64;ppl_len=0.5" "p3-haz-grad~t3~nl:ppl=100;ppl_len=0.5" "p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5;g_tau=99"
    "mppi~t3~nl:ppl=100;ppl_len=0.5" "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000" "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05")
for rg in go2 champ2 champ; do EXTRA="--regime $rg" ./algo_run.sh algo_Y${rg}_base 1500-1999 "${CF[@]}"; done
for rg in go2 champ2; do EXTRA="--regime $rg --crowd-model helb" ./algo_run.sh algo_Y${rg}_helb 1500-1999 "${CF[@]}"; done
