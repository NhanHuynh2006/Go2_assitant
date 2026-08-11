#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kiem_tra_knowledge.py — SOAT LOI knowledge.yaml sau khi them muc moi.

Kho tri thuc phinh to KHONG lam cham (do thuc te: 10.000 cach hoi van chi
~6ms/cau, khong dang ke so voi LLM ~1500ms). Cai HONG that su la cac cach hoi
DE LAN sang nhau: hai muc khac nhau ma cau hoi qua giong -> may chon nham ->
chó tra loi lac de. Script nay tim dung may chuyen do TRUOC khi mang di dien.

CHAY:
    python3 kiem_tra_knowledge.py                  # kiem knowledge.yaml
    python3 kiem_tra_knowledge.py file_khac.yaml

BAO CAO 4 muc:
  1. YAML co doc duoc khong, muc nao thieu q/a
  2. Cach hoi TRUNG NHAU giua hai muc khac dap an   <- loi nang, phai sua
  3. Cach hoi BI GATE CHAN (< 2 tu hoac < 5 ky tu)  <- go vao vo ich
  4. Tu truy xuat + bien an toan mong               <- canh bao, nen tach y ro hon

Ma thoat: 0 = sach, 1 = co loi nang (muc 2 hoac muc 1).
"""
import io
import sys
import os

NGUONG = 0.55          # phai khop nguong mac dinh cua FaqMatcher
BIEN_MONG = 0.05       # top1 - top2(khac dap an) duoi muc nay = de lat


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "knowledge.yaml"
    if not os.path.exists(path):
        print(f"Khong thay file: {path}")
        return 1

    import yaml
    try:
        data = yaml.safe_load(io.open(path, encoding="utf-8")) or []
    except Exception as e:
        print(f"[1] YAML HONG — khong doc duoc:\n    {e}")
        return 1

    loi_nang = 0

    # ---- 1. cau truc ----
    thieu = [i for i, it in enumerate(data)
             if not isinstance(it, dict) or not it.get("a") or not it.get("q")]
    print(f"[1] YAML doc duoc: {len(data)} muc, "
          f"{sum(len(it.get('q', [])) for it in data if isinstance(it, dict))} cach hoi")
    if thieu:
        loi_nang += 1
        print(f"    LOI: {len(thieu)} muc thieu 'q' hoac 'a' -> vi tri {thieu[:10]}")
    else:
        print("    moi muc deu co du q va a.")

    # ---- nap qua dung FaqMatcher that ----
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from faq_matcher import FaqMatcher
    import numpy as np
    fm = FaqMatcher(path, threshold=NGUONG)
    if not fm.ready():
        print("    (thieu sklearn -> bo qua phan do do giong)")
        return 1 if loi_nang else 0
    ans_id = [id(a) for a in fm.answers]

    # ---- 2. cach hoi trung nhau giua HAI DAP AN KHAC NHAU ----
    seen = {}
    trung = []
    for i, q in enumerate(fm.q_texts):
        if q in seen and ans_id[seen[q]] != ans_id[i]:
            trung.append((q, fm.answers[seen[q]]["a"], fm.answers[i]["a"]))
        seen.setdefault(q, i)
    print(f"\n[2] Cach hoi TRUNG giua hai muc khac dap an: {len(trung)}")
    if trung:
        loi_nang += 1
        for q, a1, a2 in trung[:10]:
            print(f"    LOI  {q!r}\n         -> dap an A: {a1[:60]}\n         -> dap an B: {a2[:60]}")
        print("    (may cau nay may se chon BUA 1 trong 2 — gop lai hoac doi cach hoi)")
    else:
        print("    khong co. Tot.")

    # ---- 3. cach hoi bi gate chan ----
    chan = [q for q in fm.q_texts if len(q.split()) < 2 or len(q) < 5]
    print(f"\n[3] Cach hoi BI CHAN vi qua ngan (<2 tu hoac <5 ky tu): {len(chan)}")
    if chan:
        print(f"    {chan[:12]}")
        print("    (gate chan manh nhieu STT — may cau nay go vao cung khong bao gio khop)")
    else:
        print("    khong co.")

    # ---- 4. tu truy xuat + bien an toan ----
    sai, bien = [], []
    for i, q in enumerate(fm.q_texts):
        v = fm.vectorizer.transform([q])
        s = (fm.matrix @ v.T).toarray().ravel()
        top = s.argsort()[::-1]
        if ans_id[top[0]] != ans_id[i]:
            sai.append((q, fm.answers[i]["a"], fm.answers[top[0]]["a"]))
        s2 = next((s[j] for j in top if ans_id[j] != ans_id[top[0]]), 0.0)
        bien.append(s[top[0]] - s2)
    bien = np.array(bien)
    n = len(fm.q_texts)
    print(f"\n[4] Tu truy xuat: {n - len(sai)}/{n} ({100 * (n - len(sai)) / n:.1f}%) "
          f"cau hoi tra ve DUNG dap an cua no")
    for q, dung, ra in sai[:8]:
        print(f"    LECH {q!r}\n         dang le: {dung[:60]}\n         lai ra : {ra[:60]}")
    mong = int((bien < BIEN_MONG).sum())
    print(f"    Bien an toan trung binh {bien.mean():.2f}; "
          f"{mong} cach hoi co bien < {BIEN_MONG} (de lat sang muc khac)")

    print("\n" + "=" * 60)
    if loi_nang:
        print("KET LUAN: CO LOI NANG — sua muc [1]/[2] truoc khi dung.")
        return 1
    print("KET LUAN: SACH. Them thoai mai, toc do khong phai van de.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
