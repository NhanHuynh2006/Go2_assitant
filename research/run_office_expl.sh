#!/bin/bash
# THAM DO (25/11 22:10, sau TEST): suite office (voice_office 32x22 m, ban do lon nhieu do dac) - C1 co ket o duong dai nhieu vat?
# $1 = partition, $2 = domain, $3 = --only list, $4 = out
source /opt/ros/lyrical/setup.bash; source "$HOME/ros2_ws/install/setup.bash"
cd "$(dirname "$0")/.."
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST GZ_IP=127.0.0.1 OPENBLAS_NUM_THREADS=1 \
       PYTHONUNBUFFERED=1 GOVOICE_FAST_SO=$PWD/research/algo_fast/fast.so GZ_PARTITION=$1 ROS_DOMAIN_ID=$2
python3 pipeline/kill_partition.py $1 >/dev/null
( cd "$HOME/ros2_ws" && setsid ros2 launch go2_voice voice_sim.launch.py headless:=true rviz:=false world:=voice_office.sdf > "$OLDPWD/$4.sim.log" 2>&1 & )
for i in $(seq 80); do sleep 3; gz service -l 2>/dev/null | grep -q "/world/voice_office/set_pose" && break; done; sleep 25
venv/bin/python -u eval_sim.py --suite office --only "$3" --trials 3 --out "$4" --resume \
  --configs "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5" "mppi~t3~nl:ppl=100;ppl_len=0.5" "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05" \
  > "$4.eval.log" 2>&1
python3 pipeline/kill_partition.py $1 >/dev/null
echo "XONG $1"
