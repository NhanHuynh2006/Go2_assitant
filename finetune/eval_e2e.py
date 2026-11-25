#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_e2e.py — DANH GIA TOAN HE THONG (giong production):
  Reflex (Tang 1) truoc -> neu None thi LLM (Tang 2) -> plan_verifier.
Khac evaluate.py (chi do RIENG LLM). Dung CHUNG trong tai actions_ok.

Chay: python3 eval_e2e.py --tag e2e_v2 --no-fewshot   (server fine-tune dang chay)
"""
import argparse, csv, json, os, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_planner import LLMPlanner            # noqa: E402
from reflex_matcher import ReflexMatcher      # noqa: E402
from combo_matcher import ComboMatcher        # noqa: E402
from plan_verifier import verify_plan         # noqa: E402
from evaluate import actions_ok               # noqa: E402  (tai su dung trong tai)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e2e")
    ap.add_argument("--test", default="data/test.jsonl")
    ap.add_argument("--no-fewshot", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--n-predict", type=int, default=200)
    a = ap.parse_args()

    grammar = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "grammar.gbnf")
    llm = LLMPlanner(grammar_path=grammar, use_fewshot=not a.no_fewshot,
                     temperature=a.temperature, n_predict=a.n_predict)
    if not llm.health():
        raise SystemExit("llama-server chua chay (port 8080).")
    reflex = ReflexMatcher()
    combo = ComboMatcher()

    rows = [json.loads(l) for l in open(a.test, encoding="utf-8")]
    stats, src = {}, {"combo": 0, "reflex": 0, "llm": 0}
    out_csv = f"eval_{a.tag}.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "user", "ok", "source", "pred", "gold"])
        for i, r in enumerate(rows):
            text = r["user"]
            # Dinh tuyen GIONG production: Combo(1.5) -> Reflex(1) -> LLM(2)+verifier
            res = combo.match(text)
            source = "combo"
            if res is None:
                res = combo.resolve_goto(text)     # lenh don go_to (truoc Reflex)
                source = "combo"
            if res is None and not combo.needs_llm(text):   # giong production
                res = reflex.match(text)
                source = "reflex"
            if res is None:
                res = llm.plan(text)
                actions = res.get("actions", []) or []
                actions, _ = verify_plan(text, actions)   # giong production
                source = "llm"
            else:
                actions = res.get("actions", []) or []
            src[source] += 1
            ok = actions_ok(actions, r["output"].get("actions", []) or [])
            if r["category"] in ("chitchat", "refuse"):
                ok = ok and bool(res.get("say", "").strip())
            c = r["category"]
            s = stats.setdefault(c, [0, 0]); s[0] += int(ok); s[1] += 1
            w.writerow([r["id"], c, text, int(ok), source,
                        json.dumps(actions, ensure_ascii=False),
                        json.dumps(r["output"]["actions"], ensure_ascii=False)])
            print(f"\r{sum(v[1] for v in stats.values())}/{len(rows)}  ", end="", flush=True)

    print(f"\n\n===== KET QUA E2E [{a.tag}] (Reflex->LLM->verifier) =====")
    tot_ok = tot = 0
    for c, (ok, n) in sorted(stats.items()):
        tot_ok += ok; tot += n
        print(f"  {c:16s}: {ok:4d}/{n:<4d} = {100*ok/n:5.1f}%")
    print(f"  {'TONG':16s}: {tot_ok:4d}/{tot:<4d} = {100*tot_ok/tot:5.1f}%")
    print(f"  dinh tuyen: Combo {src['combo']} | Reflex {src['reflex']} | LLM {src['llm']} cau")
    print(f"  chi tiet: {out_csv}")


if __name__ == "__main__":
    main()
