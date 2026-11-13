/**
 * 插件 14 · checker-pkm —— PKM 连接层检查器
 *
 * 把「知识网络健康度」纳入既有闸门：`npm run check` 会一并检查，
 * 断链等结构性缺陷会阻断放行（ERROR 0 = 可放行）。
 *
 * 与既有检查器完全同构：Python 内核算，cordis 只管何时跑、怎么汇总。
 */
export const CheckerPkm = {
  name: 'checker-pkm',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const adapter = config.adapter || './tools/checkers/pkm_check.py'

    async function run(projectIds = []) {
      // PKM 是**全仓**维度，不按项目切分 —— projectIds 一律忽略
      const r = await ctx.runner.run('pkm', adapter, [], { cwd: ctx.config.root })
      return r
    }

    ctx.checkers.register({ id: 'pkm', name: 'PKM 连接层体检（断链/孤立/规模）', run })
  },
}

export default CheckerPkm
