# GoVoice trong mô phỏng: nói chuyện với Go2 trong Gazebo, 1 hoặc 2 con, có né vật cản

Pipeline hiểu lệnh giống hệt khi chạy trên robot thật (STT → Combo/Reflex/LLM → verifier →
SafetyGuard → AsyncExecutor). Chỉ phần "tay chân" là khác:

| | Robot thật (`run_real_robot.py`, Jetson) | Mô phỏng (`run_sim.py`, laptop) |
|---|---|---|
| Di chuyển | `SportClient.Move`, vận tốc × thời gian | `/cmd_vel`, **vòng kín theo odom** + **phanh khi có vật cản** |
| Động tác (chào, nhảy, ngồi…) | `SportClient.Hello()`… | tư thế thân qua `/body_pose` của CHAMP |
| `go_to` (ra cửa, vào bếp…) | `/goal_pose` cho Nav2 | **bản đồ từ LiDAR + D435i, A\*, bám đường, nhường đường** |
| Cảm biến | — | Velodyne 360° + **RealSense D435i** gắn trước đầu |
| File | `robot_tools.py` | `robot_ros.py`, `nav_local.py`, `fleet.py` |

## Chạy

```bash
# Terminal 1: mô phỏng (Go2 có gắn D435i, trong nhà có đồ đạc chắn giữa đường)
source /opt/ros/lyrical/setup.bash && source ~/ros2_ws/install/setup.bash
ros2 launch go2_voice voice_sim.launch.py              # 1 con
ros2 launch go2_voice voice_sim.launch.py robots:=2    # 2 con, spawn ở (0, 0) và (0, 1.5)
# chờ khoảng 40 s cho robot đứng dậy

# Terminal 2: trợ lý (thư mục này)
source /opt/ros/lyrical/setup.bash && source venv/bin/activate
python3 run_sim.py --voice         # nói qua mic laptop
python3 run_sim.py                 # gõ phím
python3 run_sim.py --no-avoid      # tắt né vật cản (để so sánh)
```

**Xem trực tiếp:** launch mặc định mở 2 cửa sổ:
- **Gazebo:** thế giới 3D, con chó bước đi, người đi lại.
- **RViz** (`go2_voice/rviz/voice_sim.rviz`), là "đầu óc" của robot:
  - **bản đồ robot tự vẽ** (đen = vật, xám = chưa thấy, trắng = đã thấy trống);
  - **thân robot** kèm nhãn trạng thái ("đi tới cửa", "nhường người", "đi vòng qua vật",
    "phanh");
  - **cờ xanh** là đích, **đường xanh** là quỹ đạo đã lập;
  - **trụ cam** là người đang được theo dõi, kèm mũi tên vận tốc; chuyển **đỏ** khi robot
    phải nhường;
  - **hộp màu** là đồ vật, kèm tên như "bàn trà màu đen";
  - điểm LiDAR và ảnh D435i.

  Các lớp này chỉ hiện khi `run_sim.py` đang chạy, vì nó phát `/govoice/map`,
  `/govoice/markers` và `/govoice/path`. Không cần RViz thì thêm `rviz:=false`.

Tham số khi launch: `camera:=d435i|d455|both|none`, `headless:=true` (không mở GUI),
`localhost:=false` (chỉ dùng khi cần nối qua mạng; khi đó chạy `run_sim.py --network`).

**Gắn D435i theo đúng giá đỡ của bạn:** sửa `d435i_x`, `d435i_z`, `d435i_pitch` (tính bằng m
và rad; pitch > 0 là cúi xuống) trong
`unitree_go2_description/urdf/realsense_d435i.xacro`. Mặc định camera ở trước thân 0.30 m,
cao hơn thân 0.02 m, cúi xuống 20°.

## Nói gì cũng được

| Câu | Kết quả |
|---|---|
| "đi thẳng 2 mét", "xoay trái 90 độ", "chào đi", "ngồi xuống" | như trên robot thật; gặp vật cản thì **dừng và báo** |
| "ra cửa", "vào bếp", "đi tới chỗ sạc" | tự tìm đường vòng qua đồ đạc |
| "quay lại chỗ cũ" | về vị trí trước lần `go_to` gần nhất |
| "đi tới bên trái cái bàn", "đứng trước cửa", "ra phía sau cái ghế", "cách cửa sổ 2 mét" | đích tính theo **quan hệ không gian** với đồ vật (`spatial.py`, ý tưởng của VLMaps). Toạ độ và kích thước đồ vật nằm trong `obj` / `size` của `waypoints_sim.yaml` |
| "đi tới cái bàn màu đen", "lại cái hộp vàng", "ra cái ghế sofa xanh", "đứng bên trái cái ghế màu tím" | **đồ vật theo tên + màu** (`objects.py`). Danh mục đọc từ file `.sdf`: 16 món, mỗi món có màu |
| "đi tới cái bàn" (có 2 cái bàn) | robot **hỏi lại**: *"bàn trà màu đen hay bàn ăn màu nâu ạ?"*; trả lời "cái màu nâu" thì nó đi |
| "đi tới cái bàn màu xanh" | *"Trong nhà không có bàn màu xanh ạ. Chỉ có màu nâu, đen thôi."* |
| "lưu chỗ này là phòng ngủ" | **dạy chỗ bằng giọng nói**: ghi vị trí hiện tại vào file điểm; sau đó nói "vào phòng ngủ" là robot tới |
| "đi thẳng 3 mét" mà có vật chắn giữa đường | **vòng qua vật, quay về đường thẳng cũ, tới đúng điểm 3 m**. Đích nằm trong tường/vật thì dừng và báo |
| **2 con**, ra lệnh mà chưa gọi tên con nào | robot hỏi lại *"Dạ, con 1, con 2 hay cả hai ạ?"*; trả lời "con hai" thì con 2 làm. Sau đó, trong 2 phút, lệnh không gọi tên sẽ đi tới con vừa được gọi |
| "mày đang ở đâu" | trả lời bằng tên chỗ gần nhất |
| **2 con:** "con một …", "con hai …", "cả hai …", "tất cả …" | chọn con làm |
| "con một ra cửa, còn con hai vào bếp" | mỗi con một việc, chạy song song |
| "cả hai đổi chỗ" | hai con đổi vị trí cho nhau, tự nhường đường |
| "con hai đi theo con một" | con 2 bám theo con 1, cách 0.9 m, tới khi nói "dừng lại" |
| "con hai lại chỗ con một" | con 2 đi tới đứng cạnh con 1 |
| "con một đang ở đâu" | trả lời bằng giọng nói |
| "dừng lại" (không gọi tên) | **dừng tất cả** |

## Né vật cản hoạt động thế nào

1. **Bản đồ tự vẽ từ cảm biến** (`nav_local.OccGrid`, ô 0.1 m). Robot không được cho trước bản đồ.
   Có hai lớp:
   - lớp LiDAR, quét 360°;
   - lớp D435i, chỉ được xoá trong vùng camera nhìn thấy (87°).

   Hai robot dùng chung bản đồ: con này thấy thì con kia cũng biết. Hướng nào cảm biến
   không trả về gì thì **không** xoá ô ở hướng đó, vì có thể vật đã vào quá gần, dưới tầm
   tối thiểu của LiDAR.
2. **Lập đường A\*** với vùng cấm 0.40 m quanh vật (bằng bán kính quét khi Go2 quay tại chỗ)
   và vùng "ngại" tới 0.80 m. Phần chưa
   thấy được giả định là trống (cách làm của D\* Lite). Cứ mỗi giây lập lại đường một lần.
3. **Bám đường bằng MPPI** (mặc định từ 21/11; `nav_local.MPPI`, theo Williams et al.
   ICRA 2016 / T-RO 2018, cùng ý tưởng bộ MPPI của Nav2):
   - **10 lần/giây**, thử khoảng 600 chuỗi lệnh (tiến, **ngang**, xoay) cho 2.4 s tới;
   - mô phỏng từng chuỗi bằng mô hình có độ trễ và hệ số "vận tốc thật / lệnh"
     (ước lượng online; gait CHAMP chỉ đạt khoảng 40–50 % vận tốc lệnh);
   - chấm điểm theo: va chạm (2 hình tròn phủ thân Go2), sát vật, người (dự đoán vị trí theo
     vận tốc), bám đường A\*, tiến về đích, ưu tiên đi tới, độ mượt;
   - lấy trung bình có trọng số các chuỗi tốt.

   Kết quả là robot **vừa đi vừa vòng qua vật**, không còn kiểu dừng → quay mặt → đi. A\* chạy
   ở luồng riêng (vòng điều khiển không bao giờ phải chờ) và giữ đường cũ nếu đường mới không
   tốt hơn rõ rệt, nên không đổi bên trái/phải liên tục.

   Chọn bộ điều khiển: `GOVOICE_CONTROLLER=mppi|dwa|pp`, hoặc nút "Né vật cản" trong Studio.
   - `dwa`: Dynamic Window Approach (Fox et al. 1997), dùng chung hàm chấm điểm.
   - `pp`: bản cũ (pure pursuit, dừng lại quay mặt khi lệch > 34°, phanh ở 0.22 m), giữ lại
     để so sánh.
4. **Phanh phản xạ**. Với MPPI, đây chỉ còn là lớp an toàn cuối: phanh khi còn dưới 9 cm
   theo đúng hướng lệnh. Với bản cũ (`pp`):
   - cảm biến cho thấy dưới 0.22 m trống phía trước thì dừng;
   - kẹt quá 3 s thì lùi 0.3 m rồi lập lại đường;
   - 3 lần liền không tìm được đường thì xoá bản đồ quanh robot (giống recovery
     "clear costmap" của Nav2).
5. **Nhiều robot**:
   - robot kia được coi là vật cản tròn bán kính 0.45 m;
   - khi đối đầu, con nào **gần đích hơn** thì được đi trước, con kia đứng chờ;
   - chờ quá 6 s thì con chờ tự nâng quyền ưu tiên để không bị kẹt (deadlock).

**Vì sao cần D435i:** LiDAR mù trong vòng 0.5 m quanh nó. Vì LiDAR nằm sau mép trước thân
0.15 m, nên khoảng 0.35 m ngay trước mặt robot là vùng mù. Vật thấp (ví dụ bậc cửa 12 cm)
cũng biến mất khỏi LiDAR khi robot lại gần. D435i cúi xuống phía trước thì thấy cả hai trường
hợp đó. Số đo ở mục *Đánh giá*.

## Bản đồ lớn: văn phòng + kho 30 × 20 m (`voice_office.sdf`)

```bash
ros2 launch go2_voice voice_sim.launch.py world:=voice_office.sdf      # hoặc chọn trong Studio
python3 movers.py --world voice_office --crowd 12 --carts              # 12 người + 3 xe đẩy
python3 run_sim.py --both                                              # tự nhận ra bản đồ
```

- **118 đồ vật**, mỗi cái có tên và màu:
  - **văn phòng** (phía tây): 18 bàn làm việc, 30 ghế đặt so le, cột, tủ hồ sơ, bếp;
  - **kho** (phía đông): 6 dãy kệ hàng, 12 pallet so le chắn nửa lối, hành lang **slalom 6
    cọc** so le ±0.55 m;
  - **sảnh**: khối 10 thùng xếp zíc-zắc, khe 0.9–1.1 m;
  - **phòng họp** và **sảnh vào**: quầy lễ tân, ghế dài, bậc 12 cm.
- Tường ngăn có cửa hẹp 1.2–1.6 m.
- **Vật động**:
  - 12 người đi bộ theo Social Force, trong đó 30 % "mải nhìn điện thoại", không né robot;
  - 3 xe đẩy hàng chạy qua lại trong kho.
- 11 địa điểm trong `waypoints_office.yaml`: sảnh, phòng khách, cửa chính, sảnh vào, phòng họp,
  văn phòng, bếp, chỗ sạc, kho hàng, góc kho, cuối kho.
- Gọi theo tên đồ vật được, ví dụ "đi tới cái kệ hàng màu xanh", "ra chỗ quầy lễ tân".
- Tạo lại bản đồ: `python3 tools/gen_voice_office.py unitree_go2_description/worlds/default.sdf
  > unitree_go2_description/worlds/voice_office.sdf` (cố định seed nên chạy lại ra y hệt).
- Đánh giá: `python3 eval_sim.py --suite office --configs mppi dwa pp`. Có 8 bài: xuyên khối so le,
  văn phòng, slalom cọc, lối pallet, bếp xa, sảnh 8 người, kho có xe đẩy, văn phòng có người.
  Ngoài thành công và va chạm còn đo **số lần khựng** (≥ 1 s mà thân dịch chuyển < 0.08 m/s,
  tính trước khi tới đích), thời gian khựng, tốc độ trung bình và số lần lắc hướng.

## Vật cản động: người đi lại giống thật

`movers.py` cho người đi lại trong nhà sim. Có hai chế độ:

```bash
python3 movers.py                      # 1 người đi qua lại cắt ngang phòng khách
python3 movers.py --crowd 3 --seed 1   # 3 người đi bộ tự do kiểu Social Force
```

**Social Force Model** (Helbing & Molnár, *Phys. Rev. E* 1995; lõi của PedSim):
- mỗi người tự chọn chỗ muốn tới và đi theo đường A\* trên bản đồ thật của nhà;
- tới nơi thì đứng 0.5–3 s rồi đi tiếp;
- tốc độ riêng khoảng 0.6–1.2 m/s;
- bị đẩy ra bởi tường, đồ đạc, người khác và robot; có lực tiếp xúc thân (Helbing et al.,
  *Nature* 2000);
- **30 % người "mải điện thoại" không né robot**, nên robot phải tự né.

Phía robot (`nav_local.BlobTracker`, `cpa`):
- gom điểm LiDAR thành cụm, ghép cụm qua các khung, ước lượng vận tốc;
- nếu một vật đang di chuyển sẽ tới cách robot dưới 0.75 m trong 2 s, robot **né ngang**
  (Go2 đi ngang được) hoặc **lùi** về phía còn trống;
- đường đi được lập để tránh luôn chỗ người **sắp** tới (1 s tới);
- bản đồ quên dần (1 điểm bằng chứng mỗi giây), nên vết người đi qua tự mờ, kể cả khi bị che.

## Lên robot thật, đủ chức năng (`run_real_ros.py`, `start_real.sh`)

```bash
# trên laptop
bash deploy_jetson.sh                     # đồng bộ thư mục này lên Jetson
# trên Jetson
bash start_real.sh --text                 # chạy thử bằng gõ phím trước
bash start_real.sh                        # nói qua mic robot
```

`start_real.sh` bật ba thứ:
1. `go2_hardware_bridge.py --allow-motion --lidar-rate 10`. Bridge tự dừng robot sau 0.5 s
   không có lệnh, và nhường quyền khi bạn dùng remote.
2. `realsense2_camera` cho D435i (depth 424×240, 15 Hz).
3. `run_real_ros.py --voice --mic-robot`.

Phần né vật cản dùng cùng thuật toán với sim (`robot_real.RealRobotTools` kế thừa
`RosRobotTools`). Khác ở chỗ:
- lọc thân và chân khỏi LiDAR L1 (đã đo trên robot ngày 11/9);
- extrinsic của L1 đo sẵn;
- giá đỡ D435i lấy theo `config.yaml` → `real:`;
- động tác gọi thẳng `SportClient`.

Robot thật không có file nhà để đọc danh mục đồ vật. Hai cách thay thế:
- dạy chỗ: "lưu chỗ này là bếp";
- khai báo `objects_real.yaml` theo mẫu trong `ObjectCatalog.from_yaml`.

⚠️ **Chưa chạy trên robot thật.** Mới kiểm tra cú pháp Python 3.8 và đường gọi trong sim.
Lần đầu chạy thật:
- cầm remote (L2+B là phanh cứng);
- bắt đầu bằng "đi thẳng 1 mét";
- kiểm tra `d435i_x`, `d435i_z`, `d435i_pitch` khớp giá đỡ, rồi mới thử né vật.

## Dataset cho LLM (`finetune/gen_dataset_ext.py`)

```bash
cd finetune && python3 gen_dataset_ext.py                      # -> data_v2/
python3 train_lora.py --base 1.5b --data-dir data_v2           # -> lora_out_1.5b_v2/
```

Thêm 2720 câu mới:
- đi tới phòng hoặc chỗ: 20 nơi, trong đó có 11 nơi mới;
- đi tới đồ vật theo màu: 33 loại đồ vật, 12 màu;
- quan hệ không gian: trái, phải, trước, sau, cạnh, "cách N mét";
- combo đồ vật kèm động tác;
- câu hỏi không phải lệnh ("cái bàn màu gì") thì không di chuyển;
- 25 % câu được bỏ dấu, mô phỏng lỗi STT.

Schema JSON và `grammar.gbnf` **giữ nguyên**: LLM chỉ trích cụm địa điểm (`"bàn màu đen"`,
`"bên trái ghế màu tím"`), còn `objects.py` / `spatial.py` tìm toạ độ. Tập test cũ 300 câu
giữ nguyên, nên con số 91.0 % vẫn so được. `data_v2/test_ext.jsonl` (200 câu) dùng để chấm
khả năng mới.

**Đã train xong (21/11):** `finetune/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf`. Test cũ đạt 93.0 %,
test mới đạt 87.5 %; model cũ trên test mới chỉ đạt 19.5 %. Chạy với:
`llama.cpp/build-cuda/bin/llama-server -m finetune/govoice-qwen2.5-1.5b-v2-q4_k_m.gguf -ngl 99 -c 2048 --port 8080`
Chi tiết ở `RESEARCH_NOTES.md` mục 4.2b.

## Có cần multiprocessing không?

Đo trong lúc chạy đánh giá:
- cả trợ lý (ROS, bản đồ, A\*, theo dõi người, safety, hàng đợi) dùng **khoảng 10 % của
  1 nhân CPU**;
- mỗi callback cảm biến mất 1–3 ms.

Các phần nặng đã ở tiến trình riêng: LLM (`llama-server`), đọc giọng nói (Piper), Gazebo,
bridge, camera. Nhận dạng giọng nói (CTranslate2, viết bằng C++) nhả khoá GIL khi chạy.

Tách thêm thành nhiều tiến trình sẽ:
- **mất bản đồ chung** giữa 2 robot;
- mất luật nhường đường (cần biết vị trí con kia ngay lập tức);
- thêm độ trễ truyền tin.

Thứ thật sự làm hệ thống chậm (đã sửa):
- `MultiThreadedExecutor` của rclpy làm rớt tin;
- nghe toàn bộ `/tf` trong Python;
- giải mã point cloud D435i.

## Đánh giá (số liệu cho bài báo)

```bash
ros2 launch go2_voice voice_sim.launch.py headless:=true             # T1
python3 eval_sim.py --suite single --trials 2                        # T2, khoảng 1 giờ
ros2 launch go2_voice voice_sim.launch.py headless:=true robots:=2   # T1
python3 eval_sim.py --suite multi --trials 3
```

Mỗi lần thử, `eval_sim.py` làm như sau:
- teleport robot về vị trí xuất phát và **xoá bản đồ** (môi trường chưa biết);
- nói câu lệnh qua đúng pipeline thật;
- chấm điểm bằng vị trí thật của Gazebo và hình học thật đọc từ `voice_house.sdf`.

Chỉ số: tỉ lệ thành công, va chạm, sai số, SPL, thời gian, khoảng hở nhỏ nhất. Kết quả lưu ở
`results/<suite>_<giờ>/` (`trials.csv`, `summary.md`, `traj.png`).

Các cấu hình so sánh:

| Cấu hình | Khác gì so với `full` |
|---|---|
| `full` | đầy đủ |
| `lidar_only` | bỏ D435i |
| `no_avoid` | đi thẳng tới đích, không phanh |
| `open_loop` | đi theo vận tốc × thời gian, như robot thật |
| `no_coord` | nhiều robot nhưng không nhường đường |

## Lên robot thật

Lớp hiểu lệnh, safety và hàng đợi dùng chung một mã với sim. Khi sim đã chạy đúng:
`bash deploy_jetson.sh`, rồi trên Jetson chạy `python3 run_real_robot.py --voice --mic-robot`.

Phần né vật cản (`robot_ros.py`) hiện mới chạy trong sim. Để dùng trên robot thật, cho nó đọc:
- `/go2/cmd_vel` và `/go2/odom` qua `go2_hardware_bridge.py --allow-motion`;
- LiDAR L1 `/go2/lidar/points`;
- depth của D435i từ `realsense-ros` (16UC1 hoặc mm, intrinsics lấy từ `camera_info`; cả hai
  đều đã hỗ trợ).

Xem `RESEARCH_NOTES.md`, mục *Việc tiếp theo*.
