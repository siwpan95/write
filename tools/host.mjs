#!/usr/bin/env node
/**
 * host.mjs —— 仓根工具编排层 · 装配壳
 *
 * 这个文件刻意保持极薄：只负责「建根上下文 + 挂 loader + 挂 cordis.yml」，
 * 所有实际能力都在 tools/plugins/ 下，以插件形式由 tools/cordis.yml 声明。
 *
 * 想加新能力？改 tools/cordis.yml 加一条，或新建一个 .mjs 丢进 tools/plugins/，
 * 都不需要动这个文件 —— 这就是引入 Cordis 作为润滑层的意义。
 *
 * 用法：
 *   node tools/host.mjs <命令> [参数]     # 经 CLI 插件执行命令
 *   node tools/host.mjs --list            # 列出插件树
 *
 * 与《小说/wasteland-panel/server/host.mjs》的关系：同一个模式（薄壳 + 插件树），
 * 但插件树独立 —— 那个管单本书的面板工作台，这个管全仓的工具流水线。
 */
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { Context } from 'cordis'
import LoggerConsole from '@cordisjs/plugin-logger-console'
import Loader from '@cordisjs/plugin-loader'
import Include from '@cordisjs/plugin-include'

const HERE = path.dirname(fileURLToPath(import.meta.url))

const root = new Context()

// 根上下文的 baseUrl。必须显式设置：Loader 只把 baseUrl 存进它自己的
// ctx.extend 子作用域，不会污染根上下文；而 Include 的构造器执行
// `new URL(config.path, ctx.baseUrl)`，baseUrl 为 undefined 时会抛 ERR_INVALID_URL。
root.baseUrl = import.meta.url

// 控制台日志（可插拔的 Exporter）
await root.plugin(LoggerConsole, { level: process.env.LOG_LEVEL || 'info' })

// 插件树加载器
await root.plugin(Loader, { baseUrl: import.meta.url })

// Include 必须**由 loader 加载**，不能裸挂在根上下文：
// 它的构造器读 `ctx.fiber.entry?.parent.tree.enableLogs`，
// 根上下文的 entry 为 undefined，直接 root.plugin(Include) 会抛
// "Cannot read properties of undefined (reading 'enableLogs')"。
await root.plugin(Include, { path: './cordis.yml' })
await root.loader.await()

// 优雅退出：先 dispose 插件树（触发各插件 effect 的 disposer），再退进程
let closing = false
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, async () => {
    if (closing) return
    closing = true
    try {
      await root.fiber.dispose()
    } catch (e) {
      console.error('[host] 卸载出错:', e.message)
    }
    process.exit(0)
  })
}

process.on('unhandledRejection', (e) => {
  console.error('[host] 未处理的 Promise 拒绝:', e?.message ?? e)
})

// ---- 执行命令 ----
const argv = process.argv.slice(2)

if (argv[0] === '--list') {
  console.log('插件树（tools/cordis.yml）：')
  console.log('  config · registry · runner · checker-package · checker-doc-review')
  console.log('  checker-consistency · report · cli')
  await root.fiber.dispose()
  process.exit(0)
}

const cli = root.cli
if (!cli) {
  console.error('[host] CLI 插件未就绪（检查 tools/cordis.yml 的 cli 条目）')
  await root.fiber.dispose()
  process.exit(2)
}

let code = 2
try {
  code = await cli.main(argv)
} catch (e) {
  console.error('[host] 命令执行异常:', e?.stack ?? e)
  code = 2
}

await root.fiber.dispose()
process.exit(code)
