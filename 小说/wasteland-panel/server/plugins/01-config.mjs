/**
 * 插件 01 · config —— 基础配置服务
 *
 * 全应用唯一的路径/端口真理源。所有下游插件通过 `inject: ['config']`
 * 声明依赖，拿到的永远是同一份对象；插件挂载顺序由依赖图决定，
 * 不需要人工编排。
 *
 * 提供：ctx.config = { root, engine, web, data, rpcScript, parser,
 *                      python, port, host, bibleSources }
 */

import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')   // wasteland-panel/
const BIBLE_ROOT = process.env.BIBLE_ROOT
  ? path.resolve(process.env.BIBLE_ROOT)
  : path.resolve(ROOT, '..')                 // 小说根目录（wasteland-panel 的上级）

/**
 * 定位 Python 解释器。
 *
 * 刻意**不做 spawnSync 版本探测**：受限沙箱下 spawnSync 会返回 EBUSY
 * （文件被占用），误判成「找不到解释器」会让整个服务起不来。
 * 改为文件存在性检查，真实可用性交给引擎插件 spawn 时判定。
 *
 * 解析顺序（先命中先用，全部失败才退回 PATH）：
 *   1. PYTHON 环境变量
 *   2. 项目内虚拟环境 <root>/.venv
 *   3. 本机 .workbuddy 托管虚拟环境 envs/<name>（战斗沙盘的依赖装在里面）
 *   4. 本机 .workbuddy 托管裸解释器 versions/<ver>
 *   5. PATH 上的命令名（win32 → python，其余 → python3）
 *
 * 3 排在 4 **之前**，是刻意且必要的：战斗沙盘依赖 allin-engine（D20 规则内核），
 * 它装在独立 venv 里，不污染全局解释器。裸解释器里没有这个包，
 * 若被优先选中，沙盘会在 import 阶段静默失效——服务照样起，
 * 一点"战斗"就炸 ImportError，属于最难排查的那类问题。
 *
 * 刻意**不写死具体版本号与盘符**：版本升级、换机、换用户都会让硬编码
 * 路径失效，而这类失效是静默的（服务能起，reparse 时才炸）。
 */
function expandPythonCandidates() {
  const cands = []

  if (process.env.PYTHON) cands.push(process.env.PYTHON)

  // 项目内虚拟环境（跨机部署时优先用项目自带的）
  cands.push(
    path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(ROOT, '.venv', 'bin', 'python'),
  )

  // 本机 WorkBuddy 托管虚拟环境：<home>/.workbuddy/binaries/python/envs/<name>/
  const home = process.env.USERPROFILE || process.env.HOME || ''
  if (home) {
    const envsBase = path.join(home, '.workbuddy', 'binaries', 'python', 'envs')
    try {
      const names = fs.readdirSync(envsBase, { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => d.name)
      // 项目同名 venv 优先，其余按名字排序（保证多次解析结果一致）
      names.sort((a, b) => {
        if (a === 'wasteland-panel') return -1
        if (b === 'wasteland-panel') return 1
        return a.localeCompare(b)
      })
      for (const n of names) {
        cands.push(
          path.join(envsBase, n, 'Scripts', 'python.exe'),
          path.join(envsBase, n, 'bin', 'python'),
        )
      }
    } catch { /* 目录不存在则跳过 */ }
  }

  // 本机 WorkBuddy 托管解释器：<home>/.workbuddy/binaries/python/versions/<ver>/python.exe
  if (home) {
    const base = path.join(home, '.workbuddy', 'binaries', 'python', 'versions')
    try {
      const vers = fs
        .readdirSync(base, { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .map((d) => d.name)
      // 版本号排序：'3.13.12' → [3,13,12]，'3.9' → [3,9]
      const key = (v) => v.split('.').map((n) => parseInt(n, 10) || 0)
      vers.sort((a, b) => {
        const ka = key(a)
        const kb = key(b)
        for (let i = 0; i < Math.max(ka.length, kb.length); i++) {
          const d = (ka[i] || 0) - (kb[i] || 0)
          if (d) return d
        }
        return 0
      })
      for (const v of vers) {
        cands.push(
          path.join(base, v, 'python.exe'),
          path.join(base, v, 'Scripts', 'python.exe'),
        )
      }
    } catch { /* 目录不存在则跳过 */ }
  }

  return cands
}

export function findPython() {
  for (const c of expandPythonCandidates()) {
    try {
      if (fs.existsSync(c)) return c
    } catch { /* 试下一个 */ }
  }
  // 退回 PATH 上的命令（可能是 python / python3 / WindowsApps 别名）
  return process.platform === 'win32' ? 'python' : 'python3'
}

/**
 * bible 源文件清单——数据层新鲜度比对这些文件的 mtime
 *
 * 相对小说根目录（本文件位于 <小说根>/wasteland-panel/server/plugins/），
 * 不写死盘符：换盘、换机、整仓搬到别的目录下都仍然有效。
 * 允许用环境变量 BIBLE_ROOT 覆盖，默认取 wasteland-panel 的上级目录。
 *
 * 注意：角色卡是**目录**，单列一个 cardDir 交给引擎插件做目录级 mtime
 * 扫描（取目录内 .md 里最新的那个）——把它塞进文件列表会让新鲜度
 * 判定在角色卡变动时完全不触发，这是接入初期真实踩过的坑。
 */
const BIBLE_SOURCES = [
  path.join(BIBLE_ROOT, 'bible', 'world-bible.md'),
  path.join(BIBLE_ROOT, 'bible', 'plot-board.md'),
  path.join(BIBLE_ROOT, 'bible', 'timeline.md'),
  path.join(BIBLE_ROOT, '一致性核查', '世界观设定标尺.md'),
  path.join(BIBLE_ROOT, '设定与参考', '长弧规划.md'),
  path.join(BIBLE_ROOT, '设定与参考', '扩写规范-统一执行手册.md'),
]

const CARD_DIR = path.join(BIBLE_ROOT, 'bible', 'characters')

/** 取目录下最新 .md 的 mtime（毫秒）；目录不存在返回 0 */
function latestMtime(dir) {
  try {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith('.md'))
    let newest = 0
    for (const f of files) {
      const t = fs.statSync(path.join(dir, f)).mtimeMs
      if (t > newest) newest = t
    }
    return newest
  } catch {
    return 0
  }
}

export const Config = {
  name: 'config',
  apply(ctx) {
    const port = Number(process.env.PORT || 8777)
    const host = process.env.HOST || '127.0.0.1'
    const python = findPython()

    const cfg = {
      root: ROOT,
      engine: path.join(ROOT, 'engine'),
      web: path.join(ROOT, 'web'),
      data: path.join(ROOT, 'engine', 'data', 'dataset.json'),
      rpcScript: path.join(ROOT, 'engine', 'rpc_server.py'),
      parser: path.join(ROOT, 'engine', 'bible_parser.py'),
      python,
      port,
      host,
      bibleSources: BIBLE_SOURCES,
      cardDir: CARD_DIR,
      cardMtime: latestMtime(CARD_DIR),
    }

    ctx.provide('config', cfg)
    ctx.logger.info(
      'config: python=%s port=%d web=%s sources=%d cards=%s',
      python, port, path.basename(cfg.web),
      BIBLE_SOURCES.length, cfg.cardMtime ? 'ok' : 'missing',
    )
  },
}

export default Config
