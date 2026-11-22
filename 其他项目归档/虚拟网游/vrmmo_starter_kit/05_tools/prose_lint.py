#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prose_lint.py —— 正文体检 + 过审自检

它不评价"写得好不好看"，只回答五个能量化的问题：
    1) 字数够不够这一章的量
    2) 段落是不是太胖（手机阅读，超过 4 行就劝退）
    3) 对话占比对不对（网文甜区 30%–55%，低于 20% 是"叙述自嗨"）
    4) 有没有踩词库里的风险词 / 套话
    5) 开篇 100 字有没有钩子、章末有没有留手

用法
    python3 prose_lint.py --input ../04_manuscript/第01章_停服前夜.md
    python3 prose_lint.py --input ../04_manuscript --glob "*.md"   # 批量
    python3 prose_lint.py --input ../04_manuscript --glob "*.md" --out-md report.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")
# 中英文引号都算对话
DIALOG = re.compile(r"[“「][^”」]{2,}[”」]")

# 章末"留手"的判定词：问句、未完成动作、时间压迫
HOOK_HINTS = ["？", "?", "还没", "却", "但是", "忽然", "突然", "直到", "下一秒",
              "没有回答", "不知道", "只剩", "倒计时", "第", "如果", "除非",
              "然而", "竟然", "原来", "不属于", "脚步声", "正在", "多出", "转过头"]


def read_text(p: Path):
    return p.read_text(encoding="utf-8")


def strip_md(t: str):
    t = re.sub(r"^#{1,6}\s+.*$", "", t, flags=re.M)      # 标题
    t = re.sub(r"^>.*$", "", t, flags=re.M)              # 引用
    t = re.sub(r"^\s*[-*]\s+", "", t, flags=re.M)        # 列表
    t = re.sub(r"\*\*|__|`{1,3}", "", t)                 # 强调/代码
    t = re.sub(r"^\|.*\|$", "", t, flags=re.M)           # 表格
    return t.strip()


def paras(body: str):
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def analyze(text: str, lex: dict):
    body = strip_md(text)
    cjk_chars = len(CJK.findall(body))
    ps = paras(body)
    dia = DIALOG.findall(body)
    dia_chars = sum(len(CJK.findall(d)) for d in dia)

    sentences = [s for s in re.split(r"[。！？!?…]+", body) if CJK.search(s)]
    s_len = [len(CJK.findall(s)) for s in sentences]

    fat = [p for p in ps if len(CJK.findall(p)) > 120]
    skinny = [p for p in ps if 0 < len(CJK.findall(p)) < 8]

    # 风险词
    hits = {"P0": [], "P1": [], "P2": [], "cliches": []}
    for lv in ("P0", "P1", "P2"):
        for item in lex.get(lv, []):
            n = body.count(item["term"])
            if n:
                hits[lv].append({**item, "count": n})
    for item in lex.get("cliches", []):
        n = body.count(item["term"])
        if n:
            hits["cliches"].append({**item, "count": n})

    head = CJK.findall(body)[:0]  # 占位，保持结构清晰
    first100 = body[:100]
    last120 = body[-120:]

    return {
        "chars": cjk_chars,
        "paras": len(ps),
        "avg_para": round(cjk_chars / len(ps), 1) if ps else 0,
        "fat_paras": len(fat),
        "skinny_paras": len(skinny),
        "dialog_ratio": round(dia_chars / cjk_chars * 100, 1) if cjk_chars else 0,
        "avg_sentence": round(sum(s_len) / len(s_len), 1) if s_len else 0,
        "long_sentences": sum(1 for x in s_len if x > 45),
        "hits": hits,
        "first100": first100,
        "last120": last120,
        "hook_score": sum(1 for h in HOOK_HINTS if h in last120),
    }


def grade_report(name: str, a: dict):
    """百分制：把可量化的东西折成分，再用一票否决兜底。"""
    score = 100
    notes = []

    if a["chars"] < 2800:
        score -= 15; notes.append(f'字数 {a["chars"]}，低于单章 2800 的安全线')
    if a["avg_para"] > 90:
        score -= 10; notes.append(f'平均段长 {a["avg_para"]} 字，手机上一屏看不完，拆段')
    if a["fat_paras"]:
        score -= min(15, a["fat_paras"] * 3); notes.append(f'有 {a["fat_paras"]} 个超长段落（>120 字）')
    if a["dialog_ratio"] < 20:
        score -= 12; notes.append(f'对话占比 {a["dialog_ratio"]}%，偏"叙述自嗨"')
    if a["dialog_ratio"] > 60:
        score -= 6; notes.append(f'对话占比 {a["dialog_ratio"]}%，场景感被稀释')
    if a["avg_sentence"] > 32:
        score -= 8; notes.append(f'平均句长 {a["avg_sentence"]} 字，读着累')
    if a["hook_score"] == 0:
        score -= 12; notes.append("章末没有留手，读者没有点下一章的理由")

    cl = len(a["hits"]["cliches"])
    if cl:
        score -= min(12, cl * 2); notes.append(f"套话 {cl} 处")

    p0, p1 = len(a["hits"]["P0"]), len(a["hits"]["P1"])
    if p0:
        score = min(score, 40); notes.append(f"⛔ P0 风险词 {p0} 处，必须改设定，不是改词")
    if p1:
        score -= min(20, p1 * 4); notes.append(f"⚠️ P1 需替换 {p1} 处")

    score = max(0, min(100, score))
    return score, notes


def render_one(path: Path, a: dict, score: int, notes: list):
    L = [f'### {path.name}\n']
    L.append(f'**体检分：{score}/100**\n')
    L.append("| 指标 | 值 | 参考 |")
    L.append("|---|---|---|")
    L.append(f'| 正文字数 | {a["chars"]} | 2800–4000 |')
    L.append(f'| 段落数 / 平均段长 | {a["paras"]} / {a["avg_para"]} 字 | 平均 ≤ 90 |')
    L.append(f'| 超长段落(>120字) | {a["fat_paras"]} | 0 |')
    L.append(f'| 对话占比 | {a["dialog_ratio"]}% | 30–55% |')
    L.append(f'| 平均句长 | {a["avg_sentence"]} 字 | ≤ 32 |')
    L.append(f'| 长句(>45字) | {a["long_sentences"]} | 越少越好 |')
    L.append(f'| 章末留手信号 | {a["hook_score"]} | ≥ 2 |')
    L.append("")

    if notes:
        L.append("**诊断**\n")
        for n in notes:
            L.append(f"- {n}")
        L.append("")
    else:
        L.append("✅ 各项达标。\n")

    for lv, title in (("P0", "⛔ P0 一票否决"), ("P1", "⚠️ P1 必须替换"), ("P2", "○ P2 建议优化")):
        if a["hits"][lv]:
            L.append(f"**{title}**\n")
            L.append("| 词 | 次数 | 问题 | 改法 |")
            L.append("|---|---|---|---|")
            for h in a["hits"][lv]:
                L.append(f'| {h["term"]} | {h["count"]} | {h["note"]} | {h["fix"]} |')
            L.append("")
    if a["hits"]["cliches"]:
        L.append("**套话清单**\n")
        L.append("| 套话 | 次数 | 为什么是问题 |")
        L.append("|---|---|---|")
        for h in a["hits"]["cliches"]:
            L.append(f'| {h["term"]} | {h["count"]} | {h["why"]} |')
        L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="正文体检与过审自检")
    ap.add_argument("--input", required=True, help="md 文件或目录")
    ap.add_argument("--glob", default="*.md")
    ap.add_argument("--lexicon", default="data/sensitive_lexicon.json")
    ap.add_argument("--out-md", default=None)
    ap.add_argument("--stop-at", default=None, help="只体检该分隔符之前的内容（用于含附录的稿件）")
    ap.add_argument("--exclude", default=None, help="逗号分隔的文件名关键字，命中的文件跳过")
    args = ap.parse_args(argv)

    base = Path(__file__).parent
    lex_path = Path(args.lexicon)
    if not lex_path.is_absolute():
        lex_path = (base / lex_path).resolve()
    lex = json.loads(lex_path.read_text(encoding="utf-8"))

    p = Path(args.input)
    if not p.is_absolute():
        p = (base / p).resolve()
    if "*" in str(p):
        files = sorted(Path().glob(str(p)))
    else:
        files = sorted(p.glob(args.glob)) if p.is_dir() else [p]
    if args.exclude:
        keys = [k.strip() for k in args.exclude.split(",") if k.strip()]
        files = [f for f in files if not any(k in f.name for k in keys)]
    if not files:
        print("[x] 没有匹配到文件", file=sys.stderr)
        return 1

    L = ["# 正文体检报告（prose_lint.py 生成）\n"]
    total = 0
    for f in files:
        raw = read_text(f)
        if args.stop_at and args.stop_at in raw:
            raw = raw.split(args.stop_at)[0]
        a = analyze(raw, lex)
        s, notes = grade_report(f.name, a)
        total += a["chars"]
        L.append(render_one(f, a, s, notes))

    L.append(f"---\n\n合计正文 **{total}** 字 / {len(files)} 个文件。")
    md = "\n".join(L)
    print(md)

    if args.out_md:
        op = Path(args.out_md)
        if not op.is_absolute():
            op = (base / op).resolve()
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(md, encoding="utf-8")
        print(f"\n[√] 已写入 {op}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
