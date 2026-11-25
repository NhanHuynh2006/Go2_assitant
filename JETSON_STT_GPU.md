# ⚡ STT chạy GPU trên Jetson — cú tăng tốc lớn nhất còn lại

> Vấn đề: wheel `ctranslate2` trên PyPI cho ARM (aarch64) là bản **CPU-only** — cài pip xong
> để `device: cuda` là lỗi. Muốn GPU phải build từ source với CUDA + cuDNN, kiến trúc **SM87** (Orin).
> Tham chiếu thực đo: bản build GPU trên Orin Nano đạt ~3s cho 20s audio (faster-whisper-small)
> → câu lệnh 2-3s của bạn chỉ tốn **~0.3-0.5s STT** (so với ~1-1.5s CPU).

## Kiểm tra JetPack trước (quyết định đường đi)

```bash
cat /etc/nv_tegra_release    # R35.x = JetPack 5 (CUDA 11.4) | R36.x = JetPack 6 (CUDA 12.x)
```
Jetson của bạn: Ubuntu 20.04 + CUDA 11.4 = **JetPack 5** → đi ĐƯỜNG A (build tay).
(JetPack 6 thì có đường container dễ hơn — ghi ở ĐƯỜNG B cuối file.)

---

> ⚠️ **THỰC TẾ ĐÃ TEST (2026-06-13) trên Orin Nano JP5.1.1 / CUDA 11.4:** build tay CTranslate2
> **v3.24.0 KHÔNG qua** — lỗi (1) `thrust::cuda::par_nosync` (Thrust của CUDA 11.4 quá cũ, vá
> `par_nosync→par` được) rồi (2) `device_type<bfloat16_t> incomplete type` ở topk_gpu.cu (bf16 +
> CUDA 11.4, KHÔNG có patch 1 dòng chắc ăn, hạ version cũng dính). Host wheel dựng sẵn
> `pypi.jetson-ai-lab.dev` thì Jetson KHÔNG phân giải được DNS.
> → **Khuyến nghị thực dụng:** dùng **STT CPU tối ưu** (PhoWhisper-small + `beam_size=1` + `int8`,
>   ~1-1.5s, vẫn đúng tiếng Việt) cho demo/paper; để GPU STT lại, làm bằng **jetson-containers**
>   (ĐƯỜNG B cách 2 — chạy được cả trên JP5) khi có băng thông docker. Build tay bên dưới chỉ
>   nên thử nếu bạn nâng CUDA ≥ 11.6.

## ĐƯỜNG A — Build CTranslate2-CUDA trên JetPack 5 (CUDA 11.4)  [LỖI trên CUDA 11.4 — xem cảnh báo trên]

### A1. Phụ thuộc hệ thống
```bash
sudo apt update
sudo apt install -y build-essential cmake git libopenblas-dev
# cuDNN tu apt cua Jetson (thuong da co san voi JetPack):
dpkg -l | grep cudnn || sudo apt install -y libcudnn8 libcudnn8-dev
```

### A2. Build CTranslate2 (~30-45 phút trên Orin Nano)
```bash
git clone --recursive https://github.com/OpenNMT/CTranslate2 ~/CTranslate2
cd ~/CTranslate2
# *** DUNG v3.16.1 cho CUDA 11.4 ***  (DA TEST THANH CONG 2026-06-13, STT ~1.8s/cau):
#   - v3.24.0 KHONG build: par_nosync (Thrust cu) + bfloat16 incomplete (CUDA<11.8, KHONG va duoc)
#   - v3.7.0 build duoc nhung Whisper THIEU encode()/device -> faster-whisper khong xai duoc
#   - v3.16.1 = diem vang: CO encode/device/align (faster-whisper chay) + CHUA co bf16 GPU
#     -> chi can va par_nosync la build duoc tren CUDA 11.4.
git checkout v3.16.1 && git submodule update --init --recursive
#   ^ submodule 'thrust' cua 3.16.1 co the fetch loi (commit orphan) -> KE, dung thrust san co.

# *** VA par_nosync (BAT BUOC cho 3.16.1 / CUDA 11.4) ***
#   Thrust cua CUDA 11.4 chua co thrust::cuda::par_nosync -> doi thanh ::par (dung ket qua):
grep -rl "par_nosync" src/ | xargs sed -i 's/thrust::cuda::par_nosync/thrust::cuda::par/g'

mkdir build && cd build
cmake .. \
  -DWITH_CUDA=ON \
  -DWITH_CUDNN=ON \
  -DWITH_MKL=OFF \
  -DWITH_OPENBLAS=ON \
  -DOPENMP_RUNTIME=COMP \
  -DCMAKE_CUDA_ARCHITECTURES=87 \
  -DCMAKE_BUILD_TYPE=Release
make -j2            # -j2 cho 8GB RAM (them swap 8G truoc, xem Buoc 0)
sudo make install
sudo ldconfig
```

### A3. Build gói Python + cài faster-whisper khớp bản
```bash
cd ~/CTranslate2/python
pip3 install -r install_requirements.txt
python3 setup.py bdist_wheel
pip3 install dist/*.whl --force-reinstall
# faster-whisper khop ct2 3.16 (>=3.10,<4); --no-deps de GIU av cu (av==10 build loi Cython3):
pip3 install "faster-whisper==0.9.0" --no-deps
# pip CANH BAO fw 0.9.0 doi ct2>=3.17/av==10/tokenizers<0.15 -> KE (--no-deps), chay OK voi
#   ct2 3.16.1 + av12 + tokenizers 0.19. Neu loi tokenizers -> pin "tokenizers==0.14.1" --no-deps
```

### A3b. *** QUAN TRONG: convert lai model float16 cho ct2 3.16 ***
Model convert bang ct2 4.x (quantization int8) KHONG chay tren ct2 3.16:
`ValueError: Conv1D: input dtype is float16 but expected dtype int8`. Phai convert lai **float16**
(runtime van quantize int8 luc chay nen van nhanh). Lam tren LAPTOP roi scp xuong:
```bash
# LAPTOP (HF cache da co vinai/PhoWhisper-small):
ct2-transformers-converter --model vinai/PhoWhisper-small \
  --output_dir /tmp/phowhisper-small-ct2-fp16 \
  --quantization float16 --copy_files preprocessor_config.json
cd /tmp/phowhisper-small-ct2-fp16   # tao vocabulary.txt cho ct2 3.16:
python3 -c "import json;t=json.load(open('vocabulary.json'));open('vocabulary.txt','w').write('\n'.join(t))"
scp -r /tmp/phowhisper-small-ct2-fp16 unitree@192.168.123.18:~/<go2_dir>/models/
```
Roi config.yaml (tren cho): `model: models/phowhisper-small-ct2-fp16`, `device: cuda`,
`compute_type: int8_float16`, `beam_size: 1` (nhanh) hoac `5` (chinh xac).

### A4. Kiểm tra GPU nhận chưa
```bash
python3 - <<'EOF'
import ctranslate2
print("CUDA devices:", ctranslate2.get_cuda_device_count())   # phai >= 1
EOF
```

### A5. Bật GPU trong config GoVoice
`config.yaml`:
```yaml
stt:
  device: "cuda"
  compute_type: "int8_float16"
  model: "models/phowhisper-small-ct2"   # GPU roi thi small tha ho, khoi can tiny
  beam_size: 5                            # GPU nhanh, beam 5 lay do chinh xac
```
→ Có GPU thì quay lại **small + beam 5** (chính xác hơn tiny + beam 1 mà vẫn nhanh hơn CPU).

### Lỗi hay gặp ĐƯỜNG A
| Lỗi | Xử lý |
|---|---|
| `libctranslate2.so.X: cannot open shared object` | `sudo ldconfig`; kiểm `echo $LD_LIBRARY_PATH` có `/usr/local/lib` |
| cmake không thấy cuDNN | `sudo apt install libcudnn8-dev`; kiểm `ls /usr/include/cudnn*.h` |
| Hết RAM khi make | `make -j2`; đóng app khác; thêm swap: `sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |
| faster-whisper đòi ct2 bản mới hơn | giữ `faster-whisper==0.10.1` (khớp ct2 v3.x); muốn bản mới → build ct2 v4.x (cần JetPack 6) |

---

## ĐƯỜNG B — JetPack 6 (nếu sau này nâng cấp): container có sẵn

JetPack 6 (L4T r36.x) có sẵn image đã build GPU:
```bash
# Cach 1 — speaches (OpenAI-compatible STT server, build san SM87):
docker run -d --name speaches --runtime nvidia -p 8000:8000 \
  -v speaches-models:/home/ubuntu/.cache/huggingface/hub \
  cbinckly/speaches:0.9.0-l4t-cuda-12.6.11-arch87

# Cach 2 — jetson-containers (build/keo image faster-whisper):
git clone https://github.com/dusty-nv/jetson-containers ~/jetson-containers
bash ~/jetson-containers/install.sh
jetson-containers run $(autotag faster-whisper)
```
Dùng cách 1 thì sửa GoVoice gọi STT qua HTTP `localhost:8000/v1/audio/transcriptions`
thay vì faster-whisper nội bộ (báo mình nếu chọn đường này, mình viết adapter ~30 dòng).

---

## Tóm tắt quyết định
- **JetPack 5 (máy bạn hiện tại):** ĐƯỜNG A — build tay 1 lần (~45'), được STT GPU vĩnh viễn.
- Đường nào xong thì STT từ ~1-1.5s (CPU tiny) → **~0.3-0.5s (GPU small)**: vừa NHANH hơn vừa CHÍNH XÁC hơn — đúng tiêu chí "vừa đúng nhất vừa nhanh nhất".
