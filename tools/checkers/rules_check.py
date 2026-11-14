#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rules_check.py —— 全仓治理规则一致性检查器（适配器，协议 JSON）
================================================================================
v2 审计 G-02：全仓治理规则此前 **0 条机械断言**（规则能力只集中在
`通用模板包/tools/regression_checks.txt`，48 行）。本检查器把「让规则自己
能被机器校验」接入 `npm run check`，成为 cordis.yml 中登记的第 6 个检查器。

断言清单（全部只读、零三方依赖）：
  R-01 治理指标 drift gate        —— 端到端复用 tools/metrics.py --check
  R-02 插件声明 == 插件文件        —— cordis.yml 行首 - id 数 == plugins/*.mjs 数
  R-03 README 优先                 —— 治理锚点存在（工作区规范 / 纪律 / metrics 区块）
  R-04 章节命名合规率              —— 汇总观察项（不逐条刷屏）
  R-05 失效条目登记表 JSONL 合法性 —— 为 G-06「失效规则机读化」预留

口径：规则漂移＝ERROR（规则失效必须显性上报）；统计类＝INFO。
不改任何正文/设定/冻结卷。

作者：WorkBuddy ｜ 2026-11-14
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, '..'))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

from checker_protocol import emit, run  # noqa: E402


def _read(path: str) -> str:
    with open(path, encoding='utf-8-sig') as f:
        return f.read()


def _finding(sev, code, message, suggestion='', file='-', line=0):
    return {
        'severity': sev, 'category': '治理规则', 'code': code,
        'file': file, 'line': line, 'snippet': '',
        'message': message, 'suggestion': suggestion,
    }


def check(root: str) -> list[dict]:
    findings: list[dict] = []

    # ---- R-01 治理指标 drift gate（端到端调用，不重复实现） ----
    proc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, 'metrics.py'), '--check'],
        cwd=root, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or '').strip().replace('\n', ' ')[:600]
        findings.append(_finding(
            'error', 'RULES-METRICS-DRIFT',
            f'治理指标事实源校验失败：{detail}',
            '运行 `npm run metrics` 重新生成，或修正被手改的 README 指标区块',
            'tools/metrics.json',
        ))
    else:
        findings.append(_finding(
            'info', 'RULES-METRICS-OK',
            '治理指标事实源一致：README 区块未漂移、旧值 0 复发',
            '—', 'tools/metrics.json',
        ))

    # ---- R-02 插件声明 == 插件文件 ----
    cordis = _read(os.path.join(TOOLS, 'cordis.yml'))
    ids = re.findall(r'^- id:\s*([^\s#]+)', cordis, re.M)
    files = glob.glob(os.path.join(TOOLS, 'plugins', '*.mjs'))
    if len(ids) != len(files):
        findings.append(_finding(
            'error', 'RULES-PLUGIN-COUNT',
            f'cordis.yml 声明 {len(ids)} 个插件，但 plugins/*.mjs 有 {len(files)} 个',
            '新增/删除插件时须同步 cordis.yml 与 plugins/ 目录',
            'tools/cordis.yml',
        ))
    else:
        findings.append(_finding(
            'info', 'RULES-PLUGIN-COUNT-OK',
            f'插件声明与文件一致（{len(ids)} 个）', '—', 'tools/cordis.yml',
        ))

    # ---- R-03 README 优先（治理锚点） ----
    readme = _read(os.path.join(root, 'README.md'))
    for anchor in ('## 工作区规范', '## 纪律', '<!-- metrics:begin -->'):
        if anchor not in readme:
            findings.append(_finding(
                'error', 'RULES-README-ANCHOR',
                f'README.md 缺少治理锚点「{anchor}」',
                '《工作区规范》§七：README 是唯一顶层索引，结构变更须同步',
                'README.md',
            ))

    # ---- R-04 章节命名合规率（汇总观察项） ----
    pat = re.compile(r'^第\d{2,3}章_[^/\\]+\.md$')
    total = ok = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', 'node_modules', '审校报告', '__pycache__')]
        for fn in filenames:
            if not fn.endswith('.md'):
                continue
            if not re.match(r'^第\d+章', fn):
                continue
            total += 1
            if pat.match(fn):
                ok += 1
    rate = (ok * 100.0 / total) if total else 0.0
    findings.append(_finding(
        'info', 'RULES-NAMING',
        f'章文件严格合规 {ok}/{total}（{rate:.1f}%）；规则见《工作区规范》§二（位数 2~3 位、分隔符 _）',
        '短横分隔属历史形态，按 G-12 登记例外，不逐条报错',
        '工作区规范.md',
    ))

    # ---- R-05 失效条目登记表 JSONL 合法性 ----
    dep = os.path.join(root, 'PKM', '02-索引', '失效条目登记表.md')
    if os.path.exists(dep):
        bad = []
        for i, line in enumerate(_read(dep).splitlines(), 1):
            s = line.strip()
            if s.startswith('{'):
                try:
                    json.loads(s)
                except ValueError as e:
                    bad.append(f'{i}: {e}')
        if bad:
            findings.append(_finding(
                'error', 'RULES-DEPRECATED-JSONL',
                f'失效条目登记表存在非法 JSON 行：{"; ".join(bad[:3])}',
                '每行须为独立 JSON 对象', 'PKM/02-索引/失效条目登记表.md',
            ))
        else:
            findings.append(_finding(
                'info', 'RULES-DEPRECATED-OK',
                '失效条目登记表 JSONL 格式合法', '—',
                'PKM/02-索引/失效条目登记表.md',
            ))
    else:
        findings.append(_finding(
            'warn', 'RULES-DEPRECATED-MISSING',
            '失效条目登记表尚未建立（G-06 未完成）',
            '建 PKM/02-索引/失效条目登记表.md，把「不再作为判据」的结论机读化',
            'PKM/02-索引/',
        ))

    # ---- R-06 受控登记表重复 path（显性上报；去重规则需作者裁定，不阻断）----
    meta = os.path.join(root, 'PKM', '02-索引', '文档元数据清单.md')
    if os.path.exists(meta):
        seen: dict[str, int] = {}
        for line in _read(meta).splitlines():
            s = line.strip()
            if not s.startswith('{'):
                continue
            try:
                o = json.loads(s)
            except ValueError:
                continue
            p = o.get('path', '')
            seen[p] = seen.get(p, 0) + 1
        dups = {p: n for p, n in seen.items() if n > 1}
        if dups:
            findings.append(_finding(
                'warn', 'RULES-META-DUP',
                f'文档元数据清单有 {len(dups)} 个重复 path（共 {sum(dups.values()) - len(dups)} 条被覆盖）：'
                + '；'.join(f'{p.split("/")[-1]}×{n}' for p, n in list(dups.items())[:3]),
                '追加前查重；合并 tags/aliases 并写 note 留痕（合并规则需作者裁定）',
                'PKM/02-索引/文档元数据清单.md',
            ))

    return findings


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    sys.exit(run('rules', check, os.path.abspath(root)))
