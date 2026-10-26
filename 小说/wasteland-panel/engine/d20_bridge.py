#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
d20_bridge.py —— D20 规则内核适配层（废土旅法师 ↔ allin_engine.trpg）

为什么要有这一层
----------------
D20 项目的规则内核（siwpan/d20 v3.0 → allin-engine 的 ``allin_engine.trpg``）
是通用 D&D-GURPS 变体角色构建器：六属性、点数购买、技能难度分级、战斗宏。
《废土旅法师》的世界观跟它**不是同一套量表**，直接灌进去会当场翻车：

  · 本书五维初始 4，内核属性**不能低于 10**（set_attribute(力量,4) → 报
    "属性不能低于10"）——必须做量表映射，不能直灌。
  · 内核 HP 由「活力」技能推导，不买活力 max_hp = 0，战斗根本开不了场。
  · 内核 combat_macro() 返回的是**给人看的字符串**
    （'⚔ 近战攻击: d20+10 = 3+10 = 13 vs AC 12\\n  ✓ 命中！伤害: 1d3+2 = 4'），
    没有结构化字段，驱动不了回合制战斗；而且未装备武器时伤害退化成徒手 1d3。
  · 内核 hp() 返回的是**满血值**（take_damage 之后 hp() 不变），
    战斗期的当前 HP 必须本层自己记账。

所以本层的立场是：**数值口径从内核取，战斗循环自己搭**。
属性修正、攻击加值、AC、豁免、伤害骰、技术惩罚、法术位——一律问内核要；
骰子用内核的 roll_*；HP/回合/状态这类内核不提供的，本层负责。

零三方依赖（allin-engine 是本仓主动引入的唯一运行时依赖，见 README）。
内核缺失时**报明确错误**，不静默降级——本仓硬约定：环境不对应当报"找不到"。
"""

from __future__ import annotations

import math
from typing import Any

# --------------------------------------------------------------------------
# 内核导入
# --------------------------------------------------------------------------

_KERNEL_ERR: str | None = None
try:
    from allin_engine import trpg as _trpg
except Exception as e:                                  # pragma: no cover
    _trpg = None
    _KERNEL_ERR = (
        f"未能导入 D20 规则内核 allin_engine.trpg：{type(e).__name__}: {e}\n"
        "战斗沙盘依赖该内核。请先安装：pip install allin-engine\n"
        "（本仓推荐装进独立虚拟环境，见 README「运行依赖」一节）"
    )


def kernel_available() -> tuple[bool, str | None]:
    """内核是否可用。返回 (可用?, 错误信息)。"""
    return (_trpg is not None, _KERNEL_ERR)


def require_kernel():
    """取内核；不可用则抛 RuntimeError（带安装指引）。"""
    if _trpg is None:
        raise RuntimeError(_KERNEL_ERR)
    return _trpg


# --------------------------------------------------------------------------
# 1. 五维 → 六属性量表映射
# --------------------------------------------------------------------------

# 本书五维 → 内核属性（与 trpg_mechanics.ATTR_MAP 保持同一口径）
#   体质→体质、根骨→力量、灵敏→敏捷、精神→智力、悟性→感知
#   魅力：本书无对应维度，取常人 10（不参与废土判定）
WASTELAND_ATTRS = ["体质", "根骨", "灵敏", "精神", "悟性"]
ATTR_MAP = {
    "体质": "体质",
    "根骨": "力量",
    "灵敏": "敏捷",
    "精神": "智力",
    "悟性": "感知",
}
CHARM_FALLBACK = 10          # 魅力无废土对应，固定常人值

# 量表换算：本书 4 起步（常人偏弱），内核 10 起步（5e 常人）。
# 线性斜率 0.65：4→10、10→14、14→17、20→20（封顶），既保留成长感又不至于爆表。
_WL_SLOPE = 0.65
_ATTR_MIN, _ATTR_MAX = 10, 20


def wl2d20(v: Any) -> int:
    """本书属性值 → 内核属性值（10–20 封顶）。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = 4.0
    return max(_ATTR_MIN, min(_ATTR_MAX, int(10 + (f - 4) * _WL_SLOPE + 0.5)))


# 技能等级换算：本书 4 起步最低给 1 级（内核要求 ≥1 才算"学过"，
# 否则攻击加值走"未学默认值"，会把主角的战力算成路人）。
_SKILL_SLOPE = 0.75
_SKILL_MIN, _SKILL_MAX = 1, 16


def wl2rank(v: Any, spark: int = 0) -> int:
    """本书属性值 → 技能等级（1–16 封顶）。

    火花进度会额外抬等级：面板上"火花"是主角变强的**唯一度量**，
    只按五维算会让第一卷主角和第五卷主角一样弱，与正文不符。
    每 15% 火花 +1 级（100% 点燃 → +6）。
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = 4.0
    try:
        sp = max(0, int(spark))
    except (TypeError, ValueError):
        sp = 0
    base = 1 + (f - 4) * _SKILL_SLOPE + sp / 15.0
    return max(_SKILL_MIN, min(_SKILL_MAX, int(base + 0.5)))


def spark_level(spark: int, ignited: bool = False) -> int:
    """火花 → 火种期等级（1–10，点燃后 11 级起）。用于 HP 淬炼加成与展示。"""
    try:
        sp = max(0, min(100, int(spark)))
    except (TypeError, ValueError):
        sp = 0
    return (1 + sp // 10) + (10 if ignited else 0)


# 五维 → 默认技能包（废土旅法师的"面板会自动点亮"的那些行）
# 技能名必须是内核 SKILL_LIBRARY 里存在的键，否则 purchase_skill 会返回"未知技能"。
SKILL_PACKAGE = {
    "近战攻击": "根骨",
    "远程攻击": "灵敏",
    "闪避防御": "灵敏",
    "活力": "体质",          # 不买这个 HP = 0
    "强韧豁免": "体质",
    "反射豁免": "灵敏",
    "意志豁免": "悟性",
    "奥术施法": "精神",      # 法术位前置
    "施法攻击": "精神",
    "侦察": "悟性",
    "洞察": "悟性",
    "生存": "悟性",
}

# 点火后（火花 100%）才亮起的技能——对应面板"点燃"解锁
IGNITED_SKILLS = ("奥术施法", "施法攻击")

# 默认装备（面板态角色的起手行头；可在 spec 里覆盖）
DEFAULT_EQUIPMENT = ["长剑", "镶钉皮甲"]

# 天赋组（内核 TALENT_BONUS_GROUPS）——按五维最高项给一个
TALENT_BY_ATTR = {
    "根骨": "重击战士",
    "灵敏": "轻巧战法",
    "精神": "魔法学识",
    "悟性": "机敏斥候",
    "体质": "自然之子",
}

# --------------------------------------------------------------------------
# 2. 五色法力 → 法术（废土化）
# --------------------------------------------------------------------------

# 内核法术技术名 → 废土法力色 / 环位 / 中文动作名
SPELL_LIBRARY = {
    "火球术":     {"color": "红", "ring": 3, "label": "赤焰爆发",
                   "desc": "3 环：8d6 火焰，范围爆发（R13 五色组合征税）"},
    "闪电束":     {"color": "蓝", "ring": 3, "label": "电离长矛",
                   "desc": "3 环：8d6 闪电，直线贯穿"},
    "寒冰锥":     {"color": "蓝", "ring": 5, "label": "霜蚀锥",
                   "desc": "5 环：8d8 寒冷，锥形"},
    "魔法飞弹":   {"color": "白", "ring": 1, "label": "辉光弹",
                   "desc": "1 环：3 发自动命中，每发 1d4+1 力场"},
    "治疗言灵":   {"color": "绿", "ring": 1, "label": "生息言灵",
                   "desc": "1 环：1d4+施法调整 恢复生命"},
    "火焰箭":     {"color": "红", "ring": 0, "label": "燃焰箭",
                   "desc": "戏法：1d10 火焰，不耗法力位"},
    "霜冻射线":   {"color": "蓝", "ring": 0, "label": "凝霜射线",
                   "desc": "戏法：1d8 寒冷，不耗法力位"},
}

# 黑色：不是法术，是代偿——以记忆为燃料（R9）。走 trpg_mechanics.burn_cost_roll。
BLACK_MANA_NOTE = "黑色法力不进法术表：它烧的是记忆，代价由代价投骰决定（R9）"

# --------------------------------------------------------------------------
# 3. 战斗技术（内核 TECHNIQUES → 废土动作）
# --------------------------------------------------------------------------

# 内核元组：[关联技能, CP, 属性要求, 惩罚, 等级需求, 说明]
# 这里只登记"沙盘里能按得出来"的动作及其废土化命名。
MANEUVERS = {
    "melee_attack":       {"tech": None,           "label": "普通攻击",     "kind": "attack",
                           "desc": "d20 + 近战攻击加值 vs AC"},
    "ranged_attack":      {"tech": None,           "label": "远程攻击",     "kind": "attack",
                           "desc": "d20 + 远程攻击加值 vs AC"},
    "power_attack":       {"tech": "猛力攻击",      "label": "猛力攻击",     "kind": "attack",
                           "desc": "命中 -1 / 伤害 +2（双手 +3）"},
    "whirlwind":          {"tech": "旋风切割",      "label": "旋风切割",     "kind": "multi",
                           "desc": "对周围所有敌人各一次攻击（惩罚 -6）"},
    "sneak_attack":       {"tech": "偷袭要害打击",  "label": "偷袭要害",     "kind": "attack",
                           "desc": "需灵巧武器 + 措手不及，精准伤害随等级成长"},
    "deceptive_attack":   {"tech": "欺诈攻击",      "label": "欺诈攻击",     "kind": "attack",
                           "desc": "自攻 -2 / 敌防 -1（不可使技能低于 10）"},
    "rapid_strike":       {"tech": "连环打击",      "label": "连环打击",     "kind": "multi",
                           "desc": "一回合两次攻击，各 -6"},
    "allout_strong":      {"tech": "全力强击",      "label": "全力强击",     "kind": "attack",
                           "desc": "伤害 +2，本回合无法防御"},
    "allout_determined":  {"tech": "精准突击",      "label": "精准突击",     "kind": "attack",
                           "desc": "命中 +4，本回合无法防御"},
    "analyze":            {"tech": None,           "label": "弱点解析",     "kind": "special",
                           "desc": "侦察/洞察检定（DC 按变异等级）；成功前弱点伤害不生效"},
    "defend":             {"tech": None,           "label": "举盾防御",     "kind": "defend",
                           "desc": "本回合 AC +2，放弃攻击（内核无此宏，本层实现）"},
    "gray_surge":         {"tech": None,           "label": "灰线爆发",     "kind": "special",
                           "desc": "烧灰线格数换伤害：每 3 格 +1d6，灰线加深 2 格（R11/R13）"},
    "black_burn":         {"tech": None,           "label": "黑色代偿",     "kind": "special",
                           "desc": "以记忆为燃料换法力，代价走代价投骰（R9）"},
}


def available_maneuvers(char) -> list[dict]:
    """按角色已学技术，列出沙盘里当前能按的动作。"""
    out = []
    for key, m in MANEUVERS.items():
        tech = m["tech"]
        ok = True
        if tech is not None:
            try:
                ok = bool(char.has_technique(tech))
            except Exception:
                ok = False
        if m["kind"] == "defend":
            ok = True
        if m["kind"] == "special" and key == "gray_surge":
            ok = True
        out.append({"key": key, "label": m["label"], "kind": m["kind"],
                    "desc": m["desc"], "ready": ok, "tech": tech,
                    "blockedReason": None if ok else f"未学会「{tech}」技术"})
    # 法术：按已学技术 + 五色法力列出
    for tech, info in SPELL_LIBRARY.items():
        try:
            has = char.has_technique(tech)
        except Exception:
            has = False
        out.append({"key": f"spell:{tech}", "label": info["label"], "kind": "spell",
                    "desc": info["desc"], "ready": has, "tech": tech,
                    "color": info["color"], "ring": info["ring"],
                    "blockedReason": None if has else f"未学会「{tech}」"})
    return out


# --------------------------------------------------------------------------
# 4. 角色构建
# --------------------------------------------------------------------------

# 面板态构建用的 CP 池：面板状态是**设定事实**（第 N 章主角就是这么强），
# 不该被内核的点数经济卡住，所以给一个大池，再把实际花掉的量报出来当"强度参考分"。
BUILD_CP_POOL = 100_000


def _new_char(starting_cp: int):
    trpg = require_kernel()
    try:
        return trpg.Character(starting_cp=starting_cp)
    except TypeError:                                   # 老签名兜底
        return trpg.Character()


def _buy(char, fn, *args) -> tuple[bool, str]:
    """执行一笔购买，统一返回 (ok, msg)；内核抛异常时不炸整个构建。"""
    try:
        r = fn(*args)
        if isinstance(r, (tuple, list)) and len(r) >= 2:
            return bool(r[0]), str(r[1])
        return True, str(r)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def build_from_panel(state: dict, name: str = "魏成河",
                     equipment: list[str] | None = None,
                     techniques: list[str] | None = None) -> dict:
    """由面板状态（panel_engine 的 state）生成可战斗角色。

    state 关键字段：attrs（五维）、spark、ignited、grayCells、volume、
    manaPool、unlocked。缺失字段按面板初值兜底，不抛异常。
    """
    trpg = require_kernel()
    attrs = dict(state.get("attrs") or {}) or {k: 4 for k in WASTELAND_ATTRS}
    ignited = bool(state.get("ignited"))
    spark = int(state.get("spark") or 0)

    char = _new_char(BUILD_CP_POOL)
    spent0 = char.cp
    log: list[str] = []

    # --- 属性 ---
    for wl, d20 in ATTR_MAP.items():
        ok, msg = _buy(char, char.set_attribute, d20, wl2d20(attrs.get(wl, 4)))
        log.append(f"属性 {wl}({attrs.get(wl, 4)}) → {d20} {wl2d20(attrs.get(wl, 4))}：{msg}")

    # --- 技能包（未点燃则不点亮施法系） ---
    for skill, wl in SKILL_PACKAGE.items():
        if skill in IGNITED_SKILLS and not ignited:
            continue
        rank = wl2rank(attrs.get(wl, 4), spark)
        ok, msg = _buy(char, char.purchase_skill, skill, rank)
        log.append(f"技能 {skill} → {rank}（五维 {attrs.get(wl, 4)} + 火花 {spark}）：{msg}")

    # --- 天赋（取五维最高项对应的天赋组） ---
    top = max(WASTELAND_ATTRS, key=lambda k: float(attrs.get(k, 4) or 4))
    talent = TALENT_BY_ATTR.get(top)
    if talent:
        ok, msg = _buy(char, char.add_talent, talent, 2)
        log.append(f"天赋 {talent} → 2 级：{msg}")

    # --- 装备 ---
    for item in (equipment if equipment is not None else DEFAULT_EQUIPMENT):
        ok, msg = _buy(char, char.equip_item, item)
        log.append(f"装备 {item}：{msg}")

    # --- 技术（战技/法术） ---
    for tech in (techniques or []):
        ok, msg = _buy(char, char.purchase_technique, tech)
        log.append(f"技术 {tech}：{msg}")

    # --- 点燃后补法术位（五色法力池） ---
    if ignited:
        for ring in (1, 2, 3):
            ok, msg = _buy(char, char.buy_slot, ring)
            if ok:
                log.append(f"法术位 {ring} 环：{msg}")

    sb = stat_block(char, name=name, side="pc", level=spark_level(spark, ignited))
    sb["buildLog"] = log
    sb["cpSpent"] = spent0 - char.cp
    sb["source"] = {"mode": "panel", "spark": spark, "ignited": ignited,
                    "grayCells": state.get("grayCells", 0),
                    "volume": state.get("volume", 1)}
    sb["char"] = char          # 内核实例；不参与 JSON 序列化
    return sb


# --------------------------------------------------------------------------
# 4b. 剧情档位预设
# --------------------------------------------------------------------------
#
# 沙盘要"一进来就能打"，而不是面对一个攻击 +1、HP 6 的火柴人。
# 这里按正文各卷的实际面板状态给出几档预设，选一档即可开打。
# 数值依据：world-bible §2f 解锁总表 + §3.5 耐受递增表。

PROFILES: dict[str, dict] = {
    "v1-seed": {
        "label": "第一卷 · 火种期初启（第 5 章）",
        "spark": 4, "ignited": False, "volume": 1,
        "attrs": {"体质": 5, "根骨": 5, "灵敏": 4, "精神": 4, "悟性": 6},
        "equipment": ["短剑", "皮甲"],
        "techniques": [],
        "note": "面板刚亮，五维近乎常人；打零级/一级异族都要拼命",
    },
    "v2-gray": {
        "label": "第二卷 · 灰线初现（第 40 章）",
        "spark": 25, "ignited": False, "volume": 2,
        "attrs": {"体质": 7, "根骨": 8, "灵敏": 7, "精神": 8, "悟性": 8},
        "equipment": ["长剑", "镶钉皮甲"],
        "techniques": ["猛力攻击"],
        "note": "已解锁属性加点与突破；灰线开始爬，但尚未点燃",
    },
    "v3-mycelium": {
        "label": "第三卷 · 菌丝与合围（第 91 章）",
        "spark": 58, "ignited": False, "volume": 3,
        "attrs": {"体质": 10, "根骨": 11, "灵敏": 11, "精神": 12, "悟性": 10},
        "equipment": ["长剑", "锁子衫"],
        "techniques": ["猛力攻击", "欺诈攻击", "连环打击"],
        "note": "弱点解析成型（菌丝节点），能打二级；三级仍需搏命",
    },
    "v5-ignited": {
        "label": "第五卷 · 点燃之后（第 141 章）",
        "spark": 100, "ignited": True, "volume": 5,
        "attrs": {"体质": 14, "根骨": 16, "灵敏": 15, "精神": 18, "悟性": 14},
        "equipment": ["长剑", "半身板甲"],
        "techniques": ["猛力攻击", "欺诈攻击", "连环打击", "火球术", "闪电束",
                       "魔法飞弹", "治疗言灵", "寒冰锥"],
        "manaPool": {"白": 3, "蓝": 4, "黑": 2, "红": 4, "绿": 2},
        "note": "鹏洛克·位面行走者；五色法力池点亮，黑色代偿黑×5",
    },
}


def build_from_profile(key: str, name: str = "魏成河") -> dict:
    """按剧情档位预设生成角色（沙盘一键开局用）。"""
    p = PROFILES.get(key)
    if not p:
        raise ValueError(
            f"未知剧情档位: {key}（可选：{list(PROFILES)}）")
    state = {
        "attrs": dict(p["attrs"]),
        "spark": p["spark"],
        "ignited": p["ignited"],
        "grayCells": 0,
        "volume": p.get("volume", 1),
        "manaPool": dict(p.get("manaPool") or {"白": 0, "蓝": 0, "黑": 0, "红": 0, "绿": 0}),
    }
    sb = build_from_panel(state, name=name,
                          equipment=list(p["equipment"]),
                          techniques=list(p["techniques"]))
    sb["profile"] = {"key": key, "label": p["label"], "note": p["note"]}
    sb["manaPool"] = state["manaPool"]
    return sb


def build_from_spec(spec: dict) -> dict:
    """按显式规格构建（角色构建玩法）：

    spec = { name, cp, attributes:{五维或六属性}, skills:{名:等级},
             techniques:[...], equipment:[...], talents:[[名,等级]] }
    """
    trpg = require_kernel()
    cp = int(spec.get("cp") or 0)
    # 火花换 CP：火种期每 1% 火花 +2 CP，点燃额外 +100
    spark = int(spec.get("spark") or 0)
    ignited = bool(spec.get("ignited"))
    budget = trpg.DEFAULT_STARTING_CP + cp + spark * 2 + (100 if ignited else 0)

    char = _new_char(budget)
    log: list[str] = []
    attrs_in = dict(spec.get("attributes") or {})

    for k, v in attrs_in.items():
        # 允许直接给六属性（力量/敏捷/体质/智力/感知/魅力）或本书五维
        target = k if k in ATTR_MAP.values() else ATTR_MAP.get(k)
        if not target:
            log.append(f"属性 {k}：忽略（无对应）")
            continue
        val = v if (k in ATTR_MAP.values()) else wl2d20(v)
        ok, msg = _buy(char, char.set_attribute, target, max(10, min(20, int(val))))
        log.append(f"属性 {k}→{target} {val}：{msg}")

    # 未指定活力时兜底 1 级，避免 max_hp = 0 打不开战斗
    skills_in = dict(spec.get("skills") or {})
    skills_in.setdefault("活力", 1)
    for s, r in skills_in.items():
        ok, msg = _buy(char, char.purchase_skill, s, int(r))
        log.append(f"技能 {s} → {r}：{msg}")

    for t in (spec.get("techniques") or []):
        ok, msg = _buy(char, char.purchase_technique, t)
        log.append(f"技术 {t}：{msg}")

    for t in (spec.get("talents") or []):
        if isinstance(t, (list, tuple)):
            ok, msg = _buy(char, char.add_talent, t[0], t[1] if len(t) > 1 else 1)
        else:
            ok, msg = _buy(char, char.add_talent, t, 1)
        log.append(f"天赋 {t}：{msg}")

    for e in (spec.get("equipment") or []):
        ok, msg = _buy(char, char.equip_item, e)
        log.append(f"装备 {e}：{msg}")

    sb = stat_block(char, name=spec.get("name") or "无名旅法师", side="pc",
                    level=spark_level(spark, ignited))
    sb["buildLog"] = log
    sb["cpSpent"] = budget - char.cp
    sb["cpLeft"] = char.cp
    sb["cpBudget"] = budget
    sb["source"] = {"mode": "spec", "spark": spark, "ignited": ignited}
    sb["char"] = char
    return sb


# --------------------------------------------------------------------------
# 5. stat block 提取
# --------------------------------------------------------------------------

def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def stat_block(char, name: str = "", side: str = "pc", level: int = 0) -> dict:
    """把内核 Character 摊平成战斗层要用的结构化数值。

    注意：hp 记的是**当前 HP**（战斗层自己维护），初始值取内核 max_hp。
    内核的 hp() 返回满血值，不能当当前血量用——这是踩过的坑。

    level（火种期等级）只加**淬炼 HP**，不动攻击/AC/豁免——
    那些必须保持内核口径，否则数值就没有可追溯的规则依据了。
    """
    trpg = require_kernel()
    attrs = dict(_safe(lambda: char.attributes, {}) or {})
    skills = dict(_safe(lambda: char.skills, {}) or {})
    techs = list(_safe(lambda: char.techniques, []) or [])
    equip = list(_safe(lambda: char.equipment, []) or [])

    base_hp = int(_safe(lambda: float(char.max_hp), 0.0) or 0)
    hp_bonus = max(0, int(level)) * 3        # 火种期淬炼：每级 +3 HP
    max_hp = base_hp + hp_bonus
    ac = int(_safe(lambda: char.ac, 10) or 10)
    atk_m = int(_safe(lambda: char.attack_bonus(True), 0) or 0)
    atk_r = int(_safe(lambda: char.attack_bonus(False), 0) or 0)

    weapon = pick_weapon(equip)
    dice = trpg.WEAPON_DICE.get(weapon, trpg.WEAPON_DICE.get("徒手", (1, 3)))
    str_mod = max(0, (int(attrs.get("力量", 10)) - 10) // 2)
    dex_mod = (int(attrs.get("敏捷", 10)) - 10) // 2

    return {
        "name": name or "无名",
        "side": side,
        "level": max(0, int(level)),
        "maxHp": max_hp,
        "hp": max_hp,
        "baseHp": base_hp,
        "hpBonus": hp_bonus,
        "ac": ac,
        "atkMelee": atk_m,
        "atkRanged": atk_r,
        "initMod": dex_mod,
        "saves": {
            "fort": int(_safe(lambda: char.save_bonus("fort"), 0) or 0),
            "ref": int(_safe(lambda: char.save_bonus("ref"), 0) or 0),
            "will": int(_safe(lambda: char.save_bonus("will"), 0) or 0),
        },
        "attributes": attrs,
        "skills": skills,
        "techniques": techs,
        "equipment": equip,
        "weapon": weapon,
        "weaponDice": list(dice),
        "strMod": str_mod,
        "dexMod": dex_mod,
        "statuses": {},
        "alive": max_hp > 0,
    }


def pick_weapon(equipment: list[str]) -> str:
    """从装备列表里挑当前武器（内核没有 get_equipped_weapon，本层补）。

    规则：取 WEAPON_DICE 里存在、且骰面最大的那件；没有则徒手。
    """
    trpg = require_kernel()
    best, best_die = "徒手", -1
    for e in equipment or []:
        d = trpg.WEAPON_DICE.get(e)
        if not d:
            continue
        score = d[0] * d[1]
        if score > best_die:
            best, best_die = e, score
    return best


def is_finesse(weapon: str) -> bool:
    trpg = require_kernel()
    return weapon in trpg.FINESSE_WEAPONS


# --------------------------------------------------------------------------
# 6. 骰子（统一入口，便于测试注入 rng）
# --------------------------------------------------------------------------

def roll_d20(rng=None) -> int:
    trpg = require_kernel()
    try:
        return int(trpg.roll_d20(rng=rng) if rng is not None else trpg.roll_d20())
    except TypeError:
        return (rng or _default_rng).randint(1, 20)


def roll_dice(count: int, size: int, rng=None) -> list[int]:
    trpg = require_kernel()
    try:
        if rng is not None:
            return [int(rng.randint(1, size)) for _ in range(max(0, int(count)))]
        return [int(trpg.roll_dice(1, size)) for _ in range(max(0, int(count)))]
    except Exception:
        return [1] * max(0, int(count))


def roll_weapon(weapon: str, rng=None) -> tuple[list[int], str]:
    """掷武器伤害骰，返回 (各骰点数, 'NdM' 描述)。"""
    trpg = require_kernel()
    n, m = trpg.WEAPON_DICE.get(weapon, trpg.WEAPON_DICE.get("徒手", (1, 3)))
    rolls = roll_dice(n, m, rng)
    return rolls, f"{n}d{m}"


def roll_3d6(rng=None) -> tuple[list[int], int]:
    rolls = roll_dice(3, 6, rng)
    return rolls, sum(rolls)


# 默认 rng（内核 roll_* 不接受 rng 参数时兜底）
import random as _random_mod                              # noqa: E402
_default_rng = _random_mod.Random()


# --------------------------------------------------------------------------
# 7. 内核数据快照（给前端做下拉框/说明用）
# --------------------------------------------------------------------------

def kernel_catalog() -> dict:
    """规则数据总览：技能库/装备库/技术/法术/优缺点/天赋组/武器骰。"""
    trpg = require_kernel()
    return {
        "ok": True,
        "attributes": list(trpg.ATTRIBUTES),
        "skills": {k: {"attr": v[0], "diff": v[1], "foundation": bool(v[2])}
                   for k, v in trpg.SKILL_LIBRARY.items()},
        "equipment": {k: {"kind": v[0], "sub": v[1], "ac": v[2], "maxDex": v[3],
                          "weight": v[4], "desc": v[5], "cp": v[6]}
                      for k, v in trpg.EQUIPMENT_LIBRARY.items()},
        "techniques": {k: {"skill": v[0], "cp": v[1], "req": v[2], "penalty": v[3],
                           "minRank": v[4], "desc": v[5]}
                       for k, v in trpg.TECHNIQUES.items()},
        "weaponDice": {k: list(v) for k, v in trpg.WEAPON_DICE.items()},
        "finesse": sorted(trpg.FINESSE_WEAPONS),
        "advantages": dict(trpg.ADVANTAGES_LIBRARY),
        "disadvantages": dict(trpg.DISADVANTAGES_LIBRARY),
        "talentGroups": {k: list(v) for k, v in trpg.TALENT_BONUS_GROUPS.items()},
        "spells": SPELL_LIBRARY,
        "maneuvers": MANEUVERS,
        "wastelandMap": {
            "attrs": ATTR_MAP,
            "slope": _WL_SLOPE,
            "skillSlope": _SKILL_SLOPE,
            "note": "本书五维 4 起步 → 内核属性 10 起步；技能最低 1 级",
        },
    }


def show_sheet(char) -> str:
    """内核角色卡文本（给叙事输出用）。"""
    return str(_safe(lambda: char.show_sheet(), "") or "")
