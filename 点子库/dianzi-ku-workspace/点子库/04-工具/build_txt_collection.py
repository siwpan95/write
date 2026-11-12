import os, re

src = r"G:/repos/write/点子库/dianzi-ku-workspace/点子库/02-正文"
out = os.path.join(src, "法则权能-正文合集.txt")

# 收集所有 .md，排除创作说明 README，按文件名数字前缀排序
entries = []
for f in os.listdir(src):
    if not f.endswith(".md"):
        continue
    if f == "README-创作说明.md":
        continue
    m = re.match(r"^(\d+)-", f)
    if not m:
        continue
    entries.append((int(m.group(1)), f))
entries.sort(key=lambda x: x[0])

RULE = "——————————"
BAR = "══════════════════════════════════════"

def fmt(line):
    s = line.rstrip("\r\n")
    if s.strip() == "---":
        return RULE
    if s.startswith(">"):
        q = re.sub(r"^>\s?", "", s)
        return "　　" + q.replace("**", "")
    if s.startswith("#"):
        mm = re.match(r"^(#+)\s*(.*)$", s)
        level = len(mm.group(1))
        text = mm.group(2).replace("**", "")
        return text if level == 1 else "· " + text
    return s.replace("**", "")

chapters = []  # (prefix, filename, title, body_lines)
for num, f in entries:
    with open(os.path.join(src, f), encoding="utf-8-sig") as fh:
        raw = fh.read()
    lines = raw.split("\n")
    title = None
    body = []
    for ln in lines:
        if title is None and ln.lstrip().startswith("#"):
            title = fmt(ln)
            continue
        body.append(fmt(ln))
    while body and body[0] == "":
        body.pop(0)
    while body and body[-1] == "":
        body.pop()
    chapters.append((num, f, title or f, body))

out_lines = []
out_lines.append("《法则权能》正文合集")
out_lines.append("单文件 TXT 版")
out_lines.append("")
out_lines.append(f"合并自「点子库 / 02-正文」目录，共 {len(chapters)} 篇（序章、主线章节、支线 POV 集、索引卡、分支短章等）。")
out_lines.append("生成日期：2026-11-12。创作说明（README-创作说明.md，含校对批与排版稿指针）未并入正文。")
out_lines.append("")
out_lines.append("【目录】")
for num, f, title, body in chapters:
    out_lines.append(f"· {title}")
out_lines.append("")

total_chars = 0
for num, f, title, body in chapters:
    out_lines.append("")
    out_lines.append(BAR)
    out_lines.append(title)
    out_lines.append(BAR)
    out_lines.append("")
    prev_blank = False
    for ln in body:
        if ln == "":
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        out_lines.append(ln)
        total_chars += len(ln)

with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out_lines) + "\n")

print("输出文件:", out)
print("合并篇数:", len(chapters))
print("正文纯字数(估,含标点空格):", total_chars)
print("文件大小(字节):", os.path.getsize(out))
