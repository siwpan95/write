#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷新进度表 C21–C25 字数为实测值 + 重建 MANIFEST。"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "21": "正文/蜀山 卷二 226–230｜C21 用一次.md",
    "22": "正文/蜀山 卷二 231–235｜C22 往南.md",
    "23": "正文/蜀山 卷二 236–240｜C23 第二次门缝.md",
    "24": "正文/蜀山 卷二 241–245｜C24 别查.md",
    "25": "正文/蜀山 卷二 246–250｜C25 湿封皮.md",
}


def cyc_len(rel):
    t = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    idx = [m.start() for m in re.finditer(r"^# ", t, flags=re.M)] + [len(t)]
    return sum(len(re.sub(r"\s", "", t[idx[i]:idx[i + 1]])) for i in range(1, len(idx) - 1))


def main():
    real = {k: cyc_len(v) for k, v in FILES.items()}
    print("实测字数:", real)

    p = os.path.join(ROOT, "正文/进度表.md")
    s = open(p, encoding="utf-8").read()

    def repl(m):
        return "| {} | V2-C{} | {}–{} | {} | ✅ | {} | {} |".format(
            m.group(1), m.group(1), m.group(2), m.group(3), m.group(4), real[m.group(1)], m.group(5))

    pat = r"\| (2[1-5]) \| V2-C2[1-5] \| (\d+)–(\d+) \| (.+?) \| ✅ \| \d+ \| (2026-11-\d+) \|"
    s2, n = re.subn(pat, repl, s)
    open(p, "w", encoding="utf-8").write(s2)
    print(f"进度表字数已刷新：{n} 行")

    # 重建 MANIFEST
    files = []
    for root, _d, fs in os.walk(ROOT):
        for f in fs:
            rel = os.path.relpath(os.path.join(root, f), ROOT).replace(os.sep, "/")
            if rel.startswith("校验/"):
                continue
            if ".bak-" in rel or rel.startswith(".workbuddy-backup"):
                continue
            files.append(rel)
    files.sort()
    lines = []
    for rel in files:
        h = hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()
        lines.append(h + "  ./" + rel)
    open(os.path.join(ROOT, "校验/MANIFEST.sha256"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"MANIFEST 重建：{len(lines)} 条")


if __name__ == "__main__":
    main()
