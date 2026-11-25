#!/bin/bash
# 24/11 v3 (rao chan + cho theo shard -> tat dinh voi cung N/chia). Cung 100 the gioi, N=8.
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
A="--seeds 302-439 --only crowd --n 100"
NL="mppi~t3~nl:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
T3="mppi~t3:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3:ppl=32;ppl_len=0.5"
rm -f res_nl.csv res_nl_*.jsonl res_t3.csv res_t3_*.jsonl res_nlnotilt.csv res_nlnotilt_*.jsonl res_nlrep.csv res_nlrep_*.jsonl
./run_multi.sh nl 8 $A --configs "$NL" || { rm -f res_nl.csv res_nl_*.jsonl; ./run_multi.sh nl 8 $A --configs "$NL"; }
./run_multi.sh nlrep 8 --seeds 302-439 --only crowd --n 32 --configs "$NL"
./run_multi.sh t3 8 $A --configs "$T3"
./run_multi.sh nlnotilt 8 $A --notilt --configs "$NL"
echo FALLDONE >> run_done.log
