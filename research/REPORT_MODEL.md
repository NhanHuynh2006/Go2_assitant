# REPORT_MODEL — PPO với động học đo được, và bộ dự đoán người `nav_pred.py`

Agent MODEL, 22–23/11. Chỉ DEV (fastsim seed 0–999); không chạy VAL (2000–2399) và TEST (≥100000). Mọi lượt đã ghi
vào `research/LOG.csv` (53 dòng MODEL). Code: `rl_nav/env.py` (thêm chế độ động học), `rl_nav/train_ppo.py` (`--dyn`),
`rl_nav/eval2d.py` (`--dyn=`), `rl_nav/pred_data.py`, `rl_nav/train_pred.py`, `rl_nav/eval_pred.py`, `rl_nav/fs_pred.py`,
`nav_pred.py`, model `rl_nav/pred_nav.npz` (= `rl_nav/pred/mix_h256.npz`). Dữ liệu và đánh giá open-loop:
`results/model_pred_data/` (eval.json, eval.log). Không sửa nav_local / robot_ros / fastsim.

## 0. Kết luận ngắn
1. **Động học sai KHÔNG phải nguyên nhân 2D→fastsim hỏng.** PPO train với động học đo được ("dyn", "union") thì ngang PPO cũ
   ở cả champ, champ2 và go2 (khác nhau ≤ 2.6 điểm, p ≥ 0.17). Trong 2D, đổi sang động học CHAMP chỉ làm PPO cũ tụt 93.7→90.0 %.
   Cảm nhận người hoàn hảo (`--oracle`) cũng chỉ thêm 1.4 điểm. Phần hỏng là do NGƯỜI: hazard va người trong fastsim
   khoảng 2.1 %/s, gấp ~3 lần trong env 2D (0.68 %/s), cộng với quãng đường dài gấp ~3. **RL thuần chỉ nên là ablation.**
2. **nav_pred tốt hơn hẳn vận tốc không đổi (CV) ở open-loop, và giữ được với cả 5 mô hình người không dùng để train**
   (ORCA, Helbing 2000, Moussaïd 2009, đi lang thang, đổi ý bất chợt). Brier nguy cơ chạm thấp hơn CV đã chỉnh 15–25 %,
   CI theo tập < 0 ở 5/6 bộ. Riêng `wander` thì hoà CV_damp.
3. **Ở vòng kín, chưa hơn CV một cách có ý nghĩa.** p3+geo-haz với quạt GeoFan thay bằng nav_pred (+30 % CV) so với chính p3
   dùng CV (g_len 0.25): +38/−25 cặp gộp qua 5 điều kiện (champ, champ2, go2, champ-helb, go2-helb; 104 thế giới mỗi điều kiện),
   p = 0.13. Không điều kiện nào thua, nhưng không điều kiện nào đạt p < 0.05. Theo protocol thì **chưa khuyến nghị làm thành
   phần chính**. Có thể giữ làm tuỳ chọn. Cần thêm thế giới, hoặc người thật, mới quyết được.

## 1. Việc 1 — PPO với động học đo được
`NavEnv(dyn=...)`: `linear` là mặc định cũ (đã kiểm: obs và reward trùng bit với bản gốc). `measured` có: bão hoà vx bằng tanh
(0.20–0.40), lùi ×1.0–1.45, vy, wz, tau 0.10–0.30/0.10–0.30/0.15–0.40, trễ 0–0.1 s, lắc thân OU, vận tốc quan sát lấy bằng sai phân
vị trí rồi lọc EMA 0.5 như `robot_ros`. Phủ cả nhánh gần tuyến tính (60/40). `union` gồm 50 % CHAMP và 50 % mẫu từ
`dyn/go2_params.yaml` (gain, tau, trễ 0.04–0.20 s, giới hạn gia tốc, lắc thân thật 4 mm/0.008 rad). Mỗi cấu hình 3 seed.

**Lưu ý champ2:** env dùng dạng tanh/vsat. Dạng CHAMP đo lại (pipeline/sysid_fit2.py) là **cắt cứng 0.3/0.25/0.5 cộng trôi lùi
~0.053 m/s**. Tôi không train lại theo dạng này (kết quả dưới cho thấy động học không phải nút thắt).

Ngân sách: old 20 phút (~333 M bước). dyn: s0 20 phút (128 M), s1 và s2 33 phút (152 M / 392 M), vì máy quá tải và bị chậm 2–3 lần.
union: 20 phút (108–161 M). PPO cũ đã bão hoà ở ~40 M bước, nên chênh lệch này không đổi kết luận, nhưng nó không cân bằng hoàn toàn.

2D (4096 tập, cảm biến thực tế): ở dyn=champ, old 90.0 % (89.6–90.4) so với dyn 91.9 % (91.7–92.1). Ở dyn=linear, old 93.7 %.

fastsim, seed 0–299 chỉ thế giới có người (205 × 3 seed = 615 lượt mỗi ô), cặp gộp so với old:

| regime | old | dyn | union | dyn−old | union−old |
|---|---|---|---|---|---|
| champ | 39.8 % | 40.3 % | 40.3 % | +93/−90 (p 0.88) | +93/−90 (p 0.88) |
| champ2 | 44.1 % | 43.3 % | 45.9 % | +84/−89 (p 0.76) | +90/−79 (p 0.44) |
| go2 | 52.4 % | 49.9 % | 49.8 % | +49/−64 (p 0.19) | +53/−69 (p 0.17) |

Vật tĩnh ~98–100 % ở mọi ô. old_s0 với `--oracle` (300 thế giới): 60.7 % so với 59.3 %. Hazard va người: 2.1–2.3 %/s ở champ,
2.7–2.8 %/s ở go2. (McNemar gộp 3 seed chạy trên cùng thế giới chỉ là xấp xỉ.)

## 2. Việc 2 — nav_pred (dự đoán 2.4 s, nhiều mode)
**Dữ liệu** (`pred_data.py`): `fastsim.Sim` thật (LiDAR, OccGrid, BlobTracker; nửa số tập tracker v2, nửa v3). Robot chạy theo
kịch bản pure-pursuit, không dùng bộ né. Người theo Social Force của movers.Crowd. Seed người 40000–60999. Bản đồ: train
300–799, val 800–999, test 0–299. "train_rand" ngẫu nhiên hoá A/B/tau/nhiễu/v0/tỉ lệ mất tập trung/hazard đổi ý.
Mẫu gồm track movers() và track đã từng đi nay ĐỨNG (`History.people`). Track ma (không khớp người trong 0.6 m) bị loại khỏi
nhãn: chiếm 11–19 % số track.
**Mô hình:** MLP 77 → 256 → 256 → 8 mode × (8 nút x, y, log σ) + logit. Lưới hình học là phần dư cộng thêm vào CV; train bằng
NLL biên từng bước + 0.2 NLL quỹ đạo; đối xứng gương. Đầu vào gồm 8 điểm lịch sử (≤1.5 s, có mặt nạ), tốc độ, tuổi track,
robot (vị trí, vận tốc), 2 người gần nhất, 24 tia tới vật tĩnh trên trường khoảng cách, cờ đứng và thời gian đứng.
`predict()`: 1 người 0.4 ms, 3 người 1.1 ms, 6 người 2.5 ms (p95 2.7 ms, numpy 1 luồng).
**Baseline** (chỉnh trên val, đều nhiều lần thử hơn mạng): CV của tracker; CV_damp (20 lần); Kalman CV (24); GeoFan của ALGO
cộng CV (90). σ của baseline được fit riêng cho người đi và người đứng.

Open-loop trên test (bản đồ 0–299). "net+cv" = 0.7 mạng + 0.3 CV, là dạng dùng ở vòng kín.

| bộ (mô hình người) | NLL CV_damp / net | FDE TB CV_damp / net | FDE khi RẼ | Brier nguy cơ chạm CV_damp / net / net+cv | phủ 90 % net+cv |
|---|---|---|---|---|---|
| default (SF train) | +0.66 / −0.78 | 0.91 / 0.73 | 1.23 / 1.03 | .0598 / .0468 / .0486 | 0.95 |
| orca (khác hẳn) | +0.78 / −0.37 | 0.92 / 0.80 | 1.30 / 1.21 | .0585 / .0472 / .0482 | 0.92 |
| helb2000 | +0.60 / −0.63 | 0.87 / 0.72 | 1.17 / 1.00 | .0530 / .0449 / .0456 | 0.95 |
| mous2009 | +0.57 / −0.39 | 0.86 / 0.73 | 1.06 / 0.91 | .0510 / .0415 / .0423 | 0.95 |
| wander (không đích) | +1.05 / +0.87 | 1.15 / 1.13 | 1.39 / 1.36 | .0506 / .0509 / .0501 | 0.74 |
| sudden (đổi ý 0.35/s) | +1.07 / +0.23 | 1.10 / 1.03 | 1.35 / 1.37 | .0583 / .0483 / .0500 | 0.81 |

CI 95 % (bootstrap theo tập) của ΔBrier net − CV_damp: < 0 ở 5/6 bộ, wander [−0.0025, +0.0035]. AUC "sắp chạm" với người
rẽ muộn (CV dự đoán lệch > 0.8 m mà vẫn chạm): CV 0.69–0.81, net 0.76–0.90.
**Người ĐANG ĐỨNG rồi đi** (|v| < 0.2, 65–77 % sẽ đi > 0.5 m trong 2.4 s): NLL CV +0.45…+1.03, net −0.42…+0.27; Brier thấp hơn
CV 0.0007–0.015, CI < 0 ở default, sudden, mous và orca; wander và helb hoà. FDE gần như không đổi (0.95 so với 1.04):
mạng không biết người sẽ ĐI LÚC NÀO hay đi ĐÂU, nó chỉ trải xác suất ra rộng hơn cho đúng.
**Ablation** (NLL test default): chỉ có tốc độ (hỗn hợp không ngữ cảnh) +0.31; bỏ tia vật tĩnh −0.58; bỏ lịch sử −0.36; đủ −0.80.
Một nửa phần lợi NLL đến từ dạng hỗn hợp, nửa còn lại từ ngữ cảnh. Lợi về Brier gần như chỉ đến từ ngữ cảnh: bản không ngữ
cảnh có Brier ngang CV.
**Điểm yếu:** khi người không đi theo đích (wander), mạng tự tin quá mức: phủ 90 % chỉ đạt 0.59. Trộn thêm 30 % CV kéo lên 0.74
(CV 0.74–0.78).

**Vòng kín** (`rl_nav/fs_pred.py`, PRISM3 y nguyên; chỉ thay tập quỹ đạo trong `geo_cost` bằng 8 mode × 4 điểm sigma).
Chỉnh 3 biến thể trên DEV 0–149 champ, chọn wcv=0.3 (86.1 %). Xác nhận trên seed 150–299, chỉ thế giới có người (104):

| điều kiện | net (wcv .3) | geo (ALGO) | CV g_len .25 | net vs CV | net vs geo |
|---|---|---|---|---|---|
| champ | 80.8 % | 80.8 % | 76.9 % | +7/−3 (0.34) | +5/−5 |
| champ2 | 77.9 % | 76.9 % | 77.9 % | +10/−10 (1.0) | +8/−7 |
| go2 | 86.5 % | 79.8 % | 82.7 % | +8/−4 (0.39) | +9/−2 (0.07) |
| champ, người helb | 89.4 % | 80.8 % | 85.6 % | +8/−4 (0.39) | +12/−3 (0.04) |
| go2, người helb | 91.3 % | 91.3 % | 90.4 % | +5/−4 (1.0) | +3/−3 |
| gộp 5 điều kiện | | | | **+38/−25 p = 0.13** | +37/−20 p = 0.033* |

*Chưa hiệu chỉnh Holm, và 5 điều kiện dùng chung thế giới nên các cặp không độc lập. Vì vậy không kết luận "hơn".
mous champ bị dừng giữa chừng (28/104): net 89 %, geo 85 %, CV 78 %. Baseline CV g_len 0.25 do ALGO chỉnh (nhiều lần thử hơn).

## 3. Chưa chắc / hạn chế
- Mọi người đều là mô phỏng. Chưa thử trên người thật (THÖR, CC BY 4.0, mà OSS/SEV đã có). Người thật rẽ ít hơn mô phỏng
  ~1.7 lần (SEV), nên lợi thế của nav_pred trên người thật có thể nhỏ hơn.
- Train và test cùng một pipeline cảm biến của fastsim. Các mô hình người lạ vẫn đi theo A* tới đích (trừ wander và sudden).
- Ghi chú trong movers.py "theo Moussaïd 2009" là sai (OSS). helb và mous ở đây được tôi tự cài lại từ công thức
  (Helbing, Farkas, Vicsek, Nature 2000; Moussaïd et al., Proc. R. Soc. B 2009). ORCA viết lại theo van den Berg et al. (ISRR 2011),
  giải bằng lấy mẫu thay cho LP. Trong phiên này **chưa mở lại toàn văn** các bài trên để đối chiếu tham số.
- Track ma vẫn được dự đoán như người. Mạng chưa từng thấy track ma khi train.
- PPO dyn s1 và s2 được nhiều bước train hơn s0 (máy quá tải).

## 4. Giấy phép (Bổ sung 6)
Chỉ dùng numpy, scipy (BSD-3), PyTorch (BSD-3), PyYAML (MIT). Không chép mã RVO2/PySocialForce/lightsfm (chỉ cài lại theo
công thức). Không dùng dữ liệu ngoài.

## 5. Đề xuất
1. Nếu muốn dùng nav_pred: ghép vào p3 như `fs_pred.NetP3` (wcv 0.3). Tốn 1–3 ms mỗi nhịp. Chạy VAL 2000–2399 ở cả 3 regime,
   base và helb, với ≥ 300 thế giới mỗi bên, rồi quyết bằng McNemar + Holm. Hiện tại: **chưa đủ bằng chứng**.
2. Kiểm open-loop trên THÖR trước (rẻ, không cần sim). Nếu Brier không hơn CV trên người thật thì bỏ hẳn.
3. Không đầu tư thêm cho PPO với động học. Trong bài, giữ PPO làm ablation và báo cáo bảng ở mục 1.
4. Đề nghị cho coordinator: thêm cờ `--crowd-model orca|wander` vào fastsim (mã có sẵn trong `rl_nav/pred_data.py::step_other`).


---
*Ghi chú coordinator (23/11 20:50): agent MODEL bị chặn ghi file; người dùng yêu cầu coordinator lưu nguyên văn báo cáo này (trích từ lệnh Write bị chặn của agent). Kết luận của coordinator: RESEARCH_NOTES §7.13.*
