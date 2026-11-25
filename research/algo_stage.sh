#!/bin/bash
# XAC NHAN tren seed 300-799 (ung vien chot truoc; tiep tuc tu cho dung, fastsim bo qua luot da xong)
cd "$(dirname "$0")"
export J=10
C1="p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"; C2="p3+geo-haz~t3~nl"; B1="mppi~t3~nl:ppl=100;ppl_len=0.5"; B2="mppi~t3:ppl=100;ppl_len=0.5"; B0="mppi:ppl=32"
for rg in go2 champ2; do
  export EXTRA="--regime $rg --crowd-model helb"
  ./algo_run.sh algo_V${rg}_helb 300-799 "$C1" "$C2" "$B1" "$B2" "$B0"
done
export EXTRA="--regime champ"
./algo_run.sh algo_Vchamp_base 300-799 "$C1" "$C2" "$B1" "$B2" "$B0" "dwa~t3~nl:ppl=100;ppl_len=0.3" "log_mppi~t3~nl:ppl=100;ppl_len=0.5"
