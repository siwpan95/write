#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设定文法展开器 · grammar_expand.py（v3.12，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.2（第 2 代：Tracery 式递归文法）
用途：用 JSON 文法批量展开设定条目草稿（怪物描述/区域一句话/条目变体），
      供 03 世界观圣经、13 区域包 的素材层使用。
纪律：只产素材、不产正文；每条须人工过审（含 03 §2.1 可判定项检查）后才编号入库。

文法格式（JSON）：
  {
    "origin": ["#怪物#在#习性#。", "#怪物#盘踞于#地点#。"],
    "怪物":   ["#前缀##核心#兽", "#前缀##核心#蛟"],
    "前缀":   ["霜", "焰", "灰鳞", "裂齿"],
    "核心":   ["狼", "蟒", "鸦"],
    "习性":   ["昼伏夜出", "循铁而行", "群居换巢"],
    "地点":   ["坠星裂谷", "锈原深处", "霜井底"]
  }
  - #符号# 递归展开；值列表等权随机；支持 weight|文本 加权（如 "3|常见项"）。
用法：
  python tools/procedural/grammar_expand.py --builtin --n 3 --seed 42
  python tools/procedural/grammar_expand.py --grammar my.json --start origin --n 5 --seed 7
退出码：0 成功；1 文法错误。
"""
import argparse
import json
import random
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TOKEN = re.compile(r"#([^\s#]+)#")
WEIGHT = re.compile(r"^(\d+)\|(.*)$")

BUILTIN = {
    "origin": [
        "#怪物#，#习性#；见者当#对策#。",
        "#怪物#盘踞于#地点#，#习性#。",
        "据#记录者#手记：#怪物#畏#弱点#，出没于#地点#。"
    ],
    "怪物": ["#前缀##核心#兽", "#前缀##核心#蛟", "#前缀#独眼#核心#"],
    "前缀": ["霜", "焰", "灰鳞", "裂齿", "锈", "2|蚀影"],
    "核心": ["狼", "蟒", "鸦", "蜥"],
    "习性": ["昼伏夜出", "循铁器气息而行", "群居且定期换巢", "独居、护食至死"],
    "地点": ["坠星裂谷北缘", "锈原深处", "霜井底", "灰崖风蚀洞"],
    "对策": ["结火把队通行", "绕行三日", "以血引之、以饵困之"],
    "弱点": ["明火", "硫磺味", "铜铃声"],
    "记录者": ["商队账房", "戍堡斥候", "游方医士"]
}


def _pick(rng, choices):
    """等权或 'N|文本' 加权随机。"""
    bag = []
    for c in choices:
        m = WEIGHT.match(c.strip())
        if m:
            bag.extend([m.group(2)] * int(m.group(1)))
        else:
            bag.append(c)
    return rng.choice(bag)


def expand(grammar, symbol, rng, depth=0, leaves=None):
    """递归展开一个符号；leaves 收集每次实际选中的分支文本（供频次上限检查）。"""
    if depth > 12:
        raise ValueError("展开超过 12 层：文法疑似自环（#%s#）" % symbol)
    if symbol not in grammar:
        raise ValueError("文法缺少符号：#%s#" % symbol)
    text = _pick(rng, grammar[symbol])
    if leaves is not None:
        leaves.append(text)
    return TOKEN.sub(lambda m: expand(grammar, m.group(1), rng, depth + 1, leaves), text)


def generate(grammar, start, n, seed, max_repeat=2):
    """生成 n 条不重复展开；同一分支子句全批出现次数 ≤ max_repeat（防模板病指纹）。"""
    rng = random.Random(seed)
    seen, out, leaves_by_line = set(), [], []
    guard = 0
    while len(out) < n and guard < n * 200:
        guard += 1
        leaves = []
        line = expand(grammar, start, rng, 0, leaves)
        if line in seen:
            continue
        if max_repeat:
            over = [x for x in set(leaves)
                    if sum(ls.count(x) for ls in leaves_by_line) >= max_repeat]
            if over:
                continue
        seen.add(line)
        out.append(line)
        leaves_by_line.append(leaves)
    return out


def main():
    ap = argparse.ArgumentParser(description="设定文法展开器（素材层，禁止直接进正文）")
    ap.add_argument("--grammar", help="JSON 文法文件路径；缺省用内置演示文法")
    ap.add_argument("--start", default="origin", help="起始符号（默认 origin）")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-repeat", type=int, default=2,
                    help="同一分支子句全批最多出现次数（0=不限；默认 2，防模板病指纹）")
    ap.add_argument("--builtin", action="store_true", help="强制使用内置演示文法")
    args = ap.parse_args()

    if args.grammar and not args.builtin:
        with open(args.grammar, "r", encoding="utf-8-sig") as f:
            grammar = json.load(f)
        label = args.grammar
    else:
        grammar = BUILTIN
        label = "内置演示文法"

    try:
        lines = generate(grammar, args.start, args.n, args.seed, args.max_repeat)
    except ValueError as e:
        print("文法错误：%s" % e)
        return 1

    print("设定文法展开 · %s · start=%s n=%d seed=%d max-repeat=%d（可复现）"
          % (label, args.start, args.n, args.seed, args.max_repeat))
    for i, line in enumerate(lines, 1):
        print("  %d. %s" % (i, line))
    if len(lines) < args.n:
        print("  [警告] 去重后仅 %d/%d 条：文法组合空间不足，请扩分支" % (len(lines), args.n))
    print("\n验收门（18 §三.2）：展开 20 次重复≤2 / 与 03 专名表查重 / 过 03 §2.1 可判定项检查。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
