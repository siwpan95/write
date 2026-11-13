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

const SEV_ORDER = { error: 0, warn: 1, info: 2 }
const SEV_LABEL = {
  error: 'ERROR（硬冲突，必看）',
  warn: 'WARN（高概率，需定性）',
  info: 'INFO（体例统计，对照用）',
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

      const md = renderMarkdown(results, findings, counts, ts)
      const mdPath = path.join(dir, `${name}.md`)
      const jsonPath = path.join(dir, `${name}.json`)
      fs.writeFileSync(mdPath, md, 'utf-8')
      fs.writeFileSync(jsonPath, JSON.stringify({
        generatedAt: ts.toISOString(),
        counts,
        checkers: results.map((r) => ({
          checker: r.checker, ok: r.ok, severity: r.severity,
          summary: r.summary, counts: r.counts,
        })),
        findings,
      }, null, 1), 'utf-8')

      return { mdPath, jsonPath, counts, findings }
    }

    ctx.provide('report', { write })
    ctx.logger.info('report: 输出目录 %s', path.relative(root, reports) || reports)
  },
}

function renderMarkdown(results, findings, counts, ts) {
  const L = []
  L.push('# 工具链自检报告')
  L.push('')
  L.push(`- 生成时间：${ts.toLocaleString('zh-CN')}`)
  L.push(`- 检查器：${results.length} 个`)
  L.push(`- 发现总数：${findings.length} 条（ERROR ${counts.error} ／ WARN ${counts.warn} ／ INFO ${counts.info}）`)
  L.push('- 铁律：**只出风险与位置，不代改正文**。哪处该改由作者定。')
  L.push('')
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
