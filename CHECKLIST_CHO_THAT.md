# CHECKLIST NGÀY CHẠY CHÓ THẬT (1 trang, in ra mang theo)

Chi tiết: lệnh ở `deploy/DEPLOY.md`, quy tắc ở `audit/REAL_PREREG.md`, đo động học ở `dyn/HUONG_DAN_DO.md`.
Khoảng 2 buổi: buổi A gồm bước 1–9 và S1–S2; buổi B gồm S3–S5.

## Mang theo
- Go2 + **2 pin sạc đầy** + sạc. Remote sạc đầy, **thử L2+B trước**.
- OS1 + **nguồn riêng** (không cấp từ Go2: Orin sẽ treo). D435i nếu dùng.
- Laptop đã tắt Wi-Fi tiết kiệm điện. Không source ROS trên laptop khi SSH vào chó.
- 8 thùng carton 50 cm, băng dính màu, phấn, thước dây 10 m.
- 2 điện thoại + 2 chân máy, bảng nhỏ + bút (ghi số lượt), bộ sơ cứu, giấy đồng ý cho người tham gia.
- Người:
  - R: cầm remote. Chỉ làm việc này, mắt luôn nhìn chó.
  - O: chạy laptop.
  - P1, P2: đi bộ.
  - (tuỳ) V: quay video.
  - Tối thiểu 3 người; S4 cần 4.

## An toàn (đọc to cho mọi người trước khi bắt đầu)
- L2+B = phanh cứng (chó nằm xuống). Gạt cần remote = giành quyền ngay; lượt đó tính thất bại, **không sao cả**.
- R giành quyền khi:
  - chó sắp chạm người (< 0,3 m và đang tiến lại);
  - chó sắp chạm vật ở tốc độ nhanh;
  - chó ra ngoài sân;
  - chó sắp ngã.
- Người đi bộ: đi đúng vạch, tốc độ thường. **Thấy không an toàn thì cứ dừng hoặc tránh.** Giày kín.
- Dừng cả buổi khi:
  - chạm người;
  - chó ngã;
  - Orin treo hoặc mất cảm biến lặp lại;
  - pin < 30 %, động cơ > 70 °C;
  - sàn ướt;
  - có người lạ vào sân;
  - có ai muốn dừng.

## Thứ tự (thời gian ước tính)
| # | việc | lệnh / ghi chú | phút |
|---|---|---|---|
| 1 | Bày sân: ô 7 × 7 m trống (đo động học) + đường chạy 10 × 3,6 m. Dán vạch x = 0; 1; 1,5; 3,5; 4; 6 | theo REAL_PREREG §2 | 30 |
| 2 | Bật chó (đứng), Orin, OS1 bằng nguồn riêng. SSH vào | `ssh -i ~/.ssh/go2_key unitree@<ip>` | 10 |
| 3 | Chép gói + **kiểm hash + bench CPU** (chó đứng yên) | `bash deploy/verify_on_dog.sh --fast-so` → ĐẠT? Ghi C1/B1 p95 | 15 |
| 4 | **Ghi 10 phút có người** (chó đứng yên, bridge chỉ đọc): 2' sân tĩnh có 3 thùng S1; 3' P1 cắt ngang ở 2, 3, 4 m (mỗi khoảng 3 lần) rồi đối đầu 3 lần, dừng ở 1,5 m 5 s; 2' P1 + P2 cùng lúc; 2' R lái remote chậm qua đường S1 khi P1 cắt ngang; 1' R cho chó xoay tại chỗ | `READONLY=1 bash deploy/start_stack.sh`, rồi `ros2 bag record -o ~/realprep/people10 /go2/lidar/merged /go2/lidar/points /go2/odom /go2/imu/data /go2/status`. Quay video cùng lúc | 15 |
| 5 | Phát lại bản ghi trên chó: tracker có thấy người thật không, độ trễ, tỉ lệ ma, CPU mỗi lần quét **trên Orin** | `python3 deploy/replay_perception.py ~/realprep/people10/*.db3 --tum odom --min-period 0 --out ~/realprep/replay10` | 10 |
| 6 | **Đo động học** (bridge vẫn chỉ đọc; không người trong ô 7 × 7). Các bước A–F theo `dyn/HUONG_DAN_DO.md` §2. Nghỉ ≥ 2' giữa các giai đoạn. Bước G (nền khác) để buổi khác | `python3 ~/govoice_real/dyn/sysid_real.py --check …` rồi `--go --stage 1 …` | 40 |
| 7 | Tắt bridge chỉ đọc; bật bridge **kẹp 0,2** | `bash deploy/start_stack.sh stop; VX=0.20 VY=0.15 WZ=0.40 MERGED=1 DEPTH=0 bash deploy/start_stack.sh` | 5 |
| 8 | **Chạy thử** 2 cặp S1 + 2 cặp S2 (P1 đi chậm). Thử 1 lần R gạt cần, xem runner ghi "remote". Xem log không có "loi xu ly LiDAR" | `--make-schedule --pairs 2 --scenarios S1,S2 --seed 1 --out ~/realprep/shakedown`, rồi `--run … --cs --no-depth` | 25 |
| 9 | **Khoá đăng ký trước**: điền REAL_PREREG §9 (hash gói, verify, bench, quyết định cloud/depth/fast.so). Đổi sang kẹp 0,30/0,15/0,50: `bash deploy/start_stack.sh stop; VX=0.30 VY=0.15 WZ=0.50 MERGED=1 DEPTH=0 bash deploy/start_stack.sh` | `cp audit/REAL_SCHEDULE.csv ~/realprep/main/schedule.csv; sha256sum …` = cea711d1… | 10 |
| 10 | **S1** vật tĩnh, 40 lượt | `python3 deploy/real_trial.py --run --out ~/realprep/main --cloud /go2/lidar/merged --cs --no-depth` | 60 |
| 11 | Nghỉ, sạc hoặc đổi pin, chép bag ra laptop | `rsync -a unitree@<ip>:realprep/ ~/realprep_backup/` | 20 |
| 12 | **S2** 1 người cắt ngang, 40 lượt (P1) | runner tự tiếp từ lượt chưa xong | 70 |
| 13 | **S3** 1 người đối đầu, 40 lượt (P2). Đổi pin giữa chừng nếu < 35 % | | 70 |
| 14 | **S4** 2 người, 40 lượt (P1 + P2) | | 75 |
| 15 | **S5** túi hẹp, lùi + xoay, 40 lượt (không người; R đứng gần) | bày túi thùng §2 | 60 |
| 16 | Dọn: dừng hệ thống, chép **toàn bộ** `~/realprep` về laptop, ghi LOG | `bash deploy/start_stack.sh stop` | 20 |

Mỗi lượt có 4 nhịp:
1. Đặt chó ở vạch, đúng hướng. Giơ bảng số lượt trước camera.
2. Enter.
3. Người đi bộ xuất phát khi chân trước của chó qua vạch kích hoạt.
4. Chó dừng thì trả lời 3 câu: chạm người? chạm vật? lỗi hạ tầng?

Khoảng 1,5–2 phút một lượt. **Không mở `schedule.csv`** trong buổi: cả đội không biết lượt nào là C1 hay B1.

## Nếu có sự cố
| sự cố | làm gì |
|---|---|
| runner treo | cửa sổ SSH thứ 2: `bash deploy/estop.sh`, rồi `--bridge` nếu cần |
| SSH rớt | chó tự dừng (SIGHUP → bridge StopMove). Lượt đó trả lời "lỗi hạ tầng = i" |
| "CHUA DAT: …" trước lượt | sửa theo dòng in ra (pin, LiDAR, remote đang bị gạt), rồi `r` để kiểm lại |
| chạm người hoặc chó ngã | runner tự dừng phiên. Xem video, theo REAL_PREREG §8 trước khi tiếp tục |
