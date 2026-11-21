#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
npc_card.py —— NPC 人物卡四要素批量生成（v3.18，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.1（槽位一 · 命名工厂的**姊妹槽位**）
用途：批量生成 NPC 的「特质 / 职业 / 情绪 / 秘密」四要素底稿，供 04 人物卡
      的**龙套与次要角色**批量填充。

与 name_generator.py 的分工（**不重叠，不抢字段**）
------------------------------------------------
| 字段 | 由谁出 | 理由 |
|---|---|---|
| 姓名 | `name_generator.py` | 已有字素文法 + 全局去重 + `--profile` 双词库 + 槽位拆解，**已过 18 §3.1 验收门** |
| 特质/职业/情绪/秘密 | 本脚本 | 四要素是**语义字段**，字素文法生成不了，需要人工维护的词库 |

为什么要单列一个脚本，而不是并进 name_generator
----------------------------------------------
`name_generator` 走的是**第 2 代（递归文法）**；四要素走的是**词库抽样**。
两者的生成机制、验收门、去重口径都不同，混在一个脚本里会让验收门无法分别判定。
且四要素词库要按题材维护（仙侠/都市/民俗/科幻），与字素库的 profile 维度**不是一回事**。

关于 peasy-ai 的 `random_npc()`（借鉴记账）
------------------------------------------
结构（五要素：name/trait/occupation/mood/secret）**借鉴** peasy-ai 1.0.1 的
`easy_ai.trpg.tools.random_npc()`，登记于 通用模板包/14 §十一 D-19。
**但不直接调用它**，原因有二（均为本机实测）：
  1. 它的词库是**西方奇幻向**（艾琳·铁锤 / 酒馆老板 / 炼金术士），
     与本仓中文题材（仙侠/都市/民俗/科幻）不匹配；
  2. 它**无 seed 参数**（走全局 random），不满足 18 §五 第 3 步「固定种子可复现」。
故此处取其**结构**，换成本仓词库，并自行实现可复现采样。

用法：
  python tools/procedural/npc_card.py --theme xianxia --n 10 --seed 42
  python tools/procedural/npc_card.py --theme urban --n 5 --seed 7
  python tools/procedural/npc_card.py --demo            # 各题材各出 2 个演示
  python tools/procedural/npc_card.py --theme myth --n 3 --seed 1 --with-names
                                                             # 顺带用 name_generator 出名

输出：JSON Lines（每行一张人物卡底稿），便于下游脚本消费。

**纪律**（18 §五 SOP 第 5 步）：产物只进素材层，逐条人工过审后方可编号入库；
主角与核心配角**禁止**程序化生成生平。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEXICON_PATH = HERE / "npc_lexicon.json"

# 字段顺序固定 —— 输出可 diff、可复现
FIELDS = ["trait", "occupation", "mood", "secret"]


def load_lexicon() -> dict:
    """载入四要素词库。显式 UTF-8（Windows 默认编码不是 UTF-8）。"""
    if not LEXICON_PATH.exists():
        raise SystemExit(f"[FAIL] 词库不存在：{LEXICON_PATH}")
    try:
        data = json.load(io.open(LEXICON_PATH, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[FAIL] 词库不是合法 JSON：{LEXICON_PATH}（{exc}）")
    # 去掉以 _ 开头的说明键（_说明 / _口径 / _纪律 / _label）
    return {k: v for k, v in data.items() if not k.startswith("_")}


def available_themes(lex: dict) -> list[str]:
    return sorted(lex.keys())


def generate(theme: str, n: int, seed: int, lex: dict) -> list[dict]:
    """生成 n 张四要素卡。同 seed 同结果（可复现）。"""
    if theme not in lex:
        raise SystemExit(f"[FAIL] 未知题材 {theme!r}（可选：{', '.join(available_themes(lex))}）")
    rng = random.Random(seed)
    tables = lex[theme]
    cards: list[dict] = []
    for _ in range(n):
        card = {f: rng.choice(tables[f]) for f in FIELDS}
        cards.append(card)
    return cards


def attach_names(cards: list[dict], profile: str, seed: int) -> list[dict]:
    """用 name_generator 补姓名（**名字的单一来源**是 name_generator）。

    名字与四要素**分属两套生成机制**，故种子错开（seed 与 seed+1），
    避免二者相关导致「同 seed 换名字不改特质」这类隐性耦合。

    name_generator.generate 返回 `[(名字, 构造说明)]` —— 构造说明是
    **槽位拆解**（姓/名头/名尾），供人工过审时定向改字，故一并保留。
    """
    try:
        sys.path.insert(0, str(HERE))
        from name_generator import generate as name_generate
    except ImportError as exc:
        raise SystemExit(f"[FAIL] 无法导入 name_generator.py（{exc}）")
    pairs = name_generate("person", len(cards), seed + 1, profile)
    for card, item in zip(cards, pairs):
        if isinstance(item, (tuple, list)) and len(item) >= 1:
            card["name"] = item[0]
            if len(item) >= 2:
                card["name_breakdown"] = item[1]
        else:
            card["name"] = item if isinstance(item, str) else str(item)
    return cards


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="npc_card.py",
        description="NPC 人物卡四要素批量生成（素材层，产物须人工过审）",
    )
    ap.add_argument("--theme", help=f"题材：{', '.join(available_themes(load_lexicon()))}")
    ap.add_argument("--n", type=int, default=10, help="生成数量（默认 10）")
    ap.add_argument("--seed", type=int, default=42, help="随机种子（同种子同结果）")
    ap.add_argument("--with-names", action="store_true",
                    help="顺带用 name_generator 补姓名（名字的单一来源是 name_generator）")
    ap.add_argument("--name-profile", default="xuanhuan",
                    help="name_generator 的词库 profile（xuanhuan / reality）")
    ap.add_argument("--demo", action="store_true", help="各题材各出 2 个演示")
    args = ap.parse_args(argv)

    lex = load_lexicon()

    if args.demo:
        for theme in available_themes(lex):
            print(f"# ── {theme}（{lex[theme].get('_label', theme)}）──")
            for card in generate(theme, 2, 42, lex):
                print(json.dumps(card, ensure_ascii=False))
            print()
        return 0

    if not args.theme:
        print("[FAIL] 需要 --theme（可选：%s）" % ", ".join(available_themes(lex)), file=sys.stderr)
        return 1

    cards = generate(args.theme, args.n, args.seed, lex)
    if args.with_names:
        cards = attach_names(cards, args.name_profile, args.seed)

    for card in cards:
        print(json.dumps(card, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
