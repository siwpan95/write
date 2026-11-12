# -*- coding: utf-8 -*-
"""第一批修订补漏 C：嵌套引号与倒置引号"""
import os, glob
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')

def find(prefix):
    g = [p for p in sorted(glob.glob(os.path.join(SRC, prefix + '-*.md'))) if '.preview' not in p]
    return g[0] if g else None

R = [
 ('94', '条文第一次被走进来““我在中间”', '条文第一次被走进来”“我在中间”'),
 ('126', '“**一个字。“人”。粉笔，楷意，笔锋有回勾——**', '“**一个字。‘人’。粉笔，楷意，笔锋有回勾——**'),
 ('126', '”右栏。自记。“', '“右栏。自记。”'),
 ('131', '“**一个词。“前纪”。印刷体，黑体。来源：词卡。时长三秒。无其他异常。**“  **”无其他异常。**“',
        '“**一个词。‘前纪’。印刷体，黑体。来源：词卡。时长三秒。无其他异常。**”  **“无其他异常。”**'),
]
for pre, old, new in R:
    p = find(pre)
    t = open(p, encoding='utf-8').read()
    c = t.count(old)
    if c == 0:
        print('MISS', pre, old[:30]); continue
    open(p, 'w', encoding='utf-8').write(t.replace(old, new))
    print('OK', pre, 'x', c)

for p in sorted(glob.glob(os.path.join(SRC, '[0-9]*.md'))):
    t = open(p, encoding='utf-8').read()
    if t.count('\u201c') != t.count('\u201d'):
        d = 0; where = None
        for i, ch in enumerate(t):
            d += (ch == '\u201c') - (ch == '\u201d')
        print('UNBAL', os.path.basename(p), t.count('\u201c'), t.count('\u201d'), 'depth', d)
