# -*- coding: utf-8 -*-
"""从卷一脚本派生卷三脚本，保证三卷同一套版式。"""
src = open("/data/workspace/steel_dream/build.py", encoding="utf-8").read()

REPL = [
    ('BASE = "/data/workspace/steel_dream"', 'BASE = "/data/workspace/steel_dream/vol3"'),
    ('OUT_DOCX = "/data/workspace/钢铁之梦·卷一_血比马粪贱.docx"',
     'OUT_DOCX = "/data/workspace/钢铁之梦·卷三_钢铁之梦.docx"'),
    ('OUT_PDF  = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'OUT_PDF  = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"'),
    ('produced = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'produced = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"'),
    ('line("多诺万家族三部曲 · 卷一", 11, SANS, "C9BDA6", after=30, sp=1.0)',
     'line("多诺万家族三部曲 · 第三部　终卷", 11, SANS, "C9BDA6", after=30, sp=1.0)'),
    ('line("血比马粪贱", 22, SANS, PAPER, True, after=18, sp=1.5)',
     'line("终卷 · 钢铁之梦", 22, SANS, PAPER, True, after=18, sp=1.5)'),
    ('line("法律在东部。这里只有柯尔特。", 10, SERIF, "B9AC95", after=0)',
     'line("风把红得像锈的土卷起来，打在玻璃上，沙沙地响。", 10, SERIF, "B9AC95", after=0)'),
    ('line("一八七六 — 一九〇一　｜　一部西部黑色纪事", 9, SERIF, "9C907A", before=28)',
     'line("一八八八 — 一九〇一　｜　一部西部黑色纪事（全帙完结）", 9, SERIF, "9C907A", before=28)'),
    ('line("卷　一", 12, SANS, "C9BDA6", after=18, sp=2.0)',
     'line("卷　三", 12, SANS, "C9BDA6", after=18, sp=2.0)'),
    ('dark_page(doc, \'volume\', \'\', "血比马粪贱",\n              "人命比马粪还贱，规矩全靠左轮手枪来定。", "")',
     'dark_page(doc, \'volume\', \'\', "钢铁之梦",\n              "产权怎么变成国家。反派不签字，流程签字。", "")'),
    ('line("核心物件 · 牌", 9, SERIF, "9C907A", before=30)',
     'line("核心物件 · 发票", 9, SERIF, "9C907A", before=30)'),
    ('本卷为《钢铁之梦》三部曲第一部。全书以一八七六年美国西部为起点，循牛仔、牧场、矿山、铁路四段路，写一个被欠薪的人如何学会替别人记账。卷二《铁丝与雪》、卷三《钢铁之梦》待续。',
     '本卷为《钢铁之梦》三部曲终卷，接卷一《血比马粪贱》、卷二《铁丝与雪》：路权与拨地、费率表上的对手、自己的公司给自己开发票，终至列车包厢里那句「没有人比我更懂西部淘金梦」。全帙完结。'),
    ('light_title(doc, "目　次", "钢铁之梦 · 卷一　血比马粪贱")',
     'light_title(doc, "目　次", "钢铁之梦 · 卷三　钢铁之梦（终卷）")'),
    ('"卷一 · 血比马粪贱"', '"卷三 · 钢铁之梦"'),
]
for a, b in REPL:
    n = src.count(a)
    if n == 0:
        raise SystemExit("MISS build.py: " + a[:70])
    src = src.replace(a, b)
    print(f"build  {n}x  {a[:46]}")
open("/data/workspace/steel_dream/vol3/build3.py", "w", encoding="utf-8").write(src)

p = open("/data/workspace/steel_dream/postprocess.py", encoding="utf-8").read()
PREPL = [
    ('SRC = "/data/workspace/钢铁之梦·卷一_血比马粪贱.pdf"',
     'SRC = "/data/workspace/钢铁之梦·卷三_钢铁之梦.pdf"'),
    ('TMP = "/data/workspace/.steel_dream_post.pdf"',
     'TMP = "/data/workspace/.steel_dream_post3.pdf"'),
    ('VOL = "卷一 · 血比马粪贱"', 'VOL = "卷三 · 钢铁之梦"'),
    ("'/Title': '钢铁之梦·卷一 血比马粪贱'", "'/Title': '钢铁之梦·卷三 钢铁之梦（终卷）'"),
    ("'/Subject': '新黑色电影 × 纯正西部 · 多诺万家族三部曲第一部'",
     "'/Subject': '新黑色电影 × 纯正西部 · 多诺万家族三部曲第三部 终卷'"),
    ('prefix = "/data/workspace/steel_dream/thx"',
     'prefix = "/data/workspace/steel_dream/thx3"'),
]
for a, b in PREPL:
    n = p.count(a)
    if n == 0:
        raise SystemExit("MISS post.py: " + a[:70])
    p = p.replace(a, b)
    print(f"post   {n}x  {a[:46]}")
open("/data/workspace/steel_dream/vol3/post3.py", "w", encoding="utf-8").write(p)
print("OK")
