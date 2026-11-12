# -*- coding: utf-8 -*-
"""两本小册各排 32 面小样（大 32 开 / 105×152 版心 / 5 号字 / 15.4pt 行距）。

依 05-实体书/00-排版总则.md 与 试排样/00-试排样报告.md 的实测参数；
生成链：本脚本 → python-docx → F:\\Libre\\program\\soffice.com → PDF。
每册 4 面辅文（封面/书名页/版权页/目录）+ 28 面正文 = 32 面（1 印张）。
正文按 24 行/面预算装版（实测满页 28 行，留 4 行给短句成段与章题留白）；
全文不足 28 面时按总则 §七.5 补空白面，超过时截断为样张。
可重跑：python 04-工具/make_pdf_booklet_samples.py
"""
import os
import re
import math
from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(BASE, '05-实体书')
OUT = os.path.join(BOOK, '试排样')
os.makedirs(OUT, exist_ok=True)

FONT = 'SimSun'              # 本机无 Noto Serif CJK SC 字体族，会回退成可变字体 Heavy 实例（正文偏粗）；
                             # 故按 00-排版总则 §三「正文＝宋体（书宋）」统一用 Windows 自带 SimSun。
FONT_FALLBACK = 'Noto Serif CJK SC'   # 装有该字体族的环境可改 FONT 常量重跑，与既有 3 个样张严格一致。
LINES_PER_PAGE = 24          # 装版预算（实测满页 28 行）
CHARS_PER_LINE = 28          # 105mm 版心实测每行 28 字
BODY_PAGES = 28
FRONT_PAGES = 4

BOOKS = [
    dict(src='补遗六题.md', name='补遗六题', out='补遗六题-32面小样',
         subtitle='S-勘误支线 · 六篇合册（不含《第 1 版》）',
         toc=[('一 · 勘误页', '1'), ('二 · 刀', '6'), ('三 · 对质', '11'),
              ('四 · 洗手', '16'), ('五 · 崩口', '20'), ('六 · 鞋', '24')]),
    dict(src='小册-校书人四题.md', name='校书人四题', out='校书人四题-32面小样',
         subtitle='可独立发售 · 校书人、缺页的书、崩口的刀、没有结果的问话',
         toc=[('一 · 勘误页', '1'), ('二 · 第 1 版', '8'), ('三 · 刀', '15'), ('四 · 对质', '22')]),
]


def set_font(run, size=10.5, bold=False, font=None):
    fn = font or FONT
    run.font.name = fn
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn('w:eastAsia'), fn)


def para(doc, text='', size=10.5, bold=False, align=None, indent=True,
         space_before=0, space_after=0, page_break=False, font=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    if page_break:
        p.paragraph_format.page_break_before = True
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(15.4)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    r = p.add_run(text)
    set_font(r, size, bold, font)
    return p


def add_page_field(p):
    run = p.add_run()
    set_font(run, 9)
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = 'PAGE'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'end')
    run._r.append(f1); run._r.append(it); run._r.append(f2)


def extract_paragraphs(path):
    """从研究本小册提取可排版段落：剥离索引卡/清单/标记，保留正文文字。"""
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')
    out = []
    skipping = False
    for line in lines:
        s = line.strip()
        if s.startswith('## 本章索引卡'):
            skipping = True
            out.append('❖　❖　❖')
            continue
        if skipping:
            if s == '---':
                skipping = False
            continue
        if s.startswith('# ') or s.startswith('- [') or s.startswith('|'):
            continue
        if s == '---' or s == '':
            continue
        t = s
        if t.startswith('>'):
            t = t[1:].strip()
        t = t.replace('**', '').replace('*', '')
        t = re.sub(r'^#+\s*', '', t)
        if t:
            out.append(t)
    return out


def paginate(paras):
    """按 24 行/面装版；返回 (页面列表, 是否截断)。"""
    pages, cur, used = [], [], 0.0
    truncated = False
    for t in paras:
        lc = max(1, math.ceil(len(t) / CHARS_PER_LINE)) + 0.4
        if used + lc > LINES_PER_PAGE and cur:
            pages.append(cur)
            if len(pages) >= BODY_PAGES:
                truncated = True
                return pages[:BODY_PAGES], truncated
            cur, used = [], 0.0
        cur.append(t)
        used += lc
    if cur and len(pages) < BODY_PAGES:
        pages.append(cur)
    while len(pages) < BODY_PAGES:
        pages.append([])          # 空白面（总则 §七.5）
    return pages[:BODY_PAGES], truncated


def build(cfg):
    src = os.path.join(BOOK, cfg['src'])
    paras = extract_paragraphs(src)
    body_pages, truncated = paginate(paras)

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(140), Mm(203)
    sec.left_margin, sec.right_margin = Mm(21), Mm(15)
    sec.top_margin, sec.bottom_margin = Mm(25), Mm(26)
    sec.header_distance, sec.footer_distance = Mm(12), Mm(12)

    st = doc.styles['Normal']
    st.font.name = FONT
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    pf = st.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(15.4)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)

    settings = doc.settings.element
    e = OxmlElement('w:evenAndOddHeaders'); settings.append(e)

    hp = sec.header.paragraphs[0]; hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(hp.add_run(cfg['name']), 8.5)
    ehp = sec.even_page_header.paragraphs[0]; ehp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(ehp.add_run('法则权能 · 番外'), 8.5)
    fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_page_field(fp)
    efp = sec.even_page_footer.paragraphs[0]; efp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    add_page_field(efp)

    # ---- 辅文 4 面 ----
    # 面 1 封面
    for _ in range(4):
        para(doc, '', indent=False)
    para(doc, cfg['name'], 26, True, WD_ALIGN_PARAGRAPH.CENTER, False, space_after=18)
    para(doc, cfg['subtitle'], 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, False, space_after=54)
    para(doc, '32 面小样 · 大 32 开', 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, False)

    # 面 2 书名页
    for _ in range(5):
        para(doc, '', indent=False, page_break=(_ == 0))
    para(doc, cfg['name'], 20, True, WD_ALIGN_PARAGRAPH.CENTER, False, space_after=24)
    para(doc, '柯无衍 著', 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, False, space_after=72)
    para(doc, '点子库工作室', 9, False, WD_ALIGN_PARAGRAPH.CENTER, False)

    # 面 3 版权页
    first = True
    for line in [f'{cfg["name"]}（32 面小样）', '', '著　　者　柯无衍',
                 '编　　次　点子库工作室', '', '开　　本　140 mm × 203 mm　1/32',
                 '版　　心　105 × 152 mm　28 字 × 28 行',
                 '字　　体　' + FONT + '（缺字回退 ' + FONT_FALLBACK + '）',
                 '字号行距　10.5 pt / 15.4 pt',
                 '印　　张　1（32 面）', '版　　次　2026 年 11 月第 1 版',
                 '定　　价　（样张，非卖品）', '', '版权所有 · 侵权必究']:
        para(doc, line, 8.5, False, WD_ALIGN_PARAGRAPH.LEFT, False,
             space_after=3, page_break=first)
        first = False

    # 面 4 目录
    para(doc, '目　录', 16, True, WD_ALIGN_PARAGRAPH.CENTER, False,
         space_after=22, page_break=True)
    for name, pg in cfg['toc']:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = Pt(18)
        set_font(p.add_run(name), 10.5)
        set_font(p.add_run('　' * 2 + '…' * 6 + '　' + pg), 10.5)

    # ---- 正文 28 面 ----
    for idx, page in enumerate(body_pages):
        if not page:
            para(doc, '', indent=False, page_break=True)   # 空白面
            continue
        for j, t in enumerate(page):
            br = (j == 0)
            if t.startswith('❖'):
                para(doc, t, 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, False,
                     space_before=6, space_after=6, page_break=br)
            elif t.startswith('【') or t.startswith('——') or t.startswith('第 1 版'):
                para(doc, t, 10.5, False, WD_ALIGN_PARAGRAPH.LEFT, False, page_break=br)
            elif len(t) <= 12 and t.endswith('。'):
                para(doc, t, 10.5, False, WD_ALIGN_PARAGRAPH.CENTER, False,
                     space_before=6, space_after=6, page_break=br)
            else:
                para(doc, t, page_break=br)

    path = os.path.join(OUT, cfg['out'] + '.docx')
    doc.save(path)
    used = sum(1 for p in body_pages if p)
    print(f'{cfg["name"]}: 段落 {len(paras)} / 正文实排 {used} 面 / 空白面 {BODY_PAGES-used} 面'
          f' / {"截断为样张" if truncated else "全文收入"} -> {path}')
    return dict(cfg, paragraphs=len(paras), used=used,
                blank=BODY_PAGES - used, truncated=truncated)


def main():
    stats = [build(cfg) for cfg in BOOKS]
    print('\n合计: 每册 4 面辅文 + 28 面正文 = 32 面；生成 .docx 后用 soffice.com 转 PDF。')
    return stats


if __name__ == '__main__':
    main()
