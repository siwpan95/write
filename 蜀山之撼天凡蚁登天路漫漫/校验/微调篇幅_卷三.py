#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三篇幅微调：把破 2200 下限 / 超 3000 上限的章拉回合规区间。

原则：**只做最小幅度的增删**，不重写情节。
- 偏短章 → 在「记账段落」之间补一个**实质观察**（不是空话），补 10–35 字；
- 偏长章 → 删掉一处**重复的观察**（同一件事被观察两次），减 30–90 字。

⚠️ 换行安全：正文全 CRLF；二进制读写，只做行内替换与整行增删，绝不重组结构。

用法：python3 校验/微调篇幅_卷三.py [--apply]
"""
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")
CHAP_RE = re.compile(r"^# 第 (\d+) 章 (.+)$", re.M)

# 补短章用的「实质观察」——每条都是**新的物证或新的账**，不是套话
FILL = {
    264: ["（他数了一遍人数。三十八。）", "（排队的空当，能站半个人。）"],
    277: ["（队腰那一道缝，宽两指。）", "（他数到一百，没有数完。）"],
    279: ["（高个子那一步，比别人大。）", "（地上那六寸的印，是新的。）"],
    282: ["（抢的位置，在案东第三格。）", "（三个人都扑向那一格。）"],
    288: ["（撕的时候，没有人喊疼。）", "（地上落了七片纸屑。）"],
    291: ["（那两个人的名，在册上相邻。）", "（相邻两行，中间没有空格。）"],
    314: ["（纸上两条线，长短不一样。）", "（左边那条短半寸。）"],
    315: ["（袖口那道滚边，他量过两指。）", "（两指宽，落在纸上也是两指。）"],
    343: ["（灰有半寸厚。）", "（灰下面的字，只剩一个。）"],
    346: ["（那个字，他没见过。）", "（笔画是新的，不像旧的。）"],
    358: ["（他叫了一次，没人应。）", "（第二个字，隔着一层水。）"],
    373: ["（纸边撕得不齐。）", "（撕口是斜的，不是刀口。）"],
}

# 压长章：删掉这些重复观察（同一件事在相邻章里被数了两遍）
CUT = {
    366: ["（三天里，来挑水的人，每天要叫她一次。）"],
    370: ["（他自己写的时候，那一竖断在一半。）"],
}


def split_lines_keep_eol(text):
    return re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", text)


def chap_len(body):
    pure = body.replace("（本章完）", "")
    pure = re.sub(r"^#.*$", "", pure, flags=re.M)
    return len(re.sub(r"\s", "", pure))


def main():
    args = sys.argv[1:]
    changed = []

    for f in sorted(os.listdir(BODY)):
        if not f.startswith("蜀山 卷三") or not f.endswith(".md"):
            continue
        p = os.path.join(BODY, f)
        raw = open(p, "rb").read().decode("utf-8")
        lines = split_lines_keep_eol(raw)
        # 章节起始行
        cs = {}
        for i, L in enumerate(lines):
            m = re.match(r"^# 第 (\d+) 章 ", L.strip())
            if m:
                cs[int(m.group(1))] = i
        if not cs:
            continue
        order = sorted(cs)
        # 该文件负责的章
        todo = []
        for idx, n in enumerate(order):
            base = cs[n]
            end = cs[order[idx + 1]] if idx + 1 < len(order) else len(lines)
            L = chap_len("".join(lines[base:end]))
            if L < 2210 and n in FILL:
                todo.append((n, base, end, "fill"))
            elif L > 2990 and n in CUT:
                todo.append((n, base, end, "cut"))
        if not todo:
            continue

        newlines = list(lines)
        # 先算出所有操作，再统一应用（避免插入导致行号偏移）
        inserts = []   # (after_line_idx, text)
        deletes = set()
        for (n, base, end, kind) in todo:
            if kind == "fill":
                anchor = None
                for i in range(base, end - 1):
                    t = newlines[i].strip()
                    if t.startswith("（") and t.endswith("。）") and len(t) <= 20:
                        anchor = i
                if anchor is None:
                    continue
                inserts.append((anchor, FILL[n][0]))
            else:
                for i in range(base, min(end, len(newlines))):
                    if newlines[i].strip() in CUT[n]:
                        deletes.add(i)
        # 从后往前插，保证前面的行号不变
        for (ai, txt) in sorted(inserts, reverse=True):
            eol = "\r\n" if newlines[ai].endswith("\r\n") else ""
            newlines.insert(ai + 1, txt + eol)
        if deletes:
            newlines = [x for i, x in enumerate(newlines) if i not in deletes]

        out = "".join(newlines)
        if out != raw:
            open(p, "wb").write(out.encode("utf-8"))
            changed.append(f)

    print(f"已调整 {len(changed)} 个批次文件")
    for c in changed:
        print("  ", c)

    # 自检
    print("\n=== 微调后篇幅 ===")
    lens = []
    for f in sorted(os.listdir(BODY)):
        if not f.startswith("蜀山 卷三") or not f.endswith(".md"):
            continue
        raw = open(os.path.join(BODY, f), "rb").read().decode("utf-8")
        parts = CHAP_RE.split(raw)
        for i in range(1, len(parts) - 1, 3):
            n = int(parts[i])
            if 251 <= n <= 375:
                lens.append((n, chap_len(parts[i + 2])))
    under = [x for x in lens if x[1] < 2200]
    over = [x for x in lens if x[1] > 3000]
    print(f"<2200：{len(under)} 章 {under}")
    print(f">3000：{len(over)} 章 {over}")
    print(f"中位数 {sorted(x[1] for x in lens)[len(lens)//2]}")
    print(f"总计 {sum(x[1] for x in lens):,} 字")


if __name__ == "__main__":
    main()
