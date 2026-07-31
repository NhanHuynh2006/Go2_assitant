#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts_engine.py — "MIENG" cua GoVoice (v3 — STREAMING, realtime).

Chien luoc toc do (theo thu tu uu tien):
  1. STREAMING (piper >=1.3 + sounddevice): vua synthesize vua phat tung chunk
     -> RA TIENG sau ~0.1s, bat ke cau dai ngan. Day la che do realtime that.
  2. Khong stream duoc (piper cu / khong co sounddevice): synthesize ca cau
     trong RAM (model nap 1 lan) roi phat qua paplay/aplay (~0.3-0.5s).
  3. output="wav": chi ghi file (cho pipeline loa robot).

Do "time-to-first-sound" duoc in ra de dem vao bang so lieu bai bao.
"""

import io
import os
import shutil
import socket
import subprocess
import threading
import time
import wave


class TTS:
    def __init__(self, voice_path, enabled=True, output="local", wav_dir="tts_out",
                 piper_bin=None, robot_host="127.0.0.1", robot_port=17891,
                 pa_host=None, pa_port=17892):
        self.enabled = bool(enabled)
        # "local"     loa may (Jetson trong Go2 CHI co HDMI -> gan nhu vo dung)
        # "wav"       chi ghi file
        # "robot"     loa Go2 qua WebRTC (go2_tts_speaker.py)
        # "pa"        LOA HOI TRUONG: gui wav qua mang cho pc_speaker.py chay tren LAPTOP,
        #             laptop phat ra loa to (qua Bluetooth cua laptop hoac day jack 3.5).
        #             Dung khi bieu dien truoc dong nguoi — loa robot qua nho.
        # "robot+pa"  ra CA HAI (loa robot + loa hoi truong)
        self.output = output
        self.wav_dir = wav_dir
        self.robot_addr = (robot_host, int(robot_port))   # cau go2_tts_speaker.py nghe o day
        self.pa_addr = (pa_host, int(pa_port)) if pa_host else None
        self.voice = None
        self.sample_rate = 22050
        self.last_audio_s = 0.0          # thoi luong (giay) cua audio VUA phat -> de mute mic dung han (chong echo loa robot)
        self._new_api = False
        self._can_stream = False
        self.mode_binary = False           # fallback: goi piper BINARY (Jetson thieu piper_phonemize)
        if not self.enabled:
            return
        if not voice_path or not os.path.exists(voice_path):
            print(f"[tts] khong thay giong '{voice_path}' -> TAT TTS (chi in chu).")
            self.enabled = False
            return
        try:
            from piper import PiperVoice
            self.voice = PiperVoice.load(voice_path)
            self.sample_rate = self.voice.config.sample_rate
            self._new_api = hasattr(self.voice, "synthesize_wav")
            if self._new_api and self.output == "local":
                try:
                    import sounddevice  # noqa: F401
                    self._can_stream = True
                except Exception:
                    pass
            mode = "STREAMING realtime" if self._can_stream else \
                   ("RAM+paplay" if self.output == "local" else "ghi wav")
            print(f"[tts] Piper OK ({os.path.basename(voice_path)}, "
                  f"{self.sample_rate} Hz, che do: {mode})")
        except Exception as e:
            # Fallback: piper BINARY (Jetson aarch64 thieu module piper_phonemize)
            if self._init_binary(voice_path, piper_bin):
                return
            print(f"[tts] loi nap Piper: {e} -> TAT TTS")
            self.enabled = False

    def _init_binary(self, voice_path, piper_bin=None):
        """Tim piper binary (arg / ~/piper/piper / PATH). Tra ve True neu dung duoc."""
        import json
        cand = piper_bin or os.path.expanduser("~/piper/piper")
        binp = cand if (cand and os.path.exists(cand)) else shutil.which("piper")
        if not binp:
            return False
        try:                                # sample_rate tu file <voice>.json
            self.sample_rate = int(json.load(open(voice_path + ".json"))["audio"]["sample_rate"])
        except Exception:
            self.sample_rate = 22050
        self.piper_bin = binp
        self.voice_path = voice_path
        self.mode_binary = True
        print(f"[tts] Piper BINARY OK ({os.path.basename(voice_path)}, "
              f"{self.sample_rate} Hz, bin: {binp})")
        return True

    # ================= API chinh =================
    def speak(self, text: str) -> float:
        """Noi. Tra ve time-to-first-sound (ms) neu stream, hoac tong ms."""
        if not text:
            return 0.0
        if not self.enabled:
            print(f"\U0001F5E8\uFE0F  (TTS tat) {text}")
            return 0.0
        if self.mode_binary:
            return self._speak_binary(text)
        if self._can_stream:
            return self._speak_streaming(text)
        return self._speak_blocking(text)

    def _speak_binary(self, text: str) -> float:
        """Goi piper binary -> wav -> phat (cho Jetson). RTF ~0.1 nen nhanh."""
        t0 = time.time()
        tmp = f"/tmp/govoice_bin_{int(time.time()*1000)}.wav"
        try:
            subprocess.run([self.piper_bin, "--model", self.voice_path,
                            "--output_file", tmp],
                           input=text.encode("utf-8"),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True)
            with open(tmp, "rb") as f:
                wav_bytes = f.read()
        except Exception as e:
            print(f"[tts] piper binary loi: {e}")
            return 0.0
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
        ms = round((time.time() - t0) * 1000.0, 1)
        if not wav_bytes or len(wav_bytes) <= 100:
            print("[tts] LOI: audio rong (binary)")
            return ms
        self._emit(wav_bytes, ms)
        return ms

    def _send_to_robot(self, wav_bytes):
        """Ghi wav ra /tmp roi gui DUONG DAN qua UDP cho go2_tts_speaker.py
        (cau giu ket noi WebRTC) -> phat qua LOA ROBOT. Cau se xoa file sau khi phat."""
        path = f"/tmp/govoice_robot_{int(time.time()*1000)}.wav"
        with open(path, "wb") as f:
            f.write(wav_bytes)
        # Nho thoi luong audio -> pipeline giu mute mic het cau (loa robot phat cham qua WebRTC).
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as _wf:
                self.last_audio_s = _wf.getnframes() / float(_wf.getframerate() or self.sample_rate)
        except Exception:
            self.last_audio_s = 0.0
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(path.encode("utf-8"), self.robot_addr)
            s.close()
        except Exception as e:
            print(f"[tts] gui loa robot loi: {e}")

    def _wav_seconds(self, wav_bytes):
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                return wf.getnframes() / float(wf.getframerate() or self.sample_rate)
        except Exception:
            return 0.0

    def _send_to_pa(self, wav_bytes):
        """Gui NGUYEN BYTE wav qua TCP cho pc_speaker.py tren LAPTOP -> phat ra loa hoi truong.

        Gui byte (khong phai duong dan nhu _send_to_robot) vi laptop la MAY KHAC,
        khong doc duoc /tmp cua Jetson. Khung: 4 byte do dai (big-endian) + du lieu wav.
        Chay o thread rieng + timeout ngan: laptop rut day giua chung cung KHONG treo robot.
        """
        if not self.pa_addr:
            print("[tts] output='pa' nhung thieu tts.pa_host trong config -> bo qua")
            return
        self.last_audio_s = max(self.last_audio_s, self._wav_seconds(wav_bytes))
        addr = self.pa_addr

        def _worker():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect(addr)
                s.sendall(len(wav_bytes).to_bytes(4, "big") + wav_bytes)
                s.close()
            except Exception as e:
                print(f"[tts] loa hoi truong ({addr[0]}:{addr[1]}) loi: {e} "
                      f"— laptop da chay pc_speaker.py chua?")

        threading.Thread(target=_worker, daemon=True).start()

    def _emit(self, wav_bytes, ms):
        """Dua audio ra dau ra theo self.output."""
        if self.output == "robot+pa":
            self._send_to_pa(wav_bytes)
            self._send_to_robot(wav_bytes)
        elif self.output == "pa":
            self._send_to_pa(wav_bytes)
        elif self.output == "robot":
            self._send_to_robot(wav_bytes)
        elif self.output == "wav":
            os.makedirs(self.wav_dir, exist_ok=True)
            path = os.path.join(self.wav_dir, f"say_{int(time.time()*1000)}.wav")
            with open(path, "wb") as f:
                f.write(wav_bytes)
            print(f"[tts] da ghi: {path} ({ms} ms)")
        else:
            self._play_file(wav_bytes)

    def synth_to_file(self, text: str, path: str) -> str:
        with open(path, "wb") as f:
            f.write(self._synth_to_wav_bytes(text))
        return path

    # ================= 1) STREAMING =================
    def _speak_streaming(self, text: str) -> float:
        """Vua synthesize vua phat — ra tieng sau ~0.1s."""
        import numpy as np
        import sounddevice as sd
        t0 = time.time()
        first_ms = None
        stream = None
        try:
            for chunk in self.voice.synthesize(text):
                pcm = self._chunk_to_int16(chunk, np)
                if pcm is None or pcm.size == 0:
                    continue
                if stream is None:
                    sr = getattr(chunk, "sample_rate", self.sample_rate)
                    stream = sd.OutputStream(samplerate=sr, channels=1,
                                             dtype="int16")
                    stream.start()
                    first_ms = round((time.time() - t0) * 1000.0, 1)
                stream.write(pcm)
            if stream is not None:
                stream.stop()
                stream.close()
                return first_ms or 0.0
        except Exception as e:
            print(f"[tts] stream loi ({e}) -> chuyen sang phat thuong")
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        # stream fail -> phat thuong
        return self._speak_blocking(text)

    @staticmethod
    def _chunk_to_int16(chunk, np):
        """AudioChunk cua piper co the mang du lieu o vai dang — bat het."""
        for attr in ("audio_int16_array",):
            a = getattr(chunk, attr, None)
            if a is not None:
                return np.asarray(a, dtype=np.int16)
        for attr in ("audio_int16_bytes",):
            b = getattr(chunk, attr, None)
            if b:
                return np.frombuffer(b, dtype=np.int16)
        a = getattr(chunk, "audio_float_array", None)
        if a is not None:
            return (np.clip(np.asarray(a), -1, 1) * 32767).astype(np.int16)
        if isinstance(chunk, (bytes, bytearray)):
            return np.frombuffer(chunk, dtype=np.int16)
        return None

    # ================= 2) BLOCKING (du phong) =================
    def _speak_blocking(self, text: str) -> float:
        t0 = time.time()
        wav_bytes = self._synth_to_wav_bytes(text)
        ms = round((time.time() - t0) * 1000.0, 1)
        if not wav_bytes or len(wav_bytes) <= 100:
            print("[tts] LOI: audio rong (synthesize that bai)")
            return ms
        self._emit(wav_bytes, ms)
        return ms

    def _synth_to_wav_bytes(self, text: str) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            if self._new_api:
                self.voice.synthesize_wav(text, wf)
            else:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                self.voice.synthesize(text, wf)
        return buf.getvalue()

    def _play_file(self, wav_bytes: bytes):
        tmp = "/tmp/govoice_say.wav"
        with open(tmp, "wb") as f:
            f.write(wav_bytes)
        for player in ("paplay", "aplay"):
            if shutil.which(player):
                r = subprocess.run([player, tmp], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                if r.returncode == 0:
                    return
        try:
            import numpy as np
            import sounddevice as sd
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sr = wf.getframerate()
                audio = np.frombuffer(wf.readframes(wf.getnframes()),
                                      dtype=np.int16)
            sd.play(audio, sr)
            sd.wait()
        except Exception as e:
            print(f"[tts] khong phat duoc loa: {e}")


if __name__ == "__main__":
    import sys
    voice = sys.argv[1] if len(sys.argv) > 1 else \
        "models/piper/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
    t = TTS(voice)
    a = t.speak("Xin ch\u00e0o, m\u00ecnh l\u00e0 G\u00f4, robot ch\u00f3 c\u1ee7a b\u1ea1n \u0111\u00e2y!")
    b = t.speak("\u0110\u00e2y l\u00e0 c\u00e2u r\u1ea5t d\u00e0i \u0111\u1ec3 ki\u1ec3m tra ch\u1ebf \u0111\u1ed9 streaming: "
                "d\u00f9 c\u00e2u d\u00e0i bao nhi\u00eau th\u00ec ti\u1ebfng v\u1eabn ph\u1ea3i b\u1eadt ra g\u1ea7n nh\u01b0 ngay l\u1eadp t\u1ee9c, "
                "kh\u00f4ng ph\u1ea3i \u0111\u1ee3i sinh xong to\u00e0n b\u1ed9 c\u00e2u.")
    print(f"\n\u23F1\ufe0f  time-to-first-sound: cau ngan {a} ms | cau DAI {b} ms")
    print("Neu 2 so xap xi nhau va deu nho (~100ms) => STREAMING dang chay dung!")
