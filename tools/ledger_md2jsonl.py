#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_md2jsonl.py —— 连载台账 Markdown → JSON Lines（v3.18.3，仓级工具）
================================================================================
用途：把 `06-连载护航` 的台账表格**机械抽取**成 ledger_qa.py 可灌入的
      JSON Lines。产物只进素材层，问答回放的「出处」指向原台账行。

为什么需要转换器（而不是手抄 JSONL）
------------------------------------
台账是**活文档**（每章写完都填）。手抄一份 JSONL = 立刻过时 =
两个真相源漂移。转换器保证：**台账改一行 → 重跑 → 问答同步**。

与 md2dse.py 的分工
------------------
| 工具 | 输入 | 输出 | 用途 |
|---|---|---|---|
| `md2dse.py` | 规划层（大纲/节拍/零件卡） | YAML 场景图 | **结构校验**（三道门） |
| `ledger_md2jsonl.py` | 记录层（连载台账） | JSON Lines | **事实回放**（问答） |

两者互不重叠：dse 管「结构对不对」，ledger_qa 管「答案是什么」。

抽取范围（**只抽可机械判定的字段**）
------------------------------------
| 台账节 | kind | id | where | text |
|---|---|---|---|---|
| §三 伏笔账本 | `foreshadow` | FS-XX | 埋于章 | 描述 + 状态 + 计划回收 |
| §五 时间线锚 | `timeline` | Tn | 昼夜 | 事件 + 承接 |
| §四 线头表 | `thread` | 行动线名 | 开启章 | 当前条目 + 预计收束 |
| §一 日更台账 | `chapter` | 章号 | 时间锚 | 伏笔变动 + 代价/资源变动 |

⚠️ **不抽**长段叙述（角色知识状态表、主角状态快照表）——那些是连续文本，
硬塞进问答会变成「截断的答案」，反而不如直接查原文。

用法：
  python tools/ledger_md2jsonl.py <台账.md> -o <输出.jsonl>
  python tools/ledger_md2jsonl.py <台账.md> --stdout          # 预览
  python tools/ledger_md2jsonl.py <台账.md> --stats           # 只报统计

**纪律**：本工具只读台账、只写自己的 JSONL，不改台账、不改正文。

作者：WorkBuddy ｜ 2026-11-21
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

# Markdown 表格解析（与 tools/procedural/md2dse.py 同口径：跳过表头与分隔行）
def parse_markdown_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []   # 去掉表头


def section(text: str, pattern: str) -> str | None:
    """按标题正则切出小节（到下一个同级/更高级标题为止）。"""
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


def clean(s: str) -> str:
    """去加粗标记 + 压空白（保留中文标点与 FS 编号）。"""
    s = s.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", s).strip()


def extract_foreshadow(text: str) -> list[dict]:
    """§三 伏笔账本（8 列表）。"""
    block = section(text, r"##\s*三、伏笔账本(.*?)(?=\n##\s)")
    out = []
    for cells in parse_markdown_table(block or ""):
        if len(cells) < 6:
            continue
        fid = clean(cells[0])
        if not re.fullmatch(r"FS-\d{2,3}", fid):
            continue
        desc = clean(cells[1])
        planted = clean(cells[2])
        plan = clean(cells[3])
        status = clean(cells[5])
        body = f"{desc}｜埋于第 {planted} 章｜计划回收：{plan}｜状态：{status}"
        out.append({"kind": "foreshadow", "id": fid,
                    "where": f"第 {planted} 章", "text": body})
    return out


def extract_timeline(text: str) -> list[dict]:
    """§五 时间线锚（4 列表）。"""
    block = section(text, r"##\s*五、时间线锚(.*?)(?=\n##\s)")
    out = []
    for cells in parse_markdown_table(block or ""):
        if len(cells) < 3:
            continue
        tid = clean(cells[0])
        if not re.fullmatch(r"T\d+", tid):
            continue
        event = clean(cells[1])
        day = clean(cells[2])
        carry = clean(cells[3]) if len(cells) > 3 else ""
        body = f"{event}｜时间：{day}" + (f"｜承接：{carry}" if carry else "")
        out.append({"kind": "timeline", "id": tid,
                    "where": day[:40], "text": body})
    return out


def extract_threads(text: str) -> list[dict]:
    """§四 线头表（4 列表）。id 用序号（L01...）保证稳定。"""
    block = section(text, r"##\s*四、线头表(.*?)(?=\n##\s)")
    out = []
    for i, cells in enumerate(parse_markdown_table(block or ""), start=1):
        if len(cells) < 3:
            continue
        typ = clean(cells[0])
        item = clean(cells[1])
        opened = clean(cells[2])
        close = clean(cells[3]) if len(cells) > 3 else ""
        if not item:
            continue
        tid = f"L{i:02d}"
        body = f"{typ}：{item}｜开启：第 {opened} 章" + (f"｜收束：{close}" if close else "")
        out.append({"kind": "thread", "id": tid,
                    "where": f"第 {opened} 章", "text": body})
    return out


def extract_chapters(text: str) -> list[dict]:
    """§一 日更台账（5 列表）——「伏笔变动」与「代价/资源」两列。"""
    block = section(text, r"##\s*一、日更最小台账(.*?)(?=\n##\s)")
    out = []
    for cells in parse_markdown_table(block or ""):
        if len(cells) < 5:
            continue
        ch = clean(cells[0])
        if not ch.isdigit():
            continue
        anchor = clean(cells[1])
        fores = clean(cells[3])
        cost = clean(cells[4])
        body = f"伏笔变动：{fores}｜代价与资源：{cost}"
        out.append({"kind": "chapter", "id": ch,
                    "where": anchor[:50], "text": body})
    return out


EXTRACTORS = [
    ("伏笔账本", extract_foreshadow),
    ("时间线锚", extract_timeline),
    ("线头表", extract_threads),
    ("日更台账", extract_chapters),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="ledger_md2jsonl.py",
        description="连载台账 Markdown → JSON Lines（机械抽取，防双源漂移）",
    )
    ap.add_argument("source", help="台账 Markdown 路径")
    ap.add_argument("-o", "--output", help="输出 .jsonl 路径")
    ap.add_argument("--stdout", action="store_true", help="输出到 stdout（预览）")
    ap.add_argument("--stats", action="store_true", help="只报统计，不写文件")
    args = ap.parse_args(argv)

    src = Path(args.source)
    if not src.exists():
        print(f"[FAIL] 台账文件不存在：{src}", file=sys.stderr)
        return 1

    text = io.open(src, encoding="utf-8").read()
    records: list[dict] = []
    for label, fn in EXTRACTORS:
        got = fn(text)
        print(f"[INFO] {label}：抽取 {len(got)} 条", file=sys.stderr)
        records += got

    if not records:
        print("[FAIL] 未抽到任何台账条目 —— 源文档结构可能已变", file=sys.stderr)
        return 1

    if args.stats:
        from collections import Counter
        c = Counter(r["kind"] for r in records)
        print(f"合计 {len(records)} 条：" + "、".join(f"{k}={v}" for k, v in sorted(c.items())))
        return 0

    payload = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
    if args.stdout or not args.output:
        sys.stdout.write(payload)
    else:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        io.open(out, "w", encoding="utf-8", newline="\n").write(payload)
        print(f"[OK] 已写出 {len(records)} 条 → {out}")

    # 可复现性提示（同源文件两次输出应字节一致）
    print(f"[INFO] 固定源 ⇒ 固定输出（无随机源），可直接 diff 复核", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
