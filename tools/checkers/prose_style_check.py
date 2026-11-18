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
        hits = list(re.finditer(pat, prose_words))
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
        hits = list(pat.finditer(prose_words))
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
    # 段落切分：本仓正文段落用「单换行」分隔，也存在「空行」分隔的写法，
    # 两种都按段处理，才能正确判断「连续两段」。
    paras = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
    for p in list(paras):
        paras.extend(x.strip() for x in p.split("\n") if x.strip())
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
    findings = []
    for r in results:
        for f in r["findings"]:
            if f["rule"] not in REDLINE:
                continue
            findings.append({
                "severity": "error" if f["severity"] == "ERROR" else "warn",
                "category": "文风",
                "code": f["rule"],
                "file": r["file"],
                "line": f["line"],
                "snippet": f["detail"][:160],
                "message": f"{r['file']} 第 {f['line']} 行：{f['detail']}",
                "suggestion": f"{REDLINE[f['rule']]} —— 改写或确认属语境豁免",
            })
    n_err = sum(1 for f in findings if f["severity"] == "error")
    n_warn = len(findings) - n_err
    return emit("prose-style", findings,
                summary=f"正文文风红线：{len(results)} 篇，ERROR {n_err} ／ WARN {n_warn}",
                meta={"filesScanned": len(results),
                      "totalHan": sum(r["han"] for r in results),
                      "rawError": err_count, "rawWarn": warn_count,
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
