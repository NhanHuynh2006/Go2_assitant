# ⚡ GoVoice REALTIME — async + hành động thật + safety

> Bản nâng cấp theo nghiên cứu SOTA (SmolVLA, arxiv 2506.01844): **async inference** —
> robot VỪA làm VỪA nghe lệnh kế, kèm lớp an toàn đầy đủ.

## 2 FILE CHẠY (chọn đúng file)

### 🔒 File 1 — CHỈ GIAO TIẾP, robot KHÔNG nhúc nhích
```bash
python3 run_demo_noaction.py            # gõ phím
python3 run_demo_noaction.py --voice    # nói qua mic
python3 run_demo_noaction.py --voice --mic-robot   # mic ROBOT (chạy go2_audio_bridge.py trước)
```
Robot bị **ép chế độ giả** — mọi "hành động" chỉ in `[DRY]` ra màn hình. An toàn tuyệt đối để test nghe-nói. Đây là file bạn chạy TRƯỚC.

### 🐕 File 2 — CHẠY THẬT, robot HÀNH ĐỘNG (chỉ trên Jetson)
```bash
export CYCLONEDDS_HOME=~/cyclonedds_ws/install/cyclonedds
python3 run_real_robot.py               # gõ phím (test tay trước)
python3 run_real_robot.py --voice       # nói qua mic máy
python3 run_real_robot.py --voice --mic-robot   # nói qua mic ROBOT
```
Có **checklist xác nhận an toàn** trước khi chạy (gõ 'co' để tiếp tục). Robot điều khiển thật.

---

## 3 lớp công nghệ mới (so với bản assistant_main.py)

**1. Async executor (`async_executor.py`)** — hành động chạy ở thread riêng qua hàng đợi. Vòng chính vừa cho robot làm vừa nghe + STT + nghĩ câu kế → giảm ~30% thời gian chuỗi lệnh (kỹ thuật SmolVLA). Emergency chèn ngang bất kỳ lúc nào.

**2. Safety guard (`safety_guard.py`)** — kiểm duyệt MỌI lệnh trước khi tới chân robot:
- Clamp vận tốc/thời gian về giới hạn an toàn (LLM xuất vx=5.0 → kẹp về 0.6)
- Chặn động tác nguy hiểm (handstand, backflip...) dù model có sinh ra
- Tự chèn "đứng dậy" nếu robot đang nằm mà được lệnh đi
- Emergency có ưu tiên tuyệt đối

**3. Emergency ưu tiên tuyệt đối** — nói "dừng lại" / "stop" / "khẩn cấp" bất kỳ lúc nào → xóa sạch hàng đợi + dừng robot NGAY, kể cả đang giữa chuỗi lệnh.

---

## LỘ TRÌNH TEST AN TOÀN (làm đúng thứ tự)

1. **Laptop:** `run_demo_noaction.py --voice` — test nghe-nói, xem logic đúng không
2. **Jetson, gõ phím:** `run_real_robot.py` — gõ "đứng lên" → "đi thẳng" → "dừng lại", đứng sát cầm remote
3. **Jetson, giọng nói:** `run_real_robot.py --voice` — khi đã tin tay
4. **Mic robot:** thêm `--mic-robot` khi muốn dùng mic của chó

⚠️ Luôn: tắt app Unitree, cầm remote (L2+B phanh cứng), chỗ trống ≥2×2m, pin ≥50%.
