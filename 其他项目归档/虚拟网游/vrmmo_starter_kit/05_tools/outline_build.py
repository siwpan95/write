#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
outline_build.py —— 章节节拍表（beat sheet）生成与体检工具

解决的问题
    大纲不是"故事梗概"，是"每章要交付给读者的东西"。这本书 100 万字 = 330 章，
    靠灵感写必然崩。所以把每章压缩成 5 个字段：
        章号 / 一句话事件 / 爽点类型 / 章末钩子 / 目标字数
    只要这 5 个字段填得出来，这章就能写；填不出来，说明这章是水。

用法
    python3 outline_build.py --config data/book_config.json
    python3 outline_build.py --config data/book_config.json --out-md ../03_outline/_auto_beat_sheet.md
    python3 outline_build.py --config data/book_config.json --check      # 只跑体检

体检规则（这些是踩过的坑，不是理论）
    R1 连续 3 章爽点类型完全相同 → 审美疲劳，标红
    R2 某章没有钩子 → 读者会在这里跳出，标红
    R3 单章目标字数偏离卷均值 40% 以上 → 节奏忽快忽慢，标黄
    R4 前 3 章必须都含 hook 且爽点类型不重复 → 黄金三章硬指标
"""

import argparse
import json
import statistics
import sys
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def render(cfg):
    book = cfg["book"]
    beats = cfg["beats"]
    L = []
    L.append(f'# 《{book["title"]}》章节节拍表（outline_build.py 生成）\n')
    L.append(f'- 一句话卖点：{book["logline"]}')
    L.append(f'- 目标平台：{book["platform"]}｜目标字数：{book["target_words"]} 万字｜日更：{book["daily_words"]} 字')
    L.append(f'- 核心机制：{book["core_mechanic"]}')
    L.append(f'- 卷目标：{book["volume_goal"]}\n')

    L.append("## 节拍表\n")
    L.append("| 章 | 一句话事件 | 爽点类型 | 章末钩子 | 目标字数 |")
    L.append("|---|---|---|---|---|")
    for b in beats:
        L.append(f'| {b["ch"]} | {b["event"]} | {b["pleasure"]} | {b["hook"]} | {b["words"]} |')
    L.append("")
    return "\n".join(L)


def check(cfg):
    beats = cfg["beats"]
    issues = []
    words = [b["words"] for b in beats if b.get("words")]
    avg = statistics.mean(words) if words else 0

    # R1 连续三章同爽点
    for i in range(len(beats) - 2):
        trio = beats[i:i + 3]
        if len({t["pleasure"] for t in trio}) == 1:
            issues.append(("红", f'第 {trio[0]["ch"]}–{trio[-1]["ch"]} 章爽点类型连续 3 章都是「{trio[0]["pleasure"]}」',
                           "换一种刺激：信息差 → 力量碾压 → 社交反转 轮着来"))

    # R2 无钩子
    for b in beats:
        if not str(b.get("hook", "")).strip() or b["hook"].strip() in ("—", "-", "无"):
            issues.append(("红", f'第 {b["ch"]} 章没有章末钩子', "补一个「未完成的期待」，不要补问句式的假悬念"))

    # R3 字数偏离
    for b in beats:
        if avg and b.get("words") and abs(b["words"] - avg) / avg > 0.4:
            issues.append(("黄", f'第 {b["ch"]} 章目标 {b["words"]} 字，偏离卷均值 {avg:.0f} 超 40%',
                           "节奏突变点要么集中在一章，要么均匀分布，别让读者忽快忽慢"))

    # R4 黄金三章
    first3 = beats[:3]
    if len(first3) == 3:
        if len({b["pleasure"] for b in first3}) < 3:
            issues.append(("红", "黄金三章爽点类型重复", "第一章给「反差」、第二章给「掌控」、第三章给「规模」"))
        for b in first3:
            if not str(b.get("hook", "")).strip():
                issues.append(("红", f'第 {b["ch"]} 章（黄金三章内）缺钩子', "黄金三章每章结尾都必须是问号，不是句号"))

    return issues, avg


def render_check(cfg, issues, avg):
    L = ["## 节拍表体检\n"]
    L.append(f"单章目标字数均值：**{avg:.0f}** 字｜共 **{len(cfg['beats'])}** 章\n")
    if not issues:
        L.append("✅ 全部通过。可以开写。\n")
        return "\n".join(L)

    red = [i for i in issues if i[0] == "红"]
    yellow = [i for i in issues if i[0] == "黄"]
    L.append(f"🔴 硬伤 {len(red)} 条｜🟡 建议 {len(yellow)} 条\n")
    L.append("| 级别 | 问题 | 怎么改 |")
    L.append("|---|---|---|")
    for lv, msg, fix in issues:
        L.append(f"| {'🔴' if lv == '红' else '🟡'} | {msg} | {fix} |")
    L.append("")
    if red:
        L.append("> 硬伤没清零之前别动笔——这三章写废了，后面全白搭。\n")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="章节节拍表生成与体检")
    ap.add_argument("--config", default="data/book_config.json")
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--check", action="store_true", help="只输出体检结果")
    args = ap.parse_args(argv)

    path = Path(args.config)
    if not path.is_absolute():
        path = (Path(__file__).parent / path).resolve()
    if not path.exists():
        print(f"[x] 找不到 {path}", file=sys.stderr)
        return 1

    cfg = load(path)
    issues, avg = check(cfg)

    md = render_check(cfg, issues, avg) if args.check else render(cfg) + "\n" + render_check(cfg, issues, avg)
    print(md)

    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print(f"\n[√] 已写入 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
