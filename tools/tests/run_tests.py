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
    tampered = text.replace('| 索引文档数 | **1224** |', '| 索引文档数 | **9999** |', 1)
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


def main() -> int:
    print(f'npm test — 负向控制与自测（root={ROOT}）')
    print('-' * 64)
    t1_metrics_drift()
    t2_capabilities()
    t3_rules_clean()
    t4_gate()
    t5_retrieval()
    failed = [r for r in RESULTS if not r[1]]
    print('-' * 64)
    print(f'{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
