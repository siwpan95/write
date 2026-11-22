#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_quotes.py —— 中文正文引号规范化

为什么需要
    很多写作/传输环节会把 “ ” 压成英文直引号 "，中文小说里看着极别扭。
    这个脚本把正文里的直引号按「出现顺序成对」还原成 “ ”，并且跳过 ``` 代码块。

用法
    python3 fix_quotes.py ../04_manuscript/*.md
    python3 fix_quotes.py ../04_manuscript --dry-run     # 只看会改多少，不写盘

安全边界
    - 只处理 .md / .txt
    - 跳过代码块与行内代码
    - 引号数为奇数时不动该行（大概率不是对话，而是代码或英文缩写）
"""

import argparse
import sys
from pathlib import Path

LQ, RQ = "\u201c", "\u201d"


def convert_line(line: str):
    """一行内直引号成对替换；奇数个则原样返回。"""
    if line.count('"') % 2 != 0:
        return line, 0
    out, opened, n = [], False, 0
    for ch in line:
        if ch == '"':
            out.append(RQ if opened else LQ)
            opened = not opened
            n += 1
        else:
            out.append(ch)
    return "".join(out), n


def convert_text(text: str):
    lines = text.split("\n")
    out, in_code, changed = [], False, 0
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if in_code or "`" in line:
            out.append(line)
            continue
        new, n = convert_line(line)
        changed += n
        out.append(new)
    return "\n".join(out), changed


def main(argv=None):
    ap = argparse.ArgumentParser(description="中文引号规范化")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    total = 0
    for p in args.paths:
        path = Path(p)
        if not path.is_file() or path.suffix not in (".md", ".txt"):
            continue
        text = path.read_text(encoding="utf-8")
        new, n = convert_text(text)
        if n:
            print(f"{path.name}: {n} 个引号{'（预演）' if args.dry_run else '已转换'}")
            if not args.dry_run:
                path.write_text(new, encoding="utf-8")
        total += n

    print(f"合计 {total} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
