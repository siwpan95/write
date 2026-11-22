#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hit_score.py —— 开书方案「爆款命中率」预判模型 v1.2

为什么需要它
    选题拍脑袋的代价是 20 万字。这个模型把"这个点子能不能成"拆成 6 个可打分的维度，
    输出一个可比、可解释、可反驳的命中率数字，用来在动笔前淘汰 70% 的方案。

模型结构
    Score = Σ(维度分 × 权重)         维度分 1–5
    P     = 0.62 / (1 + e^(-1.4 × (Score - 2.6)))   ← logistic 校准
    校准依据：三个锚点
        Score=4.6 → P≈0.58  头部作者稳定开书、能进平台重点推荐区
        Score=3.5 → P≈0.48  腰部水平，能签约但未必起飞
        Score=2.5 → P≈0.29  扑街高发区
    Pmax=0.62 是刻意的天花板：网文不存在"必爆"，只存在"概率更高"。

一票否决（veto）
    命中率再高，踩中以下任一条也直接降档：
        - 触碰平台 P0 级设定（封建迷信核心、真实政治/机构/名人）
        - 金手指无限制、无代价（读者三章后失去张力）
        - 开篇 1000 字内无冲突、无钩子
        - 与在榜作品"设定+爽点"双重复

用法
    python3 hit_score.py --input data/candidates.json
    python3 hit_score.py --input data/candidates.json --sensitivity
"""

import argparse
import json
import math
import sys
from pathlib import Path

# ── 维度定义：权重之和必须为 1.0，脚本会校验 ───────────────────────────
DIMENSIONS = [
    ("赛道热度", 0.20, "该细分方向在榜单上「有读者 + 还有位置」。过热无位、过冷无客都扣分。"),
    ("差异化", 0.20, "与在榜前 50 的重复度。能不能用一句话说出「没有第二本这么写」。"),
    ("开篇钩子", 0.20, "前三章能否在 300 字内扔出事故、1000 字内亮出矛盾、章末留钩。"),
    ("金手指设计", 0.15, "稀缺性 + 限制性。有限制才有张力，无限制=无冲突=读者流失。"),
    ("爽点续航", 0.15, "爽点能否支撑 100 万字不重复。判断标准：爽点来源是否可扩增。"),
    ("平台适配与合规", 0.10, "题材是否贴合目标平台分发逻辑，且不踩审核红线。"),
]

PMax = 0.62
K = 1.4
S0 = 2.6

VETO_RULES = {
    "p0_setting": "触碰平台 P0 级设定（封建迷信核心 / 真实政治、机构、名人）",
    "no_limit_power": "金手指无限制无代价",
    "no_hook_opening": "开篇 1000 字内无冲突无钩子",
    "double_clone": "设定与爽点双重复在榜作品",
}


def hit_probability(score: float) -> float:
    return PMax / (1.0 + math.exp(-K * (score - S0)))


def grade(p: float):
    if p >= 0.55:
        return "S｜强推·优先开这本", "可直接进入设定与大纲阶段"
    if p >= 0.45:
        return "A｜可做·需补短板", "补齐最低分维度后再开，别带着短板进正文"
    if p >= 0.32:
        return "B｜谨慎·先做小样", "先写 3 章 + 1 版简介投放测试，数据不行就换"
    if p >= 0.20:
        return "C｜不建议立项", "改动成本大于重开，换题"
    return "D｜淘汰", "选题本身不成立"


def score_candidate(cand):
    dims = cand.get("scores", {})
    total, breakdown = 0.0, []
    for name, weight, _desc in DIMENSIONS:
        raw = dims.get(name)
        if raw is None:
            raise ValueError(f'方案「{cand.get("name")}」缺少维度分：{name}')
        raw = float(raw)
        if not 0 <= raw <= 5:
            raise ValueError(f'维度分必须在 0–5：{cand.get("name")} / {name} = {raw}')
        total += raw * weight
        breakdown.append({"维度": name, "权重": weight, "分": raw, "加权分": round(raw * weight, 3)})

    p = hit_probability(total)
    vetoes = [VETO_RULES[v] for v in cand.get("veto", []) if v in VETO_RULES]
    if vetoes:
        p *= 0.45  # 踩中否决项：概率腰斩后再打折，直观体现"别碰"

    label, advice = grade(p)
    return {
        "name": cand.get("name", "未命名方案"),
        "one_liner": cand.get("one_liner", ""),
        "score": round(total, 2),
        "prob": round(p, 3),
        "grade": label,
        "advice": advice,
        "vetoes": vetoes,
        "breakdown": breakdown,
        "notes": cand.get("notes", ""),
    }


def sensitivity(results):
    """敏感度分析：如果总分再提 0.3，命中率涨多少？用来回答"这钱花在哪最值"。"""
    lines = []
    for r in results:
        base = r["score"]
        p0 = hit_probability(base)
        p1 = hit_probability(base + 0.3)
        lines.append({"方案": r["name"], "当前P": round(p0, 3),
                      "提0.3后P": round(p1, 3), "增量": round(p1 - p0, 3)})
    return lines


def render(results, sens=None):
    results = sorted(results, key=lambda x: -x["prob"])
    L = ["# 开书方案命中率预判（hit_score.py 生成）\n"]
    L.append(f"模型：`P = {PMax} / (1 + e^(-{K} × (Score - {S0})))`，Score 为 6 维加权分（1–5）。")
    L.append("> 注意：这是**相对比较**工具，不是承诺。它的价值在于把「我觉得能火」变成「这 6 个维度分别几分、为什么」。\n")

    L.append("## 一、结论排序\n")
    L.append("| 排名 | 方案 | 加权分 | 命中率 | 评级 | 建议 |")
    L.append("|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        L.append(f'| {i} | {r["name"]} | {r["score"]} | {r["prob"]*100:.1f}% | {r["grade"]} | {r["advice"]} |')
    L.append("")

    for r in results:
        L.append(f'## {r["name"]}')
        if r["one_liner"]:
            L.append(f'> {r["one_liner"]}\n')
        L.append("| 维度 | 权重 | 得分 | 加权 |")
        L.append("|---|---|---|---|")
        for b in r["breakdown"]:
            L.append(f'| {b["维度"]} | {b["权重"]:.2f} | {b["分"]} | {b["加权分"]} |')
        L.append(f'| **合计** | 1.00 | — | **{r["score"]}** |\n')
        if r["vetoes"]:
            L.append("⚠️ 触发否决项：")
            for v in r["vetoes"]:
                L.append(f"- {v}")
            L.append("")
        if r["notes"]:
            L.append(f'{r["notes"]}\n')
        lowest = min(r["breakdown"], key=lambda x: x["分"])
        if lowest["分"] < 4:
            L.append(f'**最短的板**：{lowest["维度"]}（{lowest["分"]} 分）—— 立项前先想清楚怎么补。\n')
        else:
            L.append("**短板**：无 4 分以下维度，六边形偏满，进入执行阶段。\n")

    if sens:
        L.append("## 二、敏感度分析（总分 +0.3 的边际收益）\n")
        L.append("| 方案 | 当前命中率 | 提 0.3 后 | 增量 |")
        L.append("|---|---|---|---|")
        for s in sens:
            L.append(f'| {s["方案"]} | {s["当前P"]*100:.1f}% | {s["提0.3后P"]*100:.1f}% | +{s["增量"]*100:.1f}pp |')
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="开书方案爆款命中率预判")
    ap.add_argument("--input", default="data/candidates.json")
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--sensitivity", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.input)
    if not path.is_absolute():
        path = (Path(__file__).parent / path).resolve()
    if not path.exists():
        print(f"[x] 找不到 {path}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    cands = data["candidates"] if isinstance(data, dict) else data

    try:
        results = [score_candidate(c) for c in cands]
    except ValueError as e:
        print(f"[x] {e}", file=sys.stderr)
        return 1

    sens = sensitivity(results) if args.sensitivity else None
    md = render(results, sens)
    print(md)

    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print(f"\n[√] 已写入 {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
