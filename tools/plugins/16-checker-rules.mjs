/**
 * 插件 16 · checker-rules —— 全仓治理规则一致性检查器
 *
 * v2 审计 G-02：把「规则检查规则」接入 `npm run check`，
 * 与 pkm / sync / package / doc-review / consistency 完全同构。
 * 插件声明在 cordis.yml（唯一真理源），能力清单自动包含本检查器。
 */
export const CheckerRules = {
  name: 'checker-rules',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const adapter = config.adapter || './tools/checkers/rules_check.py'

    async function run() {
      // 治理规则是全仓维度，不按项目切分
      return await ctx.runner.run('rules', adapter, [], { cwd: ctx.config.root })
    }

    ctx.checkers.register({
      id: 'rules',
      name: '治理规则一致性（指标/插件/命名/失效登记）',
      run,
    })
  },
}

export default CheckerRules
