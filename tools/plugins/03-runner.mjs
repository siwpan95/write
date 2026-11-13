/**
 * 插件 03 · runner —— Python 检查器调用桥
 *
 * 编排层与 Python 内核之间的**唯一边界**：
 *   · Python 内核保持零三方依赖（只用标准库），换机即跑；
 *   · 协议 = stdout 一个 JSON 对象（见 tools/checker_protocol.py）；
 *   · 日志/诊断一律走 stderr，不污染 stdout 的数据通道。
 *
 * 提供：ctx.runner.run(checkerId, script, args, opts)
 */
import { spawn } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'

export const Runner = {
  name: 'runner',
  inject: ['config'],

  apply(ctx, config = {}) {
    const { root, python } = ctx.config
    const timeout = config.timeout ?? 600000

    /**
     * 跑一个 Python 检查器，返回协议对象。
     * **永不抛异常**：失败也返回结构化结果（协议层故障 → exitCode 2）。
     */
    function run(checkerId, script, args = [], opts = {}) {
      const scriptPath = path.isAbsolute(script)
        ? script
        : path.resolve(root, script)

      if (!fs.existsSync(scriptPath)) {
        return Promise.resolve({
          checker: checkerId,
          ok: false,
          severity: 'error',
          summary: `检查器脚本不存在：${script}`,
          counts: { error: 1, warn: 0, info: 0 },
          findings: [{
            severity: 'error', category: '执行', code: 'CHECKER-MISSING',
            file: script, line: 0, snippet: '',
            message: `检查器脚本不存在：${script}`,
            suggestion: '检查 cordis.yml 的路径配置',
          }],
          artifacts: [], meta: { exitCode: 2 },
        })
      }

      return new Promise((resolve) => {
        const child = spawn(python, [scriptPath, ...args], {
          cwd: opts.cwd || root,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        })

        let stdout = ''
        let stderr = ''
        let settled = false

        const timer = setTimeout(() => {
          if (settled) return
          settled = true
          try { child.kill() } catch { /* 已退出 */ }
          resolve({
            checker: checkerId, ok: false, severity: 'error',
            summary: `检查器超时（${timeout}ms）：${path.basename(scriptPath)}`,
            counts: { error: 1, warn: 0, info: 0 },
            findings: [{
              severity: 'error', category: '执行', code: 'CHECKER-TIMEOUT',
              file: scriptPath, line: 0, snippet: '',
              message: `检查器超时（${timeout}ms）`,
              suggestion: '缩小审校范围，或调大 cordis.yml 的 runner.timeout',
            }],
            artifacts: [], meta: { exitCode: 2, timedOut: true },
          })
        }, timeout)

        child.stdout.on('data', (d) => { stdout += d.toString('utf-8') })
        child.stderr.on('data', (d) => { stderr += d.toString('utf-8') })
        child.on('error', (e) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          resolve({
            checker: checkerId, ok: false, severity: 'error',
            summary: `检查器无法启动：${e.message}`,
            counts: { error: 1, warn: 0, info: 0 },
            findings: [{
              severity: 'error', category: '执行', code: 'CHECKER-SPAWN',
              file: scriptPath, line: 0, snippet: '',
              message: `检查器无法启动：${e.message}`,
              suggestion: '检查 Python 解释器路径（cordis.yml 的 config.python）',
            }],
            artifacts: [], meta: { exitCode: 2, stderr },
          })
        })
        child.on('close', (code) => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          // 协议解析：stdout 必须是且只是一个 JSON 对象
          let parsed = null
          try {
            const start = stdout.indexOf('{')
            const end = stdout.lastIndexOf('}')
            if (start >= 0 && end > start) {
              parsed = JSON.parse(stdout.slice(start, end + 1))
            }
          } catch { /* 解析失败 → 落到下面的兜底 */ }

          if (!parsed) {
            resolve({
              checker: checkerId, ok: false, severity: 'error',
              summary: `检查器未按协议输出 JSON（exit=${code}）`,
              counts: { error: 1, warn: 0, info: 0 },
              findings: [{
                severity: 'error', category: '执行', code: 'CHECKER-PROTOCOL',
                file: scriptPath, line: 0,
                snippet: stdout.slice(0, 200),
                message: `检查器未按协议输出 JSON（exit=${code}）`,
                suggestion: '检查器须用 tools/checker_protocol.py 的 emit() 输出',
              }],
              artifacts: [], meta: { exitCode: 2, stderr: stderr.slice(0, 800) },
            })
            return
          }
          parsed.meta = { ...(parsed.meta || {}), exitCode: code, stderr: stderr.slice(0, 2000) }
          resolve(parsed)
        })
      })
    }

    ctx.provide('runner', { run })
    ctx.logger.info('runner: python=%s timeout=%dms', path.basename(python), timeout)
  },
}

export default Runner
