# -*- coding: utf-8 -*-
"""第一批修订补漏"""
import os, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')

def find(prefix):
    g = [p for p in sorted(glob.glob(os.path.join(SRC, prefix + '-*.md'))) if '.preview' not in p]
    return g[0] if g else None

R = [
 ('170', '雾里，第 43 根桩立在河滩的原位', '雾里，第 42 根桩立在河滩的原位'),
 ('170', '7:00。第 43 桩。余 0。', '7:00。第 42 桩。余 0。'),
 ('06', '**0.683**', '**0.677**'),
 ('37', '），慈揣着借手函', '），慈笙揣着借手函'),
 ('88', '（庭外宣判过"程序僭越"的人', '（当庭宣判过"程序僭越"的人'),
 ('173', '五十年前有一个人，照着一张旧纸', '六十七年前有一个人，照着一张旧纸'),
 ('193', '——"旧件是别人的伞的命，我留着给下一把续。**——', '——"旧件是别人的伞的命，我留着给下一把续。"**——'),
]
for pre, old, new in R:
    p = find(pre)
    t = open(p, encoding='utf-8').read()
    c = t.count(old)
    if c == 0:
        print('MISS', pre, old[:26])
        continue
    open(p, 'w', encoding='utf-8').write(t.replace(old, new))
    print('OK', pre, f'x{c}')

# 复核引号奇偶
for p in sorted(glob.glob(os.path.join(SRC, '[0-9]*.md'))):
    t = open(p, encoding='utf-8').read()
    if t.count('"') % 2:
        print('ODD', os.path.basename(p), t.count('"'))
