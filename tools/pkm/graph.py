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

# 统计时**排除本工具自己生成的文件**。
# 理由：MOC 会统计自己的字数，而它的字数又随内容变化 —— 自引用导致
# 数值永不收敛（实测差 1 个字符 / 56 字）。凡由 build 生成的产物，
# 一律不计入统计，否则「跑一次」与「跑两次」结果不同。
GENERATED_PREFIXES = ("PKM/01-MOC/",)
GENERATED_FILES = {
    "PKM/MOC-全库.md",
    "PKM/graph.json",
    "PKM/孤立文档清单.md",
    "PKM/断链清单.md",
}


def is_generated(path: str) -> bool:
    """判断某路径是否为 build 生成物（不入统计，避免自引用不收敛）。"""
    return path in GENERATED_FILES or path.startswith(GENERATED_PREFIXES)

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


def load_project_links(root: str) -> dict[str, list[dict]]:
    """
    读取受控的项目关联登记表 `PKM/02-索引/项目关联登记表.md`。

    登记的是**项目之间**的真实共享关系（共享设定／方法论／研究）。
    由 build 据此给项目 MOC 补「相关项目」互链 ——
    关系是**会变的知识**，必须有独立可 diff 的登记处，不能硬编码在生成物里。

    返回 {项目名: [关联项, ...]}
    """
    path = os.path.join(root, "PKM", "02-索引", "项目关联登记表.md")
    if not os.path.exists(path):
        return {}

    try:
        raw = open(path, "rb").read()
    except OSError:
        return {}
    text = decode(raw)

    out: dict[str, list[dict]] = defaultdict(list)
    for block in re.findall(r"```jsonl\s*\n(.*?)```", text, re.S):
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            src, dst = obj.get("from"), obj.get("to")
            if src and dst:
                out[src].append(obj)
    return dict(out)


def build_graph(root: str) -> dict[str, Any]:
    """
    构建**可入库**的知识图谱。

    只保留有长期价值的信息：身份、归属、计量、连接。
    不含全文倒排（那是缓存）。
    """
    docs = scan(root)
    apply_overrides(docs, root)
    resolve_links(docs, root)
    summary = summarize(docs, exclude={d.path for d in docs if is_generated(d.path)})
    overrides = load_meta_overrides(root)

    nodes = []
    for d in docs:
        ov = overrides.get(d.path, {})
        nodes.append({
            "path": d.path,
            "title": d.title,
            "type": d.doc_type,
            "kind": d.kind,
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
        # **不含 generated_at** —— graph.json 是入库资产，带时间戳会让每次
        # 重建都产生无意义 diff。构建时刻记在 index.json（派生缓存，不入库）。
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

    **不含生成时间戳** —— 本文件是入库资产，带时间戳会让每次重建都产生
    无意义的 diff 噪音（纪律同「审校报告不入库」：时间戳只进文件名/日志，
    不进内容判定）。构建时刻由 `graph.json` 的 `generated_at` 承载，
    而它同样**不入库**（见下）。
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
    A("> **本文件由 `npm run pkm:build` 生成骨架**，请在生成段落之间补写人工叙事。")
    A("> 生成内容会被覆盖 —— 手写内容请写在「## 人工补充」之后，或另建 `MOC-*.md` 专页。")
    A("")
    A(f"<!-- 文档 {_fmt(s['docs'])} ／ 连接 {_fmt(s['total_links'])} ／ "
      f"断链 {_fmt(s['total_broken'])} -->")
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
    """
    孤立文档清单 —— **连接层待补的施工单**。

    **按「知识节点 / 叙事节点」分列**：
      · 知识节点（设定/模板/总览）—— 孤立是**真问题**，是施工单；
      · 叙事节点（正文）—— 线性叙事，**本就不该有知识链**，单列观察即可。

    （初版把两者混算，报出「96.3% 孤立」——数字虚高且误导施工方向。）
    """
    s = graph["summary"]
    nodes = graph["nodes"]

    kn = [n for n in nodes if n.get("kind") == "knowledge"
          and not n["in"] and not n["out"]]
    nv = [n for n in nodes if n.get("kind") == "narrative"
          and not n["in"] and not n["out"]]

    lines = ["# 孤立文档清单（连接层施工单）", ""]
    lines.append("> **口径分列**：知识节点（设定/模板/总览）孤立＝**真缺口**；")
    lines.append("> 叙事节点（正文）是线性叙事，本就不该有知识链 —— 不计施工量。")
    lines.append("")
    lines.append("| 项 | 知识节点 | 叙事节点 |")
    lines.append("|---|---|---|")
    lines.append(f"| 总数 | {s.get('knowledge_docs', 0):,} | {s.get('narrative_docs', 0):,} |")
    lines.append(f"| 孤立 | {s.get('knowledge_orphans', 0):,} | {s.get('narrative_orphans', 0):,} |")
    kr = s.get("knowledge_orphan_rate", 0)
    lines.append(f"| 孤立率 | **{kr}%** | — |")
    lines.append("")

    lines.append("## 施工单：知识节点（按项目）")
    lines.append("")
    byproj: dict[str, list] = defaultdict(list)
    for n in kn:
        byproj[n["project"] or "（仓根）"].append(n)
    for proj in sorted(byproj, key=lambda p: -len(byproj[p])):
        lines.append(f"### {proj}（{len(byproj[proj])}）")
        lines.append("")
        for n in byproj[proj][:limit]:
            lines.append(f"- `{n['path']}` — {n['title']}（{n['type']}）")
        lines.append("")

    lines.append("## 观察：叙事节点（不施工）")
    lines.append("")
    lines.append(f"> 共 {len(nv):,} 篇正文章节无知识链接 —— **这是正常的**。")
    lines.append("> 正文靠卷/章顺序与各项目的 `作品总览.md` 导航。")
    lines.append("")
    byproj2: dict[str, int] = defaultdict(int)
    for n in nv:
        byproj2[n["project"] or "（仓根）"] += 1
    lines.append("| 项目 | 无知识链接的正文数 |")
    lines.append("|---|---|")
    for proj, cnt in sorted(byproj2.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {proj} | {cnt} |")
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


# --------------------------------------------------------------------------
# 项目级 MOC 生成（LYT 枢纽节点法）
# --------------------------------------------------------------------------
#
# **为什么用 MOC 枢纽而不是逐篇建链**
# --------------------------------------
# 全库有 564 篇知识节点（设定/模板/总览）。若靠人工逐篇写 `[[双链]]`：
#   · 工作量巨大且必然半途而废；
#   · 更糟 —— 要在**正文/设定文件里**动手，违反「正文零改动」铁律。
#
# LYT 的标准解法是**枢纽节点（MOC）**：每个项目一份 MOC，由它给簇内所有
# 知识节点提供入链。节点文件**一个字节都不用改** —— 连接关系全部落在
# MOC 这一张索引页上（旁挂机制）。
#
# 效果：一次生成，项目内全部知识节点立刻脱离孤立；
# 且 MOC 是「活的导航页」，可人工补叙事。


def render_project_moc(project: str, nodes: list[dict], summary: dict,
                       root: str = "", links: list[dict] | None = None) -> str:
    """
    生成单个项目的 MOC（Markdown）。

    参数
    ----
    project: 项目名（一级目录名）
    nodes:   该项目的全部节点（图谱节点）
    summary: 全库统计（用于标注该项目的整体体量）
    links:   该项目的关联登记项（来自项目关联登记表）

    形态：按**角色层**分组（入口总览 / 设定 SSOT / 台账 / 方法与参考），
    每组内列出 wikilink。叙事节点（正文）单列，只给章节目录 —— 不建知识链。
    """
    kn = [n for n in nodes if n.get("kind") == "knowledge"]
    nv = [n for n in nodes if n.get("kind") == "narrative"]

    def by_role(role: str) -> list[dict]:
        return [n for n in kn if n.get("role") == role]

    lines: list[str] = []
    A = lines.append

    A(f"# MOC · {project}")
    A("")
    A(f"> **项目级内容地图**（LYT 枢纽节点）—— 由 `npm run pkm:build` 生成骨架。")
    A(f"> 本页给「{project}」的全部知识节点提供入链；节点文件本身**零改动**。")
    A("> 人工叙事请写在「## 人工补充」之后。")
    A("")

    # ---- 概览 ----
    A("## 概览")
    A("")
    A("| 项 | 值 |")
    A("|---|---|")
    A(f"| 文档总数 | {len(nodes):,} |")
    A(f"| 知识节点（设定/模板/总览） | {len(kn):,} |")
    A(f"| 叙事节点（正文） | {len(nv):,} |")
    A(f"| 净字数 | {summary.get('net_chars', 0):,} |")
    A("")

    # ---- 相关项目（来自项目关联登记表） ----
    if links:
        A("## 相关项目")
        A("")
        A("> 来自 `PKM/02-索引/项目关联登记表.md` —— 只登记**真的共享了什么**的关系。")
        A("> 题材相邻但设定独立的，不在此列（见 [[PKM/01-MOC/MOC-跨项目知识网络.md]] §四）。")
        A("")
        for rel in links:
            dst = rel.get("to", "")
            kind = rel.get("kind", "")
            shared = rel.get("shared", "")
            constraint = rel.get("constraint", "")
            moc_name = f"MOC-{dst}"
            A(f"### [[PKM/01-MOC/{moc_name}.md]] —— {dst}")
            A("")
            A(f"- **关系**：{kind}")
            if shared:
                A(f"- **共享**：{shared}")
            if constraint:
                A(f"- **硬约束**：{constraint}")
            A("")

    # ---- 入口总览 ----
    entries = by_role("入口总览")
    if entries:
        A("## 入口")
        A("")
        for n in entries:
            A(f"- [[{n['path']}]] —— {n['title']}")
        A("")

    # ---- 设定 SSOT ----
    ssot = [n for n in kn if n.get("type") == "设定"]
    if ssot:
        A("## 设定（SSOT · 单一事实源）")
        A("")
        for n in ssot:
            A(f"- [[{n['path']}]] —— {n['title']}（{n.get('net_chars', 0):,} 字）")
        A("")

    # ---- 台账 ----
    ledgers = [n for n in kn if n.get("type") == "台账"]
    if ledgers:
        A("## 台账")
        A("")
        for n in ledgers:
            A(f"- [[{n['path']}]] —— {n['title']}")
        A("")

    # ---- 方法与参考 ----
    rest = [n for n in kn if n not in ssot and n not in ledgers and n not in entries]
    if rest:
        A("## 方法 · 参考 · 其他")
        A("")
        for n in rest:
            A(f"- [[{n['path']}]] —— {n['title']}（{n.get('type', '')}）")
        A("")

    # ---- 叙事目录（不建知识链，仅导航） ----
    if nv:
        A("## 正文（叙事层 · 按顺序读，不建知识链）")
        A("")
        A(f"> 本项目共 {len(nv):,} 篇正文。正文是**线性叙事**，")
        A("> 靠卷/章顺序组织 —— 不参与知识连接，故此处只列目录不建双链。")
        A("")
        # 按目录分组
        by_dir: dict[str, list[dict]] = defaultdict(list)
        for n in nv:
            d = n["path"].rsplit("/", 1)[0] if "/" in n["path"] else ""
            by_dir[d].append(n)
        for d in sorted(by_dir):
            group = sorted(by_dir[d], key=lambda x: x["path"])
            A(f"**{d or '（仓根）'}**（{len(group)} 篇）")
            A("")
            # 章节目录用**相对链接**（可点击导航），不建知识双链。
            # 相对路径须相对 **MOC 文件自身所在目录**（PKM/01-MOC/），
            # 否则在 Obsidian / GitHub 里点不开 —— 索引器能解析不代表渲染器能。
            for n in group:
                fname = n["path"].rsplit("/", 1)[-1]
                rel = os.path.relpath(
                    os.path.join(root, n["path"]),
                    os.path.join(root, "PKM", "01-MOC"),
                ).replace(os.sep, "/")
                A(f"- [{fname}]({rel.replace(' ', '%20')})")
            A("")

    # ---- 人工补充 ----
    A("## 人工补充")
    A("")
    A("<!-- 这个项目最该记住的三件事？哪些设定互相冲突？下一个要写什么？ -->")
    A("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    g = build_graph(root)
    p, n = write_graph(g, os.path.join(root, "PKM", "graph.json"))
    print(f"图谱：{p}（{n} 字节）")
    s = g["summary"]
    print(f"文档 {s['docs']} ／ 出链 {s['total_links']} ／ 断链 {s['total_broken']}")
