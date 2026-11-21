# -*- coding: utf-8 -*-
"""PDF 精装后处理：满版深炭章扉、暖灰做旧纸色、双名制页眉与外侧页码。"""
import sys, os, glob, shutil
sys.path.insert(0, "/data/skills/pdf/scripts")

from fonts import register_all_fonts
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
from PIL import Image
from io import BytesIO

SRC = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"
TMP = "/data/workspace/.steel_dream_post3.pdf"
DARK_RGB = (0.1098, 0.1020, 0.0902)   # #1C1A17
PAPER_RGB = (0.9569, 0.9373, 0.9020)  # #F4EFE6
VOL = "卷三 · 钢铁之梦"
BOOK = "钢铁之梦"

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
    import subprocess
    prefix = "/data/workspace/steel_dream/thx3"
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

def main():
    hf = header_font()
    dark = dark_pages()
    reader = PdfReader(SRC)
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
            def overlay(c, w, h, n=i):
                c.setFont(hf, 8.5)
                c.setFillColor(HexColor('#7A6E5D'))
                if n % 2 == 0:
                    c.drawString(85, h - 46, BOOK)
                else:
                    c.drawRightString(w - 85, h - 46, VOL)
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
    writer.add_metadata({'/Title': '钢铁之梦·卷三 钢铁之梦（终卷）',
                         '/Author': '一部西部黑色纪事',
                         '/Subject': '新黑色电影 × 纯正西部 · 多诺万家族三部曲第三部 终卷'})
    with open(TMP, 'wb') as f:
        writer.write(f)
    os.replace(TMP, SRC)
    print('OK pages:', len(reader.pages), '| dark pages:', sorted(dark), '| header font:', hf)

if __name__ == '__main__':
    main()
