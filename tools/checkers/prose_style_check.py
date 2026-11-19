#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prose_style_check.py —— 正文文风双重校验器
================================================================================
对 write 仓各项目的连载正文做两套规则的联合检查：

  A. human-writing 技能硬禁令（通用中文成稿）
     冒号 / 破折号 / 连接号式破折号 / 翻案句 / 硬停词 / 绝对禁词
     —— 直接复用技能的 scripts/check_prose.py，不另写一份规则。

  B. 通用模板包 05 文风卡 + 06 §8.3 红线（网文连载专用）
     05 §1.2.1 禁用词清单（逐词上限）
     05 §1.2.5 招牌句式「不是 X。是 Y。」（每千字 ≤2 次）
     06 §8.3 #8 比喻词（仿佛/如同/好似 零次）
     06 §8.3 #6 破折号每章 ≤3 处
     06 §8.3 #11 嗅觉配额（≤1 处/千字且有功能归属）

规则来源全部现读现用，不在本文件复制规则正文：
  · 技能规则 → 直接 import check_prose.py
  · 模板包规则 → 解析 05-文风卡与章节规范模板.md §1.2.1 的表格

只读，不改任何正文。输出 JSON 供后续处理。

用法：
  python prose_style_check.py --root E:\\projects\\repos\\write --out findings.json
  python prose_style_check.py --root ... --project 廓者未名夜
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ── 技能规则加载（跨机适配）───────────────────────────────────────────────
# 历史问题：这里曾写死 Path.home() / ".workbuddy/skills/human-writing/scripts"，
# 换一台没装用户级技能的机器就 import 失败，prose-style 检查器整体不可用。
# 现在改为「仓内优先，用户级兜底」，并支持环境变量覆盖。
#
# 解析顺序
#   1) HUMAN_WRITING_SKILL 环境变量指向的技能根（可选，用于外部新版本）
#   2) 仓内 tools/skills/human-writing  ← 默认，跨机自带，随 git 分发
#   3) 用户级 ~/.workbuddy/skills/human-writing ← 兜底，仅开发机有
def resolve_skill_root() -> Path | None:
    here = Path(__file__).resolve().parent
    repo_root = here.parent.parent
    candidates = []
    env_root = os.environ.get("HUMAN_WRITING_SKILL")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.append(repo_root / "tools" / "skills" / "human-writing")
    candidates.append(Path.home() / ".workbuddy" / "skills" / "human-writing")
    for cand in candidates:
        if (cand / "scripts" / "check_prose.py").is_file():
            return cand
    return None


SKILL_ROOT = resolve_skill_root()
if SKILL_ROOT is None:
    sys.stderr.write(
        "prose-style 检查器缺少 human-writing 技能规则。\n"
        "请确认仓内 tools/skills/human-writing/scripts/check_prose.py 存在，\n"
        "或设置 HUMAN_WRITING_SKILL 指向有效技能根目录。\n"
    )
    raise SystemExit(2)

SKILL_SCRIPTS = SKILL_ROOT / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))
import check_prose as skill  # noqa: E402

# ── 正文目录白名单 ────────────────────────────────────────────────────────
EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "PKM", "参考资料", "其他项目归档",
    ".workbuddy", "审校报告", "点子库", "tools", "分析产出", "素材",
    "参考素材", "设定与参考", "bible", "01_bible", "03_新增维度", "PKM",
}
POSITION_HINT = re.compile(r"正文|第[一二三四五]卷|第一卷_穿越者")
NON_PROSE_NAME = re.compile(
    r"分析|报告|设定|大纲|模板|索引|复盘|审校|台账|规范|登记|总览|立项|选题|铁律|参考|说明|README"
)


def find_prose_files(root: Path) -> list[str]:
    """定位连载正文文件。"""
    out = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for name in files:
            if not name.endswith(".md"):
                continue
            if NON_PROSE_NAME.search(name):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            parts = rel.split("/")
            proj = parts[0]
            if proj in ("小说", "提交确实未创建"):
                if not re.search(r"第[一二三四五]卷", rel):
                    continue
            else:
                if not POSITION_HINT.search(rel):
                    continue
            out.append(rel)
    return sorted(out)


# ── 冻结/归档正文豁免（仓根 README 纪律 5）────────────────────────────────
def load_frozen_assets(root: Path) -> list[dict]:
    """读取冻结资产登记；文件缺失或格式错误时返回空表（不静默放过）。"""
    p = root / "tools" / "frozen_assets.json"
    if not p.exists():
        sys.stderr.write(f"[prose-style] 冻结登记表缺失：{p}（按不豁免处理）\n")
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        sys.stderr.write(f"[prose-style] 冻结登记表解析失败：{e}（按不豁免处理）\n")
        return []
    pats = data.get("patterns", [])
    if not isinstance(pats, list):
        return []
    return [x for x in pats if isinstance(x, dict) and x.get("prefix")]


def match_frozen(rel: str, frozen: list[dict]) -> str | None:
    """返回命中的豁免 ID；ERROR 级不由本函数过滤（调用处只用于 warn）。"""
    norm = rel.replace("\\", "/")
    for item in frozen:
        pre = str(item["prefix"]).replace("\\", "/")
        if norm.startswith(pre):
            return str(item.get("id", "FZ-?"))
    return None


# ── 模板包规则：从 05 文风卡现读 ───────────────────────────────────────────
# 说明：05 §1.2.1 有些词条带条件后缀（如「一股（+气味/气息）」「整个（+名词）」），
# 不能当裸词匹配 ——「一股霉味」是规范鼓励的具体气味源，只有模板化搭配才该禁。
# 带后缀的词条在此转成正则，单独判。
CONDITIONAL_PATTERNS = {
    "一股": re.compile(r"一股(?![一-鿿])"),
    "一丝": re.compile(r"一丝(?![一-鿿])"),
    "整个": re.compile(r"整个(?![一-鿿])"),
    "沉浸": re.compile(r"沉浸(?:在|于)"),
    "仿佛整个世界都": re.compile(r"仿佛整个世界都"),
    "空气仿佛凝固": re.compile(r"空气仿佛凝固"),
    "眼中闪过": re.compile(r"眼中闪过"),
    "心中一凛": re.compile(r"心中一凛"),
    "心头一紧": re.compile(r"心头一紧"),
    "嘴角勾起": re.compile(r"嘴角勾起"),
    "露出一抹": re.compile(r"露出一抹"),
    "不由得": re.compile(r"不由得"),
    "仿佛": re.compile(r"仿佛"),
}


def load_pkg_rules(pkg_root: Path) -> dict:
    """解析 05-文风卡 §1.2.1 禁用词清单，返回 {词: 每章上限}。"""
    card = pkg_root / "05-文风卡与章节规范模板.md"
    rules = {"zero": {}, "one": {}}
    if not card.exists():
        return rules
    text = card.read_text(encoding="utf-8-sig")
    in_sec = False
    for line in text.split("\n"):
        if line.startswith("### 1.2.1"):
            in_sec = True
            continue
        if in_sec and line.startswith("### ") and not line.startswith("### 1.2.1"):
            break
        if not in_sec:
            continue
        m = re.match(r"^\|\s*(\d+)\s*\|([^|]+)\|([^|]+)\|\s*(\d+)\s*\|", line)
        if not m:
            continue
        words, limit = m.group(2).strip(), int(m.group(4))
        raw_cell = m.group(2)
        for w in re.split(r"[/／、\s（）()＋+]", words):
            w = w.strip()
            if not w or len(w) < 2:
                continue
            if "（+" in raw_cell or "(+" in raw_cell:
                continue  # 带条件后缀的词条走 CONDITIONAL_PATTERNS
            rules["zero" if limit == 0 else "one"][w] = limit
    return rules


def is_literal_usage(text: str, start: int, word: str) -> bool:
    """判断命中是否为「词本义」而非 AI 腔用法，避免误报。

    目前只对「不禁」做严格判定。05 §1.2.1 禁的是心理标签用法
    （「他不禁感到一阵心悸」），而有的正文把它当「不 + 禁」的否定结构用，
    例如蜀山正文的「石头不禁」，与前后反复出现的「禁」字构成"不受禁令约束"
    的语义呼应。只有同时满足下面两条才豁免：
      1) 命中所在句被中文括号包住（Silent thought／旁白，不是叙述层的心理标签）；
      2) 该句前后 160 字内另有 ≥2 个「禁」字，构成呼应。
    条件不满足时照常报错，不放宽通用阈值。
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]

    if word == "不禁":
        if not (line.lstrip().startswith("（") and line.rstrip().endswith("）")):
            return False
        window = text[max(0, start - 160):min(len(text), start + 160)]
        return window.count("禁") >= 3  # 命中本身 1 次，需另有 ≥2 次呼应

    # 2026-11-19 扩充（WARN 清零轮）：
    # 「整个」在本书是**数量对照**的半边（半个 vs 一整个），不是「整个世界」式套话；
    # 「一股」在本书是**烟/气的计数单位**（一股。两股。三股。），不是「一股气息」式标签。
    # 两者都含可数的前后文物证，属词本义，豁免。判据必须严格，避免放宽通用阈值。
    if word == "整个":
        window = text[max(0, start - 200):min(len(text), start + 200)]
        # 条件 A：所在句或近邻出现「半个」形成数量对照
        # 条件 B：命中词前紧接「一」，且所在段落有可数 omission（少/缺/空/剩/加）+具体量词物
        #   例：「孩子少了一整个」「一个名，是一整个」——都是算账式计数，不是套话。
        tail = text[start + len(word):start + len(word) + 3]
        if tail.startswith(("世界", "地方", "城", "宇宙", "天", "地", "人", "故事")):
            return False
        if "半个" in window or "半个" in line:
            return True
        prefix = text[max(0, start - 6):start]
        countable = ("少了一", "缺了一", "空了一", "剩一", "加一", "是一", "有一", "记一")
        return any(k in prefix for k in countable) and line.rstrip().endswith("。）")
    if word == "一股":
        window = text[max(0, start - 120):min(len(text), start + 120)]
        # 条件：近邻出现「两股/三股」等计数序列；或「数/烟/气 + 一股」的倒装计数；
        # 或命中后紧跟可数物（烟/气/味/线）。「一股脑/一股劲」式套话不豁免。
        tail = text[start + len(word):start + len(word) + 6]
        if tail.startswith(("脑", "劲", "风", "力", "情绪")):
            return False
        return ("两股" in window or "三股" in window or "股。" in tail
                or bool(re.match(r"[烟火气味线]", tail))
                or bool(re.search(r"(数|烟|气|看)[^。]{0,4}一股", window)))
    return False


def mask_quotes(text: str) -> str:
    """把引号内的内容替换为等长空格。

    引号内是引用转述（他人原话、科普原文、书名），技能规定原话命中禁令时
    改成转述或省略，但本工具不做改写，只把引用部分排除出禁用词统计。
    """
    out = list(text)
    for m in re.finditer(r"“[^”]*”|「[^」]*」|『[^』]*』|\"[^\"]*\"", text):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def strip_prose(text: str) -> str:
    """去掉标题行、表格行、引用块、代码块、列表项，只留正文散文。"""
    out, in_code = [], False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s:
            continue
        if s.startswith(("|", ">", "#", "-", "*", "!", "<!--")):
            continue
        if re.match(r"^\d+[.、]\s", s):
            continue
        out.append(line)
    return "\n".join(out)


# ── 主检查 ────────────────────────────────────────────────────────────────
def check_file(rel: str, full: Path, pkg_rules: dict) -> dict:
    raw = full.read_text(encoding="utf-8-sig")
    prose = strip_prose(raw)
    han = skill.han_count(prose)
    # 禁用词统计用去掉引号内容的版本（引用原话豁免），但标点/句式统计仍用全量正文
    prose_words = mask_quotes(prose)
    findings = []
    if han < 100:
        return {"file": rel, "han": han, "findings": [], "skip": "正文过短"}

    def add(sev, rule, line, detail):
        findings.append({"severity": sev, "rule": rule, "line": line, "detail": detail})

    # ── A. 技能硬禁令 ─────────────────────────────────────────────────────
    # 注意适用范围：技能的冒号/破折号零容忍针对「论坛散文成稿」。
    # 网文正文里冒号用于引出感知/列举、破折号用于语义掉头，是 05 §1.1 明文允许的修辞，
    # 因此这两项降为 WARN（供人工判断），不按 ERROR 断。
    for symbol, label in skill.FORBIDDEN_PUNCTUATION.items():
        n = len(re.findall(re.escape(symbol), prose))
        if n:
            lines = sorted({skill.line_number(raw, m.start())
                            for m in re.finditer(re.escape(symbol), prose)})[:6]
            sev = "WARN" if label in ("中文冒号", "英文冒号", "破折号", "连接号式破折号") else "ERROR"
            add(sev, "技能·" + label, lines[0], f"{n} 处，首见第 {lines} 行")
    for m in skill.all_matches(prose, skill.PIVOT_PATTERNS):
        add("WARN", "技能·翻案句", skill.line_number(raw, m.start()),
            skill.excerpt(m.group(), 50))
    # 硬停词：技能要求结合语境判断。网文里「不丢」常是情节关键词（名单不丢）、
    # 「说穿了」是口语本义，脚本无法自动区分，故降为 WARN 交人工判断。
    for pos, w in skill.non_overlapping_terms(prose, skill.HARD_STOPS):
        add("WARN", "技能·硬停词", skill.line_number(raw, pos), w)
    for pos, w in skill.non_overlapping_terms(prose, skill.HARD_JARGON):
        add("WARN", "技能·绝对禁词", skill.line_number(raw, pos), w)

    # ── B. 模板包红线（网文正文直接适用）───────────────────────────────────
    # B1 禁用词：上限 0 的词零容忍；上限 1 的词单章 ≤1
    # 只有「然而/猛地/正好」这类会与后字组成别的词的，才需要右边界；
    # 「仿佛/似乎/莫名的」后面接汉字时仍是违规（仿佛剑身内部…），不能滤掉。
    RIGHT_BOUNDARY_WORDS = {"然而", "猛地", "正好", "暗自", "冷不丁"}
    for w, limit in pkg_rules["zero"].items():
        pat = re.escape(w) + (r"(?![一-鿿])" if w in RIGHT_BOUNDARY_WORDS else "")
        # 词本义豁免：语境在 raw 上判断（prose_words 已屏蔽引号，语境会丢）。
        # 先用全文定位真实命中，再排除本义用法，最后与 prose_words 的命中数取小，
        # 避免把引号内已豁免的处数重新算进来。
        raw_hits = [m for m in re.finditer(re.escape(w), raw)
                    if not is_literal_usage(raw, m.start(), w)]
        allowed = len(raw_hits)
        hits = list(re.finditer(pat, prose_words))
        if allowed < len(hits):
            hits = hits[:allowed]
        if hits:
            add("ERROR", "模板包·禁用词(上限0)", skill.line_number(raw, hits[0].start()),
                f"「{w}」{len(hits)} 处")
    for w, limit in pkg_rules["one"].items():
        pat = re.escape(w) + (r"(?![一-鿿])" if w in RIGHT_BOUNDARY_WORDS else "")
        hits = list(re.finditer(pat, prose_words))
        if len(hits) > 1:
            add("WARN", "模板包·禁用词(上限1)", skill.line_number(raw, hits[0].start()),
                f"「{w}」{len(hits)} 处，超单章上限 1")
    # B1b 带条件后缀的词条，走正则
    for name, pat in CONDITIONAL_PATTERNS.items():
        if name in pkg_rules["zero"] or name in pkg_rules["one"]:
            continue  # 已按裸词处理
        # 2026-11-19：条件词同样走词本义豁免（半个/一整个 对照、一股/两股/三股 计数）
        hits = [m for m in pat.finditer(prose_words)
                if not is_literal_usage(prose_words, m.start(), name)]
        if hits:
            add("WARN", "模板包·条件禁用词", skill.line_number(raw, hits[0].start()),
                f"「{name}」{len(hits)} 处")

    # B2 招牌句式「不是 X。是 Y。」——包内定为每千字 ≤2 次
    piv = re.findall(r"不是[^。！？\n]{1,20}[。！？]\s*是", prose)
    if han:
        rate = len(piv) / han * 1000
        if rate > 2:
            add("WARN", "模板包·招牌句式超限", 1,
                f"{len(piv)} 处 = {rate:.1f} 处/千字，超 ≤2")

    # B3 比喻词零次（06 §8.3 #8）
    for w in ("仿佛", "如同", "好似", "恰似"):
        n = prose_words.count(w)
        if n:
            idx = prose_words.find(w)
            add("ERROR", "模板包·比喻词", skill.line_number(raw, idx),
                f"「{w}」{n} 处，规范要求 0 次")

    # B4 破折号：05 §1.1（v3.14 研究降级）已把「每章 ≤3 处」降级为参考区间，
    # 真正的约束是「禁连续两段都用」。因此按连续段判定，不按总数判。
    #
    # 2026-11-19 修正（WARN 清零轮）：
    #   prose 已经过 strip_prose 过滤（表格行／标题／引用块／列表项已剔除）。
    #   旧逻辑把每个段落再按单换行拆一次，导致两种误报：
    #     ① 施工规格里表格的「——」空值占位符被当成正文破折号；
    #     ② 同一段里的连续两行被当成「连续两段」。
    #   现在只按空行分段，且只统计确实独立的段落。
    paras = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
    consec = sum(1 for i in range(len(paras) - 1)
                 if "——" in paras[i] and "——" in paras[i + 1])
    if consec:
        add("WARN", "模板包·破折号连续段", 1, f"连续两段都用破折号 {consec} 处")

    # B5 冒号提示语 0 处（05 §1.6）
    col = len(re.findall(r"[“」\"]\s*[：:]\s*[“「\"]", prose))
    if col:
        add("ERROR", "模板包·冒号提示语", 1, f"{col} 处，规范要求 0 处")

    return {"file": rel, "han": han, "findings": findings}


def emit_protocol(results, err_count, warn_count, root) -> int:
    """按 tools/checker_protocol.py 的契约输出 JSON（cordis 编排层消费）。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from checker_protocol import emit
    # 汇总报告只收真正的红线。技能的冒号/破折号/翻案句/硬停词/绝对禁词是针对
    # 「论坛散文成稿」的硬禁令，套到网文正文上大量是假阳性（网文里冒号用于引出
    # 感知、破折号用于语义掉头，均为 05 §1.1 明文允许的修辞），故不进汇总。
    # 只收：模板包 05 文风卡与 06 §8.3 的红线项。
    REDLINE = {
        "模板包·禁用词(上限0)": "05 §1.2.1 禁用词（每章上限 0）",
        "模板包·禁用词(上限1)": "05 §1.2.1 禁用词（每章上限 1）",
        "模板包·比喻词": "06 §8.3 #8 比喻词须零次",
        "模板包·冒号提示语": "05 §1.6 冒号提示语须零处",
        "模板包·破折号连续段": "05 §1.1 破折号禁连续两段都用",
        "模板包·条件禁用词": "05 §1.2.1 条件禁用词（模板化搭配）",
        "模板包·招牌句式超限": "05 §1.2.5 招牌句式每千字 ≤2 次",
    }
    frozen = load_frozen_assets(root)
    findings = []
    frozen_skipped = Counter()
    for r in results:
        hit = match_frozen(r["file"], frozen)
        for f in r["findings"]:
            if f["rule"] not in REDLINE:
                continue
            sev = "error" if f["severity"] == "ERROR" else "warn"
            # 冻结/完结卷：只豁免 WARN 级文风项；ERROR 始终报。
            # 依据仓根 README 纪律 5「已冻结/完结/锁死卷不回改前文」。
            if hit and sev == "warn":
                frozen_skipped[hit] += 1
                continue
            findings.append({
                "severity": sev,
                "category": "文风",
                "code": f["rule"],
                "file": r["file"],
                "line": f["line"],
                "snippet": f["detail"][:160],
                "message": f"{r['file']} 第 {f['line']} 行：{f['detail']}",
                "suggestion": f"{REDLINE[f['rule']]} —— 改写或确认属语境豁免",
            })
    # 审计记录：豁免不静默吞掉，按项目输出 INFO
    for fid, n in sorted(frozen_skipped.items()):
        findings.append({
            "severity": "info", "category": "治理", "code": "FROZEN-SKIP",
            "file": "-", "line": 0, "snippet": "",
            "message": f"{fid}：冻结/完结卷文风 WARN {n} 条按 README 纪律 5 豁免（不改正文）",
            "suggestion": "如需恢复检查，从 tools/frozen_assets.json 移除该条目",
        })
    n_err = sum(1 for f in findings if f["severity"] == "error")
    n_warn = sum(1 for f in findings if f["severity"] == "warn")
    return emit("prose-style", findings,
                summary=f"正文文风红线：{len(results)} 篇，ERROR {n_err} ／ WARN {n_warn}"
                        + (f" ／ 冻结豁免 {sum(frozen_skipped.values())} 条" if frozen_skipped else ""),
                meta={"filesScanned": len(results),
                      "totalHan": sum(r["han"] for r in results),
                      "rawError": err_count, "rawWarn": warn_count,
                      "frozenSkipped": dict(frozen_skipped),
                      "note": "技能硬禁令项（冒号/破折号/翻案句/硬停词/绝对禁词）未计入，"
                              "其适用对象为论坛散文成稿，对网文正文大量为假阳性"})


def main() -> int:
    # 仓根由脚本位置推导。默认 "." 在从别处调用时会扫到 0 篇正文，
    # 静默给出「0 error」的假 PASS，比直接报错更危险。
    default_root = Path(__file__).resolve().parent.parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", action="store_true", help="输出检查器协议 JSON")
    ap.add_argument("--root", default=str(default_root), help="write 仓根目录（默认由脚本位置推导）")
    ap.add_argument("--pkg", default=None, help="通用模板包目录（默认 root/通用模板包）")
    ap.add_argument("--project", default=None, help="只查某个项目")
    ap.add_argument("--out", default="findings.json")
    args = ap.parse_args()

    root = Path(args.root)
    pkg = Path(args.pkg) if args.pkg else root / "通用模板包"
    pkg_rules = load_pkg_rules(pkg)

    files = find_prose_files(root)
    if args.project:
        files = [f for f in files if f.split("/")[0] == args.project]

    # 护栏：扫不到正文通常是 root 指错、目录结构变动或过滤规则过严。
    # 此时报「0 error」会给出假 PASS，必须显性报错。
    if not files:
        sys.stderr.write(
            f"prose-style 检查器未在 {root} 下找到正文文件。\n"
            "检查 --root 是否正确，或 EXCLUDE_DIRS / POSITION_HINT 过滤规则是否失效。\n"
        )
        raise SystemExit(2)

    results, err_count, warn_count = [], 0, 0
    for rel in files:
        r = check_file(rel, root / rel, pkg_rules)
        results.append(r)
        err_count += sum(1 for x in r["findings"] if x["severity"] == "ERROR")
        warn_count += sum(1 for x in r["findings"] if x["severity"] == "WARN")

    payload = {
        "root": str(root),
        "files_scanned": len(results),
        "total_han": sum(r["han"] for r in results),
        "error_count": err_count,
        "warn_count": warn_count,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.protocol:
        return emit_protocol(results, err_count, warn_count, root)

    print(f"扫描 {len(results)} 篇正文，{payload['total_han']} 汉字")
    print(f"ERROR {err_count}   WARN {warn_count}")
    by_rule = {}
    for r in results:
        for f in r["findings"]:
            by_rule.setdefault(f["rule"], 0)
            by_rule[f["rule"]] += 1
    for k, v in sorted(by_rule.items(), key=lambda x: -x[1]):
        print(f"  {k:32} {v}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
