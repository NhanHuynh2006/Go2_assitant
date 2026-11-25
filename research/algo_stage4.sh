#!/bin/bash
# VONG 3 - DEV seed 800-999 (champ2, go2, champ2 helb)
cd "$(dirname "$0")"
export J=10
C1="p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
CF=("$C1"
 "p3-haz-grad~t3:ppl=32;ppl_len=0.5" "p3-haz-grad~t3:ppl=64;ppl_len=0.5" "p3-haz-grad~t3:ppl=100;ppl_len=0.5" "p3-haz-grad~t3:ppl=32;ppl_len=0.3" "p3-haz-grad~t3:ppl=16;ppl_len=0.3"
 "p3-haz-grad~t3~nl:ppl=32;ppl_len=0.5" "p3-haz-grad~t3~nl:ppl=64;ppl_len=0.5" "p3-haz-grad~t3~nl:ppl=100;ppl_len=0.5"
 "p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5" "p3+geo-haz-grad+gcv~t3:ppl=16;ppl_len=0.3" "p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5;g_tau=99")
EXTRA="--regime champ2" ./algo_run.sh algo_Xchamp2_base 800-999 "${CF[@]}"
EXTRA="--regime go2" ./algo_run.sh algo_Xgo2_base 800-999 "${CF[@]}"
EXTRA="--regime champ2 --crowd-model helb" ./algo_run.sh algo_Xchamp2_helb 800-999 "${CF[@]}"
