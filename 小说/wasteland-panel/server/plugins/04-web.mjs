/**
 * 插件 04 · web —— HTTP 服务 · 静态托管 · API 路由
 *
 * 这是 Cordis 最有价值的地方：原来的 `if (route === 'bootstrap') …`
 * 硬编码分支，改一个路由就要动主干代码；现在换成事件瀑布，
 * 任何插件都能在中间位置插入自己的端点。
 *
 * 事件：
 *   http/request   waterfall —— 依次询问各路由处理器。**约定**
 *     （经实测确认，cordis lib/index.js:326-341）：
 *                                  · 调用 ctx.waterfall('http/request',
 *                                    payload, innerFn)
 *                                  · handler 签名 (payload, next)
 *                                  · payload 原样传给每个 handler
 *                                  · 返回非 undefined 即接管响应
 *                                  · 调用 next() 交给下一个 handler
 *                                  · 全部 next() → 执行 innerFn 兜底
 *   http/ready     emit     —— 服务已 listen
 *
 * 有了 payload 直传，reqCtx 不必再挂到 ctx 上，闭包传参即可。
 *
 * 依赖：config, engine, dataset
 *   （dataset 是为了让 /api/bootstrap 与 /api/health 能回报数据层状态；
 *     Cordis 的 inject 是硬约束——未声明就访问会直接抛
 *     "cannot get property X without inject"，不会给你 undefined，
 *     这正是它比"到处 ctx.xxx ?? null"更可靠的地方。）
 */

import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.md': 'text/markdown; charset=utf-8',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
}

const MAX_BODY = 8 * 1024 * 1024   // 8MB

export const Web = {
  name: 'web',
  inject: ['config', 'engine', 'dataset'],
  apply(ctx) {
    const cfg = ctx.config

    // ---- 响应helper ----------------------------------------------------
    function sendJSON(res, code, obj) {
      if (res.writableEnded) return
      const body = JSON.stringify(obj)
      res.writeHead(code, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': Buffer.byteLength(body),
        'Cache-Control': 'no-store',
      })
      res.end(body)
    }

    function readBody(req) {
      return new Promise((resolve, reject) => {
        let b = ''
        req.on('data', (c) => {
          b += c
          if (b.length > MAX_BODY) {
            reject(new Error('请求体过大（上限 8MB）'))
            req.destroy()
          }
        })
        req.on('end', () => {
          if (!b) return resolve({})
          try { resolve(JSON.parse(b)) } catch { reject(new Error('请求体不是合法 JSON')) }
        })
        req.on('error', reject)
      })
    }

    // ---- 静态托管 ------------------------------------------------------
    function serveStatic(res, urlPath) {
      let rel = urlPath === '/' ? '/index.html' : urlPath
      try { rel = decodeURIComponent(rel.split('?')[0]) } catch { /* 原样 */ }
      const file = path.join(cfg.web, path.normalize(rel).replace(/^([/\\])+/, ''))

      // 目录穿越防护
      if (!file.startsWith(cfg.web)) {
        res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' })
        return res.end('403 Forbidden')
      }
      fs.readFile(file, (err, buf) => {
        if (err) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
          return res.end('404 Not Found: ' + rel)
        }
        res.writeHead(200, {
          'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
          'Cache-Control': 'no-store',
        })
        res.end(buf)
      })
    }

    // ---- HTTP 服务 ------------------------------------------------------
    const server = http.createServer(async (req, res) => {
      const url = req.url || '/'

      try {
        if (url.startsWith('/api/')) {
          const route = url.slice(5).split('?')[0]
          const params = req.method === 'POST' ? await readBody(req) : {}
          const payload = { req, res, route, params, method: req.method }

          // waterfall：innerFn 是兜底（所有 handler 都 next() 时执行）
          const handled = await ctx.waterfall('http/request', payload, () => undefined)
          if (handled === undefined) {
            return sendJSON(res, 404, { ok: false, error: { message: `未知路由 /api/${route}` } })
          }
          return
        }
        return serveStatic(res, url)
      } catch (e) {
        ctx.logger.error('web: 请求处理失败 %s', e.message)
        return sendJSON(res, 500, { ok: false, error: { message: e.message } })
      }
    })

    // ---- 内置路由：/api/<method> 透传 ------------------------------------
    ctx.on('http/request', async (payload, next) => {
      const { req, res, route, params, method } = payload

      if (route === 'bootstrap' && method === 'GET') {
        const [ds, sc, toolbox, research] = await Promise.all([
          ctx.engine.call('dataset.get', {}),
          ctx.engine.call('selfcheck', {}),
          ctx.engine.call('trpg.toolbox', {}),
          ctx.engine.call('research.get', {}),
        ])
        sendJSON(res, 200, {
          ok: true,
          dataset: ds.result ?? ds,
          selfcheck: sc.result ?? sc,
          toolbox: toolbox.result ?? toolbox,
          research: research.result ?? research,
          engine: {
            python: cfg.python,
            port: cfg.port,
            stats: ctx.engine.stats,
          },
          dataset_info: ctx.dataset ? ctx.dataset.info() : null,
        })
        return true   // 已接管
      }

      if (route === 'health' && method === 'GET') {
        sendJSON(res, 200, {
          ok: true,
          engine: ctx.engine.stats,
          dataset: ctx.dataset ? ctx.dataset.info() : null,
          uptime: Math.round(process.uptime()),
        })
        return true
      }

      // 兜底透传：GET 空参 / POST 带参
      if (method === 'POST' || method === 'GET') {
        const msg = await ctx.engine.call(route, params)
        // RPC 错误 = 带 code 的 error 对象；业务结果里的 error 计数字段
        // （如机扫）是 int/普通对象，不能当 RPC 错误
        if (msg.error && typeof msg.error === 'object' && msg.error.code != null) {
          return sendJSON(res, 400, { ok: false, error: msg.error })
        }
        return sendJSON(res, 200, msg.result ?? msg)
      }

      return next()   // 交回瀑布
    })

    // ---- effect：启动与回收 ---------------------------------------------
    ctx.effect(() => {
      server.listen(cfg.port, cfg.host, () => {
        ctx.logger.info('')
        ctx.logger.info('  ╔══════════════════════════════════════════════╗')
        ctx.logger.info('  ║   废土旅法师 · 面板工作台 (Cordis)              ║')
        ctx.logger.info('  ╚══════════════════════════════════════════════╝')
        ctx.logger.info('     → http://%s:%d', cfg.host, cfg.port)
        ctx.logger.info('')
        ctx.emit('http/ready', { port: cfg.port, host: cfg.host })
      })

      server.on('error', (e) => {
        if (e.code === 'EADDRINUSE') {
          ctx.logger.error('端口 %d 已被占用。换端口：set PORT=8899 && npm start', cfg.port)
        } else {
          ctx.logger.error('HTTP 服务错误 %s', e.message)
        }
      })

      return () => {
        server.close(() => ctx.logger.info('web: 已关闭'))
        // 兜底：1.5s 内没关干净就强退，避免端口残留
        setTimeout(() => { try { server.closeAllConnections?.() } catch { /* 忽略 */ } }, 1500)
      }
    })
  },
}

export default Web
