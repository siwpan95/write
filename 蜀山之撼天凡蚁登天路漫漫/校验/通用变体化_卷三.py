#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三文风收尾 · 通用变体化：把剩余高频句（≥20 次）统一压到 ≤12 次。

前面几轮已把「模板句」和「母题核心簇」处理完；
本轮处理**尾部**——那些仍停在 ×20–38 的次级高频句。

变体原则：**同一语义，换一种说法**，且新说法仍落在本书的
「短句／物证／算账」语汇里，不引入新语体。

⚠️ 换行安全：正文全 CRLF；二进制读写，只做行内替换。

用法：python3 校验/通用变体化_卷三.py [--apply] [--dry-run]
"""
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

VARIANTS = {
    "（他把手收回来。）": [
        "（他把手收回来。）", "（他把手抽回来。）", "（手收了。）",
        "（他把手放下，不碰。）", "（他缩回手。）", "（他把手背到身后。）",
    ],
    "（他往下翻了一页。）": [
        "（他往下翻了一页。）", "（他翻过一页。）", "（一页，往下。）",
        "（他把纸翻过去。）", "（他翻到下一页。）", "（他往下一页去。）",
    ],
    "（他绕开了半步。）": [
        "（他绕开了半步。）", "（他侧开半步。）", "（他让开半步。）",
        "（他退了半步。）", "（他错开半步。）", "（他挪开半步。）",
    ],
    "（他接着往下走。）": [
        "（他接着往下走。）", "（他往下走。）", "（他接着走。）",
        "（他继续往下。）", "（他往前走了一步。）", "（他往下，接着。）",
    ],
    "（它压在那儿，一动没动。）": [
        "（它压在那儿，一动没动。）", "（压着，没动。）", "（它没有动。）",
        "（它还在那儿压着。）", "（它压着，没挪。）", "（那儿的东西压着，没动。）",
    ],
    "（他把它留在原处。）": [
        "（他把它留在原处。）", "（他把它搁在原处。）", "（留在原处。）",
        "（他放下，没挪。）", "（他不动它。）", "（他让它留在那儿。）",
    ],
    "（他看的是它，不是旁边。）": [
        "（他看的是它，不是旁边。）", "（他看的是它。）", "（他没看旁边。）",
        "（他只看着它。）", "（旁边的不看。）", "（他眼里只有它。）",
    ],
    "（他把这件放下。）": [
        "（他把这件放下。）", "（这一件放下了。）", "（他放下这一件。）",
        "（放下。）", "（他松了手。）", "（这一件，他搁下了。）",
    ],
    "（他往前走了半步。）": [
        "（他往前走了半步。）", "（他往前走了半步，没停。）", "（他迈了半步。）",
        "（他往前一步。）", "（他往前挪了半步。）", "（半步，往前。）",
    ],
    "（他站在那上头，没有弯腰。）": [
        "（他站在那上头，没有弯腰。）", "（他站着，没弯腰。）", "（站着，没有弯腰。）",
        "（他站在那上头。）", "（他直着站。）", "（他没有弯腰。）",
    ],
    "（一周没有降下去的印。）": [
        "（一周没有降下去的印。）", "（那圈印，一周没降。）", "（印没有降。一周。）",
        "（一周了，印还在。）", "（印停在那里，一周。）", "（那圈印没有动过。）",
    ],
    "（碟里的油是平的。）": [
        "（碟里的油是平的。）", "（油面是平的。）", "（碟里的油面平。）",
        "（油没有皱。）", "（碟子上头，油是平的。）", "（那一层油，平着。）",
    ],
    "（灶上对数，一笔一笔对。）": [
        "（灶上对数，一笔一笔对。）", "（灶上一笔一笔对。）", "（一笔一笔，对着。）",
        "（在灶上对账。）", "（灶上那笔，对得上。）", "（他一笔一笔对过去。）",
    ],
    "（账和锅，对得上才算。）": [
        "（账和锅，对得上才算。）", "（账对得上锅，才算。）", "（锅和账要对得上。）",
        "（对得上，才算。）", "（账和锅，得对上。）", "（锅上那笔，要对得上账。）",
    ],
    "（这里的账，是纸。）": [
        "（这里的账，是纸。）", "（这账是纸。）", "（账是纸，不是锅。）",
        "（纸上的账。）", "（这一本账，是纸。）", "（账，在这里是纸。）",
    ],
    "（稀托不住笔尖。）": [
        "（稀托不住笔尖。）", "（墨稀，笔尖托不住。）", "（稀了，就托不住。）",
        "（笔尖压不住稀墨。）", "（太稀，托不住。）", "（稀墨撑不住笔尖。）",
    ],
    "（殿里五盏灯。四亮一暗。）": [
        "（殿里五盏灯。四亮一暗。）", "（五盏灯，四亮一暗。）", "（灯五盏。四亮，一暗。）",
        "（殿中五盏灯，四盏亮着。）", "（四亮，一暗，五盏。）", "（殿里的灯，五盏，四亮一暗。）",
    ],
}


def main():
    args = sys.argv[1:]
    files = [os.path.join(BODY, f) for f in sorted(os.listdir(BODY))
             if f.startswith("蜀山 卷三") and f.endswith(".md")]
    alltext = "".join(open(p, "rb").read().decode("utf-8") for p in files)

    present = {k: alltext.count(k) for k in VARIANTS if alltext.count(k)}
    print(f"待处理 {len(present)} 条高频句")
    for k, c in sorted(present.items(), key=lambda x: -x[1]):
        print(f"  ×{c:4}  {k}")

    seq = Counter()
    assign = defaultdict(list)
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
    print(f"\n待变体化 {total} 处")

    if "--dry-run" in args:
        pred = Counter()
        for k, vs in VARIANTS.items():
            n = alltext.count(k)
            if not n:
                continue
            for j, v in enumerate(vs):
                pred[v] += n // len(vs) + (1 if j < n % len(vs) else 0)
        print("\n=== 预估后 ≥20 次 ===")
        for v, c in pred.most_common():
            if c >= 20:
                print(f"  ×{c:4}  {v}")
        print(f"  预估单句最高：{max(pred.values())}")
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

    alltext2 = "".join(open(p, "rb").read().decode("utf-8") for p in files)
    sent = Counter()
    for s in re.findall(r"（[^（）]{6,40}）", alltext2):
        core = re.sub(r"[。，、？！：；“”\"'…—\s]", "", s)
        if len(core) >= 8:
            sent[s] += 1
    print("\n=== 变体后 ≥20 次的整句 ===")
    for s, c in sent.most_common():
        if c >= 20:
            print(f"  ×{c:4}  {s}")
    print(f"  单句最高：{sent.most_common(1)[0][1]}")
    buckets = {}
    for s, c in sent.items():
        k = "20+" if c >= 20 else ("10-19" if c >= 10 else ("4-9" if c >= 4 else "<4"))
        buckets[k] = buckets.get(k, 0) + 1
    print(f"  分布：{buckets}")


if __name__ == "__main__":
    main()
