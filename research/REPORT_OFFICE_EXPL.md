# REPORT_OFFICE_EXPL: bản đồ văn phòng lớn (voice_office 32 × 22 m), C1 / B1 / DRA*, 3 lần mỗi bài

Coordinator, 25/11 23:45. Đây là phép **THĂM DÒ**, chạy trên các bài DEV có sẵn của suite office, không phải TEST.

**Vì sao chạy.** Khi chuẩn bị demo, chạy thử nhanh 3 bài, mỗi bài 1 lần: C1 kẹt cả 3, B1 tới đích 2/3. Cần đo lại cho chắc.

**Cách chạy.**
- Script: `research/run_office_expl.sh`, chạy 2 sim headless.
- Kết quả: `results/OFFICE_EXPL/{clutter,crowd}/`.
- Mỗi cấu hình chạy 27 lượt. Bộ lọc `--only van_phong` khớp luôn cả bài `van_phong_dong`, nên bài này có 6 lượt mỗi cấu hình.

## Kết quả

| Bài | C1 | B1 | DRA* |
|---|---|---|---|
| khối so le (qua_khoi) | 1/3 (kẹt 2) | 3/3 | 1/3 (va 2) |
| văn phòng | 3/3 | 3/3 | 3/3 |
| slalom cọc | 3/3 | 2/3 | 3/3 |
| lối pallet | 3/3 | 3/3 | 1/3 |
| bếp xa | 1/3 | 0/3 | 0/3 |
| sảnh 8 người | 1/3 (va 2) | 1/3 (va 2) | 1/3 (va 2) |
| kho có xe đẩy | 2/3 | 1/3 | 3/3 |
| văn phòng có người | 3/6 | 3/6 | 2/6 |
| **Tổng** | **17/27** | **16/27** | **14/27** |

**Đọc kết quả.**
- Với cỡ mẫu này, ba bộ điều khiển không khác nhau.
- Lần thử ban đầu (C1 0/3) là rút trúng các lượt xấu. Nó không phản ánh C1 kém hơn một cách hệ thống.

## Hai chỗ kẹt (đọc từ quỹ đạo trong episodes.jsonl)

1. **Bếp xa — mọi bộ điều khiển đều kẹt ở cùng một chỗ, khoảng (−6,2; 2,7).**
   - Đây là khe hẹp giữa vách part_west_2 (x = −5), cây nước (−6, 3,8) và dãy bàn/ghế (x ≈ −7,8).
   - Đây là vấn đề của bài (đường A* đi qua khe quá hẹp so với thân Go2), không phải của C1.
   - C1 là bộ duy nhất qua được, 1/3 lần.
2. **Khối so le — kiểu kẹt riêng của C1.**
   - Đích (0; −7,7) nằm ngay sau quầy lễ tân (x ∈ [−1,3; 1,3], mặt nam y = −6,95), cách mặt quầy 0,75 m.
   - B1 và DRA* vòng qua góc quầy, sát mặt quầy chỉ 0,25–0,42 m (khoảng cách từ tâm thân tới hộp quầy).
   - Ở 2 lượt kẹt, C1 giữ khoảng cách 0,38–0,64 m. Nó dừng cạnh đầu quầy, tại (±2,2; −7,0), cách đích 2,2 m, và bộ phát hiện kẹt (4 cửa sổ không tiến được 0,15 m) kết thúc lượt.
   - Ở lượt thành công, C1 đi sát 0,36 m.

**Giải thích.** Chi phí nguy hiểm tĩnh của C1 (hình học hai đĩa, rủi ro geo) thận trọng hơn. Khi đích nằm khuất ngay sau một vật dài, C1 có thể dừng ở cực tiểu cục bộ.
- Điều này khớp với nhánh "chỉ vật tĩnh" của TEST, trong đó C1 hơi kém hơn và kẹt nhiều hơn.
- Không sửa, vì thiết kế đã khoá.
- Hướng làm tiếp: mẫu thoát kẹt hoặc giảm biên tĩnh khi gần đích.

## Gợi ý cảnh quay demo

- **C1 chạy tốt, nên quay:** văn phòng, slalom cọc, lối pallet, kho có xe đẩy, văn phòng có người (hên xui).
- **Tránh:** bếp xa (mọi bộ đều kẹt ở khe hẹp) và khối so le (C1 dễ kẹt sau quầy).
- **Sảnh 8 người:** cả ba bộ đều va 2/3. Đó là cảnh đông người khó, chỉ nên quay khi muốn nói về giới hạn.
