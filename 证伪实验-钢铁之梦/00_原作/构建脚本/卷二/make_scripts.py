# -*- coding: utf-8 -*-
"""从卷一脚本派生卷二脚本，保证两份成品同一套版式。"""
import re

src = open("/data/workspace/steel_dream/build.py", encoding="utf-8").read()

REPL = [
    ('BASE = "/data/workspace/steel_dream"',
     'BASE = "/data/workspace/steel_dream/vol2"'),
    ('OUT_DOCX = "/data/workspace/钢铁之梦·卷一_血比马粪贱.docx"',
     'OUT_DOCX = "/data/workspace/钢铁之梦·卷二_铁丝与雪.docx"'),
    ('OUT_PDF  = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'OUT_PDF  = "/data/workspace/钢铁之梦·卷二_铁丝与雪.pdf"'),
    ('produced = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'produced = "/data/workspace/钢铁之梦·卷二_铁丝与雪.pdf"'),
    ('line("多诺万家族三部曲 · 卷一", 11, SANS, "C9BDA6", after=30, sp=1.0)',
     'line("多诺万家族三部曲 · 卷二", 11, SANS, "C9BDA6", after=30, sp=1.0)'),
    ('line("血比马粪贱", 22, SANS, PAPER, True, after=18, sp=1.5)',
     'line("铁丝与雪", 22, SANS, PAPER, True, after=18, sp=1.5)'),
    ('line("法律在东部。这里只有柯尔特。", 10, SERIF, "B9AC95", after=0)',
     'line("牛会冻死，草会干，桩会烂。纸不肯挪。", 10, SERIF, "B9AC95", after=0)'),
    ('line("一八七六 — 一九〇一　｜　一部西部黑色纪事", 9, SERIF, "9C907A", before=28)',
     'line("一八七八 — 一八八七　｜　一部西部黑色纪事", 9, SERIF, "9C907A", before=28)'),
    ('line("卷　一", 12, SANS, "C9BDA6", after=18, sp=2.0)',
     'line("卷　二", 12, SANS, "C9BDA6", after=18, sp=2.0)'),
    ('dark_page(doc, \'volume\', \'\', "血比马粪贱",\n              "人命比马粪还贱，规矩全靠左轮手枪来定。", "")',
     'dark_page(doc, \'volume\', \'\', "铁丝与雪",\n              "自由放牧的时代结束了。谁圈住水，谁替整片草定规矩。", "")'),
    ('line("核心物件 · 牌", 9, SERIF, "9C907A", before=30)',
     'line("核心物件 · 铁丝", 9, SERIF, "9C907A", before=30)'),
    ('本卷为《钢铁之梦》三部曲第一部。全书以一八七六年美国西部为起点，循牛仔、牧场、矿山、铁路四段路，写一个被欠薪的人如何学会替别人记账。卷二《铁丝与雪》、卷三《钢铁之梦》待续。',
     '本卷为《钢铁之梦》三部曲第二部，接卷一《血比马粪贱》：开春带灯的人回来了，井改按股记，废沟开出矿，一场雪把整片平原抹平。写一个学会替别人记账的人，如何把会冻死的东西换成不肯挪的东西。卷三《钢铁之梦》待续。'),
    ('light_title(doc, "目　次", "钢铁之梦 · 卷一　血比马粪贱")',
     'light_title(doc, "目　次", "钢铁之梦 · 卷二　铁丝与雪")'),
    ('"卷一 · 血比马粪贱"', '"卷二 · 铁丝与雪"'),
]

for a, b in REPL:
    n = src.count(a)
    if n == 0:
        raise SystemExit("MISS in build.py: " + a[:60])
    src = src.replace(a, b)
    print(f"build.py  {n}x  {a[:44]}")

open("/data/workspace/steel_dream/vol2/build2.py", "w", encoding="utf-8").write(src)

# ---- postprocess ----
p = open("/data/workspace/steel_dream/postprocess.py", encoding="utf-8").read()
PREPL = [
    ('SRC = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'SRC = "/data/workspace/钢铁之梦·卷二_铁丝与雪.pdf"'),
    ('TMP = "/data/workspace/.steel_dream_post.pdf"',
     'TMP = "/data/workspace/.steel_dream_post2.pdf"'),
    ('VOL = "卷一 · 血比马粪贱"', 'VOL = "卷二 · 铁丝与雪"'),
    ("'/Title': '钢铁之梦·卷一 血比马粪贱'", "'/Title': '钢铁之梦·卷二 铁丝与雪'"),
    ("'/Subject': '新黑色电影 × 纯正西部 · 多诺万家族三部曲第一部'",
     "'/Subject': '新黑色电影 × 纯正西部 · 多诺万家族三部曲第二部'"),
    ('prefix = "/data/workspace/steel_dream/thx"',
     'prefix = "/data/workspace/steel_dream/thx2"'),
]
for a, b in PREPL:
    n = p.count(a)
    if n == 0:
        raise SystemExit("MISS in postprocess.py: " + a[:60])
    p = p.replace(a, b)
    print(f"post.py   {n}x  {a[:44]}")

open("/data/workspace/steel_dream/vol2/post2.py", "w", encoding="utf-8").write(p)
print("OK")
