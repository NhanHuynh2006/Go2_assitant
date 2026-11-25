# BẢN NHÁP ĐĂNG KÝ TRƯỚC — lượt TEST (fastsim + Gazebo)

Trạng thái: NHÁP của AUDIT, 22/11. Có hiệu lực khi điều phối viên điền các ô `<...>`, ghi sha256 của file này, của code
(nav_local, nav_prism2, robot_ros, fastsim, movers, eval_sim, audit/gen_gazebo_test.py) và của MANIFEST.txt vào
research/LOG.csv, TRƯỚC khi sinh hay chạy bất kỳ seed >= 100000 nào. Sau đó không sửa; mọi lệch ghi vào mục 9.

## 1. Câu hỏi và MỘT phép kiểm định chính
- A* = thuật toán đề xuất, B* = baseline tốt nhất đã chỉnh. Cả hai chốt trên VAL (mục 3).
- **Kiểm định chính duy nhất: McNemar chính xác, hai phía, alpha = 0,05, trên "thành công" (tới đích, sai < 0,35 m, KHÔNG
  chạm bất cứ thứ gì) của A* và B* trong Gazebo, N = 340 thế giới có người chưa từng xem, mỗi thế giới 1 lượt/cấu hình.**
- Báo kèm: hiệu tỉ lệ ghép cặp và KTC 95 % (bootstrap theo thế giới), Wilson từng bên, số cặp b/c.
- Kết luận cho phép: "hơn" chỉ khi p < 0,05 và hiệu > 0. p >= 0,05 ghi "không phát hiện khác biệt" kèm KTC, KHÔNG ghi "ngang nhau".
  Nếu B* hơn A* có ý nghĩa, báo như vậy.
- Mọi phép so khác (fastsim, tổ hợp gợi ý, DWA, theo loại, at_fault, SPL, thời gian) là PHỤ: Holm trong từng họ, ghi rõ "thăm dò".

## 2. Cỡ mẫu (audit/a6_power.py; McNemar chính xác, 2 phía, alpha 0,05)
| tỉ lệ cặp bất đồng d | +10 điểm, 80 % / 90 % | +5 điểm, 80 % / 90 % |
|---|---|---|
| 0,26 (fastsim DEV, TB 171 cặp cấu hình) | 217 / 284 | 851 / 1123 |
| 0,32 | 266 / 348 | 1038 / 1376 |
| 0,40 (giả định Gazebo, thế giới mới) | 331 / 433 | 1292 / 1715 |
| 0,48 (Gazebo cũ đo được 0,45; ghép theo "lần" vô ích: 0,47 khi ghép ngẫu nhiên) | 393 / 518 | 1543 / 2051 |
- fastsim TEST: N = 850 thế giới có người -> 80 % cho +5 điểm (d = 0,26). Gazebo: N = 340 -> 80 % cho +10 điểm (d = 0,40).
- **+5 điểm trong Gazebo không khả thi** (~1300 cặp = 2600 lượt = 34 giờ): không hứa.
- DEV n = 101 chỉ có ~40 % sức mạnh cho +10 và 11 % cho +5; VAL n ≈ 285 có 88 % và 32 %.

## 3. Chốt cấu hình TRÊN VAL (fastsim seed 2000–2399, có người, ~285 thế giới; điều phối viên chạy 1 lần)
1. B*: cấu hình tỉ lệ cao nhất trong các baseline đã chỉnh {mppi, dwa, log_mppi: mỗi loại 1 bản tốt nhất DEV}. Số lần thử chỉnh
   của baseline >= của đề xuất (đếm trong LOG.csv). B* dùng CÙNG K, cùng mô hình động học, cùng nguồn người như A*.
2. Nền đề xuất P: <p2+turn hoặc bản ALGO đưa ra; đúng 1 cấu hình, đã ghi LOG>.
3. **Gợi ý RL — phải chạy ĐỦ 5 bản trên cùng nền P, không bỏ bản nào, ở DEV/VAL/TEST:**
   `P` (không gợi ý), `P@ppo`, `P@ppo+sac`, `P@ppo+td3`, `P@ppo+td3+sac`.
   (Danh sách cũ chỉ giữ ppo+sac là vô căn cứ: ppo+sac và ppo+td3 bằng nhau ở mọi bảng, văn phòng 28/40 = 28/40, nhà 51/51 = 51/51.)
   Quy tắc chọn, áp dụng máy móc trên VAL:
   a. 4 phép McNemar chính xác, mỗi tổ hợp so với không gợi ý, Holm trên 4.
   b. Không tổ hợp nào p_Holm < 0,05 (và hiệu > 0) -> **A* = P, BỎ gợi ý RL** khỏi thuật toán chính (bốn bản kia vẫn vào bảng ablation).
   c. Có tổ hợp đạt -> trong số đạt, giữ những bản KHÔNG kém bản cao nhất có ý nghĩa (McNemar p >= 0,05), rồi lấy
      **bản đơn giản nhất = ít policy nhất**. Hơn 1–2 lượt không phải lý do.
   d. Vẫn hoà (vd ppo+sac và ppo+td3 đều đạt): lấy bản ít ms/bước hơn nếu chênh > 10 %; nếu không,
      `random.Random(20261122).choice(["ppo+sac", "ppo+td3"])`, chạy công khai, ghi LOG. Không lấy theo tỉ lệ.
   Bẫy cú pháp: cờ phải đứng TRƯỚC `@` (`p2+turn@ppo+sac`; `p2@ppo+sac+turn` văng KeyError; cờ gõ sai bị bỏ qua im lặng).
4. A* và B* ghi tại đây: A* = `<...>`, B* = `<...>`, sha256 code = `<...>`.

## 4. Bộ TEST và cấu hình
- Thế giới: `audit/gen_gazebo_test.py --seeds 100000-100999 --crowd-only --max-worlds 340 --allow-test` (họ = seed % 5). fastsim dùng
  850 seed có người ĐẦU TIÊN từ 100000; Gazebo dùng 340 seed có người đầu tiên (trùng phần đầu -> đo được độ khớp theo thế giới).
- Mỗi (thế giới, cấu hình) 1 lượt. KHÔNG lặp cùng seed đám đông: 5 "lần lặp" cũ là giả lặp (người đi trùng nhau vài cm suốt 10–45 s).

| | fastsim (850 thế giới) | Gazebo | vai trò |
|---|---|---|---|
| A*, B* | 850 | 340 | CHÍNH (Gazebo), phụ (fastsim) |
| 5 bản gợi ý trên nền P (A* là 1 trong 5) | 850 | 120 thế giới đầu, đủ cả 5 | phụ, thăm dò (Gazebo n = 120: không đủ sức cho +10) |
| mppi mặc định, dwa đã chỉnh | 850 | 120 thế giới đầu | phụ |

- Khối lượng: fastsim 8 cấu hình x 850 = 6800 lượt ≈ 2–3 giờ với 12 tiến trình. Gazebo 680 + 480 + 240 = 1400 lượt ≈ 18,5 giờ
  với 76 lượt/giờ, cộng ~85 lần nạp thế giới (4 ô/file). Nếu chỉ có 1 đêm: chạy 680 lượt CHÍNH trước, đó là phần bắt buộc.
- Phụ, tách riêng: 60 thế giới KHÔNG người (A*, B*) để báo lỗi tĩnh; Gazebo cũ có 12 % hỏng ở bài tĩnh, fastsim thì 0–2 %.

## 5. Điều kiện chạy Gazebo
- Trước mỗi lượt đặt lại: ev/seen_t của hai lưới, `_ctrl=None`, `vel_gain=.5`, `vel_gains=[.5]*3`, `tracker.tracks=[]`,
  `configure_world(*bounds)`. (Hiện `reset()` KHÔNG đặt lại vel_gain, vel_gains, tracker: mang từ cấu hình trước sang.)
- Thứ tự cấu hình trong mỗi thế giới xáo bằng `random.Random(seed)`; mọi cấu hình của một thế giới chạy trên CÙNG một sim.
- Monitor phải ghi: vị trí MỌI người 10 Hz, thời điểm chạm ĐẦU TIÊN, loại vật (người/xe/tĩnh). Hiện chỉ ghi người số 0 và lúc chạm SÂU nhất.

## 6. at_fault (phụ)
Định nghĩa D1 (audit/a9_fault_def.py): trung bình 0,5 s TRƯỚC lần chạm đầu, quỹ đạo làm mượt 0,5 s, vận tốc của ĐIỂM THÂN gần người nhất
(gồm cả xoay) theo phương tới người > 0,1 m/s -> robot có lỗi. Báo thêm D2 (robot đứng yên từ 1 s trước thì có bị chạm không).
Không dùng |wz| tức thời. Chỉ số chính KHÔNG phụ thuộc at_fault.

## 7. Quy tắc dừng, lượt hỏng
- Cỡ mẫu cố định; KHÔNG xem kết quả theo cấu hình trước khi đủ 340 cặp. Không kéo dài khi p gần 0,05, không dừng sớm khi p đẹp.
- Kiểm hạ tầng sau 20 thế giới đầu: chỉ xem số lỗi kỹ thuật và tổng số lượt/giờ, không xem tỉ lệ theo cấu hình.
- Lỗi kỹ thuật (EXC, mất odom/LiDAR > 2 s, RTF < 0,9, sim sập) xác định bằng log, không bằng kết quả -> chạy lại tối đa 2 lần; vẫn hỏng thì bỏ
  CẢ thế giới cho mọi cấu hình và lấy seed có người kế tiếp. "Kẹt", "hết giờ", chạm = thất bại, không chạy lại.
- Hết thời gian trước 340 cặp: kiểm định trên số cặp đã có, ghi N thật và sức mạnh thật.

## 8. Phân tích
Một script duy nhất, viết và chạy thử trên DEV trước, băm sha256. Thứ tự bảng: CHÍNH -> Holm các họ phụ -> theo loại bản đồ -> loại hỏng
(người/tĩnh/kẹt/hết giờ) -> D1/D2. Báo tổng số cấu hình đã thử (LOG.csv).

## 8b. Kiểm chứng độ vững (phụ, đăng ký trước, fastsim; không thay kiểm định chính)
- HAI CHẾ ĐỘ: A*, B* chạy ở `--regime champ` và `--regime go2` trên cùng 850 thế giới. Ở go2 kiểm KHÔNG KÉM HƠN: cận dưới KTC 95 % (2 phía)
  của hiệu ghép cặp > -5 điểm. n = 850, d = 0,26: 1 sd của hiệu ≈ 1,7 điểm nên đủ sức khi hiệu thật >= 0.
- HAI MÔ HÌNH NGƯỜI: movers.py hiện tại và Moussaïd 2009 (audit/fs_audit.py pm_step), đổi trên VAL. Nếu dấu của hiệu A* - B* đổi,
  bài phải viết kết luận "phụ thuộc mô hình người". Không chọn A* theo mô hình người nào có lợi.
- Mỗi thư mục kết quả phải có file ghi `--regime`, `--oracle`, seed, sha256 code (hiện không ghi: results/ceil1 chạy --oracle mà nhìn y hệt dev3).

## 9. Lệch so với đăng ký
(để trống)
