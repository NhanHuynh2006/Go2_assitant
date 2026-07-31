# PROJECT_CONTEXT — GoVoice: Trợ lý giọng nói tiếng Việt cho robot Unitree Go2

> **File này dành cho Claude Code / LLM đọc để nắm toàn bộ context dự án.**
> Đọc hết là hiểu: mục tiêu, kiến trúc, từng file làm gì, đã tới đâu, việc còn lại.
> Người dùng: **Nolan** — Lab **ISLab**, ĐH Công nghệ Kỹ thuật TP.HCM (tên cũ ĐH Sư phạm
> Kỹ thuật), GVHD **PGS.TS Lê Mỹ Hà**. Giao tiếp tiếng Việt. Mục tiêu: bài báo khoa học
> + biểu diễn hội nghị.
>
> Cập nhật **2026-07-30**. Nhật ký thay đổi chi tiết: `CHECKPOINT_2026-07-30.md`.
> Bản chạy được đã backup: `backups/2026-07-30_mic_robot_OK.tar.gz`.

---

## 1. MỤC TIÊU

Trợ lý giọng nói **tiếng Việt chạy 100% LOCAL** (không cloud, không internet) trên robot 4
chân Unitree Go2 EDU. Người nói → robot hiểu → trả lời ra loa → thực hiện hành động.

**Điểm bán của bài báo:**
- Kiến trúc **3 tầng** Reflex/FAQ/LLM — lệnh đơn và câu xã giao bỏ qua LLM (~0ms)
- **Fully on-board** trên Jetson Orin NX (các hệ Go2-LLM khác đều dùng cloud API)
- **Dùng được MIC CỦA CHÍNH ROBOT** — không cần mic ngoài (xem mục 5, đây là đóng góp mạnh)
- Fine-tune model nhỏ chuyên việc + dataset tổng hợp tái lập được
- Async inference + neuro-symbolic verification + safety layer

**Tiêu chí người dùng:** "vừa đúng nhất vừa nhanh nhất".

---

## 2. PHẦN CỨNG & MẠNG

### Robot Unitree Go2 EDU
- **Main board `192.168.123.161`** — mic + loa, WebRTC cổng 9991. **KHÔNG có SSH**
  (quét cả dải: chỉ mở cổng 80 và 9991).
- **Jetson Orin NX `192.168.123.18`** — `ssh unitree@192.168.123.18`, mật khẩu `123`.
  Ubuntu 20.04, CUDA 11.4, JetPack 5, kernel 5.10.104-tegra, Python 3.8, 6 nhân.
  - ⚠️ **KHÔNG có WiFi, KHÔNG có Bluetooth** (không wlan*, không adapter BT).
    WiFi 6/BT/4G nằm ở main board, và main board **không NAT** (đã test).
  - Internet hiện đi ké laptop `192.168.123.99` qua dây. Không dây mà không mua dongle:
    **USB tethering từ điện thoại Android** (driver có sẵn; iPhone không được). → `CONNECT_WIFI.md`
- SportClient qua DDS, iface `eth0`, `CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds`
- WebRTC driver: `~/go2_webrtc_new` (PyAV 12.3)

### API SportClient đã verify
Move(vx,vy,vyaw) loop @10Hz rồi StopMove, BalanceStand, StandUp, StandDown, Hello,
Stretch, Dance1, Dance2, Heart, **WalkUpright** (đứng 2 chân sau), **HandStand** (trồng
chuối), **FrontJump**. Flip = CẤM.

---

## 3. KIẾN TRÚC (luồng xử lý 1 câu nói)

```
🎤 MIC ROBOT (2 kênh 48kHz) ──WebRTC──> go2_audio_bridge.py ──UDP 16k──┐
   hoặc mic USB (sounddevice)                                          │
                                                                        ▼
   🧹 KHỬ NHIỄU 2 TẦNG: specsub (trừ phổ, vân tay nhiễu) → GTCRN (neural)
                                                                        ▼
   🔇 CỔNG BIÊN ĐỘ THÍCH NGHI + VAD (webrtcvad) cắt câu
      + chuẩn hoá độ to từng câu (có trần chống vỡ)
                                                                        ▼
   📝 STT: Zipformer-VI 30M (sherpa-onnx transducer, CPU int8) ~50-150ms
                                                                        ▼
   🚨 EMERGENCY "dừng lại" → xoá hàng đợi + dừng ngay (ưu tiên tuyệt đối)
   🔁 CHẶN ECHO (4 lớp — xem mục 5)
   🧭 CỔNG GỌI TÊN (khi diễn 2 con)
                                                                        ▼
   ├─⚡ TẦNG 1 REFLEX (~0ms): lệnh đơn, khớp luật tiếng Việt
   ├─🔎 TẦNG 1.7 FAQ ngữ nghĩa (TF-IDF char n-gram) — câu xã giao, tức thì
   └─🧠 TẦNG 2 LLM (~1-3s): Qwen2.5-1.5B fine-tuned + GBNF ép JSON
        → 🧹 PLAN VERIFIER: bỏ action LLM "bịa" (neuro-symbolic)
                                                                        ▼
   🛡️ SAFETY GUARD → ⚙️ ASYNC EXECUTOR → 🦿 SportClient
   🔊 TTS Piper → loa robot (WebRTC) HOẶC loa hội trường (qua laptop)
```

**Độ trễ thực đo:** câu luật/FAQ ≈ **0.05-0.15s**; câu qua LLM ≈ **1-3s**.
Ra tiếng thêm ~2s (Piper ~0.9s + WebRTC ra loa ~1.1s cố định, không giảm được).

---

## 4. CÁCH CHẠY

Xem `RUN.md`. Tóm tắt — **chọn config theo tình huống**:

| Tình huống | Config | Mic | Loa |
|---|---|---|---|
| **Mặc định** | `config_robot_mic.yaml` | mic robot | loa robot |
| Biểu diễn hội nghị | `config_hoinghi.yaml` | mic robot | **loa hội trường qua laptop** |
| Diễn 2 con | `config_cho_A.yaml` / `config_cho_B.yaml` | mic robot | loa hội trường |
| Thử phỏng vấn (1 con) | `config_test_phongvan.yaml` | mic robot | loa robot |
| Mic USB type-C (cũ) | `config_typec.yaml` | mic USB | loa robot |

```bash
# T1: llama-server
./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
# T2: LOA TRƯỚC (đợi "san sang"), rồi MIC — sai thứ tự thì loa chết NoSdpAnswerError
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH; export GO2_IP=192.168.123.161
python3 go2_tts_speaker.py
python3 go2_audio_bridge.py --gain 2.5
# T3:
python3 assistant_realtime.py --mode voice --config config_robot_mic.yaml [--real]
```
⚠️ Tắt app Unitree trên điện thoại (WebRTC giới hạn kết nối).

---

## 5. MIC ROBOT — phần đã tốn nhiều công nhất

> Chi tiết đầy đủ + bảng số: **`CHONG_ON_MIC.md`**. Đây là bản tóm tắt.

**Trạng thái: DÙNG ĐƯỢC, đã nghiệm thu bằng giọng thật.** WER 5.0%, 60s ồn thuần ra 0 câu rác.

### Bốn lỗi gốc đã tìm ra (và cách phát hiện)

1. **Nền ồn robot đẩy cổng lên quá cao** → không khử nhiễu thì hệ **điếc hoàn toàn**
   (0/4 câu). Đây là lý do "mic robot còn tệ hơn" suốt thời gian trước.
2. **Bridge đọc sai số kênh → audio giãn 2 lần.** PyAV ≥12 trả `frame.layout.channels`
   là **tuple**, không phải int → frame stereo bị coi là mono → lấy gấp đôi số mẫu.
   Triệu chứng: "giọng nghe vang vang, chữ kéo dài", ghi 25s ra file 50.1s.
   → Nay tính số kênh từ `frame.samples`, và bridge **tự cảnh báo** nếu lệch >10% nhịp.
3. **Tinh chỉnh cũ vô giá trị** vì đo trên audio giãn. Đo lại: `noise_gate_factor` 3.5→**2.0**,
   `denoise.mix` 0.9→**1.0**, thêm chuẩn hoá độ to.
4. **Echo (Gô nghe chính nó)** — mất 4 vòng mới trị được, xem dưới.

### Chống echo: 4 lớp độc lập

| # | Lớp | Ghi chú |
|---|---|---|
| 1 | Mute theo đồng hồ (hàng đợi loa + **một luồng nói**) | trước đây mỗi câu 1 thread → 5 Piper chạy song song → chậm 16s và mute tính sai |
| 2 | **Mute chờ tới khi mic THẬT SỰ im** (240ms) | ★ lớp chính. Trễ WebRTC không cố định nên mọi công thức đồng hồ đều có lúc hụt |
| 3 | Đối chiếu ≥3 **từ liên tiếp** với lời Gô vừa nói | dùng chuỗi liên tiếp chứ KHÔNG phải tập từ — đếm tập từ làm "BẠN LÀ AI" bị chặn nhầm |
| 4 | Mảnh <3 từ mà không tầng luật nào nhận ra | chặn ngay trước LLM |

(+ **cổng gọi tên** khi diễn 2 con — mảnh echo không chứa tên nên bị loại hết)

### Khử nhiễu: specsub + GTCRN nối tiếp

- **specsub** — trừ phổ bằng "vân tay" nhiễu ghi sẵn (`robot_noise60s_v2.wav`). Tiếng quạt/
  động cơ là nhiễu **ổn định** nên học thuộc phổ rồi trừ thẳng. RTF **0.007**.
- **GTCRN** — mạng 23.7k tham số qua **sherpa-onnx** (cùng thư viện STT, không thêm
  dependency). Dọn nhiễu *thay đổi*. RTF 0.155.

| cách lọc | bắt | WER | rác/60s ồn |
|---|---:|---:|---:|
| không lọc | 1/4 | 25.0% | 3 |
| gtcrn | 4/4 | 16.2% | 0 |
| **specsub+gtcrn** | **4/4** | **5.0%** | **0** |

⚠️ **Vân tay gắn với mức âm lượng.** Đổi `--gain` của bridge / đổi robot → phải ghi lại:
```bash
python3 go2_audio_bridge.py --record 60 --gain 2.5 && mv robot_mic_test.wav robot_noise60s_v2.wav
```
Hệ tự cảnh báo nếu lệch >2.5×.

⚠️ **To hơn KHÔNG tốt hơn**: `normalize.target_rms` 0.06→0.15 làm WER xấu từ 16% lên 27%.
Giữ **0.03**. `denoise.gain` đừng vượt 2.0 (2.2 vỡ tiếng, bắt 0/4).

---

## 6. CÁC FILE & VAI TRÒ

### Lõi xử lý
| File | Vai trò |
|---|---|
| `assistant_realtime.py` | Orchestrator. `process()` = emergency → chặn echo → cổng gọi tên → combo/reflex/FAQ → chặn mảnh nhiễu → LLM. Quản lý mute + luồng nói |
| `reflex_matcher.py` | TẦNG 1: luật tiếng Việt (mét/giây/độ/vòng, số bằng chữ). NFD strip dấu |
| `faq_matcher.py` + `knowledge.yaml` | TẦNG 1.7: tra cứu fuzzy TF-IDF. **Mở rộng = chỉ sửa knowledge.yaml** |
| `combo_matcher.py` | Chẻ câu ghép theo từ nối |
| `llm_planner.py` + `grammar.gbnf` | TẦNG 2: llama-server + GBNF ép JSON |
| `plan_verifier.py` | Bỏ action LLM bịa (chỉ BỎ, không THÊM) |
| `safety_guard.py` | Clamp vận tốc, chặn động tác nguy hiểm, tự đứng dậy |
| `async_executor.py` | Hàng đợi hành động, robot vừa làm vừa nghe |
| `robot_tools.py` | SportClient thật. `dry_run=True` → in [DRY]. Tự bật AI mode |

### Audio
| File | Vai trò |
|---|---|
| `audio_io.py` | VAD segmenter + cổng biên độ thích nghi. LocalMic/UdpMic. **Đếm khung im khi đang câm mic**. Chuẩn hoá độ to từng câu |
| `denoiser.py` | Khử nhiễu streaming: `specsub` / `gtcrn` / `rnnoise` / nối tiếp `a+b` |
| `go2_audio_bridge.py` | Mic robot WebRTC → UDP 16k. **Tự kiểm tra trôi nhịp** |
| `go2_tts_speaker.py` | Loa robot qua WebRTC (nghe UDP 17891) |
| `tts_engine.py` | Piper. output: `local`/`wav`/`robot`/**`pa`**/`robot+pa` |
| `pc_speaker.py` | ⚠️ **Chạy trên LAPTOP** — loa hội trường (nhận wav qua TCP 17892) |
| `stt_transducer.py` | Zipformer-VI qua sherpa-onnx + hotwords |

### Biểu diễn nhiều robot
| File | Vai trò |
|---|---|
| `go2_troupe.py` | 2 con nhảy khớp nhịp. `agent` trên mỗi Jetson, `conduct` trên laptop. Đồng bộ SNTP **không cần NTP** — đo được 0.10ms dù đồng hồ lệch 3.7s |

### Công cụ đo (dùng khi có sự cố — đừng đoán, hãy đo)
| File | Vai trò |
|---|---|
| `mic_debug.py` | ★ Ghi giọng thật + in RMS/ngưỡng/VAD từng khung + STT bỏ qua VAD → tách bạch "tai không nghe" vs "cổng chặn" vs "STT không đọc ra". `--wav` phân tích lại file cũ |
| `test_echo_delay.py` | Đo trễ loa→mic, in sẵn dòng config |
| `test_denoise.py` | A/B nhanh các cách khử nhiễu, xuất wav nghe thử |
| `bench_denoise_vad.py` | Chấm **cả hai mặt**: bắt được câu + số câu rác |

### Tài liệu
`RUN.md` (cách chạy) · `CHONG_ON_MIC.md` (mic, đầy đủ số liệu) · `HAI_CON_CHO.md`
(2 robot) · `CONNECT_WIFI.md` (mạng) · `CHECKPOINT_2026-07-30.md` (nhật ký)

---

## 7. QUY ƯỚC — ĐỪNG PHÁ KHI SỬA

- **Vận tốc Reflex:** vx=0.5, vyaw=1.2. Giới hạn: vx≤0.6, vy≤0.4, vyaw≤1.5, lệnh ≤20s
- **Không cap khoảng cách** (`max_step_m: 10`) — lệnh "3 mét" đi đủ 3m
- **SYSTEM_PROMPT dùng CHUNG** giữa train và chạy — không được lệch
- **fewshot=false** khi dùng model fine-tuned
- **Thứ tự khởi động**: `go2_tts_speaker.py` TRƯỚC, rồi `go2_audio_bridge.py`
- Python **3.8** trên Jetson (không f-string chứa backslash trong `{}`)
- Người dùng thích copy-paste từng lệnh, một việc một lúc

### Bẫy đã dính — đừng lặp lại
- **Bỏ dấu gây va chạm**: `đúng`=`dừng`=`dung`, `có`=`cô`=`co`, `bạn`=`bàn`.
  → Khớp theo **ranh giới từ**, tránh danh sách từ ngắn.
- **Đo trên dữ liệu sai thì kết luận ngược**: mọi tinh chỉnh khử nhiễu trước khi sửa bug
  stereo đều vô giá trị. **Luôn kiểm tra dữ liệu đo trước khi tin số.**
- **Chỉ đo một mặt là bẫy**: khử nhiễu mạnh thì hết rác nhưng điếc luôn. Phải đo **đồng thời**
  "bắt được câu" và "số câu rác".

---

## 8. VIỆC CÒN LẠI

### A. Trước hội nghị (ưu tiên cao)
1. **Test 2 con thật** — `go2_troupe.py` mới chỉ kiểm chứng giao thức đồng bộ + cổng gọi
   tên, **chưa chạy với 2 robot thật**. Chưa chắc: trễ SportClient của từng con có bằng nhau
   không (nếu lệch phải tách `--latency` riêng cho mỗi con).
2. **Test USB WiFi** khi dongle về (`ip -brief addr | grep wlan`).
3. **Thử loa hội trường**: `python3 pc_speaker.py --test <IP_laptop>` — làm ở phòng chờ.
4. **Rút ngắn câu trả lời dài.** Câu giới thiệu ISLab hiện ~9s tiếng → MC phải chờ, và
   robot câm mic suốt thời gian đó. Nên rút xuống ~3s trong `knowledge.yaml`/`reflex_matcher.py`.
5. **Cân nhắc bỏ `--stunts`** (trồng chuối/đứng 2 chân) — ngã trên sân khấu là hỏng cả buổi.

### B. Độ chính xác còn cải thiện được
- Reflex khớp **quá lỏng** với câu bị méo: "KHOẢN TIỀN" và "ĐỨNG LẦN HAI TIẾNG SAU" đều ra
  "đi thẳng". Nên thêm ngưỡng tin cậy cho Reflex.
- FAQ khớp **sai chủ đề**: "BẠN BIẾT GÌ VỀ TRƯỜNG KHÔNG" → trả lời về đồng hồ (khớp 0.58).
  Nên nâng `faq.threshold` hoặc bổ sung mục cho câu hỏi về trường.
- Đo lại độ chính xác toàn hệ sau tất cả thay đổi (số trong slide là eval CŨ).

### C. Hướng nghiên cứu
- **Mic robot có 2 kênh** → dùng chênh lệch pha để **lọc theo hướng** (beamforming),
  mạnh hơn hẳn khử nhiễu đơn kênh. Để dành sau hội nghị.
- LLM nhanh hơn: mở rộng Reflex+FAQ để né LLM, thử Qwen 0.5B, hoặc stream LLM→TTS.
- (KHÔNG nên viết lại C hay đưa ROS2 — phần nặng đã là C/CUDA sẵn.)

### D. Cho bài báo
- **Bảng 0/4 → 4/4**: khử nhiễu không chỉ "làm sạch tiếng" mà **mở khoá** được cảm biến
  mic on-board vốn không dùng được.
- **specsub+gtcrn**: WER 16.2% → 5.0% khi khai thác tính **ổn định** của nhiễu động cơ.
- **Metric "số câu rác / 60s im lặng"** — sát trải nghiệm hơn WER, ít bài báo Go2 nào báo cáo.
- Đồng bộ nhiều robot **không cần NTP** (0.10ms dù đồng hồ lệch 3.7s).
- Trích dẫn: GTCRN (ICASSP 2024), RNNoise (MMSP 2018), sherpa-onnx/k2-fsa, Zipformer,
  Qwen2.5, llama.cpp GBNF, SmolVLA (2506.01844), Piper.
