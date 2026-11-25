# GIAO THỨC NGHIÊN CỨU TỰ ĐỘNG — GoVoice né vật cản (đọc HẾT trước khi làm gì)

Mục tiêu: một thuật toán né vật cản/người cho Go2 (lệnh vận tốc 10 Hz) có tính mới THẬT và hơn baseline
ĐÃ CHỈNH CÔNG BẰNG, đủ để viết 1 bài tạp chí. Kết luận âm (không hơn) cũng là kết quả hợp lệ, phải báo.

## Bối cảnh bắt buộc đọc
RESEARCH_NOTES.md mục 7 (đặc biệt 7.9, 7.10: các lỗi đã mắc), SOTA_REVIEW.md, nav_local.py, nav_prism2.py,
robot_ros.py::_navigate_mpc, fastsim.py, fs_stats.py, fs_lead.py.

## Sự thật đã đo (22/11)
- 960 + 561 lượt Gazebo: PRISM cũ KHÔNG hơn mppi/dwa ở văn phòng (28/40 vs 26, 27); nhà nhỏ 51/51 vs 47/51
  (nhưng các bài này đã dùng để phát triển). Chọn gợi ý RL ppo+sac hay ppo+td3: bằng nhau.
- Động học CHAMP đo được (results/sysid.npz): vx bão hoà ~0.29 m/s, lùi 1.26, vy 0.97, wz 0.85; thân lắc mạnh.
  MPPI đang dùng mô hình tuyến tính 1 hệ số/trục -> sai.
- fastsim (đồng hồ ảo, chạy code thật) tương quan hạng với Gazebo 0.89 trên 12 cấu hình, chủ yếu nhờ tách
  RL/pp; TRONG nhóm MPPI chưa kiểm được.
- Bản đồ sinh: vật tĩnh 100 % ở mọi bộ. Toàn bộ khó khăn là NGƯỜI (~50-65 %). 2 s trước khi chạm chỉ 21-48 %
  người đang hướng vào robot: người RẼ muộn, robot vẫn đi hết tốc độ. Tracker thấy người 66 % ở -2 s, 80 % ở -1.5 s.
- DEV crowd-only n=101 (seed 0-149): mppi 53 %, mppi:ppl=32 63 %, mppi:ppl=16;ppl_len=0.6 62 %,
  p2+turn 65 %. => so với baseline CHỈNH, chưa có lợi thế. Nhiễu ±9 điểm.

## Chống tự lừa mình (vi phạm = kết quả vứt)
1. DEV: fastsim seed 0-999. VAL: seed 2000-2399 (chỉ để chọn ứng viên cuối, điều phối viên chạy).
   TEST: seed >= 100000 và mọi bản đồ Gazebo mới: CẤM CHẠY, CẤM XEM. Chỉ điều phối viên chạy, đúng 1 lần.
2. Mọi cấu hình đã thử (kể cả hỏng) ghi 1 dòng vào research/LOG.csv:
   thoi_gian,agent,config,suite/seed,n,success,ghi_chu. Số phép thử dùng để hiệu chỉnh Holm.
3. Baseline được chỉnh với số lần thử >= thuật toán mới, cùng cảm biến, cùng K, cùng mô hình.
4. Báo cáo: n, Wilson 95 %, McNemar ghép cặp. Không nói "hơn hẳn/chắc chắn" khi p > 0.05 sau Holm.
   Va do robot = va vật tĩnh + chạm người at_fault=1; nhớ |wz|>0.3 bị lắc thân làm nhiễu.
5. Không đổi bài toán cho dễ (giảm người, nới ngưỡng) để số đẹp. Muốn đổi mô phỏng phải có số đo thật làm lý do.
6. Không bịa trích dẫn: mỗi bài báo phải mở được link, ghi rõ đã đọc toàn văn hay chỉ tóm tắt.

## Tài nguyên: 16 luồng, RTX 4060 8 GB, 14 GB RAM
ALGO: fastsim --jobs tối đa 8. MODEL: GPU + tối đa 3 luồng. AUDIT: fastsim --jobs tối đa 3. LIT: không chạy sim.
Luôn đặt OPENBLAS_NUM_THREADS=1. Không bật Gazebo (điều phối viên giữ). Không cài gói hệ thống.

## Quyền sở hữu file (không sửa file của nhau)
ALGO: nav_local.py, nav_prism2.py, robot_ros.py (giữ tương thích ngược: hậu tố ~v1 và tên cấu hình cũ).
MODEL: rl_nav/*, file mới nav_pred.py. AUDIT: file mới trong audit/. LIT: research/LIT.md.
fastsim.py: chỉ điều phối viên; cần sửa thì nêu trong báo cáo.

## An toàn
CẤM động tới robot thật (SDK, SSH, LowCmd, 192.168.123.x). Cấm push/đăng gì ra ngoài; không đưa tên/email người
dùng vào truy vấn web. Không pkill theo mẫu (dễ tự giết shell); dừng bằng PID. Không xoá results/ của người khác.

## Cách báo cáo
Ghi research/REPORT_<ten>.md (làm gì, số, kết luận, điều CHƯA chắc, đề xuất tiếp theo) rồi trả lời tóm tắt
dưới 400 từ: điều đã KIỂM CHỨNG, điều suy đoán, và đề xuất.

## Bổ sung (người dùng chỉ ra, 22/11): không thiên vị tổ hợp gợi ý RL
Danh sách ứng viên cũ chỉ giữ ppo+sac là VÔ CĂN CỨ: ppo+sac và ppo+td3 bằng nhau (28/40 = 28/40, va do robot 7 = 7,
nhà 51/51 = 51/51). Mọi bảng DEV/VAL/TEST có gợi ý RL phải chạy ĐỦ: không gợi ý, ppo, ppo+sac, ppo+td3, ppo+td3+sac,
trên cùng thuật toán nền. Nếu không tổ hợp nào hơn "không gợi ý" có ý nghĩa thì BỎ gợi ý RL khỏi thuật toán chính
(giữ làm ablation trong bài). Chọn giữa các tổ hợp bằng nhau: lấy bản đơn giản nhất, không lấy bản có số cao hơn 1-2 lượt.

## Bổ sung 2 (22/11 23:30): thêm DYN, ISAAC, OSS (người dùng yêu cầu trực tiếp)
- DYN sở hữu dyn/ và research/REPORT_DYN.md; chỉ CPU, tối đa 2 luồng. ISAAC sở hữu ~/isaac và isaac_val/ (được phép
  pip/uv vào môi trường RIÊNG trong ~/isaac; không sudo, không apt, không đổi driver). ISAAC KHÔNG dùng GPU nặng khi
  MODEL còn train (kiểm `nvidia-smi`; chờ). OSS sở hữu oss/ (git clone chỉ ĐỌC; không chạy script/cài của repo lạ).
- Bản ghi chó thật: ~/go2_maps/*/*.db3 (chỉ đọc, đừng sửa). Không kết nối tới chó.
- Động học: mọi con số phải ghi NGUỒN (đo từ bản ghi của mình / bài báo có link / mã nguồn có link) và độ bất định.
  Số của người khác chỉ là tham khảo để so, không thay số đo. Phải nói rõ phần nào CHƯA biết và cần đo thêm ngoài đời.

## Bổ sung 3 (23/11): HAI CHẾ ĐỘ ĐỘNG HỌC
fastsim --regime champ (dáng CHAMP trong Gazebo, bão hoà 0.29 m/s) và --regime go2 (dải đo/tài liệu của DYN, dyn/go2_params.yaml,
lấy mẫu mỗi lượt; chó thật đi gần đúng lệnh ~0.95 nên nhanh khoảng gấp đôi CHAMP). Mọi kết luận về thuật toán phải báo Ở CẢ HAI chế độ.
Vì triển khai là chó thật: ứng viên phải KHÔNG kém baseline ở regime go2. Gain/tau/trễ của go2 là tài liệu/giả định (bản ghi thật không
có lệnh) cho tới khi người dùng đo theo dyn/HUONG_DAN_DO.md. Chú thích "theo Moussaïd 2009" trong movers.py là SAI: đừng trích trong bài.

## Bổ sung 4 (23/11): mô hình người và chỉ số chính
- Chỉ số chính: tới đích KHÔNG va chạm (mọi va). at_fault chỉ phụ (AUDIT: |wz|>0.3 ở 63 % mẫu).
- fastsim --crowd-model base|helb|mous. Ứng viên phải không đổi dấu so với mppi:ppl=32 ở cả base và helb (mous chưa đối chiếu PDF gốc).
- Mỗi thư mục kết quả có meta.json; không trộn chế độ trong một thư mục. Phép thử của AUDIT nằm ở audit/LOG_AUDIT_rows.csv (49 dòng), tính CẢ hai file khi đếm phép thử.

## Bổ sung 5 (23/11): SEV bị bác bỏ
Agent SEV: giá trị né ngẫu nhiên (V) không phân biệt sẽ-chạm/không-chạm tốt hơn khoảng hở nhỏ nhất với vận tốc không đổi (dce):
ΔAUC −0.020 [−0.048, +0.007] (−2 s), +0.004 (−1.5 s). turn_cost ≈ turn_const. Không theo tiếp SEV/turn_cost làm đóng góp chính.
Người thật (THÖR, CC BY 4.0) rẽ ít hơn mô phỏng ~1.7 lần: ghi vào hạn chế. Đừng in câu "robot 0.29 m/s luôn bị bắt".

## Bổ sung 6 (23/11): giấy phép phần mềm
Người dùng cho phép chấp nhận mọi giấy phép/EULA của phần mềm dùng trong dự án **mà không cần hỏi trước**. Bắt buộc: ghi tên giấy phép
+ điều khoản quan trọng (phi thương mại, GPL, cấm phân phối lại…) vào REPORT của mình, để đưa vào phần hạn chế/tái lập của bài.
Các giới hạn khác KHÔNG đổi: không chạm chó thật, không tiêu tiền, không sudo/driver, không đẩy/công bố ra ngoài, không chạy TEST trước khi khoá thiết kế.
Cập nhật 23/11: người dùng cho phép sudo và đẩy/công bố. **Chỉ coordinator** làm hai việc này (agent cần thì ghi đề nghị trong REPORT/tin nhắn,
nêu lệnh + lý do); agent không tự sudo, không push. Vẫn cấm: chạm chó thật, tiêu tiền, chạy TEST trước khi khoá thiết kế.
Cập nhật 23/11 21:00: người dùng cho phép agent tự ghi/sửa file trong ~/Documents/Go2_assitant (đã thêm quyền trong .claude/settings.local.json). Agent tự ghi REPORT và LOG của mình; vẫn không sửa file của agent khác.
