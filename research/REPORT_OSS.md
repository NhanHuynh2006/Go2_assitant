# REPORT_OSS — mã mở né người/vật cản cho Go2: ai đã làm gì, ta trùng ở đâu, lấy gì về (22/11/2026)

Agent OSS. **Không chạy mô phỏng nào**, không thêm phép thử cho Holm. Không chạy/cài script của repo nào. Clone `--depth 1` để ĐỌC
ở `Go2_assitant/oss/` (27 repo + 1 phần của navigation2, 3 GB; file > 200–600 kB không tải). Có làm 3 phép tính ngoại tuyến: đọc lại CSV
`results/dev2, dev3` đã có (mục 0.3), bảng tra xác suất va (mục 2-B), điều kiện homicidal-chauffeur (mục 0.2). Không đụng VAL/TEST.

Mức đọc: **[MÃ]** đã mở file mã nêu tên; **[TV]** đọc bản HTML toàn văn phần liên quan; **[TT]** chỉ tóm tắt/README/API GitHub.
Ngày "cập nhật" = commit cuối nhánh mặc định (hoặc `pushed_at` nếu ghi *). Đường dẫn file tính từ `oss/`.
Bài bổ sung cho `LIT.md`; chỗ nào LIT đã có thì chỉ nói phần **mã**.

---
## 0. Kết luận ngắn

### 0.1 Phát hiện quan trọng nhất: CN-CBF (LIT chưa có)
**CN-CBF** (Derajić, Bernhard, Hönig; arXiv [2603.06921](https://arxiv.org/abs/2603.06921); mã MIT `bojan-derajic/CN-CBF`) đã giải đúng câu hỏi của
`turn_cost`: *"nếu người rẽ thì robot còn thoát được không"*. Họ giải trò chơi HJ trên trạng thái tương đối `(x, y, θ_rel, v_o)`, người là unicycle
có tốc độ không đổi và **tốc độ rẽ đối kháng ω ∈ [−0.35, 0.35] rad/s**, robot chống lại; học thành mạng, gộp nhiều người bằng softmin, lọc lệnh bằng QP.
Thử trong Gazebo + HuNavSim, **người không né robot**, 5/10/15 người: ~95/92/82 %, baseline tốt nhất thấp hơn tới 18 điểm; có robot thật.
→ **Không được viết** "lần đầu xét người có thể rẽ trong biên an toàn". Phải trích, và nên so.
Phần họ **không có** (bài + luận án [2610.16522](https://arxiv.org/abs/2610.16522) tự nói): vật tĩnh (cảnh chỉ có người, khu trống); nhiều người cùng chặn mọi lối;
người rẽ gắt hơn 0.35 rad/s ("recorded failures include pedestrians who turned more sharply than the attributed bound permits"); hướng thân/thân dài ("models that include the body orientation" vượt lưới);
robot thực hiện đúng lệnh tức thì (không trễ, không bão hoà); `R_min = 0.8` m hình tròn.

### 0.2 Vì sao không bê nguyên CN-CBF: robot của ta nằm ở bên kia ngưỡng (kết quả giải tích)
Người tốc độ v_p, bán kính rẽ R = v_p/ω; robot v_e < v_p đổi hướng tức thì; chạm khi cách < l: đó là *homicidal chauffeur* (Isaacs).
Tự suy lại: rào chắn rời vòng chạm ở góc cos φ = γ = v_e/v_p; toạ độ ngang sau thời gian ngược s: `(l − γRs) sin(φ+s) + R(1 − cos s)`. Rào khép được ⇔ tồn tại s:
`l/R ≤ γs − (1−cos s)/sin(φ+s)`; cực đại tại φ+s = π/2 cho **`l/R ≤ √(1−γ²) + γ·arcsin γ − 1`**. Vượt ngưỡng = người *cố ý* luôn bắt được, từ mọi trạng thái.

| | γ | l/R | ngưỡng | |
|---|---|---|---|---|
| CN-CBF (v_e 1.0, v_p 1.2, ω 0.35, l 0.8) | 0.83 | 0.233 | 0.374 | thoát được: V∞ có nghĩa |
| **Ta** (0.29 vs 0.9, ω 0.35, l 0.43 thân hẹp / 0.64 thân dài) | 0.32 | 0.167 / 0.249 | **0.052** | **luôn bị bắt** |
| HEIGHT (0.5 vs 1.0, l 0.5) | 0.50 | 0.175 | 0.128 | luôn bị bắt |

→ V∞ kiểu CN-CBF/HJ xấu nhất vô hạn tầm sẽ **báo mọi trạng thái là không an toàn** với robot 0.29 m/s: lý do *có chứng minh* (không chỉ cảm tính) để dùng giá trị
**hữu hạn tầm + xác suất rẽ** (ý A của LIT). Giới hạn: robot điểm, bỏ qua giới hạn quay của robot và tường. Bản PDF nguồn gốc (Robertson/NUS; Isaacs) **không mở được**, công thức là tự suy
(khớp với công thức nhớ từ Isaacs); kiểm số bằng lưới min-max **chưa xong, đã dừng**. Phải tra Isaacs hoặc Pachter & Coates (DGAA 2019) trước khi in.

### 0.3 Hiện tượng "người rẽ muộn" đã được người khác ghi là lỗi còn mở
- **HEIGHT** [TV, 2411.12150 §V-C4]: va khi "a human arrives at its goal and suddenly changes directions to a new goal … due to its speed limit, the robot sometimes cannot switch … in time". Robot họ v_max 0.5 m/s.
- **DRL-VO** [TV, 2301.06512 §IV-C4]: hỏng vì "unexpected sudden changes in pedestrian movement" và mất vết do che khuất.
- **ABS** [TV, 2401.17583 §IX-E]: "RA values are learned with static obstacles, and can only generalize to quasi-static … If a dynamic object moves faster than the velocity limit of the recovery policy, the collision may happen."
- **DODGER** [TV, 2609.38873]: hai người bị gộp thành một cụm → vận tốc giả. **Cùng loại lỗi với BlobTracker**.
- **SCRAMPPI** [TV, 2603.26995 §VII]: "assumes a static environment; … dynamic obstacles … remain open challenges".

Đối chiếu dữ liệu của ta (đọc lại CSV, không chạy mới; lượt **có chạm người**, −2 s): dev3 mọi cấu hình n = 803: 51 % đang hướng vào, 15 % đứng yên; dev2 n = 59: 54 % / 17 %
(PROTOCOL ghi 21–48 %: khác bộ/định nghĩa, cần thống nhất). Riêng `p2+turn` (n ≈ 34): **21 % đứng yên ở −2 s**; góc rẽ cần thiết của người *đang đi*: trung vị 14°, p90 46°;
60 % là "mải điện thoại" (tỉ lệ nền 30 %); **69 % chạm ở |bearing| < 45°** (mũi), 20 % ở hông; 77 % có |wz| > 0.3 lúc chạm (at_fault nhiễu), 66 % robot KHÔNG tiến vào (≤ 0.1 m/s).
→ (i) `turn_cost` bỏ qua người sp ≤ 0.2 nên **mù với ~1/5** số va; (ii) ý C của LIT (xoay thân) theo chính tiêu chí bác bỏ của LIT là **yếu** (đa số chạm mũi). n nhỏ, chưa kiểm định.

---
## 1. Danh mục dự án

### 1.1 MPPI / MPC động
| Dự án (bài) | Giấy phép; ngôn ngữ; cập nhật | Thuật toán ở đâu | Rẽ muộn / robot chậm / thân dài / bão hoà | Hạn chế lộ ra |
|---|---|---|---|---|
| **Nav2 MPPI** ([2307.15236](https://arxiv.org/abs/2307.15236)) [MÃ] | gói này **MIT** (`LICENSE.md`; một số file đầu đề Apache-2.0); C++/Eigen; 11/2026, sao 5.1k | `navigation2/nav2_mppi_controller/src/optimizer.cpp:657` (cập nhật), `include/…/motion_models.hpp:89` (động học + trễ), `src/critics/*` | Người = ô costmap tức thời, **không dự đoán**. Thân: footprint tuỳ chọn. Trễ từng trục `model_delay_vx/vy/wz` (issue #6065, 4/2026) + giới hạn gia tốc + `OmniConstraintCritic` (elip vận tốc). **Không có hệ số đạt/bão hoà** | Issue **#1597** (dynamic obstacles) **mở từ 2020**, 5/2026 tác giả: "on pause". #6065: robot "heavy or long" bị overshoot/zigzag nếu không có trễ |
| **DRA-MPPI** ([2506.21205](https://arxiv.org/abs/2506.21205), IROS 25) [MÃ][TV] | **không giấy phép** (`package.xml` TODO); PyTorch+ROS1, GPU; 6/2026 | `dra-mppi/src/mppi_planner/src/prob_mppi/dynamic_obstacles.py:257` (MC), `jackal_objective.py:114`, cấu hình `run_sim_jackal.yaml` | Có: MoG, người đổi hướng Markov 0.975/0.025. Robot 2 m/s trong hành lang 6 m. 1 đĩa r 0.825. Unicycle, lệnh = vận tốc | Vanilla họ so 86/61/43 %, DRA 100/98/98 % (4/8/12 người). Người thật: **motion capture**. Trong mã: (a) Σ **hằng 0.3 → cov²** (σ = 0.3 m mọi t, không phồng), (b) hợp xác suất tính trên **mật độ** `1−∏(1−p)` (p có thể 1.77 > 1): ví dụ 3 người chồng σ 0.3 cho 0.892 so với đúng 0.969, (c) `u_min = 0.5 m/s` (mẫu thường không dừng được, chỉ có 1 mẫu null) |
| **mpc_planner** T-MPC++/SH-MPC ([2401.06021](https://arxiv.org/abs/2401.06021) T-RO; [2307.01070](https://arxiv.org/abs/2307.01070) IJRR) [MÃ] | **Apache-2.0**; C++/CasADi, acados (mở) hoặc Forces Pro (thương mại); 3/2025 | `mpc_planner/mpc_planner_modules/scripts/gaussian_constraints.py:74–116`, `src/guidance_constraints.cpp:359`; `guidance_planner/src/prm.cpp`, `homotopy_comparison/homology.cpp` | Chance constraint Gauss (risk 0.05), mode chỉ qua SH-MPC. `n_discs` hỗ trợ thân dài (mặc định Jackal = 1). Robot nhanh (3 m/s) | Issue mở #16–18 (QP fail, SH-MPC khó dùng); mã "Multiple modes not yet supported" trong wrapper Jackal |
| **Contingency-MPPI** ([2412.09777](https://arxiv.org/abs/2412.09777), L4DC 25) [MÃ] | **không giấy phép** (TODO); JAX, cần SNOPT (bản quyền) hoặc ipopt; 5/2025 | `Contingency-MPPI/branch_mppi/jax_mppi/nested_mppi_planners.py:108` (mini_mppi_ais), `reachability.py` | Không người, tập an toàn cố định | SCRAMPPI đo lại: 44 % (100 mẫu trong) / 84 % (1000), 17/126 ms GPU. Mã dùng `best_u = lowest_u` (dòng 210, 272): **lấy mẫu rẻ nhất chứ không trung bình** — khác tên "MPPI" |
| **SCRAMPPI** ([2603.26995](https://arxiv.org/abs/2603.26995)) [TV] | **không tìm thấy repo** | Alg. 1: RBR nhóm + V(x) | Tĩnh; unicycle; không người | Tự nhận ≤ 3–4 chiều, môi trường tĩnh |
| **CN-CBF / RNTC-MPC** [MÃ][TV] | **MIT**; ROS2 Humble, CasADi, PyTorch; 7/2026 (bài v2 6/7/2026) | `CN-CBF/ros2_ws/src/cn_cbf/safety_filter/safety_filter/cn_cbf.py:380`; baseline `nominal_controller/*.py` | Xem 0.1. Robot v ∈ [0.25, 1], **không dừng được** | Trong mã: baseline chỉ nhận **4 người gần nhất** (`max_num_people: 4`) còn CN-CBF nhận tất cả; `vo_mpc.yaml` 10 Hz/15 bước ≠ bài "20 Hz, 2 s". Repo **không chứa mã giải HJ**, chỉ có trọng số `.pth` |
| **PGIF-MPPI** ([2608.08323](https://arxiv.org/abs/2608.08323)) [MÃ][TV] | **MIT**; JAX, 1 file; 6/2026 | `PGIF_MPPI/mppi_dynamic_humans.py:181–217` | Nón trước người, CV/tròn biết trước; robot 2 m/s; điểm | Timeout 7→22→**59 %** khi đông; baseline "vanilla" coi người **đứng yên** (yếu); người tròn được cho biết trước tâm/ω |
| **Risk-aware MPPI hệ lai** ([2411.09198](https://arxiv.org/abs/2411.09198)) [TT] | **không giấy phép**; JAX; 4/2025* | `social-navigation/mppi_foresee_multi_humans.py` (chỉ xem danh sách) | Người đổi mode theo vùng chú ý | Mã nghiên cứu, nhiều bản trùng |
| **CFM-MPPI** ([2508.01192](https://arxiv.org/abs/2508.01192)) [MÃ] | **mâu thuẫn**: `setup.py:40` CC-by-NC, dòng 45 classifier MIT, không file LICENSE; PyTorch GPU; 3/2026 | `cfm_mppi/cfm_mppi/mppi/flowmppi.py`, `reward.py` | CV, biết vị trí chính xác; λ 0.1, σ (0.3, 0.6), lề 0.5 | 'assume … exact positions and velocities' |
| **pytorch_mppi** [MÃ] | **MIT**; 3/2026, sao 774 | `pytorch_mppi/src/pytorch_mppi/mppi.py:35, 451 (SMPPI), 593 (KMPPI)` | Thư viện. Có M rollout ngẫu nhiên + `rollout_var_cost` (dòng 372) | Không có người |
| **mppi-isaac, mppi_torch, biased-mppi, interaction_aware_mppi** (RA-L 25, RA-L 24, …) [MÃ một phần] | **cả 4 không file giấy phép**; mppi-isaac cần IsaacGym (NVIDIA) + mppi_torch; 8/2025, 6/2024, 5/2024, 5/2024 | `biased-mppi/examples/point_robot/priors.py`; `interaction_aware_mppi/ia_mppi/ia_mppi.py:77` | Biased: mồi mẫu bằng bộ điều khiển phụ | mppi-isaac issue #44 "robot goes through obstacles"; ví dụ là mô phỏng tiếp xúc, không phải đám đông |
| **log-MPPI_ros** ([2203.16599](https://arxiv.org/abs/2203.16599)) [TT] | **MIT**; 5/2024* | chưa mở | – | đã có `log_noise` |

### 1.2 Crowd navigation
| Dự án (bài) | Giấy phép; cập nhật | Ở đâu | Cách xử lý 4 vấn đề | Hạn chế |
|---|---|---|---|---|
| **CrowdNav** SARL (ICRA 19) [MÃ] | MIT; 10/2021 | `CrowdNav/crowd_nav/policy/sarl.py`, `multi_human_rl.py`, ORCA `crowd_sim/envs/policy/orca.py:58–66` | Người ORCA, robot **vô hình**; toàn v 1 m/s, tròn 0.3, không vật tĩnh, lệnh tức thì | issue #66/#71 (không có vật tĩnh), #37–57 khó train lại |
| **RGL** (IROS 20) [TT] | **không giấy phép**; 12/2020 | `RelationalGraphLearning/` | như CrowdNav | issue #26: train bằng vị trí thật? |
| **CrowdNav++** AttnGraph ([2203.01821](https://arxiv.org/abs/2203.01821)) [MÃ] | MIT; 12/2024 | phạt va với **dự đoán**: `crowd_sim/envs/crowd_sim_pred.py:216–233` | **Người đổi đích giữa chừng** p = 0.5 (`configs/config.py:79–84`): chính là "rẽ muộn" trong train | "simulated human behaviors are far from realistic"; người thật 83 % (18 lượt); issue #18: unicycle không học được |
| **HEIGHT** ([2411.12150](https://arxiv.org/abs/2411.12150)) [MÃ] | MIT; 12/2025 | PPO+transformer `training/networks/`; DWA `crowd_nav/policy/dwa.py:204`; `visible_prob = 0.2` (`config.py:343`) | Vật tĩnh + người; **động học bậc 1 của TurtleBot** trong DWA (σ 3.65/4.51/0.85/0.22) | 0.3; issue #6, #8 sim2real hỏng |
| **DRL-VO** ([2301.06512](https://arxiv.org/abs/2301.06512), T-RO 23) [MÃ] | **GPL-3.0**; 9/2025 (bản BARN 2022: MIT) | `drl_vo_nav/drl_vo/src/turtlebot_gym/turtlebot_gym/envs/drl_nav_env.py:1010` | VO với v CV; v_max 0.5 (gần ta) | 0.3 |
| **SICNav** (T-RO 24, [2310.10982](https://arxiv.org/abs/2310.10982)) [TT] | MIT; 7/2025* | `safe-interactive-crowdnav/sicnav/` | MPC hai tầng, người theo ORCA | Giả thiết người hợp tác |
| **RVO2** [MÃ] / Python-RVO2 [TT] | Apache-2.0 (tài liệu CC-BY-SA); 10/2026 / 5/2024* | `RVO2/src/Agent.cc:539–616` | CV, trách nhiệm ½ (dòng 607), holonomic tròn | không thân dài, không quán tính |
| **PySocialForce**, **lightsfm**, HuNavSim | MIT 10/2020, BSD-3 1/2026, MIT 9/2026* | `PySocialForce/pysocialforce/config/default.toml`; `lightsfm/include/sfm.hpp:48–52` | Mô hình người | PySocialForce issue #8 "agent_radius has not been considered". HuNavSim có 6 hành vi (regular, impassive, surprised, curious, scared, threatening) |
| **CVM** (Schöller, RA-L 20) [MÃ] | MIT (dữ liệu lấy từ SGAN: quyền dữ liệu chưa kiểm); 7/2020 | `constant_velocity_pedestrian_motion/evaluate.py:19, 34–49` | **OUR-S: quay vận tốc theo N(0, 25°)** | chỉ numpy/torch vài dòng, chạy CPU |
| DR-SPAAM, Frozone | GPL-3.0 (12/2020), không giấy phép (3/2020) [TT] | – | phát hiện người / chống đông cứng | – |

### 1.3 Chó 4 chân
| Dự án | Giấy phép; cập nhật | Nội dung | Hạn chế |
|---|---|---|---|
| **ABS** (RSS 24) [MÃ một phần][TV] | **CC BY-NC 4.0** (chỉ ghi README); 7/2024* | `ABS/training/legged_gym/legged_gym/scripts/testbed.py:55–68` (tối ưu twist phục hồi: vx ±1.5, vy ±0.3, wz ±3), `:205` (mạng RA 19-64-64-1) | 0.3. Học cả tầng gait, không áp lên sport mode |
| **REASAN** ([2512.09537](https://arxiv.org/abs/2512.09537), **Go2**) [TT+TV mục hạn chế] | **GPLv3** (README); 7/2026* (checkout lỗi, chỉ đọc README/cây file) | 4 mạng: gait, lọc an toàn, điều hướng, ước lượng LiDAR | Không thấy vật < 0.34 m: **cùng vùng mù LiDAR Go2**; quét vật treo từ sau |
| **NavRL** ([2409.15634](https://arxiv.org/abs/2409.15634), RA-L 25) [MÃ] | MIT; 7/2025*; 126 issue mở | Go2 chỉ là ví dụ Isaac. Lá chắn **ORCA trách nhiệm = 1**: `NavRL/ros2/navigation_runner/include/navigation_runner/safeAction.cpp:135` (`agentVel + 1.0*u`), horizon 2 s, lề 0.3 | CV, cầu; issue #151 Orin NX 100–500 ms |
| **OmniPerception** (CoRL 25, [2505.19214](https://arxiv.org/abs/2505.19214)) [TT] | huy hiệu MIT nhưng **không file LICENSE**; 11/2025* | README: training "In Progress", deploy "Planned" → chưa tái hiện được |
| **SEA-Nav** ([2603.09460](https://arxiv.org/abs/2603.09460), Go2 + L1) [TT] | không giấy phép; 8/2026* | chưa clone | |
| **DODGER** ([2609.38873](https://arxiv.org/abs/2609.38873), G1) [MÃ] | Apache-2.0; 9/2026 | DPCBF đóng kín, **holonomic (vx, vy, wz)**: `dodger/training/training/_src/locomotion/g1/multi_obstacle_navigation/dpcbf.py:91–165`, tham số `config.py:45–75` | vật tròn, CV |
| go2_ros2_sdk [MÃ cấu hình] | BSD-2; 7/2026* | Nav2 **DWB, 3 Hz**, `max_vel_y 0`, `max_vel_x 3.0` (`go2_robot_sdk/config/nav2_params.yaml`) | issue #231: odom trễ 2–3 s, #237: LiDAR chỉ ~5×5 m |
| unitree_ros2, unitree_rl_lab [TT] | BSD-3 7/2026*, Apache-2.0 5/2026* | SDK / gait RL Isaac Lab | không có né người |
| unitree_navigation (darkheaven1419-debug) [MÃ cấu hình] | MIT; 6/2026* | Nav2 MPPI cho Go2 | **Đừng tin số**: tên tham số sai (`repulse_weight`, `vx_stddev`, `max_vel_x` không phải tham số Nav2 → chạy mặc định); dùng Ackermann cho Go2 |
| agile_navigation ([2403.10101](https://arxiv.org/abs/2403.10101)) [TT] | không giấy phép; 3/2024* | elip dị hướng | không người |

Không mở được / không có mã tìm thấy: SCRAMPPI, PL-CBF (2605.16588), VOP-Nav (2607.15036), C2U-MPPI (2501.08520), REBot/UEREBot, FutureRay (HTML bài mở được, không thấy link mã), CoCoNav (chỉ thấy link mô phỏng `zsibot/matrix`),
`oscardegroot/scenario_module` (README mpc_planner nhắc, chưa clone), CUDA/Forces. Chưa tìm thấy cài đặt mở nào của Nav2-MPPI **có** dự đoán người.

---
## 2. (1) Ta đang làm lại y như ai, và khoảng trống
| Thành phần của ta | Đã có ở | Phán quyết |
|---|---|---|
| MPPI, mẫu tương quan, mẫu đứng yên, mẫu bám đường | Nav2, mppi_torch (`sample_null_action`), KMPPI | không mới |
| `near_goal` | Nav2 `near_goal_distance` (đã ghi nguồn) | không mới |
| λ thích nghi theo phân vị (`lam_q/lam_c`) | mppi_torch: chỉnh β theo η ∈ [5, 10] (`dra-mppi/…/planner/mppi.py:257–268`) | không mới |
| Người CV + exp(−d/len) | Nav2/PGIF/CFM… | không mới |
| `people_cap` 2 vòng tròn | mpc_planner `n_discs`; DRA `cost_functions.py` (4×4 đĩa) | không mới |
| Trễ trong rollout, hệ số từng trục online | Nav2 `model_delay_*`; HEIGHT DWA bậc 1 | trễ: không mới; **hệ số + bão hoà + bất đối xứng đo được**: chưa thấy trong repo nào đã mở |
| Mồi RL, critic cuối | Biased-MPPI, CFM-MPPI, CoRL-MPPI/RAY-TOLD | không mới |
| `mode` (giữ phía lách) | SCRAMPPI nhóm đồng luân, T-MPC++ `consistency 0.75` | không mới, đã đo không lợi |
| `unc` phồng bán kính, nghi ngờ | chance-constraint Gauss | không mới |
| `turn` (người rẽ vào) | **CN-CBF (xấu nhất)**, PGIF (nón), DRA-MPPI (mode rẽ) | ý không mới; tổ hợp *xác suất góc + trong mọi trạng thái rollout + tường chặn phía lách + robot chậm 3×* chưa thấy |
| `lat` đẩy vị trí người theo trễ | chuẩn | không mới |
| `vis` vùng mù sát thân | REASAN chỉ nêu hạn chế | chưa thấy ai đưa vào cost; nhưng ảnh hưởng của ta chưa chứng minh |

**Khoảng trống (không repo nào đã mở làm):** (G-a) giá trị "còn né được" **xác suất, hữu hạn tầm** khi γ ≪ 1 — nơi V∞ suy biến (0.2); (G-b) cùng lúc người rẽ + vật tĩnh + thân dài + gait bão hoà;
(G-c) **người đang đứng** bắt đầu đi (HEIGHT nêu, không ai xử lý trong bộ lập); (G-d) Nav2-MPPI chuẩn chưa có người dự đoán: một critic CPU ≤ 5 ms có giá trị thực dụng;
(G-e) so công bằng với người **không hợp tác** dùng tracker thật: CN-CBF/PGIF/CFM/DRA-sim đều cho biết trạng thái người.

## 3. (2) Năm cải tiến cụ thể lên công trình người khác
**A. CN-CBF → giá trị né hữu hạn tầm, ngẫu nhiên, trong MPPI (trùng ý A của LIT, nay có đối thủ rõ).**
Của họ: trạng thái tương đối + HJ + softmin + lọc 1 bước. Sửa: T = 3 s; ω đối kháng → xác suất góc rẽ (CVM N(0, 25°), và hazard đo); robot holonomic với bảng (tanh 0.29, lùi 1.26, vy 0.97, wz 0.85, τ);
l phụ thuộc yaw (2 đĩa); dùng trong **mọi trạng thái rollout** (RK = 1−∏(1−V)) thay QP. Hợp: ta ở vùng V∞ suy biến (0.2), chạm sớm nhất có thể phản ứng ~1.8–2.6 s.
Kiểm: (1) offline AUC tại −2/−1.5 s trên CSV dev (cần thêm log âm tính; hiện CSV chỉ lưu `lead` cho lượt chạm → **xin điều phối viên thêm log**), so với TTC, `turn`, PGIF, V∞; (2) fastsim DEV ghép cặp với `ppl=32` và `turn_const`; bỏ nếu ΔAUC < 0.03.
**B. DRA-MPPI → xác suất va CHÍNH XÁC trên CPU.** Của họ: MC 20 000 điểm, GPU, 97–114 ms, hợp trên mật độ, Σ hằng. Sửa: với mode Gauss đẳng hướng, P(‖q−X‖<r) = CDF χ² lệch tâm bậc 2 `ncx2.cdf((r/σ)², 2, (d/σ)²)` → **bảng 2D (d, σ_t)**; 2 đĩa (min/union cận trên); gộp ∏ trên *xác suất*; σ_t tăng; mode: thẳng + rẽ ±25/±50° (CVM) + "đang đứng sẽ đi".
Đã đo ngoại tuyến: 600×24×5 người×2 đĩa = **4.6 ms** numpy 1 luồng (1 mode; chưa kể lấy dữ liệu). Kiểm: fastsim DEV, `dra` so `ppl`, quét w_soft/ngưỡng với cùng ngân sách; báo cả bản "mật độ như mã gốc".
**C. Nav2 MPPI (delay + OmniConstraint 2026) → mô hình chấp hành đo được + tắt phạt có điều kiện.** Của họ: trễ, gia tốc, elip vận tốc. Sửa: `v̇ = (f_axis(u) − v)/τ`, f_x = 0.29·tanh(u/0.29), lùi ×1.26…, trễ 0.05 s; và **bỏ `fwd`/`lat`/PreferForward khi có mối đe doạ TTC < 2.5 s** (như near_goal bỏ lực đẩy).
Áp cho **mọi** baseline. Hợp: hiện rollout tuyến tính (ALGO đang thử `~nl`: số chưa hoàn chỉnh trong LOG). Kiểm: sai số dự đoán vị trí 1–2.4 s từ log sysid trước; rồi DEV, chỉ giữ nếu không hại bộ tĩnh.
**D. RBR nhóm của SCRAMPPI → cho CPU K = 600, có người.** Của họ: mẫu chết bị thay bằng mẫu sống cùng nhóm (ESS 0.446 so 0.321; thành công 100 so 92 %). Sửa: nhóm = {chuỗi cũ, bám đường, dừng, lách trái, lách phải, lùi, gợi ý RL}; tiêu chí sống = không va tĩnh **và** V_A < ngưỡng; so thứ hạng rồi đánh giá lại từ x0 như họ.
Hợp: ba `ppl`, `turn` cao dễ làm mẫu suy biến (chưa đo ESS theo cấu hình). Kiểm: ghi ESS đã có trong `last["ess"]`; K ∈ {150, 300, 600}. Tắt RL phải giữ (Bổ sung 1 PROTOCOL).
**E. Người đang đứng (HEIGHT + CrowdNav++ `goal_change`).** Của họ: chỉ train RL cho quen. Sửa: mode "khởi động": xác suất `1−exp(−t/τ_d)` với τ_d đo, hướng đều trên các hướng **không bị tường chặn** trong 1 m, v ~ 0.9, gia tốc 1/τ (τ=0.5). Hợp: 15–21 % lượt chạm có người đứng yên ở −2 s.
Kiểm: bộ kịch bản khởi-động riêng (LIT đã đề nghị) + DEV; coi chừng robot "sợ" người đứng (nhà có người ngồi): báo thêm timeout và độ lệch. Rủi ro: dwell 0.5–3 s là tham số SFM của mình.
Chọn chính: **A + B** (A là đóng góp, B là baseline tốt + thành phần); E gắn vào A; C là hạ tầng chung, D chỉ khi ESS thấp. Ưu tiên kiểm **trần** (LIT Bước 0) trước cả năm.

## 4. (3) Baseline nên cài lại trung thực (numpy, từ công thức; KHÔNG chép mã)
Cùng K, T, dt, mô hình chấp hành (C), tracker, người 0.22 m + lề; mỗi cái tối đa ~8 cấu hình DEV; ghi "cài lại từ công thức", nêu chỗ lệch.

| # | Baseline | Công thức / trọng số gốc (file) |
|---|---|---|
| 1 | **MPPI chỉnh** | có sẵn; `ppl=32`, `ppl=16;len=0.6` |
| 2 | **Nav2 MPPI (mặc định)** | `nav2_params.yaml` + critics: T 56×0.05 (2.8 s), K 2000, σ (0.2, 0.2, 0.4), λ 0.3, γ 0.015; `J += Σ γ/σ² u_i·ε_i` (`optimizer.cpp:663–679`); CostCritic 3.81/254, critical 300, collision 1e6, stride 2; PathAlign 10 (stride 4, bỏ nếu > 7 % đường bị chặn), PathFollow 5 (offset 6), PathAngle 2.2, Goal 5, GoalAngle 3, PreferForward 5, Constraint 4; SG 9 điểm `[-21,14,39,54,59,54,39,14,-21]/231`. Người = đĩa trong costmap (không dự đoán) → **baseline "không dự đoán"** |
| 3 | **PGIF** | `Σ exp(−½[(d∥/σ∥)²+(d⊥/σ⊥)²])`, σ∥ = 1.2+0.5s (trước) / 0.5 (sau), σ⊥ 0.6; gốc w 1e6, λ 1000, goal 1000, terminal 1000, path 5000, K 512, T 40 (`mppi_dynamic_humans.py:34–42, 206–217`). Quét {½,1,2,4}× và σ×{0.7,1} |
| 4 | **DRA-MPPI** | `C = 100·P̂ + 20000·[P̂>0.05]`, σ 0.3, r 0.825 (người+robot), goal×5, bám×5, tốc độ×2.2 (v_ref 1), T 19×0.2, K 400, chiết khấu 0.98, null action (`jackal_objective.py:75–127`, `run_sim_jackal.yaml`). Cài 2 bản: σ hằng (trung thực) và B (σ_t tăng, hợp xác suất) |
| 5 | **Chance-constraint Gauss** (mpc_planner) | `aᵀΔ − r − erfinv(1−2δ)·√(2aᵀΣa) ≥ 0`, δ = 0.05, Σ truyền; 2 đĩa (`gaussian_constraints.py:74–116`) |
| 6 | **ORCA, trách nhiệm 1** | `RVO2/src/Agent.cc:539–616` (bỏ ½ → 1 như NavRL `safeAction.cpp:135`); τ 2 s (NavRL) và 5 s (CrowdNav `orca.py:58–66`, +0.01 bán kính), người giữ vận tốc, v_max 0.29, LP 2D + dự phòng LP3 |
| 7 | **VO / heading DRL-VO** | `β = atan(3r/√(d²−9r²))`, chọn hướng tự do gần đích nhất trong N = 60 (`drl_nav_env.py:1010–1061`); làm baseline tay và làm thưởng RL: arrival 20, waypoint 3.2, collision −20, scan −0.2, angle 0.6 (ngưỡng π/6), rotation −0.1 (dòng 912–930) |
| 8 | **SFM robot** | `A 2, B 1, KI 1` (`CrowdNav_HEIGHT/crowd_nav/policy/social_force.py`, `config.py:496–498`) |
| 9 | **CBF lọc**: DPCBF | `h = x̃ + (√(s²−1)/r)(k_λ·d·ỹ²/v + k_μ·d)`, k_λ .5, k_μ 1, α 2, s 1.05, đóng kín, 3 hàng QP (`dpcbf.py:91–165`); QP nhỏ (3+n biến) giải numpy/scipy; **CN-CBF**: lấy hj_reachability (MIT) tự tính lưới (80×80×20×10, ~10 s GPU theo bài) — nếu đúng 0.2 thì V∞ suy biến, báo như kết quả âm |
| 10 | **CVM / CVM-S(25°)** | quay vận tốc N(0,25°) (`evaluate.py:34–49`), cắm vào `people` |
| 11 | **CrowdNav++ phạt dự đoán** | `−collision_penalty/2^{k+2}` với người dự đoán (`crowd_sim_pred.py:225–233`) — chỉ khi MODEL train lại |
| 12 | **Biased-MPPI / CFM** | thêm mẫu từ bộ điều khiển phụ, không trừ tỉ số quan trọng: chính là `prior` đang có (ablation) |

Không nên đòi: T-MPC++, SH-MPC, Contingency-MPPI (acados/SNOPT, GPU); nêu lý do, trích bài.

## 5. (4) Cảnh báo giấy phép (không phải tư vấn pháp lý)
- **Không giấy phép (mặc định giữ mọi quyền) → chỉ đọc, cài lại từ bài, không chép:** dra-mppi, Contingency-MPPI, biased-mppi, interaction_aware_mppi, mppi-isaac, mppi_torch, RGL, social-navigation (Parwana), SEA-Nav-Code, agile_navigation, frozone, OmniPerception (huy hiệu MIT không có file).
- **Copyleft/hạn chế:** DRL-VO **GPL-3.0**, REASAN GPLv3, DR-SPAAM GPL-3.0 → chép vào là cả phần phát hành phải GPL. **ABS CC BY-NC 4.0**; CFM-MPPI **mâu thuẫn** (CC-by-NC / MIT): coi như NC; hỏi tác giả.
- **Được dùng (giữ ghi công + LICENSE):** MIT: Nav2-MPPI (file có thể mang đầu đề Apache, giữ nguyên), pytorch_mppi, CrowdNav, HEIGHT, CrowdNav++, PySocialForce, NavRL, PGIF, CN-CBF (gói `hunav_gazebo_fortress_wrapper` trong repo khai "TODO", xem LICENSE riêng), NTC/RNTC, CVM, SICNav, hj_reachability, HuNavSim. Apache-2.0 (có điều khoản sáng chế, ghi thay đổi): mpc_planner, guidance_planner, RVO2, DODGER, unitree_rl_lab. BSD: lightsfm, unitree_ros2, go2_ros2_sdk.
- Phụ thuộc thương mại: Forces Pro, SNOPT, HSL MA57 (CN-CBF dùng để ra số trong bài), Isaac Gym.
- Dữ liệu ETH/UCY kèm CVM lấy từ SGAN: quyền dữ liệu chưa kiểm. Trọng số `.pth` CN-CBF: cùng MIT của repo nhưng huấn luyện cho v_p ≤ 1.2, robot 1 m/s.
- Bảng trong mục này do `gh api license` và đọc file; repo có thể đổi: chụp commit khi dùng (`git -C oss/X rev-parse HEAD`).

## 6. Cảnh báo về mô phỏng người của chính ta (phát hiện phụ)
`movers.py` ghi "tham số theo Moussaïd 2009 và PedSim" nhưng dùng `2.1·exp((r_i+r_j−d)/0.3)`: cặp (2.1, 0.3) là v0, σ của mô hình elip Helbing 1995 trong PySocialForce (`ped_repulsive_force`, lực gốc V0/σ ≈ 7) ghép với dạng trừ bán kính;
Moussaïd trong lightsfm dùng `factor 2.1·(f_v+f_θ)`, λ 2, γ 0.35, n 2, n' 3. Tức là **không trùng mô hình công bố nào** (tường A 2.0/B 0.12, gốc 10/0.2). Không chắc là lỗi (có thể chỉnh tay) nhưng **không được viết "theo Moussaïd 2009"**; nên thêm mô hình người thứ hai (lightsfm BSD/HuNavSim) cho VAL.
Đây là đề nghị cho điều phối viên, tôi không sửa.

## 7. Chưa chắc / không làm được
- HTML arXiv chuyển thành chữ: công thức trích đã đối chiếu mã ở PGIF, DRA, DODGER, Gauss, ORCA, VO; phần khác chỉ từ một nguồn.
- 2 điểm "mã khác bài" (DRA Σ hằng/hợp mật độ, CN-CBF 4 người/10 Hz) là đọc tĩnh, **chưa chạy**; có thể có cấu hình khác dùng lúc ra số bài. Với DRA: chỉ xét nhánh `simulation`.
- Bất đẳng thức homicidal chauffeur: tự suy, một lần; chưa kiểm số (lưới bị dừng), chưa xét robot quay chậm 0.85 rad/s (chỉ làm tệ hơn) hay tường.
- Số DEV mục 0.3: n nhỏ theo cấu hình, không kiểm định, chỉ từ lượt chạm (thiên lệch chọn mẫu).
- Tìm kiếm GitHub bằng `gh search`, web US; có thể sót repo (từ khoá "evasion", "kill zone", "suicidal pedestrian" chưa tìm riêng).
- 4.6 ms là trên máy này (BLAS 1 luồng), không phải Orin.
