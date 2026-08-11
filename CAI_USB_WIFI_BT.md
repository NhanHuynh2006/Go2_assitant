# Cài USB WiFi + Bluetooth (RTL8821CU) cho Jetson trong Go2

Dongle: **WB-602 / chipset Realtek RTL8821CU** (`lsusb` ra `0bda:c820`).
Đã cài xong trên con chó #1 ngày 2026-08-02. File này để làm y hệt cho con #2.

Kernel Jetson: `5.10.104-tegra` (JetPack R35.3.1).

---

## Tóm tắt: có 2 cái bẫy

1. **Kernel 5.10 không có driver WiFi cho chip này.** Driver `rtw88` trong kernel chỉ hỗ trợ 8821CU từ kernel ~6.2 trở lên → phải tự build driver ngoài.
   Bluetooth thì **chạy sẵn**, không cần làm gì (kernel đã có `btusb`).

2. **Driver `option` (GSM modem) cướp mất cổng WiFi.** Cài driver xong, `lsmod` thấy module đã load mà `ip link` vẫn **không có `wlan0`**. Lý do: `usb_modeswitch` tự đăng ký id `0bda:c820` vào driver `option` vài giây sau khi boot, và `option` giành được interface trước.
   → Phải thêm udev rule để giành lại.

Nếu bỏ qua bước 2 thì cài driver bao nhiêu lần cũng vô ích.

---

## Bước 0 — Cắm dongle vào, kiểm tra đã thấy chưa

```bash
lsusb | grep 0bda
```

Phải ra:

```
Bus 001 Device 003: ID 0bda:c820 Realtek Semiconductor Corp. 802.11ac NIC
```

- Nếu ra `0bda:1a2b ... DISK` thì chờ vài giây rồi chạy lại — nó đang ở chế độ CD-ROM ảo, `usb_modeswitch` sẽ tự chuyển sang `c820`.
- Nếu không ra gì: đổi cổng USB khác.

Kiểm tra Bluetooth (thường đã chạy sẵn luôn):

```bash
hciconfig -a          # phải thấy hci0, "UP RUNNING", Manufacturer: Realtek
```

---

## Bước 1 — Cài driver WiFi (DKMS)

Cần: máy có internet (cắm dây LAN chia mạng từ laptop, hoặc USB tethering điện thoại).

```bash
cd /home/unitree/NhanHuynh
git clone https://github.com/morrownr/8821cu-20210916.git
cd 8821cu-20210916
sudo ./install-driver.sh NoPrompt
```

Build mất khoảng 3–5 phút. Xong phải thấy `DKMS: install completed.`

> **Không có internet trên con #2?** Copy nguyên thư mục từ con #1 sang rồi chạy `sudo ./install-driver.sh NoPrompt`:
> ```bash
> # chạy trên máy có sẵn thư mục
> scp -r /home/unitree/NhanHuynh/8821cu-20210916 unitree@<ip-con-2>:/home/unitree/NhanHuynh/
> ```
> Trên con #2 nhớ `make clean` trong thư mục đó trước khi cài, để nó build lại từ đầu.

Kiểm tra:

```bash
sudo dkms status        # phải thấy: rtl8821cu, 5.12.0.4, 5.10.104-tegra, aarch64: installed
sudo modprobe 8821cu
lsmod | grep 8821cu
```

Tới đây **rất có thể vẫn chưa có `wlan0`** — đó là bẫy số 2, sang bước 2.

---

## Bước 2 — Chặn driver `option` cướp cổng WiFi

Xem thử ai đang giữ nó (thay `1-2` bằng đường dẫn thật, xem cách tìm ở dưới):

```bash
ls -l /sys/bus/usb/devices/1-2:1.2/driver
```

Nếu trỏ tới `.../drivers/option` → đúng bệnh.

Tìm đường dẫn USB thật của dongle:

```bash
for d in /sys/bus/usb/devices/*/; do
  [ "$(cat $d/idVendor 2>/dev/null):$(cat $d/idProduct 2>/dev/null)" = "0bda:c820" ] && echo "$d"
done
```

### 2a. Tạo script giành lại

```bash
sudo tee /usr/local/sbin/rtl8821cu-rebind.sh > /dev/null <<'EOF'
#!/bin/sh
# The RTL8821CU wifi interface (bInterfaceNumber 02) looks like a GSM modem to
# the kernel, so the 'option' driver grabs it and no wlan0 appears.
# Take it back and hand it to the real wifi driver.

DEV="$1"
[ -n "$DEV" ] || exit 0
SYS="/sys/bus/usb/devices/$DEV"
[ -d "$SYS" ] || exit 0

modprobe 8821cu 2>/dev/null

i=0
while [ $i -lt 20 ]; do
	CUR="$(basename "$(readlink "$SYS/driver" 2>/dev/null)" 2>/dev/null)"
	case "$CUR" in
		rtl8821cu)
			exit 0
			;;
		option)
			echo -n "$DEV" > /sys/bus/usb/drivers/option/unbind 2>/dev/null
			sleep 1
			echo -n "$DEV" > /sys/bus/usb/drivers/rtl8821cu/bind 2>/dev/null
			;;
		"")
			echo -n "$DEV" > /sys/bus/usb/drivers/rtl8821cu/bind 2>/dev/null
			;;
	esac
	i=$((i + 1))
	sleep 1
done

exit 0
EOF
sudo chmod 755 /usr/local/sbin/rtl8821cu-rebind.sh
```

### 2b. Tạo udev rule gọi script đó

```bash
sudo tee /etc/udev/rules.d/99-rtl8821cu.rules > /dev/null <<'EOF'
# RTL8821CU (0bda:c820) USB wifi + bluetooth dongle.
# Interface 02 is the wifi radio, but the 'option' GSM-modem driver claims it
# first (usb_modeswitch registers the id with option a few seconds after boot).
# Detach it in the background and bind it to the 8821cu driver instead.
ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_interface", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="c820", ATTR{bInterfaceNumber}=="02", RUN+="/usr/bin/systemd-run --no-block /usr/local/sbin/rtl8821cu-rebind.sh %k"
ACTION=="bind", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_interface", DRIVER=="option", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="c820", RUN+="/usr/bin/systemd-run --no-block /usr/local/sbin/rtl8821cu-rebind.sh %k"
EOF
sudo udevadm control --reload-rules
```

### 2c. Rút cắm lại dongle (hoặc mô phỏng bằng lệnh)

```bash
# thay 1-2 bằng đường dẫn tìm được ở trên
sudo sh -c 'echo 0 > /sys/bus/usb/devices/1-2/authorized'
sleep 3
sudo sh -c 'echo 1 > /sys/bus/usb/devices/1-2/authorized'
sleep 10
```

Kiểm tra:

```bash
ls -l /sys/bus/usb/devices/1-2:1.2/driver   # phải trỏ tới drivers/rtl8821cu
ip -br link | grep wlan                     # phải thấy wlan0
```

---

## Bước 3 — Nối WiFi

```bash
sudo nmcli dev wifi rescan
nmcli -f SSID,SIGNAL,SECURITY dev wifi list

sudo nmcli dev wifi connect "NhanHuynh" password "14082006" ifname wlan0
```

Kiểm tra:

```bash
nmcli -f DEVICE,STATE,CONNECTION dev status
ip -br addr show wlan0
ping -c3 -I wlan0 8.8.8.8
```

Lần sau boot lên nó **tự nối lại**, không phải gõ lại lệnh.

### Lưu ý về đường ra internet

Nếu vẫn cắm dây LAN chia mạng từ laptop thì máy có **2 default route**:

```
default via 192.168.123.99 dev eth0            <- dây, không có metric = ưu tiên
default via 10.30.107.102 dev wlan0 metric 600 <- WiFi, dự phòng
```

Dây vẫn được ưu tiên (và nhanh hơn). Rút dây ra thì tự động rơi sang WiFi. Đường nói chuyện với robot (`192.168.123.161`) không bị ảnh hưởng.

Muốn ép đi WiFi trước thì hạ metric của wlan0:

```bash
sudo nmcli connection modify NhanHuynh ipv4.route-metric 50
sudo nmcli connection up NhanHuynh
```

---

## Bước 4 — Bluetooth

Không cần cài gì. Kiểm tra:

```bash
bluetoothctl show                       # Powered: yes
bluetoothctl --timeout 15 scan on       # phải thấy các Device xung quanh
```

Ghép loa/tai nghe:

```bash
bluetoothctl
> scan on
> pair <MAC>
> trust <MAC>
> connect <MAC>
> quit
```

---

## Sự cố hay gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Có `ttyUSB0` mà không có `wlan0` | driver `option` cướp cổng | làm lại **Bước 2** |
| `lsusb` ra `0bda:1a2b ... DISK` | dongle còn ở chế độ CD-ROM ảo | chờ 10s, hoặc `sudo apt install usb-modeswitch` |
| Cài xong, sau khi update kernel mất WiFi | DKMS chưa build cho kernel mới | `sudo dkms status`, thiếu thì `cd 8821cu-20210916 && sudo ./install-driver.sh NoPrompt` |
| WiFi chập chờn / tự rớt | tính năng tiết kiệm điện | `sudo nano /etc/modprobe.d/8821cu.conf` → bỏ `#` dòng có `rtw_power_mgnt=1`, sửa thành `rtw_power_mgnt=0`, rồi reboot |
| Không thấy mạng 5GHz | sai vùng phủ sóng | trong `/etc/modprobe.d/8821cu.conf` thêm `options 8821cu rtw_country_code=VN` |

Xem log driver:

```bash
sudo dmesg | grep -iE '8821cu|rtl8821|option|usb 1-'
```

---

## Gỡ cài đặt (nếu cần)

```bash
cd /home/unitree/NhanHuynh/8821cu-20210916
sudo ./remove-driver.sh
sudo rm -f /etc/udev/rules.d/99-rtl8821cu.rules /usr/local/sbin/rtl8821cu-rebind.sh
sudo udevadm control --reload-rules
```
