# PKM · 知识连接层

> **一句话**：本仓的笔记方式已从「文件夹即数据库」升级为
> **「文件夹（归档轴）＋ 索引（检索轴）＋ 连接层（知识轴）」三轴并行**。

## 是什么

`PKM/` 是 `write` 工作区的**知识连接层** —— 让 1169 个 Markdown 文件
从「能翻目录找到」升级为「能检索、能导航、能发现关联」。

**它不是什么**：不是新的笔记软件，不取代 Obsidian / 思源 / Logseq，
不搬走任何内容，不产生第二份真相源。

## 目录

| 路径 | 内容 | 入库 |
|---|---|---|
| `00-原子笔记/` | **原子笔记**（永久笔记 / 文献笔记 / 指南） | ✅ 知识资产 |
| `01-MOC/` | **MOC 内容地图**（跨项目导航） | ✅ 知识资产 |
| `02-索引/` | 受控元数据清单（人工维护，旁挂注入） | ✅ 知识资产 |
| `MOC-全库.md` | 全库内容地图（脚本生成骨架 + 人工补充） | ✅ |
| `graph.json` | **知识图谱**（文档元数据 + 双向连接） | ✅ |
| `孤立文档清单.md` | 连接层施工单（按项目分组） | ✅ |
| `断链清单.md` | 断链体检结果 | ✅ |
| `index.json` | **全文倒排索引**（派生缓存） | ❌ 不入库 |

> **为什么 index.json 不入库**：它是派生产物，`npm run pkm:build` 10 秒可重建，
> 入库只会制造 17MB 的 diff 噪音。纪律与「审校报告不入库」同源。
> **入库的是知识资产**（图谱 / MOC / 原子笔记）—— 那才是人工积累的价值。

## 快速开始

```bash
npm run pkm:search 战锤四神                    # 全仓检索
npm run pkm:links 廓者未名夜/作品总览.md        # 查出链 / 入链
npm run pkm:build                              # 重建索引 + 图谱 + MOC
npm run pkm:graph                              # 图谱统计
npm run check                                  # 闸门（含连接层体检）
```

## 换机部署

见 [`../tools/bootstrap.sh`](../tools/bootstrap.sh) 与
[`../tools/bootstrap.ps1`](../tools/bootstrap.ps1)。

```bash
git clone https://gitee.com/siwpan/write.git
cd write
bash tools/bootstrap.sh            # Git Bash
# 或
powershell -ExecutionPolicy Bypass -File tools\bootstrap.ps1   # Windows
```

一条命令完成：环境自检 → 装 Node 依赖 → 重建索引 → 跑闸门。

详见 [`换机部署.md`](换机部署.md)。

## 方法论依据

| 方法论 | 在本仓的落法 |
|---|---|
| **Zettelkasten**（卡片盒） | 原子笔记：一块乐高只装一个想法；原子化后可跨项目复用 |
| **PARA**（四层分类） | 归档轴已由目录结构天然承担（作品项目＝Project/Archive，素材＝Resource） |
| **LYT**（链接你的思考） | MOC 内容地图 + 双链；孤立文档清单作为施工单 |
| **Backlink / 反向链接** | 索引器自动计算 `backlinks`，双向可导航 |

## 与 Obsidian 的关系（可选外壳）

本仓是**纯 Markdown**，Obsidian 可以「Open folder as vault」直接指向仓根 ——
**零迁移**，立刻获得图形化双链与图谱视图。

但 Obsidian **不是必需品**：
- 本仓自带的检索器对中文做了二元组切分，比 Obsidian 原生搜索更准；
- Obsidian 核心闭源、Sync 付费，中文分词需另装 Omnisearch；
- 万级文件以上 Obsidian 索引会明显变慢。

所以本仓的定位是：**仓库即 vault**，Obsidian 只是「其中一种看法」。

## 纪律

1. **正文零改动**：不批量给已有 1169 个文件注入 frontmatter —— 连接关系放在
   原子笔记里（旁挂机制），文档本身不动。
2. **只读源文件**：索引器只读，只写 `PKM/`。
3. **零三方依赖**：Python 内核只用标准库，换机即跑。
4. **断链即错链**：同名歧义一律判为断链（宁可断，不可错）。
5. **闸门只看 ERROR**：断链＝ERROR（会让知识网络给出错误答案）；孤立比例＝WARN（施工单）；规模＝INFO。

## 导航

- 全库地图：[[PKM/MOC-全库.md]]
- 跨项目导航：[[PKM/01-MOC/MOC-跨项目知识网络.md]]
- 使用指南：[[PKM/00-原子笔记/guide-0001-PKM连接层使用指南.md]]
