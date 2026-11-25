#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_lora.py — QLoRA fine-tune Qwen2.5-1.5B-Instruct thanh MODEL LENH ROBOT cua ban.

Vua khit RTX 4060 8GB nho: nap base 4-bit (QLoRA) + chi train adapter LoRA (~vai chuc MB).
QUAN TRONG: prompt huan luyen DUNG Y HET system prompt luc chay that
(import tu llm_planner.py) -> train sao, chay vay, khong lech phan phoi.

Chay:
  python3 gen_dataset.py            # tao data truoc
  python3 train_lora.py             # ~30-60 phut tren RTX 4060
Ket qua: lora_out/ (adapter)
"""

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_planner import SYSTEM_PROMPT  # noqa: E402  (dung chung prompt!)

# Model co the chon khi chay: --base 1.5b (mac dinh) hoac --base 0.5b
BASES = {"1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
         "0.5b": "Qwen/Qwen2.5-0.5B-Instruct"}
DATA_DIR = "data"
MAX_LEN = 768
EPOCHS = 3
LR = 1e-4


def to_chatml(user, output_json):
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n"
        f"{json.dumps(output_json, ensure_ascii=False)}<|im_end|>\n"
    )


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append({"text": to_chatml(r["user"], r["output"])})
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=list(BASES.keys()), default="1.5b",
                    help="kich co model: 1.5b (chinh xac hon) | 0.5b (nhanh ~2x tren Jetson)")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--data-dir", default=DATA_DIR,
                    help="data (goc) | data_v2 (them do vat+mau, quan he khong gian, "
                         "phong moi — gen_dataset_ext.py)")
    cli = ap.parse_args()
    BASE_MODEL = BASES[cli.base]
    OUT_DIR = f"lora_out_{cli.base}" + ("" if cli.data_dir == DATA_DIR else "_v2")
    print(f"[train] base={BASE_MODEL} -> adapter: {OUT_DIR}/")

    import torch
    from datasets import Dataset
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    train_rows = load_jsonl(os.path.join(cli.data_dir, "train.jsonl"))
    val_rows = load_jsonl(os.path.join(cli.data_dir, "val.jsonl"))
    print(f"train={len(train_rows)}  val={len(val_rows)}")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, quantization_config=bnb, device_map="auto")
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"])

    args = SFTConfig(
        output_dir=OUT_DIR,
        num_train_epochs=cli.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,    # eval tung mau mot — chong OOM (mac dinh 8 la no VRAM)
        eval_accumulation_steps=8,       # don ket qua eval ve CPU theo tung cum nho
        gradient_accumulation_steps=8,
        learning_rate=LR,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=20,
        eval_strategy="epoch",
        save_strategy="epoch",
        bf16=True,
        max_length=MAX_LEN,
        dataset_text_field="text",
        report_to="none",
        # chi tinh loss tren phan ASSISTANT (sau template nay):
        completion_only_loss=False,
        gradient_checkpointing=True,     # Đánh đổi tí thời gian để xả 30% VRAM
        optim="paged_adamw_8bit",
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tok,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(val_rows),
        peft_config=lora,
        args=args,
    )
    trainer.train()
    trainer.save_model(OUT_DIR)
    print(f"\nXONG! Adapter LoRA o: {OUT_DIR}/")
    print(f"Buoc tiep: python3 merge_lora.py --base {cli.base}  ->  bash export_gguf.sh merged_{cli.base} govoice-qwen2.5-{cli.base}")


if __name__ == "__main__":
    main()
