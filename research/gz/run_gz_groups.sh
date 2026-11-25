#!/bin/bash
# GAZEBO: chay file nhom cua audit/gen_gazebo_test.py tren MOT sim (kenh rieng). Dung cho kiem khoi (DEV) va TEST (dieu phoi vien).
#   bash research/gz/run_gz_groups.sh TASKDIR OUTBASE KENH DOMAIN "G1 G2 ..." [--allow-test]
#   env: CONFIGS (mac dinh "C1 B1" day du), SHAFILE (mac dinh results/frozen_C1/SHA256SUMS_TEST), TRIALS (1)
# Moi nhom: kiem sha256 -> bat sim voi TASKDIR/group_<G>.sdf -> eval_sim --suite gztest --group G -> OUTBASE/g<G>/
# Thieu luot (sim sap/treo) -> bat lai sim, --resume; toi da 2 lan chay lai (PREREG_TEST §5). Tat sim theo PID (kill_partition).
source /opt/ros/lyrical/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
export DISPLAY=${DISPLAY:-:0} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
cd "$(dirname "$0")/../.."
ROOT=$PWD
TASKDIR=$1; OUTBASE=$2; PART=$3; DOM=$4; GROUPS_=$5; ALLOW=$6
SHAFILE=${SHAFILE:-results/frozen_C1/SHA256SUMS_TEST}
TRIALS=${TRIALS:-1}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 \
       RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST GZ_IP=127.0.0.1 \
       GOVOICE_FAST_SO=$ROOT/research/algo_fast/fast.so
if [ -z "$CONFIGS" ]; then
  CFG=('p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' 'mppi~t3~nl:ppl=100;ppl_len=0.5')
else
  read -r -a CFG <<< "$CONFIGS"
fi
mkdir -p "$OUTBASE/simlog"

start_sim() {   # $1 world
  python3 pipeline/kill_partition.py "$PART" >/dev/null
  ( cd "$HOME/ros2_ws" && env GZ_PARTITION=$PART ROS_DOMAIN_ID=$DOM setsid ros2 launch go2_voice voice_sim.launch.py \
      headless:=true rviz:=false world:="$1" >> "$ROOT/$OUTBASE/simlog/sim_$PART.log" 2>&1 & )
  for i in $(seq 80); do
    sleep 3
    env GZ_PARTITION=$PART ROS_DOMAIN_ID=$DOM gz service -l 2>/dev/null | grep -q "/world/voice_office/set_pose" && { sleep 30; return 0; }
  done
  return 1
}

for G in $GROUPS_; do
  GF=$(printf "%s/group_%03d.sdf" "$TASKDIR" "$G"); O=$(printf "%s/g%03d" "$OUTBASE" "$G")
  NEED=$(python3 -c "import json,sys; print(sum(1 for t in json.load(open('$TASKDIR/tasks.json')) if t['group']==$G) * ${#CFG[@]} * $TRIALS)")
  for att in 0 1 2; do
    sha256sum -c --quiet "$SHAFILE" || { echo "$(date +%T) g$G SHA LECH -> dung"; exit 1; }
    t0=$(date +%s)
    if ! start_sim "$ROOT/$GF"; then echo "$(date +%T) g$G sim KHONG len (lan $att)"; continue; fi
    echo "$(date +%T) g$G sim len sau $(( $(date +%s) - t0 )) s (lan $att)"
    RES=(); [ $att -gt 0 ] && RES=(--resume)
    mkdir -p "$O"
    env GZ_PARTITION=$PART ROS_DOMAIN_ID=$DOM venv/bin/python -u eval_sim.py --suite gztest --tasks "$TASKDIR/tasks.json" \
        --group "$G" --trials "$TRIALS" --configs "${CFG[@]}" --out "$O" --sha-file "$SHAFILE" "${RES[@]}" $ALLOW \
        >> "$O/eval.log" 2>&1
    code=$?
    python3 pipeline/kill_partition.py "$PART" >/dev/null
    HAVE=$(python3 -c "import csv; print(len(list(csv.DictReader(open('$O/trials.csv')))))" 2>/dev/null || echo 0)
    echo "$(date +%T) g$G eval ma $code, $HAVE/$NEED luot, $(( $(date +%s) - t0 )) s"
    [ "$HAVE" -ge "$NEED" ] && break
  done
done
echo "GROUPSDONE $PART"
