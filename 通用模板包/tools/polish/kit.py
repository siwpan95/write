#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit.py —— 章节体检（比字数检查更细的一层）

它不判对错，只出体检单：哪里稀、哪里重复、哪里在注水。

用法：
    python3 tools/kit.py draft/ch126.md
    python3 tools/kit.py draft/            # 批量
    python3 tools/kit.py draft/ch126.md --top 12

体检项：
    1. 密度：汉字/段数、平均段长、短段（<8字）占比
    2. 重复：同一短句（>=6 字）出现 2 次及以上
    3. 注水：常见虚词与套话命中次数（缓缓、淡淡、仿佛、不禁……）
    4. 单调：段首词分布（"他"开头的比例）
    5. 节奏：长句（>=60 字，无句号）数量
    6. 对话：含引号段落占比
"""
import os
import re
import sys
import glob
import json

HERE = os.path.dirname(os.path.abspath(__file__))

WATER = [
    "缓缓", "淡淡", "轻轻", "微微", "静静", "慢慢", "渐渐",
    "仿佛", "似乎", "好像", "如同", "像是", "犹如",
    "某种", "一种", "一丝", "一抹", "一缕", "一点",
    "不禁", "不由", "忍不住", "不由得",
    "忽然", "突然", "猛地", "猛地",
    "心中一", "心里一", "心头一", "眼中一", "嘴角一",
    "说道", "心想", "暗想", "暗道",
    "十分", "非常", "极为", "格外", "异常",
    "气氛", "气息", "味道", "感觉",
]


def load_min():
    try:
        with open(os.path.join(os.path.dirname(HERE), "config.json"), encoding="utf-8") as f:
            return int(json.load(f).get("min_han", 3000))
    except Exception:
        return 3000


def segs(text):
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s:
            out.append(s)
    return out


def analyze(path, top=10):
    text = open(path, encoding="utf-8-sig").read()
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    ps = segs(text)
    lens = [len(re.findall(r"[\u4e00-\u9fa5]", p)) for p in ps]
    n = max(len(ps), 1)
    avg = sum(lens) / n
    short = sum(1 for x in lens if x < 8)
    longp = sum(1 for x in lens if x > 120)

    # 重复短句
    sents = re.findall(r"[^。！？\n]{6,40}[。！？]", text)
    sents = [s.strip() for s in sents]
    cnt = {}
    for s in sents:
        cnt[s] = cnt.get(s, 0) + 1
    dup = sorted([(s, c) for s, c in cnt.items() if c >= 2], key=lambda x: -x[1])[:top]

    # 注水词
    water = []
    for w in WATER:
        c = text.count(w)
        if c:
            water.append((w, c))
    water.sort(key=lambda x: -x[1])

    # 段首词
    head = {}
    for p in ps:
        h = p[:2]
        head[h] = head.get(h, 0) + 1
    head_top = sorted(head.items(), key=lambda x: -x[1])[:5]
    ta_ratio = round(head.get("他　", 0) / n, 3)

    # 长句
    longs = 0
    for p in ps:
        for chunk in re.split(r"[。！？]", p):
            if len(chunk) >= 60:
                longs += 1

    dialog = sum(1 for p in ps if "“" in p)

    return dict(
        file=os.path.basename(path), han=han, paras=len(ps), avg=round(avg, 1),
        short=short, short_ratio=round(short / n, 3),
        longp=longp, dup=dup, water=water[:top],
        head=head_top, longs=longs,
        dialog=dialog, dialog_ratio=round(dialog / n, 3),
    )


def advice(r, min_han):
    tips = []
    if r["han"] < min_han:
        tips.append("字数欠 %d：先补实内容（工序／账目／履历／规矩与例外），不要加形容词。" % (min_han - r["han"]))
    if r["avg"] > 45:
        tips.append("平均段长 %.1f 字偏长：切段，冷叙事靠短段推进。" % r["avg"])
    if r["short_ratio"] > 0.35:
        tips.append("短段占比 %.0f%% 偏高：有碎片化倾向，合并同类项。" % (r["short_ratio"] * 100))
    if r["dup"]:
        tips.append("有 %d 处短句重复，改掉或只留一处。" % len(r["dup"]))
    if r["water"] and r["water"][0][1] >= 5:
        tips.append("高频虚词：%s 等，删一半以上。" % "／".join(w for w, c in r["water"][:4]))
    if r["longs"] > 3:
        tips.append("长句（>=60 字）%d 句：拆。" % r["longs"])
    if r["dialog_ratio"] < 0.08:
        tips.append("对白占比过少（%.0f%%）：冷叙事也要靠人说短话立人物。" % (r["dialog_ratio"] * 100))
    return tips


def main():
    args = [a for a in sys.argv[1:]]
    top = 10
    if "--top" in args:
        i = args.index("--top")
        top = int(args[i + 1])
        del args[i:i + 2]
    files = []
    for a in args:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "ch*.md")))
        elif os.path.exists(a):
            files.append(a)
    if not files:
        print(__doc__)
        return 3
    min_han = load_min()
    for f in files:
        r = analyze(f, top)
        print("=" * 58)
        print("%s  汉字%d  段%d  平均段长%.1f  短段%.0f%%  对话框%d" % (
            r["file"], r["han"], r["paras"], r["avg"],
            r["short_ratio"] * 100, r["dialog"]))
        if r["dup"]:
            print("重复短句：")
            for s, c in r["dup"]:
                print("  x%d  %s" % (c, s[:40]))
        if r["water"]:
            print("高频词： " + "  ".join("%s%d" % (w, c) for w, c in r["water"]))
        print("段首高频： " + "  ".join("%s%d" % (h.replace("　", ""), c) for h, c in r["head"]))
        for t in advice(r, min_han):
            print("  · " + t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
