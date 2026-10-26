#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bible_parser.py — 从《废土旅法师》小说工程 bible/*.md 解析出结构化 JSON 数据层。

设计原则
--------
1. 零三方依赖，只用 Python 标准库（re / json / pathlib / argparse）。
2. **只读**：绝不修改源 md 文件。解析结果写入 engine/data/dataset.json。
3. **可审计**：每个解析步骤记录 ok / degraded / failed，产出 parse_report，
   让人知道哪些字段是真解析出来的、哪些是兜底填的、哪些没抓到。
4. **单一事实源**：源文件路径可通过 --root 覆盖，默认指向桌面小说工程。

用法
----
    python bible_parser.py                     # 解析并写 dataset.json
    python bible_parser.py --root "D:/小说"    # 指定工程根
    python bible_parser.py --print-report      # 只打印解析报告
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# 解析报告收集器
# --------------------------------------------------------------------------

REPORT: list[dict[str, Any]] = []


def note(step: str, status: str, detail: str = "", count: int | None = None) -> None:
    """记录一条解析审计条目。status ∈ {ok, degraded, failed, skipped}"""
    entry = {"step": step, "status": status, "detail": detail}
    if count is not None:
        entry["count"] = count
    REPORT.append(entry)
    flag = {"ok": "[ ok ]", "degraded": "[warn]", "failed": "[FAIL]", "skipped": "[skip]"}[status]
    print(f"  {flag} {step}" + (f"  ({count})" if count is not None else "") + (f"  {detail}" if detail else ""))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------
# 通用 markdown 工具
# --------------------------------------------------------------------------

def md_tables(text: str) -> list[list[list[str]]]:
    """抽取所有 markdown 表格，返回 [[row, row, ...], ...]。"""
    tables: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            # 跳过对齐行 |---|---|
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue
            cur.append(cells)
        else:
            if len(cur) >= 2:
                tables.append(cur)
            cur = []
    if len(cur) >= 2:
        tables.append(cur)
    return tables


def find_section(text: str, start_pattern: str) -> str:
    """截取从匹配 start_pattern 的标题行到下一个**同级或更高级**标题之间的内容。

    注意：结束边界要排除比 start 更高级的标题（level-1），否则
    `### 3.5` 会一路吞到下一个 `##`，把无关章节也吃进来。
    """
    m = re.search(start_pattern, text, re.M)
    if not m:
        return ""
    start = m.start()
    level = len(re.match(r"(#+)", m.group(0)).group(1))
    # 结束于 level-1 .. level 级标题（即同级或更高级）
    nxt = re.search(rf"\n#{{1,{level}}}\s", text[m.end():])
    return text[start: m.end() + (nxt.start() if nxt else len(text))]


def to_int(s: str, default: int | None = None) -> int | None:
    m = re.search(r"-?\d+", str(s).replace(",", ""))
    return int(m.group()) if m else default


def to_pct_range(s: str) -> list[int]:
    """'3-5%' -> [3,5]；'100%+' -> [100,100]；'0' -> [0,0]

    两处必要的防御（否则会静默产出错误数据）：

    1. **剥离括号出处**。源表里坠影级写的是
       `**面板判定为"？？？"——不可击杀取火花**（第 36-37 章）`，
       若不剥离，`\\d+` 会抓到 36/37 当成火花百分比——
       面板会算出"S+ 级刷出 36% 火花"，与 world-bible §7
       「不可击杀，只能送终」直接矛盾。

    2. **不可击杀哨兵**。引擎 `spark_for_tier` 以 `lo < 0`
    作为「该级不可取火花」的判据，故此处返回 [-1, -1]。
    """
    raw = str(s)

    # (1) 剥掉括号里的出处/备注，数字只从正文部分取
    body = re.sub(r"[（(][^）)]*[）)]", " ", raw)

    # (2) 不可击杀标记 -> 哨兵
    if re.search(r"不可击杀|不可取|送终|[？?]{2,}", body):
        return [-1, -1]

    nums = re.findall(r"\d+", body)
    if not nums:
        return [0, 0]
    lo = int(nums[0])
    hi = int(nums[1]) if len(nums) > 1 else lo
    return [lo, hi]


# --------------------------------------------------------------------------
# 1. 面板系统 §2f —— 核心：解锁总表
# --------------------------------------------------------------------------

SPARK_UNLOCK_ROWS = [
    # (火花%, 功能名, 效果, 落点)
    (4, "面板首次显现", "五维属性/天赋/技艺/火花槽可见；击杀异族开始计数", "第一卷 5"),
    (20, "异族感知（被动 Lv.1）", "模糊感知半径约 10 米内异族的存在与大致强度", "第一卷 12"),
    (25, "属性加点", "每满 10% 火花获得 1 点自由属性", "第一卷 16"),
    (30, "属性点入账（第 2 点）", "灵敏 4→5", "第一卷 17"),
    (40, "属性点入账（第 3 点）", "精神 4→5", "第一卷 21 前后"),
    (45, "属性突破", "可突破软上限 1 点（后续突破消耗翻倍）；体质 5→6", "第一卷 22"),
    (50, "火花共鸣", "感知火花源或接触过其他位面的存在；判定等级；可接收碎片意象", "第一卷 25"),
    (54, "异族弱点解析（Lv.1）", "锁定目标后提示弱点位置与出手时机", "第一卷 27"),
    (58, "位面残影", "偶发 0.3 秒位面闪现，不可控", "第一卷 30"),
    (100, "点燃（鹏洛克·新晋）+ 位面坐标感知 + 代偿 + 法力池（空）", "火花封顶；力量增长改走法力路径", "第一卷 37"),
]


def parse_panel(path: Path) -> dict:
    """解析 §2f 系统面板 + 解锁总表。"""
    if not path.exists():
        note("面板系统 §2f", "failed", f"文件不存在: {path}")
        return {}
    text = read_text(path)
    sec = find_section(text, r"^## 2f\..*$")
    if not sec:
        note("面板系统 §2f", "failed", "未找到 §2f 章节标题")
        return {}

    # 尝试从表格抓解锁总表，失败则用内置基线（并标 degraded）
    unlocks: list[dict] = []
    tables = md_tables(sec)
    unlocked_tbl = None
    for t in tables:
        head = " ".join(t[0])
        if "火花" in head and "解锁功能" in head:
            unlocked_tbl = t
            break
    if unlocked_tbl:
        for row in unlocked_tbl[1:]:
            if len(row) < 4:
                continue
            # 火花列可能是 "4%" / "100%" / "—"（点燃后追加项，非火花阈值）
            raw = row[0].strip()
            if re.search(r"\d", raw):
                sp = to_pct_range(raw)
                spark: int | None = sp[0]
            else:
                spark = None       # 「—」＝不占火花阈值，属点燃后追加解锁
            unlocks.append({
                "spark": spark,
                "sparkRaw": raw,
                "name": row[1].replace("*", "").strip(),
                "effect": row[2].strip(),
                "chapter": row[3].strip(),
            })
        n_thr = sum(1 for u in unlocks if u["spark"] is not None)
        n_post = sum(1 for u in unlocks if u["spark"] is None)
        note("面板解锁总表", "ok", f"火花阈值 {n_thr} 条 + 点燃后追加 {n_post} 条", len(unlocks))
        if n_post:
            note("点燃后追加解锁", "ok", "已并入 unlocks（spark=null）", n_post)
    else:
        for sp, name, eff, ch in SPARK_UNLOCK_ROWS:
            unlocks.append({"spark": sp, "sparkRaw": f"{sp}%", "name": name, "effect": eff, "chapter": ch})
        note("面板解锁总表", "degraded", "§2f 表格未命中，回落到内置基线（10 条）", len(unlocks))

    # 点燃后的追加解锁已在 unlocks 内以 spark=null 标记，这里只做兜底：
    # 若表格解析失败且走了内置基线，则此处不追加。
    post_ignite: list[dict] = [u for u in unlocks if u.get("spark") is None]
    note("点燃后追加解锁", "skipped", "已由解锁总表统一承载") if not post_ignite else None

    # 终态属性（第二卷末）
    attrs = {"体质": 18, "根骨": 15, "灵敏": 16, "精神": 24, "悟性": 20}
    level = "鹏洛克·位面行走者"
    ma = re.search(r"属性：体质(\d+)/根骨(\d+)/灵敏(\d+)/精神(\d+)/悟性(\d+)", sec)
    if ma:
        attrs = {"体质": int(ma.group(1)), "根骨": int(ma.group(2)), "灵敏": int(ma.group(3)),
                 "精神": int(ma.group(4)), "悟性": int(ma.group(5))}
        note("终态五维属性", "ok", str(attrs))
    else:
        note("终态五维属性", "degraded", "正则未命中，使用事实基线默认值", 5)

    skills = []
    ms = re.search(r"已学技能：([^\n]+)", sec)
    if ms:
        for tok in re.split(r"[,，]", ms.group(1)):
            tok = tok.strip().strip("（）() ")
            if tok:
                skills.append(tok)
        note("已学技能", "ok", f"{len(skills)} 项", len(skills))
    else:
        note("已学技能", "degraded", "未解析到技能行")

    return {
        "level": level,
        "attributes": attrs,
        "attrsBaseline": {"体质": 4, "根骨": 4, "灵敏": 4, "精神": 4, "悟性": 4},
        "sparkState": "已点燃·不再增长",
        "igniteChapter": 37,
        "skills": skills,
        "talent": "铁骨（被动——骨骼密度略高于常人，抗打击能力小幅提升）",
        "manaTendency": ["蓝（知识/理性）", "黑（代价/终结）"],
        "planeCoords": 2,
        "voidToleranceMin": 8,
        "grayLineCells": 35,
        "unlocks": unlocks,
        "postIgniteUnlocks": post_ignite,
    }


# --------------------------------------------------------------------------
# 2. 变异生物图鉴 + 等级谱系
# --------------------------------------------------------------------------

def parse_creatures(path: Path) -> dict:
    if not path.exists():
        note("变异生物图鉴", "failed", f"文件不存在: {path}")
        return {}
    text = read_text(path)
    sec = find_section(text, r"^## 7\..*$")
    if not sec:
        note("变异生物图鉴", "failed", "未找到 §7")
        return {}

    bestiary: list[dict] = []
    tiers: list[dict] = []

    for t in md_tables(sec):
        head = " ".join(t[0])
        if "打法" in head or "火花" in head and "等级" in head:
            for row in t[1:]:
                if len(row) < 4:
                    continue
                bestiary.append({
                    "name": row[0].replace("*", "").strip(),
                    "tier": row[1].strip(),
                    "feature": row[2].strip(),
                    "sparkRaw": row[3].strip(),
                    "sparkRange": to_pct_range(row[3]),
                    "source": row[4].strip() if len(row) > 4 else "",
                })
        elif "判据" in head:
            for row in t[1:]:
                if len(row) < 4:
                    continue
                tiers.append({
                    "tier": row[0].replace("*", "").strip(),
                    "name": row[1].strip(),
                    "criteria": row[2].strip(),
                    "sparkRaw": row[3].strip(),
                    "sparkRange": to_pct_range(row[3]),
                })

    if bestiary:
        note("变异生物图鉴", "ok", "", len(bestiary))
    else:
        note("变异生物图鉴", "failed", "未抓到图鉴表")
    if tiers:
        note("变异等级谱系", "ok", "", len(tiers))
    else:
        note("变异等级谱系", "failed", "未抓到谱系表")

    return {"bestiary": bestiary, "tiers": tiers}


# --------------------------------------------------------------------------
# 3. 位面体系（§3.5）
# --------------------------------------------------------------------------

def parse_planes(path: Path) -> dict:
    if not path.exists():
        note("位面体系 §3.5", "failed", f"文件不存在: {path}")
        return {}
    text = read_text(path)
    sec = find_section(text, r"^### 3\.5\s.*$")
    if not sec:
        note("位面体系 §3.5", "failed", "未找到 §3.5")
        return {}

    layers: list[dict] = []
    color_planes: list[dict] = []
    for t in md_tables(sec):
        head = " ".join(t[0])
        if "后缀" in head and "判据" in head:
            for row in t[1:]:
                if len(row) < 3:
                    continue
                raw = row[1].strip()
                # 先剥 ** 加粗，再剥括号注释。
                # 顺序不能反：`re.sub(r"[*（(].*", "", "**光桥墟**（实验体故乡）")`
                # 会从第一个 `*` 一直吃到结尾，把名字本身也清空。
                name = raw.replace("*", "")
                name = re.sub(r"[（(].*$", "", name).strip()
                # 「五色位面」是分类标签而非专名，不进白名单
                if not name or name.endswith("位面") or name == "下表":
                    name = ""
                layers.append({
                    "layer": row[0].replace("*", "").strip(),
                    "name": name,
                    "rawName": raw,
                    "suffix": row[2].strip(),
                    "criteria": row[3].strip() if len(row) > 3 else "",
                    "status": row[4].strip() if len(row) > 4 else "",
                })
        elif "DND 原型" in head or "句判词" in head:
            for row in t[1:]:
                if len(row) < 3:
                    continue
                color_planes.append({
                    "color": row[0].strip(),
                    "name": row[1].replace("*", "").strip(),
                    "dndProto": row[2].strip(),
                    "faction": row[3].strip() if len(row) > 3 else "",
                    "epigram": row[4].strip() if len(row) > 4 else "",
                })

    note("位面分层命名表", "ok" if layers else "failed", "", len(layers))
    note("五色外层位面", "ok" if color_planes else "failed", "", len(color_planes))

    # 耐受与代偿递增表
    tolerance: list[dict] = []
    tt = re.search(r"#### 耐受与代偿的卷间递增表.*?\n(\|.+\|)", sec, re.S)
    for t in md_tables(sec):
        head = " ".join(t[0])
        if "耐受上限" in head or ("卷" in head and "分钟" in " ".join(t[1][0] if len(t) > 1 else [])):
            for row in t[1:]:
                if len(row) < 3:
                    continue
                mins = to_pct_range(row[1])
                mult = re.search(r"(\d+)", row[2])
                tolerance.append({
                    "volume": row[0].strip(),
                    "voidMin": mins[1] if mins[1] else mins[0],
                    "voidRaw": row[1].strip(),
                    "blackMult": int(mult.group(1)) if mult else 0,
                })
            break
    if tolerance:
        note("虚空耐受/代偿递增表", "ok", "", len(tolerance))
    else:
        note("虚空耐受/代偿递增表", "degraded", "未解析到递增表，机扫将跳过跨卷校验")

    # 命名三铁律
    rules = re.findall(r"^\d+\.\s*\*\*(.+?)\*\*[:：]\s*(.+)$", sec, re.M)
    note("位面命名铁律", "ok" if rules else "degraded", f"{len(rules)} 条", len(rules))

    return {
        "layers": layers,
        "colorPlanes": color_planes,
        "toleranceTable": tolerance,
        "namingRules": [{"title": a, "text": b} for a, b in rules],
    }


# --------------------------------------------------------------------------
# 4. 世界规则 R1-R15（从标尺文件抽，这是机扫的规则源）
# --------------------------------------------------------------------------

def parse_rules(path: Path) -> list[dict]:
    if not path.exists():
        note("世界规则 R1-R15", "failed", f"文件不存在: {path}")
        return []
    text = read_text(path)
    sec = find_section(text, r"^## 一、物理规则.*$")
    rules: list[dict] = []
    for t in md_tables(sec):
        head = " ".join(t[0])
        if "可判定形式" in head or "规则" in head:
            for row in t[1:]:
                if len(row) < 2:
                    continue
                rid = row[0].replace("*", "").strip()
                m = re.match(r"(R\d+)", rid)
                rules.append({
                    "id": m.group(1) if m else rid,
                    "name": rid,
                    "judgement": row[1].strip(),
                    "source": row[2].strip() if len(row) > 2 else "",
                })
    # 信息权限红线
    leaks: list[dict] = []
    sec4 = find_section(text, r"^## 四、信息权限红线.*$")
    for t in md_tables(sec4):
        for row in t[1:]:
            if len(row) < 2:
                continue
            raw = row[1]
            # 取「不得早于」栏里出现的**最小章号**作为该真相的解禁章。
            # 形如「第36-37章」→ 36；「第37章后」→ 37；「第三卷127章」→ 127。
            nums = [int(n) for n in re.findall(r"(\d+)\s*章", raw)]
            vol_hint = re.search(r"第([一二三四五])卷", raw)
            if vol_hint and nums:
                vol_no = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}[vol_hint.group(1)]
                # 卷 → 近似章号（91/141/181 为各卷起点，按偏移折算）
                approx = {1: 1, 2: 91, 3: 141, 4: 181, 5: 221}[vol_no]
                nums.append(approx + nums[0] - 1)
            leaks.append({
                "truth": row[0].strip(),
                "notBefore": raw.strip(),
                "minChapter": min(nums) if nums else 0,
            })
    note("世界规则 R*", "ok" if rules else "failed", "", len(rules))
    note("信息权限红线", "ok" if leaks else "degraded", "", len(leaks))
    return rules, leaks


# --------------------------------------------------------------------------
# 5. 伏笔台账 plot-board
# --------------------------------------------------------------------------

def parse_plot_board(path: Path) -> list[dict]:
    if not path.exists():
        note("伏笔台账", "failed", f"文件不存在: {path}")
        return []
    text = read_text(path)
    items: list[dict] = []
    seen = set()

    # 形如：- F1：描述 — 埋于：第1卷 — 状态：已回收（...）
    pat = re.compile(
        r"^-\s*\*{0,2}([FL]\d+|情感\s*E\d+|E\d+)\*{0,2}[：:]\s*(.+?)\s+—\s*埋于：\s*(.+?)\s+—\s*状态：\s*(.+?)\s*$",
        re.M,
    )
    for m in pat.finditer(text):
        key = canon_thread_id(m.group(1))
        if key in seen:
            continue
        seen.add(key)
        status_raw = m.group(4)
        items.append({
            "id": key,
            "desc": m.group(2).strip().replace("**", ""),
            "plantedAt": m.group(3).strip(),
            "status": classify_status(status_raw),
            "statusRaw": status_raw.strip(),
        })

    # 简写形式：- L1：xxx — 状态：已收（...）
    pat2 = re.compile(r"^-\s*\*{0,2}([FL]\d+)\*{0,2}[：:]\s*(.+?)\s+—\s*状态：\s*(.+?)\s*$", re.M)
    for m in pat2.finditer(text):
        key = canon_thread_id(m.group(1))
        if key in seen:
            continue
        seen.add(key)
        status_raw = m.group(3)
        items.append({
            "id": key,
            "desc": m.group(2).strip().replace("**", ""),
            "plantedAt": "",
            "status": classify_status(status_raw),
            "statusRaw": status_raw.strip(),
        })

    note("伏笔台账", "ok" if items else "failed", f"F/L/E 编号去重后 {len(items)} 条", len(items))
    return items


def classify_status(s: str) -> str:
    s = s.replace("**", "")
    if "已回收" in s or "已收" in s or "已兑现" in s or "已启用" in s:
        return "已回收"
    if "推进中" in s:
        return "推进中"
    if "待回收" in s:
        return "待回收"
    return "未知"


def canon_thread_id(raw: str) -> str:
    """归一化伏笔编号。

    plot-board 里同一条线会写两种形式：`E1：变异蛋白棒事件…` 与
    `情感 E1：前世无人收尸…`。后者是「情感线 E1」，与前者并非同一条，
    但为了让活跃线统计不重复计数，这里统一去掉「情感」前缀后加后缀区分。
    """
    raw = raw.strip()
    m = re.match(r"^情感\s*([A-Z]\d+)$", raw)
    if m:
        return f"{m.group(1)}·情感"
    return raw


# --------------------------------------------------------------------------
# 6. 代价弧四维 + 已烧清单
# --------------------------------------------------------------------------

def parse_cost_arc(path: Path) -> dict:
    if not path.exists():
        note("代价弧四维", "failed", f"文件不存在: {path}")
        return {}
    text = read_text(path)
    dims: list[dict] = []
    for t in md_tables(text):
        head = " ".join(t[0])
        if "定义" in head and "年龄段" in head and "维度" in head:
            for row in t[1:]:
                if len(row) < 6:
                    continue
                md = re.search(r"(D\d)", row[0])
                dims.append({
                    "id": md.group(1) if md else row[0].strip(),
                    "name": row[0].replace("*", "").strip(),
                    "definition": row[1].strip(),
                    "ageRange": row[2].strip(),
                    "memory": row[3].strip(),
                    "judgeFact": row[4].strip(),
                    "landing": row[5].strip(),
                })
            break

    burned: list[dict] = []
    for t in md_tables(text):
        head = " ".join(t[0])
        if "已兑现症状" in head or ("章" in head and "维度" in head):
            for row in t[1:]:
                if len(row) < 4:
                    continue
                burned.append({
                    "seq": to_int(row[0], 0),
                    "content": row[1].strip().replace("**", ""),
                    "chapter": row[2].strip(),
                    "symptom": row[3].strip().replace("**", ""),
                    "done": "☑" in row[3] or "已烧" in row[3],
                })
            break

    note("代价弧四维", "ok" if dims else "degraded", "", len(dims))
    note("已烧清单", "ok" if burned else "degraded", "", len(burned))
    return {"dimensions": dims, "burned": burned}


# --------------------------------------------------------------------------
# 7. 术语锁定表
# --------------------------------------------------------------------------

def parse_terminology(path: Path) -> list[dict]:
    if not path.exists():
        note("术语锁定表", "failed", f"文件不存在: {path}")
        return []
    text = read_text(path)
    sec = find_section(text, r"^## 五、术语锁定表.*$")
    terms: list[dict] = []
    for t in md_tables(sec):
        head = " ".join(t[0])
        if "常见错写" in head or "禁止" in head:
            for row in t[1:]:
                if len(row) < 2:
                    continue
                name = row[0].strip().replace("*", "")
                wrong = row[2].strip() if len(row) > 2 else ""
                terms.append({
                    "name": name,
                    "note": row[1].strip(),
                    "forbidden": [w.strip() for w in re.split(r"[、,，]", wrong) if w.strip()],
                })
    note("术语锁定表", "ok" if terms else "degraded", "", len(terms))
    return terms


# --------------------------------------------------------------------------
# 8. 时间轴
# --------------------------------------------------------------------------

def parse_timeline(path: Path) -> list[dict]:
    if not path.exists():
        note("时间轴", "failed", f"文件不存在: {path}")
        return []
    text = read_text(path)
    events: list[dict] = []
    # 事件正文与「（出处：第N章）」之间**没有空格**，故用 \s* 而非 \s+
    pat = re.compile(r"^-\s*(T\d+)[：:]\s*(.+?)\s+—\s*事件：\s*(.+?)\s*（出处：\s*(.+?)\s*）\s*$", re.M)
    for m in pat.finditer(text):
        events.append({
            "id": m.group(1),
            "when": m.group(2).strip(),
            "event": m.group(3).strip(),
            "source": m.group(4).strip(),
            "chapter": to_int(m.group(4), 0),
        })
    events.sort(key=lambda e: e["id"])
    note("时间轴", "ok" if events else "failed", "", len(events))
    return events


# --------------------------------------------------------------------------
# 9. 角色档案
# --------------------------------------------------------------------------

def parse_character_cards(char_dir: Path) -> list[dict]:
    """解析 bible/characters/ 下的**分文件角色卡**（权威源）。

    为什么不只依赖 一致性核查/角色档案.md：
      那份档案停在第一卷（11 人），第五卷新增的陆平、王级异族、花押主人、
      誊抄人、黑石帮抱臂者、李氏残余，以及每张卡上的「外传适配」评级
      全部不在里面。外传规划要靠这些卡，缺了就没法在面板上核对。

    约定：
      文件名去掉 .md 即角色名；`index.md` / 下划线开头的文件不是角色卡，跳过。

    两代卡格式并存，抽内核要都认：
      新卡：一行`| 一句话内核 | … |`
      老卡：`## A. 基础档案` 表，键名各卡不同（记忆点/一句话/功能定位/执念…）
    内核抽不到时回退到「记忆点 → 功能定位 → 执念 → 性格」的顺序，
    宁可给一句人物速写，也不要留空——面板上空白卡比没有卡更糟。
    """
    if not char_dir.exists():
        note("角色卡", "degraded", f"目录不存在: {char_dir}")
        return []

    CORE_KEYS = (
        "一句话内核", "内核", "记忆点（首登场）", "记忆点", "首登场记忆点",
        "功能定位", "一句话", "执念", "软肋", "性格", "定位",
    )

    cards: list[dict] = []
    for p in sorted(char_dir.glob("*.md")):
        stem = p.stem
        if stem == "index" or stem.startswith("_"):
            continue
        text = read_text(p)

        core = ""
        profile = ""
        for key in CORE_KEYS:
            m = re.search(rf"^\|\s*{re.escape(key)}\s*\|(.+?)\|\s*$", text, re.M)
            if not m:
                continue
            val = re.sub(r"\s+", " ", m.group(1)).strip().strip("*")
            if not val:
                continue
            if not core:
                core = val
            if key in ("基础档案", "身份", "现状", "姓名", "性别 / 年龄"):
                profile = val

        # 外传适配评级：★★★★★ / ★★★★☆ / 结构性角色
        rating = ""
        rm = re.search(r"(★★★★★|★★★★☆|★★★☆☆|结构性角色)", text)
        if rm:
            rating = rm.group(1)

        # 写作纪律条目数：衡量这张卡约束了多少条红线
        # 标题实测六种写法：写作纪律 / D. 写作纪律 / E2. 写作纪律… /
        # 写作纪律（写他之前必读） / 二、写作纪律 / 弧光与纪律
        # 另有卡把纪律写在「### 外传适配」下的嵌套列表里（如瘦猴），故回退匹配它
        NUM_ITEM = r"^\s*(?:\d+|[一二三四五六七八九十]+)[.、]\s"
        discipline = 0

        # 优先找显式的「写作纪律」块
        dm = re.search(
            r"^#{2,4}\s*(?:[A-Za-z]\d*|[\d]+|[一二三四五六七八九十]+)?\s*[.、]?\s*写作纪律",
            text, re.M,
        )
        if dm:
            tail = text[dm.end():]
            nxt = re.search(r"^#{1,4}\s", tail, re.M)
            block = tail[: nxt.start()] if nxt else tail
            discipline = len(re.findall(NUM_ITEM, block, re.M))

        # 回退：「弧光与纪律」块
        if discipline == 0:
            dm = re.search(
                r"^#{2,4}\s*(?:[A-Za-z]\d*|[\d]+|[一二三四五六七八九十]+)?\s*[.、]?\s*弧光与纪律",
                text, re.M,
            )
            if dm:
                tail = text[dm.end():]
                nxt = re.search(r"^#{1,2}\s", tail, re.M)   # 只到二级标题为止
                block = tail[: nxt.start()] if nxt else tail
                discipline = len(re.findall(NUM_ITEM, block, re.M))

        # 再回退：「外传适配」块（纪律以嵌套编号列表形式写在里面）
        if discipline == 0:
            dm = re.search(r"^#{2,4}\s*外传适配", text, re.M)
            if dm:
                tail = text[dm.end():]
                nxt = re.search(r"^#{1,2}\s", tail, re.M)
                block = tail[: nxt.start()] if nxt else tail
                discipline = len(re.findall(NUM_ITEM, block, re.M))

        # 关键行为条数（| 章 | … | 表格行）
        beats = len(re.findall(r"^\|\s*\*{0,2}\d{1,3}\*{0,2}\s*\|", text, re.M))

        cards.append({
            "name": stem,
            "core": core,
            "profile": profile,
            "spinOffRating": rating,
            "disciplineCount": discipline,
            "beatCount": beats,
            "dead": bool(re.search(r"(已死|死于|死亡)", text[:400])),
            "source": f"bible/characters/{p.name}",
            "excerpt": re.sub(r"\s+", " ", text)[:220],
        })

    note("角色卡", "ok" if cards else "failed", "", len(cards))
    return cards


def parse_characters(path: Path) -> list[dict]:
    if not path.exists():
        note("角色档案", "failed", f"文件不存在: {path}")
        return []
    text = read_text(path)
    chars: list[dict] = []
    for m in re.finditer(r"^## \d+\.\s*(.+?)\s*$", text, re.M):
        name = m.group(1).strip()
        start = m.end()
        nxt = re.search(r"^## ", text[start:], re.M)
        body = text[start: start + (nxt.start() if nxt else len(text))]
        age = ""
        ma = re.search(r"年[龄龄段][^\n]{0,10}?(\d{1,2})", body)
        if ma:
            age = ma.group(1)
        dead = "已死" in body or "第38章" in body and "死" in body
        chars.append({
            "name": name,
            "age": age,
            "dead": bool(re.search(r"(已死|死于|死亡)", body)),
            "excerpt": re.sub(r"\s+", " ", body)[:220],
        })
    note("角色档案", "ok" if chars else "failed", "", len(chars))
    return chars


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def _default_root() -> Path:
    """推导源工程根（小说根目录），不写死绝对路径。

    本文件位于 <小说根>/wasteland-panel/engine/bible_parser.py，
    故向上一层两级即为小说根。允许用 BIBLE_ROOT 环境变量覆盖。
    旧实现写死 C:\\Users\\Administrator\\Desktop\\小说，换机即失效。
    """
    env = os.environ.get("BIBLE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent.parent


DEFAULT_ROOT = _default_root()


def build(root: Path) -> dict:
    print(f"\n源工程根: {root}")
    if not root.exists():
        print(f"[FAIL] 源工程不存在: {root}")
        sys.exit(2)

    bible = root / "bible"
    check = root / "一致性核查"
    ref = root / "设定与参考"

    print("\n[1/10] 解析面板系统 §2f …")
    panel = parse_panel(bible / "world-bible.md")
    print("[2/10] 解析变异图鉴与谱系 …")
    creatures = parse_creatures(bible / "world-bible.md")
    print("[3/10] 解析位面体系 §3.5 …")
    planes = parse_planes(bible / "world-bible.md")
    print("[4/10] 解析世界规则与权限红线 …")
    r = parse_rules(check / "世界观设定标尺.md")
    rules, leaks = r if isinstance(r, tuple) else (r, [])
    print("[5/10] 解析伏笔台账 …")
    plot = parse_plot_board(bible / "plot-board.md")
    print("[6/10] 解析代价弧 …")
    cost = parse_cost_arc(ref / "长弧规划.md")
    print("[7/10] 解析术语锁定表 …")
    terms = parse_terminology(ref / "扩写规范-统一执行手册.md")
    print("[8/10] 解析时间轴与角色档案 …")
    timeline = parse_timeline(bible / "timeline.md")
    chars = parse_characters(check / "角色档案.md")
    print("[9/10] 解析角色卡目录 …")
    cards = parse_character_cards(bible / "characters")
    print("[10/10] 汇总 …")

    ok = sum(1 for e in REPORT if e["status"] == "ok")
    degraded = sum(1 for e in REPORT if e["status"] == "degraded")
    failed = sum(1 for e in REPORT if e["status"] == "failed")

    dataset = {
        "meta": {
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sourceRoot": str(root),
            "parserVersion": "1.0.0",
            "parseReport": REPORT,
            "quality": {"ok": ok, "degraded": degraded, "failed": failed},
        },
        "panel": panel,
        "creatures": creatures,
        "planes": planes,
        "rules": rules,
        "leakLines": leaks,
        "plotThreads": plot,
        "costArc": cost,
        "terminology": terms,
        "timeline": timeline,
        "characters": chars,
        "characterCards": cards,
    }
    return dataset


def main() -> None:
    ap = argparse.ArgumentParser(description="废土旅法师 · bible 解析器")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="小说工程根目录")
    ap.add_argument("--out", default=str(Path(__file__).parent / "data" / "dataset.json"))
    ap.add_argument("--print-report", action="store_true", help="只打印解析报告")
    args = ap.parse_args()

    dataset = build(Path(args.root))
    q = dataset["meta"]["quality"]

    print("\n" + "=" * 62)
    print(f"解析完成：ok={q['ok']}  degraded={q['degraded']}  failed={q['failed']}")
    print("=" * 62)
    for e in REPORT:
        if e["status"] in ("degraded", "failed"):
            print(f"  [{e['status'].upper()}] {e['step']}: {e['detail']}")

    if args.print_report:
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    size = out.stat().st_size
    print(f"\n数据层已写入: {out}  ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
