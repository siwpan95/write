/**
 * bible 源路径解析 · bible-paths.mjs
 * ---------------------------------------------------------------------------
 * **唯一事实源**：数据层源文件清单只在这里声明一次。
 *
 * 背景（2026-11-13 审计发现）：`01-config.mjs` 的 `BIBLE_SOURCES` 与
 * `engine/bible_parser.py` 的 `check = root / "一致性核查"` **各写了一份**，
 * 且目录已按《工作区规范》§三由 `一致性核查/` 改名为 `一致性核查-历史归档/`，
 * 两处都没同步 → 面板启动时「世界规则 R1-R15」与「角色档案」两个源
 * **静默加载失败**（日志只留两行 `[FAIL]`，进程照常起，`degraded=0`）。
 *
 * 对策：
 *   ① 路径候选化——目录改名后仍能找到（`resolveFirst` 取第一个存在的）；
 *   ② 清单单一化——本文件导出，JS 侧与 Python 侧共用同一份声明；
 *   ③ 缺失可见——`resolveAll` 返回缺失清单，调用方须显式上报，不得吞掉。
 *
 * 刻意**不写死盘符**：一切相对 `BIBLE_ROOT`（默认＝小说根目录）。
 */
import path from 'node:path'
import fs from 'node:fs'

/**
 * 源清单。每项：
 *   id      逻辑名（与解析报告里的 step 对应，便于对齐排查）
 *   file    文件名（相对某个候选目录）
 *   dirs    候选目录，按优先级排列（第一个存在的胜出）
 *   kind    'file' | 'dir'
 */
export const BIBLE_SOURCES = [
  { id: 'world-bible', kind: 'file', file: 'world-bible.md', dirs: ['bible'] },
  { id: 'plot-board', kind: 'file', file: 'plot-board.md', dirs: ['bible'] },
  { id: 'timeline', kind: 'file', file: 'timeline.md', dirs: ['bible'] },
  // ↓ 目录已改名：'一致性核查' → '一致性核查-历史归档'（《工作区规范》§三）
  //   两个候选都留着，改回去也能用；解析器与配置层共用本清单。
  {
    id: 'rules',
    kind: 'file',
    file: '世界观设定标尺.md',
    dirs: ['一致性核查', '一致性核查-历史归档'],
  },
  { id: 'cost-arc', kind: 'file', file: '长弧规划.md', dirs: ['设定与参考'] },
  {
    id: 'terminology',
    kind: 'file',
    file: '扩写规范-统一执行手册.md',
    dirs: ['设定与参考'],
  },
  {
    id: 'characters',
    kind: 'file',
    file: '角色档案.md',
    dirs: ['一致性核查', '一致性核查-历史归档'],
  },
]

/** 角色卡是**目录**：单列给引擎插件做目录级 mtime 扫描 */
export const CARD_DIRS = [{ id: 'character-cards', kind: 'dir', dirs: ['bible/characters'] }]

/**
 * 取第一个存在的候选路径。
 * @returns {string|null} 绝对路径；全部不存在时返回 null
 */
export function resolveFirst(root, spec) {
  for (const d of spec.dirs) {
    const p = path.join(root, d, spec.file ?? '')
    try {
      if (spec.kind === 'dir' ? fs.statSync(p).isDirectory() : fs.existsSync(p)) {
        return p
      }
    } catch { /* 试下一个 */ }
  }
  return null
}

/**
 * 解析全部源。
 * @returns {{resolved: Array, missing: Array}}
 *   resolved —— 每项 {id, path}
 *   missing  —— 每项 {id, tried: string[]}，**调用方必须显式上报**
 */
export function resolveAll(root, specs = BIBLE_SOURCES) {
  const resolved = []
  const missing = []
  for (const spec of specs) {
    const p = resolveFirst(root, spec)
    if (p) {
      resolved.push({ id: spec.id, path: p })
    } else {
      missing.push({
        id: spec.id,
        tried: spec.dirs.map((d) => path.join(root, d, spec.file ?? '')),
      })
    }
  }
  return { resolved, missing }
}
