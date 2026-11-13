/**
 * 插件 02 · registry —— 项目登记表
 *
 * 仓内各作品/项目的**统一入口**：把「这个项目有哪些可审范围、
 * 用什么口径」集中登记一处，避免每个检查器各自去猜目录结构。
 *
 * 口径文件（项目级 JSON）由项目自己维护，检查器只消费。
 * 本插件只做三件事：解析清单、校验可达性、按 id 取项目。
 *
 * 提供：ctx.projects = { list(), get(id), all() }
 */
import path from 'node:path'
import fs from 'node:fs'

export const Registry = {
  name: 'projects',
  inject: ['config'],

  apply(ctx, config = {}) {
    const { root } = ctx.config
    const specs = config.projects || []
    const projects = []

    for (const spec of specs) {
      const projRoot = path.resolve(root, spec.root || '.')
      const item = {
        id: spec.id,
        name: spec.name || spec.id,
        root: projRoot,
        text: spec.text ? path.resolve(root, spec.text) : null,
        configPath: spec.config ? path.resolve(root, spec.config) : null,
        config: null,
        available: false,
        missing: [],
      }

      // 可达性校验：**缺文件要显性上报**，不能静默跳过
      if (!fs.existsSync(projRoot)) {
        item.missing.push(`项目根不存在：${spec.root}`)
      }
      if (item.text && !fs.existsSync(item.text)) {
        item.missing.push(`正文目录不存在：${spec.text}`)
      }
      if (item.configPath) {
        if (!fs.existsSync(item.configPath)) {
          item.missing.push(`口径文件不存在：${spec.config}`)
        } else {
          try {
            item.config = JSON.parse(
              fs.readFileSync(item.configPath, 'utf-8').replace(/^﻿/, ''))
          } catch (e) {
            item.missing.push(`口径文件解析失败：${e.message}`)
          }
        }
      }
      item.available = item.missing.length === 0
      projects.push(item)
    }

    const byId = new Map(projects.map((p) => [p.id, p]))

    const registry = {
      list: () => projects.map((p) => ({ ...p })),
      get: (id) => byId.get(id) || null,
      all: () => projects.filter((p) => p.available),
      /** 口径 JSON 路径转绝对路径（检查器要用 --config 传） */
      configArg: (id) => {
        const p = byId.get(id)
        return p && p.configPath ? p.configPath : null
      },
    }

    ctx.provide('projects', registry)

    const bad = projects.filter((p) => !p.available)
    ctx.logger.info(
      'projects: %d 个项目（可用 %d）%s',
      projects.length, projects.length - bad.length,
      bad.length ? `｜不可用：${bad.map((p) => p.id).join(', ')}` : '',
    )
    for (const p of bad) {
      ctx.logger.warn('项目 %s 不可用：%s', p.id, p.missing.join('；'))
    }
  },
}

export default Registry
