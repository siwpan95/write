# -*- coding: utf-8 -*-
"""生成实体书排版稿：净化正文（剥离索引卡/章末注/台账）+ 按卷合并 + 总目录
输出 /sandbox/workspace/点子库/05-实体书/
"""
import os, re, glob, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')
OUT = os.path.join(BASE, '05-实体书')
os.makedirs(os.path.join(OUT, '正文'), exist_ok=True)

def path(prefix):
    g = [p for p in sorted(glob.glob(os.path.join(SRC, prefix + '-*.md'))) if '.preview' not in p]
    return g[0] if g else None

def fix_title(t):
    for a, b in [('1539', '15:39'), ('1540', '15:40')]:
        t = t.replace(a, b)
    if t == '830':
        t = '8:30'
    if t == '十点零七':
        t = '10:07'
    return t

CUT = ('**检索沉淀', '**修订记录', '**下批预标', '## 台账')

def clean(text):
    lines = text.split('\n')
    out = []
    i = 0
    n = len(lines)
    while i < n:
        l = lines[i]
        s = l.strip()
        # 章首索引卡段
        if s.startswith('## 本章索引卡'):
            i += 1
            while i < n:
                s2 = lines[i].strip()
                if s2 == '' or s2.startswith('- [') or s2.startswith('* [') or s2.startswith('## ') or s2 == '---':
                    i += 1
                    continue
                break
            continue
        # 创作元信息段（仅当出现在文件末段时截断）
        if any(s.startswith(c) for c in CUT):
            if i > n - 45:
                break
            i += 1
            continue
        # 章末注
        if re.match(r'^\*\*（第[^）]{0,30}章?[^）]{0,80}）\*\*$', s) or s.startswith('**（第') and '索引卡' in s:
            i += 1
            continue
        out.append(l)
        i += 1
    # 去尾部空行与分隔线
    while out and out[-1].strip() in ('', '---', '***', '___'):
        out.pop()
    # 去头部空行
    while out and out[0].strip() == '':
        out.pop(0)
    text = '\n'.join(out)
    text = re.sub(r'^#\s.*$', '', text, flags=re.M)          # 去重复章标题
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def num_of(p):
    m = re.match(r'^(\d+)-', os.path.basename(p))
    return m.group(1) if m else ''

VOLS = [
 ('序章', '序章 · 膜', ['00']),
 ('卷一', '卷一 · 标尺失准之年', ['01','02','03','04','05','06','09','11','13','15','17','20','10']),
 ('卷二', '卷二 · 河中', [f'{i:02d}' for i in range(21, 37)] + ['12']),
 ('卷三', '卷三 · 彼岸', [f'{i:02d}' for i in range(37, 74)] + ['14']),
 ('卷四', '卷四 · 回望', [f'{i:02d}' for i in range(74, 112)] + ['16']),
 ('卷五', '卷五 · 第七种真', [f'{i:02d}' for i in range(112, 146)] + ['18']),
 ('终卷', '终卷 · 结局期', [f'{i:02d}' for i in range(146, 171)]),
 ('卷六', '卷六 · 窗内（POV）', [f'{i:02d}' for i in range(171, 175)]),
 ('卷七', '卷七 · 对岸（POV）', [f'{i:02d}' for i in range(175, 179)]),
 ('卷八', '卷八 · 册外（POV）', [f'{i:02d}' for i in range(179, 183)]),
 ('卷九', '卷九 · 第 1 日（POV）', [f'{i:02d}' for i in range(183, 187)]),
 ('番外', '番外 · 分支短章集', [f'{i:02d}' for i in range(187, 202)]),
]

CPP = 547          # 每面有效字数（试排样实测：28 行 × 28 字几何上限 784，短句体例实收 547）
toc = []
total = 0
volstat = []

for vkey, vname, prefixes in VOLS:
    buf = []
    vchars = 0
    vchapters = 0
    buf.append(f'# {vname}\n')
    for pre in prefixes:
        p = path(pre)
        if not p:
            print('MISS FILE', pre); continue
        raw = open(p, encoding='utf-8').read()
        h = next((l for l in raw.split('\n') if l.startswith('# ')), '')
        body = clean(raw)
        title = h[2:].strip() if h else ''
        # 统一章标题格式「第X章 · 名」
        m = re.match(r'^第(.+?)章\s*[·・\-—]\s*(.+)$', title)
        if m:
            title = f'第{m.group(1)}章 · {fix_title(m.group(2).strip())}'
        else:
            title = fix_title(title)
        body = re.sub(r'^#\s.*$', '', body, count=1).strip()
        chars = len(re.sub(r'\s', '', body))
        vchars += chars
        vchapters += 1
        total += chars
        page = int(total / CPP) + 1
        toc.append((vname, title, page, chars))
        buf.append(f'\n## {title}\n')
        buf.append(body)
    open(os.path.join(OUT, '正文', f'{vkey}.md'), 'w', encoding='utf-8').write('\n\n'.join(buf).strip() + '\n')
    volstat.append((vname, vchapters, vchars, int(vchars / CPP)))
    print(f'{vname}: {vchapters} 章 · {vchars} 字 · 约 {int(vchars/CPP)} 面')

# 总目录
L = ['# 总目录\n', f'> 全书 {total} 字（正文净字）。大 32 开、5 号字、版心 105×152，每面 28 行 × 28 字（几何上限 784 字；本书短句成段多，**试排样实测有效密度 547 字/面**）——正文约 {int(total/CPP)} 面，含章节另面起与卷扉页约 {int(total/CPP*1.12)} 面，**分上中下三册**。\n']
L.append('| 卷 | 章 | 起始页（估） | 字数 |')
L.append('|---|---|---|---|')
for v, t, p, c in toc:
    L.append(f'| {v} | {t} | {p} | {c} |')
open(os.path.join(OUT, '02-总目录.md'), 'w', encoding='utf-8').write('\n'.join(L))

json.dump(volstat, open(os.path.join(OUT, '_volstat.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('总字数', total, '章数', len(toc), '估面', int(total / CPP))
