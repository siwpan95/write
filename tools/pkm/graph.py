#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graph.py —— PKM 知识图谱与 MOC 生成
================================================================================
两种产物的严格区分（这是本仓的一条新纪律）
--------------------------------------------
- **派生缓存（不入库）**：`PKM/index.json` —— 全文倒排索引。
  可随时重建（10 秒），入库只会制造 diff 噪音。
- **知识资产（入库）**：`PKM/graph.json` + `PKM/MOC-*.md` —— 文档元数据与连接关系。
  这是**人工积累的价值**，必须进版本库才能跨机复用。

MOC（Map of Content · 内容地图）
--------------------------------
LYT 方法论里 MOC ��角色：**过大的文件夹需要一张索引页**。
本仓 1161 个文件、20 个顶层目录、979 个文件挤在第 2 层 —— 正符合
「需要 MOC」的条件。MOC 由脚本**生成骨架**（保证全库覆盖、不漏项），
再由人工**补充叙事**（写清各块的关系），二者结合。

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from typing import Any

from scanner import Doc, decode, resolve_links, scan, summarize

# --------------------------------------------------------------------------
# 图谱（入库资产）
# --------------------------------------------------------------------------

def load_meta_overrides(root: str) -> dict[str, dict[str, Any]]:
    """
    读取受控元数据清单 `PKM/02-索引/文档元数据清单.md`。

    **为什么要有这个**：本仓 1161 个已有文件**不批量注入 frontmatter**
    （违反《工作区规范》§五「正文零改动」）。需要给某篇文档补元数据时，
    在清单里登记一行，由索引器合并进图谱 —— **源文件一个字节不动**。

    格式：Markdown 里的 ```jsonl 围栏代码块，每行一个 JSON 对象。
    """
    path = os.path.join(root, "PKM", "02-索引", "文档元数据清单.md")
    if not os.path.exists(path):
        return {}

    try:
        raw = open(path, "rb").read()
    except OSError:
        return {}
    text = decode(raw)

    # 取出所有 ```jsonl 围栏块
    out: dict[str, dict[str, Any]] = {}
    for block in re.findall(r"```jsonl\s*\n(.*?)```", text, re.S):
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = obj.get("path")
            if p:
                out[p] = obj
    return out


def apply_overrides(docs: list[Doc], root: str) -> int:
    """
    把受控元数据清单合并进文档条目（就地修改）。

    **索引与图谱必须用同一份元数据** —— 否则「检索到的」和「图谱里显示的」
    会不一致（例如标签只在一处生效）。故此函数由两者共用。

    返回合并的条目数。
    """
    overrides = load_meta_overrides(root)
    for d in docs:
        ov = overrides.get(d.path)
        if not ov:
            continue
        d.doc_type = ov.get("type") or d.doc_type
        d.tags = list(dict.fromkeys(list(d.tags) + list(ov.get("tags") or [])))
        d.aliases = list(dict.fromkeys(list(d.aliases) + list(ov.get("aliases") or [])))
        projs = ov.get("projects") or []
        if projs and not d.project:
            d.project = projs[0]
    return len(overrides)


def build_graph(root: str) -> dict[str, Any]:
    """
    构建**可入库**的知识图谱。

    只保留有长期价值的信息：身份、归属、计量、连接。
    不含全文倒排（那是缓存）。
    """
    docs = scan(root)
    apply_overrides(docs, root)
    resolve_links(docs, root)
    summary = summarize(docs)
    overrides = load_meta_overrides(root)

    nodes = []
    for d in docs:
        ov = overrides.get(d.path, {})
        nodes.append({
            "path": d.path,
            "title": d.title,
            "type": d.doc_type,
            "project": d.project,
            "role": d.role,
            "net_chars": d.net_chars,
            "tags": d.tags,
            "aliases": d.aliases,
            "out": d.resolved,
            "in": d.backlinks,
            "broken": d.broken,
            "archived": d.archived,
            "fm": d.fm,
            "overridden": bool(ov),
        })

    return {
        "schema": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": summary,
        "overrides_count": len(overrides),
        "nodes": nodes,
    }


def write_graph(graph: dict[str, Any], path: str) -> tuple[str, int]:
    """
    落盘图谱。**不带 BOM** —— JSON 属「机器读」类，与脚本同惯例。

    与文本类文件（.md/.py，UTF-8-SIG）分开，是本仓编码约定的两分法：
    内容给人读 → 带 BOM 兼容 Windows 编辑器；机器读 → 无 BOM 免解析差异。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.dumps(graph, ensure_ascii=False, indent=1)
    with open(path, "wb") as f:
        f.write(data.replace("\r\n", "\n").encode("utf-8"))
    return path, len(data)


# --------------------------------------------------------------------------
# MOC 生成
# --------------------------------------------------------------------------

def _fmt(n: int) -> str:
    return f"{n:,}"


def render_moc(graph: dict[str, Any]) -> str:
    """
    生成全库 MOC 骨架（Markdown）。

    形态：**自上而下**（按项目分组）＋ 每组内给出「该组的核心文档」。
    这是 MOC 的标准骨架，人工在此基础上补「为什么这样组织」的叙事。
    """
    s = graph["summary"]
    nodes = graph["nodes"]

    by_project: dict[str, list[dict]] = defaultdict(list)
    for n in nodes:
        by_project[n["project"] or "（仓根）"].append(n)

    lines: list[str] = []
    A = lines.append

    A("# MOC · 全库内容地图")
    A("")
    A("> **本文件由 `npm run pkm:moc` 生成骨架**，请在生成段落之间补写人工叙事。")
    A("> 生成内容会被覆盖 —— 手写内容请写在「## 人工补充」之后，或另建 `MOC-*.md` 专页。")
    A("")
    A(f"<!-- 生成时间：{graph['generated_at']} ｜ 文档 {_fmt(s['docs'])} ｜ "
      f"连接 {_fmt(s['total_links'])} ｜ 断链 {_fmt(s['total_broken'])} -->")
    A("")
    A("## 统计")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    A(f"| 文档总数 | {_fmt(s['docs'])} |")
    A(f"| 净字符合计 | {_fmt(s['net_chars_total'])} |")
    A(f"| 出链总数 | {_fmt(s['total_links'])} |")
    A(f"| 断链 | {_fmt(s['total_broken'])} |")
    A(f"| 带 frontmatter | {_fmt(s['frontmatter_docs'])} |")
    A(f"| 标签总数 | {_fmt(s['tag_count'])} |")
    A(f"| 孤立文档（无入链无出链） | {_fmt(s['orphan_count'])} |")
    A("")

    A("## 按文档类型")
    A("")
    A("| 类型 | 数量 |")
    A("|---|---|")
    for t, c in s["by_type"].items():
        A(f"| {t} | {_fmt(c)} |")
    A("")

    A("## 按项目")
    A("")
    A("| 项目 | 文档 | 净字数 | 出链 | 主要类型 |")
    A("|---|---|---|---|---|")
    for proj, info in s["by_project"].items():
        types = sorted(info["types"].items(), key=lambda kv: -kv[1])
        tstr = "、".join(f"{t}({c})" for t, c in types[:4])
        A(f"| {proj} | {_fmt(info['docs'])} | {_fmt(info['net_chars'])} | "
          f"{_fmt(info['links'])} | {tstr} |")
    A("")

    A("## 各项目文档树")
    A("")
    for proj in sorted(by_project.keys(), key=lambda p: -len(by_project[p])):
        group = by_project[proj]
        A(f"### {proj}（{_fmt(len(group))} 篇）")
        A("")
        # 入口总览优先
        entries = [n for n in group if n["role"] == "入口总览"]
        if entries:
            A("**入口**：" + "、".join(
                f"[{n['title']}]({n['path'].replace(' ', '%20')})" for n in entries))
            A("")
        # 按 role 汇总
        byrole: dict[str, list] = defaultdict(list)
        for n in group:
            byrole[n["role"] or n["type"]].append(n)
        for role in sorted(byrole.keys()):
            items = byrole[role]
            if role == "入口总览":
                continue
            A(f"- **{role}**（{_fmt(len(items))}）：" +
              "、".join(f"`{n['path']}`" for n in items[:12]) +
              (" …" if len(items) > 12 else ""))
        A("")

    A("## 人工补充")
    A("")
    A("<!-- 在此写：这个仓库怎么读、从哪儿入手、哪几块是同一套东西、哪些坑别踩 -->")
    A("")
    return "\n".join(lines)


def render_orphans(graph: dict[str, Any], limit: int = 200) -> str:
    """孤立文档清单 —— 「连接层待补」的施工单。"""
    s = graph["summary"]
    orphans = [n for n in graph["nodes"] if not n["in"] and not n["out"]]
    lines = ["# 孤立文档清单（连接层待补）", "",
             f"> 无入链、无出链 —— 检索得到，但**从任何其他文档都走不到**。",
             f"> 共 {_fmt(len(orphans))} 篇（占 {len(orphans)*100//max(s['docs'],1)}%）。",
             "> 这份清单是**施工单**：从索引页出发补连接，比逐篇补双链更省力。", ""]
    byproj: dict[str, list] = defaultdict(list)
    for n in orphans:
        byproj[n["project"] or "（仓根）"].append(n)
    for proj in sorted(byproj, key=lambda p: -len(byproj[p])):
        lines.append(f"## {proj}（{len(byproj[proj])}）")
        lines.append("")
        for n in byproj[proj][:limit]:
            lines.append(f"- `{n['path']}` — {n['title']}（{n['type']}）")
        lines.append("")
    return "\n".join(lines)


def render_broken(graph: dict[str, Any]) -> str:
    """断链清单 —— 机械门禁的数据源。"""
    rows = []
    for n in graph["nodes"]:
        for b in n["broken"]:
            rows.append((n["path"], b))
    lines = ["# 断链清单", "",
             f"> 链接目标解析不到 —— 共 **{len(rows)}** 条。", ""]
    if rows:
        lines.append("| 来源 | 目标 |")
        lines.append("|---|---|")
        for src, tgt in rows:
            lines.append(f"| `{src}` | `{tgt}` |")
    else:
        lines.append("✅ 无断链。")
    lines.append("")
    return "\n".join(lines)


def write_text(text: str, path: str) -> tuple[str, int]:
    """写 Markdown —— **带 BOM**（UTF-8-SIG，兼容 Windows 编辑器，§六）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(text.replace("\r\n", "\n").encode("utf-8"))
    return path, len(text.encode("utf-8"))


if __name__ == "__main__":
    import sys
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    g = build_graph(root)
    p, n = write_graph(g, os.path.join(root, "PKM", "graph.json"))
    print(f"图谱：{p}（{n} 字节）")
    s = g["summary"]
    print(f"文档 {s['docs']} ／ 出链 {s['total_links']} ／ 断链 {s['total_broken']}")
