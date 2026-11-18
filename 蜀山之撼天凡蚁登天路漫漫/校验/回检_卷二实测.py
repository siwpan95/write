#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷二设定回检 · 实测扫描（照卷一回检报告的方法）。

方法：全量词频与章级定位扫描 + 关键设定条目逐条比对 + 章号冲突清单
用法：python3 校验/回检_卷二实测.py
"""
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

CHAP_RE = re.compile(r"^# 第 (\d+) 章 (.+)$", re.M)


def load_chapters():
    """返回 {章号: (标题, 正文, 文件名)}，只取正文目录下的 .md。"""
    out = {}
    for f in sorted(os.listdir(BODY)):
        if not f.endswith(".md"):
            continue
        if f.startswith("_") or f in ("进度表.md",) or f.startswith("回填台账"):
            continue
        p = os.path.join(BODY, f)
        t = open(p, encoding="utf-8").read()
        parts = CHAP_RE.split(t)
        for i in range(1, len(parts) - 1, 3):
            n = int(parts[i])
            if 126 <= n <= 250:
                out[n] = (parts[i + 1].strip(), parts[i + 2], f)
    return out


def main():
    ch = load_chapters()
    print("=" * 68)
    print(f"卷二正文实测 · 对象：第 126–250 章")
    print(f"章数 {len(ch)}；缺失 {[n for n in range(126,251) if n not in ch]}")
    total = 0
    for n in sorted(ch):
        pure = ch[n][1].replace("（本章完）", "")
        total += len(re.sub(r"\s", "", re.sub(r"^#.*$", "", pure, flags=re.M)))
    print(f"纯正文合计 {total:,} 字；平均每章 {total // max(len(ch),1):,} 字")

    # ---- 1.1 人物出场章数 ----
    people = ["白朴", "老周", "周崇", "于建", "齐灵云", "凌浑", "许飞娘", "老火工",
              "杨成志", "老弟子", "一号", "苏氏", "掌籍真人", "谱房", "掌籍房"]
    print("\n### 1.1 人物／称谓出场章数（126–250 共 %d 章）" % len(ch))
    rows = []
    for w in people:
        c = sum(1 for n in ch if w in ch[n][1])
        rows.append((c, w))
    for c, w in sorted(rows, reverse=True):
        print(f"  {w:10} {c:4}")

    # ---- 1.2 核心词频 ----
    print("\n### 1.2 核心词频（全书卷二）")
    words = ["册", "还", "算", "怕", "笔", "名字", "墨", "名分", "押", "价", "欠",
             "半截", "断口", "稀", "砚", "记名", "押名", "立约", "不可撤", "销牌",
             "元命牌", "待焚", "来历不明", "配", "虚字", "代笔", "代笔", "规", "还"]
    cnt = Counter()
    for n in ch:
        for w in words:
            cnt[w] += ch[n][1].count(w)
    for w in dict.fromkeys(words):
        print(f"  {w:10} {cnt[w]:5}")

    # ---- 1.3 能力线 / 机制链实测 ----
    print("\n### 1.3 关键机制链逐章落点")
    checks = {
        "墨渗·源头(虎口)": "虎口",
        "墨渗·绕着写": "绕",
        "墨渗·半截": "半截",
        "墨渗·稀/托不住": "托不住",
        "墨渗·新墨对照": "新墨",
        "墨渗·断口": "断口",
        "押名": "押名",
        "元命牌": "元命牌",
        "掌籍不得入谱": "不得入谱",
        "虚字": "虚字",
        "阙文·听见/回声": "回声",
        "分胙/胙": "胙",
        "罗浮仙": "罗浮仙",
        "配": "配",
        "待焚": "待焚",
        "来历不明": "来历不明",
    }
    for label, kw in checks.items():
        hits = sorted(n for n in ch if kw in ch[n][1])
        show = ", ".join(str(x) for x in hits[:14]) + (" …" if len(hits) > 14 else "")
        print(f"  {label:18} {len(hits):3} 章  {show}")

    # ---- 1.4 禁句限频（卷一第13条）----
    print("\n### 1.4 禁句限频（卷一回检 修订#6：每 5 章不超过 3 次）")
    banned = ["才是全部", "才成", "才是根", "稳，才成", "才是人"]
    for b in banned:
        hits = []
        for n in sorted(ch):
            c = ch[n][1].count(b)
            if c:
                hits.append((n, c))
        tot = sum(c for _, c in hits)
        over = [(n, c) for n, c in hits if c > 3]
        print(f"  「{b}」 合计 {tot} 次；单章 >3 的有 {len(over)} 章 {over[:6]}")
        worst = sorted(hits, key=lambda x: -x[1])[:5]
        if worst:
            print(f"      最高五章：{worst}")

    # ---- 1.5 结构性重复（跨章同句）----
    print("\n### 1.5 跨章高频整句（疑似凑字数的口头禅）")
    sent = Counter()
    for n in ch:
        for s in re.findall(r"（[^（）]{6,40}）", ch[n][1]):
            core = re.sub(r"[。，、？！：；“”\"'…—\s]", "", s)
            if len(core) >= 8:
                sent[s] += 1
    for s, c in sent.most_common(12):
        if c >= 4:
            print(f"  ×{c:3}  {s[:44]}")

    # ---- 四. 章号冲突：设定里的章号 vs 正文实际 ----
    print("\n### 四. 章号冲突核对（04 / 02E / 02B / 03C 里写的卷二章号 vs 正文）")
    targets = ["126", "136", "137", "140", "145", "150", "176", "188", "201", "206",
               "216", "226", "230", "231", "235", "236", "240", "241", "244", "245", "246", "250"]
    for t in targets:
        n = int(t)
        if n in ch:
            print(f"  第 {n:3} 章 = 「{ch[n][0]}」")
        else:
            print(f"  第 {n:3} 章 = 【卷二无此章】")

    # ---- 五. 红线抽查 ----
    print("\n### 五. 红线抽查（卷二正文内命中）")
    red = {
        "法宝类持物": ["法宝", "飞剑", "元命牌"],
        "境界链": ["筑基", "金丹", "元婴", "化神", "境界"],
        "朱文/宿命": ["宿命", "天注定", "命中注定"],
        "奇观堆砌词": ["壮观", "瑰丽", "奇观", "美不胜收", "叹为观止"],
        "洗白词": ["伟大的", "崇高", "圣洁"],
        "现代词": ["系统", "数据", "程序", "流程", "指标", "版本"],
    }
    for label, kws in red.items():
        hits = []
        for n in sorted(ch):
            for kw in kws:
                if kw in ch[n][1]:
                    hits.append((n, kw))
        # 元命牌是卷三载体，卷二应为 0
        print(f"  {label:12} 命中 {len(hits):3} 处 {hits[:6] if hits else ''}")

    # ---- 六. 篇幅分布 ----
    print("\n### 六. 篇幅分布（纯正文，卷二 125 章）")
    lens = []
    for n in sorted(ch):
        pure = ch[n][1].replace("（本章完）", "")
        lens.append((n, len(re.sub(r"\s", "", re.sub(r"^#.*$", "", pure, flags=re.M)))))
    under = [x for x in lens if x[1] < 2200]
    over = [x for x in lens if x[1] > 3000]
    print(f"  <2200：{len(under)} 章 {under[:8]}")
    print(f"  >3000：{len(over)} 章 {over[:8]}")
    print(f"  中位数 {sorted(x[1] for x in lens)[len(lens)//2]}")
    print("=" * 68)


if __name__ == "__main__":
    main()
