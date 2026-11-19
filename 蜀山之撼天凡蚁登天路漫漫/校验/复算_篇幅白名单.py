#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复算篇幅白名单：重算白名单内各章的完全重复/近似重复，与本表数据对不上就报错。

用途：防止「白名单」变成「懒得查」的口袋。任何人改了白名单内某章，本脚本会抓出来。
用法：python3 校验/复算_篇幅白名单.py
退出码：0 全部一致；1 有不一致（须重查或移出白名单）
"""
import difflib
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_whitelist():
    p = os.path.join(ROOT, "校验", "篇幅白名单.md")
    out = {}
    for ln in open(p, encoding="utf-8"):
        m = re.match(r"^\|\s*(\d{3})\s*\|\s*(\d+)\s*\|", ln)
        if m:
            out[int(m.group(1))] = int(m.group(2))
    return out


def chapters():
    """返回 {章号: 正文}（只扫卷二、卷三正文）。"""
    out = {}
    for pat in ("蜀山 卷二*.md", "蜀山 卷三*.md"):
        for f in glob.glob(os.path.join(ROOT, "正文", pat)):
            s = open(f, encoding="utf-8").read()
            parts = re.split(r"^# 第 (\d+) 章 (.+)$", s, flags=re.M)
            for i in range(1, len(parts) - 1, 3):
                out[int(parts[i])] = parts[i + 2]
    return out


def check(body):
    segs = [l.strip() for l in body.split("\n") if l.strip().startswith("（")]
    core = [re.sub(r"[（）。，、！？：；]", "", x) for x in segs]

    # 完全重复
    dup = 0
    seen = {}
    for c in core:
        if len(c) >= 8:
            seen[c] = seen.get(c, 0) + 1
    dup = sum(1 for c, k in seen.items() if k > 1)

    # 近似重复
    near = 0
    for a in range(len(core)):
        if len(core[a]) < 8:
            continue
        for b in range(a + 1, min(a + 26, len(core))):
            if len(core[b]) < 8:
                continue
            if difflib.SequenceMatcher(None, core[a], core[b]).ratio() > 0.82:
                near += 1

    pure = body.replace("（本章完）", "")
    n = len(re.sub(r"\s", "", re.sub(r"^#.*$", "", pure, flags=re.M)))
    return n, dup, near


def main():
    wl = load_whitelist()
    ch = chapters()
    bad = 0
    print(f"白名单 {len(wl)} 章；复算中…\n")
    print(f"{'章':>4} {'表内字数':>8} {'实测字数':>8} {'完全重复':>8} {'近似重复':>8}  判定")
    for num in sorted(wl):
        if num not in ch:
            print(f"{num:>4} {wl[num]:>8} {'—':>8} {'—':>8} {'—':>8}  ✗ 章号未找到")
            bad += 1
            continue
        n, dup, near = check(ch[num])
        ok = (dup == 0 and near == 0)
        mark = "✓ 一致" if ok and abs(n - wl[num]) <= 60 else "✗ 需重查"
        if not ok or abs(n - wl[num]) > 60:
            bad += 1
        print(f"{num:>4} {wl[num]:>8} {n:>8} {dup:>8} {near:>8}  {mark}")
    print()
    if bad:
        print(f"结论：FAIL（{bad} 章不一致）—— 修正白名单，或把该章压回 2200–3000 后移出。")
        return 1
    print(f"结论：PASS —— 白名单 {len(wl)} 章全部无无效重复，数据与表一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
