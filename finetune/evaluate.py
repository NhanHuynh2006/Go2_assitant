#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate.py — DANH GIA success-rate tren data/test.jsonl (300 cau chua tung train).

Cach dung (do 2 lan de co bang so sanh cho bai bao):
  1. Chay llama-server voi model BASELINE (Qwen goc) -> python3 evaluate.py --tag baseline
  2. Chay llama-server voi model CUA BAN (govoice-...gguf) -> python3 evaluate.py --tag finetuned
Ket qua: in bang theo nhom + ghi eval_<tag>.csv

Tieu chi cham DUNG cho 1 cau:
  - Chuoi tool dung thu tu (move/action/stop/go_to)
  - action: dung "name" | go_to: dung "location"
  - move: dung DAU cua vx/vy/vyaw (huong di) + duration lech <= 30% hoac <= 0.6s
  - chitchat/refuse: actions phai RONG (an toan!)
"""

import argparse
import csv
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_planner import LLMPlanner  # noqa: E402


def sign(x):
    return (x > 1e-6) - (x < -1e-6)


def _merge_moves(actions):
    """Gop cac lenh move LIEN TIEP cung van toc thanh 1 (cong duration).
    Ly do: [xoay 6s, 6s, 3.7s] va [xoay 6s, 5s, 4.7s] la TUONG DUONG ngu nghia
    (tong goc xoay nhu nhau) — chi khac cach che khuc. So tong moi cong bang."""
    out = []
    for a in actions:
        a = {"tool": (a.get("tool") or "").lower(), "args": dict(a.get("args") or {})}
        if (a["tool"] == "move" and out and out[-1]["tool"] == "move"):
            p = out[-1]["args"]
            q = a["args"]
            same = all(abs(float(p.get(k, 0)) - float(q.get(k, 0))) < 0.05
                       for k in ("vx", "vy", "vyaw"))
            if same:
                p["duration"] = float(p.get("duration", 0)) + float(q.get("duration", 0))
                continue
        out.append(a)
    return out


def move_ok(pred, gold):
    pa, ga = pred.get("args", {}), gold.get("args", {})
    for k in ("vx", "vy", "vyaw"):
        if sign(float(pa.get(k, 0))) != sign(float(ga.get(k, 0))):
            return False
    pd, gd = float(pa.get("duration", 2)), float(ga.get("duration", 2))
    return abs(pd - gd) <= max(0.6, 0.3 * gd)


def actions_ok(pred_actions, gold_actions):
    pred_actions = _merge_moves(pred_actions)
    gold_actions = _merge_moves(gold_actions)
    if len(pred_actions) != len(gold_actions):
        return False
    for p, g in zip(pred_actions, gold_actions):
        if (p.get("tool") or "").lower() != (g.get("tool") or "").lower():
            return False
        tool = (g.get("tool") or "").lower()
        if tool == "action":
            if (p.get("args", {}).get("name", "").lower()
                    != g.get("args", {}).get("name", "").lower()):
                return False
        elif tool == "go_to":
            if (p.get("args", {}).get("location", "").lower().strip()
                    != g.get("args", {}).get("location", "").lower().strip()):
                return False
        elif tool == "move":
            if not move_ok(p, g):
                return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="baseline", help="ten lan do (baseline/finetuned)")
    ap.add_argument("--test", default="data/test.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="0 = cham het")
    ap.add_argument("--no-fewshot", action="store_true",
                    help="bo vi du few-shot trong prompt (DUNG CHO MODEL DA FINE-TUNE)")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="0 = greedy, on dinh nhat khi cham diem")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080",
                    help="llama-server endpoint (vd :8081 cho model baseline song song)")
    a = ap.parse_args()

    grammar = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "grammar.gbnf")
    planner = LLMPlanner(grammar_path=grammar,
                         use_fewshot=not a.no_fewshot,
                         temperature=a.temperature,
                         endpoint=a.endpoint)
    if not planner.health():
        raise SystemExit("llama-server chua chay (port 8080).")

    rows = [json.loads(l) for l in open(a.test, encoding="utf-8")]
    if a.limit:
        rows = rows[:a.limit]

    stats = {}        # category -> [ok, total]
    lat = []
    out_csv = f"eval_{a.tag}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "user", "ok", "ms", "pred", "gold"])
        for i, r in enumerate(rows):
            pred = planner.plan(r["user"])
            ok = actions_ok(pred.get("actions", []) or [],
                            r["output"].get("actions", []) or [])
            # cau xa giao / tu choi: them dieu kien say khong rong
            if r["category"] in ("chitchat", "refuse"):
                ok = ok and bool(pred.get("say", "").strip())
            c = r["category"]
            s = stats.setdefault(c, [0, 0])
            s[0] += int(ok)
            s[1] += 1
            lat.append(pred.get("_ms", 0))
            w.writerow([r["id"], c, r["user"], int(ok), pred.get("_ms"),
                        json.dumps(pred.get("actions", []), ensure_ascii=False),
                        json.dumps(r["output"]["actions"], ensure_ascii=False)])
            done = sum(v[1] for v in stats.values())
            print(f"\r{done}/{len(rows)}  ", end="", flush=True)

    print(f"\n\n===== KET QUA [{a.tag}] =====")
    tot_ok = tot = 0
    for c, (ok, n) in sorted(stats.items()):
        tot_ok += ok
        tot += n
        print(f"  {c:10s}: {ok:4d}/{n:<4d} = {100*ok/n:5.1f}%")
    print(f"  {'TONG':10s}: {tot_ok:4d}/{tot:<4d} = {100*tot_ok/tot:5.1f}%")
    if lat:
        lat_s = sorted(lat)
        print(f"  latency: tb {sum(lat)/len(lat):.0f} ms | "
              f"p95 {lat_s[int(0.95*len(lat))-1]:.0f} ms")
    print(f"  chi tiet: {out_csv}")


if __name__ == "__main__":
    main()
