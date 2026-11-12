# -*- coding: utf-8 -*-
"""生成 32 面试排样 docx（大 32 开 / 105×152 版心 / 5 号字 / 15.4pt 行距），再转 PDF"""
import os, re, glob
from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_BREAK
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_LINE_SPACING

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, '05-实体书', '试排样')
os.makedirs(OUT, exist_ok=True)
FONT = 'Noto Serif CJK SC'

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Mm(140), Mm(203)
sec.left_margin, sec.right_margin = Mm(21), Mm(15)   # 订口 / 切口
sec.top_margin, sec.bottom_margin = Mm(25), Mm(26)   # 天头 / 地脚
sec.header_distance, sec.footer_distance = Mm(12), Mm(12)

# 默认样式
st = doc.styles['Normal']
st.font.name = FONT
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
pf = st.paragraph_format
pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
pf.line_spacing = Pt(15.4)
pf.space_before = Pt(0)
pf.space_after = Pt(0)

# 奇偶页眉
settings = doc.settings.element
e = OxmlElement('w:evenAndOddHeaders'); settings.append(e)

def set_font(run, size=10.5, bold=False, color=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

def para(text='', size=10.5, bold=False, align=None, indent=True, space_before=0, space_after=0):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(size * 1.47)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    r = p.add_run(text)
    set_font(r, size, bold)
    return p

def add_page_field(p):
    run = p.add_run()
    set_font(run, 9)
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = 'PAGE'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'end')
    run._r.append(f1); run._r.append(it); run._r.append(f2)

# 页眉页脚（奇数页=右页：章名/页码右；偶数页=左页：书名/页码左）
h = sec.header
hp = h.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r = hp.add_run('法则权能'); set_font(r, 8.5)
eh = sec.even_page_header
ehp = eh.paragraphs[0]; ehp.alignment = WD_ALIGN_PARAGRAPH.LEFT
r = ehp.add_run('卷一 · 标尺失准之年'); set_font(r, 8.5)

f = sec.footer
fp = f.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
add_page_field(fp)
ef = sec.even_page_footer
efp = ef.paragraphs[0]; efp.alignment = WD_ALIGN_PARAGRAPH.LEFT
add_page_field(efp)

# ---------- 封面 ----------
for _ in range(4):
    para('', indent=False)
para('法 则 权 能', 28, True, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=18)
para('一部关于"真而不可证"的城史', 11, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=60)
para('上 册', 12, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False)
doc.add_page_break()

# ---------- 书名页 ----------
for _ in range(5):
    para('', indent=False)
para('法 则 权 能', 20, True, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=24)
para('柯无衍 著', 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=80)
para('点子库工作室', 9, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False)
doc.add_page_break()

# ---------- 版权页 ----------
para('', indent=False)
for line in ['法 则 权 能（全二册）', '', '著　　者　柯无衍', '校　　订　衡城年刊编辑部',
             '版式设计　点子库工作室', '', '开　　本　140 mm × 203 mm　1/32',
             '印　　张　9.5（上册）', '字　　数　395 千字', '版　　次　2026 年 11 月第 1 版',
             '印　　次　2026 年 11 月第 1 次印刷', '书　　号　ISBN 978-7-XXXX-XXXX-X',
             '定　　价　（待定）', '', '版权所有 · 侵权必究']:
    para(line, 8.5, False, WD_ALIGN_PARAGRAPH.LEFT, indent=False, space_after=3)
doc.add_page_break()

# ---------- 目录（2 面） ----------
para('总 目 录', 16, True, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_after=24)
toc = [('序章 · 膜', '1'), ('第一章 · 第十三条', '3'), ('第二章 · 回望', '9'),
       ('第三章 · 渡口', '15'), ('第四章 · 三封邀请', '21'), ('第五章 · 夜巡读数', '26'),
       ('第六章 · 人群', '31')]
for name, pg in toc:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = Pt(18)
    r = p.add_run(name); set_font(r, 10.5)
    r2 = p.add_run('　' * 2 + '…' * 6 + '　' + pg); set_font(r2, 10.5)
doc.add_page_break()

# ---------- 正文 ----------
def clean(t):
    t = re.sub(r'^#\s.*$', '', t, flags=re.M)
    t = re.sub(r'^##\s.*$', '', t, flags=re.M)
    t = re.sub(r'^>.*$', lambda m: m.group(0)[2:], t, flags=re.M)
    t = t.replace('**', '').replace('*', '')
    t = re.sub(r'\n{2,}', '\n\n', t)
    return t

src = open(os.path.join(BASE, '05-实体书', '正文', '卷一.md'), encoding='utf-8').read()
chaps = re.split(r'\n## ', src)
count = 0
for ch in chaps[1:7]:
    title, _, body = ch.partition('\n')
    title = title.strip()
    # 章名另面起
    if count:
        doc.add_page_break()
    for _ in range(3):
        para('', indent=False)
    para(title, 20, True, WD_ALIGN_PARAGRAPH.LEFT, indent=False, space_after=24)
    for block in clean(body).split('\n\n'):
        b = block.strip()
        if not b:
            continue
        # 板书/判词类短行：居中或缩进
        if b.startswith('【') or b.startswith('——'):
            para(b, 10.5, False, WD_ALIGN_PARAGRAPH.LEFT, indent=False)
        elif len(b) <= 12 and b.endswith('。'):
            para(b, 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False, space_before=6, space_after=6)
        else:
            para(b)
    count += 1

path = os.path.join(OUT, '法则权能-付印样-v2-32面.docx')
doc.save(path)
print('saved', path)
