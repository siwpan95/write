#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docs/11 lint · 文档级静态检查（零依赖，纯标准库）

用途：00 号文件是本项目的"唯一索引"，但索引靠人工维护，五轮迭代后必然滞后。
本脚本把评审中发现的四类问题固化成可重复执行的检查，避免下一轮再靠人眼通读。

用法：
    python tools/lint/check_docs.py --root docs
    python tools/lint/check_docs.py --root docs --json out.json

退出码：
    0  无 FAIL（可能有 WARN / INFO）
    1  至少一条 FAIL
    2  目录或文件缺失

检查项见文件末尾 CHECKS 表。全部为文本级检查，不判断内容对错，
只判断"是否违反本项目自己立的纪律"。
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------- 基础结构

@dataclass
class Finding:
    code: str
    level: str          # FAIL / WARN / INFO
    where: str          # 文件名:行号 或 文件名
    msg: str

@dataclass
class Report:
    findings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, code, level, where, msg):
        self.findings.append(Finding(code, level, where, msg))

    def count(self, level):
        return sum(1 for f in self.findings if f.level == level)


# ---------------------------------------------------------------- 常量

# 十六母题（短关键词，用于覆盖性检查；02 号文件的写法不含"与"）
MOTIF_KEYS = [
    ("01", "死亡与腐朽"), ("02", "身体异化"), ("03", "不可名状"), ("04", "幽灵与怨念"),
    ("05", "阈限空间"), ("06", "镜像与分身"), ("07", "窥视"), ("08", "仪式与禁忌"),
    ("09", "在册"), ("10", "代价与结算"), ("11", "名分"), ("12", "管辖"),
    ("13", "言语与效力"), ("14", "计量"), ("15", "因果与归因"), ("16", "同化"),
]

# 03 号文件标 ❓（未联网复核）的点，如果在其他文档里被当成断言使用，应报警
UNVERIFIED_PAIRS = [
    # (未核主体, 被断言的具体表述, 说明)
    ("阅微草堂笔记", "卷十", "03 标『卷次未核』，01 直接写『卷十』"),
]

# 证据档位标记
TIER_RE = re.compile(r"〔[ABCD]〕")

MOTIF_SECTION_01 = re.compile(r"^## 母题[一二三四五六七八九十]+ ·")
MOTIF_SECTION_08 = re.compile(r"^### \d+ · `")

INDEX_FILE = "00_项目总纲与路线图.md"
MEDIA_FILE = "02_母题×媒介矩阵.md"
CITE_FILE = "03_M6引用核对表.md"
MOTIF_LIB_01 = "01_八母题R规程库.md"
MOTIF_LIB_08 = "08_十六母题库.md"


# ---------------------------------------------------------------- 工具函数

def read_all(root):
    """返回 {文件名: [行, ...]}，只收 .md"""
    docs = {}
    for name in sorted(os.listdir(root)):
        if name.lower().endswith(".md"):
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                docs[name] = fh.read().splitlines()
    return docs


def find(docs, keyword):
    """返回 [(文件名, 行号, 行内容)]"""
    hits = []
    for name, lines in docs.items():
        for i, line in enumerate(lines, 1):
            if keyword in line:
                hits.append((name, i, line.strip()))
    return hits


# ---------------------------------------------------------------- 检查项

# 元讨论标记：评审/核对类文本会"引述问题本身"，不能算作违规
META_CTX = ("已过期", "建议改", "建议统一", "应改", "残留", "违反", "问题",
            "仍写", "照用", "纪律", "待核", "未核", "❓")


def is_meta(line):
    return any(m in line for m in META_CTX)


def d01_version_drift(docs, rep):
    """D01 版本残留：已废弃的表述仍在流通（排除元讨论）"""
    for name, i, line in find(docs, "八选一"):
        if is_meta(line):
            continue
        rep.add("D01", "WARN", f"{name}:{i}",
                "『八选一』已过期（母题已扩到 16 条），建议改为『十六选一作主』")


def d02_index_lag(docs, rep):
    """D02 索引滞后：docs/ 下存在未在 00 号文件登记的文件（孤儿件）"""
    if INDEX_FILE not in docs:
        rep.add("D02", "WARN", INDEX_FILE, "未找到唯一索引文件，跳过索引检查")
        return
    index_text = "\n".join(docs[INDEX_FILE])
    registered = set(re.findall(r"[\w\u4e00-\u9fa5×\-]+\.md", index_text))
    for name in docs:
        if name == INDEX_FILE:
            continue
        if name not in registered:
            rep.add("D02", "WARN", name, "未在 00 号文件登记为孤儿件")


def d03_coverage(docs, rep):
    """D03 覆盖性：02 媒介矩阵是否覆盖十六母题"""
    if MEDIA_FILE not in docs:
        rep.add("D03", "FAIL", MEDIA_FILE, "文件缺失，无法检查覆盖性")
        return
    text = "\n".join(docs[MEDIA_FILE])
    missing = [f"{nid} {key}" for nid, key in MOTIF_KEYS if key not in text]
    if missing:
        rep.add("D03", "FAIL", MEDIA_FILE,
                f"仅覆盖 {16 - len(missing)}/16 母题，缺：{'、'.join(missing)}")


def d04_unverified_claims(docs, rep):
    """D04 未核项照用：核对表标 ❓ 的内容在其他文档里被当成断言

    注意区分「断言」与「元讨论」：评审/核对类文字会引述问题本身
    （例如"03 标卷次未核，01 却写卷十"），这类命中不算违规。
    """
    if CITE_FILE not in docs:
        rep.add("D04", "WARN", CITE_FILE, "文件缺失，跳过")
        return
    cite_text = "\n".join(docs[CITE_FILE])
    META = ("未核", "待核", "❓", "违反", "问题", "应改", "照用", "纪律")
    for subject, claim, note in UNVERIFIED_PAIRS:
        if subject not in cite_text or "❓" not in cite_text:
            continue
        for name, i, line in find(docs, claim):
            if name == CITE_FILE:
                continue
            ctx = "\n".join(docs[name][max(0, i - 2):i + 1])
            if any(m in ctx for m in META):
                continue
            if subject in line or subject in "\n".join(docs[name][max(0, i - 6):i + 6]):
                rep.add("D04", "FAIL", f"{name}:{i}", f"{note}（违反 00 §4 混层即废稿）")


def d05_tier_missing(docs, rep):
    """D05 档位缺失：母题条目必须带〔A〕/〔B〕/〔C〕证据档位"""
    for fname, section_re in ((MOTIF_LIB_01, MOTIF_SECTION_01),
                              (MOTIF_LIB_08, MOTIF_SECTION_08)):
        if fname not in docs:
            rep.add("D05", "WARN", fname, "文件缺失，跳过")
            continue
        lines = docs[fname]
        starts = [i for i, l in enumerate(lines) if section_re.match(l)]
        if not starts:
            continue
        missing = []
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            body = "\n".join(lines[start:end])
            if not TIER_RE.search(body):
                missing.append(lines[start].strip("# ").strip())
        if missing:
            rep.add("D05", "FAIL", fname,
                    f"{len(missing)}/{len(starts)} 个母题条目无证据档位："
                    f"{'｜'.join(missing[:8])}")


def d06_formula_notation(docs, rep):
    """D06 公式记号混用：Δm 与 Δ 并存，读者无法判断哪个是唯一版本"""
    hits_m = [(n, i) for n, i, l in find(docs, "× Δm") if not is_meta(l)]
    hits_plain = [(n, i) for n, i, l in find(docs, "× Δ")
                  if "× Δm" not in l and not is_meta(l)]
    if hits_m and hits_plain:
        rep.add("D06", "WARN", "多处",
                f"『× Δm』{len(hits_m)} 处 vs『× Δ』{len(hits_plain)} 处并存，"
                f"建议统一为 Δm 并在 07 号文件声明 Δ ≡ Δm")


def d07_same_name(docs, rep):
    """D07 同名异指：『本体层』在 08 号文件内指两个不同集合"""
    if MOTIF_LIB_08 not in docs:
        return
    text = "\n".join(docs[MOTIF_LIB_08])
    if text.count("本体层") >= 2 and "2 件" in text and "A 组" in text:
        rep.add("D07", "WARN", MOTIF_LIB_08,
                "『本体层』同时指『零件库 2 件』与『A 组 8 条母题』，建议改名（如 A 组改称『本体-感官层』）")


def d08_blind_read(docs, rep):
    """D08 验证闭环：只写了『待盲读』而无排序结果，说明证伪实验未收尾"""
    hits = find(docs, "盲读")
    if not hits:
        return
    all_text = "\n".join("\n".join(v) for v in docs.values())
    planned = re.search(r"待盲读|盲读结果出来之前|盲读包已备|盲读包（", all_text)
    # 结果侧证据：排序表、名次、一致性系数
    resolved = re.search(r"Kendall|一致率|名次|排序为|读者甲|W\s*=\s*0?\.", all_text)
    if planned and not resolved:
        rep.add("D08", "INFO", hits[0][0],
                f"『盲读』出现 {len(hits)} 次，但只有『已备/待结果』，无排序数据；"
                f"证伪实验处于未收尾状态，H2 无法判死")


CHECKS = [
    ("D01", "版本残留", d01_version_drift),
    ("D02", "索引滞后（孤儿件）", d02_index_lag),
    ("D03", "覆盖性（16 母题 × 媒介）", d03_coverage),
    ("D04", "未核项照用", d04_unverified_claims),
    ("D05", "证据档位缺失", d05_tier_missing),
    ("D06", "公式记号混用", d06_formula_notation),
    ("D07", "同名异指", d07_same_name),
    ("D08", "验证闭环", d08_blind_read),
]


# ---------------------------------------------------------------- 主程序

def main():
    ap = argparse.ArgumentParser(description="docs lint for horror-motif-lab")
    ap.add_argument("--root", default="docs", help="文档目录（默认 docs）")
    ap.add_argument("--json", default=None, help="把结果写成 JSON")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"[ERROR] 目录不存在：{args.root}", file=sys.stderr)
        return 2

    docs = read_all(args.root)
    if not docs:
        print(f"[ERROR] 目录内无 .md 文件：{args.root}", file=sys.stderr)
        return 2

    rep = Report()
    rep.stats = {
        "files": len(docs),
        "chars": sum(len("\n".join(v)) for v in docs.values()),
    }
    for code, title, fn in CHECKS:
        fn(docs, rep)

    # ---- 输出
    print("=" * 68)
    print(f"docs lint v1.0 ｜ root={args.root} ｜ "
          f"{rep.stats['files']} 份 / {rep.stats['chars']:,} 字符")
    print("=" * 68)

    order = {"FAIL": 0, "WARN": 1, "INFO": 2}
    for f in sorted(rep.findings, key=lambda x: (order[x.level], x.code)):
        print(f"[{f.level:4}] {f.code}  {f.where}")
        print(f"        {f.msg}")

    if not rep.findings:
        print("（无发现）")

    print("-" * 68)
    print(f"结论：FAIL {rep.count('FAIL')} ｜ WARN {rep.count('WARN')} ｜ INFO {rep.count('INFO')}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"stats": rep.stats,
                       "findings": [f.__dict__ for f in rep.findings]},
                      fh, ensure_ascii=False, indent=2)
        print(f"JSON 已写入 {args.json}")

    return 1 if rep.count("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
