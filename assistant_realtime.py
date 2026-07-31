#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assistant_realtime.py — GoVoice REALTIME (async + hanh dong that + safety).

Khac assistant_main.py o cho: hanh dong chay BAT DONG BO (thread rieng) nen
vong chinh VUA cho robot lam VUA nghe + STT + nghi cau ke (ky thuat SmolVLA).
Kem SafetyGuard kiem duyet moi lenh + EMERGENCY uu tien tuyet doi.

Luong 1 cau:
  audio -> STT -> [EMERGENCY?] -> Reflex/LLM -> guard -> async queue -> robot lam
  (TTS noi song song voi luc robot dang lam)

CHAY:
  # Test tren laptop (robot gia, in [DRY]):
  python3 assistant_realtime.py --mode voice
  # Tren Jetson dieu khien robot THAT:
  python3 assistant_realtime.py --mode voice --real
  # Go phim thay vi noi (test logic):
  python3 assistant_realtime.py --mode text --real
"""

import argparse
import threading
import collections
import queue
import re
import time

import yaml

from reflex_matcher import ReflexMatcher, norm
from combo_matcher import ComboMatcher, DEFAULT_LOCATIONS
from robot_tools import RobotTools
from llm_planner import LLMPlanner
from safety_guard import SafetyGuard
from async_executor import AsyncExecutor

EMERGENCY_WORDS = ("dung lai", "dung ngay", "stop", "ngung", "khan cap")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Tu tieng Viet RAT HAY GAP — dat ten cho trung mot trong nhung tu nay la hong:
# MC noi "hai ban CO moi chan khong" ma cho ten "Co" thi no tuong duoc goi.
_TU_PHO_BIEN = {
    "co", "con", "cai", "cua", "cho", "la", "ma", "na", "ba", "ta", "ra", "va",
    "di", "de", "do", "da", "den", "duoc", "khong", "nay", "no", "moi", "mi",
    "minh", "may", "toi", "ban", "the", "gi", "sao", "hai", "mot", "roi", "voi",
}


def _canh_bao_ten(names):
    xau = [w for w in names if w in _TU_PHO_BIEN]
    if xau:
        print(f"\u26a0\ufe0f  [danh tinh] ten/bi danh {xau} TRUNG tu tieng Viet thong dung "
              f"-> cho se tuong bi goi khi MC noi tu do. Doi ten khac di "
              f"(vd: Go, Mun, Bap, Tep).")


def _tu(text):
    return norm(text).split()


def _chuoi_chung_dai_nhat(a, b):
    """Do dai chuoi TU LIEN TIEP dai nhat vua co trong a vua co trong b."""
    if not a or not b:
        return 0
    truoc = [0] * (len(b) + 1)
    tot = 0
    for i in range(1, len(a) + 1):
        nay = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                nay[j] = truoc[j - 1] + 1
                if nay[j] > tot:
                    tot = nay[j]
        truoc = nay
    return tot


def _trung_loi_minh(text, da_noi, toi_thieu=3, cua_so_s=20.0):
    """Cau vua nghe co phai LOI CUA CHINH GO vong lai khong?

    Vi sao can lop nay du da co mute: mute la co che THOI GIAN, ma do tre ra loa
    qua WebRTC khong co dinh (Piper nhanh/cham, hang doi loa, mang). Ho 0.2s la du
    lot mot manh -> Go tra loi -> lai vong tiep. Da va phan thoi gian 3 lan van sot.
    Lop nay KHONG phu thuoc thoi gian.

    Do bang CHUOI TU LIEN TIEP, khong phai tap tu. Ly do da tra gia: dem theo tap
    tu thi "BAN LA AI" trung 67% voi loi Go (vi chung hu tu 'ban','la') -> CHAN
    NHAM dung cau quan trong nhat luc phong van. Echo thi lap DUNG THU TU, con
    cau hoi that chi trung vai hu tu ROI RAC -> chuoi lien tiep phan biet duoc.
    """
    t = _tu(text)
    if len(t) < toi_thieu:
        return None
    bay_gio = time.time()
    for luc, tu_da_noi in da_noi:
        if bay_gio - luc > cua_so_s:
            continue
        n = _chuoi_chung_dai_nhat(t, tu_da_noi)
        if n >= toi_thieu:
            return n
    return None


def _has_word(norm_text, words):
    """Co tu nao trong `words` xuat hien nhu MOT TU RIENG trong cau da chuan hoa?

    Dung \\b thay vi `in` vi ten con cho thuong rat ngan ("go", "mi") va rat de
    nam lot ben trong tu khac ("con", "mien", "minh") -> goi nham con kia.
    """
    return any(re.search(r"\b" + re.escape(w) + r"\b", norm_text) for w in words)


class GoVoiceRT:
    def __init__(self, cfg, force_real=False, no_tts=False):
        self.cfg = cfg
        r = cfg.get("robot", {})
        dry = False if force_real else bool(r.get("dry_run", True))
        self.robot = RobotTools(
            dry_run=dry, iface=r.get("iface", "eth0"),
            waypoints_file=r.get("waypoints_file"),
            max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
            max_vyaw=r.get("max_vyaw", 1.0),
            max_duration=r.get("max_duration", 6.0),
            max_step_m=r.get("max_step_m", 0.5),
            motion_mode=r.get("motion_mode"))
        self.guard = SafetyGuard(
            max_vx=r.get("max_vx", 0.6), max_vy=r.get("max_vy", 0.4),
            max_vyaw=r.get("max_vyaw", 1.0),
            max_duration=r.get("max_duration", 6.0),
            max_step_m=r.get("max_step_m", 0.5),
            require_stand_before_move=r.get("require_stand_before_move", True))
        self.executor = AsyncExecutor(self.robot, self.guard, on_event=print)

        # ---- DANH TINH & CONG GOI TEN (dung khi bieu dien NHIEU con cho) ----
        _a = cfg.get("assistant", {}) or {}
        self.robot_name = _a.get("name", "G\u00f4")
        self.require_name = bool(_a.get("require_name", False))
        self.wake_names = [norm(w) for w in
                           (_a.get("wake_names") or [self.robot_name])]
        self.other_names = [norm(w) for w in (_a.get("other_names") or [])]
        self.floor_hold_s = float(_a.get("floor_hold_s", 12.0))
        self._floor_until = 0.0
        if self.require_name:
            _canh_bao_ten(self.wake_names + self.other_names)
            print(f"\U0001F9ED [danh tinh] toi la '{self.robot_name}' | "
                  f"goi toi bang {self.wake_names} | im khi nghe {self.other_names} "
                  f"| giu luot {self.floor_hold_s:.0f}s")

        self.reflex = ReflexMatcher()
        # TANG 1.5: che combo theo tu noi -> giai tung ve bang luat (xem combo_matcher.py).
        # Dia diem go_to = waypoint tren map (neu co) gop voi danh sach mac dinh.
        import os
        wp = []
        try:
            wpf = r.get("waypoints_file")
            if wpf and os.path.exists(wpf):
                with open(wpf, encoding="utf-8") as _f:
                    wp = list((yaml.safe_load(_f) or {}).keys())
        except Exception:
            wp = []
        self.combo = ComboMatcher(locations=list(DEFAULT_LOCATIONS) + wp)
        # Bo sua chinh ta STT (gated) — nap them ten dia diem lam tu vung.
        try:
            from text_normalizer import TextNormalizer
            self.normalizer = TextNormalizer(
                extra_vocab=list(DEFAULT_LOCATIONS) + wp)
        except Exception as e:
            print(f"[warn] khong nap duoc text_normalizer: {e}")
            self.normalizer = None
        # TANG 1.7: TRA CUU NGU NGHIA (knowledge.yaml) — tra loi cau giao tiep tuc thi,
        # khong can LLM. Fuzzy nen noi khac di/thieu dau van hieu. Xem faq_matcher.py.
        try:
            from faq_matcher import FaqMatcher
            fcfg = cfg.get("faq", {}) or {}
            kb = fcfg.get("knowledge_file") or os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "knowledge.yaml")
            self.faq = FaqMatcher(kb, threshold=fcfg.get("threshold", 0.55))
            if not self.faq.ready():
                self.faq = None
        except Exception as e:
            print(f"[warn] khong nap duoc faq_matcher: {e}")
            self.faq = None
        l = cfg.get("llm", {})
        import os
        self.llm = LLMPlanner(
            endpoint=l.get("endpoint", "http://127.0.0.1:8080"),
            grammar_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "grammar.gbnf"),
            temperature=l.get("temperature", 0.2),
            n_predict=l.get("n_predict", 200),
            timeout_s=l.get("timeout_s", 60),
            use_fewshot=l.get("fewshot", False))

        t = cfg.get("tts", {})
        if no_tts:
            t = dict(t); t["enabled"] = False
        from tts_engine import TTS
        self.tts = TTS(t.get("voice"), enabled=t.get("enabled", True),
                       output=t.get("output", "local"),
                       wav_dir=t.get("wav_dir", "tts_out"),
                       piper_bin=t.get("piper_bin"),
                       robot_port=t.get("speaker_port", 17891),
                       pa_host=t.get("pa_host"),          # loa hoi truong qua laptop
                       pa_port=t.get("pa_port", 17892))
        self.mute = threading.Event()
        # Bien mute chong TU NGHE CHINH MINH. Loa qua WebRTC (output robot/pa) tre
        # ~1.4s moi ra tieng -> phai bu; loa cam thang may thi gan nhu tuc thi.
        # Do lai bat cu luc nao:  python3 test_echo_delay.py
        _out = (t.get("output") or "local").lower()
        _xa = _out in ("robot", "pa", "robot+pa")
        self.mute_lead_s = float(t.get("mute_lead_s", 1.3 if _xa else 0.1))
        self.mute_tail_s = float(t.get("mute_tail_s", 0.4 if _xa else 0.15))
        # mute theo HAN CHOT, khong phai "ai sleep xong thi clear".
        # Truoc day moi cau noi la 1 thread rieng cung set/clear chung 1 Event:
        # cau A ngan clear mute TRONG LUC cau B van dang phat -> mic nghe duoi cau
        # B -> STT ra manh 1-2 chu -> tra loi tiep -> CHAY LONG. Gio moi cau chi
        # DAY han chot ra xa (max), va CHI MOT luong canh duoc phep clear.
        self._mute_until = 0.0
        # Loa robot co HANG DOI phat (go2_tts_speaker.TTSTrack.q): cac cau xep hang
        # phat noi tiep nhau. Neu tinh mute tu luc GUI thi khi cau don lai, tieng
        # thuc su ra RAT TRE so voi luc gui -> mute het han truoc khi tieng ra ->
        # mic nghe chinh minh -> tra loi -> don them -> "cang ve sau cang nhieu".
        # Bien nay theo doi loa du kien ranh luc nao.
        self._speaker_free_at = 0.0
        self._mute_lock = threading.Lock()
        self._da_noi = collections.deque(maxlen=8)   # (luc, tap tu) cac cau Go vua noi
        self._listener = None          # gan trong run_voice, de xem mic im chua
        self.mute_quiet_frames = int(t.get("mute_quiet_frames", 8))   # 8 x 30ms = 240ms
        self.mute_max_extra = float(t.get("mute_max_extra_s", 6.0))
        self._say_q = queue.Queue()
        threading.Thread(target=self._say_worker, daemon=True).start()
        threading.Thread(target=self._mute_watch, daemon=True).start()

        if not self.llm.health():
            print("\u26a0\ufe0f  llama-server chua chay -> cau phuc tap se loi "
                  "(lenh don van chay qua Reflex).")
        print(f"[robot] che do: {'THAT (--real)' if not dry else 'GIA (dry-run)'}")

    def _hold_mute(self, seconds):
        """Giu mic CAM it nhat `seconds` giay nua (chi noi dai ra, khong bao gio rut ngan)."""
        with self._mute_lock:
            self._mute_until = max(self._mute_until, time.time() + float(seconds))
            self.mute.set()

    def _mute_watch(self):
        """Mo mic lai khi (a) het han theo dong ho VA (b) mic THUC SU da im.

        Chi dua vao dong ho la khong du: tre ra loa qua WebRTC thay doi theo tai
        CPU/hang doi/mang, ho 0.2s la lot mot manh roi kich ca chuoi tu noi. Dieu
        kien (b) do TRUC TIEP tin hieu vao -> mo mic dung luc tieng het, bat ke
        tre bao nhieu. Van co tran `mute_max_extra` de khong bao gio cam vinh vien
        (vd phong on len that thi (b) khong bao gio thoa).
        """
        while True:
            time.sleep(0.05)
            if not self.mute.is_set():
                continue
            bay_gio = time.time()
            if bay_gio < self._mute_until:
                continue
            l = self._listener
            im = getattr(l, "quiet_frames", 999) if l is not None else 999
            qua_lau = bay_gio >= self._mute_until + self.mute_max_extra
            if im >= self.mute_quiet_frames or qua_lau:
                if qua_lau and im < self.mute_quiet_frames:
                    print(f"   \u23f1\ufe0f  mo mic sau {self.mute_max_extra:.0f}s cho them "
                          f"(mic chua im — phong on len?)")
                self.mute.clear()

    def _speak_async(self, say):
        """Xep cau vao HANG DOI NOI — mot luong duy nhat phat lan luot.

        Truoc day moi cau tao MOT THREAD rieng. Khi Go tra loi don dap (nhat la luc
        bi nhieu kich), 4-5 tien trinh Piper chay SONG SONG tren 6 nhan Jetson ->
        moi cai cham han -> tieng ra rai rac, tre ca chuc giay, va mo hinh hang doi
        loa tinh sai -> mute het han truoc khi tieng ra -> nghe chinh minh.
        Do duoc: mo hinh bao loa ranh luc +18.9s, tieng THAT keo toi +33.4s.

        Nay: 1 luong, tong hop tuan tu -> nhanh hon VA mute tinh dung.
        """
        if not say:
            return
        self._da_noi.append((time.time(), _tu(say)))
        # Don qua 2 cau -> chac chan dang bi kich lien tuc (thuong do nhieu/echo).
        # Bo cau CU, giu cau MOI: khan gia chi quan tam cau tra loi gan nhat.
        while self._say_q.qsize() >= 2:
            try:
                bo = self._say_q.get_nowait()
                print(f"   \u23ed\ufe0f  bo cau cu chua kip noi: {bo[:32]!r}")
            except queue.Empty:
                break
        self._say_q.put(say)

    def _say_worker(self):
        while True:
            say = self._say_q.get()
            self._hold_mute(2.0)              # cam trong luc Piper tong hop
            try:
                self.tts.speak(say)
            except Exception as e:
                print(f"[tts] loi: {e}")
            finally:
                # Tinh theo HANG DOI cua loa, khong phai luc gui:
                #   bat dau phat = max(gui + tre_ra_loa, luc loa xong cau truoc)
                dur = getattr(self.tts, "last_audio_s", 0.0) or 0.0
                now = time.time()
                with self._mute_lock:
                    bat_dau = max(now + self.mute_lead_s, self._speaker_free_at)
                    self._speaker_free_at = bat_dau + dur
                    cho = self._speaker_free_at + self.mute_tail_s - now
                    ton = bat_dau - now - self.mute_lead_s
                if ton > 0.5:
                    print(f"   \U0001F50A loa con {ton:.1f}s hang doi -> giu mic cam them")
                self._hold_mute(cho if dur > 0 else self.mute_lead_s + 0.5)

    def _name_gate(self, text):
        """CO NHIEU CON CHO: chi tra loi khi DUOC GOI TEN.

        Tra ve text DA BO ten, hoac None neu cau nay khong danh cho minh.

        Vi sao can: 2 con dung canh nhau tren san khau, ca hai cung nghe mot cau
        hoi -> khong co cong nay thi hai con noi chong len nhau, khan gia khong
        biet con nao dang tra loi.

        Luat:
          - Goi ten minh        -> nhan LUOT NOI, giu `floor_hold_s` giay
          - Dang giu luot       -> cau sau KHOI goi ten ("the con ban thi sao?")
          - Goi ten con KIA     -> nha luot NGAY, im
          - Khong ten, het luot -> im lang bo qua
        """
        if not self.require_name:
            return text
        n = norm(text)
        # KHOP THEO RANH GIOI TU, khong phai chuoi con: ten ngan nhu "co" nam
        # ben trong "con/cong/cong viec" -> khong bat vay thi con kia bi goi nham.
        hit_self = _has_word(n, self.wake_names)
        hit_other = _has_word(n, self.other_names)

        if hit_other and not hit_self:
            if time.time() < self._floor_until:
                print("   \U0001F91D nhuong luot cho con kia")
            self._floor_until = 0.0
            return None

        if hit_self:
            self._floor_until = time.time() + self.floor_hold_s
            out = text                      # bo ten khoi cau, khoi lam nhieu dinh tuyen
            for w in sorted(self.wake_names, key=len, reverse=True):
                m = re.search(r"\b" + re.escape(w) + r"\b", norm(out))
                if m:
                    out = out[:m.start()] + out[m.end():]
                    break
            out = re.sub(r"^\s*[,\.]?\s*(oi|\u01a1i|a|\u00e0|\u1ea1|nay|n\u00e0y|ne|n\u00e8|e|\u00ea)\b[\s,\.]*",
                         "", out.strip(), flags=re.IGNORECASE)
            out = out.strip(" ,.!?")
            if not out:                     # chi goi ten khong -> da loi cho co duyen
                self._speak_async("D\u1ea1, %s nghe \u0111\u00e2y!" % self.robot_name)
                return None
            return out

        if time.time() < self._floor_until:
            return text                     # dang giu luot -> cho hoi noi tiep

        return None                         # khong phai goi minh -> im

    def process(self, text, stt_ms=0.0):
        t0 = time.time()
        text = (text or "").strip()
        if not text:
            return

        # 0) EMERGENCY — uu tien tuyet doi, chen ngang moi thu dang chay
        if any(w in norm(text) for w in EMERGENCY_WORDS):
            self.executor.emergency_stop()
            self._speak_async("D\u1eebng li\u1ec1n!")
            return

        # 0a2) CHAN ECHO THEO NOI DUNG: cau nghe duoc trung tu voi cai Go VUA NOI
        # -> chac chan la loa vong lai mic, bo thang. Doc lap voi mute (co che thoi
        # gian) nen bat duoc ca truong hop mute ho vai phan muoi giay.
        # CHI kiem tra trong cua so loa CON DANG / VUA phat xong. Echo la hien tuong
        # VAT LY nen bi chan trong thoi gian; ngoai cua so do thi cau trung tu la
        # nguoi noi that. Khong co rang buoc nay thi lenh that nhu "di toi cho cua
        # roi chao" bi chan nham vi trung "di toi cho" trong loi Go noi truoc do.
        _tl = (_trung_loi_minh(text, self._da_noi)
               if time.time() <= self._speaker_free_at + 3.0 else None)
        if _tl is not None:
            print(f"   \U0001F501 bo echo (trung {_tl} tu lien tiep voi loi Go vua noi): {text!r}")
            return

        # 0b) CONG GOI TEN — chi bat khi co NHIEU con cho (assistant.require_name)
        text = self._name_gate(text)
        if text is None:
            return

        # Dinh tuyen: 1.5) Combo (che + luat) -> 1) Reflex don -> 2) LLM
        r = self.combo.match(text) or self.combo.resolve_goto(text)
        if r is None:
            r = self.reflex.match(text)
        # 1c) TRA CUU NGU NGHIA (fuzzy): cau giao tiep chung -> tra loi tuc thi (khong LLM).
        # Dat TRUOC sua-chinh-ta vi robust hon (tranh normalizer bien 'bieu dien'->'bieu tien'
        # roi hieu nham thanh lenh 'di thang').
        if r is None and self.faq is not None:
            r = self.faq.match(text)
            if r is not None:
                print(f"   \U0001F50E FAQ (khop {r.get('_score', 0):.2f})")
        # 1b) SUA CHINH TA GATED: neu VAN truot, thu ban da-sua roi dinh tuyen LAI;
        # CHI dung neu no thanh 1 lenh that -> cau tro chuyen khong bao gio bi hong.
        if r is None and self.normalizer is not None:
            fixed = self.normalizer.correct(text)
            if fixed != text:
                r2 = (self.combo.match(fixed) or self.combo.resolve_goto(fixed)
                      or self.reflex.match(fixed))
                if r2 is not None:
                    print(f"   ✎ sua chinh ta: {text!r} -> {fixed!r}")
                    r = r2

        # CHAN MANH NHIEU — dat DUNG day, sau khi moi tang luat da thu.
        # Y tuong: nhieu che ra manh 1-2 chu ("DAY", "EM", "DUNG ROI") thi KHONG
        # tang luat nao nhan ra ca; con lenh that du ngan ("chao", "trong chuoi")
        # thi Reflex/Combo/FAQ nhan duoc. Nen: ngan + khong ai nhan = nhieu -> bo,
        # KHONG day sang LLM (LLM luon bia ra mot cau tra loi, roi Go phat tieng,
        # tieng vong ve mic -> mot manh nhieu du khoi dong ca chuoi tu noi).
        # Khong dung danh sach tu vi bo dau lam "dung"(dung lai) == "dung"(dung roi).
        if r is None and len(norm(text).split()) < 3:
            print(f"   \U0001F507 bo qua manh nhieu: {text!r}")
            return

        from_llm = r is None
        if r is None:
            try:
                r = self.llm.plan(text)
                tag = f"LLM {r.get('_ms', 0):.0f}ms"
            except Exception:
                r = {"say": "M\u00ecnh ch\u01b0a k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c b\u1ed9 n\u00e3o, b\u1ea1n th\u1eed l\u1ea1i nh\u00e9?",
                     "actions": []}
                tag = "LLM loi (server?)"
        else:
            tag = f"Reflex:{r.get('intent')}"

        say = r.get("say", "")
        actions = r.get("actions", []) or []
        # 2b) KIEM CHUNG symbolic: bo action LLM "bia" (chi loc nhanh LLM)
        if from_llm and actions:
            from plan_verifier import verify_plan
            actions, dropped = verify_plan(text, actions)
            for d in dropped:
                print(f"   \U0001F9F9 verifier b\u1ecf: {d}")
        print(f"\U0001F436 G\u00f4: {say}   [{tag}]")

        # 3) NOI song song + DAY hanh dong vao hang doi async (khong chan)
        self._speak_async(say)
        self.executor.enqueue(actions)
        plan_ms = (time.time() - t0) * 1000 + stt_ms
        print(f"   \u23F1\ufe0f  STT {stt_ms:.0f} + len ke hoach {plan_ms - stt_ms:.0f} "
              f"= {plan_ms:.0f}ms (robot dang lam o thread rieng)")

    # ---------- 2 che do ----------
    def run_text(self):
        print("=" * 60)
        print(" GoVoice REALTIME — TEXT (go 'thoat' de dung)")
        print("=" * 60)
        while True:
            try:
                text = input("B\u1ea1n: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if norm(text) in ("thoat", "exit", "quit"):
                break
            self.process(text)

    def run_voice(self):
        from audio_io import get_listener
        s = self.cfg.get("stt", {})
        # backend "transducer" (MOI, NHANH ~15-150ms): zipformer-VI qua sherpa-onnx + hotwords.
        # backend mac dinh "whisper": PhoWhisper qua faster-whisper (~1.8s).
        if (s.get("backend") or "whisper").lower() == "transducer":
            from stt_transducer import STTTransducer
            stt = STTTransducer(
                s.get("transducer_model",
                      "stt_streaming_test/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"),
                hotwords_file=s.get("hotwords_file"),
                hotwords_score=s.get("hotwords_score", 3.0),
                num_threads=s.get("num_threads", 4),
                use_gpu=(s.get("device", "cpu") == "cuda"))
        else:
            from stt_engine import STT
            stt = STT(model=s.get("model", "small"),
                      fallback_model=s.get("fallback_model", "small"),
                      device=s.get("device", "cuda"),
                      compute_type=s.get("compute_type", "int8_float16"),
                      language=s.get("language", "vi"),
                      beam_size=s.get("beam_size", 5),
                      initial_prompt=s.get("initial_prompt"))
        listener = get_listener(self.cfg.get("audio", {}), mute=self.mute)
        self._listener = listener      # bo canh mute doc listener.quiet_frames
        print("=" * 60)
        print(" GoVoice REALTIME — VOICE (Ctrl+C de dung)")
        print(" Noi 'dung lai' bat ky luc nao = phanh khan cap")
        print("=" * 60)
        # TACH MIC RA LUONG RIENG. Truoc day mic + STT + LLM chung 1 luong:
        # luc LLM nghi (1-2.5s) mic KHONG duoc doc -> bo dem ALSA tran -> stream
        # chet -> "mic treo" + MAT TU. Gio luong nay CHI doc mic (lien tuc, khong
        # bao gio bi chan) roi day cau vao hang doi; luong chinh lay ra STT+LLM.
        import queue
        q = queue.Queue(maxsize=20)

        def _capture():
            try:
                for audio in listener.listen():
                    try:
                        q.put_nowait(audio)
                    except queue.Full:          # xu ly khong kip -> bo cau CU, giu cau MOI
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            q.put_nowait(audio)
                        except queue.Full:
                            pass
            except Exception as e:
                print(f"[mic] luong doc dung: {e}")
            finally:
                q.put(None)                     # bao luong chinh thoat

        threading.Thread(target=_capture, daemon=True).start()

        while True:
            audio = q.get()
            if audio is None:
                break
            text, stt_ms = stt.transcribe(audio)
            if not text:
                continue
            print(f"\n\U0001F5E3\ufe0f  Nghe: {text}")
            self.process(text, stt_ms=stt_ms)


def main():
    p = argparse.ArgumentParser(description="GoVoice REALTIME (async+safety)")
    p.add_argument("--mode", choices=["text", "voice"], default="text")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--real", action="store_true", help="dieu khien robot THAT")
    p.add_argument("--no-tts", action="store_true")
    a = p.parse_args()
    cfg = load_config(a.config)
    gv = GoVoiceRT(cfg, force_real=a.real, no_tts=a.no_tts)
    try:
        if a.mode == "voice":
            gv.run_voice()
        else:
            gv.run_text()
    except KeyboardInterrupt:
        pass
    finally:
        gv.executor.emergency_stop()
        gv.executor.shutdown()
        print("\nTam biet!")


if __name__ == "__main__":
    main()
