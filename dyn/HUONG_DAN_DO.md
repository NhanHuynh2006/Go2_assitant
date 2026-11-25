# Hướng dẫn đo động học vận tốc Go2 thật (người dùng tự chạy)

Mục đích: biết khi gửi `Move(vx, vy, wz)` thì con chó **thật sự** đi bao nhiêu, trễ bao lâu, dừng trong bao xa.
Hiện **chưa có bản ghi nào có lệnh**, nên các số gain/trễ/tau trong `go2_params.yaml` đang là giả định.

Chỉ dùng **SportClient cấp cao** (Move, StopMove, BalanceStand). Không LowCmd, không nhào lộn, không chạy đua.

## 0. Cần có
- Pin >= 35 %, động cơ < 70 °C, sàn khô bằng phẳng, giày chân sạch.
- Sân trống **7 x 7 m** (không người, không vật, không bậc thềm, không kính). Dán băng dính điểm xuất phát + hướng.
- **2 người**: một người cầm remote, mắt luôn nhìn chó; một người ngồi máy.
- Phanh: **L2+B** (damp, chó mềm rồi nằm xuống) trên remote; **ENTER** hoặc Ctrl-C trên máy. Thử L2+B trước khi đo.
- Thước dây 5 m.
- Tắt mọi nguồn lệnh khác: app Unitree, `go2_hardware_bridge --allow-motion`, `go2_auto`, Nav2, GoVoice.
  (Bridge CHỈ ĐỌC, không `--allow-motion`, thì được, để có OS1/`/go2/lidar/merged`.)
- Tắt tránh vật cản của app (vì nó sửa lệnh) – ghi lại trạng thái bật/tắt và **SpeedLevel / dáng đi** đang dùng:
  số đo chỉ đúng cho dáng đi đó (mặc định, không gọi TrotRun/FreeWalk/ClassicWalk).

## 1. Chạy trên Orin của chó (không qua Wi-Fi), hoặc laptop cắm dây
```bash
scp -r dyn unitree@<ip>:~/dyn            # chỉ cần sysid_real.py
tmux new -s sysid                        # rớt SSH không giết tiến trình giữa chừng
python3 ~/dyn/sysid_real.py --sim --stage 1 --set fit --out /tmp/thu.npz     # thử phần mềm, không đụng robot
python3 ~/dyn/sysid_real.py --stage 1 --set fit                              # in kế hoạch lệnh, đọc kỹ
python3 ~/dyn/sysid_real.py --check --iface eth0 --out /tmp/check.npz        # chỉ đọc 10 s: lỗi phải là []
```
`--check` phải thấy: pin, nhiệt độ, thân ~0.32 m, odom, LiDAR, remote, và tần số odom > 100 Hz.
`error_code` khác 0 chỉ được in ra, không chặn (firmware mới có thể dùng trường này làm mã chế độ; chưa xác minh): ghi lại số đó.

Muốn có mốc LiDAR OS1 (nên có): mở cửa sổ khác, bridge + ouster + merge chạy chế độ đọc, rồi
`ros2 bag record -o ~/sysid/bag_s1 /go2/lidar/merged /go2/odom /go2/ouster/imu`.
(Đồng hồ: cả hai cùng máy Orin, script lưu `t_wall` để ghép.)

## 2. Thứ tự đo (không nhảy bước; script từ chối giai đoạn 2/3 nếu chưa xong giai đoạn trước)
| Bước | Lệnh | Giới hạn | Thời gian |
|---|---|---|---|
| A | `--go --stage 1 --set fit  --out ~/sysid/s1_fit.npz`  | 0.20 / 0.15 m/s, 0.40 rad/s | 79 s |
| B | `--go --stage 1 --set test --out ~/sysid/s1_test.npz` | như trên | 37 s |
| C | `--go --stage 1 --tape 0.2 --out ~/sysid/tape_02.npz` + đo thước | thẳng 3 s | 6 s |
| D | giai đoạn 2, fit rồi test (`s2_*.npz`) | 0.40 / 0.25, 0.80 | 79 + 31 s |
| E | `--go --stage 2 --tape 0.4`, 3 lần | thẳng 3 s (~1.2–1.5 m) | 6 s |
| F | giai đoạn 3, fit rồi test | 0.60 / 0.40, 1.00 | ~73 + 37 s |
| G | lặp D (cả fit lẫn test) ở **nền khác** (gạch bóng / xi măng / cỏ) và **pin thấp hơn** | | |

Nghỉ >= 2 phút giữa các giai đoạn (nhiệt động cơ). Trước mỗi lần chạy, đưa chó về giữa sân bằng remote.
Đo thước: đặt thước ở mũi chân trước trái lúc đứng yên trước và sau; ghi vào `~/sysid/tape.txt`: `tape_04.npz 1.23`.
Mỗi bước `--go` sẽ: kiểm tra tự động -> đòi **gạt nhẹ cần remote** (chứng minh người giành được quyền) -> đòi gõ
`TOI CAM REMOTE` -> BalanceStand -> chạy.

## 3. Script tự dừng khi
mất odom > 0.2 s, mất trạng thái > 0.5 s, mất LiDAR > 0.6 s, mất sóng remote > 1.5 s, gạt remote, nghiêng > 20°, thân thấp,
quá 170 s, ENTER, Ctrl-C, đóng SSH (SIGHUP). Ra ngoài hàng rào 2.2 m hoặc vật trên LiDAR gần hơn ~0.7 m: bỏ đoạn đó, đứng yên.
Hàng rào dùng odom nhân 1.25 vì odom thô đo thiếu ~18 %.

**Điều script KHÔNG bảo vệ được:** LiDAR L1 gần như mù phía sau thân, mù kính và vật thấp; không thấy bậc thềm xuống; hàng rào
không biết tường ở đâu. Vì vậy phải có sân trống và người cầm remote. Nếu máy treo cứng, theo tài liệu thứ cấp lệnh Move chỉ
sống 1 s, nhưng **điều này chưa được kiểm trên con chó này**: coi L2+B là phanh duy nhất.

## 4. Dừng đo ngay nếu
chó trượt, vấp, lắc mạnh, kêu lạ, đi lệch > 30° so với lệnh; tốc độ thật nhanh hơn lệnh rõ rệt (có thể xảy ra: nếu firmware
điều khiển theo vận tốc tự đo bị thiếu 18 % thì chó đi nhanh hơn lệnh ~1.2 lần); pin < 25 %.

## 5. Khớp và kiểm
```bash
cd ~/Documents/Go2_assitant/dyn
../venv/bin/python fit_real.py --fit s1_fit.npz s2_fit.npz s3_fit.npz --test s1_test.npz s2_test.npz s3_test.npz \
      --scale 1.215 --out fit_go2.json
```
- `--scale`: m thật / m odom thô. Thay 1.215 bằng số từ thước dây (tổng thước / tổng odom) nếu lệch > 2 %.
- Chỉ tin mô hình nếu trên **tập test** (chưa dùng): RMSE dự đoán hở 2 s nhỏ hơn rõ so với `M1 he so`, và test không xấu hơn
  fit quá 30 %. Tham số có ghi `CHAM BIEN`, `CI rong`, `khong nhan dang duoc` thì **không được dùng**.
- Cập nhật `go2_params.yaml`: đổi cờ `gia_dinh` -> `do_that`, ghi ngày, nền, pin, dáng đi; chạy lại trên nền khác để có dải.
