#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保真提取《创造主们的战争》前三章正文（从 AI 对话记录中切出）。

纪律：**只切分、不改写**。正文区里的每一个字符（含标点、空行、
全角符号）原样保留；只做三件事：
  1. 从「第一章 两版都对」等标题行开始截取（丢弃前面的 AI 调研独白）
  2. 在「章末·附」「本章落地的硬指标」「第N章任务：」「本回答由 AI」等
     非正文标记处停止（丢弃后面的备忘与 AI 免责）
  3. 末尾补一个换行，保证文件规范

用法：python _extract_ch1_3.py <src_dir> <out_dir> [--dry]
"""
import argparse
import io
import re
import sys
from pathlib import Path

CHAPTERS = [
    ("第一章.txt", "第一章 两版都对"),
    ("第二章.txt", "第二章 缝合线两侧"),
    ("第三章.txt", "第三章 查无此人"),
]

# 正文结束标记（任一命中即停止）
END_MARKERS = (
    "章末·附", "本章落地的硬指标", "本回答由 AI",
    "第三章任务：", "第一章任务：", "第二章任务：",
)


def extract(text: str, title: str) -> tuple[str, str]:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == title:
            start = i
            break
    if start is None:
        raise ValueError("未找到章节标题：%s" % title)

    body: list[str] = [lines[start]]
    for line in lines[start + 1:]:
        s = line.strip()
        if any(m in s for m in END_MARKERS):
            break
        body.append(line)

    # 去掉尾部空行（正文本身不改）
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n", "cuts at line %d" % (start + 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    src, out = Path(args.src_dir), Path(args.out_dir)
    mapping = {"第一章.txt": "第01章-两版都对.md",
               "第二章.txt": "第02章-缝合线两侧.md",
               "第三章.txt": "第03章-查无此人.md"}
    for fname, title in CHAPTERS:
        text = io.open(src / fname, encoding="utf-8").read()
        body, note = extract(text, title)
        # 正文汉字数（不含标点/空白）—— 与全库口径一致
        han = len(re.findall(r"[\u4e00-\u9fff]", body))
        print(f"{fname} -> {mapping[fname]} | 正文汉字 {han} | {note}")
        if not args.dry:
            target = out / mapping[fname]
            io.open(target, "w", encoding="utf-8", newline="\n").write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
