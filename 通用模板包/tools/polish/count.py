#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""count.py —— 字数与格式硬校验（唯一计数口径）

口径（固定，不要改）：
    汉字数 = 全文 Unicode 汉字（含章节标题行），不含标点、空格、数字、拉丁字母。
    PASS   = 汉字数 >= min_han 且 全角括号数 == 0 且 全角引号配对 且 无半角标点混入。

用法：
    python3 tools/count.py draft/ch126.md
    python3 tools/count.py draft/            # 目录下所有 ch*.md，按章号排序
    python3 tools/count.py draft/ch126.md --min 3200
    python3 tools/count.py draft/ch126.md --json
    python3 tools/count.py draft/ch126.md --quiet     # 只输出一行结果

退出码：0 全通过；2 有不合格；3 参数/文件错误。
"""
import os
import re
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_min():
    try:
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            return int(json.load(f).get("min_han", 3000))
    except Exception:
        return 3000


HALF_PUNCT = re.compile(r"[,.?!;:]")
CH_RE = re.compile(r"^第\s*\d+\s*章")


def stats(path, min_han):
    text = open(path, encoding="utf-8-sig").read()
    han = len(re.findall(r"[\u4e00-\u9fa5]", text))
    paren = text.count("\uff08") + text.count("\uff09")
    lq, rq = text.count("\u201c"), text.count("\u201d")
    paras = [l.strip() for l in text.split("\n") if l.strip()]
    # 半角标点混入：排除数字中的小数点、时间冒号、英文缩写
    half = 0
    for m in HALF_PUNCT.finditer(text):
        i = m.start()
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if m.group() == "." and prev.isdigit() and nxt.isdigit():
            continue
        if m.group() == ":" and prev.isdigit() and nxt.isdigit():
            continue
        half += 1
    # 连续标点（。。。 / ，， / ！！ 之类）
    cont = len(re.findall(r"[，。！？、；：]{2,}", text))
    # 空段落已由 paras 过滤；标题行数
    titles = sum(1 for p in paras if CH_RE.match(p))
    ok = (han >= min_han) and (paren == 0) and (lq == rq) and (half == 0)
    return dict(
        file=os.path.basename(path), han=han, paren=paren,
        quote_l=lq, quote_r=rq, half=half, cont=cont,
        paras=len(paras), titles=titles, ok=ok, path=path,
    )


def collect(args):
    files, rest = [], []
    for a in args:
        if a.startswith("-"):
            rest.append(a)
            continue
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "ch*.md")),
                            key=lambda p: int(re.search(r"(\d+)", os.path.basename(p)).group(1))
                            if re.search(r"(\d+)", os.path.basename(p)) else 0)
        elif os.path.exists(a):
            files.append(a)
        else:
            print("MISSING " + a)
    return files


def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    quiet = "--quiet" in argv
    min_han = load_min()
    if "--min" in argv:
        min_han = int(argv[argv.index("--min") + 1])
    files = collect([a for a in argv if a not in ("--json", "--quiet", "--min", str(min_han))])
    if not files:
        print(__doc__)
        return 3

    rows = [stats(f, min_han) for f in files]
    if as_json:
        print(json.dumps([{k: v for k, v in r.items() if k != "path"} for r in rows],
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            flag = "PASS" if r["ok"] else "FAIL"
            reasons = []
            if r["han"] < min_han:
                reasons.append("欠%d字" % (min_han - r["han"]))
            if r["paren"]:
                reasons.append("括号%d" % r["paren"])
            if r["quote_l"] != r["quote_r"]:
                reasons.append("引号%d/%d" % (r["quote_l"], r["quote_r"]))
            if r["half"]:
                reasons.append("半角%d" % r["half"])
            if r["cont"]:
                reasons.append("连续标点%d" % r["cont"])
            tail = "" if r["ok"] else "  ← " + "，".join(reasons)
            if not quiet:
                print("%-22s 汉字%5d  括号%d  引号%d/%d  半角%d  段%3d  %s%s" % (
                    r["file"], r["han"], r["paren"], r["quote_l"], r["quote_r"],
                    r["half"], r["paras"], flag, tail))
            else:
                print("%s %s %d" % (r["file"], flag, r["han"]))
        total = sum(r["han"] for r in rows)
        bad = sum(1 for r in rows if not r["ok"])
        print("合计 %d 章，汉字 %d，不合格 %d 章（下限 %d）" % (len(rows), total, bad, min_han))
    return 0 if all(r["ok"] for r in rows) else 2


if __name__ == "__main__":
    sys.exit(main())
