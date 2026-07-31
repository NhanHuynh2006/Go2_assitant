import sounddevice as sd
import numpy as np
import sys

# Dùng trực tiếp index 0 tương ứng với thiết bị CS202 USB Audio
device_id = 0 

try:
    info = sd.query_devices(device_id, 'input')
    samplerate = int(info['default_samplerate'])
except Exception as e:
    print(f'[-] Lỗi kết nối thiết bị {device_id}: {e}')
    sys.exit(1)

duration = 4
print(f'\n[OK] Đang sử dụng thiết bị: {info["name"]}')
print(f'[OK] Tần số lấy mẫu: {samplerate}Hz')
print(f'==> HÃY NÓI TO, SÁT MIC (~5cm), ĐẾM TỪ 1 ĐẾN 5 TRONG {duration} GIÂY...')

try:
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16', device=device_id)
    sd.wait()
    
    max_val = int(np.abs(recording).max())
    print('-' * 40)
    print(f'Kết quả Biên độ lớn nhất (Max Amplitude): {max_val}')
    
    if max_val > 8000:
        print('==> [MÀU XANH] MIC THU TỐT! Tín hiệu đạt yêu cầu.')
    elif max_val > 500:
        print('==> [CẢNH BÁO] Có tín hiệu nhưng RẤT NHỎ. Xem lại volume.')
    else:
        print('==> [LỖI] Tín hiệu bằng 0 hoặc nhiễu nền.')
except Exception as e:
    print(f'[-] Lỗi khi thu âm: {e}')
