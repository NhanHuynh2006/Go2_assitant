#!/bin/bash
# kiem tat dinh v3: cung 8 the gioi, N=2 hai lan va N=4 (neu doc lap lich su -> giong nhau ca khi doi N)
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
A="--seeds 302-439 --only crowd --n 8 --configs p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5"
rm -f res_d2*.csv res_d4*.csv res_d2*.jsonl res_d4*.jsonl
./run_multi.sh d2 2 $A; ./run_multi.sh d2r 2 $A; ./run_multi.sh d4 4 $A
echo DETDONE >> run_done.log
