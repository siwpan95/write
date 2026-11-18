#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷二 C21–C25 批次验收（一次性验 5 个循环）。

用法（在项目根执行）：
    python3 校验/验收_V2-C21至C25.py

判定口径见 正文/_正文施工规格-V2-C21至C25.md §一：
  篇幅   每章 2200–2800 非空白全字符
  格式   零引号（“ ” 「 」 都不许出现）
  人名   每章「杨成志」≥2 次
  禁用   现代词 + 伪轻小说腔
  结构   文件级标题 + 5 个章级标题 + 每章末行「（本章完）」
  衔接   循环标题须与规格 §二 一致
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = {
    "C21": ("正文/蜀山 卷二 226–230｜C21 用一次.md", 226, ["看", "那不是纸", "十九", "有人看见了", "两指宽"]),
    "C22": ("正文/蜀山 卷二 231–235｜C22 往南.md", 231, ["往南是海", "紫云宫", "没了也有册", "回崖", "门缝"]),
    "C23": ("正文/蜀山 卷二 236–240｜C23 第二次门缝.md", 236, ["什么都没有", "白朴开门", "库房", "空格里的东西", "两个字"]),
    "C24": ("正文/蜀山 卷二 241–245｜C24 别查.md", 241, ["我吃了", "谁塞的", "老周", "你是哪家的孩子", "我姓什么"]),
    "C25": ("正文/蜀山 卷二 246–250｜C25 湿封皮.md", 246, ["老周记得我这个人", "我像我", "紫云宫的消息", "他笑了", "湿封皮"]),
}

BAD_WORDS = ["系统", "数据", "状态", "信息", "用户", "配置", "版本", "流程", "指标",
             "命运的齿轮", "深邃的眼眸", "嘴角勾起", "邪魅", "心头一颤"]
QUOTES = ["“", "”", "「", "」"]

LO, HI = 2200, 3000


def check():
    total_err = 0
    total_ch = 0
    for cn in sorted(FILES):
        rel, start, titles = FILES[cn]
        path = os.path.join(ROOT, rel)
        print(f"\n=== {cn}  {rel} ===")
        if not os.path.exists(path):
            print("  [E] 文件不存在")
            total_err += 1
            continue
        t = open(path, encoding="utf-8").read()
        # 章级切分
        parts = re.split(r"^# 第 (\d+) 章 (.+)$", t, flags=re.M)
        if len(parts) < 3:
            print("  [E] 未找到章级标题")
            total_err += 1
            continue
        # parts = [前导, 章号, 标题, 正文, 章号, 标题, 正文, ...]
        # 注意：re.split 带 2 个捕获组时步进是 3，不是 2（2026-11-18 修正）
        got = [(int(parts[i]), parts[i + 1].strip(), parts[i + 2])
               for i in range(1, len(parts) - 1, 3)]
        if len(got) != 5:
            print(f"  [E] 章数应为 5，实为 {len(got)}")
            total_err += 1
        for i, (num, title, body) in enumerate(got):
            n = len(re.sub(r"\s", "", re.sub(r"^#.*$", "", body, flags=re.M)))
            q = sum(body.count(x) for x in QUOTES)
            y = body.count("杨成志")
            hits = [w for w in BAD_WORDS if w in body]
            endmark = body.rstrip().endswith("（本章完）")
            exp_num = start + i
            errs = []
            if num != exp_num:
                errs.append(f"章号应为 {exp_num}")
            if i < len(titles) and title != titles[i]:
                errs.append(f"标题应为「{titles[i]}」实为「{title}」")
            if not (LO <= n <= HI):
                errs.append(f"篇幅 {n} 越界({LO}-{HI})")
            if q:
                errs.append(f"引号 {q} 处")
            if y < 2:
                errs.append(f"杨成志 {y} 次")
            if hits:
                errs.append(f"禁用词 {hits}")
            if not endmark:
                errs.append("结尾缺（本章完）")
            total_ch += 1
            if errs:
                total_err += 1
                print(f"  {num} {title[:16]:18} {n:6}字 引号{q:3} 杨{y:3}  [E] {'; '.join(errs)}")
            else:
                print(f"  {num} {title[:16]:18} {n:6}字 引号{q:3} 杨{y:3}  OK")
    print("\n" + "=" * 60)
    print(f"批次结论: {'PASS' if total_err == 0 else f'FAIL {total_err} 项'}（共验 {total_ch} 章）")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(check())
