# 拆长段工具：仅对叙述段（非对话段）按句子边界拆分；避开引号内的句号；保留对话与比喻。
import re, os, glob

VOL = '第四卷'
TARGET_MAX = 115   # 叙述段上限（目标 40-120）
TARGET_MIN = 40

def split_sentences(para):
    """按句子边界切分，引号内的句号不切。"""
    out = []; cur = ''; q = 0
    for ch in para:
        cur += ch
        if ch in '“”"':
            q = 1 - q
        if ch in '。！？…' and q == 0:
            out.append(cur); cur = ''
    if cur.strip():
        out.append(cur)
    return [x for x in out if x.strip()]

def is_dialogue(para):
    qc = '“'
    return para.startswith('"') or para.startswith(qc) or (len(para) < 30 and para.count('“') == 1)

def process(text):
    lines = text.split('\n')
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            out.append('')
            continue
        # 保留章标题与分隔符
        if s == '===' or re.match(r'^第[一二三四五六七八九十百零]+卷', s) or re.match(r'^第.+章[　 ]', s):
            out.append(s)
            continue
        # 对话段不拆
        if is_dialogue(s):
            out.append(s)
            continue
        n = len(re.sub(r'\s', '', s))
        if n <= TARGET_MAX:
            out.append(s)
            continue
        # 拆叙述段
        sentences = split_sentences(s)
        if len(sentences) <= 1:
            out.append(s)  # 单句超长，无法安全拆，保留
            continue
        cur = ''
        for sent in sentences:
            if cur and len(re.sub(r'\s', '', cur)) + len(re.sub(r'\s', '', sent)) <= TARGET_MAX:
                cur += sent
            else:
                if cur:
                    out.append(cur.strip())
                cur = sent
        if cur:
            out.append(cur.strip())
    return '\n'.join(out)

def stat(path):
    t = open(path, encoding='utf-8-sig').read()
    ps = [p.strip() for p in t.split('\n') if p.strip()]
    n = len(re.sub(r'\s', '', t))
    qc = '“'
    nar = [p for p in ps if not (p.startswith('"') or p.startswith(qc) or (len(p) < 25 and p.count(qc) == 1))]
    nn = len(re.sub(r'\s', '', '\n'.join(nar)))
    return len(ps), n, round(nn / max(len(nar), 1), 1), len(re.findall(r'[他她]说[，：]', t))

files = (sorted(glob.glob(f'{VOL}/第141章*.md')) +
         sorted(glob.glob(f'{VOL}/第14[2-5]章*.md')) +
         sorted(glob.glob(f'{VOL}/第14[6-9]章*.md')) +
         sorted(glob.glob(f'{VOL}/第15[0-9]章*.md')) +
         sorted(glob.glob(f'{VOL}/第16[0-9]章*.md')) +
         sorted(glob.glob(f'{VOL}/第17[0-9]章*.md')) +
         sorted(glob.glob(f'{VOL}/第180章*.md')))
print('%-20s %8s %8s' % ('章', '段(前→后)', '均段(前→后)'))
for f in files:
    before = stat(f)
    t = open(f, encoding='utf-8-sig').read()
    new = process(t)
    open(f, 'w', encoding='utf-8-sig').write(new)
    after = stat(f)
    print('%-20s %4d→%-4d %6.1f→%6.1f' % (os.path.basename(f)[:16], before[0], after[0], before[2], after[2]))
