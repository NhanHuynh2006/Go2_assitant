#!/bin/bash
# verify_on_dog.sh (REALPREP) - CHAY TREN ORIN CUA CHO, KHONG gui lenh chuyen dong nao. ~10-15 phut (bench).
#   cd ~/govoice_real && bash deploy/verify_on_dog.sh [--fast-so] [--skip-bench]
# Ghi ket qua vao ~/realprep/verify_<gio>.txt; dan file nay vao audit/REAL_PREREG.md §9 truoc luot dau.
set -u
cd "$(dirname "$0")/.."
OUT=$HOME/realprep/verify_$(date +%Y%m%d_%H%M%S).txt; mkdir -p "$HOME/realprep"
exec > >(tee "$OUT") 2>&1
ok=1; bad() { echo "  !! $*"; ok=0; }
echo "== 1. sha256 goi (deploy/MANIFEST.sha256)"
sha256sum -c --quiet deploy/MANIFEST.sha256 && echo "  OK moi file trong goi" || bad "file trong goi bi doi/thieu"
echo "== 2. file dong bang khop SHA256SUMS_TEST (cung so bam voi TEST fastsim/Gazebo)"
grep -F -f <(sed 's/^/  /' deploy/FROZEN_IN_BUNDLE.txt) results/frozen_C1/SHA256SUMS_TEST | sha256sum -c \
    && echo "  OK $(wc -l < deploy/FROZEN_IN_BUNDLE.txt) file dong bang" || bad "file dong bang KHONG khop"
echo "== 3. may / Python / thu vien"
echo "  $(uname -m) $(lsb_release -ds 2>/dev/null) L4T: $(head -1 /etc/nv_tegra_release 2>/dev/null)"
python3 - <<'EOF' || bad "python/numpy/scipy"
import sys, numpy, scipy, yaml
print("  python", sys.version.split()[0], "numpy", numpy.__version__, "scipy", scipy.__version__)
assert sys.version_info >= (3, 8)
assert tuple(int(x) for x in numpy.__version__.split(".")[:2]) >= (1, 17), "can numpy >= 1.17 (default_rng)"
EOF
python3 deploy/py38check.py nav_local.py nav_prism2.py robot_ros.py robot_real.py isaac_val/cmd_shaper.py \
    deploy/real_trial.py deploy/replay_perception.py deploy/bench_steps.py | grep -v " OK$" && bad "cu phap" || echo "  OK cu phap"
echo "== 4. ROS"
source /opt/ros/foxy/setup.bash 2>/dev/null || bad "khong co /opt/ros/foxy"
source ~/cyclonedds_ws/install/local_setup.bash 2>/dev/null || bad "khong co ~/cyclonedds_ws"
echo "  ROS_DISTRO=$ROS_DISTRO"
python3 -c "import rclpy, tf2_ros; from sensor_msgs.msg import PointCloud2, Image, CameraInfo, Imu; from nav_msgs.msg import Odometry, Path; from std_msgs.msg import String; print('  OK rclpy/tf2_ros/msgs')" || bad "rclpy/tf2_ros"
ros2 bag -h >/dev/null 2>&1 && echo "  OK ros2 bag" || bad "khong co ros2 bag (rosbag2)"
python3 deploy/real_trial.py --dry --out /tmp/rt_dry >/dev/null && echo "  OK real_trial --dry" || bad "real_trial --dry"
echo "== 5. dia trong (moi luot ~60-120 MB bag voi /go2/lidar/merged)"
df -h "$HOME" | tail -1
avail=$(df --output=avail -k "$HOME" | tail -1); [ "$avail" -gt 30000000 ] || bad "con < 30 GB"
echo "== 6. che do nguon Orin (memory: nvpmodel 0 + jetson_clocks)"
(nvpmodel -q 2>/dev/null | head -2) || echo "  (khong doc duoc nvpmodel)"
echo "== 7. tien trinh dang chay (KHONG duoc co go2_auto / tour_driver / 2 bridge)"
ps -o pid,args -C python3 | grep -E "bridge|go2_auto|tour_driver|real_trial|ouster|lidar_merge" || echo "  (khong co)"
if [ "${1:-}" == "--fast-so" ] || [ "${2:-}" == "--fast-so" ]; then
    echo "== 8a. dung fast.so cho aarch64 tu fast.c DA BAM (fast.so x86 trong goi KHONG dung duoc)"
    gcc -O3 -mcpu=native -ffp-contract=off -fPIC -shared research/algo_fast/fast.c -o research/algo_fast/fast_aarch64.so -lm \
        && sha256sum research/algo_fast/fast_aarch64.so || bad "gcc fast.c"
fi
if [ "${1:-}" != "--skip-bench" ]; then
    echo "== 8. thoi gian ctrl.step tren Orin (fastsim go2, 4 the gioi DEV, khong chuyen dong) ~5-10 phut"
    OPENBLAS_NUM_THREADS=1 python3 deploy/bench_steps.py 4 | tee "$HOME/realprep/bench_python.json"
    if [ -f research/algo_fast/fast_aarch64.so ]; then
        GOVOICE_FAST_SO=$PWD/research/algo_fast/fast_aarch64.so OPENBLAS_NUM_THREADS=1 python3 deploy/bench_steps.py 4 \
            | tee "$HOME/realprep/bench_fastso.json"
    fi
    python3 - "$HOME/realprep/bench_python.json" <<'EOF' || bad "C1 step p95 > 60 ms: xem DEPLOY.md §6 (ngan sach CPU)"
import json, sys
s = json.load(open(sys.argv[1]))["steps"]
for k, v in s.items():
    print("  %-5s p50 %.1f  p95 %.1f  max %.1f ms" % (k, v["p50"], v["p95"], v["max"]))
assert s["C1"]["p95"] < 60 and s["B1"]["p95"] < 60
EOF
fi
echo "== KET QUA: $([ $ok = 1 ] && echo 'DAT' || echo 'CHUA DAT (xem !! o tren)')   -> $OUT"
