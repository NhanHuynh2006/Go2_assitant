# REPORT_ISAAC (22–23/11/2026)

## 1. Yêu cầu chính thức so với máy này
Nguồn (đọc qua WebFetch): [Isaac Sim 5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html),
[Isaac Lab 2.3.2 install](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/index.html),
[pip install](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/pip_installation.html).

| mục | tối thiểu | máy | |
|---|---|---|---|
| GPU / VRAM | RTX 4080 / 16 GB | RTX 4060 Laptop / 8 GB | **DƯỚI** |
| RAM | 32 GB | 14 GB | **DƯỚI** |
| OS | Ubuntu 22.04/24.04 | 26.04 | **không hỗ trợ** |
| glibc (pip) | ≥ 2.35 | 2.43 | đạt |
| driver | ≥ 580.65.06 | 595.99 | đạt số, nhưng kết quả tìm kiếm diễn đàn NVIDIA có ca 595.x làm hỏng GUI/RTX (chỉ đọc trích đoạn, trang trả 403) |
| ổ đĩa | 50 GB | còn 193 GB | đạt |

Kết luận: **máy dưới mức tối thiểu**; chỉ chạy được vật lý headless, KHÔNG thử GUI/camera/RTX (đừng thử trên máy này).

## 2. Cài đặt (xong, không sudo/apt/driver; chỉ trong ~/isaac)
- **Vì sao `import isaaclab` hỏng:** (a) lần 1 `isaaclab.sh` thoát ở lệnh `tabs` vì không có TERM (sửa TERM=xterm); (b) lần 2
  `flatdict==4.0.1` (phụ thuộc của gói lõi `isaaclab`) không build được vì setuptools ≥ 82 bỏ `pkg_resources`; `isaaclab.sh` không
  dừng nên các gói phụ (_assets/_rl/_mimic/_tasks) vẫn vào. `isaacsim` 5.1.0.0 **đã cài đủ**. Sửa: `uv pip install --build-constraints`
  với `setuptools<81`, rồi `numpy==1.26.0`. Cách sửa ghi ở cuối `~/isaac/install_isaaclab.sh`, log `~/isaac/install_run3.log`.
- Xung đột phụ thuộc của chính NVIDIA: isaaclab đòi starlette 0.49.1, isaacsim-kernel (fastapi) đòi < 0.46 -> livestream có thể hỏng; headless không ảnh hưởng.
- **Giấy phép:** `OMNI_KIT_ACCEPT_EULA=YES` (có sẵn trong script, và tôi đặt khi chạy) = chấp nhận EULA NVIDIA Omniverse. **Người dùng đã đồng ý rõ ràng ngày 23/11** (lúc cài, agent đặt cờ này trước khi hỏi). 23/11 20:10, theo lời điều phối viên chuyển: người dùng **đã chấp nhận trước mọi giấy phép phần mềm** (user accepted 23/11). sudo chỉ điều phối viên dùng.
- Checkpoint chính thức Isaac Lab (S3 NVIDIA, 14/10/2025): Go2 Flat (300 vòng), Rough (1500 vòng) ở ~/isaac/ckpt, nạp `weights_only`. Không train gì.

## 3. Chạy được không: ĐƯỢC (headless)
Đã chờ GPU rảnh + RAM > 6 GB (`~/isaac/gate.sh`). nice 10–19, có tiến trình CPU khác chạy cùng.

| | RAM tiến trình (đỉnh) | VRAM tăng (toàn máy) | RTF mỗi robot | RTF gộp |
|---|---|---|---|---|
| 1 robot, PhysX CPU | 1.7 GB | ~0 | 0.83 | 0.8 |
| 1 robot, PhysX GPU | 3.2 GB | ~2.3 GB | 0.77 | 0.8 |
| 64 robot flat, GPU | 3.2 GB | ~2.3 GB | 0.86 | 55 |
| 62 robot rough, GPU | 3.3 GB | ~2.3 GB | 0.66 | 41 |

Nghẽn ở vòng Python (~23 ms/bước 20 ms), không phải VRAM: muốn nhanh thì chạy nhiều robot song song. Bộ điều khiển + trạm Isaac cần ~2–3.5 GB RAM.

## 4. Động học đo (policy chính thức, sàn phẳng, ma sát 0.8/0.6, khối lượng ngẫu nhiên 14–18 kg, 50 Hz)
`steps`: 62 mức lệnh × 12 lần, đứng 1.5 s / lệnh 4 s / dừng 2 s, v ổn định = 2 s cuối. `random`: y hệt pipeline/sysid.py (16 robot × 120 s,
~1134 đoạn). CI95 bootstrap theo đoạn (không gom theo robot nên hơi hẹp). Bảng đủ: isaac_val/tables_steps.md, tables_random.md; số: isaac_val/sysid_isaac.npz.
CHAMP: results/sysid.npz tính bằng CÙNG mã (150 đoạn). DYN: dyn/go2_params.yaml.

| gain | Isaac flat | Isaac rough | CHAMP | DYN (chó thật) |
|---|---|---|---|---|
| vx .05–.2 | 0.38 [.31,.44] | 0.58 [.50,.66] | 0.61 [.41,.76] | 0.95 (.75–1.20, gián tiếp) |
| vx .2–.4 | 0.76 [.72,.79] | 0.83 [.78,.87] | 0.80 [.76,.85] | nt |
| vx .4–.6 | 0.97 [.95,.97] | 0.99 [.97,1.00] | **0.52** [.49,.55] | nt |
| vx lùi ≤ .2 | 0.40 [.31,.50] | 0.69 [.63,.74] | 1.10 [.88,1.32] | 1.0 giả định |
| vy .05–.15 | 0.41 [.33,.50] | 0.47 [.38,.58] | 1.09 [.92,1.29] | 0.95 (.70–1.20, tài liệu) |
| vy .15–.3 | 0.69 [.64,.74] | 0.72 [.68,.76] | 1.00 [.93,1.05] | nt |
| wz tại chỗ | **0.04** [.03,.06] | 0.71 [.66,.75] | 0.73 [.63,.86] | 0.90 (.65–1.10, tài liệu) |
| wz khi \|v\|>.25 | 0.79 [.73,.85] | 0.94 [.90,.97] | 0.81 [.71,.97] | nt |

(Hàng wz: |lệnh| > 0.2. Bài steps, lệnh giữ 4 s, rough quay tại chỗ chỉ 0.28–0.51 ở ±0.5 và 0.60/0.75 ở ±1.0, không đối xứng.)

| | Isaac flat / rough | CHAMP (fastsim) | DYN |
|---|---|---|---|
| vx 0.2 / 0.3 / 0.4 / 0.6 / 1.0 -> v | .07/.24/.36/.60/1.01 — .05/.21/.36/.61/.98 | bão hoà ~0.29 | không bão hoà tới 1.4 |
| tau (bậc 1 + trễ), vx .4–1.0 | .06–.22 / .12–.24 s | .15 | .28 (.15–.45) |
| trễ | 0.00–0.05 s | .05 | .10 (giả định) |
| t90 vx .4–1.0 | .16–.52 / .42–.80 s | — | — |
| quãng trôi sau stop, v=.6 / 1.0 | .03/.10 — .11/.11 m | — | ~0.28·v0 = .17/.28 m (cận trên) |
| lắc x, y (m), yaw (rad) | .001, .002, .002 / .002, .003, .005 | .02, .02, .06 | .011, .0045, .008 |
| lắc roll, pitch (rad), .2–.5 m/s | .005,.008 / .023,.018 | — | .010,.011 |

- **Vùng chết:** cả hai policy gần như đứng yên khi |vx| ≲ 0.2, |vy| ≲ 0.15–0.3 (không đối xứng trái/phải), flat KHÔNG quay tại chỗ (|wz| tới 1.0). Đây
  là tính chất policy của Isaac Lab (thưởng feet_air_time chỉ bật khi lệnh > 0.1 — **suy đoán** về nguyên nhân), KHÔNG phải bằng chứng về Go2 thật.
- Ở lệnh nhỏ, tau trong bảng (≈0.02–0.05) là thân nghiêng rồi dừng, không phải bước đi: bỏ qua. tau wz tại chỗ không có nghĩa vì lý do này.
- Trễ ≈ 0 vì policy thấy trạng thái hoàn hảo, không DDS: cận dưới. Lắc Isaac nhỏ hơn chó thật (~3–5 lần ở x) và CHAMP (10 lần) -> không dùng để hiệu chỉnh lắc.
- Ngã: flat 0/744 đoạn; rough 8/744 (1.1 %; 3 ở quay tại chỗ, 5 ở |vx| ≤ 0.2) + 1 lần trong 32 phút random.

Sai số dự đoán vòng hở (tb m sau 2 s; 400 cửa sổ, không CI): Isaac flat: lý tưởng .111, champ .140, go2 .123; rough: .116/.153/.109; CHAMP: .176/.097/.159
(champ khớp trên chính dữ liệu đó, trong mẫu). -> Isaac **giống regime go2 hơn champ**, nhưng đây là sai số chung của mô hình bậc 1, không phân được go2 với v=lệnh.

Thêm **champ2** (fastsim 23/11: cắt lệnh 0.3/0.25/0.5 + trôi lùi 0.053 m/s; tham số giữa dải lấy mẫu): sai số 2 s trên CHAMP **.064** m (khớp
pipeline/sysid_fit2.py 0.062; trong mẫu), trên Isaac flat .162, rough .184 (tệ nhất trong 4 mô hình vì Isaac không cắt ở 0.3). Đúng như mong đợi: champ2 là
mô hình của CHAMP, không phải của thân Go2. Bảng đủ: isaac_val/tables_random.md.

**Nhiễu quan sát bật** (đúng như lúc train; 62 robot × 6 lần, seed 1): vùng chết **nhỏ đi rõ** — rough: vx 0.2 gain .66 (không nhiễu .25), vy ±0.3 .95/.73
(.91/.54), wz ±0.5 .74/.77 (.28/.51), wz ±1.0 .78/.87 (.60/.75); flat vẫn gần như không quay tại chỗ (wz −0.5: .02). Ngã rough 2/372. Lắc tăng nhẹ
(rough .2–.5 m/s: x/y .004 m, yaw .008 rad, roll/pitch .023/.022). -> Vùng chết phần lớn là do chạy policy NGOÀI phân bố train (cấu hình Play tắt nhiễu);
khi kiểm chéo nên bật `--noise`. Bảng: isaac_val/tables_steps.md (mục *_noise_steps).

## 5. Ý nghĩa cho chương trình
1. Isaac xác nhận độc lập là **bão hoà 0.29 m/s là của CHAMP**, không phải của thân Go2 (hai policy khác đi tới 1.0 m/s, gain ~1). Không xác nhận gain chó thật.
2. Đừng đưa vùng chết Isaac vào regime go2 như số đo; dùng làm **regime nhiễu thứ ba** ("deadband") nếu muốn thử độ bền: deadband vx ~0.2, gain ~1 sau đó. Cần chó thật đo lệnh 0.05–0.3 (dyn/HUONG_DAN_DO.md) — điều bộ điều khiển dùng thường xuyên khi nhường/áp sát.
3. Dùng policy **rough**, không dùng flat (flat không quay tại chỗ -> bộ điều khiển sẽ kẹt vì lý do giả tạo). Rough vẫn kém ở vy/wz nhỏ nên mọi số thành công trên Isaac phải đọc cùng bảng trên.

## 6. Thiết kế cắm bộ điều khiển (đã viết, chạy thử chức năng 3 seed)
`isaac_val/body_server.py` + `isaac_val/isaac_sim.py`: tiến trình Isaac (Python 3.11) tách khỏi tiến trình bộ điều khiển (venv) vì fastsim thay
`time.monotonic/sleep`. Server: N robot trên sàn phẳng; socket UNIX, lockstep 0.02 s (chỉ bước khi MỌI client đã gửi lệnh) = đồng hồ ảo.
Client: `IsaacSim(fastsim.Sim)` chỉ thay `substep` (gửi lệnh, nhận x,y,yaw,v); tia 2D, `movers.Crowd`, tracker, MPPI và `check` giữ nguyên.
- Vật cản/người không cần trong PhysX vì lượt dừng ở chạm đầu tiên (kiểm hình học); không có phản lực va chạm. Trước khi dùng: kiểm va bằng chân thật
  (server đã trả `feet`) và cho tia nghiêng theo roll/pitch (server đã trả) — đây là phần "độc lập" đáng giá nhất.
- `at_fault` dùng wz lọc 0.25 s (thay vì tức thời). Trễ lệnh lấy mẫu như regime go2 vì Isaac không có trễ. Chỉ nhận seed 0–999.
- Độc lập THẬT chỉ ở động học thân; tia/đám đông/tracker vẫn chung mã fastsim, nên không phát hiện được lỗi ở các phần đó.
- Lỗi đã sửa: `self.acc` (giới hạn gia tốc của regime go2 trong fastsim) trùng tên bộ đếm thời gian -> đổi `_qacc`.

**Thử chức năng (mppi, seed DEV 0–2, trial 0, crowd base; rough KHÔNG nhiễu; n = 3 nên KHÔNG kết luận gì về thuật toán):**

| thân | tới đích không va | ghi chú | giây máy/lượt |
|---|---|---|---|
| isaac (rough) | 3/3 | 43–47 s mô phỏng, min người .37–.62 m | 56–120 |
| fastsim champ | 1/3 | 2 va người (dừng sớm ở 26–28 s) | 9 (lượt tới đích) |
| fastsim champ2 | 2/3 | 1 va người (seed 2) | 22–33 |
| fastsim real/go2 | 3/3 | 37–53 s | 12–17 |

Giao diện chạy hết, không ngã, không lỗi socket. Tốc độ thật: ~1.3–2.5 s máy cho 1 s mô phỏng (server RTF 0.4 khi cộng bộ điều khiển, 1 robot, PhysX CPU, máy đang có ALGO chạy).

## 7. Chưa làm / chưa chắc
- Bài nhiễu + thử chức năng đã chạy 08:58–09:10 (cổng RAM hạ xuống 5.0 GB theo điều phối viên; watchdog giết Isaac nếu RAM trống < 1 GB: không lần nào kích hoạt).
- Chưa có: kiểm va bằng chân thật, tia nghiêng theo roll/pitch, nhiều robot song song qua 1 server (mã hỗ trợ, chưa thử).
- Chỉ sàn phẳng, một ma sát, một seed; không tải trọng OS1+Orin; không đo được SportClient.
- CI bootstrap theo đoạn, không theo robot.

## 8. Phương án thay / bổ sung
1. Giữ Isaac Lab headless (PhysX CPU, 1.7 GB RAM, không đụng VRAM) cho kiểm chứng chéo; RTF 0.83 nên 100 lượt × ~60 s ≈ 2 giờ + thời gian bộ điều khiển (ước tính).
2. MuJoCo + [mujoco_menagerie unitree_go2](https://github.com/google-deepmind/mujoco_menagerie) (BSD-3, có Go2 12 DoF): nhẹ, độc lập thứ ba; cần policy tương thích (thứ tự khớp, PD 25/0.5, chu kỳ 50 Hz của checkpoint Isaac). Chưa thử.
3. Không khuyến nghị RTX/camera/GUI trên máy này.

## 9. Đề xuất kiểm chứng chéo (CHƯA chạy; chỉ DEV/VAL, không bao giờ TEST)
- **Mục đích:** xem thứ hạng/hiệu giữa các cấu hình trên fastsim có giữ nguyên khi thay thân bằng động học Isaac (lớp né là lệnh vận tốc).
- **Thân:** isaac rough `--noise` (chính), isaac rough không nhiễu (độ nhạy vùng chết). So với fastsim `go2`, `champ2` trên CÙNG seed/trial (ghép cặp).
- **Cấu hình (4):** `mppi`, `mppi:ppl=32` (baseline đã chỉnh), ứng viên cuối của ALGO (1, tối đa 2), `dwa`. Không thêm cấu hình mới trên Isaac (Isaac không dùng để chọn).
- **Thế giới:** 100 bản đồ CÓ người đầu tiên trong seed DEV 300–999 (tránh 0–149 đã dùng phát triển nhiều), trial 0, crowd base; rồi lặp lại với helb nếu có thời gian.
  VAL 2000–2399: chỉ khi điều phối viên muốn và tự chạy. Chỉ số: tới đích không va (mọi va + ngã tính là hỏng; ngã báo riêng), Wilson 95 %, McNemar ghép
  cặp với Holm; thêm tương quan hạng Kendall giữa fastsim-go2 và isaac trên 4 cấu hình, cùng tỉ lệ thời gian lệnh nằm trong vùng chết.
- **Trước khi chạy cần:** kiểm va bằng chân, tia nghiêng (khoảng 1–2 giờ viết, chưa làm); 5 seed thử lại.
- **Thời gian (ước tính):** 100 × 4 = 400 lượt × ~50 s mô phỏng = 20 000 s mô phỏng. 1 robot tuần tự ở mức đo được (1.3–2.5 s máy/s mô phỏng) = **7–14 giờ**;
  chỉ tính RTF 0.83 của Isaac thì cận dưới ~6.7 giờ. Với 1 server GPU 4–8 robot lockstep + 4–8 client (bước Isaac ~24 ms gần như không đổi theo số robot;
  điều khiển ~0.3 s CPU/s mô phỏng/robot): ước tính 1.5–3 giờ, dùng 4–8 luồng CPU, ~3.3 GB RAM server + ~0.3 GB/client — **chưa đo, phải thử 2 robot trước**.
  Cả hai chế độ (noise/không) gấp đôi. Chạy nice 10, cổng RAM 5 GB + watchdog 1 GB, chỉ khi MODEL không dùng GPU.

## 10. Kiểm chứng chéo: chuẩn bị, benchmark, pilot (23/11 20:10–)
### 10.1 Chuẩn bị (xong)
- **Va bằng chân thật:** server trả 4 bàn chân (Isaac, 50 Hz); client kiểm mỗi bước 0.02 s: chân (bán kính 0.022 m) chạm hộp tĩnh / người / xe -> ghi `foot`, `foot_t`.
  KHÔNG dừng lượt (lượt vẫn dừng theo khung 2D như fastsim) để so trên CÙNG lượt; `succ_foot` = thành công 2D và không chạm chân trước đó.
- **Tia nghiêng:** LiDAR (rmax 6 m) lọc theo roll/pitch thật: tia chạm sàn trước vật -> mất (như bộ lọc độ cao của pointcloud_to_scan), tia vượt đỉnh vật
  -> mất. GIẢ ĐỊNH: LiDAR cao hơn tâm thân 0.10 m, vật tĩnh cao 1.0 m, người 1.75 m (fastsim không có chiều cao). Camera (rmax 4) giữ nguyên.
  Cài bằng cách bọc `Boxes.cast`/`cast_circles` quanh `fastsim.Sim.sense` (không chép mã). Góc phương vị lệch bậc 2 (~0.001 rad) bị bỏ qua.
- **Unit test** `isaac_val/test_isaac_rays.py` (đều qua): (1) tilt 0 -> mảng khoảng cách bằng hệt fastsim (3 thế giới × 20 tư thế); (2) tilt 0 -> `sense` đầy đủ
  (local_obs, local_depth, 2 lưới chiếm chỗ, tracker) **bằng hệt từng bit** `fastsim.Sim.sense` qua 12 bước × 3 thế giới; (3) chúi 0.1 rad mất tia trước ở 5 m,
  giữ ở 3 m; lăn 0.2 rad mất tia trái ở 5 m; hàm gốc được trả lại sau sense (kể cả khi `F.Sim` đã bị thay bằng IsaacSim — lỗi đệ quy đã gặp và sửa).
- **Reset tất định** (server v2): tư thế/khớp cố định, khối lượng thân = mặc định + U(−1, 3) kg theo seed (thế giới, lượt), nhiễu quan sát Unoise Isaac Lab
  bằng Generator riêng mỗi chỗ gieo theo seed. Policy rough + nhiễu.

### 10.2 Benchmark nhiều robot (8 lượt mppi, 8 thế giới có người đầu tiên từ 302; GPU; mọi tiến trình của ISAAC trong nhân 13–15, nice 10)
| N robot | s mô phỏng / s máy / robot | thông lượng (s mô phỏng / s máy) | thành công |
|---|---|---|---|
| 1 | 1.06 | 1.1 | 6/8 |
| 2 | 0.78 (lặp lại 0.67) | 1.4–1.6 | 7/8 |
| 4 | 0.54 | 2.2 | 5/8 |
| 8 | 0.50 | 4.0 | 5/8 |
VRAM toàn máy ≤ 2.6 GB (dưới 4 GB), RSS server 3.2 GB, MemAvailable thấp nhất 7.3 GB; watchdog không kích hoạt. Máy đang tải 12–26 (ALGO + điều phối viên).
- **Tất định:** chạy lại y hệt (N = 2, cùng chia): **8/8 lượt giống từng chữ số** (time, travel, min_person, chân). Đổi N (1/2/4/8) thì KHÔNG giống:
  2–3/8 lượt đổi thành công/va (302, 303 lật), các lượt khác lệch vài cm. Nguyên nhân (suy đoán): PhysX GPU không cho cùng kết quả khi cảnh khác cỡ/lịch sử
  chỗ khác; tương tác người–robot hỗn loạn khuếch đại. => Kết quả Isaac lặp lại được **khi giữ nguyên N và cách chia**; mức lật giữa các N là thước đo
  nhiễu Isaac cho từng lượt (chỉ so tỉ lệ, không so từng lượt).
- Bug đã sửa khi chạy: Kit bỏ qua SIGTERM -> server cũ treo và giữ cổng GPU; nay kill -9 theo PID.

### 10.3 Pilot (xong 24/11; 500 lượt Isaac, 0 lỗi; 6961 s máy với N = 8)
Thế giới: 100 thế giới có người đầu tiên trong DEV 300–799 (= seed 302–439), trial 0, crowd base. Isaac: rough + nhiễu, tia nghiêng, N = 8, chia `i/8` cố định
(chạy lại y hệt cấu hình này sẽ cho y hệt số, xem 10.2). fastsim: go2 và champ2 dùng lại hàng của ALGO (`results/algo_V{go2,champ2}_base`) cho 3 cấu hình
đã có — **kiểm chạy lại 44/44 lượt giống từng chữ số** (`results/isaac_fs_chk_go2`) — còn mppi, dwa và cả 5 cấu hình champ thì tôi chạy (`results/isaac_fs_*`, 2 job, nhân 13–15).
Ghi chú: `dwa` ở đây là dwa trơn theo yêu cầu, KHÔNG phải `dwa~t3~nl:ppl=100;ppl_len=0.3` của ALGO.

Tới đích không va (Wilson 95 %); va bất kỳ loại nào và ngã đều tính là hỏng:
| thân | mppi | mppi:ppl=32 | dwa | baseline chỉnh `mppi~t3~nl:ppl=100;ppl_len=0.5` | ứng viên `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5` |
|---|---|---|---|---|---|
| **isaac** | 64 [54–73] | 72 [63–80] | 63 [53–72] | 75 [66–82] | **83** [74–89] |
| go2 | 74 [65–82] | 79 [70–86] | 64 [54–73] | 87 [79–92] | **93** [86–97] |
| champ2 | 48 [38–58] | 58 [48–67] | 43 [34–53] | **74** [65–82] | 73 [64–81] |
| champ | 47 [38–57] | 62 [52–71] | 42 [33–52] | 80 [71–87] | **83** [74–89] |

Ứng viên so với baseline chỉnh (McNemar ghép cặp, Holm trong mỗi thân với 4 so sánh): isaac +20/−12, p = 0.22 (Holm 0.43); go2 +12/−6, p = 0.24;
champ2 +11/−12, p = 1; champ +16/−13, p = 0.71. => **Chiều dương ở isaac, go2, champ; ở champ2 thì bằng nhau. Không thân nào có ý nghĩa.**
Trên Isaac không cấu hình nào khác baseline có ý nghĩa sau Holm (dwa −12, p_Holm 0.26; mppi −11, 0.24). Trên fastsim, dwa/mppi kém baseline có ý nghĩa
ở go2/champ2/champ (Holm ≤ 0.09; ≤ 1e-4 ở champ/champ2).
- **Thứ hạng 5 cấu hình:** Kendall τ isaac–go2 **+1.00**, isaac–champ +1.00, isaac–champ2 +0.80 (chỉ khác ở thứ tự hai cấu hình đầu bảng). 5 điểm
  nên τ rất thô; nhưng không có đảo thứ hạng nào giữa các cấu hình cách nhau > 5 điểm.
- **Mức tuyệt đối:** Isaac thấp hơn go2 6–12 điểm ở mọi cấu hình trừ dwa (−1); cao hơn champ/champ2 ở mppi/dwa (+15–20). Từng lượt giống go2 73 %,
  champ2 64 %, champ 63 % (đã biết 2–3/8 lượt lật chỉ vì đổi N, nên ~25 % bất đồng là gần mức nhiễu từng lượt).
- **Kiểu hỏng chỉ có ở Isaac: NGÃ 13/500**, trong đó **11 ở hai cấu hình `~t3`** (baseline 5, ứng viên 6; mppi 1, dwa 1). Tĩnh 7 (baseline 5, dwa 2), fastsim go2 0.
  Kể cả nếu coi mọi lượt ngã là thành công (cận trên) thì ứng viên 89 vs baseline 80: thứ tự không đổi. CHƯA biết lệnh nào gây ngã (không ghi lệnh); giả thuyết cần kiểm: đổi chiều/quay gắt kiểu `~t3`
  ngoài phân bố train của policy. Cũng chưa tách va tĩnh do tia nghiêng hay do động học (cần chạy lại `--notilt`).
- **Chân vs khung 2D (cùng lượt):** chạm chân 25/500, phần lớn đi kèm va khung; **chỉ chân, khung không va: 7** (dwa 4, mppi 2, ppl=32 1; 0 ở hai cấu hình
  `~t3`). Tính cả chân: mppi 64→62, ppl=32 72→71, dwa 63→59, baseline 75, ứng viên 83 (không đổi). Khung 2D của fastsim (0.64 × 0.50 m) gần như bao
  được chân; chênh ≤ 4 điểm và không đổi kết luận.

**Kết luận pilot (n = 100, một trial, một mô hình người):** Isaac xác nhận **thứ hạng** của fastsim và cho ứng viên cùng chiều dương với baseline chỉnh như go2
(+8 điểm, không có ý nghĩa). Không xác nhận được lợi thế có ý nghĩa ở bất kỳ thân nào. Rủi ro mới cho triển khai: **ngã ở cấu hình `~t3`** dưới policy học
(là policy Isaac, không phải SportClient: chỉ là cảnh báo, không phải bằng chứng về chó thật).

**Đề xuất tiếp:** (1) ghi lệnh 2 s trước khi ngã và chạy lại 13 lượt ngã (cùng N/chia, tất định) để biết nguyên nhân; (2) `--notilt` trên cùng 100 thế giới
cho baseline + ứng viên, để tách ảnh hưởng của tia nghiêng; (3) nếu ALGO chốt ứng viên khác thì thêm đúng cấu hình đó, cùng thế giới, N = 8 (~25 phút/cấu hình
khi máy tải nặng như hôm nay); (4) VAL do điều phối viên chạy.
Tệp: `isaac_val/res_pilot.csv`, `isaac_val/pilot_stats.txt`, `isaac_val/pilot_stats.py`, `results/isaac_fs_{go2,champ2,champ,chk_go2}`.

## 11. Điều tra ngã ở cấu hình `~t3` (24/11 01:50–06:40)
Cùng 100 thế giới DEV (302–439 có người), trial 0, crowd base, Isaac rough + nhiễu, N = 8; mọi tiến trình trong nhân 13–15, nice 10; VRAM ≤ 2.3 GB/server,
watchdog không kích hoạt. `res_pilot.csv`: đã bỏ 7 dòng tiêu đề lặp.

### 11.1 Tất định (sửa lỗi) và phát lại ngã
- Pilot §10 **không phát lại được**: chạy lại y hệt chỉ 8/44 lượt giống. Nguyên nhân: server bắt đầu bước khi mới có vài client kết nối, và gán chỗ theo thứ tự
  kết nối (phụ thuộc giờ máy). Sửa (server/client v3): **hàng rào** (chờ đủ client mới bước lần đầu) + **chỗ cố định = shard** (`hello`).
  Vì vậy 13 lần ngã của pilot §10 không phát lại đúng được; số của §10 vẫn đúng là một mẫu, nhưng không tái tạo được từng lượt.
- v3: N = 2 lặp lại 8/8 giống; tiền tố 32 thế giới (`nlrep`) giống `nl` **64/64**; **phát lại chỉ 3 shard có ngã (5 chỗ khác đứng yên): 58/58 lượt giống,
  6/6 lần ngã lặp lại đúng thời điểm** (w363 90.1 s, w386 17.6 s, w414 11.4 s, w366 31.8 s, w377 21.8 s, w404 74.3 s). Đổi N thì vẫn khác (PhysX GPU theo cỡ cảnh).

### 11.2 Kết quả (đếm trên 100 lượt mỗi ô; ngã tính là hỏng)
| chạy | baseline: thành công / ngã | ứng viên: thành công / ngã | ghi chú |
|---|---|---|---|
| `nl` (`~t3~nl`, tia nghiêng) | 73 / 3 | 87 / 3 | tham chiếu v3 |
| (a) `t3` (bỏ `~nl`) | 82 / 4 | 86 / 5 | **ngã KHÔNG giảm** (9 vs 6) |
| (b) `nlnotilt` (`~t3~nl`, tia phẳng) | 85 / 3 | 86 / 4 | ngã không đổi (7 vs 6) |
| `nlcs` (`~t3~nl` + bộ nắn lệnh, §11.4) | 73 / **0** | 92 / **0** | 0/200 so với 22/600 ở ba dòng trên (Fisher một phía p = 0.0016; so riêng `nl` 0/200 vs 6/200, p = 0.015) |
| fastsim go2 `~t3~nl` | 87 / 0 | 93 / 0 | fastsim không có ngã |
| fastsim go2 `~t3~nl` + nắn lệnh | 79 / 0 (+7/−15, p = 0.13) | 88 / 0 (+2/−7, p = 0.18) | **giá phải trả** −5 đến −8 điểm (chưa có ý nghĩa) |
Ghi chú: baseline lệch 73→82→85 giữa các chạy chỉ vì đổi tag/tia (McNemar `nl`→`nlnotilt` +20/−8, p = 0.04 chưa hiệu chỉnh): mức hỗn loạn từng lượt của Isaac lớn; đừng đọc
chênh 10 điểm của baseline giữa các dòng là tác dụng của tia.

### 11.3 Giả thuyết `~nl` thổi phồng lệnh: BÁC BỎ
- RespModel học được gần đúng **gain ≈ 1** trên Isaac (cuối lượt, trung vị: hiệu dụng vx tại 0.1/0.3/0.6 = 1.01/1.00/0.96, lùi 0.1: 0.79; wz tại 0.2/0.6/1.0 =
  1.07/0.98/0.88). Nó **không** học vùng chết (khi bật nhiễu quan sát, vùng chết của policy nhỏ, §4), nên không có thổi phồng lệnh.
- Tốc độ đổi lệnh |Δu|/s p95 (vx, vy, wz), gộp mọi lệnh: Isaac baseline `~t3~nl` 1.39, 0.95, 3.38 vs `~t3` 1.36, 0.93, 3.25; ứng viên 0.96, 0.58, 2.28 vs 0.94, 0.59, 2.20.
  fastsim go2 giống hệt (1.30/0.93/3.28 vs 1.30/0.92/3.17). Các cấu hình khác (go2): mppi 1.00, 0.77, 2.46; ppl=32 1.17, 0.86, 2.88; **dwa 1.08, 1.50, 4.50** (đổi dấu wz 11.7 lần/10 s)
  nhưng dwa gần như không ngã -> **giật lệnh không phải nguyên nhân**. Trong 1.5 s trước khi lật: 22 lần ngã thì chỉ 3 lần có bước nhảy wz > 0.4 hoặc vy > 0.25, và không lần nào có lệnh dừng.
- Không phải tia nghiêng (b), không phải `~nl` (a).

### 11.4 Điều thật sự khác: thời gian ở chế độ lùi/quay chậm
- 1 s trước khi lật (15 lần của nl + t3): phần lớn chậm (|vx| tb 0.08–0.26; 2 lần 0.42–0.48), **lùi** chiếm ≥ 30 % thời gian ở 13/15 lần, |wz| tb 0.1–0.97; ngang + quay mạnh cùng lúc (> 50 % thời gian) ở 6/15.
  w363 ngã ở **5 chạy khác nhau** (cả hai cấu hình, mọi biến thể): đúng tình huống (kẹt giữa người, lùi + xoay tại chỗ lâu), không phải ngẫu nhiên.
- Tỉ lệ thời gian (fastsim go2, cùng thế giới) có **lùi + |wz| > 0.6**: baseline `~t3` 0.095–0.099, ứng viên 0.049–0.055, ppl=32 0.044, mppi 0.030, dwa 0.009.
  Có **ngang + |wz| > 0.6**: 0.23 / 0.13 / 0.14 / 0.10 / 0.09. `~t3` (`wait_p`: chờ người thay vì coi là kẹt) giữ robot lâu hơn trong vùng đông người, xoay/lùi tại chỗ,
  lượt cũng dài hơn (54 s vs 37–40 s) -> **phơi nhiễm** cao hơn.
- Bản đồ ngã khi giữ lệnh (`sysid_isaac.py --test combo`, PhysX CPU, 60 tổ hợp × 8 lần × 4 s): chỉ 1 lần ngã khi đang giữ lệnh (vx −0.2, wz +1.0: 1/8), 4 lần khi
  vừa thả lệnh về 0. Nguy cơ ~1.4e-3/s, ngang mức của `~t3` trong điều hướng (11 ngã / 200 × 51 s ≈ 1.1e-3/s), cao hơn mppi/ppl/dwa (2 / 300 × 39 s ≈ 1.7e-4/s).
  => **Kết luận (có bằng chứng, chưa chắc chắn):** ngã là điểm yếu của policy rough Isaac ở lệnh chậm/lùi/xoay, và `~t3` gặp loại lệnh này nhiều hơn.
  KHÔNG có bằng chứng gì về chó thật (SportClient là bộ điều khiển khác).

### 11.5 Đề xuất sửa: tag opt-in `~cs` (bộ nắn lệnh), KHÔNG phải `~nlc` vì `~nl` không phải nguyên nhân
`isaac_val/cmd_shaper.py` (`CmdShaper`): (1) khi |vy| > 0.15 hoặc vx < −0.05 thì |wz| ≤ 0.6; (2) |Δvy| ≤ 1.5/s, |Δwz| ≤ 2.5/s; lệnh dừng (0, 0, 0) đi qua
nguyên vẹn (phanh không bị chậm). Trong thí nghiệm này nó tác động lên 26–29 % số lệnh (cắt wz) và 9–10 % (giới hạn tốc độ).
- Isaac: ngã 6 → **0**, thành công baseline 73 → 73, ứng viên 87 → 92 (+9/−4, p = 0.27).
- fastsim go2 (không có ngã): baseline 87 → 79, ứng viên 93 → 88: **tốn 5–8 điểm** (chưa có ý nghĩa, n = 100) vì bớt xoay khi né.
- **Hook cần (ALGO sở hữu, qua điều phối viên):** trong `robot_ros.RosRobotTools._navigate*`, ngay trước `self._twist(u0, u1, u2)` (dòng ~1311, sau phanh `free < 0.09`):
  `if "~cs" in self.controller: u = self._shaper(u, now)` với `self._shaper = CmdShaper()` tạo lúc `_make_ctrl`, và thêm `"cs"` vào danh sách tag hợp lệ (dòng ~1024).
  Tôi KHÔNG sửa nav_local/robot_ros; trong isaac_val chỉ bọc `_twist` (`--shaper`) để thử.
- Nên làm tiếp trước khi nhận: quét (WZ_CAP 0.6/0.8, chỉ khi lùi, có/không giới hạn tốc độ) trên DEV để giảm giá ở go2; rồi kiểm cả champ/champ2; VAL do điều phối viên.
  Trên chó thật: thử riêng lùi + xoay chậm có dây an toàn trước (dyn/HUONG_DAN_DO.md), vì đây là chỗ policy học dễ ngã nhất.

Tệp: `isaac_val/res_{nl,nlrep,nlfall,t3,nlnotilt,nlcs}.csv` (+ `*_?of8.jsonl`: lệnh/2 s trước ngã/RespModel), `res_fslog{,2,3}_go2.csv`, `res_fscs_go2.csv`,
`raw_rough_combo.npz`, `fall_stats.py`, `cmd_shaper.py`, `run_fall.sh`, `run_replay.sh`, `run_shaper.sh`.

## 12. Nhánh Isaac TEST (PREREG_TEST §3 + Lệch #3; ủy quyền của điều phối viên 25/11 00:15) — XONG 25/11 12:12
- Bắt đầu 25/11 00:05:30. `sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC`: 19/19 OK lúc bắt đầu; kiểm lại mỗi 15 phút (bộ canh) và lúc kết thúc mỗi lô.
- Thế giới: 600 thế giới có người đầu tiên từ 100000 (100001–100832) = đúng danh sách của mọi ô `results/TEST_*` (5 ô, trùng nhau), trial 0, crowd base.
  Cấu hình đóng băng C1, B1, PGIF*, DRA*; không `~cs`. Thân: rough + `--noise`, server v3 (hàng rào + chỗ theo shard). Ngã = hỏng.
- **Lệch kỹ thuật (cần ghi vào mục 9 của PREREG):** `isaac_sim.py` đã băm có `assert` chỉ cho seed DEV/VAL, nên KHÔNG chạy TEST được. Tôi không sửa tệp băm;
  thêm vỏ mỏng `isaac_val/test_arm.py` (sha256 a1d785d0…) gọi `isaac_sim.main()` với `--seeds 0-0` (qua được assert) và thay hàm chọn thế giới bằng danh sách cố định
  `isaac_val/test_worlds.json` (f8c2268d…). Mọi logic khác là của tệp đã băm. Phần sau khi Gazebo xong dùng `test_arm_rest.py` (giống hệt, đọc `test_worlds_rest.json`).
- Lệch #3: N = 4, nice 19, `taskset -c 10-15`, GPU (không có tiến trình python khác trên GPU). Bộ canh (`isaac_val/run_test_arm.sh`) cứ 15 phút đọc CHỈ trường
  `rtf_med`/`rtf_mean` của 4 lượt Gazebo mới nhất (`isaac_val/gz_rtf.py`); nếu trung vị `rtf_med` < 0.9 **hoặc** trung vị `rtf_mean` < 0.9 (chặt hơn yêu cầu, vì
  `rtf_med` gần như luôn 1.0) thì SIGSTOP server + 4 client theo PID, chỉ tiếp tục khi ≥ 2 lượt Gazebo mới hoàn thành sau lúc dừng có cả hai ≥ 0.9. Mọi lần dừng/tiếp ghi
  `results/ISAAC_TEST/guard.log`. Watchdog RAM < 1 GB giết Isaac.
- Bổ sung Lệch #3: `isaac_val/run_test_switch.sh` đợi Gazebo TEST xong (không còn `run_gz_groups` và cả hai log có GROUPSDONE), dừng lô N = 4, **bỏ các thế giới đang dở**
  (quy tắc đặt trước: chạy lại đủ 4 cấu hình của thế giới đó với N = 8), ghi `split_N.json` (thế giới nào N = 4, N = 8, bỏ dở), rồi chạy phần còn lại với N = 8,
  không ghim, nice 10.
- (Ghi lúc 00:21, trước kết quả) 44 lượt, 0 EXC, không ngắt; RTF Gazebo med 1.00, mean 0.95–0.97 (trước khi bật Isaac 0.968). Tốc độ ~2.9 lượt/phút ở N = 4 -> 2400 lượt cần ~13 giờ
  nếu toàn bộ ở N = 4 (bản ước tính "1,5–3 giờ" ở PREREG §3 là sai: đo được ~4 s mô phỏng/s với 8 robot, không phải mỗi robot). Gazebo còn ~63 nhóm mỗi sim (~14 giờ).
- Phân tích khi xong: `python3 isaac_val/test_stats.py` (viết TRƯỚC khi có kết quả): thành công Wilson, ngã theo cấu hình, McNemar chính xác + Holm 3 (C1 vs B1, PGIF*, DRA*),
  quy tắc EXC §5, tách theo N, Kendall τ và chênh C1 − B1 so với fastsim TEST cùng thế giới. Chưa xem tỉ lệ theo cấu hình (PREREG §5).

### 12.1 Thực hiện (xong 25/11 12:12:31)
- 2400 lượt = 600 thế giới × 4 cấu hình, không trùng; **toàn bộ chạy ở N = 4** (Gazebo TEST chưa xong nên không chuyển sang N = 8; `run_test_switch.sh` tự thoát).
  `split_N.json` không được tạo vì không có chuyển N.
- sha: `SHA256SUMS_ISAAC` 19/19 OK lúc đầu, mỗi 15 phút (49 lần) và lúc cuối; `SHA256SUMS_ISAAC_TEST` (Lệch #4: test_arm.py, test_worlds.json, test_stats.py,
  run_test_*.sh, gz_rtf.py) 6/6 OK trước khi phân tích. `test_stats.py` chạy **y như đã viết, không sửa**. Kết quả thô: `results/ISAAC_TEST/stats.txt`.
- Gazebo: **0 lần tạm dừng Isaac**; trung vị `rtf_mean` của 4 lượt Gazebo mới nhất trong 49 lần kiểm: thấp nhất 0.919, trung vị 0.986 (`rtf_med` luôn ≥ 0.999).
- Quy tắc EXC (§5): 0 EXC ở mọi cấu hình -> không bỏ thế giới nào; n = 600 cặp.

### 12.2 Kết quả (tới đích không va; ngã = hỏng)
| cấu hình | thành công (Wilson 95 %) | ngã | va người | va tĩnh | kẹt / hết giờ |
|---|---|---|---|---|---|
| **C1** `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5` | **531/600 = 88.5 %** [85.7, 90.8] | 8 (1.3 %) | 59 | 2 | 0 |
| B1 `mppi~t3~nl:ppl=100;ppl_len=0.5` | 477/600 = 79.5 % [76.1, 82.5] | **30 (5.0 %)** | 86 | 7 | 0 |
| PGIF* | 470/600 = 78.3 % [74.9, 81.4] | 19 (3.2 %) | 107 | 4 | 0 |
| DRA* | 523/600 = 87.2 % [84.3, 89.6] | 14 (2.3 %) | 61 | 2 | 0 |

**Phép chính (McNemar chính xác 2 phía, Holm trong 3):**
- C1 vs B1: C1 thắng 88, thua 34, **+9.0 điểm**, p = 1.1e-6, **Holm 2.2e-6**.
- C1 vs PGIF*: thắng 90, thua 29, **+10.2 điểm**, p = 1.9e-8, **Holm 5.6e-8**.
- C1 vs DRA*: thắng 48, thua 40, +1.3 điểm, p = 0.46, Holm 0.46 -> **không có ý nghĩa**.

**Tách theo N:** chỉ N = 4 (n = 600), nên không có so sánh N = 4/8.

**So với fastsim TEST trên cùng 600 thế giới:**
| ô fastsim | C1 / B1 / PGIF* / DRA* (%) | Kendall τ với Isaac | C1 − B1: fastsim vs Isaac | C1 từng lượt giống Isaac |
|---|---|---|---|---|
| go2 base | 90.5 / 84.8 / 83.8 / 89.7 | +1.00 | +5.7 vs +9.0 | 86 % |
| go2 helb | 91.2 / 90.0 / 88.8 / 89.8 | +0.67 | +1.2 vs +9.0 | 86 % |
| champ base | 82.3 / 72.7 / 73.8 / 80.0 | +0.67 | +9.7 vs +9.0 | 80 % |
| champ2 base | 82.2 / 70.2 / 73.7 / 78.0 | +0.67 | +12.0 vs +9.0 | 82 % |
| champ2 helb | 84.7 / 79.0 / 80.0 / 80.2 | +0.67 | +5.7 vs +9.0 | 83 % |
Thứ tự C1 > DRA* > {B1, PGIF*} giống nhau ở mọi thân; τ = 0.67 chỉ vì B1/PGIF* đổi chỗ (cách nhau 1–3 điểm). Chênh C1 − B1 trên Isaac (+9.0) nằm trong dải fastsim (+1.2 đến +12.0).

### 12.3 Mô tả thêm (KHÔNG phải phép đăng ký; không dùng để kết luận)
- **Ngã đóng góp lớn vào chênh với B1:** trong 88 cặp C1 thắng B1, B1 ngã ở 24; trong 34 cặp C1 thua, C1 ngã ở 6. Bỏ mọi cặp có ngã ở một bên: C1 vs B1 +64/−28 (n 563),
  vs PGIF* +77/−23 (n 573), vs DRA* +37/−33 (n 578). Như vậy C1 vẫn hơn B1/PGIF* khi bỏ ngã, nhưng một phần lợi thế Isaac của C1 là **ngã ít hơn** (1.3 % vs 5.0 %).
- Ngã là điểm yếu của policy rough Isaac khi lùi/xoay chậm (§11), không phải đặc tính đã đo của SportClient; tỉ lệ ngã KHÔNG chuyển sang chó thật.

### 12.4 Kết luận nhánh Isaac (thăm dò, họ riêng theo PREREG §3)
Trên thân Isaac độc lập, C1 hơn B1 (+9.0 điểm) và PGIF* (+10.2 điểm) có ý nghĩa sau Holm; **không hơn DRA*** (+1.3, p = 0.46). Khớp chiều và thứ tự với
mọi ô fastsim TEST. Giới hạn: tia, người và tracker là mã chung với fastsim (chỉ động học thân là độc lập); policy đi bộ là của Isaac Lab, không phải của Unitree;
chỉ một trial, một N (4); tỉ lệ ngã là của policy học, không phải của chó thật.

> **Coordinator kiểm độc lập (25/11 12:25):** tính lại trực tiếp từ results/ISAAC_TEST/res.csv (2400 dòng, 600 thế giới × 4, không trùng) bằng script riêng, cho kết quả khớp §12:
> - thành công: C1 531/600, B1 477, PGIF* 470, DRA* 523;
> - McNemar chính xác, hiệu chỉnh Holm trên 3 phép so:
>   - C1 vs PGIF*: 90/29 cặp thắng/thua, p_Holm = 5,6e-8;
>   - C1 vs B1: 88/34, p_Holm = 2,2e-6;
>   - C1 vs DRA*: 48/40, p_Holm = 0,46, không có ý nghĩa.
