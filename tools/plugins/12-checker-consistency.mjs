/**
 * 插件 12 · checker-consistency —— 项目结构一致性扫描插件
 *
 * 跑各项目自带的结构一致性扫描（章号 / 章名 / 尾标 / 字数）。
 * 扫描器各自项目维护（口径属于项目，不属于工具层），
 * 本插件只负责按项目清单调度并把结果收进统一协议。
 *
 * 提供：ctx.checkers 列表里的一项 {id, name, run()}
 */
import path from 'node:path'
import fs from 'node:fs'

export const CheckerConsistency = {
  name: 'checker-consistency',
  inject: ['config', 'projects', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const { root } = ctx.config
    const adapter = config.adapter || './tools/checkers/consistency_check.py'
    // 每个项目声明自己的扫描器（相对仓根）
    const scanners = config.scanners || {
      dianzi: {
        root: './点子库',
        scanner: './点子库/04-工具/audit_consistency.py',
      },
    }
    // 只对这些项目跑（空＝全部）
    const enabled = config.projects || []

    async function run() {
      const items = Object.entries(scanners)
        .filter(([id]) => !enabled.length || enabled.includes(id))
      if (!items.length) {
        return {
          checker: 'consistency', ok: true, severity: 'info',
          summary: '未配置任何一致性扫描项',
          counts: { error: 0, warn: 0, info: 0 },
          findings: [], artifacts: [], meta: {},
        }
      }

      const findings = []
      let error = 0, warn = 0, info = 0
      for (const [id, spec] of items) {
        const adapterPath = path.resolve(root, adapter)
        if (!fs.existsSync(adapterPath)) {
          findings.push({
            severity: 'error', category: '执行', code: 'CHECKER-MISSING',
            file: adapterPath, line: 0, snippet: '',
            message: '一致性扫描适配器不存在',
            suggestion: '检查 cordis.yml 的 checker-consistency.adapter 配置',
          })
          error++
          continue
        }
        ctx.logger.info('consistency: 项目 %s', id)
        const r = await ctx.runner.run('consistency', adapterPath, [
          '--project-root', spec.root,
          '--scanner', spec.scanner,
        ], { cwd: root })
        for (const f of r.findings || []) {
          findings.push({ ...f, project: id })
        }
        error += r.counts?.error || 0
        warn += r.counts?.warn || 0
        info += r.counts?.info || 0
      }

      return {
        checker: 'consistency',
        ok: error === 0,
        severity: error ? 'error' : (warn ? 'warn' : 'info'),
        summary: `${items.length} 个项目：错误 ${error} ／ 警告 ${warn}`,
        counts: { error, warn, info },
        findings, artifacts: [],
        meta: { projects: items.map(([id]) => id) },
      }
    }

    ctx.checkers.register({
      id: 'consistency',
      name: '项目结构一致性（章号/章名/尾标/字数）',
      run,
    })
    ctx.logger.info('checker-consistency: %d 个扫描项', Object.keys(scanners).length)
  },
}

export default CheckerConsistency
