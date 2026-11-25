# 🐕🎙️ GoVoice — Trợ lý giọng nói TIẾNG VIỆT chạy 100% LOCAL trên Go2

> Nói tiếng Việt → robot **hiểu, trả lời, hành động** (đi, xoay, chào, nhảy, đi tới điểm trên map SLAM).
> **Không API, không cloud, không mạng** — mọi model chạy local. Test trên **laptop** trước, rồi deploy xuống **Jetson trên con chó**.

---

## 🧠 KIẾN TRÚC 2 TẦNG (điểm "ăn tiền" để viết báo)

```
🎤 Mic (laptop / MIC ROBOT qua WebRTC bridge)
   │  VAD cắt câu (webrtcvad, 30ms frame)
   ▼
📝 STT: PhoWhisper-small (VinAI, ICLR 2024 — SOTA tiếng Việt) chạy faster-whisper int8
   │
   ├──⚡ TẦNG 1 — REFLEX (~0ms): câu lệnh đơn ("đi thẳng", "dừng", "chào")
   │        match luật trực tiếp → robot làm NGAY, không qua LLM
   │
   └──🧠 TẦNG 2 — PLANNER (~1-2s): câu phức tạp ("đi tới cửa rồi chào 2 cái")
            Qwen2.5-1.5B-Instruct Q4 (llama.cpp) + GRAMMAR GBNF ép JSON
            → chuỗi hành động đúng thứ tự
   ▼
🦿 robot_tools: move / action / stop / go_to(Nav2 + map SLAM của bạn)
🔊 TTS: Piper giọng vi_VN (CPU, ~0.1s) → loa
```

**Vì sao thiết kế này nhanh nhất trên Orin Nano 8GB:**
1. **2 tầng**: ~80% lệnh thực tế là lệnh đơn → đi đường Reflex, phản ứng tức thì. Chỉ câu phức mới tốn LLM.
2. **Grammar GBNF** (llama.cpp): ép model CHỈ sinh JSON đúng schema → không bao giờ lỗi parse, output ngắn → ít token → nhanh.
3. **cache_prompt**: KV-cache system prompt giữ lại giữa các câu → mỗi lượt chỉ decode phần mới.
4. **Model nhỏ đúng việc**: nhiệm vụ là "câu → tool call", Qwen2.5-1.5B Q4 (~1.1GB) là đủ; STT int8; TTS chạy CPU không tranh GPU.
5. **Phanh khẩn cấp**: từ "dừng lại" được bắt TRƯỚC mọi xử lý, kể cả trong câu dài.

**File trong package:**
| File | Vai trò |
|---|---|
| `assistant_main.py` | Chương trình chính (text mode / voice mode) |
| `reflex_matcher.py` | Tầng 1 — luật tiếng Việt |
| `llm_planner.py` + `grammar.gbnf` | Tầng 2 — LLM local + grammar |
| `robot_tools.py` + `waypoints.yaml` | Tay chân: SportClient + Nav2 go_to |
| `stt_engine.py` / `tts_engine.py` / `audio_io.py` | Tai / miệng / VAD |
| `go2_audio_bridge.py` | MIC ROBOT (WebRTC) → UDP cho assistant |
| `test_reflex.py` / `test_llm.py` / `benchmark_latency.py` | Test + đo số liệu viết báo |
| `config.yaml` | Cấu hình trung tâm (đổi khi sang Jetson) |

---

# PHẦN A — CHẠY TRÊN LAPTOP (RTX 4060) — làm hết phần này trước

> Mở terminal **sạch conda** (`conda deactivate` nếu thấy `(base)`). Đặt cả thư mục `go2_assistant` vào `~/go2_assistant`.

## A1. Cài llama.cpp + tải LLM ⭐ (làm đầu tiên)

```bash
# 1) Build llama.cpp (co CUDA cho RTX 4060)
sudo apt install -y build-essential cmake libcurl4-openssl-dev
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cd ~/llama.cpp
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j
# Neu loi CUDA (khong co nvcc): bo -DGGML_CUDA=ON -> ban CPU van chay tot voi model 1.5B

# 2) Tai model Qwen2.5-1.5B-Instruct GGUF Q4 (chinh chu Qwen, ~1.1GB)
pip3 install -U "huggingface_hub[cli]"
mkdir -p ~/models
huggingface-cli download Qwen/Qwen2.5-1.5B-Instruct-GGUF \
  qwen2.5-1.5b-instruct-q4_k_m.gguf --local-dir ~/models

# 3) Chay server (DE TERMINAL NAY CHAY suot phien lam viec)
~/llama.cpp/build/bin/llama-server \
  -m ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  -ngl 99 -c 2048 --port 8080
```
✅ Thấy `server is listening on http://127.0.0.1:8080` là OK. Test nhanh: mở trình duyệt vào `http://127.0.0.1:8080` chat thử.

## A2. Cài phụ thuộc Python

Terminal mới:
```bash
sudo apt install -y libportaudio2 ffmpeg python3-venv
cd ~/go2_assistant
python3 -m venv venv --system-site-packages   # system-site de sau nay dung duoc rclpy (go_to)
source venv/bin/activate
pip install -r requirements.txt
```
> Từ giờ mỗi terminal làm việc với GoVoice: `cd ~/go2_assistant && source venv/bin/activate`

## A3. Tải STT — PhoWhisper (SOTA tiếng Việt)

```bash
# Convert PhoWhisper-small sang CTranslate2 int8 (lam 1 lan, can ~2GB tai ve)
pip install "transformers[torch]" ctranslate2
ct2-transformers-converter --model vinai/PhoWhisper-small \
  --output_dir models/phowhisper-small-ct2 --quantization int8 --copy_files preprocessor_config.json
```
> ⏩ **Muốn test ngay khỏi chờ:** bỏ qua bước này — code tự fallback sang Whisper `small` đa ngôn ngữ (tự tải). PhoWhisper chính xác tiếng Việt hơn, convert sau cũng được.

## A4. Tải TTS — giọng Việt Piper

```bash
huggingface-cli download rhasspy/piper-voices \
  vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx \
  vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json \
  --local-dir models/piper
# Test: python3 tts_engine.py   -> loa phat "Xin chao, minh la Go..."
```

## A5. Test từng tầng

```bash
python3 test_reflex.py    # Tang 1 — phai dat 14/14
python3 test_llm.py       # Tang 2 — can llama-server (A1) dang chay
```
`test_llm.py` phải in JSON hợp lệ + actions đúng thứ tự + tốc độ tok/s.

## A6. Chạy TEXT MODE (não + tay, robot giả lập)

```bash
python3 assistant_main.py --mode text
```
Gõ thử: `đi thẳng 2 mét` (⚡Reflex) → `đi tới trước 1 mét rồi xoay trái rồi chào` (🧠LLM) → `dừng lại`. Robot in `[DRY] Move...` — đúng là được. Mỗi câu in luôn **đồng hồ từng khâu**.

## A7. Chạy VOICE MODE (nói qua mic laptop) 🎤

```bash
python3 assistant_main.py --mode voice
```
Nói: *"đi thẳng"*, *"nhảy đi"*, *"đi tới cái cửa rồi nằm xuống"*... Hệ nghe → in chữ → đáp giọng Việt → in lệnh robot [DRY]. **Đây là full demo trên laptop!**

## A8. Đo số liệu

```bash
python3 benchmark_latency.py     # ket qua vao benchmark_results.csv
```
File `latency_log.csv` cũng tự ghi mọi câu khi chạy thật — 2 file này là **bảng số liệu của bài báo**.

---

# PHẦN B — DEPLOY XUỐNG CON CHÓ (Jetson Orin Nano)

> Jetson: Ubuntu 20.04, CUDA 11.4, RAM 8GB dùng chung. Mục tiêu: cả pipeline trên robot, dùng **mic + loa CỦA ROBOT**.

## B1. Chép code + cài cơ bản

```bash
# Tu laptop:
scp -r ~/go2_assistant unitree@192.168.123.18:~/
# SSH vao Jetson (pw 123):
ssh unitree@192.168.123.18
cd ~/go2_assistant
sudo apt install -y libportaudio2 python3-pip
pip3 install -r requirements.txt
```
> Nếu `faster-whisper`/`ctranslate2` không cài được wheel GPU trên ARM: vẫn cài được bản **CPU** (`pip3 install ctranslate2 faster-whisper`) — PhoWhisper-**tiny**/small int8 CPU vẫn đủ nhanh cho câu lệnh ngắn (đo thử ở B5). Muốn GPU: dùng container `dusty-nv/jetson-containers` (l4t-ml có sẵn stack, tra "jetson-containers faster-whisper").

## B2. Build llama.cpp trên Jetson (CUDA 11.4, Orin = SM 8.7)

```bash
sudo apt install -y build-essential cmake libcurl4-openssl-dev
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cd ~/llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87
cmake --build build --config Release -j4
# Chep model tu laptop:
#   scp ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf unitree@192.168.123.18:~/models/
# Chay server tren Jetson:
~/llama.cpp/build/bin/llama-server -m ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  -ngl 99 -c 1024 --port 8080
```
> RAM 8GB chật: `-c 1024` đủ cho lệnh robot. Nếu thiếu RAM → giảm `-ngl` (bớt layer lên GPU) hoặc dùng Qwen2.5-**0.5B** GGUF (~400MB, vẫn ổn cho tool-call đơn giản nhờ grammar).

## B3. Sửa config cho Jetson

Trong `config.yaml` đổi:
```yaml
stt:    device: "cpu"        # (hoac "cuda" neu da co ct2 GPU)
        compute_type: "int8"
        model: "models/phowhisper-tiny-ct2"   # tiny cho Jetson; convert nhu A3
audio:  backend: "udp"       # <-- MIC ROBOT qua bridge
tts:    output: "wav"        # <-- ghi wav de phat qua LOA ROBOT
robot:  dry_run: false       # <-- DIEU KHIEN THAT
        iface: "eth0"
```

## B4. Mic + loa CỦA ROBOT (điểm "nghiên cứu" — không cắm gì ngoài)

Mic/loa nằm ở main board `.161`, Jetson `.18` cùng mạng nội bộ → kết nối WebRTC **từ Jetson** y như laptop từng làm:

```bash
# Terminal 1 tren Jetson — cau mic robot -> UDP (TAT app Unitree truoc!)
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH    # driver WebRTC (da co tu vu loa/mic)
export GO2_IP=192.168.123.161
python3 go2_audio_bridge.py

# Terminal 2 — chay assistant voi SportClient that
export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds
python3 assistant_main.py --mode voice --real
```
**Loa robot:** TTS đang ghi `.wav` vào `tts_out/`. Phát qua loa robot bằng `go2_speaker.py` sẵn có của bạn (cùng kết nối WebRTC với bridge — chung 1 process là gọn nhất; bước ghép này báo mình khi tới, mình nối bridge + speaker vào 1 file).

> ⚠️ Driver WebRTC chưa có trên Jetson? Chép từ laptop: `scp -r ~/go2_webrtc_new unitree@192.168.123.18:~/` rồi `pip3 install aiortc` (nếu thiếu).

## B5. Chạy + đo trên robot

Đo lại `benchmark_latency.py` + nói thử 20 câu, lấy `latency_log.csv`. Kỳ vọng thực tế trên Orin Nano: **Reflex ~0ms** (tổng = STT ~0.5-1s), **LLM 1.5-3s**. So với bảng laptop → có ngay bảng so sánh edge vs workstation cho bài báo.

## B6. An toàn khi chạy thật
- Tắt app Unitree (WebRTC 1 kết nối), cầm remote (L2+B dừng khẩn), chỗ trống ≥2×2m, pin ≥50%.
- Nói **"dừng lại"** = phanh khẩn cấp (được ưu tiên tuyệt đối trong code).
- `go_to` cần hệ Nav2 + map đang chạy (pipeline SLAM bạn đã dựng) — không có thì tool này chỉ báo lỗi nhẹ, không nguy hiểm.

---

# PHẦN C — NÂNG CẤP ĐỂ "TỐT NHẤT" + VIẾT BÁO

**1. Fine-tune model lệnh riêng (đóng góp "viết cái mới"):** sinh ~3-5k cặp *câu lệnh Việt → JSON* (dùng model lớn sinh data), **LoRA Qwen2.5-1.5B trên RTX 4060**, export GGUF, đo success-rate trước/sau. Đây là contribution chính: *compact Vietnamese command model for quadruped control*.

**2. go_to mở (open-vocabulary):** thay waypoint đặt tên bằng **ConceptGraphs** (bạn đã nghiên cứu) → "đi tới cái ghế đỏ" không cần khai báo trước. Nối: scene graph → tra vật thể → tọa độ → Nav2.

**3. Số liệu nên báo cáo:** latency từng khâu (bảng từ CSV, laptop vs Jetson), tỉ lệ lệnh đúng (20-50 câu test), WER của PhoWhisper trên **mic robot** (ồn quạt!) vs mic thường, RAM/GPU chiếm dụng, tỉ lệ câu đi Reflex vs LLM.

**4. Trích dẫn nền tảng:** PhoWhisper (ICLR 2024 Tiny Papers, VinAI) — STT; Whisper (Radford et al.); Qwen2.5 (Alibaba); llama.cpp GBNF grammar-constrained decoding; Piper TTS; so sánh với các hệ Go2-LLM dùng cloud API (điểm khác biệt: bạn full-local on-board).

---

# 🛟 TROUBLESHOOTING

| Lỗi | Xử lý |
|---|---|
| `test_llm.py` báo server chưa chạy | Mở terminal khác chạy lệnh llama-server (A1) và để nguyên |
| LLM trả JSON nhưng action sai | Tăng few-shot trong `llm_planner.py` (thêm ví dụ), hoặc hạ `temperature` về 0 |
| STT nghe sai nhiều | Dùng PhoWhisper-small thay tiny; nói gần mic; tăng `vad_aggressiveness` lên 3 nếu ồn |
| Mic laptop không thu | `python3 -m sounddevice` xem thiết bị; cài `libportaudio2` |
| Piper không kêu | Kiểm đường dẫn voice trong config; chạy `python3 tts_engine.py` để test riêng |
| Jetson thiếu RAM | Dùng Qwen2.5-0.5B; STT tiny; `-c 1024`; tắt bớt service |
| SportClient lỗi trên Jetson | `export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds`; app Unitree đã tắt |
| Bridge không có audio | App Unitree còn mở (WebRTC 1 kết nối); `GO2_IP=192.168.123.161` (KHÔNG phải .18) |

# 📌 GHI NHỚ NHANH (laptop)
```bash
# Terminal 1: ~/llama.cpp/build/bin/llama-server -m ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
# Terminal 2: cd ~/go2_assistant && source venv/bin/activate && python3 assistant_main.py --mode voice
```
Chạy ngon Phần A thì hú mình — qua Phần B đưa xuống con chó! 🐕🚀
