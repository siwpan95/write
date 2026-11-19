#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三母题簇变体化：把 382 处核心母题降到 ≤55（方案 §4.1 M-1 阈值）。

**与模板句治理的区别**：
- 模板句改写是**换掉**（每次出现零增量 → 压）；
- 母题改写是**换切面**（保留母题，但每次换一个说法／换一个对照）。

按方案 §3.3 规则 A，核心簇的四条切面必须**合并计量**：
  #5 三个字，十三个笔画。（发现）
  #6 他念自己的名。（念）
  #7 念到第二个字，那一竖是断的。（显形）
  #8 断在嘴里也一样。（转移）

变体设计原则：**同一母题的四种说法，各自携带一点新的对照**，
例如「三个字，十三个笔画。」→「三个字，十二笔。」→「三个字，十三个，第二笔短一截。」
——**数变了＝多了一层**，符合方案 §6.2 手法 6「计数变奏」。

⚠️ 换行安全：正文全 CRLF；二进制读写，只做行内替换。

用法：python3 校验/母题变体化_卷三.py [--apply] [--dry-run]
"""
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

# 四条切面的变体池（每条 ≥8 个变体，轮换后单变体频次 ≈ 1/8）
VARIANTS = {
    # #5 发现：三个字，十三个笔画。
    "（三个字，十三个笔画。）": [
        "（三个字，十三个笔画。）",
        "（三个字，十三个。第二笔短一截。）",
        "（三个字，十三个。多一横，少一竖。）",
        "（三个字，十三个笔画。他数到第二遍。）",
        "（三个字，十三个。笔画不匀。）",
        "（三个字，十三个。头一个字最宽。）",
        "（三个字，十三个。尾一个字最短。）",
        "（三个字，十三个。中间那个少一横。）",
        "（三个字，十三个。合起来是十三个。）",
    ],
    # #6 念：他念自己的名。
    "（他念自己的名。）": [
        "（他念自己的名。）",
        "（他把自己的名念了一遍。）",
        "（他念他的名。出声。）",
        "（他念了一遍名，很轻。）",
        "（他念自己的名，念得很慢。）",
        "（他念那个名，一字一字。）",
        "（他念自己的名，没有出声。）",
        "（他念自己的名，停在第二个字上。）",
        "（他念自己的名，像在点人。）",
    ],
    # #7 显形：念到第二个字，那一竖是断的。
    "（念到第二个字，那一竖是断的。）": [
        "（念到第二个字，那一竖是断的。）",
        "（念到第二个字，那一竖又短了。）",
        "（念到第二个字，断的还是那一竖。）",
        "（念到第二个字，那一竖只剩半截。）",
        "（念到第二个字，那一竖还是不全。）",
        "（念到第二个字，那一竖虚着。）",
        "（念到第二个字，那一竖缺了一截。）",
        "（念到第二个字，那一竖仍旧断着。）",
        "（念到第二个字，那一竖落在半空。）",
    ],
    # #8 转移：断在嘴里也一样。
    "（断在嘴里也一样。）": [
        "（断在嘴里也一样。）",
        "（嘴里断的，跟笔下一样。）",
        "（念出来，那一竖也是断的。）",
        "（嘴上念的，也缺一截。）",
        "（嘴里那一竖，也是半截。）",
        "（念的是断的，写的也是断的。）",
        "（嘴里断的是同一个地方。）",
        "（出声念，缺的还是那一竖。）",
        "（嘴里那一竖，跟纸上一样短。）",
    ],
}


def main():
    args = sys.argv[1:]
    files = [os.path.join(BODY, f) for f in sorted(os.listdir(BODY))
             if f.startswith("蜀山 卷三") and f.endswith(".md")]

    alltext = "".join(open(p, "rb").read().decode("utf-8") for p in files)
    print("=== 治理前 母题核心簇 ===")
    tot = 0
    for k, vs in VARIANTS.items():
        c = alltext.count(k)
        tot += c
        print(f"  ×{c:4}  {k}")
    print(f"  合计 {tot}（目标 ≤55）")

    # 轮转分配：全局按出现序号轮换，保证每个变体均摊
    seq = Counter()
    assign = defaultdict(list)
    for p in files:
        raw = open(p, "rb").read().decode("utf-8")
        lines = re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", raw)
        # ── 关键：母题以「四句连作」的固定序列出现（念→名→显形→转移）──
        # 变体必须**整组一起换**，否则序列会读不通。
        # 「他念自己的名。」是每组的开头，用它来切分组。
        gid = 0
        for i, L in enumerate(lines):
            t = L.strip()
            if t not in VARIANTS:
                continue
            if t == "（他念自己的名。）":
                gid += 1
            k = (gid - 1) % 8
            vs = VARIANTS[t]
            new = vs[k % len(vs)]
            if new != t:
                assign[p].append((i, t, new))
        seq["groups"] = gid

    total = sum(len(v) for v in assign.values())
    print(f"\n待变体化 {total} 处")

    if "--dry-run" in args:
        # 预估结果
        pred = Counter()
        for k, vs in VARIANTS.items():
            n = alltext.count(k)
            for j, v in enumerate(vs):
                pred[v] += n // len(vs) + (1 if j < n % len(vs) else 0)
        print("\n=== 预估变体后 ===")
        for v, c in pred.most_common(8):
            print(f"  ×{c:4}  {v}")
        print(f"  单句最高频次：{max(pred.values())}")
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
    print("\n=== 变体后 母题核心簇 ===")
    tot2 = 0
    for k, vs in VARIANTS.items():
        c = sum(alltext2.count(v) for v in vs)
        tot2 += c
        mx = max(alltext2.count(v) for v in vs)
        print(f"  簇合计 {c:4}｜单变体最高 ×{mx:3}  {k}")
    print(f"  总计 {tot2}")
    sent = Counter()
    for s in re.findall(r"（[^（）]{6,40}）", alltext2):
        core = re.sub(r"[。，、？！：；“”\"'…—\s]", "", s)
        if len(core) >= 8:
            sent[s] += 1
    print("\n=== 变体后 ≥40 次的整句 ===")
    for s, c in sent.most_common():
        if c >= 40:
            print(f"  ×{c:4}  {s}")


if __name__ == "__main__":
    main()
