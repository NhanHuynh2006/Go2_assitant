#!/bin/bash
# Dung chó ảo dậy khi bị lật trong Gazebo (giữ nguyên vị trí x, y và hướng mặt). Dùng: bash dung_cho_day.sh [ten_model]
source /opt/ros/lyrical/setup.bash; export GZ_IP=127.0.0.1
M=${1:-go2}
W=$(gz service -l 2>/dev/null | grep -o '/world/[^/]*/set_pose' | head -1 | cut -d/ -f3)
[ -z "$W" ] && { echo "Không thấy sim Gazebo đang chạy"; exit 1; }
read -r X Y Z < <(timeout 5 gz model -m "$M" -p 2>/dev/null | grep -A1 "XYZ" | tail -1 | tr -d '[]')
read -r R P YAW < <(timeout 5 gz model -m "$M" -p 2>/dev/null | grep -A2 "XYZ" | tail -1 | tr -d '[]')
[ -z "$X" ] && { echo "Không đọc được vị trí model $M"; exit 1; }
QZ=$(python3 -c "import math;print(math.sin($YAW/2))"); QW=$(python3 -c "import math;print(math.cos($YAW/2))")
gz service -s /world/$W/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
  --req "name: \"$M\", position: {x: $X, y: $Y, z: 0.34}, orientation: {z: $QZ, w: $QW}" >/dev/null && echo "Đã dựng $M dậy tại ($X, $Y)"
