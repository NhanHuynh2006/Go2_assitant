#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_dataset.py — SINH DATASET: cau lenh tieng Viet -> JSON tool-call (cho LoRA).

Phuong phap: sinh TONG HOP bang luat + to hop (synthetic, rule-based):
  - Tai lap 100% (seed co dinh) -> dung chuan nghien cuu
  - Khong can API, khong ton tien
  - Gold label LUON dung schema + dung quy uoc toc do (vx=0.35, vyaw=0.8...)
    -> y het quy uoc cua reflex_matcher + system prompt (NHAT QUAN!)

Pham vi sinh:
  1. move don (tien/lui/ngang/xoay, kem so met/giay/do, ca so bang chu)
  2. action (chao/nhay/vuon vai/tha tim/dung day/nam xuong) + tu dong nghia
  3. go_to (di toi diem tren map)
  4. stop
  5. COMBO 2-3 buoc noi bang "roi/xong/sau do" (phan kho nhat — ly do can LLM)
  6. chitchat (cau hoi xa giao) -> actions []
  7. refuse (lenh robot KHONG lam duoc) -> actions [] + tu choi lich su (AN TOAN)

Chay:  python3 gen_dataset.py            # ra data/train.jsonl, val.jsonl, test.jsonl
"""

import json
import math
import os
import random

random.seed(42)

VX, VY, VYAW = 0.35, 0.25, 0.8
OUT_DIR = "data"

WORD_NUM = {"m\u1ed9t": 1, "hai": 2, "ba": 3, "b\u1ed1n": 4, "n\u0103m": 5}
TAILS = ["", " nha", " nh\u00e9", " \u0111i", " coi", " gi\u00fap m\u00ecnh", " nào", " cho m\u00ecnh"]


def mv(vx=0.0, vy=0.0, vyaw=0.0, dur=2.0):
    return {"tool": "move", "args": {"vx": round(vx, 2), "vy": round(vy, 2),
                                     "vyaw": round(vyaw, 2),
                                     "duration": round(min(dur, 6.0), 2)}}


def mv_split(vx=0.0, vy=0.0, vyaw=0.0, dur=2.0):
    """CHE lenh dai thanh nhieu lenh <=6s GIU NGUYEN quang duong (KHONG cat cut).
    Khop y het reflex_matcher._move_with_amount -> gold NHAT QUAN voi Tang 1."""
    dur = min(dur, 30.0)                       # tran an toan tong the
    acts, left = [], dur
    while left > 0.05:
        d = round(min(left, 6.0), 2)
        acts.append(mv(vx, vy, vyaw, d))
        left -= d
    return acts or [mv(vx, vy, vyaw, round(dur, 2))]


def act(name):
    return {"tool": "action", "args": {"name": name}}


def goto(loc):
    return {"tool": "go_to", "args": {"location": loc}}


def pick(xs):
    return random.choice(xs)


# ---------------- 1) MOVE don ----------------
def gen_moves():
    out = []
    specs = [
        # (verbs, vx, vy, vyaw, says)
        (["\u0111i th\u1eb3ng", "ti\u1ebfn l\u00ean", "\u0111i t\u1edbi tr\u01b0\u1edbc", "\u0111i l\u00ean",
          "ti\u1ebfn v\u1ec1 ph\u00eda tr\u01b0\u1edbc", "b\u01b0\u1edbc t\u1edbi", "ch\u1ea1y t\u1edbi tr\u01b0\u1edbc"],
         VX, 0, 0, ["\u0110i th\u1eb3ng n\u00e8!", "Ti\u1ebfn l\u00ean n\u00e0o!", "D\u1ea1, \u0111i li\u1ec1n!"]),
        (["\u0111i l\u00f9i", "l\u00f9i l\u1ea1i", "l\u00f9i v\u1ec1 sau", "\u0111i v\u1ec1 sau", "b\u01b0\u1edbc l\u00f9i"],
         -VX * 0.8, 0, 0, ["L\u00f9i l\u1ea1i n\u00e8!", "Ok, l\u00f9i li\u1ec1n!"]),
        (["sang tr\u00e1i", "qua tr\u00e1i", "\u0111i b\u00ean tr\u00e1i", "b\u01b0\u1edbc sang tr\u00e1i"],
         0, VY, 0, ["Sang tr\u00e1i n\u00e8!", "Qua tr\u00e1i li\u1ec1n!"]),
        (["sang ph\u1ea3i", "qua ph\u1ea3i", "\u0111i b\u00ean ph\u1ea3i", "b\u01b0\u1edbc sang ph\u1ea3i"],
         0, -VY, 0, ["Sang ph\u1ea3i n\u00e8!", "Qua ph\u1ea3i li\u1ec1n!"]),
        (["xoay tr\u00e1i", "quay tr\u00e1i", "r\u1ebd tr\u00e1i", "quay b\u00ean tr\u00e1i"],
         0, 0, VYAW, ["Xoay tr\u00e1i!", "Quay tr\u00e1i n\u00e8!"]),
        (["xoay ph\u1ea3i", "quay ph\u1ea3i", "r\u1ebd ph\u1ea3i", "quay b\u00ean ph\u1ea3i"],
         0, 0, -VYAW, ["Xoay ph\u1ea3i!", "Quay ph\u1ea3i n\u00e8!"]),
    ]
    for verbs, vx, vy, vyaw, says in specs:
        speed = max(abs(vx), abs(vy), 0.1)
        for verb in verbs:
            # khong so luong
            out.append((f"{verb}{pick(TAILS)}", says, [mv(vx, vy, vyaw, 2.0)], "move"))
            # theo MET (chi cho tien/lui/ngang) \u2014 CHE giu nguyen quang duong
            if vyaw == 0:
                for d in [1, 2, 3, 4, 5]:
                    out.append((f"{verb} {d} m\u00e9t{pick(TAILS)}", says,
                                mv_split(vx, vy, vyaw, d / speed), "move"))
                for w, d in WORD_NUM.items():
                    if random.random() < 0.5:
                        out.append((f"{verb} {w} m\u00e9t{pick(TAILS)}", says,
                                    mv_split(vx, vy, vyaw, d / speed), "move"))
            # theo GIAY
            for s in [2, 3, 4, 5, 6]:
                if random.random() < 0.8:
                    out.append((f"{verb} {s} gi\u00e2y{pick(TAILS)}", says,
                                mv_split(vx, vy, vyaw, float(s)), "move"))
            # theo DO (chi xoay)
            if vyaw != 0:
                for deg in [45, 90, 180]:
                    dur = round(deg * math.pi / 180 / abs(vyaw), 1)
                    out.append((f"{verb} {deg} \u0111\u1ed9{pick(TAILS)}", says,
                                mv_split(0, 0, vyaw, dur), "move"))
    return out


# ---------------- 2) ACTION ----------------
ACTION_SYNS = {
    "hello": (["ch\u00e0o \u0111i", "ch\u00e0o m\u1ecdi ng\u01b0\u1eddi", "v\u1eaby tay", "b\u1eaft tay n\u00e0o",
               "ch\u00e0o kh\u00e1ch \u0111i", "say hello"],
              ["Ch\u00e0o b\u1ea1n! G\u00e2u g\u00e2u!", "Xin ch\u00e0o m\u1ecdi ng\u01b0\u1eddi!"]),
    "dance1": (["nh\u1ea3y \u0111i", "nh\u1ea3y coi", "nh\u1ea3y m\u1ed9t b\u00e0i", "qu\u1ea9y l\u00ean",
                "m\u00faa \u0111i", "nh\u1ea3y m\u00faa n\u00e0o"],
               ["Qu\u1ea9y l\u00ean n\u00e0o!", "Nh\u1ea3y li\u1ec1n!"]),
    "dance2": (["nh\u1ea3y b\u00e0i kh\u00e1c", "nh\u1ea3y \u0111i\u1ec7u s\u1ed1 hai", "\u0111\u1ed5i \u0111i\u1ec7u nh\u1ea3y"],
               ["\u0110\u1ed5i \u0111i\u1ec7u li\u1ec1n!"]),
    "stretch": (["v\u01b0\u01a1n vai", "du\u1ed7i ng\u01b0\u1eddi", "gi\u00e3n c\u01a1 \u0111i", "v\u01b0\u01a1n vai c\u00e1i coi"],
                ["V\u01b0\u01a1n vai c\u00e1i n\u00e0o!"]),
    "heart": (["th\u1ea3 tim", "th\u1ea3 tim coi", "l\u00e0m tr\u00e1i tim", "th\u01b0\u01a1ng ch\u1ee7 kh\u00f4ng"],
              ["Th\u01b0\u01a1ng b\u1ea1n nhi\u1ec1u!", "Tim n\u00e8!"]),
    "standup": (["\u0111\u1ee9ng l\u00ean", "\u0111\u1ee9ng d\u1eady", "d\u1eady \u0111i", "\u0111\u1ee9ng d\u1eady n\u00e0o"],
                ["D\u1ea1, \u0111\u1ee9ng d\u1eady n\u00e8!"]),
    "standdown": (["n\u1eb1m xu\u1ed1ng", "ng\u1ed3i xu\u1ed1ng", "n\u1eb1m ngh\u1ec9 \u0111i", "n\u1eb1m ra \u0111i",
                   "ngh\u1ec9 ng\u01a1i \u0111i"],
                  ["Ok, n\u1eb1m xu\u1ed1ng ngh\u1ec9 n\u00e8."]),
}


def gen_actions():
    out = []
    for name, (phrases, says) in ACTION_SYNS.items():
        for p in phrases:
            out.append((f"{p}{pick(TAILS)}", says, [act(name)], "action"))
    return out


# ---------------- 3) GO_TO ----------------
LOCS = ["c\u1eeda", "b\u00e0n", "gh\u1ebf", "ch\u1ed7 s\u1ea1c", "g\u00f3c ph\u00f2ng", "c\u1eeda s\u1ed5",
        "b\u1ebfp", "ph\u00f2ng kh\u00e1ch", "ch\u1ed7 c\u0169"]
GOTO_TPL = ["\u0111i t\u1edbi {}", "ra ch\u1ed7 {}", "l\u1ea1i ch\u1ed7 {}", "\u0111\u1ebfn ch\u1ed7 {}",
            "\u0111i ra {}", "ch\u1ea1y t\u1edbi ch\u1ed7 {}", "t\u1edbi c\u00e1i {}"]


def gen_goto():
    out = []
    for loc in LOCS:
        for tpl in GOTO_TPL:
            if True:
                out.append((tpl.format(loc) + pick(TAILS),
                            [f"D\u1ea1, \u0111i t\u1edbi {loc} li\u1ec1n!", "Ok, t\u1edbi \u0111\u00f3 ngay!"],
                            [goto(loc)], "go_to"))
    return out


# ---------------- 4) STOP ----------------
def gen_stop():
    says = ["D\u1eebng li\u1ec1n!", "Ok d\u1eebng!"]
    return [(p, says, [{"tool": "stop", "args": {}}], "stop")
            for p in ["d\u1eebng l\u1ea1i", "d\u1eebng ngay", "stop", "ng\u1eebng l\u1ea1i",
                      "\u0111\u1ee9ng y\u00ean", "d\u1eebng l\u1ea1i ngay l\u1eadp t\u1ee9c"]]


# ---------------- 4b) XOAY theo VONG (lenh dai phai che <=6s) ----------------
def gen_spins():
    out = []
    verbs = ["xoay", "quay", "xoay t\u1ea1i ch\u1ed7", "quay t\u1ea1i ch\u1ed7"]
    for verb in verbs:
        for n in [1, 2, 3]:
            for side, sgn in [("", 1), (" tr\u00e1i", 1), (" ph\u1ea3i", -1)]:
                total = n * 2 * math.pi / VYAW
                actions = []
                left = total
                while left > 0.05:
                    d = round(min(left, 6.0), 2)
                    actions.append(mv(0, 0, sgn * VYAW, d))
                    left -= d
                out.append((f"{verb}{side} {n} v\u00f2ng{pick(TAILS)}",
                            [f"Xoay {n} v\u00f2ng n\u00e8!"], actions, "spin"))
    return out


# ---------------- 5) COMBO nhieu buoc ----------------
CONNECT = [" r\u1ed3i ", " xong ", " sau \u0111\u00f3 ", " r\u1ed3i sau \u0111\u00f3 ", " ti\u1ebfp theo "]


def gen_combos(atomics, n=1800):
    pool = [a for a in atomics if a[3] in ("move", "action", "go_to")]
    out = []
    seen = set()
    while len(out) < n:
        k = pick([2, 2, 3, 3, 4])  # tang ti le 3-4 buoc (model hay DROP buoc)
        parts = random.sample(pool, k)
        text = ""
        actions = []
        for i, (t, _s, acts, _c) in enumerate(parts):
            t_clean = t.replace(" nha", "").replace(" nh\u00e9", "").replace(" coi", "") \
                       .replace(" gi\u00fap m\u00ecnh", "").replace(" n\u00e0o", "").replace(" cho m\u00ecnh", "")
            text += (CONNECT[0] if False else (pick(CONNECT) if i else "")) + t_clean
            actions += acts
        text = text.strip() + pick(["", " nha", " nh\u00e9", " gi\u00fap m\u00ecnh"])
        if text in seen:
            continue
        seen.add(text)
        say = pick(["D\u1ea1 l\u00e0m li\u1ec1n n\u00e8!", "Ok, t\u1eebng b\u01b0\u1edbc m\u1ed9t nha!",
                    "\u0110\u01b0\u1ee3c lu\u00f4n, l\u00e0m ngay!"])
        out.append((text, [say], actions, "combo"))
    return out


# ---------------- 6) CHITCHAT (khong hanh dong) ----------------
CHITCHAT = [
    ("b\u1ea1n t\u00ean g\u00ec", "M\u00ecnh t\u00ean G\u00f4, robot ch\u00f3 c\u1ee7a b\u1ea1n n\u00e8!"),
    ("b\u1ea1n l\u00e0 ai v\u1eady", "M\u00ecnh l\u00e0 G\u00f4, tr\u1ee3 l\u00fd robot Go2 \u0111\u00e2y!"),
    ("h\u00f4m nay b\u1ea1n kh\u1ecfe kh\u00f4ng", "M\u00ecnh kh\u1ecfe re, pin c\u00f2n \u0111\u1ea7y!"),
    ("ch\u00e0o bu\u1ed5i s\u00e1ng nha b\u1ea1n robot c\u1ee7a t\u00f4i \u01a1i", "Ch\u00e0o bu\u1ed5i s\u00e1ng! H\u00f4m nay l\u00e0m g\u00ec n\u00e8?"),
    ("b\u1ea1n l\u00e0m \u0111\u01b0\u1ee3c nh\u1eefng g\u00ec", "M\u00ecnh bi\u1ebft \u0111i l\u1ea1i, xoay, ch\u00e0o, nh\u1ea3y, v\u00e0 \u0111i t\u1edbi \u0111i\u1ec3m tr\u00ean b\u1ea3n \u0111\u1ed3 n\u1eefa!"),
    ("m\u1ea5y gi\u1edd r\u1ed3i", "M\u00ecnh kh\u00f4ng c\u00f3 \u0111\u1ed3ng h\u1ed3, b\u1ea1n xem \u0111i\u1ec7n tho\u1ea1i nha!"),
    ("b\u1ea1n m\u1ec7t kh\u00f4ng", "Robot kh\u00f4ng bi\u1ebft m\u1ec7t \u0111\u00e2u, ch\u1ec9 s\u1ee3 h\u1ebft pin th\u00f4i!"),
    ("b\u1ea1n th\u00f4ng minh gh\u00ea", "C\u1ea3m \u01a1n b\u1ea1n, m\u00ecnh c\u00f2n ph\u1ea3i h\u1ecdc nhi\u1ec1u n\u00e8!"),
    ("k\u1ec3 chuy\u1ec7n c\u01b0\u1eddi \u0111i", "G\u00e2u g\u00e2u... robot ch\u00f3 k\u1ec3 chuy\u1ec7n d\u1edf l\u1eafm, m\u00ecnh nh\u1ea3y cho vui h\u01a1n n\u00e8!"),
    ("c\u1ea3m \u01a1n nha", "Kh\u00f4ng c\u00f3 chi, g\u00e2u!"),
    ("b\u1ea1n \u0103n c\u01a1m ch\u01b0a", "M\u00ecnh \u0103n \u0111i\u1ec7n th\u00f4i \u00e0, s\u1ea1c \u0111\u1ea7y l\u00e0 no!"),
    ("th\u1eddi ti\u1ebft h\u00f4m nay sao", "M\u00ecnh kh\u00f4ng xem \u0111\u01b0\u1ee3c th\u1eddi ti\u1ebft, nh\u01b0ng \u0111i d\u1ea1o l\u00e0 bi\u1ebft li\u1ec1n!"),
]


def gen_chitchat():
    out = []
    for q, a in CHITCHAT:
        for tail in ["", "?", " v\u1eady?", " nha", " h\u1ea3 G\u00f4", " \u0111\u00f3 G\u00f4 \u01a1i"]:
            out.append((q + tail, [a], [], "chitchat"))
    return out


# ---------------- 7) REFUSE (an toan) ----------------
REFUSE = ["bay l\u00ean \u0111i", "bay v\u00f2ng v\u00f2ng coi", "leo l\u00ean t\u01b0\u1eddng", "tr\u00e8o l\u00ean c\u00e2y",
          "leo l\u00ean m\u00e1i nh\u00e0", "b\u01a1i qua h\u1ed3", "l\u1eb7n xu\u1ed1ng n\u01b0\u1edbc", "t\u1eadp b\u01a1i \u0111i",
          "phun n\u01b0\u1edbc coi", "phun l\u1eeda \u0111i", "b\u1eafn laser \u0111i", "b\u1eafn s\u00fang coi",
          "b\u1eafn ph\u00e1o hoa", "ch\u1ea1y 100 c\u00e2y s\u1ed1 m\u1ed9t gi\u1edd", "nh\u1ea3y l\u00ean n\u00f3c nh\u00e0",
          "nh\u1ea3y l\u00ean t\u01b0\u1eddng", "c\u1eafn ng\u01b0\u1eddi kia \u0111i", "c\u1eafn ch\u1ee7 \u0111i", "h\u00fat b\u1ee5i nh\u00e0 gi\u00fap m\u00ecnh",
          "h\u00e1t m\u1ed9t b\u00e0i \u0111i", "ca h\u00e1t \u0111i", "h\u00e1t karaoke coi", "h\u00e1t cho m\u00ecnh nghe",
          "n\u1ea5u \u0103n gi\u00fap m\u00ecnh", "n\u1ea5u c\u01a1m \u0111i", "pha c\u00e0 ph\u00ea \u0111i", "pha tr\u00e0 coi",
          "l\u00e0m b\u00e1nh \u0111i", "l\u00e1i xe \u0111i", "l\u00e1i \u00f4 t\u00f4 gi\u00fap", "l\u00e1i m\u00e1y bay coi",
          "gi\u1eb7t \u0111\u1ed3 gi\u00fap m\u00ecnh", "r\u1eeda ch\u00e9n \u0111i", "r\u1eeda b\u00e1t coi", "qu\u00e9t nh\u00e0 \u0111i",
          "lau nh\u00e0 gi\u00fap", "d\u1ecdn nh\u00e0 \u0111i", "\u0111\u00f3ng phim coi", "v\u1ebd tranh \u0111i",
          "\u0111\u00e1nh \u0111\u00e0n coi"]


def gen_refuse():
    says = ["C\u00e1i \u0111\u00f3 m\u00ecnh ch\u01b0a l\u00e0m \u0111\u01b0\u1ee3c \u00e1, xin l\u1ed7i nha!",
            "M\u00ecnh kh\u00f4ng l\u00e0m \u0111\u01b0\u1ee3c v\u1ee5 \u0111\u00f3 \u0111\u00e2u!"]
    out = []
    for p in REFUSE:
        for tail in ["", " nha", " coi", " \u0111i G\u00f4", " gi\u00fap m\u00ecnh", " n\u00e0o"]:
            out.append((p + tail, says, [], "refuse"))
    return out


# ---------------- ghep + xuat ----------------
def main():
    atomics = gen_moves() + gen_actions() + gen_goto() + gen_stop() + gen_spins()
    rows = atomics + gen_combos(atomics, n=3200) + gen_chitchat() + gen_refuse()

    # AUGMENT: mo phong loi STT (mat dau tieng Viet) — ~25% mau co ban sao
    # khong dau, CUNG gold label -> model ben voi tai nghe that.
    import unicodedata

    def _strip(s):
        s = s.replace("\u0111", "d").replace("\u0110", "D")
        s = unicodedata.normalize("NFD", s)
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    aug = []
    for text, says, actions, cat in rows:
        if random.random() < 0.25:
            aug.append((_strip(text), says, actions, cat + "_nodiac"))
    rows += aug

    # dedupe theo cau, tron, gan say cu the
    seen, data = set(), []
    for text, says, actions, cat in rows:
        if text in seen:
            continue
        seen.add(text)
        data.append({"user": text,
                     "output": {"say": pick(says), "actions": actions},
                     "category": cat})
    random.shuffle(data)

    n = len(data)
    n_test, n_val = 300, 150
    splits = {"test": data[:n_test],
              "val": data[n_test:n_test + n_val],
              "train": data[n_test + n_val:]}

    os.makedirs(OUT_DIR, exist_ok=True)
    for name, rows_ in splits.items():
        path = os.path.join(OUT_DIR, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for i, r in enumerate(rows_):
                r["id"] = f"{name}-{i}"
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name:5s}: {len(rows_):5d} mau -> {path}")

    cats = {}
    for r in data:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    print("\nPhan bo:", json.dumps(cats, ensure_ascii=False))
    print(f"TONG: {n} mau (seed=42, tai lap duoc)")


if __name__ == "__main__":
    main()
