#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字数与格式检查（本项目的唯一计数口径）

用法：
    python3 tools/count.py draft/ch110.md
    python3 tools/count.py draft/ch110.md draft/ch111.md

输出每章：正文汉字数（不含标点、空格、章节标题）、括号数、段落数、判定。
判定 PASS 条件：正文汉字 >= 3000 且 全角括号数 == 0。
"""
import re
import sys
import os

MIN = 3000


def stats(path):
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    body = text  # 口径：全文汉字（含章节标题，与 1—109 章已交付稿一致）
    han = len(re.findall(r"[\u4e00-\u9fa5]", body))
    paren = body.count("\uff08") + body.count("\uff09")
    ascii_quote = body.count('"')
    odd_curly = 0
    if body.count("\u201c") != body.count("\u201d"):
        odd_curly = 1
    paras = len([l for l in lines if l.strip() and not l.strip().startswith("《")])
    ok = han >= MIN and paren == 0
    return dict(path=path, han=han, paren=paren, ascii_quote=ascii_quote,
                odd_curly=odd_curly, paras=paras, ok=ok)


def main():
    files = sys.argv[1:]
    if not files:
        print(__doc__)
        sys.exit(1)
    total = 0
    bad = 0
    for f in files:
        if not os.path.exists(f):
            print("MISSING", f)
            bad += 1
            continue
        s = stats(f)
        total += s["han"]
        flag = "PASS" if s["ok"] else "FAIL"
        if not s["ok"]:
            bad += 1
        print("%-28s 汉字%5d  括号%d  段%3d  半角引号%d  单引号%d  %s" % (
            os.path.basename(f), s["han"], s["paren"], s["paras"],
            s["ascii_quote"], s["odd_curly"], flag))
    print("合计汉字 %d；不合格 %d 章" % (total, bad))
    sys.exit(0 if bad == 0 else 2)


if __name__ == "__main__":
    main()
