# MẠNG CHO JETSON — không cần mua USB WiFi / Bluetooth

> Cập nhật 2026-07-30, sau khi test thật trên máy. Phần cấu hình NAT từ laptop (cách cũ)
> nằm ở mục 3.

---

## 0. Sự thật phần cứng (đã kiểm tra, không đoán)

```
lsusb                → chỉ có 2 root hub, KHÔNG có thiết bị nào cắm
ip -brief addr       → chỉ eth0, lo, docker0, dummy0 — KHÔNG có wlan*
rfkill list          → rỗng
lsmod | grep wifi    → không có driver wifi nào nạp
hciconfig -a         → không có adapter Bluetooth nào
```

**Jetson Orin NX trong con Go2 này KHÔNG có radio WiFi lẫn Bluetooth.** WiFi 6 / BT / 4G
mà sách hướng dẫn nói (mục 1.3.3, 1.4.6) nằm ở **main board `.161`**, không phải ở Jetson.

Quét cả dải LAN robot — chỉ có 3 máy:

| IP | Là gì | Mở port |
|---|---|---|
| `192.168.123.18` | **Jetson** (máy này) | — |
| `192.168.123.99` | **Laptop** của bạn, đang chia mạng qua dây | (đóng hết) |
| `192.168.123.161` | **Main board robot** | 80, 9991 (WebRTC). **Không có SSH** |

Hiện tại Jetson **đang có internet**: `default via 192.168.123.99 dev eth0` → ping 8.8.8.8 OK,
DNS OK. Tức là đang đi ké mạng của laptop qua dây (đúng cách ở mục 3).

---

## 1. ❌ Đi ké WiFi 6 của chính con robot — ĐÃ TEST, KHÔNG ĐƯỢC

Ý tưởng rất hợp lý: main board có WiFi 6 + 4G, Jetson nối thẳng với nó qua LAN,
vậy cho main board làm gateway là xong. Đã thử:

```bash
sudo ip route add 8.8.4.4/32 via 192.168.123.161 dev eth0
ping -c3 8.8.4.4     # → 100% packet loss
sudo ip route del 8.8.4.4/32
```

**Main board không bật IP forwarding / NAT.** Muốn bật thì phải vào được nó — mà nó
**không mở SSH** (port 22 refused). Firmware Unitree khoá. ⇒ Đường này tắc.

(Ghi nhận: khi chạy `go2_audio_bridge.py`, robot có báo `Robot Connection Mode: 📡 4G`
— nó *có* mạng riêng, chỉ là không chia cho ai.)

---

## 2. ✅ CÁCH KHÔNG TỐN TIỀN: USB tethering từ điện thoại Android

Chỉ cần **sợi cáp USB** — không mua gì thêm. Đã kiểm tra driver có sẵn:

```
rndis_host   → nạp được (module)
cdc_ether    → BUILT-IN trong kernel
cdc_ncm      → BUILT-IN trong kernel
ipheth       → KHÔNG CÓ   ⚠️ iPhone không dùng được, chỉ Android
NetworkManager → đang chạy (sẽ tự nhận usb0)
```

**Làm:**
1. Cắm cáp điện thoại Android vào cổng USB của Jetson (qua hub).
2. Trên điện thoại: *Settings → Kết nối → Điểm phát sóng → **Chia sẻ Internet qua USB (USB tethering)*** → bật.
3. Trên Jetson, kiểm tra:
```bash
ip -brief addr | grep usb        # phải hiện usb0 với IP 192.168.42.x
ping -c2 8.8.8.8
```

Nếu `usb0` lên mà chưa ra được mạng, chỉ định nó làm gateway (giữ nguyên LAN robot):
```bash
sudo ip route replace default via $(ip route | grep usb0 | grep -oP 'src \K[\d.]+' | sed 's/\.[0-9]*$/.129/') dev usb0
# hoặc đơn giản để NetworkManager tự lo:
sudo nmcli dev connect usb0
```

**Cái này thay được luôn cách "hotspot NhanHuynh + IP tĩnh 10.32.230.18"** trong ghi chú
cũ — SSH vào Jetson qua IP mà điện thoại cấp cho nó, robot chạy tự do không cần dây laptop.

⚠️ Nhớ **không xoá** route `192.168.123.0/24 dev eth0` — đó là đường tới robot.

---

## 3. ✅ CÁCH ĐANG DÙNG: chia mạng từ laptop qua dây (NAT)

Dùng khi ngồi bàn làm việc. Đây chính là cái đang chạy (`gateway 192.168.123.99` = laptop).

**Trên LAPTOP** (đổi `wlp2s0` = card wifi, `eno1` = card LAN nối robot):
```bash
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o wlp2s0 -j MASQUERADE
sudo iptables -A FORWARD -i wlp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i eno1 -o wlp2s0 -j ACCEPT
```
Tìm tên card: `ip route show | grep default` (wifi) và `ip addr | grep -B1 192.168.123.99` (LAN).

**Trên JETSON:**
```bash
sudo ip route replace default via 192.168.123.99 dev eth0
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```

Nếu gặp `SSLCertVerificationError` → đồng hồ Jetson sai năm:
```bash
sudo date -s "2026-07-30 14:00:00"
```

---

## 4. Về Bluetooth

**Không có adapter ⇒ không có cách phần mềm nào.** Nhưng kiểm tra lại xem có thật sự cần không:

| Việc muốn làm bằng BT | Cách đang có, không cần BT |
|---|---|
| Ra tiếng ở loa | Loa robot qua WebRTC — `go2_tts_speaker.py` (**đang dùng**) |
| Lấy tiếng vào từ mic | Mic robot qua WebRTC — `go2_audio_bridge.py` (**đang dùng**) |
| Ghép tay cầm điều khiển | Tay cầm ghép BT thẳng với **main board**, không qua Jetson |
| Ghép app Unitree Go | App ghép BT với main board (sách hướng dẫn mục 2, Bước 3) |

Nếu về sau thật sự cần BT trên Jetson thì mới phải mua dongle — nhưng hiện dự án
**không có chỗ nào cần**.

---

## 5. Địa chỉ & mật khẩu (sách hướng dẫn mục 3.2)

| Địa chỉ | Thiết bị | User | Pass |
|---|---|---|---|
| `192.168.123.161` | GO2 MCU / main board | — | — |
| `192.168.123.18` | Jetson (Auxiliary PC) | `unitree` | `123` |
| `192.168.123.18:9000` | GO2 Webserver MBS | `admin` | `mybotshop` |

⚠️ **Port 9000 hiện đóng** trên Jetson này (`curl` → connection refused) — bản image
MyBotShop/ROS2 trong sách chưa được cài. Nếu muốn dùng webserver (bật/tắt service ROS2,
ghi rosbag, xem màn hình từ xa, nối loa ngoài) thì phải cài driver `qre_go2` theo mục 3.3.
