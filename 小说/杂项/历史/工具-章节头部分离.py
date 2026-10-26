#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
章节头部分离工具 —— 把章节 .txt 的【元信息块 + 提要段】抽出来，汇总成一份《目录与章节台账.md》，
并（可选）把正文文件改写为「标题 + 纯正文」。

用法：
    python 工具-章节头部分离.py                    # 只生成目录，不动正文文件（预演）
    python 工具-章节头部分离.py --apply             # 生成目录 + 改写正文文件（自动先备份）
    python 工具-章节头部分离.py 备份-xxx            # 从指定目录读取（源文件已分离时用备份重建目录）
    python 工具-章节头部分离.py 备份-xxx --out 目录与章节台账.md

识别规则：
  1) 元信息块 = 文件开头第一个 "════" 行 ~ 第二个 "════" 行之间的【字段】行。
  2) 提要段   = 元信息块之后、标题行之后的第一个非空块，去空白长度落在 [80, 400] 字之间。
     —— 低于 80 字视为无提要（如楔子）；高于 400 字视为正文首段（第一卷部分章节没有独立提要段）。
  3) 已分离的文件（无 "════" 元信息块）会被跳过，不重复处理。
"""
import glob
import os
import re
import shutil
import sys
from datetime import datetime

AB_MIN = 80  # 提要段长度下限（低于此值视为无提要，仅作兜底）

# 【作者确认·最终口径】以下章节没有独立提要段，标题行之后直接就是正文第一句，不得当作提要剥离。
# 其余章节标题后首块一律为提要段——包括第03/04/05/06/07章，这五章提要段偏长（474~725 字），
# 不可因"偏长"就误判成正文首段。第09章标题后首块 2101 字是正文全篇，故无提要。
NO_AB = {'楔子', '第09章'}


def scan(src):
    """扫描源目录，返回记录列表（文件顺序：楔子 → 第01章 → ……）"""
    pats = ['楔子*.txt', '第*章*.txt']
    files = []
    for p in pats:
        files += glob.glob(os.path.join(src, p))
    files = sorted(set(files))
    recs, skipped = [], []
    for path in files:
        raw = open(path, encoding='utf-8').read()
        lines = raw.split('\n')
        fence = [i for i, l in enumerate(lines) if l.startswith('═')]
        if len(fence) < 2:
            skipped.append(os.path.basename(path))
            continue

        meta = {}
        for l in lines[fence[0] + 1:fence[1]]:
            m = re.match(r'【(.+?)】(.*)', l)
            if m:
                meta[m.group(1)] = m.group(2).strip()

        r = lines[fence[1] + 1:]
        i = 0
        while i < len(r) and r[i].strip() == '':
            i += 1
        title = r[i].strip()
        i += 1
        while i < len(r) and r[i].strip() == '':
            i += 1
        st = i
        blk = []
        while i < len(r) and r[i].strip() != '':
            blk.append(r[i])
            i += 1
        ab = '\n'.join(blk)
        n = len(re.sub(r'\s', '', ab))
        key = re.match(r'(楔子|第\d+章)', os.path.basename(path))
        key = key.group(1) if key else ''
        has_ab = (key not in NO_AB) and n >= AB_MIN
        body = '\n'.join(r[i:] if has_ab else r[st:])
        recs.append(dict(path=path, name=os.path.basename(path), meta=meta,
                         title=title, ab=ab if has_ab else '', body=body, has_ab=has_ab))
    return recs, skipped


def build_md(recs):
    nw = lambda s: len(re.sub(r'\s', '', s))
    total = sum(nw(x['body']) for x in recs)
    out = ['# 《废土旅法师》目录与章节台账\n']
    out.append('> 本文件汇总全部章节的**头部信息**：元信息（时间线 / 地点 / 出场 / 新增设定 / 伏笔 / 章型 / 本章钩子）与内容提要。')
    out.append('> 各章 `.txt` 文件已改为「标题 + 纯正文」，不再包含这些信息。\n')
    out.append(f'> 共 {len(recs)} 篇。正文合计约 **{total:,}** 字（不含本目录与标题行）。\n')
    no_ab = [x['name'] for x in recs if not x['has_ab']]
    if no_ab:
        out.append('> 原文件无独立提要段（提要栏标「（无）」）：' + '、'.join(no_ab) + '\n')

    out.append('## 速览\n')
    out.append('| 序 | 章节 | 标题 | 字数 | 时间线 |')
    out.append('|---|---|---|---|---|')
    for k, x in enumerate(recs):
        ch = x['meta'].get('章节', '')
        t = re.sub(r'^\S+[　 ]', '', ch)
        w = re.search(r'(\d+)', x['meta'].get('字数', ''))
        out.append(f"| {k} | {ch.split('　')[0]} | {t} | {w.group(1) if w else '—'} | {x['meta'].get('时间线', '—')} |")

    def emit(x):
        m = x['meta']
        out.append(f"\n### {m.get('章节', '')}\n")
        out.append(f"`{x['name']}`\n")
        out.append('- ' + ' ｜ '.join(f"**{k}** {m[k]}" for k in ['字数', '时间线', '地点', '出场', '章型'] if k in m))
        for k in ['新增设定', '伏笔', '本章钩子']:
            if k in m:
                out.append(f"- **{k}** {m[k]}")
        out.append(f"- **提要** {'（无）' if not x['has_ab'] else ''}")
        if x['has_ab']:
            out.append('')
            out.append('> ' + x['ab'].strip())

    idx = {x['name']: i for i, x in enumerate(recs)}
    vol2 = next((idx[n] for n in idx if re.match(r'第41章', n)), len(recs))
    out.append('\n---\n\n## 楔子\n')
    emit(recs[0])
    out.append('\n---\n\n## 第一卷\n')
    for x in recs[1:vol2]:
        emit(x)
    out.append('\n---\n\n## 第二卷·位面行走\n')
    for x in recs[vol2:]:
        emit(x)
    return '\n'.join(out) + '\n', total


def main():
    argv = [a for a in sys.argv[1:]]
    apply_ = '--apply' in argv
    argv = [a for a in argv if a != '--apply']
    out_path = None
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1]
        argv = argv[:argv.index('--out')] + argv[argv.index('--out') + 2:]
    src = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
    out_path = out_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), '目录与章节台账.md')

    recs, skipped = scan(src)
    if not recs:
        print('未找到带元信息块的章节文件（可能已全部分离）。')
        return
    md, total = build_md(recs)
    open(out_path, 'w', encoding='utf-8').write(md)
    print(f'目录已生成：{out_path}（{len(recs)} 篇，正文约 {total:,} 字）')
    if skipped:
        print(f'跳过（无元信息块，可能已分离）：{len(skipped)} 个 → {skipped[:5]}{"…" if len(skipped) > 5 else ""}')

    if not apply_:
        print('\n[预演模式] 未改动任何正文文件。加 --apply 可执行分离。')
        return

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    root = os.path.dirname(os.path.abspath(src if os.path.isdir(src) else src)) or '.'
    bak = os.path.join(root, f'备份-头部分离-{ts}')
    os.makedirs(bak, exist_ok=True)
    for item in os.listdir(root):
        if item.startswith('备份-') or item.startswith('.'):
            continue
        s = os.path.join(root, item)
        d = os.path.join(bak, item)
        shutil.copytree(s, d) if os.path.isdir(s) else shutil.copy2(s, d)
    print(f'已备份至：{bak}')

    for x in recs:
        open(x['path'], 'w', encoding='utf-8').write(x['title'] + '\n\n' + x['body'].strip('\n') + '\n')
    print(f'{len(recs)} 个正文文件已改写为「标题 + 纯正文」')


if __name__ == '__main__':
    main()
