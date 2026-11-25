# Báo cáo GAZEBO (24/11): kiểm khói TRƯỢT S4; S1, S2, S3, S5, S6 ĐẠT

**research/REPORT_GAZEBO.md CHƯA được ghi:** hệ thống chặn lệnh ghi file .md ("Subagents should return findings as text"). Theo luật, tôi không lách. Toàn văn báo cáo nằm trong tin này; nhờ anh dán vào file đó hoặc cấp quyền ghi. Các dòng LOG.csv đã ghi (agent = GAZEBO, 9 dòng).

## Kết luận
Không chạy Gazebo TEST cho tới khi anh quyết về S4. Lỗi nằm ở perception, không phải ở hạ tầng đánh giá. Muốn sửa phải đụng robot_ros.py hoặc nav_local.py (bộ đếm vết người), mà theo luật tôi phải dừng và báo trước.

## 1. Sửa hạ tầng (PREREG §0.4)
Chỉ sửa **eval_sim.py**. File này **có trong SHA256SUMS_TEST**: sha cũ 6d975302… → mới **9041a677…**. Lý do: §0.4 bắt buộc sửa. Không đụng nav_local, nav_prism2, robot_ros, fastsim.

- **reset mỗi lượt:**
  - `vel_gain` = 0.5, `vel_gains` = [0.5, 0.5, 0.5];
  - `tracker` thay bằng `BlobTracker()` mới (bỏ cả tracks và _last_t);
  - `_ctrl`, `_ctrl_goal`, `_ctrl_kind` = None (RespModel nằm trong _ctrl nên cũng mới);
  - `v_world`, `nav_prefs` đặt lại;
  - nhiễu MPPI gieo theo [seed, lần, 11], như fastsim.
- **Đo thời gian:** bọc `_make_ctrl` và `_twist` trên đối tượng robot. Ghi từng `ctrl.step` (ms) và thời điểm từng lần gửi cmd_vel.
- **Monitor (10 Hz):**
  - ghi vị trí robot, MỌI người/xe, các vết người tracker xác nhận;
  - lần chạm người ĐẦU TIÊN và lần chạm vật đầu tiên;
  - tuổi lớn nhất của odom và LiDAR;
  - RTF đọc từ tiến trình con `gz topic -e .../stats`.
- **Bộ bài mới `--suite gztest`** (`--tasks`, `--group`):
  - chặn seed ≥ 100000 nếu không có `--allow-test`;
  - kiểm sha trước mỗi lượt (`--sha-file`);
  - thư mục ra phải rỗng; ghi meta.json;
  - xáo thứ tự cấu hình bằng Random(seed);
  - đổi bản đồ theo từng ô.
- **Đầu ra mới:** episodes.jsonl và cột mới trong trials.csv.

**Kiểm fastsim:** seed 0–20 (không lọc crowd) × 7 cấu hình × 5 ô = 735 dòng. Trùng từng dòng (bỏ cột cpu) 735/735, 0 EXC. Đã kiểm hai lần: sau bản sửa đầu và sau lần sửa tích hợp. fastsim không import eval_sim nên kết quả này là đúng như dự kiến.

**Một lần sửa tích hợp, do lỗi của chính tôi:**
- Lần chạy khói thứ nhất, Monitor đăng ký gz-transport /stats ngay trong tiến trình eval_sim. Nó tranh GIL với `Crowd._set` (lệnh request chặn 500 ms).
- Hậu quả ở bài có người: có bước ctrl.step mất 85 s, robot báo "mất cảm biến". Bài tĩnh không bị.
- Đã sửa bằng cách đọc RTF qua tiến trình con. Đã chạy lại identity (trùng) và chạy lại toàn bộ kiểm khói.
- Lần 1 hủy, lưu ở `results/GZ_smoke_try1_statsdeadlock/`.

## 2. Kiểm khói (chỉ DEV, 2 sim song song, 40/40 lượt, 0 lượt chạy lại)
File `audit/out/gztest_dev/group_000.sdf` đã có sẵn. Tôi sinh lại vào scratch để so: trùng từng byte với code hiện tại. Không sinh hay nạp seed TEST nào.

| | Kết quả | Số liệu |
|---|---|---|
| S1 | ĐẠT | 0 traceback. C1 = PRISM3/v3/RespModel, B1 = MPPI/v3/RespModel. sha_ok = 1 ở mọi lượt. |
| S2 | ĐẠT | C1: cmd_vel p50 0.101 s, p95 0.108 s; ctrl.step p50 7.5, p95 15.4, max 48 ms (n = 16343). B1: step p95 13.0 ms. |
| S3 | ĐẠT | RTF trung vị từng lượt thấp nhất 0.999, kể cả file 4 ô. |
| S4 | **TRƯỢT** | Bài có người: luôn xác nhận được ≥ 1 người (ít nhất 12 vết mỗi lượt). Bài tĩnh: có "người ma" tồn tại > 2 s ở 10/10 lượt C1 và 9/10 lượt B1. Trung bình 6 vết ma mỗi lượt, dài nhất 54 s (C1) và 144 s (B1); khoảng 30 % số nhịp có ma. |
| S5 | ĐẠT (vừa sát) | C1 bài tĩnh 7/10. Tổng office C1 10/16, B1 9/16. File 4 ô: C1 4/4, B1 3/4. |
| S6 | ĐẠT | Đủ log 40/40, nhịp log 0.103 s. Có 4 lần chạm người, tính được D1/D2 cả 4. |

**Về S4:**
- Đã kiểm, không phải lỗi đo do trùng id: vết ma xuất hiện liên tục ở chỗ gần như cố định.
- C1 kẹt ở `clutter:qua_khoi_so_le` (0/2) và `bep_xa` (1/2). B1 cũng kẹt ở `bep_xa` (0/2), và hai bên đều có vết ma ở gần chỗ kẹt.
- Nghi nguyên nhân (CHƯA kiểm chứng): thân CHAMP lắc làm tâm cụm điểm của vật tĩnh nhảy, cộng thêm việc robot_ros lấy pose tại lúc callback chứ không phải lúc quét.
- Tracker v3 chưa từng chạy trong Gazebo trước đây.

## 3. Đề nghị (anh quyết)
- **(a)** Vẫn chạy Gazebo TEST như đăng ký và ghi S4 vào mục 9 cùng phần hạn chế. Tracker dùng chung cho C1 và B1, nhưng ma tác động lên hai bộ lập kế hoạch khác nhau.
- **(b)** Hoặc cho ALGO điều tra tracker hoặc thời điểm lấy pose trong robot_ros. Nhưng làm vậy là đổi mã đã đóng băng: phải băm lại và fastsim sẽ không còn trùng.

## 4. Chạy Gazebo TEST (chỉ điều phối viên)
1. Cập nhật SHA256SUMS_TEST bằng `research/gz/SHA256SUMS_TEST.proposed` (chỉ khác dòng eval_sim). Nên băm thêm `research/gz/run_gz_groups.sh`.
2. Sinh thế giới TEST:
   `venv/bin/python audit/gen_gazebo_test.py --seeds 100000-101999 --crowd-only --max-worlds 680 --tiles 4 --allow-test --out results/gztest`
3. Chạy hai sim, mỗi sim một nửa số nhóm (chẵn/lẻ):
   ```
   SHAFILE=results/frozen_C1/SHA256SUMS_TEST bash research/gz/run_gz_groups.sh results/gztest results/GZ_TEST/s0 gzs0 41 "0 2 4 … 168" --allow-test
   SHAFILE=results/frozen_C1/SHA256SUMS_TEST bash research/gz/run_gz_groups.sh results/gztest results/GZ_TEST/s1 gzs1 42 "1 3 … 169" --allow-test
   ```
   Script kiểm sha trước mỗi nhóm và tự chạy lại tối đa 2 lần nếu sim hỏng. Đặt biến `CONFIGS` để thêm DRA* khi tới bước có cổng.
4. Thời gian đo được: một nhóm (4 thế giới × 2 cấu hình) mất 757 s kể cả 35 s bật sim. 170 nhóm trên 2 sim ≈ 18 giờ.
5. Không chạy fastsim nặng cùng lúc với Gazebo TEST, vì sẽ làm lệch RTF.

Không chấp nhận giấy phép mới nào; chỉ dùng Gazebo Harmonic và ROS đã cài sẵn. Không dùng sudo, không đụng 192.168.123.x. Một lệnh kill gộp bị auto-mode chặn; sau đó tôi chỉ dừng tiến trình theo PID và bằng `pipeline/kill_partition.py`. Hiện không còn sim hay job nào của tôi đang chạy.

Các file trong `/home/nhanhuynh/Documents/Go2_assitant/`:
- `eval_sim.py`
- `research/gz/run_smoke.sh`, `research/gz/run_gz_groups.sh`, `research/gz/smoke_check.py`, `research/gz/ident.sh`, `research/gz/ident_cmp.py`
- `research/gz/SHA256SUMS_TEST.proposed`, `research/gz/eval_sim.py.frozen`
- `results/GZ_smoke/smoke_check.txt` (kết quả S1–S6), `results/GZ_ident/compare.txt`, `results/GZ_ident/compare2.txt` (identity)

## 5. Chẩn đoán S4 (người ma): do thân lắc, không phải lệch thời gian → quyết định (a), Lệch #1 (PREREG §9)
Không đụng robot_ros.py / nav_local.py. Script: `research/gz/ghost_diag.py`, `research/gz/scan_probe.py`, `research/gz/eval_probe.py`; dữ liệu `results/GZ_ident/scanprobe/`.

**5.1 Phân tích offline 40 lượt smoke (RTF ≈ 1).**
- 944 vết ma; 83 % cách mặt vật tĩnh < 0,3 m (trung vị 0,00 m): tracker v3 coi chính vật tĩnh là người.
- Tỉ lệ ma mới phẳng theo |wz| (làm mượt 0,3 s):

| |wz| (rad/s) | 0–0,1 | 0,1–0,2 | 0,2–0,3 | 0,3–0,5 | 0,5–0,8 |
|---|---|---|---|---|---|
| ma mới/s | 0,24 | 0,27 | 0,27 | 0,28 | 0,25 |

- Đi thẳng với wz ≈ 0: khoảng 0,25/s; đứng yên: 0,13/s. Lệch thời gian sẽ cho ma tăng mạnh khi xoay; dữ liệu không thấy điều đó.

**5.2 Đo trong đường ROS, chỉ ghi log (1 sim, DEV).**
- `eval_probe.py` chạy eval_sim nguyên văn, chỉ bọc `sub.callback` của LiDAR/odom/IMU (ghi rồi gọi callback gốc). C1, `clutter:qua_khoi_so_le`.
- Lệch stamp odom được dùng − stamp quét: trung vị 0 ms, p95 20 ms, max 40 ms (452 quét). Ở |wz| ≈ 0,45 rad/s, 20 ms ≈ 9 mrad ≈ 3 cm ở 3 m. `scan_probe.py` (tiến trình nhẹ) cũng cho 0 / 20 ms.
- Nghiêng thân (IMU): |roll| p95 8,1°, |pitch| p95 5,9°. Ma chỉ xuất hiện khi nghiêng ≥ 2° (0–2°: 0 ma/173 quét; 2–4°: 3,5/100; > 6°: 3,8/100). |wz| lúc ma xuất hiện 0,44, bằng trung bình 0,46 (n = 9 ma).

**5.3 Phát lại offline cùng `_on_cloud` thật, cùng các lần quét.**

| Biến thể | Số ma | Tồn tại > 2 s | % quét có ma |
|---|---|---|---|
| A: pose + roll/pitch lúc callback (mã hiện tại) | 9 | 7 | 21 % |
| B: pose + roll/pitch nội suy tại stamp quét (bản sửa ứng viên) | 5 | 5 (dài nhất 13,7 s) | 24 % |
| B_flat: bỏ cân bằng IMU | 35 | 30 | 59 % |

Bản sửa theo stamp không làm hết ma; bỏ cân bằng thì tăng gấp nhiều lần. Kết luận: thân CHAMP lắc làm LiDAR 16 tia quét vào phần khác của vật, tâm cụm điểm nhảy; cân bằng IMU chỉ bù một phần. Đây là đặc tính vật lý/cảm biến của Gazebo, không phải lỗi topic/frame/đồng hồ, nên không có sửa tích hợp hợp lệ. Sửa thật phải đổi thuật toán tracker = bỏ đóng băng (b).

**5.4 Hạn chế.** Mục 5.2–5.3 chạy ở RTF ≈ 0,35–0,42 (fastsim TEST dùng 14 nhân); lệch tính bằng giờ sim, khi phát lại tracker chạy theo giờ sim (tương đương RTF 1). Bằng chứng độc lập ở RTF 1 là 5.1. Mẫu nghiêng nhỏ (9 ma).

**5.5 Ghi vào bài.** Trong Gazebo, tracker v3 (dùng chung cho C1 và B1) xác nhận vật tĩnh thành người > 2 s ở 10/10 (C1) và 9/10 (B1) lượt bài tĩnh của kiểm khói; nguyên nhân là thân CHAMP lắc. Kết quả Gazebo TEST phải đọc kèm giới hạn này.

---
*Ghi chú coordinator (24/11 ~13:50): agent GAZEBO bị harness chặn ghi .md; coordinator lưu nguyên văn theo cho phép chung của người dùng (23/11).*

## 6. Kết quả Gazebo TEST — coordinator, 25/11 13:50

Phân tích đúng PREREG_TEST §2 bằng `research/coord_gz_test_analyze.py`. Script được viết và băm **trước** khi xem dữ liệu (results/frozen_C1/SHA256SUMS_GZ_ANALYSIS).

**Kiểm tra quy trình**
- Đủ 680/680 thế giới, 1360 lượt chạy, không có lượt trùng, không phải bỏ thế giới nào.
- sha_ok đạt 1360/1360.
- RTF trung bình: trung vị 0,985, thấp nhất 0,841; không lượt nào dưới 0,8.

**Phép chính: C1 so với B1**

| Thuật toán | Thành công | Tỉ lệ (KTC 95 %) | Va chạm | Va chạm do robot gây ra |
|---|---|---|---|---|
| C1 | 549/680 | 80,7 % [77,6; 83,5] | 123 | 54 |
| B1 | 447/680 | 65,7 % [62,1; 69,2] | 211 | 89 |

- C1 hơn B1 **+15,0 điểm**.
- Cặp bất đồng: 149 thế giới chỉ C1 thành công, 47 thế giới chỉ B1 thành công.
- McNemar chính xác: p = 1,5e-13. **ĐẠT** ngưỡng đã đăng ký.

**So với fastsim trên cùng các thế giới (chỉ để mô tả)**
- Chênh C1−B1 ở fastsim: +8,4 điểm với champ_base, +12,2 điểm với champ2_base.
- Kết quả từng thế giới trùng nhau: 76,5 % với C1, 65,4 % với B1.

**DRA\* (có cổng, thăm dò)**
- Cổng mở vì C1 vs B1 đạt.
- Đang chạy trên 340 thế giới đầu (nhóm 0–84), dùng cùng sim gzs0/gzs1 như các lượt C1. Bắt đầu 13:46.

## 7. Vì sao Gazebo cho chênh C1−B1 lớn hơn fastsim? (coordinator, 25/11 ~14:50; PHÂN TÍCH SAU, THĂM DÒ, không đăng ký trước)

Script: `research/coord_gz_ghost_analysis.py`. Dữ liệu: episodes.jsonl, gồm tư thế robot, người thật và vết của tracker mỗi 0,1 s.

**Định nghĩa:**
- **Vết ma:** vết nằm cách mọi người thật > 1 m và cách robot ≤ 3 m.
- **Bỏ sót:** có người thật trong vòng 3 m mà không vết nào nằm trong 1 m quanh người đó.

**Kết quả:**
- **Mức tiếp xúc với ma như nhau ở hai bộ điều khiển:** tỉ lệ bước có ma ở gần là 7,4 % với C1 và 7,7 % với B1. Tỉ lệ bỏ sót người là 5,2 % và 5,7 %.
- **Chênh C1−B1 gần như không đổi theo mức ma** (chia thế giới thành 3 nhóm đều theo mức ma, tính trung bình cả hai lượt chạy):

  | nhóm | C1 | B1 | chênh |
  |---|---|---|---|
  | ít ma | 92,5 % | 78,0 % | +14,5 |
  | vừa | 77,1 % | 60,4 % | +16,7 |
  | nhiều ma | 72,6 % | 58,8 % | +13,7 |

  - Ngưỡng ma 0,7 m cho chênh +14,5 / +17,2 / +13,3; ngưỡng 1,5 m cho +12,3 / +19,4 / +13,3.
  - Ma làm cả hai bộ cùng tụt, nhưng không làm khoảng cách giữa hai bộ rộng ra.
  - Đây chỉ là liên hệ, chưa phải nhân quả, vì đông người thì cũng nhiều ma.
- **Chênh của Gazebo trừ chênh của fastsim trên cùng thế giới** (bootstrap ghép cặp, KTC 95 %):

  | mô hình fastsim | chênh thêm | KTC 95 % |
  |---|---|---|
  | champ (mô hình gốc) | +6,6 | [1,5; 11,8] |
  | champ2 (mô hình động học đã nhận dạng lại) | +2,8 | [−2,6; 8,2] — không khác có ý nghĩa |

  → Phần chênh thêm chủ yếu do mô hình CHAMP gốc trong fastsim lệch động học, và champ2 đã sửa được phần lớn.
- **Loại thất bại:**

  | loại | B1 Gazebo | B1 fastsim champ2 | C1 Gazebo | C1 fastsim champ2 |
  |---|---|---|---|---|
  | chạm người | 199 | 198 | 122 | 118 |
  | chạm vật tĩnh | 12 | 0 | 1 | — |
  | không chạm (kẹt/hết giờ) | 22 | 6 | 8 | 3 |

  - Số lần chạm người khớp nhau giữa Gazebo và fastsim champ2 ở cả hai bộ.
  - Phần dư thêm của B1 trong Gazebo nằm ở chạm vật tĩnh và kẹt.
  - Lượt B1 chạm vật tĩnh có mức ma cao nhất: 0,134, so với 0,068 ở lượt thành công. Nhưng chỉ có 12 lượt, chưa kết luận được.
- **Kết luận thăm dò:** ma không giải thích chênh lớn hơn. Mô hình champ2 giải thích phần lớn; phần dư +2,8 không khác 0 có ý nghĩa. Đã cập nhật MANUSCRIPT §6.10.

## 8. Kiểm toàn vẹn: lỗi tracker `KeyError('x')` lúc khởi động (coordinator, 25/11 ~14:25; phân tích làm sau khi đã có kết quả)

**Lỗi là gì.** Đây chính là lỗi (a) trong REPORT_REALPREP.
- Trước lượt đầu của mỗi lần gọi eval_sim, tracker còn giữ vết kiểu v2 do bộ điều khiển mặc định tạo ra.
- Khi chuyển sang `~t3`, mỗi lần quét đều ném lỗi `KeyError('x')`: khoảng 20–22 lần quét bản đồ, tức chừng 4 s đầu của lượt đó.
- Trong khoảng ấy, bản đồ và tracker không được cập nhật.

**Gazebo TEST bị ảnh hưởng thế nào.** Có 75/1360 lượt dính lỗi, toàn là lượt đầu của một lần gọi eval.

| Cấu hình | Lượt dính lỗi: thành công | Lượt không dính: thành công |
|---|---|---|
| C1 | 34 lượt, 91,2 % | 80,2 % |
| B1 | 41 lượt, 63,4 % | 65,9 % |

- Không thấy lượt dính lỗi bị kém đi một cách có hệ thống.
- Bỏ mọi thế giới có lượt dính lỗi, phép chính vẫn giữ: N = 605; C1 79,7 %, B1 65,1 % (chênh +14,6 điểm); cặp lệch 129/41; McNemar p = 8,5e-12.

**DRA\* đang chạy.** Lỗi cũng xảy ra: lúc kiểm có 5/36 lượt dính. Khi chạy xong phải kiểm lại bằng `research/coord_gz_keyerror_check.py results/GZ_TEST_DRA x`, kèm phân tích độ nhạy bỏ các thế giới có lượt dính lỗi.

**Lỗi hạ tầng riêng lẻ.** Ở DRA\* g9, lần chạy đầu bị `TypeError` trong `reset()` vì odom chưa có. Runner đã tự chạy lại theo PREREG §5.

**Mã nguồn.** Không sửa vì là mã đóng băng. Trên chó thật, `deploy/real_trial.py` đã né lỗi này.

## 9. DRA* trong Gazebo (cổng mở, THĂM DÒ): coordinator, 25/11 18:25

Chạy trên 340 thế giới đầu (nhóm 0–84), mỗi thế giới 1 lượt DRA*. Phân tích bằng script đã băm, gộp thư mục GZ_TEST và GZ_TEST_DRA.

**Kết quả trên 340 thế giới:**

| Cấu hình | Thành công | Va chạm | at_fault |
|---|---|---|---|
| C1 | 282/340 = 82,9 % [78,6; 86,6] | 54 | 21 |
| DRA* | 238/340 = 70,0 % [64,9; 74,6] | 91 | 36 |

- Cặp bất đồng: 66 thế giới chỉ C1 thành công, 22 thế giới chỉ DRA* thành công.
- Kiểm định McNemar chính xác: p = 2,9e-6.

**Độ nhạy (bỏ bớt lượt nghi lỗi hạ tầng).** Bỏ hai loại lượt:
- 44 thế giới dính lỗi KeyError của tracker;
- 4 lượt DRA* có rtf_mean < 0,8 kéo dài 29–50 s (seed 100059, 100060, 100063, 100064). Theo §5 đây là lỗi hạ tầng lẽ ra phải chạy lại, nhưng runner không kiểm RTF nên không tự chạy lại.

Còn lại N = 296: C1 81,4 %, DRA* 70,3 %; cặp bất đồng 54/21; p = 1,8e-4.

**So với fastsim trên cùng 340 thế giới.** Chênh C1−DRA* trong fastsim chỉ +2,1 (champ) và +5,0 (champ2). Tức là DRA* tụt mạnh khi sang Gazebo (khoảng 80 % → 70 %), còn C1 thì không.

**Cảnh báo về cách chạy.** DRA* chạy riêng, sau C1/B1 khoảng 5 giờ, và luôn là lượt duy nhất trong mỗi lần bật sim. Vì vậy đang kiểm "trôi điều kiện chạy": chạy lại C1 trên nhóm 0–19 (80 thế giới), lưu ở results/GZ_DRIFT_C1.

**Tình trạng:** đây là kết quả thăm dò (PREREG §2), không thuộc họ chính.

### 9b. Kiểm tra trôi điều kiện chạy (coordinator, 19:30, thăm dò)
- Chạy lại C1 trên nhóm 0–19 (80 thế giới) ngay sau khi DRA* chạy xong, đặt ở results/GZ_DRIFT_C1.
  - Kết quả: C1 chạy lại thành công 60/80, so với 58/80 ở lần chạy gốc. Số cặp bất đồng 14/16, p = 0,86, tức **không thấy C1 bị trôi**.
  - Kết quả từng thế giới chỉ trùng 50/80, do tính hỗn loạn của mô phỏng.
- Trên cùng 80 thế giới này: DRA* 53/80, B1 48/80. C1 (lần chạy lại) so với DRA*: 17/10, p = 0,25 (n nhỏ).
- RTF: các lượt DRA* có trung vị 0,933, so với 0,967 của cả hai lần chạy C1. Nguyên nhân là tác vụ HM95 chạy song song trên 4 lõi.
  - Chia các lượt DRA* thành ba nhóm theo RTF, tỉ lệ thành công là 68,1 / 67,3 / 74,6 % (từ RTF thấp đến cao).
  - Nghĩa là tải máy có thể giải thích vài điểm, nhưng không giải thích hết khoảng cách so với C1 (khoảng 83 %).
- Bước tính lệnh p95: DRA* 16,1 ms, C1 14,5 ms. cmd_dt p95 ≈ 0,11 s ở cả hai, tức lệnh vẫn gửi đúng nhịp.
- Đã cập nhật MANUSCRIPT §6.10 và T11 (make_all: 119 kiểm, 0 lệch).
