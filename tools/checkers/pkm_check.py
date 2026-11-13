#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pkm_check.py —— PKM 连接层检查器（适配器）
================================================================================
把「PKM 索引器的健康度」包成 `tools/checker_protocol.py` 定义的协议 JSON，
从而接入既有的 Cordis 检查器流水线（`npm run check`）。

**闸门口径**（与本仓既有纪律一致）
----------------------------------
- **ERROR**：连接层结构性缺陷 —— 断链、索引与图谱不一致。
  这些会让「知识网络」给出错误答案，必须阻断。
- **WARN**：需要人工定性的存量问题 —— 孤立文档比例过高（连接层还没铺开）。
  孤立不是错误，是**施工单**；但比例过高说明连接层该补了。
- **INFO**：观察项 —— 规模统计。

**只读源文件**：本检查器只读仓内文件，只写报告目录（与《工作区规范》§八 4 同源）。

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.normpath(os.path.join(HERE, ".."))
PKM_DIR = os.path.join(TOOLS_DIR, "pkm")
# 协议模块在 tools/、PKM 内核在 tools/pkm/ —— 两处都要能导入
for p in (TOOLS_DIR, PKM_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from checker_protocol import emit, run  # noqa: E402


def check(root: str) -> list[dict]:
    """执行连接层体检，产出 findings。"""
    from graph import build_graph  # noqa: PLC0415

    findings: list[dict] = []
    g = build_graph(root)
    s = g["summary"]
    nodes = g["nodes"]

    # ---- ERROR：断链 ----
    # 判定口径：**目标在仓内真实不存在**才算断链。
    # 指向目录（以 / 结尾）、指向非 Markdown 资源（.html/.svg/.docx…）的链接
    # 不是连接缺陷 —— 它们在索引范围之外，但链接本身有效。
    # （实测：README 的 4 条「断链」全是这类误判，真实断链为 0。）
    md_paths = {n["path"] for n in nodes}
    for n in nodes:
        for b in n["broken"]:
            if b.endswith("/"):
                continue                                  # 目录型链接
            if os.path.exists(os.path.join(root, b)):
                continue                                  # 目标存在，只是非 Markdown
            if not b.lower().endswith(".md"):
                continue                                  # 非 Markdown 资源，不在本检查器职责内
            findings.append({
                "severity": "error",
                "category": "连接",
                "code": "PKM-BROKEN-LINK",
                "file": n["path"],
                "line": 0,
                "snippet": f"[[{b}]]",
                "message": f"断链：目标「{b}」解析不到",
                "suggestion": "修正链接目标，或确认目标文件是否存在（改名后链接需同步）",
            })

    # ---- ERROR：索引与图谱不一致 ----
    idx_path = os.path.join(root, "PKM", "index.json")
    gph_path = os.path.join(root, "PKM", "graph.json")
    if not os.path.exists(gph_path):
        findings.append({
            "severity": "error", "category": "连接", "code": "PKM-NO-GRAPH",
            "file": "PKM/graph.json", "line": 0, "snippet": "",
            "message": "图谱不存在 —— 连接层尚未建立",
            "suggestion": "运行 `npm run pkm:build`",
        })
    if not os.path.exists(idx_path):
        findings.append({
            "severity": "warn", "category": "连接", "code": "PKM-NO-INDEX",
            "file": "PKM/index.json", "line": 0, "snippet": "",
            "message": "索引缓存不存在 —— 检索将不可用",
            "suggestion": "运行 `npm run pkm:build`（索引缓存不入库，属正常状态）",
        })

    # ---- WARN：知识节点孤立比例 ----
    # 口径：**以知识节点为分母**（设定/模板/总览）。
    # 叙事节点（正文）是线性叙事，本就不该有知识链 —— 混算会虚高问题
    # （实测：混算 96.3%，只算知识节点才是真实缺口）。
    kn = max(s.get("knowledge_docs", 0), 1)
    ratio = s.get("knowledge_orphans", 0) * 100.0 / kn
    if ratio > 5:
        findings.append({
            "severity": "warn", "category": "连接", "code": "PKM-ORPHAN-RATIO",
            "file": "PKM/孤立文档清单.md", "line": 0, "snippet": "",
            "message": (
                f"孤立知识节点 {s.get('knowledge_orphans', 0)} 篇"
                f"（{ratio:.1f}%）—— 连接层待补"
            ),
            "suggestion": "从 PKM/孤立文档清单.md 取施工单，按项目分批补连接",
        })

    # ---- INFO：规模观察 ----
    findings.append({
        "severity": "info", "category": "连接", "code": "PKM-SCALE",
        "file": "PKM/graph.json", "line": 0, "snippet": "",
        "message": (
            f"文档 {s['docs']} ／ 出链 {s['total_links']} ／ 断链 {s['total_broken']} ／ "
            f"frontmatter {s['frontmatter_docs']} ／ 标签 {s['tag_count']} ／ "
            f"知识节点 {s.get('knowledge_docs', 0)}（孤立 {s.get('knowledge_orphans', 0)}，"
            f"{s.get('knowledge_orphan_rate', 0)}%）／ "
            f"叙事节点 {s.get('narrative_docs', 0)}（孤立 {s.get('narrative_orphans', 0)}）"
        ),
        "suggestion": "—",
    })

    return findings


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    code = run("pkm", check, os.path.abspath(root))
    sys.exit(code)
