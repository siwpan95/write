# -*- coding: utf-8 -*-
"""《钢铁之梦·卷一》同源排版：Word 为主文件，PDF 由主文件导出。"""
import sys, os, re, glob, shutil, subprocess
sys.path.insert(0, "/data/skills/docx/scripts")

from docxlib import open_docx, save_docx, ensure_yuanbao_defaults, set_page_size, set_page_margins
from docx.shared import Pt, RGBColor, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = "/data/workspace/steel_dream/vol3"
OUT_DOCX = "/data/workspace/钢铁之梦·卷三_钢铁之梦.docx"
OUT_PDF  = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"

SERIF = "Source Han Serif SC"
SANS  = "Noto Sans CJK SC"
DARK  = "1C1A17"      # 带褐深炭
PAPER = "F4EFE6"      # 暖灰纸色
INK   = "2A2622"      # 旧墨
FADE  = "7A6E5D"      # 题记/分隔
GRAY  = "5A544C"      # 旁白
ARCH  = "E8E0D0"      # 档案层底
LINE  = "9A8B72"

# 清理创作过程中混入的非中文残留（保持成稿语汇统一）
CLEAN = {
    "和 nights 里轮到自己值的一班岗": "和夜里轮到自己值的一班岗",
    "人老了以后， weather 记得比人牢": "人老了以后，天气记得比人牢",
    " because 那两笔画是我第一次觉得": "因为那两笔画是我第一次觉得",
    "bó 布罗迪偏要抄这段近路": "布罗迪偏要抄这段近路",
    "最干净的还是那天棚檐下的一滴water——不对，是那滴水。": "最干净的还是那天棚檐下的一滴水。",
    "是个我 many 年前记在粗纸背面的名字": "是个我许多年前记在粗纸背面的名字",
}

def clean(t):
    for a, b in CLEAN.items():
        t = t.replace(a, b)
    return t

# ---------- 解析 ----------
def parse():
    blocks, cur = [], None
    for path in sorted(glob.glob(os.path.join(BASE, "part*.txt"))):
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                if line.startswith("@@CH|"):
                    _, no, name, epi = line.split("|", 3)
                    cur = {"type": "chapter", "no": no, "name": name, "epi": epi, "paras": []}
                    blocks.append(cur)
                elif line.startswith("@@FRAME|"):
                    _, name, epi = line.split("|", 2)
                    cur = {"type": "frame", "no": "·", "name": name, "epi": epi, "paras": []}
                    blocks.append(cur)
                elif line.startswith("@@APPENDIX|"):
                    _, name = line.split("|", 1)
                    cur = {"type": "appendix", "name": name, "paras": []}
                    blocks.append(cur)
                elif line.startswith("@@KV|"):
                    _, k, v = line.split("|", 2)
                    cur["paras"].append(("KV", k, v))
                elif line.startswith("@@T|"):
                    cur["paras"].append(("T", clean(line[4:])))
                elif line.startswith("@@N|"):
                    cur["paras"].append(("N", clean(line[4:])))
                elif line.startswith("@@A|"):
                    cur["paras"].append(("A", clean(line[4:])))
                elif line.startswith("@@Q|"):
                    cur["paras"].append(("Q", clean(line[4:])))
                elif line.strip() == "@@S":
                    cur["paras"].append(("S", "◆"))
                else:
                    cur["paras"].append(("T", clean(line)))
    return blocks

# ---------- 底层 OOXML 工具 ----------
def _rfonts(rPr, family):
    rf = rPr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rPr.insert(0, rf)
    for a in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        rf.set(qn(a), family)

def font(run, family=SERIF, size=10.5, color=INK, bold=False, spacing=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    _rfonts(rPr, family)
    if spacing is not None:
        sp = OxmlElement('w:spacing'); sp.set(qn('w:val'), str(int(spacing * 20)))
        rPr.append(sp)
    return run

def p_indent(p, first=None, left=None, right=None):
    pf = p.paragraph_format
    if first is not None: pf.first_line_indent = Pt(first)
    if left is not None:  pf.left_indent = Pt(left)
    if right is not None: pf.right_indent = Pt(right)

def p_spacing(p, before=0, after=0, line=19, exact=True):
    pf = p.paragraph_format
    pf.space_before = Pt(before); pf.space_after = Pt(after)
    if exact:
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        pf.line_spacing = Pt(line)
    else:
        pf.line_spacing = line

_AFTER_SHD = {'tabs','suppressAutoHyphens','kinsoku','wordWrap','overflowPunct',
              'topLinePunct','autoSpaceDE','autoSpaceDN','bidi','adjustRightInd',
              'snapToGrid','spacing','ind','contextualSpacing','mirrorIndents',
              'suppressOverlap','jc','textDirection','textAlignment',
              'textboxTightWrap','outlineLvl','divId','cnfStyle','rPr','sectPr','pPrChange'}

def _insert_ppr(pPr, el, after_tags):
    idx = None
    for i, ch in enumerate(pPr):
        if ch.tag.split('}')[-1] in after_tags:
            idx = i; break
    if idx is None: pPr.append(el)
    else: pPr.insert(idx, el)

def shade(p_or_cell, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:fill'), fill)
    if hasattr(p_or_cell, '_tc'):
        tcPr = p_or_cell._tc.get_or_add_tcPr()
        tcPr.insert_element_before(shd, 'w:noWrap', 'w:tcMar', 'w:textDirection',
                                   'w:tcFitText', 'w:vAlign', 'w:hideMark',
                                   'w:headers', 'w:tcPrChange')
    else:
        _insert_ppr(p_or_cell._p.get_or_add_pPr(), shd, _AFTER_SHD)

def border(p, side='bottom', color=LINE, sz=6, space=6):
    pPr = p._p.get_or_add_pPr()
    pbdr = pPr.find(qn('w:pBdr'))
    if pbdr is None:
        pbdr = OxmlElement('w:pBdr')
        _insert_ppr(pPr, pbdr, _AFTER_SHD | {'shd', 'pBdr'})
    b = OxmlElement('w:' + side)
    b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), str(sz))
    b.set(qn('w:space'), str(space)); b.set(qn('w:color'), color)
    pbdr.append(b)

def cell_margins(cell, top=140, left=260, bottom=140, right=260):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement('w:tcMar')
    for k, v in (('top', top), ('left', left), ('bottom', bottom), ('right', right)):
        e = OxmlElement('w:' + k); e.set(qn('w:w'), str(v)); e.set(qn('w:type'), 'dxa')
        mar.append(e)
    tcPr.insert_element_before(mar, 'w:textDirection', 'w:tcFitText', 'w:vAlign',
                               'w:hideMark', 'w:headers', 'w:tcPrChange')

def no_table_borders(table):
    tblPr = table._tbl.tblPr
    bd = OxmlElement('w:tblBorders')
    for k in ('top','left','bottom','right','insideH','insideV'):
        e = OxmlElement('w:' + k); e.set(qn('w:val'), 'nil'); bd.append(e)
    tblW = tblPr.find(qn('w:tblW'))
    if tblW is None:
        tblW = OxmlElement('w:tblW')
        sty = tblPr.find(qn('w:tblStyle'))
        tblPr.insert(list(tblPr).index(sty) + 1 if sty is not None else 0, tblW)
    tblW.set(qn('w:type'), 'dxa'); tblW.set(qn('w:w'), '8506')
    tblPr.insert_element_before(bd, 'w:shd', 'w:tblLayout', 'w:tblCellMar',
                                'w:tblLook', 'w:tblCaption', 'w:tblDescription',
                                'w:tblPrChange')

def page_field(p, align):
    p.alignment = align
    fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE')
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr'); _rfonts(rPr, SERIF)
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), '19'); rPr.append(sz)
    r.append(rPr)
    t = OxmlElement('w:t'); t.text = '1'; r.append(t); fld.append(r)
    p._p.append(fld)

def clear_hf(hf):
    for p in hf.paragraphs:
        for r in list(p.runs):
            r._element.getparent().remove(r._element)
        p.text = ''

def setup_section(sec, vol_name, show_headers=True):
    sec.different_first_page_header_footer = True
    for hf in (sec.header, sec.even_page_header, sec.first_page_header,
               sec.footer, sec.even_page_footer, sec.first_page_footer):
        hf.is_linked_to_previous = False
        clear_hf(hf)
    if show_headers:
        p = sec.header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_spacing(p, 0, 0, 12)
        font(p.add_run(vol_name), SERIF, 8.5, FADE)
        border(p, 'bottom', LINE, 4, 4)
        p2 = sec.even_page_header.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_spacing(p2, 0, 0, 12)
        font(p2.add_run("钢铁之梦"), SERIF, 8.5, FADE)
        border(p2, 'bottom', LINE, 4, 4)
        page_field(sec.footer.paragraphs[0], WD_ALIGN_PARAGRAPH.RIGHT)
        page_field(sec.even_page_footer.paragraphs[0], WD_ALIGN_PARAGRAPH.LEFT)
    # 首页（章扉／卷扉）不排页眉页码

def add_break(doc):
    p = doc.add_paragraph()
    p_spacing(p, 0, 0, 12)
    r = p.add_run()
    br = OxmlElement('w:br'); br.set(qn('w:type'), 'page'); r._r.append(br)

# ---------- 页面构件 ----------
def dark_page(doc, kind, no, name, epi, vol_label):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    no_table_borders(t)
    row = t.rows[0]
    row.height = Cm(21.5); row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    c = t.cell(0, 0)
    c.width = Twips(8506)
    c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    shade(c, DARK)
    cell_margins(c, 200, 620, 200, 620)
    # 清空默认段
    c.paragraphs[0].text = ''
    def line(text, size, family, col, bold=False, before=0, after=0, sp=None, align=None):
        p = c.add_paragraph()
        p_spacing(p, before, after, 15 if size < 12 else 22)
        p_indent(p, 0, 0, 0)
        if align: p.alignment = align
        font(p.add_run(text), family, size, col, bold, sp)
        return p
    if kind == 'cover':
        line("◆", 11, SANS, FADE, after=16)
        p = line("钢铁之梦", 34, SANS, PAPER, True, after=6, sp=2.0)
        border(p, 'bottom', FADE, 6, 10)
        line("多诺万家族三部曲 · 第三部　终卷", 11, SANS, "C9BDA6", after=30, sp=1.0)
        line("终卷 · 钢铁之梦", 22, SANS, PAPER, True, after=18, sp=1.5)
        line("风把红得像锈的土卷起来，打在玻璃上，沙沙地响。", 10, SERIF, "B9AC95", after=0)
        line("一八八八 — 一九〇一　｜　一部西部黑色纪事（全帙完结）", 9, SERIF, "9C907A", before=28)
    elif kind == 'volume':
        line("卷　三", 12, SANS, "C9BDA6", after=18, sp=2.0)
        line(name, 30, SANS, PAPER, True, after=14, sp=1.5)
        border(c.paragraphs[-1], 'bottom', FADE, 6, 12)
        line(epi, 10, SERIF, "B9AC95", before=8)
        line("核心物件 · 发票", 9, SERIF, "9C907A", before=30)
    else:  # chapter
        line("◆　" + ("序章" if no in ("序", "·") else "第 " + no + " 章"),
             10, SANS, "C9BDA6", after=20, sp=1.0)
        p = line(name, 23, SANS, PAPER, True, after=16, sp=1.2)
        border(p, 'bottom', FADE, 4, 10)
        line(epi, 10, SERIF, "B9AC95", before=10)
        line(vol_label + "　｜　" + "黑色电影 × 复古西部", 8.5, SERIF, "867B66", before=34)
    # 表格后不留空段干扰分页

def light_title(doc, text, sub=None):
    p = doc.add_paragraph()
    p_spacing(p, 0, 10, 22)
    p_indent(p, 0, 0, 0)
    font(p.add_run(text), SANS, 15, INK, True, 1.0)
    border(p, 'bottom', LINE, 6, 8)
    if sub:
        q = doc.add_paragraph()
        p_spacing(q, 8, 14, 16)
        p_indent(q, 0, 0, 0)
        font(q.add_run(sub), SERIF, 9.5, FADE)

def body_para(doc, kind, text):
    p = doc.add_paragraph()
    if kind == 'T':
        p_spacing(p, 0, 0, 19)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_indent(p, 21, 0, 0)
        font(p.add_run(text), SERIF, 10.5, INK)
    elif kind == 'N':
        p_spacing(p, 4, 6, 18)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_indent(p, 0, 21, 21)
        font(p.add_run(text), SERIF, 10, GRAY)
    elif kind == 'A':
        p_spacing(p, 8, 10, 17)
        p_indent(p, 0, 24, 12)
        shade(p, ARCH)
        border(p, 'left', "8A7A5E", 12, 8)
        font(p.add_run(text), SERIF, 9.5, "4A4237")
    elif kind == 'Q':
        p_spacing(p, 12, 14, 17)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_indent(p, 0, 0, 0)
        font(p.add_run(text), SERIF, 10, FADE)
    elif kind == 'S':
        p_spacing(p, 6, 12, 16)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_indent(p, 0, 0, 0)
        font(p.add_run(text), SANS, 9, FADE)
    return p

def kv_table(doc, rows):
    t = doc.add_table(rows=0, cols=2)
    no_table_borders(t)
    t.columns[0].width = Twips(2300); t.columns[1].width = Twips(6206)
    for k, v in rows:
        cells = t.add_row().cells
        cells[0].width = Twips(2300); cells[1].width = Twips(6206)
        for cell in cells:
            cell_margins(cell, 90, 100, 90, 100)
        p0 = cells[0].paragraphs[0]
        p_spacing(p0, 2, 2, 16); p_indent(p0, 0, 0, 0)
        font(p0.add_run(k), SANS, 9.5, INK, True)
        p1 = cells[1].paragraphs[0]
        p_spacing(p1, 2, 2, 16); p_indent(p1, 0, 0, 0)
        font(p1.add_run(v), SERIF, 9.5, "3A352F")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

# ---------- 主构建 ----------
def main():
    blocks = parse()
    doc = open_docx()
    ensure_yuanbao_defaults(doc)
    doc.settings.odd_and_even_pages_header_footer = True
    sec0 = doc.sections[0]
    set_page_size(sec0, 11906, 16838)
    set_page_margins(sec0, top=1700, bottom=1900, left=1700, right=1700)
    # 页面暖灰纸色（Word 内可见；PDF 另作底层铺色）
    st = doc.styles['Normal']
    st.font.size = Pt(10.5)
    _rfonts(st.element.get_or_add_rPr(), SERIF)
    st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    st.paragraph_format.line_spacing = Pt(19)
    st.paragraph_format.space_before = Pt(0)
    st.paragraph_format.space_after = Pt(0)
    setup_section(sec0, "卷三 · 钢铁之梦", show_headers=False)

    # 封面
    dark_page(doc, 'cover', '', '', '', '')
    # 扉二
    add_break(doc)
    p = doc.add_paragraph(); p_spacing(p, 0, 18, 20); p_indent(p, 0, 0, 0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(p.add_run("没有人比我更懂西部淘金梦。"), SERIF, 13, INK)
    q = doc.add_paragraph(); p_spacing(q, 0, 24, 17); p_indent(q, 0, 0, 0)
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(q.add_run("—— 伊蒙·多诺万，许多年后，专属列车包厢"), SERIF, 9.5, FADE)
    r = doc.add_paragraph(); p_spacing(r, 0, 0, 19); p_indent(r, 21, 0, 0)
    font(r.add_run("本卷为《钢铁之梦》三部曲终卷，接卷一《血比马粪贱》、卷二《铁丝与雪》：路权与拨地、费率表上的对手、自己的公司给自己开发票，终至列车包厢里那句「没有人比我更懂西部淘金梦」。全帙完结。"), SERIF, 10.5, INK)
    # 目次
    add_break(doc)
    light_title(doc, "目　次", "钢铁之梦 · 卷三　钢铁之梦（终卷）")
    for b in blocks:
        if b['type'] in ('chapter', 'frame'):
            label = ("序章" if b['no'] in ('序', '·') else "第 " + b['no'] + " 章") if b['type'] == 'chapter' else "框架"
            p = doc.add_paragraph(); p_spacing(p, 2, 2, 18); p_indent(p, 0, 0, 0)
            font(p.add_run(label + "　　" + b['name']), SERIF, 10.5, INK)
        else:
            p = doc.add_paragraph(); p_spacing(p, 2, 2, 18); p_indent(p, 0, 0, 0)
            font(p.add_run("　　　" + b['name']), SERIF, 10, FADE)

    # 卷扉（独立右页）
    s = doc.add_section(WD_SECTION_START.NEW_PAGE)
    setup_section(s, "卷三 · 钢铁之梦")
    dark_page(doc, 'volume', '', "钢铁之梦",
              "产权怎么变成国家。反派不签字，流程签字。", "")

    # 正文
    for b in blocks:
        s = doc.add_section(WD_SECTION_START.NEW_PAGE)
        setup_section(s, "卷三 · 钢铁之梦")
        if b['type'] == 'chapter':
            dark_page(doc, 'chapter', b['no'], b['name'], b['epi'], "卷三 · 钢铁之梦")
        elif b['type'] == 'frame':
            light_title(doc, b['name'], b['epi'])
        else:
            light_title(doc, b['name'])
        kv_buf = []
        need_break = (b['type'] == 'chapter')
        for item in b['paras']:
            if item[0] == 'KV':
                kv_buf.append((item[1], item[2])); continue
            if kv_buf:
                kv_table(doc, kv_buf); kv_buf = []
            if b['type'] == 'frame' and item[0] in ('T', 'N', 'A', 'Q'):
                p = body_para(doc, item[0], item[1])
                if item[0] in ('T', 'N', 'A'):
                    p.paragraph_format.left_indent = Pt(42)
                    p.paragraph_format.right_indent = Pt(42)
                    p.paragraph_format.first_line_indent = Pt(21) if item[0] == 'T' else Pt(0)
            else:
                p = body_para(doc, item[0], item[1])
            if need_break and item[0] in ('T', 'N', 'A'):
                p.paragraph_format.page_break_before = True
                need_break = False
        if kv_buf:
            kv_table(doc, kv_buf)

    save_docx(doc, OUT_DOCX)
    print("DOCX:", OUT_DOCX, os.path.getsize(OUT_DOCX))

    # PDF 同源导出
    subprocess.run(["python3", "/data/skills/docx/scripts/office/soffice.py",
                    "--headless", "--convert-to", "pdf", "--outdir", "/data/workspace", OUT_DOCX],
                   check=True, timeout=420)
    produced = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"
    if os.path.exists(produced) and produced != OUT_PDF:
        shutil.move(produced, OUT_PDF)
    print("PDF:", OUT_PDF, os.path.getsize(OUT_PDF) if os.path.exists(OUT_PDF) else "MISSING")

if __name__ == "__main__":
    main()
