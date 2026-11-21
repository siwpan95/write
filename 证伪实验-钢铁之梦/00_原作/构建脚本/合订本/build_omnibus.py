# -*- coding: utf-8 -*-
"""《钢铁之梦》全帙合订本：正编三卷（未改一字）＋番外一辑。
复用卷一 build.py 的全部版式 helper，仅替换封面文案、卷扉参数与章节解析。
输出 Word 主文件，并由主文件同源导出 PDF。
"""
import sys, os, glob, shutil, subprocess
sys.path.insert(0, "/data/workspace/steel_dream")
sys.path.insert(0, "/data/skills/docx/scripts")

import build as B
from docxlib import open_docx, save_docx, ensure_yuanbao_defaults, set_page_size, set_page_margins
from docx.shared import Pt, Cm, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START

OUT_DOCX = "/data/workspace/钢铁之梦_全帙合订本.docx"
OUT_PDF  = "/data/workspace/钢铁之梦_全帙合订本.pdf"

ROOT = "/data/workspace/steel_dream"
VOLS = [
    dict(key="v1", label="卷一 · 血比马粪贱", num="卷　一", name="血比马粪贱",
         epi="人命比马粪还贱，规矩全靠左轮手枪来定。", obj="核心物件 · 牌",
         ji="第一辑　血比马粪贱", files=sorted(glob.glob(ROOT + "/part*.txt"))),
    dict(key="v2", label="卷二 · 铁丝与雪", num="卷　二", name="铁丝与雪",
         epi="自由放牧的时代结束了。谁圈住水，谁替整片草定规矩。", obj="核心物件 · 铁丝",
         ji="第二辑　铁丝与雪", files=sorted(glob.glob(ROOT + "/vol2/part*.txt"))),
    dict(key="v3", label="卷三 · 钢铁之梦", num="卷　三", name="钢铁之梦",
         epi="产权怎么变成国家。反派不签字，流程签字。", obj="核心物件 · 发票",
         ji="第三辑　钢铁之梦", files=sorted(glob.glob(ROOT + "/vol3/part*.txt"))),
    dict(key="ex", label="番外 · 未领的纸", num="番　外", name="未领的纸",
         epi="正编三卷未增一字。这五页不进账。", obj="核心物件 · 余",
         ji="第四辑　未领的纸（番外五篇）", files=sorted(glob.glob(ROOT + "/vol3/extra*.txt"))),
]

# ---------- 解析（在卷一 parse 基础上增加 @@EX 番外章） ----------
def parse_files(paths):
    blocks, cur = [], None
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                if line.startswith("@@CH|"):
                    _, no, name, epi = line.split("|", 3)
                    cur = {"type": "chapter", "no": no, "name": name, "epi": epi, "paras": []}
                    blocks.append(cur)
                elif line.startswith("@@EX|"):
                    _, no, name, epi = line.split("|", 3)
                    cur = {"type": "extra", "no": no, "name": name, "epi": epi, "paras": []}
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
                    cur["paras"].append(("T", B.clean(line[4:])))
                elif line.startswith("@@N|"):
                    cur["paras"].append(("N", B.clean(line[4:])))
                elif line.startswith("@@A|"):
                    cur["paras"].append(("A", B.clean(line[4:])))
                elif line.startswith("@@Q|"):
                    cur["paras"].append(("Q", B.clean(line[4:])))
                elif line.strip() == "@@S":
                    cur["paras"].append(("S", "◆"))
                else:
                    cur["paras"].append(("T", B.clean(line)))
    return blocks

# ---------- 合订本专用深色页（封面／卷扉／章扉／番外扉） ----------
def dark_page(doc, kind, vol, block=None):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    B.no_table_borders(t)
    row = t.rows[0]
    row.height = Cm(21.5); row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    c = t.cell(0, 0)
    c.width = Twips(8506)
    c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    B.shade(c, B.DARK)
    B.cell_margins(c, 200, 620, 200, 620)
    c.paragraphs[0].text = ''

    def line(text, size, family, col, bold=False, before=0, after=0, sp=None, align=None):
        p = c.add_paragraph()
        B.p_spacing(p, before, after, 15 if size < 12 else 22)
        B.p_indent(p, 0, 0, 0)
        if align: p.alignment = align
        B.font(p.add_run(text), family, size, col, bold, sp)
        return p

    if kind == 'cover':
        line("◆", 11, B.SANS, B.FADE, after=16)
        p = line("钢铁之梦", 34, B.SANS, B.PAPER, True, after=6, sp=2.0)
        B.border(p, 'bottom', B.FADE, 6, 10)
        line("全帙合订本 · 三卷 ＋ 番外一辑", 11, B.SANS, "C9BDA6", after=26, sp=1.0)
        line("血比马粪贱　／　铁丝与雪　／　钢铁之梦", 12, B.SANS, B.PAPER, True, after=8, sp=1.0)
        line("未领的纸", 18, B.SANS, B.PAPER, True, after=20, sp=1.5)
        line("没有人比我更懂西部淘金梦。", 10, B.SERIF, "B9AC95", after=0)
        line("一八七六 — 一九〇一　｜　新黑色电影 × 纯正西部", 9, B.SERIF, "9C907A", before=26)
        line("正编三十六章 · 框架六篇 · 番外五篇　｜　全帙完结", 8.5, B.SERIF, "867B66", before=6)
    elif kind == 'volume':
        line(vol['num'], 12, B.SANS, "C9BDA6", after=18, sp=2.0)
        p = line(vol['name'], 30, B.SANS, B.PAPER, True, after=14, sp=1.5)
        B.border(p, 'bottom', B.FADE, 6, 12)
        line(vol['epi'], 10, B.SERIF, "B9AC95", before=8)
        line(vol['obj'], 9, B.SERIF, "9C907A", before=30)
        # 卷扉自带辑标签：保证卷首框架章的页眉归属正确
        line(vol['label'], 8, B.SANS, "867B66", before=16)
    else:
        no = block['no']
        if block['type'] == 'extra':
            head = "◆　番外 " + no
        elif block['type'] == 'frame' or no in ('序', '·'):
            head = "◆　序章"
        else:
            head = "◆　第 " + no + " 章"
        line(head, 10, B.SANS, "C9BDA6", after=20, sp=1.0)
        p = line(block['name'], 23, B.SANS, B.PAPER, True, after=16, sp=1.2)
        B.border(p, 'bottom', B.FADE, 4, 10)
        line(block['epi'], 10, B.SERIF, "B9AC95", before=10)
        line(vol['label'] + "　｜　" + "黑色电影 × 复古西部", 8.5, B.SERIF, "867B66", before=34)

# ---------- 主构建 ----------
def main():
    for v in VOLS:
        if not v['files']:
            raise SystemExit("缺源文本: " + v['key'])
        v['blocks'] = parse_files(v['files'])
    total = sum(len(v['blocks']) for v in VOLS)
    print("源文本分片:", {v['key']: len(v['files']) for v in VOLS}, "| 块数:", total)

    doc = open_docx()
    ensure_yuanbao_defaults(doc)
    doc.settings.odd_and_even_pages_header_footer = True
    sec0 = doc.sections[0]
    set_page_size(sec0, 11906, 16838)
    set_page_margins(sec0, top=1700, bottom=1900, left=1700, right=1700)
    st = doc.styles['Normal']
    st.font.size = Pt(10.5)
    B._rfonts(st.element.get_or_add_rPr(), B.SERIF)
    st.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    st.paragraph_format.line_spacing = Pt(19)
    st.paragraph_format.space_before = Pt(0)
    st.paragraph_format.space_after = Pt(0)
    B.setup_section(sec0, "钢铁之梦 · 全帙", show_headers=False)

    # 总封面
    dark_page(doc, 'cover', None)

    # 扉二：题记 + 合订本说明
    B.add_break(doc)
    p = doc.add_paragraph(); B.p_spacing(p, 0, 18, 20); B.p_indent(p, 0, 0, 0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    B.font(p.add_run("没有人比我更懂西部淘金梦。"), B.SERIF, 13, B.INK)
    q = doc.add_paragraph(); B.p_spacing(q, 0, 24, 17); B.p_indent(q, 0, 0, 0)
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    B.font(q.add_run("—— 伊蒙·多诺万，许多年后，专属列车包厢"), B.SERIF, 9.5, B.FADE)
    r = doc.add_paragraph(); B.p_spacing(r, 0, 0, 19); B.p_indent(r, 21, 0, 0)
    B.font(r.add_run(
        "本册收《钢铁之梦》正编三卷与番外一辑。全书以一八七六年美国西部为起点，循牛仔、牧场、矿山、铁路四段路，"
        "写一个被欠薪的人如何学会替别人记账，又如何把会冻死的东西换成不肯挪的东西。正编三卷此次合订未增一字、未改一章；"
        "番外五篇另立第四辑，各换一位叙述者，从旁补一页光，不插入正编、不接续章号、不改任何人物结局。"
        "凡正编已收束之物，番外只从旁看一眼，不重写一遍。"), B.SERIF, 10.5, B.INK)

    # 总目次
    B.add_break(doc)
    B.light_title(doc, "总　目　次", "钢铁之梦 · 全帙合订本　｜　四辑")
    for v in VOLS:
        p = doc.add_paragraph(); B.p_spacing(p, 14, 4, 20); B.p_indent(p, 0, 0, 0)
        B.font(p.add_run(v['ji']), B.SANS, 11.5, B.INK, True, 1.0)
        B.border(p, 'bottom', B.LINE, 4, 4)
        for b in v['blocks']:
            if b['type'] == 'chapter':
                label = "第 " + b['no'] + " 章"
            elif b['type'] == 'extra':
                label = "番外 " + b['no']
            elif b['type'] == 'frame':
                label = "框架"
            else:
                continue
            p = doc.add_paragraph(); B.p_spacing(p, 2, 2, 18); B.p_indent(p, 0, 14, 0)
            B.font(p.add_run(label + "　　" + b['name']), B.SERIF, 10.5, B.INK)
        n_app = sum(1 for b in v['blocks'] if b['type'] == 'appendix')
        if n_app:
            p = doc.add_paragraph(); B.p_spacing(p, 2, 6, 17); B.p_indent(p, 0, 14, 0)
            B.font(p.add_run("　　　本辑附录 " + str(n_app) + " 种，见辑末"), B.SERIF, 9.5, B.FADE)

    # 四辑正文
    for v in VOLS:
        s = doc.add_section(WD_SECTION_START.NEW_PAGE)
        B.setup_section(s, v['label'])
        dark_page(doc, 'volume', v)

        for b in v['blocks']:
            s = doc.add_section(WD_SECTION_START.NEW_PAGE)
            B.setup_section(s, v['label'])
            if b['type'] in ('chapter', 'extra'):
                dark_page(doc, 'chapter', v, b)
            elif b['type'] == 'frame':
                B.light_title(doc, b['name'], b['epi'])
            else:
                B.light_title(doc, b['name'])
            kv_buf = []
            need_break = b['type'] in ('chapter', 'extra')
            for item in b['paras']:
                if item[0] == 'KV':
                    kv_buf.append((item[1], item[2])); continue
                if kv_buf:
                    B.kv_table(doc, kv_buf); kv_buf = []
                if b['type'] == 'frame' and item[0] in ('T', 'N', 'A', 'Q'):
                    p = B.body_para(doc, item[0], item[1])
                    if item[0] in ('T', 'N', 'A'):
                        p.paragraph_format.left_indent = Pt(42)
                        p.paragraph_format.right_indent = Pt(42)
                        p.paragraph_format.first_line_indent = Pt(21) if item[0] == 'T' else Pt(0)
                else:
                    p = B.body_para(doc, item[0], item[1])
                if need_break and item[0] in ('T', 'N', 'A'):
                    p.paragraph_format.page_break_before = True
                    need_break = False
            if kv_buf:
                B.kv_table(doc, kv_buf)

    save_docx(doc, OUT_DOCX)
    print("DOCX:", OUT_DOCX, os.path.getsize(OUT_DOCX))

    subprocess.run(["python3", "/data/skills/docx/scripts/office/soffice.py",
                    "--headless", "--convert-to", "pdf", "--outdir", "/data/workspace", OUT_DOCX],
                   check=True, timeout=900)
    produced = "/data/workspace/钢铁之梦_全帙合订本.pdf"
    if os.path.exists(produced) and produced != OUT_PDF:
        shutil.move(produced, OUT_PDF)
    print("PDF:", OUT_PDF, os.path.getsize(OUT_PDF) if os.path.exists(OUT_PDF) else "MISSING")

if __name__ == "__main__":
    main()
