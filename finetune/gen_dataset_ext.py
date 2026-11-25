#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_dataset_ext.py — DATASET BO SUNG cho cac kha nang moi (sim 2026-11):

  goto_place     di toi phong / cho dat ten moi: "vào bếp", "ra ban công", "lại cửa chính"
  goto_object    do vat + MAU: "đi tới cái bàn màu đen", "lại cái hộp vàng", "ra chiếc ghế sofa xanh"
  goto_spatial   quan he khong gian: "đứng bên trái cái ghế tím", "lại cách tủ lạnh 1 mét"
  combo_object   ghep: "ra cái bàn đen rồi chào đi", "tới cái ghế tím xong nằm xuống"
  ask_color      HOI ve do vat (khong phai lenh): "cái bàn màu gì" -> actions [] (khong di bua)

Schema KHONG doi (grammar.gbnf giu nguyen): do vat/quan he di qua go_to.location
duoi dang chuan hoa — "bàn màu đen", "bên trái ghế màu tím", "cách tủ lạnh 1 mét" — va
robot (objects.py / spatial.py) se tim toa do. Vi vay LLM chi can TRICH dung cum dia
diem, khong can biet ban do.

Tap test cu (data/test.jsonl, 300 cau) KHONG doi -> so 91.0 % van so sanh duoc.
Ra:  data_v2/train.jsonl = train cu + ext   (dung: train_lora.py --data-dir data_v2)
     data_v2/val.jsonl   = val cu + ext
     data_v2/test.jsonl  = test CU (nguyen ven)
     data_v2/test_ext.jsonl = 200 cau moi chua train (cham kha nang moi)
Chay:  cd finetune && python3 gen_dataset_ext.py
"""

import json
import os
import random
import shutil
import unicodedata

from gen_dataset import TAILS, act, goto, mv_split, VX, VYAW

random.seed(7)
OUT = "data_v2"

VERBS = ["đi tới", "đi đến", "ra chỗ", "lại chỗ", "tới", "đến", "chạy tới", "qua chỗ",
         "lại gần", "đi lại gần", "ra", "đi ra", "tới chỗ"]
VERBS_IN = ["vào", "đi vào", "chạy vào"]          # cho phong
PLACES = ["bếp", "phòng khách", "phòng ngủ", "nhà vệ sinh", "phòng tắm", "ban công",
          "cửa chính", "cửa sau", "cầu thang", "hành lang", "phòng làm việc", "sân",
          "cổng", "chỗ sạc", "góc phòng", "cửa sổ", "bàn ăn", "ghế gỗ", "chỗ cũ", "cửa"]
ROOMS = {"bếp", "phòng khách", "phòng ngủ", "nhà vệ sinh", "phòng tắm", "ban công",
         "phòng làm việc", "sân", "hành lang"}
NOUNS = ["bàn", "bàn ăn", "bàn trà", "ghế", "ghế sofa", "ghế bành", "ghế gỗ", "tủ lạnh",
         "quầy bếp", "chậu cây", "kệ cây", "thùng carton", "thùng", "hộp đồ chơi", "hộp",
         "tấm thảm", "thảm", "trạm sạc", "cửa sổ",
         # do gia dung khac (de LLM tong quat hoa, khong chi thuoc nha sim)
         "tivi", "tủ quần áo", "giường", "máy giặt", "kệ sách", "thùng rác", "bình nước",
         "cây đèn", "tủ giày", "quạt", "bàn học", "ghế xoay", "cái gối", "xe đạp"]
COLORS = ["đỏ", "xanh lá", "xanh dương", "vàng", "đen", "trắng", "nâu", "xám", "tím",
          "hồng", "cam", "xanh"]
RELS = [("bên trái", "bên trái"), ("bên phải", "bên phải"), ("phía sau", "phía sau"),
        ("sau lưng", "phía sau"), ("phía trước", "phía trước"), ("trước mặt", "phía trước"),
        ("cạnh", "bên cạnh"), ("bên cạnh", "bên cạnh")]
DISTS = [("1 mét", "1 mét"), ("2 mét", "2 mét"), ("nửa mét", "0.5 mét"), ("một mét", "1 mét"),
         ("hai mét", "2 mét"), ("1.5 mét", "1.5 mét")]
SAY_GO = ["Dạ, tới {} liền!", "Ok, đi tới {} nè!", "Dạ, mình qua {} nha!"]


def pick(xs):
    return random.choice(xs)


def obj_phrase(noun, color):
    """(cach noi, nhan chuan cho location)."""
    if color is None:
        return pick([f"cái {noun}", f"chiếc {noun}", noun]), noun
    form = pick(["cái {n} màu {c}", "cái {n} {c}", "chiếc {n} màu {c}", "{n} màu {c}",
                 "cái {n} có màu {c}"])
    return form.format(n=noun, c=color), f"{noun} màu {color}"


def gen_places():
    out = []
    for p in PLACES:
        verbs = VERBS + (VERBS_IN if p in ROOMS else [])
        for v in random.sample(verbs, min(6, len(verbs))):
            out.append((f"{v} {p}{pick(TAILS)}", [s.format(p) for s in SAY_GO], [goto(p)],
                        "goto_place"))
    return out


def gen_objects(n=900):
    out = []
    for _ in range(n):
        noun = pick(NOUNS)
        color = pick(COLORS) if random.random() < 0.8 else None
        said, label = obj_phrase(noun, color)
        out.append((f"{pick(VERBS)} {said}{pick(TAILS)}", [s.format(label) for s in SAY_GO],
                    [goto(label)], "goto_object"))
    return out


def gen_spatial(n=600):
    out = []
    for _ in range(n):
        noun = pick(NOUNS[:19])
        color = pick(COLORS) if random.random() < 0.5 else None
        said, label = obj_phrase(noun, color)
        if random.random() < 0.75:
            rel_said, rel = pick(RELS)
            text = f"{pick(['đi tới', 'ra', 'đứng', 'lại', 'đi ra'])} {rel_said} {said}"
            loc = f"{rel} {label}"
        else:
            d_said, d = pick(DISTS)
            text = f"{pick(['lại', 'đứng', 'đi tới chỗ'])} cách {said} {d_said}"
            loc = f"cách {label} {d}"
        out.append((text + pick(TAILS), [s.format(loc) for s in SAY_GO], [goto(loc)],
                    "goto_spatial"))
    return out


def gen_combos(n=500):
    tails = [("chào đi", [act("hello")]), ("nằm xuống", [act("standdown")]),
             ("nhảy đi", [act("dance1")]), ("vươn vai", [act("stretch")]),
             ("quay lại chỗ cũ", [goto("chỗ cũ")]),
             ("đi thẳng 1 mét", mv_split(VX, 0, 0, round(1.0 / VX, 2))),
             ("xoay trái 90 độ", mv_split(0, 0, VYAW, 1.96))]
    joins = [" rồi ", " xong ", " sau đó ", ", xong rồi ", " rồi thì "]
    out = []
    for _ in range(n):
        noun = pick(NOUNS[:19])
        said, label = obj_phrase(noun, pick(COLORS) if random.random() < 0.7 else None)
        t_said, t_acts = pick(tails)
        if random.random() < 0.5:
            text = f"{pick(VERBS)} {said}{pick(joins)}{t_said}"
            acts = [goto(label)] + t_acts
        else:
            text = f"{t_said}{pick(joins)}{pick(VERBS)} {said}"
            acts = t_acts + [goto(label)]
        out.append((text + pick(TAILS), ["Dạ làm liền nè!", "Ok, từng bước một nha!"], acts,
                    "combo_object"))
    return out


def gen_questions():
    qs = ["cái {} màu gì", "{} màu gì vậy", "trong nhà có mấy cái {}", "{} ở đâu vậy",
          "mày thấy cái {} không", "cái {} đẹp không"]
    out = []
    for noun in NOUNS[:19]:
        for q in random.sample(qs, 2):
            out.append((q.format(noun), ["Để mình nhìn thử nha, bạn muốn mình đi tới đó không?",
                                         "Mình chưa chắc, bạn muốn mình lại xem không?"],
                        [], "ask_color"))
    return out


def strip(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def main():
    rows = gen_places() + gen_objects() + gen_spatial() + gen_combos() + gen_questions()
    rows += [(strip(t), s, a, c + "_nodiac") for t, s, a, c in rows if random.random() < 0.25]
    seen, data = set(), []
    for text, says, acts, cat in rows:
        if text in seen:
            continue
        seen.add(text)
        data.append({"user": text, "output": {"say": pick(says), "actions": acts},
                     "category": cat})
    random.shuffle(data)
    test_ext, val_ext, train_ext = data[:200], data[200:300], data[300:]

    os.makedirs(OUT, exist_ok=True)

    def load(p):
        return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []

    def dump(name, rows_):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            for i, r in enumerate(rows_):
                r = dict(r)
                r["id"] = f"{name.split('.')[0]}-{i}"
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name:16s} {len(rows_):5d} mau")

    dump("train.jsonl", load("data/train.jsonl") + train_ext)
    dump("val.jsonl", load("data/val.jsonl") + val_ext)
    shutil.copy("data/test.jsonl", os.path.join(OUT, "test.jsonl"))     # NGUYEN VEN
    print(f"{'test.jsonl':16s} {len(load('data/test.jsonl')):5d} mau (giu nguyen tap cu)")
    dump("test_ext.jsonl", test_ext)
    cats = {}
    for r in data:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    print("\nMau moi:", len(data), json.dumps(cats, ensure_ascii=False))


if __name__ == "__main__":
    main()
