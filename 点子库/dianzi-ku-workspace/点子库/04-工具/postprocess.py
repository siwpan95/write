# -*- coding: utf-8 -*-
"""后处理：将正文中的章/节标题行提升为 Markdown 标题。"""
import re
import glob

H_CHAPTER = re.compile(r"^(第[一二三四五六七八九十]+章\s*[·・.]?.*)$")
H_SECTION = re.compile(r"^(\d+\.\d+\s+.+)$")
H_ALT = re.compile(r"^(序章[：:].*|附录\s*[·・.]?.*|表[A-F]\s*·.*)$")

for path in sorted(glob.glob("/sandbox/workspace/output/法则权能设定集/*.md")):
    if path.endswith("README.md"):
        continue
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        # 只处理标题行（跳过引用块与表格）
        if line.startswith(">") or line.startswith("|") or line.startswith("#"):
            out.append(line)
        elif H_CHAPTER.match(s):
            out.append(f"\n## {s}\n")
        elif H_SECTION.match(s) and len(s) < 60:
            out.append(f"### {s}")
        elif H_ALT.match(s) and len(s) < 60:
            out.append(f"## {s}")
        else:
            out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("processed:", path.split("/")[-1])
