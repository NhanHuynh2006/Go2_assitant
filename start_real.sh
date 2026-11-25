#!/bin/bash
# start_real.sh — CHAY TREN JETSON CUA GO2: bat bridge + D435i + GoVoice (du chuc nang).
#   bash start_real.sh            # noi qua mic robot
#   bash start_real.sh --text     # go phim (thu truoc cho chac)
# Can: ~/unitree_go2_ros2/go2_bringup/scripts/go2_hardware_bridge.py, realsense2_camera,
#      cyclonedds_ws (xem docs cua repo ROS va memory go2-robot-access).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
BRIDGE=${BRIDGE:-$HOME/unitree_go2_ros2/go2_bringup/scripts/go2_hardware_bridge.py}
source /opt/ros/foxy/setup.bash
source ~/cyclonedds_ws/install/local_setup.bash 2>/dev/null || true
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-file:///tmp/cyclonedds_both.xml}
LOG=/tmp/govoice_real; mkdir -p $LOG

echo "[1/3] go2_hardware_bridge (motion + L1 10 Hz)"
python3 "$BRIDGE" --allow-motion --lidar-rate 10 > $LOG/bridge.log 2>&1 &
BR=$!
echo "[2/3] RealSense D435i (depth 424x240 @15 Hz)"
ros2 launch realsense2_camera rs_launch.py camera_namespace:=camera camera_name:=camera \
    depth_module.profile:=424x240x15 enable_color:=true enable_gyro:=false enable_accel:=false \
    > $LOG/realsense.log 2>&1 &
RS=$!
trap "kill $BR $RS 2>/dev/null" EXIT
sleep 6
echo "[3/3] GoVoice (log: $LOG). Noi 'dừng lại' bat ky luc nao; remote L2+B = phanh cung."
cd "$HERE"
if [ "$1" == "--text" ]; then
    python3 run_real_ros.py
else
    export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH; export GO2_IP=${GO2_IP:-192.168.123.161}
    python3 go2_audio_bridge.py > $LOG/audio.log 2>&1 &
    AU=$!; trap "kill $BR $RS $AU 2>/dev/null" EXIT
    python3 run_real_ros.py --both --mic-robot     # noi qua mic robot + go phim trong ssh
fi
