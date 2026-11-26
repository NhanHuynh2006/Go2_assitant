# ĐĂNG KÝ TRƯỚC: thí nghiệm Go2 THẬT, C1 vs B1 (REALPREP, viết 25/11/2026, TRƯỚC mọi lượt thật)

Trạng thái: **bản nháp khoá được**. Trước lượt 1, điền §9, băm file này (`sha256sum audit/REAL_PREREG.md`) và ghi vào research/LOG.csv.
Mọi thay đổi sau đó là **Lệch #k**: ghi lý do, giờ, và có thấy kết quả lượt nào trước khi đổi hay không.
Mã: chỉ dùng file đóng băng (`results/frozen_C1/SHA256SUMS_TEST`). Triển khai: `deploy/DEPLOY.md`. Lịch: `audit/REAL_SCHEDULE.csv`.

## 0. Câu hỏi và giới hạn
- **Câu hỏi chính:** trên Go2 thật, cùng cảm biến, cùng tracker v3, cùng giới hạn tốc độ, C1 có tỉ lệ "tới đích sạch" khác B1 không?
  "Tới đích sạch" định nghĩa ở §5.
- **Nói trước:** với 60 cặp có người, lực phép thử thấp, chỉ 2–49 % tuỳ hiệu ứng thật (§7.3).
  Kết quả âm hoặc không có ý nghĩa là **kết quả hợp lệ** và phải báo. Mục tiêu thực tế:
  1. chứng minh chạy được và an toàn trên chó thật;
  2. xem dấu chênh lệch có khớp fastsim/Gazebo/Isaac không;
  3. có ước lượng kèm khoảng tin cậy.
  Không phải khẳng định "hơn".

## 1. Cấu hình so sánh (đóng băng, research/FROZEN.md)
- C1 = `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5`. B1 = `mppi~t3~nl:ppl=100;ppl_len=0.5`.
  Hai cấu hình dùng chung tracker v3 (`~t3`) và RespModel (`~nl`).
- Lớp triển khai giống hệt cho cả hai, **không phải** thuộc tính của thuật toán:
  - tag `~cs` (bộ nắn lệnh, ISAAC §11.5);
  - bridge kẹp tốc độ;
  - bộ canh gác trong `deploy/real_trial.py`.
- B0, PGIF\*, DRA\* **không** chạy trên chó: không đủ thời gian và lực thống kê. Ghi vào hạn chế.

## 2. Kịch bản (độ khó tăng dần; đường 6 m, rộng 3,6 m, sàn phẳng khô)
Vạch xuất phát x = 0, hướng +x. Thùng carton 50 × 50 × 50 cm. Băng dính đánh dấu vạch kích hoạt và đường đi của người.

| | tên | mô tả | đích | người |
|---|---|---|---|---|
| S1 | vật tĩnh | 3 thùng so le: (2,0; +0,35), (3,5; −0,35), (5,0; +0,35) | (6, 0) | 0 |
| S2 | 1 người cắt ngang | đi trái → phải ở x = 3,5, từ y = +2,5 tới −2,5. Xuất phát khi chân trước của chó qua vạch x = 1,5 | (6, 0) | 1 |
| S3 | 1 người đối đầu | đi từ (7,5; 0) về phía vạch xuất phát trên trục y = 0. Xuất phát khi chó qua x = 1,0 | (6, 0) | 1 |
| S4 | 2 người | một người cắt ngang ở x = 4,0 như S2; một người đối đầu lệch y = +0,4 như S3. Cùng vạch kích hoạt x = 1,0 | (6, 0) | 2 |
| S5 | lùi + xoay chậm (ca ngã của Isaac) | túi hẹp: 2 thùng chắn trước mặt ở x = +0,9 (y = ±0,3); hai hàng thùng hai bên y = ±0,7 từ x = −0,3 tới +0,9. Chó đứng **mặt vào** thùng; đích ở **sau lưng** 3 m. Phải lùi + xoay trong khoảng 1,4 m | (−3, 0) | 0 |

- **Người đi bộ** là thành viên phòng thí nghiệm đã đồng ý (§8).
  - Đi tự nhiên, khoảng 1,0 m/s, đúng đường băng dính. Không cố né, không cố chặn robot.
  - Được phép dừng hoặc bước tránh **bất cứ lúc nào** thấy không an toàn. Lần né đó ghi là "né tránh", là chỉ số phụ, không tự thành thất bại.
  - Mỗi người giữ vai cố định (P1 cắt ngang, P2 đối đầu) suốt một kịch bản.
- S5 không có người: đây là kiểm an toàn cơ học (lùi + xoay là chỗ policy Isaac ngã). Sau S1, mức độ nguy hiểm cho người tăng dần từ S2 tới S4.

## 3. Thiết lập triển khai, khoá TRƯỚC lượt 1 và giữ nguyên CẢ phiên
| mục | giá trị đăng ký | lý do |
|---|---|---|
| kẹp bridge (vx/vy/wz) | **0,30 / 0,15 / 0,50** (thí nghiệm chính; vy hạ từ 0,25, sửa đổi #1). Chạy thử: 0,20 / 0,15 / 0,40 | trùng mức CHAMP cắt trong Gazebo TEST; người dùng yêu cầu bắt đầu ở 0,2 |
| goto_speed / goto_turn | 0,35 / 0,8 → vmax bộ điều khiển (0,595; 0,3; 1,0) | giá trị của fastsim.make_robot (đóng băng); bridge cắt giống Gazebo |
| cảm biến LiDAR | `/go2/lidar/merged` (L1 + OS1). Chỉ dùng L1 nếu bench quá ngân sách (DEPLOY §6) | replay: L1 thấy rất ít (r95 ≈ 3,6 m, mù phía sau) |
| D435i | quyết định theo DEPLOY §6 (mặc định TẮT) | CPU Orin; USB 2.1; thiếu camera_info |
| `~cs` | **BẬT** cho cả hai | an toàn phần cứng (Isaac ngã 6/200 → 0/200). Giá ở fastsim n.s. |
| fast.so | dùng nếu build được trên aarch64 và bench nhanh hơn | trùng bit với Python (đã kiểm trên laptop) |
| đặt lại mỗi lượt | bản đồ trống, tracker mới, vel_gain 0,5, bộ điều khiển mới, nhiễu MPPI gieo theo số lượt | = eval_sim.reset_learned (PREREG_TEST §0.4) |
| thời gian tối đa | 90 s / lượt | 6 m ở ≥ 0,07 m/s |
| tới đích | sai số vị trí cuối < 0,35 m (tol điều khiển 0,2) | = fastsim, eval_real |

Nếu bench hoặc kiểm tra trong ngày buộc đổi một dòng trên: đổi **trước** lượt 1, ghi vào §9, và áp dụng cho cả C1 lẫn B1.

## 4. Số lượt, ghép cặp, thứ tự
- **20 cặp / kịch bản × 5 kịch bản = 200 lượt**, tức 100 lượt mỗi cấu hình. Mỗi cặp là 2 lượt liền nhau cùng kịch bản, cùng người, cùng cách bày.
- Thứ tự trong cặp: ngẫu nhiên **cân bằng**, mỗi kịch bản đúng 10 cặp C1 đi trước.
  Seed 20261125, sinh bằng `deploy/real_trial.py --make-schedule`.
  File `audit/REAL_SCHEDULE.csv`, sha256 `cea711d14ca9f2ce643a9ca983f1752e20fca390ae88be6b78584b24930c39cc`.
- Thứ tự kịch bản cố định S1 → S5 (tăng độ khó, an toàn), **không** xáo. Hệ quả: kịch bản trùng với thời gian và pin.
  Phép so là trong cặp, nên điều này không làm lệch phép so.
- **Làm mù:**
  - Runner không in cấu hình. Người cầm remote, người đi bộ và người chấm video không biết lượt nào là C1 hay B1.
  - Người chạy runner không mở `schedule.csv` trong phiên.
  - Video đặt tên theo số lượt.
- Chạy thử (không tính): lịch riêng, `--pairs 2 --scenarios S1,S2 --seed 1`, kẹp 0,2.

## 5. Kết quả (định nghĩa cho thế giới thật)
**Thành công (chỉ số chính)** = tới đích (§3) và **không** có điều nào sau đây:
1. **Bất kỳ va chạm** nào với người hoặc vật, kể cả chạm nhẹ.
   Ghi trực tiếp (câu hỏi sau lượt), rồi chấm lại bằng video **mù cấu hình**. Video và người vận hành mâu thuẫn thì lấy "có chạm".
2. **Giành remote**: bridge báo "remote is being used" (runner tự ghi), hoặc người cầm remote báo đã can thiệp.
3. **Dừng khẩn cấp** do người (Enter, estop.sh, L2+B).
4. **Canh gác tự động dừng**: quá tốc độ, ra ngoài hàng rào, nhận thức ngừng.
5. **Hết 90 s.**
6. **Ngã hoặc mất thăng bằng**: nghiêng > 20°, thân chạm đất, hoặc video thấy vấp phải bước bù rõ.

**Quy tắc giành remote:** người cầm remote chỉ can thiệp khi
- sắp chạm người (< ~0,3 m và đang tiến lại);
- sắp chạm vật ở tốc độ > 0,1 m/s;
- đi ra ngoài sân;
- hoặc có dấu hiệu ngã.
Không can thiệp vì "chậm" hay "đi vòng".

**Lỗi hạ tầng (không tính, chạy lại):** chỉ những lỗi **độc lập với bộ điều khiển** và có bằng chứng trong log:
- SSH rớt;
- tiến trình bridge, sensor hoặc runner chết với traceback ngoài `nav_local`/`nav_prism2`/`robot_ros`;
- Orin treo;
- mất cảm biến ở mức bridge.

Xử lý:
- chạy lại cùng lượt, tối đa 2 lần; quá 2 lần thì cặp đó bị loại khỏi phân tích chính và báo riêng;
- lỗi trong mã điều khiển, kể cả exception, **tính là thất bại**;
- người chạy runner quyết bằng câu hỏi "Lỗi hạ tầng?" trước khi xem cấu hình.

**Chỉ số phụ** (báo cáo, không kết luận riêng):
- thời gian tới đích (cặp cả hai thành công);
- khoảng cách nhỏ nhất tới người, theo tracker và theo video;
- số lần người phải né;
- số lần phanh / lùi;
- p95 thời gian `ctrl.step`;
- chu kỳ lệnh;
- số lần `~cs` cắt lệnh;
- nghiêng lớn nhất.

## 6. Đo bằng gì
- **rosbag mỗi lượt** (`bags/tNNN`): /go2/odom, /go2/imu/data, cloud đang dùng, /go2/cmd_vel, /go2/status, /realprep/events (JSON bắt đầu/kết thúc), /go2/govoice/path. Ghi trên đĩa Orin.
- **Video**:
  - 2 điện thoại trên chân máy, 30 fps: một nhìn ngang đường chạy, một nhìn chéo từ phía đích.
  - Đầu mỗi lượt giơ bảng số lượt trước camera.
  - Mốc đồng bộ: thời điểm `t_wall` trong /realprep/events; đồng hồ điện thoại chỉnh NTP trước buổi.
- `trials.csv` (runner): kết quả, cờ thất bại, chỉ số phụ, thời gian.
- Chấm video sau buổi:
  - 1 người không biết cấu hình chấm chạm / né / ngã;
  - chấm xong mới ghép với `schedule.csv`;
  - người thứ hai chấm lại 20 % số lượt để đo độ đồng thuận.

## 7. Thống kê
### 7.1 Chính (1 phép thử)
- Gộp **S2–S4 (60 cặp có người)**. Phép thử: **McNemar chính xác 2 phía** (nhị thức trên cặp bất đồng b = C1 thắng, c = B1 thắng), α = 0,05.
- Ước lượng: (b − c)/n với KTC 95 % bootstrap theo cặp (10 000 lần); kèm tỉ lệ thành công mỗi cấu hình (Wilson 95 %).

### 7.2 Phụ (Holm trong 3 phép)
- (a) S1 riêng.
- (b) S5 riêng.
- (c) gộp cả 100 cặp.
- Từng kịch bản (S1–S5): chỉ mô tả (b, c, Wilson). Chỉ số phụ liên tục: Wilcoxon cặp, chỉ mô tả.
- Kiểm định nhạy: (i) bỏ "giành remote" khỏi thất bại; (ii) tính lỗi hạ tầng là thất bại của cấu hình đang chạy.

### 7.3 Lực trung thực
`audit/real_power.py`: McNemar chính xác, α 0,05. Tỉ lệ bất đồng lấy từ kết quả đã công bố.

| hồ sơ bất đồng (C1 thắng / B1 thắng) | 60 cặp | 100 cặp | 200 cặp |
|---|---|---|---|
| fastsim TEST go2_base (11,2 % / 5,1 %) | 0,13 | 0,25 | 0,51 |
| fastsim TEST go2_helb (6,1 % / 4,3 %) | 0,02 | 0,04 | 0,08 |
| Isaac v3 thăm dò (20 % / 6 %) | 0,49 | 0,75 | 0,98 |
| Isaac pilot `~cs` (9 % / 4 %) | 0,10 | 0,20 | 0,42 |

Đường chạy thật dễ hơn thế giới fastsim (1–2 người, 6 m), nên cặp bất đồng có thể còn **ít hơn**.
Muốn có ý nghĩa thì cần, ví dụ, ≥ 9/10 hoặc ≥ 15/20 cặp bất đồng nghiêng về C1.

**Câu chữ được phép:**
- p > 0,05: "trên chó thật không đủ bằng chứng có khác biệt (b vs c, KTC …); dấu chênh lệch [khớp/không khớp] mô phỏng".
- p ≤ 0,05: "C1 hơn B1 trên chó thật trong 3 kịch bản có người, n = 60 cặp", kèm các hạn chế ở §10.

Không dùng "hơn hẳn" hay "chắc chắn". Không gộp số chó thật với mô phỏng.

## 8. An toàn và quy tắc dừng
**Trước buổi:**
- người tham gia đồng ý bằng văn bản, được quyền dừng;
- kiểm quy định đạo đức nghiên cứu có người tham gia của cơ quan trước khi công bố;
- người đi bộ đi giày kín;
- không có trẻ em hay người ngoài trong sân.

**Quy tắc dừng** (runner tự dừng ở R1, R3; còn lại người điều phối quyết):
- **R1** chạm người bất kỳ: dừng phiên ngay, xem video.
  - Nếu robot đang tiến vào người (lỗi do robot): **cấu hình đó ngừng mọi kịch bản có người**. Các lượt còn lại theo lịch của nó tính **thất bại**; phân tích báo cả hai cách.
  - Nếu do người bước vào robot đang đứng hoặc lùi: ghi lại, được tiếp tục.
- **R2** chạm người lần thứ 2 (bất kỳ cấu hình): kết thúc mọi kịch bản có người.
- **R3** ngã hoặc mất thăng bằng: dừng phiên, kiểm chó (khớp, nhiệt, pin).
  Ngã trong S5 thì ngừng S5 cho cả hai cấu hình và báo số đã có.
- **R4** chạm vật ở tốc độ > 0,2 m/s hai lần cùng cấu hình: dừng, kiểm kẹp tốc độ và cảm biến.
- **R5** canh gác quá tốc độ kích hoạt: dừng phiên, kiểm cờ `--max-*` của bridge (`~/realprep/logs/bridge.log` dòng "MOTION ENABLED").
- **R6** Orin treo, lỗi NVMe, hoặc mất cảm biến > 0,6 s quá 2 lần trong 1 giờ: dừng buổi (nguồn OS1?).
- **R7** pin < 30 %, động cơ > 70 °C, sàn ướt, người lạ vào sân: nghỉ hoặc dừng.
- **R8** bất kỳ người tham gia nào yêu cầu: dừng ngay.
- **Cổng chuyển kịch bản:** chỉ sang kịch bản kế tiếp khi kịch bản trước không kích hoạt R1–R5.

## 9. Khoá trước lượt 1 (điền trong ngày, trước khi chạy)
| mục | giá trị |
|---|---|
| ngày, nơi, sàn, nhiệt độ | |
| sha256 `dist/govoice_real_*.tar.gz` | |
| `~/realprep/verify_*.txt`: ĐẠT? sha256 | |
| bench Orin: C1 / B1 step p95 (ms), Python / fast.so | |
| quyết định §3: cloud / depth / fast.so / kẹp | |
| sha256 `schedule.csv` trong thư mục phiên (phải = cea711d1…) | |
| firmware Go2, dáng đi (mặc định), tránh vật cản của app: TẮT | |
| người: remote = R, chạy runner = O, đi bộ = P1, P2, chấm video = V (mã, không tên) | |
| sha256 file REAL_PREREG.md này sau khi điền | |

## 10. Hạn chế biết trước (từ phát lại offline, REPORT_REALPREP)
- Trên bản ghi thật (L1 + OS1), tracker v3 tạo vết "người ma" trên vật tĩnh ở **24–29 % số nhịp** (toàn vòng).
  Tính riêng nửa trước trong 4 m: 7–10 % theo định nghĩa chặt, 16–17 % nếu tính cả vết không rõ.
  Con số này gần Gazebo S4 (~30 %) hơn fastsim (7–10 %). Ma làm chậm hoặc kẹt cả C1 lẫn B1 (TESTSTATIC: C1 −0,95 điểm vs B1).
- Chưa có bản ghi nào có người đi **trước mặt** chó. Bản ghi chỉ có người điều khiển đi phía sau (~3 m).
  Độ trễ xác nhận người cho người thật phía trước chưa đo được. Phải ghi 10 phút trong ngày (CHECKLIST bước 4).
- Python 3.8 / numpy 1.24 trên chó cho quỹ đạo điều khiển khác từng bit so với laptop. Perception thì trùng bit.
- CPU Orin chưa đo; DEPLOY §6.
- `~cs`: sau phanh cuối, vy còn tối đa 0,15 m/s thêm 1 nhịp (DEPLOY §8).
- 1 sàn, 1 chó, 2–3 người đi bộ quen robot. Người lạ có thể phản ứng khác.

## 11. Khác với TEST mô phỏng (công bố trong bài)
- Có `~cs` cho cả hai.
- Tốc độ bị bridge kẹp 0,30/0,15/0,50: tiến và xoay giống CHAMP trong Gazebo, ngang thấp hơn (0,15 so với 0,25); khác fastsim go2.
- Cảm biến LiDAR 3D gộp thay cho LiDAR 2D 360 tia; có hoặc không có depth.
- Người thật đi theo kịch bản, không phải mô hình đám đông.
- Không có PGIF\*/DRA\*/B0.
- Số lượt ít, thứ tự kịch bản cố định.


## Sửa đổi #1 (coordinator, 26/11/2026, TRƯỚC mọi lượt trên chó thật; người dùng yêu cầu)
- **Thay đổi:** kẹp vận tốc ngang của bridge trong thí nghiệm chính hạ từ **0,25 xuống 0,15 m/s**. Chạy thử giữ 0,20/0,15/0,40. Giới hạn cứng của script giữ nguyên.
- **Lý do:** trong Gazebo TEST, robot di chuyển lệch hướng thân khoảng 41–44° (trung vị). Nguyên nhân là MPPI dùng vận tốc ngang, trong khi CHAMP cắt tốc độ tiến ở 0,3 m/s nhưng cho ngang tới 0,25 m/s. Giảm đi chéo giúp người xung quanh dễ đoán hướng robot hơn.
- **Phạm vi:** áp dụng như nhau cho C1 và B1. Bộ điều khiển, lịch chạy (REAL_SCHEDULE.csv) và tiêu chí thành công không đổi.
- **Ảnh hưởng dự kiến:** đo trên DEV fastsim (champ2, vy 0,15 so với 0,25), xem research/LOG.csv ngày 26/11.
