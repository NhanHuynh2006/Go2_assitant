# REPORT_SEV — giá trị né ngẫu nhiên có hồi tiếp (SEV), 23/11/2026

**Kết luận: BÁC BỎ ở bước 1 (quy tắc đã viết trước trong `sev/PREREG.md`). Không nối vào MPPI, không chạy bước 4, không so vòng kín với baseline
(`mppi:ppl=32` hay `mppi~t3~nl:ppl=100;ppl_len=0.5`), chưa chạy regime go2.** Không đề nghị theo tiếp SEV làm đóng góp chính.

## 1. Đã làm
- `sev/record.py`: fastsim **bản chụp** (`sev/snap`, 22/11 23:36; không đổi khi ALGO sửa), champ, `mppi:ppl=32`, seed 0–299 có người: **205 lượt, 125 thành công, 78 lần chạm người dùng được** (ghi 10 Hz người thật, track, robot).
- `sev/hazard*.py`: tần suất rẽ. `nav_sev.py`: DP (73×73×24 hướng×4 tốc độ, chu kỳ 0.3 s = trễ phản ứng, 10 chu kỳ = 3 s, 27 hành động). `sev/score*.py`: AUC.
- Không rò rỉ: hazard của DP đo ở Crowd không robot, **seed 800–999** (và THÖR); chấm ở seed 0–299; không tham số SEV nào được chỉnh theo 0–299. Seed ≥ 1000 không chạm.
- Quy tắc chính (P): dương = −2.0 / −1.5 s trước khi chạm (78); âm = 782 mốc ngẫu nhiên (≤ 4/lượt, người gần nhất < 4 m, không chạm trong 3 s); AUC không phụ thuộc tỉ lệ lớp.
  Tập khó (H): âm = 224 lần "suýt" (cực tiểu khoảng hở 0–0.6 m không chạm). Bootstrap 2000 lần theo LƯỢT. "Tốt nhất khác" = ứng viên có AUC cao nhất trên cùng tập (thiên cho đối thủ).
- Động học trong DP: đo lại từ `results/sysid.npz` (`sev/coupling.py`, 136 đoạn lệnh): tiến 0.26–0.28, ngang 0.22 ở lệnh 0.22 (gain 0.99), lùi −0.18, **wz: gain hồi quy 0.65 + 0.25·ux** (đứng xoay thấp hơn 0.85 đang dùng trong fastsim);
  tiến+ngang = 0.34–0.39 m/s (n=3+3) ⇒ tập vận tốc là HỘP, không phải elip (bằng chứng mỏng). Lắc thân: σ 3 cm trên khoảng hở. Kiểm DP bằng MC (400 hạt × 5 trạng thái): V lệch **cao hơn** MC 0–0.05 (khuếch tán lưới).

## 2. Kết quả bước 1 — AUC "sẽ chạm trong 3 s" (trạng thái người thật)

| | P −2.0 s | P −1.5 s | H −2.0 s | H −1.5 s |
|---|---|---|---|---|
| khoảng cách thân | 0.778 | 0.844 | 0.485 | 0.500 |
| TTC | 0.674 | 0.727 | 0.584 | 0.620 |
| **dce** (hở nhỏ nhất dự đoán 3 s, vận tốc không đổi) | **0.911** | 0.942 | **0.640** | **0.654** |
| PGIF | 0.879 | 0.939 | 0.530 | 0.595 |
| turn_cost / turn_const (2.1 s) | 0.828 / 0.828 | 0.880 / 0.881 | 0.542 / 0.528 | 0.569 / 0.562 |
| turn_cost trên rollout 2 s | 0.835 | 0.881 | 0.580 | 0.631 |
| **V SEV** (hazard Crowd) | 0.891 | **0.946** | 0.511 | 0.579 |
| V SEV (hazard THÖR) | 0.899 | 0.947 | 0.522 | 0.589 |
| V + chiều tường thô (crowd) | 0.894 | 0.946 | 0.523 | 0.590 |
| V vòng hở (giữ lệnh; bóng DRA) | 0.894 | 0.928 | 0.585 | 0.601 |
| **ΔAUC V(crowd) − tốt nhất khác (CI 95 %)** | −0.020 [−0.048, +0.007] | +0.004 [−0.019, +0.025] | −0.129 [−0.202, −0.056] | −0.074 [−0.160, +0.005] |

- Cần ≥ +0.03 với CI > 0 ở cả hai mốc: **không đạt ở mốc nào**; trên tập khó V kém `dce`, và CI loại 0 ở −2 s. Với hazard THÖR cũng vậy (−0.012, +0.006).
- Lợi ích gia tăng: logistic 5-fold (theo lượt) trên 7 điểm cũ rồi thêm V: 0.915 → 0.909 (−2 s), 0.951 → 0.951 (−1.5 s); ΔAUC CI [−0.023, +0.001] và [−0.001, +0.000]. V **không thêm thông tin**.
- Thay trạng thái người thật bằng track (cùng 78 dương): ở −2 s `dce` 0.911 → 0.798, V 0.891 → 0.790, PGIF 0.879 → 0.796 (−0.08 đến −0.11), turn 0.828 → 0.781, dist 0.778 → 0.713. Tụt do bộ bám lớn hơn chênh lệch giữa dce/PGIF/V. V vẫn không qua (−0.008 [−0.034, +0.016]; −0.006).
- **turn_cost ≈ turn_const** (chênh < 0.001 ở P): phần "khả năng từng trục" đúng là vô hiệu (khớp LIT 1.3). turn_cost kém `dce` 0.083 [0.026, 0.147].
- **Người đứng yên** (sp < 0.2 ở −2 s: 14/78 = 18 % số chạm, nhóm nhỏ): AUC turn_cost 0.43 (mù), V 0.914, dce 0.913, dist 0.889. V có lợi vì mô hình hoá "đứng → khởi động", nhưng bằng `dce`/khoảng cách (chênh +0.000 [−0.043, +0.050]).
  Ở người đang đi (64): dce 0.910, turn 0.916, V 0.886 (kém −0.031 [−0.062, +0.002]).
- Thăm dò sau khi rớt (không dùng để quyết): hazard ×0.5 / ×2 không đổi kết luận (AUC 0.887–0.894); `adv3` = giá trị xấu nhất 3 s kiểu CN-CBF (|ω| ≤ 0.35): 0.898 / 0.944, tương đương V, kém ở người đứng yên (−0.084 / −0.062).

**Vì sao (suy luận, không kiểm):** V = P(chạm | né *tối ưu*): ở −2 s, V trung bình của 78 lần chạm chỉ **0.022** (trung vị 0.010) và −1.5 s 0.040. Theo mô hình (1 người, trống, biết trạng thái) hầu hết số chạm vẫn né được; xếp hạng V do đó bị
chi phối bởi phần "không né nổi", không phải bởi điều bộ điều khiển thật làm sai. AUC đo tương quan với hỏng của *chính sách đã ghi*, nên `dce` (có vận tốc robot hiện tại) có lợi. V làm **hàm chi phí** có thể vẫn khác, nhưng luật dừng đã đặt trước.
Một chỉ dấu khác: tỉ lệ 0.022 gợi ý trần oracle (74 → 89 %) là do dự đoán/cảm nhận, không do "không thể né"; nhưng mô hình bỏ tường, nhiều người, đích, nên đó là trần lạc quan.

## 3. Hazard rẽ: người thật và Crowd (cùng bộ lọc 0.8 Hz, RDP 0.12 m, |góc| > 20°)

| | Crowd (seed 800–999, không robot) | THÖR (Zenodo 3382145, **CC BY 4.0**; 5 phiên 6D, 94 phút) | ETH/Hotel |
|---|---|---|---|
| tốc độ đi TB | 0.81 m/s | 0.94 | 1.45 (ngoài trời) |
| rẽ/s, mọi tốc độ | 0.149 [0.136, 0.160] | 0.099 [0.084, 0.113] | 0.029 |
| rẽ/s ở 0.6–1.2 m/s | 0.140 [0.127, 0.152] | 0.084 [0.071, 0.098] | – |
| theo tốc độ 0.3–0.6 / 0.6–0.9 / 0.9–1.2 | 0.209 / 0.160 / 0.111 | 0.253 / 0.147 / 0.061 | 0.122 / 0.069 / 0.057 |
| góc rẽ trung vị / p90 | 32° / 51° | 27° / 52° | 26° / 40° |
| P(đổi hướng > 60° trong 2 s) | 0.058 [0.050, 0.066] | 0.021 [0.013, 0.029] | ≈ 0 |
| P(lệch ngang CV > 0.4 m ở 2 s) | 0.175 [0.161, 0.188] | 0.196 [0.174, 0.220] | 0.18 |
| dừng /s (đang đi); khởi động /s | 0.128; 0.528 | 0.063; 0.217 | 0.017; 0.085 |

- **Crowd rẽ mạnh nhiều hơn THÖR ~1.7× ở tốc độ đi bình thường (0.6–1.2 m/s) và quay > 60° trong 2 s ~2.8×, dừng/khởi động nhiều ~2×**; nhưng sai số CV ngang ở 2–3 s **không** lớn hơn (người thật lệch nhẹ liên tục nhiều hơn; một phần là lắc đầu còn sót). Đây là tính chất của mô phỏng (đích ngẫu nhiên, đường A* nhiều đốt, vật cản chật), không phải của thế giới.
  Cảnh báo: phòng khác nhau (THÖR: phòng lab, nhiệm vụ đi lại, 9 người đội mũ, tự biết bị quan sát; Crowd: 5 họ bản đồ) ⇒ không phải so sánh có kiểm soát.
- Người "mải điện thoại" không rẽ khác người thường (khi không có robot, cùng mã).
- ETH/UCY từ bản sao OpenTraj **không ghi giấy phép rõ** cho dữ liệu: chỉ dùng để so, không phân phối lại. UCY, THÖR-MAGNI, TBD: chưa dùng. Dữ liệu tải ở `sev/data/{thor,eth}` (không đăng ra ngoài).

## 4. Khác CN-CBF (2603.06921)
CN-CBF: trò chơi **xấu nhất** (theo REPORT_OSS; tôi không đọc lại bài) trên trạng thái tương đối, người unicycle ω ≤ 0.35, robot nhanh, đĩa tròn 0.8 m, không trễ, không tường. SEV (ý định) khác ở: (a) kỳ vọng theo hazard rẽ thay vì min–max, (b) tầm 3 s hữu hạn,
(c) robot phản ứng sau 0.3 s, (d) thân chữ nhật theo góc + lắc, (e) v_r ≪ v_h, (f) người đứng có thể khởi động. Những khác biệt này **không cải thiện phân biệt** so với dự đoán vận tốc không đổi ở dữ liệu ta; không được viết là "hơn".
Khẳng định "robot 0.29 m/s luôn bị bắt" (REPORT_OSS 0.2): DP min–max của tôi (`sev/adv.py`, 0.2 m, 24 hướng, ω ±0.35, ở 3/6/12 s) **không lặp lại được điều đó** (ở d ≥ 1.5 m tỉ lệ bị bắt 0.00; 1.0–1.5 m, hướng vào < 30°: 0.31),
nhưng nội suy hàm khoảng hở lệch về phía an toàn và 12 s < một vòng rẽ của người (18 s) nên **chưa kết luận được**; đừng in cả hai số.

## 5. Ý C (xoay thân): |góc| lúc chạm, dev3
mppi 47 lần: < 30° 51 %, 30–60° 34 %, hông 60–120° 11 %; `mppi:ppl=32` 36 lần: 47 / 22 / 19 %; p2+turn 35 lần: 43 / 29 / 14 %. 69–85 % chạm ở ≤ 60° quanh mũi ⇒ theo tiêu chí của LIT, **ý C bị bác bỏ yếu** (n nhỏ, mũi dài hơn hông nên tỉ lệ này một phần do hình học).

## 6. Chưa chắc / hạn chế
- Một chính sách ghi (`mppi:ppl=32`, tracker v2, champ, crowd-model base); chưa thử go2, helb, `mppi~t3~nl:ppl=100;ppl_len=0.5`. n = 78 dương: CI của ΔAUC ±0.025–0.03; một ΔAUC thật ~ +0.01 không loại được, nhưng +0.03 bị loại ở −2 s với V_crowd.
- Hướng robot trong DP: không biết vận tốc robot hiện tại (tau 0.15 gộp vào trễ), không tường động, không nhiều người phối hợp (1−∏(1−V)). Chiều tường 8 hướng cố định < 0.6 m, không xoay theo thân.
- Tổng phép thử: 8 biến thể SEV (gồm sau khi rớt) trên cùng 0–299, không biến thể nào đạt.
- Không chạy VAL/TEST, không Gazebo, không GPU.

## 7. Đề xuất
1. Dừng SEV và mọi biến thể "giá trị né" offline. 2. Khoảng mất AUC do track (~0.11) và trần cảm nhận (74 → 89 %) chỉ vào **cảm nhận + dự đoán**, không vào dạng chi phí né.
3. Trong bài: giữ bảng turn vs turn_const vs dce như ablation âm; ghi Crowd rẽ/dừng nhiều hơn THÖR (cần xác nhận ở cảnh khớp).
4. Người đứng yên: thêm mô hình "có thể khởi động" vào chi phí (rẻ: dùng `dce` với người đứng có vận tốc giả định khi gần) là chỗ duy nhất `turn` lộ điểm mù; phải kiểm AUC/vòng kín riêng, cả champ lẫn go2.
