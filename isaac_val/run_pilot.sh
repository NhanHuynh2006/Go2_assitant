#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
./run_multi.sh pilot 8 --seeds 302-439 --only crowd --n 100 --configs "mppi,mppi:ppl=32,dwa,mppi~t3~nl:ppl=100;ppl_len=0.5,p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
echo PILOTDONE >> run_done.log
