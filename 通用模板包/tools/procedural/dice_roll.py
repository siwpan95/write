#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dice_roll.py —— 可复现掷骰（v3.18，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.3 槽位三（目标驱动场景模拟）
          ＋ §五 SOP 第 3 步（固定种子可复现）

用途：为场景推演、节拍候选、批量巡检提供**可复现**的随机数来源。

为什么不用 peasy-ai 的 `easy_ai.trpg.tools.roll()`
----------------------------------------------
**实测结论**：它走**全局** `random` 模块 —— ① 自己不可复现（无 seed 参数）；
② **污染全局随机源**（调用它之后，同进程内其他脚本的随机序列被改变）。
本仓 `18` §五 第 3 步明写「每次生成记录：脚本、参数、种子、日期」——
不污染全局、seed 可复现是硬要求。

故本地实现：语义与 `roll()` 对齐（返回 `(总值, [各骰点], 修正项)`），
但用**局部** `random.Random(seed)` 实例 —— 与同包 `goal_sim.py` 的
「`random.Random(seed)` 局部实例」约定完全一致。

借鉴记账：peasy-ai 1.0.1 `easy_ai.trpg.tools.roll()` 的**骰值语法**
（`3d6+2` / `2d20-1` / `1d100`），登记于 通用模板包/14 §十一 D-19。

用法：
  python tools/procedural/dice_roll.py --expr "3d6+2" --seed 42
  python tools/procedural/dice_roll.py --expr "3d6+2" --seed 42 -n 5    # 掷 5 次
  python tools/procedural/dice_roll.py --demo

支持语法：<N>d<S>[+-<M>]   N=骰数 S=面数 M=固定修正（修正可负）
        多个表达式以逗号分隔：2d6+3,1d20
        也支持单骰：d20  ≡ 1d20

退出码：0 成功 ／ 1 表达式非法
"""
from __future__ import annotations

import argparse
import random
import re
import sys

# 骰值表达式：N d S (+/- M)
# 允许省略 N（d20 = 1d20）与省略修正（3d6）
EXPR_RE = re.compile(r"^(?:(\d*)d(\d+))([+-]\d+)?$")

# 单骰上限 —— 防止 999d1000000 之类把内存打爆
MAX_DICE = 1000
MAX_SIDES = 100000


def roll_one(expr: str, rng: random.Random) -> tuple[int, list[int], str]:
    """掷一个表达式，返回 (总值, [各骰点], 修正项字符串)。"""
    m = EXPR_RE.match(expr.strip())
    if not m:
        raise ValueError(f"骰值表达式非法：{expr!r}（应形如 3d6+2 / 2d20-1 / d20）")

    n = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    mod = m.group(3) or ""

    if n < 1 or n > MAX_DICE:
        raise ValueError(f"骰数越界：{n}（上限 {MAX_DICE}）")
    if sides < 2 or sides > MAX_SIDES:
        raise ValueError(f"面数越界：{sides}（上限 {MAX_SIDES}）")

    rolls = [rng.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + (int(mod) if mod else 0)
    return total, rolls, mod


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dice_roll.py",
        description="可复现掷骰（局部随机源，不污染全局）",
    )
    ap.add_argument("--expr", help="骰值表达式，如 3d6+2；多个用逗号分隔")
    ap.add_argument("--n", type=int, default=1, help="掷几次（默认 1）")
    ap.add_argument("--seed", type=int, default=1, help="随机种子（同种子同结果）")
    ap.add_argument("--demo", action="store_true", help="演示")
    args = ap.parse_args(argv)

    if args.demo:
        for expr in ("3d6+2", "2d20-1", "d100", "4d6,1d20"):
            rng = random.Random(42)
            total, rolls, mod = _roll_expr(expr, rng)
            print(f"{expr:14s} → 总值 {total:3d}  骰点 {rolls}  修正 {mod or '+0'}")
        print()
        print("可复现性自检（同 seed 两次应完全相同）：")
        a = [roll_one("3d6+2", random.Random(7))[0] for _ in range(3)]
        b = [roll_one("3d6+2", random.Random(7))[0] for _ in range(3)]
        print(f"  第一次 {a}  第二次 {b}  → {'一致 ✓' if a == b else '不一致 ✗'}")
        return 0

    if not args.expr:
        print("[FAIL] 需要 --expr（或用 --demo）", file=sys.stderr)
        return 1

    rng = random.Random(args.seed)
    try:
        for i in range(args.n):
            total, rolls, mod = _roll_expr(args.expr, rng)
            print(f"[{i + 1}] 总值 {total}  骰点 {rolls}  修正 {mod or '+0'}")
    except ValueError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1
    return 0


def _roll_expr(expr: str, rng: random.Random) -> tuple[int, list[int], str]:
    """掷一个（可能是逗号分隔的）表达式；多骰时总值取各骰之和。"""
    parts = [p.strip() for p in expr.split(",") if p.strip()]
    total = 0
    all_rolls: list[int] = []
    mod_text = ""
    for p in parts:
        t, r, m = roll_one(p, rng)
        total += t
        all_rolls.extend(r)
        if m:
            mod_text += m
    return total, all_rolls, mod_text


if __name__ == "__main__":
    sys.exit(main())
