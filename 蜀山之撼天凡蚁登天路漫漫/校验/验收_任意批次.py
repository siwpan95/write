#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用批次验收（任何批次都能用）。

用法：
    python3 校验/验收_任意批次.py <起章> <止章> <文件1> [文件2 ...]
    例：python3 校验/验收_任意批次.py 251 255 "正文/蜀山 卷三 251–255｜C1 押册下海.md"

判定口径（见 正文/_正文施工规格-V2-C21至C25.md §一）：
  篇幅   纯正文 2200–3000（非空白全字符，不含章标题行与末尾「（本章完）」）
         白名单章（校验/篇幅白名单.md 登记、经重复检测确认无无效重复）放宽上限
  格式   零引号（“ ” 「 」 与 ASCII " 均为 0）
  人名   「杨成志」每章 ≥2 次
  禁用   现代词（05 §1.2.1 A/B/C 三类）
  结构   章号连续、章数正确、每章末行「（本章完）」
  内容   章内重复段（只查括号内叙述段，实质字数 ≥12，两次间隔 <8 段才算机械复制）
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

QUOTES = ["“", "”", "「", "」", '"']


def load_whitelist():
    """读 校验/篇幅白名单.md：表格里第一列是章号的行，视为合法超限章。"""
    p = os.path.join(ROOT, "校验", "篇幅白名单.md")
    if not os.path.exists(p):
        return {}
    out = {}
    for ln in open(p, encoding="utf-8"):
        m = re.match(r"^\|\s*(\d{3})\s*\|\s*(\d+)\s*\|", ln)
        if m:
            out[int(m.group(1))] = int(m.group(2))
    return out


WHITELIST = load_whitelist()
BAD_WORDS = [
    # A 类：康熙二年无此物／境界链（F-35）
    "系统", "面板", "图标", "属性", "等级", "面板", "等级",
    # B 类：现代词穿越
    "bug", "程序", "数据", "代码", "加载",
    "KPI", "打工人", "内卷", "躺平", "破防", "社死", "降维", "CPU", "PUA",
    "流量", "热搜", "二次元", "梗",  # 「副本」已移除：古汉语「送…录副本一册」合法，非游戏义
    # C 类：伪轻小说腔
    "命运的齿轮", "深邃的眼眸", "嘴角勾起", "邪魅", "心头一颤",
]


def find_dup_segments(body):
    """章内实质重复的叙述段（括号内）。
    口径：① 只查以「（」开头的叙述段（对白回环是刻意手法，不判错）
          ② 去标点后实质字数 ≥12
          ③ 两次出现间隔 <8 段才算机械复制（间隔大＝刻意回环）"""
    lines = [x.strip() for x in body.split("\n") if x.strip()]
    pos = {}
    for idx, s in enumerate(lines):
        if not s.startswith("（"):
            continue
        core = re.sub(r"[（）()。，、？！：；“”\"'…—\s]", "", s)
        if len(core) >= 12:
            pos.setdefault(s, []).append(idx)
    out = []
    for s, idxs in pos.items():
        if len(idxs) < 2:
            continue
        gaps = [idxs[i + 1] - idxs[i] for i in range(len(idxs) - 1)]
        if min(gaps) < 8:
            out.append(s)
    return out


def check_one(path, exp_start, exp_count):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    if not os.path.exists(path):
        print(f"[E] 文件不存在：{rel}")
        return 1
    t = open(path, encoding="utf-8").read()
    parts = re.split(r"^# 第 (\d+) 章 (.+)$", t, flags=re.M)
    if len(parts) < 3:
        print(f"[E] {rel}：未找到章级标题")
        return 1
    got = [(int(parts[i]), parts[i + 1].strip(), parts[i + 2])
           for i in range(1, len(parts) - 1, 3)]
    errs = 0
    if len(got) != exp_count:
        print(f"[E] {rel}：章数应为 {exp_count}，实为 {len(got)}")
        errs += 1
    for i, (num, title, body) in enumerate(got):
        pure = re.sub(r"^#.*$", "", body, flags=re.M).replace("（本章完）", "")
        n = len(re.sub(r"\s", "", pure))
        q = sum(body.count(x) for x in QUOTES)
        y = body.count("杨成志")
        hits = [w for w in BAD_WORDS if w in body]
        endmark = body.rstrip().endswith("（本章完）")
        e = []
        if num != exp_start + i:
            e.append(f"章号应为 {exp_start + i}")
        cap = WHITELIST.get(num, 3000)
        if not (2200 <= n <= cap):
            e.append(f"篇幅 {n} 越界(2200-{cap})")
        elif n > 3000:
            pass  # 白名单内的合法超限，不报错
        if q:
            e.append(f"引号 {q} 处")
        if y < 2:
            e.append(f"杨成志 {y} 次")
        if hits:
            e.append(f"禁用词 {hits}")
        if not endmark:
            e.append("结尾缺（本章完）")
        dup = find_dup_segments(body)
        if dup:
            e.append(f"章内重复段 ×{len(dup)}：{dup[0][:20]}")
        if e:
            errs += 1
            print(f"  {num} {title[:16]:18} {n:6}字 引号{q:3} 杨{y:3}  [E] {'; '.join(e)}")
        else:
            print(f"  {num} {title[:16]:18} {n:6}字 引号{q:3} 杨{y:3}  OK")
    return errs


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        print("用法：python3 校验/验收_任意批次.py <起章> <止章> <文件...>")
        return 2
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    files = sys.argv[3:]
    total_err = 0
    total_ch = 0
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        print(f"\n=== {os.path.basename(f)} ===")
        total_err += check_one(p, start, end - start + 1)
        total_ch += end - start + 1
    print("\n" + "=" * 60)
    print(f"批次结论: {'PASS' if total_err == 0 else f'FAIL {total_err} 项'}（共验 {total_ch} 章）")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
