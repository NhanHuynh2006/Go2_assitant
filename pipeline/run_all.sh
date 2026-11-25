#!/bin/bash
# Bao boc cho systemd: nap ROS + workspace, bien man hinh (gz render cam bien), chi 1 ban chay.
source /opt/ros/lyrical/setup.bash
source "$HOME/ros2_ws/install/setup.bash"
export DISPLAY=${DISPLAY:-:0} WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
cd "$HOME/Documents/Go2_assitant"
# chan may tu ngu khi pipeline dang chay (neu he thong cho phep)
if systemd-inhibit --what=idle:sleep --who=GoVoice --why=test true 2>/dev/null; then
  INH=(systemd-inhibit --what=idle:sleep --who=GoVoice --why="pipeline nghien cuu dang chay")
else
  INH=()
fi
exec "${INH[@]}" flock -n pipeline/.lock venv/bin/python -u pipeline/run_all.py
