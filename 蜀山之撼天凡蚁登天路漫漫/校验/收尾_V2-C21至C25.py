#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷二 C21–C25 收尾：进度表补登 + 回填台账回填 + MANIFEST 重建。

用法（项目根）：
    python3 校验/收尾_V2-C21至C25.py

前置：五个循环的正文都已通过 校验/验收_V2-C21至C25.py。
本脚本只做三件事：① 进度表补登 5 行 ② 回填台账填 C21–C25 ③ 重建 MANIFEST。
"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    ("C21", "正文/蜀山 卷二 226–230｜C21 用一次.md", 226, "用一次"),
    ("C22", "正文/蜀山 卷二 231–235｜C22 往南.md", 231, "往南"),
    ("C23", "正文/蜀山 卷二 236–240｜C23 第二次门缝.md", 236, "第二次门缝"),
    ("C24", "正文/蜀山 卷二 241–245｜C24 别查.md", 241, "别查"),
    ("C25", "正文/蜀山 卷二 246–250｜C25 湿封皮.md", 246, "湿封皮"),
]

# 钩子摘要（据 03C 逐章细纲，写作时须落地）
HOOKS = {
    "C21": "227章「字是十九」／229章「袖口有两指宽」／230章「雪地上往南的脚印」",
    "C22": "231章「海里有一座宫」／232章「宫里的人早没了」／235章「他站了很久」",
    "C23": "237章「进来」／238章「他那一格还是空的」／240章「他把纸吃了」",
    "C24": "241章「纸的味道像灰」／242章「剩下一个人」／244章「他答不出」",
    "C25": "247章「名字在雪上写了十遍」／248章「旧册要送到掌籍房」／250章「封皮写着紫云宫，里面少一页」",
}
COSTS = {
    "C21": "226章 忘掉他母亲的脸／228章 想起旧册缺的那一页",
    "C22": "235章 默认老弟子替他背错；于建在崖上认不出他",
    "C23": "237章 白朴说「你又回来了」（与103章对照）／240章 把写着「别查」的纸吃了",
    "C24": "244章 他的姓开始被墨渗掉／245章 脸上没有变化",
    "C25": "246章 姓名的一部分／248章 紫云宫旧库出事，旧册要归档（不写宫破）／250章 记名（押册人）",
}


def chapter_stats(path):
    t = open(path, encoding="utf-8").read()
    idx = [m.start() for m in re.finditer(r"^# ", t, flags=re.M)] + [len(t)]
    out = []
    for i in range(len(idx) - 1):
        seg = t[idx[i]:idx[i + 1]]
        head = seg.split("\n")[0]
        n = len(re.sub(r"\s", "", seg))
        m = re.match(r"^# 第 (\d+) 章 (.+)$", head)
        if not m:
            continue  # 文件级标题（# 蜀山 卷二 …），跳过
        out.append((int(m.group(1)), m.group(2).strip(), n))
    return out


def main():
    total = 0
    rows = []
    for cn, rel, start, name in FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"[E] 缺文件：{rel}")
            return 1
        chs = chapter_stats(path)
        cyc = sum(c[2] for c in chs)  # chapter_stats 已跳过文件级标题
        total += cyc
        rows.append((cn, start, start + 4, name, cyc, chs))
        print(f"{cn}: {len(chs)} 章，{cyc} 字  " + " / ".join(f"{c[0]}:{c[2]}" for c in chs))

    # ① 进度表补登
    p = os.path.join(ROOT, "正文/进度表.md")
    s = open(p, encoding="utf-8").read()
    anchor = "| 20 | V2-C20 | 221–225 | C20 半块饼的味道 | ✅ | 12733 | 2026-11-17 |"
    if anchor in s:
        add = ""
        for i, (cn, a, b, name, cyc, chs) in enumerate(rows, start=21):
            add += f"\n| {i} | V2-{cn} | {a}–{b} | C{cn[1:]} {name} | ✅ | {cyc} | 2026-11-18 |"
        s = s.replace(anchor, anchor + add, 1)
        # 总览表同步
        s = s.replace(
            "| 卷二 青螺峪 | 25 | 125 | **正文 20/25 · 章纲 25/25** | 🟨 正文进行中 |",
            "| 卷二 青螺峪 | 25 | 125 | **正文 25/25 · 章纲 25/25** | ✅ **完成** |")
        s = s.replace(
            "| **合计** | **150** | **750** | **45 循环 + 2 章** | 🟨 卷二进行中 |",
            "| **合计** | **150** | **750** | **47 循环 + 2 章** | 🟨 卷二完成，卷三待写 |")
        s = s.replace(
            "> 缺口顺位：卷二剩 5 循环（226–250）→ 卷三 → 卷四 → 卷五 → 卷六 17 章。",
            "> **2026-11-18 补记**：卷二 C21–C25（226–250）已成稿，**卷二 25/25 全部完成**（126–250，125 章无缺号）。\n"
            "> 缺口顺位：**卷三 → 卷四 → 卷五 → 卷六 17 章**。")
        open(p, "w", encoding="utf-8").write(s)
        print("① 进度表已补登 5 行 + 总览同步")
    else:
        print("[E] 进度表锚点未命中")

    # ② 回填台账
    p2 = os.path.join(ROOT, "正文/回填台账-卷二.md")
    s2 = open(p2, encoding="utf-8").read()
    for cn, a, b, name, cyc, chs in rows:
        pat = re.compile(rf"^\| {cn} \| {a}–{b} \| {re.escape(name)} \| ⏳ 待填 \| ⏳ 待填 \|$", re.M)
        repl = f"| {cn} | {a}–{b} | {name} | {COSTS[cn]} | {HOOKS[cn]} |"
        s2 = pat.sub(repl, s2)
    s2 = s2.replace(
        "> C21–C25（226–250）待本批正文完成后回填。",
        "> C21–C25（226–250）已于 2026-11-18 成稿并回填（见 §二）。")
    open(p2, "w", encoding="utf-8").write(s2)
    print("② 回填台账 C21–C25 已回填")

    # ③ MANIFEST 重建
    files = []
    for root, _d, fs in os.walk(ROOT):
        for f in fs:
            p = os.path.relpath(os.path.join(root, f), ROOT).replace("\\", "/")
            if p.startswith("校验/"):
                continue
            if ".bak-" in p or p.startswith(".workbuddy-backup"):
                continue
            files.append(p)
    files.sort()
    lines = [f"{hashlib.sha256(open(os.path.join(ROOT, p), 'rb').read()).hexdigest()}  ./{p}" for p in files]
    open(os.path.join(ROOT, "校验/MANIFEST.sha256"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"③ MANIFEST 重建：{len(lines)} 条")

    print(f"\n本批正文合计 {total} 字（5 循环 25 章）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
