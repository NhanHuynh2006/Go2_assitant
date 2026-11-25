# THIẾT KẾ ĐÓNG BĂNG (24/11/2026, coordinator)

Sau 3 vòng ALGO (PLAN §00, tối đa 3 vòng). Không sửa thuật toán nữa trước TEST.

- **Thuật toán đề xuất (C1):** `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5`
- **Baseline (cấu hình cố định, cùng tracker v3 + `~nl`):**
  - B1 `mppi~t3~nl:ppl=100;ppl_len=0.5` (MPPI chỉnh tốt nhất)
  - PGIF* `pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000` (cài lại từ 2608.08323)
  - DRA* `dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05` (cài lại)
  - B0 `mppi:ppl=32` (MPPI gốc, tracker cũ)
  - `dwa~t3~nl:ppl=100;ppl_len=0.3`, `log_mppi~t3~nl:ppl=100;ppl_len=0.5` (tham khảo)
- **Mã:** sha256 trong `results/frozen_C1/SHA256SUMS`, bản chụp `results/frozen_C1/code.tgz`. Mọi lượt VAL/TEST phải khớp sha256 (kiểm trước khi chạy).
- `~cs` (nắn lệnh an toàn) là tuỳ chọn triển khai, không thuộc so sánh.

## Đăng ký trước VAL (ghi TRƯỚC khi chạy)
- Seed 2000–2399, `--suite gen --crowd-only`, 1 lượt, 5 ô: champ/champ2/go2 × base, champ2/go2 × helb.
- Chỉ số chính: tới đích không va chạm gì (`success`). Phụ: va người, va vật, kẹt, thời gian.
- Phép so chính (họ 3, Holm): C1 vs B1, C1 vs PGIF*, C1 vs DRA*. Mỗi phép: chênh gộp theo thế giới (trung bình 5 ô), hoán vị dấu theo thế giới (2-phía, 200 000 lần) + KTC 95 % bootstrap.
- Phụ (báo cáo, không kết luận): từng ô (McNemar chính xác, Holm trong 15), vs B0/dwa/log_mppi.
- Vai trò VAL: kiểm lần cuối trên seed chưa ai dùng; KHÔNG được đổi thiết kế theo VAL. Nếu C1 vs B1 không có ý nghĩa ở VAL thì vẫn chạy TEST như đăng ký và báo cáo trung thực cả hai.

## Bổ sung 24/11 ~10:50 (sau duyệt AUDIT, TRƯỚC khi xem bất kỳ kết quả VAL nào)
- Quy tắc EXC cho VAL (theo PREREG_TEST): EXC ở mọi cấu hình của một thế giới = lỗi hạ tầng → bỏ thế giới đó khỏi mọi phép so; EXC chỉ ở một cấu hình → tính là thất bại của cấu hình đó.
- sha256 sẽ được kiểm lại SAU khi VAL xong (VAL chỉ kiểm ở đầu); kết quả kiểm ghi vào LOG.
- TEST: dùng `results/frozen_C1/SHA256SUMS_TEST` (thêm fast.so, eval_sim.py, audit/gen_gazebo_test.py, audit/PREREG_TEST.md), chạy từ bản giải nén chỉ-đọc, kiểm sha trước MỖI ô, thư mục ra phải rỗng.
- Công bố trong bài (AUDIT 4–5): ngân sách chỉnh lệch về C1 (họ p3 60 cấu hình trên 5 ô; mppi~t3 21; PGIF*/DRA* 35 nhưng chỉ ở ô champ-base seed 0–149); ở người helb C1 ≈ PGIF*/DRA*; seed 300–799 thuộc dải DEV nhưng chỉ dùng để xác nhận.
