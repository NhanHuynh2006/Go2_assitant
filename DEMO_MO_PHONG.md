# Chạy demo mô phỏng có hình (để quay clip)

Bản đồ là văn phòng lớn `voice_office.sdf` (32 × 22 m): sảnh, văn phòng, bếp, kho, pallet, người đi bộ và xe đẩy.

Trước khi quay, đóng các sim khác đang chạy ngầm. Kiểm bằng `pgrep -fa "gz sim"`; nếu còn sim nào, tắt nó theo PID.

## 0. Chạy trong MỖI terminal trước tiên

```bash
source /opt/ros/lyrical/setup.bash && source ~/ros2_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST GZ_IP=127.0.0.1 OPENBLAS_NUM_THREADS=1
cd ~/Documents/Go2_assitant
export GOVOICE_FAST_SO=$PWD/research/algo_fast/fast.so
```

## 1. Terminal 1: mở sim (Gazebo 3D + RViz)

```bash
ros2 launch go2_voice voice_sim.launch.py world:=voice_office.sdf
```

- Chờ khoảng 30–40 s cho tới khi con chó đứng lên trong Gazebo.
- Không muốn mở RViz thì thêm `rviz:=false`.

## 2. Cách A: tự chạy lần lượt 8 tình huống (C1 rồi B1, tiện quay cảnh so sánh)

Terminal 2:

```bash
venv/bin/python eval_sim.py --suite office --trials 1 --out results/demo_office \
  --configs "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5" "mppi~t3~nl:ppl=100;ppl_len=0.5"
```

**Tám tình huống:** khối so le → văn phòng → slalom cọc → lối pallet → bếp xa → sảnh 8 người → kho có xe đẩy → văn phòng có người.

**Chọn bớt tình huống:**
- Chỉ các cảnh có người: thêm `--only crowd`.
- Chỉ một số cảnh: dùng `--only sanh_8,van_phong_dong`. Các tên dùng được: `qua_khoi`, `van_phong`, `slalom`, `loi_pallet`, `bep_xa`, `sanh_8`, `kho_xe_day`, `van_phong_dong`.

**Muốn quay cả DRA\*:** thêm chuỗi `"dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05"` vào `--configs`.

**Kết quả:** `results/demo_office/summary.md`, gồm thành công, va chạm và thời gian.

Cách này chỉ hiện con chó và người trong Gazebo. RViz không vẽ người đang được theo dõi; muốn có thì dùng Cách B.

## 3. Cách B: tự ra lệnh, RViz vẽ đầy đủ (người đang theo dõi, mũi tên vận tốc, đường đi)

**Terminal 2:** thả 12 người đi bộ và 3 xe đẩy.

```bash
venv/bin/python movers.py --world voice_office --crowd 12 --carts
```

**Terminal 3:** chạy robot bằng thuật toán C1.

```bash
GOVOICE_CONTROLLER='p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5' venv/bin/python run_sim.py --no-tts
```

Gõ lệnh, ví dụ: `đi tới bếp`, `đi tới văn phòng`, `đi tới kho hàng`, `đi tới sảnh vào`, `đi tới phòng họp`, `đi tới cuối kho`, `đi tới chỗ sạc`.

Các địa điểm có sẵn: bếp, chỗ sạc, cuối kho, cửa chính, góc kho, kho hàng, phòng họp, phòng khách, sảnh, sảnh vào, văn phòng.

**So với B1 (MPPI chuẩn):** thoát (Ctrl+C) rồi chạy lại Terminal 3 với bộ điều khiển khác.

```bash
GOVOICE_CONTROLLER='mppi~t3~nl:ppl=100;ppl_len=0.5' venv/bin/python run_sim.py --no-tts
```

Muốn nói bằng mic thay vì gõ phím thì bỏ `--no-tts` và thêm `--voice`. Cần llama-server cho câu phức tạp; lệnh đơn vẫn chạy.

## 4. Tắt

Bấm Ctrl+C ở mọi terminal. Nếu Gazebo còn treo, kiểm bằng `pgrep -fa "gz sim"` rồi tắt theo PID.

## Lưu ý trước khi quay

- **C1 có thể kẹt trên bản đồ này.** Ngày 25/11, chạy thử nhanh 3 bài (khối so le, bếp xa, văn phòng có người):
  - C1 kẹt cả 3 bài;
  - B1 tới đích 2/3 bài.

  Đang đo đủ 8 bài × 3 thuật toán × 3 lần (`results/OFFICE_EXPL/`). Xem kết quả trước để chọn cảnh quay cho đúng.
- **Mỗi lần chạy mỗi khác.** Người đi bộ có ngẫu nhiên, nên một lượt thành công hay thất bại không đại diện cho cả thuật toán. Con số đại diện nằm trong bài báo, tính trên hàng nghìn lượt.
