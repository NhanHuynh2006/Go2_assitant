#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
denoiser.py — KHU NHIEU bang MANG NEURAL, chay STREAMING o 16kHz.

Vi tri cam trong pipeline (audio_io.py):
    mic (local hoac UDP tu mic ROBOT) -> [DENOISER] -> VAD/noise-gate -> STT

Vi sao cam TRUOC VAD (khong phai chi truoc STT):
    Van de lon nhat cua mic dom / mic robot KHONG phai la "STT doc sai" ma la
    "tieng on lot qua cong, VAD tuong la giong noi" -> STT che loi ra cau bay ba.
    Khu nhieu TRUOC VAD lam nen nhieu sup xuong -> cong tu dong het lot.

BACKEND:
  "gtcrn"   (MAC DINH, khuyen dung) — GTCRN (Grouped Temporal Convolutional
            Recurrent Network), mo hinh khu nhieu sieu nhe ~23.7k tham so,
            chay qua sherpa-onnx (CUNG thu vien voi STT zipformer dang dung).
            16kHz, ONNX CPU. Do tren Jetson Orin NX: RTF ~0.15 voi 2 thread
            (~4.4ms cho moi khung 30ms) -> thua realtime.
            Model: models/denoiser/gtcrn_simple.onnx (~523KB)
  "rnnoise" — RNNoise (xiph.org), RNN nho + DSP co dien. CHAY O 48kHz nen o day
            phai resample 16k->48k->16k (ton them ~1ms/khung, chat luong kem
            GTCRN mot chut). Dung khi khong co model GTCRN. Xem rnnoise_denoise.py.
  "none"    — tat.

THAM SO:
  mix   (0..1): 1.0 = lay 100% tin hieu DA KHU. Ha xuong (vd 0.85) de tron lai
                15% tin hieu GOC — dung khi thay khu nhieu "cat lem" giong lam
                STT mat chu (hien tuong over-suppression).
  gain  (float): khuech dai SAU khi khu. Khu nhieu lam RMS tut (do dai nhieu bi
                xoa), neu STT nghe "nho" thi nang len 1.5-2.0.

DUNG (streaming, giu dung kich thuoc khung 30ms/960 byte):
    dn = StreamDenoiser(backend="gtcrn", model="models/denoiser/gtcrn_simple.onnx")
    out = dn.process_frame(frame_960_bytes)   # b"" o vai khung dau (do tre thuat toan)

TU TEST A/B:  python3 test_denoise.py --wav robot_mic_test.wav
"""

import os

import numpy as np

SR = 16000
FRAME_SAMPLES = 480          # 30ms @16k — khop audio_io.FRAME_SAMPLES
FRAME_BYTES = FRAME_SAMPLES * 2

DEFAULT_GTCRN = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "models", "denoiser", "gtcrn_simple.onnx")
# Van tay nhieu cua CHINH con robot (ghi luc phong yen, robot bat, khong ai noi)
DEFAULT_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "robot_noise60s_v2.wav")


class _GtcrnCore:
    """sherpa-onnx OnlineSpeechDenoiser (GTCRN). Vao/ra float32 16k, do dai KHAC nhau."""

    def __init__(self, model, num_threads=2, provider="cpu", **_):
        import sherpa_onnx
        if not model:
            model = DEFAULT_GTCRN
        if not os.path.exists(model):
            raise OSError(
                "khong tim thay model GTCRN: %s\n"
                "  tai ve: mkdir -p models/denoiser && curl -sSL -o %s \\\n"
                "    https://github.com/k2-fsa/sherpa-onnx/releases/download/"
                "speech-enhancement-models/gtcrn_simple.onnx" % (model, model))
        cfg = sherpa_onnx.OnlineSpeechDenoiserConfig()
        cfg.model.gtcrn.model = model
        cfg.model.num_threads = int(num_threads)
        cfg.model.provider = provider
        if not cfg.validate():
            raise RuntimeError("cau hinh GTCRN khong hop le")
        self._sherpa = sherpa_onnx
        self._cfg = cfg
        self.d = sherpa_onnx.OnlineSpeechDenoiser(cfg)
        self.name = "gtcrn(%s)" % os.path.basename(model)

    def feed(self, x_f32: np.ndarray) -> np.ndarray:
        r = self.d.run(x_f32, SR)
        s = r.samples
        return np.asarray(s, dtype=np.float32) if len(s) else _EMPTY

    def reset(self):
        # sherpa OnlineSpeechDenoiser khong co reset() -> tao lai (re, ~ms)
        self.d = self._sherpa.OnlineSpeechDenoiser(self._cfg)


class _RnnoiseCore:
    """RNNoise chay 48k -> phai upsample/downsample quanh no."""

    def __init__(self, **_):
        from rnnoise_denoise import RnnoiseDenoiser
        from scipy.signal import resample_poly
        self._rs = resample_poly
        self.dn = RnnoiseDenoiser(mix=1.0)
        self.name = "rnnoise@48k"

    def feed(self, x_f32: np.ndarray) -> np.ndarray:
        if x_f32.size == 0:
            return _EMPTY
        up = self._rs(x_f32, 3, 1)                       # 16k -> 48k
        i16 = np.clip(up * 32768.0, -32768, 32767).astype(np.int16)
        out48 = self.dn.process(i16)
        if out48.size == 0:
            return _EMPTY
        return self._rs(out48.astype(np.float32) / 32768.0, 1, 3)   # 48k -> 16k

    def reset(self):
        from rnnoise_denoise import RnnoiseDenoiser
        self.dn = RnnoiseDenoiser(mix=1.0)


class _SpecSubCore:
    """TRU PHO (spectral subtraction) voi VAN TAY NHIEU ghi san — khong dung mang neural.

    Y tuong: tieng quat/dong co cua robot la nhieu ON DINH (stationary) — pho cua no
    gan nhu khong doi theo thoi gian. Vay thi khong can mo hinh hoc may: chi can ghi
    truoc vai chuc giay tieng on, lay pho TRUNG BINH lam "van tay", roi voi moi khung
    tin hieu thi TRU thang van tay do ra khoi pho bien do.

        |S|^2  =  |X|^2  -  alpha * |N|^2          (alpha = he so tru du)
        G      =  max( |S|^2 / |X|^2 , floor )     (floor = san, chong "musical noise")
        Y      =  G * X                            (giu nguyen PHA cua tin hieu goc)

    Uu the so voi GTCRN: cuc re (chi FFT), va NHAM DUNG loai nhieu nay vi van tay lay
    tu chinh con robot. Nhuoc: khong xu ly duoc nhieu THAY DOI (nguoi noi chuyen, va
    cham) — cai do vay moi can GTCRN. Hai cai BO SUNG cho nhau, dung noi tiep duoc.

    STFT chay streaming: cua so Hann can bac hai, chong lan 50% -> tai tao hoan hao.
    """

    def __init__(self, model=None, profile=None, over_sub=2.0, floor=0.06,
                 n_fft=512, **_):
        # CHI dung `profile` — KHONG rot ve `model` (model la file .onnx cua GTCRN,
        # khi noi tiep "specsub+gtcrn" thi ca hai bo cung nhan `model` do).
        path = profile or DEFAULT_PROFILE
        if not os.path.exists(path):
            raise OSError("khong thay file van tay nhieu: %s\n"
                          "  ghi bang: python3 go2_audio_bridge.py --record 60 --gain 2.5\n"
                          "  (de robot BAT, phong yen, KHONG ai noi)" % path)
        import wave
        with wave.open(path) as w:
            noise = np.frombuffer(w.readframes(w.getnframes()),
                                  dtype=np.int16).astype(np.float32) / 32768.0
        self.n = int(n_fft)
        self.hop = self.n // 2
        self.win = np.sqrt(np.hanning(self.n + 1)[:self.n]).astype(np.float32)
        # van tay = pho CONG SUAT trung vi (trung vi chiu duoc va cham la trong ban ghi)
        specs = []
        for i in range(0, len(noise) - self.n, self.hop):
            specs.append(np.abs(np.fft.rfft(noise[i:i + self.n] * self.win)) ** 2)
        if not specs:
            raise OSError("file van tay nhieu qua ngan")
        self.noise_pow = np.median(np.stack(specs), axis=0).astype(np.float32)
        self.alpha = float(over_sub)
        self.floor = float(floor)
        # TU CO GIAN theo muc nhieu HIEN TAI. Van tay ghi o mot muc am luong cu the;
        # neu doi --gain cua bridge, doi khoang cach, hay quat robot chay nhanh/cham
        # hon thi muc nhieu doi -> tru sai (tru thieu = con on, tru thua = mat chu).
        # Do thay: cham vao dung muc hieu chuan thi WER 5%, lech muc 3x thi hong han.
        # Cach chua: giu HINH DANG pho tu van tay, con DO LON thi bam theo thong ke
        # cuc tieu (minimum statistics) cua chinh tin hieu dang chay.
        self._mau = []              # gom khung dau de DOI CHIEU voi van tay (canh bao)
        self._n_khung = 0
        self._in = np.zeros(0, dtype=np.float32)
        self._ola = np.zeros(self.n, dtype=np.float32)
        self.name = "specsub(%s, a=%.1f)" % (os.path.basename(path), self.alpha)

    def feed(self, x_f32: np.ndarray) -> np.ndarray:
        self._in = np.concatenate([self._in, x_f32]) if self._in.size else x_f32
        out = []
        while self._in.size >= self.n:
            seg = self._in[:self.n] * self.win
            X = np.fft.rfft(seg)
            p = np.abs(X) ** 2
            # KHONG tu co gian he so: da thu "minimum statistics" -> TE HON han
            # (bat 1.6/4 thay vi 2.0/4), vi cuc tieu bam ca vao khoang lang giua cac
            # tu roi uoc luong sai. Giu he so CO DINH, va chi CANH BAO khi lech.
            self._n_khung += 1
            if self._n_khung <= 300:            # ~5s dau: uoc luong muc nhieu that
                # PHAI so sanh cung mot dai luong: van tay la TRUNG VI qua cac khung,
                # nen o day cung gom cac khung roi lay TRUNG VI (khong phai cuc tieu).
                self._mau.append(p)
                if self._n_khung == 300:
                    hien = np.median(np.stack(self._mau), axis=0)
                    self._mau = []
                    r = float(np.median(hien / np.maximum(self.noise_pow, 1e-12)))
                    if not (0.4 < r < 2.5):
                        print(f"[specsub] \u26a0\ufe0f  muc nhieu hien tai lech {r:.2f}x so voi "
                              f"van tay -> GHI LAI van tay:\n"
                              f"    python3 go2_audio_bridge.py --record 60 --gain 2.5\n"
                              f"    mv robot_mic_test.wav robot_noise60s_v2.wav")
            g = np.maximum((p - self.alpha * self.noise_pow) / np.maximum(p, 1e-12),
                           self.floor)
            y = np.fft.irfft(X * np.sqrt(g), n=self.n).astype(np.float32) * self.win
            self._ola += y
            out.append(self._ola[:self.hop].copy())
            self._ola = np.concatenate([self._ola[self.hop:],
                                        np.zeros(self.hop, dtype=np.float32)])
            self._in = self._in[self.hop:]
        return np.concatenate(out) if out else _EMPTY

    def reset(self):
        self._in = np.zeros(0, dtype=np.float32)
        self._ola = np.zeros(self.n, dtype=np.float32)
        self._mau = []
        self._n_khung = 0


class _Chuoi:
    """Noi TIEP nhieu bo khu nhieu: ra cua bo nay la vao cua bo kia."""

    def __init__(self, cores):
        self.cores = cores
        self.name = " -> ".join(c.name for c in cores)

    def feed(self, x):
        for c in self.cores:
            if x.size == 0:
                return _EMPTY
            x = c.feed(x)
        return x

    def reset(self):
        for c in self.cores:
            c.reset()


_EMPTY = np.zeros(0, dtype=np.float32)
_CORES = {"gtcrn": _GtcrnCore, "rnnoise": _RnnoiseCore,
          "specsub": _SpecSubCore}


class StreamDenoiser:
    """Bo khu nhieu streaming GIU NGUYEN nhip khung 30ms cua pipeline.

    Loi khu nhieu (GTCRN/RNNoise) nha ra so mau KHAC so mau nap vao (do tre
    thuat toan + kich thuoc hop noi bo). Lop nay dem lai thanh dung khung
    480 mau de webrtcvad va phan con lai cua audio_io khong phai doi gi.

    Vai khung dau tra ve b"" (chua du du lieu) — binh thuong, tre ~30-60ms.
    """

    def __init__(self, backend="gtcrn", model=None, num_threads=2,
                 provider="cpu", mix=1.0, gain=1.0, profile=None,
                 over_sub=4.0, floor=0.06):
        phu = dict(profile=profile, over_sub=over_sub, floor=floor)
        backend = (backend or "none").lower()
        if backend in ("none", "off", "0", "false"):
            self.core = None
            self.name = "off"
        else:
            if "+" in backend:              # noi tiep nhieu bo, vd "specsub+gtcrn"
                self.core = _Chuoi([_CORES[b](model=model, num_threads=num_threads,
                                              provider=provider, **phu)
                                    for b in backend.split("+")])
                self.name = self.core.name
                self.mix = max(0.0, min(1.0, float(mix)))
                self.gain = float(gain)
                self._wet = _EMPTY
                self._dry = _EMPTY
                return
            if backend not in _CORES:
                raise ValueError("backend khu nhieu la khong biet: %r "
                                 "(chon gtcrn/rnnoise/none)" % backend)
            self.core = _CORES[backend](model=model, num_threads=num_threads,
                                        provider=provider, **phu)
            self.name = self.core.name
        self.mix = max(0.0, min(1.0, float(mix)))
        self.gain = float(gain)
        self._wet = _EMPTY          # duoi ra da khu, cho du 480 mau
        self._dry = _EMPTY          # duoi tin hieu goc, de tron mix (giu dong bo)

    @property
    def enabled(self):
        return self.core is not None

    def reset(self):
        if self.core is not None:
            self.core.reset()
        self._wet = _EMPTY
        self._dry = _EMPTY

    def process_frame(self, frame_bytes: bytes) -> bytes:
        """480 mau int16 vao -> 0 hoac 480 mau int16 ra (bytes)."""
        if self.core is None:
            return frame_bytes
        x = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            wet = self.core.feed(x)
        except Exception:
            return frame_bytes                      # loi -> tra nguyen goc, khong bao gio cam tieng
        if wet.size:
            self._wet = np.concatenate([self._wet, wet]) if self._wet.size else wet
        if self.mix < 1.0:
            # giu duoi DRY cung do dai da nap, de lay ra dung so mau voi WET
            self._dry = np.concatenate([self._dry, x]) if self._dry.size else x

        if self._wet.size < FRAME_SAMPLES:
            return b""
        y = self._wet[:FRAME_SAMPLES]
        self._wet = self._wet[FRAME_SAMPLES:]
        if self.mix < 1.0 and self._dry.size >= FRAME_SAMPLES:
            d = self._dry[:FRAME_SAMPLES]
            self._dry = self._dry[FRAME_SAMPLES:]
            y = self.mix * y + (1.0 - self.mix) * d
        if self.gain != 1.0:
            y = y * self.gain
        return np.clip(y * 32768.0, -32768, 32767).astype(np.int16).tobytes()

    def process_array(self, x_f32: np.ndarray) -> np.ndarray:
        """Khu nhieu CA MANG float32 16k (dung cho test/offline). Tra ve float32."""
        if self.core is None:
            return x_f32
        out = []
        for i in range(0, len(x_f32), FRAME_SAMPLES):
            blk = x_f32[i:i + FRAME_SAMPLES]
            if blk.size < FRAME_SAMPLES:
                blk = np.pad(blk, (0, FRAME_SAMPLES - blk.size))
            b = self.process_frame(
                np.clip(blk * 32768.0, -32768, 32767).astype(np.int16).tobytes())
            if b:
                out.append(np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0)
        return np.concatenate(out) if out else _EMPTY


def from_config(cfg_audio: dict):
    """Tao StreamDenoiser tu khoi `audio.denoise` trong config.yaml.

    audio:
      denoise:
        backend: gtcrn          # gtcrn | rnnoise | none
        model: models/denoiser/gtcrn_simple.onnx
        num_threads: 2
        mix: 1.0
        gain: 1.0
    Chap nhan ca dang rut gon `denoise: gtcrn` hoac `denoise: false`.
    """
    d = (cfg_audio or {}).get("denoise")
    if d is None or d is False:
        return StreamDenoiser(backend="none")
    if d is True:
        d = {"backend": "gtcrn"}
    if isinstance(d, str):
        d = {"backend": d}
    return StreamDenoiser(profile=d.get("profile"),
                          over_sub=d.get("over_sub", 4.0),
                          floor=d.get("floor", 0.06),
                          backend=d.get("backend", "gtcrn"),
                          model=d.get("model"),
                          num_threads=d.get("num_threads", 2),
                          provider=d.get("provider", "cpu"),
                          mix=d.get("mix", 1.0),
                          gain=d.get("gain", 1.0))
