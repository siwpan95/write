#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docs/11 附录 · 盲评排序统计（零依赖）

M13 的问题不是"没有样本"，是"用绝对分数当判据"。本脚本把判据换成
**读者间排序一致性**，从而把"尺子好不好"和"分数定多少"拆开。

输入 CSV（无表头亦可，三列：reader,item,rank）：
    reader,item,rank
    A,base,1
    A,same_axis,2
    A,cross_axis,5
    ...

用法：
    python tools/lint/blind_rank.py ranks.csv
    python tools/lint/blind_rank.py ranks.csv --expect base=1,cross_axis=5

输出：
    - 每项平均名次（越小越靠前）
    - 两两读者一致率（同项名次之差的容忍度默认 0）
    - Kendall's W（0–1，越大越一致）
    - 若给了 --expect，逐项判定是否符合预登记预测

判定口径（写在 docs/11 §附录二）：
    W ≥ 0.6 且预测命中      → 尺子有排序力，铁律改为"斜率"形态（H2 方向）
    W ≥ 0.6 但预测相反      → 铁律被反向证伪，必须改
    W < 0.3                 → 读者间无共识，"好看"不可排序，方案作废
"""

import argparse
import csv
import itertools
import sys
from collections import defaultdict


def load(path):
    data = defaultdict(dict)   # reader -> {item: rank}
    with open(path, encoding="utf-8-sig") as fh:
        rows = [r for r in csv.reader(fh) if r and not r[0].startswith("#")]
    if rows and not rows[0][2].strip().isdigit() and rows[0][0].lower() != "a":
        rows = rows[1:]        # 跳过表头
    for r in rows:
        if len(r) < 3:
            continue
        reader, item, rank = r[0].strip(), r[1].strip(), int(r[2])
        data[reader][item] = rank
    return data


def kendall_w(data):
    items = sorted({i for d in data.values() for i in d})
    readers = sorted(data)
    m, n = len(readers), len(items)
    if m < 2 or n < 2:
        return None, items, readers
    rank_sum = {i: sum(data[r].get(i, 0) for r in readers) for i in items}
    mean = sum(rank_sum.values()) / n
    S = sum((v - mean) ** 2 for v in rank_sum.values())
    W = 12 * S / (m * m * (n ** 3 - n))
    return W, items, readers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--expect", default="", help="预登记预测，如 base=1,cross_axis=5")
    ap.add_argument("--tol", type=int, default=0, help="两两一致的名次容差，默认 0")
    args = ap.parse_args()

    data = load(args.csv)
    W, items, readers = kendall_w(data)
    if W is None:
        print("[ERROR] 至少需要 2 位读者 × 2 份材料", file=sys.stderr)
        return 2

    print("=" * 60)
    print(f"盲评排序统计 ｜ 读者 {len(readers)} 人 ｜ 材料 {len(items)} 份")
    print("=" * 60)

    rank_sum = {i: sum(data[r].get(i, 0) for r in readers) for i in items}
    avg = {i: rank_sum[i] / len(readers) for i in items}
    print("\n【平均名次】（越小越靠前）")
    for i in sorted(items, key=lambda x: avg[x]):
        print(f"  {i:16}  {avg[i]:.2f}   各读者："
              + " ".join(f"{r}={data[r].get(i, '-')}" for r in readers))

    print("\n【两两读者一致率】（同一材料名次差 ≤ %d 记为一致）" % args.tol)
    rates = []
    for a, b in itertools.combinations(readers, 2):
        same = sum(1 for i in items
                   if abs(data[a].get(i, 0) - data[b].get(i, 0)) <= args.tol)
        rate = same / len(items)
        rates.append(rate)
        print(f"  {a} ↔ {b}: {rate:.0%}")

    print(f"\n【Kendall's W】 {W:.3f}   "
          + ("（一致性可接受）" if W >= 0.6 else
             "（弱一致，仅可看趋势）" if W >= 0.3 else
             "（无共识，方案作废）"))

    if args.expect:
        print("\n【预登记预测核对】")
        pred = {}
        for pair in args.expect.split(","):
            if "=" in pair:
                k, v = pair.split("=")
                pred[k.strip()] = int(v)
        hit = 0
        for k, v in pred.items():
            ranks = [data[r].get(k) for r in readers if data[r].get(k) is not None]
            ok = bool(ranks) and abs(sum(ranks) / len(ranks) - v) <= 0.5
            hit += 1 if ok else 0
            print(f"  {k:16} 预测第 {v} 名 → 实际 {ranks}  "
                  f"（均值 {sum(ranks)/len(ranks):.2f}）{'✅' if ok else '✗'}")
        print(f"  命中 {hit}/{len(pred)}")
        print("\n判定：", end="")
        if W >= 0.6 and hit == len(pred):
            print("尺子有排序力 → 铁律改为『斜率』形态（H2 方向）")
        elif W >= 0.6 and hit < len(pred):
            print("一致但与预测不符 → 反向证伪，铁律必须改")
        else:
            print("读者间无共识 → 『好看』不可排序，本方案作废（有效作废）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
