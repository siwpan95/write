#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc_review.py —— 长篇文档审校引擎（零三方依赖）
================================================================================
八类检查：TYPO / TIME / NUM / COND / STYLE / TERM / DUP / STRUCT

铁律：只出风险与位置，不代改正文。引擎只写 --out 目录，绝不修改被审文件。

用法：
  python doc_review.py --text <dir-or-file> [--text ...] [--out DIR]
                       [--config FILE] [--only CODE] [--json PATH]
                       [--fail-on error|warn|none]

退出码：0 无 ERROR ／ 1 存在 ERROR ／ 2 参数或 IO 错误
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SEV_ORDER = {"error": 0, "warn": 1, "info": 2}

# 全角 → 半角 映射（仅用于检测混用，不做转换）
FULLWIDTH_MAP = {
    "！": "!", "＂": '"', "＃": "#", "＄": "$", "％": "%", "＆": "&",
    "（": "(", "）": ")", "＊": "*", "＋": "+", "，": ",", "－": "-",
    "．": ".", "／": "/", "：": ":", "；": ";", "＜": "<", "＝": "=",
    "＞": ">", "？": "?", "＠": "@", "［": "[", "］": "]", "｛": "{",
    "｝": "}", "～": "~", "　": " ",
}

# 常见形近/音近误写对：(错误写法, 正确写法, 说明)
# 收录标准：**误写形式在现代汉语中基本不成词**，命中即可判定为错字。
# 两边都成词的（「作/做」「截止/截至」等）不入本表，改列 HIGH_RISK_ONLY 交人工判定。
CONFUSABLES = [
    ("迫不急待", "迫不及待", "成语"),
    ("走头无路", "走投无路", "成语"),
    ("一如即往", "一如既往", "成语"),
    ("再接再励", "再接再厉", "成语"),
    ("迫在眉捷", "迫在眉睫", "成语"),
    ("无与仑比", "无与伦比", "成语"),
    ("金榜提名", "金榜题名", "成语"),
    ("沤心沥血", "呕心沥血", "成语"),
    ("世外桃园", "世外桃源", "成语"),
    ("相形见拙", "相形见绌", "成语"),
    ("既使", "即使", "连词"),
    ("那末", "那么", "连词"),
    ("按耐", "按捺", "动词"),
    ("莫明", "莫名", "副词"),
    ("以经", "已经", "副词"),
    ("己经", "已经", "副词"),
    ("起负", "起飞", "动词"),
    ("帐薄", "账簿", "名词"),
    ("身分", "身份", "名词"),
    ("身分证", "身份证", "名词"),
    ("辩别", "辨别", "动词"),
    ("一诺千斤", "一诺千金", "成语"),
    ("谈笑风声", "谈笑风生", "成语"),
    ("有侍无恐", "有恃无恐", "成语"),
    ("震聋发聩", "振聋发聩", "成语"),
    ("沤瀣一气", "沆瀣一气", "成语"),
    ("循私舞弊", "徇私舞弊", "成语"),
    ("察颜观色", "察言观色", "成语"),
    ("甘败下风", "甘拜下风", "成语"),
    ("原形必露", "原形毕露", "成语"),
    ("不径而走", "不胫而走", "成语"),
    ("流言蜚语", "流言蜚语", "合法"),
]

# 两边都成词的高危词：只提示，不判定（常见于专名、引文、方言用法）
HIGH_RISK_ONLY = {
    "其它": "其他",
    "登陆": "登录",
    "渡过": "度过",
    "作出": "做出",
    "截止": "截至",
    "分量": "份量",
    "必须": "必需",
    "以至": "以致",
}

# 合法叠词白名单（双字重叠构词，不算重复词错误）
LEGIT_REDUPLICATES = {
    "刚刚", "常常", "渐渐", "慢慢", "轻轻", "静静", "默默", "深深", "好好",
    "紧紧", "牢牢", "明明", "往往", "处处", "步步", "点点", "丝丝", "念念",
    "历历", "栩栩", "津津", "踌躇", "吩咐", "招呼", "玲珑", "徘徊", "含糊",
    "婆娑", "淋漓", "蜿蜒", "斑驳", "沧桑", "从容", "人人", "看看", "想想",
    "说说", "听听", "试试", "走走", "站站", "坐坐", "歇歇", "玩玩", "等等",
    "偏偏", "仅仅", "单单", "稍稍", "略微", "多多", "少少", "长长", "短短",
    "圆圆", "方方", "正正", "空空", "满满", "沉沉", "悄悄", "幽幽", "暗暗",
    "微微", "匆匆", "淡淡", "浓浓", "久久", "远远", "三三两两", "千千万万",
    "日日夜夜", "年复一年", "时时刻刻", "家家户户", "你你", "我我", "他他",
    "她她", "它它", "就就", "也也", "和和", "不不",
}

# 功能词重叠集合（只对功能词的双写报警；内容词的 AA 重叠是合法中文构词）
FUNCTION_WORD_DUP = set("的了是在不没和就都很也才还把被让给对从到向与及或但因所")

# 中文数字单位（用于数量解析）
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}

# 时间表达
RE_CLOCK = re.compile(r"(?<!\d)(\d{1,2})[:：](\d{2})(?!\d)")
RE_CLOCK_CN = re.compile(r"([零一二三四五六七八九十]{1,3})\s*[点時时]\s*([零一二三四五六七八九十]{1,3})?\s*分?")
RE_REL_DAY = re.compile(r"([零一二三四五六七八九十两\d]{1,4})\s*天\s*(后|後|前|之后|之后|以前|之前|之后)")
RE_REL_TIME = re.compile(r"([零一二三四五六七八九十两\d]{1,4})\s*(个)?\s*(分钟|分鐘|小时|小時|秒|周|星期|个月|個月|月|年)\s*(后|後|前|之前|以后|之后|以前)")
RE_ABS_TIME = re.compile(r"(第\s*([零一二三四五六七八九十两\d]{1,4})\s*(天|日|年|个月|周))")
RE_NIGHT = re.compile(r"(清晨|凌晨|早晨|上午|中午|下午|傍晚|晚上|夜里|深夜|半夜|午夜|拂晓|天亮|入夜)")

# 时间锚解析：抽「第N天」+ 锚尾的相对偏移（如「主线第3天·午后至三天后」）
RE_ANCHOR_DAY = re.compile(r"第\s*([零一二三四五六七八九十两\d]{1,4})\s*[天日]")
RE_ANCHOR_REL = re.compile(r"([零一二三四五六七八九十两\d]{1,4})\s*天\s*(后|後|前|之后|以后|以前|之前)")

# 表格行
RE_TABLE_SEP = re.compile(r"^\s*\|[\s:\-\|]+\|\s*$")

# 表格单元格切分：**必须跳过转义竖线**（`\|`）。
# 数学式里常见 `\|a\|≈\|b\|` 这类写法；按裸竖线切会把一行数成 7 列，
# 而表头只有 3 列 → 误报「表格列数不一致」。
RE_TABLE_SPLIT = re.compile(r"(?<!\\)\|")


def split_cells(line: str) -> list[str]:
    """按未转义的竖线切分表格行，返回单元格列表（保留原始空白）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return RE_TABLE_SPLIT.split(s)

# 悬空引用
RE_SEC_REF = re.compile(r"`(\d{2})`\s*§\s*([0-9]+(?:\.[0-9]+)*)")
RE_FILE_REF = re.compile(r"`([^`\n]{2,120}?\.(?:md|py|txt|json|yml|yaml|html|svg|mjs|js|xlsx|docx))`")
RE_FS_REF = re.compile(r"\b(FS-[A-Z]?\d+|F-[A-Z]\d+)\b")
RE_CHAPTER_HEAD = re.compile(r"^#{1,6}\s+(.*)$")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def read_text(path: Path) -> str:
    """稳健读取：自动处理 BOM / UTF-16 / UTF-8 / GBK。"""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def cn2int(s: str):
    """中文数字 → int（支持到亿级；解析失败返回 None）。"""
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    if any(c not in CN_DIGITS and c not in CN_UNITS for c in s):
        return None
    total, num, seen = 0, 0, False
    for ch in s:
        if ch in CN_DIGITS:
            num = CN_DIGITS[ch]
            seen = True
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if unit >= 10000:
                total = (total + num) * unit
                num = 0
            else:
                if num == 0:
                    num = 1
                total += num * unit
                num = 0
            seen = True
    return (total + num) if seen else None


def is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def detect_width_mix(line: str):
    """检测一行内全角/半角标点混用。返回 (字符, 上下文) 或 None。"""
    has_full = any(c in FULLWIDTH_MAP for c in line)
    has_half = any(c in (",", ".", "!", "?", ":", ";", "(", ")") for c in line)
    if not (has_full and has_half):
        return None
    # 只在同一句内、且不是 URL / 代码 / 英文段落
    if re.search(r"https?://|\w+\.\w+|[A-Za-z]{4,}", line):
        return None
    return line


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", "", s)


# ---------------------------------------------------------------------------
# 发现项
# ---------------------------------------------------------------------------

class Finding:
    __slots__ = ("severity", "category", "code", "file", "line", "snippet",
                 "message", "suggestion")

    def __init__(self, severity, category, code, file, line, snippet,
                 message, suggestion=""):
        self.severity = severity
        self.category = category
        self.code = code
        self.file = file
        self.line = line
        self.snippet = snippet
        self.message = message
        self.suggestion = suggestion

    def as_dict(self):
        return {
            "severity": self.severity, "category": self.category,
            "code": self.code, "file": self.file, "line": self.line,
            "snippet": self.snippet, "message": self.message,
            "suggestion": self.suggestion,
        }

    def __repr__(self):
        return f"<{self.severity} {self.code} {self.file}:{self.line}>"


# ---------------------------------------------------------------------------
# 语料装载
# ---------------------------------------------------------------------------

class Doc:
    """一份被审文档。"""

    def __init__(self, path: Path, text: str):
        self.path = path
        self.text = text
        self.lines = text.split("\n")
        self.chapter = None
        self.chapter_index = None
        self.is_chapter = False
        # 章节识别：文件名含「第N章」，或行首数字前缀 **且** 该数字前缀
        # 后面跟着中文章名（如「01-第一章-第十三条.md」）。
        # 注意：「06-连载护航-…md」这类**编号配置文件**不是章节，
        # 必须排除，否则它会被当成「第 6 章」参与时间比对。
        m = re.search(r"第\s*([零一二三四五六七八九十两\d]{1,4})\s*章", path.name)
        if m:
            self.chapter = cn2int(m.group(1))
            self.is_chapter = True
        else:
            m2 = re.match(r"^(\d{1,3})[-_]", path.name)
            if m2:
                self.chapter = int(m2.group(1))
                # 行首数字前缀后紧跟「第…章」才算章节文件
                self.is_chapter = bool(
                    re.match(r"^\d{1,3}[-_].*第[零一二三四五六七八九十两\d]{1,4}章",
                             path.name))
        self._extract_time_anchors()

    def rel(self, path=None) -> str:
        """相对路径显示（相对当前工作目录）。"""
        p = Path(path) if path is not None else self.path
        try:
            return str(p.relative_to(Path.cwd()))
        except ValueError:
            return str(p)

    def _extract_time_anchors(self):
        """抽取本章的显式时间锚（绝对日/时刻）。"""
        self.clocks = []       # (minute_of_day, raw, line_no)
        self.abs_days = []     # (day, raw, line_no)
        self.nights = []       # (时段, raw, line_no)
        for i, line in enumerate(self.lines, 1):
            for m in RE_CLOCK.finditer(line):
                h, mi = int(m.group(1)), int(m.group(2))
                if 0 <= h <= 23 and 0 <= mi <= 59:
                    self.clocks.append((h * 60 + mi, m.group(0), i))
            for m in RE_CLOCK_CN.finditer(line):
                h = cn2int(m.group(1))
                mi = cn2int(m.group(2)) if m.group(2) else 0
                if h is not None and 0 <= h <= 23:
                    self.clocks.append((h * 60 + (mi or 0), m.group(0), i))
            for m in RE_ABS_TIME.finditer(line):
                d = cn2int(m.group(2))
                if d is not None:
                    self.abs_days.append((d, m.group(0), i))
            for m in RE_NIGHT.finditer(line):
                self.nights.append((m.group(1), m.group(0), i))


class Corpus:
    """被审语料集合。"""

    TEXT_EXT = {".md", ".txt", ".markdown"}

    # 永远跳过的目录（工具链产物 / 依赖 / 缓存，不是创作内容）
    SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
                 ".idea", ".vscode", ".mypy_cache", ".pytest_cache",
                 "dist", "build", ".workbuddy"}

    # 合集/导出件：内容天然是各章的拼接，不参与「跨文件重复」判定
    AGGREGATE_HINT = re.compile(
        r"(全集版|合集|整合版|合订|汇编|选集|全文|合并版|总集|"
        r"全书|txt$|complete|collected|anthology)", re.IGNORECASE)

    def __init__(self, paths, config):
        self.config = config or {}
        self.docs = []
        self.errors = []
        self.ignore_patterns = [re.compile(p) for p in self.config.get("ignore", [])]
        seen = set()
        for p in paths:
            p = Path(p)
            if p.is_dir():
                files = sorted(q for q in p.rglob("*")
                               if q.is_file() and q.suffix.lower() in self.TEXT_EXT
                               and not self._in_skip_dir(q)
                               and not self._in_skip_dir(q.parent))
            elif p.is_file():
                files = [p]
            else:
                self.errors.append(f"路径不存在：{p}")
                continue
            for f in files:
                key = f.resolve()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    self.docs.append(Doc(f, read_text(f)))
                except Exception as e:                      # pragma: no cover
                    self.errors.append(f"读取失败：{f} — {e}")
        self.docs.sort(key=lambda d: (d.chapter if d.is_chapter else 10 ** 6,
                                      str(d.path)))

    def ignored(self, line: str) -> bool:
        return any(p.search(line) for p in self.ignore_patterns)

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return str(path)

    @classmethod
    def _in_skip_dir(cls, p: Path) -> bool:
        return any(part in cls.SKIP_DIRS for part in p.parts)

    def is_aggregate(self, doc) -> bool:
        """合集/导出件判定：内容天然是各章拼接，不参与跨文件重复判定。"""
        if self.config.get("include_aggregates"):
            return False
        name = doc.path.name
        if doc.is_chapter:
            return False
        return bool(self.AGGREGATE_HINT.search(name))


# ---------------------------------------------------------------------------
# 检查器：TYPO
# ---------------------------------------------------------------------------

def check_typo(corpus, out):
    """
    错别字：
      TYPO-DUP   重复词（排除合法叠词；只对**非叠字构词**报警）
      TYPO-CONF  形近/音近误写对（高置信度）
      TYPO-RISK  易混词（需人工确认，如「其它/其他」）
    """
    for doc in corpus.docs:
        for i, line in enumerate(doc.lines, 1):
            if corpus.ignored(line):
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ">", "|", "```", "-", "*")):
                continue
            # --- 重复词 ---
            # 中文「AA」重叠式是合法构词（刚刚/常常/一格一格/不急不急），
            # 因此只有**功能词重叠**（的的/是是）才是硬错；内容词重叠不报。
            # 判定要求双写是**独立成词**的：
            #   · 前后都不是汉字（避免「现在在十九楼」把「现|在」误切）
            #   · 不是三连（避免「对对对」这类对话强调）
            for m in re.finditer(r"(?<![一-鿿])([一-鿿])\1(?![一-鿿])", line):
                w = m.group(1)
                if w not in FUNCTION_WORD_DUP:
                    continue
                out.append(Finding(
                    "warn", "错别字", "TYPO-DUP", doc.rel(doc.path), i,
                    stripped[:120],
                    f"疑似重复词「{w}{w}」（功能词重叠）",
                    f"改为「{w}」",
                ))
            # --- 形近/音近对 ---
            for wrong, right, _ctx in CONFUSABLES:
                if wrong == right:
                    continue
                idx = line.find(wrong)
                while idx != -1:
                    if wrong in HIGH_RISK_ONLY:
                        out.append(Finding(
                            "info", "错别字", "TYPO-RISK", doc.rel(doc.path), i,
                            stripped[:120],
                            f"「{wrong}」与「{right}」易混，请人工确认",
                            f"若非专名或引文，考虑改为「{right}」",
                        ))
                    else:
                        out.append(Finding(
                            "warn", "错别字", "TYPO-CONF", doc.rel(doc.path), i,
                            stripped[:120],
                            f"疑似误写「{wrong}」，应为「{right}」",
                            f"改为「{right}」",
                        ))
                    idx = line.find(wrong, idx + len(wrong))


# ---------------------------------------------------------------------------
# 检查器：TIME
# ---------------------------------------------------------------------------

def parse_anchor(text: str):
    """
    解析一个时间锚字符串，返回 (起始日, 结束日, 相对偏移)。

    支持：
      「主线第3天·晨会」                → (3, 3, None)
      「主线第3天·午后至三天后」        → (3, 6, +3)
      「主线第5-6天·晨至夜」            → (5, 6, None)
      「主线第6-7天·晚至夜」            → (6, 7, None)
    """
    if not text:
        return None
    t = text.strip()
    days = [cn2int(x) for x in re.findall(r"第\s*([零一二三四五六七八九十两\d]{1,4})\s*[天日]", t)]
    days = [d for d in days if d is not None]
    if not days:
        return None
    start = days[0]
    end = days[-1] if len(days) > 1 else start
    # 锚尾的相对偏移：「…至三天后」→ end += 3
    rel = None
    tail = t[t.find("天", t.find("第")):] if "第" in t else ""
    rm = RE_ANCHOR_REL.search(t)
    if rm:
        n = cn2int(rm.group(1))
        if n is not None:
            if rm.group(2) in ("前", "以前", "之前"):
                rel = -n
            else:
                rel = n
                end = max(end, start + n)
    return (start, end, rel)


def extract_ledger_rows(doc):
    """
    从台账类文档的 markdown 表格里抽出 (章号 → 时间锚文本, 行号)。

    识别规则：表头含「章」列与含「时间」或「锚」字的列；或首列为章号且某列含「第N天」。
    """
    rows = []
    lines = doc.lines
    i = 0
    in_code = False
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if in_code or not s.startswith("|"):
            i += 1
            continue
        if i + 1 >= len(lines) or not RE_TABLE_SEP.match(lines[i + 1]):
            i += 1
            continue
        header = [c.strip() for c in split_cells(s)]
        # 找时间锚列
        tcol = None
        for idx, h in enumerate(header):
            if re.search(r"时间|锚|时段|日\s*期", h):
                tcol = idx
                break
        if tcol is None:
            i += 1
            continue
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = [c.strip() for c in split_cells(lines[j])]
            if tcol < len(cells):
                ch = None
                if cells:
                    m = re.match(r"^\s*(\d+)\s*$", cells[0])
                    if m:
                        ch = int(m.group(1))
                anchor = cells[tcol]
                pa = parse_anchor(anchor)
                if ch is not None and pa:
                    rows.append({"chapter": ch, "start": pa[0], "end": pa[1],
                                 "rel": pa[2], "raw": anchor, "line": j + 1,
                                 "file": doc})
            j += 1
        i = j
    return rows


def check_time(corpus, out):
    """
    时间矛盾：
      TIME-REG    跨章时间倒挂（后一章时间锚早于前一章）——来源：台账表或正文显式锚
      TIME-ORDER  同一文件内，绝对日锚倒挂
      TIME-REL    相对时间与绝对日锚冲突（正文「三天后」与台账「第3天」算不平）
      TIME-CLOCK  同一句内出现两个相隔较大的时刻
    """
    # --- 跨章时间倒挂（台账表） ---
    # **必须按文件分组比对**：不同项目的台账共用同一套章号（都是 1..N），
    # 若把全仓台账行混在一起按章号排序，会把「A 项目的第 9 章」和
    # 「B 项目的第 10 章」拿来比，产生完全虚假的倒挂。
    ledger_rows = []
    for doc in corpus.docs:
        ledger_rows.extend(extract_ledger_rows(doc))
    # 按文件分组，每组独立比对
    by_file = defaultdict(list)
    for r in ledger_rows:
        by_file[id(r["file"])].append(r)
    for _, rows in by_file.items():
        by_ch = defaultdict(list)
        for r in rows:
            by_ch[r["chapter"]].append(r)
        ordered = sorted(by_ch.items())
        for i in range(1, len(ordered)):
            (ch_a, ra), (ch_b, rb) = ordered[i - 1], ordered[i]
            if ch_b != ch_a + 1:
                continue
            a, b = ra[0], rb[0]
            if b["start"] < a["start"]:
                out.append(Finding(
                    "error", "时间矛盾", "TIME-REG",
                    corpus.rel(b["file"].path),
                    b["line"], b["raw"],
                    f"跨章时间倒挂：第 {ch_a} 章锚为「{a['raw']}」（第 {a['start']} 天），"
                    f"第 {ch_b} 章却回到「{b['raw']}」（第 {b['start']} 天）",
                    f"核对第 {ch_a} 章与第 {ch_b} 章的时间锚，确认是笔误还是倒叙未标注",
                ))
            elif b["start"] < a["end"]:
                out.append(Finding(
                    "error", "时间矛盾", "TIME-REG",
                    corpus.rel(b["file"].path),
                    b["line"], b["raw"],
                    f"跨章时间重叠：第 {ch_a} 章锚「{a['raw']}」延伸到第 {a['end']} 天，"
                    f"第 {ch_b} 章却起于第 {b['start']} 天",
                    f"核对第 {ch_a} 章与第 {ch_b} 章的时间锚",
                ))

    # --- 单文件内绝对日锚倒挂 ---
    # 两条约束，缺一不可，否则误报率极高：
    #   ① 只对**章节正文**生效（台账/设定类文档里「第N天」既是数据行又是定义说明）；
    #   ② 只比较**带相同限定前缀**的锚（如「主线第3天」vs「主线第4天」）。
    #      无前缀的「第N天」在正文里多指**回叙**（"第一天，我们还是小作坊"），
    #      与当前时间轴无关，不能拿来判倒挂。
    # 严重度定 WARN：即使限定前缀相同，也可能是作者的有意回叙，由作者定性。
    for doc in corpus.docs:
        if not doc.is_chapter:
            continue
        seq = sorted(doc.abs_days, key=lambda x: x[2])
        prev = None
        for day, raw, ln in seq:
            prefix = re.sub(r"第.*$", "", raw).strip()
            if prefix and prev is not None and prev[3] == prefix and day < prev[0]:
                out.append(Finding(
                    "warn", "时间矛盾", "TIME-ORDER", doc.rel(doc.path), ln,
                    f"{raw}",
                    f"同一文件内时间倒挂：第 {prev[2]} 行出现「{prev[1]}」，"
                    f"第 {ln} 行又出现「{raw}」（同为「{prefix}」时间轴）",
                    "确认哪一处是笔误；若为倒叙请显式标注",
                ))
            if prev is None or day >= prev[0]:
                prev = (day, raw, ln, prefix)

    # --- 正文相对时间 vs 台账锚 ---
    # 台账锚必须与章节**属于同一项目**才可比：按「台账文件所在目录」分组，
    # 只取与该章正文同目录（或同父目录）的那份台账的锚。
    #
    # ⚠️ 白名单（2026-11-14 新增）：相对时间表述有两种含义 ——
    #   ① **叙述当前时点向后推**：如「五天之后生产线会停」—— 事件**尚未发生**，
    #      是人物对话中的预期时点，不等于「叙述时点 + 5 天」；
    #   ② **真实推进**：如「三天后他回来了」—— 叙述确实跳到了 3 天后。
    #   原判据只按 ① 之外的方式理解，② 之外的 ① 会误报。
    #   项目可在配置里声明 `time_anchor_exempt`：列出**已知为预期时点**的表述，
    #   这些表述不再参与 TIME-REL 推算（真实推进型仍会被报出来）。
    time_exempt = set(corpus.config.get("time_anchor_exempt", []))
    if ledger_rows:
        anchors_by_dir = defaultdict(dict)
        for r in ledger_rows:
            anchors_by_dir[r["file"].path.parent][r["chapter"]] = r
        for doc in corpus.docs:
            if not doc.is_chapter:
                continue
            # 找最近的同项目台账：优先同目录，其次父目录
            cand = (anchors_by_dir.get(doc.path.parent)
                    or anchors_by_dir.get(doc.path.parent.parent))
            if not cand:
                continue
            r = cand.get(doc.chapter)
            if not r:
                continue
            for i, line in enumerate(doc.lines, 1):
                if corpus.ignored(line):
                    continue
                for m in RE_REL_DAY.finditer(line):
                    n = cn2int(m.group(1))
                    if n is None:
                        continue
                    back = m.group(2) in ("前", "以前", "之前")
                    if back:
                        # 「三天前」指本章锚之前，不构成冲突；跨度由台账自行登记
                        continue
                    # 白名单：项目已声明该表述为「预期时点」，不参与推算
                    if m.group(0) in time_exempt:
                        continue
                    implied = r["start"] + n
                    if implied > r["end"] + 1:
                        out.append(Finding(
                            "warn", "时间矛盾", "TIME-REL", doc.rel(doc.path), i,
                            m.group(0),
                            f"正文称「{m.group(0)}」，按台账本章锚「第 {r['start']} 天」"
                            f"推算为第 {implied} 天，超出台账登记的跨度"
                            f"（第 {r['start']}~{r['end']} 天）",
                            "核对台账时间锚是否需延长，或正文表述是否需修正",
                        ))

    # --- 同句时刻矛盾 ---
    for doc in corpus.docs:
        for i, line in enumerate(doc.lines, 1):
            if corpus.ignored(line):
                continue
            clocks = [(int(m.group(1)) * 60 + int(m.group(2)), m.group(0))
                      for m in RE_CLOCK.finditer(line)]
            if len(clocks) < 2:
                continue
            diff = abs(clocks[0][0] - clocks[1][0])
            if diff == 0:
                continue
            if diff > 12 * 60 and len(clocks) == 2:
                out.append(Finding(
                    "info", "时间矛盾", "TIME-CLOCK", doc.rel(doc.path), i,
                    line.strip()[:120],
                    f"同一行出现两个相隔较大的时刻（{clocks[0][1]} / {clocks[1][1]}）",
                    "若为跨时段叙述请分行或显式标注",
                ))


# ---------------------------------------------------------------------------
# 检查器：NUM
# ---------------------------------------------------------------------------

RE_NUM_WITH_UNIT = re.compile(
    r"([零一二三四五六七八九十百千万亿两\d][零一二三四五六七八九十百千万亿两\d,.]{0,12})\s*"
    r"(个|名|位|人|次|条|本|张|件|天|月|年|周|小时|分钟|秒|元|万|亿|%|％|米|公里|斤|吨|层|级|章|卷|拍|件)"
)


def _norm_num(raw: str):
    """把数字串标准化为 (value, unit) 的数值部分，失败返回 None。"""
    s = raw.strip().replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    v = cn2int(s)
    return float(v) if v is not None else None


def check_number(corpus, out):
    """
    数字口径：
      NUM-METRIC  同一指标（配置声明）在不同文件出现不同取值 → error
      NUM-UNIT    同一指标单位不统一 → warn
      NUM-CAP     声明的总字数/章数与实际文件数/字数不符 → error

    口径判定的关键区分：**状态演进 ≠ 口径冲突**。
    「真气 70%→68%→61%」是资源随剧情消耗的**演进序列**，不是矛盾；
    真正要报的是「同一时点、同一指标、两套数值」，以及
    「指标被声明为无面板数值，却在台账里按数值记账」这类**定义处与使用处打架**。
    因此指标配置支持：
      pattern      捕获数值的正则（必须有捕获组）
      scope        限定目录关键字
      mode         "state"（演进序列，默认不报冲突）/ "constant"（恒定值，
                   出现不同取值即报冲突）
      transitions  演进分隔符正则，默认匹配 → → ~ 等
      forbid_if    正则；命中即说明该处禁止出现数值型口径（如
                   「无面板数值」），此时任何数值捕获都报冲突
    """
    cfg = corpus.config.get("metrics", {})
    if cfg:
        for mname, mcfg in cfg.items():
            pat = mcfg.get("pattern")
            if not pat:
                continue
            scope = mcfg.get("scope")
            mode = mcfg.get("mode", "state")
            trans_re = re.compile(mcfg.get("transitions", r"→|~|—>|->"))
            forbid_re = re.compile(mcfg["forbid_if"]) if mcfg.get("forbid_if") else None

            rx = re.compile(pat)
            # 命中项：(值, 文件, 行号, 原始片段, 整行, 该行是否含演进符)
            hits = []
            for doc in corpus.docs:
                if scope and not any(s in str(doc.path) for s in scope):
                    continue
                for i, line in enumerate(doc.lines, 1):
                    if corpus.ignored(line):
                        continue
                    for mm in rx.finditer(line):
                        raw = mm.group(1) if mm.groups() else mm.group(0)
                        val = _norm_num(raw)
                        if val is None:
                            continue
                        hits.append((val, doc.rel(doc.path), i, mm.group(0).strip(),
                                     line.strip()[:110], bool(trans_re.search(line))))

            # --- 定义处禁止数值型口径 ---
            # 判定要件：**声明存在 且 确有数值记账**，二者同时满足才算冲突，
            # 且冲突点落在**记账处**（不是定义处 —— 定义处出现该声明本身就是对的）。
            # 只声明、无数值记账时不得报，否则该规则对"声明了无面板数值"的项目
            # 永远误报（2026-11-13 实测修正）。
            if forbid_re and hits:
                decl = None
                for doc in corpus.docs:
                    if scope and not any(s in str(doc.path) for s in scope):
                        continue
                    for i, line in enumerate(doc.lines, 1):
                        if corpus.ignored(line):
                            continue
                        fm = forbid_re.search(line)
                        if fm:
                            decl = (corpus.rel(doc.path), i, fm.group(0))
                            break
                    if decl:
                        break
                if decl:
                    h = hits[0]
                    out.append(Finding(
                        "error", "数字口径", "NUM-METRIC",
                        h[1], h[2], h[4],
                        f"指标「{mname}」的定义处（{decl[0]}:{decl[1]}）声明「{decl[2]}」"
                        f"（不设数值口径），但此处按数值记账：{h[3]}",
                        f"要么删除「{mname}」的数值记账（改用可观测症状），要么改设定定义处",
                    ))

            if len(hits) < 2:
                continue

            # --- 恒定值型指标：不同取值即冲突 ---
            if mode == "constant":
                vals = defaultdict(list)
                for v, f, ln, raw, line, is_trans in hits:
                    vals[v].append((f, ln, raw, line))
                if len(vals) > 1:
                    ordered = sorted(vals.items(), key=lambda kv: -len(kv[1]))
                    for i in range(len(ordered)):
                        for j in range(i + 1, len(ordered)):
                            (va, ha), (vb, hb) = ordered[i], ordered[j]
                            fa, la, ra, _ = ha[0]
                            fb, lb, rb, _ = hb[0]
                            out.append(Finding(
                                "error", "数字口径", "NUM-METRIC", fb, lb, rb,
                                f"指标「{mname}」口径冲突：{ra}（{fa}）"
                                f" vs {rb}（{fb}）",
                                f"统一「{mname}」的取值；数值只应由 SSOT 定义处给出",
                            ))

            # --- 演进型指标：只在「同一行内出现两套并行口径」时报冲突 ---
            else:
                by_line = defaultdict(list)
                for v, f, ln, raw, line, is_trans in hits:
                    by_line[(f, ln)].append((v, raw))
                for (f, ln), items in by_line.items():
                    vals = {v for v, _ in items}
                    if len(vals) > 1 and not any(
                            trans_re.search(x[1]) for x in items):
                        out.append(Finding(
                            "error", "数字口径", "NUM-METRIC", f, ln,
                            items[0][1],
                            f"指标「{mname}」同一行出现两套口径："
                            f"{'、'.join(x[1] for x in items)}",
                            f"同一时点只应有一个「{mname}」取值",
                        ))

    # 单位不统一：**同一指标**在跨文件场景下混用不同量级单位才报。
    # （此前版本统计「整文件出现过哪些单位」，把「一个文件里既有万又有亿」
    #   误报为单位冲突——同一文件里不同量级本就可以共存。）
    metric_units = defaultdict(lambda: defaultdict(list))
    for mname, mcfg in cfg.items():
        pat = mcfg.get("pattern")
        if not pat:
            continue
        scope = mcfg.get("scope")
        rx = re.compile(pat)
        for doc in corpus.docs:
            if scope and not any(s in str(doc.path) for s in scope):
                continue
            for i, line in enumerate(doc.lines, 1):
                if corpus.ignored(line):
                    continue
                for mm in rx.finditer(line):
                    raw = mm.group(0)
                    um = RE_NUM_WITH_UNIT.search(raw)
                    unit = um.group(2) if um else mcfg.get("unit", "")
                    if unit:
                        metric_units[mname][unit].append(
                            (doc.rel(doc.path), i, raw.strip()))
    for mname, units in metric_units.items():
        if len(units) < 2:
            continue
        # 只在「万/亿」这类**量级单位**之间冲突时报（人/天/元 不冲突）
        magnitude = {u: v for u, v in units.items() if u in ("万", "亿")}
        if len(magnitude) < 2:
            continue
        ulist = sorted(magnitude)
        f1, l1, r1 = magnitude[ulist[0]][0]
        f2, l2, r2 = magnitude[ulist[1]][0]
        out.append(Finding(
            "warn", "数字口径", "NUM-UNIT", f2, l2, r2,
            f"指标「{mname}」跨文件混用量级单位："
            f"「{ulist[0]}」（{f1}）与「{ulist[1]}」（{f2}）",
            f"统一「{mname}」的量级单位，或在设定中明确换算关系",
        ))


# ---------------------------------------------------------------------------
# 检查器：COND
# ---------------------------------------------------------------------------

RE_NO_SUBJECT = re.compile(
    r"^(?![（(【\[])(?:然后|接着|随后|于是|但是|不过|而且|并且|另外|此外)"
    r"[^。！？\n]{0,20}?(?:说|问|答|道|喊|叫)[：:]")
RE_MISSING_PRECOND = re.compile(
    r"(?:如果|假如|一旦|除非|只要|只有)[^。！？\n]{0,40}?(?:就|便|则)")
RE_VAGUE = re.compile(r"(?:大概|可能|也许|差不多|好像|似乎|或许)")


def check_condition(corpus, out):
    """
    缺失条件：
      COND-SUBJ   句子缺主语（连副词开头直接跟对话动词）
      COND-PRE    「如果…」句缺结果子（只有条件没有"就…"）
      COND-VAGUE  模糊限定词无量化锚（大概/差不多等）
      COND-MEASURE 量词与数词不匹配（中文常见：一台电脑 vs 一部手机类）
    """
    for doc in corpus.docs:
        in_code = False
        for i, line in enumerate(doc.lines, 1):
            s = line.strip()
            if s.startswith("```"):
                in_code = not in_code
                continue
            if in_code or corpus.ignored(line) or not s:
                continue
            if s.startswith(("#", ">", "|", "-", "*")):
                continue
            m = RE_NO_SUBJECT.match(s)
            if m:
                out.append(Finding(
                    "warn", "缺失条件", "COND-SUBJ", doc.rel(doc.path), i, s[:120],
                    "句子以连接副词开头且直接跟对话动词，主语缺位",
                    "补主语；若为前文延续的对话，可保留但建议加引号标识说话人",
                ))
            if RE_MISSING_PRECOND.search(s) and "否则" not in s:
                # 检查是否已有结果子
                if not re.search(r"(?:就|便|则|那么|才能|方可)", s):
                    out.append(Finding(
                        "warn", "缺失条件", "COND-PRE", doc.rel(doc.path), i, s[:120],
                        "条件句有条件但缺结果子（只有「如果…」，没有「就…」）",
                        "补结果子；若为刻意留白请显式标注",
                    ))


# ---------------------------------------------------------------------------
# 检查器：STYLE
# ---------------------------------------------------------------------------

def check_style(corpus, out):
    """
    体例：
      STYLE-QUOTE  直引号 " 与弯引号混用
      STYLE-ELL   三点省略号 ... 与六点 ……
      STYLE-DASH  单破折号 — 与双破折号 —— 混用
      STYLE-PAREN 半角括号与全角括号混用
      STYLE-TIME  时刻用半角冒号
    """
    for doc in corpus.docs:
        curly = doc.text.count("“")
        curly_end = doc.text.count("”")
        straight = doc.text.count('"')
        if curly and straight:
            out.append(Finding(
                "warn", "体例", "STYLE-QUOTE", doc.rel(doc.path), 1, "",
                f"引号体例混用：弯引号 {curly} 个、直引号 {straight} 个",
                "统一为中文弯引号「“ ”」（与本仓《工作区规范》一致）",
            ))
        elif straight:
            out.append(Finding(
                "warn", "体例", "STYLE-QUOTE", doc.rel(doc.path), 1, "",
                f"使用直引号 {straight} 个",
                "统一为中文弯引号「“ ”」",
            ))
        if curly != curly_end:
            out.append(Finding(
                "warn", "体例", "STYLE-QUOTE", doc.rel(doc.path), 1, "",
                f"弯引号不配对：开 {curly} / 闭 {curly_end}",
                "检查是否有引号遗漏或多打",
            ))
        if "..." in doc.text:
            out.append(Finding(
                "warn", "体例", "STYLE-ELL", doc.rel(doc.path), 1, "",
                "使用三点省略号「...」",
                "中文正文统一用六点「……」",
            ))
        if re.search(r"(?<!—)—(?!—)", doc.text):
            n = len(re.findall(r"(?<!—)—(?!—)", doc.text))
            out.append(Finding(
                "info", "体例", "STYLE-DASH", doc.rel(doc.path), 1, "",
                f"单破折号「—」出现 {n} 处（双破折号「——」为中文规范用法）",
                "如为插入语请用「——」",
            ))
        if "(" in doc.text and "（" in doc.text:
            out.append(Finding(
                "info", "体例", "STYLE-PAREN", doc.rel(doc.path), 1, "",
                "半角括号「( )」与全角括号「（ ）」混用",
                "中文正文统一用全角括号",
            ))
        for i, line in enumerate(doc.lines, 1):
            if corpus.ignored(line):
                continue
            for m in RE_CLOCK.finditer(line):
                out.append(Finding(
                    "info", "体例", "STYLE-TIME", doc.rel(doc.path), i,
                    line.strip()[:100],
                    f"时刻写作「{m.group(0)}」使用半角冒号",
                    "中文正文时刻统一用全角冒号「：」",
                ))
                break


# ---------------------------------------------------------------------------
# 检查器：TERM
# ---------------------------------------------------------------------------

def check_term(corpus, out):
    """
    术语：
      TERM-MIX    同一文件内同一概念出现多个**非等价**写法（需作者定性）
      TERM-REG    出现未登记的专名候选（配置声明 canon 时的漏登记）

    等价声明：配置里写 ``"equivalent": [["格式化", "矫正"], ...]``
    表示这些写法**刻意并存**，不报 TERM-MIX。
    （子串关系如「楚嫣然／嫣然」本就不算冲突，无需声明。）
    """
    terms = corpus.config.get("terms", {})
    if not terms:
        return
    # 「声明为等价的变体对」：配置里写 equivalent: [[a, b], ...]，
    # 表示同一概念的这两种写法**刻意并存**（如「格式化」是文书说法、
    # 「矫正」是行当说法 —— 两者并存本身就是要表达的设定）。
    # 这些对**不报 TERM-MIX**。
    declared_eq = set()
    for pair in corpus.config.get("equivalent", []):
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            a, b = pair
            declared_eq.add((a, b))
            declared_eq.add((b, a))
    for concept, variants in terms.items():
        variants = list(variants)
        seen_files = defaultdict(set)
        for doc in corpus.docs:
            for i, line in enumerate(doc.lines, 1):
                if corpus.ignored(line):
                    continue
                for v in variants:
                    if v in line:
                        seen_files[doc.rel(doc.path)].add(v)
        # 变体混用：**只有当两个变体都不是对方的子串**才算真冲突
        # （「楚嫣然」与「嫣然」是全名/简称，合法；「楚家」与「楚氏」是同义异写，
        #  需作者定性 —— 取决于配置里是否在 equivalent 里声明了这一对）
        for f, vs in seen_files.items():
            if len(vs) < 2:
                continue
            vs = sorted(vs)
            conflict = []
            for i in range(len(vs)):
                for j in range(i + 1, len(vs)):
                    a, b = vs[i], vs[j]
                    if a in b or b in a:
                        continue        # 全名/简称关系，合法
                    if (a, b) in declared_eq:
                        continue        # 已声明等价（配置 equivalent 段）
                    conflict.append((a, b))
            if conflict:
                a, b = conflict[0]
                out.append(Finding(
                    "warn", "术语", "TERM-MIX", f, 1, "",
                    f"概念「{concept}」在同一文件内出现多个写法：{vs}"
                    f"（如「{a}」与「{b}」）",
                    "统一写法；如为有意别名请在配置里登记为等价变体",
                ))

    # 未登记专名候选：只在配置显式开启（unregistered_scan）时运行，
    # 且要求候选串**以已登记术语为前缀或后缀**（如「冥殿」→「处冥殿」不算，
    # 「冥殿主」算），以压低误报。
    if corpus.config.get("unregistered_scan"):
        all_variants = set()
        for vs in terms.values():
            all_variants.update(vs)
        for doc in corpus.docs:
            for i, line in enumerate(doc.lines, 1):
                if corpus.ignored(line):
                    continue
                for m in re.finditer(r"[一-鿿]{2,8}", line):
                    cand = m.group(0)
                    for v in all_variants:
                        if cand == v or len(v) < 2:
                            continue
                        if (cand.startswith(v) or cand.endswith(v)) \
                                and len(cand) - len(v) <= 2:
                            out.append(Finding(
                                "info", "术语", "TERM-REG", doc.rel(doc.path), i,
                                line.strip()[:100],
                                f"疑似未登记专名「{cand}」（含已登记术语「{v}」）",
                                "确认是否为新专名；是则登记，否则改回原写法",
                            ))
                            break


# ---------------------------------------------------------------------------
# 检查器：DUP
# ---------------------------------------------------------------------------

def check_duplicate(corpus, out, min_cross=36, min_intra=44, top_n=40):
    """
    重复内容：跨文件重复段 + 单文件内重复段。

    全仓规模下配对数是 O(n²)，直接全报会淹没真问题，因此加三道闸：
      · 重复段长度 ≥ min_cross（默认 36 字连续相同才算重复）
      · 重复覆盖率 ≥ 2%（两文件共享的重复段需占较小文件的一定比例）
      · 按重复量排序后**只报前 top_n 对**（默认 40），其余在报告里给总数
    """
    shingles = {}
    for doc in corpus.docs:
        if corpus.is_aggregate(doc):
            continue                      # 合集/导出件不参与跨文件重复比对
        t = normalize_ws(doc.text)
        shingles[id(doc)] = {t[i:i + min_cross] for i in range(max(0, len(t) - min_cross))}
    ids = [id(d) for d in corpus.docs if id(d) in shingles]
    by_id = {id(d): d for d in corpus.docs}

    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = shingles[ids[i]], shingles[ids[j]]
            if not a or not b:
                continue
            inter = a & b
            if not inter:
                continue
            smaller = min(len(a), len(b))
            ratio = len(inter) / smaller if smaller else 0
            if ratio < 0.02:
                continue
            # 确定性取样：inter 是 set，等长 shingle 用 max(..., key=len)
            # 会随 PYTHONHASHSEED 取到不同样本 —— 导致「同一输入同一结果」
            # 不成立、报告产物去重永远不触发。按长度降序 + 字典序固定取值。
            sample = sorted(inter, key=lambda s: (-len(s), s))[0]
            pairs.append((len(inter), ratio, ids[i], ids[j], sample))
    pairs.sort(key=lambda x: (-x[0], -x[1]))
    total_pairs = len(pairs)
    for n, (cnt, ratio, ai, bi, sample) in enumerate(pairs[:top_n], 1):
        out.append(Finding(
            "warn", "重复", "DUP-CROSS", by_id[bi].rel(by_id[bi].path), 1,
            sample[:80],
            f"与「{by_id[ai].rel(by_id[ai].path)}」有 {cnt} 段 ≥{min_cross} 字"
            f"的完全重复（占较小文件 {ratio * 100:.1f}%）",
            "确认是否为有意回扣；非刻意请删改其一",
        ))
    if total_pairs > top_n:
        out.append(Finding(
            "info", "重复", "DUP-SUM", "-", 0, "",
            f"跨文件重复共 {total_pairs} 对，已按重复量降序只列前 {top_n} 对；"
            f"其余 {total_pairs - top_n} 对未逐条列出",
            "如需全量清单，用 --only dup 并缩小审校范围",
        ))

    for doc in corpus.docs:
        if corpus.is_aggregate(doc):
            continue
        t = normalize_ws(doc.text)
        # ⚠️ 计数口径（2026-11-14 修）：
        #   原实现按**每个滑动窗口位置**计数 ⇒ 一处 N 字的重复段会被切成
        #   N-min_intra+1 个偏移窗口，累加成「2860 处」这类失真数字，
        #   无法用于判断文件质量（实测：资料包文件报 142 处，实际仅 1~2 处）。
        #   现改为「极大重复区间」口径：
        #     1) 以 min_intra 为窗口宽，索引出现 ≥2 次的窗口 → 候选重复起点
        #     2) 对相邻两次出现做 LCP 扩展 ⇒ 得到重复区间 [a, a+L)
        #     3) **合并重叠区间** ⇒ 同一处重复的不同偏移归为一处
        #     4) 每区间 = 一处重复；出现次数 = 该区间起点窗口的出现次数
        n = len(t)
        if n < min_intra * 2:
            continue
        occ = defaultdict(list)
        for i in range(max(0, n - min_intra)):
            occ[t[i:i + min_intra]].append(i)
        repeated = {w: ps for w, ps in occ.items() if len(ps) > 1}
        if not repeated:
            continue

        def _lcp(a, b):
            L = 0
            while a + L < n and b + L < n and t[a + L] == t[b + L]:
                L += 1
            return L

        intervals = []
        for ps in repeated.values():
            ps = sorted(ps)
            for i in range(len(ps) - 1):
                a, b = ps[i], ps[i + 1]
                L = _lcp(a, b)
                if L >= min_intra:
                    intervals.append((a, a + L))
        if not intervals:
            continue
        intervals.sort()
        merged = []
        for s, e in intervals:
            if merged and s < merged[-1][1]:      # 严格重叠 ⇒ 同一处重复
                if e > merged[-1][1]:
                    merged[-1][1] = e
            else:
                merged.append([s, e])
        # 每区间 = 一处重复；出现次数取该区间起点窗口的出现次数
        best_seg, best_cnt = None, 0
        for s, _e in merged:
            w = t[s:s + min_intra]
            c = len(repeated.get(w, ()))
            if c > best_cnt:
                best_cnt, best_seg = c, s
        out.append(Finding(
            "warn", "重复", "DUP-INTRA", doc.rel(doc.path), 1,
            (t[best_seg:best_seg + 80] if best_seg is not None else ""),
            f"文件内有 {len(merged)} 处 ≥{min_intra} 字的完全重复段（例出现 {best_cnt} 次）",
            "确认是否为刻意的排比或回扣",
        ))


# ---------------------------------------------------------------------------
# 检查器：STRUCT
# ---------------------------------------------------------------------------

# 仓根标志文件（用于定位仓根；取第一个存在的）
_REPO_MARKERS = (".git", "package.json", "工作区规范.md")


def _find_repo_root():
    """定位仓根：自 cwd 逐层向上找仓根标志文件。

    插件以 ``cwd=仓根`` 调用本引擎，故 cwd 通常即仓根；向上兜底是为了
    允许直接以 ``python tools/doc_review.py`` 从其他目录调用。
    找不到标志文件时退回 cwd（此时第 2 层判定等价于「cwd 下可解析」）。
    """
    cur = Path.cwd().resolve()
    for p in (cur, *cur.parents):
        for marker in _REPO_MARKERS:
            if (p / marker).exists():
                return p
    return cur


def _resolves_in_repo(tok, doc_dir, repo_root):
    """引用 token 能否在仓内解析到真实存在的文件。

    判定顺序（任一命中即视为存在）：
      1. 相对**引用所在文件所在目录**解析（markdown 链接的常规语义）
      2. 相对**仓根**解析（作者写的是仓内相对路径时的常见省略）
      3. 相对**引用所在项目根**解析（项目内写作相对路径、但文件在项目根下时）
      4. 在仓根下按 basename 查找**唯一**匹配（跨项目引用的兜底）

    ⚠️ 只在**仓根之内**查找 —— 否则「包外引用」会被误判为存在，
    失去「登记到外部依赖登记表」的意义。
    """
    tok_norm = tok.replace("\\", "/")
    candidates = []

    # 1) 相对引用文件自身所在目录
    try:
        candidates.append((doc_dir / tok).resolve())
    except OSError:
        pass

    # 2) 相对仓根
    try:
        candidates.append((repo_root / tok_norm).resolve())
    except OSError:
        pass

    # 3) 相对**引用所在项目根**解析
    #    （项目内写作 `bible/world-bible.md` 这类相对路径时，
    #     实际文件在项目根下而非引用文件所在目录下；
    #     仓内同名文件常有多个（如 4 个 world-bible.md），
    #     故按「项目根 + 相对路径」判定比 basename 唯一匹配更准）
    proj_root = _find_project_root(doc_dir, repo_root)
    if proj_root is not None:
        try:
            candidates.append((proj_root / tok_norm).resolve())
        except OSError:
            pass

    for c in candidates:
        if _is_under(c, repo_root) and c.is_file():
            return True

    # 4) 仓根内按 basename 找唯一匹配
    base = os.path.basename(tok_norm)
    if not base:
        return False
    hits = []
    try:
        for p in repo_root.rglob(base):
            if _is_under(p.resolve(), repo_root) and p.is_file():
                hits.append(p)
                if len(hits) > 1:
                    break          # 多个同名 ⇒ 无法唯一判定，交给「不存在」报出
    except OSError:
        return False
    return len(hits) == 1


def _find_project_root(doc_dir, repo_root):
    """定位引用文件所属的「项目根」。

    仓内每个小说项目是一个顶层目录（含自己的正文/设定/bible 等）。
    从引用文件所在目录向上找第一个「仓根的直接子目录」，
    找不到（引用文件本身就在仓根下）则返回 None。
    """
    try:
        rel = doc_dir.resolve().relative_to(repo_root)
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    return repo_root / parts[0]


def _is_under(path, root):
    """path 是否在 root 之内（含 root 自身）。"""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def check_structure(corpus, out):
    """
    结构：
      STRUCT-TABLE  表格列数与表头不一致
      STRUCT-REF    悬空引用（指向不存在的文件）
      STRUCT-HEAD   标题层级跳级
      STRUCT-ENC    编码/BOM/行尾不符合本仓规范
    """
    # --- 表格列数 ---
    for doc in corpus.docs:
        lines = doc.lines
        i = 0
        in_code = False
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("```"):
                in_code = not in_code
                i += 1
                continue
            if in_code:
                i += 1
                continue
            if s.startswith("|") and i + 1 < len(lines) and RE_TABLE_SEP.match(lines[i + 1]):
                ncol = len(split_cells(s))
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    nrow = len(split_cells(lines[j]))
                    if nrow != ncol:
                        out.append(Finding(
                            "error", "结构", "STRUCT-TABLE", doc.rel(doc.path), j + 1,
                            lines[j].strip()[:100],
                            f"表格列数不一致：表头 {ncol} 列，本行 {nrow} 列",
                            "补齐或删减单元格，使列数与表头一致",
                        ))
                    j += 1
                i = j
            else:
                i += 1

    # --- 悬空文件引用 ---
    # 只报**审校范围内**的相对引用；跳过模板占位（XX/xx/＿/＊）、
    # 通配路径、以及审校范围外的绝对路径（那属于「外部依赖登记」职责）。
    #
    # ⚠️ 判定分三层（2026-11-14 修）：
    #   语料内 → 仓内 → 仓外。原先只查「语料内 basename」一层，
    #   而每个项目的语料**只含本项目根下的文件**（huaxi 只扫 华夏克苏鲁/），
    #   于是指向**其他项目**的真实文件（如 ../../二十一世纪奇门遁甲/...）
    #   被误报为「不存在」—— 23 条误报的根因。
    #   现在增加「仓内相对路径可解析」一层，把跨项目引用正确判为存在。
    existing = set()
    for doc in corpus.docs:
        existing.add(doc.path.name)
    # 仓根：以 cwd 为基准（插件以 cwd=仓根 调用引擎），逐层向上找标志文件兜底。
    # 合并说明（2026-11-14）：上游 fd26565 以 Path.cwd() 修「仓根相对路径假红」；
    #   本处改用 _find_repo_root() + _resolves_in_repo()，覆盖同一场景并额外处理
    #   跨项目引用，且 _is_under 保证不会把仓外文件误判为存在。
    repo_root = _find_repo_root()
    for doc in corpus.docs:
        for i, line in enumerate(doc.lines, 1):
            if corpus.ignored(line):
                continue
            for m in RE_FILE_REF.finditer(line):
                tok = m.group(1)
                if tok.startswith("http"):
                    continue
                # 模板占位：第XX章_标题.md / ＿＿ / *.md 通配
                if re.search(r"[xX]{2,}|＿|＊|\*", tok):
                    continue
                base = os.path.basename(tok)
                if base in existing:
                    continue
                # 绝对路径 / 含盘符 → 范围外，交给外部依赖登记表
                if re.match(r"^[A-Za-z]:[\\/]", tok) or tok.startswith("\\\\"):
                    continue
                if "/" not in tok and "\\" not in tok:
                    continue
                # 第 2 层：仓内可解析（相对引用目录 / 仓根 / 项目根 / basename 唯一匹配）
                #   —— 涵盖上游 fd26565 的「仓根工具路径」场景，且带仓内边界校验
                if _resolves_in_repo(tok, doc.path.parent, repo_root):
                    continue
                out.append(Finding(
                    "warn", "结构", "STRUCT-REF", doc.rel(doc.path), i,
                    tok[:80],
                    f"引用了审校范围内不存在的文件「{tok}」",
                    "补文件或改引用；若在包外请登记到外部依赖登记表",
                ))

    # --- 标题层级跳级 ---
    for doc in corpus.docs:
        prev = 0
        in_code = False
        for i, line in enumerate(doc.lines, 1):
            s = line.strip()
            if s.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not s.startswith("#"):
                continue
            m = RE_CHAPTER_HEAD.match(s)
            if not m:
                continue
            level = len(s) - len(s.lstrip("#"))
            if prev and level > prev + 1:
                out.append(Finding(
                    "info", "结构", "STRUCT-HEAD", doc.rel(doc.path), i, s[:100],
                    f"标题层级从 H{prev} 跳到 H{level}",
                    "补齐中间层级，避免目录渲染错乱",
                ))
            prev = level

    # --- 编码 ---
    for doc in corpus.docs:
        try:
            raw = doc.path.read_bytes()
        except Exception:
            continue
        if not raw.startswith(b"\xef\xbb\xbf"):
            out.append(Finding(
                "info", "结构", "STRUCT-ENC", doc.rel(doc.path), 1, "",
                "缺少 UTF-8 BOM（本仓《工作区规范》§六 要求新建文本用 UTF-8-SIG）",
                "如为历史文件可不改；新建文件请带 BOM",
            ))
        if b"\r\n" in raw:
            # 注意：工作区出现 CRLF **未必是仓库缺陷**——
            # git 的 core.autocrlf=true 会在检出时把 LF 转成 CRLF。
            # 因此这里只提示「工作区状态」，并明确指向判定方法
            # （用 `git ls-files --eol` 看索引侧，或 `git cat-file blob` 看入库内容）。
            n_crlf = raw.count(b"\r\n")
            out.append(Finding(
                "info", "结构", "STRUCT-ENC", doc.rel(doc.path), 1, "",
                f"工作区含 CRLF 行尾（{n_crlf} 处）",
                "先确认是入库缺陷还是 autocrlf 检出假象："
                "`git ls-files --eol <file>` 看索引侧（i/lf 即入库干净）、"
                "`git cat-file blob HEAD:<file>` 看入库字节",
            ))


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

CHECKERS = {
    "typo": ("错别字", check_typo),
    "time": ("时间矛盾", check_time),
    "number": ("数字口径", check_number),
    "cond": ("缺失条件", check_condition),
    "style": ("体例", check_style),
    "term": ("术语", check_term),
    "dup": ("重复", check_duplicate),
    "struct": ("结构", check_structure),
}


def run(corpus, only=None):
    out = []
    for key, (label, fn) in CHECKERS.items():
        if only and key not in only:
            continue
        try:
            fn(corpus, out)
        except Exception as e:                          # pragma: no cover
            out.append(Finding("error", "结构", "ENGINE-ERR", "-", 0, "",
                               f"检查器 {key} 执行异常：{type(e).__name__}: {e}",
                               "引擎缺陷，请报 issue；该类检查结果不完整"))
    return out


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

CATEGORY_ORDER = ["错别字", "时间矛盾", "数字口径", "缺失条件",
                  "体例", "术语", "重复", "结构"]
SEV_LABEL = {"error": "ERROR（硬冲突，必看）",
              "warn": "WARN（高概率，需定性）",
              "info": "INFO（体例统计，对照用）"}


def render_markdown(findings, corpus, only):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 文档审校报告")
    lines.append("")
    lines.append(f"- 生成时间：{ts}")
    lines.append(f"- 引擎版本：doc_review.py v{VERSION}")
    lines.append(f"- 被审文件：{len(corpus.docs)} 个")
    lines.append(f"- 发现总数：{len(findings)} 条")
    lines.append("- 铁律：**只出风险与位置，不代改正文**。哪处该改由作者定。")
    if corpus.errors:
        lines.append("")
        lines.append("## 读取异常")
        lines.append("")
        for e in corpus.errors:
            lines.append(f"- {e}")
    counts = Counter(f.severity for f in findings)
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    lines.append(f"- ERROR {counts['error']} 条 ／ WARN {counts['warn']} 条 ／ "
                 f"INFO {counts['info']} 条")
    lines.append("- ERROR 是机器可判定的硬冲突（同一指标两套数值、时间倒挂、"
                 "悬空引用、表格列数不齐），必看。")
    lines.append("- WARN 需作者定性（形近字、术语漂移、重复段），勿当成确定错误。")
    lines.append("- INFO 仅为体例统计，供对照，不要求逐条修改。")
    lines.append("")
    by_cat = Counter(f.category for f in findings)
    lines.append("| 类别 | 合计 | ERROR | WARN | INFO |")
    lines.append("|---|---|---|---|---|")
    for cat in CATEGORY_ORDER:
        if by_cat.get(cat, 0) == 0:
            continue
        sub = Counter(f.severity for f in findings if f.category == cat)
        lines.append(f"| {cat} | {by_cat[cat]} | {sub['error']} | "
                     f"{sub['warn']} | {sub['info']} |")
    for cat in sorted(set(by_cat) - set(CATEGORY_ORDER)):
        sub = Counter(f.severity for f in findings if f.category == cat)
        lines.append(f"| {cat} | {by_cat[cat]} | {sub['error']} | "
                     f"{sub['warn']} | {sub['info']} |")

    for cat in CATEGORY_ORDER + sorted(set(by_cat) - set(CATEGORY_ORDER)):
        group = [f for f in findings if f.category == cat]
        if not group:
            continue
        lines.append("")
        lines.append(f"## {cat}")
        lines.append("")
        for sev in ("error", "warn", "info"):
            sub = [f for f in group if f.severity == sev]
            if not sub:
                continue
            lines.append(f"### {SEV_LABEL[sev]}（{len(sub)} 条）")
            lines.append("")
            for f in sub:
                lines.append(f"- **`{f.file}:{f.line}`** `{f.code}`")
                lines.append(f"  - {f.message}")
                if f.snippet:
                    lines.append(f"  - 原文：{f.snippet}")
                if f.suggestion:
                    lines.append(f"  - 建议：{f.suggestion}")
            lines.append("")
    return "\n".join(lines)


def _protocol_emit(checker: str, findings: list, summary: str = "",
                   artifacts: list | None = None, meta: dict | None = None) -> int:
    """
    按仓根 cordis 编排层的**检查器协议**输出（stdout 一个 JSON 对象）。

    协议定义见 `tools/checker_protocol.py`：
      stdout 只放这一个 JSON；日志/诊断走 stderr。
    退出码：0 无 ERROR ／ 1 有 ERROR ／ 2 协议层故障。
    """
    counts = Counter(f.get("severity", "info") for f in findings)
    payload = {
        "checker": checker,
        "ok": counts["error"] == 0,
        "severity": ("error" if counts["error"] else
                      "warn" if counts["warn"] else
                      "info" if counts["info"] else "none"),
        "summary": summary or f"错误 {counts['error']} ／ 警告 {counts['warn']} ／ 提示 {counts['info']}",
        "counts": {"error": counts["error"], "warn": counts["warn"],
                   "info": counts["info"]},
        "findings": findings,
        "artifacts": artifacts or [],
        "meta": meta or {},
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=1))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 1 if counts["error"] else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="长篇文档审校引擎（只出报告，不代改正文）")
    ap.add_argument("--text", action="append", required=True,
                    help="待审目录或文件，可重复")
    ap.add_argument("--out", default=".", help="报告输出目录")
    ap.add_argument("--config", help="JSON 配置文件")
    ap.add_argument("--only", action="append",
                    help="只跑指定检查：typo/time/number/cond/style/term/dup/struct")
    ap.add_argument("--json", dest="json_path", help="额外的 JSON 输出路径")
    ap.add_argument("--fail-on", choices=["error", "warn", "none"], default="none",
                    help="存在该级别及以上发现时以退出码 1 结束")
    ap.add_argument("--protocol", action="store_true",
                    help="按仓根 cordis 编排层的检查器协议输出（stdout 一个 JSON 对象）")
    args = ap.parse_args(argv)

    config = {}
    if args.config:
        try:
            config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
        except Exception as e:
            print(f"配置读取失败：{e}", file=sys.stderr)
            return 2

    only = set(args.only) if args.only else None
    if only:
        bad = only - set(CHECKERS)
        if bad:
            print(f"未知检查项：{bad}；可用：{sorted(CHECKERS)}", file=sys.stderr)
            return 2

    corpus = Corpus(args.text, config)
    if not corpus.docs:
        msg = "没有可审文件。"
        if args.protocol:
            return _protocol_emit(
                "doc-review",
                [{"severity": "error", "category": "执行", "code": "NO-FILE",
                  "file": "-", "line": 0, "snippet": "",
                  "message": msg, "suggestion": "确认 --text 指向的目录存在且含文本文件"}],
                summary=msg, meta={"errors": corpus.errors})
        print(msg, file=sys.stderr)
        for e in corpus.errors:
            print("  " + e, file=sys.stderr)
        return 2

    findings = run(corpus, only)
    findings.sort(key=lambda f: (SEV_ORDER.get(f.severity, 9),
                                 CATEGORY_ORDER.index(f.category)
                                 if f.category in CATEGORY_ORDER else 99,
                                 f.file, f.line))

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    md_path = outdir / f"doc-review-{stamp}.md"
    json_path = Path(args.json_path) if args.json_path else outdir / f"doc-review-{stamp}.json"

    md_path.write_text(render_markdown(findings, corpus, only), encoding="utf-8-sig")
    json_path.write_text(
        json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=1),
        encoding="utf-8-sig")

    counts = Counter(f.severity for f in findings)
    artifacts = [
        {"kind": "report", "path": str(md_path), "bytes": md_path.stat().st_size},
        {"kind": "json", "path": str(json_path), "bytes": json_path.stat().st_size},
    ]

    if args.protocol:
        return _protocol_emit(
            "doc-review", [f.as_dict() for f in findings],
            summary=f"{len(corpus.docs)} 个文件：错误 {counts['error']} ／ "
                    f"警告 {counts['warn']} ／ 提示 {counts['info']}",
            artifacts=artifacts,
            meta={"files": len(corpus.docs), "readErrors": corpus.errors})

    print("=" * 60)
    print(f"文档审校 · {len(corpus.docs)} 个文件")
    print("=" * 60)
    print(f"  ERROR {counts['error']} ／ WARN {counts['warn']} ／ INFO {counts['info']}")
    by_cat = Counter(f.category for f in findings)
    for cat in CATEGORY_ORDER:
        if by_cat.get(cat):
            sub = Counter(f.severity for f in findings if f.category == cat)
            print(f"  {cat:<8} {by_cat[cat]:<4} "
                  f"(E{sub['error']} W{sub['warn']} I{sub['info']})")
    print("-" * 60)
    for f in findings:
        if f.severity == "error":
            print(f"  × {f.file}:{f.line} [{f.code}] {f.message}")
    print("-" * 60)
    print(f"报告：{md_path}")
    print(f"JSON：{json_path}")

    if args.fail_on == "error" and counts["error"]:
        return 1
    if args.fail_on == "warn" and (counts["error"] or counts["warn"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
