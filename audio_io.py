#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_io.py — "ONG TAI" cua GoVoice: lay audio mic + tu cat thanh tung CAU.

2 backend (chon trong config.yaml -> audio.backend):
  "local" — mic laptop qua sounddevice (giai doan test tren may)
  "udp"   — nhan PCM 16kHz mono int16 qua UDP tu go2_audio_bridge.py
            (bridge lay tu MIC ROBOT qua WebRTC) -> dung cho deploy len Jetson

VAD (webrtcvad) cat cau:
  - frame 30ms; bat dau ghi khi >=60% frame gan day la giong noi
  - ket thuc cau sau ~450ms im lang
  - cau < min_utterance_s bi bo (tieng on lat nhat)

KHU NHIEU AI (tuy chon, xem denoiser.py) — bat bang config `audio.denoise`:
  mic -> [GTCRN/RNNoise] -> VAD/noise-gate -> STT
  Dat TRUOC VAD co chu dich: nen nhieu bi keo sat 0 nen cong khong con lot
  tieng on -> het "che loi" khi im lang. Dac biet an cho MIC ROBOT (backend udp)
  vi tieng quat/dong co/ban chan la nhieu on dinh, dung so truong cua GTCRN.
"""

import collections
import socket

import numpy as np

SR = 16000
FRAME_MS = 30
FRAME_SAMPLES = SR * FRAME_MS // 1000      # 480 samples
FRAME_BYTES = FRAME_SAMPLES * 2            # int16 -> 960 bytes

# Card noi bo cua Jetson — KHONG phai mic USB, auto-detect phai bo qua
_INTERNAL_HINTS = ("APE", "HDA", "tegra", "pulse", "default", "sysdefault",
                   "dmix", "surround", "front", "iec958", "spdif", "hdmi",
                   "lavrate", "samplerate", "speexrate", "upmix", "vdownmix")


def resolve_input_device(device):
    """Doi config audio.input_device -> device dung duoc cho sounddevice.

    - "auto" (hoac ten khong tim thay): quet tat ca input, chon mic USB dau tien
      (bo qua card noi bo APE/HDA/pulse...). Ho tro cam mic BAT KY (CS202 jack 3.5
      hay mic Type-C moi) ma khong phai sua config.
    - None: mic mac dinh he thong.
    - Ten/so hop le: dung truc tiep.
    """
    import sounddevice as sd

    def _scan():
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) <= 0:
                continue
            name = d.get("name", "")
            if any(h.lower() in name.lower() for h in _INTERNAL_HINTS):
                continue
            return i, name
        return None, None

    def _auto():
        import time
        # THU LAI: neu vua cam mic USB thi no can vai giay de enumerate xong.
        # Doi & lam moi danh sach thiet bi toi ~6s -> khoi phai canh thoi gian khi cam.
        for attempt in range(7):
            if attempt > 0:
                time.sleep(1.0)
                try:
                    sd._terminate(); sd._initialize()      # lam moi danh sach thiet bi
                except Exception:
                    pass
            i, name = _scan()
            if i is not None:
                print(f"\U0001F3A4 [auto] chon mic: [{i}] {name!r}")
                return i
            if attempt == 0:
                print("⏳ [auto] chua thay mic USB — doi mic enumerate (toi 6s)...")
        print("⚠️  [auto] KHONG thay mic USB nao — dung mic mac dinh he thong")
        return None

    if device is None:
        return None
    if isinstance(device, str) and device.strip().lower() == "auto":
        return _auto()
    try:
        sd.query_devices(device, "input")      # ten/so co ton tai khong?
        return device
    except Exception:
        print(f"⚠️  khong thay mic {device!r} -> tu dong tim mic USB khac...")
        return _auto()


def ensure_capture_gain(device, percent=25):
    """Dat gain thu cua card USB ve muc chuan (mac dinh 25%).

    Hub/mic USB hay reset gain sau khi rut cam. Qua THAP (15%) -> mic gan cam,
    VAD kich nhieu ao. Qua CAO (100% = +32dB tren CS202) -> vo tieng/qua tai,
    VAD truot cau noi that. 25% la diem ngot do thuc te 2026-07-04.
    Goi truoc khi mo stream; loi thi bo qua (best-effort). Chinh bang
    config audio.mic_gain.
    """
    import re, subprocess
    import sounddevice as sd
    try:
        name = sd.query_devices(device, "input")["name"]
        m = re.search(r"hw:(\d+)", name)
        if not m:
            return
        card = m.group(1)
        for ctl in ("Mic", "Capture"):
            r = subprocess.run(["amixer", "-c", card, "sset", ctl,
                                f"{percent}%", "unmute"],
                               capture_output=True, timeout=5)
            if r.returncode == 0:
                print(f"🎚️  gain thu card {card} ('{ctl}') -> {percent}%")
                return
    except Exception:
        pass


def chuan_hoa_do_to(audio, target_rms=0.06, peak_ceiling=0.95, max_gain=8.0,
                    min_gain=0.3):
    """Keo CA CAU len mot muc do to CO DINH, KHONG lam vo tieng.

    Vi sao khong dung `denoise.gain` co dinh: he so co dinh la canh bac — de thap
    thi cau noi xa qua nho, de cao thi cau noi gan bi VO TIENG (do: gain 2.2 ->
    bat 0/4 cau). O day tinh he so RIENG cho tung cau:

        g = min( muc_muon / RMS_that ,  tran / dinh_that ,  max_gain )

    Ve tri: goi SAU khi da cat xong cau (khong phai tung khung) -> KHONG dung toi
    nen nhieu ma cong bien do dang bam theo, nen moi tinh chinh cong van con nguyen.
    Ve chong vo: gioi han theo DINH that cua cau nen ve nguyen tac khong the clip;
    con chen them limiter mem (tanh) o cuoi cho chac.
    """
    if audio is None or audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(audio)))
    if rms <= 1e-6 or peak <= 1e-6:
        return audio
    g = min(target_rms / rms, peak_ceiling / peak, max_gain)
    g = max(g, min_gain)
    y = audio * g
    over = np.abs(y) > peak_ceiling            # gan nhu khong bao gio xay ra
    if np.any(over):                           # limiter MEM: uon cong thay vi cat phang
        y[over] = np.sign(y[over]) * (
            peak_ceiling + (1.0 - peak_ceiling) *
            np.tanh((np.abs(y[over]) - peak_ceiling) / max(1.0 - peak_ceiling, 1e-6)))
    return y.astype(np.float32)


class _VadSegmenter:
    """Nhan tung frame 30ms (bytes int16) -> tra ve ca CAU (np.float32) khi xong."""

    def __init__(self, aggressiveness=2, max_s=12, min_s=0.45,
                 silence_end_frames=9, trigger_ratio=0.6, ring=10,
                 noise_gate=0, noise_gate_factor=3.0, norm=None):
        import webrtcvad
        self.norm = norm            # dict tham so chuan hoa do to; None = tat
        self.vad = webrtcvad.Vad(int(aggressiveness))
        self.max_frames = int(max_s * 1000 / FRAME_MS)
        self.min_frames = int(min_s * 1000 / FRAME_MS)
        self.silence_end = silence_end_frames
        self.trigger_ratio = trigger_ratio
        # CONG BIEN DO THICH NGHI (adaptive): chan tieng on nen lam webrtcvad kich
        # nham -> STT 'che loi' khi im lang. noise_gate = san RMS TOI THIEU tuyet doi;
        # gate_factor = giong phai to hon NEN nhieu (uoc luong lien tuc) bao nhieu lan
        # moi tinh la 'noi'. Nguong that = max(noise_gate, noise_floor * gate_factor).
        self.noise_gate = float(noise_gate)
        self.gate_factor = float(noise_gate_factor)
        self.noise_floor = 60.0             # uoc luong muc on nen, tu cap nhat theo phong
        self.ring = collections.deque(maxlen=ring)
        self.recording = False
        self.buf = []
        self.silence = 0

    def reset(self):
        """Xoa trang thai dang ghi (dung khi mute mic luc Go noi)."""
        self.ring.clear()
        self.recording = False
        self.buf = []
        self.silence = 0

    def feed(self, frame_bytes: bytes):
        if len(frame_bytes) != FRAME_BYTES:
            return None
        try:
            raw_speech = self.vad.is_speech(frame_bytes, SR)
        except Exception:
            raw_speech = False
        # Do do to (RMS) frame nay
        s = np.frombuffer(frame_bytes, dtype=np.int16)
        rms = float(np.sqrt(np.mean(s.astype(np.float32) ** 2))) if s.size else 0.0
        # Uoc luong NEN nhieu tu cac frame KHONG phai giong: len NHANH, xuong CHAM
        # -> nguong tu dong bam theo do on that su cua phong luc do.
        if not raw_speech:
            # Noise floor bam muc YEN: xuong NHANH (0.3) de settle ngay trong phong yen,
            # len CHAM (0.05) de giong/tieng dong ngan khong lam phong nguong -> chan giong.
            a = 0.05 if rms > self.noise_floor else 0.3
            self.noise_floor = (1.0 - a) * self.noise_floor + a * rms
        # Cong bien do thich nghi: giong phai to hon nen x gate_factor (va >= san toi thieu)
        thr = max(self.noise_gate, self.noise_floor * self.gate_factor)
        speech = raw_speech and rms >= thr

        if not self.recording:
            self.ring.append((frame_bytes, speech))
            voiced = sum(1 for _, s in self.ring if s)
            if len(self.ring) == self.ring.maxlen and \
               voiced >= self.trigger_ratio * self.ring.maxlen:
                # Bat dau cau: lay ca phan dau trong ring de khoi mat chu dau
                self.recording = True
                self.buf = [f for f, _ in self.ring]
                self.ring.clear()
                self.silence = 0
            return None

        # dang ghi
        self.buf.append(frame_bytes)
        self.silence = 0 if speech else self.silence + 1
        if self.silence >= self.silence_end or len(self.buf) >= self.max_frames:
            frames = self.buf
            self.recording = False
            self.buf = []
            self.silence = 0
            if len(frames) < self.min_frames:
                return None                      # qua ngan -> bo
            pcm = b"".join(frames)
            arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
            # Ca cau phai du to: chan chuoi tieng on ngan lot qua VAD ma tong the van nho.
            utt_thr = max(self.noise_gate, self.noise_floor * self.gate_factor) * 0.6
            if utt_thr > 0 and float(np.sqrt(np.mean(arr ** 2))) < utt_thr:
                return None
            audio = arr / 32768.0
            if self.norm is not None:
                audio = chuan_hoa_do_to(audio, **self.norm)
            return audio
        return None


class LocalMic:
    """Mic laptop. Dung: for utterance in LocalMic(cfg).listen(): ..."""

    def __init__(self, vad_aggr=2, max_s=12, min_s=0.45, mute=None,
                 silence_end_frames=9, device=None, mic_gain=25, noise_gate=0,
                 noise_gate_factor=3.0, denoiser=None, norm=None):
        self.seg = _VadSegmenter(vad_aggr, max_s, min_s,
                                 silence_end_frames=silence_end_frames,
                                 noise_gate=noise_gate,
                                 noise_gate_factor=noise_gate_factor, norm=norm)
        self.mute = mute
        self.device = device       # None=mic mac dinh | so/ten = chon mic USB cu the
        self.quiet_frames = 0      # so khung LIEN TIEP im (de mo mic dung luc)
        self.mic_gain = mic_gain      # % gain thu ALSA; 25 la diem ngot cua CS202 (100 = +32dB -> vo tieng, VAD truot)
        self.den = denoiser           # StreamDenoiser hoac None (xem denoiser.py)

    def listen(self):
        import sounddevice as sd
        import time

        # Doi ten mic trong config -> device that (auto-detect neu "auto"/khong thay)
        self.device = resolve_input_device(self.device)
        ensure_capture_gain(self.device, self.mic_gain)   # hub hay reset gain -> dat lai muc chuan

        # Mic USB hay chi chay rate cao (vd 48k), khong cho mo 16k truc tiep.
        # -> thu o rate NATIVE roi resample ve SR (16k).
        cap_sr = SR
        try:
            di = sd.query_devices(self.device, "input")
            dsr = int(round(di.get("default_samplerate") or SR))
            if dsr != SR and dsr % SR == 0:
                cap_sr = dsr
        except Exception:
            pass
        down = cap_sr // SR
        blocksize = FRAME_SAMPLES * down

        def _open():
            """Mo (hoac mo lai) stream, thu vai lan neu device con ban."""
            last_err = None
            for _ in range(20):
                try:
                    st = sd.RawInputStream(samplerate=cap_sr, blocksize=blocksize,
                                           dtype="int16", channels=1,
                                           device=self.device)
                    st.start()
                    return st
                except Exception as e:                       # device con ban / dang re-enumerate
                    last_err = e
                    time.sleep(0.5)
            raise RuntimeError(f"khong mo duoc mic {self.device!r}: {last_err}")

        dev = self.device if self.device is not None else "mac dinh"
        sr_note = f"@{cap_sr}Hz->16k" if cap_sr != SR else "@16k"
        dn_note = f" | khu nhieu: {self.den.name}" if _den_on(self.den) else ""
        print(f"\U0001F3A4 [mic local: {dev} {sr_note}]{dn_note} dang nghe... (Ctrl+C de thoat)")

        # POLL thay vi blocking read() vo han. Ly do: USB CS202 (full-speed, qua hub
        # Jetson) THINH THOANG mo duoc nhung KHONG bao gio bat dau stream -> read()
        # kep cung trong poll() cua ALSA MAI MAI, Ctrl+C KHONG an duoc (ket trong C).
        # Cach nay giu quyen dieu khien o Python: (1) Ctrl+C an lien, (2) neu mic
        # "treo" (khong ra frame) qua STALL_S giay thi TU MO LAI stream de tu hoi phuc.
        # (Mic binh thuong luon ra frame ke ca luc im lang -> khong lo bao dong nham.)
        # 0.8s: mic that su chet moi kich (im lang van ra frame) -> hoi phuc NHANH,
        # gan nhu khong mat nhip. Voi mic doc o luong rieng, stall gio rat hiem.
        STALL_S = 0.8
        stream = _open()
        last_ok = time.time()
        try:
            while True:
                if stream.read_available < blocksize:
                    if time.time() - last_ok > STALL_S:
                        print("⚠️  mic treo (khong ra du lieu) -> mo lai stream...")
                        try:
                            stream.stop(); stream.close()
                        except Exception:
                            pass
                        self.seg.reset()
                        stream = _open()
                        last_ok = time.time()
                    time.sleep(0.005)
                    continue
                data, _overflow = stream.read(blocksize)     # co san san -> khong chan
                last_ok = time.time()
                if cap_sr == SR:
                    frame = bytes(data)
                else:
                    x = np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32)
                    try:
                        from scipy.signal import resample_poly
                        y = resample_poly(x, SR, cap_sr)        # 48k -> 16k
                    except Exception:
                        y = x[::down]                            # fallback tho
                    frame = np.clip(y, -32768, 32767).astype(np.int16).tobytes()
                if len(frame) != FRAME_BYTES:
                    continue
                if _den_on(self.den):
                    frame = self.den.process_frame(frame)
                    if not frame:          # vai khung dau: chua du du lieu ra
                        continue
                if self.mute is not None and self.mute.is_set():
                    self.seg.reset()       # Go dang noi -> bo qua, khoi tu nghe minh
                    x = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
                    thr = max(self.seg.noise_gate, self.seg.noise_floor * 2.5)
                    self.quiet_frames = (self.quiet_frames + 1) if rms < thr else 0
                    continue
                self.quiet_frames = 0
                utt = self.seg.feed(frame)
                if utt is not None:
                    yield utt
        finally:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass


class UdpMic:
    """Nhan PCM 16k mono int16 tu go2_audio_bridge.py (mic ROBOT)."""

    def __init__(self, host="127.0.0.1", port=17890, vad_aggr=2,
                 max_s=12, min_s=0.45, mute=None, silence_end_frames=9,
                 noise_gate=0, noise_gate_factor=3.0, denoiser=None, norm=None):
        self.addr = (host, int(port))
        self.seg = _VadSegmenter(vad_aggr, max_s, min_s,
                                 silence_end_frames=silence_end_frames,
                                 noise_gate=noise_gate,
                                 noise_gate_factor=noise_gate_factor, norm=norm)
        self.mute = mute
        self.den = denoiser           # StreamDenoiser hoac None (xem denoiser.py)
        self.quiet_frames = 0     # so khung LIEN TIEP im (de mo mic dung luc)

    def listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(self.addr)
        dn_note = f" | khu nhieu: {self.den.name}" if _den_on(self.den) else ""
        print(f"\U0001F3A4 [mic ROBOT/UDP] dang nghe tren {self.addr}{dn_note} ... "
              f"(nho chay go2_audio_bridge.py)")
        leftover = b""
        while True:
            data, _ = sock.recvfrom(4096)
            leftover += data
            while len(leftover) >= FRAME_BYTES:
                frame, leftover = leftover[:FRAME_BYTES], leftover[FRAME_BYTES:]
                # KHU NHIEU TRUOC ca luc dang cam mic: can do do to cua tin hieu DA
                # KHU de biet loa robot that su im chua (xem quiet_frames ben duoi).
                if _den_on(self.den):
                    frame = self.den.process_frame(frame)
                    if not frame:
                        continue
                if self.mute is not None and self.mute.is_set():
                    self.seg.reset()
                    # DEM KHUNG IM. Mute theo dong ho luon hut vi tre ra loa qua
                    # WebRTC khong co dinh; day la cach do TRUC TIEP "loa het keu
                    # chua" -> mo mic dung luc, khong som mot phan muoi giay nao.
                    x = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
                    rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
                    thr = max(self.seg.noise_gate, self.seg.noise_floor * 2.5)
                    self.quiet_frames = (self.quiet_frames + 1) if rms < thr else 0
                    continue
                self.quiet_frames = 0
                utt = self.seg.feed(frame)
                if utt is not None:
                    yield utt


def _den_on(den):
    return den is not None and getattr(den, "enabled", False)


def build_denoiser(cfg_audio: dict):
    """Tao bo khu nhieu tu config. Loi (thieu model/thieu goi) -> canh bao roi chay khong khu."""
    if not (cfg_audio or {}).get("denoise"):
        return None
    try:
        import denoiser as _dn
        d = _dn.from_config(cfg_audio)
        if d.enabled:
            print(f"\U0001F9F9 [khu nhieu] {d.name} | mix={d.mix} gain={d.gain}")
        return d
    except Exception as e:
        print(f"⚠️  khong bat duoc khu nhieu ({e}) -> chay KHONG khu nhieu")
        return None


def _doc_chuan_hoa(cfg_audio):
    """Doc khoi `audio.normalize`. Mac dinh BAT — STT thich muc do to on dinh."""
    n = (cfg_audio or {}).get("normalize", True)
    if n is False or n == "off":
        return None
    if n is True or n is None:
        n = {}
    d = dict(target_rms=n.get("target_rms", 0.06),
             peak_ceiling=n.get("peak_ceiling", 0.95),
             max_gain=n.get("max_gain", 8.0),
             min_gain=n.get("min_gain", 0.3))
    return d


def get_listener(cfg_audio: dict, mute=None):
    backend = (cfg_audio.get("backend") or "local").lower()
    # silence_end_ms: cang nho -> phan hoi cang "lien" (nhung pause giua cau de bi cat).
    # 270ms (9 frame) la diem can; lenh ngan co the ha 210ms, doc cham nen de 360ms.
    sil_frames = max(3, round(cfg_audio.get("silence_end_ms", 270) / FRAME_MS))
    kw = dict(vad_aggr=cfg_audio.get("vad_aggressiveness", 2),
              max_s=cfg_audio.get("max_utterance_s", 12),
              min_s=cfg_audio.get("min_utterance_s", 0.45),
              silence_end_frames=sil_frames,
              noise_gate=cfg_audio.get("noise_gate_rms", 0),
              noise_gate_factor=cfg_audio.get("noise_gate_factor", 3.0),
              denoiser=build_denoiser(cfg_audio),
              norm=_doc_chuan_hoa(cfg_audio),
              mute=mute)
    if backend == "udp":
        return UdpMic(cfg_audio.get("udp_host", "127.0.0.1"),
                      cfg_audio.get("udp_port", 17890), **kw)
    return LocalMic(device=cfg_audio.get("input_device"),
                    mic_gain=cfg_audio.get("mic_gain", 25), **kw)
