import io, re, glob, os, collections

CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')
LAT = re.compile(r'[A-Za-z]+')
REPL = '\ufffd'

vols = ['第一卷', '第二卷', '第三卷', '第四卷', '第五卷']
files = []
for v in vols:
    files += sorted(glob.glob(os.path.join(v, '第*.txt'))) + sorted(glob.glob(os.path.join(v, '楔子*.txt')))


def wc(p):
    n = 0
    for i, line in enumerate(io.open(p, encoding='utf-8')):
        if i == 0:
            continue
        t = line.strip()
        if not t or t.startswith('==='):
            continue
        n += len(CJK.findall(line))
    return n


print('=== 1. 规模 ===')
total_files = 0
total_words = 0
for v in vols:
    g = [f for f in files if f.startswith(v)]
    w = sum(wc(f) for f in g)
    total_files += len(g)
    total_words += w
    print(f'{v}: {len(g)} 篇 / {w} 字')
print(f'合计: {total_files} 篇 / {total_words} 字')

print()
print('=== 2. 字数下限（<3000）===')
low = [(os.path.basename(f), wc(f)) for f in files if wc(f) < 3000]
print(low if low else 'PASS 零章低于 3000')

print()
print('=== 3. 第五卷拉丁字母残留（第一卷历史遗留不计）===')
lat_hits = collections.defaultdict(list)
for f in files:
    if f.startswith('第一卷'):
        continue
    for i, line in enumerate(io.open(f, encoding='utf-8')):
        if i == 0:
            continue
        if LAT.search(line):
            lat_hits[os.path.basename(f)].append((i + 1, line.strip()[:70]))
if lat_hits:
    for k, v in lat_hits.items():
        for ln, txt in v:
            print(f'  {k}:{ln}  {txt}')
else:
    print('PASS 二至五卷零拉丁字母')

print()
print('=== 4. 替换字符 U+FFFD ===')
rep = []
for f in files:
    for i, line in enumerate(io.open(f, encoding='utf-8')):
        if REPL in line:
            rep.append((os.path.basename(f), i + 1))
print(rep if rep else 'PASS 全书零替换字符')

print()
print('=== 5. 章号连续性 ===')
for v in vols:
    g = glob.glob(os.path.join(v, '第*.txt'))
    # 按章号数值排序，避免 "第100章" 排在 "第91章" 之前造成假 GAP
    nums = sorted(int(re.match(r'第(\d+)', os.path.basename(f)).group(1)) for f in g)
    gaps = [(a, b) for a, b in zip(nums, nums[1:]) if b != a + 1]
    dup = [n for n, c in collections.Counter(nums).items() if c > 1]
    tag = f'GAP {gaps}' if gaps else 'PASS 连续'
    if dup:
        tag += f' DUP {sorted(dup)}'
    print(f'{v}: {len(nums)} 章 {nums[0]}-{nums[-1]} {tag}')

print()
print('=== 6. 第四/五卷标题行与文件名一致性 ===')
CN = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
      '七': 7, '八': 8, '九': 9}


def cn2int(s):
    """中文数字转阿拉伯数字（覆盖 1-999 范围，本书够用）。"""
    s = s.replace('两', '二')
    total, section, number = 0, 0, 0
    for ch in s:
        if ch in CN:
            number = CN[ch]
        elif ch == '十':
            section += (number or 1) * 10
            number = 0
        elif ch == '百':
            section += (number or 1) * 100
            number = 0
        else:
            return None
    return section + number


bad = []
for f in files:
    if not f.startswith('第四卷') and not f.startswith('第五卷'):
        continue
    with io.open(f, encoding='utf-8') as fh:
        first = fh.readline().strip()
    stem = os.path.splitext(os.path.basename(f))[0]
    parts = stem.split('-', 1)
    if len(parts) != 2:
        bad.append((stem, first, '文件名无标题段'))
        continue
    num, title = parts
    m = re.match(r'^第(\d+)章$', num)
    if not m:
        bad.append((stem, first, '文件名章号格式异常'))
        continue
    want = int(m.group(1))
    # 标题行形如「第二百三十章\u3000火种」，须与文件名章号+标题逐字对齐
    hm = re.match(r'^第([零一二三四五六七八九十百两]+)章[\u3000 ]*(.*)$', first)
    if not hm:
        bad.append((stem, first, '标题行格式异常'))
        continue
    got = cn2int(hm.group(1))
    if got != want:
        bad.append((stem, first, f'章号不符 期望{want} 实得{got}'))
    elif hm.group(2).strip() != title.strip():
        bad.append((stem, first, f'标题不符 期望「{title}」实得「{hm.group(2).strip()}」'))
print(bad if bad else 'PASS 第四/五卷 90 章标题行与文件名逐字对齐')

print()
print('=== 7. 第五卷章型分布（从台账详情块统计）===')
s = io.open('设定与参考/目录与章节台账.md', encoding='utf-8').read()
blocks = re.split(r'\n`第', s)
c = collections.Counter()
cnt = 0
for b in blocks:
    m = re.match(r'(\d+)章', b)
    if not m:
        continue
    n = int(m.group(1))
    if n < 181 or n > 230:
        continue
    mm = re.search(r'\*\*章型\*\* ([^｜\n]*)', b)
    if not mm:
        continue
    cnt += 1
    t = mm.group(1)
    if '独' in t:
        c['独'] += 1
    elif '对' in t:
        c['对'] += 1
    elif '动' in t:
        c['动'] += 1
    elif '混' in t:
        c['混'] += 1
print(f'已录章型块 {cnt} / 50  {dict(c)}')
print('第五卷红线：独 ≤10 · 对 ≥18 · 动 ≥14 · 能力冻结（不新增能力，只交出去）')
ok = (c['独'] <= 10) and (c['对'] >= 18) and (c['动'] >= 14)
print('PASS 红线满足' if ok else f'FAIL 红线未满足：独{c["独"]} 对{c["对"]} 动{c["动"]}')

print()
print('=== 8. timeline 与台账末条一致 ===')
tl = io.open('bible/timeline.md', encoding='utf-8').read()
t_ids = re.findall(r'^- T(\d+)：', tl, re.M)
print(f'timeline 事件数: {len(t_ids)}，T 编号连续: {t_ids == [str(i) for i in range(1, len(t_ids)+1)]}')
last = re.findall(r'\| (T\d+) \|\n', s)
print(f'台账速览表末行 T 编号: {last[-1] if last else "NONE"} / timeline 末条: T{t_ids[-1]}')

print()
print('=== 9. 核心红线数值 ===')
p = '第五卷/第230章-火种.txt'
txt = io.open(p, encoding='utf-8').read()
checks = {
    '灰线到九十四（不越 82 硬红线，作为能力上探留口）': '九十四' in txt,
    '灰线未被解除/归零': '空' in txt and '还没有数' in txt,
    '主角不恢复记忆（仍记不住来处）': '我记不住来处' in txt,
    'F19 门仍认不出、靠门框刻度': '第八十二格' in txt,
    '不新增能力、只交出去': '等有人替它数' in txt,
}
for k, v in checks.items():
    print(('PASS  ' if v else 'FAIL  ') + k)

print()
print('=== 10. 关键道具闭环 ===')
all5 = ''.join(io.open(f, encoding='utf-8').read() for f in files if f.startswith('第五卷'))
props = {
    '铜齿轮（已交小雨）': '铜齿轮' in all5,
    '圆物（已交小雨、不再抖）': '圆物' in all5,
    '四百一十七片薄铁（白格第九格铁架上）': '四百一十七片铁' in all5 or '四百一十七片薄铁' in all5,
    '小錾子（铁手→主角→刻"收"）': '錾子' in all5,
    '李氏账板（冷库门口横铁框上）': '账板' in all5,
    '门框八十二格（过缝锚点）': '第八十二格' in all5,
    '记事本（主角记"事"）': '记事' in all5,
}
for k, v in props.items():
    print(('PASS  ' if v else 'FAIL  ') + k)
