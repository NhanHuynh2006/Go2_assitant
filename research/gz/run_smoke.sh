#!/bin/bash
# GAZEBO: kiem khoi PREREG_TEST §4 (CHI DEV). 2 sim song song, moi sim 1 kenh rieng (GZ_PARTITION + ROS_DOMAIN_ID):
#   sim gzs0: voice_office.sdf  -> eval_sim --suite office (8 bai) x 2 lan x {C1, B1}         -> $OUT/office
#   sim gzs1: audit/out/gztest_dev/group_000.sdf (seed 0-3) -> research/gz/run_gz_groups.sh (eval_sim --suite gztest) x {C1, B1} -> $OUT/gz4/g000
# bash research/gz/run_smoke.sh [OUT=results/GZ_smoke]
# Dung: python3 pipeline/kill_partition.py gzs0 ; ... gzs1   (tat theo PID qua bien moi truong, khong pkill mau)
source /opt/ros/lyrical/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
export DISPLAY=${DISPLAY:-:0} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
cd "$(dirname "$0")/../.."
ROOT=$PWD
OUT=${1:-results/GZ_smoke}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 \
       RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST GZ_IP=127.0.0.1 \
       GOVOICE_FAST_SO=$ROOT/research/algo_fast/fast.so
C1='p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5'
B1='mppi~t3~nl:ppl=100;ppl_len=0.5'
mkdir -p "$OUT/simlog"
SHAFILE=${SHAFILE:-research/gz/SHA256SUMS_TEST.proposed}      # = SHA256SUMS_TEST voi eval_sim.py moi (24/11)
sha256sum -c --quiet "$SHAFILE" || { echo "SHA MISMATCH"; exit 1; }

start_sim() {   # $1 kenh, $2 domain, $3 world
  python3 pipeline/kill_partition.py "$1" >/dev/null
  ( cd "$HOME/ros2_ws" && env GZ_PARTITION=$1 ROS_DOMAIN_ID=$2 setsid ros2 launch go2_voice voice_sim.launch.py \
      headless:=true rviz:=false world:="$3" > "$ROOT/$OUT/simlog/sim_$1.log" 2>&1 & )
  for i in $(seq 80); do
    sleep 3
    env GZ_PARTITION=$1 ROS_DOMAIN_ID=$2 gz service -l 2>/dev/null | grep -q "/world/voice_office/set_pose" && { sleep 30; echo "$(date +%T) sim $1 san sang"; return 0; }
  done
  echo "$(date +%T) sim $1 KHONG len"; return 1
}

run_eval() {    # $1 kenh, $2 domain, $3 out, rest = args
  local P=$1 D=$2 O=$3; shift 3
  env GZ_PARTITION=$P ROS_DOMAIN_ID=$D venv/bin/python -u eval_sim.py "$@" --configs "$C1" "$B1" --out "$O" --sha-file "$SHAFILE" \
      > "$O.log" 2>&1
  echo "$(date +%T) eval $P xong (ma $?)"
}

( start_sim gzs0 41 voice_office.sdf && mkdir -p "$OUT/office" && \
  run_eval gzs0 41 "$OUT/office" --suite office --trials 2 ; python3 pipeline/kill_partition.py gzs0 ) &
A=$!
sleep 20
( SHAFILE=$SHAFILE bash research/gz/run_gz_groups.sh audit/out/gztest_dev "$OUT/gz4" gzs1 42 "0" > "$OUT/gz4.log" 2>&1 ) &
B=$!
wait $A $B
cp "$OUT/office.log" "$OUT/office/eval.log" 2>/dev/null
venv/bin/python research/gz/smoke_check.py "$OUT/office" "$OUT/gz4/g000" > "$OUT/smoke_check.txt" 2>&1
echo SMOKEDONE
