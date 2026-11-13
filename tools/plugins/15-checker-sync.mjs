/**
 * 插件 15 · checker-sync —— 三端同步状态检查
 *
 * 「提交了」不等于「推送了」，也不等于「两端都推了」。
 * GitHub 直连在部分网络下被阻断，会静默造成单端落后 —— 本检查器把它显性化。
 */
export const CheckerSync = {
  name: 'checker-sync',
  inject: ['config', 'runner', 'checkers'],

  apply(ctx, config = {}) {
    const adapter = config.adapter || './tools/checkers/sync_check.py'

    async function run(projectIds = []) {
      // 同步状态是**仓级**维度，与项目无关 —— projectIds 一律忽略
      return ctx.runner.run('sync', adapter, [], { cwd: ctx.config.root })
    }

    ctx.checkers.register({ id: 'sync', name: '三端同步状态（Gitee/GitHub）', run })
  },
}

export default CheckerSync
