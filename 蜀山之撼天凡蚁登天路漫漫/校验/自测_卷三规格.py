#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验卷三合并规格的内部一致性。

用法：python3 校验/自测_卷三规格.py

注意：合并后的规格里，同一章号会出现两遍——
  §七  逐章施工单（03D 版，施工依据，在前）
  §十一 发现的问题（02E 旧口径对照表，在后）
因此取章行时一律 **first_wins（首次出现优先）**，即 03D 版。
"""
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "正文/_正文施工规格-V3-卷三.md")
SRC = os.path.join(ROOT, "03D-卷三章纲-逐章.md")


def chapter_rows(text):
    """取 251–375 的章行，首次出现优先。"""
    out = {}
    for line in text.split("\n"):
        if not line.startswith("| "):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if c and c[0].isdigit() and 251 <= int(c[0]) <= 375:
            n = int(c[0])
            if n not in out:
                out[n] = c
    return out


def main():
    ok = True
    spec = open(SPEC, encoding="utf-8").read()
    src = open(SRC, encoding="utf-8").read()

    print("== 1. 节号无重复 ==")
    heads = re.findall(r"^## ([一二三四五六七八九十]+)、", spec, flags=re.M)
    print("  节序:", " ".join(heads))
    if len(heads) != len(set(heads)):
        print("  ✗ 有重复节号")
        ok = False
    else:
        print("  ✓ 无重复")

    print("\n== 2. 逐章施工单覆盖 251–375 ==")
    rows = chapter_rows(spec)
    missing = [n for n in range(251, 376) if n not in rows]
    print(f"  章数 {len(rows)}；缺 {len(missing)} 章 {missing[:8]}")
    if missing:
        ok = False

    print("\n== 3. 标题与 03D 逐字一致 ==")
    srows = chapter_rows(src)
    both = sorted(set(rows) & set(srows))
    diff = [(n, srows[n][1], rows[n][1]) for n in both if rows[n][1] != srows[n][1]]
    print(f"  比对 {len(both)} 章；不一致 {len(diff)} 处")
    for d in diff[:6]:
        print("   ✗", d)
    if diff:
        ok = False
    else:
        print("  ✓ 标题零差异")

    print("\n== 4. 四条必备内容在规格内 ==")
    for w in ("押名", "齐灵云", "待焚", "来历不明", "我担"):
        c = spec.count(w)
        print(f"  {w:8} {c} 次 {'✓' if c >= 1 else '✗'}")
        if c < 1:
            ok = False

    print("\n== 5. 接法轮换无连续同种 ==")
    m = re.search(r"## 十、「合即起」接法轮换表(.+?)(?=\n## |\Z)", spec, flags=re.S)
    if not m:
        print("  ✗ 未找到接法轮换表")
        ok = False
    else:
        body = m.group(1)
        kinds = re.findall(r"(物件|人物|时间)", body)
        # 只取"接法"列的值：形如 | 物件 | 或 | 物件（…）
        rows_k = []
        for line in body.split("\n"):
            if not line.startswith("| "):
                continue
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            # 接法值在第 3 列（索引 2）：| 循环 | 起… | **物件** | 备注 |
            for cell in c:
                v = cell.strip("*")
                if v in ("物件", "人物", "时间"):
                    rows_k.append(v)
                    break
        print(f"  接法行 {len(rows_k)}：{Counter(rows_k)}")
        bad = [i for i in range(len(rows_k) - 1) if rows_k[i] == rows_k[i + 1]]
        if not rows_k:
            print("  ⚠ 未识别到接法行（表头格式可能变了，需人工核）")
        elif bad:
            print(f"  ✗ 有连续同种，位置 {bad}")
            ok = False
        else:
            print("  ✓ 无连续同种")

    print("\n== 6. FS 编号不越界（约定 ≤179）==")
    fs = sorted({int(x) for x in re.findall(r"FS-(\d+)", spec)})
    print(f"  范围 {fs[0]}–{fs[-1]}；共 {len(fs)} 个")
    if fs and fs[-1] > 179:
        print("  ✗ 超过约定上限 179")
        ok = False
    else:
        print("  ✓ 在约定范围内")

    print("\n结论：" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
