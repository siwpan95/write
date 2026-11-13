# -*- coding: utf-8 -*-
"""按三册重排总目录（册内页码自 1 起）"""
import os, re, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '05-实体书', '正文')
CPP = 547

VOLS = ['序章', '卷一', '卷二', '卷三', '卷四', '卷五', '终卷', '卷六', '卷七', '卷八', '卷九', '番外']
BOOKS = [
 ('上册', ['序章', '卷一', '卷二', '卷三']),
 ('中册', ['卷四', '卷五']),
 ('下册', ['终卷', '卷六', '卷七', '卷八', '卷九', '番外']),
]

def chapters(v):
    p = os.path.join(SRC, v + '.md')
    if not os.path.exists(p):
        return []
    t = open(p, encoding='utf-8').read()
    out = []
    for m in re.finditer(r'^## (.+)$', t, re.M):
        out.append(m.group(1).strip())
    # 每章字数：按下一个标题切分
    parts = re.split(r'^## (?=第[一二三四五六七八九十百]+章)', t, flags=re.M)[1:]
    res = []
    for part in parts:
        title, _, body = part.partition('\n')
        res.append((title.strip(), len(re.sub(r'\s', '', body))))
    return res

L = ['# 总目录（三册本）\n']
total_pages = 0
book_stat = []
for bname, vols in BOOKS:
    rows = []
    pages = 0
    for v in vols:
        chs = chapters(v)
        if not chs:
            continue
        for title, chars in chs:
            pages += max(1, round(chars / CPP))
            rows.append((v, title, pages, chars))
    book_stat.append((bname, pages, len(rows)))
    total_pages += pages

L.append(f'> 全书正文 **397,517 字 / 193 章**，大 32 开（140×203）、版心 105×152、5 号字 15.4 pt 行距，'
         f'试排样实测 **547 字/面**。三册合计约 **{total_pages} 面**（另加各册辅文 12 面、章名页留白已计入）。\n')

for bname, vols in BOOKS:
    L.append(f'\n---\n\n## {bname}\n')
    L.append(f'*收：{" · ".join(vols)}*\n')
    L.append('| 卷 | 章 | 册内页 | 字数 |')
    L.append('|---|---|---|---|')
    pages = 0
    for v in vols:
        chs = chapters(v)
        for title, chars in chs:
            pages += max(1, round(chars / CPP))
            L.append(f'| {v} | {title} | {pages} | {chars} |')

L.append('\n---\n\n## 分册规格\n')
L.append('| 册 | 正文面数 | 章数 | 印张（32 面/印张） | 收卷 |')
L.append('|---|---|---|---|---|')
for (bname, pages, n), (_, vols) in zip(book_stat, BOOKS):
    L.append(f'| {bname} | {pages} | {n} | {pages/32:.1f} | {" · ".join(vols)} |')

open(os.path.join(BASE, '05-实体书', '02-总目录.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('总面数', total_pages)
for b in book_stat:
    print(b)
