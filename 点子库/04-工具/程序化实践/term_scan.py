#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
术语白名单扫描 · term_scan.py（点子库程序化实践配套，2026-11-13）
--------------------------------------------------------------------------
对应模板：通用模板包 18-程序化创作与算法脚本模板.md §三.4（机械巡检槽位在本项目的具体化）
用途：对生成候选 / 章节文本做两项确定性核查：
  A. 典内术语命中——文本里出现了哪些《18-全设定术语表》收录的术语、各多少次；
  B. 疑似新专名报警——高频（≥2 次）连续汉字片段，既不在术语白名单内、
     也不包含/包含于任何术语 → 标记"待人审"（可能是候选生成擅自造的专名，或正文漏登术语）。
纪律：只出报告，不代改正文（与 11 号模板铁律同源）。

用法（在 04-工具/程序化实践/ 下）：
  python term_scan.py --text 支线候选-20261113.txt
  python term_scan.py --text ../../02-正文/第001章_xxx.md --min-freq 3
退出码：0 成功。
"""
import argparse
import re
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_TERMS = r"..\..\01-设定集\18-全设定术语表.md"
HAN = re.compile(r"[\u4e00-\u9fff]{2,}")

# 噪声词：确知非专名的高频片段（首轮实跑后人工判定沉淀；新增噪声往这里加）
NOISE = {"候选", "一句话", "只说了一", "了一句话", "台账记作", "记作", "之后", "直到"}


def _read_text(path):
    """按 BOM/试探读取 UTF-16 / UTF-8(-SIG) / GBK 文本（Windows 管道存档常见混用）。"""
    b = open(path, "rb").read()
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        return b.decode("utf-16")
    if b.startswith(b"\xef\xbb\xbf"):
        return b.decode("utf-8-sig")
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("无法识别文件编码：%s" % path)


def load_terms(path):
    """从三列术语表抽第一列；复合条目（A/B、A=B）拆成独立术语。"""
    terms = set()
    for line in open(path, "r", encoding="utf-8-sig"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if set(cells[0]) <= set("-—: "):        # 分隔行
            continue
        for t in re.split(r"[／/＝=]", cells[0]):
            t = t.strip()
            if len(t) >= 2 and not t.startswith("术语"):
                terms.add(t)
    return terms


def scan(text, terms):
    # A. 术语命中
    hits = sorted(((t, text.count(t)) for t in terms if t in text),
                  key=lambda x: (-x[1], x[0]))
    # B. 疑似新专名：2~4 字高频片段，与白名单无包含关系
    grams = Counter()
    for seg in HAN.findall(text):
        for n in (2, 3, 4):
            for i in range(len(seg) - n + 1):
                grams[seg[i:i + n]] += 1
    suspects = []
    for g, c in grams.items():
        if c < 2 or g in NOISE:
            continue
        if any(g in t or t in g for t in terms):
            continue
        suspects.append((g, c))
    # 长片段吞并：若被更长且频次不低于自己的可疑片段包含，则视为其切分噪声
    keep = []
    for g, c in sorted(suspects, key=lambda x: -len(x[0])):
        if not any(g in G and C >= c for G, C in keep):
            keep.append((g, c))
    keep.sort(key=lambda x: (-x[1] * len(x[0]), x[0]))
    return hits, keep


def main():
    ap = argparse.ArgumentParser(description="术语白名单扫描（只出报告，不代改正文）")
    ap.add_argument("--text", required=True, help="待扫描文本文件（候选/章节均可）")
    ap.add_argument("--terms", default=DEFAULT_TERMS, help="术语表 md（默认点子库 18-全设定术语表）")
    ap.add_argument("--top", type=int, default=15, help="疑似新专名最多列几条")
    args = ap.parse_args()

    text = _read_text(args.text)
    terms = load_terms(args.terms)
    hits, suspects = scan(text, terms)

    print("术语白名单扫描 · text=%s · 术语表=%s（白名单 %d 条）" % (args.text, args.terms, len(terms)))
    print("-" * 52)
    print("A. 典内术语命中（%d 种）：" % len(hits))
    for t, c in hits:
        print("   %-14s ×%d" % (t, c))
    if not hits:
        print("   （无）")
    print("-" * 52)
    print("B. 疑似新专名（待人审，前 %d 条）：" % args.top)
    shown = suspects[:args.top]
    for g, c in shown:
        print("   %-6s ×%d" % (g, c))
    if not shown:
        print("   （无）")
    print("-" * 52)
    print("处置：A 区术语用法须与《18-全设定术语表》定义一致；B 区片段人工判定——")
    print("      确属新专名 → 走正式入典流程（白名单铁律）；是误报 → 加入噪声词忽略。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
