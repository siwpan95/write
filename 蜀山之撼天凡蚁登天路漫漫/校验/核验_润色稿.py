#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核验「凡人登天路漫漫-润色资料包」前 20 章（1–5 / 6–10 / 11–15 / 16–20 四份 docx）。

只读，不改任何文件。用途：确认润色稿的章数、字数、结构、与原稿的对应关系。
用法：python3 校验/核验_润色稿.py
"""
import os
import re
import zipfile
from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "凡人登天路漫漫-润色资料包")
FILES = [
    "凡人登天路漫漫-第1至5章-润色稿.docx",
    "凡人登天路漫漫-第6至10章-润色稿.docx",
    "凡人登天路漫漫-第11至15章-润色稿.docx",
    "凡人登天路漫漫-第16至20章-润色稿.docx",
]

# 原稿：卷一 1–125 在哪些文件
src = {}
for f in os.listdir(os.path.join(ROOT, "正文")):
    if "蜀山 卷一" not in f or not f.endswith(".md"):
        continue
    path = os.path.join(ROOT, "正文", f)
    s = open(path, encoding="utf-8").read()
    parts = re.split(r"^# 第 (\d+) 章 (.+)$", s, flags=re.M)
    for i in range(1, len(parts) - 1, 3):
        src[int(parts[i])] = (parts[i + 1].strip(), parts[i + 2], f)

print(f"原稿卷一章数: {len(src)}；范围 {min(src)}–{max(src)}\n")

all_ok = True
for name in FILES:
    path = os.path.join(PACK, name)
    print("=" * 72)
    print(f"{name}  ({os.path.getsize(path):,} bytes)")
    if not zipfile.is_zipfile(path):
        print("  ❌ 不是有效 docx（zip 损坏）")
        all_ok = False
        continue
    try:
        doc = Document(path)
    except Exception as ex:
        print(f"  ❌ 打不开: {ex}")
        all_ok = False
        continue

    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    title_lines = [p for p in paras if re.match(r"^第\s*\d+\s*章", p)]
    print(f"  段落数 {len(paras)}；识别章标题 {len(title_lines)} 个")

    # 逐章切分与统计
    chapters = []
    cur = None
    for p in paras:
        m = re.match(r"^第\s*(\d+)\s*章\s*(.*)$", p)
        if m:
            cur = {"n": int(m.group(1)), "title": m.group(2).strip(), "lines": []}
            chapters.append(cur)
        elif cur:
            cur["lines"].append(p)
    for c in chapters:
        body = "\n".join(c["lines"])
        chars = len(re.sub(r"\s", "", body))
        dq = body.count("“") + body.count("”") + body.count("「") + body.count("」") + body.count('"')
        s = src.get(c["n"])
        if s:
            src_chars = len(re.sub(r"\s", "", s[1]))
            delta = chars - src_chars
            rel = f"原稿《{s[0]}》{src_chars}字 → 差 {delta:+d} ({delta/src_chars*100:+.1f}%)"
            title_same = "同" if s[0] == c["title"] else f"异（原：{s[0]}）"
        else:
            rel = "⚠ 原稿未找到对应章号"
            title_same = "—"
        print(f"  {c['n']:>3} {c['title'][:14]:16} {chars:>5}字  引号{dq:>3}  标题{title_same}")
        print(f"       {rel}")
        if dq:
            print(f"       ⚠ 引号 {dq} 处（若沿用零引号体例需处理）")

    expect = [int(x) for x in re.findall(r"第(\d+)至(\d+)章", name)[0]]
    got = [c["n"] for c in chapters]
    want = list(range(expect[0], expect[1] + 1))
    if got != want:
        print(f"  ❌ 章号不符：期望 {want}，实得 {got}")
        all_ok = False
    else:
        print(f"  ✅ 章号齐 {want[0]}–{want[-1]}")

print("\n" + "=" * 72)
print("结论:", "PASS（结构层面）" if all_ok else "FAIL：有文件需重查")
print("注：本脚本只核结构与字数对应，**不判润色质量**；质量须抽样对读。")
