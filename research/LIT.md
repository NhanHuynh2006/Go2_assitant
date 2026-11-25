# LIT — khảo sát tài liệu cho bài toán "robot chậm hơn người, người rẽ muộn" (22/11/2026)

Agent LIT. **Không chạy mô phỏng nào** (không thêm phép thử cho Holm). Chỉ có 2 phép tính ngoại tuyến gọi thẳng
`PRISM2.turn_cost` trên trạng thái ngẫu nhiên (mục 1.3), không dùng seed nào của DEV/VAL/TEST.

Ký hiệu mức đọc: **[TV]** = tải bản HTML/PDF và đọc phần phương pháp + thí nghiệm (nguyên văn, có thể bỏ phụ lục);
**[MP]** = tải toàn văn, chỉ đọc tóm tắt, mở đầu và các đoạn liên quan; **[TT]** = chỉ tóm tắt hoặc trang thư mục.
Bài năm 2026 phần lớn là arXiv chưa phản biện — ghi "preprint".

---
## 0. Kết luận ngắn

1. **`turn_cost` chưa đủ mới để đứng một mình làm đóng góp chính.** Không tìm thấy bài nào có *đúng* tổ hợp của nó,
   nhưng từng mảnh đều đã có: hình nón nguy hiểm có trọng số góc, closed-form, trong MPPI (PGIF 2026); "TTC so với thời
   gian cần để đánh lái" (BTN/STN, ô tô, 2010); "người mất chú ý + vật tĩnh chặn đường lách" (CDC 2022); elip vận tốc
   dị hướng của chó (2024); thư viện chính sách lách có xét phòng trú (PL-CBF 2026).
2. **Số của chính mình cũng ủng hộ điều đó.** Phần "khả năng từng trục" gần như vô tác dụng trên Go2/CHAMP: 2 trục đều
   ~0.29 m/s nên elip là **hình tròn**. Bản rút gọn (TTC + trọng số góc, thời gian lách là **hằng số**) xếp hạng mẫu
   giống bản đầy đủ: Spearman trung vị 0.85 (chỗ trống, không tường). **Ablation bắt buộc: `turn` so với `turn_const`.**
3. **Khoảng trống thật, có lý do vật lý:** các bài có bảo đảm đều cần robot nhanh ít nhất bằng người hoặc dừng được là
   an toàn. CDC 2022 viết thẳng giả thiết `v_e >= v_p`. Với ta 0.29 < 0.9 thì tập "chắc chắn né được" trong trường hợp
   xấu nhất gần như rỗng → phải làm bài toán **né xác suất, có hồi tiếp, tầm hữu hạn**. Đó là chỗ nên đặt đóng góp (Ý tưởng A).
4. **Trước khi phát minh thêm, phải đo trần.** Tính tay: cần ~1.8 s (người tới dọc thân, lách ngang) tới ~2.6 s (người tới
   ngang hông) để ra khỏi hành lang nếu bị nhắm **chính tâm**. Người rẽ ~2 s trước khi chạm, nên một phần các lần chạm
   có thể **không né được bởi bất kỳ thuật toán nào**. Chưa biết phần đó bao nhiêu.

---
## 1. Tính mới của "biên né có xét khả năng rẽ" (`turn_cost`)

### 1.1 Từng bài gần nhất
| Bài | Đọc | Họ làm gì | Trùng với ta | Khác ta |
|---|---|---|---|---|
| **PGIF-MPPI**, Mundane, [2608.08323](https://arxiv.org/abs/2608.08323) (8/2026, preprint) | TV | Gauss dị hướng quanh người dự đoán ở từng bước rollout: phía trước `1.2+0.5s`, sau 0.5, ngang 0.6 m. Closed-form, trong MPPI, chạy song song | **Gần nhất về vai trò**: "phạt đứng trong nón phía trước người, dài theo tốc độ, closed-form trong MPPI" | Không có khả năng robot, không có thân, không có tường. Robot 2 m/s, hành lang trống. Đối chứng chỉ là MPPI coi người đứng yên (yếu) |
| **BTN/STN**, Brännström, Coelingh, Sjöberg, [T-ITS 2010](https://research.chalmers.se/en/publication/144746); tổng quan [Westhofen 2108.02403](https://arxiv.org/abs/2108.02403) | TT | Vật bất kỳ, thân chữ nhật: tài xế còn phanh/lái/tăng tốc kịp không, tính giải tích | **Gần nhất về ý niệm**: so thời gian còn lại với thao tác lách khả thi, có hình dạng thân | Ô tô, không có MPPI, không có phân bố góc rẽ của người |
| **Wang, Nielsen, Smith, CDC 2022** [PDF](https://ece.uwaterloo.ca/~sl2smith/papers/2022CDC-Pursuit_Evasion.pdf) | TV | Trò chơi "suicidal pedestrian" + 1 vật tĩnh. "Kill zone" giải tích, **đường lách mặc định bị vật tĩnh chặn** thì lách sớm hơn; người mất chú ý, xấu nhất | Đúng bộ ba: người mất chú ý + đường lách + tường chặn, closed-form | Giả thiết `v_e >= v_p` (mô phỏng 1 và 0.6), Dubins, điểm tròn, 1 người, bộ điều khiển theo sự kiện. Đối thủ xấu nhất, không có xác suất rẽ |
| [Suicidal pedestrian](https://econpapers.repec.org/RePEc:spr:dyngam:v:5:y:2015:i:3:p:297-317), Exarchos et al., DGAA 2015 | TT | Lời giải đầy đủ trò chơi gốc | Nền lý thuyết | Không có tường, không có MPPI |
| **Contingency-MPPI**, Jung, Estornell, Everett, L4DC 2025 [2412.09777](https://arxiv.org/abs/2412.09777) | TV (phương pháp) | Từ **mỗi** trạng thái của nominal phải có đường tới **tập an toàn cho trước S** trong Tc bước; MPPI lồng MPPI | Ý "mỗi trạng thái dự đoán phải còn đường thoát" | S cố định và tĩnh. Đề cập agent động chỉ ở phần liên quan. Đắt (lồng) |
| **SCRAMPPI**, Srirangam et al., [2603.26995](https://arxiv.org/abs/2603.26995) (v2 9/2026, preprint) | TV | Thay tìm lồng bằng tra hàm giá trị HJ reach-avoid; resampling trong nhóm; 15–20 Hz GPU | Tra giá trị "còn thoát được không" cho mọi trạng thái rollout | Mục tiêu hồi phục do nhiệm vụ đặt, môi trường tĩnh đang lộ dần, **không có người**. Docstring `nav_prism2.py` mô tả đúng nhưng nên ghi thêm điểm này |
| **DualGuard-MPPI** [2502.01924](https://arxiv.org/abs/2502.01924); ReSQ-MPPI [2610.04406](https://arxiv.org/abs/2610.04406) (preprint) | MP | HJ lọc rollout + lọc đầu ra | Giá trị an toàn offline trong MPPI | Bảo đảm cho vật có mô hình; không xét đối thủ nhanh hơn |
| **PL-CBF**, Kim et al., [2605.16588](https://arxiv.org/abs/2605.16588) (v2 11/2026, preprint) | MP | Lọc an toàn bằng **thư viện chính sách lách** (dừng, lùi, 12 hướng, **vào phòng trú**) rollout song song tầm hữu hạn | Lách nhiều phía, có tường, tầm hữu hạn, CPU vài ms, có thử người đi bộ | Lọc lệnh hiện tại (QP), không chấm mọi trạng thái rollout; người dự đoán xác định |
| **CoCoNav** [2608.07751](https://arxiv.org/abs/2608.07751) (8/2026, preprint) | MP | Conformal PI theo tầm + MPC mềm rồi **kiểm tra nominal và thư viện dự phòng** (giữ, chậm, phanh thẳng/rẽ). Chó 4 chân thật | Dự phòng + bất định người, chó 4 chân | Không lách ngang chủ động, không xét tường trong đường lách, bán kính đẳng hướng |
| **DRA-MPPI**, Trevisan, Mustafa et al., [2506.21205](https://arxiv.org/abs/2506.21205) | TV | Xác suất va đồng thời, phân bố không Gauss, MC dùng chung; **đã có người rẽ ngẫu nhiên** (Markov thẳng → chéo, p=0.025 mỗi bước, MoG 4 mode) | Đã xử lý "người có thể rẽ" trong MPPI; báo cáo 98–100 % so với 43–86 % của vanilla | Vòng hở: không tính robot sẽ **thấy người rẽ rồi phản ứng**. Robot 2 m/s nhanh hơn người; hành lang rộng 6 m; bán kính tròn |
| **C2U-MPPI**, Mohamed, Ali, Liu, RA-L 2025 [2501.08520](https://arxiv.org/abs/2501.08520) | MP | Chance-constraint dạng tất định: `Pr≈A_r/sqrt(det 2πΣ)·exp(−½ dᵀΣ⁻¹d)`; có chế độ **không hợp tác (NCM)** | NCM là giao thức tham chiếu tốt | CV + Gauss, đẳng hướng, robot ≥ 1 m/s, 10 lượt mỗi ô |
| **Risk-aware MPPI hệ lai ngẫu nhiên**, Parwana et al., [2411.09198](https://arxiv.org/abs/2411.09198) | TV (đến hết mô phỏng) | Người đổi mode theo vùng chú ý; UT truyền bất định | Nêu đúng "sudden changes in direction" và mode chú ý/không | Đổi mode phụ thuộc robot, không phải rẽ ngẫu nhiên; vòng hở; không tường chặn lách |
| **DS-MPEPC** [2303.10133](https://arxiv.org/abs/2303.10133) | TV (cost) | Xác suất va giảm theo TTC; chi phí cuối gồm time-to-goal và TTC | TTC trong cost | **Không phải MPPI** (là MPEPC) và TTC chỉ để *giảm* bảo thủ. Giả thiết vận tốc không đổi. Nhãn "MPPI terminal cost TTC/ICS" trong đề bài là chưa đúng |
| **FutureRay** [2609.32158](https://arxiv.org/abs/2609.32158) (9/2026, preprint) | TV | Học dự đoán tầm nhìn tương lai 0.5 s + giới hạn phản ứng–phanh; chó 4 chân; 93.3/75/80 % trên 60 cảnh | Có footprint, phản ứng, chó | Cần huấn luyện; robot 1.9 m/s; phanh chứ không lách khỏi người nhanh hơn |
| **Dị hướng của chó**, Zhang et al., [2403.10101](https://arxiv.org/abs/2403.10101) | MP | Elip vận tốc tối đa theo hướng thân | Đúng elip `1/sqrt(cd²/ax²+sd²/ay²)` | Không có người. → không được nhận elip là mới |
| **Stochastic reachable set + APF**, Chiang, Malone, Lesser, Oishi, Tapia, [T-RO 2017](https://archive.cps-vo.org/node/50417) | TT | SR set tính trước cho vật động ngẫu nhiên/lai, tra khi chạy để tạo lực đẩy | **Gần nhất với Ý tưởng A** | Trường thế; theo tóm tắt không có thân dài, tường, MPPI. **Phải đọc toàn văn trước khi viết** (tải PDF bị lỗi) |
| **MPPIPS-HWP**, Long, Bardaro, Matteucci, [ROBIO 2025](https://re.public.polimi.it/handle/11311/1309792) | TT (trang trả 403, chỉ thấy qua kết quả tìm kiếm) | MPPI + STGN-S dự đoán + chính sách cảnh báo bằng âm thanh | MPPI + người | Hướng khác (dự đoán học + cảnh báo). **Không xác nhận được chi tiết cost** |
| **T-MPC++** [2401.06021](https://arxiv.org/abs/2401.06021) (T-RO) | MP | Nhiều lớp đồng luân song song, chọn nhất quán | Giống cờ `mode` | `mode` đã đo: không lợi (58–65/101) |
| **OA-MPC / FRS** [2211.09156](https://arxiv.org/abs/2211.09156) | MP | Tập tới được xấu nhất của người khuất + điều kiện **dừng ở cuối** | Tập tới được | Dừng = an toàn; với người mất chú ý thì đứng yên vẫn bị va |
| **Maximin ở trạng thái tới hạn**, Lo et al., [ICRA 2021](https://utw10730.utweb.utexas.edu/static/papers/ICRA21a_shihyun.pdf) | MP | Chỉ dùng xấu nhất gần lúc va | Giống "chỉ lo khi TTC < thời gian lách" | Robot 0.8, người 1.0 m/s: chậm hơn một ít, không phải 3 lần |
| Passive safety / Braking-ICS, Bouraine, Fraichard, Salhi, [AURO 2012](https://www.doi.org/10.1007/S10514-011-9258-8) | TT | Nếu có va thì robot phải đang đứng yên | Cơ sở cho metric at-fault | Không chống được người tự va |
| RA-CBF, Cosner et al., [ICRA 2023, 2303.03504](https://arxiv.org/abs/2303.03504) | TT | Chia trách nhiệm né học từ dữ liệu | Khái niệm trách nhiệm | Ô tô |
| **VOP-Nav** [2607.15036](https://arxiv.org/abs/2607.15036) (7/2026, preprint, **Go2 thật**) | MP (phần baseline) | Học vùng vận tốc an toàn VO từ LiDAR; so ORCA (trách nhiệm = 1), NavRL, HEIGHT, REASAN, ABS | Chó + người không hợp tác | End-to-end khớp, 2–3 m/s |
| **Go2 + video policy** [2609.37476](https://arxiv.org/abs/2609.37476) (2026, preprint, Go2 thật) | MP | Nav2-MPPI 8/20, policy 19/20; "MPPI giữ hướng tới khi người vào costmap → né muộn" | Bằng chứng độc lập, cùng robot, cùng hiện tượng né muộn | Học |

ORCA/VO, HJ, FRS theo nghĩa chung: là trường hợp "vận tốc không đổi" (VO) hoặc "xấu nhất" (HJ/FRS); `turn_cost` nằm giữa.

### 1.2 Phán quyết
- **Không được viết:** "biên né đầu tiên", "closed-form đầu tiên trong MPPI", "dị hướng của chó là mới", "xét tường chặn lối lách là mới".
- **Có thể viết (hẹp, đúng):** trong các bài đã khảo sát, chưa thấy bài nào chấm **mọi trạng thái rollout** của MPPI bằng
  biên [TTC tới khi người rẽ thẳng vào] − [thời gian lách theo thân dài + phía bị chặn], có trọng số hợp lý góc rẽ, **khi robot chậm hơn người 3 lần**.
  Đây là tổ hợp, reviewer sẽ gọi là incremental nếu thiếu (i) ablation từng mảnh và (ii) thắng PGIF + baseline chỉnh.
- Hiện số DEV chưa tách được khỏi baseline chỉnh: 65–66/101 so với `ppl=32` 64/101 (xem LOG.csv).

### 1.3 Tự kiểm tra rẻ (ngoại tuyến, không phải sim)
500 (bản rút gọn) và 400 (bản khoảng cách) tình huống ngẫu nhiên, 300 rollout, 1 người 0.9 m/s cách 1–3.5 m, lệch hướng ±1.2 rad, không tường,
gains theo sysid (0.29/0.97/0.85), tau 0.25. Spearman giữa `turn_cost` và hàm khác, **trong từng tình huống**:

| So với | Trung vị | IQR |
|---|---|---|
| TTC + trọng số góc, thời gian lách **hằng số** 2.1 s (bỏ trục, bỏ thân, bỏ tường) | **0.85** | 0.67–0.96 |
| như trên, bỏ trọng số góc | 0.40 | 0.17–0.61 |
| cost khoảng cách của MPPI (`ppl`), cả len 0.3 / 0.6 / 1.0 | 0.48 | 0.29–0.67 |

→ Thứ hạng mẫu chủ yếu do **TTC + trọng số góc** (tức nón dự đoán — PGIF đã có dạng gần); phần "khả năng" chỉ xếp lại ít. **Nhưng** `turn` không phải
cost khoảng cách trá hình (0.48). Giới hạn: phân bố trạng thái bịa, không tường, xếp hạng mẫu chứ không phải kết quả vòng kín.

Thời gian lách nếu bị nhắm chính tâm (rad 0.25, lề 0.05, tau 0.25, v 0.29):
lách vuông góc thân **1.83 s**; 60° 2.39 s; 45° 2.57 s; dọc thân (người tới ngang hông) **2.56 s**. Quay 90° mất ≥ 1.85 s.
Horizon hiện tại 2.4 s, `turn_cost` chỉ nhìn 2 s → **ngắn hơn thời gian lách ở hướng xấu**. Quán tính nhỏ (tau 0.15–0.25 s)
nên "robot vẫn đi hết tốc độ" **không** tự nó là nguyên nhân; vị trí và góc thân mới quyết định. (Suy luận, chưa đo.)

---
## 2. Ý tưởng thuật toán (xếp theo kỳ vọng lợi ích / công sức)

### Bước 0 (bắt buộc, ~0.5 ngày, không phải đóng góp): trần và hai ablation
- **Trần A (oracle hiện tại):** đã có `dev*_oracle`. DEV2: p2 70→80/100 khi biết người, mppi 69→70. Chưa kiểm định; nếu thật thì
  cảm biến chỉ đáng sửa khi bộ lập biết dùng.
- **Trần B (oracle tương lai):** đưa quỹ đạo người thật 3 s tới (sao chép trạng thái SFM, coi robot đi thẳng) vào MPPI gốc. Nếu
  trần B chỉ hơn baseline chỉnh < 8 điểm thì **mọi ý A–E không thể có kết quả đáng viết** → đổi câu hỏi nghiên cứu.
- **`turn_const`** và **`pgif`** cùng ngân sách chỉnh với `turn`.

### A. Giá trị né ngẫu nhiên có hồi tiếp cho kẻ né CHẬM hơn (Stochastic Evasion Value, SEV) — nên làm trước
- **Nguồn:** stochastic reachability (Chiang/Malone T-RO 2017 [TT]), HJ trong MPPI (SCRAMPPI, DualGuard), suicidal pedestrian (CDC 2022).
- **Mới so với gần nhất:** (1) không xấu nhất: người là quá trình **đổi hướng có tần suất rẽ** (hazard) đo từ dữ liệu, vì xấu nhất vô nghĩa khi v_r < v_h;
  (2) robot **thấy rồi phản ứng** (quy hoạch động với hồi tiếp + trễ 0.2–0.3 s) thay cho vòng hở của DRA-MPPI; (3) thân dài + động học
  bão hoà đo được; (4) tra trong từng trạng thái rollout MPPI.
- **Vì sao hợp số đo:** 21–48 % hướng vào ở −2 s ⇒ rủi ro nằm ở sự kiện rẽ, không ở quỹ đạo trung bình; inertia nhỏ ⇒ trạng thái robot chỉ cần (vị trí, yaw).
- **Cài:** lưới (r 40 × bearing 36 × hướng người 36) × 3 tốc độ; 27 hành động thân; 8 góc rẽ; 30 bước 0.1 s → V = P(chạm trong 3 s | né tốt nhất).
  Ước tính (chưa đo) ~1e9 phép nội suy: vài giây tới 1–2 phút offline trên GPU, vài phút numpy. Tường: thêm 1 chiều "hướng tường gần" (8 + không).
  Online: 600×8×N ≤ 5 tra bảng nearest/float32, ước ~1 ms; nhiều người: 1−∏(1−V_i) (gần đúng, ghi rõ).
  Không phải train thêm: DP trên mô hình đã đo.
- **Bác bỏ rẻ nhất (trước khi nối vào MPPI):** trên log DEV, tại −2 s và −1.5 s, AUC phân biệt "sẽ chạm / không" của V so với `turn_cost`, TTC,
  khoảng cách, PGIF. Không hơn (ΔAUC < 0.03, bootstrap) → bỏ. Nếu qua: fastsim DEV, ghép cặp.
- **Rủi ro:** hazard đo từ chính fastsim = học mô phỏng. Phải đo từ dữ liệu người thật (THÖR, ETH/UCY, TBD) hoặc để tham số và quét độ nhạy;
  giả thiết nhiều người độc lập; 1 chiều tường thô.

### B. Trường phơi và nơi nép (exposure / refuge) theo thời gian tới trên bản đồ
- **Nguồn:** OA-MPC/FRS; PL-CBF room-entry; [chờ ở vị trí không cản (ICSR 2015, TT)](https://core.ac.uk/display/103788944); CoHAN [2106.09971](https://arxiv.org/abs/2106.09971) [TT].
- **Ý:** T_h(x) = thời gian sớm nhất người tới x **đi vòng tường** (geodesic, có trễ rẽ). Với mỗi trạng thái: phần hướng mà người tới được
  trước khi robot lách xong (cùng công thức `m/v`) = "độ phơi". Cộng vào cost và làm đích trung gian tạm (nép cạnh tủ, hốc tường).
- **Mới:** chưa thấy "độ phơi theo thời gian lách" dùng trong MPPI; khác FRS ở chỗ tường **chắn** người chứ không chỉ chặn robot. Mức mới trung bình.
- **Hợp số đo:** tường hiện chỉ bị coi là xấu (phía lách bị chặn); nhưng tường cũng giảm số hướng người có thể tới.
- **Cài:** lưới cục bộ 8×8 m, 0.2 m (40×40); Bellman quét numpy ~40 lần/người (ước 2–4 ms/người), chỉ cho người < 4 m; tra như EDT.
- **Bác bỏ:** log DEV: tỉ lệ chạm / giây theo tam phân vị độ phơi. Không đơn điệu → bỏ.
- **Rủi ro:** trong sim người bị lực tường đẩy (B = 0.12) và A* lethal 0.30 → nép tường có thể lợi **giả tạo**; robot thật không chắc. Dễ đông cứng.

### C. Chuẩn bị hướng thân để lách (aspect control) — rẻ nhất
- **Nguồn:** VO cho robot dạng capsule (EPFL [RA-L 2021](https://infoscience.epfl.ch/record/284026/files/09385856.pdf) [TT]), dị hướng chó 2403.10101.
- **Ý:** thêm 2–3 họ mẫu MPPI (không chỉnh cost): (i) quay để trục thân trùng hướng mối đe doạ có xác suất rẽ cao nhất, (ii) bước ngang trái/phải
  0.29 m/s, (iii) lùi (đo được 1.26 × lệnh). `vmin[0] = −0.2`, phạt `fwd`/`lat` đang phạt đúng các thao tác né: cần **tắt có điều kiện khi có mối đe doạ** (kiểu near-goal Nav2), áp cho cả baseline.
- **Mới:** thấp–trung bình; đáng là thành phần của A (V phụ thuộc yaw).
- **Hợp số đo:** 1.83 s so với 2.56 s: chênh 0.7 s ở thân bề hẹp.
- **Bác bỏ:** trên log chạm, phân bố |bearing|: nếu phần lớn chạm ở mũi/đuôi (không phải hông) thì ý này vô ích. Có sẵn cột `bearing`, 10 phút.
- **Rủi ro:** quay tăng |wz|, nhiễu at-fault và chạm khi quét thân.

### D. Vết chưa xác nhận có xác suất tồn tại + trễ (existence-weighted risk)
- **Nguồn:** integrated-existence tracker ([2504.20526](https://arxiv.org/abs/2504.20526) [TT]); không tìm thấy bộ lập đám đông nào dùng vết chưa xác nhận.
- **Ý:** mỗi cụm nhỏ có xác suất là người p_e (LLR theo số khung, kích thước, từng là ô trống) và phân bố vận tốc rộng; cost nhân p_e. Thay ngưỡng cứng `min_hits = 3, min_travel = 0.5`.
- **Mới:** trung bình thấp, nhưng giải thích trực tiếp 66 % thấy ở −2 s.
- **Cài:** 1 hàm trong BlobTracker, 0 ms thêm. **Bác bỏ:** trần A phải > 0 với bộ lập đang dùng; nếu không, bỏ.
- **Rủi ro:** tái phát "9 người ma" ở slalom (7.7). Bắt buộc chạy cả bài tĩnh.

### E. MPPI phân nhánh có hồi tiếp (recourse) — chỉ nếu A thắng mà bảng thô
- **Nguồn:** Branch MPC ([2405.03470](https://arxiv.org/abs/2405.03470), [2502.02550](https://arxiv.org/abs/2502.02550) [MP]); RACP [2402.17387](https://arxiv.org/abs/2402.17387) [TT].
- **Ý:** tại 2–3 thời điểm của top-64 rollout, rẽ 5 góc × 9 động tác lách, lấy min theo động tác rồi trung bình theo góc rẽ (bài toán 2 giai đoạn có hồi tiếp).
- **Mới:** chưa tìm thấy Branch-MPC dạng này trong MPPI với người. **Chi phí:** 86k đoạn × 10 bước ~ 15–25 ms numpy, sát ngân sách.
- **Bác bỏ:** so thứ tự mẫu với A; nếu Spearman > 0.9 thì không cần. Rủi ro: chậm, nhiều hằng số.

### F. Suy diễn ai nhường (30/70) và thử dò (probe)
- **Nguồn:** [2603.00507](https://arxiv.org/abs/2603.00507) (Transformer suy luận hợp tác + chọn horizon, preprint), Parwana 2411.09198.
- Bayes 2 mode (né / mải điện thoại) từ phản ứng; siết biên chỉ cho người không nhường. Mới thấp; tỉ lệ 30/70 là **chọn của mô phỏng**, nên kết luận yếu. Xếp cuối.

**Đã loại:** chọn phía/đồng luân (cờ `mode`, đã đo không lợi); conformal thuần ([CoCoNav](https://arxiv.org/abs/2608.07751), [2508.05634](https://arxiv.org/abs/2508.05634)) làm phồng đẳng hướng → dễ đông cứng;
dự đoán học: [Poddar et al. 2303.01424](https://arxiv.org/abs/2303.01424) [MP] đo robot thật, S-GAN trong MPC **không** hơn vận tốc không đổi, cả với hành vi gây hấn/mất chú ý.

---
## 3. Baseline bắt buộc và cách tái hiện tối giản
Nguyên tắc: cùng K, cùng mô hình rollout, cùng tracker, cùng số lần chỉnh (PROTOCOL mục 3). Mỗi baseline tối đa ~8 cấu hình trên DEV.

| # | Baseline | Cách cài (numpy) | Lý do reviewer đòi |
|---|---|---|---|
| 1 | **MPPI chỉnh** (`ppl`, `ppl_len`, `cap`, T 24/32) | đã có; hiện mạnh nhất `ppl=32` | đối chứng chính |
| 2 | **PGIF-MPPI** | σ∥ = 1.2+0.5 s (trước), 0.5 (sau), σ⊥ 0.6; Σ exp(−½...); quét trọng số 4 mức + σ nhân {0.7, 1} | gần nhất, 2 giờ |
| 3 | **`turn_const`** | thay `need` bằng hằng số 2.1 s | ablation bắt buộc |
| 4 | **DRA-MPPI** | MoG: CV (σ 0.3 m/s như bài) + 4 mode rẽ ±45°, p = 0.025/bước; **lưới 0.1 m + chập đĩa bán kính r** rồi tra thay cho 20000 điểm MC (N=20000 là GPU của họ); σ=0.05, w_soft/w_hard quét | SOTA MPPI cho người |
| 5 | **Chance-constrained (dạng C2U, không UT)** | `A_r/η·exp(−½dᵀΣ⁻¹d) > δ` → phạt; Σ_o tăng theo thời gian (CV + ω); δ 0.01–0.1. Dùng UT 3 trạng thái nếu muốn gọi tên C2U-MPPI; nếu không phải ghi "CC-MPPI (lấy cảm hứng)" | yêu cầu trong đề |
| 6 | **ORCA/VO, trách nhiệm = 1** | nửa mặt phẳng + LP 2D (RVO2 hoặc tự viết), tốc độ 0.29, tiền định A*, tường = đoạn; dùng *cùng* tracker và biến thể oracle | VOP-Nav cũng làm vậy với người không hợp tác |
| 7 | **FRS xấu nhất + dừng cuối** (OA-MPC rút gọn) | bán kính người + v_max·t | chứng minh "xấu nhất = đông cứng" |
| 8 | **Thư viện dự phòng** (PL-CBF/CoCoNav) | 14 chính sách (dừng, lùi, 12 hướng) kiểm 3 s trên dự đoán CV±; nếu lệnh MPPI không có dự phòng thì thay | đối chứng trực tiếp cho "biên né"; Contingency-MPPI lồng không khả thi trên CPU 20 ms và cần tập S cố định |
| 9 | **RL**: PPO/SAC/TD3 hiện có + **DRL-VO reward hoặc SARL/attention** train cùng ngân sách | MODEL; đừng chỉ lấy trọng số CrowdNav/HEIGHT chính thức: VOP-Nav cho thấy HEIGHT (giới hạn 0.5 m/s) sụp 0.2–59 % vì lệch miền | CrowdNav-kiểu RL |
| 10 | **DWA chỉnh**, pure pursuit | đã có | cổ điển |
| 11 | **Trần oracle A/B** | Bước 0 | ngữ cảnh |
| 12 | Unitree `obstacles_avoid` | Go2 thật, về sau | 7.4 |

T-MPC++/SH-MPC: cần acados/C++; không bắt buộc nếu nêu lý do và có #4–5 (DRA-MPPI so với SH-MPC ở bài gốc). Chưa kiểm mã nguồn công khai của DRA-MPPI.
ORCA trong bài gần: [2603.00507](https://arxiv.org/abs/2603.00507) báo SR 66–85 % (va 7–24 %) với người không hợp tác — đừng coi ORCA là baseline yếu.

---
## 4. Metric và giao thức
**Nguồn chuẩn:** Francis et al., [THRI 2025, 2306.16740](https://arxiv.org/abs/2306.16740) [MP: bảng metric, hướng dẫn] và tổng quan 85 bài
[2510.22448](https://arxiv.org/abs/2510.22448) [MP] (S, T, C, PL là 4 metric phi xã hội phổ biến nhất; ORCA, DWA, SFM, CADRL, SARL là baseline phổ biến; 35.8 % bài không nêu lý do chọn baseline).
Francis nhấn mạnh: đo nhiều mặt, **kèm cả ca thất bại gồm người bất hợp tác/thất thường** (mục factor "Edge cases"), không có một số duy nhất.

Đề nghị báo cáo:
1. **An toàn:** tỉ lệ chạm người / vật, **tách** tự gây và bị va; khoảng hở nhỏ nhất; TTC nhỏ nhất; **PSC 0.5 m**; tốc độ tương đối lúc chạm
   (mức nghiêm trọng; [Paez-Granados & Billard, Sci. Rep. 2022](https://www.nature.com/articles/s41598-022-09349-9) [TT] gợi ý giảm tốc độ va dưới 1.5 m/s để giảm rủi ro).
2. **Hiệu quả:** S, SPL, thời gian, timeout, **stalled time / failure to progress** (để thấy đông cứng).
3. **At-fault phản thực (thay at_fault hiện tại):** phát lại người với robot **đứng yên** (hoặc tiếp tục hướng cũ) từ t_chạm − 1 s; nếu vẫn chạm → "không tránh khỏi từ 1 s";
   nếu robot tiến vào > 0.1 m/s theo *lệnh* (không phải vận tốc đo, vì thân lắc 0.43 rad/s làm |wz| > 0.3 dễ đúng ngẫu nhiên) → robot gây ra. Không tìm thấy chuẩn nào định nghĩa
   "robot-initiated" ([một bài đo thực địa chỉ phân tích tình huống xung đột](https://orbit.dtu.dk/en/publications/pedestrian-robot-collaboration-in-urban-unstructured-environment-/) [TT]); phải tự nêu định nghĩa và độ nhạy ngưỡng.
   Lưu ý người mô phỏng có phản ứng với robot, nên phản thực "đứng yên" chỉ gần đúng.
4. **Người không hợp tác:** báo riêng theo (a) tỉ lệ không hợp tác 0/30/100 % như C2U (NCM/CM), (b) góc/ thời điểm rẽ, (c) mật độ. Thêm 1 kịch bản **người khởi động từ đứng yên** (đang bị `turn_cost` bỏ qua vì sp ≤ 0.2).
5. **Mô hình người KHÁC tập DEV** để kiểm khái quát: (i) SFM khác tham số, (ii) ORCA người, (iii) phát lại quỹ đạo người thật (ETH/UCY, THÖR).
   Hiện người sim dùng **cùng hàm A\* `plan`** với robot → mọi ý "dự đoán theo đích/A*" là rò rỉ.
6. **Thống kê:** seed ghép cặp, Wilson, McNemar, Holm. Cỡ mẫu McNemar (tỉ lệ bất đồng 30 %, power 0.8, α 0.05 **trước** Holm):
   Δ 5 điểm n≈938; Δ 8 điểm n≈365; Δ 10 điểm n≈233; Δ 12 điểm n≈161. DEV crowd n = 101 **không đủ** thấy Δ < ~15 điểm; VAL 2000–2399 (~270 crowd) chỉ thấy Δ ≥ ~10.
   → TEST cần ≥ 600 cảnh đông người. CrowdNav++-kiểu: 500 seed test.

---
## 5. Chỗ chưa chắc
- Phần [TT]/[MP] chưa đọc hết; riêng **Chiang/Malone T-RO 2017** và **EPFL RA-L 2021** (VO cho capsule) phải đọc toàn văn trước khi viết Related Work.
- Chi phí tính của A, B, E là **ước tính**, chưa đo. Con số 0.85/0.48 là trạng thái bịa.
- Không tìm thấy ≠ không có: tìm kiếm bằng web, US, không truy cập được IEEE Xplore. Trước khi nộp phải rà lại với từ khoá "evasion margin", "escape time", "stochastic reachability pedestrian".
- Thứ hạng ý tưởng là ý kiến; các "bác bỏ rẻ nhất" mới là căn cứ.
