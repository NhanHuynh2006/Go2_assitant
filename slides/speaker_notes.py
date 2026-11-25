#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
speaker_notes.py — KICH BAN THUYET TRINH cho GoVoice (ban 17 slide: Model · Realtime · So lieu).
Chay:  python3 speaker_notes.py
  -> KICH_BAN_THUYET_TRINH.md  + nhung notes vao GoVoice_Slides.pptx (Presenter View)
"""
import os

NOTES = [
("1", "Bìa", 30,
"""Em xin chào thầy cô và các bạn. Em là Nhân, trình bày đề tài GoVoice — trợ lý giọng nói tiếng Việt
cho robot chó Unitree Go2. Điểm đặc biệt là toàn hệ thống chạy 100% ngay trên robot, không cần internet.
Hôm nay em tập trung vào ba thứ: dùng những MODEL nào, ghép chúng thành KIẾN TRÚC ra sao, và làm cách
nào để robot phản hồi gần như tức thì — kèm SỐ LIỆU độ trễ cụ thể.
[Nhấn: model · kiến trúc · realtime + số liệu]"""),

("2", "Bài toán", 40,
"""Bài toán có hai mục tiêu xung đột. Một là ĐÚNG tuyệt đối — robot là vật thật, hiểu sai hướng hay khoảng
cách là đâm vào người. Hai là NHANH — đợi vài giây mỗi câu thì vô dụng. Mâu thuẫn nằm ở chỗ: LLM thì
thông minh nhưng chậm và hay đoán sai số; còn luật cứng thì nhanh và đúng nhưng không hiểu câu phức.
GoVoice giải bằng cách phối hợp cả hai và tối ưu từng mili-giây.
[Nhấn: đây là cái móc — vừa đúng vừa nhanh]"""),

("3", "Hướng giải quyết", 40,
"""Chìa khoá là phân loại câu trước. Khoảng 80% câu thực tế là lệnh đơn hoặc đếm được — "đi thẳng",
"xoay phải hai vòng", "đi A rồi B" — em giải bằng LUẬT, gần như 0 mili-giây, không cần model não nào.
Chỉ khoảng 18% câu khó, mơ hồ hay trò chuyện, mới đưa lên LLM. Đây chính là chìa khoá realtime: né được
LLM cho 82% câu là né được phần lớn độ trễ, vì mỗi lần gọi LLM tốn khoảng 0.8 giây.
[Nhấn: 80% câu không cần model não]"""),

("4", "Các model sử dụng", 55,
"""Đây là slide quan trọng để thầy cô nắm rõ em dùng gì. Hệ thống có ba model nhỏ, mỗi model một việc,
tất cả chạy offline. Thứ nhất, để NGHE, em dùng PhoWhisper bản small — đây là model nhận dạng giọng nói
tiếng Việt của VinAI, khoảng 244 triệu tham số, nền tảng là Whisper. Thứ hai, để NGHĨ, em dùng Qwen2.5
phiên bản 1.5 tỉ tham số của Alibaba, mà em đã fine-tune lại rồi xuất ra định dạng GGUF chạy bằng llama.cpp.
Thứ ba, để NÓI, em dùng Piper với giọng tiếng Việt. Còn webrtcvad chỉ là thuật toán cắt câu, không phải AI.
Điểm em muốn nhấn mạnh: 82% câu KHÔNG hề đụng tới model não Qwen — chúng được giải bằng luật. Qwen chỉ
nhảy vào 18% câu khó. Đây gọi là kiến trúc neuro-symbolic, lai giữa luật và học máy.
[Nhấn: 3 model + 82% không cần Qwen]"""),

("5", "Kiến trúc & luồng dữ liệu", 55,
"""Đây là toàn cảnh đường đi một câu nói. Mic thu, webrtcvad cắt ra từng câu. STT — tức PhoWhisper trên GPU
— chuyển thành chữ. Em chuẩn hóa bằng cách bỏ dấu, rồi kiểm tra khẩn cấp: nghe "dừng lại" là dừng ngay.
Phần lõi là định tuyến, dừng ở tầng đầu tiên giải được: 82% câu đi qua nhánh LUẬT — Reflex cộng Combo —
chỉ tốn 0.07 mili-giây và không dùng model nào; 18% còn lại mới qua LLM Qwen. Sau đó plan đi qua bộ kiểm
chứng và lớp an toàn, rồi bộ thực thi bất đồng bộ điều khiển robot, đồng thời Piper đọc câu trả lời ra loa.
Toàn bộ chạy trên Jetson trong robot; mic và loa ra vào qua cầu WebRTC, không bước nào gọi internet.
[Nhấn: 2 nhánh luật/LLM + tất cả on-board]"""),

("6", "STT — nút thắt thời gian", 50,
"""Tầng nghe dùng PhoWhisper, và đây chính là chỗ tốn thời gian nhất nên em nói kỹ. Em tăng tốc bằng
CTranslate2 lượng tử fp16 cộng faster-whisper, chạy trên GPU của Jetson. Có hai lá chắn chống nghe sai:
mớm trước từ vựng lệnh, và lọc ảo giác bằng hai ngưỡng xác suất. Vì sao đây là nút thắt? Vì encoder của
Whisper phải xử lý cả cửa sổ 30 giây âm thanh, nên mất khoảng 1.8 giây mỗi câu — chiếm tới 80% tổng độ
trễ. Trước đây chạy CPU mất 2 đến 4 giây; đưa lên GPU là cải tiến realtime lớn nhất của em.
[Nhấn: 1.8s = 80% độ trễ → đây là bottleneck]"""),

("7", "Nhận & phân tích lệnh (gọn)", 40,
"""Phần phân tích câu em xin nói tóm tắt. Sau khi có câu chữ đã bỏ dấu, hệ thống làm bốn bước: một là nhận
câu; hai là chia câu tại các từ nối như "rồi", "sau đó"; ba là phân tích từng vế — tìm động từ, con số
kèm đơn vị mét giây độ vòng, và hướng trái phải; bốn là ghép thành chuỗi hành động đúng thứ tự. Ví dụ
"đi thẳng 3 mét rồi xoay phải" chia thành hai vế, mỗi vế giải bằng luật, tổng cộng chỉ 0.07 mili-giây.
Nếu một vế không khớp luật thì giao cả câu cho LLM cho an toàn. Các quy tắc tinh tế hơn em sẽ nói thêm
nếu thầy cô quan tâm.
[Nhấn: nói nhanh phần này — chỉ minh hoạ cơ chế]"""),

("8", "LLM — Qwen2.5-1.5B", 45,
"""Với 18% câu khó, em dùng LLM là Qwen2.5 1.5 tỉ tham số đã fine-tune. Có ba điểm kỹ thuật. Thứ nhất,
model nhỏ chuyên việc: vì nó chỉ phải sinh JSON lệnh robot nên 1.5 tỉ tham số là đủ, không cần model lớn.
Thứ hai, em dùng văn phạm GBNF để ép model chỉ sinh JSON đúng cấu trúc — không lỗi parse, không lệnh rác,
và quan trọng là ít token hơn nên nhanh hơn. Thứ ba, cache_prompt giữ lại bộ nhớ đệm của prompt nên mỗi
câu chỉ xử lý phần mới. Kết quả khoảng 780 mili-giây mỗi câu, và nhớ là chỉ 18% câu phải trả chi phí này.
[Nhấn: model nhỏ + GBNF vừa đúng vừa nhanh]"""),

("9", "TTS — Piper streaming", 35,
"""Tầng nói dùng Piper với giọng tiếng Việt. Điểm hay là chế độ streaming: em vừa tổng hợp vừa phát từng
đoạn, nên tiếng bật ra chỉ sau khoảng 100 mili-giây, không phải đợi sinh xong cả câu. Dù câu dài bao nhiêu
thì robot vẫn lên tiếng gần như ngay lập tức. Tiếng đi ra loa của robot qua cầu WebRTC.
[Nhấn: 100ms — phát ngay không đợi cả câu]"""),

("10", "Chiến lược realtime", 50,
"""Slide này tổng hợp sáu đòn em dùng để cắt độ trễ. Một, đưa STT lên GPU, từ 2-4 giây xuống 1.8 giây.
Hai, né LLM cho 82% câu, dùng luật 0.07 mili-giây thay vì 780. Ba, dùng GBNF để output ngắn, LLM sinh ít
token nên nhanh hơn khi buộc phải dùng. Bốn, cache_prompt bỏ chi phí lặp prompt. Năm, TTS streaming phát
sau 100 mili-giây. Sáu, thực thi bất đồng bộ để robot làm song song lúc nghe câu kế. Triết lý chung là ở
mỗi tầng đều hỏi: có cách nào không phải đợi không — GPU thay CPU, luật thay LLM, streaming thay batch,
song song thay tuần tự.
[Nhấn: đây là phần "hướng giải quyết realtime" thầy cô hỏi]"""),

("11", "Số liệu độ trễ từng tầng", 55,
"""Đây là bảng số liệu quan trọng nhất, đo từ lúc người nói xong tới lúc Gô bắt đầu đáp. Bước cắt câu chờ
im lặng mất khoảng 270 mili-giây. Nhận dạng giọng nói bằng PhoWhisper trên GPU mất khoảng 1800 mili-giây
— đây là nút thắt rõ ràng. Lập kế hoạch bằng luật cho 82% câu chỉ 0.07 mili-giây, còn nếu phải dùng LLM
thì thêm khoảng 780. Phát tiếng đầu mất 100 mili-giây. Cộng lại: câu thường khoảng 2.2 giây, câu khó có
LLM khoảng 3 giây. Và lưu ý robot bắt đầu cử động song song với lúc Gô nói nhờ cơ chế bất đồng bộ, nên
không cộng dồn thêm thời gian.
[Nhấn: đọc rõ từng con số — đây là slide số liệu]"""),

("12", "Timeline end-to-end", 45,
"""Slide này minh họa trực quan: nhìn thanh thời gian sẽ thấy STT chiếm gần hết, ba phần còn lại gần như
không đáng kể. Câu thường tổng khoảng 2.2 giây, trong đó riêng STT đã 1.8 giây. Câu khó thì có thêm khối
LLM màu tím khoảng 780 mili-giây. Kết luận về realtime là: nếu muốn nhanh hơn nữa thì phải tấn công vào
STT — dùng model nhỏ hơn hoặc tinh chỉnh cửa sổ âm thanh — vì ba phần kia đã gần như tối ưu hết mức rồi.
[Nhấn: STT là chỗ duy nhất còn cải thiện được]"""),

("13", "Async + Safety", 45,
"""Hai cơ chế đảm bảo vừa realtime vừa an toàn. Bộ thực thi bất đồng bộ, lấy ý tưởng từ SmolVLA, cho hành
động chạy trong luồng riêng, nên vòng chính vẫn tiếp tục nghe và nhận dạng câu kế — robot không bị điếc
lúc đang làm, và giảm khoảng 30% thời gian chuỗi lệnh. Lớp an toàn thì kẹp vận tốc, chặn động tác nguy
hiểm, tự đứng dậy trước khi đi, và lệnh dừng lại có ưu tiên tuyệt đối. Vì sao tách thực thi ra luồng riêng?
Để bước nghe và nghĩ tốn khoảng 2 giây không bị khoá trong lúc robot đang cử động, nhờ vậy cảm giác mượt.
[Nhấn: tách luồng = mượt; safety = clamp + chặn]"""),

("14", "Fine-tune & Dataset", 40,
"""Về huấn luyện model não. Em dùng QLoRA 4-bit, chỉ train một adapter nhỏ trên một GPU RTX 4060 trong
khoảng 70 phút, rồi gộp và xuất ra GGUF chạy trên Jetson. Hiệu quả rõ rệt: Qwen gốc chỉ 5.7%, sau fine-tune
lên 61.7%. Dữ liệu khoảng 4.700 mẫu, sinh bằng luật với seed cố định nên tái lập 100%, nhãn vàng dùng đúng
quy ước tốc độ và cùng prompt như lúc chạy, cộng thêm augment mất dấu để mô phỏng lỗi STT. Mấu chốt là
model học đúng luật chơi mà hệ thống thực thi nên không lệch giữa lúc train và lúc chạy.
[Nhấn: 5.7 → 61.7 nhờ fine-tune đúng quy ước]"""),

("15", "Kết quả", 50,
"""Đây là kết quả tổng. Bảng bên trái là ablation trên 300 câu test: Qwen gốc 5.7%, sau fine-tune 61.7%,
và khi ghép đầy đủ hệ thống thì lên 91%. Điều đáng nói là fine-tune đóng góp 56 điểm, còn kiến trúc
neuro-symbolic đóng góp thêm 29.3 điểm — gần ngang nhau, chứng minh giá trị của hướng lai luật và học máy.
Bên phải: 82% câu được giải bằng luật chỉ 0.07 mili-giây không cần LLM; định tuyến cụ thể là Combo 222 câu,
Reflex 23, LLM 55. Về tốc độ: LLM trung bình 780 mili-giây, STT 1.8 giây, TTS 100 mili-giây.
[Nhấn: 5.7 → 61.7 → 91; và 82% không cần LLM]"""),

("16", "Kết luận", 40,
"""Tóm lại, triết lý của GoVoice là đúng bằng luật, nhanh bằng định tuyến thông minh cộng GPU, và linh hoạt
bằng LLM khi cần. Em đạt được: ba model nhỏ là PhoWhisper, Qwen2.5-1.5B và Piper chạy 100% trên robot;
phản hồi khoảng 2.2 giây cho câu thường và 3 giây cho câu khó; 91% chính xác với 82% câu không cần LLM.
Hướng tăng tốc tiếp theo là tấn công nút thắt STT, thử model 0.5 tỉ tham số để LLM nhanh gấp đôi, đo WER
và triển khai không dây.
[Nhấn: nhắc lại triết lý 3 vế + con số chính]"""),

("17", "Cảm ơn & Hỏi đáp", 20,
"""Phần trình bày của em đến đây là hết. Em xin cảm ơn thầy cô và các bạn, rất mong nhận được câu hỏi và
góp ý.
[Câu hỏi hay gặp: Vì sao không dùng cloud? Vì sao chọn 1.5B? Bottleneck ở đâu (STT)? Combo khác gì để LLM
tự chẻ? Số liệu đo trên tập nào (300 câu test chưa train)?]"""),
]


def make_markdown():
    total=sum(t for _,_,t,_ in NOTES)
    L=["# 🎤 KỊCH BẢN THUYẾT TRÌNH — GoVoice (17 slide · Model · Realtime · Số liệu)\n",
       f"> Tổng thời lượng gợi ý: **~{total//60} phút {total%60} giây**. Phần `[ngoặc vuông]` là nhắc riêng cho người nói, KHÔNG đọc to.\n",
       "\n---\n"]
    for num,title,secs,body in NOTES:
        L.append(f"\n## Slide {num} — {title}  ·  ⏱ ~{secs}s\n")
        L.append(body.strip()+"\n")
    L.append("\n---\n\n## 📋 Mẹo trình bày\n")
    L.append("- **3 slide đinh phải nói chậm, rõ:** slide 4 (3 model), slide 11 (bảng số liệu độ trễ), slide 15 (5.7→61.7→91).\n")
    L.append("- **Nếu thầy cô hỏi 'realtime làm sao':** mở slide 10 + 11 + 12 (chiến lược + số liệu + timeline).\n")
    L.append("- **Nếu thiếu giờ:** lướt nhanh slide 7, 14.\n")
    L.append("- Luôn quay về từ khoá: **3 model on-board · 82% không cần LLM · STT là nút thắt 1.8s · phản hồi ~2.2s**.\n")
    with open("KICH_BAN_THUYET_TRINH.md","w",encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[md ] KICH_BAN_THUYET_TRINH.md  (~{total//60}m{total%60}s)")


def inject_pptx():
    pptx="GoVoice_Slides.pptx"
    if not os.path.exists(pptx):
        print(f"[!!] khong thay {pptx} — chay build_pptx.py truoc."); return
    from pptx import Presentation
    prs=Presentation(pptx); slides=list(prs.slides)
    for i,(num,title,secs,body) in enumerate(NOTES):
        if i>=len(slides): break
        slides[i].notes_slide.notes_text_frame.text=f"[{title} · ~{secs}s]\n\n{body.strip()}"
    prs.save(pptx)
    print(f"[ppt] da nhung notes vao {pptx} ({len(NOTES)} slide) — xem o Presenter View")


if __name__=="__main__":
    make_markdown(); inject_pptx()
