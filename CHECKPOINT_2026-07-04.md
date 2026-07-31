# CHECKPOINT 2026-07-04 — GoVoice chạy ổn định (nghe → nghĩ → nói → hành động)

> Mốc "hệ đã chạy tốt": mic realtime không treo, không echo loop, robot đi thật
> giới hạn 50cm/lệnh, có chế độ bấm-để-nói, có bộ sửa chính tả STT.
> Nếu sau này sửa gì hỏng → đối chiếu/khôi phục theo file này.

---

## 1. TỔNG QUAN KIẾN TRÚC (không đổi)

```
mic USB ──> audio_io (VAD cắt câu) ──> STT (zipformer transducer ~70-200ms)
        ──> định tuyến: Combo (luật ghép) → Reflex (luật đơn) → LLM (llama-server)
        ──> SafetyGuard (clamp + chặn 50cm) ──> AsyncExecutor (thread riêng) ──> robot
        ──> TTS piper ──> UDP :17891 ──> go2_tts_speaker (WebRTC) ──> loa robot
```

3 terminal khi demo:
1. `./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080`
2. `export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH; export GO2_IP=192.168.123.161; python3 go2_tts_speaker.py`
3. `python3 assistant_realtime.py --mode voice --real`  (hoặc `assistant_ptt.py --real`)

---

## 2. CÁC SỬA ĐỔI TRONG CHECKPOINT NÀY (theo thứ tự đã làm)

### 2.1 `audio_io.py` — mic không bao giờ treo cứng nữa
**Vấn đề:** mic USB CS202 (full-speed, qua hub) thỉnh thoảng mở được nhưng không
stream → `stream.read()` chặn kẹt VĨNH VIỄN trong poll() của ALSA, Ctrl+C vô dụng,
tiến trình chết ôm mic làm lần chạy sau cũng hỏng.
**Sửa (`LocalMic.listen()`):**
- Đọc kiểu **poll** (`read_available` + sleep 5ms) thay vì blocking read
  → Python giữ quyền điều khiển, Ctrl+C ăn ngay.
- **Watchdog `STALL_S = 0.8`**: mic không ra dữ liệu quá 0.8s → tự stop/close
  → mở lại stream (thử tối đa 20 lần, mỗi lần cách 0.5s) + `seg.reset()`.
- `resolve_input_device()` (thêm sau): config `input_device: "auto"` tự quét mic
  USB đầu tiên (bỏ qua card nội bộ APE/HDA/pulse...); tên sai → tự fallback auto.
- `ensure_capture_gain()`: hub/mic USB hay RESET GAIN THU sau khi rút cắm. Quá
  thấp (15%) → mic câm, VAD kích nhiễu ảo; quá cao (100% = +32dB) → VỠ TIẾNG,
  VAD trượt câu nói thật (đo thực tế: 25% nghe tốt, 100% liên tục "không nghe
  thấy gì"). Giờ mỗi lần mở mic tự `amixer -c N sset Mic <mic_gain>%` — chỉnh
  bằng `audio.mic_gain` trong config, mặc định 25.
**Rollback:** quay về `stream.read(blocksize)` chặn trong `with RawInputStream(...)`
(bản cũ) — KHÔNG khuyến nghị, sẽ treo lại.

### 2.2 `assistant_realtime.py` — 3 thay đổi
a) **Chống echo loop** (`_speak_async`): trước đây thả mute sau 0.25s trong khi loa
   robot phát trễ vài giây qua WebRTC → robot NGHE CHÍNH NÓ và tự trả lời vòng lặp.
   Giờ giữ mute = `tts.last_audio_s + 1.2s` (thời lượng wav + biên độ WebRTC).
   Chỉnh biên độ tại dòng `time.sleep(dur + 1.2 ...)` nếu còn sót echo (tăng 1.8–2.0).
b) **Mic chạy LUỒNG RIÊNG** (`run_voice`): trước đây mic+STT+LLM chung luồng →
   LLM nghĩ 2.5s là mic bị bỏ đói → ALSA tràn → "mic treo" mất nhịp. Giờ luồng
   capture chỉ đọc mic đẩy vào `queue.Queue(maxsize=20)` (đầy → bỏ câu cũ giữ câu
   mới); luồng chính lấy ra STT+LLM.
c) **Sửa chính tả STT gated** (`process`): câu không khớp luật → thử bản đã sửa
   qua `text_normalizer`; CHỈ nhận nếu bản sửa khớp thành lệnh thật, không thì giữ
   nguyên cho LLM. In `✎ sua chinh ta: ...` khi kích hoạt.
   + `GoVoiceRT.__init__` nạp `self.normalizer = TextNormalizer(extra_vocab=địa điểm)`.
   + Truyền `max_step_m` vào RobotTools + SafetyGuard.

### 2.3 `tts_engine.py` — thêm `self.last_audio_s`
Đo thời lượng wav (frames/rate) mỗi lần gửi loa robot trong `_send_to_robot()`
→ để 2.2a giữ mute đúng hạn. Khởi tạo `last_audio_s = 0.0` trong `__init__`.

### 2.4 `robot_tools.py` + `safety_guard.py` — chặn quãng đường ~50cm/lệnh
- Tham số mới `max_step_m` (mặc định 0.5) ở CẢ 2 lớp (guard + actuator).
- Logic: `speed = hypot(vx,vy)`; nếu `speed*duration > max_step_m` → rút ngắn
  `duration = max_step_m/speed`. Xoay tại chỗ (vx=vy=0) KHÔNG bị chặn.
- Đã test: yêu cầu 3.6m → thực đi 50cm; 30cm giữ nguyên; đi chéo cũng đúng 50cm.

### 2.5 `config.yaml` — thêm section `robot:` + cắt câu nhanh hơn
```yaml
audio:
  silence_end_ms: 200        # cũ 270 → cắt câu sớm hơn ~70ms
robot:
  dry_run: true              # bật thật bằng cờ --real (run_demo_noaction LUÔN giả)
  max_vx: 0.3  max_vy: 0.25  max_vyaw: 0.8  max_duration: 3.0
  max_step_m: 0.5            # ← 50cm/lệnh
  require_stand_before_move: true
```

### 2.6 `assistant_ptt.py` — MỚI: chế độ bấm-để-nói (outdoor chống ồn)
- Bấm phím **T** (1 lần) → mic mở nghe đúng 1 câu → VAD tự ngắt khi im lặng →
  xử lý xong → chờ bấm T tiếp. `q`/Ctrl+C thoát.
- Không nói gì 8s → tự bỏ; mic stall 1.5s → tự bỏ (không kẹt).
- Đợi Gô nói xong (mute) mới mở mic. Đổi phím: `--key space`.
- Chạy: `python3 assistant_ptt.py --real` (giữ nguyên assistant_realtime).

### 2.7 `text_normalizer.py` — MỚI: sửa chính tả STT (an toàn nhờ GATE)
- Sửa từ lệch về từ lệnh: bảng tay (`xay→xoay, chinh→chín, qoay→quay...`) +
  fuzzy Levenshtein≤1 + stoplist từ phổ thông.
- AN TOÀN vì **gate ở pipeline** (2.2c): bản sửa chỉ được dùng nếu khớp thành lệnh
  → câu trò chuyện KHÔNG BAO GIỜ bị bóp méo (đã test 12 câu hội thoại: 0 hỏng,
  7 lệnh nghe sai: cứu được hết).
- Thêm từ vựng SLAM sau này: `TextNormalizer(extra_vocab=[tên địa điểm...])` —
  tự nạp từ `DEFAULT_LOCATIONS` + keys của `waypoints.yaml`.

### 2.8 `hotwords.txt` — 70 → 99 cụm
Thêm: góc độ (30/60/120), khoảng cách (một/hai/ba mét, nửa mét, mét rưỡi),
giây, vòng, cụm go_to ("ĐI TỚI CÁI BÀN", "VỀ CHỖ CŨ"...), khẩn cấp
("DỪNG LẠI NGAY", "KHẨN CẤP"), từ nối "XONG". Đã test nạp + decode OK (~206ms).

### 2.9b `robot_tools.py` + `async_executor.py` — emergency cắt được lệnh ĐANG CHẠY
**Vấn đề (phát hiện khi demo PTT):** "dừng lại" chỉ xóa hàng đợi, KHÔNG cắt được
lệnh đang chạy: (a) vòng `move()` gửi Move 10Hz đè lên StopMove → robot đi hết
lệnh; (b) `Dance1()` chặn worker → StopMove của emergency phải xếp hàng chờ nhảy xong.
**Sửa:**
- `RobotTools.abort` (threading.Event): vòng `move()` kiểm tra mỗi 0.1s → thoát
  ngay + StopMove; `action()`/`go_to()` chặn trước khi bắt đầu (trừ standup/balance).
- `emergency_stop()`: bật cờ TRƯỚC, StopMove+BalanceStand gửi từ LUỒNG RIÊNG
  (không chờ sau lời gọi đang kẹt); `enqueue()` lệnh mới tự xóa cờ.
**Đo được:** lệnh đi cắt trong ~0.1s; emergency phản hồi 1ms kể cả khi đang nhảy;
lệnh xếp sau bị hủy; lệnh mới sau emergency chạy bình thường.
**Giới hạn còn lại:** động tác đóng gói (Dance1/2...) firmware tự chạy hết bài —
StopMove được gửi ngay nhưng không cam kết cắt tức thì → tránh cho nhảy chỗ chật.

### 2.9 `config_typec.yaml` — MỚI: biến thể cho mic Type-C
Giống config.yaml, chỉ khác `audio.input_device: "auto"`.
- **Mic cũ (jack 3.5 trên hub, tên CS202):** `python3 assistant_realtime.py --mode voice --real`
- **Mic mới (cổng Type-C):** `python3 assistant_realtime.py --mode voice --real --config config_typec.yaml`
(Nhờ auto-fallback trong audio_io, config.yaml cũng TỰ chuyển sang mic khác nếu
không thấy CS202 — 2 file là để tách bạch rõ ràng.)

---

## 3. NHỮNG GÌ ĐÃ ĐO — ĐỪNG LÀM LẠI (đã thử và loại)

| Ý tưởng | Kết quả đo | Kết luận |
|---|---|---|
| "Chuyển LLM sang GPU" | llama-server ĐÃ chạy GPU (`-ngl 99`, GR3D 91-99% khi suy luận, ~24 tok/s) | Không có gì để chuyển |
| Rút gọn grammar GBNF (bỏ khoảng trắng) | Model fine-tune LOẠN: nói tiếng Anh, mất actions | **Cấm sửa grammar.gbnf** |
| Prompt "nói ngắn + bỏ args=0" | Như trên, hỏng nặng hơn | **Cấm sửa SYSTEM_PROMPT** |
| PhoWhisper thay transducer | fp16: 7.2s/câu + bịa ("putin... triều tiên"); int8: lỗi dtype trên CUDA Jetson | Không dùng được ở đây |
| Fuzzy sửa chữ KHÔNG gate | "người→ngồi", "cười→duỗi", "nhìn→chín" (va chạm khi bỏ dấu) | Bắt buộc phải GATE |

Độ trễ hiện tại: Reflex/Combo ~70-160ms tổng; LLM 0.8-3.2s (trần phần cứng
= số token output ÷ 24 tok/s). Muốn nhanh hơn nữa chỉ còn: thêm luật Reflex/Combo,
hoặc đổi model nhỏ hơn (đánh đổi chính xác).

---

## 4. SỰ CỐ ĐÃ GẶP + CÁCH XỬ LÝ NHANH

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Đứng im không nghe, Ctrl+C vô dụng | Tiến trình cũ ôm mic (fd `(deleted)`, spin CPU) | `fuser -k /dev/snd/pcmC2D0c; sleep 1` rồi chạy lại |
| CS202 biến mất khỏi `sounddevice` | Mic đang bị tiến trình khác giữ | Như trên |
| Robot tự nói chuyện một mình | Echo loop (đã fix 2.2a) | Nếu tái phát: tăng biên độ 1.2→1.8 |
| `⚠️ mic treo` liên tục mỗi câu | Mic bị bỏ đói khi LLM chạy (đã fix 2.2b) | Còn lác đác = USB yếu thật → đổi cổng/hub |
| `lsusb`/sysfs treo, không card audio | USB bus wedge (hub/thiết bị kẹt enumerate) | Rút HẲN hub chờ 5s cắm lại; không được thì `sudo reboot` |
| Mic "nhận" nhưng thu toàn im lặng, STT bịa chữ ngắn | Gain thu bị reset quá thấp (15%) | Tự fix (`ensure_capture_gain` → `audio.mic_gain`, mặc định 25%) |
| VAD liên tục "không nghe thấy gì" dù nói to | Gain quá CAO (100%) → vỡ tiếng, VAD trượt | Hạ `audio.mic_gain` về 25 (điểm ngọt CS202) |
| Mic Type-C cắm hub: thu im lặng cả khi gain 100% | Mic/cổng Type-C của hub lỗi (đã thử 2026-07-04) | Dùng mic jack 3.5; test lại Type-C bằng `typec_mic_test.wav` |
| Loa robot im lặng | go2_tts_speaker chưa chạy (UDP :17891 không ai nghe) | Bật lại terminal 2; kiểm tra `ss -lunp \| grep 17891` |
| llama lỗi 429/NoSdpAnswer (WebRTC) | App Unitree trên điện thoại đang chiếm | Tắt app, chạy lại |

---

## 5. FILE TRONG CHECKPOINT (13 file liên quan)

| File | Trạng thái |
|---|---|
| `audio_io.py` | SỬA: poll+watchdog, resolve_input_device |
| `assistant_realtime.py` | SỬA: echo mute, capture thread, normalizer gate, max_step_m |
| `tts_engine.py` | SỬA: last_audio_s |
| `robot_tools.py`, `safety_guard.py` | SỬA: max_step_m 50cm |
| `config.yaml` | SỬA: robot section, silence 200ms |
| `hotwords.txt` | SỬA: 99 cụm |
| `assistant_ptt.py` | MỚI: bấm-để-nói |
| `text_normalizer.py` | MỚI: sửa chính tả gated |
| `config_typec.yaml` | MỚI: mic Type-C (input_device auto) |
| `grammar.gbnf`, `llm_planner.py`, `reflex_matcher.py`, `combo_matcher.py` | GIỮ NGUYÊN (cấm sửa grammar/prompt — xem mục 3) |

> Gợi ý: dự án chưa có git. Để checkpoint cứng:
> `cd ~/NhanHuynh/go2_jetson_demo && git init && git add -A ':!*.gguf' ':!llama.cpp' ':!models' && git commit -m "checkpoint 2026-07-04: he chay on dinh"`

---

## 6. VIỆC TIẾP THEO (đã bàn, chưa làm)

- [ ] Mic Type-C: xác nhận hệ nhận card → test bằng `python3 debug_vad_live.py auto`
- [ ] Khi build SLAM: đổ tên địa điểm thật vào `waypoints.yaml` (tự vào combo +
      normalizer), thêm cụm tương ứng vào `hotwords.txt`
- [ ] Cân nhắc phanh khẩn khi Gô đang nói (hiện mute chặn cả "dừng lại" lúc TTS phát)
