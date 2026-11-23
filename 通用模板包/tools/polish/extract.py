#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract.py —— 从原稿里抽出指定章节，去括号、并段落，便于一次读一章

用法：
    python3 tools/extract.py 126                 # 第 126 章
    python3 tools/extract.py 126 --raw           # 保留原稿一行一括号
    python3 tools/extract.py 126 --limit 2000    # 只看前 2000 字
    python3 tools/extract.py 126 --src ./原稿    # 指定原稿目录
    python3 tools/extract.py 126 --scan          # 只列全目录（章号 + 标题）

识别：# 第 126 章 / 第126章 / ## 第 126 章 三种写法。
输出：去括号、连续短句合并为 6～8 句一段、对白独立成段。
"""
import os
import re
import sys
import glob
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def cfg():
    try:
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


CH_ANY = re.compile(r"^#{0,3}\s*第\s*0*(\d+)\s*章\s*(.*)$")


def scan(src):
    seen = {}
    for path in sorted(glob.glob(os.path.join(src, "*.md"))):
        for i, l in enumerate(open(path, encoding="utf-8-sig").read().split("\n")):
            s = l.strip().strip("\ufeff").strip()
            if not s.startswith("#"):
                continue
            m = CH_ANY.match(s)
            if m:
                seen.setdefault(int(m.group(1)),
                                (m.group(2).strip(), os.path.basename(path), i + 1))
    return [(no,) + seen[no] for no in sorted(seen)]


def find(n, src):
    for path in sorted(glob.glob(os.path.join(src, "*.md"))):
        lines = open(path, encoding="utf-8-sig").read().split("\n")
        start = None
        for i, l in enumerate(lines):
            m = CH_ANY.match(l.strip())
            if m and l.strip().startswith("#") and int(m.group(1)) == n:
                start = i
                break
        if start is None:
            continue
        end = len(lines)
        for j in range(start + 1, len(lines)):
            m = CH_ANY.match(lines[j].strip())
            if m and lines[j].strip().startswith("#"):
                end = j
                break
        return path, lines[start:end]
    return None, None


def clean(lines, per=4):
    out, buf = [], []

    def flush():
        nonlocal buf
        if buf:
            out.append("".join(buf))
            buf = []

    for l in lines[1:]:
        s = l.strip()
        if not s:
            continue
        if s.startswith("（"):
            s = s.strip("（）()").strip()
            if not s:
                continue
            buf.append(s)
            if len(buf) >= per:
                flush()
        else:
            flush()
            out.append(s)
    flush()
    return "\n\n".join(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 3
    c = cfg()
    src = c.get("src_dir") or os.environ.get("POLISH_SRC_DIR", "./src")
    if "--src" in sys.argv:
        src = sys.argv[sys.argv.index("--src") + 1]
    if "--scan" in sys.argv:
        rows = scan(src)
        if not rows:
            print("未在 %s 找到章标题（需 # 第 N 章 或 第N章）" % src)
            return 3
        for no, title, f, ln in rows:
            print("%4d  %-28s %s:%d" % (no, title, f, ln))
        return 0
    m = re.search(r"\d+", sys.argv[1] or "")
    if not m:
        print(__doc__)
        return 3
    n = int(m.group())
    path, lines = find(n, src)
    if not path:
        print("未找到第 %d 章（检索目录：%s）" % (n, src))
        return 3
    body = "\n".join(lines) if "--raw" in sys.argv else clean(lines)
    if "--limit" in sys.argv:
        body = body[:int(sys.argv[sys.argv.index('--limit') + 1])]
    print("# 来源：%s" % os.path.basename(path))
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
