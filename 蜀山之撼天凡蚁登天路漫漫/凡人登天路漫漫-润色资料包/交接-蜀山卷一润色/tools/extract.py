#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从原稿提取指定章节，去括号、按段落输出，便于一次读完一章素材。

用法：
    python3 tools/extract.py 110            # 输出第110章
    python3 tools/extract.py 110 --raw       # 保留原稿一行一括号形式
    python3 tools/extract.py 110 --limit 3000

原理：在 uploads 目录的所有 md 里找 “# 第 N 章” 标记，取到下一个章标题为止。
原稿是“一行一括号”的草稿，本脚本把括号去掉，并把连续短句合并成 6-8 句一段；
原稿中不以“（”开头的行是对白，遇到对白另起一段。
"""
import re
import sys
import glob
import os

UP = "/sandbox/workspace/uploads"
PER_PARA = 7


def find_chapter(n):
    pat = re.compile(r"^#\s*第\s*0*%d\s*章" % n)
    nxt = re.compile(r"^#\s*第\s*0*\d+\s*章")
    for path in sorted(glob.glob(os.path.join(UP, "*.md"))):
        lines = open(path, encoding="utf-8").read().split("\n")
        start = None
        for i, l in enumerate(lines):
            if pat.match(l.strip()):
                start = i
                break
        if start is None:
            continue
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if nxt.match(lines[j].strip()):
                end = j
                break
        return path, lines[start:end]
    return None, None


def clean(seg, raw=False):
    out = []
    for l in seg:
        s = l.strip()
        if not s:
            continue
        if raw:
            out.append(s)
            continue
        is_dialog = not s.startswith("\uff08")
        s = s.replace("\uff08", "").replace("\uff09", "")
        out.append(("D" if is_dialog else "N", s))
    return out


def paragraphize(items, per=PER_PARA):
    paras, buf = [], []
    for kind, s in items:
        if kind == "D":
            if buf:
                paras.append("".join(buf))
                buf = []
            paras.append(s)
        else:
            buf.append(s)
            if len(buf) >= per:
                paras.append("".join(buf))
                buf = []
    if buf:
        paras.append("".join(buf))
    return paras


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    n = int(sys.argv[1])
    raw = "--raw" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    path, seg = find_chapter(n)
    if seg is None:
        print("未找到第 %d 章（检查 uploads 目录）" % n)
        sys.exit(2)
    print("# 来源：%s" % os.path.basename(path))
    print("# 第 %d 章" % n)
    items = clean(seg, raw=raw)
    if raw:
        for kind, s in items:
            print(s)
        return
    paras = paragraphize(items)
    body = []
    for p in paras:
        q = p.lstrip("# ").strip()
        if q.startswith("第") and "章" in q[:8]:
            continue
        p = q
        body.append(p)
    text = "\n\n".join(body)
    if limit:
        text = text[:limit]
    print(text)


if __name__ == "__main__":
    main()
