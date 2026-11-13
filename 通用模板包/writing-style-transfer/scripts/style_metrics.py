#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style_metrics.py —— 网文文风量化指标（通用模板包 · 中性工具）

用法：python style_metrics.py 文件1.md 文件2.md ...
或：python style_metrics.py --stdin  （从管道读入单篇）

指标：平均句长 / 短句占比(<=15字) / 长句占比(>35字) / 句长标准差 /
      单句成段占比 / 对话占比 / 逗号密度(每百字) / 感叹号数 / 破折号数
说明：句子以 。！？… 切分；段落以换行切分；对话=引号“”内字符占比。
"""
import sys, re, statistics, io

def metrics(text: str) -> dict:
    text = re.sub(r"^#+ .*$", "", text, flags=re.M)          # 去标题行
    text = re.sub(r"^>\s?", "", text, flags=re.M)            # 去引用前缀
    text = re.sub(r"^\|.*$", "", text, flags=re.M)           # 去表格行
    body = text.strip()
    total_chars = len(re.sub(r"\s", "", body)) or 1

    paras = [p for p in re.split(r"\n+", body) if p.strip()]
    sentences = []
    for p in paras:
        sentences += [s.strip() for s in re.split(r"(?<=[。！？…])", p) if s.strip()]

    lens = [len(re.sub(r"[\s，。！？…、；：”“”]", "", s)) for s in sentences]
    n = len(lens) or 1
    short = sum(1 for x in lens if x <= 15) / n
    long_ = sum(1 for x in lens if x > 35) / n
    single = 0
    for p in paras:
        cnt = len([s for s in re.split(r"(?<=[。！？…])", p.strip()) if s.strip()])
        if cnt <= 1:
            single += 1
    single /= max(len(paras), 1)

    dialogue = sum(len(m) for m in re.findall(r"“([^”]*)”", body)) / total_chars
    commas = len(re.findall(r"，", body)) / total_chars * 100

    return {
        "字符数": total_chars,
        "句数": n,
        "平均句长": round(sum(lens) / n, 1),
        "短句占比": f"{short:.0%}",
        "长句占比": f"{long_:.0%}",
        "句长标准差": round(statistics.pstdev(lens), 1) if n > 1 else 0.0,
        "单句成段占比": f"{single:.0%}",
        "对话占比": f"{dialogue:.0%}",
        "逗号/百字": round(commas, 1),
        "感叹号": len(re.findall(r"！(?!”)", body)),
        "破折号": len(re.findall(r"—", body)),
    }

def main():
    args = sys.argv[1:]
    if "--stdin" in args:
        text = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8").read()
        rows = [("STDIN", metrics(text))]
    else:
        rows = []
        for path in args:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                rows.append((path, metrics(f.read())))
    keys = list(rows[0][1].keys())
    for k in keys:
        line = " | ".join(f"{v}" for _, v in rows)
        print(f"{k:<10}", line)
    print("\n文件:", " ; ".join(r[0] for r in rows))

if __name__ == "__main__":
    main()
