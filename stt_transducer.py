#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stt_transducer.py — STT engine THAY THE (Huong 1): zipformer-transducer tieng Viet
qua sherpa-onnx. Cung interface voi stt_engine.STT (transcribe -> (text, ms)) nen
co the CAM THANG vao pipeline (assistant_realtime / run_demo).

Vi sao: PhoWhisper xu ly ca cua so 30s -> ~1800ms. Transducer khong pad 30s, model
30M int8 -> ~15-30ms tren CPU laptop (~100x nhanh hon). Xem stt_streaming_test/.

Dung:
    from stt_transducer import STTTransducer
    stt = STTTransducer(model_dir=".../sherpa-onnx-zipformer-vi-30M-int8-2026-02-09",
                        hotwords_file="hotwords.txt")   # hotwords -> moi tu vung lenh
    text, ms = stt.transcribe(audio_f32_16k)

Yeu cau: pip install sherpa-onnx  (Jetson: build sherpa-onnx co CUDA -> use_gpu=True)
"""
import os
import time
import numpy as np


class STTTransducer:
    def __init__(self, model_dir, hotwords_file=None, hotwords_score=3.0,
                 num_threads=4, use_gpu=False):
        import sherpa_onnx
        enc = self._pick(model_dir, "encoder")
        dec = self._pick(model_dir, "decoder")
        joi = self._pick(model_dir, "joiner")
        tok = os.path.join(model_dir, "tokens.txt")
        provider = "cuda" if use_gpu else "cpu"

        kw = dict(encoder=enc, decoder=dec, joiner=joi, tokens=tok,
                  num_threads=num_threads, provider=provider)

        use_hot = hotwords_file and os.path.exists(hotwords_file)
        if use_hot:
            vocab = os.path.join(model_dir, "bpe.vocab")
            if not os.path.exists(vocab):
                self._make_bpe_vocab(os.path.join(model_dir, "bpe.model"), vocab)
            kw.update(decoding_method="modified_beam_search",
                      modeling_unit="bpe", bpe_vocab=vocab,
                      hotwords_file=hotwords_file, hotwords_score=hotwords_score)
        else:
            kw.update(decoding_method="greedy_search")

        self.rec = sherpa_onnx.OfflineRecognizer.from_transducer(**kw)
        mode = f"hotwords x{len(open(hotwords_file, encoding='utf-8').readlines())}" if use_hot else "greedy"
        print(f"[stt-transducer] OK ({os.path.basename(model_dir)}, {provider}, {mode})")

    @staticmethod
    def _pick(d, kind):
        """Chon file .onnx (uu tien int8 cho nhanh)."""
        for name in (f"{kind}.int8.onnx", f"{kind}.onnx"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        raise FileNotFoundError(f"khong thay {kind}.onnx trong {d}")

    @staticmethod
    def _make_bpe_vocab(bpe_model, out):
        """Sinh bpe.vocab (token score) tu bpe.model — can cho hotwords."""
        import sentencepiece as spm
        sp = spm.SentencePieceProcessor(model_file=bpe_model)
        with open(out, "w", encoding="utf-8") as f:
            for i in range(sp.get_piece_size()):
                f.write(f"{sp.id_to_piece(i)} {sp.get_score(i)}\n")

    def transcribe(self, audio_f32_16k: np.ndarray) -> tuple:
        """audio float32 mono 16kHz -> (text, ms). Cung chu ky voi stt_engine.STT."""
        t0 = time.time()
        x = np.ascontiguousarray(audio_f32_16k, dtype=np.float32)
        s = self.rec.create_stream()
        s.accept_waveform(16000, x)
        self.rec.decode_stream(s)
        text = s.result.text.strip()
        return text, round((time.time() - t0) * 1000.0, 1)


if __name__ == "__main__":
    import sys
    import wave
    here = os.path.dirname(os.path.abspath(__file__))
    md = os.path.join(here, "stt_streaming_test",
                      "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
    hw = os.path.join(here, "stt_streaming_test", "hotwords.txt")
    stt = STTTransducer(md, hotwords_file=hw)
    wav = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "test_voice.wav")
    with wave.open(wav, "rb") as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if sr != 16000:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr, 16000)
        a = resample_poly(a, 16000 // g, sr // g).astype(np.float32)
    print(stt.transcribe(a))
