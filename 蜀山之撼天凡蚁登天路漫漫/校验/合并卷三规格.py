#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并卷三施工规格的两份来源为一份完整规格。

来源：
  正文/_正文施工规格-V3-卷三-取值与边界.md      （取值表 + 跨批约束 + 执行须知 + 验收命令）
  正文/_正文施工规格-V3-卷三-施工单部分.md      （逐章施工单 + 伏笔缺口 + 循环清单 + 接法轮换 + 问题）
输出：
  正文/_正文施工规格-V3-卷三.md                （完整规格，开工前入库）
两份来源保留不删（可回溯），但执行单元只认合并后的这一份。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, "正文/_正文施工规格-V3-卷三-取值与边界.md")
B = os.path.join(ROOT, "正文/_正文施工规格-V3-卷三-施工单部分.md")
OUT = os.path.join(ROOT, "正文/_正文施工规格-V3-卷三.md")


def read(p):
    return open(p, encoding="utf-8").read()


def main():
    a = read(A)
    b = read(B)

    # A 的正文从第一个 "## 一、本批次取值" 开始，取到 "## 六、适用范围" 之前
    ia = a.find("## 一、本批次取值")
    ia = a.rfind("---", 0, ia)
    ia = a.find("\n", ia) + 1
    ja = a.find("## 六、适用范围")
    a_body = a[ia:ja].rstrip()

    # B 的正文从 "## 零、与卷二的接口" 开始
    ib = b.find("## 零、与卷二的接口")
    if ib < 0:
        ib = b.find("## 零、")
    b_body = b[ib:].rstrip()

    header = """# 施工规格 · 卷三 紫云宫（251–375）

> **卷三完整施工规格**（开工前入库，规程 A）。
> 本件由两份来源合并而成：
> - **§一～§五（取值与边界）** 来自 `_正文施工规格-V3-卷三-取值与边界.md`
> - **§六～§十（施工单与清单）** 来自 `_正文施工规格-V3-卷三-施工单部分.md`（据 `03D` 机械提取，125 章标题零差异）
> 两份来源文件保留以供回溯；**执行单元只认本件**。
>
> 上游：`03D-卷三章纲-逐章.md`（逐章细纲）、`02F`（六幕与接法方法）、`02B`（卷级结构）、
> `04`（人物卡与红线）、`05`（文风）、`06`（护航）、`正文/机制台账.md`（跨批机制交接）
> 参照上批：`正文/_正文施工规格-V2-C21至C25.md`

---

"""

    mid = """
---

## 六、逐章施工单（照 `03D`，勿改标题）

"""

    tail = """
---

> **合并说明**：本件 §一～§五 与 §六～§十 分别来自上述两份来源；**若两份来源与本件不一致，以本件为准**。
> 2026-11-18 裁决记录见 §一-13（红线三边界澄清）与 §二（跨批机制与设定约束）。
"""

    out = header + a_body + mid + b_body + tail

    # 节号重编：施工单来源的「零/一/二/三/四/五」→ 合并件的「六/七/八/九/十/十一」
    # （来源 A 已占 §一～§五，故施工单侧顺延为 §六～§十一）
    renum = [
        ("## 零、", "## 六、"),
        ("## 一、本批逐章施工单", "## 七、本批逐章施工单"),
        ("## 二、伏笔密度缺口", "## 八、伏笔密度缺口"),
        ("## 三、25 个循环清单", "## 九、25 个循环清单"),
        ("## 四、「合即起」接法轮换表", "## 十、「合即起」接法轮换表"),
        ("## 五、发现的问题", "## 十一、发现的问题"),
    ]
    for old_h, new_h in renum:
        out = out.replace(old_h, new_h, 1)
    # 同步来源内部的交叉引用
    out = out.replace("见第二节", "见第八节")
    out = out.replace("见第五节第 2 条", "见第十一节第 2 条")
    out = out.replace("六幕（第三节）", "六幕（第九节）")
    # 去掉重复的 §六 引导标题（合并时插入的 mid 与来源B的标题撞了）
    dup_title = "## 六、逐章施工单（照 `03D`，勿改标题）"
    while dup_title in out:
        i = out.find(dup_title)
        j = out.find("\n## ", i + 1)
        if j < 0:
            break
        # 连同其后的分隔线一起去掉，但保留下一个真实标题
        seg = out[i:j]
        seg = seg.replace(dup_title, "", 1)
        seg = seg.replace("\n---\n", "", 1)
        seg = seg.strip("\n")
        out = out[:i] + seg + out[j:]
    open(OUT, "w", encoding="utf-8", newline="\n").write(out)

    n = len(re.sub(r"\s", "", out))
    print(f"已生成 {os.path.relpath(OUT, ROOT)}（{n} 非空白字符）")
    print("章节结构：")
    for line in out.split("\n"):
        if line.startswith("## ") or line.startswith("# "):
            print("  " + line[:60])


if __name__ == "__main__":
    main()
