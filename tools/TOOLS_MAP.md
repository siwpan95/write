# tools/ · 全仓工具地图（唯一权威登记处）

> 建立：2026-11-23（本机 @SIWPAN）｜依据：全仓机械扫描（160 脚本）+ 逐目录抽查代码头部与调用方
> **痛点**：工具脚本散落 11 个顶层目录，"找不到 / 不知道有没有 / 重复造轮子"。
> **根治方式**：**不在物理位置上一刀切**——那会断掉三条链：① 适配器对扫描器的硬编码引用（`consistency_check.py:31` / `cordis.yml:122` / `12-checker-consistency.mjs:24`）；② 脚本间相对 import（钢铁之梦 `build_omnibus.py` import 卷一 `build.py`）；③ 自包含包的"解压即用"（通用模板包 / 零件库 / horror-motif-lab / vrmmo kit 的 README/SOP 写死包内路径）。改为**统一登记 + 统一入口 + 权威标注 + 门禁防复发**。
> 口径：跨机共识为通用结论；下列路径、数量、引用行号为**本机时点事实**（2026-11-23 快照），换机 / 新增脚本后须复跑 `python3 tools/tool_registry_check.py` 校验。

---

## 一、四类判定标准（新脚本先归类再落地）

| 类 | 含义 | 落地规则 | 本次数量 |
|---|---|---|---|
| **A** | 通用可复用工具（与具体书稿无关） | **必须放仓根 `tools/`**，在本文登记；已有子目录按职能分（checkers/plugins/pkm/procedural/skills） | 44 |
| **B** | 自包含包随包工具（README/SOP/MANIFEST 写死相对路径） | **留包内**，本文登记位置与调用方；搬走 = 包缺件 | 28 |
| **C** | 作品生产脚本（硬编码书名/章号/路径/批次） | **留作品目录**，本文标注"一次性"，不复用 | 约 72 |
| **D** | 软件项目业务代码（引擎/服务端，非工具） | **完全不动**，本文仅标注存在 | 约 16 |

> 判定顺序：D（软件源码）→ B（被包内路径引用）→ C（硬编码作品信息）→ 剩下才是 A。拿不准时按 C 处理并留作品目录——宁可少收，不可断链。

---

## 二、脚本登记（全量，机械扫描）

> 每个脚本都列出，避免"登记了但漏了"。分类理由见各类小节的说明，关键调用方证据见 §三。

### tools/ — 44 个 · A 类

> 仓根统一入口 · Cordis 编排层（checkers/plugins/pkm/procedural/skills 子系统）；所有工具的唯一权威入口

| 脚本 | 类 | 备注 |
|---|---|---|
| `tools/bootstrap.ps1` | A |  |
| `tools/bootstrap.sh` | A |  |
| `tools/capabilities.mjs` | A |  |
| `tools/checker_protocol.py` | A |  |
| `tools/checkers/consistency_check.py` | A |  |
| `tools/checkers/dse_check.py` | A |  |
| `tools/checkers/package_check.py` | A |  |
| `tools/checkers/pkm_check.py` | A |  |
| `tools/checkers/prose_fix.py` | A |  |
| `tools/checkers/prose_style_check.py` | A |  |
| `tools/checkers/rules_check.py` | A |  |
| `tools/checkers/sync_check.py` | A |  |
| `tools/doc_review.py` | A |  |
| `tools/fix_bom.py` | A |  |
| `tools/host.mjs` | A |  |
| `tools/ledger_md2jsonl.py` | A |  |
| `tools/ledger_qa.py` | A |  |
| `tools/manifest.py` | A |  |
| `tools/metrics.py` | A |  |
| `tools/pkm/eval.py` | A |  |
| `tools/pkm/graph.py` | A |  |
| `tools/pkm/indexer.py` | A |  |
| `tools/pkm/pkm_cli.py` | A |  |
| `tools/pkm/scanner.py` | A |  |
| `tools/plugins/01-config.mjs` | A |  |
| `tools/plugins/02-registry.mjs` | A |  |
| `tools/plugins/03-runner.mjs` | A |  |
| `tools/plugins/04-checkers.mjs` | A |  |
| `tools/plugins/10-checker-package.mjs` | A |  |
| `tools/plugins/11-checker-doc-review.mjs` | A |  |
| `tools/plugins/12-checker-consistency.mjs` | A |  |
| `tools/plugins/13-pkm.mjs` | A |  |
| `tools/plugins/14-checker-pkm.mjs` | A |  |
| `tools/plugins/15-checker-sync.mjs` | A |  |
| `tools/plugins/16-checker-rules.mjs` | A |  |
| `tools/plugins/17-checker-prose-style.mjs` | A |  |
| `tools/plugins/18-checker-dse.mjs` | A |  |
| `tools/plugins/20-report.mjs` | A |  |
| `tools/plugins/30-cli.mjs` | A |  |
| `tools/procedural/md2dse.py` | A | dse 内容包转换器（仓级权威源） |
| `tools/repeat_probe.py` | A |  |
| `tools/skills/human-writing/scripts/check_prose.py` | A |  |
| `tools/tests/run_tests.py` | A |  |
| `tools/tool_registry_check.py` | A | 工具资产登记门禁（本文的机器校验器） |

### 小说/ — 33 个 · C/D 类

> wasteland-panel 为软件项目业务代码（engine/server，D 类不动）；杂项/历史为一次性 QC 脚本（C 类）

| 脚本 | 类 | 备注 |
|---|---|---|
| `小说/wasteland-panel/engine/bestiary_combat.py` | C/D |  |
| `小说/wasteland-panel/engine/bible_parser.py` | C/D |  |
| `小说/wasteland-panel/engine/campaign.py` | C/D |  |
| `小说/wasteland-panel/engine/combat_engine.py` | C/D |  |
| `小说/wasteland-panel/engine/consistency_scanner.py` | C/D |  |
| `小说/wasteland-panel/engine/d20_bridge.py` | C/D |  |
| `小说/wasteland-panel/engine/panel_engine.py` | C/D |  |
| `小说/wasteland-panel/engine/rpc_server.py` | C/D |  |
| `小说/wasteland-panel/engine/trpg_mechanics.py` | C/D |  |
| `小说/wasteland-panel/server/cli.mjs` | C/D |  |
| `小说/wasteland-panel/server/host.mjs` | C/D |  |
| `小说/wasteland-panel/server/plugins/01-config.mjs` | C/D |  |
| `小说/wasteland-panel/server/plugins/02-engine.mjs` | C/D |  |
| `小说/wasteland-panel/server/plugins/03-dataset.mjs` | C/D |  |
| `小说/wasteland-panel/server/plugins/04-web.mjs` | C/D |  |
| `小说/wasteland-panel/server/plugins/bible-paths.mjs` | C/D |  |
| `小说/杂项/历史/_audit.py` | C/D |  |
| `小说/杂项/历史/_check_lines.ps1` | C/D |  |
| `小说/杂项/历史/_final_check.ps1` | C/D |  |
| `小说/杂项/历史/_patch221.py` | C/D |  |
| `小说/杂项/历史/_scan_frag.py` | C/D |  |
| `小说/杂项/历史/check_batch01.py` | C/D |  |
| `小说/杂项/历史/check_batch02.py` | C/D |  |
| `小说/杂项/历史/check_batch03.py` | C/D |  |
| `小说/杂项/历史/check_batch04.py` | C/D |  |
| `小说/杂项/历史/check_batch05.py` | C/D |  |
| `小说/杂项/历史/check_batch06.py` | C/D |  |
| `小说/杂项/历史/check_batch07.py` | C/D |  |
| `小说/杂项/历史/check_batch08.py` | C/D |  |
| `小说/杂项/历史/check_batch09.py` | C/D |  |
| `小说/杂项/历史/check_batch10.py` | C/D |  |
| `小说/杂项/历史/工具-章节头部分离.py` | C/D |  |
| `小说/设定与参考/_split_long_para.py` | C/D |  |

### 蜀山之撼天凡蚁登天路漫漫/ — 20 个 · C 类

> 蜀山作品生产/校验脚本（校验/）；硬编码批次号、章号、人名，一次性生产记录

| 脚本 | 类 | 备注 |
|---|---|---|
| `蜀山之撼天凡蚁登天路漫漫/校验/check_package.py` | C | 项目专属自检器（非仓级 package_check.py） |
| `蜀山之撼天凡蚁登天路漫漫/校验/刷新进度表与MANIFEST.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/压模板句_卷三.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/变体化_卷三.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/合并卷三规格.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/回检_卷三实测.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/回检_卷二实测.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/复算_篇幅白名单.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/微调篇幅_卷三.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/扫描章纲冲突.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/收尾_V2-C21至C25.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/收尾_卷三文风.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/核验_回检清单.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/核验_润色稿.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/母题变体化_卷三.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/自测_卷三规格.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/自测_段落去重检查.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/通用变体化_卷三.py` | C |  |
| `蜀山之撼天凡蚁登天路漫漫/校验/验收_V2-C21至C25.py` | C | 表面通用、判据作品专属（硬编码人名/禁词） |
| `蜀山之撼天凡蚁登天路漫漫/校验/验收_任意批次.py` | C | 表面通用、判据作品专属（硬编码人名/禁词） |

### 点子库/ — 18 个 · C 类

> 作品生产脚本（04-工具）；audit_consistency 被 3 处硬编码引用为扫描器，其余硬编码书名/章号

| 脚本 | 类 | 备注 |
|---|---|---|
| `点子库/04-工具/audit2_style.py` | C |  |
| `点子库/04-工具/audit_consistency.py` | C | 被 consistency_check.py:31 / cordis.yml:122 / 12-checker-consistency.mjs:24 三处引用，不改 |
| `点子库/04-工具/build_book.py` | C |  |
| `点子库/04-工具/build_buyi_qiti.py` | C |  |
| `点子库/04-工具/build_law_table.py` | C |  |
| `点子库/04-工具/build_txt_collection.py` | C |  |
| `点子库/04-工具/extract_sections.py` | C |  |
| `点子库/04-工具/make_pdf_booklet_samples.py` | C |  |
| `点子库/04-工具/make_pdf_lower.py` | C |  |
| `点子库/04-工具/make_pdf_sample.py` | C |  |
| `点子库/04-工具/make_toc.py` | C |  |
| `点子库/04-工具/normalize_quotes.py` | C |  |
| `点子库/04-工具/postprocess.py` | C |  |
| `点子库/04-工具/revise_pass1.py` | C |  |
| `点子库/04-工具/revise_pass1b.py` | C |  |
| `点子库/04-工具/revise_pass1c.py` | C |  |
| `点子库/04-工具/revise_pass2.py` | C |  |
| `点子库/04-工具/程序化实践/term_scan.py` | C |  |

### 通用模板包/ — 15 个 · B 类

> 自包含模板包随包工具（tools/procedural + tools/polish）；README/SOP/MANIFEST 写死相对路径，搬走即缺件

| 脚本 | 类 | 备注 |
|---|---|---|
| `通用模板包/tools/build_sample_pages.py` | B |  |
| `通用模板包/tools/check_package.py` | B | 项目专属自检器（非仓级 package_check.py） |
| `通用模板包/tools/polish/build.py` | B | 交付件合成（随包/作品构建同名，注意区分） |
| `通用模板包/tools/polish/count.py` | B | 逐章润色字数硬校验（随包） |
| `通用模板包/tools/polish/extract.py` | B | 原稿抽章（随包） |
| `通用模板包/tools/polish/kit.py` | B | 逐章润色体检（随包） |
| `通用模板包/tools/polish/selftest.sh` | B |  |
| `通用模板包/tools/polish/upload.sh` | B |  |
| `通用模板包/tools/procedural/dice_roll.py` | B | 程序化创作脚本 |
| `通用模板包/tools/procedural/goal_sim.py` | B | 程序化创作脚本（包内/仓级各一份） |
| `通用模板包/tools/procedural/grammar_expand.py` | B | 程序化创作脚本（包内/仓级各一份） |
| `通用模板包/tools/procedural/name_generator.py` | B | 程序化创作脚本（包内/仓级各一份，见重复实现表） |
| `通用模板包/tools/procedural/npc_card.py` | B | 程序化创作脚本 |
| `通用模板包/tools/tab_lint.py` | B |  |
| `通用模板包/writing-style-transfer/scripts/style_metrics.py` | B |  |

### 证伪实验-钢铁之梦/ — 14 个 · C 类

> 构建脚本；硬编码 /data/workspace/steel_dream 与卷次，合订本 import 卷一，搬迁断链

| 脚本 | 类 | 备注 |
|---|---|---|
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷一/build.py` | C | 交付件合成（随包/作品构建同名，注意区分） |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷一/postprocess.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷三/build3.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷三/clean.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷三/make_scripts.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷三/post3.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷二/build2.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷二/clean.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷二/clean2.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷二/make_scripts.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/卷二/post2.py` | C |  |
| `证伪实验-钢铁之梦/00_原作/构建脚本/合订本/build_omnibus.py` | C | import build as B（相对导入卷一） |
| `证伪实验-钢铁之梦/00_原作/构建脚本/合订本/post_omnibus.py` | C |  |
| `证伪实验-钢铁之梦/99_工具/build_variants.py` | C |  |

### 其他项目归档/ — 6 个 · B 类

> vrmmo_starter_kit 自包含开书包（05_tools）；SOP 声明解压即用

| 脚本 | 类 | 备注 |
|---|---|---|
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/build_package.py` | B |  |
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/fix_quotes.py` | B |  |
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/hit_score.py` | B |  |
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/outline_build.py` | B |  |
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/prose_lint.py` | B |  |
| `其他项目归档/虚拟网游/vrmmo_starter_kit/05_tools/rank_scan.py` | B |  |

### horror-motif-lab/ — 4 个 · B 类

> 自包含母题实验室（tools/generator|build|lint）；README/docs 写死相对路径

| 脚本 | 类 | 备注 |
|---|---|---|
| `horror-motif-lab/tools/build/build.py` | B | 交付件合成（随包/作品构建同名，注意区分） |
| `horror-motif-lab/tools/generator/gen.py` | B |  |
| `horror-motif-lab/tools/lint/blind_rank.py` | B |  |
| `horror-motif-lab/tools/lint/check_docs.py` | B |  |

### 零件库/ — 3 个 · B 类

> 零件库方法论资产包随包工具；被 00/01/13/14/16 号文件按名引用，依赖 HERE + 固定卡片文件名

| 脚本 | 类 | 备注 |
|---|---|---|
| `零件库/build_edges.py` | B |  |
| `零件库/check_assembly.py` | B |  |
| `零件库/check_parts.py` | B |  |

### 创造主们的战争/ — 2 个 · C 类

> 分析/ 硬编码书名与章文件，跨目录调用零件库，作品生产脚本

| 脚本 | 类 | 备注 |
|---|---|---|
| `创造主们的战争/分析/_extract_ch1_3.py` | C |  |
| `创造主们的战争/分析/check_vol1.py` | C |  |

### (root)/ — 1 个 · A 类

> cli.py 通用 CLI 入口；保留仓根，不迁入 tools/（避免破坏 python cli.py 约定）

| 脚本 | 类 | 备注 |
|---|---|---|
| `cli.py` | A | 通用 CLI 入口，保留仓根 |

### 综网废柴逆命/ — 1 个 · C 类

> 场景图生成器，硬编码输出目录，作品生产脚本

| 脚本 | 类 | 备注 |
|---|---|---|
| `综网废柴逆命/素材/场景图/_gen_scenes.py` | C |  |

---

## 三、重复实现与权威源（避免改错副本）

| 能力 | 多处实现 | 权威源 | 说明 |
|---|---|---|---|
| 模板包自检 | `通用模板包/tools/check_package.py`、`蜀山…/校验/check_package.py`、仓级 `tools/checkers/package_check.py` | **各自权威于其所在包/层** | 三份判据不同（包规约 / 作品专属 / Cordis 协议 JSON），不可互相替代 |
| 程序化创作脚本 | `通用模板包/tools/procedural/*`、`tools/procedural/md2dse.py` | 命名工厂等以**通用模板包**为源；md2dse 以**仓级**为源 | 前者随包分发，后者接 dse-core 三道门 |
| CLI 入口 | 仓根 `cli.py`、`tools/pkm/pkm_cli.py`、各作品 server/cli.mjs | 各司其职 | 仓根=通用脚手架；pkm_cli=知识库；server/cli=业务项目 |
| 一致性扫描 | `点子库/04-工具/audit_consistency.py`（原件）＋ `tools/checkers/consistency_check.py`（适配器） | **原件不动、适配器包装**（工作区规范 §8.4） | 三处硬编码指向原件路径，迁移会同时断掉 `npm run check` 链路 |

## 四、新工具的落地规则（防"再次开花"）

1. **先判类**：写新脚本前对照 §一 四类标准。通用能力（A）**一律进仓根 `tools/`**，不许在作品目录 / 包外另起炉灶。
2. **必登记**：任何新增 `.py/.sh/.mjs/.ps1` 必须跑 `tool_registry_check.py`，未登记即 ERROR；登记时在本文 §二 对应目录表加一行。
3. **能复用就复用**：写之前先查 §二 / §三——已有同类 A 类工具直接调用，不重写。B 类包内工具跨包使用须经 `tools/checkers/` 适配器包装，不改原件（工作区规范 §8.4）。
4. **C 类标注**：作品生产脚本文件名带作品名或放作品目录，本文标"一次性"，避免误当通用工具。
5. **D 类隔离**：软件项目（如 wasteland-panel）源码不算工具，目录自带 README，本文仅登记存在。

## 五、门禁

```bash
# 单独跑：扫描全仓脚本 vs 本文登记，未登记 / 已删除均报错
python3 tools/tool_registry_check.py
# 集成：npm run check 通过 Cordis 插件调用（见 tools/cordis.yml）
```

> 本文是**机器可读的权威表**：脚本清单由 `tool_registry_check.py` 每次实时扫描比对，登记行数与实存数不符即 FAIL。维护本文 = 维护工具资产台账。
