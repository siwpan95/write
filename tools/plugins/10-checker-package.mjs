/**
 * 插件 10 · checker-package —— 通用模板包自检插件
 *
 * 跑 `通用模板包/tools/check_package.py`：包级引用完整性（C2/C3）、表格列数
 * （C5）、编码（C1）、防回归断言（C8）。
 *
 * 该脚本原本只打印人读报告；本插件把它接到统一协议上，
 * 使「模板包有问题」也能进同一份汇总报告。
 *
 * 提供：ctx.checkers 列表里的一项 {id, name, run()}
 */
import path from 'node:path'
import fs from 'node:fs'

export const CheckerPackage = {
  name: 'checker-package',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const { root } = ctx.config
    const pkgRoot = path.resolve(root, config.package || './通用模板包')
    // 适配器：把 check_package.py 的人读报告包成协议 JSON
    // （原脚本是包级资产，有 sha256 与 MANIFEST 保护，**不改它**）
    const script = config.adapter || './tools/checkers/package_check.py'

    async function run() {
      const scriptPath = path.resolve(root, script)
      if (!fs.existsSync(scriptPath)) {
        return {
          checker: 'package', ok: false, severity: 'error',
          summary: `模板包自检适配器不存在：${scriptPath}`,
          counts: { error: 1, warn: 0, info: 0 },
          findings: [{
            severity: 'error', category: '执行', code: 'CHECKER-MISSING',
            file: scriptPath, line: 0, snippet: '',
            message: '模板包自检适配器不存在',
            suggestion: '检查 cordis.yml 的 checker-package.adapter 配置',
          }],
          artifacts: [], meta: {},
        }
      }

      const r = await ctx.runner.run('package', scriptPath, [], { cwd: root })
      r.meta = { ...(r.meta || {}), packageRoot: path.relative(root, pkgRoot) }
      return r
    }

    ctx.checkers.register({
      id: 'package',
      name: '通用模板包自检（引用完整性/表格/编码/防回归）',
      run,
    })
    ctx.logger.info('checker-package: package=%s adapter=%s',
      path.relative(root, pkgRoot) || pkgRoot, script)
  },
}

export default CheckerPackage
