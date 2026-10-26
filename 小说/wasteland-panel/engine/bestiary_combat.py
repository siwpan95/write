#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bestiary_combat.py —— 战斗用敌人 stat block（谱系自动生成 + 具名异族覆盖）

数据来源（单一事实源）
----------------------
骨架由 dataset.json 的变异谱系（world-bible §7）推导：
    creatures.tiers → 6 档（零级/一级/二级/三级/王级/坠影级）
特性覆盖来自 engine/data/bestiary_combat.json：9 种具名异族各自的
弱点、行为与火花产出修正（第 5、7、27、36-37 章等正文依据）。

设计立场
--------
异族不是"怪物手册里的数字"，是**正文里写过的东西**：
蟑螂王会带着工头合围、变异鬣狗的弱点在脊背菌丝根部的蓝紫节点、
三级母体的旧伤能用钢管捅。这些必须体现在战斗数值里，否则沙盘
就是个换了皮的木桩模拟器——打谁都一样，赢了也不知道赢在哪。

坠影级（S+）按设定**不可击杀取火花**，面板判「？？？」——
它不进战斗表，尝试遭遇时返回 blocked（R2/R6 + 第 36-37 章）。

零三方依赖（只用标准库 + 本仓 dataset）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
OVERRIDE_PATH = HERE / "data" / "bestiary_combat.json"

# --------------------------------------------------------------------------
# 1. 谱系骨架（与 trpg_mechanics.TIER_TABLE 同一口径）
# --------------------------------------------------------------------------
#
# 数值对齐四档角色预设的战力曲线：
#   第一卷（近战+2 / HP12）打得动零级～一级；
#   第三卷（近战+10 / HP70）能搏二级、三级要拼命；
#   第五卷点燃（近战+16 / HP163）才够看王级。

TIER_BLOCKS: dict[str, dict] = {
    "零级": {
        "hp": 5, "ac": 10, "atk": 1, "dice": [1, 4], "dmgMod": 0,
        "init": 0, "danger": "背景板",
        "note": "个体略大、无质变；火花 0，只作氛围",
    },
    "一级": {
        "hp": 12, "ac": 12, "atk": 3, "dice": [1, 6], "dmgMod": 1,
        "init": 1, "danger": "遭遇",
        "note": "体型/甲壳/行为质变；单体可搏，围一群则危险",
    },
    "二级": {
        "hp": 28, "ac": 14, "atk": 6, "dice": [1, 8], "dmgMod": 2,
        "init": 2, "danger": "硬战",
        "note": "多器官异常、类策略行为；需弱点解析",
    },
    "三级": {
        "hp": 60, "ac": 16, "atk": 9, "dice": [2, 6], "dmgMod": 3,
        "init": 3, "danger": "搏命",
        "note": "脱离原物种、可伤人；弱点与时机决定生死",
    },
    "王级": {
        "hp": 160, "ac": 18, "atk": 16, "dice": [2, 10], "dmgMod": 6,
        "init": 5, "danger": "不可交战",
        "note": "高智慧、统御同类；理论上不应硬碰（实测：第五卷点燃档位单挑仍会掉半血）",
    },
    "坠影级（S+）": {
        "hp": -1, "ac": -1, "atk": -1, "dice": [-1, -1], "dmgMod": 0,
        "init": 0, "danger": "送终",
        "note": "面板判定为「？？？」——不可击杀取火花，只能「送终」",
        "unkillable": True,
    },
}

# 谱系别名归一：正文里的写法五花八门（"二级上位"、"工头级"、"零级～一级"）
TIER_ALIASES = {
    "工头级": "二级",
    "二级上位": "二级",
    "一级～二级上位": "二级",
    "一级～二级": "一级",
    "零级～一级": "零级",
}

# --------------------------------------------------------------------------
# 2. 具名异族覆盖表（缺省时用内置兜底，文件缺失不影响运行）
# --------------------------------------------------------------------------

FALLBACK_OVERRIDES: dict[str, dict] = {
    "广东双马尾": {
        "tier": "零级", "hpMul": 1.5, "sparkMul": 1.0,
        "traits": [{"key": "tough", "label": "甲壳再生",
                    "desc": "被拍裂甲壳仍能挣扎（第 5、7 章）——生命值 ×1.5"}],
        "source": "第 5、7 章",
    },
    "巨蝎": {
        "tier": "一级", "acMod": -2,
        "traits": [{"key": "weakpoint", "label": "弱点·关节缝",
                    "desc": "找关节缝——AC -2（正文判定）"}],
        "source": "第 7 章",
    },
    "三头秃鹫": {
        "tier": "一级", "initMod": -2, "multiattack": 2,
        "traits": [{"key": "multihead", "label": "三头齐喙",
                    "desc": "每回合 2 次攻击；不主动招惹，先攻 -2"}],
        "source": "第 7 章",
    },
    "掘地者": {
        "tier": "三级", "initMod": 3,
        "traits": [{"key": "ambush", "label": "潜地突袭",
                    "desc": "从地下钻出，先攻 +3；正文建议避让"}],
        "source": "第 27 章",
    },
    "变异鬣狗": {
        "tier": "二级",
        "traits": [{"key": "weakpoint", "label": "弱点·脊背菌丝根部蓝紫节点",
                    "desc": "命中弱点伤害 ×2（第 27 章判定）",
                    "dmgMul": 2}],
        "source": "第 27 章",
    },
    "变异蜥蜴 / 巨型蜈蚣 / 变异鼠": {
        "tier": "零级", "sparkMul": 0.5,
        "traits": [{"key": "scatter", "label": "火花零星",
                    "desc": "火花产出 ×0.5（正文：火花零星）"}],
        "source": "第 5 章",
    },
    "蟑螂王": {
        "tier": "二级", "multiattack": 2,
        "traits": [{"key": "commander", "label": "工头合围",
                    "desc": "金属夹 + 跑动技能，同伴攻击 +1（合围）",
                    "allyAtkBonus": 1}],
        "source": "第 27 章",
    },
    "菌丝寄生体（多足畸形生物）": {
        "tier": "二级",
        "traits": [{"key": "infest", "label": "菌丝寄生",
                    "desc": "命中后附加「菌丝寄生」状态（体质 -2，需凝晶原液解除）",
                    "status": "mycelium"}],
        "source": "第 27 章",
    },
    "三级母体（巢穴）": {
        "tier": "三级",
        "traits": [{"key": "weakpoint", "label": "弱点·旧伤（钢管可捅）",
                    "desc": "猛力攻击/全力强击命中旧伤时伤害 ×2",
                    "dmgMul": 2, "cond": ["power_attack", "allout_strong"]}],
        "source": "第 27 章",
    },
}


def load_overrides(path: Path = OVERRIDE_PATH) -> dict:
    """读具名覆盖表；文件缺失/损坏时用内置兜底并**报出来**，不静默。"""
    if not path.exists():
        return dict(FALLBACK_OVERRIDES)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data:
            # 跳过 _comment 之类的说明键（它们的值是字符串，不是覆盖表）
            clean = {k: v for k, v in data.items()
                     if not k.startswith("_") and isinstance(v, dict)}
            if clean:
                return clean
    except Exception as e:
        print(f"[warn] bestiary_combat.json 解析失败，回退内置覆盖表: {e}")
    return dict(FALLBACK_OVERRIDES)


OVERRIDES = load_overrides()


def normalize_tier(tier: Any) -> str:
    """把任意写法的等级归一成标准谱系名。"""
    s = str(tier or "").strip()
    for k in TIER_BLOCKS:
        if k in s:
            return k
    for k in TIER_BLOCKS:
        if k.replace("（S+）", "") in s:
            return k
    return TIER_ALIASES.get(s, s)


# --------------------------------------------------------------------------
# 3. 生成 stat block
# --------------------------------------------------------------------------

def make_enemy(name: str, uid: str | None = None, ds: dict | None = None) -> dict:
    """生成一个敌人的战斗 stat block。

    name 可以是具名异族（"蟑螂王"）或纯等级（"二级"）。
    """
    ov = OVERRIDES.get(name)
    if not isinstance(ov, dict):
        ov = None
    tier_raw = (ov or {}).get("tier") or name
    tier = normalize_tier(tier_raw)
    base = TIER_BLOCKS.get(tier)

    if base is None:
        # 没认出来就按"一级"兜底，并在 note 里标明，避免静默变成木桩
        tier, base = "一级", TIER_BLOCKS["一级"]
        unknown = True
    else:
        unknown = False

    if base.get("unkillable"):
        return {
            "uid": uid or f"{name}#1",
            "name": name, "tier": tier, "side": "enemy",
            "unkillable": True,
            "verdict": "异族·坠影级（S+）",
            "note": "面板判定为「？？？」——不可击杀取火花，只能「送终」（第 36-37 章）",
        }

    hp = int(round(base["hp"] * float((ov or {}).get("hpMul", 1.0))))
    ac = int(base["ac"] + int((ov or {}).get("acMod", 0)))
    atk = int(base["atk"] + int((ov or {}).get("atkMod", 0)))
    init = int(base["init"] + int((ov or {}).get("initMod", 0)))

    traits = list((ov or {}).get("traits") or [])
    multiattack = int((ov or {}).get("multiattack") or 1)

    return {
        "uid": uid or f"{name}#1",
        "name": name, "tier": tier, "side": "enemy",
        "maxHp": hp, "hp": hp,
        "ac": ac, "atk": atk,
        "dice": list(base["dice"]), "dmgMod": int(base["dmgMod"]),
        "initMod": init,
        "multiattack": multiattack,
        "sparkMul": float((ov or {}).get("sparkMul", 1.0)),
        "traits": traits,
        "statuses": {},
        "alive": True,
        "danger": base["danger"],
        # 未识别的名字会被兜底成一级——必须写进 note，否则静默降级：
        # 日志/前端只看到"变异鼠"三个字，实际却是 HP12/AC12/+3 的一级怪，
        # 配遭遇链时会以为放的是零级杂兵，难度直接失控。
        "note": base["note"] + ("⚠ 未识别的名称，已按「一级」兜底" if unknown else ""),
        "source": (ov or {}).get("source", ""),
        "unknownTier": unknown,
    }


def spawn_group(specs: list[dict], ds: dict | None = None) -> list[dict]:
    """按 [{name, count}] 生成一群敌人，自动编号。

    坠影级直接跳过并标记 blocked（不可击杀）。
    """
    out, blocked = [], []
    for s in specs or []:
        name = s.get("name") or s.get("tier") or "一级"
        count = max(1, int(s.get("count", 1)))
        for i in range(count):
            e = make_enemy(name, uid=f"{name}#{i + 1}", ds=ds)
            if e.get("unkillable"):
                blocked.append(e["name"])
                break
            out.append(e)
    return out, blocked


def apply_commander_bonus(enemies: list[dict]) -> list[str]:
    """蟑螂王的「工头合围」：给同伴 +1 攻击。返回说明行。"""
    notes = []
    bonus = 0
    for e in enemies:
        for t in e.get("traits") or []:
            if t.get("key") == "commander" and e.get("alive"):
                bonus = max(bonus, int(t.get("allyAtkBonus", 1)))
    if bonus:
        for e in enemies:
            has_cmd = any((t.get("key") == "commander") for t in (e.get("traits") or []))
            if not has_cmd:
                e["atk"] = int(e["atk"]) + bonus
                e["commanderBonus"] = bonus
        notes.append(f"蟑螂王在场，工头合围：其余异族攻击 +{bonus}")
    return notes


# --------------------------------------------------------------------------
# 4. 目录（给前端下拉框）
# --------------------------------------------------------------------------

def catalog(ds: dict | None = None) -> dict:
    """图鉴 + 谱系 + 覆盖表，供沙盘选怪。"""
    tiers = []
    for k, v in TIER_BLOCKS.items():
        tiers.append({"tier": k, **v})

    named = []
    for name, ov in OVERRIDES.items():
        e = make_enemy(name)
        named.append({
            "name": name,
            "tier": e.get("tier"),
            "hp": e.get("maxHp"),
            "ac": e.get("ac"),
            "atk": e.get("atk"),
            "dice": e.get("dice"),
            "dmgMod": e.get("dmgMod"),
            "danger": e.get("danger"),
            "traits": e.get("traits") or [],
            "source": ov.get("source", ""),
            "unkillable": bool(e.get("unkillable")),
        })

    return {"ok": True, "tiers": tiers, "named": named,
            "overrideSource": str(OVERRIDE_PATH.name)}


if __name__ == "__main__":
    c = catalog()
    print("=== 谱系 ===")
    for t in c["tiers"]:
        if t.get("unkillable"):
            print(f"  {t['tier']}: 不可击杀（{t['note']}）")
        else:
            print(f"  {t['tier']}: HP{t['hp']} AC{t['ac']} 攻+{t['atk']} "
                  f"{t['dice'][0]}d{t['dice'][1]}+{t['dmgMod']} [{t['danger']}]")
    print("\n=== 具名异族 ===")
    for n in c["named"]:
        if n["unkillable"]:
            print(f"  {n['name']}: ???")
            continue
        tr = "、".join(t["label"] for t in n["traits"]) or "—"
        print(f"  {n['name']}（{n['tier']}）HP{n['hp']} AC{n['ac']} 攻+{n['atk']} "
              f"{n['dice'][0]}d{n['dice'][1]}+{n['dmgMod']} · {tr}")
