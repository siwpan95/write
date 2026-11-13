# -*- coding: utf-8 -*-
"""全稿一致性扫描（可重跑）
用法: python3 04-工具/audit_consistency.py
输出: 04-工具/报告/一致性扫描报告.md + audit.json
"""
import os, re, glob, json, collections, difflib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, '02-正文')
OUT = os.path.join(BASE, '04-工具', '报告')
os.makedirs(OUT, exist_ok=True)

CN = '零一二三四五六七八九'
UNITS = {'十': 10, '百': 100, '千': 1000}

def cn2int(s):
    if not s:
        return None
    if re.fullmatch(r'\d+', s):
        return int(s)
    total, num = 0, 0
    for ch in s:
        if ch in CN:
            num = CN.index(ch)
        elif ch in UNITS:
            u = UNITS[ch]
            if num == 0:
                num = 1
            total += num * u
            num = 0
        else:
            return None
    return total + num

files = sorted(glob.glob(os.path.join(SRC, '[0-9]*.md')))
rows = []
for p in files:
    fn = os.path.basename(p)[:-3]
    m = re.match(r'^(\d+)-(.+)$', fn)
    fidx, rest = int(m.group(1)), m.group(2)
    text = open(p, encoding='utf-8-sig').read()
    nchar = len(re.sub(r'\s', '', text))
    lines = [l for l in text.split('\n')]
    first = next((l.strip() for l in lines if l.strip()), '')
    # 文件名中的章号/章名
    fm = re.match(r'^第(.+?)章-(.+)$', rest)
    f_ch, f_title = (cn2int(fm.group(1)), fm.group(2)) if fm else (None, None)
    # 首行标题
    hm = re.match(r'^#\s*第(.+?)章\s*[·・\-—]\s*(.+)$', first)
    h_ch, h_title = (cn2int(hm.group(1)), hm.group(2).strip()) if hm else (None, None)
    tail = [l.strip() for l in lines if l.strip()][-1] if text.strip() else ''
    # 章末创作注：本书约定为「**（第X章完 · 索引卡：… · 下接…）**」（见 05-实体书/03-勘误表.md）。
    # 尾行可能只截到「（第X章 · 索引卡：…）」而没有「完」字，故两种写法都要认。
    tm = re.search(r'（第(.+?)章(?:\s*完)?(?:\s*·|\s*索引卡|\s*$)', tail)
    t_ch = cn2int(tm.group(1)) if tm else None
    # 格式统计
    st = {
        'quote_cn': text.count('\u201c'),
        'quote_jp': text.count('\u300c'),
        'quote_ascii': text.count('"'),
        'ellipsis_6': text.count('……'),
        'ellipsis_3': len(re.findall(r'(?<!…)…(?!…)', text)),
        'ellipsis_dot': len(re.findall(r'\.\.\.', text)),
        'dash_double': text.count('——'),
        'dash_single': len(re.findall(r'(?<!—)—(?!—)', text)),
        'excl': text.count('！'),
        'paren_ascii': len(re.findall(r'[\(\)]', text)),
        'time_colon': re.findall(r'\d{1,2}[:：]\d{2}', text),
        'trailing_ws': sum(1 for l in lines if l != l.rstrip()),
        'blank3': len(re.findall(r'\n{3,}', text)),
    }
    rows.append(dict(file=fn, idx=fidx, kind=('chapter' if f_ch else 'special'),
                     f_ch=f_ch, f_title=f_title, h_ch=h_ch, h_title=h_title,
                     t_ch=t_ch, nchar=nchar, first=first, tail=tail[:80], st=st, path=p))

# ---------- 1 结构异常 ----------
anom = []
for r in rows:
    if r['kind'] == 'chapter':
        if r['f_ch'] is None:
            anom.append((r['file'], '文件名章号无法解析'))
        if r['h_ch'] is None:
            anom.append((r['file'], '首行非「# 第X章 · 名」体例: ' + r['first'][:40]))
        else:
            if r['h_ch'] != r['f_ch']:
                anom.append((r['file'], f'章号不一致 文件{r["f_ch"]} vs 标题{r["h_ch"]}'))
            if r['f_title'].replace(':', '').replace('：', '') != r['h_title'].replace(':', '').replace('：', ''):
                anom.append((r['file'], f'章名不一致 文件「{r["f_title"]}」 vs 标题「{r["h_title"]}」'))
        if r['t_ch'] is None:
            anom.append((r['file'], '缺章末标记: ' + r['tail'][:50]))
        elif r['t_ch'] != r['f_ch']:
            anom.append((r['file'], f'章末章号不一致 {r["t_ch"]} vs {r["f_ch"]}'))

# 章号连续性
nums = sorted([r['f_ch'] for r in rows if r['kind'] == 'chapter' and r['f_ch']])
missing = [n for n in range(1, max(nums) + 1) if n not in nums] if nums else []
dup = [n for n, c in collections.Counter(nums).items() if c > 1]

# ---------- 2 字数异常 ----------
short = [r for r in rows if r['kind'] == 'chapter' and r['nchar'] < 1300]
longx = [r for r in rows if r['kind'] == 'chapter' and r['nchar'] > 4000]

# ---------- 3 标点/体例分布 ----------
agg = collections.Counter()
for r in rows:
    for k, v in r['st'].items():
        if isinstance(v, int):
            agg[k] += v
jp_files = [r['file'] for r in rows if r['st']['quote_jp']]
ascii_files = [r['file'] for r in rows if r['st']['quote_ascii']]
dot_files = [r['file'] for r in rows if r['st']['ellipsis_dot']]
paren_files = [r['file'] for r in rows if r['st']['paren_ascii']]
halfcolon = [(r['file'], r['st']['time_colon']) for r in rows
             if any('：' in t for t in r['st']['time_colon'])]
trail_files = [(r['file'], r['st']['trailing_ws']) for r in rows if r['st']['trailing_ws']]
blank_files = [(r['file'], r['st']['blank3']) for r in rows if r['st']['blank3']]

# ---------- 4 跨文件长重复（>=36 字连续） ----------
def shingles(t, n=36):
    """返回 {36 字片段: 首次出现位置}。

    2026-11-13 修正：原实现返回**集合**，配合 `sorted(inter, key=len)`
    在「所有片段等长」时退化为**集合迭代序** ⇒ 每次跑出的示例片段不同
    （受 PYTHONHASHSEED 影响），受控产物 `一致性扫描报告.md` 每次运行都漂移。
    改存首次出现位置后，示例取「最靠前的那一段」，顺序可复现。
    """
    t = re.sub(r'\s', '', t)
    out = {}
    for i in range(0, max(0, len(t) - n)):
        s = t[i:i + n]
        if s not in out:
            out[s] = i
    return out
sh = {}
for r in rows:
    sh[r['file']] = shingles(open(r['path'], encoding='utf-8-sig').read())
pairs = collections.Counter()
sample = {}
fl = [r['file'] for r in rows]
for i in range(len(fl)):
    for j in range(i + 1, len(fl)):
        inter = sh[fl[i]].keys() & sh[fl[j]].keys()
        if inter:
            pairs[(fl[i], fl[j])] = len(inter)
            # 片段等长 ⇒ 按「首次出现位置」定序（位置相同再按字面），保证可复现
            sample[(fl[i], fl[j])] = sorted(
                inter, key=lambda s: (sh[fl[i]][s], s))[0][:60]
top_dup = pairs.most_common(15)

# 单文件内重复段（>=44 字完全重复）
intra = []
for r in rows:
    t = re.sub(r'\s', '', open(r['path'], encoding='utf-8-sig').read())
    seg = collections.Counter(t[i:i + 44] for i in range(0, max(0, len(t) - 44)))
    d = [(s, c) for s, c in seg.items() if c > 1]
    if d:
        intra.append((r['file'], len(d), d[0][0][:40]))

# ---------- 5 章名里的数字/时间写法 ----------
numtitle = [(r['file'], r['h_title']) for r in rows if r['kind'] == 'chapter' and r['h_title'] and re.search(r'\d', r['h_title'])]

# ---------- 输出 ----------
L = []
L.append('# 全稿一致性扫描报告（机器）\n')
L.append(f'- 正文文件 {len(rows)} 个；章文件 {sum(1 for r in rows if r["kind"]=="chapter")}；特殊文件 {sum(1 for r in rows if r["kind"]=="special")}')
L.append(f'- 章号范围 {min(nums)}–{max(nums)}；缺号 {missing}；重号 {dup}')
L.append(f'- 全稿净字数 {sum(r["nchar"] for r in rows)}')
L.append(f'- 章长：最短 {min([r["nchar"] for r in rows if r["kind"]=="chapter"])}，最长 {max([r["nchar"] for r in rows if r["kind"]=="chapter"])}，均值 {sum(r["nchar"] for r in rows if r["kind"]=="chapter")//max(1,sum(1 for r in rows if r["kind"]=="chapter"))}')
L.append('\n## 一 结构与体例异常\n')
L.append(f'共 {len(anom)} 条：')
for f, m in anom:
    L.append(f'- `{f}` — {m}')
if not anom:
    L.append('（无）')
L.append('\n## 二 标点与字符体例\n')
L.append(f'- 弯引号“ 计 {agg["quote_cn"]}；直角引号「 出现在 {len(jp_files)} 个文件: {jp_files[:10]}')
L.append(f'- 直引号 " 出现在 {len(ascii_files)} 个文件: {ascii_files[:10]}')
L.append(f'- 省略号：六点 {agg["ellipsis_6"]}；单点… {agg["ellipsis_3"]}；三点... 出现于 {len(dot_files)} 文件 {dot_files[:10]}')
L.append(f'- 破折号：—— {agg["dash_double"]}；单— {agg["dash_single"]}')
L.append(f'- 半角括号出现于 {len(paren_files)} 文件: {paren_files[:10]}')
L.append(f'- 时间写法含全角冒号: {halfcolon[:15]}')
L.append(f'- 行尾空白: {trail_files[:15]}')
L.append(f'- 连续 3+ 空行: {blank_files[:15]}')
L.append(f'- 感叹号总数 {agg["excl"]}')
L.append('\n## 三 跨文件 36 字重复片段 Top\n')
for (a, b), c in top_dup:
    L.append(f'- `{a}` × `{b}`：{c} 片 · 例「{sample[(a,b)]}」')
L.append('\n## 四 单文件内 44 字重复段\n')
for f, n, s in intra[:20]:
    L.append(f'- `{f}`：{n} 处 · 例「{s}」')
L.append('\n## 五 章名含阿拉伯数字\n')
for f, t in numtitle:
    L.append(f'- `{f}` → 「{t}」')
L.append('\n## 六 字数异常\n')
L.append('偏短(<1300)：' + ', '.join(f'{r["file"]}({r["nchar"]})' for r in short))
L.append('偏长(>4000)：' + ', '.join(f'{r["file"]}({r["nchar"]})' for r in longx))
L.append('\n## 七 章目录（文件→章号→章名→字数）\n')
for r in rows:
    L.append(f'| {r["file"]} | {r["f_ch"] if r["f_ch"] else "—"} | {r["h_title"] or r["f_title"] or "—"} | {r["nchar"]} |')

# 产物用 UTF-8-SIG（本仓《工作区规范》§六：文本文件统一 UTF-8-SIG 带 BOM）。
# 此前写的是 'utf-8'（无 BOM），重跑会剥掉已有产物的 BOM，与入库形态不一致。
open(os.path.join(OUT, '一致性扫描报告.md'), 'w', encoding='utf-8-sig').write('\n'.join(L))
json.dump([{k: v for k, v in r.items() if k != 'path'} for r in rows],
          open(os.path.join(OUT, 'audit.json'), 'w', encoding='utf-8-sig'), ensure_ascii=False, indent=1)

print('结构异常', len(anom), '| 缺号', missing, '| 重号', dup)
print('净字数', sum(r['nchar'] for r in rows))
for f, m in anom[:40]:
    print(' !', f, m)
print('标点 agg', dict(agg))
print('直角引号文件', jp_files)
print('直引号文件', ascii_files)
print('三点省略文件', dot_files)
print('半角括号文件数', len(paren_files))
print('全角冒号时间', halfcolon[:10])
print('报告已写入', OUT)
