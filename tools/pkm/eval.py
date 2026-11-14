#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval.py —— 最小检索评测集（v2 审计 G-05）
================================================================================
目的：证明「检索打分修复」不是靠感觉，而是有修复前/后的数值基线。

两种打分并存，便于对比：
  current  —— indexer.search()（per-document 命中 + IDF + 覆盖率折扣）
  legacy   —— 复现 2026-11-14 修复前的算法（body_hit 为全局常数 +
              10*body_hit/(net_chars/1000) 长度反比放大）

指标（对齐通用 IR 口径，k 固定，不跨系统比较不同 k）：
  MRR@10        第一个相关结果排名的倒数均值
  NDCG@10       binary relevance 的 DCG / IDCG
  HitRate@5     top5 是否含相关文档
  Precision@10  top10 中相关文档占比

评测集：tools/pkm/eval_set.json（20 条；gold_any 为路径子串，命中任一即相关；
空数组＝负例）。负例不计入 MRR/NDCG 汇总，单独统计「是否硬凑结果」。

用法：
  python tools/pkm/eval.py                 # 前后对比
  python tools/pkm/eval.py --mode current  # 只看当前
  python tools/pkm/eval.py --json          # 机读输出
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import indexer  # noqa: E402


def _ids_of_factory(index):
    terms = index['terms']
    id_to_path = index.get('id_to_path') or [d['path'] for d in index['docs']]

    def _ids_of(term):
        raw = terms.get(term)
        if not raw:
            return []
        if isinstance(raw[0], int):
            return raw
        out = []
        for p in raw:
            for i, dp in enumerate(id_to_path):
                if dp == p:
                    out.append(i)
                    break
        return out

    return _ids_of, id_to_path


def legacy_search(index: dict, query: str, limit: int = 20) -> list[dict]:
    """修复前的打分（逐行复现，用于 before/after 对比；不用于生产）。"""
    q = query.strip().lower()
    if not q:
        return []
    qtoks = list(dict.fromkeys(indexer.tokenize(q)))
    if not qtoks:
        return []
    _ids_of, id_to_path = _ids_of_factory(index)
    docs_by_path = {d['path']: d for d in index['docs']}
    cand = set()
    for t in qtoks:
        cand.update(_ids_of(t))
    out = []
    for i in cand:
        path = id_to_path[i]
        d = docs_by_path.get(path)
        if d is None:
            continue
        score = 0.0
        matched = []
        title_toks = set(indexer.tokenize(d.get('title', '')))
        body_hit = 0
        for t in qtoks:
            if t in title_toks:
                score += 3.0
                matched.append(t)
            elif _ids_of(t):
                body_hit += 1
                matched.append(t)
        score += body_hit
        if score == 0:
            continue
        denom = max(d.get('net_chars', 1), 200)
        score += 10.0 * (body_hit / (denom / 1000.0))
        out.append({'path': path, 'score': round(score, 3), 'matched': sorted(set(matched))})
    out.sort(key=lambda r: (-r['score'], r['path']))
    return out[:limit]


def is_relevant(path: str, gold_any: list[str]) -> bool:
    return any(g in path for g in gold_any)


def one_query(index, case, searcher, k=20):
    rows = searcher(index, case['query'], limit=k)
    rels = [1 if is_relevant(r['path'], case['gold_any']) else 0 for r in rows]
    mrr = next((1.0 / (i + 1) for i, v in enumerate(rels[:10]) if v), 0.0)
    dcg = sum(v / math.log2(i + 2) for i, v in enumerate(rels[:10]))
    total_rel = sum(1 for d in index['docs'] if is_relevant(d['path'], case['gold_any']))
    idcg_terms = min(total_rel, 10)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(idcg_terms)) or 1.0
    return {
        'id': case['id'], 'type': case['type'], 'query': case['query'],
        'gold_patterns': len(case['gold_any']), 'total_related_docs': total_rel,
        'returned': len(rows), 'mrr': mrr, 'ndcg': dcg / idcg,
        'hit5': 1.0 if any(rels[:5]) else 0.0,
        'precision10': sum(rels[:10]) / 10.0,
        'top1': rows[0]['path'] if rows else '',
        'gold_has_docs': total_rel > 0 or not case['gold_any'],
    }


def summarize(rows):
    graded = [r for r in rows if r['type'] != '负例' and r['total_related_docs'] > 0]
    negatives = [r for r in rows if r['type'] == '负例']
    n = max(len(graded), 1)
    return {
        'graded_queries': len(graded),
        'MRR@10': sum(r['mrr'] for r in graded) / n,
        'NDCG@10': sum(r['ndcg'] for r in graded) / n,
        'HitRate@5': sum(r['hit5'] for r in graded) / n,
        'Precision@10': sum(r['precision10'] for r in graded) / n,
        'negative_avg_returned': (sum(r['returned'] for r in negatives) / len(negatives)) if negatives else 0,
        'gold_without_docs': [r['id'] for r in rows if not r['gold_has_docs']],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['both', 'current', 'legacy'], default='both')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    index = json.load(open(os.path.join(ROOT, 'PKM', 'index.json'), encoding='utf-8-sig'))
    cases = json.load(open(os.path.join(HERE, 'eval_set.json'), encoding='utf-8'))['queries']

    result = {}
    for mode in (['current', 'legacy'] if args.mode == 'both' else [args.mode]):
        searcher = indexer.search if mode == 'current' else legacy_search
        rows = [one_query(index, c, searcher) for c in cases]
        result[mode] = {'per_query': rows, 'summary': summarize(rows)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    for mode, data in result.items():
        s = data['summary']
        print(f"\n=== {mode} ===")
        print(f"  有效查询 {s['graded_queries']} 条 ｜ MRR@10={s['MRR@10']:.3f} "
              f"NDCG@10={s['NDCG@10']:.3f} HitRate@5={s['HitRate@5']:.3f} "
              f"Precision@10={s['Precision@10']:.3f}")
        print(f"  负例平均返回 {s['negative_avg_returned']:.1f} 条 ｜ gold 无对应文档：{s['gold_without_docs'] or '无'}")
        print(f"  {'ID':4} {'类型':8} {'查询':14} {'MRR':>6} {'NDCG':>6} {'top1'}")
        for r in data['per_query']:
            print(f"  {r['id']:4} {r['type']:8} {r['query'][:14]:14} "
                  f"{r['mrr']:6.2f} {r['ndcg']:6.2f} {r['top1'][:60]}")

    if args.mode == 'both':
        a, b = result['legacy']['summary'], result['current']['summary']
        print('\n=== 修复前后对比 ===')
        for k in ('MRR@10', 'NDCG@10', 'HitRate@5', 'Precision@10'):
            delta = b[k] - a[k]
            print(f'  {k:14} {a[k]:.3f} → {b[k]:.3f}  ({delta:+.3f})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
