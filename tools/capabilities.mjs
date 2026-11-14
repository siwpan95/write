#!/usr/bin/env node
/**
 * capabilities.mjs —— 能力清单的唯一读取口（零依赖）
 *
 * 依据 tools/README.md:44：「cordis.yml 是应用能力的唯一真理源」。
 * 历史问题：host.mjs --list 硬编码 9 个插件名、30-cli.mjs list 用
 * Object.keys(ctx) 取能力（输出为空），而 cordis.yml 实际有 12 个 - id。
 * 本模块让两处都从同一份 cordis.yml 解析，消除多套能力清单。
 *
 * 不引入 YAML 解析依赖：插件声明是行首 `- id: xxx` 的扁平结构，
 * 用正则读即可（与仓内「Python 内核零三方依赖」同源纪律）。
 */
import fs from 'node:fs'
import path from 'node:path'

/** 从 tools/cordis.yml 读取全部插件 id（保持声明顺序） */
export function readPluginIds(root) {
  const file = path.join(root, 'tools', 'cordis.yml')
  const text = fs.readFileSync(file, 'utf8')
  const ids = []
  for (const line of text.split(/\r?\n/)) {
    // 只认行首无缩进的 `- id:`：cordis.yml 的 projects 段还有嵌套的
    // `- id: wushuang/huaxi/kz`（项目登记），那些不是插件，不能计入能力清单。
    const m = /^- id:\s*([^\s#]+)/.exec(line)
    if (m) ids.push(m[1])
  }
  return ids
}

/** tools/plugins/ 下实际存在的 .mjs 文件（用于一致性断言） */
export function readPluginFiles(root) {
  const dir = path.join(root, 'tools', 'plugins')
  return fs.readdirSync(dir).filter((f) => f.endsWith('.mjs')).sort()
}

/** 一致性校验：声明 id 数 == 插件文件数；返回问题列表（空数组＝通过） */
export function checkCapabilities(root) {
  const ids = readPluginIds(root)
  const files = readPluginFiles(root)
  const issues = []
  const dup = ids.filter((id, i) => ids.indexOf(id) !== i)
  if (dup.length) issues.push(`cordis.yml 存在重复 id: ${[...new Set(dup)].join(', ')}`)
  if (ids.length !== files.length) {
    issues.push(`插件声明 ${ids.length} 个，但 plugins/*.mjs 有 ${files.length} 个`)
  }
  return { ids, files, issues }
}
