#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二次实战校验：把《创造主们的战争》已写正文与零件库装配层对齐。

用法：
    python check_vol1.py              # 全文输出
    python check_vol1.py --strict     # 有 ERROR 时退出码 1

校验对象：
  A. 正文 vs 装配体 ASM-CCZ-0001（课题／成员件／序位／band／phase）
  B. 正文 vs 项目设定（03 世界观圣经／13 世界先行区域卡）
  C. 装配层工具自检（check_assembly.py 对本项目的装配体）
  D. 代价推进链（02 校勘员 → 工龄 → 亲属关系 → 姓名）
  E. 元叙事锚点（十三册并置是否在正文中真正出现）

定位：**只判一致性，不判文采。** 文采与节奏是人工判据。
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 仓根 write
PROJ = os.path.join(ROOT, "创造主们的战争")
LIB = os.path.join(ROOT, "零件库")
ANA = os.path.join(PROJ, "分析")
CH = [os.path.join(ANA, f) for f in ("第一章.txt", "第二章.txt", "第三章.txt")]


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    strict = "--strict" in sys.argv
    errs, warns, infos = [], [], []

    texts = {}
    for p in CH:
        if not os.path.exists(p):
            errs.append(f"缺文件: {p}")
            continue
        texts[os.path.basename(p)] = read(p)
    full = "\n".join(texts.values())
    c1, c2, c3 = (texts.get("第一章.txt", ""), texts.get("第二章.txt", ""),
                  texts.get("第三章.txt", ""))

    # ---------- A. 正文 vs 装配体 ASM-CCZ-0001 ----------
    asm = read(os.path.join(LIB, "装配体", "ASM-CCZ-0001.md"))
    a_topic = re.search(r"\| `课题` \| (.+?) \|", asm)
    topic = a_topic.group(1) if a_topic else ""
    # 装配体序位三件
    a_members = re.findall(r"WB-[A-Z]+-\d{4}",
                           re.search(r"### 2\.2 成员件与角色(.*?)(?=### 2\.3)", asm, re.S).group(1))
    # 正文中三件对应的实体（不写 WB-ID，正文不得出现库内部 ID）
    a_checks = [
        ("记录即存在", ["册碑", "在册", "划名", "查无此人"], c1 + c3),
        ("划名机制", ["划掉", "划名", "刮痕", "覆盖"], c1 + c3),
        ("篡改痕迹符号系统", ["痕迹", "字迹", "铅笔字", "压痕"], c1 + c2 + c3),
    ]
    for name, kws, text in a_checks:
        hit = sum(1 for k in kws if k in text)
        if hit == 0:
            errs.append(f"装配体成员「{name}」在正文中完全无对应实体")
        elif hit <= 1:
            warns.append(f"装配体成员「{name}」在正文中痕迹稀薄（仅 {hit}/{len(kws)} 个关键词）")
        else:
            infos.append(f"装配体成员「{name}」：{hit}/{len(kws)} 关键词命中")

    # 序位：设→翻→压 三相位在正文中的体现
    seq_checks = [
        ("设（立规则）", ["通则", "第二十五条", "规矩", "规则"], c1),
        ("翻（倒向另一边）", ["不存在的人", "不构成任何记载", "查无此人"], c1 + c2 + c3),
        ("压（加压）", ["第二十三份", "代价", "抹掉", "抹了"], c1 + c2 + c3),
    ]
    for ph, kws, text in seq_checks:
        if not any(k in text for k in kws):
            errs.append(f"序位相位「{ph}」在正文中无体现")

    # ---------- B. 正文 vs 项目设定 ----------
    # 区域卡「出场零件」四件必须都在正文落地
    area = read(os.path.join(PROJ, "13-世界先行与地图叙事-创造主们的战争.md"))
    area_card = re.search(r"### 2\.3 卷一区域卡.*?\n(.*?)\n###", area, re.S)
    area_text = area_card.group(1) if area_card else ""
    # 接口四型
    ifaces = ["位置", "差事", "身份", "交易"]
    for k in ifaces:
        if k not in area_text:
            warns.append(f"区域卡接口四型缺「{k}」")
    # 正文是否覆盖接口四型中的至少「位置」「差事」（第一章入场测试）
    if "烂尾楼" not in c1 and "烂尾楼" not in c2:
        warns.append("接口四型「位置」在正文无落地（烂尾楼未出现）")
    else:
        infos.append("接口四型「位置」落地：烂尾楼（无碑地带）")

    # 不可申诉之物：碑上旧痕擦不掉只能覆盖
    if "覆盖" in c1 and "刮痕" in c1:
        infos.append("不可申诉之物落地：旧痕擦不掉只能覆盖")
    else:
        errs.append("区域卡「不可申诉之物」（旧痕擦不掉只能覆盖）未在正文落地")

    # 换图条件：主角拿到半枚旧印 + 确认划名非事故 + 被列为待核 → 去乙区
    if "乙区" in c2:
        infos.append("换图已发生：第一章甲区 → 第二章乙区（缝合线过线）")
    else:
        errs.append("换图未发生：正文未过缝合线到乙区")

    # ---------- D. 代价推进链 ----------
    cost_chain = [
        ("学历被抹", ["学历", "硕士"], c1, "第一章"),
        ("工龄被抹三年", ["工龄", "八年"], c2, "第二章"),
        ("亲属关系（待抹）", ["亲属关系"], c2 + c3, "第二章起"),
        ("姓名（最后一样）", ["姓名", "两个残字", "残字"], c1 + c3, "第一章起"),
    ]
    for name, kws, text, when in cost_chain:
        if not any(k in text for k in kws):
            errs.append(f"代价链断裂：「{name}」在正文无落地")
        else:
            infos.append(f"代价链「{name}」（{when}）落地")
    # 顺序：学历在前，工龄在后
    i_edu = c1.find("学历")
    i_work = c2.find("工龄")
    if i_edu >= 0 and i_work >= 0:
        infos.append("代价顺序正确：学历（第一章）→ 工龄（第二章）")
    else:
        warns.append("代价顺序未能确认")

    # ---------- E. 元叙事锚点 ----------
    meta = [
        ("十三册并置", ["十三", "十三块碑", "十三本书"], c1 + c3),
        ("缝合线", ["缝合线"], c1 + c2 + c3),
        ("两版并存", ["两版", "两份"], c1 + c2 + c3),
        ("唯一能判的人", ["唯一", "第三方"], c1 + c3),
    ]
    for name, kws, text in meta:
        if not any(k in text for k in kws):
            warns.append(f"元叙事锚点「{name}」在正文弱或缺")
        else:
            infos.append(f"元叙事锚点「{name}」落地")

    # ---------- F. 装配层工具自检 ----------
    r = subprocess.run([sys.executable, os.path.join(LIB, "check_assembly.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    m = re.search(r"合计：装配体 (\d+)｜ERROR (\d+)｜WARN (\d+)｜INFO (\d+)", out)
    if m:
        infos.append(f"check_assembly.py：{m.group(1)} 装配体／ERROR {m.group(2)}／WARN {m.group(3)}")
        if int(m.group(2)) > 0:
            errs.append(f"check_assembly.py 报 {m.group(2)} 个 ERROR")
    else:
        warns.append("check_assembly.py 未输出可解析的汇总行")

    # ---------- G. 冲突检查：正文是否引入装配体未登记的机制 ----------
    # 正文出现「代管处」「发文员」等设定实体——这些应是 03 登记过的
    bible = read(os.path.join(PROJ, "03-世界观圣经-创造主们的战争.md"))
    # 设定实体清单：正文用到、且必须是 03 登记的（登记处可不在 §7，但必须在 03 全文）
    ENTITIES = [
        ("碑吏", "§7 势力表"),
        ("代管处", "§7 势力表"),
        ("勘定所", "§7 势力表"),
        ("勘定权", "§6 金手指卡"),
        ("划名", "§2.2 法则表／§6.1"),
        ("缝合线", "§10 地理地点表"),
        ("零号窗口", "§10 地理地点表"),
        ("勘定通则", "§2.2 法则表"),
    ]
    for ent, where in ENTITIES:
        if ent in full and ent not in bible:
            errs.append(f"正文引入设定实体「{ent}」（应登记于 03 {where}）但 03 未登记")
        elif ent in full:
            infos.append(f"设定实体「{ent}」已登记于 03（{where}）")

    # ---------- H. 反向检查：03 登记的关键实体是否在正文落地 ----------
    # 只查「卷一必然出现」的三个
    for ent, kw in [("缝合线", "缝合线"), ("零号窗口", "零号窗口")]:
        if ent in bible and kw not in full:
            warns.append(f"03 已登记「{ent}」但正文未落地（可能属后续卷，可忽略）")

    # ---------- 输出 ----------
    print("=" * 64)
    print("二次实战校验 · 《创造主们的战争》卷一三章 vs 零件库装配层")
    print("=" * 64)
    print(f"正文：三章合计 {len(full)} 字符（{len(c1)}/{len(c2)}/{len(c3)}）")
    print(f"装配体：ASM-CCZ-0001　课题「{topic}」")
    print()
    for e in errs:
        print("  ERROR " + e)
    for w in warns:
        print("  WARN  " + w)
    for i in infos:
        print("  INFO  " + i)
    print()
    print(f"合计：ERROR {len(errs)}｜WARN {len(warns)}｜INFO {len(infos)}")
    print("说明：本脚本只判一致性，不判文采与节奏（后者为人工判据）")
    return 1 if (strict and errs) else 0


if __name__ == "__main__":
    sys.exit(main())
