#!/usr/bin/env node
/**
 * cli.mjs — wasteland-panel 单文件零依赖命令行
 *
 * 零第三方依赖，仅用 node:child_process / node:fs / node:path / node:url。
 *
 * 子进程模型（照搬 server/plugins/02-engine.mjs 的 start()/call()）：
 *   每一条 CLI 命令拉起一个**持久**的 rpc_server.py 子进程，
 *   通过 stdin 写一行 JSON 请求、从 stdout 按 "\n" 切分读 JSON 响应。
 *
 * 用法见 `--help`。
 */

import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))

// 本文件位于 wasteland-panel/server/cli.mjs，故向上一层即为项目根。
// （简报里写了 '..','..'，但那适用于 server/plugins 下的文件；
//   这里 cli.mjs 直接在 server/ 下，'..' 即可得到 wasteland-panel/。）
const ROOT = path.resolve(HERE, '..')
const ENGINE = path.join(ROOT, 'engine')
const RPC_SCRIPT = path.join(ROOT, 'engine', 'rpc_server.py')
const PARSER = path.join(ROOT, 'engine', 'bible_parser.py')
const DATA = path.join(ROOT, 'engine', 'data', 'dataset.json')

const RPC_TIMEOUT = 30_000

// --------------------------------------------------------------------------
// Python 解释器选择
//
// 直接复用 01-config.mjs 的 findPython —— cli 与 host 必须解析出同一个
// 解释器，否则「面板能连上但 CLI 报缺依赖」这类问题极难定位。
// 单份实现是刻意的：曾经这里和 01-config 各写一份候选表，
// 结果两边都写死了具体版本号，升级后各自静默失效。
// --------------------------------------------------------------------------
async function findPython() {
  try {
    const mod = await import('./plugins/01-config.mjs')
    if (typeof mod.findPython === 'function') return mod.findPython()
  } catch { /* 回落到本地实现 */ }

  const cands = [process.env.PYTHON].filter(Boolean)
  const home = process.env.USERPROFILE || process.env.HOME || ''
  if (home) {
    const base = path.join(home, '.workbuddy', 'binaries', 'python', 'versions')
    try {
      for (const v of fs.readdirSync(base, { withFileTypes: true })
        .filter((d) => d.isDirectory()).map((d) => d.name)
        .sort((a, b) => {
          const ka = a.split('.').map(Number)
          const kb = b.split('.').map(Number)
          for (let i = 0; i < Math.max(ka.length, kb.length); i++) {
            const d = (ka[i] || 0) - (kb[i] || 0)
            if (d) return d
          }
          return 0
        })) {
        cands.push(
          path.join(base, v, 'python.exe'),
          path.join(base, v, 'Scripts', 'python.exe'),
        )
      }
    } catch { /* 目录不存在 */ }
  }
  for (const c of cands) {
    try { if (fs.existsSync(c)) return c } catch { /* 试下一个 */ }
  }
  return process.platform === 'win32' ? 'python' : 'python3'
}

const PYTHON = await findPython()

// --------------------------------------------------------------------------
// 命令行标志解析：--flag value … → { flag: coercedValue }
//   --flag（无值，或下一个仍以 -- 开头）→ true
// --------------------------------------------------------------------------
function parseFlags(args) {
  const out = {}
  for (let i = 0; i < args.length; i++) {
    const a = args[i]
    if (!a.startsWith('--')) continue
    const key = a.slice(2)
    const nxt = args[i + 1]
    if (nxt === undefined || nxt.startsWith('--')) {
      out[key] = true
    } else {
      out[key] = coerce(nxt)
      i++
    }
  }
  return out
}

// 值强制转换：true/false → bool；数字串 → number；@file → 读文件文本；
// 能 JSON.parse 的 → 解析对象；否则原样字符串。
function coerce(v) {
  if (v === 'true') return true
  if (v === 'false') return false
  if (typeof v === 'string' && v.startsWith('@')) {
    const fp = v.slice(1)
    try {
      return fs.readFileSync(fp, 'utf8')
    } catch (e) {
      throw new Error(`无法读取 @文件 ${fp}: ${e.message}`)
    }
  }
  if (/^-?\d+$/.test(v) || /^-?\d*\.\d+$/.test(v)) {
    const n = Number(v)
    if (!Number.isNaN(n)) return n
  }
  try {
    return JSON.parse(v)
  } catch { /* 非 JSON，保持字符串 */ }
  return v
}

// --------------------------------------------------------------------------
// JSON-RPC 引擎客户端（单持久子进程 + 行缓冲 + 超时）
// --------------------------------------------------------------------------
class EngineClient {
  constructor() {
    this.child = null
    this.seq = 0
    this.pending = new Map()
    this.buf = ''
  }

  _ensure() {
    if (this.child) return
    let child
    try {
      child = spawn(PYTHON, [RPC_SCRIPT], {
        cwd: ENGINE,
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
      })
    } catch (e) {
      throw new Error(`无法启动引擎子进程: ${e.message}（python=${PYTHON}）`)
    }
    this.child = child

    child.stdout.setEncoding('utf8')
    child.stdout.on('data', (chunk) => {
      this.buf += chunk
      let idx
      while ((idx = this.buf.indexOf('\n')) >= 0) {
        const line = this.buf.slice(0, idx).trim()
        this.buf = this.buf.slice(idx + 1)
        if (!line) continue
        let msg
        try { msg = JSON.parse(line) } catch { continue }
        if (msg.id != null && this.pending.has(msg.id)) {
          const slot = this.pending.get(msg.id)
          this.pending.delete(msg.id)
          slot.resolve(msg)
        }
      }
    })

    let errBuf = ''
    child.stderr.setEncoding('utf8')
    child.stderr.on('data', (d) => { errBuf += d })
    this._errBuf = () => errBuf

    child.on('exit', (code) => {
      this.child = null
      for (const { reject } of this.pending.values()) {
        reject(new Error(`引擎进程已退出（code=${code}）`))
      }
      this.pending.clear()
    })
    child.on('error', (e) => {
      this.child = null
      for (const { reject } of this.pending.values()) reject(e)
      this.pending.clear()
    })
  }

  call(method, params = {}) {
    this._ensure()
    if (!this.child) return Promise.reject(new Error('引擎未启动'))
    return new Promise((resolve, reject) => {
      const id = ++this.seq
      const timer = setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`RPC 超时 (${RPC_TIMEOUT}ms): ${method}`))
        }
      }, RPC_TIMEOUT)
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      })
      try {
        this.child.stdin.write(
          JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n'
        )
      } catch (e) {
        clearTimeout(timer)
        this.pending.delete(id)
        reject(e)
      }
    })
  }

  shutdown() {
    if (this.child) {
      try { this.child.kill() } catch { /* 已退出 */ }
    }
  }
}

// --------------------------------------------------------------------------
// 输出
// --------------------------------------------------------------------------
function printResult(resp) {
  if (!resp) {
    console.error('无响应')
    return 1
  }
  if (resp.error) {
    console.error('RPC 错误: ' + (resp.error.message || JSON.stringify(resp.error)))
    if (resp.error.data) console.error(resp.error.data)
    return 1
  }
  const r = resp.result ?? null
  const json = JSON.stringify(r, null, 2)
  // 终端友好：中文确保可显示（node 默认 utf8）。直接打印。
  process.stdout.write(json + '\n')
  return 0
}

// --------------------------------------------------------------------------
// 子命令实现
// --------------------------------------------------------------------------
async function cmdServe(args, engine) {
  const flags = parseFlags(args)
  const port = flags.port
  const env = { ...process.env }
  if (port) env.PORT = String(port)
  // 启动 GUI 主机（Cordis）。stdio 继承，便于直接在终端看日志/交互。
  const p = spawn('node', ['server/host.mjs'], {
    cwd: ROOT,
    stdio: 'inherit',
    env,
    windowsHide: true,
  })
  p.on('exit', (code) => { process.exit(code ?? 0) })
  // 转发退出信号
  const fwd = (s) => { try { p.kill(s) } catch {} }
  process.on('SIGINT', fwd)
  process.on('SIGTERM', fwd)
  return new Promise(() => {}) // 常驻
}

function cmdCall(args, engine) {
  const method = args[0]
  if (!method) {
    console.error('用法: call <METHOD> [--flag value ...]')
    return Promise.resolve(1)
  }
  const flags = parseFlags(args.slice(1))
  return engine.call(method, flags).then(printResult)
}

async function cmdReparse(args, engine) {
  let child
  try {
    child = spawn(PYTHON, [PARSER], {
      cwd: ENGINE,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
  } catch (e) {
    console.error(`无法启动解析器: ${e.message}（python=${PYTHON}）`)
    return 1
  }
  let out = ''
  let err = ''
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (d) => { out += d; process.stdout.write(d) })
  child.stderr.on('data', (d) => { err += d; process.stderr.write(d) })
  return new Promise((resolve) => {
    child.on('exit', (code) => {
      const summary = out.match(/ok=(\d+)\s+degraded=(\d+)\s+failed=(\d+)/)
      if (code === 0 && summary) {
        console.log(`\nreparse 成功: ok=${summary[1]} degraded=${summary[2]} failed=${summary[3]}`)
        resolve(0)
      } else {
        console.error(`\nreparse 失败（exit=${code}）。stderr:\n${err || '(空)'}`)
        resolve(1)
      }
    })
    child.on('error', (e) => {
      console.error(`reparse 启动错误: ${e.message}`)
      resolve(1)
    })
  })
}

function cmdScan(args, engine) {
  const flags = parseFlags(args)
  if (flags.file) {
    return engine.call('scan.file', { path: flags.file, chapter: flags.chapter ?? 999 })
      .then(printResult)
  }
  const text = flags.text
  if (text === undefined) {
    console.error('用法: scan --text "..." [--chapter N]  或  scan --file 路径 [--chapter N]')
    return Promise.resolve(1)
  }
  return engine.call('scan.chapter', { text, chapter: flags.chapter ?? 999 })
    .then(printResult)
}

function wrap(method) {
  return (args, engine) => engine.call(method, parseFlags(args)).then(printResult)
}

const SUBCOMMANDS = {
  // 便捷命令
  selfcheck: (args, e) => e.call('selfcheck', {}).then(printResult),
  dataset: (args, e) => e.call('dataset.get', {}).then(printResult),
  research: (args, e) => e.call('research.get', {}).then(printResult),
  // 通用
  call: cmdCall,
  serve: cmdServe,
  reparse: cmdReparse,
  scan: cmdScan,
  // 前缀式
  panel: (args, e) => {
    const sub = args[0]
    if (!sub) { console.error('用法: panel <sub> [--flag value ...] （如 snapshot/kill/allocate/render）'); return Promise.resolve(1) }
    return e.call(`panel.${sub}`, parseFlags(args.slice(1))).then(printResult)
  },
  trpg: (args, e) => {
    const sub = args[0]
    if (!sub) { console.error('用法: trpg <sub> [--flag value ...] （如 check/tier/matchup）'); return Promise.resolve(1) }
    return e.call(`trpg.${sub}`, parseFlags(args.slice(1))).then(printResult)
  },
  codex: (args, e) => {
    const sub = args[0]
    if (!sub) { console.error('用法: codex <sub> （如 bestiary/tiers/planes/rules）'); return Promise.resolve(1) }
    return e.call(`codex.${sub}`, parseFlags(args.slice(1))).then(printResult)
  },
  pc: (args, e) => {
    const sub = args[0]
    if (!sub) { console.error('用法: pc <sub> （profiles/build/maneuvers/catalog）'); return Promise.resolve(1) }
    return e.call(`pc.${sub}`, parseFlags(args.slice(1))).then(printResult)
  },
  combat: cmdCombat,
  campaign: cmdCampaign,
}

// --------------------------------------------------------------------------
// campaign —— 战役层（跨场保留 HP / 法力 / 灰线 / 火花）
// --------------------------------------------------------------------------
function cmdCampaign(args, engine) {
  const sub = args[0]
  const flags = parseFlags(args.slice(1))
  if (!sub) {
    console.error([
      '用法: campaign <sub> [选项]',
      '  campaign chains                         预置卷级遭遇链目录',
      '  campaign new [--chain v3-mycelium] [--seed N]',
      '  campaign state                          战役快照（HP/法力/灰线/火花/进度）',
      '  campaign next                           开战役链的下一场（PC 沿用跨场状态）',
      '  campaign insert --enemies \'[{"name":"二级","count":2}]\' [--name "临时遭遇"]',
      '  campaign rest                           休整：恢复 25% 生命上限（灰线不回退 R11）',
      '  campaign draw --color 绿 [--cells 1]     汲取法力，灰线 +1（R11）',
      '  campaign heal                           治疗言灵（绿 1 环，耗 1 点绿法力）',
      '  campaign apply                          把当前战斗结果收回战役并推进链',
      '  campaign end                            结束战役',
    ].join('\n'))
    return Promise.resolve(1)
  }
  const known = ['chains', 'new', 'state', 'next', 'insert', 'rest', 'draw',
                 'heal', 'apply', 'end']
  if (!known.includes(sub)) {
    console.error(`未知 campaign 子命令: ${sub}（可选：${known.join('/')}）`)
    return Promise.resolve(1)
  }
  return engine.call(`campaign.${sub}`, flags).then(printResult)
}

// --------------------------------------------------------------------------
// combat —— 遭遇战沙盘
//
// flags 里 enemies 需要传数组（--enemies '[{"name":"变异鬣狗","count":2}]'），
// parseFlags 会把能 JSON.parse 的值转成对象/数组，所以直接写 JSON 即可。
// --------------------------------------------------------------------------
function cmdCombat(args, engine) {
  const sub = args[0]
  const flags = parseFlags(args.slice(1))
  if (!sub) {
    console.error([
      '用法: combat <sub> [选项]',
      '  combat catalog                        敌人目录（谱系 + 具名异族）',
      '  combat new [--profile v3-mycelium] [--enemies \'[{"name":"变异鬣狗","count":2}]\'] [--seed N]',
      '  combat state                          取战斗快照',
      '  combat act --action power_attack [--params \'{"target":"变异鬣狗#1"}\']',
      '  combat enemies                        推进敌人回合',
      '  combat auto                           PC 用简单策略自动打完',
      '  combat narrate                        生成可粘进正文的叙事文本',
      '  combat end                            结束/放弃战斗',
    ].join('\n'))
    return Promise.resolve(1)
  }
  const known = ['catalog', 'new', 'state', 'act', 'enemies', 'auto', 'narrate', 'end']
  if (!known.includes(sub)) {
    console.error(`未知 combat 子命令: ${sub}（可选：${known.join('/')}）`)
    return Promise.resolve(1)
  }
  return engine.call(`combat.${sub}`, flags).then(printResult)
}

// --------------------------------------------------------------------------
// 帮助
// --------------------------------------------------------------------------
function printHelp() {
  const lines = [
    'wasteland-panel CLI — 零依赖命令行工具',
    '',
    '用法: node server/cli.mjs <子命令> [选项]',
    '',
    '可用子命令:',
    '  serve [--port P]          启动 Cordis GUI 主机（node server/host.mjs）',
    '  call <METHOD> [--f v ...] 直接调用任意 JSON-RPC 方法',
    '  selfcheck                 数据层完整性体检（= call selfcheck）',
    '  dataset                  取数据层概要（= call dataset.get）',
    '  research                 取调研数据（= call research.get）',
    '  reparse                  运行 bible_parser.py 重建 dataset.json',
    '  scan --text "..." [--chapter N]   机扫章节文本',
    '  scan --file 路径 [--chapter N]     按文件机扫',
    '  panel <sub> [--f v ...]  面板操作（snapshot/kill/allocate/breakthrough/',
    '                           grayline/structureTax/volume/mana/ignite/render/reset）',
    '  trpg <sub> [--f v ...]   检定机制（check/rate/tier/matchup/status/burn）',
    '  codex <sub>              图鉴/设定（bestiary/tiers/planes/rules/plot/...）',
    '  pc <sub> [--f v ...]     角色（profiles/build/maneuvers/catalog）',
    '  combat <sub> [--f v ...] 遭遇战沙盘（catalog/new/state/act/enemies/',
    '                           auto/narrate/end）',
    '  campaign <sub> [--f v ...] 战役层（chains/new/state/next/insert/rest/',
    '                           draw/heal/apply/end）',
    '  --help | help            显示本帮助',
    '',
    '标志值强制转换:',
    '  true/false → 布尔; 数字串 → 数字; @文件 → 读文件文本;',
    '  能 JSON.parse 的 → 对象/数组; 否则原样字符串。',
    '',
    `Python: ${PYTHON}`,
  ]
  console.log(lines.join('\n'))
}

// --------------------------------------------------------------------------
// 入口
// --------------------------------------------------------------------------
async function main() {
  const argv = process.argv.slice(2)
  const sub = argv[0]

  if (!sub || sub === '--help' || sub === 'help' || sub === '-h') {
    printHelp()
    return
  }

  const handler = SUBCOMMANDS[sub]
  if (!handler) {
    console.error(`未知子命令: ${sub}\n`)
    printHelp()
    return
  }

  const engine = new EngineClient()
  try {
    const code = await handler(argv.slice(1), engine)
    engine.shutdown()
    process.exit(code ?? 0)
  } catch (e) {
    console.error('错误: ' + (e.message || e))
    engine.shutdown()
    process.exit(1)
  }
}

main()
