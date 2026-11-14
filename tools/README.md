# tools/ · 仓根工具编排层（Cordis 润滑层）

> **这是什么**：全仓工具链的**统一入口**。加能力 = 改 `cordis.yml` 加一条，
> 或新建一个 `.mjs` 丢进 `plugins/` —— **不需要动 `host.mjs`**。
>
> **一句话架构**：**Cordis 做壳（编排/配置/汇总），Python 做里（检查内核）**。
> Python 内核保持零三方依赖（只用标准库），换机即跑；
> cordis 负责「何时跑、跑哪些、怎么汇总」。

---

## 30 秒上手

```bash
npm install                      # 装 cordis 与插件（node_modules/ 已 gitignore）
npm run doctor                   # 环境自检：解释器 / 插件 / 项目可达性
npm run list                     # 列出插件、项目、检查器
npm run check                    # 跑全部检查器 → 审校报告/工具链自检报告-*.md
npm run check:package            # 只跑模板包自检
npm run check:doc                # 只跑文档审校
npm run check:consistency        # 只跑结构一致性
node tools/host.mjs check wushuang   # 只审《无敌不是他人路》

# PKM 知识连接层
npm run pkm:build                # 重建索引 + 图谱 + MOC
npm run pkm:search 战锤四神       # 全仓检索（中文二元组切分）
npm run pkm:links <文档路径>      # 查某文档的出链 / 入链
npm run pkm:graph                # 图谱统计
npm run pkm:doctor               # PKM 环境自检
```

**退出码**：`0` 无 ERROR ／ `1` 有 ERROR ／ `2` 参数或环境故障 —— 可直接进 CI。

**换机一键部署**：`bash tools/bootstrap.sh`（Git Bash）或
`powershell -ExecutionPolicy Bypass -File tools\bootstrap.ps1`（Windows）。
详见 [`PKM/换机部署.md`](../PKM/换机部署.md)。

---

## 目录

```
tools/
├── cordis.yml              插件树（应用能力的唯一真理源）
├── host.mjs                装配壳（极薄：建上下文 + 挂 loader + 挂 cordis.yml）+ 命令分派
├── checker_protocol.py     检查器 JSON 协议（Python 侧定义）
├── doc_review.py           审校引擎（八类检查；也作为 WorkBuddy Skill 使用）
├── manifest.py             模板包哈希校验（MANIFEST.sha256）
├── bootstrap.sh            换机一键部署（Git Bash / Linux / macOS）
├── bootstrap.ps1           换机一键部署（Windows PowerShell）
├── fix_bom.py              编码归一（内容类带 BOM / 机器读类不带）
├── pkm/                    PKM 知识连接层内核（Python，零三方依赖）
│   ├── scanner.py          仓扫描 · 元数据抽取 · 双链解析
│   ├── indexer.py          中文二元组分词 · 倒排索引 · 检索打分
│   ├── graph.py            知识图谱 · MOC · 孤立清单 · 断链清单
│   └── pkm_cli.py          统一 CLI（build/search/links/graph/doctor）
├── plugins/
│   ├── 01-config.mjs       配置服务（仓根 / Python 解释器 / 报告目录）
│   ├── 02-registry.mjs     项目登记表（各项目范围与口径）
│   ├── 03-runner.mjs       Python 调用桥（协议边界）
│   ├── 04-checkers.mjs     检查器登记表
│   ├── 10-checker-package.mjs      通用模板包自检
│   ├── 11-checker-doc-review.mjs   文档审校
│   ├── 12-checker-consistency.mjs  项目结构一致性
│   ├── 13-pkm.mjs                  PKM 索引与检索服务（提供 ctx.pkm）
│   ├── 14-checker-pkm.mjs          PKM 连接层体检
│   ├── 15-checker-sync.mjs         三端同步状态（Gitee/GitHub）
│   ├── 20-report.mjs       汇总报告（Markdown + JSON）
│   └── 30-cli.mjs          统一命令行（命令：check / list / doctor / pkm）
├── checkers/               Python 适配器（把项目自带脚本包成协议 JSON）
│   ├── package_check.py
│   ├── consistency_check.py
│   ├── pkm_check.py
│   └── sync_check.py
└── projects/               各项目的审校口径（JSON）
    ├── wushuang.json
    └── huaxi.json
```

---

## 插件树与依赖图

加载顺序由**依赖图**决定，不由 `cordis.yml` 的行序决定：

```
config ──┬─→ projects ──┐
         ├─→ runner ────┼─→ checker-package
         └─→ checkers ←─┴─→ checker-doc-review
                        └─→ checker-consistency
                                    ↓
        report ←────────────────── cli
```

各插件通过 `inject: [...]` 声明依赖；**依赖未就绪则插件挂起**，
就绪后自动启动。加载顺序变了不用改代码。

---

## 检查器 JSON 协议

cordis 编排层与 Python 内核之间的**唯一边界**（定义见 `checker_protocol.py`）：

- **stdout 只放一个 JSON 对象**；日志/诊断一律走 stderr。
- 退出码：`0` 通过 ／ `1` 有 ERROR ／ `2` 协议层故障。

```json
{
  "checker": "doc-review",
  "ok": true,
  "severity": "warn",
  "summary": "11 个文件：错误 0 ／ 警告 3 ／ 提示 1",
  "counts": { "error": 0, "warn": 3, "info": 1 },
  "findings": [
    { "severity": "warn", "category": "术语", "code": "TERM-MIX",
      "file": "...", "line": 12, "snippet": "...", "message": "...",
      "suggestion": "..." }
  ],
  "artifacts": [ { "kind": "report", "path": "...", "bytes": 1234 } ],
  "meta": { }
}
```

### 为什么 Python 内核要「包一层」

项目自带的扫描器（如 `点子库/04-工具/audit_consistency.py`）打印的是**人读报告**，
且路径写死在自身目录下。适配器（`tools/checkers/*.py`）**不改原脚本**
（它们是项目资产，纳入版本库），而是捕获其输出并转成协议 JSON。

---

## 审校口径（项目级）

口径**属项目，不属工具层**：每个项目的指标声明、术语表放在 `tools/projects/<id>.json`，
由项目自己维护；工具层只消费。

```json
{
  "metrics": {
    "真气": {
      "scope": ["无敌不是他人路"],
      "pattern": "真气[^。；\\n]{0,10}?(\\d+(?:\\.\\d+)?)%",
      "mode": "state",
      "forbid_if": "无面板数值"
    }
  },
  "terms": { "楚嫣然": ["楚嫣然", "嫣然"] },
  "ignore": [ "^#{1,6}\\s" ]
}
```

| 字段 | 说明 |
|---|---|
| `metrics` | 跨文件比对数值口径。`mode: state`＝随剧情演进（默认，不报冲突）／`constant`＝恒定值（不同取值即报）。`forbid_if` 抓「定义处说不设数值口径、使用处却记数值」——**须声明与记账同时命中才报**（只有声明、没有数值记账时不算冲突） |
| `terms` | 概念的合法变体。全名与简称互为子串时视为合法 |
| `ignore` | 整行跳过的正则 |
| `unregistered_scan` | 默认关；开启后报疑似未登记专名 |

### 扫描范围＝项目根，不是正文目录（2026-11-13 起）

`tools/cordis.yml` 里每个项目的 `text` 指向**项目根**（含设定、台账、正文），不是 `正文/`：

- 口径类规则（`metrics` / `forbid_if` / 时间锚换算）本质是**「设定 ↔ 台账 ↔ 正文」三方比对**；
  只扫正文会让口径规则全程失效 —— P1-1/2/3 三处冲突正是靠三方比对才暴露的。
- 代价：设定层的体例存量项（直引号、破折号、括号、悬空引用、段内重复）会一并进报告。
  这些是**真实且未分流**的存量问题，severity 为 `warn`（需一次性人工定性）；
  `STRUCT-ENC`（工作区 CRLF）恒为 `info` —— 入库字节是 LF、工作区 CRLF 只是 `core.autocrlf=true`
  的检出假象，按《工作区规范》§八 3 的口径**不作为入库缺陷**。
- **闸门只看 ERROR**：`ERROR 0`＝可放行；WARN 需定性、INFO 是观察项。
  想收窄范围时，在 `tools/cordis.yml` 的 `checker-doc-review` 下加 `only: [typo, number, time]`。

---

## 新增一个检查器（三步）

1. 写 `plugins/5X-checker-xxx.mjs`：

```js
export const CheckerXxx = {
  name: 'checker-xxx',
  inject: ['config', 'runner', 'checkers'],
  apply(ctx, config = {}) {
    async function run(projectIds = []) {
      const r = await ctx.runner.run('xxx', './tools/checkers/xxx_check.py', [], { cwd: ctx.config.root })
      return r                      // 协议对象
    }
    ctx.checkers.register({ id: 'xxx', name: '我的检查器', run })
  },
}
```

2. 在 `cordis.yml` 加一条：

```yaml
- id: checker-xxx
  name: ./plugins/5X-checker-xxx.mjs
  inject: [config, runner, checkers]
```

3. 写 `tools/checkers/xxx_check.py`（用 `checker_protocol.emit()` 输出）。

**CLI 与报告不用改** —— 它们从 `ctx.checkers` 表里取。

---

## 与《小说/wasteland-panel》的关系

| | `tools/`（本层） | `小说/wasteland-panel/` |
|---|---|---|
| 范围 | **全仓**（`cordis.yml` 已注册 3 个项目，未注册项 SKIP） | 单本书《废土旅法师》 |
| 形态 | 工具流水线（CLI → 报告） | Web 面板工作台（HTTP + 数据层） |
| 插件树 | `tools/cordis.yml` | `小说/wasteland-panel/cordis.yml` |
| 约定 | 同：薄壳 + 插件树 + `inject` 依赖图 | 同 |

两者用**同一套 cordis 约定**，但插件树互不相干 —— 插件树是**应用内**的，
两个应用各自有自己的一套。

---

## 工程约束

- **Python 内核零三方依赖**：只用标准库。`checker_protocol.py` 与 `doc_review.py` 均如此。
- **不写死盘符/用户名**：路径一律相对仓根；解释器按 `配置 → PYTHON 环境变量 → WorkBuddy 内置 → PATH` 探测。
- **只读源文件**：所有检查器只写报告目录，不改被审文件（与 `11` 号模板铁律同源）。
- **可复跑**：同一输入同一结果（时间戳只进文件名，不进判定）。
- **失败可见**：路径缺失、源加载失败、检查器崩溃都**显性上报**，不静默吞掉。

---

*2026-11-13 建立。依据：`审计报告-深度审计与架构重构-20261113.md` §五 架构重构评估。*
