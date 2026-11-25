#!/bin/bash
# estop.sh (REALPREP) - DUNG MEM tu cua so SSH THU HAI (khi cua so chay real_trial.py khong phan hoi).
# Thu tu khuyen dung (REAL_PREREG §7): 1) remote L2+B (phanh cung, cho nam xuong); 2) gat can remote (bridge nhuong
# quyen ngay, robot theo remote); 3) Enter trong cua so real_trial; 4) script nay; 5) bash deploy/start_stack.sh stop.
#   bash deploy/estop.sh           # SIGINT real_trial (no tu _halt + thoat) roi gui 5 lenh 0 len /go2/cmd_vel
#   bash deploy/estop.sh --bridge  # them: TERM bridge (bridge goi StopMove khi tat)
set -u
source /opt/ros/foxy/setup.bash
source ~/cyclonedds_ws/install/local_setup.bash 2>/dev/null
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-1}
export CYCLONEDDS_URI=${CYCLONEDDS_URI:-file://$HOME/go2_bridge/cyclonedds_go2.xml}
f=$HOME/realprep/pids/real_trial.pid
if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
    echo "SIGINT real_trial pid $(cat "$f")"; kill -INT "$(cat "$f")"
fi
timeout 3 ros2 topic pub -r 10 -t 5 /go2/cmd_vel geometry_msgs/msg/Twist "{}" >/dev/null 2>&1
if [ "${1:-}" == "--bridge" ]; then
    f=$HOME/realprep/pids/bridge.pid
    [ -f "$f" ] && { echo "TERM bridge pgid $(cat "$f")"; kill -TERM -- "-$(cat "$f")"; rm -f "$f"; }
fi
ps -o pid,args -C python3 | grep -E "real_trial|go2_hardware_bridge" || echo "khong con real_trial / bridge"
