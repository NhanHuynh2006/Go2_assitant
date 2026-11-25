#!/bin/bash
cd /home/nhanhuynh/Documents/Go2_assitant/isaac_val
A="--seeds 302-439 --only crowd --n 8 --configs mppi"
./run_multi.sh b1 1 $A
./run_multi.sh b2 2 $A
./run_multi.sh b2r 2 $A
./run_multi.sh b4 4 $A
./run_multi.sh b8 8 $A
echo BENCHDONE >> run_done.log
