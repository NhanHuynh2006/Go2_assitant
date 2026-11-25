#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_lora.py — Gop adapter LoRA vao base model -> model HOAN CHINH (HF format).
Chay sau train_lora.py:
  python3 merge_lora.py --base 1.5b     # hoac --base 0.5b
Ket qua: merged_<base>/  (san sang convert GGUF bang export_gguf.sh)
"""

import argparse

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASES = {"1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
         "0.5b": "Qwen/Qwen2.5-0.5B-Instruct"}

ap = argparse.ArgumentParser()
ap.add_argument("--base", choices=list(BASES.keys()), default="1.5b")
ap.add_argument("--suffix", default="", help="'_v2' cho adapter train tren data_v2")
a = ap.parse_args()

base_model = BASES[a.base]
adapter = f"lora_out_{a.base}{a.suffix}"
out = f"merged_{a.base}{a.suffix}"

print(f"Nap base {base_model} (fp16)...")
model = AutoModelForCausalLM.from_pretrained(
    base_model, torch_dtype=torch.float16, device_map="cpu")
print(f"Gop LoRA tu {adapter}/ ...")
model = PeftModel.from_pretrained(model, adapter)
model = model.merge_and_unload()
model.save_pretrained(out)
AutoTokenizer.from_pretrained(base_model).save_pretrained(out)
print(f"XONG -> {out}/")
print(f"Tiep theo: bash export_gguf.sh {out} govoice-qwen2.5-{a.base}")
