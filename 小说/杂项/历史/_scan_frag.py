# -*- coding: utf-8 -*-
"""写前查重：扫描全书高频 8-12 字片段，供 115-117 章避雷。
用法: python _scan_frag.py [最低长度]
"""
import glob, os, re, collections, sys

MINLEN = int(sys.argv[1]) if len(sys.argv) > 1 else 9
ROOT = r"C:\Users\Administrator\Desktop\小说"

# 本批三章：候选高频片段
FILES = [
    os.path.join(ROOT, "第三卷", "第115章-名字的重量.txt"),
    os.path.join(ROOT, "第三卷", "第116章-顶开.txt"),
    os.path.join(ROOT, "第三卷", "第117章-王.txt"),
]

def han(t):
    return "".join(re.findall(r"[\u4e00-\u9fff]", t))

# 1) 全书高频片段库（排除本批与标题行）
lib = collections.Counter()
detail = {}
for f in glob.glob(os.path.join(ROOT, "**", "*.txt"), recursive=True):
    if os.path.basename(f) in ("小说前九章.txt",):
        continue
    base = os.path.basename(f)
    if any("第11%d章" % n in base for n in (5, 6, 7)):
        continue
    try:
        t = open(f, encoding="utf-8").read()
    except Exception:
        continue
    h = han(t)
    for n in (12, 10, 9, 8):
        for i in range(len(h) - n + 1):
            g = h[i:i + n]
            lib[g] += 1
            if n == MINLEN:
                detail.setdefault(g, set()).add(base)

print("=== 全书片段库 ===")
print("片长:", MINLEN, "唯一片段:", len(lib))
hot = [(g, c) for g, c in lib.items() if c >= 2]
hot.sort(key=lambda x: -x[1])
print("出现>=2次的片段:", len(hot))
for g, c in hot[:200]:
    srcs = sorted(detail.get(g, []))
    srcs = [s.replace(".txt", "").replace("第", "").replace("章-", ":") for s in srcs]
    print("%3d %s   <- %s" % (c, g, ",".join(srcs[:6])))

# 2) 本批候选片段查命中
print("\n=== 本批候选查重 ===")
if not os.path.exists(FILES[0]):
    print("(本批尚未落盘，先看上面的库)")
else:
    for path in FILES:
        if not os.path.exists(path):
            continue
        h = han(open(path, encoding="utf-8").read())
        print("--", os.path.basename(path))
        for i in range(len(h) - MINLEN + 1):
            g = h[i:i + MINLEN]
            if lib[g] >= 2:
                print("   命中[%d] %s" % (lib[g], g))