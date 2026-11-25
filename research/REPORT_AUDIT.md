# REPORT_AUDIT — phản biện độc lập (22–23/11/2026)

Làm gì: soi code, phân tích 960 lượt Gazebo đã có, chạy 2.720 lượt fastsim DEV (seed 150–~300, 3 tiến trình) trên BẢN CHỤP code 23:01 22/11
(`audit/snap`, vì ALGO sửa code song song). Bộ chạy `audit/fs_audit.py` khớp từng bit với fastsim gốc ở cấu hình base (kiểm seed 0–1).
Không chạy Gazebo, không chạy/xem seed >= 1000. Dòng LOG của AUDIT nằm ở `audit/LOG_AUDIT_rows.csv`: lệnh nối vào research/LOG.csv bị bộ kiểm quyền chặn, điều phối viên cần tự nối. Mọi phép thử dưới đây: McNemar chính xác, p CHƯA hiệu chỉnh trừ khi ghi Holm.

## 1. Lỗi/khuyết đã tái hiện (nghiêm trọng trước)

| # | Phát hiện | Số / script |
|---|---|---|
| 1 | **p2+turn không hơn baseline chỉnh; lợi thế trên dev3 là do chọn max.** DEV mới n = 100: p2+turn 57, mppi:ppl=32 57 (+16/-16, p = 1), mppi 50 (p2+turn +19/-12, p = 0,28). Nếu 19 cấu hình dev3 bằng nhau, cấu hình cao nhất vẫn hơn trung bình +6,4 điểm (p95 +9,4); quan sát +8,1 | a10, a6 |
| 2 | **Dữ liệu Gazebo có người không chứa thứ hạng.** Giữa 18 cấu hình họ MPPI, 3 bài có người: phương sai thật ước lượng 0 (p = 0,875), tin cậy chia đôi -0,23. Khác biệt thật chỉ có ở 5 bài TĨNH (p < 0,001, sd 9 điểm) | a5 |
| 3 | **5 "lần lặp" Gazebo là giả lặp.** Crowd(seed=21/22/23) cố định: người số 0 trùng nhau 0–6 cm suốt 45 s ở kho_xe_day và 30 s ở van_phong_dong (sảnh 8 người: lệch 0,33 m ở 10 s, 2,3 m từ 20 s); mải điện thoại chỉ 3/18 người, kho 0/4. Ghép McNemar theo "lần" vô ích (bất đồng 0,45; ghép ngẫu nhiên 0,47). Cỡ mẫu thật về người gần 3 kịch bản, không phải 15/cấu hình | a2, a6 |
| 4 | **at_fault gần như luôn bật khi robot đi.** P(abs(wz) 0,1 s > 0,3) = 63 % lúc đi ở bài không người (đi thẳng: 61 %). 102 lượt "lỗi robot": 44 chỉ vì wz, 24/44 (55 %) mất khi lấy TB 0,5 s. Ghi tại lúc chạm SÂU nhất (trễ median 0,1 s, p90 0,42 s sau chạm đầu) | a3, a9 |
| 5 | **at_fault fastsim và Gazebo là hai đại lượng khác nhau**: fastsim dùng vận tốc lệnh đã lọc, không có lắc thân. So "ng_robot" giữa hai nơi là sai | đọc code + a9 |
| 6 | Tham số bị BỎ QUA im lặng: `prism:ppl_len` (0,3 viết cứng), `prism:obs` (ghi đè mỗi bước): lệnh ra y hệt. `p2+tunr`, `p2-Evade` chạy như `p2`. `rl:ppl=32` không tác dụng. `mppi:T=`, `sigma=`, `p2@..+turn` văng lỗi. Bản chụp 23:01; ALGO đã đổi set_param, cần kiểm lại | b1 |
| 7 | BlobTracker v1/v2: mất 1–2 lần quét rồi thấy lại thì chia dt 1 chu kỳ -> 0,9 m/s thành 1,24 / 1,74; 1,2 thành 1,9 / 2,4. Chung mọi bộ, không bất công | b2 |
| 8 | Thư mục kết quả không ghi `--oracle/--regime`/mã code. `ceil1` chạy `--oracle` nhưng cột, tên cấu hình giống dev3; mppi:ppl=32 "64 -> 75/101" là do oracle. Tôi đã suýt báo nhầm thành lỗi tương thích; chạy lại seed 1–2 khớp cả hai chế độ, và mppi/A* bản hiện tại khớp bản chụp 60/60, 30/30 | b4 |
| 9 | `eval_sim.reset` không đặt lại vel_gain, vel_gains, tracker giữa các lượt (đọc code; mức ảnh hưởng CHƯA đo) | — |
| 10 | Khác bộ: movers.Crowd (Gazebo) bỏ trụ/cọc, không chặn người sinh sát robot; fastsim có cả hai | đọc code |

Nghi ngờ nhưng KHÔNG phải vấn đề lớn (đã đo): mô hình một hệ số/trục của mppi (cấp vel_gains từng trục: 54 so với 50, p = 0,57; ppl32 59 so với 57, p = 0,86);
lambda bị phạt va chạm lấn át chỉ 2–3 % bước, 5–10 % giây cuối (sửa lambda 47 so với 50, p = 0,61); people_cost của p2 = MPPI (lệch 1e-12);
fastsim tất định (670/670 cặp trùng khít giữa dev1/dev2/dev3); không trùng seed DEV/VAL/TEST; chu kỳ Monitor 0,104 s (sai 4 %).

## 2. fastsim so với Gazebo
- Nội bộ họ MPPI/DWA (7 cấu hình): Spearman 0,83 (p = 0,02), KTC bootstrap [-0,56; 0,87]. Nếu fastsim HOÀN HẢO và sd thật 5–6 điểm,
  xác suất thấy p < 0,05 với 7 cấu hình chỉ 13 %, với 18 cấu hình 37 %. **Không đủ sức kết luận theo cả hai hướng.** Con số 0,89 chủ yếu từ tách RL/pp.
- Kiểu hỏng khác hẳn. Có người: Gazebo chạm người 42 %, kẹt 10 %, va tĩnh 6 %, hết giờ 2 %; fastsim chạm người 70 %, còn lại 0. Tĩnh (không tính noprior):
  Gazebo đạt 88 % (kẹt 7, va 3, giờ 2), fastsim 98 %. Câu "toàn bộ khó khăn là NGƯỜI" là tính chất của gen_world, không phải của Gazebo.
- Lắc thân fastsim hơi quá: sd wz 0,73 so với 0,59 rad/s; quãng đường 0,1 s/0,5 s = 1,28 so với 1,13. Tốc độ người khớp (0,79–0,86 m/s, lệch 0–3 %).
- 56 % lần chạm người Gazebo nông hơn 5 cm (median 4,4 cm), cỡ lắc thân: thành/bại nhạy với tiêu chí.

## 3. Độ nhạy (n = 40, cùng thế giới; SE hiệu ~8 điểm, chỉ thấy được đổi > 16 điểm)
Hiệu p2+turn - mppi:ppl=32 (điểm, ±95 %): base -15±15, real(cũ) -10±17, trễ lệnh 0,2 s -2±18, mải đt 60 % -5±16, 0 % 0±17, trễ thấy +2±15,
người nhanh x1,3 +5±20, **đông +3 người +20±20**, không lắc -5±19, **thân thật -20±14**, **bỏ chạm < 5 cm -18±16**, chậm x0,7 -5±17.
mppi:ppl=32 hơn mppi (điểm ước lượng) ở 10/12 điều kiện; người nhanh: 0; đông: -8. Kiểm tương tác: chỉ mật độ gần ngưỡng (đổi +35 điểm, p = 0,0026, Holm 22 phép 0,058).
Lưu ý base của 40 thế giới đầu (-15) là nửa mẫu; đủ 100 là 0. => mật độ là giả định đáng ngờ nhất; tiêu chí va chạm đổi mức tuyệt đối mạnh (mppi 42 -> 65).

## 4. Câu hỏi (a): hệ số người
n = 100: Moussaïd 2009 (A 4,5, gamma 0,35, n 2, n' 3, lambda 2): 65 / 71 / 71 (mppi / ppl32 / p2+turn); **không đổi hạng** (p2t-ppl32 +12/-12, p = 1).
Helbing biên độ 7 (tức 2,1/0,3): 62 / 66 / **80**: p2+turn hơn ppl32 +23/-9 (p = 0,02), tương tác so với base +14 điểm, z = 1,80, p = 0,072 (chưa đủ; Moussaïd: 0 điểm, p = 1).
Kết luận: mức tuyệt đối đổi 8–23 điểm và khoảng cách giữa thuật toán PHỤ THUỘC người né robot mạnh cỡ nào (ở helb 100 % lần chạm là người mải điện thoại).
Nên có mô hình thứ hai (Moussaïd) bắt buộc ở VAL; không viết "theo Moussaïd/PedSim" cho movers.py. Công thức Moussaïd tôi viết theo trí nhớ, tham số khớp
REPORT_OSS/lightsfm trừ biên độ (4,5 so với 2,1); chưa đối chiếu bản PDF. Lực tường, mục tiêu, tiếp xúc và nhiễu giữ nguyên như movers.

## 5. Câu hỏi (b): mức trần
n = 50, cảm biến oracle, cost mppi:ppl=32: robot đứng yên khi mô phỏng trước (= oracle_ctrl) 41/50; robot theo kế hoạch 41/50 (+2/-2); theo kế hoạch + rng khác 42/50;
trạng thái thật + vận tốc không đổi 33/50 (so với trần +2/-10, p = 0,039). Sai số dự đoán của bản đứng yên, người < 2 m, 2 s: 0,04 m (người né), 0,00 (mải đt); vận tốc không đổi: 0,51 m.
=> **Giả định đứng yên không làm trần cao/thấp đáng kể, biết trước rng cũng không.** Trần cao vì BIẾT Ý ĐỊNH (điểm đến, đường A*, v0): không bộ dự đoán nào có.
Nó là cận cho "MPPI này + biết ý định", không phải cận tối ưu (còn 8 lần chạm, đều người mải đt). Khoảng có thể giành bằng dự đoán quỹ đạo nằm giữa 66 % và 82 %, thêm phần tracker.
Bất định ±12 điểm; không so trực tiếp 89 % của ceil1 (seed khác).

## 6. at_fault đề xuất
D1: TB 0,5 s trước CHẠM ĐẦU, quỹ đạo làm mượt 0,5 s, vận tốc điểm thân gần người nhất (gồm xoay) theo hướng tới người > 0,1 m/s. D2 (phản thực tế): robot đứng yên từ 1 s trước có bị chạm?
n = 269 chạm fastsim: hiện tại (D0) đổi nhãn khi vẽ lại lắc thân 31 %, D05 23 %, D1 15 %, D2 3 %; báo oan khi không lắc = 0: 72 / 27 / 10 / 2 %. Tỉ lệ "lỗi robot": D0 87 %, D1 55 %, D2 28 %.
D1 và D2 chỉ đồng thuận 58 %: hai khái niệm khác nhau (robot ép tới so với robot gây ra), phải báo cả hai. Lúc chạm robot góp 0,09 m/s, người 0,58 m/s.
Gazebo chỉ áp được cho 26 lượt chạm người số 0. Cần Monitor ghi mọi người 10 Hz và thời điểm chạm đầu. Chỉ số chính phải là mọi va chạm, không phụ thuộc at_fault.

## 7. Sức mạnh và kế hoạch TEST: `audit/PREREG_DRAFT.md`
+10 điểm: 217 cặp (d = 0,26) đến 331 (d = 0,40), 393 (d = 0,48). +5: 851 / 1292 / 1543. DEV n = 101: 40 % cho +10, 11 % cho +5. Gazebo 15 lượt có người/cấu hình: 3 %.
Gazebo 340 thế giới x 2 cấu hình = 680 lượt (~9 giờ) là bắt buộc; +5 điểm ở Gazebo không khả thi (~34 giờ). Đủ 5 tổ hợp gợi ý RL và quy tắc chọn bản đơn giản nhất.

## 8. Bộ sinh TEST Gazebo: `audit/gen_gazebo_test.py`, kiểm `audit/check_gazebo_test.py`
Thử seed DEV 0–20 và 0–120 (82 thế giới có người): 0 lỗi, `gz sdf -k` Valid (2 file đầu), tên model đủ, hộp khớp gen_world < 1 mm, người cách robot > 1,2 m (bằng movers.Crowd),
mải điện thoại 28 %. Seed >= 100000 bị chặn khi không có --allow-test; 1000–99999 bị chặn hẳn. CHƯA nạp vào Gazebo thật (bị cấm): cần thử 1 file DEV (tải, tốc độ RTF với 4 ô) trước khi đăng ký.

## 9. Chưa chắc
- Độ nhạy n = 40, nhiều phép so: chỉ là cảnh báo. "real" là regime cũ của bản chụp, KHÔNG phải go2 (Bổ sung 3): chưa kiểm go2.
- Bản chụp 23:01: không đánh giá p3, ~t3, ~nl (ra sau). Lưu ý ~t3 đẩy tâm cụm 0,64 x bán kính: khớp hình học người tròn của fastsim, dễ quá khớp.
- Trễ tính toán (MPPI 29 ms, có gợi ý RL 56–62 ms/bước trên máy này) bị fastsim bỏ qua; trên Orin chưa đo.
- D1/D2 chưa có nhãn người để đối chiếu.

## 10. Kiểm thiết kế đóng băng (24/11, 10:30) — PREREG_TEST: `audit/PREREG_TEST.md`
Không rò rỉ:
- Không thư mục kết quả nào ngoài VAL_* có seed >= 2000. LOG chỉ có dòng đóng băng cho 2000–2399.
- Không gian seed tách rời: gen_world dùng Random(s*1000+a), a < 60; người dùng Random(s*7919+trial); SeedSequence theo [s, trial].
- sha256 khớp lúc 10:16.
- fast.so cho kết quả trùng từng dòng với numpy (C1, champ2, seed 0–6).
- meta.json đã ghi regime/oracle/crowd_model.

Thiếu sót (cần sửa trước TEST, không ảnh hưởng VAL đang chạy nếu mã không đổi):
(1) coord_val.sh chỉ kiểm sha256 một lần đầu script, nhưng mỗi ô mở tiến trình mới đọc lại mã.
(2) fast.so được nạp mà không băm. eval_sim.py và gen_gazebo_test.py cũng chưa băm.
(3) Không có quy tắc loại lượt EXC cho VAL.
(4) Ngân sách chỉnh lệch: p3 60 cấu hình trên 5 ô; mppi~t3 21; PGIF*/DRA* 35 mỗi cái nhưng chỉ ô champ base 0–149. Trái quy tắc 3, phải công bố.
(5) Seed 300–799 nằm trong dải DEV của PROTOCOL, nhưng chỉ dùng xác nhận và Isaac pilot: chấp nhận được, phải ghi.
(6) Ở helb, C1 ≈ PGIF*/DRA*: kết luận phụ thuộc mô hình người.

Sức mạnh: sd theo thế giới 0,18–0,20. C1 − DRA* ở +3 cần 293–503 thế giới; ở +2 cần 658–1131 → fastsim TEST 1000 thế giới (≈ 6 giờ).
Gazebo C1 vs B1: 680 cặp (≈ 20 giờ) cho 80 % ở +6.
Kết luận: VAL đúng như đăng ký thì CHẤP NHẬN; TEST cần SỬA (mục 0 của PREREG_TEST) rồi mới chạy.
