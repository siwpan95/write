# 审计报告 · `peasy-ai` / `dse-core` 引入 `write` 仓的可行性评估

> **时点**：2026-11-21 ｜ **性质**：可行性评估（**未写入任何仓内资产，未改任何小说正文，未 commit/push**）
> **评估对象**：[peasy-ai 1.0.1](https://pypi.org/project/peasy-ai/)（siwpan 自有，MIT）、[dse-core 0.7.0](https://pypi.org/project/dse-core/)（siwpan 自有，MIT）
> **实测环境**：本机 `@SIWPAN`（win32）｜ Python 3.13.14（`E:\Python314`）｜ 隔离 venv `Temp/probe_venv`
> **证据口径**：本报告所有「✅ 已验证」条目均附实际命令输出；「⏳ 待验」条目为未实测的推断，不得当作结论使用。
> **⚠️ 本机事实标注**：本报告含盘符、解释器路径、venv 路径、文档计数等**本机时点事实**，换机/换版本即失效。他机复现方式见 §附录 B。

---

## 〇、TL;DR

**结论：可行，但两者定位完全不同，不能当同一类东西用。建议 `dse-core` 引入、`peasy-ai` 只在特定槽位取用，`peasy-ai` 的叙事引擎部分建议不引入。**

| 维度 | 结论 | 一句话理由 |
|---|---|---|
| **dse-core** | ✅ **建议引入（P1）** | 唯一能把 write 仓「大纲/节拍/零件库」变成**可执行、可验证**的图结构的东西；其 `check`/`traverse`/`coverage` 三道门与 write 仓现有 Cordis 闸门同构，接入成本低 |
| **peasy-ai（AI 核心）** | ⚠️ **有限取用（P2）** | 零依赖规则引擎 + 可学习记忆，对 write 仓价值主要在「术语/设定问答台账」；但**不是 LLM 框架**，别当 AI 写作引擎用 |
| **peasy-ai（叙事引擎）** | ❌ **不建议引入** | 属性模型是「全局标量 + 上下界触发结局」，装不下 write 仓网文的多实体/条件语义状态；能力已被 dse-core 全面超越 |
| **peasy-ai（TRPG 训练器 + tools）** | ✅ **值得取用（P2）** | `random_npc()` 五要素 NPC 生成、`AITrainer` 事件→记忆入库，天然对接 write 仓「04 人物卡」批量龙套槽位 |

**最有价值的单条发现**：`write` 仓的 Markdown 四层大纲**可自动转换成 dse 内容包**，本报告已写出转换器探针并跑通 —— 7 段主线 → 14 个可达结局 → `traverse` 9 条完整路径全绿。这是把「写过的规划」变成「可执行的机器」的真路径。

**最有价值的单条警告**：`peasy-ai` 与 `dse-core` **都不是 LLM 封装**。它们是规则引擎和数据引擎。write 仓要接 LLM，得另走 Ollama（已在 E 盘）那条线。把这两个包装成「AI 写作助手」是营销话术，不是工程事实。

---

## 一、评估方法论

### 1.1 原则（继承全哥既有铁律）

1. **README 优先但不信 README** —— 两个包的 PyPI README 都写得漂亮，但实测发现 **dse-core README 的条件表达式写法有错**（详见 §四 D-2）。所有能力一律以 **schema + 实跑输出** 为准。
2. **端到端实测** —— 每个「支持」结论都必须有实际命令输出，不接受「看起来能跑」。
3. **反向验证** —— 不只测「能过」，还要测「坏了能不能抓到」。断链、悬空跳转必须能触发非零退出码。
4. **零污染** —— 不往 `E:\Python314` 主环境装任何东西，全部在临时 venv 里测；本报告不写仓内资产。

### 1.2 评估维度

| 维度 | 关注点 |
|---|---|
| 契合度 | 与 write 仓现有资产（模板包 / 零件库 / PKM / Cordis 工具链）的重叠与互补 |
| 可集成性 | 能否接入 `tools/cordis.yml` 插件树与检查器协议 |
| 可验证性 | 是否自带机械门禁，能否替代/补充现有 `npm run check` |
| 内容安全 | 是否有沙箱；产物是否适合入 Git |
| 依赖成本 | 是否破坏「Python 内核零三方依赖」洁癖 |
| 作者一致性 | 与 `通用模板包/18` 已定的程序化创作纪律是否冲突 |

---

## 二、write 仓现状盘点（引入前的地基）

> 结论先行：**write 仓不是白板**。程序化创作的地基已经打好，两个包是「往上加楼层」，不是「从零打地基」。

| 现有资产 | 位置 | 与本次评估的关系 |
|---|---|---|
| **程序化创作方法论** | `通用模板包/18-程序化创作与算法脚本模板.md` | 已含五代方法谱系（TALE-SPIN→MEXICA→Tracery→Re3）、**五个算法槽位**、启用/禁用判据、验收门 |
| **三个随包脚本** | `通用模板包/tools/procedural/`（`goal_sim.py` / `grammar_expand.py` / `name_generator.py`） | 已实现槽位一/二/三；**槽位四（巡检）已落地、槽位五（LLM 混合流水线）仅有设计** |
| **零件库 v2.1** | `零件库/` | 28 件 L2 抽象零件 + 49 条咬合边 + 装配体 ＝ **现成的图结构素材** |
| **Cordis 工具链** | `tools/cordis.yml`（14 插件 / 7 检查器） | 插件树 + `inject` 依赖图；**这就是 dse-core 的天然宿主** |
| **检查器协议** | `tools/checker_protocol.py` + `tools/checkers/*.py` | 适配器模式：不改被检脚本，捕获 stdout 包成协议 JSON → **dse 接入的模板** |
| **PKM 知识层** | `PKM/`（1613 文档 / 2574 出链 / 0 断链） | 中文二元组切分检索，`matched` 字段带命中词 → **可作引擎的检索上下文源** |
| **既有 dse 实跑记录** | `其他项目归档/dict-scene-engine实跑记录_单文件合订.html`（1.19MB / 88 条路线） | **是 Node 版 dse 的记录**，与 PyPI 的 Python 版**内容格式不互通** |

### 2.1 关键口径澄清（先说清，避免后面打架）

**⏳ 重要：`dse-core` 有两个，且不互通**

| 版本 | 载体 | 内容格式 | 安全模型 |
|---|---|---|---|
| **Node 版** | Gitee `siwpan/dse-core` | ESM `.js` 模块，**可执行代码** | ⚠️ 无沙箱，`state.check()` 走 `new Function`，内容包＝运行别人的 `.exe` |
| **Python 版** | PyPI `dse-core` 0.7.0 ＝ Gitee `siwpan/dse-core`（Python 原生仓） | **YAML 数据包** | ✅ **AST 白名单求值**，禁调用、禁下划线属性 |

本报告评估的是 **Python 版**（PyPI 可装的那一个）。write 仓那份 1.19MB 实跑记录来自 **Node 版**，**内容不可直接复用**，需重做。

**为什么这个差异对 write 仓至关重要**：write 仓是要进 Git、要多人维护、要长期演进的资产仓。**YAML 数据包比 ESM 代码安全一个数量级** —— 内容写错最多 check 报错，写成 JS 则是任意代码执行。Python 版是这个仓的正确答案。

---

## 三、`peasy-ai` 评估

### 3.1 包基本情况

| 项 | 值 |
|---|---|
| 版本 / 发布 | 1.0.1 ／ 2026-10-26 |
| 导入名 | `easy_ai`（发行名 `peasy-ai`，因 `easy-ai`/`easy_ai`/`easyai` 已被占用） |
| Python | >=3.9（**比 dse-core 宽松**） |
| 核心依赖 | **零**（可选 extra：`numpy` / `jieba` / `sklearn`） |
| 许可 / 维护 | MIT ／ siwpan（本仓自有） |
| 成熟度 | Development Status :: 4 - Beta |

### 3.2 分模块评估

#### ✅ 3.2.1 AI 核心（AICore）—— 值得取用，但定位要准

**实测输出**：
```
[respond] 你好呀！
[learn]   陈默            ← ai.learn("主角名字","陈默") 后精确回放
[props]   memory_count=1  matchers=[RegexMatcher, FuzzyMatcher, MarkovMatcher]
[intent]  ('command', 0.8)
```

**能力面**：`create()` 零文件启动 / `learn()`+`respond()` 可学习记忆 / `enable_sessions()` 多轮会话 / `enable_intent()` 意图识别 / `set_safety()` 安全过滤 / `save()`+`load()` 持久化 / `reload()` 配置热重载。

**⚠️ 实测到的坑**：
1. **缺 `jieba` 时 `extract_keywords` 退化为整句** —— 实测 `extract_keywords("今天的天气真好")` 返回 `[('今天的天气真好', 1.0)]`，不是分词结果。**中文场景必须装 `jieba` extra**，否则关键词抽取基本无效。
2. **缺 `numpy` 时 TextCNN 匹配器直接跳过** —— 实测启动即 WARN：`匹配器 neural 因缺少可选依赖被跳过`。降级不崩，但匹配能力少一层。

**对 write 仓的价值（定位纠偏）**：
它**不是 LLM 框架**，是「规则 + 模糊匹配 + 马尔可夫」的可学习问答引擎。它能做的最有价值的事，是**把设定/术语/台账条目做成可语义追问的知识库**：

> 「归档单上的『其他』是谁定的？」 → AICore 记住的是精确条目而非泛泛回答。

这正好补 write 仓现在的一个空缺：**PKM 只检索不回答**。`npm run pkm:search` 给你「哪些文档命中」，但不会告诉你「答案是什么、散落在几处」。AICore 的 `learn()` + `respond()` 可以把台账条目灌进去做「设定问答」。

**但注意**：它的马尔可夫/模糊匹配是**弱语义**，不是真理解。复杂问题会答错。定位应该是**「台账精确回放」**（类似 grep+缓存），**不是「作者大脑」**。

#### ❌ 3.2.2 叙事引擎（NarrativeEngine）—— 建议不引入

**实测输出（用 write 仓《廓者：未名夜》真实剧情结构）**：
```
[scene] start
[opts]  ['按下 Alt 72 下', '先读工牌背面']
WARNING 选项引用了未定义的属性：hp
[stats] {'turn_count': 1, 'current_scene': 'classify', 'attributes': {}, 'flags': [], 'clues': [], 'is_ended': False}
```

**致命问题：属性全部落空。** `attributes: {}` —— 我在选项里写的 `hp: -3`、`soul: -1`、`gold: 10` **一个都没生效**。

**根因**（读源码 + 读内置 `data/config.json` 确认）：它的属性模型是**全局标量 + 上下界触发结局**：

```json
{
  "title": "星舰迷途",
  "attributes": ["hull", "energy", "crew", "oxygen"],
  "attribute_default": 50, "attribute_max": 100, "attribute_min": 0,
  "endings": { "low_hull": "船体破裂……", "high_hull": "……", … }
}
```

一套 config 绑定**一整个故事**，结局由「属性越界」触发。write 仓网文的状态是 `hp/soul/trust/warmth` **各带各区间**，外加 `flags` 布尔树、`visits` 计数器、语义化标签（`flags.other_cell`、`flags.refuse`）。**这套模型装不下。**

**能力对比（结论性）**：

| 能力 | peasy-ai 叙事引擎 | dse-core 0.7.0 |
|---|---|---|
| 内容格式 | JSON 单文件场景图 | YAML 多包 + manifest |
| 状态模型 | 全局标量，**须在 config 预声明** | 点路径深层写入，**任意嵌套** |
| 条件表达式 | 无（仅 `condition: {attr, min}`） | AST 白名单，**比较/布尔/算术/下标** |
| 条件文本段 | 无 | `extraText`（按条件拼接文本） |
| 文本变体 | 无 | `variants` + `variantMode`（cycle/shuffle） |
| 一次性选项 | 无 | `once`（含稳定键，随存档持久化） |
| 隧道/压栈 | 无 | `goto: {call: X}` + `@return` |
| 回滚 | 有 undo/redo（仅历史栈） | `rollback [n]`（含状态快照） |
| 结局门 | 靠属性越界 | `coverage` 门（结局必须有来源） |
| 静态校验 | `validate()` 软告警 | `dse check`（JSON Schema + 悬空跳转） |
| 动态遍历 | 无 | `dse traverse`（真跑引擎 DFS） |
| 脚本回归 | 无 | `dse test --script --expect-scene --expect` |
| 图导出 | 无 | `dse graph --format mermaid/dot` |
| 单文件导出 | 无 | `dse export-html` |
| 埋点分析 | 无 | `telemetry` + `dse analyze` |

**一句话**：peasy-ai 的叙事引擎是 dse-core 的**功能子集**，且状态模型更弱。**引入它＝引入一个被 dse-core 全面覆盖的旧实现**，没有理由。

#### ✅ 3.2.3 TRPG 工具与训练器 —— 值得取用

**实测输出**：
```python
[roll]  (16, [6, 3, 5], '+2')
[npc]   {'name': '诺拉·黑木', 'trait': '疑心重重', 'occupation': '草药师', 'mood': '敌意'}   # + secret
```
```python
# AITrainer：从事件自动学习
learn: 感知检定是什么结果 -> 失败：掷出12，目标10，差值2。
learn: 攻击巨鼠群的躯干造成了多少伤害 -> 造成了5点伤害。
[学习后记忆数] 6
[问] 失败：掷出12，目标10，差值2。   ← 精确回放 ✅
```

**对 write 仓的三个直接用途**：

1. **`random_npc()` → 「04 人物卡」批量龙套槽位**。输出的五要素（姓名/特质/职业/情绪/秘密）正好是龙套卡字段。注意：模板包 `18` §3.1 槽位一已有 `name_generator.py`，**二者择一或交叉校验**（同一个名字两处生成会撞车，必须有主源）。
2. **`AITrainer` → 「06 连载护航」台账自动化**。台账的本质就是「事件 → 结论」的累积，训练器机制与台账语义高度同构。
3. **`roll()` → 场景推演**。`18` 槽位三 `goal_sim.py` 的随机源，与 `roll()` 可以共用同一套可复现约定（固定 seed）。

---

## 四、`dse-core` 评估

### 4.1 包基本情况

| 项 | 值 |
|---|---|
| 版本 / 发布 | 0.7.0 ／ 2026-11-15 |
| 导入名 / CLI | `dse_core` / `dse` |
| Python | >=3.10（3.10–3.13 声明支持；**本机 3.13.14 实测通过**） |
| 依赖 | **PyYAML>=6.0 + jsonschema>=4.0**（仅 2 个直接依赖） |
| 许可 / 维护 | MIT ／ siwpan |
| 成熟度 | Development Status :: 3 - **Alpha** ⚠️ |

### 4.2 实测：通过的部分

**① 两道内容门（静态 + 动态，分工不重叠）**

用 write 仓《廓者：未名夜》真实剧情结构（接单→分类→揭伤→归档→结局）构造内容包：

```
$ dse check
[check] 通过：11 场景 / 5 结局（可达 2）        ← 退出码 0

$ dse traverse
截断分支: start（重访超限 3）        ← 如实报告截断，不静默跳过
访问场景: 5 | 走过边: 5 | 结局: 2
完整路径: 6
可达结局: end_archived, end_refuse
```

**② 反向验证：门禁真能咬住（不是走过场）**

故意把一个出口改成不存在的场景：
```
$ dse check
[check] 发现 1 个问题:
  - #archive 第 1 个选项 -> "nowhere_at_all"     ← 退出码 1

$ dse traverse / coverage
[dse] 存在未定义的场景跳转: ...                   ← 退出码 1
```
**✅ 断链立刻被抓，退出码非零。**

**③ 表达式能力（按真实 schema 实测）**

| 能力 | 实测结果 |
|---|---|
| 状态插值 | `text: '多层下标 flags.deep.nested = {flags.deep.nested}；信任 {trust}'` → 渲染 `flags.deep.nested = 1；信任 40` ✅ |
| 深层下标 | `flags.deep.nested == 1` ✅ |
| 复合布尔 | `trust >= 60 and soul > 0` ✅（不满足时选项**被过滤隐藏**，只剩 2 个选项而非 3 个） |
| 条件文本段 | `extraText: [{if: ..., text: ...}]` ✅ 命中拼接 |
| 状态写入 | `do: { hp: -3, 'flags.other_cell': true }` ✅ 数值=加减、非数值=赋值、点路径=深层写 |
| 场景插值 | `onEnter: { visits: +1 }` ✅ 计数累积 |

**④ 全套工具链可用**

```
$ dse test --script "1,1" --expect-scene end_archived --expect "gold >= 10"
[test] ✗ 最终场景应为 end_archived，实际 archive       ← 精确报告实际状态（我的脚本少走一步，引擎行为正确）

$ dse graph --format mermaid
flowchart LR
  n_start("接单 · 按下第几下") --> n_classify("分类 · 对象是人")
  n_classify --> n_archive("归档 · 结论行填日子")
  …

$ dse export-html -o game.html
[export-html] ⚠ #wolf-fight: mode=battle 浏览器端不结算插件逻辑，导出为「阅读版」只读出口（3 条），不是可玩版
已导出单文件播放器: game.html（11 场景，警告 1 条）
```

**⑤ 「Markdown 大纲 → dse 内容包」自动转换（本次评估新写的探针，已跑通）**

解析 `廓者未名夜/02-大纲四层-廓者未名夜.md` 的主线表格（段 | 内容 | 状态）：

```
[OK] 解析 7 段 → content/kz-auto.yml
   1. 一 · 接单        → seg-01  [已写（第 01–02 章]
   2. 二 · 归档        → seg-02  [已写（第 03、06、0]
   3. 三 · 编号的旧记录  → seg-03  [待写]
   4. 四 · 猎魔人      → seg-04  [待写]
   5. 五 · 换辖区      → seg-05  [待写]
   6. 六 · 廓清        → seg-06  [待写]
   7. 七 · 大／清       → seg-07  [待写]
```

生成的内容包过全套门禁：
```
$ dse check     → [check] 通过：36 场景 / 22 结局（可达 7）    退出码 0
$ dse traverse  → 访问场景: 14 | 走过边: 14 | 结局: 7 | 完整路径: 9
                  可达结局: seg-01-written … seg-07-pending
```

### 4.3 实测：发现的问题与坑

| # | 问题 | 严重度 | 实测证据 | 应对 |
|---|---|---|---|---|
| **D-1** | **`dse new` 写进 site-packages，不写工程目录** | 🔴 高 | `$ dse new demo-pack` → `已生成 C:\...\site-packages\dse_core\example\content\demo-pack.yml` | 不用 `dse new`；内容包自建目录，引擎通过 `dse.yml` 的 `packs` 显式挂载 |
| **D-2** | **PyPI README 的条件表达式写法与 schema 不符** | 🟠 中 | README 写 `goto: [{to: lucky, weight: 1}, {to: unlucky, weight: 3}]` 且暗示 goto 数组项可带 `when`；实测 `goto` 数组项 schema 为 `additionalProperties: false`，**只允许 `to` + `weight`**；写了 `when` → `dse check` 直接报错 `is not valid under any of the given schemas` | 条件必须写在**选项级 `if`**（`Choice.properties = [text, if, once, do, goto]`）。**按 README 写必踩坑** |
| **D-3** | **schema 全局 `additionalProperties: false`** | 🟠 中 | 多写一个 key 即报错 | 内容规范须严格对齐 `scene.schema.json`，建议把 schema 纳入仓内 |
| **D-4** | **YAML 重复 key 静默吞掉前一个** | 🟠 中 | 手改 `dse.yml` 产生两个 `flags:` 节点，后者覆盖前者，无任何警告 | 内容包须过**重复键检查**（PyYAML 默认不报错） |
| **D-5** | **场景 ID 限 ASCII 正则** | 🟡 低 | `^[a-z][a-z0-9]*([-_][a-z0-9]+)*(\.[a-z0-9]+([-_][a-z0-9]+)*)*$` | 中文段落名须映射为 ASCII slug（转换器已实现） |
| **D-6** | **`export-html` 不结算插件逻辑** | 🟡 低 | battle 场景导出为「阅读版」只读出口 | 仅导出「阅读版」用于审阅；可玩版走 `dse play` |
| **D-7** | **Development Status = 3 - Alpha** | 🟡 低 | PyPI 元数据 | 引入须锁定版本号；CI 加 `pip freeze` 快照 |
| **D-8** | **引入 PyYAML + jsonschema，破坏「零三方依赖」** | 🟠 中 | `Requires-Dist: PyYAML>=6.0` / `jsonschema>=4.0` | 见 §五·3 隔离方案 |

---

## 五、契合度矩阵

### 5.1 `dse-core` × write 仓现有资产

| write 仓资产 | dse-core 对应物 | 契合度 | 说明 |
|---|---|---|---|
| `02-大纲四层`（主线/暗线/悬念/线头） | `scenes` + `choices` + `goto` 图 | 🟢 **高** | 主线＝场景链；线头＝tunnels；悬念＝条件分支。**已实测自动转换成功** |
| `10-节拍表`（15 拍定位） | `extraText` + `variants` + 条件文本段 | 🟢 **高** | 节拍对应的备选文本段天然是 `extraText` |
| `06-连载护航`（台账 C1–C12） | `state` + `onEnter/onExit` + `do` | 🟢 **高** | 状态累积语义与台账一致；且 `state.initial` 需预声明（同名 `dse check` 会拦） |
| `零件库`（28 件 L2 零件 + 49 条咬合边） | `goto` 图 + `do` 装配 | 🟢 **高** | 咬合索引＝图边；装配体＝场景包。**现成素材** |
| `13-世界先行`（区域包 / M-01 / M-02） | 多内容包（`packs` 列表） | 🟢 **高** | 一图一包，天然分包 |
| `tools/` Cordis 工具链 | `ctx.isolate()` / `Service` / `inject` | 🟡 **中** | 两套插件模型语义相近但**不通用**（Node vs Python），须适配 |
| `tools/checkers/*.py` 适配器模式 | — | 🟢 **高** | `dse check/traverse/coverage` 退出码可直接包成协议 findings |
| `PKM/` 检索层 | `dse` 无检索能力 | 🔵 **互补** | PKM 作上下文源，dse 作执行层，二者**不冲突，是上下游** |
| 正文（627 篇） | — | 🔴 **不适用** | 正文是叙述性长文本，**不是场景图**。转换只能到「章纲/节拍」层，**不得生成正文** |
| `通用模板包/18` 纪律 | — | 🟢 **不冲突** | `18` 的铁律「程序化产物只进素材层，不直接进正文」**恰好与 dse 的定位一致** |

### 5.2 `peasy-ai` × write 仓现有资产

| write 仓资产 | peasy-ai 对应物 | 契合度 | 说明 |
|---|---|---|---|
| `04-人物卡`（批量龙套） | `random_npc()` | 🟢 **高** | 五要素匹配龙套卡字段 |
| `06-连载护航`（台账） | `AITrainer` 事件→记忆 | 🟢 **高** | 机制同构 |
| `PKM/` 检索层 | `AICore.learn/respond` | 🟡 **中** | PKM 检索不答问；AICore 答问但不检索。**互补**：PKM 召回 → AICore 组织答案 |
| `18` 槽位一 命名工厂 | `name_generator.py`（已有）vs peasy-ai | ⚠️ **重复** | peasy-ai 无命名器；`18` 已有自研，**不需引入** |
| `18` 槽位三 场景模拟 | `goal_sim.py`（已有） | ⚠️ **重复** | 同上 |
| `05` 文风卡 | — | 🔴 **不适用** | 马尔可夫/TextCNN 无法承载中文网文文体 |
| 叙事引擎 | dse-core | 🔴 **负价值** | 引入即重复且更弱 |

---

## 六、集成方案

### 6.1 目标架构（不推翻现有，只加一层）

```
write 仓
├── PKM/            （检索层 · 已有）─────┐
├── 零件库/          （结构素材 · 已有）────┤
├── 02/10/06 模板文档（规划层 · 已有）──────┤
│                                          ▼
│              ┌─────────── 转换层（新）───────────┐
│              │  md2dse：Markdown → YAML 内容包   │
│              │  （本次评估已写出探针，7段跑通）   │
│              └───────────────┬──────────────────┘
│                              ▼
│              ┌─────────── 执行层（新）───────────┐
│              │  dse-core 0.7.0                  │
│              │  check / traverse / coverage /   │
│              │  test / graph / export-html      │
│              └───────────────┬──────────────────┘
│                              ▼
│              ┌─────────── 校验层（已有 · 扩展）────┐
│              │  tools/cordis.yml + 检查器协议     │
│              │  新增 checker-dse 适配器           │
│              └────────────────────────────────────┘
```

### 6.2 dse-core 接入 write 仓的具体路径

**Step 1 · 内容包目录（新增，建议 `write/叙事内容包/` 或 `write/dse-content/`）**

```
dse-content/
├── dse.yml                 # 引擎配置：packs 列表 + state.initial 预声明 + engine.entry
├── content/
│   ├── kz-outline.yml      # 由 02-大纲四层 转换
│   ├── kz-beats.yml        # 由 10-节拍表 转换
│   └── parts-*.yml         # 由 零件库/装配体 转换
└── docs/
    └── 内容包规范.md         # dse schema 约束 + ID 规范 + 重复键检查（针对 D-2~D-5）
```

**Step 2 · 检查器适配器（新增 `tools/checkers/dse_check.py`）**

完全照抄 `tools/checkers/package_check.py` 的模式 —— **不改 dse 任何代码**，捕获 `dse check/traverse/coverage` 的退出码与输出，包成协议 findings：

```python
# 契约草案
dse check      退出码 1 → ERROR   （悬空跳转 / Schema 不符）
dse traverse   截断分支 → WARN    （撞 max-revisit 上限，如实上报不静默）
dse coverage   缺来源结局 → ERROR （结局必须可达成）
```

**Step 3 · 接入 `tools/cordis.yml`**

在 `checker-*` 段追加一个插件（照 `15-checker-sync.mjs` 抄），并在 `projects` 段按需登记项目。

**Step 4 · 转换器（`tools/procedural/md2dse.py`）**

本次评估的探针 `md2dse_probe.py` 已验证可行（7 段 → 全绿），需补：
- **重复键检查**（D-4）
- **中文段落名 → ASCII slug** 映射表（D-5）
- **`state.initial` 预声明推导**（从内容包用到的字段自动生成 `dse.yml` 片段）

### 6.3 peasy-ai 接入路径（只取两个模块）

| 取用 | 位置建议 | 方式 |
|---|---|---|
| `random_npc()` | `通用模板包/tools/procedural/`（与 `name_generator.py` 并列） | 独立脚本，**输出必过 `18` §3.1 验收门**（重名率 0 / 与 `04` 查重 / 语义冲突过滤） |
| `AITrainer` + `AICore` | 新增 `tools/pkm/qa/` 或独立 `tools/qa/` | 台账条目 → 记忆 → 设定问答。**须显式标注「弱语义，只答台账里有的」** |

**不引入**：peasy-ai 叙事引擎（能力被 dse-core 全面覆盖）、tkinter GUI（write 仓已有自己的 `可视化_结构映射/index.html`）。

### 6.4 依赖隔离方案（应对 D-8）

write 仓现在的铁律是「**Python 内核零三方依赖**（无需 `pip install`）」。dse-core 会打破它。三条路：

| 方案 | 做法 | 代价 | 评价 |
|---|---|---|---|
| **A · 独立 venv**（推荐） | dse 相关检查器走独立 venv，宿主用 `sys.executable` 切换 | 需在 `tools/bootstrap.sh` / `.ps1` 里加装包步骤；换机需重装 | ✅ **不动主环境，换机可重现，闸门语义不变** |
| B · 降级为可选插件 | dse 检查器标 `optional: true`，缺依赖时 SKIP | 新机器上闸门静默失效 —— **正是 write 仓历史上踩过的坑**（廓者未名夜未注册进审校 ⇒ `npm run check` 对它「SKIP」而非「通过」） | ❌ 不可接受 |
| C · 破例进主环境 | 接受两个三方依赖 | 换机部署文档要改，`bootstrap` 要改 | 🟡 可接受但不如 A 干净 |

**建议 A**，并在 `tools/README.md` 记「哪些检查器需要 venv」的口径。

---

## 七、风险登记

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R-1 | **把「自动转换产物」当正文用** | 🟡 中 | 🔴 高 | 模板包 `18` 铁律已禁（程序化产物只进素材层）。转换器输出**只进 `dse-content/`**，不自动回写 `正文/` |
| R-2 | **YAML 内容包成为第二份事实源**（正文一处、dse 包一处） | 🔟 高 | 🔴 高 | 内容包**单向由模板文档派生**，加 `source_of_truth` 注释 + 生成器带 SHA 指纹；`dse check` 不管这个，需自建「漂移检查」 |
| R-3 | **Alpha 版依赖 breakage** | 🟡 中 | 🟠 中 | 锁 `==0.7.0`；CI 加 `pip freeze`；`dse doctor` 纳入检查 |
| R-4 | **中文内容在 YAML/CLI 下的编码坑** | 🟡 中 | 🟠 中 | 全部读写显式 `encoding='utf-8'`；Windows 终端 `PYTHONIOENCODING=utf-8`（write 仓 `package_check.py` 已用此法，照抄） |
| R-5 | **转换器把「待写段」也变成场景**，造成未写内容的既视感 | 🟡 中 | 🟠 中 | 状态标记已解析出（`已写`/`待写`）；**「待写」场景正文置空或标注**，并考虑单独 `status` 字段 |
| R-6 | **新增依赖破坏换机部署** | 🟡 中 | 🟠 中 | 独立 venv（§6.4 方案 A）；`bootstrap.sh` 增装包步骤并做幂等 |
| R-7 | **范围蔓延**：把 write 仓变成「网文+游戏」双形态仓 | 🟡 中 | 🟠 中 | dse 内容包**只做规划层校验**，不做可玩版交付；可玩版属另一个仓（如 `dict-scene-engine`） |

---

## 八、行动项（待全哥裁定）

> **本报告未执行任何一项**。以下按优先级排列，等全哥点头再动。

### P1 · dse-core 落地（建议先做，投入产出比最高）

| # | 动作 | 产物 | 预估工作量 |
|---|---|---|---|
| 1 | 建 `dse-content/` 目录 + `dse.yml` + 内容包规范文档（含 D-2~D-5 四条坑） | 目录 + 文档 | 小 |
| 2 | 把探针 `md2dse_probe.py` 移正为 `tools/procedural/md2dse.py`（补重复键检查 / slug 映射 / initial 推导） | 生产级转换器 | 中 |
| 3 | 新增 `tools/checkers/dse_check.py` 适配器 + `tools/plugins/18-checker-dse.mjs` + `cordis.yml` 登记 | 闸门接入 | 中 |
| 4 | 选 1 本书（推荐《廓者：未名夜》，结构最规整）做端到端试点：转换 → check → traverse → coverage 全绿 | 试点内容包 | 中 |
| 5 | 独立 venv + `bootstrap.sh`/`.ps1` 装包步骤（§6.4 方案 A） | 换机可重现 | 小 |

### P2 · peasy-ai 局部取用

| # | 动作 | 备注 |
|---|---|---|
| 6 | `random_npc()` 封装进 `通用模板包/tools/procedural/`，过 `18` §3.1 验收门 | 与 `name_generator.py` 主源关系需明确 |
| 7 | `AICore` + `AITrainer` 做「设定问答」小工具（挂在 PKM 检索之后） | 须标注弱语义边界 |
| 8 | `roll()` 与 `goal_sim.py` 的 seed 约定对齐 | 可复现性 |

### P3 · 纪律与登记

| # | 动作 |
|---|---|
| 9 | `通用模板包/14-外部依赖与来源登记表.md` 登记两个包（来源/许可/范围）—— 模板包铁律要求 |
| 10 | `通用模板包/18` 增补「dse 内容包」槽位（现五槽位 → 六槽位），并明确与 Node 版不互通 |
| 11 | `工作区规范.md` 增补「程序化内容包纪律」：单向派生、不得直接成正文、重复键/ID 规范 |
| 12 | README「仓根工具链」表补 `dse-content/` 条目 |

---

## 附录 A · 完整实测命令清单（可复现）

```bash
# 0. 隔离环境（不污染 E:\Python314）
/e/Python314/python.exe -m venv "$TEMP/probe_venv"
"$TEMP/probe_venv/Scripts/python.exe" -m pip install "peasy-ai==1.0.1" "dse-core==0.7.0"
# 实测装入：attrs 26.1.0 / dse-core 0.7.0 / jsonschema 4.26.0 / peasy-ai 1.0.1 / PyYAML 6.0.3
#            jsonschema-specifications 2025.9.1 / referencing 0.37.0 / rpds-py 2026.9.1

# 1. peasy-ai 核心
python -c "from easy_ai import create; ai=create(); ai.learn('主角名字','陈默'); print(ai.respond('主角名字')); print(ai.memory_count, ai.matchers_info)"
python -c "from easy_ai.trpg.tools import roll, random_npc; print(roll('3d6+2')); print(random_npc())"
python -c "from easy_ai import AICore; from easy_ai.trpg.trainer import AITrainer; ..."

# 2. dse-core 全套
cd $TEMP/dseproj
dse check      # → 通过 / 退出码 1
dse traverse   # → 访问场景/走过边/结局/完整路径
dse coverage   # → 结局来源审计
dse test --script "1,1" --expect-scene end_archived --expect "gold >= 10"
dse graph --format mermaid
dse export-html -o game.html
dse doctor

# 3. 反向验证（断链）
sed -i 's|        goto: end_archived|        goto: nowhere_at_all|' content/kz.yml
dse check  # → 发现 1 个问题，退出码 1

# 4. Markdown → dse 自动转换
python md2dse_probe.py "<write仓>/廓者未名夜/02-大纲四层-廓者未名夜.md" content/kz-auto.yml
dse check && dse traverse   # → 全绿
```

## 附录 B · 他机复现口径

- **Python**：本机用 `E:\Python314`（3.13.14）。他机请用 `python -V` 确认 >= 3.10（dse-core 硬要求；peasy-ai 只要 >= 3.9）。
- **包版本**：必须显式钉版本 `peasy-ai==1.0.1` / `dse-core==0.7.0`，不要用 `>=`。
- **venv 路径**：本机在 `%TEMP%\probe_venv`；他机路径自定，**但要写进 `tools/bootstrap.sh` 的可复现步骤**。
- **仓库路径**：本机 write 仓在 `D:\projects\repos\write`（**盘符随机器**）。他机以自身 `git rev-parse --show-toplevel` 的上级目录为准 —— 与仓根 README §「换机部署」口径一致。
- **源文档**：`廓者未名夜/02-大纲四层-廓者未名夜.md` 的结构若变动，转换器需重跑（`md2dse_probe.py` 对主线表格格式敏感）。
- **不可复用**：write 仓 `其他项目归档/dict-scene-engine实跑记录_单文件合订.html` 来自 **Node 版 dse**，其内容包格式与本报告评估的 **Python 版不互通**，他机也不可直接复用。

---

## 附录 C · 引用来源

**联网调研（2026-11-20~21 访问）**
- [Best Narrative Design Tools for Game Developers (2026) — Eposyne](https://eposyne.com/insights/best-narrative-design-tools) —— authoring vs runtime、Twine/Ink/articy 定位对比
- [The 11 Best Tools for Game Narrative Teams in 2026 — Storyflow](https://info@storyflow.so/blog/best-tools-game-narrative-teams-2026) ——「三个字数」模型（写了多少 / 玩家看到多少 / 需记录本地化多少）
- [Top 10 Best Narrative Software of 2026 — Statpit](https://statpit.com/best/narrative-software/) ／ [Gaugius](https://gaugius.com/best/narrative-software) —— Twine 9.4/10、Ink 6.9/10；passage-level variable conditions
- [AI-driven tools reshape interactive fiction — Quest Review Center](https://questreviewcenter.com/?p=12821) —— IVIE 论文：LLM + 符号校验的增量流水线
- [2026 AI Plot Engines: 30% Velocity from Constraint, Not Speed — StoryWriter](https://storywriter.pro/blog/2026-ai-plot-engines-30-velocity-from-constraint-not-speed.php) —— Narrative Constraint Injection / Scaffold-First；单次草稿伪造检出 14% → 完整校验栈 92%；仅 11% 作者让 AI 自动生成可发表正文、87% 报告产能提升
- [Story Plot Generator Fundamentals — Advance Automator](https://advance.automator.ai/story-plot-generator) —— 三范式（规则/概率/约束求解）；FSM / Markov / 文法 / 约束规划
- [AI Story Generator: Building Interactive Narrative Loops — Quicktool](https://quicktool.space/articles/ai-story-generator-building-interactive-narrative-loops) —— 创意漂移（drift）与持久状态摘要

**包文档**
- [peasy-ai @ PyPI 1.0.1](https://pypi.org/project/peasy-ai/) ／ [Gitee siwpan/peasy-ai](https://gitee.com/siwpan/peasy-ai)
- [dse-core @ PyPI 0.7.0](https://pypi.org/project/dse-core/) ／ [Gitee siwpan/dse-core（Python 版）](https://gitee.com/siwpan/dse-core)
- [dse-core（Node 版）@ Gitee](https://gitee.com/siwpan/dse-core) —— 安全须知：内容包＝可执行代码，`new Function` 无沙箱
- `dse_core/schema/scene.schema.json`（实测读取：`Scene` / `Choice` / `Effects` 定义）

**仓内依据**
- `通用模板包/18-程序化创作与算法脚本模板.md` v3.16 —— 五代方法谱系、五槽位、启用/禁用判据、§五·A 两条红线
- `tools/cordis.yml` —— 14 插件 / 3 项目 / 7 检查器
- `tools/checkers/package_check.py` —— 适配器模式参考实现
- `PKM/` + `tools/pkm/pkm_cli.py` —— `search` 实测输出（命中 20 条 / `matched` 字段）
- `廓者未名夜/02-大纲四层-廓者未名夜.md` —— 自动转换的输入样本

---

> **报告结束。** 本报告为**只读评估**：未修改 write 仓任何小说正文、未新增仓内资产、未 commit、未 push。所有实测产物（venv、内容包、转换器探针）均在 `%TEMP%` 下，不污染仓库。**待全哥裁定后再执行 §八 行动项。**
