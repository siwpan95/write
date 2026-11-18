#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
素材表形式校验 · tab_lint.py（v3.15 新增，配合 20-素材与设定整理模板.md 工序 3）
--------------------------------------------------------------------------
只查「形式」是否合格，不判断内容对错、不给出定名结论。检查项：
  L1 声明行：归属 / 来源 / 基线 三者是否齐（缺则 WARN，CSV 可关）
  L2 列数：同一张表内每行列数必须等于表头
  L3 键：首列不得为空
  L4 重复键：同键同内容＝纯重复（WARN，可删）；同键不同内容＝重名分歧（INFO，需登记表 4）
     ——表头含「别名」的表是**一对多表**（一键多行是常态），自动跳过本项；
  L5 加粗配对：** 或 ''' 必须成对；且不应落在基线列
  L6 空值分类：空 / — / ?  三种「没有」分别计数；格内出现 无·未知·待定·待补 则 WARN
  L7 编码：UTF-8 可解码（允许 BOM）；含 CRLF 则 WARN

用法：
  python3 tools/tab_lint.py M-02-地名.md
  python3 tools/tab_lint.py --csv M-02-地名.csv
  python3 tools/tab_lint.py *.md          （多份一起查，逐份出结论）
退出码：0 无 ERROR；1 有 ERROR。
"""
import io
import os
import re
import sys

BAD_WORDS = ("无", "未知", "待定", "待补", "TBD", "N/A")
DASHES = ("—", "-", "－")


def read_text(path):
    raw = open(path, "rb").read()
    warn = []
    if b"\r\n" in raw:
        warn.append("L7 含 CRLF（建议统一 LF，避免逐行比对时误判差异）")
    try:
        return raw.decode("utf-8-sig"), warn
    except UnicodeDecodeError as e:
        return raw.decode("utf-8", errors="replace"), warn + ["L7 非 UTF-8（%s），已按替换字符读取" % e]


def split_md_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def split_csv_row(line):
    out, cur, q = [], "", False
    for ch in line:
        if ch == '"':
            q = not q
        elif ch == "," and not q:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def parse_decls(lines):
    """抓 > 归属：… / > 来源：… / > 基线＝A 三类声明。"""
    d = {"归属": None, "来源": None, "基线": None, "来源代号": {}}
    for ln in lines:
        s = ln.strip().lstrip("> ").strip()
        m = re.match(r"^(归属|来源|基线)\s*[：:=＝]\s*(.+)$", s)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "基线":
            d["基线"] = val[:1].upper()
        else:
            d[key] = val
        if key == "来源":
            for code in re.findall(r"([A-Z])\s*[＝=]", val):
                d["来源代号"][code] = None
    return d


def find_tables(lines):
    """返回 [(表头 cells, 起始行号, [行 cells...])]，自动跳过代码栅栏。"""
    tables, i, fence = [], 0, False
    while i < len(lines):
        if lines[i].strip().startswith("```"):
            fence = not fence
            i += 1
            continue
        if (not fence and lines[i].strip().startswith("|")
                and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-\|]+\|\s*$", lines[i + 1])):
            head = split_md_row(lines[i])
            rows, j = [], i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(split_md_row(lines[j]))
                j += 1
            tables.append((head, i + 1, rows))
            i = j
        else:
            i += 1
    return tables


def bold_pairs(cell):
    n = cell.count("**")
    m = cell.count("'''")
    return n // 2, n % 2, m // 2, m % 2


def classify(cell):
    if cell == "":
        return "空"
    if cell in DASHES:
        return "不适用"
    if cell in ("?", "？"):
        return "存疑"
    return "有值"


def lint(path, is_csv=False):
    errs, warns, infos = [], [], []
    text, w = read_text(path)
    warns += w
    lines = text.split("\n")
    decls = parse_decls(lines)

    for k in ("归属", "来源", "基线"):
        if not decls[k]:
            warns.append("L1 缺少「%s」声明行（形式要件 F-%s）" % (k, {"归属": 1, "来源": 2, "基线": 5}[k]))

    if is_csv:
        rows = [split_csv_row(l) for l in lines if l.strip() and not l.startswith("#")]
        if not rows:
            return ["L2 文件为空"], warns, infos
        tables = [(rows[0], 1, rows[1:])]
    else:
        tables = find_tables(lines)
        if not tables:
            return ["L2 未找到 Markdown 表格（需表头 + 分隔行）"], warns, infos

    total_rows = total_empty = total_dash = total_q = total_cells = 0
    for head, start, rows in tables:
        ncol = len(head)
        # 一对多表：表头含「别名」「称呼」的，同键多行是常态，跳过 L4
        one_to_many = any(("别名" in h or "称呼" in h) for h in head)
        # 来源代号 → 列序号
        col_of = {}
        for idx, h in enumerate(head):
            m = re.search(r"(?:来源\s*)?([A-Z])$", h.strip())
            if m:
                col_of[m.group(1)] = idx
        base_idx = col_of.get(decls["基线"]) if decls["基线"] else None

        keys = {}
        for r_i, cells in enumerate(rows, start=start + 1):
            if len(cells) != ncol:
                errs.append("L2 第 %d 行：列数 %d ≠ 表头 %d" % (r_i, len(cells), ncol))
                continue
            total_rows += 1
            total_cells += max(0, len(cells) - 1)
            key = cells[0]
            if key == "":
                errs.append("L3 第 %d 行：键（首列）为空" % r_i)
            else:
                keys.setdefault(key, []).append(tuple(cells[1:]))
            for c_i, cell in enumerate(cells):
                cls = classify(cell)
                if cls == "空":
                    total_empty += 1
                elif cls == "不适用":
                    total_dash += 1
                elif cls == "存疑":
                    total_q += 1
                for bw in BAD_WORDS:
                    if cell == bw:
                        warns.append("L6 第 %d 行第 %d 列：用「%s」占位，应改为空 / — / ?" % (r_i, c_i + 1, bw))
                p2, odd2, p3, odd3 = bold_pairs(cell)
                if odd2 or odd3:
                    errs.append("L5 第 %d 行第 %d 列：加粗标记不成对" % (r_i, c_i + 1))
                if (p2 or p3) and base_idx is not None and c_i == base_idx:
                    warns.append("L5 第 %d 行：基线列（%s）不应加粗——基线自身即基准"
                                 % (r_i, decls["基线"]))

        if one_to_many:
            continue
        same = diff = 0
        for k, v in keys.items():
            if len(v) > 1:
                if len(set(v)) == 1:
                    same += len(v) - 1
                else:
                    diff += len(v) - 1
                    infos.append("L4 重名分歧：键「%s」有 %d 行且写法不同 → 需在表 4 登记" % (k, len(v)))
        if same:
            warns.append("L4 纯重复行 %d 处（同键同内容，可直接删）" % same)

    if total_rows:
        cov = 100.0 * total_empty / max(1, total_cells)
        infos.append("统计：表 %d 张 / 行 %d / 空 %d / 不适用 %d / 存疑 %d / 全表空缺率约 %.1f%%"
                     % (len(tables), total_rows, total_empty, total_dash, total_q, cov))
    return errs, warns, infos


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    is_csv = "--csv" in argv
    if not args:
        print(__doc__)
        return 2
    failed = False
    for p in args:
        if not os.path.exists(p):
            print("× 找不到文件：%s" % p)
            failed = True
            continue
        errs, warns, infos = lint(p, is_csv or p.lower().endswith(".csv"))
        print("=" * 62)
        print("素材表形式校验 · %s" % p)
        print("=" * 62)
        for i in infos:
            print("  · " + i)
        for w in warns:
            print("  ! " + w)
        for e in errs:
            print("  × " + e)
        if errs:
            print("结论：FAIL（%d error / %d warn）" % (len(errs), len(warns)))
            failed = True
        else:
            print("结论：PASS（0 error / %d warn）" % len(warns))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
