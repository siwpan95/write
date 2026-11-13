/**
 * 插件 13 · pkm —— PKM 索引与检索服务
 *
 * 全仓**知识连接层**的服务提供者：把 1161 个各自为政的 Markdown 文件
 * 变成可检索、可导航、可复用的知识网络。
 *
 * 为什么在仓内自建，而不是直接用 Obsidian / SiYuan / Logseq？
 * ---------------------------------------------------------------
 * 1. **零迁移**：本仓 1161 个 md 一个字节不动（遵守《工作区规范》§五「正文零改动」）。
 *    Obsidian / 思源 / Logseq 都要求「先搬进它的库」，本仓不做这个动作。
 * 2. **零三方依赖**：Python 内核只用标准库，换机即跑（与本仓 49 个 .py 同源纪律）。
 * 3. **中文可检索**：自建二元组索引，绕开 Obsidian 原生搜索对中文分词不友好的问题。
 * 4. **可复跑、可校验**：索引可重建、结果确定，能进闸门做机械门禁。
 *
 * 架构与既有检查器完全同构：**Cordis 做壳（何时跑、跑哪些），Python 做里（怎么算）**。
 *
 * 提供：ctx.pkm = { build(), search(q, opts), links(path), graph(), doctor() }
 *
 * 产物纪律（与「审校报告不入库」同源）：
 *   · `PKM/index.json`  派生缓存 —— 可重建，**不入库**（避免 diff 噪音）
 *   · `PKM/graph.json`  知识图谱 —— 人工积累的价值，**入库**
 *   · `PKM/MOC-*.md`    内容地图 —— 人读导航，**入库**
 */
import { spawn } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'

const PKM_CLI = './tools/pkm/pkm_cli.py'

export const Pkm = {
  name: 'pkm',
  inject: ['config', 'runner'],

  apply(ctx, config = {}) {
    const { root } = ctx.config
    const script = config.script || PKM_CLI

    /**
     * 调 Python 内核，统一走 runner 的协议约定：
     * stdout 一个 JSON 对象，诊断走 stderr，永不抛异常。
     */
    function call(args = [], { timeout = 600000 } = {}) {
      return new Promise((resolve) => {
        const scriptPath = path.resolve(root, script)
        if (!fs.existsSync(scriptPath)) {
          resolve({
            ok: false,
            error: `PKM 内核不存在：${script}`,
            stdout: '', stderr: '', exitCode: 2,
          })
          return
        }
        const child = spawn(ctx.config.python, [scriptPath, ...args], {
          cwd: root,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        })
        let stdout = ''
        let stderr = ''
        const timer = setTimeout(() => {
          try { child.kill() } catch { /* 已退出 */ }
          resolve({
            ok: false, error: `PKM 内核超时（${timeout}ms）`,
            stdout, stderr, exitCode: 2,
          })
        }, timeout)
        child.stdout.on('data', (d) => { stdout += d.toString('utf-8') })
        child.stderr.on('data', (d) => { stderr += d.toString('utf-8') })
        child.on('error', (e) => {
          clearTimeout(timer)
          resolve({
            ok: false, error: `PKM 内核无法启动：${e.message}`,
            stdout, stderr, exitCode: 2,
          })
        })
        child.on('close', (code) => {
          clearTimeout(timer)
          // 内核约定：stdout 末尾是 JSON 汇总；其余是日志
          let parsed = null
          const start = stdout.indexOf('{')
          const end = stdout.lastIndexOf('}')
          if (start >= 0 && end > start) {
            try { parsed = JSON.parse(stdout.slice(start, end + 1)) } catch { /* 非 JSON */ }
          }
          resolve({
            ok: code === 0,
            data: parsed,
            stdout,
            stderr,
            exitCode: code,
          })
        })
      })
    }

    /** 重建索引 + 图谱 + MOC */
    async function build() {
      return call(['build', '--root', root])
    }

    /** 全文检索；返回 {ok, results[], stderr} */
    async function search(query, { project = '', docType = '', limit = 20 } = {}) {
      const args = ['search', query, '--root', root, '--limit', String(limit)]
      if (project) args.push('--project', project)
      if (docType) args.push('--type', docType)
      const r = await call(args)
      // 内核输出 JSON Lines（每行一个结果对象）—— 稳定解析，不猜列宽
      const results = []
      for (const line of (r.stdout || '').split('\n')) {
        const s = line.trim()
        if (!s.startsWith('{')) continue
        try { results.push(JSON.parse(s)) } catch { /* 非结果行 */ }
      }
      return { ...r, results }
    }

    /** 查文档的出链 / 入链 */
    async function links(target) {
      const r = await call(['links', target, '--root', root])
      return { ...r, text: r.stdout }
    }

    /** 图谱统计 */
    async function graph() {
      const r = await call(['graph', '--root', root])
      return { ...r, data: r.data }
    }

    /** 环境自检 */
    async function doctor() {
      return call(['doctor', '--root', root])
    }

    ctx.provide('pkm', { build, search, links, graph, doctor, call })
    ctx.logger.info('pkm: 内核 %s（Python 零三方依赖）', script)
  },
}

export default Pkm
