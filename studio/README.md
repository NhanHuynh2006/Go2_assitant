# GoVoice Studio

App desktop cho GoVoice. Có:
- bản đồ robot tự vẽ (LiDAR + D435i) cập nhật trực tiếp, kèm đồ vật, địa điểm, quỹ đạo và người;
- thẻ trạng thái cho từng robot;
- ô ra lệnh **vừa gõ vừa nói**;
- nút E‑STOP;
- nút bật/tắt mô phỏng và LLM ngay trong app.

```
studio/
  govoice_studio.py   cửa sổ app (GTK + WebKitGTK của hệ thống, không phải Electron)
  server.py           backend: FastAPI + WebSocket, chạy CHÍNH pipeline GoVoice bên trong
  web/                giao diện (HTML/CSS/JS thuần, không cần mạng, không cần build)
  packaging/build_deb.sh   đóng gói thành file .deb
```

## Cài

```bash
cd ~/Documents/Go2_assitant
bash studio/packaging/build_deb.sh              # tạo dist/govoice-studio_<ver>_all.deb (~45 KB)
sudo apt install ./dist/govoice-studio_0.1.0_all.deb
```

Sau đó tìm **GoVoice Studio** trong menu ứng dụng, hoặc gõ `govoice-studio`.

- Lần chạy đầu, app tự cài `fastapi` và `uvicorn` vào venv của GoVoice.
- Chạy thử mà không cài: `python3 studio/govoice_studio.py`.
- Mở bằng trình duyệt thay cho cửa sổ app: thêm `--browser`.

Gói cài chỉ chứa app. App dùng GoVoice, ROS và workspace đã có sẵn trên máy. Nếu bạn để ở
chỗ khác thì sửa đường dẫn trong `~/.config/govoice-studio/settings.json`:

```json
{"home": "~/Documents/Go2_assitant", "ros_setup": "/opt/ros/lyrical/setup.bash",
 "ws_setup": "~/ros2_ws/install/setup.bash", "port": 8765}
```

## Dùng

1. Bấm **▶ Chạy tất cả**. App lần lượt bật mô phỏng, bộ não LLM, rồi trợ lý, mất khoảng 40 giây.
   Nếu sim hoặc LLM đã chạy sẵn từ terminal, app nhận ra và dùng luôn, không bật thêm, và
   khi đóng app cũng không tắt chúng.
2. Ra lệnh bằng một trong các cách:
   - gõ vào ô lệnh;
   - bấm 🎙 để nói;
   - bấm một địa điểm hoặc đồ vật ở cột trái;
   - bấm **⌖ Chọn đích** rồi bấm lên bản đồ.
3. **E‑STOP** (hoặc phím **Esc**) dừng tất cả robot ngay.

## Chấm trên bản đồ để đi

| Thao tác | Kết quả |
|---|---|
| Bấm lên bản đồ | Hiện hộp cho biết chỗ đó **trống / chưa quét / vật cản**, kèm nút **▶ Đi tới đây** |
| Bấm đúp | Đi luôn |
| **⌖ Chấm nhanh** (phím G): bấm rồi **kéo** | Đi tới điểm đó, tới nơi thì quay mặt theo hướng vừa kéo (giống 2D Goal Pose của RViz) |
| Shift + bấm nhiều điểm | Thành **lộ trình** đánh số. Bấm **▶ Đi lộ trình**, hoặc **↻ Tuần tra** để lặp lại 3 vòng |
| 📍 Đặt tên (trong hộp) | Lưu chỗ đó thành địa điểm. Sau đó nói "đi tới <tên>" là robot tới |
| Chấm điểm mới khi robot đang đi | **Đổi đích** ngay, không phải xếp hàng chờ |

- Chấm lên vật cản hoặc sát tường (cách dưới 22 cm) thì bị từ chối.
- Chấm vào chỗ **chưa quét** thì vẫn đi được: robot vừa đi vừa dò, gặp vật thì vòng qua.

### Quét bản đồ rồi lưu
- **Bản đồ quét** không phai: tường và đồ đạc robot đã thấy được giữ lại. Vết người đi qua
  tự xoá khi robot thấy chỗ đó trống trở lại.
- Bản đồ dùng để tránh vật khi đi vẫn là bản đồ "sống" (quên dần sau vài giây) để né người.
- **💾 Lưu** ghi ra `maps/<tên>.pgm` + `.yaml` theo định dạng ROS map_server, mở được bằng
  RViz/Nav2, kèm `.npz` để app mở lại đúng.
- **📂 Mở** nạp lại bản đồ đã lưu. **🧹 Quét lại** xoá bản đồ để quét từ đầu.

### Ngoài đời (Go2 thật)
1. Cho robot đi một vòng để quét bằng LiDAR L1 và D435i. Có thể ra lệnh bằng giọng nói,
   hoặc chấm vào chỗ "chưa quét" để nó tự dò tới.
2. Bấm 💾 Lưu.
3. Chấm để đi.

⚠️ **Lưu ý khi tắt/bật lại chó.** Toạ độ robot (odometry) bắt đầu lại từ 0 tại chỗ nó
khởi động. Vì vậy bản đồ lưu từ lần trước **chỉ khớp nếu chó khởi động đúng chỗ và đúng
hướng như lúc quét**. Muốn khớp ở bất kỳ đâu thì cần bước định vị lại trên bản đồ
(localization). Repo ROS đã có bộ định vị bằng bản đồ 3D, nhưng chưa nối vào GoVoice.
Trong cùng một lần bật máy thì quét rồi chấm luôn là chạy đúng.

| Phím | Việc |
|---|---|
| Esc | E‑STOP (hoặc huỷ chọn đích) |
| / | nhảy tới ô lệnh |
| M | bật/tắt mic |
| G | chọn đích trên bản đồ |
| F | camera bám robot đang chọn |
| Lăn chuột / kéo | phóng to / di chuyển bản đồ |

**Chống nghe nhầm tiếng TV:**
- Mic chỉ nhận câu có từ lệnh (đi, tới, xoay, tên đồ vật, …) và bỏ câu dài hơn 25 từ.
- Muốn chắc hơn thì điền **Từ đánh thức**, ví dụ "gô ơi". Khi đó robot chỉ nghe câu có gọi
  tên. Gọi riêng "gô ơi" thì robot đáp "Dạ?" và chờ lệnh 8 giây.
- "Dừng lại" luôn được nhận.

## Robot thật

Backend chạy **trên chó** (Jetson, Python 3.8), còn app trên laptop nối tới qua Wi‑Fi:

```bash
# trên Jetson (sau start_real.sh phần bridge + realsense, hoặc tự bật chúng)
python3 studio/server.py --real --host 0.0.0.0 --port 8765
#   -> in ra: http://<ip>:8765/?token=XXXX

# trên laptop
govoice-studio --url "http://192.168.123.18:8765/?token=XXXX"
```

- Mọi lệnh từ máy khác phải có token. Token lưu ở `~/.config/govoice-studio/token` trên chó.
- Mở bằng điện thoại cũng được: dán URL có token vào trình duyệt.
- Chế độ `--real` chưa được thử trên phần cứng.

## Tài nguyên (đo trên laptop RTX 4060, ngày 21/11/2026)

| Tiến trình | RAM | CPU khi robot đứng | CPU khi robot đang đi |
|---|---|---|---|
| backend, gồm cả trợ lý GoVoice (bản đồ, A\*, LiDAR, D435i) | 180 MB | 19 % | 23 % |
| WebKit (vẽ giao diện) | 220 MB | 14 % | 36 % |
| cửa sổ GTK | 220 MB | 5 % | 18 % |

CPU tính theo % của **một** nhân.

- Bản đồ chỉ vẽ lại khi có thay đổi, tối đa 30 hình/giây.
- Khi cửa sổ bị thu nhỏ thì không vẽ.
- Trên Linux, Tauri cũng dùng chính WebKitGTK này nên RAM tương đương. Electron kèm theo
  nguyên một Chromium (~150 MB đĩa, thường 300–500 MB RAM).
