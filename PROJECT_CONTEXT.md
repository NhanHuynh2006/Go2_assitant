# PROJECT_CONTEXT — GoVoice: Trợ lý giọng nói tiếng Việt cho robot Unitree Go2

> **File này dành cho Claude Code / LLM đọc để nắm toàn bộ context dự án.**
> Đọc hết file này là hiểu: mục tiêu, kiến trúc, từng file làm gì, đã làm tới đâu, việc còn lại.
> Người dùng: Nolan (sinh viên HCMUTE). Giao tiếp tiếng Việt. Mục tiêu: làm bài báo khoa học.

---

## 1. MỤC TIÊU DỰ ÁN

Xây trợ lý giọng nói **tiếng Việt chạy 100% LOCAL** (không cloud, không internet) trên robot 4 chân Unitree Go2 EDU. Người nói tiếng Việt → robot hiểu → trả lời ra loa → thực hiện hành động (đi, xoay, chào, nhảy, đi tới điểm trên bản đồ SLAM).

**Điểm bán của bài báo (research contribution):**
- Kiến trúc **3 tầng** Reflex / Combo-segmenter / Planner — 82% câu (kể cả combo) giải tất định ~0ms, bỏ qua LLM
- Combo segmenter neuro-symbolic: chẻ câu phức theo từ nối → Reflex từng vế (đẩy e2e 61.7%→91.0%)
- Fully on-board trên Jetson Orin Nano (các hệ Go2-LLM khác đều dùng cloud API)
- Tiếng Việt với PhoWhisper (STT, GPU ~1.8s) + grammar-constrained LLM fine-tune
- Fine-tune model nhỏ chuyên việc + dataset tổng hợp tái lập được
- Async inference + neuro-symbolic verification + safety layer

**Tiêu chí người dùng nhấn mạnh:** "vừa đúng nhất vừa nhanh nhất" (realtime + chính xác).

---

## 2. PHẦN CỨNG & MÔI TRƯỜNG

### Laptop (phát triển + train)
- Lenovo Legion, Ubuntu 22.04, RTX 4060 8GB, Python 3.10
- User `nolan`, host `NhanHuynh`. Project: `~/Documents/Go2_assitant`
- venv runtime: `~/Documents/Go2_assitant/venv` (đã cài cả torch để train — KHÔNG tách venv_ft)
- LD_LIBRARY_PATH đã thêm nvidia cublas/cudnn cu12 (cho faster-whisper GPU)
- llama.cpp build CUDA tại `~/llama.cpp`, model GGUF tại `~/models`

### Robot Unitree Go2 EDU
- **Main board: `192.168.123.161`** — có mic/loa, WebRTC port 9991
- **Jetson Orin Nano 8GB: `192.168.123.18`** — SSH `ssh unitree@192.168.123.18` pw `123`
  - Ubuntu 20.04, CUDA 11.4, JetPack 5 (~40 TOPS)
  - KHÔNG có WebRTC (phải dùng main board .161 cho audio)
- SportClient điều khiển qua DDS, iface `eth0`, `CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds`
- `unitree_sdk2_python` đã cài. WebRTC driver tại `~/go2_webrtc_new`

### API SportClient đã verify (dùng trong robot_tools.py)
Move(vx,vy,vyaw) loop @10Hz rồi StopMove, BalanceStand, StandUp, StandDown,
Hello, Stretch, Dance1, Dance2, Heart. (HandStand/WalkUpright/flip = CẤM vì nguy hiểm)

---

## 3. KIẾN TRÚC HỆ THỐNG (luồng xử lý 1 câu nói)

```
🎤 Mic (laptop HOẶC mic robot qua WebRTC bridge → UDP)
   │ VAD cắt câu (webrtcvad)
   ▼
📝 STT: PhoWhisper-small/tiny (faster-whisper, CTranslate2 int8)
   │  + initial_prompt mớm từ vựng lệnh + lọc hallucination
   ▼
🚨 EMERGENCY check: "dừng lại/stop" → xóa hàng đợi + dừng ngay (ưu tiên tuyệt đối)
   │
   ├─⚡ TẦNG 1 REFLEX (~0ms): lệnh đơn ("đi thẳng", "xoay 2 vòng")
   │    khớp luật tiếng Việt → CHÍNH XÁC TUYỆT ĐỐI theo toán học
   │    (chẻ lệnh dài >6s thành nhiều lệnh nối nhau)
   │
   ├─⚡ TẦNG 1.5 COMBO SEGMENTER (~0.07ms): câu phức "đếm được"
   │    (combo_matcher.py) CHẺ câu theo từ nối (rồi/sau đó/tiếp theo/xong)
   │    → giải TỪNG VẾ bằng Reflex + go_to theo từ vựng địa điểm (waypoint).
   │    Mọi vế giải được → plan ĐÚNG TUYỆT ĐỐI, KHÔNG cần LLM (82% câu).
   │    1 vế không giải được → nhường LLM (an toàn, không đoán bừa).
   │    (Đóng góp neuro-symbolic: diệt tất định lỗi sai-hướng + sai-duration)
   │
   └─🧠 TẦNG 2 LLM (~200-900ms): câu phức còn lại (~18%)
        Qwen2.5-1.5B fine-tuned + GBNF grammar ép JSON
        → 🧹 PLAN VERIFIER: bỏ action LLM "bịa" (neuro-symbolic)
   ▼
🛡️ SAFETY GUARD: clamp vận tốc, chặn động tác nguy hiểm, tự đứng dậy trước khi đi
   ▼
⚙️ ASYNC EXECUTOR: hành động chạy thread riêng (vừa làm vừa nghe câu kế — SmolVLA)
   ▼
🦿 robot_tools: SportClient (move/action/stop/go_to Nav2)
🔊 TTS: Piper streaming (vi_VN) → loa (~100ms time-to-first-sound)
```

---

## 4. CÁC FILE & VAI TRÒ (toàn bộ ~2700 dòng)

### Lõi xử lý
| File | Vai trò |
|---|---|
| `reflex_matcher.py` | TẦNG 1: luật tiếng Việt. Xử lý mét/giây/độ/vòng, số bằng chữ, chẻ lệnh >6s. NFD strip dấu. Câu >6 từ → nhường LLM (trừ phanh tường minh). Có rule dance2 (đổi điệu) |
| `combo_matcher.py` | **MỚI — TẦNG 1.5**: chẻ combo theo từ nối → giải từng vế bằng Reflex + go_to theo từ vựng địa điểm. `match()` (≥2 vế) + `resolve_goto()` (lệnh đơn go_to, gọi TRƯỚC Reflex). Giải 82% câu không cần LLM, ~0.07ms |
| `llm_planner.py` | TẦNG 2: gọi llama-server qua HTTP loopback. ChatML, cache_prompt, GBNF grammar. Có cờ `use_fewshot` (False cho model fine-tuned) |
| `grammar.gbnf` | Grammar ép LLM CHỈ sinh JSON `{"say":..., "actions":[{tool, args}]}`. tool = move/action/stop/go_to |
| `plan_verifier.py` | MỚI (neuro-symbolic): bỏ action LLM bịa. action chỉ giữ nếu câu nói có từ kích hoạt tương ứng. Chỉ BỎ không THÊM |
| `safety_guard.py` | MỚI: clamp vx/vy/vyaw/duration, chặn động tác nguy hiểm (handstand...), tự chèn standup nếu robot nằm, emergency |
| `async_executor.py` | MỚI: thread riêng + hàng đợi. Robot vừa làm vừa nghe câu kế (kỹ thuật SmolVLA arxiv 2506.01844). emergency_stop xóa queue |
| `robot_tools.py` | Điều khiển SportClient thật. dry_run=True → in [DRY]. ACTION_MAP, go_to qua Nav2 /goal_pose |

### Audio
| File | Vai trò |
|---|---|
| `stt_engine.py` | Wrap faster-whisper. initial_prompt mớm từ vựng, lọc hallucination (no_speech_prob>0.6, avg_logprob<-1.0), beam_size config |
| `stt_transducer.py` | **MỚI** — STT engine THAY THẾ (Hướng 1): zipformer-transducer tiếng Việt qua sherpa-onnx. Cùng interface `transcribe()->(text,ms)` với stt_engine → cắm thẳng vào pipeline. ~15-30ms (vs 1.8s Whisper). Hotwords biasing + `use_gpu` cho Jetson |
| `tts_engine.py` | Wrap Piper. STREAMING (vừa sinh vừa phát ~100ms). Tự nhận API piper mới/cũ. paplay/aplay/sounddevice |
| `audio_io.py` | VAD segmenter (webrtcvad). LocalMic (sounddevice) + UdpMic (mic robot). mute event chống tự nghe mình. silence_end_ms config |
| `go2_audio_bridge.py` | v2: mic robot WebRTC → UDP 16kHz. scipy polyphase resample (chống rè/méo), high-pass (bỏ ù), normalize, --denoise, --record để test |

### Entry points (file chạy chính)
| File | Vai trò |
|---|---|
| `run_demo_noaction.py` | **CHỈ NGHE-NÓI**, robot KHÔNG hành động (ép dry_run). Test giao tiếp an toàn. `--voice`, `--mic-robot` |
| `run_real_robot.py` | **CHẠY THẬT**, robot hành động. Có checklist xác nhận an toàn. `--voice`, `--mic-robot`, `--yes` |
| `assistant_realtime.py` | Orchestrator realtime (async+safety+verifier). 2 file trên gọi vào đây. GoVoiceRT class |
| `assistant_main.py` | Bản CŨ (tuần tự, không async). Vẫn chạy được, giữ để so sánh |

### Test & benchmark
| File | Vai trò |
|---|---|
| `test_reflex.py` | 14 assert ca Reflex (12 đơn + 2 phức→None) |
| `test_llm.py` | 4 prompt test LLM, in JSON + ms + tok/s |
| `benchmark_latency.py` | Đo latency Reflex vs LLM, xuất CSV |

### Config
| File | Vai trò |
|---|---|
| `config.yaml` | Cấu hình trung tâm. llm/stt/tts/audio/robot. `fewshot: false` cho model fine-tuned, `dry_run` cho an toàn |
| `waypoints.yaml` | Điểm đặt tên trên bản đồ SLAM cho go_to |
| `requirements.txt` | Deps runtime |

### Fine-tune (thư mục finetune/)
| File | Vai trò |
|---|---|
| `gen_dataset.py` | Sinh dataset tổng hợp câu lệnh Việt → JSON. 7 nhóm + augment "mất dấu" (mô phỏng lỗi STT). seed=42 tái lập. ~4700 mẫu. `mv_split()` chẻ move giữ full distance (KHÔNG cap 6s) |
| `train_lora.py` | QLoRA 4-bit trên RTX 4060. `--base 1.5b|0.5b`. Import SYSTEM_PROMPT từ llm_planner (cùng phân phối train/chạy). eval_batch=1 chống OOM |
| `merge_lora.py` | Gộp adapter → merged HF. `--base` |
| `export_gguf.sh` | merged → GGUF Q4_K_M. `bash export_gguf.sh <merged_dir> <name>` |
| `evaluate.py` | Chấm success-rate LLM-only trên test set 300 câu. `--no-fewshot`, `--tag`, `--endpoint` (chạy 2 server song song). Trọng tài gộp move tương đương (công bằng vụ chẻ lệnh) |
| `eval_e2e.py` | **MỚI**: chấm TOÀN HỆ THỐNG giống production (Combo→Reflex→LLM→verifier). Dùng chung trọng tài với evaluate.py. `--n-predict`. In tỉ lệ định tuyến |

### Tài liệu (.md)
- `HUONG_DAN.md` — hướng dẫn A-Z gốc (laptop → Jetson → paper)
- `README_REALTIME.md` — 2 file chạy + 3 lớp công nghệ mới
- `README_FINETUNE.md` — pipeline fine-tune 5 bước
- `JETSON_STT_GPU.md` — build CTranslate2-CUDA cho Jetson (STT GPU)
- `FIX_MIC_ROBOT.md` — trị mic robot rè/méo/ù

---

## 5. TRẠNG THÁI HIỆN TẠI (đã làm tới đâu)

### ĐÃ XONG ✅
- Toàn bộ pipeline chạy trên laptop: STT + Reflex + **Combo segmenter** + LLM + TTS + async + safety + verifier
- TTS streaming: 98ms time-to-first-sound
- Reflex: 14/14 test pass, xử lý đúng mét/giây/độ/vòng, chẻ lệnh dài
- **TẦNG 1.5 Combo segmenter** (combo_matcher.py): giải 82% câu KHÔNG cần LLM, ~0.07ms/câu
- LLM trên laptop: 172-945ms, 135 tok/s (grammar ép JSON hoàn hảo)
- Voice mode laptop: nói tiếng Việt → nghe → đáp giọng, mute chống echo OK
- Fine-tune LoRA Qwen2.5-1.5B: **ĐÃ RETRAIN** trên data chẻ-consistent (4 epoch) → LLM-only **61.7%**, e2e **91.0%**
- Đã xuất GGUF model fine-tuned mới (finetune/govoice-qwen2.5-1.5b-q4_k_m.gguf)
- **STT GPU trên Jetson XONG** ✅: CTranslate2 **v3.16.1** build CUDA (vá par_nosync→par) + faster-whisper 0.9.0 + PhoWhisper-small **fp16** → **~1.8s/câu** (CPU trước 2-4s). Công thức đầy đủ: JETSON_STT_GPU.md

### SỐ LIỆU ĐÁNG CHÚ Ý (2026-06-13 — test set MỚI 300 câu, đã chấm lại v2)
**Bảng ablation cho paper (3 cột) — ĐÃ RETRAIN trên data chẻ-consistent:**
| Cấu hình | Success-rate |
|---|---|
| Baseline (Qwen gốc + few-shot, LLM-only) | **5.7%** |
| Fine-tuned (no-fewshot, LLM-only) | **61.7%** |
| **Full system** (Reflex + Combo segmenter + verifier) | **91.0%** |

- Đóng góp tách bạch: fine-tune (5.7→61.7) + kiến trúc neuro-symbolic (61.7→91.0)
- Định tuyến 300 câu: Combo 222 / Reflex 23 / LLM 55. Combo 89.9%/93.5%, go_to 100%, move 100%, spin 100%
- LLM-only latency: tb 780ms / p95 1197ms. CSV: eval_baseline_v2 / eval_finetuned_v2 / eval_e2e_final.
- (Trước retrain: LLM 55.7% / e2e 89.3% — retrain data mới đẩy +6 / +1.7)

### CHẨN ĐOÁN LỖI ĐÃ GẶP & FIX
- **Nạp NHẦM model gốc khi eval** → finetuned_v2 ra 7.7% (= baseline). Phải kiểm `curl localhost:8080/props`. Dấu hiệu: vận tốc ra 0.6/0.4/0.8, go_to bịa "3m"/"standup"
- **gen_dataset cap duration 6.0** → "3 mét" thành 2.1m (cắt cụt, trái §7). Thêm mv_split() chẻ giữ full distance
- combo_matcher: `_strip_tail` từng cắt nhầm "độ"(do)≡"đó"(do) → 180° ra 2.0s; go_to "cho cu" lọt vào "cho cua" → thêm \b word-boundary
- TTS câm: API piper mới đổi → đã wrap nhận cả 2 API
- f-string backslash: Python 3.10 cấm → đã sửa
- STT bịa "tổng thống Mỹ...": hallucination từ ồn → đã thêm lọc
- CUDA libcublas.so.12: thiếu nvidia cu12 → đã pip install + LD_LIBRARY_PATH
- OOM lúc train eval: batch eval mặc định 8 → đã ghim eval_batch=1
- Mic robot rè/méo: resample "trung bình 3 mẫu" → đã thay scipy polyphase
- venv torch từng là 2.11.0+CPU (không train được) → đã cài lại torch CUDA cu126, RETRAIN xong
- **STT GPU Jetson/CUDA 11.4** (chuỗi lỗi đã giải, xem JETSON_STT_GPU.md): ct2 v3.24 không build (par_nosync + bf16 host-incomplete <11.8); v3.7 build được nhưng Whisper thiếu encode() → faster-whisper không xài; **CHỐT v3.16.1** (vá par_nosync→par, chưa có bf16 GPU). Model int8 (convert ct2 4.x) lỗi `Conv1D expected int8` → convert lại **float16** trên laptop rồi scp; vocabulary.json→txt cho ct2 3.16

---

## 6. VIỆC CÒN LẠI (ưu tiên giảm dần)

### A. ĐỘ CHÍNH XÁC — ✅ XONG: e2e **91.0%** (retrain trên data chẻ-consistent)
Đã vượt mốc 80%. Retrain (torch CUDA cu126, 4 epoch) đẩy LLM-only 55.7→61.7%, e2e 89.3→91.0%.
Quy trình tái lập: `train_lora.py --base 1.5b --epochs 4` → `merge_lora.py` → `export_gguf.sh merged_1.5b govoice-qwen2.5-1.5b` → restart server → `eval_e2e.py --tag e2e_final --no-fewshot`.

### B. TỐC ĐỘ / REALTIME — ✅ STT GPU XONG (~1.8s/câu, từ 2-4s CPU)
- Planning ~0.07ms cho 82% câu (Combo segmenter) — đã rất nhanh.
- STT GPU trên Jetson: **ĐÃ LÀM** theo JETSON_STT_GPU.md (ct2 v3.16.1 CUDA + faster-whisper 0.9.0 + PhoWhisper fp16). ~1.8s/câu (encoder cửa sổ 30s; beam1≈beam5 nên để beam5 cho chính xác).
- Còn (tùy chọn) cho paper: **Qwen 0.5B** (`train_lora.py --base 0.5b`) → cột ablation 0.5B vs 1.5B + LLM nhanh ~2×.
- KHÔNG làm speculative decoding (output ngắn lãi ít, tốn RAM Jetson).

### B2. STT NÚT THẮT & HƯỚNG 1 — thay Whisper bằng TRANSDUCER (MỚI 2026-07-03) 🔥
**Chẩn đoán:** STT (~1.8s) là nút thắt lớn nhất (~80% tổng độ trễ). Lý do gốc: Whisper LUÔN xử lý cửa sổ cố định 30s dù lệnh chỉ 1-3s → dư ~3.7× tính toán (WhisperFlow, arXiv 2412.11272).

**Nghiên cứu quốc tế (3 nhóm):** (A) tối ưu Whisper (bỏ padding 30s, Distil-Whisper 6×, int8, speculative); (B) streaming (whisper_streaming/WhisperFlow — phiên âm TRONG lúc nói, ~0.5s); (C) đổi kiến trúc **RNN-T/FastConformer streaming** (chuẩn industry Google/Apple/NVIDIA; tiền lệ 🇹🇭 Typhoon ASR cho tiếng Thái). Audio-LLM (GPT-4o/Qwen2.5-Omni/Moshi) = tầm nhìn xa (nặng ~7B, mất GBNF/safety, khó Jetson).

**→ CHỌN Hướng C (transducer). ĐÃ TEST trên laptop (thư mục `stt_streaming_test/`):**
- Model: **`sherpa-onnx-zipformer-vi-30M-int8`** (nguồn HF `hynt/Zipformer-30M-RNNT-6000h`, 6000h tiếng Việt, offline transducer, 26MB) chạy qua **sherpa-onnx** (pip).
- **Latency: ~15-30ms/câu trên CPU laptop (RTF ~0.009) → nhanh hơn PhoWhisper GPU ~100×.** Kể cả trên Jetson vẫn kỳ vọng <300ms.
- Độ chính xác: câu dài + câu combo transcribe HOÀN HẢO; lệnh ngắn rời có lỗi (test bằng Piper TTS→STT là proxy nhiễu). **Hotwords (contextual biasing)** cứu được lệnh quan trọng ("dừng lại", "đi thẳng ba mét").
- **Giữ nguyên kiến trúc** (3 tầng + GBNF + safety) — chỉ thay "lỗ tai".

**File mới:** `stt_transducer.py` (STT engine drop-in, cùng interface stt_engine.STT — có param `use_gpu` cho Jetson + hotwords); `stt_streaming_test/` (bench + model + hotwords.txt 70 từ vựng lệnh + `record_and_test.py` thu mic thật + `bench_vi_transducer.py`).

**Việc còn lại Hướng 1:** (A) test MIC THẬT (`record_and_test.py`, thay TTS proxy); (B) **fine-tune/adapt transducer trên data lệnh robot** (đóng góp paper); (C) port Jetson (build sherpa-onnx CUDA hoặc chạy CPU cũng đã đủ nhanh). Lộ trình 3 giai đoạn + 4 slide future-work: `slides/GoVoice_FutureWork.*`.

**B1 — ADAPTATION bằng contextual biasing (ĐÃ ĐO, CHỐT LÀ GIẢI PHÁP CHÍNH):** `finetune_stt/make_and_eval.py` sinh 57 câu lệnh → Piper synth → đo. **Hotwords (mồi 70 từ vựng lệnh, `stt_streaming_test/hotwords.txt`) đẩy intent-match ~51% → 82.5%, WER 13.5% → 7.1%**, điểm ngọt `hotwords_score=2–3`. Zero training. Default `hotwords_score=3.0` trong `stt_transducer.py`.

**→ B1 LÀ GIẢI PHÁP CHÍNH THỨC cho STT — ĐÃ DEPLOY & VERIFY TRÊN JETSON THẬT (2026-07-04).** Engine: **`stt_transducer.py`** (cùng interface `transcribe()->(text,ms)` với stt_engine → cắm thẳng). Model: `sherpa-onnx-zipformer-vi-30M-int8` (hynt, 6000h, 26MB) + hotwords. **Latency đo THẬT trên Jetson Orin NX (CPU): 78-160ms/câu** (vs PhoWhisper GPU 1800ms → nhanh ~11-23×), transcribe đúng nghĩa. sherpa-onnx 1.13.3 đã có sẵn trên chó (khỏi cần cài). Bật qua config: `stt.backend: transducer` (đã wire vào `assistant_realtime.run_voice`). Deploy bundle: `govoice_stt_b1.tar.gz` (26MB, ở project root — KHÔNG để /tmp vì bị dọn).

**Mic robot setup (đã fix trên chó):** mic 3.5mm qua hub USB → ALSA card `CS202: USB Audio` (số card/device DAO ĐỘNG, re-enumerate khi rớt/cắm lại — giống bệnh mic laptop cũ, cần cắm chắc tay). Gain mặc định 100%/32dB → clip 32767. Fix: `amixer -c <card_hiện_tại> sset 'Mic' 25%` → max am ~9706 (đẹp). Ghi native rate 48000 (không hỗ trợ 16000 trực tiếp), code tự resample. **Cần chạy lại amixer set-gain mỗi lần boot/cắm lại mic** (chưa persist qua reboot).

**B2 — fine-tune neural: ĐÃ THỬ ĐỦ, KHÔNG VƯỢT B1 (2026-07-03).** Dựng xong env k2/icefall/lhotse trên venv (torch2.11+cu126 CÓ k2 wheel `dev20260625+cuda12.6.torch2.11.0`). Nghịch lý: model fine-tune-able (`zzasdf` 68M) LẠI KÉM hơn hynt-30M+hotwords trên lệnh (64.9% < 82.5%); model tốt nhất (hynt 30M) KHÔNG có checkpoint train (chỉ jit_script.pt). Fine-tune zzasdf collapse (loss tự viết bug: base loss 385 dù decode chuẩn; forward trả 5 giá trị, cần simple/pruned_loss_scale+warmup như train.py; LoRA cũng ⁇). → GIỮ B1. Env B2 sẵn cho tương lai (cần data THẬT đa giọng + recipe `zipformer_lora` + sửa loss). Chi tiết: memory `stt-zipformer-vi-transducer-test`. (Đã xóa file thử nghiệm B2 nặng — tải lại từ HF `zzasdf/viet_iter3_pseudo_label` + clone icefall nếu cần.)

### C. Deploy xuống chó — ĐANG LÀM
1. **scp code segmenter MỚI** (combo_matcher.py + reflex_matcher.py + assistant_realtime.py) xuống chó — BẮT BUỘC, nếu không chó chạy code cũ ~57% (không có Tầng 1.5).
2. **scp GGUF mới** (govoice-qwen2.5-1.5b-q4_k_m.gguf đã retrain) xuống chó, restart llama-server.
3. Sửa config.yaml chó: stt device cuda + model phowhisper-small-ct2-fp16 + beam_size 5 (đã làm).
4. Test `run_demo_noaction.py --voice --mic-robot` (nghe-nói, chưa hành động).
5. Khi ổn: `run_real_robot.py` (gõ phím → giọng nói, đứng sát cầm remote).

### D. Cho bài báo
- **Bảng ablation 3 cột ĐÃ CÓ**: baseline 5.7% → fine-tune 61.7% → full system **91.0%** (xem §5). Tùy chọn thêm cột 0.5B.
- **Tỉ lệ định tuyến ĐÃ ĐO**: 82% câu giải bằng Reflex+Combo (~0.07ms, không LLM), 18% qua LLM → điểm nhấn realtime + neuro-symbolic.
- **Latency STT ĐÃ ĐO**: CPU 2-4s → GPU ~1.8s (Jetson Orin, PhoWhisper-small). LLM-only tb 780ms/p95 1197ms.
- WER PhoWhisper trên mic robot vs mic thường (còn đo).
- Trích dẫn: PhoWhisper (ICLR 2024), Qwen2.5, llama.cpp GBNF, SmolVLA (2506.01844), Piper.

---

## 7. QUY ƯỚC QUAN TRỌNG (đừng phá khi sửa code)

- **Vận tốc chuẩn Reflex:** vx=0.35, vy=0.25, vyaw=0.8 (đi bộ an toàn). Lùi = -0.28
- **Giới hạn an toàn:** vx≤0.6, vy≤0.4, vyaw≤1.0, mỗi lệnh ≤6s, trần tổng 30s
- **Chẻ lệnh:** quãng đường/góc lớn → nhiều lệnh ≤6s nối nhau (KHÔNG cắt cụt). PHẢI nhất quán ở 3 nơi: reflex_matcher (`_move_with_amount`), gen_dataset (`mv_split`), combo_matcher (qua Reflex). Trọng tài evaluate.py gộp move tương đương nên chỉ cần TỔNG quãng đường đúng
- **combo_matcher locations**: từ vựng địa điểm go_to phải khớp waypoints.yaml + DEFAULT_LOCATIONS. Match dùng \b word-boundary, longest-first
- **SYSTEM_PROMPT** dùng CHUNG giữa train (train_lora.py import) và chạy (llm_planner.py) — không được lệch
- **fewshot=false** khi dùng model fine-tuned (vì few-shot đã "nướng" vào model)
- **dry_run/force_real:** demo luôn ép giả, real cần checklist xác nhận
- Người dùng giao tiếp tiếng Việt, thích copy-paste từng lệnh, một việc một lúc, cần "đáp án đúng nhất + nhanh nhất"
- Mọi file Python phải chạy được Python 3.10 (KHÔNG f-string chứa backslash trong {})

---

## 8. CÁCH CHẠY NHANH (cheat sheet)

```bash
# --- LAPTOP ---
cd ~/Documents/Go2_assitant && source venv/bin/activate
# Terminal 1: não — ⚠️ DÙNG GGUF FINE-TUNE, KHÔNG dùng model gốc ~/models/...!
#   (nạp nhầm model gốc = eval ra 7.7% giả. Kiểm: curl localhost:8080/props)
~/llama.cpp/build/bin/llama-server -m ~/Documents/Go2_assitant/finetune/govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
# Terminal 2: test
python3 test_reflex.py                           # 14/14
python3 combo_matcher.py                          # smoke-test segmenter
python3 run_demo_noaction.py --voice             # nghe-nói, không hành động

# --- FINE-TUNE ---
cd finetune
python3 gen_dataset.py                            # ~4700 mẫu (chẻ giữ full distance)
python3 train_lora.py --base 1.5b --epochs 4     # ~70 phút RTX 4060 (cần torch CUDA!)
python3 merge_lora.py --base 1.5b
bash export_gguf.sh merged_1.5b govoice-qwen2.5-1.5b
python3 eval_e2e.py --tag e2e_final --no-fewshot  # TOÀN HỆ THỐNG (số quan trọng nhất)
python3 evaluate.py --tag finetuned_v2 --no-fewshot   # LLM-only (cho bảng ablation)

# --- JETSON (sau khi scp code + models + gguf xuống) ---
ssh unitree@192.168.123.18                       # pw 123
# build llama.cpp -DCMAKE_CUDA_ARCHITECTURES=87
# Terminal 1: llama-server với govoice gguf
# Terminal 2 (mic robot): export PYTHONPATH=~/go2_webrtc_new; export GO2_IP=192.168.123.161; python3 go2_audio_bridge.py
# Terminal 3: python3 run_demo_noaction.py --voice --mic-robot
```
