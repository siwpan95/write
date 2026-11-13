/**
 * 插件 11 · checker-doc-review —— 审校引擎插件
 *
 * 把「文档审校」能力接入插件树：跑 tools/doc_review.py，按项目口径配置，
 * 产出统一协议结果。**只出报告，不改正文**（与本仓 11 号模板铁律同源）。
 *
 * 提供：ctx.checkers 列表里的一项 {id, name, run()}
 */
import path from 'node:path'

export const CheckerDocReview = {
  name: 'checker-doc-review',
  inject: ['config', 'projects', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const { root } = ctx.config
    const registry = ctx.projects
    const engine = config.engine || './tools/doc_review.py'
    const only = config.only || []

    /**
     * 跑一次审校。
     * @param {string[]} projectIds 限定项目；空＝全部可用项目
     */
    async function run(projectIds = []) {
      const projects = projectIds.length
        ? projectIds.map((id) => registry.get(id)).filter((p) => p && p.available)
        : registry.all()

      if (!projects.length) {
        return {
          checker: 'doc-review', ok: false, severity: 'error',
          summary: '没有可审的项目',
          counts: { error: 1, warn: 0, info: 0 },
          findings: [{
            severity: 'error', category: '执行', code: 'NO-PROJECT',
            file: '-', line: 0, snippet: '',
            message: '没有可审的项目（检查 cordis.yml 的 registry.projects 与口径文件）',
            suggestion: '确认项目目录与口径 JSON 存在',
          }],
          artifacts: [], meta: {},
        }
      }

      const results = []
      for (const p of projects) {
        // --protocol 让引擎按检查器协议输出（stdout 一个 JSON 对象）
        const args = ['--text', p.text, '--protocol']
        const cfgArg = registry.configArg(p.id)
        if (cfgArg) args.push('--config', cfgArg)
        for (const o of only) args.push('--only', o)

        const outDir = path.resolve(ctx.config.reports, 'doc-review')
        args.push('--out', outDir)

        ctx.logger.info('doc-review: 项目 %s（%s）', p.id, p.name)
        const r = await ctx.runner.run('doc-review', engine, args, { cwd: root })
        r.meta = { ...(r.meta || {}), project: p.id, projectName: p.name }
        results.push(r)
      }

      // 汇总：多个项目的结果合并成一条协议输出
      const findings = []
      const artifacts = []
      let error = 0, warn = 0, info = 0
      for (const r of results) {
        for (const f of r.findings || []) {
          findings.push({ ...f, project: r.meta?.project })
        }
        for (const a of r.artifacts || []) artifacts.push(a)
        error += r.counts?.error || 0
        warn += r.counts?.warn || 0
        info += r.counts?.info || 0
      }

      return {
        checker: 'doc-review',
        ok: error === 0,
        severity: error ? 'error' : (warn ? 'warn' : 'info'),
        summary: `${projects.length} 个项目：错误 ${error} ／ 警告 ${warn} ／ 提示 ${info}`,
        counts: { error, warn, info },
        findings,
        artifacts,
        meta: { projects: projects.map((p) => p.id) },
      }
    }

    ctx.checkers.register({
      id: 'doc-review',
      name: '文档审校（错别字/时间矛盾/数字口径/缺失条件/体例/术语/重复/结构）',
      run,
    })
    ctx.logger.info('checker-doc-review: engine=%s', engine)
  },
}

export default CheckerDocReview
