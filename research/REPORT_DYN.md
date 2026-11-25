# REPORT_DYN — động học vận tốc Go2 thật ở lớp lệnh (SportClient.Move)

Agent DYN, 22–23/11. Chỉ CPU, ≤ 2 luồng, không kết nối tới chó, không chạy GPU/Gazebo, không chạy seed nào của fastsim
(chỉ dùng `fastsim.Sim.substep` làm nguồn dữ liệu tổng hợp). Mã ở `dyn/`, số thô ở `dyn/results/`.

## 1. Bản ghi thật: KHÔNG có lệnh vận tốc
| bản ghi | dài | topic | dùng được |
|---|---|---|---|
| lab_20260911_160656_slim | 180 s | /utlidar/cloud, /utlidar/imu, /utlidar/robot_odom | odom; ICP L1 phân kỳ, **bỏ** |
| lab2_20260915_174920 | ? | file hỏng (sqlite malformed) | không |
| lab2_20260915_174958 | 16 s | như dưới | chưa phân tích (quá ngắn) |
| lab2_20260915_175037 | 209 s | /go2/odom, /go2/odom/fused, /go2/imu/data, /go2/ouster/imu, /go2/lidar/merged | có |
| yard_20260916_104758 | 194 s | như trên | có |

Không có cmd_vel, sport request hay wirelesscontroller ở bất kỳ file nào (các run ghi lệnh nằm ở `~/runs` **trên chó**, máy này
không có). Vì vậy **gain, bão hoà, trễ, tau theo lệnh, gia tốc tối đa, ghép chéo: KHÔNG nhận dạng được** từ dữ liệu hiện có.
Robot do người lái remote, nên phân bố vận tốc/gia tốc là của người lái, không phải giới hạn robot.

## 2. Đo thật (CI bootstrap khối 95 %)
**Odom.** Kiểm float32: `x` của lab2 là float32 chính xác 100 % (odom thô); của yard chỉ chính xác sau khi chia 1.19 (100 %)
-> yard đã bị bridge nhân 1.19, lab2 thì chưa. Không biết điều này thì hai bản ghi mâu thuẫn nhau. ICP quét-tới-bản đồ 6 bậc tự
viết (`lidar_odo.py`), hai cách khởi tạo độc lập (odom / vận tốc không đổi) cho cùng số:
- lab2 (thô): 1.2148 [1.213, 1.218] / 1.2136; yard: 1.0276 [1.023, 1.034] / 1.0278 -> thô 1.223 [1.217, 1.230].
- **Thật/odom thô = 1.215–1.223**, ngoài hai bản ghi lấy 1.215 (1.19–1.24). Odom thô thiếu **~18 %** quãng đường (phải nhân
  ~1.22, không phải 1.19). Phụ thuộc tốc độ nhẹ: ~1.17 ở 0.3 m/s (n = 26, ±0.05), 1.205 ở 0.5, 1.22 ở ≥ 0.9.
- Yaw đúng: LiDAR/odom 1.001–1.008. Trễ odom so với IMU ≤ 5 ms; twist ở hệ THÂN; 43–46 Hz sau bridge, khe lớn nhất 0.12 s.
- 1–2 % cửa sổ 1.5 s lệch > 15 % (chủ yếu khi quay gắt).

**LiDAR OS1 (merged).** Trễ 0.04–0.045 s so với IMU; mốc thời gian là lúc NHẬN, rung tới ~±0.1 s và mất 5–13 % khung. Hướng đi
đo bằng LiDAR lệch +2.3–2.5° so với odom ở cả hai bản ghi: hoặc extrinsic OS1 sai ~2°, hoặc chó đi chéo. **Chưa tách được.**

**Dừng** (7 lần nhả remote, v0 0.32–1.13 m/s): tau giảm tốc trung vi 0.30 s (6/7 trong 0.20–0.32; 1 lần 0.78 do nhả chậm);
quãng đường từ lúc bắt đầu giảm ≈ **0.28 s × v0** (0.24–0.35). Gồm cả tay người và lọc remote của firmware nên là CẬN TRÊN cho tau
robot; **không chứa trễ lệnh**.

**Gia tốc** (người lái, lọc 1 Hz): |ax| p99 1.3–1.6, max 1.7–1.8 m/s²; |αz| p99 1.6–2.0, max 3.0–3.3 rad/s². CẬN DƯỚI khả năng.
vx tới 1.3–1.6 m/s, |wz| tới 1.9 rad/s không thấy bão hoà kiểu CHAMP (0.29). |vy| p99 chỉ ~0.1 m/s: **không có dữ liệu đi ngang**.

**Lắc thân** (> 0.8 Hz, đi thẳng > 0.3 m/s): ngang 4.4 mm (LiDAR cận trên 7 mm), dọc 11–13 mm, yaw 0.0073–0.0087 rad, roll/pitch
0.010/0.011 rad; gyro xyz 0.34/0.26/0.112 rad/s; vận tốc ngang 0.10–0.11, dọc 0.23–0.31 m/s (nhịp chân + nhiễu ước lượng).
-> `wob` fastsim go2 đề xuất (0.011, 0.005, 0.009) thay cho (0.006, 0.006, 0.015).

## 3. Tài liệu (đều là robot/firmware KHÁC; chỉ để so)
| nguồn | nội dung | đọc | tin |
|---|---|---|---|
| [arXiv 2403.08185](https://arxiv.org/html/2403.08185) PwC, phụ lục | **Go1**, Vicon, khớp PEM: A=diag(−2.517, −3.968), B=(2.335, 4.651) -> tau 0.40/0.25 s, gain 0.93/1.17 (tôi suy) | toàn phụ lục qua HTML | vừa (Go1) |
| [arXiv 2409.09882](https://arxiv.org/pdf/2409.09882) SIA, bảng I | **Go2** lệnh vận tốc cao cấp, OptiTrack: hệ số a 0.082/0.120, yaw 0.707; tải 3.5/5.9 kg: 0.111/0.132/0.685, 0.121/0.100/0.661; R² > 0.78 -> tau x 0.41/0.30/0.28, y 0.28/0.25/0.33 (tôi suy dt/A, gộp cả trễ) | phần liên quan PDF | vừa |
| [arXiv 2607.11204](https://arxiv.org/pdf/2607.11204) | Go2 EDU, chỉ có trễ vòng điều khiển, không có gain/trễ động học | grep toàn văn | thấp cho mục này |
| [arXiv 2610.01219](https://arxiv.org/html/2610.01219) EIDA | Go2, lệnh 10 Hz, vx 0–1, vy ±0.2, ω ±π/3; mô hình MLP, **không** công bố trễ/tau | qua WebFetch | vừa |
| [arXiv 2610.01612](https://arxiv.org/html/2610.01612) ReCo | dạng bậc 1 (k, tau) đúng loại mình dùng, không công bố số; policy riêng | qua WebFetch | vừa |
| [CSDN, chép tài liệu Unitree](https://damodev.csdn.net/69782b327c1d88441d8fdca1.html) | Move vx [−2.5, 3.8], vy [−1, 1], vyaw [−4, 4]; lệnh sống 1 s; không lọc; firmware ≥ 1.1.6 | trang thứ cấp, dấu phân cách bị mất; **trang gốc Unitree không đọc được** | thấp–vừa |
| [unitree.com/go2](https://www.unitree.com/go2) | EDU 3.7 m/s (5 lab), ~15 kg | trang | vừa |
| [unitree_ros URDF](https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go2_description/urdf/go2_description.urdf) | base 6.921 kg, I (0.0245, 0.0981, 0.107); chân 1.984 kg; 23.7/45.43 N·m; 30.1/15.7 rad/s | file | cao |
| [rl_gym](https://raw.githubusercontent.com/unitreerobotics/unitree_rl_gym/main/legged_gym/envs/go2/go2_config.py), [IsaacLab](https://raw.githubusercontent.com/isaac-sim/IsaacLab/main/source/isaaclab_assets/isaaclab_assets/robots/unitree.py) | kp/kd 20/0.5 và 25/0.5; khối lượng ±, v ±1 | file | cao, nhưng không phải bộ điều khiển SportClient |

Không tìm thấy bài nào đo gain/trễ/tau của SportClient.Move **Go2 mặc định** đúng như của mình. Mâu thuẫn: vx tối đa 3.8/3.7/2.5/5.0 tuỳ
nguồn; URDF cộng ~14.9 kg khớp 15 kg; tau x từ tài liệu 0.28–0.41 (gộp trễ) và cận trên của mình 0.30 (không gộp trễ).
Ghi chú cũ "gain 80 %" (0.43 m/s ở lệnh 0.45–0.55, 12/9) đo lúc odom chưa nhân 1.19: sửa lại ~0.52 m/s -> **gain 0.94–1.15 (gián tiếp)**;
nếu 0.43 đo bằng LiDAR thì 0.78–0.96. Hệ số 0.25/0.15 s trong `eval_controllers.py` không có nguồn đo.

## 4. Số cuối: `dyn/go2_params.yaml` (cờ do_that / gian_tiep / tai_lieu / gia_dinh); `dyn/go2_params.py` lấy mẫu cho train
| tham số | giá trị (dải) | cờ |
|---|---|---|
| thật/odom thô | 1.215 (1.19–1.24) | đo thật |
| quãng dừng (sau trễ) / v0; tau giảm | 0.28 s (0.24–0.35); ≤ 0.30 s | đo thật (cận trên) |
| lắc thân; gia tốc ≥ | xem mục 2 | đo thật |
| gain x / y / wz | 0.95 (0.75–1.20) / 0.95 (0.70–1.20) / 0.90 (0.65–1.10) | gián tiếp / tài liệu / tài liệu |
| tau x / y / wz | 0.28 (0.15–0.45) / 0.22 (0.12–0.35) / 0.15 (0.06–0.30) s | tài liệu + cận trên / tài liệu / **giả định** |
| trễ lệnh | 0.10 (0.04–0.20) s | **giả định** |
| bão hoà x / y / wz | 3 (1.5–3.8) / 1 / 3 | tài liệu |
| lùi, vùng chết, ghép wz->vy | 1.0 (0.8–1.2), 0–0.08, ±0.06 m | **giả định** |

Phản ứng toàn phần (trễ + tau) x ≈ 0.38 s (0.25–0.50), không phải 0.17–0.25 s của fastsim regime "go2": **fastsim go2 có thể quá NHANH**;
ở 0.35 m/s mất 0.13 m (0.09–0.18), ở 0.6 m/s 0.23 m (0.15–0.30).

Đề xuất cho fastsim (điều phối viên, tôi không sửa): regime "go2": gain U(.75,1.2)/U(.7,1.2)/U(.65,1.1), vsat U(1.5,3.5), back U(.85,1.15),
tau U(.15,.45)/U(.12,.35)/U(.06,.30), delay U(.04,.20) (hiện cố định 0.05), wob (0.011, 0.005, 0.009)×U(.6,1.6); cần thêm: giới hạn gia tốc
(1.2–3.5, 0.8–3, 2.5–8), tỉ lệ odom dư U(.97,1.06), trễ LiDAR 0.03–0.12 và rung mốc. Đây là **dải giả định rộng**, không phải số đo.

## 5. Odom sai ~18 % làm hỏng gì
- Đi `x` m theo odom thô = 1.215x thật. Vật tĩnh trên bản đồ odom "chạy" ~0.18 × v (0.06 m/s ở 0.35; 6 cm mỗi giây tự bồi) và tracker
  thấy vận tốc giả; gain học online thấp hơn thật 18 %. Bridge nhân 1.19 còn dư +2–3 % (≈0 ở 0.3 m/s): **không cần vội sửa**.
- Nếu firmware điều khiển theo vận tốc tự đo bị thiếu, chó có thể đi ~1.2 lần lệnh. Chưa biết -> kịch bản đo bắt đầu 0.2 m/s.
- `robot_ros.vel_gain` khởi tạo 0.5 (CHAMP), học chậm (~3 s): trên chó thật model sẽ tưởng robot chậm gấp đôi; đề nghị ALGO đặt 0.95 cho RealRobotTools.

## 6. Công cụ để người dùng đo (chưa chạy trên chó)
- `sysid_real.py`: chỉ Move/StopMove/BalanceStand; 3 giai đoạn 0.2→0.4→0.6 m/s, đoạn ≤ 3 s, hàng rào 2.2 m, dừng khi mất odom/LiDAR/remote,
  gạt remote, nghiêng, vật gần; không có `--go` thì không gửi gì, `--go` đòi gạt remote và gõ chữ. `test_safety.py` kiểm
  logic an toàn bằng trạng thái giả: đạt 16/16. Chưa kiểm với SDK/robot thật: tần số `wirelesscontroller`, kiểu dữ liệu cloud, chuẩn 1 s của Move.
- `fit_real.py`: thang M0..M6, chọn bằng kiểm chéo trong tập fit, báo số trên tập test riêng, dự đoán hở 1–3 s.
- Kiểm `test_fit.py`, 10 bộ tham số ngẫu nhiên, dữ liệu từ đúng `fastsim.substep` (odom 1/1.22, rung mốc): sai số trung vị gain 0.3–1.3 %,
  tau 1.3–2.5 %, trễ 2.8 ms (p90 4.4), back 1.4 %, bão hoà 12 %. **CI95 chỉ phủ 78/90 = 87 %** (tau_x 7/10, cx 6/10) -> nhân bề rộng CI ~1.5.
  Dự đoán hở 2 s: đúng mô hình ~0.016 m so với 0.06–0.12 m của `v = lệnh`. Robot giả có thêm gia tốc + lắc mạnh (`fit_simio.log`):
  gain/tau/trễ/back/xoff nằm trong CI; bão hoà x (thật 1.25 theo 1/s, khớp 1.46 và 1.59) NẰM NGOÀI CI; ax, ay không nhận dạng được (script ghi rõ); chỉ cho phép
  kiểm phương pháp, KHÔNG nói lên độ chính xác trên chó thật (mô hình thật không chắc là bậc 1).

## 7. Chưa chắc / sai số lớn nhất
Một mình LiDAR OS1 làm mốc, không thước dây; hai bản ghi, hai ngày, một sàn/khu; ICP chung cảm biến nên sai số tỉ lệ chung (khoảng cách
OS1) không bị phát hiện; gain/trễ/vy/vùng chết/ghép/payload chưa đo. Mọi số trên là ước lượng có sai số, không phải giá trị tuyệt đối.
Đề xuất: người dùng đo theo `dyn/HUONG_DAN_DO.md` (~30 phút, 7×7 m, 2 người), rồi khớp lại và thay cờ.
