#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描上游章纲文件的章段重叠——三套章纲互斥而无人察觉的防线。

问题背景（2026-11-18）：`02E` / `02B` / `02F` / `03D` 四份文件都声明了卷三
251–375 的章纲，彼此逐章事件互斥（实测 02E 的 15 个 ★ 章与 03D 一致 0 个），
但没有任何检查项能发现——直到人工复核才暴露。

本脚本输出：哪些文件声明了哪些章段、同一章号是否被多份文件同时声明。
不判"对错"（对错靠人裁决），只暴露**声明冲突的事实**，供人工加裁定块。

用法：python3 校验/扫描章纲冲突.py
"""
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = ("校验/", "正文/", "废弃/", ".workbuddy-backup/")
# 正文与施工规格不算"上游章纲"——正文是成稿，规格是派工依据
TABLE_RE = re.compile(r"^\| (\d{3}) ", re.M)


def main():
    files = {}
    for root, _d, fs in os.walk(ROOT):
        for f in fs:
            if not f.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, f), ROOT).replace(os.sep, "/")
            if any(rel.startswith(p) for p in SKIP_DIRS):
                continue
            try:
                t = open(os.path.join(ROOT, rel), encoding="utf-8").read()
            except Exception:
                continue
            chs = {int(m.group(1)) for m in TABLE_RE.finditer(t)}
            if chs:
                files[rel] = chs

    print("=== 含章号表的上游文件（声明了哪些章）===")
    for p, c in sorted(files.items()):
        print(f"  {p:44} {min(c):3}–{max(c):3}  {len(c):3}章")

    owner = defaultdict(list)
    for p, c in files.items():
        for n in c:
            owner[n].append(p)
    dup = {n: v for n, v in owner.items() if len(v) > 1}

    print()
    print("=== 章号声明重叠 ===")
    print("  ⚠ 读法（重要）：**章号重叠本身多半是设计，不是缺陷**——")
    print("    02E 是「卷级关键章摘录」（71 章），03C/03D/03E/03F 是「施工级逐章」；")
    print("    前者从后者里挑关键章，章号必然重叠（137–250、376–500、501–625 都是这层关系）。")
    print("    **真正要人工裁定的是「同一章的事件是否互斥」**，不是章号是否重叠。")
    print("    2026-11-18 卷三段实测：02E 的 15 个 ★ 章与 03D 逐章比对，事件一致 0 个 → 已加裁定块。")
    print()
    if not dup:
        print("  无重叠")
        return 0
    print(f"  {len(dup)} 个章号被多份文件同时声明（供人工挑出「事件互斥」的可疑组）：")
    # 按重叠组合汇总
    combos = defaultdict(list)
    for n, v in dup.items():
        combos[tuple(sorted(v))].append(n)
    for combo, nums in sorted(combos.items(), key=lambda kv: -len(kv[1])):
        rng = f"{min(nums)}–{max(nums)}" if len(nums) > 1 else str(nums[0])
        print(f"    {len(nums):3}章  {rng}")
        for c in combo:
            print(f"           · {c}")
    print()
    print("  → 处置：逐组挑出**事件互斥**的，裁定以哪份为准；")
    print("    然后在被采纳的那份之外的其它文件里加「口径裁定块」注明作废，")
    print("    并在下游规格里写明以哪份为准。")
    print("  → 已裁定的：卷三段（02E/02B/02F 三处裁定块，2026-11-18）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
