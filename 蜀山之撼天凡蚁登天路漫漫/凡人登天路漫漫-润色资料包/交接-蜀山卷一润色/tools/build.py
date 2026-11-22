#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并草稿 → 交付件（md / txt / docx），校验后自动上传知识库。

用法：
    python3 tools/build.py --start 110 --end 114
    python3 tools/build.py --start 110 --end 114 --upload
    python3 tools/build.py --start 110 --end 110 --dir draft --force

草稿命名约定：<dir>/ch110.md、ch111.md …（一章一个文件，正文不含括号）
输出：/sandbox/workspace/凡人登天路漫漫-第X至Y章-润色稿.md / .txt / .docx
知识库：ima_kb_UDyaN3jL（“少年不流氓，发育不正常的知识库”）
"""
import os
import re
import sys
import argparse
import subprocess

import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

KB = "ima_kb_UDyaN3jL"
UPLOADER = "/sandbox/workspace/skills/ima-knowledge/scripts/upload_file.py"
OUTDIR = "/sandbox/workspace"
MIN = 3000

CN = "〇一二三四五六七八九"


def cn(n):
    if n < 10:
        return CN[n]
    if n < 20:
        return "十" + (CN[n % 10] if n % 10 else "")
    if n < 100:
        return CN[n // 10] + "十" + (CN[n % 10] if n % 10 else "")
    h, r = divmod(n, 100)
    s = CN[h] + "百"
    if r == 0:
        return s
    if r < 10:
        return s + "〇" + CN[r]
    return s + cn(r)


def han(t):
    return len(re.findall(r"[\u4e00-\u9fa5]", t))


def check(name, t):
    h = han(t)  # 口径：全文汉字
    p = t.count("\uff08") + t.count("\uff09")
    ok = h >= MIN and p == 0
    print("%-14s 汉字%5d 括号%d %s" % (name, h, p, "OK" if ok else "FAIL"))
    return ok


def make_docx(out, text):
    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    pf = st.paragraph_format
    pf.line_spacing = 1.6
    pf.space_after = Pt(6)
    for line in text.split("\n"):
        if not line.strip():
            continue
        s = line.strip()
        if s.startswith("《凡人登天路漫漫》"):
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(18)
            r = p.add_run(s)
            r.font.size = Pt(14)
            r.bold = True
            r.font.name = "宋体"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            continue
        if re.match(r"^第[〇一二三四五六七八九十百零\d]+章", s):
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(12)
            r = p.add_run(s)
            r.font.size = Pt(15)
            r.bold = True
            r.font.name = "宋体"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            continue
        p = d.add_paragraph(s.replace("\u3000\u3000", ""))
        p.paragraph_format.first_line_indent = Pt(24)
    d.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--dir", default="draft")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    parts, bad = [], 0
    for n in range(a.start, a.end + 1):
        f = os.path.join(a.dir, "ch%d.md" % n)
        if not os.path.exists(f):
            print("缺稿", f)
            bad += 1
            continue
        t = open(f, encoding="utf-8").read().strip()
        if not check("ch%d" % n, t):
            bad += 1
        parts.append(t)

    if bad and not a.force:
        print("\n有 %d 处不合格，已停止。修好后重跑；确要强行交付加 --force" % bad)
        sys.exit(2)

    title = "《凡人登天路漫漫》第一卷·第%s至%s章（润色稿）" % (cn(a.start), cn(a.end))
    text = title + "\n\n" + "\n\n".join(parts) + "\n"
    base = os.path.join(OUTDIR, "凡人登天路漫漫-第%d至%d章-润色稿" % (a.start, a.end))
    open(base + ".md", "w", encoding="utf-8").write(text)
    open(base + ".txt", "w", encoding="utf-8-sig").write(text)
    make_docx(base + ".docx", text)
    print("\n已生成：\n  %s.md\n  %s.txt\n  %s.docx" % (base, base, base))
    print("合计汉字 %d" % sum(han(p) for p in parts))

    if a.upload:
        cmd = [sys.executable, UPLOADER, "--file-path", base + ".docx",
               "--knowledge-base-id", KB,
               "--rename", os.path.basename(base) + ".docx"]
        print("上传中…")
        subprocess.run(cmd, check=True)
    else:
        print("未上传（加 --upload 上传到 %s）" % KB)


if __name__ == "__main__":
    main()
