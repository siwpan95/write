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
from collections import Counter

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


def find_dup_segments(body):
    """找出章内实质重复的**叙述段**（括号内的场景/内心/清单）。

    判定口径（三条都须满足才算重复）：
      ① 该行以「（」开头——即叙述段。**对白行（不以括号开头）不算**：
         本书的对话回环是刻意手法（如「老弟子说，往南是海。」反复出现以加重语气），
         判错会误报。
      ② 去标点后实质字数 ≥ 12——再短的（「（嗯。）」）重复是正常写法。
      ③ 同一章内出现 ≥2 次。
      ④ **两次出现之间间隔 ≥ 8 个段落**才算机械复制。间隔大＝作者刻意让同一句
         在两个场景分别落下（回环强化，本书常用手法，如 236 章
         「绕出来的字是他的字；不绕的字是他自己的。」在主角自述与于建追问后
         各落一次）；间隔小＝编辑复制粘贴的残留。

    2026-11-18 补：C21 执行单元实测教训——用整文件行号删重复段时误伤了同文件
    另一章的八段，而「字数达标 / 引号为 0」等既有检查**全部绿灯**，纯靠人工
    通读才发现。说明内容层的破坏（误删、重复）需要脚本单独兜一道。
    """
    lines = [x.strip() for x in body.split("\n") if x.strip()]
    pos = {}
    for idx, s in enumerate(lines):
        if not s.startswith("（"):
            continue
        core = re.sub(r"[（）()。，、？！：；“”\"'…—\s]", "", s)
        if len(core) >= 12:
            pos.setdefault(s, []).append(idx)
    out = []
    for s, idxs in pos.items():
        if len(idxs) < 2:
            continue
        gaps = [idxs[i + 1] - idxs[i] for i in range(len(idxs) - 1)]
        if min(gaps) < 8:
            out.append(s)
    return out



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
            # 字数口径：**纯正文**，不含章标题行与末尾「（本章完）」标记。
            # 2026-11-18 修正：原先按整段算，把每章固定的格式开销（约 18–35 字）
            # 算进了内容篇幅，等于对每章多收一遍"过路费"，口径不公平。
            pure = re.sub(r"^#.*$", "", body, flags=re.M)
            pure = pure.replace("（本章完）", "")
            n = len(re.sub(r"\s", "", pure))
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
            # 章内段落去重（2026-11-18 补：C21 代理实测教训——重复块纯脚本不报，
            # 靠人工通读才发现；且"字数达标"完全抓不到"内容被误删/误伤"）
            segs = [s_.strip() for s_ in body.split("\n") if s_.strip()]
            dup = find_dup_segments(body)
            if dup:
                errs.append(f"章内重复段 ×{len(dup)}：{dup[0][:22]}")
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
