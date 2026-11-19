#!/usr/bin/env python3
"""repeat_probe.py —— 语料级「同一内容多份副本」探针（零第三方依赖）。

用途
    以基数树/前缀身份的口径回答一个问题：一个写作仓里，究竟有多少字被"重复存放"了？
    即：同一段连续汉字，在两个位置（可能是两个文件）被完整保存了两遍以上。

    这不是 KV 缓存，但它和 RadixAttention 共享同一个前提判断——
    **同一段内容应该只有一个身份，否则下游每一次「读全文」都要为它付第二遍钱，
    并且可能给出两份互相竞争的结论。**

算法
    1. 规范化：NFKC + 只保留汉字（去掉标点/空白/英文数字），消除排版差异造成的假阴性。
    2. K-gram 建桶：K 个连续汉字作键，记录 (文件, 偏移)。
    3. 桶内两两延伸：对同桶候选做最长公共前缀延伸（LCE），长度 ≥ MIN 才算重复。
    4. 覆盖去重：命中区域打标记，保证每段内容只被报告一次（极大重复段），
       避免"整体重复文件"被逐字滑窗放大成十万条。
    5. 汇总：被覆盖字数占比、最长重复段、重复字数最多的文件对。

用法
    python repeat_probe.py <目录> [--k 20] [--min 40] [--top 10]

退出码
    0 正常 ／ 2 参数错误

注意
    只读。不修改任何被扫文件。同一输入同一输出（无时间戳、无随机数）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from collections import defaultdict

CJK = re.compile(r"[\u4e00-\u9fff]")
SKIP_DIRS = {".git", "node_modules", "_archive", "__pycache__"}


def normalize(text: str) -> str:
    return "".join(CJK.findall(unicodedata.normalize("NFKC", text)))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            return text[end + 4 :]
    return text


def load_corpus(root: str, min_chars: int = 400) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            try:
                raw = open(path, encoding="utf-8-sig").read()
            except OSError:
                continue
            body = normalize(strip_frontmatter(raw))
            if len(body) >= min_chars:
                docs.append((os.path.relpath(path, root), body))
    docs.sort()
    return docs


def lce(a: str, i: int, b: str, j: int, cap: int) -> int:
    """最长公共前缀延伸，上界 cap 防止重复整档时无限拉长。"""
    k = 0
    la, lb = len(a), len(b)
    while i + k < la and j + k < lb and k < cap and a[i + k] == b[j + k]:
        k += 1
    return k


def probe(root: str, k: int, min_len: int, top: int) -> int:
    docs = load_corpus(root)
    if not docs:
        print(f"[空] {root} 下没有 ≥400 汉字的 md 文件")
        return 0
    total = sum(len(body) for _, body in docs)
    print(f"[语料] {len(docs)} 文件 / 规范化汉字 {total:,}")

    index: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for di, (_, body) in enumerate(docs):
        for i in range(0, len(body) - k + 1):
            index[body[i : i + k]].append((di, i))
    print(f"[索引] {k}-gram 桶数 {len(index):,}")

    cover = [bytearray(len(body)) for _, body in docs]
    spans: list[tuple[int, int, int, int, int]] = []
    for positions in index.values():
        if len(positions) < 2:
            continue
        for x in range(len(positions)):
            d1, i1 = positions[x]
            if cover[d1][i1]:
                continue
            for y in range(x + 1, len(positions)):
                d2, i2 = positions[y]
                if d1 == d2 and abs(i1 - i2) < k:
                    continue
                if cover[d2][i2] and d1 != d2:
                    continue
                length = lce(docs[d1][1], i1, docs[d2][1], i2, cap=len(docs[d1][1]))
                if length < min_len:
                    continue
                for t in range(i1, i1 + length):
                    cover[d1][t] = 1
                for t in range(i2, i2 + length):
                    cover[d2][t] = 1
                spans.append((length, d1, i1, d2, i2))
                break  # 一个起点只报最长的一次

    covered = sum(sum(c) for c in cover)
    spans.sort(reverse=True)
    print(f"[结果] 极大重复段 {len(spans)} 处；被重复覆盖 {covered:,} 字（占 {covered / total * 100:.1f}%）")

    if spans:
        print(f"\n[最长的 {min(top, len(spans))} 段]")
        for length, d1, i1, d2, i2 in spans[:top]:
            print(f"  {length:5d}字  {docs[d1][0]}  <->  {docs[d2][0]}")
            print(f"         {docs[d1][1][i1 : i1 + min(length, 44)]}…")

    pair: dict[tuple[str, str], int] = defaultdict(int)
    for length, d1, _, d2, _ in spans:
        pair[tuple(sorted((docs[d1][0], docs[d2][0])))] += length
    if pair:
        print(f"\n[重复字数最多的文件对 Top{min(6, len(pair))}]")
        for (a, b), value in sorted(pair.items(), key=lambda kv: -kv[1])[:6]:
            print(f"  {value:7,d}字  {a}  |  {b}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="语料级重复副本探针（只读）")
    parser.add_argument("root", help="待扫目录（作品项目根）")
    parser.add_argument("--k", type=int, default=20, help="K-gram 长度，默认 20")
    parser.add_argument("--min", dest="min_len", type=int, default=40, help="计入重复的最短长度，默认 40")
    parser.add_argument("--top", type=int, default=10, help="展示最长重复段条数，默认 10")
    args = parser.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"[错] 不是目录：{args.root}", file=sys.stderr)
        return 2
    if args.k < 8 or args.min_len <= args.k:
        print("[错] 需满足 k ≥ 8 且 min > k", file=sys.stderr)
        return 2
    return probe(args.root, args.k, args.min_len, args.top)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
