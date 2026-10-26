#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rpc_server.py — Python 侧 JSON-RPC over stdio 服务端

Node 桥以子进程拉起本脚本，通过 stdin/stdout 传 JSON-RPC 2.0 请求。
stderr 用于日志（不污染协议流），stdout 只跑协议。

方法一览
--------
dataset.get        取数据层概要 + 解析报告
selfcheck          数据层完整性体检
panel.new          新建面板状态
panel.snapshot     取面板快照
panel.kill         击杀异族（累加火花 + 解锁判定）
panel.allocate     分配自由属性
panel.breakthrough 属性突破
panel.grayline     灰线扩张
panel.structureTax 结构税
panel.volume       卷间跃迁（耐受/代偿档位）
panel.mana         法力池存取
panel.ignite       手动点燃
panel.render       生成可粘进正文的面板文本
panel.reset        重置状态
codex.bestiary     异族图鉴
codex.tiers        变异等级谱系
codex.planes       位面体系
codex.rules        R1-R15
codex.plot         伏笔台账
codex.costArc      代价弧
codex.timeline     时间轴
codex.characters   角色档案（旧版 11 人，停在第一卷）
codex.characterCards  角色卡（bible/characters/ 19 张，含外传适配评级）
codex.terms        术语锁定表
codex.selfcheck    数据层自检
scan.chapter       章节机扫
scan.file          按路径机扫
trpg.toolbox       机制库总览
trpg.check         d20 检定
trpg.tier          变异等级档位
trpg.matchup       群遭遇配平
trpg.status        状态效果叠加
trpg.burn          代价投骰
pc.profiles        剧情档位预设列表
pc.build           按档位/规格构建可战斗角色
pc.maneuvers       角色当前可用动作（含法术）
pc.catalog         D20 规则数据总览（技能/装备/技术/武器骰）
combat.catalog     敌人目录（谱系 + 具名异族 + 特性）
combat.new         开一场遭遇战
combat.state       取战斗快照
combat.act         执行一次行动
combat.enemies     推进敌人回合
combat.auto        自动打完（PC 用简单策略）
combat.end         结束/放弃战斗
combat.narrate     把战斗日志转成叙事文本
campaign.chains    预置卷级遭遇链目录
campaign.new       新建战役（按链）
campaign.state     战役快照（HP/法力/灰线/火花/进度）
campaign.next      开战役链的下一场（PC 沿用跨场状态）
campaign.insert    自由插入一场遭遇
campaign.rest      休整：恢复 25% 生命上限，灰线不回退（R11）
campaign.draw      汲取法力：+1 点指定色，灰线 +1 格（R11）
campaign.heal      治疗言灵（绿 1 环，耗 1 点绿法力）
campaign.apply     把当前战斗结果收回战役并推进链
campaign.end       结束战役
research.get       调研数据
"""

from __future__ import annotations

import json
import os
import random
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import panel_engine as PE          # noqa: E402
import consistency_scanner as CS   # noqa: E402
import trpg_mechanics as TM        # noqa: E402

# 战斗沙盘的三个模块**延迟导入**：它们依赖 allin-engine（D20 规则内核），
# 而内核是本仓唯一的可选运行时依赖。直接顶层 import 会让"没装内核"变成
# 整个引擎起不来——连设定检索都用不了。延迟导入后，内核缺失只影响沙盘，
# 且错误信息由 d20_bridge.kernel_available() 精确给出。
import d20_bridge as DB            # noqa: E402  （本模块本身不 import 内核）

HERE = Path(__file__).parent
DS: dict = {}
STATES: dict[str, dict] = {}
RESEARCH: dict = {}
ENCOUNTERS: dict[str, Any] = {}    # sid → combat_engine.Encounter
CAMPAIGNS: dict[str, Any] = {}     # sid → campaign.Campaign（跨场状态）

# 战斗存档：CLI 每条命令一个子进程、GUI 刷新页面都会丢内存状态，
# 故每场遭遇都落一份 JSON，恢复后连随机数发生器状态都一致。
COMBAT_STATE_PATH = HERE / "data" / "combat_state.json"


def _combat_save(sid: str) -> None:
    e = ENCOUNTERS.get(sid)
    if not e:
        return
    store = {}
    if COMBAT_STATE_PATH.exists():
        try:
            store = json.loads(COMBAT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            store = {}
    store[sid] = e.to_dict()
    try:
        COMBAT_STATE_PATH.write_text(json.dumps(store, ensure_ascii=False),
                                     encoding="utf-8")
    except Exception as ex:
        print(f"[warn] 战斗存档失败: {ex}", file=sys.stderr)


def _combat_drop(sid: str) -> None:
    ENCOUNTERS.pop(sid, None)
    if not COMBAT_STATE_PATH.exists():
        return
    try:
        store = json.loads(COMBAT_STATE_PATH.read_text(encoding="utf-8"))
        store.pop(sid, None)
        COMBAT_STATE_PATH.write_text(json.dumps(store, ensure_ascii=False),
                                     encoding="utf-8")
    except Exception:
        pass


def _combat_load(sid: str):
    """内存没有就试着从存档恢复。"""
    if sid in ENCOUNTERS:
        return ENCOUNTERS[sid]
    if not COMBAT_STATE_PATH.exists():
        return None
    try:
        store = json.loads(COMBAT_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    d = store.get(sid)
    if not d:
        return None
    try:
        import combat_engine as CE
        e = CE.Encounter.from_dict(d, ds=DS, panel_state=_state_for(sid))
        ENCOUNTERS[sid] = e
        return e
    except Exception as ex:
        print(f"[warn] 战斗存档恢复失败: {ex}", file=sys.stderr)
        return None


def _err(msg: str, code: int = -32000):
    return {"error": {"code": code, "message": msg}}


# --------------------------------------------------------------------------
# 方法实现
# --------------------------------------------------------------------------

def m_dataset_get(p):
    meta = DS.get("meta") or {}
    return {
        "ok": True,
        "generatedAt": meta.get("generatedAt"),
        "sourceRoot": meta.get("sourceRoot"),
        "parseReport": meta.get("parseReport"),
        "quality": meta.get("quality"),
    }


def m_selfcheck(p):
    return PE.selfcheck(DS)


def _state(sid: str) -> dict:
    if sid not in STATES:
        STATES[sid] = PE.new_state(DS)
    return STATES[sid]


def m_panel_new(p):
    sid = p.get("sid") or "default"
    STATES[sid] = PE.new_state(DS)
    return {"ok": True, "sid": sid, "snapshot": PE.snapshot(DS, STATES[sid])}


def m_panel_snapshot(p):
    st = _state(p.get("sid") or "default")
    return {"ok": True, "snapshot": PE.snapshot(DS, st)}


def m_panel_kill(p):
    st = _state(p.get("sid") or "default")
    diff = PE.op_kill(DS, st, p.get("tier", "一级"), int(p.get("count", 1)))
    return {"ok": True, "diff": diff, "snapshot": PE.snapshot(DS, st)}


def m_panel_allocate(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_allocate(DS, st, p.get("attr", "体质"), int(p.get("count", 1)))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_breakthrough(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_breakthrough(DS, st, p.get("attr", "体质"))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_grayline(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_grayline(DS, st, int(p.get("cells", 0)), p.get("reason", ""))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_structure_tax(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_structure_tax(DS, st, int(p.get("cells", 1)))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_volume(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_volume_progress(DS, st, int(p.get("volume", 2)))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_mana(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_mana(DS, st, p.get("color", "蓝"), int(p.get("amount", 1)))
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_ignite(p):
    st = _state(p.get("sid") or "default")
    r = PE.op_ignite(DS, st)
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_panel_render(p):
    st = _state(p.get("sid") or "default")
    return {"ok": True, "text": PE.render_panel_text(DS, st)}


def m_panel_reset(p):
    sid = p.get("sid") or "default"
    STATES[sid] = PE.new_state(DS)
    return {"ok": True, "snapshot": PE.snapshot(DS, STATES[sid])}


def m_codex_bestiary(p):
    return {"ok": True, "items": (DS.get("creatures") or {}).get("bestiary") or []}


def m_codex_tiers(p):
    return {"ok": True, "items": PE.get_tiers(DS)}


def m_codex_planes(p):
    pl = DS.get("planes") or {}
    return {"ok": True, "layers": pl.get("layers") or [],
            "colorPlanes": pl.get("colorPlanes") or [],
            "toleranceTable": pl.get("toleranceTable") or [],
            "namingRules": pl.get("namingRules") or []}


def m_codex_rules(p):
    return {"ok": True, "rules": DS.get("rules") or [],
            "leakLines": DS.get("leakLines") or []}


def m_codex_plot(p):
    return {"ok": True, "items": DS.get("plotThreads") or []}


def m_codex_costarc(p):
    return {"ok": True, **(DS.get("costArc") or {})}


def m_codex_timeline(p):
    return {"ok": True, "items": DS.get("timeline") or []}


def m_codex_characters(p):
    return {"ok": True, "items": DS.get("characters") or []}


def m_codex_character_cards(p):
    """bible/characters/ 下的分文件角色卡（19 张，含外传适配评级与写作纪律数）。

    与 codex.characters 的区别：那份是 一致性核查/角色档案.md 的旧版11 人档案，
    停在第一卷；这份是本轮梳理后的权威源，第五卷新角色与外传评级只在这里。
    """
    return {"ok": True, "items": DS.get("characterCards") or []}


def m_codex_terms(p):
    return {"ok": True, "items": DS.get("terminology") or []}


def m_scan_chapter(p):
    text = p.get("text") or ""
    ch = int(p.get("chapter") or 999)
    return CS.scan(DS, text, ch)


def m_scan_file(p):
    path = Path(p.get("path") or "")
    if not path.exists():
        return _err(f"文件不存在: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    ch = int(p.get("chapter") or 999)
    r = CS.scan(DS, text, ch)
    r["file"] = path.name
    r["path"] = str(path)
    return r


def m_trpg_toolbox(p):
    return {"ok": True, **TM.toolbox()}


def m_trpg_check(p):
    mod = TM.attr_mod_5e(int(p.get("score", 10)))
    dc = int(p.get("dc", 15))
    r = TM.roll_check(dc, mod, bool(p.get("advantage")), bool(p.get("disadvantage")))
    r["attrName"] = p.get("attrName", "")
    r["attrScore"] = int(p.get("score", 10))
    return {"ok": True, **r}


def m_trpg_rate(p):
    mod = TM.attr_mod_5e(int(p.get("score", 10)))
    return {"ok": True, "dc": int(p.get("dc", 15)), "mod": mod,
            "rate": round(TM.success_rate(int(p.get("dc", 15)), mod,
                                          bool(p.get("advantage")),
                                          bool(p.get("disadvantage"))), 1)}


def m_trpg_tier(p):
    try:
        return {"ok": True, **TM.tier_profile(p.get("tier", "一级"))}
    except ValueError as e:
        return _err(str(e))


def m_trpg_matchup(p):
    specs = p.get("tiers") or ["二级"]
    profiles = []
    for s in specs:
        try:
            profiles.append(TM.tier_profile(s))
        except ValueError as e:
            return _err(str(e))
    return {"ok": True, **TM.matchup(profiles)}


def m_trpg_status(p):
    st = _state(p.get("sid") or "default")
    st.setdefault("statuses", {})
    r = TM.apply_status(st, p.get("key", "gray_erosion"))
    r["effectiveAttrs"] = TM.effective_attrs(st)
    r["snapshot"] = PE.snapshot(DS, st)
    return r


def m_trpg_burn(p):
    try:
        return TM.burn_cost_roll(int(p.get("volume", 3)),
                                  int(p.get("blackMult", 2)),
                                  p.get("mode", "self"))
    except ValueError as e:
        return _err(str(e))


def m_research_get(p):
    return {"ok": True, **(RESEARCH or {})}


# --------------------------------------------------------------------------
# 战斗沙盘（pc.* / combat.*）
# --------------------------------------------------------------------------

def _require_combat():
    """取战斗模块；内核缺失时返回明确的错误字典。"""
    ok, err = DB.kernel_available()
    if not ok:
        return None, {"error": {"code": -32001, "message": err}}
    import combat_engine as CE
    import bestiary_combat as BC
    return (CE, BC), None


def m_pc_profiles(p):
    ok, err = DB.kernel_available()
    if not ok:
        return err
    return {"ok": True, "profiles": [
        {"key": k, "label": v["label"], "spark": v["spark"],
         "ignited": v["ignited"], "attrs": v["attrs"],
         "equipment": v["equipment"], "techniques": v["techniques"],
         "note": v["note"]}
        for k, v in DB.PROFILES.items()
    ]}


def m_pc_build(p):
    ok, err = DB.kernel_available()
    if not ok:
        return err
    key = p.get("profile") or "v3-mycelium"
    try:
        sb = DB.build_from_profile(key, name=p.get("name") or "魏成河")
    except ValueError as e:
        return _err(str(e))
    char = sb.pop("char", None)
    if p.get("spec"):                    # 在档位基础上叠加自定义（属性/技能/技术/装备）
        spec = dict(p["spec"])
        try:
            extra = DB.build_from_spec({
                "name": spec.get("name") or sb["name"],
                "cp": spec.get("cp", 0),
                "spark": sb.get("source", {}).get("spark", 0),
                "ignited": sb.get("source", {}).get("ignited", False),
                "attributes": spec.get("attributes") or sb["attributes"],
                "skills": spec.get("skills") or sb["skills"],
                "techniques": spec.get("techniques") or sb["techniques"],
                "equipment": spec.get("equipment") or sb["equipment"],
            })
            extra.pop("char", None)
            sb = extra
            char = None
        except RuntimeError as e:
            return _err(str(e))
    if char is not None:
        sb["maneuvers"] = DB.available_maneuvers(char)
    return {"ok": True, "pc": sb}


def m_pc_maneuvers(p):
    ok, err = DB.kernel_available()
    if not ok:
        return err
    key = p.get("profile") or "v3-mycelium"
    try:
        sb = DB.build_from_profile(key)
    except ValueError as e:
        return _err(str(e))
    return {"ok": True, "maneuvers": DB.available_maneuvers(sb["char"]),
            "profile": {"key": key, "label": sb.get("profile", {}).get("label", "")}}


def m_pc_catalog(p):
    ok, err = DB.kernel_available()
    if not ok:
        return err
    return DB.kernel_catalog()


def m_combat_catalog(p):
    mods, err = _require_combat()
    if err:
        return err
    CE, BC = mods
    return BC.catalog(DS)


def _state_for(sid: str) -> dict:
    """取（必要时新建）面板状态——战斗结算要回写火花/灰线。"""
    if sid not in STATES:
        STATES[sid] = PE.new_state(DS)
    return STATES[sid]


def m_combat_new(p):
    mods, err = _require_combat()
    if err:
        return err
    CE, BC = mods
    sid = p.get("sid") or "default"
    try:
        r = CE.new_encounter(
            profile_key=p.get("profile") or "v3-mycelium",
            enemies=p.get("enemies") or [{"name": "变异鬣狗", "count": 2}],
            ds=DS, panel_state=_state_for(sid),
            seed=p.get("seed"), name=p.get("name") or "魏成河",
            carry_over=bool(p.get("carryOver")),
        )
    except ValueError as e:
        return _err(str(e))
    if not r.get("ok"):
        return _err(r.get("error", "开局失败"))
    ENCOUNTERS[sid] = r["encounter"]
    _combat_save(sid)
    return {"ok": True, "blocked": r.get("blocked") or [],
            "snapshot": ENCOUNTERS[sid].snapshot()}


def _enc(p):
    sid = p.get("sid") or "default"
    e = _combat_load(sid)
    if not e:
        return None, _err(f"没有进行中的战斗（sid={sid}），先调 combat.new")
    return e, None


def m_combat_state(p):
    e, err = _enc(p)
    if err:
        return err
    return {"ok": True, "snapshot": e.snapshot()}


def m_combat_act(p):
    e, err = _enc(p)
    if err:
        return err
    sid = p.get("sid") or "default"
    r = e.act(p.get("uid") or "pc", p.get("action") or "melee_attack",
              p.get("params") or {})
    _combat_save(sid)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error"), "snapshot": e.snapshot()}
    return {"ok": True, "result": r, "snapshot": e.snapshot()}


def m_combat_enemies(p):
    e, err = _enc(p)
    if err:
        return err
    e.run_enemy_turns()
    _combat_save(p.get("sid") or "default")
    return {"ok": True, "snapshot": e.snapshot()}


def m_combat_auto(p):
    """自动打完：PC 用简单策略（血少先治疗/防御，否则优先高伤害动作）。"""
    e, err = _enc(p)
    if err:
        return err
    max_rounds = int(p.get("maxRounds", 40) or 40)
    steps = 0
    while e.status == "ongoing" and steps < max_rounds * 8:
        steps += 1
        cur = e.current
        if cur is None:
            break
        if cur["uid"] == "pc":
            alive = e._enemies_alive()
            if not alive:
                break
            tgt = alive[0]
            pc = e.pc
            act, params = "melee_attack", {"target": tgt["uid"]}
            # 先解析弱点，再打（弱点未解析时伤害不加成）
            if not tgt.get("weakpointFound") and any(
                    t.get("key") == "weakpoint" for t in (tgt.get("traits") or [])):
                act = "analyze"
            elif pc["hp"] < pc["maxHp"] * 0.35 and "治疗言灵" in (pc.get("techniques") or []):
                act, params = "spell:治疗言灵", {}
            elif "猛力攻击" in (pc.get("techniques") or []):
                act, params = "power_attack", {"target": tgt["uid"], "twoHanded": False}
            r = e.act("pc", act, params)
            if not r.get("ok"):
                e.act("pc", "melee_attack", {"target": tgt["uid"]})
        else:
            e.run_enemy_turns()
        if e.round > max_rounds:
            break
    _combat_save(p.get("sid") or "default")
    return {"ok": True, "status": e.status, "round": e.round,
            "snapshot": e.snapshot()}


def m_combat_end(p):
    sid = p.get("sid") or "default"
    e = _combat_load(sid)
    if not e:
        return _err(f"没有进行中的战斗（sid={sid}）")
    _combat_drop(sid)
    return {"ok": True, "status": e.status, "round": e.round,
            "snapshot": e.snapshot(), "spark": _state_for(sid).get("spark")}


def m_combat_narrate(p):
    """把战斗日志转成可直接粘进正文的段落。

    纪律：只写**可观测的行为与结果**，不写内心独白
    （长弧规划·写作纪律：失忆/代价写行为不写独白）。
    """
    e, err = _enc(p)
    if err:
        return err
    lines = []
    for entry in e.log:
        k = entry["kind"]
        t = entry["text"]
        if k in ("initiative", "round", "tax", "status", "analyze",
                 "gray", "burn", "death", "spark", "end", "heal", "defend"):
            lines.append(t)
        elif k in ("hit", "miss", "spell"):
            lines.append(t)
    head = f"【遭遇】{' vs '.join(x['name'] for x in e.enemies)}"
    return {"ok": True, "title": head, "lines": lines,
            "text": "\n".join([head] + lines),
            "status": e.status, "round": e.round}


# --------------------------------------------------------------------------
# 战役层：跨场保留 HP / 法力 / 灰线 / 火花，把一场场遭遇串成推进线
# --------------------------------------------------------------------------

def _require_campaign():
    """战役层依赖战斗模块（进而依赖 D20 内核），故同样延迟导入。"""
    try:
        import campaign as CP
        return CP, None
    except Exception as e:
        return None, _err(f"战役层不可用：{type(e).__name__}: {e}"
                          f"（需要 allin-engine 内核：pip install allin-engine）")


def _campaign_load(sid: str):
    if sid in CAMPAIGNS:
        return CAMPAIGNS[sid]
    CP, err = _require_campaign()
    if err:
        return None
    raw = CP.load().get(sid)
    if not raw:
        return None
    try:
        c = CP.Campaign.from_dict(raw, ds=DS)
        CAMPAIGNS[sid] = c
        return c
    except Exception as ex:
        print(f"[warn] 战役存档恢复失败: {ex}", file=sys.stderr)
        return None


def _campaign_save() -> None:
    CP, err = _require_campaign()
    if err or not CAMPAIGNS:
        return
    CP.save(CAMPAIGNS)


def _camp(sid: str):
    c = _campaign_load(sid)
    if not c:
        return None, _err(f"没有进行中的战役（sid={sid}），先调 campaign.new")
    return c, None


def m_campaign_chains(p):
    CP, err = _require_campaign()
    if err:
        return err
    return CP.chains()


def m_campaign_new(p):
    CP, err = _require_campaign()
    if err:
        return err
    sid = p.get("sid") or "default"
    try:
        c = CP.Campaign(chain_key=p.get("chain") or "v1-seed", ds=DS,
                        name=p.get("name") or "魏成河", seed=p.get("seed"))
    except ValueError as e:
        return _err(str(e))
    CAMPAIGNS[sid] = c
    _campaign_save()
    return c.snapshot()


def m_campaign_state(p):
    c, err = _camp(p.get("sid") or "default")
    if err:
        return err
    return c.snapshot()


def _campaign_open_battle(sid: str, c, spec: dict) -> dict:
    """用战役当前（跨场累积后的）PC 状态开一场遭遇。"""
    CE, BC = _require_combat()[0]
    try:
        r = CE.new_encounter(
            enemies=spec["enemies"], ds=DS, panel_state=_state_for(sid),
            seed=spec.get("seed"), name=c.name, pc_override=c.build_pc(),
        )
    except ValueError as e:
        return _err(str(e))
    if not r.get("ok"):
        return _err(r.get("error", "开局失败"))
    ENCOUNTERS[sid] = r["encounter"]
    _combat_save(sid)
    out = c.snapshot()
    out["battle"] = ENCOUNTERS[sid].snapshot()
    out["encounterName"] = spec.get("name")
    out["encounterNote"] = spec.get("note", "")
    return out


def m_campaign_next(p):
    """开战役链的下一场（PC 沿用跨场状态）。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    if c.status != "ongoing":
        return _err(f"战役已结束（status={c.status}），先调 campaign.new")
    spec = c.next_spec()
    if not spec.get("ok"):
        return _err(spec.get("error", "取下一场失败"))
    return _campaign_open_battle(sid, c, spec)


def m_campaign_insert(p):
    """自由插入一场（不计入链进度，但插在下一场之前）。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    spec = c.insert_spec(p.get("enemies") or [], name=p.get("name") or "")
    if not spec.get("ok"):
        return _err(spec.get("error", "插入失败"))
    _campaign_save()
    return _campaign_open_battle(sid, c, spec)


def m_campaign_rest(p):
    """休整：恢复 25% 生命上限，灰线不回退（R11），法力不恢复。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    r = c.rest()
    if not r.get("ok"):
        return _err(r.get("error", "休整失败"))
    _campaign_save()
    out = c.snapshot()
    out["rest"] = r
    return out


def m_campaign_draw(p):
    """汲取法力：+1 点指定色，灰线 +1 格（污染加深才扛得住，R11）。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    r = c.draw_mana(p.get("color") or "绿", int(p.get("cells", 1) or 1))
    if not r.get("ok"):
        return _err(r.get("error", "汲取失败"))
    _campaign_save()
    out = c.snapshot()
    out["draw"] = r
    return out


def m_campaign_heal(p):
    """战役层施放治疗言灵（绿 1 环，耗 1 点绿法力）。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    r = c.heal()
    if not r.get("ok"):
        return _err(r.get("error", "治疗失败"))
    _campaign_save()
    out = c.snapshot()
    out["heal"] = r
    return out


def m_campaign_apply(p):
    """把当前战斗的结果收回战役，并推进链（战斗随之结束）。"""
    sid = p.get("sid") or "default"
    c, err = _camp(sid)
    if err:
        return err
    e = _combat_load(sid)
    if not e:
        return _err(f"没有进行中的战斗（sid={sid}），先调 campaign.next")
    snap = e.snapshot()
    r = c.apply_result(snap)
    _combat_drop(sid)
    _campaign_save()
    out = c.snapshot()
    out["record"] = r.get("record")
    out["before"] = r.get("before")
    out["battleResult"] = {"status": snap.get("status"),
                           "round": snap.get("round")}
    return out


def m_campaign_end(p):
    """放弃/结束战役（存档移除）。"""
    sid = p.get("sid") or "default"
    c = _campaign_load(sid)
    if not c:
        return _err(f"没有进行中的战役（sid={sid}）")
    snap = c.snapshot()
    CAMPAIGNS.pop(sid, None)
    _combat_drop(sid)
    _campaign_save()
    return {"ok": True, "ended": True, "snapshot": snap}


METHODS = {
    "dataset.get": m_dataset_get,
    "selfcheck": m_selfcheck,
    "panel.new": m_panel_new,
    "panel.snapshot": m_panel_snapshot,
    "panel.kill": m_panel_kill,
    "panel.allocate": m_panel_allocate,
    "panel.breakthrough": m_panel_breakthrough,
    "panel.grayline": m_panel_grayline,
    "panel.structureTax": m_panel_structure_tax,
    "panel.volume": m_panel_volume,
    "panel.mana": m_panel_mana,
    "panel.ignite": m_panel_ignite,
    "panel.render": m_panel_render,
    "panel.reset": m_panel_reset,
    "codex.bestiary": m_codex_bestiary,
    "codex.tiers": m_codex_tiers,
    "codex.planes": m_codex_planes,
    "codex.rules": m_codex_rules,
    "codex.plot": m_codex_plot,
    "codex.costArc": m_codex_costarc,
    "codex.timeline": m_codex_timeline,
    "codex.characters": m_codex_characters,
    "codex.characterCards": m_codex_character_cards,
    "codex.terms": m_codex_terms,
    "scan.chapter": m_scan_chapter,
    "scan.file": m_scan_file,
    "trpg.toolbox": m_trpg_toolbox,
    "trpg.check": m_trpg_check,
    "trpg.rate": m_trpg_rate,
    "trpg.tier": m_trpg_tier,
    "trpg.matchup": m_trpg_matchup,
    "trpg.status": m_trpg_status,
    "trpg.burn": m_trpg_burn,
    "pc.profiles": m_pc_profiles,
    "pc.build": m_pc_build,
    "pc.maneuvers": m_pc_maneuvers,
    "pc.catalog": m_pc_catalog,
    "combat.catalog": m_combat_catalog,
    "combat.new": m_combat_new,
    "combat.state": m_combat_state,
    "combat.act": m_combat_act,
    "combat.enemies": m_combat_enemies,
    "combat.auto": m_combat_auto,
    "combat.end": m_combat_end,
    "combat.narrate": m_combat_narrate,
    "campaign.chains": m_campaign_chains,
    "campaign.new": m_campaign_new,
    "campaign.state": m_campaign_state,
    "campaign.next": m_campaign_next,
    "campaign.insert": m_campaign_insert,
    "campaign.rest": m_campaign_rest,
    "campaign.draw": m_campaign_draw,
    "campaign.heal": m_campaign_heal,
    "campaign.apply": m_campaign_apply,
    "campaign.end": m_campaign_end,
    "research.get": m_research_get,
}


# --------------------------------------------------------------------------
# JSON-RPC 循环
# --------------------------------------------------------------------------

def handle(req: dict) -> dict:
    rid = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}
    fn = METHODS.get(method)
    if not fn:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"未知方法: {method}"}}
    try:
        result = fn(params)
        # 业务结果可能自带 "error" 字段（如机扫的 error 是错误**计数** int），
        # 不能见 "error" 就当 RPC 错误响应包装——那会把整个结果吞掉。
        # 只有「带 code/message 的字典」才是真错误（_err 的产物）。
        if (isinstance(result, dict) and "jsonrpc" not in result
                and isinstance(result.get("error"), dict)
                and "code" in result["error"]):
            return {"jsonrpc": "2.0", "id": rid, "error": result["error"]}
        return {"jsonrpc": "2.0", "id": rid, "result": result}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32603,
                          "message": f"{type(e).__name__}: {e}",
                          "data": traceback.format_exc(limit=3)}}


def main() -> None:
    global DS, RESEARCH
    try:
        DS = PE.load_dataset()
    except Exception as e:
        print(json.dumps({"jsonrpc": "2.0", "id": None,
                          "error": {"code": -32000,
                                    "message": f"数据层加载失败: {e}"}}),
              flush=True)
        return

    rpath = HERE / "data" / "research.json"
    if rpath.exists():
        try:
            RESEARCH = json.loads(rpath.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] research.json 解析失败: {e}", file=sys.stderr)

    print(f"[rpc] 引擎就绪 · 数据层 {len(DS.get('plotThreads') or [])} 伏笔 / "
          f"{len(DS.get('rules') or [])} 规则", file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700,
                                        "message": f"JSON 解析失败: {e}"}}),
                  flush=True)
            continue
        if req.get("method") == "shutdown":
            print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"),
                              "result": {"ok": True}}), flush=True)
            break
        resp = handle(req)
        if req.get("id") is not None or "error" in resp:
            print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
