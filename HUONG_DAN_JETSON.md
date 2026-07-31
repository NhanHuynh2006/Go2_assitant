# 🐕🎙️ GoVoice DEMO — Nghe & Nói trên con chó (Jetson)

> **HÀNH ĐỘNG ĐÃ KHÓA CỨNG.** Robot chỉ nghe tiếng Việt → suy nghĩ → trả lời ra loa.
> KHÔNG di chuyển, KHÔNG chạy SportClient. An toàn tuyệt đối để test giọng nói.
> Khi model fine-tune đạt độ chính xác cao → mới mở khóa hành động (dùng `assistant_main.py --real`).

---

## CẦN CHUẨN BỊ (mang từ laptop xuống)

1. **Cả thư mục này** (`go2_jetson_demo/`)
2. **Model LLM GGUF** — copy 1 trong 2:
   - Model fine-tune của bạn: `finetune/govoice-qwen2.5-1.5b-q4_k_m.gguf` (nhớ để `fewshot: false`)
   - Hoặc model gốc: `~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf` (đặt `fewshot: true`)
3. **Model STT + TTS** — copy thư mục `models/` từ laptop (chứa `phowhisper-*-ct2/` và `piper/`)
4. **llama.cpp đã build trên Jetson** (xem bước 2 bên dưới)

---

## BƯỚC 1 — Chép mọi thứ xuống Jetson

```bash
# Tu LAPTOP:
scp -r go2_jetson_demo unitree@192.168.123.18:~/
scp -r ~/Documents/Go2_assitant/models unitree@192.168.123.18:~/go2_jetson_demo/
scp ~/Documents/Go2_assitant/finetune/govoice-qwen2.5-1.5b-q4_k_m.gguf \
    unitree@192.168.123.18:~/go2_jetson_demo/
```

## BƯỚC 2 — Trên Jetson: build llama.cpp + cài Python

```bash
ssh unitree@192.168.123.18      # pw: 123
cd ~/go2_jetson_demo

# llama.cpp (CUDA cho Orin = SM 8.7)
sudo apt install -y build-essential cmake libcurl4-openssl-dev libportaudio2 ffmpeg
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cd ~/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j4      # ~15-20 phut, kien nhan
cd ~/go2_jetson_demo

# Python deps
pip3 install -r requirements.txt
# Neu faster-whisper/ctranslate2 kho cai ban GPU tren ARM -> ban CPU van chay:
#   pip3 install ctranslate2 faster-whisper
```

## BƯỚC 3 — Bật não (Terminal 1 — để chạy suốt)

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/go2_jetson_demo/govoice-qwen2.5-1.5b-q4_k_m.gguf \
  -ngl 99 -c 1024 --port 8080
```
> RAM 8GB chật: dùng `-c 1024`. Nếu thiếu RAM → giảm `-ngl` (vài layer lên GPU) hoặc đổi model Qwen 0.5B.

## BƯỚC 4 — Chạy DEMO (Terminal 2)

### Cách A — mic + loa cắm thẳng vào Jetson (đơn giản, test trước)
```bash
cd ~/go2_jetson_demo
python3 demo_voice_only.py
```

### Cách B — DÙNG MIC + LOA CỦA ROBOT (cái bạn muốn — "thuần" hơn)
Mic/loa ở main board `.161`, kết nối WebRTC từ Jetson:
```bash
# Terminal 2 — cau mic robot -> UDP (TAT app Unitree truoc!)
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export GO2_IP=192.168.123.161
python3 go2_audio_bridge.py

# Terminal 3 — demo nghe tu mic robot
cd ~/go2_jetson_demo
python3 demo_voice_only.py --mic-robot
```
> Loa robot: hiện demo phát ra loa Jetson. Muốn ra LOA ROBOT thì cần nối Piper → WebRTC speaker — để sau khi bản mic robot chạy ổn, mình ghép cho.

---

## KẾT QUẢ MONG ĐỢI

```
🗣️  Nghe: chào mọi người đi
   [Reflex:hello]
🐶 Gô: Chào bạn! Gâu gâu!
   🔒 (du dinh, KHONG chay): action(hello)
   <Gô nói ra loa>
```
Robot **đứng yên hoàn toàn**, chỉ phát giọng. Mỗi câu in rõ: nghe được gì, định làm gì (nhưng khóa), nói gì.

---

## ƯỚC LƯỢNG TỐC ĐỘ trên Orin Nano (CPU STT)
- STT (PhoWhisper-small CPU): ~0.8-1.5s/câu
- LLM (Qwen-1.5B Q4): ~1.5-3s
- TTS (Piper): ~0.2s
→ Nói xong tới khi Gô đáp: ~2.5-4.5s. Chậm hơn laptop nhưng **robot tự lập, không cần mạng**.
Muốn nhanh hơn: đổi STT sang PhoWhisper-**tiny**, hoặc build CTranslate2-CUDA cho Jetson.

## SỰ CỐ HAY GẶP
| Lỗi | Xử lý |
|---|---|
| `llama-server` build lỗi CUDA | Bỏ `-DGGML_CUDA=ON` → bản CPU vẫn chạy model 1.5B (chậm hơn) |
| STT lỗi `libcublas` | Đang để `device: cpu` rồi thì không cần CUDA; nếu muốn GPU phải build ct2-cuda |
| Mic robot không có tiếng | App Unitree còn mở (WebRTC 1 kết nối); `GO2_IP=192.168.123.161` (KHÔNG phải .18) |
| Không nghe loa | `aplay -l` xem thiết bị; thử cắm loa USB |
| RAM đầy khi chạy | Đóng app thừa; `-c 1024`; STT tiny; hoặc Qwen 0.5B |