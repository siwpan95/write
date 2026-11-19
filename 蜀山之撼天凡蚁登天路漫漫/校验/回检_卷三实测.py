#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三设定回检 · 实测扫描（照卷一／卷二回检报告的方法）。

方法：全量词频与章级定位扫描 + 关键设定条目逐条比对 + 章号冲突清单
对象：卷三正文第 251–375 章
用法：python3 校验/回检_卷三实测.py
"""
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

CHAP_RE = re.compile(r"^# 第 (\d+) 章 (.+)$", re.M)


def load_chapters():
    """返回 {章号: (标题, 正文, 文件名)}，只取卷三区间的 .md。"""
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
            if 251 <= n <= 375:
                out[n] = (parts[i + 1].strip(), parts[i + 2], f)
    return out


def pure_len(text):
    pure = text.replace("（本章完）", "")
    return len(re.sub(r"\s", "", re.sub(r"^#.*$", "", pure, flags=re.M)))


def main():
    ch = load_chapters()
    print("=" * 72)
    print("卷三正文实测 · 对象：第 251–375 章")
    missing = [n for n in range(251, 376) if n not in ch]
    print(f"章数 {len(ch)}；缺号 {missing if missing else '无'}")
    total = sum(pure_len(ch[n][1]) for n in ch)
    print(f"纯正文合计 {total:,} 字；平均每章 {total // max(len(ch),1):,} 字")

    # ---- 1.1 人物出场章数 ----
    people = ["白朴", "老周", "周崇", "于建", "齐灵云", "凌浑", "许飞娘", "老火工",
              "杨成志", "老弟子", "一号", "崔五姑", "执事", "掌籍房", "谱房",
              "船夫", "阿但含婆"]
    print("\n### 1.1 人物／称谓出场章数（251–375 共 %d 章）" % len(ch))
    rows = [(sum(1 for n in ch if w in ch[n][1]), w) for w in people]
    for c, w in sorted(rows, reverse=True):
        print(f"  {w:10} {c:4}")

    # ---- 1.2 核心词频 ----
    print("\n### 1.2 核心词频")
    words = ["册", "还", "算", "怕", "笔", "名字", "墨", "名分", "押", "价", "欠",
             "半截", "断口", "稀", "砚", "记名", "押名", "立约", "不可撤", "销牌",
             "元命牌", "待焚", "来历不明", "配", "虚字", "代笔", "规", "赐", "抢",
             "无格", "格", "编号", "号", "拓", "灰", "火", "烧", "杨", "名"]
    cnt = Counter()
    for n in ch:
        for w in words:
            cnt[w] += ch[n][1].count(w)
    for w in dict.fromkeys(words):
        print(f"  {w:10} {cnt[w]:5}")

    # ---- 1.3 关键机制链逐章落点 ----
    print("\n### 1.3 关键机制链逐章落点")
    checks = {
        "押名": "押名",
        "立约": "立约",
        "不可撤": "不可撤",
        "元命牌": "元命牌",
        "销牌": "销牌",
        "备案": "备案",
        "待焚": "待焚",
        "来历不明": "来历不明",
        "无格者名册": "无格者名册",
        "无格": "无格",
        "有人批注": "批注",
        "齐灵云": "齐灵云",
        "我担": "我担",
        "许飞娘": "许飞娘",
        "于建": "于建",
        "白朴": "白朴",
        "虚字": "虚字",
        "回声(阙文退化)": "回声",
        "旧主名录": "旧主名录",
        "灯油/灯册": "灯",
        "体例": "体例",
        "拓": "拓",
        "十九世孙": "十九世孙",
        "格是给的": "格是给",
        "来历": "来历",
        "编号/一号": "一号",
        "押册人": "押册",
        "销毁场": "销毁",
    }
    for label, kw in checks.items():
        hits = sorted(n for n in ch if kw in ch[n][1])
        show = ", ".join(str(x) for x in hits[:14]) + (" …" if len(hits) > 14 else "")
        print(f"  {label:18} {len(hits):3} 章  {show}")

    # ---- 1.4 禁句限频（卷一回检 修订#6）----
    print("\n### 1.4 禁句限频（每 5 章不超过 3 次）")
    banned = ["才是全部", "才成", "才是根", "稳，才成", "才是人"]
    for b in banned:
        hits = [(n, ch[n][1].count(b)) for n in sorted(ch) if b in ch[n][1]]
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
    for s, c in sent.most_common(15):
        if c >= 4:
            print(f"  ×{c:3}  {s[:46]}")

    # ---- 1.5.1 模板句专项门禁（05 文风卡 13a）----
    print("\n### 1.5.1 模板句专项门禁（05 文风卡 13a · 模板句每章 ≤1 次）")
    TPL_FAMILY = ["（他把这一样记下。）", "（他把这几样记下。）",
                  "（他把这一样放着。）", "（他数自己的心跳。）"]
    over_ch = []
    tot_tpl = 0
    for n in sorted(ch):
        c = sum(ch[n][1].count(t) for t in TPL_FAMILY)
        tot_tpl += c
        if c > 1:
            over_ch.append((n, c))
    print(f"  模板句族合计 {tot_tpl} 处（卷三 125 章，上限 125）")
    print(f"  超限章（>1 次）：{len(over_ch)} 章 {over_ch[:10]}")
    print(f"  判定：{'达标' if not over_ch else '超限，需跑 校验/压模板句_卷三.py'}")

    # ---- 1.5.2 母题簇合并计量（方案 §3.3 规则 A）----
    print("\n### 1.5.2 母题簇合并计量（核心簇四切面须合计）")
    MOTIF_CLUSTER = ["三个字，十三个笔画。", "他念自己的名。",
                     "念到第二个字，那一竖是断的。", "断在嘴里也一样。"]
    cluster_total = 0
    per_ch = []
    for n in sorted(ch):
        c = sum(ch[n][1].count(t) for t in MOTIF_CLUSTER)
        cluster_total += c
        if c > 2:
            per_ch.append((n, c))
    print(f"  母题核心簇合计 {cluster_total} 处（卷三上限 55）")
    print(f"  单章 >2 次的章：{len(per_ch)} 章 {per_ch[:8]}")
    print(f"  判定：{'达标' if cluster_total <= 55 and not per_ch else '超限'}")

    # ---- 1.5.3 母题破点登记检查 ----
    print("\n### 1.5.3 母题破点（每卷 ≥1 处，方案 §4.4）")
    print("  注意：破点为**语义层**判定，机械脚本查不出——须人工核 348 章（拓出「杨」字）")

    # ---- 四. 章号冲突核对 ----
    print("\n### 四. 章号核对（03D 逐章 vs 正文实际）")
    targets = [251, 252, 255, 256, 260, 261, 263, 265, 266, 267, 268, 269, 270,
               275, 276, 278, 280, 281, 283, 284, 290, 295, 298, 300,
               301, 302, 305, 310, 311, 312, 315, 318, 319, 320, 321, 325,
               326, 328, 329, 330, 335, 340, 341, 345, 346, 348, 350,
               351, 355, 356, 360, 361, 365, 366, 370, 371, 374, 375]
    for n in targets:
        if n in ch:
            print(f"  第 {n:3} 章 = 「{ch[n][0]}」")
        else:
            print(f"  第 {n:3} 章 = 【卷三无此章】")

    # ---- 五. 红线抽查 ----
    print("\n### 五. 红线抽查（卷三正文内命中）")
    red = {
        "法宝类持物": ["法宝", "飞剑"],
        "境界链": ["筑基", "金丹", "元婴", "化神", "境界"],
        "朱文/宿命": ["宿命", "天注定", "命中注定"],
        "奇观堆砌词": ["壮观", "瑰丽", "奇观", "美不胜收", "叹为观止"],
        "洗白词": ["伟大的", "崇高", "圣洁"],
        "现代词": ["系统", "数据", "程序", "流程", "指标", "版本"],
        "破宫参与": ["破宫", "天一真水", "南明离火", "九疑鼎"],
    }
    for label, kws in red.items():
        hits = []
        for n in sorted(ch):
            for kw in kws:
                if kw in ch[n][1]:
                    hits.append((n, kw))
        print(f"  {label:12} 命中 {len(hits):3} 处 {hits[:8] if hits else ''}")

    # ---- 六. 篇幅分布 ----
    print("\n### 六. 篇幅分布（纯正文，卷三 %d 章）" % len(ch))
    lens = [(n, pure_len(ch[n][1])) for n in sorted(ch)]
    under = [x for x in lens if x[1] < 2200]
    over = [x for x in lens if x[1] > 3000]
    print(f"  <2200：{len(under)} 章 {under[:10]}")
    print(f"  >3000：{len(over)} 章 {over[:10]}")
    s = sorted(x[1] for x in lens)
    print(f"  中位数 {s[len(s)//2]}；最小 {s[0]}；最大 {s[-1]}")

    # ---- 七. 零引号 / 章末标记 ----
    print("\n### 七. 格式门禁")
    import glob
    for f in sorted(glob.glob(os.path.join(BODY, "蜀山 卷三 *.md"))):
        t = open(f, encoding="utf-8").read()
        parts = CHAP_RE.split(t)
        nums = [int(parts[i]) for i in range(1, len(parts) - 1, 3)]
        q = len(re.findall(r'[""]', t))
        end = len(re.findall(r"（本章完）", t))
        dup = []
        for i in range(1, len(parts) - 1, 3):
            body = parts[i + 2]
            lines = [x.strip() for x in body.split("\n") if x.strip()]
            seen = set()
            for x in lines:
                if len(x) > 12 and x in seen:
                    dup.append((int(parts[i]), x[:20]))
                    break
                seen.add(x)
        flag = "  ⚠️" if (q or end != len(nums) or dup) else "  ✓"
        print(f"{flag} {os.path.basename(f)[:44]:46} 章{len(nums)} 引号{q} 章末标记{end} 重复段{dup if dup else '无'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
