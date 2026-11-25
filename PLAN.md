# PLAN — kế hoạch dự án GoVoice (cập nhật 21/11/2026)

Đọc file này trước khi làm tiếp. Các tài liệu liên quan:
- `RESEARCH_NOTES.md`: kết quả, khoảng trống nghiên cứu, mục 7 về các bài báo;
- `SOTA_REVIEW.md`: tổng quan tài liệu, vì sao chọn thuật toán nào;
- `README_SIM.md`: cách chạy mô phỏng;
- `studio/README.md`: ứng dụng desktop.

---

## 00. KẾ HOẠCH TỔNG TỚI KHI CÓ KẾT QUẢ VIẾT BÁO (23h30 22/11 — người dùng giao toàn quyền điều phối)
Luật chung: `research/PROTOCOL.md`. Nhật ký mọi phép thử: `research/LOG.csv`. Báo cáo agent: `research/REPORT_*.md`.

| Chặng | Việc | Dự kiến |
|---|---|---|
| 1 | Vòng 1: LIT, OSS, ALGO, MODEL, DYN, ISAAC, AUDIT chạy song song | sáng sớm 23/11 |
| 2 | Điều phối viên kiểm lại số, sửa lỗi AUDIT tìm ra, chọn ý tưởng; vòng 2 (tối đa 3 vòng) | trong ngày 23/11 |
| 3 | VAL (seed 2000–2399): chọn 1 thuật toán chính + baseline đã chỉnh; AUDIT duyệt; KHOÁ thiết kế (PREREG) | tối 23/11 |
| 4 | TEST chạy đúng 1 lần: fastsim seed ≥ 100000 (lớn) + Gazebo bản đồ mới (~13 h) | đêm 23 → sáng 24/11 |
| 5 | Kiểm chứng chéo Isaac/MuJoCo nếu máy chạy nổi | 24/11 |
| 6 | `results/paper_package/`: bảng, hình, KTC + Holm, ablation, hạn chế, lệnh tái lập | tối 24 – 25/11 |
| 7 | Chó thật (CẦN người dùng): đo động học `dyn/HUONG_DAN_DO.md`, rồi `eval_real.py` với baseline Unitree | khi người dùng rảnh |

Quy tắc dừng: sau 3 vòng không có bản hơn baseline đã chỉnh (p < 0.05 sau Holm trên DEV xác nhận) -> khoá bản đơn giản
nhất, viết bài theo hướng phân tích/so sánh công bằng. Không chạy lại TEST để tìm số đẹp.
Vẫn phải HỎI người dùng: chạm chó thật, đăng/push ra ngoài, mua/trả tiền, sudo hoặc đổi driver.
Ước tính chặng có thể trễ; chặng 2 khó đoán nhất.

## 0. Đang dở: PIPELINE TỰ CHẠY (`pipeline/`, dịch vụ `govoice-pipeline`)
Từ 22/11 mọi việc chạy bằng `pipeline/run_all.py`:
- ~~dịch vụ systemd người dùng, tự chạy tiếp sau khi tắt/mở máy~~ (đã gỡ 23/11);
- chặn máy tự ngủ khi để không (nhưng gập nắp vẫn ngủ);
- tiến độ ở `pipeline/STATUS.md`, nhật ký ở `pipeline/pipeline.log`.

| Bước | Nội dung | Ai |
|---|---|---|
| 1 screen + 2 train (**song song**) | sàng lọc 17 cấu hình × 8 bài (1 sim); PPO, TD3, SAC × 3 seed × 20 phút, cảm biến thực tế | máy |
| 3 analyze | `results/RL_ANALYSIS.md`: eval2d từng seed + bù trừ (**chỉ số liệu**) | máy |
| ⏸ **Trạm chờ 1** | Claude **tự đánh giá** (không dùng script chọn), ghi `pipeline/decisions.json`: `rl` (policy cài đặt, critic) và `select_configs` | Claude |
| 4 select | chạy các cấu hình PRISM Claude chọn, 2 lần lặp, **2 sim song song** | máy |
| ⏸ **Trạm chờ 2** | Claude xem quỹ đạo và lỗi, ghi `final`: `configs` (PRISM cuối đứng ĐẦU), `trials` (5), `house_configs`, `house_trials` (3) | Claude |
| 5 final | văn phòng × 5 lần lặp + nhà nhỏ (nav, an toàn, né vòng, người) × 3 lần, 2 sim song song | máy |
| 6 report | `results/FINAL_REPORT_*.md` (bảng, KTC Wilson, McNemar, Wilcoxon) → **Claude viết kết luận** | máy + Claude |

- Ước tính (đo 22/11 lúc 00:10): xong toàn bộ khoảng **20:00–21:00 ngày 22/11**.
- Cập nhật 05:45 22/11: trạm chờ 1 + 2 đã xong (RESEARCH_NOTES 7.7, 7.8). Lượt chính thức lớn hơn dự kiến (24 cấu hình văn phòng × 5 + 11 cấu hình nhà nhỏ × 3 = 1521 lượt) -> xong khoảng **00:00–01:00 ngày 23/11**.
- **23/11: dịch vụ `govoice-pipeline` đã GỠ theo yêu cầu người dùng (pipeline 960+561 lượt đã xong). `pipeline/` vẫn còn để đọc; không tự chạy khi bật máy nữa.**
- Người dùng yêu cầu: **không bỏ cấu hình nào**, thêm thì được. Mọi lựa chọn do Claude đánh giá bằng
  suy xét, kèm lý do ghi trong decisions.json và RESEARCH_NOTES.

⚠️ Bẫy đã gặp, nhớ khi chạy đánh giá:
- **BLAS phải chạy 1 luồng** (`OPENBLAS_NUM_THREADS=1`, đã đặt ở đầu run_sim, eval_sim, server, …).
  Nhiều luồng làm policy RL chậm 25 lần, và các bộ né có dùng RL bị đánh giá thiệt (gặp 21/11).
- **Xe đẩy phải được đưa ra ngoài bản đồ** trước mỗi bài (`park_carts()` trong eval_sim). Trước
  ngày 21/11, xe đẩy bài trước chắn lối đi của bài sau, làm kết quả bài lối pallet sai.
- **Không bao giờ** chạy lệnh `pkill -f "eval_[s]im"` chung một dòng với lệnh có chữ `eval_sim.py`,
  vì nó tự giết chính lệnh đó. Dùng `kill_eval.sh` riêng.
- Train RL hoặc chạy test offline **song song** với đánh giá Gazebo sẽ làm vòng điều khiển chậm.
  Lượt chính thức phải chạy một mình.

## 1. Bài báo: MỘT bài tạp chí (quyết định 21/11)
Phần "trộn RL qua MPPI" (trước đây định làm bài A) là **một thành phần bên trong PRISM**: cùng bài
toán, cùng robot, cùng benchmark. Vì vậy gộp thành **một bài tạp chí lớn**, gồm cả mô phỏng và
thực nghiệm trên chó thật.

- **Tên dự kiến:**
  - 🇬🇧 *PRISM: Policy-Prior, Gait-Adaptive and Blind-Spot-Aware Sampling-Based Navigation for
    Voice-Commanded Quadruped Robots*
  - 🇻🇳 *PRISM: Điều hướng lấy mẫu kết hợp tiên nghiệm chính sách, thích nghi dáng đi và nhận biết
    điểm mù cho robot bốn chân điều khiển bằng giọng nói*
- **Nơi nộp:** IEEE T-RO (hàng đầu, bài dài). Phương án an toàn hơn: Robotics and Autonomous
  Systems, Journal of Field Robotics, IEEE T-ASE. RA-L quá ngắn cho từng này đóng góp.
- **Đóng góp và ablation chứng minh từng cái:**

| # | Đóng góp | Khoảng trống | Ablation |
|---|---|---|---|
| C1 | Gợi ý từ **nhiều policy RL** (PPO + TD3) chạy vòng kín trong MPPI, **tỉ lệ từng policy tự điều chỉnh**, critic PPO làm chi phí cuối. So với policy-guided MPPI (CoRL-MPPI 2025, RAY-TOLD 2026) và Biased-MPPI (2024) | G5 | `prism_noprior`, `prism_noadaptratio`, `prism_novalue` |
| C2 | Mô hình gait thích nghi theo từng trục (vx, vy, wz) | G1 | `prism_noadapt` |
| C3 | Nhận biết vùng mù LiDAR/camera | G2 | `prism_novis` |
| C4 | Dự đoán người có bất định + người đi chậm | G3, G3b | `prism_nounc` |
| C5 | Chống rung (giới hạn thay đổi lệnh, bỏ giới hạn khi nguy hiểm) | G4 | (so với MPPI: số lần lắc hướng) |
| C6 | Lệnh giọng nói tiếng Việt chỉnh cách né, chạy trên robot | G6 | thí nghiệm có và không có "tránh xa người" |
| C7 | Benchmark mở (văn phòng 30 × 20 m, người, xe đẩy) + **chó thật so với bộ né của Unitree** | — | — |

- **Đối chứng:** bản cũ (pure pursuit), DWA, MPPI, log-MPPI, PPO, `rl_ens` (PPO + TD3 trung bình),
  `rl_safe`, PG-MPPI, Biased-MPPI (`bmppi`), AP-MPPI (`apmppi_multi`). Ngoài đời thêm bộ né
  Unitree (`unitree_path`).
- Kiểm tra tên trên Google Scholar trước khi nộp. Thành phần nào ablation cho thấy không tác dụng
  thì **bỏ khỏi tên và khỏi danh sách đóng góp**.
- Phản biện tạp chí thường mất 6–12 tháng. Nếu cần bài sớm hơn, có thể viết 1 bài hội nghị ngắn
  trước (ICRA/IROS) rồi mở rộng thành tạp chí với ≥ 30 % nội dung mới.

## 2. Thuật toán: việc còn phải làm
- [ ] **G3c, người áp sát từ vùng mù:** mọi lần va của PRISM đều là người "mải điện thoại" đi vào
  robot đang đứng, từ hông hoặc sau lưng (LiDAR mù dưới 0.5 m). Hướng làm:
  - giữ dự đoán track khi người vào vùng mù;
  - bước tránh khi người được dự đoán sẽ đi vào chỗ robot đang đứng.
- [ ] Kiểm tra chống "đóng băng" (freezing robot problem, Trautman IJRR 2015) ở bài 8 người.
- [ ] Thử **C-Uniform MPPI** (2025) nếu PRISM còn kẹt ở chỗ dày.
- [ ] RL: policy có **attention cho người** (kiểu SARL, ICRA 2019) nếu RL thắng ở bài đông người.
  Train lâu hơn 20 phút.
- [ ] Thử nghiệm **lệnh giọng nói chỉnh cách né** (G6): cùng một bài, có và không có câu "tránh xa
  người", đo khoảng cách người nhỏ nhất.

## 3. Thực nghiệm trên chó thật

### 3.1 Chuẩn bị (làm trước)
- [ ] Lần đầu: `start_real.sh`, tốc độ thấp (`real.goto_speed 0.25`), remote trong tay (L2+B).
  Thử "đi thẳng 1 mét" trước.
- [ ] Đo hệ số vận tốc thật (`vel_gains`, Go2 khoảng 0.8–0.9) và kiểm tra gá D435i
  (`config.yaml` mục `real:`).
- [ ] **Đo thời gian tính trên Jetson Orin** cho MPPI, PRISM, AP-MPPI (cần dưới 100 ms mỗi chu kỳ).
  Laptop: MPPI 11 ms, PRISM 15 ms, AP-MPPI khoảng 40 ms. Jetson có thể chậm hơn 3–5 lần. Nếu
  chậm thì:
  1. giảm K (600 → 300);
  2. tăng bước giữ policy (`hold` 6 → 8);
  3. chuyển phần lấy mẫu sang torch trên GPU của Orin.
  Không chạy planner trên laptop qua Wi-Fi (xem bộ nhớ: Wi-Fi gây giật).
- [ ] Kiểm tra bộ né Unitree: `example/obstacles_avoid/obstacles_avoid_switch.py` (bật/tắt được
  không, phiên bản API 1.0.0.2).
- [ ] Policy RL train trong 2D với hệ số vận tốc ngẫu nhiên 0.4–1.0, đã phủ Go2 thật. Kiểm tra
  quan sát (72 tia từ bản đồ LiDAR + D435i) ngoài đời giống lúc train.

### 3.2 Đường chạy (`course_real.yaml`, dựng bằng thùng carton khoảng 0.5 m)
1. thẳng trống;
2. 1 thùng giữa đường;
3. 4 thùng zíc-zắc, khe khoảng 0.9 m;
4. hành lang hẹp 0.9 m;
5. người cắt ngang;
6. người đi đối đầu.

Thêm (vùng mù):
7. vật thấp 12 cm ở vùng mù LiDAR;
8. người đi từ hông hoặc sau lưng (vùng mù, khoảng trống G3c).

### 3.3 Quy trình
- `python3 eval_real.py --course course_real.yaml --controllers <danh sách> --trials 5`
  - Chính: `unitree_path mppi dwa pgmppi rl prism`
  - Ablation trên chó: `prism_novis prism_noadapt prism_noprior`
- Mỗi đường chạy lặp ≥ 5 lần. Thứ tự các bộ né xáo ngẫu nhiên mỗi vòng (script đã làm).
- **Đo đạc:**
  - odometry + log LiDAR: thời gian, số lần khựng, tốc độ, khoảng hở nhỏ nhất;
  - người quan sát đánh dấu va chạm;
  - **quay video từ trên cao** (điện thoại trên giá cao) để kiểm lại va chạm và vẽ quỹ đạo thật.
    Nếu có hệ thống motion capture thì dùng làm ground truth.
- **Người tham gia** (bài người cắt ngang hoặc đối đầu):
  - tình nguyện viên được giải thích trước;
  - tốc độ robot ≤ 0.4 m/s;
  - người giữ remote đứng sát;
  - có thể dùng tấm xốp chắn thay người ở các lượt đầu.
- Ghi lại pin, mặt sàn, ánh sáng (ảnh hưởng tới D435i) mỗi buổi.
- **Lệnh giọng nói (C6):** cùng đường chạy 5 có và không có câu "tránh xa người". Đo khoảng cách
  người nhỏ nhất và thời gian. Có thể hỏi người tham gia cảm giác an toàn (thang Likert 1–5).

### 3.4 Không làm
- **Không** chạy policy RL ở tầng thấp (LowCmd). Đi bộ và leo cầu thang dùng bộ mặc định của
  Unitree. RL và các bộ né chỉ gửi lệnh vận tốc (SportClient, hoặc `obstacles_avoid` khi đối
  chứng).
- [ ] Nối bộ định vị trên bản đồ có sẵn (KISS-ICP hoặc FAST-LIO2 + định vị lại) để bản đồ đã lưu
  dùng được sau khi tắt/bật. Thí nghiệm bài A và B không cần (mỗi lượt xoá bản đồ, đích tương đối).

## 4. Các phần khác (theo `SOTA_REVIEW.md`, đo trước khi đổi)
- [ ] Phát hiện người trên robot thật: **DR-SPAAM** (IROS 2020) thay cho gom cụm.
- [ ] Tìm đồ vật trên robot thật: **YOLO-World** (CVPR 2024) + độ sâu D435i → `ObjectCatalog`. Về
  sau là HOV-SG khi cần nhiều phòng.
- [ ] Nhận dạng tiếng Việt: thu vài trăm câu lệnh, đo WER của PhoWhisper-small, zipformer và
  **VietASR** (2025), rồi chọn.
- [ ] LLM: thử **Qwen3-1.7B** và Llama-3.2 trên cùng test 300 + 200 câu (model hiện tại v2:
  93.0 % / 87.5 %).
- [ ] Dataset: thêm mẫu "combo động tác + đồ vật" (hiện đúng 71 %).

## 5. Ứng dụng GoVoice Studio
- [ ] Cài bản mới nhất: `bash studio/packaging/build_deb.sh && sudo apt install ./dist/govoice-studio_*.deb`.
- [ ] Thêm nút **chọn bộ né** đầy đủ (`apmppi`, `prism`, …) và hiển thị tỉ lệ mẫu RL trực tiếp.
- [ ] Bản Windows/macOS (Tauri) nếu cần. Hiện app cần ROS nên chỉ chạy trên Ubuntu.

## 6. Bản đồ lệnh hay dùng
```bash
# sim văn phòng 30 x 20 m (hoặc chọn trong Studio)
ros2 launch go2_voice voice_sim.launch.py world:=voice_office.sdf headless:=true
python3 movers.py --world voice_office --crowd 12 --carts          # người + xe đẩy
python3 run_sim.py --both [--wake "gô ơi"]                         # nói + gõ
# LLM
NhanHuynh/go2_jetson_demo/llama.cpp/build-cuda/bin/llama-server -m finetune/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
# đánh giá
python3 eval_sim.py --suite office --configs prism mppi --trials 3
venv/bin/python rl_nav/eval2d.py rl_nav/policy_nav.npz rl_nav/policy_nav_td3.npz
# train RL (mỗi cái 20 phút GPU)
venv/bin/python rl_nav/train_ppo.py --minutes 20 --name ppo_vX
venv/bin/python rl_nav/train_td3.py --minutes 20 --curriculum-time --name td3_vX
venv/bin/python rl_nav/export_value.py rl_nav/runs/ppo_vX rl_nav/value_nav.npz
```

## 7. File quan trọng
| File | Vai trò |
|---|---|
| `nav_local.py` | Bản đồ, A\*, MPPI, DWA, **PRISM**, **PolicyMPPI** (PG/AP-MPPI), RLPolicy, EnsemblePolicy |
| `robot_ros.py` | Robot sim: chọn bộ né (`controller`), ước lượng gait, vùng mù, người |
| `robot_real.py` | Robot thật + đối chứng bộ né Unitree (`unitree`, `unitree_path`) |
| `eval_sim.py`, `eval_real.py` | Đánh giá sim và robot thật (cùng chỉ số) |
| `rl_nav/` | Môi trường RL GPU, train PPO/FastTD3, eval2d, policy `.npz` |
| `studio/` | App desktop (backend FastAPI + giao diện web + gói .deb) |
| `~/ros2_ws/src/unitree_go2_ros2/tools/gen_voice_office.py` | Sinh bản đồ văn phòng |
| `~/isaac/install_isaaclab.sh` | Cài Isaac Lab (đã dừng, vì không cần train đi bộ) |

## Ràng buộc từ đề tài NCKH SV 2027 (TB 4041/TB-ĐHCNKT, 18/11/2026) — ảnh hưởng thời điểm nộp bài báo
- Đề tài (chủ nhiệm Huỳnh Lê Thành Nhân, mức 25 tr = 1 bài Scopus/WoS) thực hiện 01/2027–12/2027; nghiệm thu đợt 1 ~6/2027, đợt 2 ~10/2027.
- 25/11/2026: người dùng HẠ xuống mức 10 tr; sản phẩm đăng ký đổi thành 01 bài trong kỷ yếu hội thảo quốc tế có ISBN/ISSN (ưu tiên hội thảo robot IEEE, phản biện toàn văn), gửi 03–06/2027, phải được chấp nhận trong 2027 (vd. IROS 2027 hợp lịch; ICRA 2028 báo kết quả 1/2028 → KHÔNG hợp). Kiểm 25/11: IROS 2027 (Florence, cuối 9–đầu 10/2027) hạn nộp bài dự kiến 01/03/2027 (nguồn bên thứ ba, chưa có CFP chính thức; ngày báo kết quả chưa công bố, thường khoảng 6–7) → bài + chó thật phải xong trước 01/03/2027. Bài tạp chí vẫn có thể viết sau; cần tránh trùng lặp nội dung (bản tạp chí phải mở rộng rõ so với bản hội thảo và trích dẫn nó).
- Bài báo phải: được CHẤP NHẬN trong 01–12/2027; tác giả đầu là sinh viên thành viên đề tài; chỉ ghi đơn vị HCMUTE; có lời cảm ơn kèm mã số đề tài SV2027-xx; GVHD (PGS.TS. Lê Mỹ Hà) nên là tác giả liên hệ; nội dung khớp đề tài; tạp chí không săn mồi, có DOI.
- → Không để bài được chấp nhận trước 01/2027; nộp sau khi có mã số (hoặc thêm lời cảm ơn khi sửa bài). Hạn nộp hồ sơ đăng ký tại Khoa: 30/11/2026.
