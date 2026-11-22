#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rank_scan.py —— 网文榜单清洗与赛道统计工具

用途
    把从起点 / 番茄等平台人工或半自动抓下来的榜单快照（CSV）做清洗、聚合，
    输出「赛道热度 / 饱和度 / 新书占比」三张表，供选题决策使用。

用法
    python3 rank_scan.py --input data/rank_samples.csv --out-md ../01_report/_auto_rank_stats.md
    python3 rank_scan.py --input data/rank_samples.csv --explode-books

输入字段（首行为表头，缺列会自动跳过不报错）
    platform, category, title, author, tags, words_wan, status, heat, heat_type, snapshot
    - tags      用分号 ; 分隔
    - words_wan 单位：万字（缺失填 0）
    - heat      月票 / 内部热度等代理指标（缺失填 0）

设计原则
    1) 不做"平台对比玄学"，只用能在 CSV 里复现的口径；
    2) 热度数值常常缺失（番茄不公开月票），所以统计里同时给「有值样本数」，
       避免用 0 拉低均值制造假结论；
    3) 饱和度 = 同标签重复出现的程度，用来判断"这条赛道还挤不挤得进去"。
"""

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# 字数低于该阈值的连载作品，视为"新书"（用于估算赛道的新书供给速度）
NEW_BOOK_WORDS = 30.0
# 标签视为"热门标签"的最少出现次数
HOT_TAG_MIN = 3


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for raw in reader:
            if not raw or not (raw.get("title") or "").strip():
                continue
            rows.append({
                "platform": (raw.get("platform") or "").strip(),
                "category": (raw.get("category") or "").strip(),
                "title": (raw.get("title") or "").strip(),
                "author": (raw.get("author") or "").strip(),
                "tags": [t.strip() for t in (raw.get("tags") or "").split(";") if t.strip()],
                "words_wan": _to_float(raw.get("words_wan")),
                "status": (raw.get("status") or "").strip(),
                "heat": _to_float(raw.get("heat")),
                "heat_type": (raw.get("heat_type") or "").strip(),
                "snapshot": (raw.get("snapshot") or "").strip(),
            })
    return rows


def _to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return 0.0


def agg_by_category(rows):
    buckets = defaultdict(list)
    for r in rows:
        key = f'{r["platform"]} / {r["category"]}'
        buckets[key].append(r)

    out = []
    total = len(rows)
    for key, items in buckets.items():
        heats = [i["heat"] for i in items if i["heat"] > 0]
        words = [i["words_wan"] for i in items if i["words_wan"] > 0]
        new_books = [i for i in items
                     if i["status"] == "连载" and 0 < i["words_wan"] < NEW_BOOK_WORDS]
        done = [i for i in items if i["status"] in ("完本", "完结")]
        out.append({
            "赛道": key,
            "样本数": len(items),
            "占比": round(len(items) / total * 100, 1),
            "有热度样本": len(heats),
            "热度中位数": round(statistics.median(heats), 0) if heats else None,
            "热度头部": max(heats) if heats else None,
            "头部集中度": round(max(heats) / statistics.median(heats), 2) if len(heats) > 1 and statistics.median(heats) else None,
            "平均字数(万)": round(statistics.mean(words), 1) if words else None,
            "新书占比%": round(len(new_books) / len(items) * 100, 1),
            "完本率%": round(len(done) / len(items) * 100, 1),
        })
    out.sort(key=lambda x: (-x["样本数"], x["赛道"]))
    return out


def tag_stats(rows):
    cnt = Counter()
    by_tag_words = defaultdict(list)
    for r in rows:
        for t in r["tags"]:
            cnt[t] += 1
            if r["words_wan"] > 0:
                by_tag_words[t].append(r["words_wan"])

    hot = []
    for tag, c in cnt.most_common():
        if c < HOT_TAG_MIN:
            break
        ws = by_tag_words.get(tag, [])
        hot.append({
            "标签": tag,
            "出现次数": c,
            "占样本比%": round(c / len(rows) * 100, 1),
            "平均字数(万)": round(statistics.mean(ws), 1) if ws else None,
            "饱和度": _saturate(c, len(rows)),
        })
    return hot


def _saturate(count, total):
    """饱和度：出现次数占样本比例的经验分档，用于判断"同类供给是否已经过载"。"""
    ratio = count / total if total else 0
    if ratio >= 0.15:
        return "极高（红海）"
    if ratio >= 0.08:
        return "高（拥挤）"
    if ratio >= 0.04:
        return "中（可切入）"
    return "低（蓝海/待验证）"


def find_whitespace(rows, hot_tags):
    """找「独占标签」：全库只出现 1 次的标签 = 作者独有的卖点，是差异化的直接证据。"""
    freq = Counter()
    for r in rows:
        for t in r["tags"]:
            freq[t] += 1
    out = []
    for r in rows:
        solo = [t for t in r["tags"] if freq[t] == 1]
        if solo:
            out.append({"书名": r["title"], "平台": r["platform"],
                        "差异化标签": solo, "热度": r["heat"]})
    out.sort(key=lambda x: -x["热度"])
    return out


def _clean(d):
    """把 None 渲染成破折号，避免表格里出现难看的 None。"""
    return {k: ("—" if v is None else v) for k, v in d.items()}


def render_md(rows, cat_table, hot_tags, outliers):
    L = []
    L.append("# 榜单自动统计（rank_scan.py 生成）\n")
    L.append(f"- 样本量：**{len(rows)}** 条（起点 + 番茄，2026 年 5–11 月榜单快照）")
    L.append(f"- 口径说明：起点用「月票」、番茄用「内部热度/榜位」作代理指标；缺失计 0 且不计入均值。")
    L.append(f"- 新书口径：连载且字数 < {NEW_BOOK_WORDS:.0f} 万字。\n")

    L.append("## 一、平台 × 分类 分布\n")
    L.append("| 赛道 | 样本 | 占比% | 有热度样本 | 热度中位 | 热度头部 | 头部集中度 | 平均字数(万) | 新书占比% | 完本率% |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for c in cat_table:
        L.append("| {赛道} | {样本数} | {占比} | {有热度样本} | {热度中位数} | {热度头部} | {头部集中度} | {平均字数(万)} | {新书占比%} | {完本率%} |".format(**_clean(c)))
    L.append("")

    L.append("## 二、高频标签与饱和度\n")
    L.append("| 标签 | 出现次数 | 占比% | 平均字数(万) | 饱和度判断 |")
    L.append("|---|---|---|---|---|")
    for t in hot_tags:
        L.append("| {标签} | {出现次数} | {占样本比%} | {平均字数(万)} | {饱和度} |".format(**_clean(t)))
    L.append("")

    L.append("## 三、独占标签（差异化证据）\n")
    L.append("全库只出现 1 次的标签，说明这类作品是靠一个别人没有的钩子挤上榜单的，值得单独拆解：\n")
    L.append("| 作品 | 平台 | 独占标签 |")
    L.append("|---|---|---|")
    for o in outliers:
        L.append(f'| {o["书名"]} | {o["平台"]} | {", ".join(o["差异化标签"])} |')
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="网文榜单清洗与赛道统计")
    ap.add_argument("--input", default="data/rank_samples.csv", help="榜单 CSV 路径")
    ap.add_argument("--out-md", default=None, help="markdown 输出路径")
    ap.add_argument("--out-json", default=None, help="json 输出路径")
    args = ap.parse_args(argv)

    path = Path(args.input)
    if not path.is_absolute():
        path = (Path(__file__).parent / path).resolve()
    if not path.exists():
        print(f"[x] 找不到输入文件：{path}", file=sys.stderr)
        return 1

    rows = read_rows(path)
    if not rows:
        print("[x] CSV 里没有有效行", file=sys.stderr)
        return 1

    cat_table = agg_by_category(rows)
    hot_tags = tag_stats(rows)
    outliers = find_whitespace(rows, hot_tags)

    md = render_md(rows, cat_table, hot_tags, outliers)
    print(md)

    if args.out_md:
        p = Path(args.out_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print(f"\n[√] markdown 已写入：{p}")

    if args.out_json:
        p = Path(args.out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "sample_size": len(rows),
            "by_category": cat_table,
            "hot_tags": hot_tags,
            "whitespace": outliers,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[√] json 已写入：{p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
