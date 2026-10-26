#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trpg_mechanics.py — TRPG 机制库（可插拔）

把 D&D 5e 的成熟检定/状态/资源机制，映射到《废土旅法师》的叙事场景，
让「写战斗场面」从凭感觉变成有骰子可掷、有阈值可查。

设计立场
--------
网文里的面板要**能算**，读者才会信；但机制不能喧宾夺主变成游戏播报。
因此本库定位是**作者侧工具**：帮你决定「这一击成功率多少」「这个敌人
什么档位」「代价该付多少」，而不是把 d20 写进正文。

三块：
  1. d20 检定：属性修正 = floor((属性-10)/2)，对照 DC 难度表
  2. 变异等级 ↔ 挑战等级（CR）映射：把 §7 谱系接到 5e 难度分档
  3. 状态效果 / 资源 / 代价投骰：灰蚀、污染、僵直、五色法力池

数据来源（联网调研，见 调研-面板系统与外部考据.md）：
  · DC 难度档：5/10/15/20/25/30（Very easy … Nearly impossible）
  · 属性修正公式：floor((score − 10) / 2)
  · 优势/劣势：2d20 取高/取低，**优势劣势不叠加、互相抵消**
  · 豁免 DC = 8 + 施法者修正 + 熟练加值
  · 被动检定 = 10 + 修正

零三方依赖。
"""

from __future__ import annotations

import math
import random
from typing import Any

# --------------------------------------------------------------------------
# 1. d20 检定
# --------------------------------------------------------------------------

# 5e 官方难度分档：DC → 无修正时的成功率
DC_TABLE = [
    {"dc": 5,  "label": "极易",   "base": 80,  "en": "Very easy"},
    {"dc": 10, "label": "简单",   "base": 55,  "en": "Easy"},
    {"dc": 15, "label": "中等",   "base": 30,  "en": "Medium"},
    {"dc": 20, "label": "困难",   "base": 5,   "en": "Hard"},
    {"dc": 25, "label": "极难",   "base": 0,   "en": "Very hard"},
    {"dc": 30, "label": "近乎不可能", "base": 0, "en": "Nearly impossible"},
]

# 五维 → 5e 属性 key
ATTR_MAP = {
    "体质": "con",   # 体质 → 耐力/生命/抗毒
    "根骨": "str",   # 根骨 → 力量/蛮力
    "灵敏": "dex",   # 灵敏 → 敏捷/反应
    "精神": "int",   # 精神 → 思维/法力/解析
    "悟性": "wis",   # 悟性 → 感知/直觉/经验
}


def attr_mod(score: int) -> int:
    """5e 属性修正 = floor((score - 10) / 2)"""
    return math.floor((int(score) - 10) / 2)


def attr_mod_5e(score: int) -> int:
    """本书属性（初始全 4）直接套 5e 公式会得到负值（4→-3），
    因为本书初始值并非 5e 的 3-18 量表。这里做线性映射：

        4 → -1, 10 → 0, 18 → +4, 24 → +7

    即先扣掉本书基准下限 4，再按 5e 公式算。
    """
    return math.floor((int(score) - 4 - 10) / 2)


def success_rate(dc: int, mod: int, advantage: bool = False, disadvantage: bool = False) -> float:
    """给定 DC 与修正，算成功率（%）。优势劣势不叠加、互相抵消（5e 规则）。"""
    net = "adv" if advantage and not disadvantage else ("dis" if disadvantage and not advantage else "norm")
    if net == "norm":
        p = (21 - dc) / 20.0
    elif net == "adv":
        p = sum(((21 - dc) / 20.0) ** i for i in (1, 2))
    else:
        p = (1 - (21 - dc) / 20.0) ** 2
    # 修正不影响概率的滚动次数，只平移成败线；5e 中加 X = DC 减 X
    p = (21 - (dc - mod)) / 20.0
    if net == "adv":
        p = sum(((21 - (dc - mod)) / 20.0) ** i for i in (1, 2))
    elif net == "dis":
        p = (1 - (21 - (dc - mod)) / 20.0) ** 2
    return max(0.0, min(100.0, p * 100))


def roll_check(dc: int, mod: int, advantage: bool = False,
               disadvantage: bool = False, rng: random.Random | None = None) -> dict:
    """掷一次检定。返回 d20 明细、总值与成败。"""
    r = rng or random
    adv = advantage and not disadvantage
    dis = disadvantage and not advantage
    d1 = r.randint(1, 20)
    d2 = r.randint(1, 20) if (adv or dis) else None
    if adv:
        d20, mode = max(d1, d2), "优势"
    elif dis:
        d20, mode = min(d1, d2), "劣势"
    else:
        d20, mode = d1, "正常"
    total = d20 + mod
    return {
        "d20": [x for x in (d1, d2) if x is not None],
        "mode": mode,
        "mod": mod,
        "total": total,
        "dc": dc,
        "success": total >= dc,
        "crit": d20 == 20,
        "fumble": d20 == 1,
        "rate": round(success_rate(dc, mod, adv, dis), 1),
    }


def dc_preset(label: str) -> dict:
    for row in DC_TABLE:
        if row["label"] == label or row["en"].lower() == label.lower():
            return row
    raise ValueError(f"未知难度档: {label}（可选：{[r['label'] for r in DC_TABLE]}）")


# --------------------------------------------------------------------------
# 2. 变异等级 ↔ 挑战档位
# --------------------------------------------------------------------------

# 变异谱系 → 建议 DC / 建议属性档 / 危险度
TIER_TABLE = {
    "零级":         {"dc": 5,  "attr": 10, "danger": "背景板",   "note": "零级火花 0，仅作氛围；不构成战斗"},
    "一级":         {"dc": 10, "attr": 10, "danger": "遭遇",     "note": "单体可搏；围一群则危险"},
    "二级":         {"dc": 13, "attr": 13, "danger": "硬战",     "note": "多器官异常、类策略，需弱点解析"},
    "三级":         {"dc": 18, "attr": 16, "danger": "搏命",     "note": "脱离原物种，弱点/时机决定生死"},
    "王级":         {"dc": 25, "attr": 20, "danger": "不可交战", "note": "高智慧统御同类，理论上不应硬碰"},
    "坠影级(S+)":   {"dc": None, "attr": 24, "danger": "送终",  "note": "面板判「？？？」，不可击杀取火花"},
}


def tier_profile(tier) -> dict:
    """取某变异等级的 TRPG 档案。

    容错：等级可能以 '二级' / '二级 ' / 数字序号 2 传入（前端 select
    传 index、curl 直传数字），统一归一后再查表。
    """
    keys = list(TIER_TABLE.keys())
    if isinstance(tier, int):
        idx = tier - 1 if 0 <= tier - 1 < len(keys) else tier
        if 0 <= idx < len(keys):
            return dict(TIER_TABLE[keys[idx]], tier=keys[idx])
        raise ValueError(f"未知变异等级序号: {tier}")
    s = str(tier)
    key = next((k for k in keys if k.replace(" ", "") in s.replace(" ", "")), None)
    if not key:
        raise ValueError(f"未知变异等级: {tier}")
    return dict(TIER_TABLE[key], tier=key)


def matchup(profiles: list[dict]) -> dict:
    """群遭遇配平：按 5e 预算模型，n 个同级怪的总危险不是 n 倍而是约 n^1.5 倍。

    参考 EN World 讨论的三角和近似：合成难度 ≈ (Σ 单体难度^1.5)^(2/3)。
    """
    if not profiles:
        return {"ok": False, "error": "缺少怪物档案"}
    budget = 0.0
    for p in profiles:
        dc = p.get("dc") or 15
        attr = p.get("attr") or 10
        mon = (attr * (1 + 0.06 * max(0, dc - 10)))
        budget += mon ** 1.5
    total = budget ** (2 / 3)
    # 反推建议 DC
    suggest_dc = int(round(10 + (total - 10) / 0.6 / 6)) if total > 10 else 10
    return {
        "ok": True,
        "count": len(profiles),
        "monsterBudget": round(budget, 1),
        "encounterBudget": round(total, 1),
        "suggestDC": max(5, min(30, suggest_dc)),
        "note": "合成难度 ≈ (Σ 单体^1.5)^(2/3)；n 只同级怪总危险约 n^1.5 倍，不是 n 倍",
        "dangerLabel": dc_preset_label(max(5, min(30, suggest_dc))),
    }


def dc_preset_label(dc: int) -> str:
    best = min(DC_TABLE, key=lambda r: abs(r["dc"] - dc))
    return best["label"]


# --------------------------------------------------------------------------
# 3. 状态效果（对应本书的污染/代价体系）
# --------------------------------------------------------------------------

STATUS_EFFECTS = [
    {"key": "gray_erosion", "name": "灰蚀", "attr": "体质", "penalty": -1,
     "condition": "灰线格数 > 30", "desc": "耐辐射、抗法力能力下降，末端出现无法施力的旧格",
     "stacking": "按格数叠加，每 10 格额外 -1"},
    {"key": "sweat_loss", "name": "灰线汗腺失能", "attr": "体质", "penalty": 0,
     "condition": "灰线爬过处", "desc": "分界齐整、热水/凉水/运动/灶烤均不出汗（91章判定）",
     "stacking": "不叠加（布尔状态）"},
    {"key": "stiffness", "name": "僵直", "attr": "灵敏", "penalty": -2,
     "condition": "灰线发作时", "desc": "左手三指僵直，解除次序与僵住倒序",
     "stacking": "按发作计时（min）"},
    {"key": "pollution", "name": "污染·进行性", "attr": "精神", "penalty": -1,
     "condition": "灰线扩张中", "desc": "写不写规矩都长，税无免征日（99章判定）",
     "stacking": "持续加剧，不可逆（除 220 章冻结）"},
    {"key": "mycelium", "name": "菌丝寄生", "attr": "体质", "penalty": -2,
     "condition": "被寄生体缠绕", "desc": "体表生暗红菌丝、眼发蓝紫荧光；弱点＝脊背菌丝根部蓝紫节点",
     "stacking": "需凝晶原液/退丝药解除"},
    {"key": "structural_tax", "name": "结构税", "attr": "精神", "penalty": -1,
     "condition": "五色组合施法", "desc": "组合越复杂，灰线增长越快（R13）",
     "stacking": "按组合复杂度"},
    {"key": "black_burn", "name": "黑色代偿", "attr": "精神", "penalty": -1,
     "condition": "烧记忆换法力", "desc": "以记忆/情感碎片为燃料，一次消耗一段，不可复原（R9）",
     "stacking": "单次可烧档位 = 黑×N"},
]


def apply_status(state: dict, key: str) -> dict:
    """给面板叠加状态。返回 diff。"""
    eff = next((e for e in STATUS_EFFECTS if e["key"] == key), None)
    if not eff:
        return {"ok": False, "error": f"未知状态: {key}"}
    state.setdefault("statuses", {})
    st = state["statuses"].setdefault(key, {"n": 0, "attr": eff["attr"], "penalty": 0})
    st["n"] += 1
    st["penalty"] = eff["penalty"] * st["n"]
    return {"ok": True, "status": eff["name"], "attr": eff["attr"],
            "totalPenalty": st["penalty"], "count": st["n"],
            "desc": eff["desc"]}


def effective_attrs(state: dict) -> dict:
    """把状态惩罚折算进有效属性（用于检定）。"""
    from panel_engine import ATTR_ORDER, new_state
    base = {k: v for k, v in (state.get("attrs") or {}).items()} or {k: 4 for k in ATTR_ORDER}
    eff = dict(base)
    for st in (state.get("statuses") or {}).values():
        attr = st.get("attr")
        if attr in eff:
            eff[attr] += st.get("penalty", 0)
    return eff


# --------------------------------------------------------------------------
# 4. 代价投骰（黑色法力以记忆为燃料）
# --------------------------------------------------------------------------

BURN_MODES = [
    {"key": "self", "name": "燃己之忆", "speed": "速", "risk": "低",
     "desc": "烧自己私人的记忆片段，见效快，代价小", "example": "办公室窗外那棵树（第40章）"},
    {"key": "recorded", "name": "燃记于己者", "speed": "缓", "risk": "中",
     "desc": "烧「自己曾记得」这件事本身，见效慢，代价大", "example": "落册那夜签册第二栏「来路」（111章）"},
    {"key": "shared", "name": "燃己所记而人亦记之", "speed": "禁", "risk": "极高",
     "desc": "烧掉的是别人也记得的事——碑上第五行明文禁止", "example": "（禁术，正文不得使用）"},
]


def burn_cost_roll(volume: int, black_mult: int, mode_key: str = "self",
                   rng: random.Random | None = None) -> dict:
    """代价投骰：按卷与代偿档位决定这次燃烧的「症状等级」。

    这是叙事工具不是数值工具——返回该次燃烧应该写到多深（症状清单）。
    """
    r = rng or random
    mode = next((m for m in BURN_MODES if m["key"] == mode_key), None)
    if not mode:
        return {"ok": False, "error": f"未知燃法: {mode_key}"}
    if mode_key == "shared":
        return {"ok": False, "error": "燃己所记而人亦记之——碑上禁术，正文不得使用（R9）"}

    base = {"1": 1, "2": 1, "3": 2, "4": 2, "5": 3}.get(str(volume), 1)
    depth = base + (1 if mode["speed"] == "缓" else 0)
    depth += r.randint(0, 1)
    depth = max(1, min(5, depth * (1 if black_mult < 2 else 1)))

    SYMPTOMS = {
        1: ["端东西洒一点", "写字略歪", "习惯性小动作消失（自己后知后觉）"],
        2: ["精细操作明显下降", "旁人先发现异常", "某个熟悉场景认不出"],
        3: ["能力退化到影响战斗", "关键台词说不出口", "靠他人接住"],
        4: ["认不出至亲的脸", "站在自家门口犹豫", "由别人替他记住"],
        5: ["记忆只剩功能没有画面", "连「以前会」都不记得", "元认知丧失"],
    }
    return {
        "ok": True,
        "volume": volume,
        "blackMult": black_mult,
        "mode": mode["name"],
        "modeDesc": mode["desc"],
        "depth": depth,
        "symptoms": SYMPTOMS[depth],
        "rule": "失忆写行为不写独白（长弧规划·写作纪律）",
        "example": mode["example"],
    }


# --------------------------------------------------------------------------
# 汇总
# --------------------------------------------------------------------------

def toolbox() -> dict:
    """给 GUI 展示的机制库总览。"""
    return {
        "dcTable": DC_TABLE,
        "attrMap": ATTR_MAP,
        "tierTable": [{"tier": k, **v} for k, v in TIER_TABLE.items()],
        "statusEffects": STATUS_EFFECTS,
        "burnModes": BURN_MODES,
        "formulas": {
            "attrMod5e": "floor((属性 − 4 − 10) / 2)  —— 因本书初始值 4 低于 5e 的 3-18 量表下限，先扣基准",
            "attrModRaw": "floor((score − 10) / 2)  —— 标准 5e 公式",
            "success": "P(成功) = (21 − (DC − 修正)) / 20；优势 = 1 − (1−p)²；劣势 = p²",
            "encounter": "合成难度 ≈ (Σ 单体^1.5)^(2/3)",
            "saveDC": "豁免 DC = 8 + 施法者修正 + 熟练加值",
            "passive": "被动检定 = 10 + 修正",
        },
    }


if __name__ == "__main__":
    print("=== d20 检定：体质 18 攻 深渊蟑螂王（DC 18）===")
    r = roll_check(18, attr_mod_5e(18))
    print(f"  {r['mode']} {r['d20']} + {r['mod']} = {r['total']} vs DC {r['dc']} → "
          f"{'成功' if r['success'] else '失败'}（成功率 {r['rate']}%）")
    print("\n=== 群遭遇配平：7 只二级 + 1 只三级母体 ===")
    p = [tier_profile("二级")] * 7 + [tier_profile("三级")]
    m = matchup(p)
    print(f"  预算 {m['monsterBudget']} → 合成 {m['encounterBudget']}，建议 DC {m['suggestDC']}（{m['dangerLabel']}）")
    print("\n=== 代价投骰（第五卷·黑×5·燃记于己者）===")
    b = burn_cost_roll(5, 5, "recorded")
    print(f"  {b['mode']} 深度{b['depth']}: {'、'.join(b['symptoms'])}")
