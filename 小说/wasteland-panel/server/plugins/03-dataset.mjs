/**
 * 插件 03 · dataset —— bible 解析器调度与数据层新鲜度
 *
 * 数据层是「解析现有文件 + 生成独立 JSON」的单向产物：
 *   bible/*.md  →  bible_parser.py  →  engine/data/dataset.json
 *
 * 本插件负责判断是否需要重解析（比对源文件 mtime），并提供
 * 手动触发接口。注意解析用 spawnSync 包在 try/catch 里——
 * 沙箱下可能被拦，不能让它掀翻整个启动流程。
 *
 * 依赖：config
 * 提供：ctx.dataset = { ensure, reparse, info }
 */

import fs from 'node:fs'
import { spawnSync } from 'node:child_process'

export const Dataset = {
  name: 'dataset',
  inject: ['config'],
  apply(ctx) {
    const cfg = ctx.config

    function runParser(reason) {
      ctx.logger.info('dataset: %s，正在解析 bible …', reason)
      try {
        const r = spawnSync(cfg.python, [cfg.parser], {
          encoding: 'utf8',
          cwd: cfg.engine,
          timeout: 60_000,
        })
        const out = (r.stdout || '') + (r.stderr || '')
        const m = out.match(/ok=(\d+)\s+degraded=(\d+)\s+failed=(\d+)/)
        if (m) {
          ctx.logger.info('dataset: 解析完成 ok=%s degraded=%s failed=%s', m[1], m[2], m[3])
          return { ok: true, ok_: +m[1], degraded: +m[2], failed: +m[3] }
        }
        ctx.logger.warn('dataset: 解析器输出无法解析，末尾：\n%s',
          out.split('\n').slice(-6).join('\n'))
        return { ok: false, error: '解析器输出无法解析' }
      } catch (e) {
        // 不致命：引擎启动时会报真实错误
        ctx.logger.warn('dataset: 解析器无法执行（%s），将由引擎启动时报错', e.message)
        return { ok: false, error: e.message }
      }
    }

    function info() {
      let exists = false
      let size = 0
      let mtime = 0
      try {
        const st = fs.statSync(cfg.data)
        exists = true; size = st.size; mtime = st.mtimeMs
      } catch { /* 尚未生成 */ }

      let srcNewest = 0
      let srcMissing = []
      for (const rel of cfg.bibleSources) {
        try { srcNewest = Math.max(srcNewest, fs.statSync(rel).mtimeMs) }
        catch { srcMissing.push(path_basename(rel)) }
      }
      return { exists, size, mtime, srcNewest, stale: exists ? mtime < srcNewest : true, srcMissing }
    }

    function ensure() {
      const i = info()
      if (!i.exists) return runParser('数据层缺失')
      if (i.stale) return runParser('源文件已更新')
      ctx.logger.info('dataset: 数据层已是最新（%d KB）', Math.round(i.size / 1024))
      return { ok: true, skipped: true }
    }

    function reparse() {
      return runParser('手动触发')
    }

    ctx.provide('dataset', { ensure, reparse, info })

    // effect：插件启动即保证数据层可用。
    // 注意 ctx.effect 的执行器**只能返回 disposer 函数或 undefined**，
    // 返回普通对象会抛 "Invalid effect"（cordis lib/index.js:845）。
    ctx.effect(() => {
      ensure()
      if (process.argv.includes('--reparse')) {
        ctx.logger.info('dataset: 收到 --reparse，强制重解析')
        reparse()
      }
      // 无需清理：解析器是同步子进程，函数返回即已结束
    })

    ctx.on('dataset/reparse', reparse)
  },
}

function path_basename(p) {
  const parts = String(p).split(/[\\/]/)
  return parts[parts.length - 1]
}

export default Dataset
