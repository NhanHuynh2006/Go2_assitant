# ĐĂNG KÝ TRƯỚC — TEST cho thiết kế đóng băng C1 (AUDIT, 24/11)

Thay cho audit/PREREG_DRAFT.md. Có hiệu lực khi điều phối viên ghi sha256 của file này vào research/LOG.csv TRƯỚC khi sinh hay chạy
bất kỳ seed >= 100000 nào. Sau đó không sửa; mọi lệch ghi vào mục 9.
Cấu hình: đúng 7 cấu hình của research/FROZEN.md (C1, B1, PGIF*, DRA*, B0, dwa, log_mppi), mã khớp results/frozen_C1/SHA256SUMS.

## 0. Việc bắt buộc TRƯỚC TEST (phải xong và ghi LOG)
1. Thêm vào SHA256SUMS: `research/algo_fast/fast.so` (đang được nạp qua GOVOICE_FAST_SO nhưng không băm), `eval_sim.py`,
   `audit/gen_gazebo_test.py`, file này. Đã kiểm: C1 champ2, seed DEV 0–6, có và không có fast.so cho kết quả trùng từng dòng.
2. Kiểm sha256 trước MỖI ô và mỗi lần nạp thế giới Gazebo, không chỉ một lần đầu script (coord_val.sh hiện chỉ kiểm một lần, trong khi
   mỗi ô mở tiến trình mới đọc lại mã từ đĩa). Cách chắc nhất: chạy từ bản giải nén của code.tgz vào thư mục chỉ đọc.
3. Thư mục ra phải rỗng lúc bắt đầu (fastsim bỏ qua dòng đã có nên có thể trộn lượt của mã cũ); meta.json ghi thêm sha256 của mã.
4. Gazebo: `eval_sim.reset` đặt lại `vel_gain`, `vel_gains`, `tracker.tracks`, `_ctrl` mỗi lượt. Monitor ghi vị trí MỌI người 10 Hz và
   thời điểm chạm ĐẦU TIÊN (để tính D1/D2). Đây là sửa hạ tầng đánh giá, không đụng thuật toán: chứng minh bằng fastsim bit-identical (mục 4).

## 1. fastsim TEST — họ chính (phép kết luận của bài)
- Thế giới: 1000 thế giới có người ĐẦU TIÊN tính từ seed 100000 (`--suite gen --crowd-only`, khoảng 1400 seed), 1 lượt, 5 ô như VAL:
  champ/champ2/go2 × base, champ2/go2 × helb. Seed ngoài DEV/VAL/xác nhận (đã kiểm: không thư mục nào ngoài VAL_* có seed >= 2000).
- Chỉ số: `success` (tới đích, không chạm gì). Với mỗi thế giới w và baseline X: d_w = trung bình 5 ô của (C1 − X).
- Kiểm định: hoán vị dấu theo thế giới, 2 phía, 200 000 lần; KTC 95 % bootstrap theo thế giới (10 000). Họ chính Holm 3:
  C1 vs B1, C1 vs PGIF*, C1 vs DRA*. "C1 hơn X" chỉ khi p_Holm < 0,05 và d̄ > 0.
- Sức mạnh (audit/c1_power.py, sd theo thế giới gộp algo_W*+algo_Y*: B1 0,202, PGIF 0,202, DRA 0,183):

| so sánh | chênh giả định | n cho 80 % / 90 %, α 0,05 | α 0,0167 (Holm bước 1) |
|---|---|---|---|
| C1 − B1 | +6,5 | 76 / 102 | 101 / 130 |
| C1 − PGIF* | +5,2 | 119 / 159 | 159 / 204 |
| C1 − DRA* | +3,0 | 293 / 391 | 390 / 503 |
| C1 − DRA* (co lại) | +2,0 | 658 / 880 | 877 / 1131 |

  n = 1000 vẫn đủ khi chênh thật với DRA* co về +2 (≈ 93 % ở α 0,05; ≈ 85 % ở 0,0167). Bootstrap trên dữ liệu vòng 2+3 cho n = 600: 99 % / 95 %.
- Khối lượng: 7 × 5 × 1000 = 35 000 lượt. Tốc độ VAL đo được ≈ 100 lượt/phút với 14 tiến trình, tức khoảng 6 giờ.
- Phụ (báo cáo, không kết luận): từng ô McNemar chính xác (Holm trong 15); vs B0, dwa, log_mppi; loại hỏng (người/vật/kẹt/hết giờ); thời gian;
  D1/D2 at_fault. Ô helb báo riêng: ở vòng 2–3, C1 ≈ PGIF*/DRA*.

## 2. Gazebo TEST — họ riêng (độ vững ngoài fastsim)
- Thế giới: `audit/gen_gazebo_test.py --seeds 100000-101999 --crowd-only --max-worlds 680 --tiles 4 --allow-test` (680 thế giới có người
  đầu tiên = phần đầu của bộ fastsim TEST, để so theo từng thế giới). Ô duy nhất là Gazebo CHAMP với người movers (base).
- Chính trong họ Gazebo: C1 vs B1, McNemar chính xác 2 phía, α 0,05. DRA* chỉ được kiểm (α 0,05, có cổng: CHỈ khi C1 vs B1 đạt), và
  chỉ trên 340 thế giới đầu: mức đó coi là thăm dò (sức mạnh cho +4 khoảng 30 %).
- Sức mạnh: fastsim champ_base cho C1 − B1 +5,5 / +9,0, tỉ lệ cặp bất đồng 0,18–0,21. Gazebo ồn hơn nên giả định d = 0,30, chênh +6:
  680 cặp cho 80 % (d = 0,20: 462). 400 cặp chỉ có khoảng 60 %.
- Thời gian: 1360 lượt / 76 lượt/giờ ≈ 18 giờ, cộng 170 lần nạp file 4 ô (chưa đo; ước 1–2 phút mỗi lần, 2 sim) ≈ 2–3 giờ, tổng ≈ 20–21 giờ.
  Thêm DRA* trên 340 thế giới: +340 lượt ≈ 4,5 giờ.
- Thứ tự: thế giới theo seed tăng dần; trong mỗi thế giới xáo thứ tự cấu hình bằng `random.Random(seed)`; cả cặp chạy trên CÙNG một sim.

## 3. Isaac (tùy chọn, họ riêng, thăm dò)
- rough + `--noise`, 8 robot lockstep, bản server v3 (pilot §10 không phát lại được từng lượt). 600 thế giới đầu của bộ TEST; cấu hình C1, B1, PGIF*, DRA*.
- Khoảng 4 giây sim mỗi giây thật × 8 robot, lượt ≈ 60 s sim: khoảng 1900 lượt/giờ, nên 2400 lượt mất 1,5–3 giờ cả nạp.
- Ngã = hỏng; tỉ lệ ngã báo riêng theo cấu hình. Không dùng `~cs`. Kiểm: McNemar, Holm 3. Pilot cho C1 − B1 +8, d ≈ 0,32: cần ~390 cặp,
  nên 600 đủ cho B1; DRA* là thăm dò.

## 4. Kiểm khói Gazebo BẮT BUỘC (C1 chưa từng chạy trong Gazebo). Chỉ DEV, không dùng thế giới TEST
- Bộ: `eval_sim.py --suite office` (8 bài DEV đã dùng) × 2 lần × {C1, B1} = 32 lượt, cộng 1 file DEV 4 ô (`audit/out/gztest_dev/group_000.sdf`,
  seed 0–20) × {C1, B1} = 8 lượt. Khoảng 0,5–1 giờ trên 2 sim.
- ĐẠT khi đủ cả 6 điều:
  S1. 0 ngoại lệ/traceback. Log in tên lớp bộ điều khiển (PRISM3), tracker mode v3, `RespModel` bật, sha256 khớp.
  S2. Vòng điều khiển: chu kỳ `cmd_vel` trung vị <= 0,11 s, p95 <= 0,15 s; `ctrl.step` của C1 p95 <= 80 ms (ghi thời gian từng bước).
  S3. RTF trung vị >= 0,9 trong mỗi lượt, cả với file 4 ô.
  S4. Ở mỗi bài có người, tracker v3 xác nhận >= 1 người. Ở bài tĩnh, không có "người" xác nhận tồn tại > 2 s.
  S5. Kiểm sàn (không phải chỉnh): C1 ở bài tĩnh >= 7/10, và tổng C1 >= tổng B1 − 4 trên 16 cặp.
  S6. Log mới của Monitor (mọi người 10 Hz, chạm đầu) có đủ và D1/D2 tính được.
- TRƯỢT: chỉ được sửa lỗi TÍCH HỢP (topic, frame, đồng hồ, tham số ROS), không đổi tham số thuật toán. Mỗi lần sửa phải: chạy lại fastsim DEV
  seed 0–20 × 7 cấu hình × 5 ô và trùng từng dòng với trước khi sửa; băm lại; ghi lệch ở mục 9; rồi chạy lại toàn bộ kiểm khói.
  Nếu S5 trượt mà không tìm được lỗi tích hợp: vẫn chạy TEST như đăng ký, và báo cáo kết quả kiểm khói.

## 5. Quy tắc dừng, loại lượt
- Cỡ mẫu cố định (fastsim 1000, Gazebo 680, Isaac 600). Không có phân tích giữa chừng theo cấu hình. Sau 5 % đầu, chỉ kiểm hạ tầng:
  số lỗi kỹ thuật và tốc độ, không xem tỉ lệ theo cấu hình.
- fastsim tất định. EXC ở MỌI cấu hình của một (thế giới, ô) là lỗi hạ tầng: bỏ thế giới đó khỏi mọi ô và mọi cấu hình, lấy thế giới có người kế tiếp.
  EXC chỉ ở một số cấu hình: tính là THẤT BẠI của cấu hình đó (bộ điều khiển văng là hỏng). Báo số lượng. Nếu > 1 % thế giới bị loại thì
  báo thêm phân tích "EXC = thất bại cho mọi cấu hình".
- Gazebo/Isaac: lỗi kỹ thuật xác định bằng log, không bằng kết quả (sim sập, mất odom hoặc LiDAR > 2 s, RTF < 0,8 quá 10 s, set_pose lỗi,
  sha256 lệch) -> chạy lại tối đa 2 lần. Vẫn hỏng thì bỏ thế giới cho CẢ cặp. Bộ điều khiển văng, kẹt, hết giờ, chạm, ngã = thất bại.
- Hết giờ Gazebo trước 680: dừng theo THỜI GIAN, không theo kết quả; phân tích các thế giới đã đủ cặp, báo N và sức mạnh thật.
  Đã bắt đầu một thế giới thì chạy đủ các cấu hình của thế giới đó.

## 6. Khi VAL và TEST, hoặc fastsim và Gazebo, không khớp
- TEST là kết quả khẳng định. VAL chỉ là bằng chứng đi kèm; không gộp VAL + TEST làm phép chính. Được báo một bảng gộp mô tả, có ghi rõ.
- VAL đạt, TEST không: tiêu đề là "không được xác nhận trên TEST", báo cả hai cùng KTC. Không chạy lại TEST, không thêm seed.
- VAL không đạt, TEST đạt: báo TEST kèm cảnh báo "chỉ 1/2 bộ kín đạt". Không nói "vững".
- Dấu ngược nhau: báo dị biệt; không chọn bộ có lợi.
- fastsim đạt, Gazebo không: kết luận giới hạn ở fastsim; nêu Gazebo là giới hạn chuyển giao. Gazebo đạt, fastsim không: báo cả hai.
- Ô helb (hoặc go2) ngược dấu với gộp: phải viết vào tóm tắt bài.

## 7. Công bố kèm (không đổi kiểm định)
- Ngân sách chỉnh không cân (LOG.csv tới 24/11): họ p3 60 cấu hình / 31 nghìn lượt, trên 5 ô và khoảng 500 thế giới; mppi~t3 21 cấu hình;
  PGIF* 35 và DRA* 35, chỉ ở ô champ base, seed 0–149. Vi phạm quy tắc 3 của PROTOCOL ("baseline >= đề xuất"), thiên lệch có lợi cho C1.
  Bài phải ghi rõ. Lượt TEST không sửa được điểm này.
- Phần lợi so với B0 chủ yếu do tracker v3 dùng chung: báo tách riêng.

## 8. Phân tích
Một script, viết và chạy thử trên VAL trước khi mở TEST, băm sha256 ở mục 0. Thứ tự: họ chính fastsim -> Gazebo -> Isaac -> phụ.

## 9. Lệch so với đăng ký
(để trống)

### Lệch #1 (coordinator, 24/11 14:40, TRƯỚC khi sinh/nạp bất kỳ thế giới Gazebo TEST nào)
- Kiểm khói Gazebo: S1, S2, S3, S5, S6 đạt; **S4 trượt** (vết "người" ma > 2 s ở bài tĩnh: 10/10 lượt C1, 9/10 B1).
- Chẩn đoán (REPORT_GAZEBO + tin GAZEBO 14:30): 83 % vết ma nằm sát mặt vật tĩnh; tỉ lệ ma phẳng theo |wz| (không do lệch thời gian); lệch stamp quét–odom p95 20 ms; ma chỉ xuất hiện khi thân nghiêng ≥ 2° (CHAMP |roll| p95 8°); phát lại với pose nội suy tại stamp không hết ma. → nguyên nhân là thân lắc của CHAMP trong Gazebo (vật lý/cảm biến), KHÔNG phải lỗi tích hợp.
- Theo §4 (không có lỗi tích hợp để sửa): **chạy Gazebo TEST đúng như đăng ký**, không đổi mã đóng băng; S4 báo trong phần hạn chế. Đã băm eval_sim.py mới (9041a677…) và run_gz_groups.sh vào SHA256SUMS_TEST.
- Gazebo TEST bắt đầu sau khi fastsim TEST xong (không chạy song song để giữ RTF).

### Bổ sung #2 (coordinator, 24/11 16:45, TRƯỚC khi chạy) — nhánh VẬT TĨNH (phụ, báo cáo; không thuộc họ chính)
- Lý do: TEST/VAL dùng `--crowd-only` (thế giới có người, vẫn có vật tĩnh) nên chưa có kết quả riêng cho thế giới CHỈ có vật tĩnh.
- Thế giới: mọi seed 100000–101386 KHÔNG có người (phần bù của bộ TEST chính), 3 ô champ/champ2/go2 (mô hình người không áp dụng), 1 lượt.
- Cấu hình: C1, B1, PGIF*, DRA*, B0, dwa~t3~nl, log_mppi~t3~nl. Chạy từ bản chụp chỉ-đọc, sau fastsim TEST chính, trước Gazebo TEST.
- Chỉ số: tới đích không va; va vật; kẹt; thời gian. Kiểm định không-kém C1 vs B1 (KTC 95 % bootstrap theo thế giới, ngưỡng −2 điểm) — câu hỏi: lớp né người có làm hỏng né vật tĩnh không.

### Lệch #3 (coordinator, 25/11 ~00:10, TRƯỚC khi chạy nhánh Isaac)
- Theo yêu cầu người dùng (chạy song song mọi thứ không cần chó thật), nhánh Isaac (§3) chạy NGAY, song song với Gazebo TEST, thay vì sau đó.
- Để không làm lệch RTF của Gazebo: Isaac dùng **4 robot** (thay vì 8), nice 19, ghim CPU ở nhân 10–15; theo dõi RTF Gazebo, nếu trung vị RTF lượt Gazebo < 0.9 thì tạm dừng Isaac. Đổi N chỉ đổi kết quả từng lượt do hỗn loạn (REPORT_ISAAC §11), không đổi phân bố.
- Mã Isaac được băm: results/frozen_C1/SHA256SUMS_ISAAC (isaac_sim.py, body_server.py, go2_env.py + toàn bộ SHA256SUMS_TEST).
- Bổ sung Lệch #3 (25/11 00:30, trước khi có kết quả Isaac nào): khi Gazebo TEST xong, các lô Isaac còn lại chạy với 8 robot (chỉ đổi thông lượng; mỗi lượt là một thế giới độc lập, phân bố kết quả không đổi). Ghi rõ lượt nào chạy với N nào.

### Lệch #4 (coordinator, 25/11 00:35; ghi SAU khi nhánh Isaac đã bắt đầu — 50 lượt — nhưng chỉ là chi tiết kỹ thuật đã có trước lượt đầu, chưa ai xem kết quả theo cấu hình)
- isaac_sim.py đã băm có assert chỉ cho seed DEV/VAL nên không tự chạy seed TEST. Không sửa tệp băm; dùng vỏ mỏng isaac_val/test_arm.py (gọi main() với --seeds 0-0 và thay hàm chọn thế giới bằng danh sách cố định isaac_val/test_worlds.json: 600 thế giới có người, từ 100000, trùng các ô fastsim TEST). Coordinator đã đọc vỏ (15 dòng): không đổi logic nào khác.
- Script phân tích isaac_val/test_stats.py viết TRƯỚC khi có kết quả; băm cùng vỏ và danh sách thế giới trong results/frozen_C1/SHA256SUMS_ISAAC_TEST.
- Bộ canh RTF dùng cả rtf_med và rtf_mean (< 0.9 ⇒ tạm dừng), chặt hơn §Lệch #3.
- Sửa ước tính §3: "1,5–3 giờ" sai (4 s mô phỏng/s là thông lượng gộp của 8 robot); thực đo ~2,9 lượt/phút ở N=4 ⇒ ~13–14 giờ cho 2400 lượt.
