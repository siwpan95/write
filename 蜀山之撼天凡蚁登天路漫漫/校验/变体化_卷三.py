#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三文风收尾 · 第三轮：把高频整句「变体化」，压到 ≤25 次/句。

问题：前两轮把 1612 处模板句换成了新句式，但新句式又聚成 ×43–57 的簇。
这是调研报告 §2.3 预言的「禁具体句式是打地鼠」——**必须改判据，不改词表**。

本轮做法（对应方案 §6.2 手法 6「计数型母题 → 计数变奏」）：
对每个高频整句，按它在全书出现序号**轮换变体**，
使每一变体各自只占原句的 1/N，读者读到的是「同一句话的几种说法」，
而不是「第 N 次复读同一句」。

⚠️ 换行安全：正文全 CRLF；二进制读写，只做行内替换。

用法：python3 校验/变体化_卷三.py [--apply]
"""
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

# 每个高频句的变体（同一语义，不同说法）
VARIANTS = {
    "（他把这一样记下。）": [
        "（他把这一样记下。）",
        "（这一样，他记下了。）",
        "（他记下的是这一样。）",
        "（他把这一样记进账。）",
        "（他记得这一样。）",
        "（这一样，进账了。）",
    ],
    "（他把它挪到下一行。）": [
        "（他把它挪到下一行。）",
        "（他挪到下一行。）",
        "（下一行，他在上头写。）",
        "（他把它往下挪了一行。）",
        "（他往下一行写。）",
        "（他换了一行。）",
    ],
    "（他把这笔销了。）": [
        "（他把这笔销了。）",
        "（这一笔销了。）",
        "（他销掉这一笔。）",
        "（这笔，他划掉了。）",
        "（他把这笔划去。）",
        "（销一笔。）",
    ],
    "（他在账边补了一个数。）": [
        "（他在账边补了一个数。）",
        "（账边添了个数。）",
        "（他补了一个数在账边。）",
        "（他在旁边补个数。）",
        "（账边多了一个数。）",
        "（他添了一个数。）",
    ],
    "（这一栏添上了数。）": [
        "（这一栏添上了数。）",
        "（这一栏添了数。）",
        "（数添在这一栏。）",
        "（这一栏多了数。）",
        "（他往这一栏添数。）",
        "（这一栏，数添上了。）",
    ],
    "（他拿笔添了一笔。）": [
        "（他拿笔添了一笔。）",
        "（他添了一笔。）",
        "（一笔添上。）",
        "（他拿笔添上去。）",
        "（他添上一笔。）",
        "（笔添了一笔。）",
    ],
    "（他抄在纸角上。）": [
        "（他抄在纸角上。）",
        "（抄在纸角上。）",
        "（他写在纸角。）",
        "（纸角上抄着。）",
        "（他往纸角抄。）",
        "（抄到了纸角上。）",
    ],
    "（数写进账，没多写。）": [
        "（数写进账，没多写。）",
        "（数进了账，一个字没多。）",
        "（他写进账，没多写。）",
        "（账上写了数，没多。）",
        "（数写进账，不多写。）",
        "（进了账，没多。）",
    ],
    "（他把数记在下一行。）": [
        "（他把数记在下一行。）",
        "（数记在下一行。）",
        "（他往下一行记数。）",
        "（下一行记着数。）",
        "（他把数写在下一行。）",
        "（数落到下一行。）",
    ],
    "（他把这一件放下。）": [
        "（他把这一件放下。）",
        "（这一件他放下了。）",
        "（他放下这一件。）",
        "（放下。）",
        "（他把手里的放下。）",
        "（这一件放下了。）",
    ],
    "（它压在那儿，没动。）": [
        "（它压在那儿，没动。）",
        "（压在那儿，一动没动。）",
        "（它没有动。）",
        "（它还在那儿压着。）",
        "（压着，没有动。）",
        "（它压着，没挪。）",
    ],
    "（他站在那上头，没弯腰。）": [
        "（他站在那上头，没弯腰。）",
        "（他站着，没弯腰。）",
        "（站着，没有弯腰。）",
        "（他站在那上头。）",
        "（他没有弯腰。）",
        "（他直着站。）",
    ],
    "（他闭了一下眼。）": [
        "（他闭了一下眼。）",
        "（他闭了眼。）",
        "（眼闭了一下。）",
        "（他闭了一下眼睛，又睁开。）",
        "（他闭眼，又睁开。）",
        "（他眨了一下眼。）",
    ],
}


def main():
    args = sys.argv[1:]
    files = []
    for f in sorted(os.listdir(BODY)):
        if f.startswith("蜀山 卷三") and f.endswith(".md"):
            files.append(os.path.join(BODY, f))

    # 统计每个目标句在全书出现次数
    alltext = "".join(open(p, "rb").read().decode("utf-8") for p in files)
    targets = {k: alltext.count(k) for k in VARIANTS if alltext.count(k)}

    # 按文件、按行序，为每个出现分配变体（全局轮转）
    seq = Counter()
    assign = defaultdict(list)   # path -> [(line_idx, old, new)]
    for p in files:
        raw = open(p, "rb").read().decode("utf-8")
        lines = re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", raw)
        for i, L in enumerate(lines):
            t = L.strip()
            if t not in VARIANTS:
                continue
            vs = VARIANTS[t]
            k = seq[t]
            seq[t] += 1
            new = vs[k % len(vs)]
            if new != t:
                assign[p].append((i, t, new))

    total = sum(len(v) for v in assign.values())
    print(f"待变体化 {total} 处")
    for k, c in sorted(targets.items(), key=lambda x: -x[1]):
        print(f"  ×{c:4} → 分 {len(VARIANTS[k])} 变体  {k}")

    if "--dry-run" in args:
        print("\n(--dry-run)")
        return

    changed = 0
    for p, items in assign.items():
        raw = open(p, "rb").read().decode("utf-8")
        lines = re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", raw)
        for (i, old, new) in items:
            if i >= len(lines) or lines[i].strip() != old:
                continue
            m = re.match(r"^([^\r\n]*)(\r?\n?)$", lines[i])
            content, eol = m.group(1), m.group(2)
            lead = content[:len(content) - len(content.lstrip())]
            lines[i] = lead + new + eol
        open(p, "wb").write("".join(lines).encode("utf-8"))
        changed += 1
    print(f"\n已改写 {changed} 个批次文件")

    # 自检
    alltext2 = "".join(open(p, "rb").read().decode("utf-8") for p in files)
    sent = Counter()
    for s in re.findall(r"（[^（）]{6,40}）", alltext2):
        core = re.sub(r"[。，、？！：；“”\"'…—\s]", "", s)
        if len(core) >= 8:
            sent[s] += 1
    print("\n=== 变体化后 ≥40 次的整句 ===")
    for s, c in sent.most_common():
        if c >= 40:
            print(f"  ×{c:4}  {s}")
    print(f"\n≥4 次的整句总数: {sum(1 for s, c in sent.items() if c >= 4)}")


if __name__ == "__main__":
    main()
