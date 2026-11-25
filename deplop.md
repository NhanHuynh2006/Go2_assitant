# T1: não
/home/unitree/NhanHuynh/go2_jetson_demo/llama.cpp/build/bin/llama-server -m ~/NhanHuynh/go2_jetson_demo/govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
# T2: mic VÀO
export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161
python3 ~/NhanHuynh/go2_jetson_demo/go2_audio_bridge.py
# T3: loa RA (stream)
export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161
python3 ~/NhanHuynh/go2_jetson_demo/go2_tts_speaker.py
# T4: demo
cd ~/NhanHuynh/go2_jetson_demo && python3 run_demo_noaction.py --voice --mic-voice
# T2: mic VÀO
export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161
python3 ~/NhanHuynh/go2_jetson_demo/go2_audio_bridge.py
# T3: loa RA (stream)
export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161
python3 ~/NhanHuynh/go2_jetson_demo/go2_tts_speaker.py
# T4: demo
cd ~/NhanHuynh/go2_jetson_demo && python3 run_demo_noaction.py --voice --mic-voice