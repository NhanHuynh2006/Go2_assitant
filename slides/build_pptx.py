#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GoVoice_Slides.pptx (16:9, theme toi) — ban KIEN TRUC · MODEL · REALTIME (17 slide)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

BG=RGBColor(0x0B,0x10,0x20); CARD=RGBColor(0x16,0x21,0x3F); LINE=RGBColor(0x24,0x34,0x56)
INK=RGBColor(0xEA,0xF2,0xFF); MUT=RGBColor(0x9F,0xB3,0xD1); ACC=RGBColor(0x22,0xD3,0xEE)
ACC2=RGBColor(0xFB,0x92,0x3B); GOOD=RGBColor(0x34,0xD3,0x99); BAD=RGBColor(0xF8,0x71,0x71)
PUR=RGBColor(0xA7,0x8B,0xFA); CODE=RGBColor(0x0E,0x1B,0x38); WHY=RGBColor(0x1C,0x15,0x30)
HLBG=RGBColor(0x13,0x30,0x1F); HL2=RGBColor(0x2A,0x1A,0x10); GREY=RGBColor(0x47,0x55,0x69)

EMU_W,EMU_H=Inches(13.333),Inches(7.5)
prs=Presentation(); prs.slide_width,prs.slide_height=EMU_W,EMU_H
BLANK=prs.slide_layouts[6]; N_TOTAL=17


def slide():
    s=prs.slides.add_slide(BLANK)
    r=s.shapes.add_shape(1,0,0,EMU_W,EMU_H)
    r.fill.solid(); r.fill.fore_color.rgb=BG; r.line.fill.background(); r.shadow.inherit=False
    s.shapes._spTree.remove(r._element); s.shapes._spTree.insert(2,r._element)
    return s


def box(s,x,y,w,h,fill=None,line=None,rad=True):
    shp=s.shapes.add_shape(5 if rad else 1,Inches(x),Inches(y),Inches(w),Inches(h))
    if fill is None: shp.fill.background()
    else: shp.fill.solid(); shp.fill.fore_color.rgb=fill
    if line is None: shp.line.fill.background()
    else: shp.line.color.rgb=line; shp.line.width=Pt(1)
    shp.shadow.inherit=False
    return shp


def text(s,x,y,w,h,runs,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,sp=5):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=tb.text_frame; tf.word_wrap=True; tf.vertical_anchor=anchor
    if runs and isinstance(runs[0],tuple): runs=[runs]
    for pi,para in enumerate(runs):
        p=tf.paragraphs[0] if pi==0 else tf.add_paragraph()
        p.alignment=align; p.space_after=Pt(sp); p.space_before=Pt(0)
        for (t,sz,col,b) in para:
            run=p.add_run(); run.text=t; run.font.size=Pt(sz); run.font.color.rgb=col
            run.font.bold=b; run.font.name='Segoe UI'
    return tb


def kicker(s,t): text(s,0.62,0.42,12,0.5,[[(t.upper(),12,ACC,True)]])
def title(s,parts): text(s,0.62,0.92,12.1,1.2,[parts])


def bullets(s,x,y,w,h,items,sz=13,col=MUT,gap=5):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=tb.text_frame; tf.word_wrap=True
    for k,it in enumerate(items):
        p=tf.paragraphs[0] if k==0 else tf.add_paragraph(); p.space_after=Pt(gap); p.space_before=Pt(0)
        if isinstance(it,list):
            for (t,c,b) in it:
                r=p.add_run(); r.text=t; r.font.size=Pt(sz); r.font.color.rgb=c; r.font.bold=b; r.font.name='Segoe UI'
        else:
            r=p.add_run(); r.text='•  '+it; r.font.size=Pt(sz); r.font.color.rgb=col; r.font.name='Segoe UI'
    return tb


def card(s,x,y,w,h,head,hcol,items,sz=12.5):
    box(s,x,y,w,h,fill=CARD,line=LINE)
    text(s,x+0.22,y+0.14,w-0.44,0.5,[[(head,15,hcol,True)]])
    bullets(s,x+0.22,y+0.72,w-0.44,h-0.85,items,sz=sz,gap=4)


def why(s,x,y,w,h,parts):
    box(s,x,y,w,h,fill=WHY,line=ACC2)
    text(s,x+0.22,y+0.1,w-0.44,h-0.2,parts,anchor=MSO_ANCHOR.MIDDLE)


def footer(s,n):
    text(s,0.62,7.05,7,0.4,[[('GoVoice · HCMUTE · Kiến trúc & Realtime',9,MUT,False)]])
    text(s,11.2,7.05,1.5,0.4,[[(f'{n} / {N_TOTAL}',9,MUT,False)]],align=PP_ALIGN.RIGHT)


def trow(s,y,cols,widths,x0=0.62,bg=CARD,cols_col=None,h=0.5,sz=12.5,bold=False):
    x=x0
    for j,(c,w) in enumerate(zip(cols,widths)):
        box(s,x,y,w,h,fill=bg,line=LINE)
        col=cols_col[j] if cols_col else INK
        text(s,x+0.12,y+0.03,w-0.2,h-0.06,[[(c,sz,col,bold)]],anchor=MSO_ANCHOR.MIDDLE)
        x+=w


# ===== 1 TITLE =====
s=slide()
text(s,0.62,1.45,12,0.5,[[('🐕🎙️  KIẾN TRÚC · MODEL · GIẢI PHÁP REALTIME · HCMUTE',14,ACC,True)]])
text(s,0.62,2.25,12.1,1.8,[
    [('GoVoice — Trợ lý giọng nói ',29,INK,True),('tiếng Việt',29,ACC,True),(' cho Unitree Go2',29,INK,True)],
    [('Hệ thống 100% on-board & độ trễ thời gian thực',29,ACC2,True)]])
text(s,0.62,4.3,12,1.0,[[('Dùng những model nào? Ghép ra sao? Làm cách nào để robot phản hồi gần như tức thì?',16,MUT,False)]])
text(s,0.62,6.1,12,0.5,[[('Nolan (Huỳnh Lê Thành Nhân) · Trường ĐH Sư phạm Kỹ thuật TP.HCM',13,MUT,False)]])

# ===== 2 PROBLEM =====
s=slide(); kicker(s,'Bài toán')
title(s,[('Hai mục tiêu ',24,INK,True),('xung đột',24,ACC,True),(': vừa ĐÚNG vừa NHANH',24,INK,True)])
card(s,0.62,2.0,6.0,1.5,'✓ ĐÚNG tuyệt đối',GOOD,['Robot vật lý — hiểu sai hướng/khoảng cách là đâm vào người/vật.'],13)
card(s,6.82,2.0,6.0,1.5,'✓ NHANH realtime',ACC,['Đợi vài giây mỗi câu là vô dụng. Phải phản hồi tức thì.'],13)
why(s,0.62,3.75,12.2,1.5,[
    [('Mâu thuẫn:  ',14,ACC2,True),('LLM thông minh nhưng chậm + hay đoán sai số; luật cứng thì nhanh + đúng',14,INK,False)],
    [('nhưng không hiểu câu phức. → GoVoice phối hợp cả hai + tối ưu từng mili-giây.',14,INK,False)]])
text(s,0.62,5.5,12,0.5,[[('100% on-board (Jetson)   ·   Không internet   ·   3 model nhỏ',13,ACC,True)]])
footer(s,2)

# ===== 3 INSIGHT =====
s=slide(); kicker(s,'Hướng giải quyết')
title(s,[('Phân loại câu → chỉ "động não" khi ',23,INK,True),('thật sự cần',23,ACC2,True)])
card(s,0.62,2.0,6.0,2.0,'⚡ ~80% câu = lệnh đơn/đếm được',GOOD,
     ['"đi thẳng", "xoay phải 2 vòng", "đi A rồi B".','→ giải bằng LUẬT, ~0ms, không cần model não.'],13)
card(s,6.82,2.0,6.0,2.0,'🧠 ~18% câu khó',ACC2,['Mơ hồ, trò chuyện, tổ hợp lạ.','→ mới dùng LLM.'],13)
why(s,0.62,4.3,12.2,1.6,[
    [('Đây là chìa khoá realtime:  ',14,ACC2,True),('không cho mọi câu chạy qua LLM (mỗi lần ~0.8s).',14,INK,False)],
    [('Né được LLM cho 82% câu = né được phần lớn độ trễ. Não AI chỉ gánh số ít câu khó nhất.',14,INK,False)]])
footer(s,3)

# ===== 4 MODELS =====
s=slide(); kicker(s,'★ Các model sử dụng')
title(s,[('3 model nhỏ, mỗi model một việc — đều chạy ',22,INK,True),('offline',22,ACC,True)])
W=[2.3,2.9,4.5,2.5]
trow(s,1.95,['Việc','Model','Chi tiết','Chạy bằng'],W,bg=LINE,cols_col=[ACC,ACC,ACC,ACC],bold=True,sz=12.5,h=0.5)
data=[('🎤 Nghe (STT)','PhoWhisper-small','ASR tiếng Việt (VinAI, ~244M, nền Whisper)','faster-whisper + CTranslate2 (fp16, GPU)',ACC),
      ('🧠 Nghĩ (LLM)','Qwen2.5-1.5B','Đã fine-tune QLoRA → GGUF Q4_K_M','llama.cpp (llama-server)',ACC),
      ('🔊 Nói (TTS)','Piper · vi_VN-vais1000','Tổng hợp giọng tiếng Việt','Piper (streaming)',ACC),
      ('✂️ Cắt câu','webrtcvad','Thuật toán (KHÔNG phải AI)','—',MUT)]
y=2.45
for v,m,d,r,mc in data:
    trow(s,y,[v,m,d,r],W,bg=CARD,cols_col=[INK,mc,MUT,MUT],sz=11,h=0.62)
    y+=0.66
why(s,0.62,5.25,12.2,1.05,[[('Điểm nhấn:  ',12.5,ACC2,True),('82% câu KHÔNG đụng model não (Qwen) — giải bằng luật. Qwen chỉ vào ~18% câu khó. Đây là "neuro-symbolic".',12.5,INK,False)]])
footer(s,4)

# ===== 5 ARCHITECTURE =====
s=slide(); kicker(s,'★ Kiến trúc & luồng dữ liệu')
title(s,[('Một câu nói chảy qua hệ thống thế nào',23,INK,True)])
def node(x,y,w,t1,t2,lc):
    box(s,x,y,w,0.85,fill=CARD,line=lc)
    text(s,x+0.06,y+0.1,w-0.12,0.7,[[(t1,12,INK,True)],[(t2,9,MUT,False)]],align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
node(0.62,1.9,2.9,'🎤 Mic','webrtcvad cắt câu',LINE)
node(3.72,1.9,2.9,'📝 STT','PhoWhisper · GPU',ACC)
node(6.82,1.9,2.9,'🔤 Chuẩn hóa','bỏ dấu',LINE)
node(9.92,1.9,2.9,'🚨 Emergency','"dừng lại"',ACC)
text(s,0.62,2.9,12,0.35,[[('↓ định tuyến — dừng ở tầng đầu tiên giải được ↓',11,MUT,False)]],align=PP_ALIGN.CENTER)
node(0.62,3.35,6.0,'⚡ Luật: Reflex + Combo','82% câu · ~0.07ms · KHÔNG model',GOOD)
node(6.82,3.35,6.0,'🧠 LLM Qwen2.5-1.5B','18% câu · ~0.8s · GBNF ép JSON',ACC2)
node(0.62,4.55,3.6,'🧹 Verifier → 🛡️ Safety','lọc bịa + kẹp an toàn',LINE)
node(4.42,4.55,3.6,'⚙️ Async Executor','vừa làm vừa nghe',LINE)
node(8.22,4.55,2.2,'🦿 Robot','SportClient',GOOD)
node(10.62,4.55,2.2,'🔊 Piper → loa','',ACC2)
text(s,0.62,5.6,12.2,0.6,[[('Tất cả chạy trên Jetson trong robot; mic/loa robot ra-vào qua cầu WebRTC. Không bước nào gọi internet.',12,MUT,False)]])
footer(s,5)

# ===== 6 STT =====
s=slide(); kicker(s,'Tầng nghe · STT (nút thắt thời gian)')
title(s,[('PhoWhisper trên GPU: ',24,INK,True),('2–4s → 1.8s',24,ACC,True)])
bullets(s,0.62,1.95,7.4,2.0,[
    [('PhoWhisper-small ',INK,True),('— ASR tiếng Việt chuyên dụng (VinAI).',MUT,False)],
    [('CTranslate2 (fp16) + faster-whisper ',INK,True),('chạy GPU Jetson (CUDA 11.4).',MUT,False)],
    [('2 lá chắn: ',INK,True),('mớm từ vựng + lọc ảo giác (no_speech>0.6, logprob<−1.0).',MUT,False)]],sz=13,gap=7)
why(s,0.62,4.1,7.4,1.7,[
    [('Vì sao tốn thời gian nhất? ',12.5,ACC2,True),('Encoder Whisper xử lý cả cửa sổ 30s âm thanh.',12.5,INK,False)],
    [('~1.8s/câu — chiếm ~80% tổng độ trễ. Đưa lên GPU là cải tiến realtime lớn nhất.',12.5,INK,False)]])
box(s,8.32,1.95,4.5,3.85,fill=CARD,line=LINE)
text(s,8.32,2.2,4.5,0.5,[[('Độ trễ STT / câu',13,MUT,False)]],align=PP_ALIGN.CENTER)
text(s,8.32,2.75,4.5,0.6,[[('CPU 2–4 s',20,BAD,True)]],align=PP_ALIGN.CENTER)
text(s,8.32,3.5,4.5,1.0,[[('1.8 s',52,GOOD,True)]],align=PP_ALIGN.CENTER)
text(s,8.32,4.95,4.5,0.6,[[('GPU Jetson · PhoWhisper-small fp16',12,MUT,False)]],align=PP_ALIGN.CENTER)
footer(s,6)

# ===== 7 PARSE (GON) =====
s=slide(); kicker(s,'Nhận & phân tích lệnh (tóm tắt)')
title(s,[('Nhận chữ → chia câu → khớp từng vế → ghép lệnh',22,INK,True)])
bullets(s,0.62,1.95,7.4,2.6,[
    [('① Nhận ',INK,True),('câu chữ đã bỏ dấu từ STT.',MUT,False)],
    [('② Chia câu ',INK,True),('tại từ nối: rồi / sau đó / tiếp theo / xong.',MUT,False)],
    [('③ Phân tích từng vế: ',INK,True),('động từ (đi/xoay), số + đơn vị (mét/giây/độ/vòng), hướng.',MUT,False)],
    [('④ Ghép ',INK,True),('thành chuỗi hành động đúng thứ tự.',MUT,False)]],sz=13,gap=7)
text(s,0.62,4.7,7.4,0.6,[[('Nếu một vế không khớp luật → giao cả câu cho LLM (an toàn).',12,MUT,False)]])
card(s,8.32,1.95,4.5,3.3,'Ví dụ',ACC,
     ['"đi thẳng 3 mét rồi xoay phải"','↓ chia 2 vế ↓','đi thẳng 3 mét → move (3÷0.35=8.6s)','xoay phải → spin 90°','⏱ ~0.07 ms · không cần LLM'],12)
text(s,0.62,5.5,12,0.5,[[('(Chi tiết quy tắc — bỏ dấu, chẻ lệnh, từ chối — em sẽ nói thêm khi trình bày.)',11,MUT,False)]])
footer(s,7)

# ===== 8 LLM =====
s=slide(); kicker(s,'Tầng não · LLM')
title(s,[('Qwen2.5-1.5B fine-tune + ',22,INK,True),('ép JSON',22,ACC,True),(' cho 18% câu khó',22,INK,True)])
card(s,0.62,1.95,3.95,2.4,'🧠 Model nhỏ chuyên việc',ACC,['Qwen2.5-1.5B, fine-tune QLoRA 4-bit. Đủ nhỏ on-board, đủ giỏi vì chỉ làm 1 việc: sinh JSON lệnh.'],12.5)
card(s,4.72,1.95,3.95,2.4,'📐 GBNF Grammar',ACC,['Ép sinh JSON đúng schema → không lỗi parse, không lệnh rác, ít token → nhanh hơn.'],12.5)
card(s,8.82,1.95,4.0,2.4,'🗄️ cache_prompt',ACC,['Giữ KV-cache system prompt → mỗi câu chỉ xử lý phần mới.'],12.5)
why(s,0.62,4.65,12.2,1.4,[
    [('Vì sao 1.5B mà đủ? ',13,ACC2,True),('Việc rất hẹp (câu Việt → JSON lệnh) + fine-tune đúng phân phối →',13,INK,False)],
    [('không cần model lớn. → chạy lọt Jetson, ~780ms/câu, và chỉ 18% câu phải dùng.',13,INK,False)]])
footer(s,8)

# ===== 9 TTS =====
s=slide(); kicker(s,'Tầng nói · TTS')
title(s,[('Piper ',24,INK,True),('streaming',24,ACC,True),(': phát tiếng sau ~100ms',24,INK,True)])
bullets(s,0.62,2.0,7.4,3.0,[
    [('Piper ',INK,True),('giọng vi_VN-vais1000-medium — tổng hợp tiếng Việt, nhẹ.',MUT,False)],
    [('Vừa sinh vừa phát ',INK,True),('từng đoạn: ra tiếng sau ~100ms, KHÔNG đợi sinh hết câu.',MUT,False)],
    'Câu dài cỡ nào, tiếng vẫn bật ra gần như ngay lập tức.',
    'Tiếng đi ra loa robot qua cầu WebRTC.'],sz=13,gap=9)
box(s,8.32,2.0,4.5,3.0,fill=CARD,line=LINE)
text(s,8.32,2.3,4.5,0.5,[[('Time-to-first-sound',13,MUT,False)]],align=PP_ALIGN.CENTER)
text(s,8.32,2.9,4.5,1.0,[[('~100 ms',46,ACC,True)]],align=PP_ALIGN.CENTER)
text(s,8.32,4.3,4.5,0.5,[[('phát ngay, không đợi cả câu',12,MUT,False)]],align=PP_ALIGN.CENTER)
footer(s,9)

# ===== 10 REALTIME STRATEGY =====
s=slide(); kicker(s,'★ Chiến lược REALTIME'); title(s,[('6 đòn cắt độ trễ',24,INK,True)])
cards=[('1 · STT lên GPU','PhoWhisper qua CTranslate2 trên GPU: 2–4s → 1.8s. Cắt nút thắt lớn nhất.'),
       ('2 · Né LLM 82% câu','Luật giải ~0.07ms thay vì ~780ms. Tiết kiệm phần lớn độ trễ.'),
       ('3 · GBNF ít token','Output JSON ngắn → LLM sinh ít token → nhanh hơn khi buộc dùng.'),
       ('4 · cache_prompt','Bỏ chi phí lặp lại system prompt dài mỗi câu.'),
       ('5 · TTS streaming','Phát tiếng sau 100ms, không đợi sinh hết câu.'),
       ('6 · Async execution','Robot làm song song lúc nghe câu kế → giảm ~30% chuỗi lệnh.')]
for k,(h,b) in enumerate(cards):
    x=0.62+(k%3)*4.07; yy=1.95+(k//3)*1.75
    card(s,x,yy,3.85,1.6,h,GOOD,[b],11.5)
why(s,0.62,5.5,12.2,0.85,[[('Triết lý: ',12.5,ACC2,True),('mỗi tầng đều hỏi "có cách nào không phải đợi không?" — GPU thay CPU, luật thay LLM, streaming thay batch, song song thay tuần tự.',12.5,INK,False)]])
footer(s,10)

# ===== 11 LATENCY TABLE =====
s=slide(); kicker(s,'★★★ Số liệu độ trễ — từng tầng')
title(s,[('Từ lúc nói xong → Gô bắt đầu đáp',24,INK,True)])
W=[6.4,3.4,2.4]
trow(s,1.9,['Giai đoạn','Bộ phận','Thời gian'],W,bg=LINE,cols_col=[ACC,ACC,ACC],bold=True,h=0.5)
rows=[('1. Cắt câu (đợi im lặng)','webrtcvad','~270 ms',CARD,[INK,MUT,INK]),
      ('2. Nhận dạng giọng nói','PhoWhisper-small (GPU)','~1800 ms  ⟵ nút thắt',CARD,[INK,MUT,BAD]),
      ('3a. Lập kế hoạch — luật (82%)','Reflex + Combo','~0.07 ms',CARD,[INK,MUT,GOOD]),
      ('3b. Lập kế hoạch — LLM (18%)','Qwen2.5-1.5B','~780 ms',CARD,[INK,MUT,INK]),
      ('4. Phát tiếng đầu','Piper (streaming)','~100 ms',CARD,[INK,MUT,INK])]
y=2.4
for a,b,c,bg,cc in rows:
    trow(s,y,[a,b,c],W,bg=bg,cols_col=cc,sz=12.5,h=0.52); y+=0.55
trow(s,y+0.05,['TỔNG — câu thường (82%, không LLM)','','≈ 2.2 giây'],W,bg=HLBG,cols_col=[GOOD,GOOD,GOOD],bold=True,h=0.52); y+=0.62
trow(s,y+0.05,['TỔNG — câu khó (18%, có LLM)','','≈ 3.0 giây'],W,bg=HL2,cols_col=[ACC2,ACC2,ACC2],bold=True,h=0.52)
text(s,0.62,6.55,12.2,0.4,[[('🦿 Robot bắt đầu cử động song song với lúc Gô nói (async) — không cộng dồn thêm.',11.5,MUT,False)]])
footer(s,11)

# ===== 12 TIMELINE =====
s=slide(); kicker(s,'★★ Timeline end-to-end')
title(s,[('STT chiếm phần lớn — phần còn lại gần như "miễn phí"',21,INK,True)])
def track(y,segs,total):
    x=0.62; full=12.2
    for label,ms,col in segs:
        w=full*ms/total
        box(s,x,y,max(w,0.12),0.95,fill=col,line=BG)
        if w>0.6:
            text(s,x,y+0.12,w,0.7,[[(label,10.5,BG,True)],[(f'{ms}ms' if ms<1000 else f'~{ms}ms',9,BG,False)]],
                 align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
        x+=w
text(s,0.62,1.95,12,0.4,[[('Câu thường (không LLM) — tổng ≈ 2.2 giây:',12.5,MUT,False)]])
track(2.4,[('VAD',270,GREY),('STT — PhoWhisper GPU',1800,ACC),('Luật',60,GOOD),('TTS',100,ACC2)],2230)
text(s,0.62,3.75,12,0.4,[[('Câu khó (có LLM Qwen) — tổng ≈ 3.0 giây:',12.5,MUT,False)]])
track(4.2,[('VAD',270,GREY),('STT',1800,ACC),('LLM Qwen',780,PUR),('TTS',100,ACC2)],2950)
why(s,0.62,5.5,12.2,0.95,[[('Kết luận realtime: ',12.5,ACC2,True),('muốn nhanh hơn nữa phải tấn công STT (model nhỏ hơn / tinh chỉnh cửa sổ) — 3 phần kia đã gần tối ưu hết.',12.5,INK,False)]])
footer(s,12)

# ===== 13 ASYNC + SAFETY =====
s=slide(); kicker(s,'Thực thi realtime + An toàn')
title(s,[('Vừa làm vừa nghe, và luôn ',24,INK,True),('an toàn',24,GOOD,True)])
card(s,0.62,1.95,6.0,2.7,'⚙️ Async Executor (SmolVLA)',ACC,
     ['Hành động chạy thread riêng + hàng đợi.','Vòng chính vẫn nghe + STT câu kế → robot không "điếc".','Giảm ~30% chuỗi lệnh; phanh khẩn cấp chèn ngang.'],12.5)
card(s,6.82,1.95,6.0,2.7,'🛡️ Safety Guard',GOOD,
     ['Kẹp vận tốc/thời gian (vx≤0.6, dur≤6s).','Chặn động tác nguy hiểm (lộn/trồng chuối).','Tự đứng dậy trước khi đi; "dừng lại" ưu tiên tuyệt đối.'],12.5)
why(s,0.62,4.95,12.2,1.1,[[('Vì sao tách thực thi ra thread riêng? ',12.5,ACC2,True),('Để bước "nghe + nghĩ" (~2s STT) KHÔNG bị khoá lúc robot đang cử động → mượt, realtime.',12.5,INK,False)]])
footer(s,13)

# ===== 14 FINETUNE+DATASET =====
s=slide(); kicker(s,'Huấn luyện model não')
title(s,[('Fine-tune Qwen trên dataset ',23,INK,True),('tự sinh, tái lập',23,ACC,True)])
card(s,0.62,1.95,6.0,2.6,'🔧 QLoRA 4-bit',ACC,
     ['Train adapter nhỏ trên 1 GPU RTX 4060 (~70 phút). Merge → GGUF Q4_K_M chạy Jetson.',
      'Qwen gốc 5.7% → fine-tune 61.7%.'],13)
card(s,6.82,1.95,6.0,2.6,'📦 Dataset (~4.700 mẫu)',ACC,
     ['Sinh bằng luật, seed cố định (tái lập 100%). Nhãn vàng dùng đúng quy ước tốc độ + cùng prompt như lúc chạy. Augment "mất dấu" mô phỏng lỗi STT.'],13)
why(s,0.62,4.85,12.2,1.1,[[('Mấu chốt: ',12.5,ACC2,True),('model học đúng "luật chơi" hệ thống thực thi (vx=0.35, schema JSON, chẻ lệnh) → không lệch giữa train và chạy.',12.5,INK,False)]])
footer(s,14)

# ===== 15 RESULTS =====
s=slide(); kicker(s,'Kết quả'); title(s,[('Độ chính xác & phân bổ tải',24,INK,True)])
W=[5.0,1.4]
trow(s,2.0,['Cấu hình','Đúng'],W,bg=LINE,cols_col=[ACC,ACC],bold=True,h=0.55)
rr=[('Qwen gốc + few-shot','5.7%',CARD,[INK,BAD]),('+ Fine-tune (LLM thuần)','61.7%',CARD,[INK,ACC2]),
    ('Full system (Luật + LLM + Verifier)','91.0%',HLBG,[GOOD,GOOD])]
y=2.55
for a,b,bg,cc in rr:
    trow(s,y,[a,b],W,bg=bg,cols_col=cc,sz=12.5,h=0.58,bold=(bg==HLBG)); y+=0.62
text(s,0.62,4.6,6.4,0.7,[[('Fine-tune +56đ · kiến trúc neuro-symbolic +29.3đ (gần ngang nhau).',12,MUT,False)]])
box(s,7.2,1.95,5.6,3.5,fill=CARD,line=LINE)
text(s,7.2,2.15,5.6,1.0,[[('82%',46,ACC,True)]],align=PP_ALIGN.CENTER)
text(s,7.2,3.25,5.6,0.5,[[('câu giải bằng LUẬT (~0.07ms, không LLM)',12,MUT,False)]],align=PP_ALIGN.CENTER)
text(s,7.45,4.0,5.2,0.5,[[('📊 Định tuyến 300 câu: Combo 222 · Reflex 23 · LLM 55',12,INK,False)]])
text(s,7.45,4.55,5.2,0.5,[[('⏱ LLM tb 780ms · p95 1197ms · STT 1.8s · TTS 100ms',12,INK,False)]])
footer(s,15)

# ===== 16 CONCLUSION =====
s=slide(); kicker(s,'Kết luận')
title(s,[('Đúng',21,GOOD,True),(' bằng luật · ',21,INK,True),('Nhanh',21,ACC,True),(' bằng định tuyến + GPU · ',21,INK,True),('Linh hoạt',21,ACC2,True),(' bằng LLM',21,INK,True)])
card(s,0.62,2.05,6.0,3.2,'✓ Đạt được',GOOD,
     ['3 model nhỏ (PhoWhisper · Qwen2.5-1.5B · Piper) chạy 100% on-board.','Phản hồi ≈ 2.2s (câu thường) / 3.0s (câu khó).','91% chính xác · 82% câu không cần LLM.'],13.5)
card(s,6.82,2.05,6.0,3.2,'→ Hướng tăng tốc tiếp',ACC2,
     ['Tấn công STT (nút thắt 1.8s): model nhỏ hơn / cắt cửa sổ.','Thử Qwen 0.5B → LLM nhanh ~2×.','Đo WER mic robot vs mic ngoài; triển khai không dây.'],13.5)
footer(s,16)

# ===== 17 THANKS =====
s=slide()
text(s,0.62,2.0,12,0.8,[[('🐕💬',48,INK,True)]],align=PP_ALIGN.CENTER)
text(s,0.62,3.1,12,1.0,[[('Cảm ơn đã lắng nghe!',38,INK,True)]],align=PP_ALIGN.CENTER)
text(s,0.62,4.3,12,0.6,[[('GoVoice — 3 model on-board · luật + LLM · phản hồi ~2.2 giây',17,MUT,False)]],align=PP_ALIGN.CENTER)
text(s,0.62,5.5,12,0.5,[[('PhoWhisper · Qwen2.5-1.5B · Piper — 91% · 100% local · Hỏi đáp',14,ACC,True)]],align=PP_ALIGN.CENTER)

prs.save('GoVoice_Slides.pptx')
print('SAVED GoVoice_Slides.pptx ·',len(prs.slides._sldIdLst),'slides')
