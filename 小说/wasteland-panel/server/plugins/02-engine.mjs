/**
 * 插件 02 · engine —— Python 引擎子进程 + JSON-RPC 转发
 *
 * 把 rpc_server.py 拉成一个 stdio JSON-RPC 子进程，对外提供
 * `ctx.engine.call(method, params)`。
 *
 * 依赖：config
 * 提供：ctx.engine = { call, ready, restart, stats }
 *
 * 生命周期要点（借 Cordis 的 effect 语义）：
 *   子进程句柄是「注册即所得」的资源，插件卸载时必须回收，
 *   否则热重载会留下孤儿 python 进程。disposer 放在 ctx.effect 里。
 */

import { spawn } from 'node:child_process'

const RPC_TIMEOUT = 30_000

export const Engine = {
  name: 'engine',
  inject: ['config'],
  apply(ctx) {
    const cfg = ctx.config

    let child = null
    let ready = false
    let seq = 0
    let callCount = 0
    let failCount = 0
    const pending = new Map()

    // ---- 启动子进程 ---------------------------------------------------
    function start() {
      if (child) return
      ctx.logger.info('engine: 启动子进程 %s', cfg.python)

      child = spawn(cfg.python, [cfg.rpcScript], {
        cwd: cfg.engine,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
      })

      let buf = ''
      child.stdout.setEncoding('utf8')
      child.stdout.on('data', (chunk) => {
        buf += chunk
        let idx
        while ((idx = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, idx).trim()
          buf = buf.slice(idx + 1)
          if (!line) continue
          let msg
          try { msg = JSON.parse(line) } catch { continue }
          if (msg.id != null && pending.has(msg.id)) {
            const slot = pending.get(msg.id)
            pending.delete(msg.id)
            slot.resolve(msg)
          }
        }
      })

      child.stderr.setEncoding('utf8')
      child.stderr.on('data', (d) => {
        for (const line of String(d).split('\n')) {
          if (line.trim()) ctx.logger.info('[engine] %s', line)
        }
      })

      child.on('exit', (code) => {
        ctx.logger.warn('engine: 子进程退出 code=%s', code)
        child = null
        ready = false
        for (const { reject } of pending.values()) reject(new Error('引擎进程已退出'))
        pending.clear()
      })

      child.on('error', (e) => {
        ctx.logger.error('engine: 启动失败 %s', e.message)
        child = null
        ready = false
      })

      // 就绪探测：selfcheck 是一次最轻的调用
      call('selfcheck', {})
        .then(() => { ready = true; ctx.logger.info('engine: 就绪') })
        .catch((e) => ctx.logger.error('engine: 就绪探测失败 %s', e.message))
    }

    // ---- JSON-RPC 调用 ------------------------------------------------
    function call(method, params = {}) {
      return new Promise((resolve, reject) => {
        if (!child) start()
        if (!child) return reject(new Error('引擎未启动'))

        const id = ++seq
        const timer = setTimeout(() => {
          if (pending.has(id)) {
            pending.delete(id)
            reject(new Error(`RPC 超时: ${method}`))
          }
        }, RPC_TIMEOUT)

        pending.set(id, {
          resolve: (v) => { clearTimeout(timer); resolve(v) },
          reject: (e) => { clearTimeout(timer); reject(e) },
        })

        try {
          callCount++
          child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n')
        } catch (e) {
          clearTimeout(timer)
          pending.delete(id)
          failCount++
          reject(e)
        }
      })
    }

    function restart() {
      ctx.logger.info('engine: 手动重启')
      try { if (child) child.kill() } catch { /* 已退出 */ }
      child = null
      ready = false
      pending.clear()
      start()
    }

    ctx.provide('engine', {
      call,
      restart,
      get ready() { return ready },
      get stats() { return { callCount, failCount, alive: !!child, ready } },
    })

    // ctx.on 是 Cordis 的可逆注册：插件卸载时监听器自动摘除
    ctx.on('engine/restart', restart)

    // effect disposer：插件被卸载/热重载时回收子进程，避免孤儿进程
    ctx.effect(() => {
      start()
      return () => {
        ctx.logger.info('engine: 插件卸载，回收子进程')
        try { if (child) child.kill() } catch { /* 已退出 */ }
        child = null
        ready = false
        pending.clear()
      }
    })
  },
}

export default Engine
