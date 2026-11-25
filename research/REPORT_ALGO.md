# REPORT_ALGO — cải tiến thuật toán né người cho Go2 (22–23/11/2026)

Tất cả số liệu là fastsim, chế độ `--suite gen --crowd-only`. DEV dùng seed 0–299. Xác nhận dùng seed 300–799, chạy một lần. VAL/TEST không đụng. Chỉ số chính là tới đích không va chạm gì. Mỗi thế giới chạy một lượt, mọi cấu hình cùng thế giới và cùng seed nhiễu, nên so được ghép cặp (McNemar). Có thêm phép hoán vị gộp theo thế giới qua các ô.

File liên quan:
- Bảng thô: `research/algo_tables.txt`, `research/algo_confirm.txt`.
- Phép thử: `research/LOG.csv`, agent ALGO, 171 dòng.
- Công cụ: `research/algo_run.sh`, `algo_run_oracle.sh`, `algo_oracle.py`, `algo_confirm.py`, `algo_compat.py`, `algo_trkerr.py`, `algo_timing.py`, `algo_fast/fast.c`.

### 1. Thay đổi (mỗi thứ là một tag/cờ; cấu hình cũ giống từng bit, kiểm 25/25 lượt so với dev3/dev1)

**`~t3`: BlobTracker v3** (nav_local `_update_v3`):
- Lọc Kalman vận tốc không đổi.
- Trừ nền: bỏ điểm nằm trong ô chắc chắn là tĩnh.
- Bằng chứng "động" tính theo từng điểm.
- Bù tâm cụm lệch về phía robot: đẩy ra 0,64 × bán kính cụm.
- Tầm 5,5 m; xác nhận sau 2–3 lần quét.
- Người dừng lại vẫn là người, tối đa 6 s, rồi hạ cấp nếu mất bằng chứng.
- Giữ vết khi bị che hoặc vào vùng mù.
- Không đếm là "kẹt" khi đang chờ người.

Lý do: mổ 16 lần chạm của `mppi:ppl=32` thì ~6/16 là người dừng rồi đi tiếp. Sai số vị trí luôn lệch 0,15–0,2 m về phía robot, vận tốc dao động ±0,3 m/s.

Sai số đo trên 10 thế giới DEV (`algo_trkerr.py`), vị trí / vận tốc trung bình:

| Tracker | Vị trí | Vận tốc |
|---|---|---|
| v2 | 0,184 m | 0,194 m/s |
| v2 + `~dt` | 0,182 m | 0,179 m/s |
| v3 | 0,088 m | 0,137 m/s |

Tỉ lệ bóng ma ngang nhau (7–10 %).

**`~dt`: sửa lỗi AUDIT b2.** Vận tốc chia cho `t − tr['t']`. Đo bằng `b2_tracker`: khi mất 2 lần quét, người 0,9 m/s trước bị đọc thành 1,74, sau sửa còn 0,90. Tracker v3 không có lỗi này.

**`~nl`: RespModel.** Mỗi trục dùng v = s·tanh(g·u/s) cộng trễ bậc 1. Hậu nghiệm trên lưới (g, s) học online từ (lệnh, vận tốc đo). Bốn bộ: tiến, lùi, ngang, quay. Không đọc tham số mô phỏng.

**`p3` (nav_prism2.PRISM3).** Các cờ:
- `prim`: thêm 96 mẫu là vận tốc tối đa theo 16 hướng × 3 kiểu quay, chạy cả tầm hoặc 1,2 s đầu.
- `grad`: λ = 0,3·(phân vị 15 % − min), phạt va = 300·(1 − t_chạm/T) + độ lún. Baseline dùng trung vị, nên khi hơn 50 % mẫu chạm thì λ ≈ 400 và mọi mẫu có trọng số như nhau.
- `geo`: rủi ro R = Σ_m w_m · max_t e^(−t/1,2) · (d>0 ? e^(−d/0,12) : 1−d), với d là khoảng hở thân 2 đĩa đến người.
  - Với cờ `gcv` (có trong C1): chỉ dùng một giả thuyết vận tốc không đổi.
  - Bản đầy đủ: 55 % CV + 45 % quạt ý định trắc địa (Dijkstra trên bản đồ của robot).
- `haz`, `hyp`, `cvar`, `ggs`, `commit`: các cờ khác, xem mục 4.

**Các thứ khác:**
- `MPPI.set_param` nhận tham số để chỉnh baseline, và báo lỗi nếu tham số không tồn tại hoặc không có tác dụng.
- `_make_ctrl` báo lỗi khi gặp tag lạ hoặc cờ lạ.
- Bản C tuỳ chọn cho A* và argmin (`GOVOICE_FAST_SO`), kết quả giống từng bit.

**Thời gian một bước:**

| Cấu hình | TB | p99 | Ghi chú |
|---|---|---|---|
| C1 | 9,2 ms | 12,2 ms | numpy |
| C1 | 6,8 ms | — | bản C |
| C2 | 12,6 ms | — | |
| Có gợi ý RL | ~50 ms | — | vượt ngưỡng 40 ms |

**Khác bài trước (nguồn: LIT/OSS, tôi không đọc lại toàn văn):**
- **PGIF-MPPI (2608.08323):** cộng Gauss dị hướng quanh dự đoán CV ở mọi bước, không chiết khấu, trạng thái người cho biết trước. p3 khác ở bốn điểm:
  - lấy max theo thời gian, có chiết khấu (recourse rẻ);
  - sửa suy biến nhiệt độ;
  - thêm mẫu né nguyên thuỷ;
  - dùng tracker thật, robot chậm hơn người 3×.
- **CN-CBF (2603.06921):** giá trị HJ xấu nhất, vô hạn tầm, robot nhanh gần bằng người. Với γ ≈ 0,32 thì tập luôn-thoát gần như rỗng (OSS 0.2). p3 không cho bảo đảm, chỉ giảm rủi ro hữu hạn tầm, nhưng có vật tĩnh, thân dài và bão hoà.
- Không mảnh nào mới riêng lẻ. Đóng góp là tổ hợp, kèm ablation.

### 2. Chẩn đoán cảm nhận (oracle từng phần, chỉ để chẩn đoán)

Cấu hình `mppi:ppl=32`, seed 0–149, n = 101:

| Chế độ | v2 thật | t3 | Thấy (≤ 5,5 m) | 4 m | Bỏ người đứng | Trễ xác nhận 0,6 s | Nhiễu + lệch + EMA | Mù < 0,75 m | Oracle đủ |
|---|---|---|---|---|---|---|---|---|---|
| champ | 63 | 70 | 74 | 75 | 71 | 76 | **61** | 73 | 75 |
| go2 | 69 | 83 | 79 | 85 | 86 | 84 | **66** | 78 | 89 (đ.p.v.) |

Kết luận:
- Tầm và trễ xác nhận gần như không ảnh hưởng.
- Nút thắt là chất lượng ước lượng (lệch tâm, nhiễu và trễ vận tốc). v3 đưa t3 lên tới mức "thấy hoàn hảo".
- Phần còn lại ở go2 (79 → 89) là che khuất: oracle đủ thấy cả xuyên tường.
- C1 với "thấy hoàn hảo" đạt 90 (champ) / 92 (go2), nên khoảng trống cảm nhận còn lại của C1 khoảng 8–10 điểm.

### 3. DEV

**Vòng D, seed 0–299, n = 205:**

| Cấu hình | champ | go2 |
|---|---|---|
| C1 | 81,0 | **89,3** |
| C2 có ppl=32;0.5 | 82,4 | 87,8 |
| `mppi~t3~nl:ppl=100;0.5` | 77,1 | 80,5 |
| `mppi~t3:ppl=100;0.5` | 67,8 | 82,0 |
| `mppi~t3:ppl=32` | 67,8 | 79,0 |
| `mppi~dt:ppl=32` | 63,4 | 72,2 |
| `mppi:ppl=32` | 61,0 | 68,8 |

**Ablation** trên champ, seed 0–149, n = 101; nền là `p3+geo-haz+gcv~t3~nl` (ppl=16) = 82,2:

| Bỏ / đổi | Tỉ lệ |
|---|---|
| −grad | 81,2 |
| −prim | 81,2 |
| không chiết khấu (τ = ∞) | 79,2 |
| bỏ phạt va có cấp | 82,2 |
| ppl=0 | **69,3** (+2/−15) |
| không `nl` | 76,2 |
| không `t3` | 75,2 |
| quạt trắc địa | 87,1 |
| quạt Gauss (n = 40) | 75 |
| cvar (n = 39) | 84,6 |
| commit (n = 37) | 83,8 |
| p3 gốc có `haz` | 77,2 |
| p3 + geo + haz | 77,2 |

Ở n = 101 nhiễu khoảng ±9 điểm, nên từng ablation riêng lẻ không có ý nghĩa, trừ ppl=0.

**Gợi ý RL** (seed 150–299, n = 104), so với "không gợi ý":

| Tổ hợp | champ | go2 |
|---|---|---|
| không gợi ý | 80,8 | 79,8 |
| ppo | 80,8 | 87,5 (p = 0,057) |
| ppo+sac | 82,7 | 84,6 |
| ppo+td3 | 76,9 | 81,7 |
| ppo+td3+sac | 79,8 | 87,5 (p = 0,096) |

Không tổ hợp nào có ý nghĩa, lại tốn 50 ms/bước, nên bỏ RL khỏi thuật toán chính và chỉ giữ làm ablation.

**Chỉnh baseline:** 31 cấu hình mppi/dwa/log_mppi khác nhau (gồm ppl, ppl_len, sig, T, K, lam, w_pen, ang/lat). p3 dùng 35 cấu hình. Tính thêm 8 lượt dev3 của điều phối viên thì baseline mới ≥ p3.

### 4. Xác nhận, seed 300–799, 356 thế giới mỗi ô

| Cấu hình | champ | champ2 | go2 | champ2 helb | go2 helb | Gộp |
|---|---|---|---|---|---|---|
| **C1** | 83,4 | 78,4 | 92,4 | 84,8 | 92,1 | **86,2** |
| C2 | 83,1 | 79,2 | 88,5 | 81,5 | 89,0 | 84,3 |
| mppi~t3~nl:ppl=100;0.5 | 78,9 | 70,8 | 86,0 | 78,1 | 88,8 | 80,5 |
| mppi~t3:ppl=100;0.5 | 69,9 | 67,1 | 83,1 | 76,1 | 88,2 | 76,9 |
| mppi:ppl=32 | 59,6 | 58,7 | 74,7 | 73,0 | 87,1 | 70,6 |
| dwa~t3~nl:ppl=100;0.3 | 77,0 | 72,8 | 82,0 | – | – | 77,2 |
| log_mppi~t3~nl:ppl=100;0.5 | 75,3 | 71,3 | 85,1 | – | – | 77,2 |

C1 so với baseline mạnh nhất (`mppi~t3~nl:ppl=100;0.5`), từng ô:

| Ô | Chênh | +/− | p | Holm |
|---|---|---|---|---|
| champ | +4,5 | +47/−31 | 0,089 | — |
| champ2 | +7,6 | — | 0,004 | 0,09 |
| go2 | +6,5 | — | 0,005 | — |
| champ2 helb | +6,7 | — | 0,006 | — |
| go2 helb | +3,4 | — | 0,13 | — |
| **gộp** | **+5,7** | — | **1e-5** | **0,0004** |

Holm tính trong họ 52 phép so. Bonferroni theo 391 dòng LOG cho kết quả gộp là 0,004.

Các so sánh gộp khác:
- C1 so với `mppi:ppl=32`: +15,6 điểm.
- C2 so với baseline mạnh nhất: +3,8 điểm, Holm 0,08, không qua.

Thời gian đi (champ): C1 65 s, baseline mạnh 74 s.

Về `~nl` ở champ2 (điểm "inverse crime" điều phối viên nêu):
- Với baseline, `~nl` vẫn giúp: 70,8 so với 67,1.
- Với p3 thì không: p3 không `nl` đạt 80,3, có `nl` đạt 78,4 (n = 356).

### 5. Không hiệu quả / chưa chắc
- `haz` (hazard đổi hướng học online), `turn` / p2+turn, quạt Gauss, CVaR, commit: đều không lợi.
- Quạt trắc địa không hơn CV. Mô phỏng người đi A* tới đích ngẫu nhiên, tức trùng giả định của quạt, mà vẫn không hơn. Vì thế C1 dùng CV.
- Baseline: lam_q/lam_c (−8 đến −20 điểm), K=1200, T=36, w_pen, ppl=150 đều không giúp. Tracker `~t4` 10 Hz: vận tốc 0,137 → 0,127 nhưng bóng ma tăng lên 16 %.
- Hạn chế:
  - Chỉ có fastsim. Độ trung thực so với Gazebo: Spearman 0,90 (champ) / 0,59 (champ2), chênh lệch không có ý nghĩa.
  - Người mô phỏng rẽ nhiều hơn người thật (THÖR) ~1,7×.
  - Hình dạng tanh của `~nl` trùng với regime champ.
  - Che khuất chưa xử lý.
  - Chưa đo trên Jetson.
- Giấy phép: chỉ dùng numpy/scipy (BSD) và mã tự viết. Không chép mã của repo nào.

### 6. Đề xuất
1. VAL do điều phối viên chạy: C1 so với `mppi~t3~nl:ppl=100;ppl_len=0.5` và `mppi:ppl=32`.
2. Cài lại PGIF-MPPI và DRA-MPPI từ công thức, cùng tracker v3 và cùng `~nl`.
3. Thêm vết "có thể có người" ở mép vùng khuất cho go2.
4. Đo `~nl` trong Gazebo và trên chó thật bằng `dyn/HUONG_DAN_DO.md`.
5. Ghi rõ trong bài rằng phần lợi chia thành phần tracker/mô hình dùng chung và phần riêng của p3 (+5,7 điểm so với baseline đã nhận cả hai).

---
*Ghi chú coordinator (23/11 ~22:00): agent ALGO bị chặn ghi file .md (phiên agent bắt đầu trước khi người dùng mở quyền ghi); coordinator lưu nguyên văn theo cho phép của người dùng. Coordinator đã tính lại độc lập C1 vs `mppi~t3~nl:ppl=100;ppl_len=0.5` trên 356 thế giới × 5 ô: +5.7 điểm, CI95 [3.6; 7.9], hoán vị dấu theo thế giới p ≈ 5e-6; từng ô khớp bảng.*

---
# Vòng 2 (24/11) — PHẦN ĐĂNG KÝ TRƯỚC (ghi lúc 01:35 24/11, TRƯỚC khi chạy xác nhận seed 1000–1499)

Ứng viên vòng 1 đã khoá: **C1 = `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5`** (không sửa gì nữa).

Quy tắc chấp nhận C3 = C1 + `occ` (vết "người có thể có" ở mép vùng khuất):
1. Chỉ đưa C3 vào xác nhận nếu trên DEV (go2, seed 0–149) C3 KHÔNG kém C1 (ghép cặp, số thắng ≥ số thua).
2. Trên seed xác nhận 1000–1499: C3 thay C1 chỉ khi C3 hơn C1 gộp 5 ô với p < 0.05 (hoán vị theo thế giới) VÀ không ô nào kém C1 quá 2 điểm. Ngược lại C1 giữ nguyên.

Xác nhận (chạy MỘT lần, seed 1000–1499 crowd-only, 5 ô: champ/champ2/go2 × base, champ2/go2 × helb):
- So sánh chính (Holm trong họ này): C1 so với mỗi baseline {mppi~t3~nl:ppl=100;ppl_len=0.5 (B1), PGIF chỉnh tốt nhất, DRA chỉnh tốt nhất, mppi:ppl=32 (B0)}, mỗi ô + gộp.
- PGIF/DRA cài lại từ công thức bài, cùng tracker `~t3` và `~nl`, chỉnh trên đúng bộ DEV C1 đã chỉnh (champ seed 0–149), ngân sách ≈ 35 cấu hình mỗi cái; cấu hình tốt nhất chọn bằng tỉ lệ thành công DEV champ 0–149 (hoà thì lấy cái tốt hơn ở go2 0–149) TRƯỚC khi chạy xác nhận.
- Ablation (một lần, 3 ô base: champ, champ2, go2), mỗi lần bỏ một thành phần khỏi C1: −grad, −prim, −chiết khấu (g_tau=99), −~t3, −~nl, rủi ro geo → chi phí ppl thường (`p3-haz~t3~nl:ppl=32;ppl_len=0.5`).
- Chọn trước khi xác nhận (02:08 24/11): **PGIF\* = `pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000`** (champ 0–149: 77,2 %, hoà với bản lam; go2 0–149: 80,0 so với 79,8),
  **DRA\* = `dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05`** (champ 0–149: 82,2 %). C3 (occ) KHÔNG đưa vào xác nhận: DEV go2 0–149 mọi biến thể `occ` kém C1
  (84–90 % so với 93,1 %, thua nhiều hơn thắng), và chẩn đoán cho thấy C1 không có khoảng trống che khuất ở go2 (oracle xuyên tường 93,1 % ≤ oracle chỉ-thấy 97,0 %).

---
# Vòng 2 (24/11) — KẾT QUẢ

Mọi phép thử ở `research/LOG.csv` (agent ALGO). Bảng: `research/algo_confirm2.txt` (so sánh chính), `research/algo_ablation2.txt` (ablation),
`research/algo_timing.txt` (CPU), thư mục `results/algo_W{champ,champ2,go2}_base`, `results/algo_W{champ2,go2}_helb` (xác nhận, seed 1000–1499, 348 thế giới có người mỗi ô).

## R2.1 Baseline cài lại từ bài (đọc bản HTML arXiv, phần phương pháp + siêu tham số; không chép mã)
- **PGIF-MPPI** (arXiv 2608.08323, Eq. 10–16): trường Gauss dị hướng quanh người dự đoán CV ở mọi bước, σ∥ = 1.2 + 0.5·s phía trước / 0.5 phía sau,
  σ⊥ = 0.6 m, cộng theo người và theo thời gian, không chiết khấu, không phạt va cứng. `nav_prism2.PGIFMPPI`. Lệch có chủ ý: robot 2 đĩa (bài: điểm tâm), trọng số
  tương đối theo thang chi phí của ta (bài: w_human 1e6 so với goal 1e3, λ 1000) → `w_h` là tham số chỉnh; `sig_scale` nhân cả σ; tuỳ chọn `hard` thêm phạt va cứng.
  Mã của bài: github.com/ChinmayMundane/PGIF_MPPI, theo REPORT_OSS là **MIT** — không chép, chỉ cài lại từ công thức.
- **DRA-MPPI** (arXiv 2506.21205, Eq. 8–14): xác suất va mỗi bước P_t = 1 − Π_o(1 − P_t^o), P_t^o = tích phân Gauss của người trên đĩa bán kính
  (robot + người); C = ω_soft·P + ω_hard·[P > 0.05] cộng theo bước. Bài ước lượng P bằng Monte Carlo 20 000 điểm; ở đây tính **đúng** bằng CDF χ² lệch tâm
  (bảng tra theo (t, d), dựng một lần ~200 ms ở bước đầu — nên dựng sẵn khi khởi tạo trên robot). Bất định theo mô hình mô phỏng của bài
  (σ_w = 0.3 nhiễu vận tốc mỗi bước → σ_t = σ_w·√(dt·t)); robot 2 đĩa, gộp 1 − (1−P_mũi)(1−P_đuôi). ω_soft, ω_hard bài không cho số → chỉnh.
  Mã gốc (dra-mppi) **không có giấy phép** theo REPORT_OSS → chỉ đọc bài, không đọc/chép mã.
- Cùng tracker `~t3`, cùng `~nl`, cùng K = 600, T = 24, cùng chi phí bám đường/vật tĩnh của MPPI gốc. Không cho PGIF/DRA các phần riêng của p3 (prim, grad).
- **Ngân sách chỉnh: 35 cấu hình mỗi baseline** (bằng p3), trên đúng bộ C1 đã chỉnh (champ seed 0–149, n = 101), tie-break ở go2 0–149.
  Tốt nhất: PGIF\* `w_h=300;sig_scale=0.7;hard=5000` 77,2 %; DRA\* `w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05` 82,2 % (C1 trên cùng thế giới: 81,0 % ở 0–299; B1 80,2 %).
  Quan sát: DRA tốt nhất khi **tắt** phạt ngưỡng cứng (ω_hard = 0) và tăng σ_w ×4 so với bài — đúng hiện tượng suy biến nhiệt độ đã thấy ở MPPI (ngưỡng cứng 2000–20000 làm
  phần lớn mẫu bằng nhau); PGIF cần w_h lớn và σ nhỏ hơn bài (robot chậm 3×).

## R2.2 Che khuất (C3 = C1 + `occ`) — không đạt quy tắc đăng ký trước
`occ`: từ lần quét LiDAR (1°/bin, lấp lỗ 1–2 tia, bỏ tường nhìn xiên bằng tỉ số bước nhảy) tìm mép khuất trong 4 m, đặt "người có thể có" ngay sau mép,
đi thẳng tới robot với tốc độ đi bộ học được, tính rủi ro như geo với trọng số `w_occ`. DEV go2 0–149 (n = 101): C1 93,1 %; occ w_occ ∈ {0.01, 0.03, 0.1}
và biến thể n/jump/reach: 84,2–90,1 %, mọi biến thể thua nhiều hơn thắng → theo quy tắc 1 **không đưa vào xác nhận**. Chẩn đoán độc lập: C1 với oracle
xuyên tường 93,1 % ≤ oracle chỉ-người-nhìn-thấy 97,0 % ≤ … tức ở go2 C1 **không có khoảng trống che khuất** để lấp; phần còn lại (93 → 97) là chất lượng ước lượng.
Bản đầu của `occ` (chưa lấp lỗ tia) đặt người ảo dọc tường thẳng → robot đứng im tới hết giờ: lỗi đã sửa, ghi lại để khỏi lặp.

## R2.3 Xác nhận (seed 1000–1499, một lần, 348 thế giới/ô)

| cấu hình | champ | champ2 | go2 | champ2 helb | go2 helb | gộp |
|---|---|---|---|---|---|---|
| **C1** | **82,2** | **81,6** | **89,7** | **84,2** | **91,4** | **85,8** |
| B1 `mppi~t3~nl:ppl=100;ppl_len=0.5` | 76,7 | 72,7 | 85,1 | 74,1 | 87,4 | 79,2 |
| PGIF\* | 79,3 | 70,1 | 78,7 | 84,2 | 90,5 | 80,6 |
| DRA\* | 77,9 | 77,0 | 84,5 | 83,6 | 90,2 | 82,6 |
| B0 `mppi:ppl=32` | 62,9 | 59,8 | 74,1 | 68,7 | 86,8 | 70,5 |

Họ 24 phép so (C1 × 4 baseline × (5 ô + gộp)), Holm; tổng dòng LOG (ALGO + AUDIT) = 533 cho Bonferroni thô:
- C1 − B1 gộp **+6,6 điểm**, p ≈ 1e-5 (hoán vị theo thế giới), Holm 0,0002, Bonf(533) 0,005. Từng ô: +5,5 / +8,9 / +4,6 / +10,1 / +4,0 (Holm 0,31 / 0,011 / 0,32 / 0,003 / 0,27).
- C1 − PGIF\* gộp **+5,2**, Holm 0,0002 (go2 +10,9, champ2 +11,5 có ý nghĩa; **helb 0,0 và +0,9: hoà**).
- C1 − DRA\* gộp **+3,2**, p 0,0018, Holm 0,024, Bonf(533) 0,98 (không ô nào riêng có ý nghĩa; champ2 helb +0,6, go2 helb +1,1: hoà).
- C1 − B0 gộp +15,3, Holm 0,0002.
- **Lặp lại vòng 1** (seed 300–799): C1 − B1 lúc đó +5,7, nay +6,6 trên thế giới mới.
- Điều phải nói thẳng: với người mô hình helb, PGIF\* và DRA\* bằng C1; ưu thế của C1 so với hai baseline bài báo nằm ở người mô hình base. Không ô nào C1 kém.

## R2.4 Ablation (seed 1000–1499, 3 ô base, một lần; bỏ từng thành phần khỏi C1)

| bỏ | champ | champ2 | go2 | gộp Δ so với C1 | p (Holm trong 24) |
|---|---|---|---|---|---|
| C1 đầy đủ | 82,2 | 81,6 | 89,7 | — | |
| − `~t3` (tracker v2) | 76,7 | 75,6 | 83,6 | **−5,8** | 6e-5 (0,0014) |
| − `prim` | 79,6 | 76,7 | 84,5 | **−4,2** | 0,0012 (0,029) |
| geo-risk → chi phí ppl thường | 82,8 | 79,0 | 85,1 | −2,2 | 0,078 (1) |
| − `grad` | 82,5 | 77,6 | 90,2 | −1,1 | 0,40 |
| − chiết khấu (g_tau = 99) | 82,8 | 79,3 | 89,4 | −0,7 | 0,62 |
| − `~nl` | 82,5 | 80,5 | 89,4 | −0,4 | 0,81 |

Đọc đúng: phần lợi **chứng minh được** của C1 so với chính nó là tracker v3 và mẫu né nguyên thuỷ. Rủi ro geo có chiết khấu, sửa nhiệt độ và mô hình đáp ứng học online
**không chứng minh được là cần** trong C1 (khác vòng 1 DEV nơi `~nl` giúp baseline; với C1 thì không). Lưu ý: −`~t3` và −`~nl` cũng là thứ baseline B1 đã có.
Đề xuất cho bài: thuật toán chính nên là bản **gọn nhất không kém** — C1 bỏ grad/chiết khấu/nl — nhưng bản đó CHƯA được xác nhận; cần vòng 3 (DEV rồi một lần xác nhận mới).

## R2.5 CPU mỗi bước (máy dev, tải nền ~5–9, `research/algo_timing.txt`, seed 93)

| cấu hình | numpy TB / p99 (ms) | bản C TB / p99 (ms) |
|---|---|---|
| C1 | 8,6 / 10,9 | 7,5 / 9,6 |
| B1 | 8,7 / 12,1 | 7,4 / 9,5 |
| PGIF\* | 9,1 / 11,1 | 8,5 / 10,7 |
| DRA\* | 9,2 / 12,7 (bước đầu 205 ms dựng bảng) | 6,9 / 8,6 |
| B0 | 9,2 / 11,2 | 6,4 / 7,8 |
| C3 (occ) | 10,7 / 14,1 | 7,0 / 9,8 |

Mọi cấu hình < 40 ms. Chưa đo trên Jetson.

## R2.6 Hạn chế / chưa chắc
- Toàn bộ là fastsim; Spearman với 960 lượt Gazebo: champ 0,90, champ2 0,59 (khác biệt không có ý nghĩa) → chỉ báo theo từng chế độ, không khẳng định chế độ nào "đúng".
- Ưu thế so với PGIF/DRA phụ thuộc mô hình người (hoà ở helb). Người mô phỏng rẽ nhiều hơn người thật (THÖR) ~1,7×.
- PGIF/DRA là bản cài lại theo công thức, có lệch (2 đĩa, thang trọng số, P tính giải tích thay MC, bỏ MoG theo mode của DRA): reviewer có thể đòi bản chạy mã gốc.
- Ngân sách chỉnh: p3 35, PGIF 35, DRA 35, mppi 31 (+8 dev3 của coordinator).

---
# Vòng 3 (24/11) — PHẦN ĐĂNG KÝ TRƯỚC (ghi lúc ~07:10 24/11, TRƯỚC khi chạy xác nhận seed 1500–1999)

Mục tiêu: ứng viên **đơn giản nhất không kém C1**. Mọi ứng viên dùng `~t3`.
- C4 = MPPI + `prim` (tắt geo, tắt grad, không chiết khấu): `p3-haz-grad~t3:...` (không `~nl`) và `p3-haz-grad~t3~nl:...` (có `~nl`).
- C5 = C4 + geo (rủi ro CV có chiết khấu, như C1): `p3+geo-haz-grad+gcv~t3:...` (không `~nl`).
- C1 = `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5` (đã khoá).
DEV: seed 800–999 crowd-only, 3 ô (champ2 base, go2 base, champ2 helb), ≤ 10 cấu hình mỗi lớp (danh sách: `research/algo_stage4.sh`).
Chọn biến thể đại diện mỗi lớp = tỉ lệ thành công gộp 3 ô DEV cao nhất (hoà → ppl nhỏ hơn).

Quy tắc chọn (áp dụng trên seed xác nhận 1500–1999, 5 ô như vòng 2, chạy MỘT lần):
1. Với mỗi ứng viên X ∈ {C4 không nl, C4 có nl, C5}: Δ = thành công gộp(X) − gộp(C1), KTC 95 % bootstrap theo thế giới (`research/algo_noninf.py`, 20 000 lần).
2. Chọn X **đơn giản nhất** có cận dưới KTC > −2,0 điểm. Thứ tự đơn giản: C4 không nl < C4 có nl < C5 < C1. Không ai đạt → giữ C1.
3. Báo thêm (không dùng để chọn): ứng viên được chọn so với B1, PGIF\*, DRA\* (cấu hình như vòng 2), McNemar từng ô + hoán vị gộp, Holm trong họ này.
Sau đó DỪNG phát triển; coordinator chạy VAL.
- (07:20) Thêm tag tuỳ chọn `~cs` (CmdShaper của ISAAC, isaac_val/cmd_shaper.py) trước `_twist`; không thuộc chọn ứng viên. Kiểm tương thích: 12/12 lượt cũ giống từng số; C1 không ~cs giống từng số.
- DEV vòng 3 (seed 800–999, 138 thế giới × 3 ô = 414 cặp; C1 = 82,4 % gộp). Đại diện mỗi lớp, chọn theo quy tắc (07:36 24/11, TRƯỚC khi xác nhận):
  - C4 không nl: `p3-haz-grad~t3:ppl=64;ppl_len=0.5` 76,3 % (5 biến thể: 70,3–76,3)
  - C4 có nl: `p3-haz-grad~t3~nl:ppl=100;ppl_len=0.5` 79,0 % (3 biến thể: 74,4–79,0)
  - C5: `p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5;g_tau=99` 84,5 % (3 biến thể: 79,2–84,5; +37/−28 so với C1 trên DEV)

# Vòng 3 (24/11) — KẾT QUẢ (seed 1500–1999, một lần, 357 thế giới/ô, 5 ô)
Bảng: `research/algo_noninf3.txt`, `research/algo_confirm3.txt`, `research/algo_confirm3_C1.txt`; thư mục `results/algo_Y*`.

| cấu hình | champ | champ2 | go2 | champ2 helb | go2 helb | gộp |
|---|---|---|---|---|---|---|
| **C1** `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5` | 84,6 | 79,3 | 90,2 | 82,4 | 90,8 | **85,4** |
| C5 `p3+geo-haz-grad+gcv~t3:ppl=32;ppl_len=0.5;g_tau=99` | 82,9 | 78,2 | 87,1 | 83,5 | 91,3 | 84,6 |
| C4 có nl `p3-haz-grad~t3~nl:ppl=100;ppl_len=0.5` | 78,7 | 70,0 | 84,0 | 77,9 | 88,2 | 79,8 |
| C4 không nl `p3-haz-grad~t3:ppl=64;ppl_len=0.5` | 77,0 | 72,0 | 86,3 | 74,5 | 89,1 | 79,8 |
| DRA\* | 77,3 | 75,9 | 88,0 | 80,7 | 91,3 | 82,6 |
| PGIF\* | 77,6 | 73,9 | 81,8 | 75,9 | 87,7 | 79,4 |
| B1 `mppi~t3~nl:ppl=100;ppl_len=0.5` | 75,6 | 73,1 | 79,6 | 76,8 | 86,3 | 78,3 |

**Áp quy tắc đăng ký trước (không-kém, cận dưới KTC 95 % > −2,0 điểm):**
- C4 không nl: −5,66 [−7,79; −3,59] → không đạt.
- C4 có nl: −5,66 [−7,62; −3,70] → không đạt.
- C5: −0,84 [−2,69; +0,95] → **không đạt** (cận dưới −2,69, sát ngưỡng).
- → **Giữ C1.** Thiết kế đóng băng: `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5`.

**C1 so với baseline trên seed vòng 3** (họ 18 phép so, Holm; KTC bootstrap theo thế giới):
- C1 − B1: **+7,2** [+5,0; +9,4], Holm 0,0002 (từng ô +4,5 … +10,6; go2 và champ có ý nghĩa sau Holm).
- C1 − PGIF\*: **+6,1** [+3,9; +8,2], Holm 0,0002.
- C1 − DRA\*: **+2,8** [+1,0; +4,7], p 0,004, Holm 0,047 (không ô nào riêng có ý nghĩa; go2 helb −0,6).

**Lặp lại qua 3 bộ seed xác nhận độc lập:** C1 − B1 = +5,7 (300–799), +6,6 (1000–1499), +7,2 (1500–1999); C1 − DRA\* = +3,2 rồi +2,8; C1 − PGIF\* = +5,2 rồi +6,1.

**Diễn giải trung thực:**
- Trong C1, phần "MPPI + prim" một mình (C4) **không đủ**: thiếu rủi ro geo thì mất ~5,7 điểm. Điều này khác với ablation vòng 2, nơi bỏ geo chỉ −2,2 (n.s.). Lý do: ở vòng 2, bỏ geo vẫn giữ lại grad; còn C4 bỏ cả grad.
  Vậy geo và grad thay thế được cho nhau một phần. Đây là suy đoán: chưa chạy bản C4 + grad trên seed xác nhận.
- C5 (geo, không grad, không chiết khấu, không nl) gần bằng C1 (−0,8) nhưng không chứng minh được là không kém → theo luật, giữ C1.
- `~nl` không đổi gì cho C4 (79,8 = 79,8). Không có bằng chứng `~nl` có ích hay có hại trong thiết kế p3. ISAAC xác nhận nó không gây ngã.
- DỪNG phát triển theo PLAN §00. VAL (2000–2399) do coordinator chạy trên C1.
