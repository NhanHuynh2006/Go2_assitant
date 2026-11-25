#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
until grep -q REPLAYDONE run_done.log; do sleep 30; done
NL="mppi~t3~nl:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
rm -f res_nlcs.csv res_nlcs_*.jsonl
./run_multi.sh nlcs 8 --seeds 302-439 --only crowd --n 100 --shaper --configs "$NL"
echo SHAPERDONE >> run_done.log
