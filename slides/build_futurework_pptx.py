#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GoVoice_FutureWork.pptx — 4 slide dinh huong phat trien STT (RNN-T vs Audio-LLM)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

BG=RGBColor(0x0B,0x10,0x20); CARD=RGBColor(0x16,0x21,0x3F); LINE=RGBColor(0x24,0x34,0x56)
INK=RGBColor(0xEA,0xF2,0xFF); MUT=RGBColor(0x9F,0xB3,0xD1); ACC=RGBColor(0x22,0xD3,0xEE)
ACC2=RGBColor(0xFB,0x92,0x3B); GOOD=RGBColor(0x34,0xD3,0x99); BAD=RGBColor(0xF8,0x71,0x71)
PUR=RGBColor(0xA7,0x8B,0xFA); WHY=RGBColor(0x1C,0x15,0x30); HLG=RGBColor(0x13,0x30,0x1F); HLP=RGBColor(0x21,0x1A,0x35)

EMU_W,EMU_H=Inches(13.333),Inches(7.5)
prs=Presentation(); prs.slide_width,prs.slide_height=EMU_W,EMU_H
BLANK=prs.slide_layouts[6]; N=4


def slide():
    s=prs.slides.add_slide(BLANK); r=s.shapes.add_shape(1,0,0,EMU_W,EMU_H)
    r.fill.solid(); r.fill.fore_color.rgb=BG; r.line.fill.background(); r.shadow.inherit=False
    s.shapes._spTree.remove(r._element); s.shapes._spTree.insert(2,r._element); return s


def box(s,x,y,w,h,fill=None,line=None,rad=True,lw=1):
    shp=s.shapes.add_shape(5 if rad else 1,Inches(x),Inches(y),Inches(w),Inches(h))
    if fill is None: shp.fill.background()
    else: shp.fill.solid(); shp.fill.fore_color.rgb=fill
    if line is None: shp.line.fill.background()
    else: shp.line.color.rgb=line; shp.line.width=Pt(lw)
    shp.shadow.inherit=False; return shp


def text(s,x,y,w,h,runs,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,sp=4):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=tb.text_frame; tf.word_wrap=True; tf.vertical_anchor=anchor
    if runs and isinstance(runs[0],tuple): runs=[runs]
    for pi,para in enumerate(runs):
        p=tf.paragraphs[0] if pi==0 else tf.add_paragraph(); p.alignment=align; p.space_after=Pt(sp); p.space_before=Pt(0)
        for (t,sz,col,b) in para:
            run=p.add_run(); run.text=t; run.font.size=Pt(sz); run.font.color.rgb=col; run.font.bold=b; run.font.name='Segoe UI'
    return tb


def kicker(s,t): text(s,0.62,0.42,12,0.5,[[(t.upper(),12,ACC,True)]])
def title(s,parts): text(s,0.62,0.92,12.1,1.2,[parts])


def bullets(s,x,y,w,h,items,sz=12,col=MUT,gap=4):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); tf=tb.text_frame; tf.word_wrap=True
    for k,it in enumerate(items):
        p=tf.paragraphs[0] if k==0 else tf.add_paragraph(); p.space_after=Pt(gap); p.space_before=Pt(0)
        if isinstance(it,list):
            for (t,c,b) in it:
                r=p.add_run(); r.text=t; r.font.size=Pt(sz); r.font.color.rgb=c; r.font.bold=b; r.font.name='Segoe UI'
        else:
            r=p.add_run(); r.text='•  '+it; r.font.size=Pt(sz); r.font.color.rgb=col; r.font.name='Segoe UI'


def card(s,x,y,w,h,head,hcol,items,sz=12,bcol=LINE,lw=1):
    box(s,x,y,w,h,fill=CARD,line=bcol,lw=lw)
    text(s,x+0.22,y+0.14,w-0.44,0.5,[[(head,14,hcol,True)]])
    bullets(s,x+0.22,y+0.7,w-0.44,h-0.85,items,sz=sz,gap=4)


def why(s,x,y,w,h,parts):
    box(s,x,y,w,h,fill=WHY,line=ACC2); text(s,x+0.22,y+0.1,w-0.44,h-0.2,parts,anchor=MSO_ANCHOR.MIDDLE)


def footer(s,n):
    text(s,0.62,7.05,8,0.4,[[('GoVoice · HCMUTE · Future Work — Tăng tốc STT',9,MUT,False)]])
    text(s,11.6,7.05,1.1,0.4,[[(f'{n} / {N}',9,MUT,False)]],align=PP_ALIGN.RIGHT)


def cell(s,x,y,w,h,t,col=INK,bold=False,bg=CARD,sz=10.5):
    box(s,x,y,w,h,fill=bg,line=LINE)
    text(s,x+0.1,y+0.05,w-0.18,h-0.1,[[(t,sz,col,bold)]],anchor=MSO_ANCHOR.MIDDLE)


# ===== 1 OVERVIEW + VERDICT =====
s=slide(); kicker(s,'Định hướng phát triển · Tăng tốc STT')
title(s,[('Hai con đường gỡ nút thắt STT (1.8s)',24,INK,True)])
X0,W0,W1=0.62,2.7,4.75; y=1.95; H=0.62
# header
cell(s,X0,y,W0,0.5,'Tiêu chí',ACC,True,bg=RGBColor(0x0E,0x1B,0x38),sz=11)
cell(s,X0+W0,y,W1,0.5,'① Streaming RNN-T / FastConformer',ACC,True,bg=RGBColor(0x0E,0x1B,0x38),sz=11)
cell(s,X0+W0+W1,y,W1,0.5,'② Audio-LLM (nghe thẳng)',ACC,True,bg=RGBColor(0x0E,0x1B,0x38),sz=11)
y+=0.5
rows=[('Nguyên lý','Vẫn STT→chữ, nhưng phiên âm NGAY lúc nói',INK,'BỎ STT — model nghe thẳng âm thanh',INK),
      ('Độ trễ cảm nhận','~0.3–0.5 s',GOOD,'~0.2–0.5 s',GOOD),
      ('Nặng / Jetson','Nhẹ (0.1–0.6B) — chạy tốt on-board',GOOD,'Nặng (~7B) — khó nhét Jetson 8GB',BAD),
      ('Giữ kiến trúc (3 tầng+GBNF+safety)','✅ Giữ nguyên — chỉ thay engine STT',GOOD,'❌ Thay gần hết — mất GBNF/an toàn',BAD),
      ('Tiếng Việt','Train data Việt (tiền lệ 🇹🇭 Thái)',INK,'Chưa có bản nhỏ tiếng Việt cho edge',INK),
      ('Rủi ro','Thấp–vừa',GOOD,'Cao',BAD)]
for c0,c1,col1,c2,col2 in rows:
    cell(s,X0,y,W0,H,c0,INK,False,sz=10.5)
    cell(s,X0+W0,y,W1,H,c1,col1,False,sz=10.5)
    cell(s,X0+W0+W1,y,W1,H,c2,col2,False,sz=10.5)
    y+=H
why(s,0.62,y+0.08,12.2,1.0,[[('Kết luận:  ',12.5,ACC2,True),('CHỌN ① cho dự án bây giờ — gỡ đúng nút thắt mà vẫn giữ trọn đóng góp neuro-symbolic + chạy on-board.',12.5,INK,False)],
                            [('② là tầm nhìn xa để đón đầu, nhưng nặng & mất kiểm soát an toàn.',12.5,INK,False)]])
footer(s,1)

# ===== 2 PATH 1 =====
s=slide(); kicker(s,'① Con đường khuyến nghị')
title(s,[('Streaming ',23,INK,True),('RNN-T / FastConformer',23,ACC,True),(' cho tiếng Việt',23,INK,True)])
text(s,0.62,1.9,7.4,0.4,[[('Ý tưởng',14,ACC,True)]])
bullets(s,0.62,2.35,7.4,1.7,[
    [('Thay Whisper (xử lý cả cửa sổ 30s) bằng Transducer streaming: ',MUT,False),('sinh chữ ngay từng đoạn 0.1–0.3s trong lúc nói.',INK,True)],
    'Khi nói xong là gần như phiên âm xong → STT 1.8s xuống ~0.3s cảm nhận.',
    'GIỮ NGUYÊN lõi: chữ ra → 3 tầng Reflex/Combo/LLM → GBNF → safety.'],sz=11.5,gap=5)
text(s,0.62,4.15,7.4,0.4,[[('Cách triển khai',14,ACC,True)]])
bullets(s,0.62,4.6,7.4,1.5,[
    'NVIDIA NeMo FastConformer-Transducer (cache-aware) hoặc RNN-T.',
    'Fine-tune trên data tiếng Việt: VIVOS, Common Voice VI, VLSP, hoặc tự thu lệnh robot.',
    'Xuất chạy GPU Jetson (TensorRT / NeMo).'],sz=11.5,gap=5)
card(s,8.32,1.9,4.5,3.5,'🇹🇭 Tiền lệ vàng',GOOD,
     ['Typhoon ASR Real-time (2026): Thái Lan tự train FastConformer-Transducer streaming cho tiếng Thái thay Whisper.',
      'Tiếng Việt làm tương tự được. Đây là cách industry chuẩn (Google/Apple/NVIDIA on-device).',
      'Kỳ vọng: STT ~0.3s · 0.1–0.6B · on-board.'],11.5,bcol=GOOD,lw=1.5)
why(s,0.62,6.05,12.2,0.95,[[('Vì sao hợp GoVoice nhất: ',12,ACC2,True),('rủi ro thấp (chỉ thay "lỗ tai"), đóng góp khoa học rõ (streaming command-ASR tiếng Việt cho robot), giữ trọn an toàn + grammar JSON.',12,INK,False)]])
footer(s,2)

# ===== 3 PATH 2 =====
s=slide(); kicker(s,'② Tầm nhìn xa')
title(s,[('Audio-LLM: model ',23,INK,True),('nghe thẳng',23,PUR,True),(', bỏ STT',23,INK,True)])
card(s,0.62,1.95,6.0,2.5,'Là gì?',PUR,
     ['Âm thanh → token âm thanh → vào thẳng LLM (không phiên âm). Model "hiểu" âm như hiểu chữ.',
      'VD: GPT-4o, Gemini, Qwen2.5-Omni (mã nguồn mở, cùng họ Qwen), Moshi (full-duplex ~200ms).'],12,bcol=PUR)
card(s,6.82,1.95,6.0,2.5,'Lợi thế',PUR,
     ['Bỏ hẳn vòng STT → độ trễ thấp nhất.','Vừa nghe vừa đáp, ngắt lời được.','Hiểu cả ngữ điệu/cảm xúc, không bị ép thành chữ trơ.'],12,bcol=PUR)
why(s,0.62,4.65,12.2,1.4,[
    [('Vì sao CHƯA dùng ngay cho robot: ',12.5,ACC2,True),('model ~7B rất nặng (khó chạy Jetson 8GB/CUDA 11.4);',12.5,INK,False)],
    [('khó ép JSON bằng GBNF + khó gắn lớp an toàn; chưa có bản nhỏ tiếng Việt cho edge. → để dành khi phần cứng mạnh hơn.',12.5,INK,False)]])
text(s,0.62,6.2,12,0.5,[[('Qwen2.5-Omni (Thinker-Talker)   ·   Moshi (Mimi codec)   ·   GPT-4o Realtime',12,ACC,True)]])
footer(s,3)

# ===== 4 ROADMAP =====
s=slide(); kicker(s,'Lộ trình đề xuất')
title(s,[('3 giai đoạn — từ "ăn liền" tới "đón đầu"',23,INK,True)])
def stage(x,w,ph,h,hcol,items,res,rescol,bcol):
    box(s,x,2.0,w,3.5,fill=CARD,line=bcol,lw=1.5)
    text(s,x+0.2,2.15,w-0.4,0.4,[[(ph,10.5,MUT,True)]])
    text(s,x+0.2,2.6,w-0.4,0.5,[[(h,13.5,hcol,True)]])
    bullets(s,x+0.2,3.25,w-0.4,1.6,items,sz=11,gap=4)
    text(s,x+0.2,4.95,w-0.4,0.5,[[(res,11.5,rescol,True)]])
stage(0.62,3.95,'NGẮN HẠN · vài tuần','Tối ưu Whisper hiện có',ACC,
      ['Giảm padding 30s → ~5–8s.','Streaming chunk (whisper_streaming).','int8 / chưng cất PhoWhisper.'],
      '→ STT 1.8s ⟶ ~0.5–0.8s',GOOD,ACC)
stage(4.72,3.95,'TRUNG HẠN · cốt lõi đồ án','① RNN-T / FastConformer',GOOD,
      ['Train Transducer streaming trên data Việt.','Giữ nguyên 3 tầng + GBNF + safety.','Tiền lệ: Typhoon ASR (Thái).'],
      '→ STT cảm nhận ~0.3s · on-board',GOOD,GOOD)
stage(8.82,3.95,'DÀI HẠN · đón đầu','② Audio-LLM',PUR,
      ['Thử Qwen2.5-Omni khi HW mạnh hơn.','Gộp nghe + hiểu vào 1 model.','Cần giải an toàn + on-board.'],
      '→ kiến trúc thế hệ mới',PUR,PUR)
why(s,0.62,5.75,12.2,0.85,[[('Thông điệp: ',12,ACC2,True),('bám mục tiêu realtime + on-board + an toàn → ưu tiên ①; ② là hướng nghiên cứu tiếp khi điều kiện cho phép.',12,INK,False)]])
footer(s,4)

prs.save('GoVoice_FutureWork.pptx')
print('SAVED GoVoice_FutureWork.pptx ·',len(prs.slides._sldIdLst),'slides')
