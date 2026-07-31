#!/usr/bin/env bash
# run_dryrun.sh — GOM tat ca lenh chay GoVoice (mic ROBOT, PUSH-TO-TALK) vao 1 file.
# Robot KHONG cu dong that (an toan) — chi nghe/hieu/noi. Dung de test logic.
#
# Chay:  ./run_dryrun.sh
# Thoat: bam 'q' trong man PTT, hoac Ctrl+C bat ky luc nao — tu dong dep het
#        cac dich vu nen (llama-server, loa robot, mic robot).

cd "$(dirname "$0")"
export GO2_IP=192.168.123.161
export PYTHONUNBUFFERED=1

LOG_DIR=/tmp/govoice_logs
mkdir -p "$LOG_DIR"

LLAMA_PID=""
TTS_PID=""
BRIDGE_PID=""

cleanup() {
    echo ""
    echo ">>> Dang dung cac dich vu nen..."
    [ -n "$BRIDGE_PID" ] && kill "$BRIDGE_PID" 2>/dev/null
    [ -n "$TTS_PID" ]    && kill "$TTS_PID"    2>/dev/null
    [ -n "$LLAMA_PID" ]  && kill "$LLAMA_PID"  2>/dev/null
}
trap cleanup EXIT INT TERM

# Don dep tien trinh cu con sot tu lan chay truoc (tranh loi "Address already in use")
pkill -f "llama.cpp/build/bin/llama-server" 2>/dev/null
pkill -f "go2_tts_speaker.py"   2>/dev/null
pkill -f "go2_audio_bridge.py"  2>/dev/null
sleep 1

# Ket noi WebRTC toi robot doi luc bi loi thoang qua (NoSdpAnswerError /
# DataChannelTimeoutError) neu 2 ket noi khoi dong qua sat nhau — THU LAI la du,
# khong phai loi cau hinh. Ham nay: chay 1 lenh, doi PATTERN xuat hien trong log,
# neu tien trinh chet truoc do -> thu lai (toi da 3 lan, cho dan giua cac lan).
start_webrtc_step() {
    local name="$1" cmd="$2" log="$3" pattern="$4" pidvar="$5"
    local tries=3 attempt pid ok
    for attempt in $(seq 1 $tries); do
        : > "$log"
        eval "$cmd" > "$log" 2>&1 &
        pid=$!
        ok=0
        for i in $(seq 1 20); do
            grep -q "$pattern" "$log" 2>/dev/null && { ok=1; break; }
            kill -0 "$pid" 2>/dev/null || break
            sleep 1
        done
        if [ "$ok" = "1" ]; then
            printf -v "$pidvar" '%s' "$pid"
            eval "export $pidvar"
            echo "    OK (PID $pid, lan thu $attempt)"
            return 0
        fi
        kill "$pid" 2>/dev/null
        if grep -qi "NoSdpAnswerError\|DataChannelTimeoutError" "$log"; then
            echo "    $name: WebRTC loi thoang qua (lan $attempt/$tries) — cho robot roi thu lai..."
            sleep 5
        else
            echo "    $name: loi khong ro, xem $log"
            break
        fi
    done
    return 1
}

echo "===================================================="
echo " GoVoice — CHE DO GIA (dry-run, KHONG cu dong that)"
echo "===================================================="

echo "[1/3] Khoi dong LLM server..."
./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf \
    -ngl 99 -c 2048 --port 8080 > "$LOG_DIR/llama.log" 2>&1 &
LLAMA_PID=$!
ok=0
for i in $(seq 1 30); do
    curl -s -m1 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok && { ok=1; break; }
    sleep 1
done
if [ "$ok" != "1" ]; then
    echo "    LOI: llama-server khong san sang sau 30s. Xem: tail $LOG_DIR/llama.log"
    exit 1
fi
echo "    OK (PID $LLAMA_PID)"

echo "[2/3] Khoi dong LOA robot (phai truoc mic, tranh NoSdpAnswerError)..."
echo "      (NHO tat app Unitree tren dien thoai truoc — WebRTC chi cho 1 ket noi)"
if ! start_webrtc_step "Loa robot" "stdbuf -oL -eL python3 go2_tts_speaker.py" \
        "$LOG_DIR/tts_speaker.log" "san sang" TTS_PID; then
    echo "    LOI: loa robot khong ket noi duoc sau nhieu lan thu. Xem: tail $LOG_DIR/tts_speaker.log"
    exit 1
fi

# Cho robot "tho" mot chut truoc khi mo ket noi WebRTC thu 2 (mic) — giam kha
# nang dinh NoSdpAnswerError do 2 handshake qua sat nhau.
sleep 3

echo "[3/3] Khoi dong MIC robot..."
if ! start_webrtc_step "Mic robot" "stdbuf -oL -eL python3 go2_audio_bridge.py --gain 2.5" \
        "$LOG_DIR/audio_bridge.log" "gui udp" BRIDGE_PID; then
    echo "    LOI: mic robot khong ket noi duoc sau nhieu lan thu. Xem: tail $LOG_DIR/audio_bridge.log"
    exit 1
fi

echo "===================================================="
echo " San sang. Bam PHIM CACH de noi, 'q' de thoat."
echo "===================================================="
python3 assistant_ptt.py --config config_robot_mic.yaml --key space
