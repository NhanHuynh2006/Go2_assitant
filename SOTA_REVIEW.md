# Tổng quan tài liệu trước khi chọn thuật toán (21/11/2026)

**Nguyên tắc.** Mỗi phần của GoVoice đi qua cùng một quy trình:

1. Tìm xem các nơi uy tín đã làm gì tốt nhất:
   - robot: ICRA, IROS, RSS, CoRL, T-RO, RA-L, IJRR, Science Robotics;
   - thị giác: CVPR, ICCV, ECCV;
   - học máy và ngôn ngữ: NeurIPS, ICML, ICLR, ACL, EMNLP.
2. Lập danh sách ứng viên mạnh nhất.
3. **Đo trên chính bài toán của mình**, cùng bộ bài, cùng chỉ số, nhiều lần lặp, rồi mới chọn.

Lý do phải đo: ở hầu hết các mảng, tài liệu **không** có một thuật toán thắng mọi bài. Kết quả
phụ thuộc vào robot, cảm biến, môi trường và cách đặt phần thưởng.

Ký hiệu cột "Quyết định":
- ✔ giữ;
- ↑ nâng cấp (đã làm hoặc đang làm);
- ◯ chưa làm (có lý do).

---

## 1. Né vật cản cục bộ (phần đang tối ưu)

### 1.1 Tài liệu nói gì
- **Cuộc thi BARN** (benchmark chung cho né vật cản trong không gian chật):
  - báo cáo ICRA 2022 (Xiao et al., IEEE RAM 2023) kết luận bài toán **chưa giải xong**;
  - đội thắng đổi mỗi năm;
  - năm 2024 đội thắng dùng **bộ lập đường học máy kiến trúc Transformer**, lần đầu tiên trong cuộc thi.
- **Môi trường đông người.** Arena-Bench (Kästner et al. 2022) so DRL với TEB, MPC, DWA, CADRL.
  Một bài năm 2026 cho thấy DWA và TEB **giảm mạnh** khi đông người. Tổng quan và benchmark
  Frontiers 2025 (Alyassi et al.) cho thấy nhiều phương pháp học vượt phương pháp mô hình,
  ví dụ khi đi qua cửa.
- **Cổ điển mạnh nhất hiện nay là họ MPPI:**
  - MPPI gốc: Williams et al., ICRA 2016 / T-RO 2018;
  - Nav2 chọn MPPI làm bộ điều khiển chính (Macenski et al., RAS 2023);
  - log-MPPI (Mohamed et al. 2022): nhiễu "normal × log-normal", giảm hơn 30 % phương sai, ít bị kẹt hơn;
  - Shield-MPPI (Yin et al. 2023): thêm CBF để có bảo đảm an toàn;
  - DBaS-Log-MPPI (2025);
  - C-Uniform MPPI (2025): lấy mẫu theo bản đồ, hợp với chỗ dày vật.
- **Học máy cho chó 4 chân:**
  - **ABS** (He et al., RSS 2024): Go1 chạy trên 3 m/s không va chạm, gồm policy RL nhanh cộng
    mạng giá trị reach-avoid để chuyển sang chế độ phục hồi;
  - VIPlanner (ICRA 2024);
  - Omni-Perception (CoRL 2025);
  - Top-Nav (CoRL 2025).
- **Né đám đông:**
  - CADRL (Chen et al., ICRA 2017);
  - SARL, có attention (Chen et al., ICRA 2019);
  - DS-RNN (Liu et al., ICRA 2021);
  - **DRL-VO** (Xie & Dames, T-RO 2023): PPO với phần thưởng dựa trên velocity obstacle, 55 người.

  Đa số các bài này dùng **PPO**.
- **Chọn thuật toán RL:**
  - PPO là mặc định khi chạy song song hàng nghìn môi trường trên GPU (Rudin et al., CoRL 2021);
  - **FastTD3** (Seo et al. 2025) và FastSAC: off-policy chạy song song, batch lớn, nhanh hơn PPO
    theo thời gian thực và có lúc tốt hơn;
  - các so sánh PPO/SAC/TD3 cho bài né vật cản **không thống nhất**: TD3/SAC thường đi đường
    ngắn hơn, PPO mượt và ít va chạm hơn;
  - nhiều bài chỉ ra **phần thưởng quyết định nhiều hơn thuật toán**.

### 1.2 Danh sách ứng viên và trạng thái
| Ứng viên | Nguồn | Trạng thái |
|---|---|---|
| Pure pursuit + phanh (bản cũ) | — | đối chứng |
| DWA | Fox et al., IEEE RAM 1997 | ↑ đã cài (`nav_local.DWA`) |
| **MPPI** | Williams ICRA 2016 / T-RO 2018; Nav2 | ↑ đã cài, mặc định |
| log-MPPI | Mohamed et al. 2022 | ↑ cài để so (`log_mppi`) |
| **PPO policy** | Schulman 2017; DRL-VO; ABS | ↑ đang train (`rl_nav/train_ppo.py`) |
| **FastTD3 policy** | Fujimoto ICML 2018; Seo et al. 2025 | ↑ đang train (`rl_nav/train_td3.py`) |
| RL + MPPI kiểm tra an toàn | ý tưởng ABS (RSS 2024), Shield-MPPI | ↑ đã cài (`rl_safe`) |
| TEB | Rösmann et al., RAS 2017 | ◯ hợp xe kiểu ô tô hơn. Nav2 chuyển từ TEB sang MPPI (RAS 2023) |
| Policy có attention cho người (SARL, DS-RNN) | ICRA 2019, ICRA 2021 | ◯ bước sau, nếu RL thắng ở bài đông người |
| Transformer (đội thắng BARN 2024) | BARN 2024 | ◯ cần dữ liệu lớn. Để sau khi có kết quả RL |
| C-Uniform MPPI | 2025 | ◯ chỉ là preprint; cài nếu MPPI còn kẹt ở chỗ dày |

### 1.3 Cách quyết định cái nào tốt nhất
- **Bộ bài:** `eval_sim.py --suite office`. Bản đồ 30 × 20 m, 8 bài:
  - khối vật so le;
  - văn phòng;
  - slalom cọc;
  - lối pallet;
  - đường dài tới bếp;
  - sảnh có 8 người;
  - kho có xe đẩy;
  - văn phòng có người.
- **Chỉ số:**
  - thành công, va chạm, SPL (Anderson et al. 2018);
  - thời gian;
  - **số lần khựng** (≥ 1 s dịch chuyển < 0.08 m/s);
  - tốc độ trung bình, số lần lắc hướng, khoảng hở nhỏ nhất.
- Mọi cấu hình chạy **cùng bản đồ, cùng điểm xuất phát, cùng seed đám đông**, và bản đồ được
  xoá trước mỗi lượt.
- **Thống kê:** ít nhất 3 lần lặp mỗi bài. Báo cáo trung bình ± khoảng tin cậy 95 %. Kiểm định
  Wilcoxon cặp (cùng bài, cùng seed) giữa ứng viên tốt nhất và MPPI.
- **RL được so công bằng:**
  - PPO và FastTD3 dùng cùng môi trường, cùng phần thưởng, cùng 20 phút GPU;
  - so trước trên bộ thử 2D cố định, rồi so trong Gazebo cùng với MPPI và DWA.

---

## 2. Phát hiện và dự đoán người
| | Đang dùng | Tốt nhất trong tài liệu | Quyết định |
|---|---|---|---|
| Phát hiện người | Gom cụm điểm LiDAR (BlobTracker), lọc "phải đi được ≥ 0.5 m" | **DR-SPAAM** (Jia, Hermans, Leibe, IROS 2020): 87 FPS trên laptop, 22 FPS trên Jetson AGX, có ROS node; bản tự giám sát (ICRA 2021) | ◯ trong sim người là hình trụ nên gom cụm là đủ. **Robot thật nên dùng DR-SPAAM** trên lát quét 2D của LiDAR L1 |
| Dự đoán đường đi người | Vận tốc không đổi | Social-LSTM (CVPR 2016), Social-GAN (CVPR 2018), Trajectron++ (ECCV 2020) | ✔ giữ vận tốc không đổi. Schöller et al. (RA-L 2020) cho thấy mô hình vận tốc không đổi ngang hoặc hơn nhiều mạng học sâu ở tầm 1–2 s, đúng tầm nhìn của MPPI |

## 3. Tìm đồ vật theo tên và màu (robot thật)
| Đang dùng | Tốt nhất trong tài liệu | Quyết định |
|---|---|---|
| Sim: danh mục đọc từ file .sdf. Thật: file yaml, hoặc `go2_perception/scene_graph.py` (YOLO) | Phát hiện từ vựng mở: **YOLO-World** (CVPR 2024, thời gian thực), Grounding DINO (ECCV 2024), OWL-ViT (ECCV 2022). Bản đồ ngữ nghĩa: VLMaps (ICRA 2023), ConceptGraphs (ICRA 2024), **HOV-SG** (Werby et al. 2024; 84.9 % so với 56.2 % của VLMaps trên HM3DSem) | ◯ bước tiếp cho robot thật: YOLO-World trên D435i + độ sâu → vị trí và màu đồ vật → `ObjectCatalog`, nối vào scene_graph có sẵn. HOV-SG khi cần nhiều phòng, nhiều tầng |

## 4. Hiểu lệnh (LLM)
| Đang dùng | Tài liệu | Quyết định |
|---|---|---|
| Luật (Combo, Reflex) → Qwen2.5-1.5B fine-tune QLoRA + **ép ngữ pháp GBNF** (Geng et al., EMNLP 2023) + verifier symbolic | SayCan (CoRL 2022), Code as Policies (ICRA 2023) dùng LLM lớn trên cloud. Mô hình nhỏ trên thiết bị: TinyLLM (2025), "Small Models, Big Tasks" (2025), ALRM (2026). Bài nhỏ fine-tune riêng cho lĩnh vực đạt ngang mô hình lớn | ✔ giữ kiến trúc: chạy trên Jetson, không cần mạng, đúng hướng các bài 2025. ◯ thử Qwen3-1.7B và Llama-3.2-1B/3B **trên cùng test 300 + 200 câu** trước khi đổi |

## 5. Nhận dạng tiếng Việt (ASR)
| Đang dùng | Tài liệu | Quyết định |
|---|---|---|
| PhoWhisper-small (CTranslate2), có tuỳ chọn zipformer streaming 30M | PhoWhisper (VinAI, ICLR 2024 Tiny Papers; bản large đạt WER 4.67 trên VIVOS). **VietASR** (2025): mô hình 68M, 50 giờ nhãn, vượt Whisper-large-v3, có bản streaming (Zipformer nhân quả). Vietnamese ASR Revisit (Findings EACL 2026) | ◯ đo WER **trên tập câu lệnh robot** (ghi âm vài trăm câu) cho PhoWhisper-small, zipformer và VietASR, rồi chọn. Hướng đúng cho Jetson là streaming nhỏ (VietASR, zipformer) |

## 6. Định vị trên bản đồ đã lưu (robot thật sau khi bật lại)
| Đang dùng | Tài liệu | Quyết định |
|---|---|---|
| Odometry (bắt đầu lại từ 0 mỗi lần bật). Repo ROS có KISS-ICP + bộ định vị bản đồ 3D | **FAST-LIO2** (T-RO 2022), KISS-ICP (RA-L 2023). Đánh giá cho thấy mỗi cái thắng ở loại cảnh khác nhau. Định vị lại trên bản đồ: ICP/NDT + nhận dạng nơi chốn (Scan Context, IROS 2018; RING++, T-RO 2023) | ◯ nối bộ định vị có sẵn vào GoVoice (map → odom) để bản đồ lưu dùng lại được sau khi tắt/bật. FAST-LIO2 nếu KISS-ICP trôi trên Go2 |

## 7. Nhiều robot
| Đang dùng | Tài liệu | Quyết định |
|---|---|---|
| Ưu tiên theo khoảng cách tới đích, nâng ưu tiên khi chờ quá 6 s, coi robot kia là vật động trong MPPI | ORCA (van den Berg et al., ISRR 2011), MAPF/CBS (Sharon et al., AIJ 2015), RoCo: LLM điều phối nhiều robot (ICRA 2024) | ✔ đủ cho 2 robot (94 % thành công, 0 va chạm). ◯ ORCA hoặc CBS nếu lên 3–4 robot ở hành lang hẹp |

---

## Nguồn
- BARN: [báo cáo ICRA 2022](https://arxiv.org/abs/2208.10473), [trang BARN](https://people.cs.gmu.edu/~xiao/Research/BARN_Challenge/BARN_Challenge26.html)
- Arena-Bench: [arXiv 2206.05728](https://arxiv.org/abs/2206.05728)
- Benchmark điều hướng xã hội: [Frontiers 2025](https://www.frontiersin.org/articles/10.3389/frobt.2025.1658643/full)
- Nav2 và MPPI: [Macenski et al., RAS 2023](https://arxiv.org/abs/2307.15236)
- log-MPPI: [arXiv 2203.16599](https://arxiv.org/abs/2203.16599)
- Shield-MPPI: [arXiv 2302.11719](https://arxiv.org/abs/2302.11719)
- C-Uniform: [arXiv 2510.16905](https://www.arxiv.org/pdf/2510.16905)
- ABS: [RSS 2024](https://arxiv.org/abs/2401.17583)
- DRL-VO: [T-RO 2023](https://arxiv.org/abs/2301.06512)
- FastTD3: [arXiv 2505.22642](https://arxiv.org/abs/2505.22642)
- DR-SPAAM: [IROS 2020](https://arxiv.org/abs/2004.14079)
- HOV-SG: [arXiv 2403.17846](https://arxiv.org/abs/2403.17846)
- ConceptGraphs: [arXiv 2309.16650](https://arxiv.org/abs/2309.16650)
- PhoWhisper: [arXiv 2406.02555](https://arxiv.org/abs/2406.02555)
- VietASR: [arXiv 2505.21527](https://arxiv.org/abs/2505.21527)
- Vietnamese ASR Revisit: [Findings EACL 2026](https://aclanthology.org/2026.findings-eacl.345)
- TinyLLM: [arXiv 2511.22138](https://arxiv.org/html/2511.22138v1)
- Small Models, Big Tasks: [arXiv 2504.19277](https://arxiv.org/html/2504.19277v1)
- So sánh LiDAR SLAM: [arXiv 2509.06593](https://arxiv.org/pdf/2509.06593)
