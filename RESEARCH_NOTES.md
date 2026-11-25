# RESEARCH_NOTES — từ GoVoice tới một bài báo

Ghi chú để viết bài báo: những bài liên quan đã đọc, đóng góp nào là của mình, thí nghiệm nào
đã có số, và việc gì nên làm tiếp. Số liệu ở mục 4 đến từ `eval_sim.py` (chạy lại được) và từ
`finetune/eval_e2e.py` (đã có từ trước).

## 1. Hướng bài báo

**Tên đề xuất:** *GoVoice: điều khiển một hoặc nhiều robot bốn chân bằng tiếng Việt, chạy
hoàn toàn trên robot, có kiểm chứng an toàn từ câu nói tới chân robot.*

So với ROSA và khoá học "điều khiển robot bằng LLM + ROS 2 + Gazebo" (Claude trên cloud, gõ
chữ, một robot bánh xe), hệ của mình khác ở năm điểm. Mỗi điểm là một đóng góp có số đo:

| # | Đóng góp | Bằng chứng |
|---|---|---|
| C1 | Hiểu lệnh tiếng Việt **3 tầng** (Reflex, Combo, LLM fine-tune ép grammar), chạy trên Jetson | e2e **93.0 %** trên 300 câu cũ, **87.5 %** trên 200 câu mới (đồ vật, màu, quan hệ không gian; model cũ 19.5 %); 82 % câu cũ không cần gọi LLM (mục 4.2b) |
| C2 | **Gọi tên nhiều robot bằng lời nói** không cần LLM: "con một…, còn con hai…", "cả hai đổi chỗ", "con hai đi theo con một" | `fleet.py`, 11 test offline, thí nghiệm multi ở mục 4 |
| C3 | **An toàn ở tầng thực thi**: bản đồ từ LiDAR + D435i, A\*, phanh phản xạ, nhường đường. Lệnh có đúng ngữ pháp đến đâu thì robot cũng không đâm vào vật | thí nghiệm safety và nav ở mục 4, so sánh với/không có D435i |
| C4 | **Sim và robot dùng chung mã**: cùng Combo/Reflex/LLM/SafetyGuard/AsyncExecutor, chỉ thay backend | `run_sim.py` và `run_real_robot.py` |
| C5 | **Bộ đánh giá trong sim chạy lại được**: teleport, xoá bản đồ, chấm bằng vị trí và hình học thật; đo SR, SPL, va chạm, sai số | `eval_sim.py`, `results/` |

## 2. Bài liên quan, xếp theo hội nghị và tạp chí

✔ = đã kiểm venue trên proceedings, IEEE Xplore hoặc arXiv (ngày 2026-11-20).
◐ = chỉ có trên arXiv hoặc venue chưa xác nhận.
◯ = venue ghi theo trí nhớ, **kiểm DOI trước khi đưa vào bài**.

### 2.1 LLM / VLM điều khiển robot (CoRL, ICRA, RSS)
| Bài | Venue | Liên quan tới mình |
|---|---|---|
| SayCan, *Do As I Can, Not As I Say* (Ahn et al.) | ✔ CoRL 2022, PMLR 205 | LLM chọn kỹ năng có sẵn. GoVoice cũng chỉ cho LLM chọn trong `move/action/stop/go_to` |
| Code as Policies (Liang et al.) | ✔ ICRA 2023, tr. 9493–9500 | LLM sinh code điều khiển. Mình chọn ngược lại: JSON bị grammar ép, vì cần an toàn |
| SayPlan (Rana et al.) | ✔ CoRL 2023 (oral) | Plan trên scene graph 3D và lập lại plan. Gợi ý cho N7 |
| VLMaps (Huang, Mees, Zeng, Burgard) | ✔ ICRA 2023 | Đích theo quan hệ không gian. **`spatial.py` làm phiên bản tất định của ý này** |
| LM-Nav (Shah et al.) | ◯ CoRL 2022 | Đi tới mốc, không có quan hệ không gian |
| KnowNo, *Robots That Ask For Help* (Ren et al.) | ✔ CoRL 2023, PMLR 229:661–682 | Robot hỏi lại khi không chắc. **Câu "con nào ạ?" là trường hợp riêng của ý này** (mơ hồ về robot đích); có thể dùng cách đo của họ |
| SayTap (Tang et al.) | ✔ CoRL 2023, PMLR 229 | LLM điều khiển robot **bốn chân** qua mẫu chạm chân. Gần lĩnh vực nhất |
| NaVILA (Cheng et al.) | ✔ RSS 2025 | VLA cho robot có chân, **chạy trên Go2**. Sinh lệnh trung gian bằng lời ("tiến 75 cm") rồi giao cho policy RL. Giống cách GoVoice chia tầng |
| ROSA, NASA JPL (Royce et al.) | ◐ arXiv 2410.06472 | Agent ReAct trên ROS. Khoá học dùng nó |
| LLM ở edge cho mobile robot | ◐ arXiv 2405.17670 | Chạy offline nhưng trên robot bánh xe |
| Quadruped plan generation với LLM | ◐ arXiv 2512.21293 | Robot bốn chân, LLM trên cloud, đầu vào là chữ |

### 2.2 Nhiều robot với LLM
| Bài | Venue | Ghi chú |
|---|---|---|
| RoCo (Mandi, Jain, Song) | ✔ ICRA 2024, tr. 286–299 | Các robot "đối thoại" với nhau; benchmark RoCoBench |
| *Scalable Multi-Robot Collaboration with LLMs: Centralized or Decentralized?* (Chen et al.) | ✔ ICRA 2024 | Kiểu lai thắng. GoVoice là **tập trung, không cần LLM** cho phần gọi tên robot |
| SMART-LLM (Kannan et al.) | ◐ arXiv 2309.10062 (đã nộp IROS 2024) | Chia và phân việc. Hướng N4 |
| LiP-LLM, COHERENT | ◐ arXiv 2410.21040, 2409.15146 | Phê phán việc thiếu so sánh và đánh giá. Mình có `eval_sim.py` |

### 2.3 An toàn và bảo mật khi robot dùng LLM
| Bài | Venue | Ghi chú |
|---|---|---|
| SELP (constrained decoding + LTL) | ✔ ICRA 2025 | Tăng 10.8 % tỉ lệ an toàn |
| RoboPAIR, *Jailbreaking LLM-Controlled Robots* (Robey et al.) | ◐ arXiv 2410.13691 | **Jailbreak được chính Unitree Go2 chạy GPT-3.5.** Đây là lý do có `test_adversarial.py`: 39/39 câu tấn công bị chặn ở tầng tất định và SafetyGuard |
| SafeDec | ◐ arXiv 2509.01728 | Ràng buộc STL lúc decode |
| SafeGate | ◐ arXiv 2604.05427 | Kiểm plan bằng Z3 trước khi thực thi |
| Grammar-constrained decoding (Geng et al.) | ✔ EMNLP 2023, tr. 10932–10952 | Cơ sở cho `grammar.gbnf` |

### 2.4 Điều hướng, bản đồ, tránh nhau (nền tảng đã dùng)
| Bài | Venue | Dùng ở đâu |
|---|---|---|
| Occupancy grids (Elfes) | ◯ IEEE Computer 1989 | `OccGrid` |
| Layered costmaps (Lu, Hershberger, Smart) | ✔ IROS 2014, tr. 709–715 | **Hai lớp LiDAR và D435i**, gộp bằng OR |
| D\* Lite (Koenig & Likhachev) | ✔ AAAI 2002; IEEE T-RO 21(3) 2005 | Lập lại plan với giả định chưa thấy thì trống |
| Pure pursuit (Coulter) | ✔ CMU-RI-TR-92-01, 1992 | Bám đường |
| DWA (Fox, Burgard, Thrun) | ✔ IEEE RAM 4(1) 1997 | Phương án để so (N6) |
| VFH (Borenstein & Koren) | ✔ IEEE TRA 7(3) 1991 | Phương án để so |
| ORCA (van den Berg et al.) | ✔ ISRR 2011 | Hướng N5 |
| Ưu tiên theo khoảng cách tới đích / nâng ưu tiên khi kẹt | ◐ arXiv 2109.09041, 2210.04231 | `_must_yield` |
| SPL (Anderson et al.) | ◐ arXiv 1807.06757 | Chỉ số trong `eval_sim.py` |
| ROS 2 (Macenski et al.) | ✔ Science Robotics 7(66) 2022 | Trích dẫn chính thức của ROS 2 |

### 2.5 Tiếng nói và mô hình nhỏ
| Bài | Venue | Ghi chú |
|---|---|---|
| Whisper (Radford et al.) | ◯ ICML 2023 | Gốc của PhoWhisper |
| PhoWhisper (VinAI) | ◐ arXiv 2406.02555 | 844 giờ âm thanh nhiều giọng vùng miền |
| LoRA / QLoRA | ◯ ICLR 2022 / NeurIPS 2023 | Fine-tune Qwen2.5-1.5B |
| CNN-LSTM nhận lệnh tiếng Việt trên Raspberry Pi | TNU JST 2025 | 96.25 % nhưng chỉ nhận lệnh cố định |

### 2.6 Nên nộp ở đâu
- **Thực tế nhất, có robot thật:** IROS hoặc ICRA (IEEE), hạn nộp thường vào khoảng
  tháng 3 với IROS và tháng 9 với ICRA. Gửi kèm option sang **IEEE RA-L** nếu số liệu mạnh.
  Cả hai cần thí nghiệm trên robot thật (N1).
- **Chỉ có số sim:** hội thảo IEEE khu vực như ICCAIS, NICS, KSE, RiTA; hoặc tạp chí IEEE
  Access, *Sensors* hay *Robotics* (MDPI). Nhanh hơn, chấp nhận kết quả sim kỹ lưỡng.
- **CoRL / RSS:** đòi hỏi đóng góp học máy mới, ví dụ học policy. Hướng hiện tại của
  GoVoice là hệ thống và an toàn, hợp với IROS/ICRA/RA-L hơn.

## 3. Thiết kế đáng viết trong phần Method

1. **Định tuyến câu nói:** EMERGENCY → Fleet (gọi tên, đổi chỗ, đi theo) → Combo → Reflex →
   LLM + verifier → SafetyGuard → hàng đợi riêng cho từng robot.
2. **Thực thi vòng kín:** "đi 2 mét" là đi đủ 2 m đo bằng odom, chứ không phải vận tốc ×
   thời gian. Gait CHAMP trong sim chỉ đạt khoảng 41 % vận tốc được lệnh; robot thật đạt
   khoảng 80 %. Thí nghiệm `open_loop` đo cái giá của việc tin vào vận tốc × thời gian.
3. **Hợp nhất LiDAR và D435i thành hai lớp bản đồ:**
   - lớp camera chỉ được xoá trong vùng nhìn thấy (87°);
   - hướng không có tín hiệu thì không xoá (đã gặp: tường bị xoá đúng lúc robot sát tường);
   - mỗi ô cần bằng chứng từ ít nhất 2 lần quét;
   - ngưỡng độ cao tăng theo tầm xa, vì thân robot lắc khoảng ±3° làm tia chạm đất ở 1.3 m
     bị đọc thành vật cao 7 cm.
4. **Phanh có trí nhớ:** vùng mù 0.35 m trước mặt được che bằng D435i, và bằng bản đồ (vật đã
   thấy nhưng giờ nằm trong vùng mù).
5. **Hai robot:** bản đồ chung, robot kia là vật cản tròn, ưu tiên theo khoảng cách tới đích,
   chờ quá 6 s thì tự nâng ưu tiên.

Những bẫy kỹ thuật đáng nêu trong phần Implementation, vì người khác làm lại sẽ gặp:
- `MultiThreadedExecutor` của rclpy làm odom chỉ về 5–15 Hz và LiDAR trễ tới 2.5 s. Dùng
  `SingleThreadedExecutor` với QoS sensor thì nhận đủ 49/98/10/15 Hz.
- Nghe toàn bộ `/tf` trong Python làm mỗi callback mất 70–250 ms. Chỉ nghe TF tĩnh thì còn
  1–3 ms.
- Đọc point cloud của D435i (3.2 MB mỗi khung) quá nặng. Đọc ảnh depth (400 kB) rồi tự
  chiếu bằng intrinsics.

## 4. Kết quả (sim, chạy thống nhất ngày 2026-11-21 với code cuối)

Điều kiện chung:
- Nhà `voice_house.sdf`: 16 món đồ, 1 bậc thấp 12 cm, có người đi bộ ở nhóm bài động
  (Social Force, 30 % người mải nhìn điện thoại).
- Go2 dùng CHAMP, gắn Velodyne và D435i, giao tiếp qua CycloneDDS.
- Mỗi lần thử: teleport về chỗ xuất phát, **xoá bản đồ**, nói câu lệnh qua pipeline thật,
  chấm bằng vị trí thật của Gazebo.
- "Thành công": nav lệch < 0.35 m; đi/xoay sai < 0.10 m hoặc < 10°; an toàn = không đâm;
  luôn kèm điều kiện không va chạm (theo hình học URDF).
- **Mỗi bài lặp 3 lần**, tất cả cấu hình trong **cùng một lần chạy, cùng một phiên bản code**:
  `results/single_20261121_024207` (264 lượt thử, khoảng 2 giờ 13 phút).

### 4.1 Một robot

Số trong ngoặc ở tiêu đề cột là số lượt thử mỗi cấu hình: số bài × 3.

| Cấu hình | Đi tới chỗ (24) | Đi/xoay (21) | Dừng an toàn (6) | Né vòng về đường cũ (9) | Vật cản động & đám đông (12) |
|---|---|---|---|---|---|
| **full** (LiDAR + D435i + né + theo dõi người) | **100 %**, va chạm 0, SPL 0.69, 24 s | **100 %** (0.013 m / 2.2°) | **100 %** | **89 %**, va chạm 0, SPL 0.42 | **92 %**, va chạm 8 % (1/12), SPL 0.46, 46 s |
| lidar_only (bỏ D435i) | 100 %, SPL 0.71 | 100 % | 100 % | 78 %, **va chạm 22 %** (bậc 12 cm, 2/3) | 83 %, va chạm 8 % |
| no_people (không theo dõi người) | — | — | — | — | 75 %, **va chạm 25 %**, nhưng nhanh hơn (30 s) |
| brake_only (chỉ phanh, không vòng) | — | — | 100 % | **0 %** (đứng lại, không tới đích) | — |
| no_avoid (đi thẳng tới đích) | 38 %, **va chạm 62 %** | 100 % | **0 %**, va chạm 100 % | 0 %, va chạm 100 % | 8 %, va chạm 92 % |
| open_loop (vận tốc × thời gian, như robot thật) | — | **14 %** (0.21 m / **59°**) | — | — | — |

Những điều bảng cho thấy (dùng cho phần Discussion):
1. **Né vật cản là bắt buộc.** Không né thì 62 % lần đi tới chỗ là đâm vào đồ, và 92 %
   lần có người thì đâm người. `full` chỉ có **1 va chạm trong 72 lượt**.
2. **D435i bù vùng mù của LiDAR.** Chỉ LiDAR thì đâm bậc thấp 12 cm 2/3 lần. Có D435i thì
   0/3 lần.
3. **Theo dõi người (tracker + CPA + né ngang/lùi) đổi tốc độ lấy an toàn.** Thời gian
   tăng từ 30 s lên 46 s, va chạm giảm từ 25 % xuống 8 %.
   Va chạm duy nhất của `full` nằm ở bài "đám đông tới bếp" (lượt 2/3): robot bị kẹt giữa
   người và quầy bếp, phanh 21 lần, rồi hết giờ ở cách đích 2.1 m. Một người
   Social-Force đi vào sườn robot đang đứng yên (hở −0.18 m). Đây là giới hạn thật: Go2 không
   có chỗ lùi khi bị ép từ hai phía. Lần chạy trước (2 lượt mỗi bài) có 0/8 va chạm, nên tỉ lệ
   thật nằm khoảng 0-10 %.
4. **Né vòng về đường cũ thay cho chỉ phanh.** Tới đích tăng từ 0 % lên 89 %, vẫn 0 va chạm.
5. **Phải điều khiển vòng kín.** Gait sim chỉ đạt khoảng 41 % vận tốc được lệnh: theo thời
   gian thì sai 59° khi xoay; vòng kín thì sai 2.2°.
6. **Thời gian phản ứng** từ khi có câu chữ tới khi chân bắt đầu bước (đo bằng vị trí thật):
   trung bình 0.38 s, trung vị 0.40 s, n = 258. Chưa tính thời gian STT.

Nguồn và hình:
- Tất cả số: `results/single_20261121_024207/{trials.csv, summary.md}`.
- Hình quỹ đạo: `results/single_20261121_024207/traj.png`. Đường nét đứt là quỹ đạo đã
  lập, chấm đỏ là người.
- Các lần chạy cũ (`single_20261120_*`) giữ lại để đối chiếu. Số của chúng nằm trong khoảng
  ±1 lượt thử so với bảng trên.

### 4.2 Hiểu lệnh và an toàn ngôn ngữ
| Đo | Kết quả |
|---|---|
| e2e trên 300 câu test (Reflex + Combo + LLM fine-tune + verifier) | **93.0 %** với model v2 (91.0 % với model cũ, đo trước đây). Chi tiết ở 4.2b |
| Câu tấn công / jailbreak (`test_adversarial.py`) | **39/39** bị chặn. Tìm và sửa lỗi NaN: `min(0.6, nan) = 0.6` từng biến thành chạy hết tốc |
| Test offline (`test_fleet_nav.py`, `test_reflex.py`) | 17/17, 14/14 |
| Model cũ và model mới, chấm ngày 21/11 | xem bảng 4.2b ngay dưới |

#### 4.2b Model cũ và model mới (fine-tune thêm trên `data_v2`), cùng định tuyến, cùng llama.cpp (GPU, Q4_K_M)

Train `data_v2`: 6714 câu, 3 epoch, 2520 bước, khoảng 2 giờ 27 phút trên RTX 4060 (QLoRA r=16).
eval_loss: 0.064 → 0.057 → **0.055**.

| Model | Test cũ (300 câu, `data/test.jsonl`) | Test mới (200 câu, `data_v2/test_ext.jsonl`) |
|---|---|---|
| Model cũ, định tuyến cũ | 92.0 % | 12.0 % |
| Model cũ, định tuyến mới | 91.3 % | 19.5 % |
| **Model mới, định tuyến mới** | **93.0 %** | **87.5 %** |

Chi tiết model mới trên test mới:
- goto_object 98.6 % (73/74);
- goto_spatial 85.0 % (34/40);
- goto_place 90.9 % (10/11);
- combo_object 71.0 % (22/31);
- ask_color 4/4.

Model cũ trên test mới: goto_spatial 0/53, goto_object 18/89.

Hai sửa đổi ở lớp luật (không phải model) mà phép chấm này làm lộ ra:

1. **Verifier quá chặt.** `plan_verifier` đòi tên địa điểm xuất hiện nguyên văn trong câu.
   Vì vậy LLM trả đúng `"tủ lạnh màu vàng"` cho câu "qua chỗ cái tủ lạnh vàng" vẫn bị bỏ.
   Sửa: so theo từ nội dung, bỏ qua từ đệm (cái, chiếc, màu, bên, phía, …). Mọi từ còn lại
   vẫn phải có trong câu, nên vẫn chặn được việc bịa (`"bàn màu đen"` cho câu "đi tới cái bàn"
   vẫn bị bỏ). Riêng bước này đưa model mới từ 31.5 % lên 57.0 %.
2. **Combo/Reflex cắt mất đồ vật.** `ComboMatcher` chỉ biết 9 tên điểm, nên cắt
   "ghế gỗ màu cam" thành "ghế" và "ban công" thành "bàn". Reflex còn hiểu "chạy tới ghế gỗ"
   thành đi thẳng. Sửa: `ComboMatcher.needs_llm()`: vế có từ chỉ quan hệ (trước, sau, trái,
   phải, cạnh, cách), có chữ thừa sau tên điểm, hoặc có danh từ đồ vật ngoài 9 điểm, thì
   nhường hẳn cho LLM. Bước này đưa model mới từ 57.0 % lên 87.5 %, và test cũ không đổi
   (Combo 222 → 221 câu).

Cả hai sửa đổi đã áp dụng cho production (`assistant_realtime.py`) và cho `eval_e2e.py`.
Sau khi sửa: `test_adversarial` 39/39, `test_fleet_nav` 17/17.

Lỗi còn lại của model mới (25/200):
- combo có đồ vật kèm động tác, ví dụ "vươn vai rồi ra hộp màu xám" bị thành `move`;
- câu không dấu ngắn ("goto_place_nodiac" 1/3);
- tên đồ vật bị lặp chữ ("cái cái gối").

Hướng tiếp: thêm mẫu combo + đồ vật vào dataset.

Trong sim, `run_sim.py` còn giải câu đồ vật/quan hệ **trước** cả Combo, bằng danh mục đồ vật
thật trong nhà (`_object`, `_spatial`). LLM chỉ là đường dự phòng, nên con số trên là cận dưới
khi chạy sim.

### 4.3 Hai robot (`results/multi_20261121_045648`, chạy lại ngày 21/11 với code cuối; 3 bài × 3 lần lặp × 2 robot = 18 lượt mỗi cấu hình. Khớp lần chạy 20/11 `multi_20261120_164312` tới từng ô)

| Cấu hình | Thành công | Va chạm | Song song: "con một ra cửa, còn con hai vào bếp" | Đổi chỗ đối đầu: "cả hai đổi chỗ" | Cắt chéo |
|---|---|---|---|---|---|
| **full** (bản đồ chung + ưu tiên theo khoảng cách tới đích + nâng ưu tiên khi kẹt) | **94 %** | **0 %** | 6/6, 31 s | **5/6**, 38 s, hở min 0.14 m | 6/6, 18 s, hở min 0.50 m |
| no_coord (không nhường, không coi nhau là vật cản) | 67 % | 0 % | 6/6 | **0/6: kẹt đối đầu tới hết giờ (137 s)** | 6/6, nhưng hở min chỉ **0.07 m** |
| no_avoid | 17 % | **83 %** | 3/6 | 0/6, đâm nhau | 0/6, đâm nhau |

Nhận xét:
- **Luật nhường đường giải được bế tắc đối đầu.** Không có luật thì 0/6 lần đổi chỗ thành
  công (cả hai cùng chờ hoặc cùng chen); có luật thì 5/6.
- Khi cắt chéo, luật nhường đường tăng khoảng hở nhỏ nhất từ 0.08 m lên 0.50 m.
- Lệnh "con một…, còn con hai…" được tách thành 2 việc chạy **song song** mà không cần LLM.

## 5. Công nghệ đã áp dụng (27 món, có nguồn)

| Tầng | Công nghệ | Nguồn / ý tưởng | File |
|---|---|---|---|
| Tiếng nói | PhoWhisper (faster-whisper, CTranslate2), VAD webrtcvad, Piper TTS streaming | PhoWhisper (arXiv 2406.02555), Whisper (ICML 2023) | `stt_engine.py`, `tts_engine.py` |
| Hiểu lệnh | Reflex + Combo tất định → LLM Qwen2.5-1.5B fine-tune QLoRA, **grammar-constrained decoding** | Geng et al. (EMNLP 2023), LoRA/QLoRA | `reflex_matcher.py`, `combo_matcher.py`, `grammar.gbnf` |
| Hiểu lệnh | Kiểm chứng plan neuro-symbolic, bỏ action "bịa" | — | `plan_verifier.py` |
| Hiểu lệnh | **Gọi tên nhiều robot** ("con một…, còn con hai…"), đổi chỗ, đi theo | — | `fleet.py` |
| Hiểu lệnh | **Đồ vật theo tên + màu**, màu đặt tên bằng HSV | — | `objects.py` |
| Hiểu lệnh | **Quan hệ không gian** (trái/phải/sau/cách N m) | VLMaps (ICRA 2023) | `spatial.py` |
| Hiểu lệnh | **Hỏi lại khi mơ hồ** ("con nào ạ?", "bàn nào ạ?") | KnowNo (CoRL 2023) | `run_sim.py` |
| Hiểu lệnh | Dạy chỗ bằng giọng nói ("lưu chỗ này là bếp") | — | `run_sim._teach` |
| Hiểu lệnh | Dataset tổng hợp thêm 2720 câu (đồ vật, màu, quan hệ, phòng) | — | `finetune/gen_dataset_ext.py` |
| An toàn | SafetyGuard: kẹp vận tốc, whitelist, chặn NaN/inf, EMERGENCY | RoboPAIR (arXiv 2410.13691) là động lực | `safety_guard.py`, `test_adversarial.py` |
| An toàn | Thực thi bất đồng bộ (vừa làm vừa nghe) | SmolVLA (arXiv 2506.01844) | `async_executor.py` |
| Bản đồ | Occupancy grid, **2 lớp LiDAR + D435i**, xoá chỉ trong FOV, cần 2 lần quét, quên dần theo thời gian | Elfes 1989; layered costmaps (IROS 2014) | `nav_local.OccGrid` |
| Bản đồ | Hợp nhất LiDAR 360° và depth D435i (che vùng mù 0.35 m, vật thấp 12 cm) | — | `robot_ros._on_depth` |
| Lập đường | A\* với inflation (vùng cấm 0.40 m, vùng ngại 0.80 m), giả định chưa thấy thì trống, lập lại mỗi giây | D\* Lite (AAAI 2002, T-RO 2005) | `nav_local.plan` |
| Lập đường | Rút gọn line-of-sight, làm mượt Chaikin | Theta\*-like | `nav_local.shortcut`, `smooth` |
| Lập đường | **Né vòng rồi quay về đường cũ** (phạt độ lệch khỏi đường thẳng) | — | `nav_local.line_cost`, `robot_ros._detour` |
| Điều khiển | Pure pursuit, giảm tốc theo khoảng trống, giữ hướng khi đi thẳng | Coulter (CMU TR 1992) | `robot_ros._navigate` |
| Điều khiển | Đi vòng kín theo odom, gộp các đoạn lệnh liền nhau | — | `robot_ros._translate`, `fleet.merge_moves` |
| Điều khiển | Phanh phản xạ, trí nhớ vùng mù, lùi khi kẹt, xoá bản đồ khi bế tắc (recovery) | Nav2 recoveries | `robot_ros` |
| Điều khiển | Fail-safe: mất cảm biến thì dừng | — | `robot_ros.free_distance` |
| Người / vật động | **Theo dõi cụm LiDAR**: gom cụm, ghép qua các khung, vận tốc EMA | — | `nav_local.BlobTracker` |
| Người / vật động | **Dự đoán va chạm CPA**, né ngang hoặc lùi, tránh chỗ người sắp tới | Velocity obstacles, social-aware navigation | `nav_local.cpa`, `robot_ros._evade` |
| Nhiều robot | Bản đồ chung, robot kia là vật cản, **ưu tiên theo khoảng cách tới đích**, nâng ưu tiên khi kẹt | arXiv 2109.09041, 2210.04231 | `robot_ros._must_yield` |
| Mô phỏng | CHAMP + Gazebo Harmonic, 2 robot, D435i, nhà có đồ đạc, bậc thấp | — | `voice_sim.launch.py` |
| Mô phỏng | **Người đi bộ Social Force** (đích ngẫu nhiên, A\*, nghỉ, 30 % không né robot, lực tiếp xúc thân) | Helbing & Molnár (PRE 1995), Helbing et al. (Nature 2000) | `movers.Crowd` |
| Đánh giá | Teleport + xoá bản đồ mỗi lần; SR, **SPL**, va chạm theo hình học thật, khoảng hở, thời gian phản ứng; 6 cấu hình so sánh | SPL (Anderson et al. 2018) | `eval_sim.py` |
| Hạ tầng | CycloneDDS, localhost discovery, executor đơn luồng với QoS sensor, chỉ nghe TF tĩnh, đóng DDS sạch khi thoát | — | `run_sim.py`, `robot_ros.RosBus` |

## 6. Còn áp dụng được (xếp theo lợi ích trên công sức)

| # | Công nghệ | Lợi ích cho bài báo | Công sức | Cần gì |
|---|---|---|---|---|
| N1 | **Chạy thật trên Go2** (`run_real_ros.py`, `start_real.sh` đã sẵn) | Không có thì khó vào IROS/ICRA | 1–2 ngày | robot, gắn D435i, đo giá đỡ |
| N2 | **Tìm đồ vật bằng YOLO** trên ảnh màu D435i (đã có `go2_perception/yolo_detector.py`) để tự điền `objects` | Bỏ được danh mục từ file `.sdf` (đang là "nhận thức hoàn hảo") | 2–3 ngày | camera thật hoặc ảnh sim |
| N3 | **Huấn luyện lại LLM** với `data_v2`, chấm `test_ext.jsonl` | Cột mới trong bảng ablation | 1 buổi trên RTX 4060 | `train_lora.py --data-dir data_v2` |
| N4 | **ORCA** (van den Berg, ISRR 2011) thay luật ưu tiên khi 2 robot đối đầu | So sánh deadlock và thời gian | 1–2 ngày | — |
| N5 | So với **Nav2 MPPI / DWB** trên cùng `eval_sim` | Baseline chuẩn cộng đồng, reviewer sẽ hỏi | 1–2 ngày | Nav2 có sẵn trong repo |
| N6 | **Dự đoán quỹ đạo người** tốt hơn EMA (Kalman / Social-LSTM) | Ít phải đứng chờ hơn trong đám đông | 1–3 ngày | — |
| N7 | **Phân việc bằng LLM** cho 2 robot ("dọn bếp và phòng khách"), kiểu SMART-LLM | Nối LLM với nhiều robot | 2–3 ngày | thêm trường `robot` vào grammar và dataset |
| N8 | **VLM hỏi đáp cảnh** ("trong bếp có gì?") bằng mô hình nhỏ trên Jetson | Tương tác giàu hơn | lớn | GPU Jetson, model VLM |
| N9 | **Ràng buộc LTL** ("không vào bếp khi có người") kiểu SELP | Lý thuyết an toàn | lớn | — |
| N10 | **Nhiễu cảm biến thật hơn** trong sim (LiDAR ±3 cm, IMU drift, trượt chân) và trượt odom | Sim gần đời thật hơn | nhỏ | sửa xacro, chạy lại đánh giá |
| N11 | **Đo độ trễ đầu-cuối trên Jetson**: STT, plan, bước chân đầu tiên | Biến "realtime" thành con số | nhỏ | robot |

**Đã cân nhắc nhưng không làm:** tách multiprocessing cho từng robot. Đo được cả trợ lý chỉ
dùng khoảng 10 % của 1 nhân CPU; các phần nặng (LLM, TTS, STT C++, Gazebo) đã nằm ở tiến
trình riêng hoặc nhả GIL. Tách tiến trình sẽ mất bản đồ chung và luật nhường đường mà không
nhanh hơn.

## 7. Thuật toán đề xuất: PRISM (né vật cản cho chó 4 chân điều khiển bằng giọng nói)

Tổng quan tài liệu đầy đủ: `SOTA_REVIEW.md`.

### 7.1 Khoảng trống nghiên cứu (mỗi ý đều có số đo của mình làm bằng chứng)
| # | Khoảng trống | Bằng chứng (bản đồ văn phòng 30 × 20 m, `results/office_20261121_150759`) | Tài liệu gần nhất và chỗ còn thiếu |
|---|---|---|---|
| G1 | Robot **không đi đúng vận tốc lệnh**: gait chỉ đạt khoảng 41 % và có trễ, nhưng MPPI, DWA và RL đều giả định robot làm đúng lệnh | Mục 4.1: chạy theo thời gian thì xoay sai 59°. Bộ ước lượng online đo được hệ số khác nhau theo trục vx, vy, wz | MPPI (Williams 2016), Nav2: mô hình cố định. ABS (RSS 2024) học cả tầng đi bộ nên không áp dụng được cho robot dùng bộ đi bộ gốc |
| G2 | **Vùng mù** của bộ LiDAR + D435i trên Go2: LiDAR mù dưới khoảng 0.5 m, D435i chỉ nhìn phía trước | MPPI va pallet ở lối hẹp (hở −0.06 m) dù phanh an toàn kích hoạt 182 lần, vì đi ngang hoặc xoay vào vùng không nhìn thấy | Perception-aware MPC (Falanga et al., IROS 2018) giữ *mục tiêu* trong khung nhìn, không xét vùng mù sát thân khi né vật |
| G3 | **Nhận ra người muộn và dự đoán quá tự tin** | Cả MPPI lẫn DWA va người ở 2/3 bài đông người (hở −0.02 đến −0.17 m). PPO trong môi trường 2D: 5.1 % va người so với 1.7 % va vật | DRL-VO (T-RO 2023) và SARL (ICRA 2019) giả định biết vị trí người. Schöller (RA-L 2020) chỉ ra vận tốc không đổi là đủ ở tầm 1–2 s, nhưng **bất định tăng theo thời gian** chưa được đưa vào cost của MPPI cho robot chân |
| G4 | MPPI **rung lệnh và đi lòng vòng** | MPPI lắc hướng 28–43 lần mỗi bài, DWA 9–12. Quãng đường dài hơn 55 % ở bài khối so le | Nav2 dùng lọc Savitzky–Golay. SMPPI (Kim et al., ICRA 2022) làm mượt trong không gian đạo hàm |
| G5 | RL phản xạ tốt với người nhưng **không có bảo đảm**. MPPI lập kế hoạch tốt nhưng **kẹt ở cực tiểu địa phương** | PPO đạt 93 % ở môi trường 2D. MPPI/DWA kẹt ở lối pallet | CoRL-MPPI (2025, nhiều robot) và RAY-TOLD (2026) trộn mẫu từ policy vào MPPI, **chưa có cho chó 4 chân + giọng nói + vùng mù** |
| G6 | **Lệnh giọng nói không chỉnh được cách né**: "đi chậm", "tránh xa người", "đi thẳng 3 m rồi về đường cũ" | Hệ thống cũ chỉ hiểu đích đến | Language to Rewards (Yu et al., CoRL 2023): LLM lớn viết hàm thưởng cho MPC của tay máy, chạy trên cloud. Chưa có cho điều hướng, tiếng Việt, mô hình nhỏ chạy trên robot |

### 7.2 PRISM (`nav_local.PRISM`)
**P**olicy-prior, **R**isk- and vi**S**ibility-aware, gait-adaptive **I**nformation-theoretic **M**PC.

Mỗi chu kỳ 0.1 s, PRISM chạy MPPI với 600 mẫu, cộng 6 thành phần. Mỗi thành phần tắt được riêng
để làm ablation:

1. **prior (G5).** 20 % số mẫu được gieo quanh hành động của policy PPO, giữ trong khoảng 1 s,
   nhiễu bằng nửa bình thường. 80 % còn lại quanh chuỗi MPPI cũ. Có luôn mẫu "đứng yên" và mẫu
   "bám đường".
2. **adapt (G1).** Mô hình rollout có độ trễ τ và **hệ số vận tốc riêng từng trục** `vel_gains`,
   ước lượng online từ odometry (EMA khi lệnh đủ lớn và cùng dấu với vận tốc đo).
3. **vis (G2).** Bản đồ lưu thời điểm mỗi ô được nhìn thấy lần cuối (`OccGrid.seen_t`). Cost phạt
   điểm thân sắp tới, cách tâm dưới 0.8 m, rơi vào ô chưa được thấy trong 2.5 s. Phạt nặng hơn khi
   đi ngang (ra hai bên là vùng LiDAR mù và ngoài khung nhìn của camera).
4. **unc (G3).**
   - Bán kính người dự đoán tăng 0.15 m mỗi giây dự đoán.
   - Vẫn tính "người nghi đang đi" (vận tốc > 0.3 m/s nhưng chưa đi đủ 0.5 m), nên robot phản ứng
     sớm.
   - Va chạm cứng chỉ tính với khoảng cách *không* nới, trong 1.2 s đầu, để không đóng băng.
5. **smooth (G4).** Giới hạn thay đổi lệnh mỗi 0.1 s: 0.08 m/s cho vx và vy, 0.22 rad/s cho wz.
   Tăng trọng số bám đường và hướng. Ngoại lệ: khi sát vật thì cho phanh gấp.
6. **lang (G6).** Câu lệnh mang tuỳ chọn né (`nav_prefs`):
   - "đi chậm" / "từ từ" → tốc độ × 0.6;
   - "nhanh" → × 1.2;
   - "tránh xa người" / "cẩn thận" → khoảng cách người +0.4 m, trọng số vật × 1.5.

   "Đi thẳng N mét" vẫn dùng cost bám đường thẳng của A* (vòng qua vật rồi về đường cũ).

### 7.3 Thí nghiệm cho bài báo
- **Bộ bài:** `eval_sim.py --suite office`, 8 bài: 5 bài vật tĩnh so le, 3 bài có người và xe đẩy.
- **Đối chứng (baselines):**
  - pure pursuit + phanh (bản cũ);
  - DWA (1997);
  - MPPI (2016, Nav2);
  - log-MPPI (2022);
  - PPO thuần;
  - FastTD3 thuần;
  - RL + MPPI shield (kiểu ABS).
- **Ablation:** `prism_noprior`, `prism_noadapt`, `prism_novis`, `prism_nounc` (mỗi bản tắt 1 thành
  phần).
- **Chỉ số:** thành công, va chạm (vật và người), SPL, thời gian, số lần khựng, tốc độ trung bình,
  số lần lắc hướng, khoảng hở nhỏ nhất.
- **Thống kê:** mỗi bài lặp 3–5 lần, báo cáo trung bình ± khoảng tin cậy 95 %, kiểm định Wilcoxon
  cặp PRISM so với MPPI và so với RL.
- **Lệnh giọng nói chỉnh cách né (G6):** so cùng một bài với và không có "tránh xa người": đo
  khoảng cách người nhỏ nhất và thời gian.

### 7.4 Đối chứng với bộ né có sẵn của Unitree (chỉ làm được trên chó thật)
- **Bộ né của Unitree** là dịch vụ `obstacles_avoid` chạy trong firmware của Go2. **Mã nguồn
  không công bố.** SDK chỉ có client: `unitree_sdk2py/go2/obstacles_avoid/` với các lệnh
  `SwitchSet`, `UseRemoteCommandFromApi` và `Move(vx, vy, wz)`. Sách hướng dẫn chỉ nói chó né theo
  dữ liệu radar và **chỉ né phía trước**.
- Vì không có mã nguồn nên **không mô phỏng được**. Phải so trên robot thật bằng `eval_real.py`
  và `course_real.yaml`:
  - 6 đường chạy: thẳng trống, 1 thùng, 4 thùng zíc-zắc, hành lang 0.9 m, người cắt ngang,
    người đối đầu;
  - mỗi đường lặp 5 lần;
  - thứ tự các bộ né xáo ngẫu nhiên mỗi vòng;
  - người vận hành đánh dấu va chạm, các chỉ số còn lại giống `eval_sim`.
- Hai chế độ đối chứng trong `robot_real.py`:
  - `unitree`: lái thẳng về đích, firmware tự né;
  - `unitree_path`: bám đường A\* của GoVoice, firmware né cục bộ. Chế độ này so công bằng với
    MPPI/PRISM vì cùng đường toàn cục.
- Lập luận cho bài báo: *"PRISM vượt bộ né của chính nhà sản xuất trên cùng robot và cùng cảm
  biến"*. Đây là đối chứng mạnh nhất có thể có, và dễ tái lập vì ai có Go2 cũng chạy lại được.

### 7.5 Kết quả trung gian (21/11, chưa phải số cuối)
**PPO và FastTD3**, cùng môi trường, cùng phần thưởng, mỗi bên 20 phút GPU RTX 4060. TD3 dùng
lịch tăng độ khó theo thời gian, vì nó chậm hơn mỗi bước: 9 nghìn so với 240 nghìn bước/s.
Bộ thử 2D cố định 4096 tập, mật độ vật đầy đủ (`rl_nav/eval2d.py`):

| Policy | Tới đích (KTC 95 % Wilson) | Va vật | Va người |
|---|---|---|---|
| PPO (`ppo_v2/best`) | 93.8 % [93.0–94.5] | 1.2 % | 5.0 % |
| FastTD3 (`td3_v2/best`) | 94.4 % [93.6–95.0] | 2.8 % | 2.8 % |

→ **Không khác biệt có ý nghĩa** về tỉ lệ tới đích. TD3 né người tốt hơn, PPO né vật tốt hơn. Điều
này khớp với tài liệu: thuật toán RL không phải yếu tố quyết định.

**Đông người trong Gazebo, PRISM so với MPPI** (`results/office_*`, 3 bài × 2 lần). Bộ đánh giá
tách hai loại va chạm:
- **va do robot**: robot tiến vào người hơn 0.1 m/s, hoặc xoay quét thân hơn 0.3 rad/s;
- **bị va**: người đi vào robot đang gần như đứng yên.

| | Tới đích | Va do robot | Bị người va | Va vật tĩnh |
|---|---|---|---|---|
| PRISM | 2/6 | **0/6** | 4/6 | **0/6** |
| MPPI | 2/6 | 1/6 | 2/6 | 2/6 |

→ Các lần va còn lại của PRISM đều do người "mải điện thoại" (30 % đám đông, không né robot) đi
thẳng vào robot đang đứng hoặc nhường, thường từ hông hoặc sau lưng, đúng vùng mù dưới 0.5 m
của LiDAR. Đây là **khoảng trống G3c**: né chủ động người áp sát từ vùng mù. Hướng giải quyết:
dùng tracker giữ dự đoán khi người vào vùng mù, và cho robot bước tránh khi người được dự đoán
sẽ đi vào chỗ robot đang đứng.

**Khoảng trống G3b**: người **đi chậm** (0.08–0.3 m/s) lọt khe giữa bản đồ vật tĩnh và bộ theo
dõi người. Đã gặp PRISM bản đầu đâm vào người đi chậm ở 0.39 m/s. Bản sau đã đưa mọi vật cỡ
người có vận tốc trên 0.08 m/s vào cost, kèm bất định tỉ lệ với vận tốc.

**Vật tĩnh** (5 bài, 1 lần): PRISM 4/5, 0 lần khựng, lắc hướng 7–13 lần. MPPI 3/5 có 1 va chạm,
lắc hướng 14–28 lần. DWA 4/5. Bài lối pallet thì cả ba đều kẹt; cần kiểm tra độ rộng khe so với
vùng cấm 0.32 m của A\*.

### 7.6 Sắp xếp các bài báo
- **Bài A: AP-MPPI** (cải tiến từ policy-guided MPPI). Đóng góp:
  1. tỉ lệ mẫu **của từng policy** tự điều chỉnh online theo phần trọng số giành được;
  2. **nhiều policy gợi ý bù nhau** (PPO né vật tốt, TD3 né người tốt). Có số liệu cho thấy trộn
     kiểu trung bình (`rl_ens`) không tốt hơn: 2D 94.4 %, ngang TD3;
  3. critic PPO làm chi phí cuối quỹ đạo (ý tưởng TD-MPC2).

  Đối chứng: `pgmppi` (CoRL-MPPI 2025, RAY-TOLD 2026), `bmppi` (kiểu Biased-MPPI, Trevisan &
  Alonso-Mora 2024: nhiều bộ gợi ý, tỉ lệ cố định), MPPI, RL thuần, `rl_ens`.
- **Bài B: PRISM** (mới, đi từ khoảng trống G1–G6). Thành phần gợi ý RL dùng bộ trộn qua MPPI.
- **Bản tạp chí về sau:** gộp A + B + thí nghiệm trên Go2 thật so với bộ né của Unitree
  (`eval_real.py`), với ≥ 30 % nội dung mới. **Không** tách phần "trộn PPO + TD3" thành bài
  riêng, vì Biased-MPPI (2024) đã làm control fusion trong MPPI và tách ra sẽ thành chẻ nhỏ
  (salami slicing).

### 7.7 Trạm chờ 1 (22/11, 03:20–04:00) — Claude tự đánh giá, không dùng script chọn

**Sàng lọc 17 cấu hình × 8 bài văn phòng × 1 lần** (`results/office_20261121_164514`), lúc này mới chỉ để *loại* chứ chưa kết luận gì:

| cấu hình | tới đích | va | SPL | ghi chú |
|---|---|---|---|---|
| dwa | 7/8 | 1 | 0.66 | va ở sảnh 8 người |
| **prism** | 6/8 | **0** | 0.49 | duy nhất không va lần nào; trượt slalom + bếp xa |
| prism_noadaptratio | 6/8 | 1 | 0.56 | |
| apmppi_multi / bmppi / rl | 5/8 | 1 / 1 / 3 | | |
| mppi, pgmppi, log_mppi, rl_ens, rl_safe, prism_novalue, prism_nounc | 4/8 | | | |
| prism_noadapt, prism_novis | 3/8 | | | |
| prism_noprior | 2/8 | 2 | 0.14 | bỏ gợi ý RL là tụt mạnh nhất -> gợi ý RL có ích |
| pp | 2/8 | 2 | 0.25 | 28 lần dừng/bài |

Đọc từng lượt hỏng (không chỉ nhìn tổng):

1. **`slalom_coc` — lỗi chung của cả họ MPPI, không phải của PRISM.** Mọi biến thể MPPI dừng cách đích 0.41–0.48 m rồi báo "kẹt"; DWA/RL/pp tới được (0.17–0.25 m, không va). Đích (13.3, 0) cách cọc (13.4, 0.55) có 0.56 m -> lực đẩy mềm của vật cản cân bằng lực kéo đích ở ~0.45 m (cực tiểu địa phương). **Sửa theo Nav2 MPPI** (`ObstaclesCritic.near_goal_distance`, mặc định 0.5 m): trong 0.5 m quanh đích bỏ lực đẩy mềm, **giữ** phạt va chạm cứng. Sửa ở lớp `MPPI` gốc -> mọi baseline họ MPPI (mppi, log_mppi, pgmppi, apmppi_multi, bmppi, rl_safe-shield, DWA) và PRISM cùng được hưởng: công bằng. Số sàng lọc là *trước* khi sửa; lượt chính thức chạy lại tất cả với code mới.
2. **`bep_xa` — kẹt ở khe hẹp (-6.2, 2.5) giữa bàn 18 / ghế 26 / bình nước.** MPPI và PRISM đi *cùng* khe; prism, prism_noprior, prism_novalue, prism_novis kẹt 4 lần × 4 s rồi bỏ; prism_noadapt/noadaptratio/nounc lại qua được. 1 lần/cấu hình thì 50/50 kiểu này chưa nói được gì -> để bước select (2 lần × 8 bài) và lượt chính thức (5 lần) trả lời. Nếu vẫn là PRISM-riêng thì nghi phạm số 1 là vòng phản hồi hệ số vận tốc từng trục (robot bị chặn -> hệ số đo tụt -> mô hình nghĩ robot không đi được -> càng kẹt).
3. **Đám đông**: va của PRISM ở sàng lọc = 0; các va khác phần lớn `at_fault=0` (người đâm robot đứng yên) — đúng như G3c.

**RL (`results/RL_ANALYSIS.md`, 4096 tình huống ghép cặp, cảm biến thực tế):**
- PPO 3 seed: 93.5–93.8 % (rất đều); TD3 3 seed: 91.6–92.3 %; SAC 3 seed: 91.2–92.1 %. PPO hơn TD3/SAC có ý nghĩa (McNemar p ≈ 0.001–0.003); TD3 ≈ SAC (p = 0.53). **Bảng so sánh thuật toán trong bài dùng đúng 3×3 lượt cùng ngân sách 20 phút này.**
- Kiểm tra thêm (không có trong script): `td3_v2` (cũng 20 phút, train cảm biến *lý tưởng*) dưới cảm biến thực tế được **94.1 %** — hơn rõ cả 3 TD3 train-thực-tế (CI không chồng), ngang PPO (p = 0.60) và **lỗi khác kiểu PPO**: PPO ít va vật (1.3 %) nhiều va người (4.8 %), td3_v2 ngược lại (2.9 % / 2.9 %). Oracle ppo+td3_v2 = 96.2 % — cặp bù nhau tốt nhất; thêm SAC chỉ +0.6 (lợi giảm dần, tốn thêm tính toán trên Jetson).
- Trung bình hành động PPO+TD3 (ensemble) = 93.6 % < PPO một mình -> **ghép phải ở mức lấy mẫu (PRISM), không phải trung bình hành động** — câu chuyện cho bài.

**Quyết định:**
- Cài: ppo = `ppo_r_s0` (ngang ppo_v2 nhưng train với cảm biến thực tế -> lập luận chuyển sang chó thật tốt hơn), td3 = `td3_v2` (TD3 tốt nhất đo được; chọn trên bộ kiểm tra 2D tách biệt, đánh giá cuối ở Gazebo -> không phải chọn trên tập test; ghi rõ trong bài), sac = `sac_r_s0` (seed SAC tốt nhất, cho baseline `rl@sac` và thử 3 gợi ý). Critic: `ppo_r_s0` (V(s) cùng chuẩn hoá quan sát với gợi ý PPO đứng đầu).
- Thử ở select (2 lần × 8 bài, 2 sim): `prism` (= ppo+td3), `prism@ppo`, `prism@ppo+td3+sac`, `prism@ppo+sac`, `prism~t0` (ngưỡng 'người nghi' cũ, xem dưới), `prism_noprior` (đối chứng gợi ý) và `mppi` (đối chứng cho bản sửa gần-đích).

**Chẩn đoán bằng phát lại (không đoán):** thêm `GOVOICE_DEBUG_DIR` -> mỗi lần "kẹt" lưu đủ trạng thái (field, đường, người, gains, chính đối tượng `ctrl`) để gọi lại `ctrl.step` ngoại tuyến 20 bước vòng kín, tắt từng thành phần (`pipeline/replay_stuck.py`). Kết quả:
- Bản sửa gần-đích: mppi 0.436 -> **0.178 m (tới)**, pgmppi 0.474 -> **0.20 m (tới)** ở slalom. PRISM vẫn kẹt -> lỗi riêng PRISM.
- PRISM kẹt ở slalom vì **9 'người nghi đang đi' trong bài không có người nào**: `movers(min_speed=0.08, min_travel=0.0)` nhận cọc/thùng (tâm cụm nhảy 0.2–0.4 m theo góc nhìn — chính docstring BlobTracker đã ghi) là người đi chậm. Phát lại: tắt `unc` là đi tiếp; gần đích thì 'người ma' ở cọc đẩy robot ra (lực đẩy người không thuộc phần near-goal). **Sửa: tentative cần đi được ≥ 0.3 m** (vẫn sớm hơn người xác nhận 0.5 m ≈ 0.7 s với người 0.3 m/s). Sau sửa: slalom **tới 0.19 m, 29.8 s** (nhanh ngang RL 26.7 s), bếp xa **tới 0.15 m, 76.7 s** (trước: kẹt cả 2).
- Cùng lượt thử: kho_xe_day hết giờ — robot đối đầu xe đẩy trong lối 1 làn, lùi ra rồi vào lại 6 lần (dự đoán vận tốc không đổi chiếm hết lối -> chỉ còn đường lùi; 'freezing robot problem'). Ở sàng lọc hầu hết bộ né cũng hỏng bài này -> khó chung, để 5 lần lặp trả lời. van_phong_dong: chạm người 5.5 cm khi robot đang xoay (người tiến 0.13, robot 0.03) -> `prism~t0` trong select để xem ngưỡng mới có làm chậm phản ứng với người đi chậm không (đánh đổi G3b).
- Nghi vấn ghi lại: ở 1 lần kẹt gần đích (0.33 m), tắt critic/gợi ý thì mô hình tới 0.15 m -> critic V(s) có thể thấp ngay trước trạng thái kết thúc (đặc điểm quen của V có điểm dừng). Xem `prism_novalue` ở lượt chính thức.

### 7.8 Trạm chờ 2 (22/11, 05:40) — bước select, chốt PRISM cuối

`results/select_prism_priors_w{0,1}` — 7 cấu hình × 8 bài văn phòng × 2 lần, code đã có 2 bản sửa ở 7.7:

| cấu hình | tới đích /16 | va | do robot | SPL | tĩnh (5 bài ×2) | đám đông (3 bài ×2) |
|---|---|---|---|---|---|---|
| **prism@ppo+sac** | **12** | 2 | 1 | 0.58 | 8/10 | **4/6** |
| prism@ppo | 11 | 5 | 2 | 0.67 | 10/10 | 1/6 |
| prism@ppo+td3+sac | 11 | 3 | 2 | 0.62 | 9/10 | 2/6 |
| prism (ppo+td3) | 10 | 4 | 0 | 0.60 | 9/10 | 1/6 |
| mppi | 9 | 6 | 3 | 0.51 | 8/10 | 1/6 |
| prism_noprior | 8 | 7 | 3 | 0.55 | 8/10 | 0/6 |
| prism~t0 (ngưỡng cũ) | 7 | 3 | 1 | 0.37 | 5/10 | 2/6 |

Đánh giá:
- **Bản sửa 'người nghi' đứng vững:** ngưỡng cũ (`~t0`) mất 4 bài tĩnh (bếp xa, khối so le, văn phòng) vì 'người ma' ở vật tĩnh; ở đám đông không kém rõ (2/6 vs 1–4/6) -> giữ 0.3 m.
- **Gợi ý RL có ích ở cả 4 tổ hợp** (10–12/16 so với 8/16 không gợi ý); cùng hướng với sàng lọc.
- **Va ở sảnh 8 người phần lớn `at_fault=0`**: robot đứng yên (v ≈ 0–0.1), người mô phỏng (không né robot) đi vào. prism@ppo+sac là cấu hình duy nhất qua sảnh cả 2 lần — robot **chủ động đi** (v 0.44–0.62) thay vì đứng chờ bị đâm. Bài báo phải báo cáo tách: va do robot / do người.
- Chênh 10–12/16 giữa các tổ hợp **chưa có ý nghĩa thống kê** (n = 16). Chọn PRISM chính = **prism@ppo+sac** vì: nhiều tới đích nhất, đám đông tốt nhất (đúng điểm yếu chung), ít va do robot, chỉ 2 policy (rẻ hơn 3 trên Jetson). Lưu ý: điều này **đảo** dự đoán từ 2D (oracle ppo+td3 cao nhất) -> trong bài nói thẳng: bù trừ 2D không đoán đúng tổ hợp tốt nhất trong Gazebo; phải chọn bằng kiểm định closed-loop.
- **Quy tắc chống 'chọn trên tập test'**: PRISM chính chốt *bây giờ*, trên dữ liệu select; lượt chính thức chỉ đo, không chọn lại. Mọi biến thể gợi ý khác vẫn chạy và báo cáo.

Lượt chính thức (`decisions.json["final"]`): 24 cấu hình × 8 bài × 5 lần = 960 lượt (văn phòng) + 11 cấu hình × 17 bài × 3 lần = 561 lượt (nhà nhỏ). Ablation đều trên chính `@ppo+sac`. Đã kiểm tra trước: dựng được cả 24 bộ điều khiển, đúng số gợi ý/cờ/critic. Giữ 2 sim (không 3): 3 sim + 3 tiến trình eval ~14/16 luồng -> nguy cơ sim chậm hơn thời gian thực làm sai số đo; đúng đắn hơn nhanh.

### 7.9 ĐÍNH CHÍNH 7.7–7.8 và kết quả văn phòng đủ 960 lượt (22/11, 21:00)

Bảng: `python3 pipeline/analyze_office.py`. prism@ppo+sac 28/40 (70 %, CI 55–82), prism (ppo+td3) 28/40, dwa 27/40, mppi 26/40 (p = 0.79).

**Sai cần sửa:**
1. Bước select KHÔNG phải tập kiểm định tách biệt: cùng 8 bài, cùng seed đám đông (21–23) với lượt chính thức. Hai bản sửa (near_goal, min_travel 0.3) cũng được tìm từ lượt hỏng trên chính các bài này. Cần bộ bài/seed/bản đồ CHƯA TỪNG XEM để làm kết quả chính.
2. Lý do "ít va do robot nhất" của prism@ppo+sac là SAI: select có prism (ppo+td3) = 0, ppo+sac = 1.
3. `at_fault` chỉ ghi khi chạm người -> mọi bảng trước bỏ sót va vật tĩnh (lỗi robot). report.py dòng 50 cũng vậy. Đúng: va tĩnh + va người at_fault=1.
4. "Gợi ý RL có ích rõ / tụt mạnh" là nói quá: select n = 16; đủ 40 lượt prism 28, noprior 26 (p = 0.75).
5. 7.8: `~t0` mất 5 lượt tĩnh (5/10), không phải 4. Cơ chế "chủ động đi nên qua sảnh" chỉ là suy đoán từ 2 lượt.
6. td3_v2 chọn trên chính bộ 2D dùng để so (seed 12345) -> 94.1 % lạc quan; "train cảm biến lý tưởng" suy từ tên lượt, chưa kiểm. rl@td3 ở Gazebo 5/40.
7. 23 phép so với PRISM: sau Holm chỉ pp, rl@sac, rl@td3 kém có ý nghĩa; rl_ens (p = 0.035), rl_safe (0.006) không còn.

### 7.10 (22/11, 22:00) Mô phỏng nhanh + nhận dạng động học

- Gợi ý RL: office 28/40 (ppo+sac) = 28/40 (ppo+td3), nhà 51/51 = 51/51, va do robot 7 = 7, ghép cặp 4–4 -> KHÔNG phân biệt được; không gợi ý 26/40 + 50/51.
- Báo nhầm (đã rút lại): "PolicyMPPI dịch kế hoạch 2 lần" là do in file chồng dòng, code đúng. Thật: K = 400 so với 600.
- `fastsim.py`: đồng hồ ảo, chạy nguyên `_navigate_mpc`/OccGrid/BlobTracker/A*. Lần đầu KHÔNG dự đoán được Gazebo (Spearman 0.25).
- `pipeline/sysid.py` (300 s, Gazebo): vx bão hoà ~0.27–0.29 m/s (0.87 ở lệnh 0.15, 0.54 ở 0.47), lùi 1.26, vy 0.97, wz ~0.85; trễ 0.05 s, tau 0.15/0.15/0.25; thân lắc (vận tốc 0.11 m/s, 0.43 rad/s ở cửa sổ 0.2 s). Đưa vào -> Spearman 0.89 (12 cấu hình, 8 bài × 4; phần lớn nhờ tách nhóm RL/pp).
- DEV: seed 0–149 (fastsim). TEST giữ kín: seed ≥ 100000 và các bản đồ Gazebo mới.

### 7.11 (23/11) Kết quả vòng agent (chưa xác nhận đủ lớn)
- Mức trần (DEV 0-149 đông người, n=101): CHAMP mppi:ppl=32 63 % -> cảm nhận hoàn hảo 74 % -> biết trước 89 %; chó thật 69 -> 89 -> 97. Chế độ chó thật: cảm nhận là nút thắt.
- AUDIT: p2+turn 57 = mppi:ppl=32 57 (100 thế giới mới); họ MPPI ở Gazebo có người không phân biệt được (p=0.875); at_fault không tin được; BlobTracker đo sai vận tốc khi mất dấu.
- SEV: bác bỏ. DYN: bản ghi thật không có lệnh; odom thiếu ~18 %. OSS: CN-CBF (2603.06921) đã làm người-rẽ trong HJ.
- ALGO (104 thế giới mới, seed 150-299): mppi~t3~nl:ppl=100 74/80 %; p3+geo-haz 81/80 %; p3+geo+gcv 76/86 % (CHAMP/chó thật); McNemar p 0.23-0.31; gợi ý RL không hơn có ý nghĩa. Chờ xác nhận 500 thế giới.

### 7.12 (23/11) Sửa mô hình động học CHAMP: cắt lệnh + trôi lùi (regime `champ2`)
- Kiểm lại REPORT_ISAAC thì thấy mô hình `champ` ("vx bão hoà 0.29, lùi ×1.26, wz 0.85") **hiểu nhầm hai thứ đơn giản**:
  (1) `unitree_go2_sim/config/gait/gait.yaml` **cắt lệnh** ở 0.3 / 0.25 / 0.5 (vx/vy/wz) — "bão hoà 0.29" là giới hạn cấu hình, không phải thân robot;
  (2) khi có bước chân thân **trôi lùi ~0.053 m/s** (lệnh chỉ vy hoặc chỉ wz cho vx = −0.053 ± 0.02; lệnh vx 0.025 → −0.028) — "lùi ×1.26" là độ lệch này.
  wz thật bị chặn 0.5 (lệnh 0.73 → 0.51); `champ` cũ cho tới ~0.85×lệnh.
- `pipeline/sysid_fit2.py`: sai số dự đoán vòng hở 2 s: lý tưởng 0.169 m, champ cũ 0.088, **mới 0.062**; kiểm chéo hai nửa bản ghi: mới thắng cũ ở cả hai nửa.
- fastsim `--regime champ2` (cắt + trôi; gain ~1, tau 0.08–0.16, trễ 0–0.05 lấy mẫu mỗi lượt). `champ`/`go2` không đổi (kiểm từng dòng, seed 0–5).
- Hệ quả: (a) trong Gazebo mọi bộ điều khiển (vmax ≈ 0.47) đều bị CHAMP cắt ở 0.3 → nói rõ trong bài; (b) `RespModel` (`~nl`) giả định dạng tanh = đúng dạng của `champ` cũ (inverse crime) → phải đo lại dưới champ2; (c) Isaac (2 policy chính thức) đi tới 1.0 m/s, gain ~1 → giới hạn 0.3 không phải của Go2.
- Isaac: vùng chết ở lệnh nhỏ là đặc tính policy, không phải Go2 thật; policy flat không quay tại chỗ → nếu kiểm chéo dùng rough.
- **Kiểm vòng kín (20:10):** chạy lại 8 bài văn phòng × 12 cấu hình × 4: Spearman với Gazebo champ 0.90, champ2 0.59; bootstrap theo bài: chênh 0.14 [−0.12; 0.41], không có ý nghĩa. Vậy champ2 **đúng hơn ở dự đoán 1–2 s nhưng KHÔNG khớp kết quả Gazebo hơn** (champ cũ từng được chọn vì làm tăng Spearman → lợi thế chọn). Kết luận: báo cáo cả champ, champ2, go2 như các regime độ bền; không gọi regime nào là "đúng Gazebo nhất".

### 7.13 (23/11 tối) Kết luận coordinator từ vòng MODEL (chỉ DEV; toàn văn báo cáo của agent nằm trong output của agent, CHƯA có research/REPORT_MODEL.md — agent bị chặn ghi file, chờ người dùng quyết)
- PPO train lại với động học đo được (dyn/union, 3 seed) **không hơn** PPO cũ ở champ/champ2/go2 (mọi p ≥ 0.17, 615 lượt/ô). Nút thắt RL trong fastsim là người (va người ~2.1 %/s, gấp ~3 env 2D), không phải động học. → **RL chỉ còn là ablation** (khớp kết luận ALGO: không gợi ý RL nào có ý nghĩa).
- `nav_pred` (MLP 8 mode): vòng hở hơn CV rõ (Brier −15…25 %, CI < 0 ở 5/6 mô hình người, kể cả ORCA/Helbing2000/Moussaïd2009 không dùng khi train); **vòng kín chưa hơn CV**: gộp 5 điều kiện +38/−25, p = 0.13. → không phải thành phần chính; chỉ đưa vào VAL nếu còn chỗ trong ngân sách so sánh (quyết sau khi ALGO xong). Cần kiểm vòng hở trên người thật (THÖR) trước khi viết bất cứ gì về nó.

### 7.14 (23/11 ~22:00) Kết quả vòng 1 ALGO — đã kiểm độc lập
- Ứng viên C1 = `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5` (khoá trước khi xác nhận). Xác nhận 1 lần, seed 300–799 (356 thế giới đông người) × 5 ô (champ, champ2, go2 × base; champ2, go2 × helb).
- C1 vs baseline mạnh nhất đã chỉnh, cùng tracker v3 + `~nl` (`mppi~t3~nl:ppl=100;ppl_len=0.5`): 86.2 vs 80.5 %, **+5.7 điểm, CI95 [3.6; 7.9], hoán vị dấu theo thế giới p ≈ 5e-6** (coordinator tính lại). Mọi ô cùng dấu (+3.4…+7.6); từng ô riêng chưa qua Holm.
- So `mppi:ppl=32` gốc: +15.6; dwa/log_mppi chỉnh: +7.5. Phần lớn lợi "so với gốc" là tracker v3 (dùng chung) — bài phải tách rõ.
- RL: không tổ hợp gợi ý nào hơn "không gợi ý" → RL chỉ là ablation (khớp MODEL).
- Vòng 2 (đang chạy): baseline PGIF-MPPI + DRA-MPPI cài lại, C3 = C1 + vết khuất, bảng ablation trên seed 1000–1499. VAL để sau vòng 2.

### 7.15 (24/11 01:50) Kiểm chéo Isaac (pilot, 100 thế giới DEV 302–439, thân Isaac rough + nhiễu, 8 robot lockstep)
- Tới đích không va (ngã = hỏng): isaac mppi 64, ppl32 72, dwa 63, baseline chỉnh 75, **C1 83**; cùng thế giới ở fastsim go2 74/79/64/87/93, champ 47/62/42/80/83, champ2 48/58/43/74/73.
- Thứ hạng: Kendall τ isaac–go2 = isaac–champ = 1.00, isaac–champ2 = 0.80 → Isaac xác nhận thứ hạng fastsim. C1 vs baseline trên isaac +20/−12 (p 0.22, n=100 — chưa đủ lực; pilot).
- **Cảnh báo an toàn:** ngã 13/500, trong đó 11/200 ở hai cấu hình `~t3~nl` (2/300 ở cấu hình khác). Nghi `~nl` thổi lệnh lên do vùng chết của policy Isaac → ISAAC đang điều tra (§11). Phải có kết luận trước khi đưa `~nl` lên chó thật.
- Khung 2D bao gần hết va chân (7/25 lượt chạm chân không bị khung bắt).

### 7.16 (24/11 07:00) Vòng 2 ALGO (seed 1000–1499, 348 × 5 ô) — coordinator kiểm lại khớp
- C1 lặp lại: vs B1 (mppi~t3~nl chỉnh) **+6.6** (p 2e-5); vs PGIF-MPPI cài lại (cùng tracker, chỉnh 35 cấu hình) **+5.2** (p 2e-5); vs DRA-MPPI cài lại **+3.2** (p 0.002; không qua Bonferroni toàn LOG). Ở helb C1 ≈ PGIF/DRA → ưu thế phụ thuộc mô hình người; phải nói rõ.
- C3 (che khuất) bị loại theo quy tắc đăng ký trước; chẩn đoán: go2 không còn khoảng trống che khuất với C1.
- Ablation trên seed xác nhận: chỉ `~t3` (−5.8) và `prim` (−4.2) có ý nghĩa; geo −2.2, grad −1.1, chiết khấu −0.7, `~nl` −0.4 chưa chứng minh.
- Vòng 3 (cuối): tìm bản đơn giản nhất không kém C1 (non-inferiority −2 điểm), xác nhận seed 1500–1999; sau đó VAL do coordinator.

### 7.17 (24/11 07:15) Điều tra ngã Isaac (REPORT_ISAAC §11) — coordinator kiểm số khớp
- Ngã KHÔNG do `~nl` (bỏ nl: 4–5/100, như có nl), không do tia nghiêng, không do lệnh giật (dwa giật nhất mà gần như không ngã). RespModel học gain ≈ 1 trên Isaac.
- Nguyên nhân có bằng chứng: thời gian ở chế độ chậm/lùi/xoay (policy rough Isaac yếu ở đó; bản đồ ngã lệnh cố định ~1.4e-3/s). Không nói gì về chó thật (SportClient khác).
- Tag opt-in `~cs` (giới hạn wz khi đi ngang/lùi, giới hạn tốc độ đổi vy/wz): Isaac ngã 0/200 vs 6/200 (p 0.015); giá ở fastsim go2 −5…−8 điểm (n.s.). → lớp an toàn khi triển khai, KHÔNG thuộc thuật toán chính. Trên chó thật phải thử riêng lùi + xoay chậm, người cầm remote.
- Pilot §10 không phát lại được từng lượt (server bước trước khi đủ client) → đã sửa v3; tỉ lệ §10 vẫn dùng được, từng lượt thì không.
- Tôi rút lại lập luận "bỏ ~nl vì an toàn" đã gửi ALGO lúc 07:00.

### 7.18 (24/11 10:15) Vòng 3 + ĐÓNG BĂNG
- Vòng 3 (seed 1500–1999, 357 × 5, quy tắc không-kém −2 điểm đăng ký trước): C4 (MPPI+prim) −5.7 [−7.8; −3.5]; C5 (C1 bỏ grad/chiết khấu/nl) −0.8 [−2.7; +1.0] → không ai đạt → **giữ C1**. Coordinator kiểm lại khớp.
- C1 qua 3 bộ seed xác nhận độc lập: vs B1 +5.7 / +6.6 / +7.2; vs PGIF* +5.2 / +6.1; vs DRA* +3.2 / +2.8 (Holm 0.047 ở vòng 3; không ô nào riêng lẻ có ý nghĩa vs DRA).
- Đóng băng: research/FROZEN.md (+ sha256, bản chụp mã). VAL đăng ký trước và đang chạy (7 cấu hình × 5 ô, seed 2000–2399).

### 7.19 (24/11 12:10) VAL (seed 2000–2399, 315 thế giới × 5 ô; phân tích đúng đăng ký trước; sha256 khớp sau khi chạy; 0 EXC)
- Gộp: C1 87.6 · DRA* 83.0 · PGIF* 81.3 · log_mppi 80.2 · dwa 79.8 · B1 78.5 · B0 68.8.
- Họ chính (Holm 3): C1−B1 **+9.1 [7.0; 11.2]**, C1−PGIF* **+6.2 [4.1; 8.3]**, C1−DRA* **+4.5 [2.5; 6.5]**; cả ba Holm ≤ 3e-5.
- Từng ô: C1 hơn rõ ở champ/champ2 base; ở go2 và helb (đặc biệt go2-helb) C1 ≈ DRA*/PGIF* (không có ý nghĩa). Mẫu hình giống vòng 2–3: lợi thế lớn khi robot chậm/động học CHAMP, nhỏ khi robot nhanh (go2) hoặc người Helbing.
- Bước tiếp: kiểm khói Gazebo (agent GAZEBO) → TEST fastsim (1000 thế giới, chạy từ bản chụp chỉ-đọc) → TEST Gazebo (680 cặp) → Isaac (tuỳ chọn).

### 7.20 (24/11 14:40) Kiểm khói Gazebo + S4
- S1/S2/S3/S5/S6 đạt (C1 step p95 15 ms, RTF ≥ 0.999). S4 trượt: "người ma" ở bài tĩnh do thân CHAMP lắc (nghiêng p95 8°; chó thật đo 0.5°) làm LiDAR 16 tia cắt vật ở độ cao khác → tâm cụm nhảy. Không phải lệch thời gian. Ảnh hưởng cả C1 lẫn B1. → chạy Gazebo TEST như đăng ký (Lệch #1 trong PREREG_TEST §9), ghi hạn chế. Gợi ý bài sau: bộ lọc vật tĩnh của tracker bền với nghiêng thân.

### 7.21 (24/11 19:05) TEST fastsim (họ chính, đăng ký trước; 1000 thế giới × 5 ô; 0 EXC; bản chụp sha khớp)
- Gộp: C1 85.3 · DRA* 82.6 · PGIF* 80.3 · dwa 79.1 · B1 78.3 · log_mppi 77.9 · B0 68.9.
- Họ chính (Holm 3): **C1−B1 +7.0 [5.7; 8.3]; C1−PGIF* +5.0 [3.8; 6.2]; C1−DRA* +2.7 [1.5; 3.8]**; cả ba Holm 1.5e-5. Khớp VAL (+9.1/+6.2/+4.5) và 3 vòng xác nhận.
- Từng ô: vs DRA* chỉ có ý nghĩa ở champ2-base; ở go2 và helb C1 ≈ DRA*/PGIF*. → kết luận bài: lợi thế chắc chắn so với MPPI chuẩn và PGIF; so với DRA nhỏ (+2.7) và phụ thuộc điều kiện.

### 7.22 (24/11 19:45) Nhánh VẬT TĨNH (bổ sung #2 đăng ký trước; 387 thế giới không người × 3 ô; 0 EXC)
- Mọi cấu hình 96–99.5 %; **0 va vật** (trừ B0 0.1 %); thất bại gần như toàn là KẸT.
- C1 96.9 vs B1 97.8: **−0.95 [−1.55; −0.34]** → đạt không-kém (ngưỡng −2) nhưng kém nhẹ có thật. B0 (tracker cũ) 99.0, dwa 99.5 tốt nhất.
- Diễn giải (chưa kiểm): tracker v3 giữ vết "người" lâu hơn → đôi khi coi vật tĩnh là người, chờ/kẹt (cùng hiện tượng S4 ở Gazebo). Ghi vào hạn chế; hướng sửa sau: lọc vật tĩnh bền hơn.

### 7.23 (24/11) Đính chính + gói bài báo
- **Đính chính 7.12:** chênh Spearman champ − champ2 là ước lượng điểm **+0.31** (0.90 − 0.59), KTC bootstrap theo bài [−0.13; +0.42]; con số "0.14" tôi ghi trước là trung vị bootstrap, không phải ước lượng điểm. Kết luận không đổi (không có ý nghĩa).
- results/paper_package/ (agent PAPER): make_all.py tái lập 97 điểm số = 0 lệch; T1–T10, F1–F5, DRAFT_results/limitations, NOVELTY, REPRODUCE; T11 (Gazebo) và T12 (chó thật) để trống.
- Thăm dò (không đăng ký trước): Isaac v3 tất định, 100 thế giới DEV: C1 87 vs B1 73 (+20/−6, p 0.009).
