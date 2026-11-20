#!/usr/bin/env python3
"""生成零件库咬合索引（对称闭包）＋ 互斥索引（对称闭包）。

用法：python build_edges.py
输出：14-咬合索引.md

背景：卡内的「可咬合零件」是**单侧登记**——A 说能咬 B，B 未必写 A。
若不补全，从 B 检索会漏掉 A（实测双向互认仅 36%，49 条单向边）。
本脚本不改卡，只生成一份对称索引，并在每条边上标注「明写／反向」。

v2.2 增补：
- 解析「装配角色」：判定件与元件（`WB-IFACE-0018`／`WB-MECH-0005`）**不产生咬合边**，
  不计入度数——修「度数 0 却称可咬任何件」的矛盾。
- 解析「互斥零件」：生成对称闭包，与咬合索引分节列出，并标出
  **接口相容但装配互斥**的对（装配时重点检查）。
"""
import io
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["02-制度型零件.md", "03-机制型零件.md",
         "04-地理与资源型零件.md", "05-历史与接口型零件.md"]

META_ROLES = ("判定", "元")


def load():
    """返回 (name, edges, mutex_edges, roles)"""
    name, edges, mutex_edges, roles = {}, defaultdict(set), defaultdict(set), {}
    for f in FILES:
        p = os.path.join(HERE, f)
        s = io.open(p, encoding="utf-8").read()
        parts = re.split(r"^## `(WB-[A-Z]+-\d{4})`[^\n]*$", s, flags=re.M)
        for i in range(1, len(parts) - 1, 2):
            pid, body = parts[i], parts[i + 1]
            m = re.search(r"\| 零件名 \| (.+?) \|", body)
            name[pid] = m.group(1).strip() if m else pid
            # 装配角色
            r = re.search(r"\| 装配角色 \| \*\*(\S+?)\*\*", body)
            roles[pid] = r.group(1) if r else "参与"
            # 咬合边：判定件与元件不产生咬合边
            e = re.search(r"\| 可咬合零件 \| (.+?) \|", body)
            if e and roles[pid] not in META_ROLES:
                for x in re.findall(r"WB-[A-Z]+-\d{4}", e.group(1)):
                    if x != pid:
                        edges[pid].add(x)
            # 互斥边：单侧登记
            mx = re.search(r"\| 互斥零件 \| (.+?) \|", body)
            if mx:
                for x in re.findall(r"WB-[A-Z]+-\d{4}", mx.group(1)):
                    if x != pid:
                        mutex_edges[pid].add(x)
    return name, edges, mutex_edges, roles


def main():
    name, edges, mutex_edges, roles = load()
    nodes = sorted(name)
    # 咬合对称闭包
    sym = {n: set(edges.get(n, set())) for n in nodes}
    explicit = {(a, b) for a, bs in edges.items() for b in bs}
    for a, bs in list(edges.items()):
        for b in bs:
            if a not in sym.get(b, set()):
                sym[b].add(a)
    # 互斥对称闭包
    msym = {n: set(mutex_edges.get(n, set())) for n in nodes}
    mexplicit = {(a, b) for a, bs in mutex_edges.items() for b in bs}
    for a, bs in list(mutex_edges.items()):
        for b in bs:
            if a not in msym.get(b, set()):
                msym[b].add(a)

    total_dir = sum(len(v) for v in edges.values())
    mutual = sum(1 for a, bs in edges.items() for b in bs if a in edges.get(b, set()))
    deg = sorted(((n, len(sym[n])) for n in nodes), key=lambda x: -x[1])
    n_mutex_pairs = sum(len(v) for v in msym.values()) // 2
    n_meta = sum(1 for n in nodes if roles[n] in META_ROLES)

    out = ["# 14 · 咬合索引（脚本生成）", "",
           "> 本文件由 `build_edges.py` 从 02–05 的零件卡自动生成，**改卡后须重跑**。",
           "> 卡内「可咬合零件」是**单侧登记**；本索引给出**对称闭包**，"
           "标注每条边的来源：`明写`＝双方卡内都写了，`反向`＝仅一方写了、由索引补全。",
           "",
           f"> 统计：零件 {len(nodes)} 件（其中判定件／元件 {n_meta} 件，**不产生咬合边**）｜"
           f"有向边 {total_dir} 条｜双向明写 {mutual} 条（{mutual / total_dir * 100:.0f}%）｜"
           f"索引后对称边 {sum(len(v) for v in sym.values()) // 2} 对｜"
           f"互斥对称边 {n_mutex_pairs} 对",
           "",
           "---", "",
           "## 一、按咬合度数排序（哪些件最百搭）", "",
           "| 排名 | 零件 | 度数 | 装配角色 | 说明 |", "|---|---|---|---|---|"]
    for i, (n, d) in enumerate(deg, 1):
        r = roles[n]
        if r == "判定":
            note = "判定件：验收装配体，不产生咬合边、不进装配体成员清单"
        elif r == "元":
            note = "元件：写作期方法论工具，不产生咬合边"
        else:
            note = ""
        out.append(f"| {i} | `{n}` {name[n]} | **{d}** | {r} | {note} |")

    out += ["", "---", "", "## 二、完整邻接表（咬合）", "",
            "> 读法：`A` 行列出可与 A 咬合的件；括号内标 `明写`／`反向`。", ""]
    for n in nodes:
        if not sym[n]:
            out.append(f"- **`{n}` {name[n]}**（{roles[n]}）：无"
                       + ("——判定件／元件不产生咬合边" if roles[n] in META_ROLES else ""))
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

    # ---- 互斥索引（v2.2 新增）----
    out += ["", "---", "", "## 四、互斥索引（装配互斥 · 对称闭包）", "",
            "> 卡内「互斥零件」是**单侧登记**，本节给出**对称闭包**。",
            "> 互斥＝两件各自单看都成立，但**同场会互相拆台**（判据见 `00` §五 G.2）。",
            "> **接口相容 ≠ 装配相容**：同一对件可以既在咬合表也在互斥表。", ""]
    if n_mutex_pairs == 0:
        out.append("（当前无互斥边）")
    else:
        out += ["| # | 互斥对 | 登记 | 咬合表中有边？ |", "|---|---|---|---|"]
        k = 0
        seen_pair = set()
        for a in nodes:
            for b in sorted(msym[a]):
                if (b, a) in seen_pair:
                    continue
                seen_pair.add((a, b))
                k += 1
                in_bite = "是" if (b in sym[a] or a in sym[b]) else "否"
                rel = "明写" if ((a, b) in mexplicit or (b, a) in mexplicit) else "反向"
                flag = "⚠️ **接口相容但装配互斥**——装配时重点检查" if in_bite == "是" else ""
                out.append(f"| {k} | `{a}` {name.get(a, '')} ⊗ `{b}` {name.get(b, '')} | {rel} | {in_bite} {flag} |")
        out += ["", f"> 共 {n_mutex_pairs} 对。"
                "凡「咬合表中有边＝是」者，均属**接口相容但装配互斥**——"
                "这两件能接上接口，但不能同时站进一个装配体。"]

    p = os.path.join(HERE, "14-咬合索引.md")
    # 沿用目标文件既有行尾符：本机 core.autocrlf=true 检出为 CRLF，
    # 硬写 LF 会让每次重跑都产生全文件 diff（内容其实不变）。
    # 首次生成（文件不存在）时按平台默认换行。
    newline = None
    if os.path.exists(p):
        with io.open(p, "rb") as f:
            sample = f.read(4096)
        newline = "\r\n" if b"\r\n" in sample else "\n"
    io.open(p, "w", encoding="utf-8", newline=newline).write("\n".join(out) + "\n")
    print(f"OK 已生成 {p}：{len(nodes)} 件、{len(only_one)} 条单向边、"
          f"互斥 {n_mutex_pairs} 对（判定件/元件 {n_meta} 件不计入度数）")


if __name__ == "__main__":
    main()
