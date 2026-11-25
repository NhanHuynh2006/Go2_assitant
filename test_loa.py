#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess

class TTS:
    def __init__(self, voice_path, enabled=True):
        self.enabled = bool(enabled)
        self.voice_path = voice_path
        
        if not os.path.exists(self.voice_path):
            print(f"[tts] LỖI: Không tìm thấy file model tại {self.voice_path}")
            self.enabled = False
        else:
            print(f"[tts] Hệ thống nói Piper độc lập đã sẵn sàng!")

    def speak(self, text: str):
        if not self.enabled or not text:
            return
            
        print(f"🗣️ Gô nói: {text}")
        tmp_wav = "debug_audio.wav"
        
        try:
            # 1. Gọi trực tiếp bộ công cụ piper của hệ thống qua subprocess (Cách ly hoàn toàn bộ nhớ RAM)
            # Điều này tương đương với lệnh: echo "text" | piper --model ... --output_file ...
            process = subprocess.Popen(
                ['piper', '--model', self.voice_path, '--output_file', tmp_wav],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, # Giấu các dòng log thừa của piper
                stderr=subprocess.DEVNULL
            )
            # Bơm text vào cho piper xử lý
            process.communicate(input=text.encode('utf-8'))
            
            # Kiểm tra xem piper có tạo ra file ruột thật không (lớn hơn 44 bytes)
            if os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 100:
                print("[tts] Đang đẩy luồng âm thanh ra loa...")
                
                # 2. Gọi aplay (hoặc paplay) để xuất âm thanh
                os.system(f"paplay {tmp_wav}")
                
                # 3. Dọn dẹp rác để nhẹ máy
                os.remove(tmp_wav)
            else:
                print("[tts] LỖI: piper không thể tạo ra file âm thanh hợp lệ!")

        except Exception as e:
            print(f"[tts] Lỗi hệ thống: {e}")

if __name__ == "__main__":
    import sys
    voice_model = sys.argv[1] if len(sys.argv) > 1 else "models/piper/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
    
    t = TTS(voice_model)
    t.speak("Xin chào, mình là Gô. Quá trình kiểm tra hệ thống âm thanh đã hoàn tất, mọi thứ hoạt động rất tuyệt vời!")