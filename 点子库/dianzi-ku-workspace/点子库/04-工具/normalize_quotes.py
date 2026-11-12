# -*- coding: utf-8 -*-
"""引号规范化：直引号 " 与直角引号「」→ 中文弯引号 “”
用法: python3 04-工具/normalize_quotes.py [--apply] [文件名...]
默认 dry-run，只打印样本。
"""
import os, sys, glob, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')
APPLY = '--apply' in sys.argv
targets = [a for a in sys.argv[1:] if not a.startswith('--')]

def convert(text):
    """状态机：按出现顺序交替开/闭；已闭合则下次为开。"""
    out = []
    open_ = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            out.append('\u201d' if open_ else '\u201c')
            open_ = not open_
        elif ch == '\u300c':  # 「
            out.append('\u201c')
            open_ = True
        elif ch == '\u300d':  # 」
            out.append('\u201d')
            open_ = False
        else:
            out.append(ch)
        i += 1
    return ''.join(out), open_

files = sorted(glob.glob(os.path.join(SRC, '[0-9]*.md')))
if targets:
    files = [f for f in files if any(t in os.path.basename(f) for t in targets)]

stat = []
for p in files:
    t = open(p, encoding='utf-8').read()
    new, left_open = convert(t)
    stat.append((os.path.basename(p), t.count('"'), t.count('\u300c'), left_open))
    if not APPLY:
        if targets:
            for m in re.finditer(r'.{0,18}[\u201c\u201d].{0,26}', new):
                print('  ', m.group(0).replace('\n', ' '))
        open(p[:-3] + '.preview.md', 'w', encoding='utf-8').write(new)
    else:
        open(p, 'w', encoding='utf-8').write(new)

bad = [s for s in stat if s[3]]
print('文件', len(stat), '| 转换后仍处于开引号状态的文件', len(bad), bad[:10])
print('直引号合计', sum(s[1] for s in stat), '| 直角引号合计', sum(s[2] for s in stat))
if not APPLY and not targets:
    print('（dry-run：已写 .preview.md 供比对）')
