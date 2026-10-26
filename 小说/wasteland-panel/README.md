# wasteland-panel · 废土旅法师设定面板

《废土旅法师》正史（231 篇 / 745,786 字）的设定检索工作台 **+ 可玩的 D20 遭遇战沙盘**。  
Cordis 插件式 Node 宿主 + 零三方依赖 Python 引擎 + 静态前端。

---

## 一、快速开始

```bash
pip install allin-engine         # 战斗沙盘的唯一运行时依赖（D20 规则内核）
node server/cli.mjs reparse      # 重建数据层（改了 bible 之后必跑）
node server/host.mjs             # 启动面板 → http://127.0.0.1:8777
node server/cli.mjs selfcheck    # 数据层体检
node server/cli.mjs --help       # 全部子命令
```

> **不装 `allin-engine` 也能跑**：设定检索、一致性扫描、伏笔台账全部照常工作，
> 只有「战斗沙盘」会明确报「D20 内核不可用」而不静默降级。
> Python 解释器由 `plugins/01-config.mjs` 自动发现，**venv 优先于裸解释器**
> ——否则会 import 得到裸解释器、静默 ImportError，属于最难排查的那类问题。

CLI 与 host 解析出的Python 解释器**保证是同一个**（cli 直接复用  
`plugins/01-config.mjs` 导出的 `findPython`，不做第二份实现）。

## 二、目录职责

| 路径                              | 职责                                                 |
| ------------------------------- | -------------------------------------------------- |
| `server/host.mjs`               | Cordis 宿主，装配 `server/plugins/`                     |
| `server/cli.mjs`                | 零依赖命令行，与 host 共用配置真理源                              |
| `server/plugins/01-config.mjs`  | **全应用唯一的路径/端口真理源**                                 |
| `server/plugins/02-engine.mjs`  | 拉起并管理 Python 子进程（JSON-RPC stdio）                   |
| `server/plugins/03-dataset.mjs` | 数据层新鲜度判定，必要时提示 reparse                             |
| `server/plugins/04-web.mjs`     | HTTP 服务与静态资源                                       |
| `engine/bible_parser.py`        | 把 bible/ 解析成 `engine/data/dataset.json`            |
| `engine/rpc_server.py`          | JSON-RPC 方法表（codex.* / panel.* / trpg.* / scan.\*） |
| `engine/panel_engine.py`        | 面板机制计算（解锁、代价弧、TRPG 检定…）                            |
| `engine/data/dataset.json`      | 生成产物，不手工编辑                                         |
| **`engine/d20_bridge.py`**      | **D20 内核适配层：废土五维→D20 六属性映射、角色构建、战技/法术表** |
| **`engine/bestiary_combat.py`** | **异族 stat block：谱系骨架自动生成 + 9 种具名覆盖**         |
| **`engine/combat_engine.py`**   | **回合制战斗：先攻/命中/伤害/状态/死亡/火花回写 + 落盘**        |
| **`engine/campaign.py`**        | **战役层：跨场保留 HP/法力/灰线/火花 + 卷级遭遇链 + 休整/汲取** |
| `engine/data/bestiary_combat.json` | 具名异族覆盖表，**可手改**（`_comment` 键会被跳过）      |
| `engine/data/combat_state.json` | 进行中战斗的存档（含 rng 状态），`combat.end` 后移除         |
| `engine/data/campaign.json`     | 战役存档（跨场状态 + 链进度），服务重启后自动恢复             |
| `web/combat.js`                 | 战斗沙盘前端（零依赖，只发指令 + 渲染，不自算战斗数值）        |
| `web/campaign.js`               | 战役推进前端（跨场状态 + 遭遇链；对轰仍在战斗沙盘页打）      |
| `web/`                          | 其余静态前端                                           |

## 三、路径可移植化约定（硬要求）

**源码里不得出现任何盘符绝对路径。** 三处曾经写死过，全部已改：

| 位置                       | 旧写法                                                        | 现方案                                                                       |
| ------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| `plugins/01-config.mjs`  | `C:\Users\Administrator\Desktop\小说`                        | `BIBLE_ROOT` 环境变量，默认 `path.resolve(ROOT, '..')`                           |
| `plugins/01-config.mjs`  | `…\.workbuddy\binaries\python\versions\3.13.12\python.exe` | glob 展开 `~/.workbuddy/binaries/python/versions/*`，取版本号最高者；`PYTHON` 环境变量优先 |
| `engine/bible_parser.py` | `DEFAULT_ROOT = Path(r"C:\…")`                             | `_default_root()` 从 `__file__` 上溯两级；`BIBLE_ROOT` 可覆盖                      |

环境变量：`BIBLE_ROOT`（小说根目录）、`PYTHON`（解释器）、`PORT`、`HOST`。

换机/ 换盘 / 整仓搬迁时，只要环境对了就能跑；**环境不对时应当报"找不到"，而不是静默用旧路径**。

## 四、数据层

`bible_parser.py` 把下列源文件解析为 `dataset.json`（当前 `ok=19 degraded=0 failed=0`）：

| 源                       | 产物键                              | 条数                   |
| ----------------------- | -------------------------------- | -------------------- |
| `bible/world-bible.md`  | `panel` / `creatures` / `planes` | 面板系统、9 种变异生物、6 层位面   |
| `一致性核查/世界观设定标尺.md`      | `rules` / `leakLines`            | R1–R15、5 条权限红线       |
| `bible/plot-board.md`   | `plotThreads`                    | 42 条伏笔/线头/事件         |
| `设定与参考/长弧规划.md`         | `costArc`                        | 代价弧四维 + 已烧清单         |
| `设定与参考/扩写规范-统一执行手册.md`  | `terminology`                    | 10 条术语锁定             |
| `bible/timeline.md`     | `timeline`                       | T1–T224（119 个事件条目）   |
| `一致性核查/角色档案.md`         | `characters`                     | 11 人 —— **旧版，停在第一卷** |
| `bible/characters/*.md` | `characterCards`                 | **19 张角色卡（权威源）**     |

### characters 与 characterCards 的区别（重要）

- `codex.characters` 读的是 `一致性核查/角色档案.md`，只有第一卷的 11 人。
- `codex.characterCards` 读的是 `bible/characters/` 目录，19 张，  
  含第五卷新角色（陆平、王级异族、花押主人、誊抄人、黑石帮抱臂者、李氏残余）  
  与每张卡的**外传适配评级 / 写作纪律条数 / 关键行为幕数**。

**外传相关的一切工作以后者为准。** `selfcheck` 会分别报出  
`characters` 与 `characterCards` 两个计数，别看错。

## 五、常用 RPC

```bash
node server/cli.mjs codex characterCards     # 19 张角色卡
node server/cli.mjs codex plot               # 伏笔台账
node server/cli.mjs codex rules              # R1-R15
node server/cli.mjs call codex.characterCards
```

新增 RPC 方法时同步更新 `rpc_server.py` 文件头的方法清单表——  
那份表是自文档，漏改会让下一个人以为方法不存在。

## 六、战斗沙盘（新增）

把「面板数值」变成**能掷出来的遭遇战**：选剧情档位 → 配异族 → 逐回合行动 → 结算 → 生成可粘正文的叙事文本。

### 剧情档位（PC 战力锚点）

| key            | 出处                 | 火花  | 实测战力               |
| -------------- | ------------------ | --- | ------------------ |
| `v1-seed`      | 第一卷·火种期初启（第 5 章）  | 4%  | 近战 +2 / HP 12     |
| `v2-gray`      | 第二卷·灰线初现（第 40 章）  | 25% | 近战 +8 / HP 34     |
| `v3-mycelium`  | 第三卷·菌丝与合围（第 91 章） | 58% | 近战 +10 / HP 70    |
| `v5-ignited`   | 第五卷·点燃之后（第 141 章） | 100% | 近战 +16 / HP 163 / AC 25 |

### 异族分级与火花产出

| 档位        | HP  | AC | 攻击   | 伤害       | 定位    |
| --------- | --- | -- | ---- | -------- | ----- |
| 零级        | 5   | 10 | +1   | 1d4      | 背景板  |
| 一级        | 12  | 12 | +3   | 1d6+1    | 遭遇   |
| 二级        | 28  | 14 | +6   | 1d8+2    | 硬战   |
| 三级        | 60  | 16 | +9   | 2d6+3    | 搏命   |
| 王级        | 160 | 18 | +16  | 2d10+6   | 不可交战 |
| 坠影级（S+）  | —   | —  | —    | —        | **送终**：不可击杀取火花，开局时被 `spawn_group` 跳过 |

9 种具名异族带特性覆盖（广东双马尾甲壳再生 HP×1.5、巨蝎关节缝 AC-2、
三头秃鹫三头齐喙 2 次攻击、掘地者先攻+3、变异鬣狗脊背菌丝节点 ×2 等），
改 `engine/data/bestiary_combat.json` 即可微调，无需动代码。

### 废土机制已接进战斗循环

- **火花回写**：异族死亡按谱系产火花 → 回写面板（**点燃后不再增长，R8**）。
- **结构税**（R13）/ **灰线爆发**（R11 单调递增，不回退）/ **黑色代偿**（R9）。
- **五色法力池**：火球术→红 3 环「赤焰爆发」、闪电束→蓝 3 环「电离长矛」、
  寒冰锥→蓝 5 环「霜蚀锥」、魔法飞弹→白 1 环「辉光弹」、治疗言灵→绿 1 环「生息言灵」。
- **弱点解析**：必须先用 `analyze` 做侦察/洞察检定（DC 按变异等级），
  **成功前弱点伤害不生效**——把正文里"找弱点"变成可掷的一步。

### 开局语义：选档即重开

`combat.new` 传 `profile` 时，**火花/点燃/灰线/卷号一律回到该档初值**；
要跨场累积需显式传 `carryOver: true`（前端「接续上一场」复选框）。
否则同一 sid 的 panel 状态会串场，出现「选了第三卷档位、火花却显示上一场的 14%」。

### CLI

```bash
node server/cli.mjs pc profiles
node server/cli.mjs pc build --profile v3-mycelium
node server/cli.mjs pc maneuvers --profile v3-mycelium
node server/cli.mjs combat catalog
node server/cli.mjs combat new --profile v3-mycelium \
      --enemies '[{"name":"变异鬣狗","count":2},{"name":"广东双马尾","count":1}]' --seed 20261003
node server/cli.mjs combat state
node server/cli.mjs combat act --action analyze --target 变异鬣狗#1
node server/cli.mjs combat enemies      # 推进异族回合
node server/cli.mjs combat auto         # 自动打完（PC 用简单策略）
node server/cli.mjs combat narrate      # 生成可粘正文的叙事段落
node server/cli.mjs combat end
```

### D20 内核边界（实测，勿凭直觉改）

| 现象              | 事实                                        |
| --------------- | ----------------------------------------- |
| 属性下限           | **不能低于 10**（本书五维 4 起步，内核 10 起步，斜率 0.65 映射）  |
| HP              | 由「活力」技能推导——**不买活力则 max_hp=0**            |
| `combat_macro()` | 返回**字符串**，没有结构化字段，命中/伤害由本层自己算            |
| 内核 `hp()`      | 返回**满血值**，受伤后不变，不能当当前血量用                 |
| 法术位             | 需「奥术施法」≥1 才有                              |
| Python API      | **snake_case**（`max_hp` / `attack_bonus()` / `slot_table()`），不是 TS 版的 camelCase |

## 七、战役推进（跨场状态）

`combat.*` 是**单场**的：开局满血、法力从档位初值起、打完就散。
`campaign.*` 把它串成一条线——**带着上一场的伤走进下一场**。

### 跨场保留什么

| 状态           | 行为                                        |
| ------------ | ----------------------------------------- |
| 生命           | **跨场保留，不自动回满**                              |
| 五色法力池        | 跨场保留（绿法术才能真正当补给用）                         |
| 灰线           | 跨场保留，且**只增不回退**（R11）                       |
| 火花 / 点燃      | 跨场累积，点燃后封顶（R8）                            |
| 虚空耐受 / 黑色代偿档 | 随卷联动                                      |

火花涨 → `wl2rank` 技能等级涨 → **生命上限也涨**（实测第三卷链：70 → 90 → 101）。
上限变高时当前生命**不补满**——伤就是伤。

### 战间恢复只有两条路

设定里没有成文的「休息回血」，故只开了两条：

1. **休整**：恢复 25% 生命上限，灰线不回退（R11），法力不恢复。可重复。
2. **治疗言灵**：绿 1 环，耗 1 点绿法力（战斗内外都能用）。
   **第三卷及更早的档位没学会这个技术**——法术要等点燃前后才点亮，会被明确拒绝。

法力补给走**汲取**：+1 点指定色，**灰线 +1 格**——污染加深才扛得住更多（R11）。
黑色法力不能汲取：它烧的是记忆/情感碎片，不可复原（R9）。

### 预置卷级遭遇链

| key            | 链                          | 收尾            | 整链通关率（20 种子） |
| -------------- | -------------------------- | ------------- | ------------ |
| `v1-seed`      | 第一卷 · 火种期（第 5–39 章）      | 巨蝎（45%）      | **5/20（25%）** |
| `v2-gray`      | 第二卷 · 灰线初现（第 40–90 章）    | 三头秃鹫 + 一级×2（35%） | **9/20（45%）** |
| `v3-mycelium`  | 第三卷 · 菌丝与合围（第 91–140 章）  | 三级母体 + 二级（75%） | **16/20（80%）** |
| `v5-ignited`   | 第五卷 · 点燃之后（第 141 章起）     | 王级（100%）      | **20/20（100%）** |

每场的实测胜率写在 `engine/campaign.py` 的 `winrate` 字段里，前端选链时会显示。
**越早期越难通关**——面板刚亮时打什么都拼命，成长兑现后才谈得上碾压。
这个曲线是调过的：第一版 v1 链放了「广东双马尾×2」，实测第一场就大概率团灭，战役根本推不动。

链的敌人名只用**能精确解析**的：具名用 JSON 完整键，杂兵用档位名（零级/一级/二级/三级）。
像「变异鼠」这种只存在于组合键「变异蜥蜴 / 巨型蜈蚣 / 变异鼠」里的简称，
会被 `make_enemy` 兜底成一级（HP12/AC12/+3）——实测胜率从预期的零级水平直接掉到 0/20。

第四卷暂无剧情档位预设（`PROFILES` 里只有 v1/v2/v3/v5 四档），
**不为此虚构数值**——缺哪一档就是缺哪一档，报清楚比编一个强。

随时可 `campaign.insert` 自由插入一场（不计入链进度，插在下一场之前）。

### CLI

```bash
node server/cli.mjs campaign chains
node server/cli.mjs campaign new --chain v3-mycelium --seed 20261004
node server/cli.mjs campaign state
node server/cli.mjs campaign next                       # 开下一场（PC 沿用跨场状态）
node server/cli.mjs combat auto                         # 在战斗沙盘里打
node server/cli.mjs campaign apply                      # 收回结果 + 推进链
node server/cli.mjs campaign rest                       # 休整
node server/cli.mjs campaign heal                       # 治疗言灵（绿 -1）
node server/cli.mjs campaign draw --color 绿             # 汲取，灰线 +1
node server/cli.mjs campaign insert --enemies '[{"name":"二级","count":2}]'
node server/cli.mjs campaign end
```

### 实测：第三卷链（seed 20261004，场间休整）

| 场次   | 遭遇         | 开局      | 结果  | 剩血   | 火花    |
| ---- | ---------- | ------- | --- | ---- | ----- |
| 1    | 菌丝带 · 脊背节点 | 70/70   | 胜   | 49   | 85%   |
| 2    | 塌陷区 · 寄生体  | 70/90   | 胜   | 55   | 100%  |
| 3    | 巢穴 · 三级母体  | 90/101  | 胜   | 84   | 100%  |

生命上限随火花涨（70 → 90 → 101），**上限涨了也不补满**——伤就是伤。
不打休整直接连打会明显吃力，战役张力就在这里。

状态落 `engine/data/campaign.json`，**服务重启后自动恢复**。

## 八、已知坑位

- **章号连续性检查**：必须按章号**数值**排序。按字符串排会让「第100章」  
  排在「第91章」前，误报 GAP。
- **标题一致性检查**：正文标题用汉字数字（「第一百四十一章」），  
  用阿拉伯数字去正则匹配会全量误报。需要`cn2int()` 逐字转换。
- **数据层新鲜度**：角色卡是**目录**，不能塞进文件 mtime 列表——  
  变动时判定不会触发。故单列`cardDir` / `cardMtime`。
- **spawnSync 不可用于解释器探测**：受限沙箱下返回 EBUSY，  
  会被误判成"找不到解释器"，服务直接起不来。用文件存在性检查。
- **`findPython()` 必须 venv 优先**：venv 排在裸解释器之后时，沙盘会在
  import 阶段静默失效（服务照样起、一点"战斗"才炸 ImportError）。
- **火花初值判据不能用 `is None`**：`PE.new_state()` 产出的 panel 里
  `spark` 字段存在且为 0，判 `is None` 永远落空、火花池从 0 起算。
  要判「0 / 缺失」。
- **同名异族的弱点标记是逐目标的**：`weakpointFound` 挂在 uid 上
  （`变异鬣狗#1` 解析了，`变异鬣狗#2` 没有），按 name 聚合核对会误判成"没生效"。
- **战役模式必须强制同步 panel_state**：只靠 `Encounter.__init__` 里
  「panel 火花为 0 才取 profile」的兜底不够——上一场残留的火花会留在
  `_state_for(sid)` 里，导致战役开局火花是上一场的值。
  `new_encounter(pc_override=...)` 分支里必须显式覆盖。
- **战役里生命上限会随火花变**：`apply_result` 回写时要把 `maxHp` 一起收回来，
  否则下一场 `build_pc` 夹紧 `hp` 时会拿旧上限算，血量显示对不上。
- **敌人名写错会静默降级**：`make_enemy("变异鼠")` 认不出（JSON 键是组合名
  「变异蜥蜴 / 巨型蜈蚣 / 变异鼠」），兜底成一级 HP12/AC12/+3，
  而 note 里显示的却是一级的说明文字。配遭遇链时**只用档位名或 JSON 完整键**，
  并看 `unknownTier` / note 里的 ⚠ 标记。

## 九、HTTP 状态码语义（排错必读）

**200 不等于业务成功。** `server/bridge.js:265-276` 只按 JSON-RPC 层有没有
`msg.error` 决定状态码，业务成败根本不参与判断：

```js
if (req.method === 'POST') {
  const params = await readBody(req);
  const msg = await rpc(route, params);
  if (msg.error) return sendJSON(res, 400, { ok: false, error: msg.error });
  return sendJSON(res, 200, msg.result);   // ← 只要 RPC 层没抛错就 200
}
```

所以「20 个接口全 200」的验证结论只能翻译成：**RPC 全通、进程没崩、方法都在**。
业务对不对必须另外看返回体的**字段**（HP 有没有跨场保留、火花有没有累积、
灰线有没有回退、`cursor` 有没有推进、`status` 到没到终态）。

| 状态码        | 含义                           | 实测例子                                                                                 |
| ---------- | ---------------------------- | ------------------------------------------------------------------------------------ |
| **200**    | RPC 调用成功（业务可能成功，也可能只是取到快照） | `campaign.new` / `campaign.state` / `GET /campaign.js`                                |
| **400**    | RPC 层有 error（业务规则拒绝 / 未知方法）  | `campaign.heal` 未学会「治疗言灵」→ `未学会「治疗言灵」技术`；`campaign.draw {"color":"黑"}` → R9 拒绝；`nope.nope` → `-32601 未知方法` |
| **404**    | 路由/HTTP 方法层面不存在              | `PUT /api/campaign.state`（只收 GET/POST）；`GET /nope.html`（静态文件没有）                     |
| **500**    | bridge 自己抛异常（catch 兜底）       | 解释器探测失败、JSON 解析炸了等                                                                  |

两个容易踩的误读：

- **未知 RPC 方法是 400，不是 404。** 路由 `/api/<method>` 匹配上了才调 RPC，
  匹配不上（比如用了 PUT）才是 404。所以看到 400 先看 `error.code`：
  `-32601` 是方法没注册，`-32000` 是业务规则拒绝。
- **`campaign.heal` / `rest` / `draw` 返回 400 多半是对的行为**，不是 bug。
  例：v3 及更早档位没学会「治疗言灵」→ 400；角色 `status == "dead"` 时
  `rest`/`draw`/`heal` 全拒 → 400；黑色法力按 R9 不可汲取 → 400。
  要确认是不是拒绝，看 `error.message`，别看状态码。
