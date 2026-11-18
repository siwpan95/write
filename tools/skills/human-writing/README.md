# human-writing 技能 · 仓内运行包（v1.0.0）

本目录是「活人感写作」技能的**仓内副本**，随 git 分发，用于让 `prose-style` 检查器跨机可用。

## 为什么在这里

`tools/checkers/prose_style_check.py` 依赖技能的 `scripts/check_prose.py` 提供硬禁令常量
（禁词表、翻案句正则、标点禁令、借喻字段）。原先它从
`~/.workbuddy/skills/human-writing/scripts` 加载，换一台没装该技能的机器就 import 失败，
整个检查器不可用。现在改为仓内优先，本目录就是它的默认来源。

## 解析顺序

`prose_style_check.py` 按下面的顺序找技能根，取第一个含 `scripts/check_prose.py` 的：

1. 环境变量 `HUMAN_WRITING_SKILL` 指向的目录（用于临时试用外部新版本）
2. **本目录**（默认，跨机自带）
3. `~/.workbuddy/skills/human-writing`（兜底，仅开发机有）

全部找不到时退出码 2，并打印可操作提示，不会静默降级成「没有规则」。

## 目录内容

| 文件 | 用途 |
|---|---|
| `SKILL.md` | 技能规则正文（创作与改稿流程、交付禁令） |
| `VERSION` | 版本号，当前 `1.0.0` |
| `LICENSE` | 技能许可 |
| `scripts/check_prose.py` | **运行必需**。硬禁令常量与检查函数，检查器直接 import |
| `references/*.md` | 五份深度参考（forum-prose / reality / fiction / formats / revision） |

规则文件按 **UTF-8 无 BOM + LF** 存放，跨机一致。

## 与用户级技能的关系

- 本目录是随仓分发的**固定版本**，规则更新要显式提交，保证同一 commit 的检查结果可复现。
- 用户级 `~/.workbuddy/skills/human-writing` 是 WorkBuddy 会话里实际加载的技能，两者互不覆盖。
- 已实测：把用户级技能目录临时移走后，`prose-style` 检查器仍能正常加载规则并产出完整报告，
  说明跨机运行不依赖用户级安装。

### 跨机适配已处理的三处硬编码

1. **技能路径**。原 `prose_style_check.py` 直接 `import` 自 `Path.home()/.workbuddy/...`，
   现按「环境变量 → 仓内 → 用户级」顺序解析，仓内为默认来源。
2. **仓根路径**。两个检查器的 `--root` 原默认 `.` 或写死本机绝对路径。前者从别处调用会
   扫到 0 篇正文却报 `0 error` 的假 PASS，后者换机直接失效。现都由脚本位置推导仓根。
3. **空扫描静默通过**。扫不到正文时现在退出码 2 并打印原因，不再静默返回 PASS。

## 更新规则

升级技能版本时：

1. 用新版本文件覆盖本目录对应文件，保持 UTF-8 无 BOM + LF。
2. 同步更新 `VERSION`。
3. 跑全量校验确认结果无意外漂移：

   ```bash
   python tools/checkers/prose_style_check.py --root . --protocol
   npm run check
   ```

4. 若规则变动导致大量新 WARN，先按 `references/revision.md` 判断是否属语境豁免，
   不要直接批量改正文。项目级风格口径（如 `小说/设定与参考/叙事风格修正手册.md`）
   优先于通用规则。
