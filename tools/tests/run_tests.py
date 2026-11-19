#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_tests.py —— 负向控制与自测（`npm test` 入口，零三方依赖）
================================================================================
v2 审计 G-02 / G-03：本仓此前 `package.json` 无 test script、无 CI、检查器
没有负向控制（规则自身错了，门禁照样全绿）。本脚本用「故意制造已知违规 →
断言门禁报红 → 恢复 → 断言报绿」证明门禁真的会响，而不是只确认文件存在。

测试：
  T1 治理指标 drift gate 的负向控制（手改 README 指标区块）
  T2 插件能力清单一致性（cordis.yml == plugins/*.mjs）
  T3 治理规则检查器干净态无 ERROR
  T4 放行判据 gate：能力缺失→BLOCKED；干净→PASS；同步不确定→DEGRADED
  T5 检索评测基线：MRR@10 ≥ 0.6 且 NDCG@10 ≥ 0.5（防止打分修复被回退）

外部基线：Policy-as-Code 的 --selftest 用 good/bad fixtures 元校验检查器本身。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
RESULTS: list[tuple[str, bool, str]] = []


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )


def record(name: str, ok: bool, detail: str = '') -> None:
    RESULTS.append((name, ok, detail))
    print(('PASS  ' if ok else 'FAIL  ') + name + (('  — ' + detail) if detail else ''))


def t1_metrics_drift() -> None:
    """负向控制：手改指标区块必须让 drift gate 报红；恢复后必须报绿。"""
    path = os.path.join(ROOT, 'README.md')
    raw = open(path, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    # 不再硬编码文档数：2026-11-19 该值从 1224 长到 1613，硬编码导致本测试静默失效
    # （「未找到指标区块」被当成 FAIL 挂在 T1 上，实际是夹具过期）。
    # 改为就地自增该行的数字，任何现值都能注入违规。
    tampered = re.sub(
        r'(\|\s*索引文档数\s*\|\s*\*\*)(\d+)(\*\*\s*\|)',
        lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}',
        text, count=1)
    if tampered == text:
        record('T1 治理指标负向控制', False, '未找到指标区块，无法注入违规')
        return
    try:
        open(path, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + tampered.encode('utf-8'))
        negative = run([PY, 'tools/metrics.py', '--check']).returncode != 0
    finally:
        open(path, 'wb').write(raw)
    restored = run([PY, 'tools/metrics.py', '--check']).returncode == 0
    record('T1 治理指标负向控制（改→红，恢复→绿）', negative and restored,
           f'injected_detected={negative} restored_ok={restored}')


def t2_capabilities() -> None:
    script = ("import('./tools/capabilities.mjs').then(m=>{"
              "const r=m.checkCapabilities(process.cwd());"
              "console.log(JSON.stringify(r.issues));"
              "process.exit(r.issues.length?1:0)})")
    r = run(['node', '-e', script])
    record('T2 插件声明 == 插件文件', r.returncode == 0,
           (r.stdout or r.stderr).strip()[:200])


def t3_rules_clean() -> None:
    r = run([PY, 'tools/checkers/rules_check.py', ROOT])
    errs = -1
    try:
        out = r.stdout
        payload = json.loads(out[out.index('{'):out.rindex('}') + 1])
        errs = payload.get('counts', {}).get('error', -1)
    except (ValueError, KeyError) as e:
        record('T3 治理规则检查器干净态', False, f'协议解析失败：{e}')
        return
    record('T3 治理规则检查器干净态无 ERROR', errs == 0, f'error={errs}')


def t4_gate() -> None:
    script = """
import('./tools/plugins/20-report.mjs').then(m => {
  const root = process.cwd();
  const mk = (findings) => m.evaluateGate(
    [{ checker: 'pkm', findings }], { partial: true, root });
  const bad = mk([{ severity: 'warn', code: 'PKM-NO-INDEX', message: '索引缺失' }]);
  const clean = mk([]);
  const deg = mk([{ severity: 'warn', code: 'SYNC-UNKNOWN-STATE', message: '状态未确认' }]);
  const ok = !bad.pass && clean.pass && deg.pass && deg.status === 'DEGRADED'
             && bad.status === 'BLOCKED' && clean.status === 'PASS';
  console.log(JSON.stringify({
    bad: bad.status, clean: clean.status, deg: deg.status,
    conditions: clean.conditions.length,
  }));
  process.exit(ok ? 0 : 1);
}).catch(e => { console.error(e); process.exit(2) })
"""
    r = run(['node', '-e', script])
    record('T4 放行判据（能力缺失/干净/同步降级）', r.returncode == 0,
           (r.stdout or r.stderr).strip()[:220])


def t5_retrieval() -> None:
    """检索质量回归：修复后的 MRR/NDCG 不得跌破基线。"""
    r = run([PY, 'tools/pkm/eval.py', '--mode', 'current', '--json'])
    try:
        s = json.loads(r.stdout)['current']['summary']
    except (ValueError, KeyError) as e:
        record('T5 检索评测基线', False, f'解析失败：{e} / {(r.stderr or "")[:160]}')
        return
    ok = s['MRR@10'] >= 0.6 and s['NDCG@10'] >= 0.5
    record('T5 检索评测（MRR≥0.6 / NDCG≥0.5）', ok,
           f"MRR={s['MRR@10']:.3f} NDCG={s['NDCG@10']:.3f} Hit@5={s['HitRate@5']:.3f}")


def t6_derived_consistency() -> None:
    """派生整档口径：索引判定必须**从属**于审校判定（is_derived ⇒ is_aggregate）。

    两个模块刻意各自持有规则副本（doc_review.py 会被复制成仓外 Skill，必须自足）。
    二者的**严格度不同，且必须如此**：
      · 审校侧宽松（含「全书/全文/区间章」）—— 判错只影响重复告警的噪音；
      · 索引侧严格 —— 判错会把内容从检索里摘掉。
    所以断言的是方向而非相等：**索引藏得起的，审校必须也认为是派生件**；
    反向不要求（审校可以多认，索引不能多藏）。

    2026-11-19 立此闸的直接原因：首版规则把「全书总纲」和蜀山
    `第001-005章（C01-崖前）.md`（该书正文主存形态）判成派生，
    会把整部蜀山摘出检索 —— 这类误判必须由测试挡住，不能靠人眼复核。
    """
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'pkm'))
    try:
        from pathlib import Path
        from scanner import is_derived
        import doc_review
    except ImportError as e:
        record('T6 派生整档口径', False, f'导入失败：{e}')
        return

    # (路径, 索引侧期望) —— 索引侧是硬断言；审校侧只要求不弱于索引
    cases = [
        ('小说/正文五卷-整合版.md', True),
        ('点子库/05-实体书/正文/卷一.md', True),
        ('蜀山之撼天凡蚁登天路漫漫/正文/_正文施工规格-V3-卷三-施工单部分.md', True),
        ('蜀山之撼天凡蚁登天路漫漫/正文/蜀山 卷二-第151-175章-合订.md', True),
        # ↓ 三个负例：判成派生就会误藏内容
        ('蜀山之撼天凡蚁登天路漫漫/正文/蜀山 卷一-第001-005章（C01-崖前）.md', False),
        ('华夏克苏鲁/05_模板对齐/05-立项与大纲/01-全书总纲L1-L3.md', False),
        ('小说/第五卷/第216章_下舰.md', False),
        ('PKM/01-MOC/MOC-全库.md', False),
    ]
    corpus = doc_review.Corpus([], {})
    problems = []
    for rel, expect_scan in cases:
        got_scan = is_derived(rel)
        got_review = corpus.is_aggregate(doc_review.Doc(Path(rel), ''))
        if got_scan != expect_scan:
            problems.append(f'{rel}: 索引={got_scan} 期望={expect_scan}')
        elif got_scan and not got_review:
            problems.append(f'{rel}: 索引判派生但审校不认（藏内容无依据）')
    record('T6 派生整档口径（索引 ⊆ 审校）', not problems,
           '；'.join(problems) if problems else f'{len(cases)} 例通过')


def main() -> int:
    print(f'npm test — 负向控制与自测（root={ROOT}）')
    print('-' * 64)
    t1_metrics_drift()
    t2_capabilities()
    t3_rules_clean()
    t4_gate()
    t5_retrieval()
    t6_derived_consistency()
    failed = [r for r in RESULTS if not r[1]]
    print('-' * 64)
    print(f'{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
