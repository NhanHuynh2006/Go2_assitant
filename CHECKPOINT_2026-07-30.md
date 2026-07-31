# CHECKPOINT 2026-07-30 — GoVoice (bản mới nhất)

> Tổng hợp thay đổi so với CHECKPOINT_2026-07-04.md. Đọc file này để nắm trạng thái HIỆN TẠI.
> Người dùng: Nolan (Lab ISLab · ĐH Công nghệ Kỹ thuật TP.HCM, tên cũ ĐH Sư phạm Kỹ thuật; GVHD PGS.TS Lê Mỹ Hà).

---

## 0. TÓM TẮT NHANH — cách chạy
Mọi thứ chạy bằng **`config_typec.yaml`** (KHÔNG phải config.yaml). Ví dụ chính:
```bash
# Test gõ chữ (không mic/loa/robot):
python3 assistant_realtime.py --mode text  --config config_typec.yaml --no-tts
# Nói + nghe, KHÔNG cử động:
python3 assistant_realtime.py --mode voice --config config_typec.yaml
# Nói + nghe + LÀM ĐỘNG TÁC THẬT:
python3 assistant_realtime.py --mode voice --config config_typec.yaml --real
```
LLM server (`llama-server` cổng 8080) + loa robot (`go2_tts_speaker.py`) chạy như cũ. Xem RUN.md.

---

## 1. STT ĐỔI: PhoWhisper → Zipformer-VI 30M (transducer)
- STT giờ là **zipformer-vi-30M qua sherpa-onnx (ONNX transducer, CPU, int8) + hotwords** — cấu hình `stt.backend: transducer` trong config.
- **~50–150ms/câu** (thay vì ~1.8s của PhoWhisper). **STT không còn là nút thắt** — giờ LLM (~0.8–3s) mới là phần chậm nhất.
- Độ trễ mới: câu thường (luật/FAQ) ≈ **0.4s**; câu khó (LLM) ≈ **1–3s**.

## 2. MIC MỚI: type-C USB + chống nhiễu
- Mic cũ CS202 (jack 3.5) → **mic USB "USB2.0 Device"** cắm cổng type-C. Số card ALSA đổi mỗi lần cắm (hw:0,0 / hw:2,0) — `input_device: "auto"` tự tìm theo tên.
- `mic_gain: 35` (60% vỡ tiếng). Mic SNR thấp; đã thử mic robot (backend udp) → còn tệ hơn. Kế hoạch: mua lavalier/headset sau.
- **Chống nhiễu (audio_io.py):** VAD webrtcvad + **noise-gate THÍCH NGHI** — ngưỡng = max(`noise_gate_rms`, noise_floor×`noise_gate_factor`), floor tự bám mức yên (xuống nhanh/lên chậm). Config: `vad_aggressiveness 2`, `noise_gate_rms 130`, `noise_gate_factor 3.5`, `min_utterance_s 0.5`, `silence_end_ms 220`.
- Mic dỏm nên vẫn có lúc lọt nhiễu (do phần cứng). Có `assistant_ptt.py --key space` (bấm-để-nói) nếu cần sạch tuyệt đối.
- udev tự set gain khi cắm: `govoice-mic-setup.sh` + `99-govoice-mic.rules` (cài bằng sudo — xem trong file).

## 3. TẦNG HỘI-ĐÁP (mới) — 3 lớp: Reflex → FAQ → LLM
- **reflex_matcher.py**: thêm ~20 câu chat lõi (bạn là ai, làm được gì, chào, cảm ơn...) + tri thức **trường/lab ISLab/thầy Lê Mỹ Hà**.
- **faq_matcher.py + knowledge.yaml** (TANG 1.7): tra cứu ngữ nghĩa fuzzy (TF-IDF char n-gram, sklearn) → trả lời câu giao tiếp TỨC THÌ không cần LLM; chịu thiếu dấu/nói lóng. **~113 mục / 350+ cách hỏi** (trường, lab, robot, xã giao, demo, linh tinh). Ngưỡng `faq.threshold 0.55`, chặn mảnh nhiễu < 2 chữ.
- Thứ tự trong assistant_realtime.process(): combo → reflex → **FAQ** → sửa-chính-tả → LLM. Sửa lỗi va chạm dấu 'bạn'↔'bàn' trong combo_matcher.resolve_goto.
- **Mở rộng = chỉ sửa `knowledge.yaml`** (thêm mục q/a/action), không đụng code.

## 4. CHUYỂN ĐỘNG MƯỢT — bỏ cap 50cm
- config `robot`: `max_vx 0.6`, `max_vy 0.4`, `max_vyaw 1.5`, `max_duration 20`, **`max_step_m 10`** (bỏ cap 50cm — lệnh "3 mét" đi đủ 3m), giữ `require_stand_before_move`.
- reflex_matcher: VX 0.5 / VYAW 1.2; đi **1 khúc liền mạch** (MAX_CHUNK_S 30, không StopMove giữa chừng) → hết giật. Thêm "xoay bên phải/trái".

## 5. ĐỘNG TÁC ACROBATIC (mới, đã mở khóa)
- Thêm: **WalkUpright** ("đứng bằng hai chân" — 2 chân sau), **HandStand** ("trồng chuối" / "đứng 2 chân trước"), **FrontJump** ("nhảy/bật về phía trước", khác Dance1). robot_tools._ACRO_TOGGLE/_ACRO_ONESHOT; safety_guard cho phép (flips vẫn chặn).
- **Tự bật AI sport mode**: config `robot.motion_mode: ai` → RobotTools tự gọi MotionSwitcherClient().SelectMode("ai") mỗi lần `--real` (khỏi bật app điện thoại). AI mode reset khi tắt nguồn robot nên phải tự bật mỗi lần — đã tự động hóa.
- ⚠️ RỦI RO: dễ ngã, cần không gian trống + nền phẳng; firmware không cắt được giữa chừng.

## 6. MẠNG — IP tĩnh
- SSH Jetson qua wifi hotspot điện thoại "NhanHuynh": **10.32.230.18** (IP tĩnh, NetworkManager manual). LAN tới robot: 192.168.123.x (eth0), robot .161.

## 7. BACKUP & SLIDE
- `backups/2026-07-12_working.tar.gz` (trước tầng hội thoại), `_conversation.tar.gz` (có FAQ), `_acrobatic.tar.gz` (đầy đủ, mới nhất). Phục hồi: `tar -xzf backups/<file>` trong thư mục dự án.
- **GoVoice_Slides.pptx** đã cập nhật khớp bản này (STT Zipformer, FAQ, độ trễ mới, acrobatic). Bản gốc: `backups/GoVoice_Slides_before_20260729.pptx`. LƯU Ý: số 91%/82%/dataset trong slide là eval CŨ (chỉ đo lệnh) — cần đo lại nếu muốn số chuẩn.

## 9. KHỬ NHIỄU AI + MỞ KHOÁ MIC ROBOT (bổ sung cuối ngày 2026-07-30)
- **Mic robot dùng được rồi.** Nguyên nhân "mic robot còn tệ hơn" (mục 2) đã tìm ra: nền ồn của chính robot **-27.7 dBFS** đẩy ngưỡng noise-gate thích nghi lên quá cao → chặn luôn cả giọng. Đo thật: **không khử nhiễu = 0/6 câu** ở mọi mức SNR 15/10/5/0 dB.
- **`denoiser.py` (mới)**: khử nhiễu neural streaming, cắm **TRƯỚC VAD** trong `audio_io.py`. Backend **GTCRN** (23.7k tham số, model 523KB) chạy qua **sherpa-onnx — đúng thư viện STT đang dùng, không thêm dependency**. RTF **0.155** (2 thread) trên Orin NX.
- **Kết quả: 0/6 → 35/36 câu**; báo động nhầm 1 lần/30s ồn thuần. Chạy thật 35s qua toàn chuỗi: 1 lần kích hoạt nhầm.
- ⚠️⚠️ **CÁC SỐ TRONG MỤC NÀY ĐÃ LỖI THỜI — xem MỤC 14.** Toàn bộ phép đo ở mục này chạy trên audio **bị giãn 2 lần** (bug đếm kênh của bridge, tìm ra sau). Kết luận "phải bật khử nhiễu" vẫn đúng, nhưng tham số thì **ngược lại**: đo lại trên audio đúng nhịp thì **`mix: 1.0` thắng `0.9`**, và `noise_gate_factor` phải là **2.0** (không phải 3.5).
- **`config_robot_mic.yaml` (mới)** = chạy bằng mic robot. Bridge phải dùng `--gain 2.5`. `config_typec.yaml` cũng đã thêm khối `audio.denoise` (chưa đo trên mic type-C — mic không cắm lúc làm).
- Công cụ tự đo: **`test_denoise.py`** (A/B nhanh + xuất wav nghe thử), **`bench_denoise_vad.py`** (chấm cả 2 mặt: bắt được câu + số câu rác).
- Chi tiết + bảng số: **`CHONG_ON_MIC.md`**.

## 17. CHAN ECHO — BAN CUOI: mo mic khi mic THUC SU IM (2026-07-30)
Da va bang DONG HO 3 lan (bien mute -> han chot -> hang doi loa + 1 luong noi) va them
lop doi chieu VAN BAN, Go VAN nghe lai chinh no. Ly do goc: **do tre ra loa qua WebRTC
KHONG co dinh** (tai CPU, hang doi, mang) -> moi cong thuc theo thoi gian deu co luc hut.
Va van ban cung khong cuu duoc khi echo bi meo nat ("EM THICH DU LICH HOC TAP NAY KHONG"
chi con 1 tu chung voi loi Go).

**Cach chua dung**: khong doan nua — **DO TRUC TIEP**. Mic chi mo lai khi CA HAI thoa:
  (a) het han theo dong ho (nhu cu), VA
  (b) tin hieu vao da IM lien tuc >= `mute_quiet_frames` khung (mac dinh 8 = 240ms)
Co tran `mute_max_extra_s` (6s) de khong bao gio cam vinh vien neu phong on len that.
De lam duoc (b) phai **khu nhieu TRUOC ca khi dang cam mic** (audio_io) — cho phep do do
to cua tin hieu DA KHU, so voi `noise_floor` cua segmenter.

**Do qua DUNG chuoi that** (get_listener + bo canh mute + loa robot, 4 cau lien tiep gom
ca cau gioi thieu ISLab dai ~9s, KHONG ai noi):
  - **0 cau lot** (truoc do: lot deu moi luot)
  - mic **mo lai dung luc**: +6.3s, chi cho them 0.04s so voi han dong ho

**BON lop chan hien co, doc lap nhau:**
  1. mute theo dong ho (hang doi loa + 1 luong noi)      <- muc 15
  2. **mute cho toi khi mic THUC SU im**                 <- muc nay, lop CHINH
  3. doi chieu noi dung voi loi Go vua noi (>=3 tu lien tiep, trong cua so loa) <- muc 16
  4. manh <3 tu ma khong tang luat nao nhan ra           <- muc 13
  (+ cong goi ten khi dien 2 con)

## 16. LOP CHAN ECHO THEO NOI DUNG (2026-07-30 — sau 3 lan va phan THOI GIAN van sot)
- Da va co che THOI GIAN 3 lan (bien mute, han chot, hang doi loa + 1 luong noi) ma Go VAN
  nghe lai chinh no. Ly do: do tre ra loa qua WebRTC KHONG co dinh (Piper nhanh/cham, hang
  doi, mang) — ho 0.2s la du lot mot manh roi kich ca chuoi.
- **Them lop KHONG phu thuoc thoi gian**: luu 8 cau Go vua noi; cau nghe duoc co **>= 3 TU
  LIEN TIEP** trung voi loi Go -> bo thang (`_trung_loi_minh`).
- ⚠️ **Da tra gia mot lan**: ban dau dem theo TAP TU -> **"BAN LA AI" bi chan nham 67%**
  (vi chung hu tu 'ban','la') — dung cau quan trong nhat luc phong van. Doi sang **chuoi tu
  LIEN TIEP** vi echo lap DUNG THU TU con cau hoi that chi trung hu tu ROI RAC.
- ⚠️ **Rang buoc thu hai**: chi kiem tra khi `time.time() <= _speaker_free_at + 3s` (loa con
  dang / vua phat xong). Khong co no thi lenh that "di toi cho cua roi chao" bi chan nham vi
  trung "di toi cho" trong loi Go noi truoc do. Echo la hien tuong VAT LY nen bi chan trong
  thoi gian — dung dung dac diem do.
- **Do tren DUNG du lieu log that cua Nolan**: chan 6/8 echo | **0/13 cau that bi chan nham**
  (khi loa dang phat), va **0/5 bi chan** khi loa da im. Hai echo con sot ("LA GOM CHU CHO XOA")
  la manh bi nat qua khong con khop tu — vo hai, chi ra mot cau tra loi FAQ.
- Ba lop chan hien co, doc lap nhau: **mute (thoi gian)** -> **echo theo noi dung** ->
  **manh < 3 tu khong tang luat nao nhan ra**. Khi dien 2 con con them **cong goi ten**.

## 15. SUA TRIET DE ECHO + DO TRE (2026-07-30, sau khi Nolan chay thu voi giong that)
Trieu chung Nolan bao: *"no van nhan cau no noi"*, *"luc dau dung, cang ve sau cang bay"*,
*"STT co 79ms ma phat ra am thanh lau qua"*. **Ca ba deu tu MOT nguyen nhan.**
- **Nguyen nhan**: `_speak_async` tao MOT THREAD RIENG cho moi cau. Khi Go tra loi don dap,
  4-5 tien trinh **Piper chay SONG SONG** tren 6 nhan Jetson -> moi cai cham han -> tieng ra
  rai rac va tre ca chuc giay -> mo hinh hang doi loa tinh sai -> mute het han TRUOC khi tieng
  ra -> mic nghe chinh minh -> tra loi -> don them. **Vong xoay tang dan.**
- **Do duoc (tai hien dung kich ban cua Nolan, 5 cau lien tiep):**
  | | truoc | sau |
  |---|---:|---:|
  | tieng phat xong luc | +33.45s | **+17.53s** |
  | mo hinh du doan loa ranh | +18.95s | +18.69s |
  | khung CO TIENG ma mic DANG MO | 3 | **0** |
- **Sua**: bo thread-moi-cau, dung **MOT luong noi duy nhat** (`_say_q` + `_say_worker`) ->
  tong hop tuan tu. Nhanh hon 16s cho cung 5 cau, VA mo hinh mute tinh dung.
- Them: **bo cau cu** neu hang doi noi > 2 cau (dau hieu dang bi nhieu/echo kich lien tuc) —
  khan gia chi quan tam cau tra loi gan nhat.
- Luu y con lai: do tre 1 cau don ~2.0s = Piper tong hop (~0.9s) + **WebRTC ra loa (~1.1s,
  co dinh, khong giam duoc)**. Muon nhanh hon nua thi phai RUT NGAN cau tra loi (cau gioi
  thieu ISLab hien ~7s tieng).

## 14. HAI LOI NANG tim ra khi chay THAT voi giong nguoi (2026-07-30, cuoi ngay)
- **(A) `go2_audio_bridge.py` doc SAI so kenh -> audio GIAN 2 LAN.** Mic robot la **2 kenh (stereo) 48kHz**; PyAV >=12 tra `frame.layout.channels` la **tuple**, khong phai int, nen `arr.shape[0] == ch` va `ch == 2` LUON False -> frame stereo packed `(1,1920)` bi coi la mono, lay tron 1920 mau thay vi 960 -> **audio dai gap doi, cao do tut mot quang tam** -> STT khong doc ra chu nao. Nguoi dung mo ta dung: *"giong nghe vang vang, chu keo dai"*; `mic_debug.py` ghi 25s ra file 50.1s.
  - Sua: tinh so kenh tu `frame.samples`. Them **tu kiem tra troi nhip** (lech >10% so voi dong ho that thi canh bao ngay). Kiem: ghi 10s -> file 10.0s (0.98x).
  - ⚠️ **Moi tham so khu nhieu do TRUOC muc nay deu dua tren audio bi gian** -> da do lai.
- **(B) Mute khong tinh HANG DOI cua loa -> "cang ve sau cang nhieu".** `go2_tts_speaker.TTSTrack.q` xep hang phat noi tiep, nhung assistant tinh mute tu luc GUI. Cau don lai -> tieng ra tre dan -> mute het han truoc khi tieng ra -> nghe chinh minh -> tra loi -> don them -> vong xoay tang dan.
  - Sua: mo hinh hoa hang doi — `bat_dau_phat = max(gui + tre_ra_loa, loa_xong_cau_truoc)`, giu mute toi `bat_dau + dur + du_phong`. Kiem (mo phong 4 cau x 4s don dap): loa xong 17.45s, mute giu toi 18.00s -> che kin (truoc khi sua het han tu ~6s).
- **Tham so DO LAI tren giong that** (4 cau o 20cm/1m/1m to/2m to + 60s on thuan):
  - `noise_gate_factor: 3.5 -> 2.0` (3.5 chi bat 1/4 cau; 2.0 bat 4/4)
  - `denoise.mix: 0.9 -> 1.0` (**nguoc** ket luan cu — so cu do tren audio gian)
  - `denoise.gain: 1.0 -> 1.6` (dung vuot 2.0: 2.2 lam VO TIENG, bat 0/4)
  - Ket qua: bat 4/4 cau, WER 16.2%, **60s on thuan ra 0 chu rac**. Ap cho ca 5 config dung mic robot.
- **Cong cu moi: `mic_debug.py`** — ghi giong that + in RMS/nguong/VAD tung khung + STT doc thang bo qua VAD -> tach bach "tai khong nghe" vs "cong chan" vs "STT khong doc ra". `--wav` de phan tich lai ban ghi cu.
- Ban ghi on moi (dung nhip): `robot_noise60s_v2.wav`. File cu `robot_mic_noise30s.wav` la ban BI GIAN, dung dung de benchmark nua.

## 13. SỬA LỖI "CHẠY LỒNG" — Gô tự nói với chính nó (2026-07-30, chạy thật mic robot)
- Triệu chứng: mic robot ra một tràng câu cụt ("ĐẤY", "MỘT", "CẢM ƠN") và Gô trả lời liên tục dù không ai nói. **Nội dung các mảnh chính là đuôi câu Gô vừa nói** → tự nghe chính mình.
- Đo: nghe 60s **không cho Gô nói** → chỉ 1 mảnh rác (nền ồn KHÔNG phải thủ phạm). Trễ loa robot đo bằng `test_echo_delay.py`: tiếng ra sau **1.07–1.12s**, hết ở +1.84s; mute cũ giữ ~2.97s → **đủ dài rồi**.
- **Nguyên nhân thật**: `self.mute` là `threading.Event` **không có bộ đếm** — mỗi câu nói một thread, thread nào sleep xong trước là `clear()` mute, kể cả khi câu sau đang phát → hở → echo → trả lời tiếp → chạy lồng.
- **Sửa 1**: mute theo **HẠN CHÓT** (`_hold_mute` chỉ đẩy `max`, một luồng `_mute_watch` duy nhất được clear) + thêm `tts.mute_lead_s` (1.3s cho loa robot/PA, 0.1s cho loa cắm thẳng).
- **Sửa 2**: chặn mảnh nhiễu **sau khi mọi tầng luật đã thử, ngay trước LLM** — <3 từ và không tầng nào nhận ra → bỏ, không gọi LLM. (Cách dùng **danh sách từ lệnh ngắn** đã thử và HỎNG: bỏ dấu thì `đúng`==`dừng`==`dung`.)
- Kết quả: **90s không ai nói, có bật loa → 1 mảnh, bị chặn, Gô nói 0 lần**. Rác thật từ log: chặn 8/11. Câu/lệnh thật: **0/10 bị chặn nhầm**.
- ⚠️ **Thứ tự khởi động**: `go2_tts_speaker.py` TRƯỚC (đợi "san sang") rồi mới `go2_audio_bridge.py`, ngược lại loa chết `NoSdpAnswerError`.
- Công cụ mới: **`test_echo_delay.py`** (đo trễ loa→mic, in sẵn dòng config). Chi tiết: `CHONG_ON_MIC.md` mục 6b.

## 12. HAI CON CHÓ — nhảy đồng bộ + phỏng vấn từng con (mới)
- ⚠️ **KHÔNG được nối chung 2 LAN của 2 con**: cả hai main board đều `.161`, cả hai Jetson đều `.18` → đụng IP. Mỗi Jetson cắm **USB WiFi** để có địa chỉ thứ hai trên wifi chung; LAN `.123.x` của từng con vẫn nằm riêng.
- **`go2_troupe.py` (mới)** — `agent` chạy trên Jetson mỗi con, `conduct` chạy trên laptop. Nhạc trưởng phân tích beat (librosa) rồi gửi CÙNG bản đồ beat cho cả hai.
- **Nhạc phát từ LAPTOP ra loa hội trường**, không phát từ loa chó: loa chó nhỏ, và 2 con cùng phát thì lệch nhau → nghe dội. Hai con chỉ nhảy.
- **Đồng bộ không cần NTP**: bắt tay SNTP (lấy mẫu RTT nhỏ nhất) → ra lệnh "khởi động lúc giờ RIÊNG của mày". **Đã kiểm chứng: đồng hồ 2 máy lệch 3.7s → vẫn bắt đầu cách nhau 0.10ms.**
- Con thứ hai tự nhảy **lệch pha** (lắc ngược chiều) cho đẹp mắt.
- **Cổng gọi tên** (`assistant_realtime._name_gate`): mỗi con chỉ đáp khi được gọi tên; **giữ lượt 12s** để MC hỏi nối tiếp khỏi gọi lại; nghe tên con kia thì nhường lượt ngay. `dừng lại` đặt TRƯỚC cổng → phanh khẩn ăn với cả hai.
- Khớp tên theo **ranh giới từ** — lỗi đã gặp: bí danh `"cô"` nuốt chữ `"có"`. Có **cảnh báo tự động** khi tên trùng từ tiếng Việt thông dụng. Tên đang dùng: **Gô** / **Mun**.
- Configs: **`config_cho_A.yaml`**, **`config_cho_B.yaml`**. Chi tiết + trình tự buổi diễn: **`HAI_CON_CHO.md`**.
- ⚠️ **Chưa test với 2 con thật** (chỉ có 1 con) — phần chưa chắc là trễ SportClient của từng con có bằng nhau không.

## 11. LOA HỘI TRƯỜNG cho buổi biểu diễn (mới)
- Jetson **không có Bluetooth, không có jack 3.5** (chỉ HDMI) → không nối thẳng loa hội trường được. Giải pháp **không tốn tiền**: cho **laptop làm loa** (laptop có sẵn BT + jack, đang nối dây LAN với robot).
- `tts_engine.py` thêm output **`pa`** (và **`robot+pa`** ra cả hai loa): gửi NGUYÊN BYTE wav qua TCP :17892 sang laptop (khác `robot` — cái đó gửi *đường dẫn* file, laptop là máy khác nên không đọc được). Gửi ở thread riêng + timeout 2s → laptop rớt mạng KHÔNG treo robot.
- **`pc_speaker.py` (mới)** chạy trên **LAPTOP**: nhận wav → phát ra đầu ra mặc định của laptop (sounddevice, fallback paplay/aplay/ffplay).
- **`config_hoinghi.yaml` (mới)** = mic robot + loa hội trường. Nhớ sửa `pa_host` thành IP laptop.
- Thử trước buổi diễn: `python3 pc_speaker.py --test 192.168.123.99`.
- Đã test: mic bridge (`go2_audio_bridge.py`) và loa robot (`go2_tts_speaker.py`) **chạy song song được** — robot chấp nhận cả hai kết nối WebRTC.

## 10. MẠNG — không cần mua USB WiFi/BT (đã test)
- Jetson **không có radio WiFi lẫn BT** (lsusb rỗng, không wlan*, không adapter BT). WiFi6/BT/4G nằm ở main board `.161`.
- ❌ Đi ké WiFi của robot: **đã test, không được** — main board không NAT và không mở SSH để bật.
- ✅ **USB tethering từ điện thoại Android** — chỉ cần sợi cáp, driver `rndis_host`/`cdc_ether`/`cdc_ncm` đã có sẵn. Thay được cách "hotspot + IP tĩnh 10.32.230.18". (iPhone KHÔNG được — thiếu `ipheth`.)
- Cách đang chạy: laptop `.99` chia mạng qua dây. Chi tiết: **`CONNECT_WIFI.md`**.
- Webserver MBS `:9000` trong sách hướng dẫn **chưa cài** trên Jetson này (port đóng).

## 8. VIỆC CÒN LẠI / HƯỚNG ĐI
- **Mic tốt hơn** (lavalier/headset) — cải thiện độ chính xác (phần cứng).
- **LLM nhanh/thông minh hơn**: mở rộng reflex+FAQ (né LLM), thử Qwen 0.5B, hoặc stream LLM→TTS; nâng FAQ lên embedding thần kinh. (KHÔNG nên viết lại C / đưa ROS2 — phần nặng đã là C/CUDA sẵn, ROS2 chỉ thêm overhead, không nhanh hơn.)
- Đo lại độ chính xác toàn hệ sau khi thêm FAQ.
