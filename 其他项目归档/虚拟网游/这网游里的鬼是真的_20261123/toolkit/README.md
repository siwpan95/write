# 网文全流程写作工具链（虚拟网游项目版）

> 「全哥游戏工坊」· 番茄小说全流程九阶段生产链配套工具
> 定位：把「扫榜 → 选题 → 世界观 → 人物 → 大纲 → 正文 → 节奏 → 润色 → 质检」的每一阶段都配上可落盘的模板与确定性执法脚本。
> 纪律：**没落盘等于没做；没跑脚本等于没达标。**

## 目录结构

```
toolkit/
├── scripts/
│   ├── scan_chart.py        # 榜单快照扫描与赛道拥挤度分析（零依赖）
│   ├── example_chart.csv    # 扫榜脚本示例数据（可直接跑通演示）
│   └── （外部）pipeline_check.py 等 5 个闸门脚本随专家包分发：
│       skills/webnovel-pipeline-baseline/scripts/
│         ├── pipeline_check.py        # 统一入口：outline / all / deai 三道闸
│         ├── outline_health_check.py  # 大纲健康度
│         ├── quality_check.py         # 质检
│         ├── deai_audit.py            # AI 味审计
│         └── stat_chapters.py         # 字数统计
└── templates/
    ├── 选题模板.md           # Phase 2 选题立项书骨架（含命中率自评表）
    ├── 世界观模板.md         # Phase 3 世界观设定集骨架（含一致性台账）
    ├── 人物模板.md           # Phase 4 人物档案集骨架（含弧光表/关系网）
    └── 大纲模板.md           # Phase 5 大纲三件套骨架（含黄金三章校验表）
```

## 一、扫榜分析：scan_chart.py

### 数据采集约定

人工扒榜或脚本采集后整理成 CSV（UTF-8；Excel 导出选 UTF-8 CSV 即可，脚本兼容 BOM 与 GBK），
列名固定：`书名,平台,分类,细分,在读,收藏,推荐,字数万,更新天数`。

### 常用命令

```bash
# 全量扫描（控制台输出 Markdown）
python scan_chart.py example_chart.csv

# 只看虚拟网游分类，头部 10 名，写出报告文件
python scan_chart.py example_chart.csv --category 虚拟网游 --top 10 --out 报告.md
```

### 输出内容

1. 数据健康检查（缺失/异常字段定位到行号）
2. 分类分布、细分占比
3. 头部榜（按在读排序）
4. 集中度与拥挤度：CR5 / CR10 / HHI + 拥挤度评分（≥70 红海，50-69 次拥挤，30-49 适中，<30 蓝海）
5. 结论提示（差异化方向建议）

**快照条款**：榜单随时变动，扫描结论有效期建议 ≤ 7 天，过期重扫。

## 二、四套创作模板

| 模板 | 对应阶段 | 核心纪律 |
|---|---|---|
| 选题模板.md | Phase 2 | 频道/分类最先锁定，混用即分类级事故；命中率自评 ≥4.0 才立项 |
| 世界观模板.md | Phase 3 | 金手指必须有代价；术语表全书唯一口径 |
| 人物模板.md | Phase 4 | 主角必有缺陷；反派必有逻辑；男频情感线 ≤15% |
| 大纲模板.md | Phase 5 | 章末钩子必须写到具体画面/台词；伏笔编号埋收对齐 |

## 三、闸门执法（外部脚本，随专家包分发）

```bash
# 大纲闸门（男频口径）
python pipeline_check.py outline project/05_大纲/逐章细纲.md --channel male

# 正文闸门（目录批量：字数/格式/缺章；--min 按项目字数配置传）
python pipeline_check.py all project/06_正文 --min 2800

# AI 味闸门（九道硬闸门）
python pipeline_check.py deai project/07_润色/第001章_精修稿.txt --lines
```

**退出码 0 = 过闸**；非 0 必须回退对应阶段重做，严禁带病交付。

## 四、推荐工作流

1. 扒榜整理 CSV → `scan_chart.py` 出赛道报告 → 决定细分切入
2. 用**选题模板**写立项书 → 命中率自评 → 过闸
3. 并行：**世界观模板** + **人物模板**（互相引用对齐）
4. **大纲模板**写黄金三章细纲 → `pipeline_check.py outline` 过闸
5. 逐章写作 → `pipeline_check.py all` 过闸 → 润色 → `pipeline_check.py deai` 过闸
6. 全部落盘归档：`project/01~08_*/`

## 版本

- v1.0（2026-11-23）：首发。随「虚拟网游类小说全流程生产」项目交付。
- 许可：MIT
