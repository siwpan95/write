/**
 * 插件 01 · config —— 基础配置服务
 *
 * 全应用唯一的路径 / 解释器 / 报告目录真理源。
 * 下游插件通过 `inject: ['config']` 声明依赖，拿到的永远是同一份对象；
 * 插件挂载顺序由依赖图决定，不需要人工编排。
 *
 * 提供：ctx.config = { root, python, reports, ... }
 */
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const TOOLS_ROOT = path.resolve(HERE, '..')          // tools/
const REPO_ROOT = path.resolve(TOOLS_ROOT, '..')     // 仓根

/**
 * 定位 Python 解释器。
 *
 * 刻意**不做 spawnSync 版本探测**：受限沙箱下 spawnSync 会返回 EBUSY
 * （文件被占用）而误判成「找不到解释器」，导致整个工具链起不来。
 * 改为「文件存在性检查 + 真正 spawn 后由子进程自报版本」。
 *
 * 候选顺序：显式配置 → PYTHON 环境变量 → 本机 WorkBuddy 内置 → PATH。
 * **不写死任何用户名**（旧版 wasteland-panel/bridge.js 写死
 * `C:\Users\Administrator\...`，换机即失效 —— 2026-11-13 审计已修）。
 */
function findPython(configured) {
  const cands = [
    configured,
    process.env.PYTHON,
    process.env.WRITE_PYTHON,
    path.join(process.env.USERPROFILE || process.env.HOME || '',
      '.workbuddy', 'binaries', 'python', 'envs', 'default', 'Scripts', 'python.exe'),
    path.join(process.env.USERPROFILE || process.env.HOME || '',
      '.workbuddy', 'binaries', 'python', 'envs', 'default', 'bin', 'python'),
  ].filter(Boolean)
  for (const c of cands) {
    try { if (fs.existsSync(c)) return c } catch { /* 试下一个 */ }
  }
  // 退回 PATH 上的命令（可能是 python / python3 / WindowsApps 别名）
  return process.platform === 'win32' ? 'python' : 'python3'
}

export const Config = {
  name: 'config',
  inject: [],

  apply(ctx, config = {}) {
    const root = config.root
      ? path.resolve(REPO_ROOT, config.root)
      : REPO_ROOT
    const python = findPython(config.python)
    const reports = path.resolve(root, config.reports || './审校报告')

    const cfg = {
      root,
      toolsRoot: TOOLS_ROOT,
      python,
      reports,
      platform: process.platform,
    }

    ctx.provide('config', cfg)
    ctx.logger.info(
      'config: root=%s python=%s reports=%s',
      path.relative(root, root) || root,
      path.basename(python),
      path.relative(root, reports) || reports,
    )
  },
}

export default Config
