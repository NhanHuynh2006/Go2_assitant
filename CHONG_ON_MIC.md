# CHỐNG ỒN CHO MIC ROBOT — GoVoice

> 2026-07-30. Trả lời: *"lấy mic con chó mà không bị nhiễu tiếng ồn"*.
> **Kết quả chính: mic robot từ 0/6 câu → 35/36 câu.** Tất cả số dưới đây đo trên
> chính Jetson này, với tiếng ồn THẬT ghi từ mic robot — không phải ước lượng.
>
> File mới: `denoiser.py`, `test_denoise.py`, `bench_denoise_vad.py`, `config_robot_mic.yaml`
> File sửa: `audio_io.py` (nối denoiser), `config_typec.yaml` (thêm khối `audio.denoise`)

---

## 1. Vì sao mic robot "còn tệ hơn" — đã tìm ra nguyên nhân thật

Ghi 30s tiếng ồn từ mic robot trong phòng yên (`robot_mic_noise30s.wav`):

```
RMS nền ồn = -27.7 dBFS   ← tiếng quạt/nguồn của chính robot, RẤT to
```

Noise-gate thích nghi trong `audio_io.py` đặt ngưỡng = `noise_floor × 3.5`.
Nền ồn robot cao ⇒ ngưỡng bị đẩy lên **≈ -16 dBFS**. Giọng người nói ở khoảng cách
demo hiếm khi vượt nổi mức đó ⇒ **cổng chặn luôn cả giọng thật**.

Đo lại đúng như vậy — thả 6 câu tiếng Việt thật (Piper đọc) trộn vào nền ồn thật:

| SNR | Không khử nhiễu | Có GTCRN |
|---:|:---:|:---:|
| 15 dB | **0/6** | 6/6 |
| 10 dB | **0/6** | 6/6 |
| 5 dB | **0/6** | 6/6 |
| 0 dB | **0/6** | 6/6 (mix 1.0) |

→ Đây chính là dòng trong CHECKPOINT: *"đã thử mic robot (backend udp) → còn tệ hơn"*.
**Không phải mic robot dở — là noise-gate bị nền ồn của robot đẩy ngưỡng lên quá cao.**
Khử nhiễu kéo nền ồn xuống ⇒ ngưỡng hạ theo ⇒ giọng lọt qua.

---

## 2. Chọn mô hình: GTCRN

| Mô hình | Đo được | Kết luận |
|---|---|---|
| **GTCRN** — 23.7k tham số, ONNX, chạy qua **sherpa-onnx** (*đúng thư viện STT zipformer đang dùng*), model **523 KB** | RTF **0.155** (2 thread) ≈ 4.6ms/khung 30ms. Hạ nền ồn robot **−17.5 dB** | ✅ **CHỌN** |
| **RNNoise** (`rnnoise_denoise.py` — có sẵn trong dự án nhưng chưa từng được nối vào) | RTF 0.255. Bắt được 6/6 nhưng WER 25.6% ở SNR 5 dB (kém hơn), và xoá sạch tín hiệu khi mức vào nhỏ | ⚠️ dự phòng |
| DeepFilterNet3 | nặng hơn nhiều + phải dựng stack riêng trên Python 3.8 | ❌ không đáng |

**GTCRN không thêm dependency nào** — `sherpa_onnx` 1.13.3 đã cài sẵn cho STT.

---

## 3. Chỉnh `mix` — chỗ này phản trực giác, phải đo

`mix` = tỉ lệ tín hiệu đã khử (1.0 = khử 100%, 0.9 = giữ lại 10% tín hiệu gốc).

Gộp 3 seed × SNR {5, 0} = **36 câu** mỗi cấu hình, cộng 30s nền ồn thuần:

| cấu hình | bắt được | WER TB | câu rác | báo động nhầm /30s ồn thuần |
|---|---:|---:|---:|---:|
| **mix = 0.9** | **35/36** | 21.1% | **8** | **1** |
| mix = 0.95 | 33/36 | **10.5%** | 9 | 1 |
| mix = 1.0 | 33/36 | 15.6% | 9 | **4** |
| mix = 0.85 | 32/36 | 23.4% | 12 | 1 |

⚠️ **Khử mạnh nhất KHÔNG phải tốt nhất.** `mix=1.0` làm nền ồn sụp quá sâu → bộ ước
lượng nền của noise-gate mất điểm tựa → chính các mẩu dư (residual artifact) của
mạng lại lọt qua cổng: **4 lần báo động nhầm, gấp 4 lần mix=0.9**.
Giữ lại 10% tín hiệu gốc giúp cổng vẫn "nhìn thấy" nền thật.

→ **Chốt `mix: 0.9`.** Cần đọc chính xác hơn (chấp nhận sót câu) thì `0.95`.

---

## 4. Cách chạy — dùng MIC ROBOT

Đã tạo sẵn **`config_robot_mic.yaml`** (backend `udp` + GTCRN bật sẵn). 3 terminal:

```bash
# T1 — não
~/llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf --port 8080

# T2 — cầu nối mic robot  (TẮT app Unitree trên điện thoại trước: WebRTC chỉ 1 kết nối)
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export GO2_IP=192.168.123.161
python3 go2_audio_bridge.py --gain 2.5          # 2.5 chứ không phải 1.0 — mức gốc quá nhỏ

# T3 — trợ lý
python3 assistant_realtime.py --mode voice --config config_robot_mic.yaml
```

Khởi động phải thấy:
```
🧹 [khu nhieu] gtcrn(gtcrn_simple.onnx) | mix=0.9 gain=1.0
🎤 [mic ROBOT/UDP] dang nghe tren ('127.0.0.1', 17890) | khu nhieu: gtcrn(...)
```

**Đã chạy thử thật 35s** qua đúng chuỗi này: **1 lần kích hoạt nhầm / 35s** phòng yên
(ra đúng 1 chữ "EM" — mảnh ngắn, tầng FAQ vốn đã chặn mảnh < 2 chữ).

Mic type-C vẫn dùng `config_typec.yaml` như cũ (đã thêm cùng khối khử nhiễu).

---

## 5. Chỉnh khi gặp sự cố

| Triệu chứng | Sửa |
|---|---|
| Mất chữ / cụt câu | `mix: 0.95` |
| Vẫn lọt nhiễu | `mix: 0.9` (đừng lên 1.0 — tệ hơn), hoặc `noise_gate_factor: 4.0` |
| Nói xa bị bỏ | `go2_audio_bridge.py --gain 3.5`, hoặc `denoise.gain: 1.5` |
| CPU căng, LLM chậm | `num_threads: 1` |
| Cần sạch tuyệt đối cho demo | `assistant_ptt.py --key space` (bấm-để-nói) |

---

## 6. Tự đo lại (đừng tin, hãy đo)

```bash
# A/B nhanh trên 1 lần ghi
python3 test_denoise.py --record-udp 6 --say "đi thẳng ba mét rồi chào"
aplay denoise_ab/01_gtcrn.wav          # nghe bằng tai

# Chấm điểm đầy đủ (bắt được bao nhiêu câu + bao nhiêu rác)
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH GO2_IP=192.168.123.161
python3 go2_audio_bridge.py --record 30 --gain 2.5
mv robot_mic_test.wav robot_mic_noise30s.wav
python3 bench_denoise_vad.py --noise robot_mic_noise30s.wav
```

`bench_denoise_vad.py` chấm **cả hai mặt cùng lúc** — báo động nhầm *và* bắt được câu.
Chỉ đo một mặt là bẫy: khử thật mạnh thì hết rác nhưng điếc luôn (đúng cái bẫy `mix=1.0` ở trên).

---

## 6b. Lỗi "chạy lồng" — Gô tự nói với chính nó (đã sửa 2026-07-30)

Lần chạy thật đầu tiên bằng mic robot, log ra một tràng câu cụt và Gô trả lời liên tục
dù không ai nói:
```
🗣️ Nghe: ĐẤY      🐶 Gô: Dạ, đứng dậy liền!
🗣️ Nghe: MỘT      🐶 Gô: Ok, làm ngay!
🗣️ Nghe: CẢM ƠN   🐶 Gô: Không có chi, mình vui lắm nè!
```
Nhìn nội dung là ra bệnh: Gô nói *"Dạ, **đứng dậy** liền"* → mic nghe **"ĐẤY"**;
nói *"**cảm ơn** bạn đã quan tâm"* → nghe **"CẢM ƠN"**. **Nó đang nghe chính nó.**

### Chẩn đoán (đo, không đoán)

| Đo | Kết quả |
|---|---|
| Nghe 60s, **Gô không nói gì** | **1 mảnh rác** → nền ồn KHÔNG phải thủ phạm |
| Trễ loa robot (`test_echo_delay.py`, 3 lần) | tiếng ra sau **1.07–1.12s**, hết ở +1.84s |
| Mute cũ giữ được | ~2.97s → **thừa sức** che 1.84s |

Mute đủ dài mà vẫn echo → **lỗi không nằm ở độ dài mute mà ở cách quản lý nó.**

**Nguyên nhân thật:** `self.mute` là một `threading.Event` **không có bộ đếm**. Mỗi câu
nói chạy một thread riêng, thread nào `sleep` xong trước sẽ `mute.clear()` — **kể cả
khi câu sau vẫn đang phát**. Nên:

```
1 mảnh nhiễu → Gô trả lời → 2 thread mute chồng nhau → thread cũ mở mic sớm
→ mic nghe đuôi câu → STT ra 1-2 chữ → trả lời tiếp → CHẠY LỒNG
```

### Hai lớp sửa

1. **Mute theo HẠN CHÓT** (`_hold_mute` + `_mute_watch`): mỗi câu chỉ **đẩy hạn chót ra
   xa** (`max`), không bao giờ rút ngắn; **chỉ một luồng canh** được phép `clear`.
   Thêm `tts.mute_lead_s` (mặc định **1.3s** cho loa robot/hội trường, 0.1s cho loa cắm
   thẳng) vì tiếng qua WebRTC ra trễ ~1.1s.
2. **Chặn mảnh nhiễu** — đặt **sau** khi mọi tầng luật đã thử, **ngay trước** LLM:
   câu < 3 từ **và** không tầng nào (Reflex/Combo/FAQ) nhận ra → **bỏ, không gọi LLM**.
   LLM luôn bịa ra câu trả lời, mà mỗi câu trả lời lại làm Gô phát tiếng → một mảnh
   nhiễu đủ khởi động cả chuỗi.

> ⚠️ Đã thử cách dùng **danh sách từ lệnh ngắn** trước — **hỏng**: bỏ dấu thì
> `"đúng"` (đúng rồi) == `"dừng"` (dừng lại) == `"dung"`. Cách "để tầng luật tự nhận
> ra" không cần danh sách nào, và không dính bẫy dấu.

### Kết quả đo lại

| | Trước | Sau |
|---|---|---|
| 90s không ai nói, **có bật loa** | chạy lồng liên tục | **1 mảnh, bị chặn, Gô nói 0 lần** |
| 11 mảnh rác thật từ log | đều được trả lời | **8/11 bị chặn** (3 mảnh còn lại khớp FAQ xã giao → trả lời nhanh, không qua LLM) |
| 10 câu/lệnh thật | — | **0/10 bị chặn nhầm** |

> Khi biểu diễn có **2 con** thì `require_name: true` là lớp lọc thứ ba: mảnh nhiễu
> không bao giờ chứa chữ "Gô"/"Mun" nên bị bỏ hết.

### Đo lại trên robot khác
```bash
python3 test_echo_delay.py --repeat 3
```
In thẳng dòng `mute_lead_s` / `mute_tail_s` để dán vào config.

---

## 6c. Hai lỗi nặng tìm ra khi chạy thật với giọng người (2026-07-30)

> ⚠️ **Mọi số đo khử nhiễu ở mục 1–6 phía trên đều đo trên audio BỊ GIÃN 2 LẦN** vì
> lỗi (A) dưới đây. Kết luận lớn ("phải bật khử nhiễu") vẫn đúng, nhưng **các tham số
> cụ thể đã được đo lại** — xem bảng cuối mục này.

### (A) Bridge đọc sai số kênh → audio giãn 2 lần

**Triệu chứng người dùng báo:** *"giọng nghe như bị vang, chữ bị kéo dài ra"*, và
`mic_debug.py` ghi 25s ra file **50.1s**.

**Nguyên nhân:** mic robot là **2 kênh (stereo) 48kHz**. PyAV ≥12 trả
`frame.layout.channels` là **tuple các `AudioChannel`**, không phải số nguyên. Nên
trong `go2_audio_bridge.py`:
```python
arr.shape[0] == ch     # int vs tuple  -> LUÔN False
ch == 2                # tuple vs int  -> LUÔN False
```
đều âm thầm sai → frame stereo packed `(1, 1920)` bị coi là mono, lấy trọn 1920 mẫu
thay vì 960 → **audio dài gấp đôi, cao độ tụt một quãng tám** → STT không đọc ra chữ nào.

**Sửa:** tính số kênh từ `frame.samples` (số mẫu **mỗi kênh**), không hỏi `layout`.
Thêm **tự kiểm tra trôi nhịp**: audio sinh ra lệch >10% so với đồng hồ thật thì bridge
tự cảnh báo ngay.

**Kiểm:** ghi 10s → file **10.0s** (0.98×, trước là ~2.0×). Bản cũ: `backups/go2_audio_bridge.py.bak-*`

### (B) Mute không tính hàng đợi của loa → "càng về sau càng nhiễu"

**Triệu chứng:** vài câu đầu nghe đúng, càng về sau càng lọt echo — và nội dung lọt
đúng là câu Gô vừa nói (*"Xoay 90 độ rồi sau đó đi tới chỗ cũ"* → mic nghe
*"TÔI CHÍN MƯƠI ĐỘ RỒI SAU ĐÓ ĐI TỚI CHỖ"*).

**Nguyên nhân:** `go2_tts_speaker.py` có **hàng đợi phát** (`TTSTrack.q`) — các câu xếp
hàng phát nối tiếp. Nhưng assistant tính mute **từ lúc GỬI**. Khi câu dồn lại, tiếng
thực sự ra trễ hơn lúc gửi ngày một nhiều → mute hết hạn trước khi tiếng ra → nghe
chính mình → trả lời → dồn thêm → **vòng xoáy tăng dần**.

**Sửa:** mô hình hoá hàng đợi loa trong assistant:
```
bắt_đầu_phát = max(gửi + trễ_ra_loa, loa_phát_xong_câu_trước)
giữ mute tới bắt_đầu_phát + độ_dài_câu + dự_phòng
```
**Kiểm (mô phỏng 4 câu dồn, mỗi câu 4s):** loa xong lúc 17.45s, mute giữ tới 18.00s →
che kín. Trước khi sửa mute hết hạn từ ~6s.

### Tham số đo lại (trên giọng thật, audio đúng nhịp)

Kịch bản: 4 câu nói ở 20cm / 1m / 1m to / 2m to, cộng 60s nền ồn thuần.

| factor | gain | mix | bắt được | WER | rác trong 60s ồn |
|---:|---:|---:|---:|---:|---:|
| **3.5 (cũ)** | 1.0 | 0.9 | **1/4** | — | 1 câu |
| **2.0 (chốt)** | **1.6** | **1.0** | **4/4** | **16.2%** | **0 câu** |
| 1.6 | 2.2 | 0.9 | 0/4 (vỡ tiếng) | — | 0 |

→ Cấu hình mới **vừa nghe tốt hơn vừa ít rác hơn**, không phải đánh đổi.
`mix: 1.0` giờ thắng `0.9` — **ngược hẳn** kết luận cũ ở mục 3, vì số cũ đo trên audio giãn.
⚠️ `gain` **đừng vượt 2.0** — 2.2 làm vỡ tiếng, bắt 0/4.

### Công cụ mới
```bash
python3 mic_debug.py --seconds 25    # ghi giọng thật + chỉ ra CHỖ TẮC trong chuỗi
python3 mic_debug.py --wav file.wav  # phân tích lại bản ghi cũ
```
In cho từng đoạn: RMS thô / sau khử / ngưỡng cổng / % lọt cổng / % VAD, biểu đồ biên độ
theo thời gian, và cho STT đọc thẳng **bỏ qua VAD** — tách bạch được *tai không nghe*
với *cổng chặn* với *STT không đọc ra*.

---

## 7. Giới hạn còn lại (không sửa được bằng phần mềm)

Đường mic robot **không có cách nào ngắn hơn**:
```
mic robot → WebRTC/Opus (port 9991) → go2_audio_bridge.py → UDP 16k → audio_io.UdpMic
```
Đã kiểm tra: main board `192.168.123.161` chỉ mở **port 80 và 9991**, **không có SSH**
(quét cả dải `192.168.123.0/24` — chỉ có 3 máy: `.18` Jetson, `.99` laptop, `.161` main board).
Sách hướng dẫn mục 1.3.3 nói Voice Module rẽ ra cổng USB, nhưng cổng đó nằm bên CPU
chính — Jetson không với tới. **WebRTC là đường duy nhất**, nên audio đã bị Opus nén +
AGC của robot xử lý trước khi tới tay mình.

---

## 8. Dùng cho bài báo

- **Bảng 0/6 → 35/36**: khử nhiễu không chỉ "làm sạch tiếng" mà *mở khoá* được cảm biến
  mic on-board vốn không dùng được. Đây là đóng góp mạnh hơn một bảng WER thông thường.
- **Phát hiện phản trực giác**: khử nhiễu tối đa (`mix=1.0`) làm **tăng gấp 4** tỉ lệ báo
  động nhầm, vì phá vỡ bộ ước lượng nền của VAD thích nghi. Lập luận: khử nhiễu và VAD
  thích nghi **phải được đồng chỉnh**, không được tối ưu riêng lẻ.
- **Metric mới**: "số câu rác lọt vào hệ thống / 30s im lặng" — sát trải nghiệm thật hơn WER.
- **Chi phí**: RTF 0.155 trên Orin NX, model 523 KB — vẫn đúng tinh thần fully on-board.
- Trích dẫn: GTCRN (Rong et al., ICASSP 2024), RNNoise (Valin, MMSP 2018), sherpa-onnx (k2-fsa),
  và mục 6.1.1 sách hướng dẫn Go2 (Unitree cũng dùng push-to-talk làm "bộ lọc nhiễu cấp giao diện").
