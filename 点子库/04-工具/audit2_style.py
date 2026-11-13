# -*- coding: utf-8 -*-
"""体例与专名一致性扫描（可重跑）
python3 04-工具/audit2_style.py
"""
import os, re, glob, json, collections

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')
OUT = os.path.join(BASE, '04-工具', '报告')
os.makedirs(OUT, exist_ok=True)

files = sorted(glob.glob(os.path.join(SRC, '[0-9]*.md')))
texts = {os.path.basename(p)[:-3]: open(p, encoding='utf-8').read() for p in files}

# ---------- 1 引号画像 ----------
prof = []
odd = []
for k, t in texts.items():
    a = t.count('"')
    jp = t.count('「')
    cn = t.count('\u201c')
    dbl = t.count('""')
    if a % 2:
        odd.append((k, a))
    prof.append((k, a, jp, cn, dbl))
jp_files = [(k, jp) for k, a, jp, cn, dbl in prof if jp]
cn_files = [(k, cn) for k, a, jp, cn, dbl in prof if cn]
dbl_files = [(k, dbl) for k, a, jp, cn, dbl in prof if dbl]

# 直角引号上下文
jp_ctx = []
for k, t in texts.items():
    for m in re.finditer(r'.{0,14}「.{0,24}', t):
        jp_ctx.append((k, m.group(0).replace('\n', ' ')))
# 弯引号上下文
cn_ctx = []
for k, t in texts.items():
    for m in re.finditer(r'.{0,14}\u201c.{0,24}', t):
        cn_ctx.append((k, m.group(0).replace('\n', ' ')))

# ---------- 2 章末形态 ----------
tail_kind = collections.Counter()
tail_list = collections.defaultdict(list)
for k, t in texts.items():
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    tail = lines[-1] if lines else ''
    if re.search(r'（第[^）]{1,12}章\s*[·完]', tail):
        kind = 'A_章末注(索引卡体)'
    elif '下接' in tail:
        kind = 'B_下接式'
    elif tail in ('---', '***', '___'):
        kind = 'C_分隔线'
    elif re.search(r'（全[书文]终', tail):
        kind = 'D_全书终'
    else:
        kind = 'E_无标记(以正文句收尾)'
    tail_kind[kind] += 1
    tail_list[kind].append(k)

# ---------- 3 专名 ----------
names = ['柯无衍', '柯无言', '算守', '老箴', '卫蒹', '慈笙', '简伯', '文敛', '阿钉', '陈永年',
         '周婶', '净衡', '了尘', '阿钉妈', '柯守诲', '老柯', '小吴', '审判长', '书记员']
cnt = {n: 0 for n in names}
per_file_absent = {}
for k, t in texts.items():
    for n in names:
        c = t.count(n)
        cnt[n] += c
# 近似串（编辑距离 1 的 3 字窗口）
def edit1(a, b):
    if len(a) != len(b):
        return False
    d = sum(1 for x, y in zip(a, b) if x != y)
    return d == 1
win = collections.Counter()
for t in texts.values():
    for run in re.findall(r'[\u4e00-\u9fa5]{2,}', t):
        for i in range(len(run) - 2):
            win[run[i:i + 3]] += 1
names3 = [n for n in names if len(n) == 3]
approx = []
for n in names3:
    for w, c in win.items():
        if w != n and edit1(w, n) and c >= 3:
            approx.append((n, w, c))
approx.sort(key=lambda x: -x[2])

# 4 字专名
names4 = [n for n in names if len(n) == 4]
win4 = collections.Counter()
for t in texts.values():
    for run in re.findall(r'[\u4e00-\u9fa5]{4,}', t):
        for i in range(len(run) - 3):
            win4[run[i:i + 4]] += 1
approx4 = []
for n in names4:
    for w, c in win4.items():
        if w != n and edit1(w, n) and c >= 2:
            approx4.append((n, w, c))

# ---------- 4 时间/数字表达 ----------
tm = collections.Counter()
for k, t in texts.items():
    for m in re.findall(r'\d{1,2}[:：]\d{2}', t):
        tm[m] += 1
tm2 = collections.Counter()
for k, t in texts.items():
    for m in re.findall(r'[零一二三四五六七八九十两]{1,3}点[零一二三四五六七八九十]{0,3}分?', t):
        tm2[m] += 1
arab = collections.Counter()
for k, t in texts.items():
    for m in re.findall(r'第\d+[次章节度天日年月分秒格条页个人]', t):
        arab[m] += 1

# ---------- 5 常见标点误用 ----------
mis = collections.Counter()
for k, t in texts.items():
    mis['逗号句号连用 ，。'] += len(re.findall(r'，。', t))
    mis['重复句号 。。'] += len(re.findall(r'。。', t))
    mis['空格夹中文'] += len(re.findall(r'[\u4e00-\u9fa5] +[\u4e00-\u9fa5]', t))
    mis['半角逗号'] += t.count(',')
    mis['半角句点(非省略/数字)'] += len(re.findall(r'(?<![\d.])\.(?![\d.])', t))
    mis['半角问号'] += t.count('?')
    mis['半角叹号'] += t.count('!')
    mis['全角空格'] += t.count('\u3000')

L = ['# 体例与专名一致性报告\n']
L.append('## 一 引号画像')
L.append(f'- 全书直引号 `"` 总数 {sum(p[1] for p in prof)}；奇数（未配对）文件 {len(odd)} 个：{odd[:20]}')
L.append(f'- 直角引号「出现在 {len(jp_files)} 文件：{jp_files}')
L.append(f'- 中文弯引号“出现 {len(cn_files)} 文件：{cn_files}')
L.append(f'- 相邻双直引号 `""` 出现 {sum(p[4] for p in prof)} 次，涉及 {len(dbl_files)} 文件：{dbl_files[:12]}')
L.append('\n### 直角引号样本（前 12）')
for k, s in jp_ctx[:12]:
    L.append(f'- `{k}`：{s}')
L.append('\n### 弯引号样本（前 12）')
for k, s in cn_ctx[:12]:
    L.append(f'- `{k}`：{s}')
L.append('\n## 二 章末形态分类')
for kind, c in tail_kind.most_common():
    L.append(f'- {kind}：{c} 个 → {tail_list[kind][:12]}{" …" if c>12 else ""}')
L.append('\n## 三 专名频次')
L.append('；'.join(f'{n} {c}' for n, c in cnt.items()))
L.append('\n### 近似串（编辑距离 1，窗口≥3）')
for n, w, c in approx[:40]:
    L.append(f'- 「{n}」~「{w}」×{c}')
L.append('\n### 四字专名近似串')
for n, w, c in approx4[:20]:
    L.append(f'- 「{n}」~「{w}」×{c}')
L.append('\n## 四 时间与数字表达')
L.append('冒号时间 Top：' + '；'.join(f'{k}×{v}' for k, v in tm.most_common(20)))
L.append('汉字钟点 Top：' + '；'.join(f'{k}×{v}' for k, v in tm2.most_common(20)))
L.append('阿拉伯序数（可疑混用）：' + '；'.join(f'{k}×{v}' for k, v in arab.most_common(25)))
L.append('\n## 五 标点误用')
for k, v in mis.most_common():
    L.append(f'- {k}：{v}')

open(os.path.join(OUT, '体例与专名报告.md'), 'w', encoding='utf-8').write('\n'.join(L))
print('直引号总数', sum(p[1] for p in prof), '| 奇数文件', odd)
print('直角引号文件', len(jp_files), jp_files[:20])
print('弯引号文件', cn_files)
print('相邻双引号', sum(p[4] for p in prof), dbl_files[:10])
print('章末形态', dict(tail_kind))
print('专名', cnt)
print('近似', approx[:15])
print('近似4', approx4[:10])
print('汉字钟点', tm2.most_common(12))
print('阿拉伯序数', arab.most_common(12))
print('标点', dict(mis))
