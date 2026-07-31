# RUN — cách chạy GoVoice (bản 2026-07-30)

> **Chọn config theo tình huống:**
>
> | Tình huống | Config | Mic | Loa |
> |---|---|---|---|
> | **Mặc định — dùng mic con chó** | `config_robot_mic.yaml` | mic robot (WebRTC→UDP) | loa robot |
> | **Biểu diễn hội nghị** | `config_hoinghi.yaml` | mic robot | **loa hội trường qua laptop** |
> | Mic USB type-C (cũ, không dùng nữa) | `config_typec.yaml` | mic USB | loa robot |
>
> Mic robot **bắt buộc bật khử nhiễu** — tắt là điếc hoàn toàn (0/6 câu). Xem `CHONG_ON_MIC.md`.
> Xem CHECKPOINT_2026-07-30.md để nắm thay đổi.

---

## Chạy với MIC CON CHÓ — 3 terminal (cách dùng thường ngày)

**T1 — LLM server** (bỏ qua nếu cổng 8080 đã có):
```bash
cd ~/NhanHuynh/go2_jetson_demo
./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
```

**T2 — Mic robot** (cầu WebRTC → UDP). Tắt app Unitree trên điện thoại trước:
```bash
cd ~/NhanHuynh/go2_jetson_demo
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export GO2_IP=192.168.123.161
python3 go2_audio_bridge.py --gain 2.5        # 2.5 chứ không phải 1.0 — mức gốc quá nhỏ
```

**T3 — Trợ lý:**
```bash
python3 assistant_realtime.py --mode voice --config config_robot_mic.yaml          # không cử động
python3 assistant_realtime.py --mode voice --config config_robot_mic.yaml --real   # cử động thật
```
Khởi động phải thấy:
```
🧹 [khu nhieu] gtcrn(gtcrn_simple.onnx) | mix=0.9 gain=1.0
🎤 [mic ROBOT/UDP] dang nghe tren ('127.0.0.1', 17890) | khu nhieu: gtcrn(...)
```

> Muốn nghe tiếng **ra loa robot** thì thêm terminal chạy `go2_tts_speaker.py`.
> ⚠️ **THỨ TỰ QUAN TRỌNG: bật `go2_tts_speaker.py` TRƯỚC**, đợi nó báo `>>> ... san sang`,
> **rồi mới** bật `go2_audio_bridge.py`. Bật ngược lại thì loa chết với
> `NoSdpAnswerError` (robot từ chối bắt tay WebRTC thứ hai khi cái đầu đang dở).
> Đúng thứ tự thì cả hai chạy song song bình thường.

---

## Biểu diễn HỘI NGHỊ — tiếng ra loa hội trường

Jetson **không có Bluetooth, không có jack 3.5** (chỉ HDMI). Nên cho **laptop làm loa** —
laptop đã có sẵn BT + jack và đang nối dây LAN với robot. Không tốn tiền mua gì.

**Trên LAPTOP** (làm trước):
1. Ghép laptop với loa hội trường (Bluetooth) **hoặc** cắm dây jack 3.5 vào mixer.
2. *Settings → Sound → Output*: chọn đúng loa đó, phát thử nhạc cho chắc.
3. `python3 pc_speaker.py`

**Trên JETSON:** sửa `pa_host` trong `config_hoinghi.yaml` thành IP laptop, rồi
```bash
python3 pc_speaker.py --test 192.168.123.99     # ⬅ THỬ TRƯỚC, loa phải kêu ngay
```
Kêu rồi thì chạy như 3 terminal ở trên, chỉ đổi config:
```bash
python3 assistant_realtime.py --mode voice --config config_hoinghi.yaml --real
```
`output: robot+pa` nếu muốn ra **cả hai** loa (robot + hội trường).

⚠️ Test đường loa **trước khi lên sân khấu**, đừng để tới lúc diễn mới biết.

---

## Cách nhanh nhất: test hỏi-đáp bằng GÕ CHỮ (không cần mic/loa/robot)
```bash
cd ~/NhanHuynh/go2_jetson_demo
# LLM server chạy nền (nếu chưa có — kiểm tra: curl -s 127.0.0.1:8080/health)
./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080 &
python3 assistant_realtime.py --mode text --config config_typec.yaml --no-tts
```
Gõ câu hỏi (bạn là ai / trường bạn tên gì / ISLab là gì / đi thẳng 3 mét...) → Gô in trả lời ngay.

---

## (Cũ) Chạy với MIC USB type-C — 3 terminal

**🖥️ Terminal 1 — LLM server** (bộ não). Nếu cổng 8080 đã có server thì BỎ QUA (đừng chạy trùng):
```bash
cd ~/NhanHuynh/go2_jetson_demo
./llama.cpp/build/bin/llama-server -m govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
```

**🖥️ Terminal 2 — Loa robot** (WebRTC):
```bash
cd ~/NhanHuynh/go2_jetson_demo
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export GO2_IP=192.168.123.161
python3 go2_tts_speaker.py
```
Đợi thấy "sẵn sàng". Nếu lỗi 429/NoSdpAnswer → tắt app Unitree trên điện thoại rồi chạy lại.

**🖥️ Terminal 3 — Trợ lý chính:**
```bash
cd ~/NhanHuynh/go2_jetson_demo
fuser -k /dev/snd/pcmC*D0c 2>/dev/null; sleep 1     # nha mic (quet moi card)

# (a) NÓI + NGHE, robot KHÔNG cử động (test an toàn):
python3 assistant_realtime.py --mode voice --config config_typec.yaml

# (b) NÓI + NGHE + LÀM ĐỘNG TÁC THẬT (ra chỗ trống!):
python3 assistant_realtime.py --mode voice --config config_typec.yaml --real
```
Khởi động phải thấy `🎤 [auto] chon mic: ... USB2.0 Device` và `gain ... -> 35%`.
Với `--real`, robot tự chuyển sang **AI mode** (`[robot] chuyen che do dong co -> 'ai'`, chờ ~3s).

---

## Chế độ bấm-để-nói (mic quá ồn → sạch tuyệt đối)
```bash
python3 assistant_ptt.py --config config_typec.yaml --key space   # thêm --real nếu muốn cử động
```
Bấm PHÍM CÁCH → nói ngay → tự ngắt. Bấm `q` để thoát.

---

## Lệnh nói thử
- **Điều khiển:** đi thẳng / lùi lại (2 mét) · sang trái/phải · xoay trái/phải · xoay 3 vòng · dừng lại (phanh khẩn) · ngồi xuống · đứng lên · nhảy · chào · thả tim.
- **Acrobatic (chỗ trống!):** đứng bằng hai chân · trồng chuối · nhảy về phía trước.
- **Hỏi-đáp:** bạn là ai · làm được gì · trường/lab/thầy · khỏe không · kể chuyện cười · ...

## Tinh chỉnh nhanh (config_typec.yaml)
- STT nhận nhiễu nhiều → tăng `noise_gate_factor` (3.5 → 4.0). Nói mà bị bỏ → hạ (3.0).
- STT nhỏ → tăng `mic_gain` (35 → 40). Nói gần bị vỡ tiếng → hạ (30).
- Chậm/an toàn lại chuyển động → hạ `max_vx`, `max_vyaw`. Cần cap khoảng cách → hạ `max_step_m`.
