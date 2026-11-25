# 🔊 Trị mic con chó bị RÈ/MÉO/Ù — hướng dẫn từng bước

> Mic robot ở xa, có tiếng quạt/động cơ, đi qua WebRTC resample 48k→16k.
> Bản `go2_audio_bridge.py` v2 đã sửa tận gốc 4 nguyên nhân. Làm theo thứ tự dưới.

## BƯỚC 1 — Cài thư viện xử lý âm thanh (trên Jetson)

```bash
pip3 install scipy            # BAT BUOC: resample chuan, het re/meo
pip3 install noisereduce      # tuy chon: loc on quat/dong co
```
> `scipy` là quan trọng nhất — nó thay phép "trung bình 3 mẫu" (gây méo) bằng
> polyphase resampling có lọc chống aliasing đúng chuẩn.

## BƯỚC 2 — GHI THỬ 5 giây để nghe tận tai (chẩn đoán)

```bash
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export GO2_IP=192.168.123.161
# TAT app Unitree truoc!
python3 go2_audio_bridge.py --record 5
# noi vai cau trong 5 giay do, roi:
aplay robot_mic_test.wav
```
Nghe file này và đối chiếu:

| Nghe thấy | Nguyên nhân | Cách trị |
|---|---|---|
| Đỡ rè hơn nhiều rồi | scipy đã trị được | Xong! Dùng bình thường |
| Tiếng nhỏ xíu, xa xăm | mic xa, gain thấp | thêm `--gain 2.5` |
| Còn ù trầm | tiếng động cơ | đã có high-pass; nếu còn → `--denoise` |
| Rẹt rẹt, ngắt quãng | mạng WebRTC rớt gói | xem BƯỚC 4 |
| Vẫn méo như cũ | scipy chưa cài | `pip3 install scipy` lại |

## BƯỚC 3 — Chạy thật với tham số đã tinh chỉnh

Ví dụ mic nhỏ + ồn:
```bash
# Terminal 1:
python3 go2_audio_bridge.py --gain 2.5 --denoise

# Terminal 2:
python3 run_demo_noaction.py --voice --mic-robot
```
Chỉnh dần `--gain` (1.5 → 3.0) tới khi STT bắt ổn. Đừng để quá cao kẻo méo do clip.

## BƯỚC 4 — Nếu rẹt/ngắt quãng (lỗi mạng, không phải mic)

WebRTC qua WiFi rớt gói → tiếng ngắt. Thử:
- Jetson cắm **dây LAN** thay WiFi tới robot (ổn định hơn hẳn)
- Hoặc lại gần router
- Kiểm tải mạng: tắt các stream video/SLAM đang chạy song song

## BƯỚC 5 — Bù ở tầng STT (nếu vẫn còn sai chút ít)

Trong `config.yaml`, mic ồn thì nới VAD + tăng beam:
```yaml
stt:
  beam_size: 5              # ồn thì để 5 cho chính xác (đừng để 1)
  model: "models/phowhisper-small-ct2"   # ồn thì small > tiny
audio:
  vad_aggressiveness: 3     # khó tính với ồn nền
  min_utterance_s: 0.5      # bỏ tiếng tách ngắn
```

---

## Tóm tắt — làm gì trước
1. `pip3 install scipy` (90% là đủ — đây là thủ phạm chính)
2. `python3 go2_audio_bridge.py --record 5` rồi `aplay robot_mic_test.wav` nghe thử
3. Còn nhỏ → `--gain 2.5` | còn ồn → `--denoise`
4. Còn ngắt → cắm LAN cho Jetson

Gửi mình file `robot_mic_test.wav` nghe thế nào (rõ chưa / nhỏ / ù / ngắt) — mình chỉnh tiếp tham số chính xác cho bạn.
