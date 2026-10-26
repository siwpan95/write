#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
campaign.py — 战役层：把「一场遭遇战」串成一条跨场推进的线。

为什么需要这一层
----------------
`combat_engine.Encounter` 是**单场**的：开局满血、法力从档位初值起、
打完就散。而正文是一场接一场的——魏成河带着上一场的伤走进下一场，
灰线只增不减（R11），火花只涨不落（R8）。

这一层负责的就是**跨场保留**：

  · 生命：跨场保留，不自动回满
  · 法力池（五色）：跨场保留，绿法术才能真正当补给用
  · 灰线：跨场保留，且**只增不回退**（R11）
  · 火花 / 点燃：跨场累积，点燃后封顶（R8）
  · 虚空耐受 / 黑色代偿档位：随卷联动

战间恢复只有两条路（设定里没有成文的「休息回血」）：

  1. **休整**：恢复 25% 生命上限，灰线不回退（R11）
  2. **治疗言灵**：绿 1 环法术，耗 1 点绿法力（战斗内外都能用）

法力补给走「汲取」：吸 1 点指定色法力，**灰线 +1 格**——
污染加深才扛得住更多（R11），有代价的选择才有分量。

推进方式：预置卷级遭遇链（打完一场自动进下一场）+ 随时自由插入。

零三方依赖（规则内核经 d20_bridge 间接引入，缺失时该层整体不可用并明确报错）。
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path
from typing import Any

import d20_bridge as DB
import bestiary_combat as BC

DATA_PATH = Path(__file__).parent / "data" / "campaign.json"

MANA_COLORS = ["白", "蓝", "黑", "红", "绿"]

# 休整恢复比例（占生命上限）
REST_RATIO = 0.25


# ==========================================================================
# 预置卷级遭遇链
# ==========================================================================
# 配置取自 bestiary_combat.json 里已登记的具名异族与档位名，
# 章号出处一并写在 note 里，便于回正文核对。
#
# 难度是**实测调过的**，不是拍脑袋写的：每个配置跑 20 个随机种子
# （PC 用 combat.auto 的简单策略），记录胜率与平均剩血，见 winrate 字段。
# 改配置前先看这个数——第一版 v1 链放了「广东双马尾×2」，实测 40%，
# 第一场就大概率团灭，战役根本推不动。
#
# 只用**能精确解析**的名字：具名异族用 JSON 里的完整键，杂兵用档位名
# （零级/一级/二级/三级）。像「变异鼠」这种只出现在组合键
# 「变异蜥蜴 / 巨型蜈蚣 / 变异鼠」里的简称，会被 make_enemy 静默兜底成
# 一级（HP12/AC12/+3），实测胜率从预期的零级水平直接掉到 0/20。
#
# 第四卷暂无剧情档位预设（PROFILES 里只有 v1/v2/v3/v5 四档），
# 不在此虚构数值——缺哪一档就是缺哪一档，报清楚比编一个强。

CAMPAIGN_CHAINS: dict[str, dict] = {
    "v1-seed": {
        "label": "第一卷 · 火种期（第 5–39 章）",
        "volume": 1,
        "profile": "v1-seed",
        "note": "面板刚亮，五维近乎常人；零级都要拼命",
        "encounters": [
            {"name": "工厂外围 · 初遇",
             "enemies": [{"name": "广东双马尾", "count": 1}],
             "note": "第 5、7 章：甲壳再生，被拍裂了还能挣扎",
             "winrate": "19/20（95%）· 平均剩血 7.6/12"},
            {"name": "排水渠 · 杂兵群",
             "enemies": [{"name": "零级", "count": 2}],
             "note": "第 5 章：个体略大、无质变；火花 0，只作氛围",
             "winrate": "14/20（70%）· 平均剩血 3.4/12"},
            {"name": "排水渠深处 · 甲壳与毒尾",
             "enemies": [{"name": "巨蝎", "count": 1}],
             "note": "第 7 章：关节缝是弱点（AC-2）",
             "winrate": "9/20（45%）· 平均剩血 3.2/12"},
        ],
    },
    "v2-gray": {
        "label": "第二卷 · 灰线初现（第 40–90 章）",
        "volume": 2,
        "profile": "v2-gray",
        "note": "灰线开始爬；一级成群、二级单挑都够呛",
        "encounters": [
            {"name": "废车场 · 甲壳与毒尾",
             "enemies": [{"name": "巨蝎", "count": 2}],
             "note": "第 7 章：关节缝是弱点（AC-2）",
             "winrate": "20/20（100%）· 平均剩血 20.4/34"},
            {"name": "地下管廊 · 群猎",
             "enemies": [{"name": "一级", "count": 3}],
             "note": "体型/甲壳质变，围上来就危险",
             "winrate": "13/20（65%）· 平均剩血 6.8/34"},
            {"name": "天台 · 三头齐喙",
             "enemies": [{"name": "三头秃鹫", "count": 1},
                         {"name": "一级", "count": 2}],
             "note": "第 7 章：一回合两次攻击",
             "winrate": "7/20（35%）· 平均剩血 3.0/34"},
        ],
    },
    "v3-mycelium": {
        "label": "第三卷 · 菌丝与合围（第 91–140 章）",
        "volume": 3,
        "profile": "v3-mycelium",
        "note": "弱点解析成型；二级能打，三级仍需搏命",
        "encounters": [
            {"name": "菌丝带 · 脊背节点",
             "enemies": [{"name": "变异鬣狗", "count": 2}],
             "note": "第 27 章：脊背菌丝根部蓝紫节点，弱点 ×2",
             "winrate": "20/20（100%）· 平均剩血 45.8/70"},
            {"name": "塌陷区 · 寄生体",
             "enemies": [{"name": "菌丝寄生体（多足畸形生物）", "count": 1},
                         {"name": "二级", "count": 1}],
             "note": "第 27 章：命中后附加菌丝状态",
             "winrate": "17/20（85%）· 平均剩血 32.4/70"},
            {"name": "巢穴 · 三级母体",
             "enemies": [{"name": "三级母体（巢穴）", "count": 1},
                         {"name": "二级", "count": 1}],
             "note": "第 27 章：旧伤在，强击类伤害 ×2",
             "winrate": "15/20（75%）· 平均剩血 19.8/70"},
        ],
    },
    "v5-ignited": {
        "label": "第五卷 · 点燃之后（第 141 章起）",
        "volume": 5,
        "profile": "v5-ignited",
        "note": "鹏洛克·位面行走者；火花封顶，力量改走汲取多位面法力（R8）",
        "encounters": [
            {"name": "焦土 · 清扫",
             "enemies": [{"name": "三级", "count": 2}],
             "note": "脱离原物种、可伤人",
             "winrate": "20/20（100%）· 平均剩血 115/163"},
            {"name": "旧厂区 · 合围再临",
             "enemies": [{"name": "变异鬣狗", "count": 2},
                         {"name": "蟑螂王", "count": 1}],
             "note": "老对手，但这一次的底牌多得多",
             "winrate": "20/20（100%）· 平均剩血 145/163"},
            {"name": "巢穴深处 · 王级",
             "enemies": [{"name": "王级", "count": 1}],
             "note": "理论上不应硬碰——高智慧、统御同类",
             "winrate": "20/20（100%）· 平均剩血 46.5/163"},
        ],
    },
}


def chains() -> dict:
    """给前端/CLI 的链目录。"""
    return {
        "ok": True,
        "chains": [
            {
                "key": k,
                "label": v["label"],
                "volume": v["volume"],
                "profile": v["profile"],
                "note": v["note"],
                "count": len(v["encounters"]),
                "encounters": [
                    {"name": e["name"], "note": e.get("note", ""),
                     "enemies": e["enemies"],
                     "winrate": e.get("winrate", "")}
                    for e in v["encounters"]
                ],
            }
            for k, v in CAMPAIGN_CHAINS.items()
        ],
    }


# ==========================================================================
# 战役
# ==========================================================================

class Campaign:
    """一条战役：跨场保留的 PC 状态 + 一条遭遇序列。"""

    def __init__(self, chain_key: str = "v1-seed", ds: dict | None = None,
                 name: str = "魏成河", seed: int | None = None):
        chain = CAMPAIGN_CHAINS.get(chain_key)
        if not chain:
            raise ValueError(
                f"未知战役链: {chain_key}（可选：{list(CAMPAIGN_CHAINS)}）")

        prof = DB.PROFILES.get(chain["profile"])
        if not prof:
            raise ValueError(f"战役链 {chain_key} 引用了不存在的剧情档位: "
                             f"{chain['profile']}")

        self.ds = ds or {}
        self.name = name
        self.chain_key = chain_key
        self.seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()

        # --- 跨场保留的 PC 状态 ---
        self.attrs = dict(prof["attrs"])
        self.spark = int(prof["spark"])
        self.ignited = bool(prof.get("ignited"))
        self.gray_cells = int(prof.get("grayCells", 0) or 0)
        self.volume = int(chain["volume"])
        self.void_min = 7
        self.black_mult = 1
        self.mana_pool = dict(prof.get("manaPool")
                              or {c: 0 for c in MANA_COLORS})
        for c in MANA_COLORS:
            self.mana_pool.setdefault(c, 0)
        self.equipment = list(prof.get("equipment") or [])
        self.techniques = list(prof.get("techniques") or [])

        self.hp = 0            # 由 build_pc 填成满血
        self.max_hp = 0

        # --- 序列 ---
        self.encounters = [dict(e) for e in chain["encounters"]]
        self.cursor = 0
        self.status = "ongoing"          # ongoing | complete | dead
        self.history: list[dict] = []    # 每场摘要
        self.log: list[str] = []

        # 起手先建一次，把 hp / max_hp 落定
        self.build_pc()
        self.hp = self.max_hp
        self.log.append(f"战役开始：{chain['label']}"
                        f"（{len(self.encounters)} 场）")

    # ---------------------------------------------------------------- 状态

    def party_state(self) -> dict:
        """传给 d20_bridge.build_from_panel 的面板状态。"""
        return {
            "attrs": dict(self.attrs),
            "spark": self.spark,
            "ignited": self.ignited,
            "grayCells": self.gray_cells,
            "volume": self.volume,
            "manaPool": dict(self.mana_pool),
            "voidMin": self.void_min,
            "blackMult": self.black_mult,
            "unlocked": [],
        }

    def build_pc(self) -> dict:
        """按当前（跨场累积后的）状态重建 PC，并套用持久生命值。

        火花涨了 → wl2rank 技能等级涨 → 战力涨，所以每场都重建而不是复用
        上一场的 stat block。生命上限变高时，当前生命**不补满**——
        伤就是伤，只保证不会超过新的上限。
        """
        sb = DB.build_from_panel(self.party_state(), name=self.name,
                                 equipment=self.equipment,
                                 techniques=self.techniques)
        pc = {k: v for k, v in sb.items() if k not in ("char", "buildLog")}
        pc["uid"] = "pc"
        pc["side"] = "pc"
        pc["alive"] = int(self.hp) > 0
        pc.setdefault("statuses", {})
        pc["manaPool"] = dict(self.mana_pool)
        pc["grayCells"] = self.gray_cells
        pc["defending"] = False
        pc["noDefense"] = False

        self.max_hp = int(pc.get("maxHp", 0))
        # 首次构建时 hp 还是 0，此时按满血起手；之后一律沿用持久值
        if not self.hp:
            self.hp = self.max_hp
        pc["hp"] = min(int(self.hp), self.max_hp)
        self.hp = pc["hp"]
        return pc

    def current_encounter(self) -> dict | None:
        if self.cursor >= len(self.encounters):
            return None
        return self.encounters[self.cursor]

    # ---------------------------------------------------------------- 推进

    def next_spec(self) -> dict:
        """下一场的配置（供 combat.new 使用）。"""
        e = self.current_encounter()
        if not e:
            return {"ok": False, "error": "战役链已走完（status=complete）"}
        seed = self.rng.randint(1, 2 ** 31 - 1)
        return {"ok": True, "name": e["name"], "note": e.get("note", ""),
                "enemies": [dict(x) for x in e["enemies"]], "seed": seed,
                "index": self.cursor, "total": len(self.encounters)}

    def insert_spec(self, enemies: list[dict], name: str = "") -> dict:
        """自由插入一场：不改变链的游标，插在下一场之前。"""
        if not enemies:
            return {"ok": False, "error": "没有指定异族"}
        e = {"name": name or "临时遭遇（自由插入）", "enemies": enemies,
             "note": "自由插入，不计入战役链进度", "inserted": True}
        self.encounters.insert(self.cursor, e)
        return {"ok": True, "name": e["name"], "note": e["note"],
                "enemies": [dict(x) for x in enemies],
                "seed": self.rng.randint(1, 2 ** 31 - 1),
                "index": self.cursor, "total": len(self.encounters)}

    def apply_result(self, snap: dict) -> dict:
        """战斗结束后把跨场状态收回来。"""
        pc = snap.get("pc") or {}
        before = {"hp": self.hp, "spark": self.spark,
                  "grayCells": self.gray_cells}

        self.hp = int(pc.get("hp", self.hp))
        self.max_hp = int(pc.get("maxHp", self.max_hp) or self.max_hp)
        # 法力池：战斗里消耗的要带出来
        pool = snap.get("manaPool") or pc.get("manaPool")
        if isinstance(pool, dict):
            for c in MANA_COLORS:
                if c in pool:
                    self.mana_pool[c] = int(pool[c])
        # 灰线：R11 单调不回退
        g = int(pc.get("grayCells", self.gray_cells) or 0)
        self.gray_cells = max(self.gray_cells, g)
        # 火花：R8 点燃后封顶
        sp = snap.get("spark")
        if sp is not None:
            self.spark = int(sp)
        if snap.get("ignited"):
            self.ignited = True

        cur = self.current_encounter()
        rec = {
            "name": (cur or {}).get("name", "遭遇"),
            "status": snap.get("status"),
            "round": snap.get("round"),
            "hpAfter": self.hp,
            "maxHp": self.max_hp,
            "sparkAfter": self.spark,
            "grayAfter": self.gray_cells,
        }
        self.history.append(rec)

        if self.hp <= 0:
            self.status = "dead"
            self.log.append(f"第 {len(self.history)} 场「{rec['name']}」：倒下了")
            return {"ok": True, "status": self.status, "record": rec,
                    "before": before}

        # 链推进（自由插入的场次也算推进，它已经在序列里了）
        self.cursor += 1
        if self.cursor >= len(self.encounters):
            self.status = "complete"
            self.log.append(f"第 {len(self.history)} 场「{rec['name']}」："
                            f"胜，战役链走完")
        else:
            self.log.append(f"第 {len(self.history)} 场「{rec['name']}」："
                            f"{rec['status']}，剩 {self.hp}/{self.max_hp}")

        return {"ok": True, "status": self.status, "record": rec,
                "before": before}

    # ---------------------------------------------------------------- 战间

    def rest(self) -> dict:
        """休整：恢复 25% 生命上限，灰线不回退（R11），法力不恢复。"""
        if self.status == "dead":
            return {"ok": False, "error": "旅法师已倒下，战役结束"}
        gain = int(math.ceil(self.max_hp * REST_RATIO))
        before = self.hp
        self.hp = min(self.max_hp, self.hp + gain)
        self.log.append(f"休整：生命 {before} → {self.hp}/{self.max_hp}"
                        f"（灰线 {self.gray_cells} 格，不回退 R11）")
        return {"ok": True, "hpBefore": before, "hpAfter": self.hp,
                "gain": self.hp - before, "maxHp": self.max_hp,
                "grayCells": self.gray_cells,
                "note": f"恢复 {REST_RATIO:.0%} 生命上限；法力不恢复，"
                        f"灰线只增不减（R11）"}

    def draw_mana(self, color: str, cells: int = 1) -> dict:
        """汲取法力：+1 点指定色，灰线 +1 格（污染加深才扛得住，R11）。"""
        if self.status == "dead":
            return {"ok": False, "error": "旅法师已倒下，战役结束"}
        if color not in MANA_COLORS:
            return {"ok": False,
                    "error": f"未知法力色: {color}（可选：{MANA_COLORS}）"}
        if color == "黑":
            return {"ok": False,
                    "error": "黑色法力不靠汲取——它烧的是记忆/情感碎片（R9）"}
        n = max(1, int(cells or 1))
        self.mana_pool[color] = int(self.mana_pool.get(color, 0)) + n
        self.gray_cells += n
        self.log.append(f"汲取{color}色法力 +{n} → {self.mana_pool[color]}；"
                        f"灰线 +{n} → {self.gray_cells} 格（R11）")
        return {"ok": True, "color": color, "gained": n,
                "pool": dict(self.mana_pool),
                "grayCells": self.gray_cells,
                "note": "越能扛越不像人（R11）"}

    def heal(self) -> dict:
        """战役层施放治疗言灵（绿 1 环，耗 1 点绿法力）。"""
        if self.status == "dead":
            return {"ok": False, "error": "旅法师已倒下，战役结束"}
        if "治疗言灵" not in self.techniques:
            return {"ok": False, "error": "未学会「治疗言灵」技术"}
        if int(self.mana_pool.get("绿", 0)) < 1:
            return {"ok": False, "error": "绿色法力不足：需要 1，剩 "
                                          f"{int(self.mana_pool.get('绿', 0))}"}
        self.mana_pool["绿"] = int(self.mana_pool["绿"]) - 1
        rolls = [self.rng.randint(1, 4) for _ in range(1)]
        base = sum(rolls)
        # 施法调整取近战加值的量级（与战斗内 _cast 一致：1d4 + 施法调整）
        bonus = max(1, self._cast_bonus())
        heal = base + bonus
        before = self.hp
        self.hp = min(self.max_hp, self.hp + heal)
        self.log.append(f"治疗言灵（绿 -1）：1d4 [{rolls[0]}] + {bonus} = "
                        f"{heal}，生命 {before} → {self.hp}/{self.max_hp}")
        return {"ok": True, "heal": heal, "hpBefore": before,
                "hpAfter": self.hp, "maxHp": self.max_hp,
                "pool": dict(self.mana_pool)}

    def _cast_bonus(self) -> int:
        """治疗量用的施法调整：与战斗内一致，取近战加值。"""
        try:
            pc = self.build_pc()
            return int(pc.get("atkMelee", 1) or 1)
        except Exception:
            return 1

    # ---------------------------------------------------------------- 快照

    def snapshot(self) -> dict:
        cur = self.current_encounter()
        return {
            "ok": True,
            "chain": {"key": self.chain_key,
                      "label": CAMPAIGN_CHAINS[self.chain_key]["label"],
                      "volume": self.volume},
            "name": self.name,
            "status": self.status,
            "cursor": self.cursor,
            "total": len(self.encounters),
            "next": ({"name": cur["name"], "note": cur.get("note", ""),
                      "enemies": cur["enemies"]}
                     if cur else None),
            "hp": self.hp,
            "maxHp": self.max_hp,
            "spark": self.spark,
            "ignited": self.ignited,
            "grayCells": self.gray_cells,
            "manaPool": dict(self.mana_pool),
            "volume": self.volume,
            "voidMin": self.void_min,
            "blackMult": self.black_mult,
            "techniques": list(self.techniques),
            "equipment": list(self.equipment),
            "history": list(self.history),
            "log": list(self.log[-20:]),
        }

    # ---------------------------------------------------------------- 存档

    def to_dict(self) -> dict:
        return {
            "chainKey": self.chain_key, "name": self.name,
            "seed": self.seed, "attrs": dict(self.attrs),
            "spark": self.spark, "ignited": self.ignited,
            "grayCells": self.gray_cells, "volume": self.volume,
            "voidMin": self.void_min, "blackMult": self.black_mult,
            "manaPool": dict(self.mana_pool),
            "equipment": list(self.equipment),
            "techniques": list(self.techniques),
            "hp": self.hp, "maxHp": self.max_hp,
            "cursor": self.cursor, "status": self.status,
            "encounters": [dict(e) for e in self.encounters],
            "history": list(self.history), "log": list(self.log),
            "rng": None,
        }

    @classmethod
    def from_dict(cls, d: dict, ds: dict | None = None) -> "Campaign":
        key = d.get("chainKey") or "v1-seed"
        c = cls(chain_key=key, ds=ds, name=d.get("name") or "魏成河",
                seed=d.get("seed"))
        c.attrs = dict(d.get("attrs") or c.attrs)
        c.spark = int(d.get("spark", c.spark))
        c.ignited = bool(d.get("ignited", c.ignited))
        c.gray_cells = int(d.get("grayCells", c.gray_cells) or 0)
        c.volume = int(d.get("volume", c.volume) or 1)
        c.void_min = int(d.get("voidMin", c.void_min) or 7)
        c.black_mult = int(d.get("blackMult", c.black_mult) or 1)
        pool = d.get("manaPool") or {}
        for k in MANA_COLORS:
            c.mana_pool[k] = int(pool.get(k, 0) or 0)
        c.equipment = list(d.get("equipment") or c.equipment)
        c.techniques = list(d.get("techniques") or c.techniques)
        c.max_hp = int(d.get("maxHp", 0) or 0)
        c.hp = int(d.get("hp", 0) or 0)
        c.cursor = int(d.get("cursor", 0) or 0)
        c.status = d.get("status") or "ongoing"
        c.encounters = [dict(e) for e in (d.get("encounters")
                                          or c.encounters)]
        c.history = list(d.get("history") or [])
        c.log = list(d.get("log") or [])
        # 生命上限可能因为火花变化而变了，重算一次并夹紧
        c.build_pc()
        return c


# --------------------------------------------------------------------------
# 存档
# --------------------------------------------------------------------------

def save(campaigns: dict[str, Campaign]) -> None:
    payload = {k: v.to_dict() for k, v in campaigns.items()}
    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False),
                             encoding="utf-8")
    except Exception as ex:  # 存档失败不该打断战役
        print(f"[warn] 战役存档失败: {ex}", file=sys.stderr)


def load() -> dict[str, dict]:
    if not DATA_PATH.exists():
        return {}
    try:
        raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}
