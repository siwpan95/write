# -*- coding: utf-8 -*-
"""下册付印样：番外（含两篇补遗）+ 后记，32 面"""
import os, re
from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, '05-实体书', '试排样')
FONT = 'Noto Serif CJK SC'

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Mm(140), Mm(203)
sec.left_margin, sec.right_margin = Mm(21), Mm(15)
sec.top_margin, sec.bottom_margin = Mm(25), Mm(26)
sec.header_distance, sec.footer_distance = Mm(12), Mm(12)

st = doc.styles['Normal']
st.font.name = FONT; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
st.paragraph_format.line_spacing = Pt(15.4)
st.paragraph_format.space_before = Pt(0); st.paragraph_format.space_after = Pt(0)

settings = doc.settings.element
settings.append(OxmlElement('w:evenAndOddHeaders'))

def sf(run, size=10.5, bold=False):
    run.font.name = FONT; run.font.size = Pt(size); run.bold = bold
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

def para(text='', size=10.5, bold=False, align=None, indent=True, sb=0, sa=0):
    p = doc.add_paragraph()
    if align is not None: p.alignment = align
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(size * 1.47)
    p.paragraph_format.space_before = Pt(sb); p.paragraph_format.space_after = Pt(sa)
    if indent: p.paragraph_format.first_line_indent = Pt(size * 2)
    r = p.add_run(text); sf(r, size, bold)
    return p

def page_field(p):
    run = p.add_run(); sf(run, 9)
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = 'PAGE'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'end')
    run._r.append(f1); run._r.append(it); run._r.append(f2)

hp = sec.header.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
sf(hp.add_run('法则权能'), 8.5)
ehp = sec.even_page_header.paragraphs[0]; ehp.alignment = WD_ALIGN_PARAGRAPH.LEFT
sf(ehp.add_run('下册 · 结局期 · 番外'), 8.5)
fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT; page_field(fp)
efp = sec.even_page_footer.paragraphs[0]; efp.alignment = WD_ALIGN_PARAGRAPH.LEFT; page_field(efp)

def clean(t):
    t = re.sub(r'^#\s.*$', '', t, flags=re.M)
    t = re.sub(r'^##\s.*$', '', t, flags=re.M)
    t = re.sub(r'^-\s\[.\].*$', '', t, flags=re.M)
    t = re.sub(r'^>.*$', lambda m: m.group(0)[2:], t, flags=re.M)
    t = t.replace('**', '').replace('*', '')
    t = '\n'.join(l for l in t.split('\n') if l.strip() not in ('---', '***'))
    return re.sub(r'\n{2,}', '\n\n', t)

def add_chapter(title, body):
    for _ in range(3):
        para('', indent=False)
    para(title, 20, True, WD_ALIGN_PARAGRAPH.LEFT, indent=False, sa=24)
    for block in clean(body).split('\n\n'):
        b = block.strip()
        if not b: continue
        if len(b) <= 12 and (b.endswith('。') or b.endswith('！')):
            para(b, 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False, sb=6, sa=6)
        else:
            para(b)

# 扉页
for _ in range(5): para('', indent=False)
para('下 册', 16, True, WD_ALIGN_PARAGRAPH.CENTER, indent=False)
para('结局期 · 番外 · 后记', 11, False, WD_ALIGN_PARAGRAPH.CENTER, indent=False)
doc.add_page_break()

# 番外篇目（含两篇补遗）
src = open(os.path.join(BASE, '05-实体书', '正文', '番外.md'), encoding='utf-8').read()
parts = re.split(r'^## (?=第[一二三四五六七八九十百]+章)', src, flags=re.M)[1:]
picked = parts[-6:]
for p in picked:
    title, _, body = p.partition('\n')
    add_chapter(title.strip(), body)

# 后记
doc.add_page_break()
for _ in range(3): para('', indent=False)
para('后 记 · 两套数', 20, True, WD_ALIGN_PARAGRAPH.LEFT, indent=False, sa=24)
post = open(os.path.join(BASE, '05-实体书', '05-后记-两套数.md'), encoding='utf-8').read()
for block in clean(post).split('\n\n'):
    b = block.strip()
    if not b: continue
    if b.startswith('#'): continue
    para(b)

path = os.path.join(OUT, '法则权能-下册-付印样-番外与后记.docx')
doc.save(path)
print('saved', path)
