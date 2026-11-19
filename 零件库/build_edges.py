#!/usr/bin/env python3
"""生成零件库咬合索引（对称闭包）。

用法：python build_edges.py
输出：14-咬合索引.md

背景：卡内的「可咬合零件」是**单侧登记**——A 说能咬 B，B 未必写 A。
若不补全，从 B 检索会漏掉 A（实测双向互认仅 36%，49 条单向边）。
本脚本不改卡，只生成一份对称索引，并在每条边上标注「明写／反向」。
"""
import io
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["02-制度型零件.md", "03-机制型零件.md",
         "04-地理与资源型零件.md", "05-历史与接口型零件.md"]


def load():
    name, edges = {}, defaultdict(set)
    for f in FILES:
        p = os.path.join(HERE, f)
        s = io.open(p, encoding="utf-8").read()
        parts = re.split(r"^## `(WB-[A-Z]+-\d+)`[^\n]*$", s, flags=re.M)
        for i in range(1, len(parts) - 1, 2):
            pid, body = parts[i], parts[i + 1]
            m = re.search(r"\| 零件名 \| (.+?) \|", body)
            name[pid] = m.group(1).strip() if m else pid
            e = re.search(r"\| 可咬合零件 \| (.+?) \|", body)
            if e:
                for x in re.findall(r"WB-[A-Z]+-\d+", e.group(1)):
                    if x != pid and x in name or x != pid:
                        edges[pid].add(x)
    return name, edges


def main():
    name, edges = load()
    nodes = sorted(name)
    # 对称闭包
    sym = {n: set(edges.get(n, set())) for n in nodes}
    explicit = {(a, b) for a, bs in edges.items() for b in bs}
    for a, bs in list(edges.items()):
        for b in bs:
            if a not in sym.get(b, set()):
                sym[b].add(a)
    total_dir = sum(len(v) for v in edges.values())
    mutual = sum(1 for a, bs in edges.items() for b in bs if a in edges.get(b, set()))
    deg = sorted(((n, len(sym[n])) for n in nodes), key=lambda x: -x[1])

    out = ["# 14 · 咬合索引（脚本生成）", "",
           "> 本文件由 `build_edges.py` 从 02–05 的零件卡自动生成，**改卡后须重跑**。",
           "> 卡内「可咬合零件」是**单侧登记**；本索引给出**对称闭包**，"
           "标注每条边的来源：`明写`＝双方卡内都写了，`反向`＝仅一方写了、由索引补全。",
           "",
           f"> 统计：零件 {len(nodes)} 件｜有向边 {total_dir} 条｜"
           f"双向明写 {mutual} 条（{mutual / total_dir * 100:.0f}%）｜"
           f"索引后对称边 {sum(len(v) for v in sym.values()) // 2} 对",
           "",
           "---", "",
           "## 一、按咬合度数排序（哪些件最百搭）", "",
           "| 排名 | 零件 | 度数 | 说明 |", "|---|---|---|---|"]
    for i, (n, d) in enumerate(deg, 1):
        note = "元零件，可与任何件咬" if n == "WB-IFACE-0018" else ""
        out.append(f"| {i} | `{n}` {name[n]} | **{d}** | {note} |")

    out += ["", "---", "", "## 二、完整邻接表", "",
            "> 读法：`A` 行列出可与 A 咬合的件；括号内标 `明写`／`反向`。", ""]
    for n in nodes:
        if not sym[n]:
            out.append(f"- **`{n}` {name[n]}**：无")
            continue
        items = []
        for b in sorted(sym[n]):
            mark = "明写" if (n, b) in explicit else "反向"
            items.append(f"`{b}` {name.get(b, '')}（{mark}）")
        out.append(f"- **`{n}` {name[n]}**：{'、'.join(items)}")

    only_one = [(a, b) for a, bs in edges.items() for b in bs if a not in edges.get(b, set())]
    out += ["", "---", "", "## 三、单向边清单（需人工确认是否补写）", "",
            f"共 {len(only_one)} 条。这些边只在一方卡内出现，另一方未提；"
            "若确认关系成立，建议在另一方的「可咬合零件」里补上，使索引也标为`明写`。", "",
            "| # | 单侧登记方 | 被指向方 |", "|---|---|---|"]
    for i, (a, b) in enumerate(sorted(only_one), 1):
        out.append(f"| {i} | `{a}` {name.get(a, '')} | `{b}` {name.get(b, '')} |")

    p = os.path.join(HERE, "14-咬合索引.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(f"OK 已生成 {p}：{len(nodes)} 件、{len(only_one)} 条单向边")


if __name__ == "__main__":
    main()
