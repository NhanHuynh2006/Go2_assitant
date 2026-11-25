#!/bin/bash
# XAC NHAN VONG 2: seed 1000-1499, chay MOT lan
cd "$(dirname "$0")"
while pgrep -f "fastsim.py --worker" > /dev/null; do sleep 5; done
export J=10
C1="p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"; B1="mppi~t3~nl:ppl=100;ppl_len=0.5"; B0="mppi:ppl=32"
PG="pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000"; DR="dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"
AB=("p3+geo-haz+gcv-grad~t3~nl:ppl=32;ppl_len=0.5" "p3+geo-haz+gcv-prim~t3~nl:ppl=32;ppl_len=0.5" "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5;g_tau=99" "p3+geo-haz+gcv~nl:ppl=32;ppl_len=0.5" "p3+geo-haz+gcv~t3:ppl=32;ppl_len=0.5" "p3-haz~t3~nl:ppl=32;ppl_len=0.5")
for rg in go2 champ2 champ; do
  EXTRA="--regime $rg" ./algo_run.sh algo_W${rg}_base 1000-1499 "$C1" "$B1" "$PG" "$DR" "$B0" "${AB[@]}"
done
for rg in go2 champ2; do
  EXTRA="--regime $rg --crowd-model helb" ./algo_run.sh algo_W${rg}_helb 1000-1499 "$C1" "$B1" "$PG" "$DR" "$B0"
done
