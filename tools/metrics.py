#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metrics.py —— 全仓治理指标单一事实源（零三方依赖）
================================================================================
背景（v2 审计 G-01）：治理数字散落在 12+ 个文件且 6 套值并存
（1161/1169/1173/1205/1224、出链 102/1333/1464/2021、插件 10/12/9），
恰好违反《通用模板包/00-总档与SOP.md》§九 R-8「计数类口径唯一定义处」。

本模块把「同一事实写两处必须相等」变成机器事实：
  collect()          从 PKM/index.json、PKM/graph.json、tools/cordis.yml 取数
  --write            生成 tools/metrics.json + 重写 README.md 的 metrics 区块
  --check            drift gate：事实源未变、README 区块未被手改、旧值未复发

设计纪律（沿用仓内既有做法）：
  - 零三方依赖；生成物不带时间戳（用 index.json 的 generated_at 作数据时点，
    避免每次运行制造 diff 噪音 —— 同《工作区规范》§8.6「生成物不带时间戳」）
  - 历史快照文件（诊断与选型报告 / 换机部署 / guide-0001 / 文档元数据清单）
    显式豁免，它们记录的是建层前后时点，不做现值校验 —— 同 v3.11
    `EXCLUDE_PREFIXES` 纪律
  - 只做「声明 vs 实测」的一致性，不改任何正文/设定/冻结卷

用法：
  python tools/metrics.py --write
  python tools/metrics.py --check        # exit 0/1，可直接进 CI
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS = os.path.join(ROOT, 'tools', 'metrics.json')
README = os.path.join(ROOT, 'README.md')

BEGIN = '<!-- metrics:begin -->'
END = '<!-- metrics:end -->'

# 显式豁免：这些文件里的旧数字是「历史时点快照」，不是现值声明
HISTORICAL_EXEMPT = (
    'PKM/诊断与选型报告-20261113.md',
    'PKM/换机部署.md',
    'PKM/00-原子笔记/guide-0001-PKM连接层使用指南.md',
    'PKM/02-索引/文档元数据清单.md',
    '审计报告-深度审计与架构重构-20261113.md',
    '审计报告-联网深度审计-20261114.md',      # v1 已作废，纯过程留痕
    '审计报告-知识库运行与规则-20261114.md',  # v2 审计快照，引用旧值作证据
)

# 旧值复发即 ERROR（防回归断言，同通用模板包 regression_checks.txt 思路）
FORBIDDEN = (
    ('README.md', r'10 个插件', '插件数应引用 metrics 区块（当前 12）'),
    ('README.md', r'把 1161 个孤立 Markdown', '文档数应由 metrics 区块承载'),
    ('README.md', r'\*\*实测（2026-11-13）\*\*[^\n]*1173 文档', '建层前快照不得标成「实测」现值'),
    ('PKM/README.md', r'当前 8 篇永久笔记', '实际 25 篇永久笔记 + 1 篇指南'),
    ('tools/README.md', r'\*\*全仓\*\* 8 个作品/项目', '当前注册 3 个项目'),
    ('审校报告/README.md', r'3 个检查器的结论', '当前 5 个检查器'),
)


def _load_json(rel: str) -> dict:
    with open(os.path.join(ROOT, rel), encoding='utf-8-sig') as f:
        return json.load(f)


def _cordis_text() -> str:
    with open(os.path.join(ROOT, 'tools', 'cordis.yml'), encoding='utf-8-sig') as f:
        return f.read()


def collect() -> dict:
    """从唯一事实源取数；任何指标都必须能指出它来自哪个文件。"""
    idx = _load_json('PKM/index.json')
    graph = _load_json('PKM/graph.json')
    cordis = _cordis_text()
    s = idx['summary']
    plugin_ids = re.findall(r'^- id:\s*([^\s#]+)', cordis, re.M)
    # 嵌套项目登记：必须用 [ \t]，不能用 \s —— \s 含换行，会把行首插件也吞进来
    project_ids = re.findall(r'^[ \t]+- id:\s*([^\s#]+)', cordis, re.M)
    checkers = [p for p in plugin_ids if p.startswith('checker-')]
    return {
        'schema': 1,
        'data_as_of': idx.get('generated_at', ''),
        'docs': s['docs'],
        'by_type': s.get('by_type', {}),
        'total_links': s['total_links'],
        'total_broken': s['total_broken'],
        'knowledge_docs': s.get('knowledge_docs', 0),
        'knowledge_orphan_rate': s.get('knowledge_orphan_rate', 0.0),
        'frontmatter_docs': s.get('frontmatter_docs', 0),
        'plugins': len(plugin_ids),
        'projects_registered': len(project_ids),
        'checkers_registered': len(checkers),
        'checker_adapters': len(glob.glob(os.path.join(ROOT, 'tools', 'checkers', '*.py'))),
        'graph_schema': graph.get('schema'),
        'sources': {
            'docs/by_type/total_links/total_broken/knowledge_*/frontmatter_docs': 'PKM/index.json + PKM/graph.json',
            'plugins/projects_registered/checkers_registered': 'tools/cordis.yml',
            'checker_adapters': 'tools/checkers/*.py',
            'graph_schema': 'PKM/graph.json',
        },
    }


def render(m: dict) -> str:
    """生成 README 的指标区块（人工不得手改标记区间内的内容）。"""
    lines = [
        BEGIN,
        '> **治理指标（自动生成 · 勿手改）** ｜ 事实源：`PKM/index.json` / `PKM/graph.json` / `tools/cordis.yml`；',
        '> 由 `npm run metrics` 生成、`npm run metrics:check` 校验（手改本区块即报错）。',
        '> 数据时点：`' + str(m['data_as_of']) + '`',
        '>',
        '> | 指标 | 值 | 事实源 |',
        '> |---|---:|---|',
        f"> | 索引文档数 | **{m['docs']}** | `PKM/index.json` |",
        f"> | 出链总数 | **{m['total_links']}** | `PKM/graph.json` |",
        f"> | 断链 | **{m['total_broken']}** | `PKM/graph.json` |",
        f"> | 知识节点孤立率 | **{m['knowledge_orphan_rate']}%** | `PKM/index.json` |",
        f"> | frontmatter 文档数 | **{m['frontmatter_docs']}** | `PKM/index.json` |",
        f"> | 插件数 | **{m['plugins']}** | `tools/cordis.yml`（行首 `- id`） |",
        f"> | 已注册项目 | **{m['projects_registered']}** | `tools/cordis.yml`（projects 段） |",
        f"> | 已注册检查器 | **{m['checkers_registered']}** | `tools/cordis.yml`（checker-* 插件） |",
        f"> | 检查器适配器 | **{m['checker_adapters']}** | `tools/checkers/*.py`（doc-review 直连引擎，故少 1） |",
        '>',
        '> 文档形态分布：' + ' / '.join(f'{k} {v}' for k, v in m['by_type'].items()),
        '>',
        '> 历史时点快照（1161 / 1173 / 102 / 1333 / 1464）保留在诊断报告与换机部署文档中，',
        '> 不作现值校验 —— 见 `tools/metrics.py` 的 `HISTORICAL_EXEMPT`。',
        END,
    ]
    return '\n'.join(lines)


def _read_text(rel: str) -> tuple[str, bool, str]:
    raw = open(os.path.join(ROOT, rel), 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in text else '\n'
    return text, bom, nl


def _write_text(rel: str, text: str, bom: bool) -> None:
    payload = (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')
    with open(os.path.join(ROOT, rel), 'wb') as f:
        f.write(payload)


def do_write() -> int:
    m = collect()
    with open(METRICS, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')
    text, bom, nl = _read_text('README.md')
    block = render(m).replace('\n', nl)
    pattern = re.escape(BEGIN) + r'.*?' + re.escape(END)
    if re.search(pattern, text, re.S):
        new_text = re.sub(pattern, lambda _: block, text, flags=re.S)
    else:
        # 首次：插到「## 工作区规范」之前
        anchor = '## 工作区规范'
        new_text = text.replace(anchor, block + nl + nl + anchor, 1)
        if new_text == text:
            print('[metrics] 找不到插入锚点，未改 README', file=sys.stderr)
            return 2
    _write_text('README.md', new_text, bom)
    print(f"[metrics] 已写入 tools/metrics.json 与 README.md 指标区块（docs={m['docs']}, plugins={m['plugins']}）")
    return 0


def do_check() -> int:
    m = collect()
    issues: list[str] = []

    # 1) 事实源文件是否与当前实测一致
    try:
        saved = _load_json('tools/metrics.json')
    except (OSError, ValueError) as e:
        print(f'[metrics] 无法读取 tools/metrics.json：{e}', file=sys.stderr)
        return 1
    if saved != m:
        diff_keys = [k for k in set(saved) | set(m) if saved.get(k) != m.get(k)]
        issues.append(f'tools/metrics.json 与实测不符，差异字段：{", ".join(sorted(diff_keys))}')

    # 2) README 区块是否被手改（drift gate）
    text, _, nl = _read_text('README.md')
    pattern = re.escape(BEGIN) + r'(.*?)' + re.escape(END)
    hit = re.search(pattern, text, re.S)
    if not hit:
        issues.append('README.md 缺少 metrics:begin/end 指标区块')
    else:
        expected = render(m).replace('\n', nl)
        actual = (BEGIN + hit.group(1) + END)
        if actual.replace('\r\n', '\n') != expected.replace('\r\n', '\n'):
            issues.append('README.md 指标区块被手改或与事实源不一致（请跑 npm run metrics）')

    # 3) 旧值复发断言（只查时效性治理文件，历史快照显式豁免）
    for rel, pat, why in FORBIDDEN:
        if rel in HISTORICAL_EXEMPT:
            continue
        try:
            body, _, _ = _read_text(rel)
        except OSError:
            continue
        if re.search(pat, body):
            issues.append(f'{rel} 出现已作废声明 /{pat}/ —— {why}')

    if issues:
        print('[metrics] 一致性检查失败：', file=sys.stderr)
        for i in issues:
            print(f'  - {i}', file=sys.stderr)
        return 1
    print(f"[metrics] OK — 事实源一致，README 区块未漂移，旧值 0 复发（docs={m['docs']}, links={m['total_links']}, plugins={m['plugins']}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='全仓治理指标单一事实源')
    ap.add_argument('--write', action='store_true', help='生成 metrics.json 与 README 指标区块')
    ap.add_argument('--check', action='store_true', help='一致性校验（drift gate）')
    args = ap.parse_args()
    if args.write:
        return do_write()
    if args.check:
        return do_check()
    print(json.dumps(collect(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
