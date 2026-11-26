#!/bin/bash
# start_stack.sh (REALPREP) - CHAY TREN ORIN CUA CHO. Bat bridge (CO kep toc do) + cam bien cho deploy/real_trial.py.
#
#   VX=0.20 VY=0.15 WZ=0.40 MERGED=1 DEPTH=0 bash deploy/start_stack.sh      # chay thu (shakedown)
#   VX=0.30 VY=0.15 WZ=0.50 MERGED=1 DEPTH=0 bash deploy/start_stack.sh      # thi nghiem chinh (vy 0.15: sua doi #1 REAL_PREREG, 26/11)
#   bash deploy/start_stack.sh stop                                         # dung MOI tien trinh do script nay bat (theo PID)
#
# Gioi han CUNG: script tu choi VX > 0.35, VY > 0.30, WZ > 0.80 (REAL_PREREG §3).
# Moi truong giong tools/scan_map_fused.sh cua repo ROS: ROS_DOMAIN_ID=1, Cyclone o ~/go2_bridge/cyclonedds_go2.xml.
set -u
VX=${VX:-0.20}; VY=${VY:-0.15}; WZ=${WZ:-0.40}; MERGED=${MERGED:-1}; DEPTH=${DEPTH:-0}; READONLY=${READONLY:-0}
# READONLY=1: bridge KHONG --allow-motion (ghi bag 10 phut, phien do dong hoc dyn/sysid_real.py)
PIDS=$HOME/realprep/pids; mkdir -p "$PIDS" "$HOME/realprep/logs"; LOG=$HOME/realprep/logs
source /opt/ros/foxy/setup.bash
source ~/cyclonedds_ws/install/local_setup.bash 2>/dev/null || echo "CANH BAO: khong co cyclonedds_ws (Cyclone cua Foxy khong doc <Interfaces>)"
source ~/go2_ws/install/setup.bash 2>/dev/null || echo "CANH BAO: khong co ~/go2_ws (ouster_node / lidar_merge)"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-1}
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-file://$HOME/go2_bridge/cyclonedds_go2.xml}

stop_all() {
    for f in "$PIDS"/*.pid; do
        [ -f "$f" ] || continue
        p=$(cat "$f")
        # nhom tien trinh (setsid) -> TERM ca vo ros2 lan tien trinh con (memory: SIGINT khong dung ouster_node/lidar_merge)
        kill -TERM -- "-$p" 2>/dev/null || kill -TERM "$p" 2>/dev/null
        echo "TERM $(basename "$f" .pid) (pgid $p)"
        rm -f "$f"
    done
    sleep 2
    ps -o pid,args -C python3 | grep -E "go2_hardware_bridge|ouster_node|lidar_merge|realsense_node|caminfo_relay" || echo "khong con tien trinh nao"
}
if [ "${1:-}" == "stop" ]; then stop_all; exit 0; fi

awk -v a="$VX" -v b="$VY" -v c="$WZ" 'BEGIN{exit !(a<=0.35 && b<=0.30 && c<=0.80 && a>0 && b>0 && c>0)}' \
    || { echo "TU CHOI: cap ($VX, $VY, $WZ) vuot (0.35, 0.30, 0.80)"; exit 2; }
n=$(ps -o args -C python3 | grep -c go2_hardware_bridge)
[ "$n" = 0 ] || { echo "DA CO $n bridge dang chay (ps -o pid,args -C python3 | grep bridge). Tat bang PID truoc."; exit 2; }
for x in go2_auto tour_driver; do pgrep -f "$x" >/dev/null && { echo "DANG CHAY $x: tat truoc (2 nguon lenh)"; exit 2; }; done

start() {   # ten lenh...
    local name=$1; shift
    setsid nohup "$@" > "$LOG/$name.log" 2>&1 < /dev/null &
    echo $! > "$PIDS/$name.pid"
    echo "  $name pid $(cat "$PIDS/$name.pid") -> $LOG/$name.log"
}
if [ "$READONLY" == "1" ]; then
    echo "[1] bridge CHI DOC (khong --allow-motion), L1 10 Hz"
    start bridge bash "$HOME/go2_bridge/start_hardware_bridge.sh" --lidar-rate 10
else
    echo "[1] bridge --allow-motion, kep |vx|<=$VX |vy|<=$VY |wz|<=$WZ, L1 10 Hz, StopMove sau 0.5 s khong lenh"
    start bridge bash "$HOME/go2_bridge/start_hardware_bridge.sh" --allow-motion --lidar-rate 10 \
          --max-vx "$VX" --max-vy "$VY" --max-wz "$WZ" --cmd-timeout 0.5 --min-battery 25 --max-tilt 20
fi
sleep 8
if [ "$MERGED" == "1" ]; then
    echo "[2] OS1 + lidar_merge -> /go2/lidar/merged (OS1 PHAI dung nguon rieng: memory go2-orin-freeze-and-ouster)"
    [ -f ~/go2_maps/ouster_extrinsic.txt ] || echo "  CANH BAO: chua hieu chinh gia OS1 (~/go2_maps/ouster_extrinsic.txt) -> lidar_merge chi gop L1"
    start ouster_node ros2 run go2_perception ouster_node
    start lidar_merge ros2 run go2_perception lidar_merge
    sleep 6
fi
if [ "$DEPTH" == "1" ]; then
    if ros2 pkg prefix realsense2_camera >/dev/null 2>&1; then
        echo "[3] realsense2_camera depth 424x240@15 -> /camera/camera/depth/image_rect_raw (+camera_info)"
        start realsense ros2 launch realsense2_camera rs_launch.py camera_namespace:=camera camera_name:=camera \
            depth_module.profile:=424x240x15 enable_color:=false enable_gyro:=false enable_accel:=false
    else
        echo "[3] khong co realsense2_camera -> go2_perception realsense_node + caminfo_relay"
        echo "    (real_trial.py --depth-topic /go2/camera/aligned_depth/image_raw)"
        start realsense_node ros2 run go2_perception realsense_node
        start caminfo_relay python3 "$(dirname "$0")/caminfo_relay.py"
    fi
    sleep 6
fi
echo "--- kiem tan so (moi cai ~5 s)"
for t in /go2/odom /go2/imu/data /go2/lidar/points $( [ "$MERGED" == "1" ] && echo /go2/lidar/merged ); do
    printf "%-28s" "$t"; timeout 6 ros2 topic hz "$t" 2>/dev/null | grep -m1 "average rate" || echo "KHONG CO DU LIEU"
done
timeout 4 ros2 topic echo --once /go2/status 2>/dev/null | head -3
echo "Xong. Dung: bash deploy/start_stack.sh stop"
