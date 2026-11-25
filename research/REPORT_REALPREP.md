# REPORT_REALPREP — chuẩn bị thí nghiệm chó thật, offline (agent REALPREP, 25/11/2026)

> Coordinator lưu từ báo cáo bàn giao: harness chặn agent ghi .md, và người dùng đã cho phép lưu báo cáo của agent.
>
> **Coordinator đã kiểm lại (25/11 00:40):**
> - Gói `dist/govoice_real_20261125.tar.gz` có sha 6bf5b5ac…. Giải nén vào scratchpad rồi chạy `sha256sum -c deploy/MANIFEST.sha256` từ gốc gói: OK (32 file). MANIFEST trong repo: OK.
> - SHA256SUMS_TEST, SHA256SUMS_ISAAC và SHA256SUMS_ISAAC_TEST: OK.
> - `deploy/real_trial.py` không khởi tạo SportClient trong tiến trình. Chuyển động chỉ đi qua /go2/cmd_vel → go2_hardware_bridge, có kẹp tốc độ.
> - REAL_PREREG.md sha 6bf81188…, REAL_SCHEDULE.csv sha cea711d1….
>
> **Quyết định của coordinator:** giữ `~cs` BẬT cho cả C1 và B1 trên chó thật, như REAL_PREREG đề xuất. Lý do là an toàn phần cứng: ở Isaac, tỉ lệ ngã từ 6/200 xuống 0/200. Quyết định này có trước lượt 1.
>
> **Vi phạm nhỏ, agent tự khai:** vài lần chạy ngắn bị ghim vào nhân 10–11, trùng vùng nhân của Isaac. Isaac chỉ chiếm GPU và nhân 10–15 ở nice 19, nên kết quả từng lượt không đổi; chỉ có thông lượng bị ảnh hưởng. guard.log không có lần tạm dừng nào.

## Điều kiện
- Không chạm chó, không đụng mạng 192.168.123.x, không sudo.
- Không sửa file đóng băng; sha khớp đầu và cuối phiên.
- Tối đa 2 nhân, nice 19, OPENBLAS 1 luồng.
- File mới: `deploy/` (12 file + MANIFEST), `audit/REAL_PREREG.md`, `audit/REAL_SCHEDULE.csv`, `audit/real_power.py`, `CHECKLIST_CHO_THAT.md`, `results/REALPREP/`, `dist/govoice_real_20261125.tar.gz`.
- Có 7 dòng REALPREP trong LOG.csv.

## §1 Phát lại bản ghi thật qua nhận thức đóng băng (`deploy/replay_perception.py`)

**Cách chạy**
- Gọi đúng `RealRobotTools._on_imu` và `_on_cloud` đã băm, rồi đưa qua BlobTracker v3. C1 và B1 dùng chung khâu này.
- Đối tượng được tạo qua `object.__new__`, nên không cần ROS.
- Đồng hồ lấy theo thời gian của bản ghi.

**Sự thật độc lập**
- Quỹ đạo lấy từ SLAM `~/go2_maps/*.tum`, cộng một lưới "bền vững" 0,2 m.
- Phân loại vết:
  - **ma:** trung vị độ bền ≥ 0,30;
  - **thật:** đi ≥ 1 m, độ bền < 0,25, đỉnh cụm 1,2–2,1 m;
  - mọi vết khác: **không rõ**.

| bản ghi | cảm biến | số nhịp | % nhịp có vết | % nhịp có ma (chặt / tính cả không rõ) | ma nửa trước, < 4 m | số vết ma / không rõ / thật | ma > 2 s | CPU TB / p95 (ms) |
|---|---|---|---|---|---|---|---|---|
| lab2_175037 | gộp | 982 | 50,6 | 29,2 / 33,1 | 7,4 / 16,0 | 54 / 32 / 20 | 15 | 5,0 / 10,2 (Py3.8 6,8 / 13,9) |
| yard_104758 | gộp | 844 | 35,8 | 24,3 / 30,6 | 10,4 / 16,7 | 38 / 15 / 5 | 10 | 3,9 / 8,1 |
| lab_slim | chỉ L1, 10 Hz | 693 | 5,6 | 0 / 3,6 | 0 / 3,3 | 0 / 9 / 1 | 0 | 1,1 / 2,3 |

**Về ma**
- Tỉ lệ nhịp có ma ở thực tế gần Gazebo S4 (~30 %) và cao hơn hẳn fastsim (7–10 %).
- Ma nằm chủ yếu phía sau chó, góc trung vị 159–163°, nơi người điều khiển đi theo.
- Mỗi vết ma sống 0,9–1,2 s (trung vị), dài nhất 5,9–8,2 s.

**Về người thật**
- Người thật duy nhất trong các bản ghi là người điều khiển, ở góc 168°, cách khoảng 3 m.
- Tracker xác nhận người này sau 0,42 / 0,41 s (độ trễ bên trong tracker).
- **Không bản ghi nào có người cắt ngang hoặc đi đối đầu.**

**Chỉ dùng L1**
- 54 % điểm rơi vào thân chó, r95 chỉ 3,6 m, phía sau bị mù.
- Vì vậy đăng ký trước chọn cloud gộp.

**Bản ghi khác**
- lab2_174920 hỏng.
- lab2_174958 (16 s) có 71 % nhịp có vết, chưa giải thích được.

**Chưa chắc:** tiêu chí phân loại là heuristic, chưa kiểm bằng video; lưới bền vững bỏ qua che khuất.

**Cần làm:** ghi 10 phút có người trong ngày chạy chó (CHECKLIST bước 4–5), rồi phát lại trên Orin.

## §2 Thời gian một bước điều khiển (fastsim go2, 8 thế giới DEV)

| | Py3.14 Python | Py3.14 fast.so | Py3.8 Python |
|---|---|---|---|
| C1 p50 / p95 (ms) | 15,3 / 20,0 | 10,6 / 14,5 | 12,7 / 15,5 |
| B1 p50 / p95 (ms) | 14,8 / 17,9 | 10,9 / 14,4 | 11,7 / 13,7 |

- fast.so cho kết quả trùng bit với bản Python.
- Ước tính Orin chậm hơn 3–5 lần.
- Ngưỡng chọn đã đăng ký trước ở DEPLOY §6: 60 / 90 ms.
- fast.so phải build lại trên chó.

## §3 Gói triển khai và các lỗi tìm được offline

**Thành phần:** DEPLOY.md, make_bundle.sh, verify_on_dog.sh, start_stack.sh (có chế độ READONLY), real_trial.py, estop.sh, caminfo_relay.py, py38check.py.

**Kẹp tốc độ ở bridge**
- Chạy thử: 0,2.
- Chạy chính: 0,30 / 0,25 / 0,50.
- Từ chối giá trị lớn hơn 0,35 / 0,30 / 0,80.

**Runner tự bắt:** giành remote, nghiêng, quá tốc, ra ngoài hàng rào, mất nhận thức, hết giờ. Runner làm mù cấu hình (không lộ C1 hay B1).

**Kiểm khói với chó giả:** 2 lượt tới đích (lệch 0,17 / 0,14 m), bắt đúng việc giành remote.

**Lỗi tìm được**
- (a) Tracker v2→v3: bộ điều khiển mặc định "mppi" tạo vết kiểu v2. Với `~t3`, mỗi lần quét ném `KeyError('x')` và bản đồ đứng im, nhưng lượt vẫn ghi "tới đích", nên trên chó lỗi sẽ không ai thấy. Runner đã xử lý.
- (b) Cloud gộp đã ở base_link, nhưng khi không có TF thì code rơi về R_BASE_LIDAR của L1 và xoay sai. Runner đã xử lý.
- (c) `start_real.sh` / `eval_real.py` không dùng được cho thí nghiệm: không đặt ROS_DOMAIN_ID, cấu hình Cyclone nằm ở /tmp, SportClient chạy cùng tiến trình.
- (d) `~cs`: sau phanh cuối, vy còn tối đa 0,15 m/s trong 1 nhịp. File đóng băng nên không sửa.
- (e) D435i không có camera_info cho depth. Đã thêm caminfo_relay.py.
- (f) Foxy: TransformListener nghe cả /tf và chiếm GIL.

**Chưa kiểm được:** gcc aarch64, rclpy trên Foxy, Cyclone, CPU Orin, tần số /go2/status.

## §4 So Python 3.8 với 3.14
- Nhận thức trùng bit.
- Quỹ đạo khác bit: 0/43 lượt cùng thời gian.
- Tỉ lệ tới đích:
  - C1: 21 vs 20 (p 1,0);
  - B1: 19 vs 15 (p 0,29).
- Chạy dừng giữa chừng; có thể chạy tiếp từ chỗ dừng.

## §5 Đăng ký trước cho chó thật (`audit/REAL_PREREG.md`)

**Thiết kế**
- 5 kịch bản S1–S5, mỗi kịch bản 20 cặp, tổng 200 lượt.
- Thứ tự trong mỗi cặp ngẫu nhiên, cân bằng 10/10.
- Lịch chạy: REAL_SCHEDULE.csv.

**Thành công** khi tới đích và không có: chạm, giành remote, dừng khẩn, ngã, quá 90 s.

**Kiểm định**
- Phép chính: McNemar chính xác trên S2–S4 (60 cặp).
- 3 phép phụ, hiệu chỉnh Holm.
- Quy tắc dừng: R1–R8.
- Mục §9 khoá trong ngày chạy.

**Lực thống kê**

| số cặp | hồ sơ go2_base | go2_helb | Isaac v3 |
|---|---|---|---|
| 60 | 0,13 | 0,02 | 0,49 |
| 100 | 0,25 | 0,04 | 0,75 |
| 200 | 0,51 | 0,08 | 0,98 |

Lực thấp, nên phần chó thật trong bài là **kiểm chứng khả thi** (an toàn, chạy được thời gian thực, tỉ lệ ma thật). Không được nói là "thắng có ý nghĩa thống kê". Câu chữ được phép dùng đã viết sẵn trong REAL_PREREG.

## §6 Đề nghị (chưa áp dụng vì file đã đóng băng; để cho bài sau)
- cmd_shaper: cho lệnh phanh đi qua.
- Đặt tracker.mode theo controller ngay từ đầu.
- `_lidar_to_base` nhận frame `base_link`.
- Ghi chú `start_real.sh` là bản cũ.
- Đưa tỉ lệ ma thật vào phần hạn chế của bài.

## §7 Giấy phép
Venv thử (uv, trong scratchpad): CPython 3.8.20 (PSF), numpy 1.24.4 (BSD-3), scipy 1.10.1 (BSD-3), PyYAML 6.0.3 (MIT). Không phân phối lại.

## Danh mục: CHECKLIST_CHO_THAT.md
1 trang, gộp phiên đo động học và bản ghi 10 phút. Ước khoảng 2 buổi:
- buổi A: bước 1–9, S1, S2;
- buổi B: S3–S5.

## §4b Python 3.8 so với 3.14: đã chạy đủ (coordinator, 25/11 16:20)

Chạy tiếp lần dở trước, đủ 101 thế giới có người (DEV seed 0–149, go2) × 2 cấu hình = 202 cặp lượt.

**Kết quả:** chạy được trên Python 3.8, và tỉ lệ thành công không khác với 3.14.
- **Quỹ đạo khác từng bit:** chỉ 3/202 lượt có cùng thời gian. Nguyên nhân là phép tính số thực khác nhau giữa numpy 1.24 và numpy 2.x. Đây là hỗn loạn số học, không có hướng lệch.
- **Tỉ lệ thành công:**

  | Cấu hình | Py3.8 | Py3.14 | Bất đồng (chỉ 3.8 / chỉ 3.14 thành công) | p |
  |---|---|---|---|---|
  | C1 | 92/101 | 94/101 | 5/7 | 0,77 |
  | B1 | 83/101 | 82/101 | 11/10 | 1,0 |

- **Chênh C1−B1:** +9 lượt trên Py3.8, +12 lượt trên Py3.14.

**Dùng trên chó thật:** chạy được trên Python 3.8 của chó. Chênh lệch từng lượt chỉ là nhiễu số học, nên không cần tái lập từng bit.
