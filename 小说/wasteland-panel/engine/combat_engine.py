#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combat_engine.py —— 废土旅法师 · 遭遇战沙盘（回合制战斗）

为什么不用内核的 combat_macro
-----------------------------
内核（allin_engine.trpg）的战斗宏返回的是**给人看的字符串**：

    '⚔ 近战攻击: d20+10 = 3+10 = 13 vs AC 12\\n  ✓ 命中！伤害: 1d3+2 = 4'

它有三个致命问题（实测结论，见 README「内核边界」表）：
  1. 没有结构化字段——命中/伤害拿不出来，驱动不了回合循环；
  2. 未装备武器时伤害退化成徒手 1d3，静默把主角削成路人；
  3. 内核 hp() 返回的是**满血值**，take_damage 之后读数不变，
     当前 HP 无法依赖内核记账。

所以本模块的立场：**数值口径向内核要，战斗循环自己实现**。
    · 攻击加值 / AC / 豁免 / 武器伤害骰 / 技术惩罚 → d20_bridge → 内核
    · HP / 回合 / 先攻 / 状态 / 死亡 / 结算 → 本模块

废土机制接线
------------
    · 施法 → 五色法力池扣色，并征 1 格结构税（R13）
    · 灰线爆发 → 烧 3 格灰线换 1d6 伤害，灰线 +2（R11 单调递增）
    · 黑色代偿 → 走 trpg_mechanics.burn_cost_roll，付记忆代价（R9）
    · 异族死亡 → 火花产出回写面板（panel_engine.spark_for_tier）
    · 坠影级 → 不可击杀，进不了战斗（R2/R6）

零三方依赖（allin-engine 除外）。
"""

from __future__ import annotations

import random
from typing import Any

import d20_bridge as DB
import bestiary_combat as BC
import panel_engine as PE
import trpg_mechanics as TM

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

CRIT_FACE = 20          # d20=20 暴击（伤害骰翻倍）
FUMBLE_FACE = 1         # d20=1 必失
DEFEND_BONUS = 2        # 举盾防御 AC 加值
GRAY_SURGE_PER_D6 = 3   # 灰线爆发：每 3 格换 1d6
GRAY_SURGE_COST = 2     # 灰线爆发额外加深的格数


# --------------------------------------------------------------------------
# 结构化日志
# --------------------------------------------------------------------------

def _entry(kind: str, text: str, **data) -> dict:
    return {"kind": kind, "text": text, "data": data}


def _dice_str(rolls: list[int]) -> str:
    return "[" + ",".join(str(r) for r in rolls) + "]"


# --------------------------------------------------------------------------
# 遭遇
# --------------------------------------------------------------------------

class Encounter:
    """一场遭遇战。

    状态机：init → ongoing → (victory | defeat)
    PC 回合等待外部指令（act）；敌人回合可一键推进（run_enemy_turns）。
    """

    def __init__(self, pc: dict, enemies: list[dict], ds: dict | None = None,
                 panel_state: dict | None = None, seed: int | None = None,
                 volume: int = 1):
        self.ds = ds or {}
        self.panel = panel_state if panel_state is not None else {}
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.round = 0
        self.log: list[dict] = []
        self.status = "init"

        # 火花 / 点燃 / 卷号：以「角色构建时的剧情档」为初值。
        # 否则 profile 声明 spark=58 只进了 pc.source，火花池却从 0 起算，
        # 打完一结算显示 24%，与第三卷设定直接矛盾。
        # 显式传入 panel_state 时（战役接续）以传入值为准，不覆盖。
        # 判据用「0 / 缺失」而不是 is None：rpc_server 传进来的 panel_state 是
        # PE.new_state() 的产物，spark 字段存在且为 0，用 is None 判断会永远落空。
        # 战役接续时 panel 里的火花/灰线必然 > 0，不会被这里覆盖回去。
        _src = pc.get("source") or {}
        if not self.panel.get("spark") and _src.get("spark"):
            self.panel["spark"] = int(_src["spark"] or 0)
        if not self.panel.get("ignited") and _src.get("ignited"):
            self.panel["ignited"] = True
        if not self.panel.get("grayCells") and _src.get("grayCells"):
            self.panel["grayCells"] = int(_src["grayCells"] or 0)
        if not self.panel.get("volume") and _src.get("volume"):
            self.panel["volume"] = int(_src["volume"] or 1)

        self.volume = int(volume or self.panel.get("volume", 1) or 1)

        # 战斗单位（PC 来自 d20_bridge.stat_block，敌人来自 bestiary_combat）
        self.pc = dict(pc)
        self.pc["uid"] = "pc"
        self.pc["side"] = "pc"
        self.pc["alive"] = True
        self.pc.setdefault("statuses", {})
        self.pc.setdefault("manaPool", dict(self.panel.get("manaPool")
                                            or {"白": 0, "蓝": 0, "黑": 0, "红": 0, "绿": 0}))
        self.pc["grayCells"] = int(self.panel.get("grayCells", 0) or 0)
        self.pc["defending"] = False
        self.pc["noDefense"] = False      # 全力强击/精准突击后本回合不能防御

        self.enemies = [dict(e) for e in enemies]
        for e in self.enemies:
            e.setdefault("statuses", {})
            e.setdefault("alive", True)
            e["defending"] = False

        # 工头合围
        for note in BC.apply_commander_bonus(self.enemies):
            self.log.append(_entry("trait", note))

        self.order: list[str] = []        # uid 行动序
        self.turn_idx = 0
        self._rolled_initiative = False

    # ---------------- 先攻与回合 ----------------

    def roll_initiative(self) -> list[dict]:
        """掷先攻并排序。返回先攻表。"""
        rows = []
        for u in [self.pc] + self.enemies:
            d = DB.roll_d20(self.rng)
            tot = d + int(u.get("initMod", 0) or 0)
            rows.append({"uid": u["uid"], "name": u["name"], "d20": d,
                         "initMod": int(u.get("initMod", 0) or 0), "total": tot})
        rows.sort(key=lambda r: r["total"], reverse=True)
        self.order = [r["uid"] for r in rows]
        self.turn_idx = 0
        self.round = 1
        self.status = "ongoing"
        self._rolled_initiative = True
        self.log.append(_entry(
            "initiative",
            "先攻：" + " → ".join(f"{r['name']}({r['total']})" for r in rows),
            rows=rows))
        return rows

    @property
    def current(self) -> dict | None:
        if not self.order:
            return None
        uid = self.order[self.turn_idx]
        return self.find(uid)

    def find(self, uid: str) -> dict | None:
        if uid == "pc":
            return self.pc
        for e in self.enemies:
            if e["uid"] == uid:
                return e
        return None

    def _advance(self) -> None:
        """推进到下一个存活单位的回合；绕回时回合数 +1。"""
        if not self.order:
            return
        n = len(self.order)
        for i in range(1, n + 1):
            idx = (self.turn_idx + i) % n
            uid = self.order[idx]
            u = self.find(uid)
            if u and u.get("alive"):
                if idx <= self.turn_idx:
                    self.round += 1
                    self._on_new_round()
                self.turn_idx = idx
                return
        self.status = "victory" if self._enemies_alive() else "defeat"

    def _on_new_round(self) -> None:
        """新回合：清除防御状态。"""
        self.pc["defending"] = False
        self.pc["noDefense"] = False
        for e in self.enemies:
            e["defending"] = False
        self.log.append(_entry("round", f"—— 第 {self.round} 回合 ——", round=self.round))

    def _enemies_alive(self) -> list[dict]:
        return [e for e in self.enemies if e.get("alive")]

    def _check_end(self) -> None:
        if not self._enemies_alive():
            self.status = "victory"
            self.log.append(_entry("end", "异族已全部倒下。", result="victory"))
        elif not self.pc.get("alive"):
            self.status = "defeat"
            self.log.append(_entry("end", "旅法师倒下了。", result="defeat"))

    # ---------------- 命中与伤害 ----------------

    def _effective_ac(self, target: dict) -> int:
        ac = int(target.get("ac", 10))
        if target.get("defending"):
            ac += DEFEND_BONUS
        # 状态惩罚：僵直（灵敏 -2）等折算进 AC
        for st in (target.get("statuses") or {}).values():
            if st.get("attr") == "灵敏":
                ac += int(st.get("penalty", 0) or 0)
        return ac

    def _atk_bonus(self, unit: dict, melee: bool = True) -> int:
        base = int(unit.get("atkMelee" if melee else "atkRanged",
                            unit.get("atk", 0)) or 0)
        # 状态惩罚（灰蚀/僵直等按关联属性折算）
        for st in (unit.get("statuses") or {}).values():
            base += int(st.get("penalty", 0) or 0)
        return base

    def _resolve_attack(self, actor: dict, target: dict, mod: int = 0,
                        label: str = "攻击", dmg_bonus: int = 0,
                        extra_dice: list[int] | None = None,
                        maneuver: str = "melee_attack",
                        ranged: bool = False) -> dict:
        """一次攻击的完整结算（命中 → 伤害 → 特性 → 死亡）。"""
        d20 = DB.roll_d20(self.rng)
        atk = self._atk_bonus(actor, melee=not ranged) + mod
        ac = self._effective_ac(target)
        crit = (d20 == CRIT_FACE)
        fumble = (d20 == FUMBLE_FACE)
        hit = (not fumble) and (crit or (d20 + atk >= ac))

        total = d20 + atk
        mod_txt = f" {mod:+d}" if mod else ""
        head = (f"{actor['name']} → {target['name']}｜{label}："
                f"d20 = {d20}{mod_txt} → {total} vs AC {ac}")

        if not hit:
            self.log.append(_entry("miss", head + " ✗ 未命中", d20=d20, total=total, ac=ac))
            return {"hit": False, "damage": 0, "d20": d20, "total": total, "ac": ac}

        # 伤害骰（PC 取武器骰，异族取天生骰）
        dice = actor.get("dice") or actor.get("weaponDice") or [1, 4]
        n, m = int(dice[0]), int(dice[1])
        rolls = DB.roll_dice(n, m, self.rng)
        if crit:
            rolls = rolls + DB.roll_dice(n, m, self.rng)   # 暴击：骰数翻倍

        # 固定加值：异族的天生加值 dmgMod；PC 近战另加力量修正（内核口径）
        flat = int(actor.get("dmgMod", 0) or 0)
        if not ranged and actor.get("strMod"):
            flat += int(actor.get("strMod") or 0)
        dmg = sum(rolls) + flat + dmg_bonus

        # 额外骰（灰线爆发）
        if extra_dice:
            rolls = rolls + extra_dice
            dmg += sum(extra_dice)

        # 弱点特性：默认**先解析再生效**（否则"找弱点"这件事就不存在了）
        weak_note = ""
        for t in (target.get("traits") or []):
            if t.get("key") != "weakpoint":
                continue
            cond = t.get("cond")
            if cond and maneuver not in cond:
                continue
            if t.get("requiresAnalyze", True) and not target.get("weakpointFound"):
                weak_note = f"｜{t['label']}未解析（伤害未加成）"
                continue
            mul = float(t.get("dmgMul", 2) or 2)
            dmg = int(round(dmg * mul))
            weak_note = f"｜命中弱点（{t['label']}）×{mul:g}"

        # 施法者的力量修正（近战武器才加）
        line = (f"{head} ✓ 命中{weak_note}｜伤害 {n}d{m}"
                + (f"+{flat}" if flat else "")
                + (f"+{dmg_bonus}" if dmg_bonus else "")
                + (f" {_dice_str(rolls)}" if rolls else "")
                + f" = {dmg}")
        self.log.append(_entry("hit", line + ("（暴击！）" if crit else ""),
                               d20=d20, total=total, ac=ac, damage=dmg, crit=crit))

        self._apply_damage(target, dmg, source=actor, maneuver=maneuver)
        return {"hit": True, "damage": dmg, "d20": d20, "total": total,
                "ac": ac, "crit": crit, "rolls": rolls}

    def _apply_damage(self, target: dict, dmg: int, source: dict | None = None,
                      maneuver: str = "") -> None:
        target["hp"] = max(0, int(target.get("hp", 0)) - int(dmg))
        self.log.append(_entry("damage",
                               f"{target['name']} 生命 {target['hp']}/{target.get('maxHp', '?')}",
                               uid=target["uid"], hp=target["hp"], dmg=dmg))
        if target["hp"] <= 0:
            target["alive"] = False
            self._on_death(target)
        elif source is not None:
            # 菌丝寄生：命中后附加状态
            for t in (source.get("traits") or []):
                if t.get("key") == "infest" and t.get("status"):
                    if target["uid"] == "pc":
                        TM.apply_status(self.pc, t["status"])
                        self.log.append(_entry(
                            "status", f"{target['name']} 被附加「{t['label']}」",
                            status=t["status"]))

    def _on_death(self, unit: dict) -> None:
        if unit["uid"] == "pc":
            self.log.append(_entry("death", f"{unit['name']} 倒下了。", uid="pc"))
            self._check_end()
            return
        self.log.append(_entry("death", f"{unit['name']} 被击杀。", uid=unit["uid"]))
        self._grant_spark(unit)

    def _grant_spark(self, unit: dict) -> None:
        """异族死亡 → 火花产出，回写面板状态。"""
        tier = unit.get("tier") or "一级"
        info = PE.spark_for_tier(self.ds, tier, self.rng)
        spark = int(info.get("spark", 0) or 0)
        if spark > 0:
            spark = int(round(spark * float(unit.get("sparkMul", 1.0) or 1.0)))
        before = int(self.panel.get("spark", 0) or 0)
        ignited = bool(self.panel.get("ignited"))
        if self.panel and not ignited and spark > 0:
            self.panel["spark"] = min(100, before + spark)
        after = self.panel.get("spark", before)
        tail = "（已点燃 · 火花不再增长，R8）" if ignited else f"→ {after}%"
        self.log.append(_entry(
            "spark",
            f"{unit['name']}（{tier}）火花 +{spark}% {tail}",
            tier=tier, spark=spark, sparkBefore=before, sparkAfter=after,
            blockedByIgnite=ignited))

    # ---------------- 行动 ----------------

    def act(self, uid: str, action: str, params: dict | None = None) -> dict:
        """执行一个单位的行动。返回本次结算摘要。"""
        params = params or {}
        u = self.find(uid)
        if not u or not u.get("alive"):
            return {"ok": False, "error": "单位不存在或已倒下"}
        if self.status != "ongoing":
            return {"ok": False, "error": f"战斗已结束（{self.status}）"}

        before_hp = dict((e["uid"], e["hp"]) for e in self.enemies)

        if u["uid"] == "pc":
            res = self._pc_action(u, action, params)
        else:
            res = self._enemy_action(u, params)

        self._check_end()
        if self.status == "ongoing":
            self._advance()
        return res

    def _pc_action(self, u: dict, action: str, p: dict) -> dict:
        target_uid = p.get("target") or (self._enemies_alive()[0]["uid"]
                                         if self._enemies_alive() else None)
        target = self.find(target_uid) if target_uid else None

        # ---- 法术 ----
        if action.startswith("spell:"):
            return self._cast(u, action.split(":", 1)[1], p, target)

        # ---- 特殊 ----
        if action == "analyze":
            return self._analyze(u, target)
        if action == "gray_surge":
            return self._gray_surge(u, target, p)
        if action == "black_burn":
            return self._black_burn(u, p)
        if action == "defend":
            if u.get("noDefense"):
                return {"ok": False, "error": "本回合已全力出击，无法防御"}
            u["defending"] = True
            self.log.append(_entry("defend", f"{u['name']} 举盾防御（AC +{DEFEND_BONUS}）"))
            return {"ok": True, "action": "defend"}

        # ---- 战技 ----
        if not target:
            return {"ok": False, "error": "没有可攻击的目标"}

        table = {
            "melee_attack":    (0, 0, "近战攻击"),
            "ranged_attack":   (0, 0, "远程攻击"),
            "power_attack":    (-1, 3 if p.get("twoHanded") else 2, "猛力攻击"),
            "whirlwind":       (-6, 0, "旋风切割"),
            "sneak_attack":    (0, 0, "偷袭要害"),
            "deceptive_attack": (-2, 0, "欺诈攻击"),
            "rapid_strike":    (-6, 0, "连环打击"),
            "allout_strong":   (0, 2, "全力强击"),
            "allout_determined": (+4, 0, "精准突击"),
        }
        if action not in table:
            return {"ok": False, "error": f"未知行动: {action}"}

        # 技术前置（内核口径：不学就不能用）
        tech = DB.MANEUVERS.get(action, {}).get("tech")
        if tech and tech not in (u.get("techniques") or []):
            return {"ok": False, "error": f"未学会「{tech}」技术"}

        mod, dmg_bonus, label = table[action]

        # 欺诈攻击：技能有效等级不得低于 10（GURPS 口径）
        if action == "deceptive_attack":
            if self._atk_bonus(u) + mod < 10:
                return {"ok": False, "error": "技能有效等级不足（欺诈攻击不可使技能低于 10）"}

        # 全力强击 / 精准突击：本回合无法防御
        if action in ("allout_strong", "allout_determined"):
            u["noDefense"] = True

        # 多目标（旋风切割 → 所有敌人；连环打击 → 2 次）
        if action == "whirlwind":
            results = []
            for t in self._enemies_alive():
                results.append(self._resolve_attack(u, t, mod, label, dmg_bonus,
                                                    maneuver=action))
            return {"ok": True, "action": action, "results": results}

        if action == "rapid_strike":
            r1 = self._resolve_attack(u, target, mod, label + "①", dmg_bonus, maneuver=action)
            alive = self._enemies_alive()
            r2 = None
            if alive:
                t2 = target if target.get("alive") else alive[0]
                r2 = self._resolve_attack(u, t2, mod, label + "②", dmg_bonus, maneuver=action)
            return {"ok": True, "action": action, "results": [r1, r2]}

        # 偷袭要害：需灵巧武器 + 措手不及，精准伤害随等级成长
        extra_dice = None
        if action == "sneak_attack":
            if not DB.is_finesse(u.get("weapon", "")):
                return {"ok": False, "error": "偷袭需要灵巧武器（匕首/短剑/刺剑/弯刀…）"}
            if not (p.get("flatFooted", True)):
                return {"ok": False, "error": "目标未措手不及，无法偷袭"}
            dice = max(1, min(10, (self._atk_bonus(u) - 4) // 2 + 1))
            extra_dice = DB.roll_dice(dice, 6, self.rng)
            self.log.append(_entry("sneak", f"偷袭精准伤害 {dice}d6 {_dice_str(extra_dice)}",
                                   dice=dice))

        r = self._resolve_attack(u, target, mod, label, dmg_bonus,
                                 extra_dice=extra_dice, maneuver=action,
                                 ranged=(action == "ranged_attack"))
        return {"ok": True, "action": action, "results": [r]}

    def _cast(self, u: dict, tech: str, p: dict, target: dict | None) -> dict:
        """施法：扣五色法力 → 施法检定 → 伤害/治疗 → 结构税（R13）。"""
        info = DB.SPELL_LIBRARY.get(tech)
        if not info:
            return {"ok": False, "error": f"未知法术: {tech}"}
        if tech not in (u.get("techniques") or []):
            return {"ok": False, "error": f"未学会「{tech}」"}

        pool = u.get("manaPool") or {}
        color = info["color"]
        ring = int(info.get("ring", 1))
        cost = 2 if ring >= 3 else 1
        if int(pool.get(color, 0)) < cost:
            return {"ok": False,
                    "error": f"{color}色法力不足：需要 {cost}，剩 {int(pool.get(color, 0))}"}

        pool[color] = int(pool.get(color, 0)) - cost

        # 结构税：五色组合施法，灰线加深（R13）
        tax = 1 if ring > 0 else 0
        if tax:
            u["grayCells"] = int(u.get("grayCells", 0)) + tax
            self.log.append(_entry("tax", f"结构税：灰线 +{tax} 格 → {u['grayCells']} 格（R13）",
                                   gray=u["grayCells"]))

        label = info["label"]
        d20 = DB.roll_d20(self.rng)
        cast_bonus = int(u.get("atkMelee", 0)) if tech in ("治疗言灵",) else \
            int((u.get("skills") or {}).get("施法攻击", u.get("atkMelee", 0)) or 0)

        # 治疗类
        if tech == "治疗言灵":
            heal = sum(DB.roll_dice(1 + max(0, ring - 1), 4, self.rng)) + max(1, cast_bonus)
            u["hp"] = min(int(u.get("maxHp", u["hp"])), int(u.get("hp", 0)) + heal)
            self.log.append(_entry("heal",
                                   f"{u['name']} 施放{label}：恢复 {heal} 生命 → "
                                   f"{u['hp']}/{u.get('maxHp')}",
                                   heal=heal, hp=u["hp"]))
            return {"ok": True, "action": f"spell:{tech}", "heal": heal}

        if not target:
            return {"ok": False, "error": "没有可攻击的目标"}

        # 自动命中类（魔法飞弹）
        if tech == "魔法飞弹":
            n = 3
            rolls = [self.rng.randint(1, 4) + 1 for _ in range(n)]
            dmg = sum(rolls)
            self.log.append(_entry("hit",
                                   f"{u['name']} 施放{label}：{n} 发自动命中 "
                                   f"1d4+1 ×{n} = {dmg}", damage=dmg))
            self._apply_damage(target, dmg, source=u, maneuver=f"spell:{tech}")
            return {"ok": True, "action": f"spell:{tech}", "damage": dmg}

        # 豁免类（火球术/闪电束/寒冰锥）
        dc = int(p.get("dc") or (13 + ring))
        save_bonus = int((target.get("saves") or {}).get("ref", 0) or 0)
        total = d20 + cast_bonus
        n_d, m_d = {"火球术": (8, 6), "闪电束": (8, 6), "寒冰锥": (8, 8)}.get(tech, (8, 6))
        rolls = DB.roll_dice(n_d, m_d, self.rng)
        dmg = sum(rolls)
        saved = (d20 + save_bonus) >= dc
        if saved:
            dmg = dmg // 2
        self.log.append(_entry(
            "spell",
            f"{u['name']} 施放{label}（{color}色 -{cost}）：{n_d}d{m_d} {_dice_str(rolls)} = {dmg}"
            + (f"，{target['name']} 豁免成功（减半）" if saved else ""),
            damage=dmg, saved=saved, dc=dc))
        targets = [target]
        if p.get("aoe") and tech in ("火球术", "闪电束", "寒冰锥"):
            targets = self._enemies_alive()
        for t in targets:
            self._apply_damage(t, dmg if not p.get("aoe") else dmg, source=u,
                               maneuver=f"spell:{tech}")
        return {"ok": True, "action": f"spell:{tech}", "damage": dmg, "saved": saved}

    def _analyze(self, u: dict, target: dict | None) -> dict:
        """弱点解析：侦察/洞察检定，成功后对该目标的弱点伤害才生效。

        DC 按变异等级取（trpg_mechanics.TIER_TABLE：二级 13 / 三级 18 / 王级 25）。
        这是把正文里的"弱点解析"变成可掷的一步——不解析就只能硬砍，
        解析成功才能打在脊背菌丝根部的蓝紫节点上。
        """
        if not target:
            return {"ok": False, "error": "没有可解析的目标"}
        if target.get("weakpointFound"):
            return {"ok": False, "error": f"{target['name']} 的弱点已解析"}

        try:
            dc = TM.tier_profile(target.get("tier") or "一级").get("dc") or 10
        except Exception:
            dc = 10
        skills = u.get("skills") or {}
        rank = max(int(skills.get("侦察", 0) or 0), int(skills.get("洞察", 0) or 0))
        wis = int((u.get("attributes") or {}).get("感知", 10) or 10)
        mod = (wis - 10) // 2
        d20 = DB.roll_d20(self.rng)
        total = d20 + rank + mod
        ok = total >= dc
        if ok:
            target["weakpointFound"] = True
        self.log.append(_entry(
            "analyze",
            f"{u['name']} 解析 {target['name']}：d20 = {d20} + 侦察{rank} "
            f"+ 感知{mod:+d} = {total} vs DC {dc} → "
            + ("✓ 弱点已标记" if ok else "✗ 未能看穿"),
            d20=d20, rank=rank, mod=mod, total=total, dc=dc, success=ok))
        return {"ok": True, "action": "analyze", "success": ok, "dc": dc, "total": total}

    def _gray_surge(self, u: dict, target: dict | None, p: dict) -> dict:
        """灰线爆发：烧 3 格灰线换 1d6 伤害，灰线加深深 2 格（R11/R13）。"""
        cells = int(p.get("cells") or GRAY_SURGE_PER_D6)
        if cells < GRAY_SURGE_PER_D6:
            return {"ok": False, "error": f"至少烧 {GRAY_SURGE_PER_D6} 格灰线"}
        cur = int(u.get("grayCells", 0) or 0)
        if cur < cells:
            return {"ok": False, "error": f"灰线仅 {cur} 格，不足 {cells} 格"}
        dice_n = cells // GRAY_SURGE_PER_D6
        extra = DB.roll_dice(dice_n, 6, self.rng)
        u["grayCells"] = cur + GRAY_SURGE_COST
        self.log.append(_entry(
            "gray",
            f"{u['name']} 引爆灰线 {cells} 格 → {dice_n}d6 {_dice_str(extra)}；"
            f"灰线加深 +{GRAY_SURGE_COST} → {u['grayCells']} 格（R11 单调递增）",
            cells=cells, dice=dice_n, gray=u["grayCells"]))
        if not target:
            return {"ok": True, "action": "gray_surge", "extra": extra}
        r = self._resolve_attack(u, target, 0, "灰线爆发", sum(extra),
                                 maneuver="gray_surge")
        return {"ok": True, "action": "gray_surge", "results": [r]}

    def _black_burn(self, u: dict, p: dict) -> dict:
        """黑色代偿：以记忆为燃料换法力（R9），代价走代价投骰。"""
        mode = p.get("mode", "self")
        pool = u.get("manaPool") or {}
        if int(pool.get("黑", 0)) < 1:
            return {"ok": False, "error": "黑色法力不足（黑色代偿需黑×1）"}
        roll = TM.burn_cost_roll(self.volume, int(p.get("blackMult", 1) or 1), mode, self.rng)
        if not roll.get("ok"):
            return {"ok": False, "error": roll.get("error", "代偿失败")}
        pool["黑"] = int(pool.get("黑", 0)) - 1
        gain = int(p.get("gain", 2))
        pool[p.get("to", "蓝")] = int(pool.get(p.get("to", "蓝"), 0)) + gain
        u["grayCells"] = int(u.get("grayCells", 0) or 0) + 1
        self.log.append(_entry(
            "burn",
            f"{u['name']} 黑色代偿：{roll['mode']}（深度 {roll['depth']}）→ "
            f"{p.get('to', '蓝')}色 +{gain}，灰线 +1 → {u['grayCells']} 格｜"
            f"症状：{'、'.join(roll['symptoms'])}",
            depth=roll["depth"], symptoms=roll["symptoms"], gray=u["grayCells"]))
        return {"ok": True, "action": "black_burn", "burn": roll, "gain": gain}

    def _enemy_action(self, u: dict, p: dict) -> dict:
        """敌人 AI：打 PC；多攻击者按次数连击；低血量不逃跑（异族不撤退）。"""
        results = []
        times = max(1, int(u.get("multiattack", 1) or 1))
        for i in range(times):
            if not self.pc.get("alive"):
                break
            # 异族的天生伤害加值走 stat block 的 dmgMod，不再重复传 dmg_bonus
            r = self._resolve_attack(
                u, self.pc, 0,
                f"{u['name']}的攻击" + (f"#{i + 1}" if times > 1 else ""),
                0, maneuver="enemy_attack")
            results.append(r)
        return {"ok": True, "action": "enemy_attack", "results": results}

    # ---------------- 推进 ----------------

    def run_enemy_turns(self, max_turns: int = 50) -> list[dict]:
        """一键推进所有敌人回合，直到轮到 PC（或战斗结束）。"""
        out = []
        n = 0
        while self.status == "ongoing" and n < max_turns:
            cur = self.current
            if cur is None:
                break
            if cur["uid"] == "pc":
                break
            out.append(self.act(cur["uid"], "enemy_attack"))
            n += 1
        return out

    # ---------------- 快照 ----------------

    # ---------------- 持久化 ----------------
    #
    # 战斗要跨进程存活：CLI 每条命令一个子进程、GUI 刷新页面都会丢状态。
    # 这里把整场遭遇（含随机数发生器状态）序列化到 JSON，
    # 恢复后继续打的骰子序列与中断前完全一致——不会"读档后运气变了"。

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "status": self.status,
            "turnIdx": self.turn_idx,
            "order": list(self.order),
            "volume": self.volume,
            "pc": _public(self.pc),
            "enemies": [_public(e) for e in self.enemies],
            "log": self.log[-200:],
            "rng": list(self.rng.getstate()),
        }

    @classmethod
    def from_dict(cls, d: dict, ds: dict | None = None,
                  panel_state: dict | None = None) -> "Encounter":
        pc = dict(d.get("pc") or {})
        enemies = [dict(e) for e in (d.get("enemies") or [])]
        enc = cls(pc, enemies, ds=ds, panel_state=panel_state, volume=d.get("volume", 1))
        enc.round = int(d.get("round", 1) or 1)
        enc.status = d.get("status", "ongoing")
        enc.order = list(d.get("order") or [])
        enc.turn_idx = int(d.get("turnIdx", 0) or 0)
        enc.log = list(d.get("log") or [])
        st = d.get("rng")
        if st:
            try:
                enc.rng.setstate((int(st[0]), tuple(int(x) for x in st[1]), st[2]))
            except Exception:
                pass                       # 状态损坏就重新播种，不炸恢复流程
        return enc

    def snapshot(self) -> dict:
        return {
            "round": self.round,
            "status": self.status,
            "turn": (self.current or {}).get("uid"),
            "turnName": (self.current or {}).get("name"),
            "pc": _public(self.pc),
            "enemies": [_public(e) for e in self.enemies],
            "order": list(self.order),
            "log": self.log[-40:],
            "spark": self.panel.get("spark"),
            "grayCells": self.pc.get("grayCells"),
            "manaPool": self.pc.get("manaPool"),
        }


def _public(u: dict) -> dict:
    """去掉不可序列化的字段（如内核 Character 实例）。"""
    skip = {"char", "_skip"}
    return {k: v for k, v in u.items() if k not in skip and not callable(v)}


# --------------------------------------------------------------------------
# 便捷入口
# --------------------------------------------------------------------------

def new_encounter(profile_key: str = "v3-mycelium", enemies: list[dict] | None = None,
                  ds: dict | None = None, panel_state: dict | None = None,
                  seed: int | None = None, name: str = "魏成河",
                  carry_over: bool = False,
                  pc_override: dict | None = None) -> dict:
    """开一场遭遇：按剧情档位建 PC + 按 [{name,count}] 生成敌人。

    carry_over=False（默认）——**显式选档 = 从该卷重新开局**：
      火花 / 点燃 / 灰线 / 卷号一律回到 profile 的初值。
      否则同一 sid 的 panel_state 会沿用上一场的累积值，出现
      「选了第三卷档位、火花却显示上一场打完的 14%」这种串场。
    carry_over=True ——接续战役：保留 panel_state 已有进度，
      只在本场战斗内继续累积。

    pc_override ——**战役模式**：PC 由 campaign.Campaign.build_pc() 按跨场
      累积状态重建（带持久生命 / 法力 / 灰线）。此时战役状态是唯一真理源，
      panel_state 必须被强制同步，否则会沿用上一场残留的火花。
    """
    ok, err = DB.kernel_available()
    if not ok:
        return {"ok": False, "error": err}

    if pc_override is not None:
        pc = dict(pc_override)
        # 战役状态优先：把面板火花/点燃/灰线对齐到战役当前值
        if panel_state is not None:
            src = pc.get("source") or {}
            if src.get("spark") is not None:
                panel_state["spark"] = int(src["spark"] or 0)
            panel_state["ignited"] = bool(src.get("ignited"))
            panel_state["grayCells"] = int(pc.get("grayCells", 0) or 0)
            if src.get("volume"):
                panel_state["volume"] = int(src["volume"])
            pn = pc.get("manaPool")
            if isinstance(pn, dict):
                panel_state["manaPool"] = dict(pn)
    else:
        sb = DB.build_from_profile(profile_key, name=name)
        pc = {k: v for k, v in sb.items() if k not in ("char", "buildLog")}

        if panel_state is not None and not carry_over:
            src = pc.get("source") or {}
            if src.get("spark") is not None:
                panel_state["spark"] = int(src["spark"] or 0)
            panel_state["ignited"] = bool(src.get("ignited"))
            panel_state["grayCells"] = int(src.get("grayCells") or 0)
            if src.get("volume"):
                panel_state["volume"] = int(src["volume"])

    specs = enemies or [{"name": "变异鬣狗", "count": 2}]
    group, blocked = BC.spawn_group(specs, ds)
    if not group:
        return {"ok": False, "error": "没有可交战的异族"
                + (f"（{', '.join(blocked)} 不可击杀）" if blocked else "")}

    enc = Encounter(pc, group, ds=ds, panel_state=panel_state, seed=seed)
    enc.roll_initiative()
    return {"ok": True, "encounter": enc, "blocked": blocked,
            "pc": _public(enc.pc), "enemies": [_public(e) for e in enc.enemies],
            "initiative": enc.log[0] if enc.log else None}
