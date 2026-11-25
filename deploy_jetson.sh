#!/usr/bin/env bash
# deploy_jetson.sh — Chep code + cai dat toan bo GoVoice len Jetson Orin Nano cua Go2.
# Chi chay duoc SAU KHI Jetson (192.168.123.18) da len mang (ping/ssh duoc).
#
# Dung: ./deploy_jetson.sh
set -euo pipefail

JETSON_IP="192.168.123.18"
JETSON_USER="unitree"
JETSON_PW="123"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_DIR="~/go2_assistant"

command -v sshpass >/dev/null 2>&1 || { echo "Can 'sshpass' -> sudo apt install -y sshpass"; exit 1; }

echo "==> 1) Kiem tra Jetson co online khong"
if ! ping -c1 -W2 "$JETSON_IP" >/dev/null 2>&1; then
  echo "!! Jetson $JETSON_IP KHONG PING DUOC. Dung lai. Kiem tra nguon/day mang module truoc."
  exit 1
fi
sshpass -p "$JETSON_PW" ssh -o StrictHostKeyChecking=no "$JETSON_USER@$JETSON_IP" "echo OK" || {
  echo "!! SSH khong vao duoc. Kiem tra user/pass hoac dich vu sshd tren Jetson."; exit 1; }
echo "    Jetson online, SSH OK."

echo "==> 2) Chep code GoVoice + go2_webrtc_new + unitree_sdk2_python sang Jetson"
sshpass -p "$JETSON_PW" rsync -az --progress \
  --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'models/PhoWhisper-small-hf' \
  "$PROJECT_DIR"/ "$JETSON_USER@$JETSON_IP:$REMOTE_DIR/"
sshpass -p "$JETSON_PW" rsync -az /home/nolan/go2_webrtc_new/ "$JETSON_USER@$JETSON_IP:~/go2_webrtc_new/"
sshpass -p "$JETSON_PW" rsync -az /home/nolan/unitree_sdk2_python/ "$JETSON_USER@$JETSON_IP:~/unitree_sdk2_python/"
sshpass -p "$JETSON_PW" scp /home/nolan/models/qwen2.5-1.5b-instruct-q4_k_m.gguf "$JETSON_USER@$JETSON_IP:~/models/" 2>/dev/null || \
  sshpass -p "$JETSON_PW" ssh "$JETSON_USER@$JETSON_IP" "mkdir -p ~/models" && \
  sshpass -p "$JETSON_PW" scp /home/nolan/models/qwen2.5-1.5b-instruct-q4_k_m.gguf "$JETSON_USER@$JETSON_IP:~/models/"
sshpass -p "$JETSON_PW" scp "$PROJECT_DIR/finetune/govoice-qwen2.5-1.5b-q4_k_m.gguf" "$JETSON_USER@$JETSON_IP:~/models/"
# Model v2 (train them do vat/mau/quan he khong gian; 87.5 % test moi, 93.0 % test cu)
[ -f "$PROJECT_DIR/finetune/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf" ] && \
  sshpass -p "$JETSON_PW" scp "$PROJECT_DIR/finetune/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf" "$JETSON_USER@$JETSON_IP:~/models/"

echo "==> 3) Cai dat phu thuoc tren Jetson (cyclonedds, unitree_sdk2py, requirements, aiortc)"
sshpass -p "$JETSON_PW" ssh "$JETSON_USER@$JETSON_IP" bash -s <<'REMOTE'
set -e
sudo apt update
sudo apt install -y build-essential cmake libcurl4-openssl-dev libportaudio2 python3-pip python3-venv git

# CycloneDDS
if [ ! -d ~/cyclonedds_ws ]; then
  mkdir -p ~/cyclonedds_ws && cd ~/cyclonedds_ws
  git clone --branch releases/0.10.x --depth 1 https://github.com/eclipse-cyclonedds/cyclonedds.git
  cd cyclonedds && mkdir -p build && cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=~/cyclonedds_ws/install/cyclonedds -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF
  cmake --build . --target install -j$(nproc)
fi

cd ~/go2_assistant
pip3 install -r requirements.txt || echo "!! mot so package co the can ban CPU/ARM rieng, xem TROUBLESHOOTING"
pip3 install aiortc || echo "!! aiortc build tren ARM co the loi, thu 'pip3 install av==10.0.0 aiortc'"
CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds pip3 install -e ~/unitree_sdk2_python
pip3 install "numpy==1.26.4"   # ghim lai, sdk co the nang len 2.x pha faster-whisper

# llama.cpp CUDA cho Orin (SM 8.7)
if [ ! -d ~/llama.cpp ]; then
  git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
fi
cd ~/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j4
echo "==> XONG CAI DAT TREN JETSON"
REMOTE

echo ""
echo "==> DEPLOY XONG. Buoc tiep theo (lam tay tren Jetson, xem B3-B5 trong HUONG_DAN.md):"
echo "    1. Sua config.yaml: dry_run:false, iface:eth0, model tro finetune/govoice-*.gguf"
echo "    2. ssh $JETSON_USER@$JETSON_IP"
echo "    3. ~/llama.cpp/build/bin/llama-server -m ~/models/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf -ngl 99 -c 1024 --port 8080"
echo "    4. (terminal khac) export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161; python3 go2_audio_bridge.py"
echo "    5. (terminal khac) export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds; python3 assistant_main.py --mode voice --real"
