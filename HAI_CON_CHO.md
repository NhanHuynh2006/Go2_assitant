# HAI CON CHÓ — nhảy đồng bộ + phỏng vấn từng con

> 2026-07-30. Kịch bản hội nghị: 2 con Go2 nhảy chung 1 bài → xong thì MC phỏng vấn từng con.
> File mới: `go2_troupe.py`, `config_cho_A.yaml`, `config_cho_B.yaml`
> File sửa: `assistant_realtime.py` (cổng gọi tên)

---

## 1. Nút thắt phải hiểu trước: **KHÔNG được nối chung 2 mạng LAN của 2 con**

Mỗi con Go2 có mạng nội bộ riêng, và **cả hai đánh số giống hệt nhau**:

| | Chó A | Chó B |
|---|---|---|
| Main board | 192.168.123.**161** | 192.168.123.**161** ← trùng |
| Jetson | 192.168.123.**18** | 192.168.123.**18** ← trùng |

Cắm dây cho 2 con vào chung 1 switch = **đụng IP**, hỏng cả hai. Đây là lý do
USB WiFi là lời giải đúng: mỗi Jetson có thêm **một địa chỉ thứ hai** trên wifi
chung, còn mạng `192.168.123.x` của từng con vẫn nằm riêng, không đụng nhau.

```
              ROUTER WIFI 5GHz (mang riêng, đừng xài wifi hội trường)
                │             │                  │
         wlan0  │      wlan0  │            wifi  │
      ┌─────────┴──┐   ┌──────┴─────┐   ┌────────┴────────┐
      │  CHÓ A     │   │  CHÓ B     │   │     LAPTOP      │
      │ 10.42.0.11 │   │ 10.42.0.12 │   │   10.42.0.10    │
      │  agent     │   │  agent     │   │ conduct+pc_spk  │──► loa hội trường
      └──────┬─────┘   └──────┬─────┘   └─────────────────┘
        eth0 │  .123.x   eth0 │  .123.x     (2 LAN RIÊNG, không nối nhau)
```

**Đặt IP tĩnh** cho 2 Jetson trên wifi đó (`10.42.0.11`, `.12`) — đừng để DHCP đổi
IP ngay lúc sắp diễn.

---

## 2. Tiết mục 1 — NHẢY ĐỒNG BỘ (`go2_troupe.py`)

### Nhạc phát từ LAPTOP, không phải từ loa chó

Đây là quyết định thiết kế quan trọng nhất:

- Loa chó **nhỏ**, hội trường không nghe rõ.
- Hai con cùng phát một bài thì lệch nhau vài trăm ms → nghe **dội như vọng âm**.

→ **Một nguồn nhạc duy nhất** (laptop → loa hội trường). Hai con chỉ NHẢY, theo
cùng một bản đồ beat mà nhạc trưởng tính sẵn bằng `librosa` rồi gửi cho cả hai.
Nhờ vậy hai con dùng **y hệt** một danh sách beat, không con nào tự phân tích lệch.

### Đồng bộ đồng hồ — không cần internet/NTP

Nhạc trưởng bắt tay kiểu SNTP với từng con (T1→T4, lấy mẫu **RTT nhỏ nhất** vì mẫu
đó ít bị wifi làm nhiễu nhất), tính độ lệch đồng hồ, rồi ra lệnh
*"khởi động lúc `<giờ RIÊNG của mày>`"*.

**Đã kiểm chứng:** cố tình cho 2 máy lệch đồng hồ **+2.5s** và **−1.2s**
(cách nhau 3.7 giây) → hệ đo ra `+2500.01ms` / `−1200.02ms` và hai con
bắt đầu nhảy cách nhau **0.10 ms**.

### Chạy

**Trên Jetson MỖI con:**
```bash
export PYTHONPATH=~/go2_webrtc_new:$PYTHONPATH
export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds
python3 go2_troupe.py agent --name A        # con kia: --name B
```

**Trên laptop:**
```bash
python3 go2_troupe.py conduct \
    --robots 10.42.0.11,10.42.0.12 \
    --music ~/dance.mp3 --play-here
```

Nhạc trưởng in ra sai số dự kiến trước khi diễn:
```
   10.42.0.11: RTT   3.21ms | lech   +12.40ms
   10.42.0.12: RTT   2.88ms | lech    -4.10ms
[dan] sai so dong bo du kien: ~1.6ms (TOT)
```
Nếu báo `HOI CAO — wifi yeu?` thì **đổi chỗ router lại gần**, đừng diễn.

### Tuỳ chọn
| Cờ | Tác dụng |
|---|---|
| `--latency 0.15` | bù trễ. Nhảy trễ hơn nhạc → tăng; sớm → giảm |
| `--special` | Dance1/Dance2 mỗi 32 beat (cần ≥3×3m **mỗi con**) |
| `--stunts` | trồng chuối / đứng 2 chân mỗi 64 beat — **rất dễ ngã** |
| `--lead 3` | đếm ngược trước khi khởi diễn |

Con thứ hai tự động nhảy **lệch pha** (lắc ngược chiều, động tác nhấn so le) —
nhìn đẹp hơn là hai con làm y hệt nhau.

### Diễn tập không cần chó
```bash
python3 go2_troupe.py agent --name A --port 18800 --dry &
python3 go2_troupe.py agent --name B --port 18801 --dry &
python3 go2_troupe.py conduct --robots 127.0.0.1:18800,127.0.0.1:18801 \
    --music ~/dance.mp3 --dry
```

---

## 3. Tiết mục 2 — PHỎNG VẤN TỪNG CON (cổng gọi tên)

Hai con đứng cạnh nhau đều nghe cùng một câu hỏi. Không có cổng này thì **cả hai
cùng trả lời, chồng tiếng lên nhau**. Giải pháp: mỗi con chỉ đáp khi **được gọi tên**.

| MC nói | Chó A (Gô) | Chó B (Mun) |
|---|---|---|
| "**Gô ơi**, bạn tên là gì" | trả lời | im |
| "Bạn học ở trường nào" | trả lời *(đang giữ lượt)* | im |
| "hai bạn có mỏi chân không" | trả lời | im |
| "**Mun ơi**, còn bạn thì sao" | 🤝 nhường lượt, im | trả lời |
| "Bạn làm được những gì" | im | trả lời |
| "**Gô à**, đi thẳng ba mét" | 🤝 nhận lại lượt | im |
| "**dừng lại**" | **dừng** | **dừng** |

Điểm mấu chốt:
- **Giữ lượt 12s** (`floor_hold_s`): MC hỏi nối tiếp *"thế còn bạn thì sao?"* mà
  không phải gọi tên lại — nghe tự nhiên như nói chuyện với người.
- **Gọi tên con kia → nhường lượt ngay**, không cần lệnh riêng.
- **`dừng lại` đặt TRƯỚC cổng gọi tên** → phanh khẩn ăn với **cả hai con**, khỏi gọi tên.

### Chạy (mỗi con một Jetson)
```bash
# Chó A
python3 assistant_realtime.py --mode voice --config config_cho_A.yaml --real
# Chó B
python3 assistant_realtime.py --mode voice --config config_cho_B.yaml --real
```

### ⚠️ Đặt tên: tránh từ tiếng Việt thông dụng
Tên chó khớp theo **ranh giới từ**, nhưng vẫn phải tránh từ hay gặp. Trong lúc làm
đã dính đúng lỗi này: đặt bí danh `"cô"` thì câu *"hai bạn **có** mỏi chân không"*
làm chó tưởng bị gọi (bỏ dấu thì `có` = `cô` = `co`).

Hệ thống **tự cảnh báo** lúc khởi động nếu tên trùng danh sách từ phổ biến:
```
⚠️  [danh tinh] ten/bi danh ['co'] TRUNG tu tieng Viet thong dung -> ... Doi ten khac di
```
Tên đang dùng: **Gô** và **Mun** (đã kiểm tra, không đụng). Muốn đổi thì sửa
`assistant.wake_names` / `other_names` trong 2 file config — nhớ **sửa chéo cả hai**.

---

## 4. Trình tự chạy cả buổi diễn

**Chuẩn bị (làm ở phòng chờ, đừng làm trên sân khấu):**
1. Bật router wifi riêng. 2 Jetson + laptop vào cùng mạng, IP tĩnh.
2. Laptop: ghép loa hội trường → `python3 pc_speaker.py`
3. Thử loa: `python3 pc_speaker.py --test 10.42.0.10` → **phải kêu**.
4. Mỗi con: `go2_audio_bridge.py --gain 2.5` (mic robot) + `llama-server`.
5. Diễn tập nhảy `--dry` một lần để xem sai số đồng bộ.

**Tiết mục 1 — nhảy:** mỗi con chạy `go2_troupe.py agent`, laptop chạy `conduct --play-here`.

**Tiết mục 2 — phỏng vấn:** Ctrl+C tắt `agent`, mỗi con chạy `assistant_realtime.py`
với config riêng. (Không chạy đồng thời với `agent` — cả hai đều điều khiển SportClient.)

**An toàn:**
- **Mỗi con một người cầm remote** (L2+B = dừng khẩn). Hai con = hai người.
- Mỗi con vùng trống riêng ≥2×2m (≥3×3m nếu `--special`/`--stunts`).
- Pin ≥60% mỗi con (≥70% nếu `--stunts`). Tắt app Unitree trên mọi điện thoại.
- `--stunts` trước hội nghị: **cân nhắc bỏ** — ngã trên sân khấu là hỏng cả buổi.

---

## 5. Còn thiếu / chưa test được

- **Chưa test với 2 con thật** (ở đây chỉ có 1 con). Phần đã kiểm chứng: giao thức
  đồng bộ, bù lệch đồng hồ (0.10ms với đồng hồ lệch 3.7s), cổng gọi tên (0 lần
  chồng tiếng trên 7 câu kịch bản). Phần **chưa** chắc: trễ thực tế của
  `SportClient` trên từng con có bằng nhau không → **phải chạy thử với 2 con thật
  và soi bằng mắt**, nếu một con trễ hơn thì chỉnh `--latency` riêng cho nó
  (hiện `--latency` áp chung cho cả hai — cần tách nếu lệch rõ).
- **Chưa test USB WiFi** (dongle chưa cắm). Cắm xong kiểm: `ip -brief addr | grep wlan`.
