# Triển khai C1 / B1 lên Go2 thật (REALPREP, 25/11/2026)

Mã thuật toán **không đổi**: chỉ chạy các file có sha256 trong `results/frozen_C1/SHA256SUMS_TEST`. Mọi thứ mới nằm trong `deploy/`.
Kế hoạch thí nghiệm: `audit/REAL_PREREG.md`. Danh sách việc trong ngày: `CHECKLIST_CHO_THAT.md`.

## 0. Nguyên tắc
- Vòng điều khiển chạy **trên Orin của chó** (Wi-Fi chỉ để gõ lệnh SSH). Lý do: memory "run onboard" (một lần quét L1 128 kB, Wi-Fi tiết kiệm điện làm odom còn 4 Hz).
- Chuyển động **chỉ** qua `/go2/cmd_vel` → `go2_hardware_bridge --allow-motion` → `SportClient.Move`. Không LowCmd, không SDK trong tiến trình thí nghiệm.
- Bridge **kẹp tốc độ** (`--max-vx/--max-vy/--max-wz`) và dừng sau 0,5 s không có lệnh. Người cầm remote suốt buổi.
- **Không** dùng `start_real.sh` / `eval_real.py` / `run_real_ros.py` cho thí nghiệm. Ba file này có lỗi đã thấy offline:
  không đặt `ROS_DOMAIN_ID` (SDK và rclpy cùng domain 0 → "Precondition Not Met"), cấu hình Cyclone ở `/tmp` (chó xoá `/tmp` khi khởi động),
  sai đường dẫn bridge, và `eval_real.py` khởi tạo SportClient trong cùng tiến trình.

## 1. Trên laptop: đóng gói
```bash
cd ~/Documents/Go2_assitant
bash deploy/make_bundle.sh      # kiểm sha256 đóng băng → dist/govoice_real_<ngày>.tar.gz + deploy/MANIFEST.sha256
```
Gói gồm:
- **11 file đóng băng**: nav_local, nav_prism2, robot_ros, isaac_val/cmd_shaper, research/algo_fast/fast.c, fastsim, movers, crowd_models, oracle_ctrl, dyn/go2_params.{py,yaml}.
  fastsim và các file đi cùng chỉ dùng cho bench trên chó.
- **4 file chạy kèm không đóng băng**: robot_real.py (sha c59b692f…), reflex_matcher.py (324551cc…), dyn/__init__.py, dyn/bagio.py.
- **Phiên đo động học**: dyn/sysid_real.py, dyn/HUONG_DAN_DO.md.
- **deploy/\***, SHA256SUMS_TEST, FROZEN.md, REAL_PREREG.md, REAL_SCHEDULE.csv, CHECKLIST_CHO_THAT.md.

Không chép: `fast.so` (bản x86-64, không chạy được trên aarch64), rl_nav/ (C1/B1 không dùng gợi ý RL), file Gazebo.

## 2. Chép lên chó (chỉ khi đã ở cạnh chó, ngày thí nghiệm)
```bash
scp -i ~/.ssh/go2_key dist/govoice_real_<ngày>.tar.gz unitree@<ip>:~/
ssh -i ~/.ssh/go2_key unitree@<ip> 'mkdir -p ~/govoice_real && tar xzf ~/govoice_real_<ngày>.tar.gz -C ~/govoice_real'
```
`<ip>`: 192.168.123.18 nếu cắm dây; nếu qua Wi-Fi thì xem IP trên router (IP đổi theo mạng).

## 3. Kiểm trên chó: mã khớp hash đóng băng
```bash
cd ~/govoice_real && bash deploy/verify_on_dog.sh --fast-so     # không gửi lệnh chuyển động nào; khoảng 10-15 phút
```
Script làm 8 việc:
1. `sha256sum -c deploy/MANIFEST.sha256` cho cả gói.
2. So 11 file đóng băng với **chính** `SHA256SUMS_TEST`, tức cùng hash đã dùng cho TEST fastsim và Gazebo.
3. Kiểm Python ≥ 3.8, numpy, scipy và cú pháp 3.8 (`deploy/py38check.py`).
4. Kiểm rclpy, tf2_ros, ros2 bag, và chạy `real_trial.py --dry`.
5. Còn ≥ 30 GB đĩa.
6. In chế độ nguồn (nvpmodel).
7. Xem có tiến trình trùng không (2 bridge, go2_auto, tour_driver).
8. Bench `ctrl.step` (C1, B1, C1~cs) trên CPU Orin. Với `--fast-so`, script build `fast_aarch64.so` từ `fast.c` đã băm
   (`gcc -O3 -mcpu=native -ffp-contract=off`) rồi bench lại.

**ĐẠT** nghĩa là mọi mục OK và C1, B1 có step p95 < 60 ms. File kết quả nằm ở `~/realprep/verify_*.txt`. Ghi sha của file này vào REAL_PREREG §9.

## 4. Bật hệ thống, kẹp tốc độ
```bash
cd ~/govoice_real
VX=0.20 VY=0.15 WZ=0.40 MERGED=1 DEPTH=0 bash deploy/start_stack.sh    # CHẠY THỬ, tối đa 0,2 m/s
# ... chạy thử xong và đạt §5 REAL_PREREG:
bash deploy/start_stack.sh stop
VX=0.30 VY=0.15 WZ=0.50 MERGED=1 DEPTH=0 bash deploy/start_stack.sh    # THÍ NGHIỆM CHÍNH (vy 0,15: sửa đổi #1 REAL_PREREG, 26/11)
```
- Script **từ chối** VX > 0,35, VY > 0,30, WZ > 0,80.
- Script không chạy nếu đã có bridge, go2_auto hoặc tour_driver.
- Script lưu PID vào `~/realprep/pids/` và chỉ dừng theo PID hoặc nhóm tiến trình.
- `MERGED=1`: chạy ouster_node + lidar_merge để có `/go2/lidar/merged` (L1 + OS1, base_link).
  **OS1 phải dùng nguồn riêng**: cấp từ Go2 thì Orin treo vì NVMe rớt.
- `DEPTH=1`: dùng realsense2_camera nếu có. Nếu không có, script chạy realsense_node + `caminfo_relay.py`
  (anh depth đã căn theo màu nhưng không có camera_info → robot_ros dùng sai FOV). Khi đó chạy real_trial với `--depth-topic /go2/camera/aligned_depth/image_raw`.

## 5. Chạy C1 và B1
```bash
mkdir -p ~/realprep/main && cp audit/REAL_SCHEDULE.csv ~/realprep/main/schedule.csv
sha256sum ~/realprep/main/schedule.csv      # phải là cea711d1… (REAL_PREREG §4)
python3 deploy/real_trial.py --run --out ~/realprep/main --cloud /go2/lidar/merged --cs --no-depth
```
- Chạy **trực tiếp trong cửa sổ SSH, không dùng tmux**. Nếu SSH rớt, SIGHUP làm runner dừng robot.
  Bridge (chạy nohup) giữ Move(0) rồi gọi StopMove. Lượt đó ghi là lỗi hạ tầng.
- Chạy thử dùng lịch riêng:
  `python3 deploy/real_trial.py --make-schedule --pairs 2 --scenarios S1,S2 --seed 1 --out ~/realprep/shakedown`, rồi `--run --out ~/realprep/shakedown …`.
- Mỗi lượt runner làm:
  1. Kiểm trước: odom, LiDAR, /go2/status, pin ≥ 30 %, nhiệt < 70 °C, thân đứng, bridge không chặn.
  2. Đặt lại y như `eval_sim.reset + reset_learned`: bản đồ trống, tracker v3 mới, vel_gain 0,5, bộ điều khiển mới.
     Nhiễu MPPI gieo theo số lượt. Khung "map" lấy tư thế xuất phát.
  3. Ghi rosbag `bags/tNNN` gồm odom, imu, cloud, cmd_vel, status, `/realprep/events`, path.
  4. Gọi `RealRobotTools.go_to_pose`, tức đúng `_navigate_mpc` đã băm.
  5. Canh gác trong lượt (dừng = thất bại):
     - người gạt remote (`/go2/status`: "remote is being used");
     - nghiêng > 20° hoặc thân thấp;
     - quá tốc độ (odom > hypot(cap) + 0,15 m/s);
     - ra ngoài hàng rào ±1,8 m;
     - nhận thức ngừng (bản đồ không cập nhật > 2 s);
     - hết 90 s;
     - bấm Enter.
  6. Người vận hành trả lời 3 câu: chạm người? chạm vật? lỗi hạ tầng?
  7. Ghi `trials.csv`.
- **Cấu hình không hiện trên màn hình** trong lúc chạy, để làm mù cho người cầm remote và người đi bộ.
- Đã kiểm khói trên laptop với "chó giả" (localhost, domain riêng, không có robot): 2 lượt đến đích, 1 lượt thất bại do gạt remote được bắt đúng, bag ghi được.
  Lần kiểm này bắt được và đã sửa 2 lỗi: thiếu thư mục bags, và tracker v2→v3 gây `KeyError('x')` ở mọi lần quét.

## 6. Ngân sách CPU và các quyết định khoá trước lượt 1
Đo trên laptop (Ryzen 7 8745H, 1 nhân, nice 19):

| phần | Py 3.14 + numpy 2.5 | Py 3.8 + numpy 1.24 (như chó) |
|---|---|---|
| `_on_cloud` mỗi lần quét, cloud merged (~30 k điểm) | 5,0 ms TB, p95 10,2 | 6,8 ms TB, p95 13,9 |
| `_on_cloud`, chỉ L1 | 1,1 ms TB, p95 2,3 | (chưa đo) |
| C1 `ctrl.step`, Python thuần | p50 15,3, p95 20,0 | p50 12,7, p95 15,5 |
| B1 `ctrl.step`, Python thuần | p50 14,8, p95 17,9 | p50 11,7, p95 13,7 |
| C1 có fast.so | p50 10,6, p95 14,5 | (chưa đo) |

- Orin Nano (A78AE 1,5 GHz) có thể chậm hơn khoảng 3–5 lần. Đây là **ước lượng, chưa đo**.
  Như vậy C1 step p95 có thể ~50–80 ms, cộng thêm 20–70 ms LiDAR mỗi lần quét trong cùng GIL, sát ngân sách 100 ms.
  Bench ở §3 cho số thật.
- Quy tắc chọn (ghi vào REAL_PREREG §3 trước lượt 1, giữ nguyên **cả phiên**, giống nhau cho C1 và B1):
  1. fast.so: dùng nếu build được và bench cho p95 thấp hơn. fast.so cho kết quả **trùng từng bit** với Python trên laptop (cùng số bước).
  2. Nếu C1 p95 > 60 ms: tắt depth trước. Nếu vẫn > 60 ms: dùng `/go2/lidar/points` (L1) thay cho merged.
  3. Nếu C1 p95 > 90 ms: **không chạy**. Báo lại, đừng đổi mã đóng băng tại chỗ.
- Số học: perception phát lại **trùng từng bit** giữa Py 3.8/numpy 1.24 và Py 3.14/numpy 2.5.
  Quỹ đạo điều khiển trong fastsim thì **không trùng bit** (số bước khác nhau). Kết quả có tương đương về thống kê hay không: xem REPORT_REALPREP §4.

## 7. Đường dừng khẩn cấp (từ mạnh tới nhẹ)
1. **Remote L2+B**: damp ở firmware, chó nằm xuống. Luôn dùng được, kể cả khi Orin treo. Đây là phanh chính.
2. **Gạt cần remote**: bridge ngừng chuyển `/go2/cmd_vel` ngay và trong 2 s sau đó; chó theo remote. Runner ghi lượt là "giành quyền" (thất bại).
3. **Enter** trong cửa sổ runner: `r.stop()` (hủy + 3 lệnh 0). **Ctrl-C** hoặc rớt SSH: runner dừng robot và thoát.
4. Cửa sổ SSH thứ hai: `bash deploy/estop.sh`. Lệnh này gửi SIGINT tới runner theo PID file, rồi phát 5 lệnh 0. `--bridge` thì tắt cả bridge (StopMove).
5. Tiến trình runner chết: bridge giữ Move(0) sau 0,5 s và gọi StopMove sau 2 s.
   Nếu chính bridge treo, tài liệu thứ cấp nói Move chỉ "sống" 1 s, nhưng **điều này chưa kiểm trên con chó này**.
   Vì vậy L2+B là phanh duy nhất đáng tin.

## 8. `~cs` (bộ nắn lệnh)
- `--cs` thêm tag `~cs` cho **cả** C1 và B1: `p3+geo-haz+gcv~t3~nl~cs:ppl=32;ppl_len=0.5`, `mppi~t3~nl~cs:ppl=100;ppl_len=0.5`.
- Tag có sẵn trong robot_ros.py (đã băm), gọi `isaac_val/cmd_shaper.CmdShaper`:
  - khi |vy| > 0,15 hoặc vx < −0,05 thì |wz| ≤ 0,6;
  - |Δvy| ≤ 1,5/s, |Δwz| ≤ 2,5/s.
- Isaac: ngã 6/200 → 0/200. fastsim go2: mất 5–8 điểm, chưa có ý nghĩa.
- **Đã thấy offline**: phanh cuối của robot_ros (free < 0,09 m) đặt vx = vy = 0 *trước* shaper, nên vy vẫn bị giới hạn tốc độ đổi.
  Sau khi phanh, chó có thể còn nhận vy ≤ 0,15 m/s thêm 1 nhịp (0,1 s). Chú thích "lệnh dừng đi qua nguyên vẹn" trong cmd_shaper.py
  chỉ đúng với `install()` (bọc `_twist`), không đúng với đường gọi trong robot_ros.
  Ảnh hưởng: tối đa ~1,5 cm. Ghi vào hạn chế; không sửa vì file đã đóng băng.

## 9. Bẫy tương thích đã kiểm offline (và phải kiểm lại trong ngày)
| vấn đề | đã xử lý? | kiểm trong ngày |
|---|---|---|
| Cloud merged ở `base_link`. RosRobotTools hỏi TF `go2/base_link←base_link`, không có, nên **tự rơi về R_BASE_LIDAR của L1** và xoay sai toàn bộ điểm | runner đặt sẵn `_lidar_tf` = đơn vị | không |
| Tracker tạo ở v2 (controller mặc định "mppi") rồi chuyển sang `~t3` → `KeyError('x')` ở **mọi** lần quét, bản đồ ngừng cập nhật | runner đặt C1 từ đầu, tracker mới có mode v3; có canh gác "nhận thức ngừng" | xem log không có "loi xu ly LiDAR" |
| fast.so chỉ có bản x86-64 | build từ fast.c đã băm, hoặc dùng Python | verify §8 |
| Python 3.8 / numpy 1.24 / scipy 1.10 | cú pháp 3.8 OK; chạy thật perception, bench, real_trial --dry trong venv 3.8.20 + numpy 1.24.4 + scipy 1.10.1 | verify §3 |
| Foxy: `TransformListener` không có `static_only` → nghe cả `/tf` (chiếm GIL) | không sửa được (đóng băng) | `ros2 topic hz /tf`; nếu > 30 Hz thì tắt robot_state_publisher trong lúc thí nghiệm |
| `ros2 bag record`: Foxy nhận topic theo vị trí, bản mới dùng `--topics` | runner chọn theo `ROS_DISTRO` | verify §4 |
| Laptop Lyrical (Fast DDS 3) vào domain 1 làm Cyclone 0.10 trên chó **abort** bridge | — | laptop KHÔNG source ROS khi SSH; nếu cần xem topic thì dùng `config/fastdds_go2.xml` |
| 2 bridge cùng chạy (start_hardware_bridge tự khởi động lại) | start_stack từ chối | `ps -o pid,args -C python3 \| grep bridge` = 1 dòng |
| OS1 cấp nguồn từ Go2 → Orin treo | — | OS1 dùng nguồn riêng; `journalctl -k \| grep -i nvme` sau mỗi giờ |
| D435i chỉ chạy USB 2.1; realsense_node không có camera_info cho depth | caminfo_relay.py | quyết định DEPTH trước lượt 1 |
| `_backup` lùi 0,3 m chỉ kiểm `free_distance(-1,0)`. L1 gần như mù phía sau | merged có OS1 360° | nếu chỉ có L1: ghi vào hạn chế |
| odom bridge nhân 1,19, còn dư +2–3 % | không cần sửa (REPORT_DYN) | không |
| Pin < 25 % hoặc nghiêng > 20° thì bridge từ chối chạy | runner dừng ở 30 % | không |
