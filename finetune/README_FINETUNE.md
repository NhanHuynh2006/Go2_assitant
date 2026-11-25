# 🔬 Phần C — Fine-tune model lệnh robot RIÊNG CỦA BẠN (LoRA)

> Mục tiêu: từ Qwen2.5-1.5B "đa dụng" → **GoVoice-1.5B chuyên lệnh robot tiếng Việt**.
> Chạy hết trên **laptop RTX 4060** (~30-60 phút train). Jetson chỉ nhận file GGUF cuối.
> Đây là đóng góp "viết cái mới" của bài báo: *dataset + model + bảng so sánh baseline vs fine-tuned*.

## Quy trình 5 bước

```
[1] gen_dataset.py  →  [2] train_lora.py  →  [3] merge_lora.py  →  [4] export_gguf.sh  →  [5] evaluate.py ×2
     sinh ~4-6k mẫu        QLoRA 4060            gộp adapter           GGUF Q4 cho llama.cpp     baseline vs của bạn
```

## Bước 0 — Môi trường (1 lần)

```bash
cd ~/go2_assistant/finetune
python3 -m venv venv_ft && source venv_ft/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements_finetune.txt
```
> Venv RIÊNG cho train (venv_ft) — đừng trộn với venv chạy assistant.

## Bước 1 — Sinh dataset

```bash
python3 gen_dataset.py
```
Ra `data/train.jsonl` (~4-6k), `val.jsonl` (150), `test.jsonl` (300 — **giữ kín, chỉ để chấm**).
Dataset gồm 7 nhóm: move đơn (kèm mét/giây/độ, số bằng chữ), action, go_to, stop, **combo nhiều bước**, chitchat (actions rỗng), **refuse** (lệnh không làm được → từ chối = hành vi an toàn). Seed cố định → tái lập 100%, ghi thẳng vào mục Dataset của bài báo. Muốn "xịn" hơn nữa: tự thêm ~100-200 câu **người thật nói** (bạn bè đọc lệnh) vào train — paper gọi là human-in-the-loop augmentation.

## Bước 2 — Train LoRA (~30-60 phút RTX 4060)

```bash
python3 train_lora.py
```
- QLoRA: base nạp 4-bit, chỉ train adapter (r=16) → ~5-6GB VRAM, vừa 4060.
- **Điểm thiết kế quan trọng**: prompt huấn luyện *import thẳng* `SYSTEM_PROMPT` từ `llm_planner.py` → train và chạy thật **cùng một phân phối**, không lệch.
- Theo dõi `eval_loss` giảm dần qua epoch là ổn.

## Bước 3 + 4 — Gộp & xuất GGUF

```bash
python3 merge_lora.py
bash export_gguf.sh
```
Ra **`govoice-qwen2.5-1.5b-q4_k_m.gguf`** (~1.1GB) — model của bạn, chạy y chang model gốc trên llama.cpp (laptop lẫn Jetson).

## Bước 5 — Đánh giá ĐỐI CHỨNG (bảng chính của bài báo)

```bash
# Lan 1 — BASELINE (terminal khac chay server voi Qwen GOC):
#   ~/llama.cpp/build/bin/llama-server -m ~/models/qwen2.5-1.5b-instruct-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
python3 evaluate.py --tag baseline

# Lan 2 — MODEL CUA BAN (tat server cu, chay lai voi GGUF moi):
#   ~/llama.cpp/build/bin/llama-server -m $(pwd)/govoice-qwen2.5-1.5b-q4_k_m.gguf -ngl 99 -c 2048 --port 8080
python3 evaluate.py --tag finetuned
```
Mỗi lần in **success-rate theo nhóm** (move/action/go_to/combo/chitchat/refuse) + latency, ghi `eval_baseline.csv` / `eval_finetuned.csv`. Kỳ vọng: baseline đã khá (nhờ grammar), fine-tuned **nhảy vọt ở nhóm combo + refuse** — đó chính là 2 cột "đẹp" nhất trong bảng kết quả.

## Dùng model mới trong GoVoice
Chỉ cần chạy llama-server với GGUF mới (lệnh ở Bước 5 lần 2) — `config.yaml` không phải đổi gì. Trên Jetson: `scp` file `.gguf` xuống rồi chạy server với nó.

## Nâng cấp thêm (tùy chọn, cho "nhanh nhất")
- **Distill xuống 0.5B**: lặp lại đúng pipeline với `BASE_MODEL="Qwen/Qwen2.5-0.5B-Instruct"` → model ~400MB, nhanh gần gấp đôi trên Jetson; nhờ dataset chuyên + grammar, độ chính xác thường vẫn giữ. So 3 cột: baseline-1.5B / tuned-1.5B / tuned-0.5B = bảng ablation đẹp.
- **Tăng độ khó test**: thêm câu nhiễu (STT nghe sai dấu) vào test set để đo độ bền.

## Sự cố thường gặp
| Lỗi | Xử lý |
|---|---|
| CUDA OOM khi train | Giảm `per_device_train_batch_size=2`, tăng `gradient_accumulation_steps=8` |
| bitsandbytes lỗi | `pip install -U bitsandbytes`; cần GPU NVIDIA + driver mới (bạn có) |
| trl/SFTConfig đổi API | `pip install -U trl transformers` (API các bản mới ổn định quanh tham số trong script) |
| convert GGUF lỗi thiếu lib | `pip install gguf sentencepiece protobuf` |
| eval điểm thấp bất thường | Kiểm server đang chạy ĐÚNG model muốn đo (nhìn log llama-server lúc khởi động) |
