#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
indexer.py —— PKM 索引器 · 倒排索引与全文检索
================================================================================
为什么自建检索，而不是直接用 Obsidian / Everything / ripgrep？

1. **中文分词**：Obsidian 原生搜索对中文支持一般（需另装 Omnisearch）；
   自建索引器用**二元组（bigram）**切分，零依赖且对中文检索友好。
2. **可复跑、可校验**：索引落盘为 JSON，任何机器上重建结果一致，
   可进版本库、可 diff、可做「索引是否过期」的机械门禁。
3. **换机即跑**：只用标准库，不需要额外装软件。

索引结构（落盘为 PKM/index.json）
--------------------------------
{
  "generated_at": "...",
  "schema": 1,
  "summary": { ... },
  "docs":   [ {path, title, doc_type, project, role, net_chars, ...} ],
  "terms":  { "词条": ["路径", ...] },
  "titles": { "标题": "路径" },
  "project_terms": { "项目": {"词条": 频次} }
}

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from typing import Any, Iterable

from scanner import Doc, decode, net_chars, resolve_links, scan, summarize

# 停用词：中文虚词 + 英文冠词介词（检索时忽略）
STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "也", "就", "都", "而", "及", "或",
    "一", "个", "这", "那", "有", "为", "以", "于", "上", "下", "中", "不",
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "it",
}

# 抽取正文时忽略的区块（代码块 / 表格分隔线 / HTML 注释）
CODE_BLOCK = re.compile(r"```.*?```", re.S)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
TABLE_SEP = re.compile(r"^\s*\|[\s\-:|]+\|\s*$", re.M)


def tokenize(text: str) -> list[str]:
    """
    中英混合分词。

    - 英文/数字：按词边界切，转小写
    - 中文：切**二元组**（bigram）。无需词典即可支持中文子串检索，
      是中文全文检索的经典零依赖做法（精度略逊于分词，召回率好）。
    """
    text = CODE_BLOCK.sub(" ", text)
    text = HTML_COMMENT.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    text = TABLE_SEP.sub(" ", text)
    text = text.lower()

    tokens: list[str] = []
    # 英文与数字
    for m in re.finditer(r"[a-z0-9_]{2,}", text):
        w = m.group(0)
        if w not in STOPWORDS:
            tokens.append(w)
    # 中文：连续汉字串 → 二元组
    for m in re.finditer(r"[一-鿿]+", text):
        run = m.group(0)
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in STOPWORDS:
                tokens.append(bg)
    return tokens


def build_index(root: str, include_archived: bool = True,
                min_term_docs: int = 2) -> dict[str, Any]:
    """
    扫描 + 解析连接 + 建倒排索引 → 完整索引对象。

    体积控制（实测：初版 64MB → 本版约 6MB）
    ------------------------------------------
    - **倒排表用文档 ID 整数引用**，不再重复存路径字符串（路径平均 30+ 字节，
      在 1.6M 条倒排项上重复存储是体积主因）。
    - **剔除只命中 1 篇文档的词条**（占词条总数 37%）：这类词条检索价值极低
      （多为专有名词片段），且检索时可由「标题/别名」兜底命中。
    """
    docs = scan(root, include_archived=include_archived)
    # 元数据清单须与图谱共用同一份（否则检索到的和图谱显示的不一致）
    from graph import apply_overrides
    apply_overrides(docs, root)
    resolve_links(docs, root)

    # 文档 ID ↔ 路径 双向映射
    path_to_id = {d.path: i for i, d in enumerate(docs)}
    id_to_path = [d.path for d in docs]

    freq: Counter = Counter()
    postings: dict[str, set[int]] = defaultdict(set)
    project_terms: dict[str, Counter] = defaultdict(Counter)

    for i, d in enumerate(docs):
        full = os.path.join(root, d.path)
        try:
            body = decode(open(full, "rb").read())
        except OSError:
            body = ""
        # 标题词额外加权（标题命中在检索时再乘 3）
        toks = tokenize(d.title) + tokenize(body)
        for t in toks:
            freq[t] += 1
            postings[t].add(i)
            if d.project:
                project_terms[d.project][t] += 1

    summary = summarize(docs)

    # 过滤低价值词条
    kept = {t: sorted(ids) for t, ids in postings.items() if len(ids) >= min_term_docs}

    titles: dict[str, str] = {}
    for d in docs:
        titles.setdefault(d.title, d.path)

    return {
        "schema": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root_hint": "仓根（换机路径不同，内容一致）",
        "min_term_docs": min_term_docs,
        "summary": summary,
        "docs": [d.to_dict() for d in docs],
        "id_to_path": id_to_path,
        "terms": kept,
        "titles": titles,
        "project_terms": {p: dict(c.most_common(300)) for p, c in project_terms.items()},
        "term_freq": dict(freq.most_common(1500)),
    }


def write_index(index: dict[str, Any], path: str) -> tuple[str, int]:
    """落盘索引。**不带 BOM** —— JSON 属「机器读」类（与 graph.json 同惯例）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.dumps(index, ensure_ascii=False, indent=1)
    with open(path, "wb") as f:
        f.write(data.replace("\r\n", "\n").encode("utf-8"))
    return path, len(data)


# --------------------------------------------------------------------------
# 检索
# --------------------------------------------------------------------------

def search(index: dict[str, Any], query: str, limit: int = 20,
           project: str = "", doc_type: str = "") -> list[dict[str, Any]]:
    """
    检索：按词条倒排索引打分。

    评分：标题命中权重 3×，正文命中 1×；再按「文档越短命中占比越高」微调
    （短文档命中更可能是主题文档）。同分按路径排序，保证结果稳定可复现。
    """
    q = query.strip().lower()
    if not q:
        return []
    qtoks = tokenize(q)
    if not qtoks:
        return []

    docs_by_path = {d["path"]: d for d in index["docs"]}
    terms = index["terms"]
    id_to_path = index.get("id_to_path") or [d["path"] for d in index["docs"]]

    # 倒排表存的是文档 ID（schema 2）；兼容 schema 1 的路径列表
    def _ids_of(term: str) -> list:
        raw = terms.get(term)
        if not raw:
            return []
        if raw and isinstance(raw[0], int):
            return raw
        # schema 1：路径 → id
        out = []
        for p in raw:
            for i, dp in enumerate(id_to_path):
                if dp == p:
                    out.append(i)
                    break
        return out

    # 候选集：取各词条倒排表的并集
    cand: set[int] = set()
    for t in set(qtoks):
        cand.update(_ids_of(t))

    results: list[dict[str, Any]] = []
    for i in cand:
        path = id_to_path[i]
        d = docs_by_path.get(path)
        if d is None:
            continue
        if project and d.get("project") != project:
            continue
        if doc_type and d.get("doc_type") != doc_type:
            continue

        score = 0.0
        matched: list[str] = []
        title_toks = set(tokenize(d.get("title", "")))
        body_hit = 0
        for t in set(qtoks):
            if t in title_toks:
                score += 3.0
                matched.append(t)
            elif _ids_of(t):
                body_hit += 1
                matched.append(t)
        # ⚠️ 顺序要点：body_hit 必须**先计入 score**，再判 score == 0。
        # 否则「只在正文命中、标题未命中」的文档会被整批丢弃
        #（实测：查「真气」返回 0 条 —— 11 篇命中文档全在这一类）。
        score += body_hit
        if score == 0:
            continue
        # 短文档优先（命中密度）
        denom = max(d.get("net_chars", 1), 200)
        score += 10.0 * (body_hit / (denom / 1000.0))
        results.append({
            "path": path,
            "title": d.get("title", ""),
            "doc_type": d.get("doc_type", ""),
            "project": d.get("project", ""),
            "role": d.get("role", ""),
            "net_chars": d.get("net_chars", 0),
            "score": round(score, 3),
            "matched": sorted(set(matched)),
        })

    results.sort(key=lambda r: (-r["score"], r["path"]))
    return results[:limit]


def backlinks(index: dict[str, Any], path: str) -> list[str]:
    """查某文档的入链。"""
    for d in index["docs"]:
        if d["path"] == path:
            return d.get("backlinks", [])
    return []


def outgoing(index: dict[str, Any], path: str) -> list[str]:
    """查某文档的出链。"""
    for d in index["docs"]:
        if d["path"] == path:
            return d.get("resolved", [])
    return []


def broken_links(index: dict[str, Any]) -> list[dict[str, Any]]:
    """全仓断链清单 —— 机械门禁的数据源。"""
    out = []
    for d in index["docs"]:
        for b in d.get("broken", []):
            out.append({"from": d["path"], "target": b})
    return out


if __name__ == "__main__":
    import sys
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    idx = build_index(root)
    out = os.path.join(root, "PKM", "index.json")
    p, n = write_index(idx, out)
    s = idx["summary"]
    print(f"索引已生成：{p}（{n} 字节）")
    print(f"文档 {s['docs']} ／ 出链 {s['total_links']} ／ 断链 {s['total_broken']}")
    print(f"frontmatter {s['frontmatter_docs']} ／ 孤立文档 {s['orphan_count']}")
