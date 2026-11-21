# -*- coding: utf-8 -*-
"""合订本 PDF 精装后处理：满版深炭章扉、暖灰做旧纸色、页眉按辑切换、外侧页码。"""
import sys, os, glob, subprocess
sys.path.insert(0, "/data/skills/pdf/scripts")

from fonts import register_all_fonts
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
from PIL import Image
from io import BytesIO

SRC = "/data/workspace/钢铁之梦_全帙合订本.pdf"
TMP = "/data/workspace/.steel_dream_omnibus_post.pdf"
DARK_RGB = (0.1098, 0.1020, 0.0902)
PAPER_RGB = (0.9569, 0.9373, 0.9020)
BOOK = "钢铁之梦"
FALLBACK = "钢铁之梦 · 全帙"

# 与 build_omnibus.py 中 setup_section 的 vol_name 完全一致
LABELS = [
    ("卷一 · 血比马粪贱", "卷一 · 血比马粪贱"),
    ("卷二 · 铁丝与雪", "卷二 · 铁丝与雪"),
    ("卷三 · 钢铁之梦", "卷三 · 钢铁之梦"),
    ("番外 · 未领的纸", "番外 · 未领的纸"),
]

def header_font():
    fonts = register_all_fonts()
    path = os.popen('fc-match -f "%{file}" "Noto Serif CJK SC"').read().strip().split('\n')[0]
    try:
        pdfmetrics.registerFont(TTFont('SerifCJK', path, subfontIndex=2))
        return 'SerifCJK'
    except Exception:
        try:
            pdfmetrics.registerFont(TTFont('SerifCJK', path, subfontIndex=0))
            return 'SerifCJK'
        except Exception:
            return fonts['cjk']

def dark_pages():
    prefix = "/data/workspace/steel_dream/omni_th"
    for old in glob.glob(prefix + "-*.jpg"):
        os.remove(old)
    subprocess.run(["pdftoppm", "-jpeg", "-r", "30", SRC, prefix],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = []
    for f in sorted(glob.glob(prefix + "-*.jpg")):
        idx = int(os.path.basename(f).split('-')[1].split('.')[0])
        im = Image.open(f).convert('L').resize((40, 40))
        if sum(im.getdata()) / 1600 < 160:
            out.append(idx)
    return set(out)

def make_layer(w, h, draw):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    draw(c, w, h)
    c.showPage(); c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]

def volume_labels(reader):
    """按页文本里出现的卷标切换页眉；正文页自带页眉，章扉页自带 vol_label。"""
    cur, out = FALLBACK, []
    for page in reader.pages:
        txt = (page.extract_text() or "").replace("\n", " ")
        for needle, lab in LABELS:
            if needle in txt:
                cur = lab
                break
        out.append(cur)
    return out

def main():
    hf = header_font()
    dark = dark_pages()
    reader = PdfReader(SRC)
    labels = volume_labels(reader)
    writer = PdfWriter()
    for i, src_page in enumerate(reader.pages, start=1):
        page = writer.add_page(src_page)
        w = float(page.mediabox.width); h = float(page.mediabox.height)
        is_dark = i in dark
        rgb = DARK_RGB if is_dark else PAPER_RGB
        under = make_layer(w, h, lambda c, w, h, rgb=rgb: (
            c.setFillColorRGB(*rgb), c.rect(0, 0, w, h, stroke=0, fill=1)))
        page.merge_page(under, over=False)
        txt = (src_page.extract_text() or '').strip()
        if (not is_dark) and i >= 5 and txt:
            vol = labels[i - 1]
            def overlay(c, w, h, n=i, vol=vol):
                c.setFont(hf, 8.5)
                c.setFillColor(HexColor('#7A6E5D'))
                if n % 2 == 0:
                    c.drawString(85, h - 46, BOOK)
                else:
                    c.drawRightString(w - 85, h - 46, vol)
                c.setStrokeColor(HexColor('#C9BDA6'))
                c.setLineWidth(0.4)
                c.line(85, h - 53, w - 85, h - 53)
                c.setFont(hf, 9)
                c.setFillColor(HexColor('#5A544C'))
                if n % 2 == 0:
                    c.drawString(85, 34, str(n))
                else:
                    c.drawRightString(w - 85, 34, str(n))
            page.merge_page(make_layer(w, h, overlay), over=True)
    writer.add_metadata({'/Title': '钢铁之梦 全帙合订本（三卷＋番外一辑）',
                         '/Author': '一部西部黑色纪事',
                         '/Subject': '新黑色电影 × 纯正西部 · 正编三卷未增一字，番外五篇另立一辑'})
    with open(TMP, 'wb') as f:
        writer.write(f)
    os.replace(TMP, SRC)
    seg = {}
    for i, lab in enumerate(labels, 1):
        seg.setdefault(lab, []).append(i)
    print('OK pages:', len(reader.pages), '| dark:', len(dark), '| header font:', hf)
    for lab, pages in seg.items():
        print('  ', lab, pages[0], '-', pages[-1])

if __name__ == '__main__':
    main()
