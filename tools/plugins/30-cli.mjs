/**
 * 插件 30 · cli —— 统一命令行入口
 *
 * 全仓工具链的**唯一入口**：
 *   node tools/cli.mjs <命令> [参数]
 *
 * 命令：
 *   check [项目id...]     跑全部检查器（默认）
 *   check <检查器id>      只跑某个检查器（doc-review / package / consistency）
 *   list                  列出插件、项目、检查器
 *   doctor                环境自检（解释器、插件、路径可达性）
 *   pkm build             重建 PKM 索引 + 图谱 + MOC
 *   pkm search <关键词>   全文检索（中文二元组切分）
 *   pkm links <文档路径>  查文档的出链 / 入链
 *   pkm graph             图谱统计
 *   pkm doctor            PKM 环境自检
 *
 * 退出码：0 无 ERROR ／ 1 有 ERROR ／ 2 参数或环境故障
 */
import path from 'node:path'
import fs from 'node:fs'

export const Cli = {
  name: 'cli',
  inject: ['config', 'projects', 'runner', 'report', 'checkers', 'pkm'],

  apply(ctx, config = {}) {
    const { root } = ctx.config

    /** 已注册的检查器（由各检查器插件 push 进 ctx.checkers） */
    function collectCheckers() {
      return ctx.checkers.list()
    }

    async function main(argv = process.argv.slice(2)) {
      const cmd = argv[0] || config.default || 'check'
      const rest = argv.slice(1)

      if (cmd === 'list') {
        ctx.logger.info('插件：%s', Object.keys(ctx).filter(
          (k) => k !== 'root' && k !== 'fiber').join(', '))
        ctx.logger.info('项目：%s', ctx.projects.list().map(
          (p) => `${p.id}(${p.available ? '可用' : '不可用'})`).join(', '))
        ctx.logger.info('检查器：\n  %s', collectCheckers().map(
          (c) => `${c.id} —— ${c.name}`).join('\n  '))
        return 0
      }

      if (cmd === 'doctor') {
        return doctor()
      }

      // ---- PKM 子命令族：pkm build / search / links / graph / doctor ----
      if (cmd === 'pkm') {
        return await pkmCommand(rest)
      }

      if (cmd !== 'check') {
        ctx.logger.error('未知命令：%s（可用：check / list / doctor / pkm）', cmd)
        return 2
      }

      const checkers = collectCheckers()
      if (!checkers.length) {
        ctx.logger.error('没有可用检查器')
        return 2
      }

      // 参数：先看是不是检查器 id，否则当项目 id
      const wanted = rest.filter((a) => !a.startsWith('-'))
      const byId = new Map(checkers.map((c) => [c.id, c]))
      const isCheckerArg = wanted.length > 0 && byId.has(wanted[0])
      const selected = isCheckerArg ? [byId.get(wanted[0])] : checkers
      const projectIds = isCheckerArg ? [] : wanted

      const results = []
      for (const c of selected) {
        ctx.logger.info('── 运行检查器 %s ──', c.id)
        const r = await c.run(projectIds)
        results.push(r)
      }

      const { mdPath, jsonPath, counts } = ctx.report.write(results)
      ctx.logger.info('汇总报告：%s', mdPath)
      ctx.logger.info('机读 JSON：%s', jsonPath)
      ctx.logger.info('合计：错误 %d ／ 警告 %d ／ 提示 %d',
        counts.error, counts.warn, counts.info)

      if (counts.error) {
        ctx.logger.error('存在 %d 条 ERROR', counts.error)
        return 1
      }
      return 0
    }

    function doctor() {
      const cfg = ctx.config
      let bad = 0
      ctx.logger.info('仓根：%s', cfg.root)
      ctx.logger.info('Python：%s', cfg.python)
      try {
        const ok = fs.existsSync(cfg.python) || !path.isAbsolute(cfg.python)
        ctx.logger.info('  解释器可达：%s', ok ? '是' : '否')
        if (!ok) bad++
      } catch { bad++ }

      for (const p of ctx.projects.list()) {
        ctx.logger.info('项目 %s（%s）：%s', p.id, p.name,
          p.available ? '可用' : `不可用 —— ${p.missing.join('；')}`)
        if (!p.available) bad++
      }
      for (const c of collectCheckers()) {
        ctx.logger.info('检查器 %s：已注册', c.id)
      }
      ctx.logger.info(bad ? '环境自检：%d 项异常' : '环境自检：全部正常', bad)
      return bad ? 1 : 0
    }

    /**
     * PKM 子命令族 —— 知识连接层的对外入口。
     *
     *   pkm build          重建索引 + 图谱 + MOC
     *   pkm search <词>    全文检索（中文二元组切分）
     *   pkm links <路径>   查出链 / 入链
     *   pkm graph          图谱统计
     *   pkm doctor         PKM 环境自检
     */
    async function pkmCommand(args = []) {
      if (!ctx.pkm) {
        ctx.logger.error('PKM 服务未就绪（检查 tools/cordis.yml 的 pkm 条目）')
        return 2
      }
      const sub = args[0] || 'build'
      const rest = args.slice(1)

      if (sub === 'build') {
        const r = await ctx.pkm.build()
        if (!r.ok) {
          ctx.logger.error('PKM build 失败：%s', r.error || r.stderr || `exit=${r.exitCode}`)
          return r.exitCode || 2
        }
        if (r.stderr) ctx.logger.info('%s', r.stderr.trim())
        return 0
      }

      if (sub === 'search') {
        const query = rest.filter((a) => !a.startsWith('-')).join(' ')
        if (!query) {
          ctx.logger.error('用法：node tools/host.mjs pkm search <关键词>')
          return 2
        }
        const r = await ctx.pkm.search(query, { limit: 20 })
        for (const hit of r.results) {
          // 注意：cordis logger 用 util.format，**不支持** printf 的 %8.3f
          ctx.logger.info('%s  %s', hit.score.toFixed(3).padStart(8), hit.path)
          ctx.logger.info('         %s  [%s/%s]', hit.title, hit.project, hit.doc_type)
        }
        ctx.logger.info('命中 %d 条（查询：%s）', r.results.length, query)
        return r.results.length ? 0 : 1
      }

      if (sub === 'links') {
        const target = rest.filter((a) => !a.startsWith('-')).join(' ')
        if (!target) {
          ctx.logger.error('用法：node tools/host.mjs pkm links <文档路径>')
          return 2
        }
        const r = await ctx.pkm.links(target)
        if (!r.ok) {
          ctx.logger.error('查询失败：%s', r.error || r.stderr.trim())
          return r.exitCode || 1
        }
        process.stdout.write(r.text)
        return 0
      }

      if (sub === 'graph') {
        const r = await ctx.pkm.graph()
        if (!r.ok) {
          ctx.logger.error('读取图谱失败：%s', r.error || r.stderr.trim())
          return r.exitCode || 2
        }
        process.stdout.write(JSON.stringify(r.data, null, 1) + '\n')
        return 0
      }

      if (sub === 'doctor') {
        const r = await ctx.pkm.doctor()
        process.stdout.write(r.stdout || '')
        return r.exitCode === 0 ? 0 : 1
      }

      ctx.logger.error('未知 pkm 子命令：%s（可用：build / search / links / graph / doctor）', sub)
      return 2
    }

    ctx.provide('cli', { main, collectCheckers })
    ctx.logger.info('cli: 命令 %s / list / doctor', config.default || 'check')
  },
}

export default Cli
