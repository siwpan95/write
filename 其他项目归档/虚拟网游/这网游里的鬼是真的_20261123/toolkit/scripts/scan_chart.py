#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_chart.py — 网文榜单快照扫描与赛道拥挤度分析（零依赖，Python 3.8+）

用途：
  对人工采集/扒榜得到的榜单快照 CSV 做确定性统计：
  分类分布、细分占比、头部集中度（CR5/CR10/HHI）、赛道拥挤度启发式评分，
  并输出 Markdown 摘要报告。所有计算本地完成，不联网。

输入 CSV 约定（UTF-8，带表头，列顺序不限但列名必须一致）：
  书名,平台,分类,细分,在读,收藏,推荐,字数万,更新天数
  * 在读/收藏/推荐/字数万 为数字；更新天数 = 距上次更新天数（整数）
  * 参考 example_chart.csv

用法：
  python scan_chart.py <榜单.csv>                        # 全量扫描
  python scan_chart.py <榜单.csv> --category 虚拟网游     # 只看某分类
  python scan_chart.py <榜单.csv> --top 10               # 头部榜展示条数（默认 10）
  python scan_chart.py <榜单.csv> --out report.md        # 写出 Markdown 报告文件

退出码：0=正常；2=输入文件/列缺失错误。

作者：全哥游戏工坊 · 网文全流程工具链（主理人汇编）
"""
import argparse
import csv
import io
import math
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REQUIRED = ["书名", "平台", "分类", "细分", "在读", "收藏", "推荐", "字数万", "更新天数"]
NUMERIC = ["在读", "收藏", "推荐", "字数万", "更新天数"]


def fail(msg):
    print("[ERROR] " + msg, file=sys.stderr)
    sys.exit(2)


def load_rows(path):
    # utf-8-sig 兼容 Excel 导出的 BOM；失败再试 gbk（中文 Windows 常见导出格式）
    for enc in ("utf-8-sig", "gbk"):
        try:
            with io.open(path, "r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            break
        except UnicodeDecodeError:
            continue
        except OSError as e:
            fail("无法读取文件: %s (%s)" % (path, e))
    else:
        fail("编码无法识别（尝试过 utf-8-sig / gbk）")
    if not rows:
        fail("CSV 无数据行: " + path)
    missing = [c for c in REQUIRED if c not in (rows[0].keys() or [])]
    if missing:
        fail("缺少必需列: %s（实际列: %s）" % (",".join(missing), ",".join(rows[0].keys())))
    out = []
    for i, r in enumerate(rows, start=2):  # start=2 对应含表头的行号
        item = {k: (r.get(k) or "").strip() for k in REQUIRED}
        ok = True
        for k in NUMERIC:
            v = item[k].replace(",", "")
            if v == "":
                item["_missing"] = item.get("_missing", "") + k + ","
                item[k] = None
                continue
            try:
                item[k] = float(v)
                if k in ("更新天数",):
                    item[k] = int(item[k])
            except ValueError:
                item["_badnum"] = item.get("_badnum", "") + k + ","
                item[k] = None
                ok = False
        item["_line"] = i
        out.append(item)
    return out


def hhi(shares):
    # shares: 百分比列表（和为100）；HHI = Σ share^2，范围 0~10000
    return round(sum(s * s for s in shares), 1)


def crowd_score(n_books, cr5, cat_share_pct):
    """拥挤度启发式评分 0~100（越高越挤）：
       60% 权重看同分类上榜书量相对全榜密度，40% 看头部集中度 CR5。"""
    density = n_books / max(cat_share_pct, 1.0)  # 该分类相对密度
    d_norm = min(density * 20, 100)              # 密度 5 倍以上即满
    c_norm = min(cr5 * 2.5, 100)                 # CR5=40% 即满
    return round(d_norm * 0.6 + c_norm * 0.4, 1)


def main():
    ap = argparse.ArgumentParser(description="网文榜单快照扫描与赛道拥挤度分析")
    ap.add_argument("csv_path", help="榜单快照 CSV 路径")
    ap.add_argument("--category", default=None, help="只统计该分类（如 虚拟网游）")
    ap.add_argument("--top", type=int, default=10, help="头部榜展示条数")
    ap.add_argument("--out", default=None, help="Markdown 报告输出路径")
    args = ap.parse_args()

    rows = load_rows(args.csv_path)
    if args.category:
        rows = [r for r in rows if r["分类"] == args.category]
        if not rows:
            fail("分类 %s 下无数据行" % args.category)

    lines = []
    A = lines.append
    A("# 榜单扫描报告（scan_chart.py）")
    A("")
    A("- 数据文件：%s" % args.csv_path)
    A("- 统计范围：%s（共 %d 条）" % (args.category or "全部分类", len(rows)))
    A("")

    # 数据健康检查
    bad = [r for r in rows if r.get("_badnum") or r.get("_missing")]
    A("## 0. 数据健康检查")
    A("")
    if bad:
        for r in bad[:20]:
            A("- 第 %d 行《%s》：异常字段 %s" % (
                r["_line"], r["书名"], (r.get("_badnum") or "") + (r.get("_missing") or "")))
        A("- **提示**：异常数值按缺失处理，不参与相关统计。")
    else:
        A("- 全部字段正常，无缺失。")
    A("")

    # 有效行（在读非缺失才参与头部榜）
    valid = [r for r in rows if r.get("在读") is not None]
    if not valid:
        fail("没有可用于统计的『在读』数据")

    # 分类分布
    cat_cnt = Counter(r["分类"] for r in rows)
    total = sum(cat_cnt.values())
    A("## 1. 分类分布")
    A("")
    A("| 分类 | 书量 | 占比 |")
    A("|---|---|---|")
    for c, n in cat_cnt.most_common():
        A("| %s | %d | %.1f%% |" % (c, n, n * 100.0 / total))
    A("")

    # 细分占比（若填写了细分列）
    sub_cnt = Counter(r["细分"] for r in rows if r["细分"])
    if sub_cnt:
        A("## 2. 细分占比")
        A("")
        A("| 细分 | 书量 | 占比 |")
        A("|---|---|---|")
        st = sum(sub_cnt.values())
        for c, n in sub_cnt.most_common():
            A("| %s | %d | %.1f%% |" % (c, n, n * 100.0 / st))
        A("")

    # 头部榜（按在读）
    ranked = sorted(valid, key=lambda r: r["在读"], reverse=True)
    A("## 3. 头部榜（按在读 Top %d）" % min(args.top, len(ranked)))
    A("")
    A("| # | 书名 | 平台 | 分类 | 细分 | 在读 | 收藏 | 字数万 | 更新天数 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(ranked[:args.top], 1):
        A("| %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            i, r["书名"], r["平台"], r["分类"], r["细分"],
            fmt(r["在读"]), fmt(r["收藏"]), fmt(r["字数万"]),
            r["更新天数"] if r["更新天数"] is not None else "-"))
    A("")

    # 集中度与拥挤度（针对目标分类或全榜）
    target_rows = rows
    tgt_name = args.category or "全榜"
    reads = [r["在读"] for r in target_rows]
    s = sum(reads)
    if s <= 0:
        fail("『在读』总和为 0，无法计算集中度")
    shares_pct = [v * 100.0 / s for v in reads]
    cr5 = sum(sorted(shares_pct, reverse=True)[:5])
    cr10 = sum(sorted(shares_pct, reverse=True)[:10])
    h = hhi(shares_pct)
    n = len(target_rows)
    cat_share = (cat_cnt.get(args.category, n) * 100.0 / total) if args.category else 100.0
    score = crowd_score(n, cr5, max(cat_share, 1.0))
    level = ("红海（拥挤）" if score >= 70 else "次拥挤" if score >= 50 else
             "适中" if score >= 30 else "蓝海（稀缺）")
    A("## 4. 集中度与拥挤度（%s）" % tgt_name)
    A("")
    A("- 书量：%d；在读总量：%s" % (n, fmt(s)))
    A("- CR5 = %.1f%%；CR10 = %.1f%%；HHI = %.1f" % (cr5, cr10, h))
    A("- **拥挤度评分：%s / 100（%s）**" % (score, level))
    A("  - 评分口径：60% 权重=分类相对密度，40% 权重=头部集中度；≥70 红海，50-69 次拥挤，30-49 适中，<30 蓝海。")
    A("")

    # 结论建议
    A("## 5. 结论提示")
    A("")
    if cr5 >= 40:
        A("- 头部集中度高（CR5≥40%）：新书蹭流量应找头部未覆盖的细分空白，不建议同质对位。")
    else:
        A("- 头部分散：腰部以下有翻身窗口，中前期数据反馈比题材标签更决定走向。")
    top3_sub = sub_cnt.most_common(3)
    if top3_sub:
        A("- 细分头部：%s —— 拥挤度最高的细分建议做混合嫁接（如 +重生/+第四天灾/+电竞）做差异化。" %
          "、".join("%s(%d)" % (k, v) for k, v in top3_sub))
    A("- 本报告为快照统计，榜单随时变动，结论有效期建议 ≤ 7 天。")

    report = "\n".join(lines) + "\n"
    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
        print("报告已写出: %s" % args.out)
    print(report)


def fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return "{:,}".format(int(v)) if isinstance(v, (int, float)) and abs(v) >= 1000 else str(v)


if __name__ == "__main__":
    main()
