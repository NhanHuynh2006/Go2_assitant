# REPORT_HM95: mô hình người Helbing–Molnár 1995 cài trung thành ("hm95") — nhánh THĂM DÒ, chạy sau khi đã có kết quả TEST

> Coordinator lưu lại từ báo cáo bàn giao của agent HM95, ngày 25/11. Agent bị chặn ghi file .md; người dùng đã cho phép lưu báo cáo của agent.
>
> Coordinator kiểm độc lập lúc 18:45:
> - Tính lại tỉ lệ thành công và McNemar từ `results/TEST_hm95_{go2,champ2}`: khớp từng số với §4.
> - `SHA256SUMS_SNAP` khớp. Thư mục `results/frozen_C1/snap/results/` (do agent ghi nhầm vào lúc đầu) không còn.
>
> Nhánh này KHÔNG thay kết quả đăng ký nào (FROZEN.md, PREREG_TEST, `research/TEST_fastsim_results.txt`). Agent không sửa file đóng băng nào, không chạm robot thật, Gazebo hay `results/GZ_*`.

## 1. Khác nhau giữa 'helb' và 'hm95'

Nguồn: toàn văn HM1995 (arXiv cond-mat/9805244), phương trình (1)–(13) và đoạn tham số.

| Thành phần | `helb` (crowd_models.py, đóng băng) | `hm95` (crowd_hm95.py) = HM95 |
|---|---|---|
| Lực đẩy người–người | Tròn, theo **khoảng cách mặt**: 7·exp((r_i+r_j−d)/0.3)·n̂ | Thế **elip** V = V0·exp(−b/σ). Nửa trục nhỏ b theo (4): 2b = √((‖r‖+‖r−v_βΔt‖)² − (v_βΔt)²), Δt = 2 s, theo **khoảng cách tâm**. Lực f = −∇V tính giải tích |
| Độ mạnh (β đứng yên) | 7·e^{(0.44−d)/0.3} | 7·e^{−d/0.3}, **yếu hơn ≈ 4,33 lần** |
| Dị hướng | Liên tục: 0.35 + 0.65(1−n̂·e)/2 | Bậc thang: 1 trong góc 2φ = 200°, ngoài góc c = 0.5 |
| Lực tường | 2·exp((r−d)/0.12)·n | (U0/R)·exp(−d/R)·n, U0 = 10, R = 0.2. Không nhân trọng số w |
| Lực tiếp xúc cứng | Có | Tắt (HM95 không có) |
| Nhiễu | Gauss 0.15 | Không |
| τ, v_max | 0.5 s; 1.3 v0 | 0.5 s; 1.3 v0. Tích phân w rồi cắt theo (10)–(12) |
| Cập nhật | Tuần tự | Đồng thời |

**Giữ nguyên như helb:** logic đích, thời gian chờ, người distracted, dt 0.05 s, v0 ~ N(0.9, 0.15) cắt trong [0.6, 1.2], bán kính 0.22 m.

**Robot** được coi là một β có vận tốc riêng. Bán kính robot chỉ dùng để phát hiện va chạm.

**Ba lựa chọn tự đặt** (bài gốc không nói rõ):
1. e_β lấy theo vận tốc thực, không theo hướng mong muốn.
2. Lực tường không nhân w.
3. Giữ Δt = 2 s, dù khi đó s_β ≈ 1,8–2,7 m, lớn hơn nhiều so với "cỡ bước chân" mà bài mô tả.

## 2. Kiểm tra hợp lý

**Gradient:** sai số tương đối lớn nhất 6,6e-9, trên 1995 cặp điểm.

**Hai người đi ngược chiều nhau:**
- Lệch ngang 0,05 m: tránh được nhau, khoảng cách tâm nhỏ nhất 0,61 m.
- Lệch ngang 0,3 m: khoảng cách tâm nhỏ nhất 0,72 m.
- Đối xứng tuyệt đối: kẹt mặt đối mặt. Điều này đúng như dự kiến vì mô hình tất định, không có nhiễu.

**Hành lang ngược chiều: KHÔNG tạo lane.** Thiết lập: tuần hoàn, 40 × 10 m, 0,3 người/m², v0 ~ N(1,34; 0,26). Đo mức tách lane Φ qua các dải ngang 0,5 m, so với giá trị null khi xáo nhãn hướng đi:

| Biến thể | Φ | Null | Có lane? |
|---|---|---|---|
| hm95 (Δt = 2 s) | 0,322 / 0,332 | 0,30 | không |
| w := v | ≈ 0,30 | 0,30 | không |
| V0 × 4,33 | ≈ 0,30 | 0,31 | không |
| Δt = 0,5 s | ≈ 0,50 | 0,30 | yếu |
| Δt = 0 (tròn) | 0,749 / 0,662 | 0,29 | có |
| helb | 0,752 / 0,645 | 0,31 | có |

- Nguyên nhân dập tắt lane là elip với Δt = 2 s (dùng vận tốc thực), không phải độ mạnh của lực.
- Chưa rõ đây là do chi tiết trong mô phỏng gốc của HM hay do cách tái hiện. Agent không chỉnh mô hình theo kết quả này.
- Hệ quả: hm95 tạo ra đám đông "yếu, nhìn xa". Người phanh sớm, ít né ngang, và chồng lấn nhau ≈ 0,38 % số cặp-bước.

**Ổn định số, không cần lực tiếp xúc:** trên ≈ 9,6 triệu bước đám đông có 0 lần tâm người lọt vào vật và 0 giá trị không hữu hạn.

**Wrapper:** `research/hm95_fastsim.py` vá cả tiến trình cha lẫn worker. Chạy `helb` qua wrapper cho kết quả trùng từng bit với fastsim gốc (14 thế giới DEV).

## 3. Chạy

- **DEV smoke:** 20 seed, 0 EXC, khoảng 8 s CPU mỗi lượt.
- **Sự cố:** smoke đầu tiên ghi nhầm vào snap vì dùng đường dẫn tương đối. Agent đã chuyển ra ngoài, kiểm lại sha snap (OK) và sửa wrapper sang đường dẫn tuyệt đối.
- **TEST:** seed 100000–101386 crowd-only, 1000 thế giới, chạy trên lõi 10, 11, 14, 15 với nice 19.
  - go2: 14:21–16:24.
  - champ2: 16:24–18:45.
  - 0 EXC.

## 4. Kết quả (THĂM DÒ, n = 1000 mỗi ô)

| Cấu hình | go2/hm95 | champ2/hm95 | go2/helb | champ2/helb |
|---|---|---|---|---|
| C1 | **80,3** [77,7; 82,6] | **66,9** [63,9; 69,7] | 90,9 | 83,5 |
| B1 | 76,8 | 59,7 | 89,1 | 76,8 |
| PGIF* | 73,2 | 60,7 | 89,5 | 80,8 |
| DRA* | 80,8 | 62,2 | 90,1 | 80,0 |

| Phép so (McNemar, Holm 3 mỗi ô) | go2/hm95 | champ2/hm95 | Gộp (hoán vị dấu, Holm 3) |
|---|---|---|---|
| C1 − B1 | +3,5 (117/82), Holm 0,031 | +7,2 (167/95), Holm 3e-5 | +5,35 [3,25; 7,45] |
| C1 − PGIF* | +7,1 (141/70), Holm 3,5e-6 | +6,2 (157/95), Holm 2,3e-4 | +6,65 [4,55; 8,75] |
| C1 − DRA* | −0,5 (81/86), p 0,76 | +4,7 (140/93), Holm 0,0025 | +2,10 [0,15; 4,00], Holm 0,037 |

- **Thất bại gần như toàn là va chạm với người.** hm95 khó hơn helb, tỉ lệ thành công thấp hơn 10–17 điểm.
- **So khớp từng thế giới với helb/base:**
  - Trùng kết quả 72–80 %, nhưng κ chỉ 0,14–0,29.
  - Chênh lệch C1 so với baseline theo từng thế giới gần như không tương quan (r ≈ 0).
  - Nghĩa là kết quả chỉ giữ ở dấu và độ lớn trung bình, không giữ ở mức từng thế giới.

## 5. Kết luận (THĂM DÒ)

- **C1 > B1:** GIỮ ở cả hai ô.
- **C1 > PGIF\*:** GIỮ ở cả hai ô.
- **C1 ≈ DRA\*:** GIỮ ở go2. Ở champ2, C1 hơn DRA\* (+4,7), cùng chiều với champ2/helb và champ2/base.
- Không có kết luận nào bị đảo dấu.

## 6. Chưa chắc và hạn chế

- Đây là phân tích làm sau khi đã có kết quả, trên các seed TEST, nên p chỉ để tham khảo.
- Bản tái hiện không tạo được lane, tức là trung thành với phương trình nhưng chưa trung thành với hành vi bài báo mô tả.
- Phần còn lại của đám đông vẫn theo fastsim:
  - v0 ≈ 0,9 m/s;
  - đích ngẫu nhiên;
  - 30 % người distracted.
- Chưa chạy độ nhạy cho các lựa chọn cài đặt 1–3 ở mục 1.

## 7. Đề xuất

- Đưa vào bài một câu kiểm tra độ bền, ghi rõ là post-hoc và ghi rằng bản tái hiện không tạo lane.
- Có thể chạy độ nhạy với Δt ∈ {0,5; 2} s và e_β theo hướng mong muốn.

## File

**Mã:**
- `crowd_hm95.py`
- `research/hm95_fastsim.py`
- `research/hm95_test.sh`
- `research/hm95_sanity.py`
- `research/hm95_lanes.py`
- `research/hm95_analyze.py`

**Kết quả:**
- `results/TEST_hm95_{go2,champ2}`
- `results/DEV_hm95_smoke_*`
- `results/hm95_sanity/`
- `results/hm95_analysis.txt`
- `results/hm95_code.sha256`
- `results/hm95_test_driver.log`

**Nhật ký:** 17 dòng trong LOG.csv, agent = HM95.

## 8. Bổ sung lúc 19:20: lane khi dùng hướng/tốc độ MONG MUỐN; quyết định về TEST hm95b (THĂM DÒ)

**Cách làm.** Tạo `crowd_hm95b.py`, chỉ khác hm95 ở phương trình (4):
- e_β là hướng mong muốn (tới điểm đường đi kế tiếp); v_β = v0_β; Δt = 2 s.
- Người đang chờ được tính bước = 0. Robot vẫn dùng vận tốc thực.

Script: `research/hm95b_lanes.py`. Biến thể và thước đo cố định trước khi chạy:
- Mật độ 0,3/m²; hành lang 40 × 10 m; v0 ~ N(1,34; 0,26); T = 120 s.
- Φ lấy trung bình trên t = 30–120 s. Riêng (b) chỉ tính trên đoạn x ∈ [5, 35].
- (c) thêm nhiễu σ = 0,15.

**Kết quả** (giá trị viết theo seed 1 / seed 2):

| Biến thể | Φ | null | Φ − null | lane? |
|---|---|---|---|---|
| (a) hướng/tốc độ mong muốn, tuần hoàn | 0,374 / 0,342 | 0,303 / 0,300 | +0,071 / +0,042 | không |
| (b) (a) + người vào lại ở hai đầu | 0,405 / 0,418 | 0,352 / 0,354 | +0,053 / +0,063 | không |
| (c) (a) + nhiễu 0,15 | 0,350 / 0,349 | 0,302 / 0,304 | +0,048 / +0,045 | không |
| Đối chứng dương: Δt = 0, thế tròn (không phải ứng viên) | 0,749 / 0,662 | 0,288 / 0,292 | +0,461 / +0,370 | có |

- **Chồng lấn:** 4,8–7,7 cặp/khung ở ba biến thể, so với 2–3 cặp ở đối chứng.
- **Thước đo hoạt động đúng:** đối chứng dương cho Φ − null = 0,37–0,46.
- **Nguyên nhân mất lane không phải lựa chọn "vận tốc thực".** Lane mất do chính thế elip Δt = 2 s với V0 = 2,1 và σ = 0,3: thế này chủ yếu hãm người theo hướng đi, ít đẩy ngang.
- **Hình 2–3 của HM95 vẫn chưa tái tạo được.** Chưa phân định được nguyên nhân là một chi tiết bài báo không nêu, hay chính phương trình (4) với Δt = 2 s.

**Quyết định về TEST hm95b: KHÔNG chạy.** Quy tắc định trước là chạy biến thể đầu tiên đạt Φ − null ≥ 0,2 ở cả 2 seed; không biến thể nào đạt.

**Kết luận chung không đổi so với §5.**

> **Ghi chú coordinator.** Kết luận C1 > B1 và C1 > PGIF* giữ trên ba mô hình người khác nhau:
> - base;
> - helb: thế tròn, CÓ tạo lane, Φ − null ≈ 0,35–0,44;
> - hm95: thế elip, đúng phương trình nhưng không tạo lane.
>
> Tức là kết luận vững cả với đám đông có lane lẫn đám đông không có lane. Không theo đuổi thêm biến thể HM ngoài bài báo.
