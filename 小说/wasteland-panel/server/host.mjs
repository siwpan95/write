#!/usr/bin/env node
/**
 * host.mjs — Cordis 装配壳
 *
 * 这个文件刻意保持极薄：它只负责「建根上下文 + 装 loader + 挂 cordis.yml」，
 * 所有实际能力都在 server/plugins/ 下，以插件形式由 cordis.yml 声明。
 *
 * 想加新能力？改 cordis.yml 加一条，或新建一个 .mjs 丢进 plugins/，
 * 都不需要动这个文件——这就是引入 Cordis 作为润滑层的意义。
 *
 * 用法：
 *   node server/host.mjs            正常启动
 *   node server/host.mjs --reparse  强制重解析 bible 后启动
 *   PORT=8899 node server/host.mjs  换端口
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
// ctx.extend 子作用域（第 211 行），不会污染根上下文；而 Include 的
// 构造器执行 `new URL(config.path, ctx.baseUrl)`，baseUrl 为 undefined
// 时会直接抛 ERR_INVALID_URL。
root.baseUrl = import.meta.url

// 控制台日志（可插拔的 Exporter）
await root.plugin(LoggerConsole, { level: 'info' })

// 插件树加载器
await root.plugin(Loader, { baseUrl: import.meta.url })

// Include 必须**由 loader 加载**，不能裸挂在根上下文：
// 它的构造器读 `ctx.fiber.entry?.parent.tree.enableLogs`，
// 根上下文的 entry 为 undefined，直接 root.plugin(Include) 会抛
// "Cannot read properties of undefined (reading 'enableLogs')"。
// config.path 相对根 baseUrl（即 server/）解析，故为 '../cordis.yml'。
await root.plugin(Include, { path: '../cordis.yml' })
await root.loader.await()

// 优雅退出：先 dispose 插件树（触发各插件 effect 的 disposer），
// 再退进程——顺序反了会留下孤儿 python 子进程。
let closing = false
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, async () => {
    if (closing) return
    closing = true
    console.log('\n[host] 关闭中，正在卸载插件树 …')
    try {
      await root.fiber.dispose()
      console.log('[host] 插件树已卸载，bye')
    } catch (e) {
      console.error('[host] 卸载出错:', e.message)
    }
    setTimeout(() => process.exit(0), 300)
  })
}

process.on('unhandledRejection', (e) => {
  console.error('[host] 未处理的 Promise 拒绝:', e?.message ?? e)
})
