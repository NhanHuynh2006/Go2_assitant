
Mở Terminal trên Laptop và chạy lệnh tìm card Wifi (Internet):

Bash
ip route show | grep default
Nhìn sau chữ dev để lấy tên card Wifi. (Của bạn hiện tại là: wlp2s0).

Chạy tiếp lệnh tìm card dây LAN (Nối với robot):

Bash
ip addr show | grep -B 1 "192.168.123.99"
Nhìn tên card hiển thị ở cuối dòng inet. (Của bạn hiện tại là: eno1).

BƯỚC 2: Cấu hình chia sẻ Internet (NAT) trên Laptop
Bạn chạy chuỗi lệnh này trên Laptop để mở cổng cho phép robot đi ké mạng ra ngoài:

Bash
# 1. Xóa sạch các cấu hình cũ để tránh xung đột
sudo iptables -F
sudo iptables -t nat -F

# 2. Bật tính năng chuyển tiếp gói tin (IP Forwarding)
sudo sysctl -w net.ipv4.ip_forward=1

# 3. Cấu hình NAT (Thay wlp2s0 và eno1 nếu sau này bạn dùng máy khác)
sudo iptables -t nat -A POSTROUTING -o wlp2s0 -j MASQUERADE
sudo iptables -A FORWARD -i wlp2s0 -o eno1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i eno1 -o wlp2s0 -j ACCEPT
BƯỚC 3: Cấu hình bảng định tuyến (Routing) trên Robot
Bây giờ, bạn chuyển sang cửa sổ Terminal của Robot (unitree@ubuntu):

Bash
# 1. Chuyển sang quyền root để cấu hình hệ thống
sudo -i

# 2. Xóa sạch các cổng gateway mặc định cũ đang bị loạn
ip route flush default

# 3. Ép Robot nhận Laptop (192.168.123.99) làm cổng ra Internet duy nhất
ip route add default via 192.168.123.99 dev eth0

# 4. Ghi đè DNS để Robot dịch được tên miền (như google.com, pypi.org)
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 5. Thoát quyền root để về user thường
exit
BƯỚC 4: Sửa lỗi thời gian (SSL Certificate) trên Robot
Đây là bước mấu chốt để bạn fix lỗi SSLCertVerificationError lúc nãy. Bạn cần vặn lại đồng hồ của robot về thời gian thực tế (năm 2026).

Chạy lệnh này trên Robot:

Bash
# Đặt thời gian thủ công (Bạn có thể sửa lại giờ/phút cho đúng thực tế lúc làm)
sudo date -s "2026-06-13 14:00:00"

# Kiểm tra lại xem hệ thống đã nhận đúng năm 2026 chưa
date