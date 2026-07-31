#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_normalizer.py — "SUA CHINH TA" cho output STT, an toan nho DINH TUYEN-GATED.

Van de: transducer 30M nhanh nhung cau dai/kho hay TRUOT chu ("xoay"->"xay",
"chin"->"chinh"). Chu lech -> Reflex/Combo khong khop -> roi xuong LLM (cham, de bia).

KHO: tieng Viet bo dau thi rat nhieu tu trung "khung" (quay~qua, chao~cho, xuong~xong)
-> sua fuzzy bua bai se LAM HONG cau tro chuyen.

CACH AN TOAN (dung trong assistant_realtime.process):
  1. Thu dinh tuyen cau GOC bang Combo/Reflex.
  2. Neu TRUOT, tao ban da-sua (aggressive fuzzy) roi thu dinh tuyen LAI.
  3. CHI dung ban da-sua NEU no dinh tuyen thanh 1 lenh that (Combo/Reflex khop).
     Neu khong -> vut ban sua, giu cau GOC (cho LLM). => cau tro chuyen KHONG BAO GIO
     bi hong, vi "moi ngoi" hay "chao qua duong" co sua kieu gi cung khong thanh lenh.

Module nay chi lo BUOC SUA (correct). Phan "gate" nam o pipeline (route_with_fix).
Them tu vung (dia diem SLAM sau nay): TextNormalizer(extra_vocab=[...]).
"""

import re
import unicodedata


def _strip(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _strip(s.lower())).strip()


def _lev1(a: str, b: str) -> int:
    """Levenshtein co chan: tra 0/1, con lai 2 (du de loc dist<=1)."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 1:
        return 2
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[len(b)] if prev[len(b)] <= 1 else 2


# Tu vung lenh (canonical co dau) — fuzzy duoc phep vi da co GATE bao ve o pipeline.
_VOCAB = [
    "xoay", "quay", "rẽ", "thẳng", "tiến", "lùi", "trái", "phải", "sang",
    "đứng", "dậy", "nằm", "ngồi", "dừng", "ngưng", "nhảy", "múa", "vươn",
    "vai", "chào", "vẫy", "bắt", "duỗi", "bước", "xuống", "lên", "vòng",
    "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười",
    "mươi", "trăm", "lăm", "mét", "giây", "độ",
]

# Bang sua tay (skeleton khong dau -> canonical). Them khi thay STT sai kieu moi.
_CORRECTIONS = {
    "xay": "xoay", "xoai": "xoay", "qoay": "quay",
    "phair": "phải", "fai": "phải", "chinh": "chín", "muroi": "mười",
    "nhayr": "nhảy", "thang": "thẳng",
}

# Tu thuong hay trung khung — khong dong (them lop bao ve du da co gate).
_STOP = {
    "toi", "tao", "minh", "ban", "cau", "no", "con", "co", "qua", "cua",
    "cho", "mua", "day", "la", "di", "ra", "ve", "moi", "noi", "gio", "hoi",
    "vay", "hay", "roi", "khong", "duoc", "gi", "the", "nay", "nguoi", "nhin",
    "muon", "nghe", "xem", "thich", "biet", "choi", "hoc", "lam", "nha",
    "duong", "thuong", "an", "uong", "ngu", "buon", "vui", "cuoi", "xong",
}


class TextNormalizer:
    def __init__(self, extra_vocab=None, corrections=None):
        self._canon = {}                      # skeleton -> canonical co dau
        for w in list(_VOCAB) + list(extra_vocab or []):
            n = _norm(w)
            if n and n not in _STOP:
                self._canon.setdefault(n, w)
        self._keys = list(self._canon)
        self._corr = dict(_CORRECTIONS)
        if corrections:
            self._corr.update(corrections)

    def _fix_word(self, w: str) -> str:
        n = _norm(w)
        if not n or n in _STOP:
            return w
        if n in self._corr:
            return self._corr[n]
        if n in self._canon:
            return self._canon[n]
        if len(n) >= 3:                        # fuzzy: cuc gan 1 tu lenh & duy nhat
            hits = [k for k in self._keys if _lev1(n, k) == 1]
            if len(hits) == 1:
                return self._canon[hits[0]]
        return w

    def correct(self, text: str) -> str:
        if not text:
            return text
        return " ".join(self._fix_word(w) for w in text.split())


if __name__ == "__main__":
    tn = TextNormalizer()
    for s in ["xay phai chinh muoi do", "qoay trai", "di than", "luj lai",
              "hom nay ban khoe khong", "moi nguoi oi ra day"]:
        print(f"  {s!r:34s} -> {tn.correct(s)!r}")
