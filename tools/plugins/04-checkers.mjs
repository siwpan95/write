/**
 * 插件 04 · checkers —— 检查器登记表
 *
 * 各检查器插件把自己**注册**到本服务，CLI 从这里取。
 *
 * 为什么不直接遍历 ctx 的服务表：cordis 的 Context 是 Proxy，
 * `Object.keys(ctx)` 只列得出内置服务（events/logger/registry…），
 * 插件 `provide()` 上去的服务**不可枚举**（实测确认）。
 * 而 `ctx.registry.keys()` 是 core 的**别名/注入**注册表，也不是服务表。
 *
 * 所以显式做一张表：插件声明 `inject: ['checkers']` → push 自身 → CLI 读表。
 * 这样「有哪些检查器」仍是**声明式**的：加一个检查器插件 = 改 cordis.yml +
 * 在新插件里 push 一行，CLI 与报告都不用动。
 *
 * 提供：ctx.checkers = { register(c), list(), get(id) }
 */
export const Checkers = {
  name: 'checkers',
  inject: [],

  apply(ctx) {
    const table = new Map()

    const api = {
      /** 检查器插件在 apply 里调用，把自己挂进来 */
      register(checker) {
        if (!checker || !checker.id || typeof checker.run !== 'function') {
          throw new TypeError('检查器必须含 id 与 run()')
        }
        if (table.has(checker.id)) {
          throw new Error(`检查器 id 重复：${checker.id}`)
        }
        table.set(checker.id, checker)
        ctx.logger.info('checkers: 注册 %s —— %s', checker.id, checker.name)
      },
      list: () => [...table.values()],
      get: (id) => table.get(id) || null,
      size: () => table.size,
    }

    ctx.provide('checkers', api)
  },
}

export default Checkers
