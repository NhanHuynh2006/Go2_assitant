#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_planner.py — TANG 2 "SUY NGHI" cua GoVoice: LLM local (llama.cpp).

Toi uu toc do (cac diem ghi vao bao):
  1. Grammar GBNF        — EP output la JSON dung schema -> khong loi parse,
                           output ngan -> it token -> nhanh.
  2. cache_prompt=True   — llama-server giu KV-cache cua system prompt,
                           moi cau chi decode phan moi -> giam dang ke latency.
  3. Few-shot 1 vi du    — prompt ngan nhat co the ma van chinh xac.
  4. temperature=0.2     — on dinh, it "sang tao bay".
"""

import json
import time
import requests

SYSTEM_PROMPT = (
    "B\u1ea1n l\u00e0 b\u1ed9 n\u00e3o robot ch\u00f3 Unitree Go2 t\u00ean l\u00e0 G\u00f4. "
    "Ch\u1ee7 ra l\u1ec7nh b\u1eb1ng ti\u1ebfng Vi\u1ec7t, b\u1ea1n tr\u1ea3 v\u1ec1 DUY NH\u1ea4T m\u1ed9t JSON:\n"
    '{"say": "<c\u00e2u \u0111\u00e1p ng\u1eafn ti\u1ebfng Vi\u1ec7t>", "actions": [<h\u00e0nh \u0111\u1ed9ng theo th\u1ee9 t\u1ef1>]}\n'
    "C\u00e1c tool:\n"
    '- move: args {"vx":m/s, "vy":m/s, "vyaw":rad/s, "duration":gi\u00e2y}. '
    "vx>0 ti\u1ebfn, vx<0 l\u00f9i (t\u1ed1i \u0111a 0.6); vy>0 sang tr\u00e1i (t\u1ed1i \u0111a 0.4); "
    "vyaw>0 xoay tr\u00e1i (t\u1ed1i \u0111a 1.0); duration t\u1ed1i \u0111a 6.\n"
    '- action: args {"name": "hello"|"dance1"|"dance2"|"stretch"|"heart"|"standup"|"standdown"}\n'
    '- stop: args {}\n'
    '- go_to: args {"location": "<t\u00ean \u0111i\u1ec3m tr\u00ean b\u1ea3n \u0111\u1ed3>"} \u2014 t\u1ef1 \u0111i t\u1edbi \u0111i\u1ec3m \u0111\u00e3 l\u01b0u.\n'
    "Quy t\u1eafc: l\u1ec7nh ph\u1ee9c t\u1ea1p th\u00ec x\u1ebfp nhi\u1ec1u action theo \u0111\u00fang th\u1ee9 t\u1ef1; "
    "c\u00e2u h\u1ecfi/tr\u00f2 chuy\u1ec7n th\u00ec actions r\u1ed7ng []; xoay 90 \u0111\u1ed9 \u2248 vyaw 0.8 trong 2 gi\u00e2y; "
    '"say" ng\u1eafn g\u1ecdn, th\u00e2n thi\u1ec7n, ti\u1ebfng Vi\u1ec7t.'
)

# 1 vi du few-shot de model "bat song" format (giu ngan cho nhanh)
FEWSHOT_USER = "\u0111i t\u1edbi tr\u01b0\u1edbc 1 m\u00e9t r\u1ed3i ch\u00e0o m\u1ecdi ng\u01b0\u1eddi \u0111i"
FEWSHOT_ASSISTANT = json.dumps({
    "say": "D\u1ea1, \u0111i t\u1edbi r\u1ed3i ch\u00e0o li\u1ec1n n\u00e8!",
    "actions": [
        {"tool": "move", "args": {"vx": 0.35, "vy": 0, "vyaw": 0, "duration": 2.9}},
        {"tool": "action", "args": {"name": "hello"}},
    ],
}, ensure_ascii=False)


def _chatml(user_text: str, use_fewshot: bool = True) -> str:
    """Ghep prompt theo dinh dang ChatML cua Qwen.
    use_fewshot=False cho model DA FINE-TUNE (vi du da duoc 'nuong' vao model,
    nhet them vao prompt chi lam lech phan phoi + ton token)."""
    parts = [f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"]
    if use_fewshot:
        parts.append(f"<|im_start|>user\n{FEWSHOT_USER}<|im_end|>\n"
                     f"<|im_start|>assistant\n{FEWSHOT_ASSISTANT}<|im_end|>\n")
    parts.append(f"<|im_start|>user\n{user_text}<|im_end|>\n"
                 f"<|im_start|>assistant\n")
    return "".join(parts)


class LLMPlanner:
    def __init__(self, endpoint="http://127.0.0.1:8080", grammar_path="grammar.gbnf",
                 temperature=0.2, n_predict=200, timeout_s=60, use_fewshot=True):
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.n_predict = n_predict
        self.timeout_s = timeout_s
        self.use_fewshot = use_fewshot
        with open(grammar_path, "r", encoding="utf-8") as f:
            self.grammar = f.read()

    def plan(self, user_text: str) -> dict:
        """Tra ve {"say":..., "actions":[...], "_ms": <thoi gian>, "_tps": <token/s>}"""
        t0 = time.time()
        payload = {
            "prompt": _chatml(user_text, self.use_fewshot),
            "grammar": self.grammar,        # <-- ep JSON dung schema
            "temperature": self.temperature,
            "n_predict": self.n_predict,
            "cache_prompt": True,           # <-- giu KV-cache system prompt
            "stop": ["<|im_end|>"],
        }
        r = requests.post(f"{self.endpoint}/completion", json=payload,
                          timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        ms = (time.time() - t0) * 1000.0
        text = (data.get("content") or "").strip()
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            out = {"say": "Xin l\u1ed7i, m\u00ecnh ch\u01b0a hi\u1ec3u, b\u1ea1n n\u00f3i l\u1ea1i nh\u00e9?", "actions": []}
        out["_ms"] = round(ms, 1)
        timings = data.get("timings") or {}
        out["_tps"] = round(timings.get("predicted_per_second", 0.0), 1)
        return out

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.endpoint}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False


if __name__ == "__main__":
    p = LLMPlanner()
    if not p.health():
        print("llama-server chua chay? Xem HUONG_DAN.md phan A1.")
    else:
        for q in ["\u0111i t\u1edbi c\u00e1i c\u1eeda r\u1ed3i nh\u1ea3y m\u1ed9t b\u00e0i",
                  "h\u00f4m nay b\u1ea1n kh\u1ecfe kh\u00f4ng?"]:
            print(q, "->", json.dumps(p.plan(q), ensure_ascii=False, indent=1))
