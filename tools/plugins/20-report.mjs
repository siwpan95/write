/**
 * 插件 20 · report —— 汇总报告
 *
 * 把各检查器的协议结果汇总成**一份**人读报告 + 一份机读 JSON。
 * 放在仓根 `审校报告/` 下（与 §八 的产物目录一致）。
 *
 * 提供：ctx.report.write(results, opts)
 */
import path from 'node:path'
import fs from 'node:fs'
import time from 'node:fs'
import { readPluginIds } from '../capabilities.mjs'

const SEV_ORDER = { error: 0, warn: 1, info: 2 }
const SEV_LABEL = {
  error: 'ERROR（硬冲突，必看）',
  warn: 'WARN（高概率，需定性）',
  info: 'INFO（体例统计，对照用）',
}

// 核心能力缺失：硬阻断（索引/图谱不可用 = 检索能力不可用）
const BLOCKING_CODES = new Set(['PKM-NO-INDEX', 'PKM-NO-GRAPH', 'CHECKER-MISSING', 'CHECKER-PROTOCOL'])
// 同步状态不确定：只降级上报，不因网络抖动阻断本地检查；
// 但**绝不允许**在这种情况下把报告标成「已同步 / ✅ 通过」。
const DEGRADE_CODES = new Set([
  'SYNC-UNKNOWN-STATE', 'SYNC-REMOTE-UNREACHABLE',
  'SYNC-REMOTE-BEHIND', 'SYNC-LOCAL-BEHIND', 'SYNC-DIVERGED',
])

/**
 * 放行判据（v2 审计 G-03）。
 * 历史问题：ok = counts.error == 0 只有一个条件，导致「项目未纳管 SKIP 静默」
 * 「缺 PKM/index.json 仅 WARN」「sync 三态互斥」三种情况仍盖「✅ 通过」。
 * 现在按外部基线（SonarQube quality gate = a set of conditions）改为条件集合。
 */
export function evaluateGate(results, opts = {}) {
  const partial = !!opts.partial
  // 期望的检查器 id 来自**实际注册表**（ctx.checkers.list()），不是 cordis.yml 的插件 id
  // —— 两者命名体系不同（plugin: checker-package vs checker: package），
  // 混用会把「6 个检查器全跑了」误判成「6 个检查器未运行」。
  let expected = Array.isArray(opts.expectedCheckers) ? opts.expectedCheckers : []
  if (!expected.length) {
    try {
      expected = readPluginIds(opts.root).filter((id) => id.startsWith('checker-'))
    } catch { /* cordis.yml 不可读时退化为不检查覆盖率 */ }
  }

  const ran = results.map((r) => r.checker)
  const missing = partial ? [] : expected.filter((id) => !ran.includes(id))
  const all = results.flatMap((r) => r.findings || [])
  const errCount = all.filter((f) => f.severity === 'error').length
  const capabilityBlockers = all.filter((f) => BLOCKING_CODES.has(f.code))
  const syncDegraded = all.filter((f) => DEGRADE_CODES.has(f.code))

  const conditions = [
    { metric: 'error', operator: '==', errorValue: 0, actual: errCount, pass: errCount === 0 },
    {
      metric: 'requiredCheckers', operator: '==', errorValue: expected.length, actual: ran.length,
      pass: missing.length === 0, skipped: partial,
      note: partial ? '单检查器模式，跳过覆盖率条件' : '',
    },
    {
      metric: 'capabilitiesAvailable', operator: '==', errorValue: 0,
      actual: capabilityBlockers.length, pass: capabilityBlockers.length === 0,
    },
  ]

  const degraded = [
    ...missing.map((id) => `检查器未运行：${id}`),
    ...capabilityBlockers.map((f) => `${f.code}：${f.message}`),
    ...syncDegraded.map((f) => `${f.code}：${f.message}`),
  ]
  const hardPass = conditions.every((c) => c.pass || c.skipped)
  return {
    pass: hardPass,
    status: !hardPass ? 'BLOCKED' : (syncDegraded.length ? 'DEGRADED' : 'PASS'),
    conditions,
    degraded,
    scope: { expectedCheckers: expected, ranCheckers: ran, partial },
  }
}

export const Report = {
  name: 'report',
  inject: ['config', 'projects'],

  apply(ctx, config = {}) {
    const { root, reports } = ctx.config

    function write(results, opts = {}) {
      const dir = opts.dir || reports
      fs.mkdirSync(dir, { recursive: true })
      const stamp = time.strftime ? '' : ''
      const ts = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      const name = `${config.filename || '工具链自检报告'}-` +
        `${ts.getFullYear()}${pad(ts.getMonth() + 1)}${pad(ts.getDate())}-` +
        `${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}`

      const findings = []
      for (const r of results) {
        for (const f of r.findings || []) {
          findings.push({ ...f, checker: r.checker })
        }
      }
      findings.sort((a, b) =>
        (SEV_ORDER[a.severity] ?? 3) - (SEV_ORDER[b.severity] ?? 3) ||
        String(a.file).localeCompare(String(b.file)) ||
        (a.line || 0) - (b.line || 0))

      const counts = { error: 0, warn: 0, info: 0 }
      for (const f of findings) {
        if (counts[f.severity] !== undefined) counts[f.severity]++
      }

      const gate = evaluateGate(results, {
        partial: opts.partial,
        root,
        expectedCheckers: opts.expectedCheckers,
      })
      const md = renderMarkdown(results, findings, counts, ts, gate)
      const mdPath = path.join(dir, `${name}.md`)
      const jsonPath = path.join(dir, `${name}.json`)
      // 产物去重（G-07）：同一输入产生相同 md 时不写第二份，复用已有报告。
      // 生成时间已从 md 正文移除，故内容可逐字节比较；JSON 也一并复用。
      // 已有历史产物**不删除**（可重跑、无追溯价值，清理需作者另行授权）。
      let finalMd = mdPath
      const stem = config.filename || '工具链自检报告'
      for (const f of fs.readdirSync(dir)) {
        if (!f.startsWith(stem) || !f.endsWith('.md')) continue
        const p = path.join(dir, f)
        try {
          if (fs.readFileSync(p, 'utf-8') === md) { finalMd = p; break }
        } catch { /* 读不到就跳过 */ }
      }
      if (finalMd !== mdPath) {
        return {
          mdPath: finalMd,
          jsonPath: finalMd.replace(/\.md$/, '.json'),
          counts, findings, gate, deduplicated: true,
        }
      }
      fs.writeFileSync(mdPath, md, 'utf-8')
      fs.writeFileSync(jsonPath, JSON.stringify({
        generatedAt: ts.toISOString(),
        gate,
        counts,
        checkers: results.map((r) => ({
          checker: r.checker, ok: r.ok, severity: r.severity,
          summary: r.summary, counts: r.counts,
        })),
        findings,
      }, null, 1), 'utf-8')

      return { mdPath, jsonPath, counts, findings, gate, deduplicated: false }
    }

    ctx.provide('report', { write })
    ctx.logger.info('report: 输出目录 %s', path.relative(root, reports) || reports)
  },
}

function renderMarkdown(results, findings, counts, ts, gate) {
  const L = []
  L.push('# 工具链自检报告')
  L.push('')
  L.push('- 生成批次：见文件名时间戳（时间戳只进文件名，不进报告正文 —— 保证同一输入同一结果）')
  L.push(`- 检查器：${results.length} 个`)
  L.push(`- 发现总数：${findings.length} 条（ERROR ${counts.error} ／ WARN ${counts.warn} ／ INFO ${counts.info}）`)
  L.push('- 铁律：**只出风险与位置，不代改正文**。哪处该改由作者定。')
  L.push('')
  const statusLabel = gate.status === 'PASS' ? '✅ 可放行'
    : gate.status === 'DEGRADED' ? '⚠️ 状态未确认 —— 本地检查可放行，但同步结论不成立，不得视为「已同步」'
      : '⛔ 阻断 —— 放行条件未满足'
  L.push(`## 放行判定：${statusLabel}`)
  L.push('')
  L.push('> 判据为条件集合（不再是单一 `error == 0`）；依据 v2 审计 G-03。')
  L.push('')
  L.push('| 条件 | 期望 | 实测 | 结果 |')
  L.push('|---|---|---|---|')
  for (const c of gate.conditions) {
    const result = c.skipped ? '跳过（单检查器模式）' : (c.pass ? '✅ 通过' : '❌ 未满足')
    L.push(`| \`${c.metric}\` ${c.operator} ${c.errorValue} | ${c.errorValue} | ${c.actual} | ${result} |`)
  }
  L.push('')
  if (gate.degraded.length) {
    L.push('### 状态未确认 / 降级项（必须显性上报）')
    L.push('')
    for (const d of gate.degraded) L.push(`- ${d}`)
    L.push('')
  }
  L.push('## 检查器结果')
  L.push('')
  L.push('| 检查器 | 结论 | ERROR | WARN | INFO | 说明 |')
  L.push('|---|---|---|---|---|---|')
  for (const r of results) {
    const c = r.counts || {}
    L.push(`| \`${r.checker}\` | ${r.ok ? '✅ 通过' : '❌ 有 ERROR'} | ` +
      `${c.error || 0} | ${c.warn || 0} | ${c.info || 0} | ${r.summary || ''} |`)
  }
  L.push('')
  if (findings.length) {
    L.push('## 逐条发现')
    L.push('')
    for (const sev of ['error', 'warn', 'info']) {
      const sub = findings.filter((f) => f.severity === sev)
      if (!sub.length) continue
      L.push(`### ${SEV_LABEL[sev]}（${sub.length} 条）`)
      L.push('')
      for (const f of sub) {
        const loc = f.file && f.file !== '-' ? `\`${f.file}${f.line ? ':' + f.line : ''}\`` : '—'
        L.push(`- ${loc} \`${f.code}\`${f.checker ? ` · \`${f.checker}\`` : ''}`)
        L.push(`  - ${f.message}`)
        if (f.snippet) L.push(`  - 原文：${f.snippet}`)
        if (f.suggestion) L.push(`  - 建议：${f.suggestion}`)
      }
      L.push('')
    }
  } else {
    L.push('## 逐条发现')
    L.push('')
    L.push('（无）')
    L.push('')
  }
  return L.join('\n')
}

export default Report
