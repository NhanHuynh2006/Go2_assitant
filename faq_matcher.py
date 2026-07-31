#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faq_matcher.py — TANG 1.7 "TRA CUU NGU NGHIA" cua GoVoice.

Reflex (Tang 1) khop TU KHOA cung -> chinh xac nhung cung nhac, noi khac di la truot.
LLM (Tang 2) mem deo nhung cham (1-3s). Tang nay o GIUA: so khop cau hoi nguoi dung
voi KHO TRI THUC (knowledge.yaml) bang do tuong dong NGU NGHIA (fuzzy), tra loi
TUC THI cho cac tinh huong giao tiep thong thuong ma khong can dung LLM.

Ky thuat: TF-IDF tren n-gram KY TU (char_wb 2..4) + cosine. Uu diem:
  - Khong can tai model (chi sklearn) -> chay offline, nhe, tuc thi.
  - Chiu duoc THIEU DAU, DAO CHU, SAI CHINH TA nhe (vi so khop theo cum ky tu).
  - Scale toi hang ngan cau de dang (vector hoa 1 lan).
Nguong (threshold): >= thi nhan, < thi tra None (nhuong LLM) -> khong tra loi bậy.

Nang cap Phase 2 (tuy chon): thay TF-IDF bang embedding than kinh (sentence
-transformers/onnx) de hieu ca DONG NGHIA that su. Giao dien match() giu nguyen.
"""

import os

import numpy as np

try:
    import yaml
except Exception:
    yaml = None

from reflex_matcher import norm


class FaqMatcher:
    """match(text) -> {intent,say,actions,_score} neu du giong 1 cau trong kho,
    nguoc lai None (de nhuong LLM)."""

    def __init__(self, path, threshold=0.55):
        self.threshold = float(threshold)
        self.answers = []      # index-aligned voi q_texts: dict {a, action}
        self.q_texts = []      # cac cach hoi (da norm) — nhieu q tro cung 1 answer
        self.vectorizer = None
        self.matrix = None
        self._load(path)
        self._build()

    def _load(self, path):
        if not path or not os.path.exists(path) or yaml is None:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or []
        except Exception as e:
            print(f"[faq] khong doc duoc {path}: {e}")
            return
        for item in data:
            if not isinstance(item, dict):
                continue
            a = item.get("a")
            if not a:
                continue
            action = item.get("action")
            qs = item.get("q") or []
            if isinstance(qs, str):
                qs = [qs]
            for q in qs:
                qn = norm(str(q))
                if qn:
                    self.q_texts.append(qn)
                    self.answers.append({"a": a, "action": action})

    def _build(self):
        if not self.q_texts:
            return
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except Exception as e:
            print(f"[faq] thieu sklearn -> tat FAQ ngu nghia: {e}")
            return
        # char_wb: n-gram ky tu trong bien tu -> chiu thieu dau/dao chu tot cho tieng Viet
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
        self.matrix = self.vectorizer.fit_transform(self.q_texts)   # da L2-normalize
        print(f"[faq] nap {len(set(id(a) for a in self.answers))} cau tra loi "
              f"/ {len(self.q_texts)} cach hoi (nguong {self.threshold})")

    def ready(self):
        return self.vectorizer is not None

    def match(self, text):
        if self.vectorizer is None:
            return None
        qn = norm(text or "")
        # CHAN MANH NHIEU: cau hoi that luon >= 2 chu. Mảnh nhiễu STT ('ĐÂY','RỒI','À')
        # la 1 chu -> KHONG cho FAQ tra loi bua (truoc day khop ao 0.6+ -> dap lung tung).
        if not qn or len(qn.split()) < 2 or len(qn) < 5:
            return None
        v = self.vectorizer.transform([qn])
        # tfidf da L2-normalize -> tich vo huong = cosine similarity
        sims = (self.matrix @ v.T).toarray().ravel()
        i = int(sims.argmax())
        score = float(sims[i])
        if score < self.threshold:
            return None
        ans = self.answers[i]
        acts = ([{"tool": "action", "args": {"name": ans["action"]}}]
                if ans.get("action") else [])
        return {"intent": "faq", "say": ans["a"], "actions": acts, "_score": score}


if __name__ == "__main__":
    import sys
    kb = sys.argv[1] if len(sys.argv) > 1 else "knowledge.yaml"
    fm = FaqMatcher(kb)
    tests = ["ê bạn tên gì thế", "làm được cái gì kể coi", "buồn quá gô ơi",
             "khoẻ hông", "mày là chó thiệt hả", "cảm ơn nhiều nha", "biểu diễn coi",
             "đi thẳng ba mét"]  # cau cuoi la LENH -> nen tra None (nhuong reflex/LLM)
    for t in tests:
        r = fm.match(t)
        if r:
            print(f"{t!r:32s} -> ({r['_score']:.2f}) {r['say'][:50]}")
        else:
            print(f"{t!r:32s} -> None (nhuong LLM)")
