#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
panel_engine.py — 旅法师面板引擎（核心域逻辑）

职责
----
把 bible 里写成「条件 → 结果」的世界规则，落成可执行的判定：

  · 面板状态机（火种期 0-100% → 点燃 → 鹏洛克）
  · 火花累加与解锁阈值判定（§2f 解锁总表为唯一明细处）
  · 属性加点 / 软上限突破（25%/45% 规则）
  · 变异等级 → 火花产出映射（R2/R6 可判定）
  · 灰线格数单调递增断言（R11，越能扛越不像人）
  · 虚空耐受与黑色代偿档位按卷联动（§3.5 递增表）
  · 五色法力与结构税（R13）

零三方依赖。所有状态变更都返回 diff，便于 GUI 展示与写作留痕。
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).parent / "data" / "dataset.json"

# 加点软上限：初始 5，突破一次 +1，突破消耗翻倍
SOFT_CAP_BASE = 5
ATTR_ORDER = ["体质", "根骨", "灵敏", "精神", "悟性"]


def load_dataset(path: Path = DATA_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"数据层不存在: {path}\n请先运行: python bible_parser.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ==========================================================================
# 变异等级 → 火花产出（R2/R6）
# ==========================================================================

# 兜底谱系（解析失败时的保底值，来源 world-bible §7）
FALLBACK_TIERS = [
    {"tier": "零级", "name": "普通辐射生物", "criteria": "个体略大、无质变", "sparkRange": [0, 0], "sparkRaw": "0"},
    {"tier": "一级", "name": "变异体", "criteria": "体型/甲壳/行为质变", "sparkRange": [3, 5], "sparkRaw": "3-5%"},
    {"tier": "二级", "name": "深度异变", "criteria": "多器官异常、类策略行为", "sparkRange": [8, 15], "sparkRaw": "8-15%"},
    {"tier": "三级", "name": "异化兽 / 实验体", "criteria": "脱离原物种、可伤人", "sparkRange": [20, 50], "sparkRaw": "20-50%"},
    {"tier": "王级", "name": "异族之王", "criteria": "高智慧、统御同类", "sparkRange": [100, 100], "sparkRaw": "100%+"},
    {"tier": "坠影级(S+)", "name": "位面坠落残骸", "criteria": "携鹏洛克碎片知识", "sparkRange": [-1, -1], "sparkRaw": "面板判定为「？？？」"},
]


def get_tiers(ds: dict) -> list[dict]:
    tiers = (ds.get("creatures") or {}).get("tiers") or []
    return tiers if tiers else FALLBACK_TIERS


def normalize_tier(ds: dict, tier) -> str:
    """把任意形态的等级输入归一成数据层里的标准 tier 名。

    RPC 层的参数可能来自 HTTP 表单（字符串）、也可能直接传数字
    （curl / 脚本 / 前端 select 传 index）。引擎内部一律用
    `t['tier']` 原文做等值比较，若不归一会静默落到
    「面板未登记该等级」，或直接抛 'int' has no attribute 'replace'。
    """
    tiers = get_tiers(ds)
    if isinstance(tier, str):
        s = tier.strip()
        # 已精确命中
        for t in tiers:
            if t["tier"] == s:
                return s
        # 1-based 序号（"1" / "第1级" / "1."）
        m = re.search(r"\d+", s)
        if m:
            idx = int(m.group()) - 1
            if 0 <= idx < len(tiers):
                return tiers[idx]["tier"]
        return s
    if isinstance(tier, int):
        idx = tier - 1 if 0 <= tier - 1 < len(tiers) else tier
        if 0 <= idx < len(tiers):
            return tiers[idx]["tier"]
    return str(tier)


def spark_for_tier(ds: dict, tier: str, rng: random.Random | None = None) -> dict:
    """按变异等级取火花产出。坠影级返回不可击杀标记。"""
    r = rng or random
    tier = normalize_tier(ds, tier)
    for t in get_tiers(ds):
        if t["tier"].replace(" ", "") == tier.replace(" ", ""):
            lo, hi = t["sparkRange"]
            if lo < 0:
                return {"tier": t["tier"], "name": t["name"], "spark": 0,
                        "raw": t["sparkRaw"], "killable": False,
                        "verdict": "异族·坠影级（S+）",
                        "note": "面板判定为「？？？」——不可击杀取火花，只能「送终」"}
            val = r.randint(lo, hi) if hi > lo else lo
            return {"tier": t["tier"], "name": t["name"], "spark": val,
                    "raw": t["sparkRaw"], "killable": True,
                    "verdict": f"异族·{t['name']}（{t['tier']}）"}
    return {"tier": tier, "name": "未登记", "spark": 0, "raw": "—",
            "killable": False, "verdict": "面板未登记该等级", "note": "先回 world-bible §7 登记"}


# ==========================================================================
# 面板状态
# ==========================================================================

def new_state(ds: dict) -> dict:
    """新建面板状态：火种期 0%，全 4，初始天赋/技艺。"""
    p = ds.get("panel") or {}
    return {
        "spark": 0,
        "ignited": False,
        "igniteChapter": None,
        "attrs": {k: 4 for k in ATTR_ORDER},
        "attrPoints": 0,          # 待分配自由属性点
        "breakthroughs": 0,       # 已用突破次数
        "breakthroughCost": 1,    # 下次突破消耗（翻倍）
        "unlocked": [],
        "grayCells": 0,           # 灰线格数（单调递增）
        "volume": 1,              # 当前卷（1-5）
        "voidMin": 7,             # 虚空耐受上限（分钟）
        "blackMult": 1,           # 黑色代偿档位
        "manaPool": {"白": 0, "蓝": 0, "黑": 0, "红": 0, "绿": 0},
        "taxCells": 0,            # 结构税累计格
        "planeCoords": 0,
        "log": [],
    }


def unlock_thresholds(ds: dict) -> list[dict]:
    """火花阈值型解锁（spark 为 int）。点燃后追加项 spark=null，不在此列。"""
    u = (ds.get("panel") or {}).get("unlocks") or []
    return sorted(
        [x for x in u if isinstance(x.get("spark"), int) and 0 <= x["spark"] <= 100],
        key=lambda x: x["spark"],
    )


def post_ignite_unlocks(ds: dict) -> list[dict]:
    """点燃后追加解锁（法力池点亮 / 乙太感知 / 代偿升级 / 耐受跃迁 …）。"""
    u = (ds.get("panel") or {}).get("unlocks") or []
    return [x for x in u if x.get("spark") is None]


def pending_unlocks(ds: dict, st: dict) -> list[dict]:
    """返回已达成阈值但尚未记录解锁的功能。"""
    got = set(st["unlocked"])
    out = []
    for u in unlock_thresholds(ds):
        if st["spark"] >= u["spark"] and u["name"] not in got:
            out.append(u)
    return out


# ==========================================================================
# 核心操作（全部返回 diff）
# ==========================================================================

def op_kill(ds: dict, st: dict, tier: str, count: int = 1, rng: random.Random | None = None) -> dict:
    """击杀异族 → 火花累加 → 解锁判定。返回 diff。"""
    before_spark = st["spark"]
    gained = 0
    verdicts: list[str] = []
    blocked = False

    if st["ignited"]:
        blocked = True   # R8：火花点燃后不再增长

    for _ in range(max(1, count)):
        info = spark_for_tier(ds, tier, rng)
        verdicts.append(info["verdict"])
        if not info["killable"]:
            continue
        gained += info["spark"]

    if not blocked and gained > 0:
        st["spark"] = min(100, st["spark"] + gained)

    new_ul = [] if blocked else pending_unlocks(ds, st)
    for u in new_ul:
        st["unlocked"].append(u["name"])

    # 加点入账：每满 10% 得 1 点（25% 解锁后生效）
    points = 0
    if "属性加点" in st["unlocked"]:
        points = st["spark"] // 10 - st.get("_pointsGranted", 0)
        if points > 0:
            st["attrPoints"] += points
            st["_pointsGranted"] = st["spark"] // 10

    # 100% 自动点燃
    ignited_now = False
    if st["spark"] >= 100 and not st["ignited"]:
        st["ignited"] = True
        st["igniteChapter"] = 37
        for name in ("点燃（鹏洛克·新晋）+ 位面坐标感知 + 代偿 + 法力池（空）",):
            if name not in st["unlocked"]:
                st["unlocked"].append(name)
        st["planeCoords"] = max(st["planeCoords"], 1)
        ignited_now = True

    diff = {
        "op": "kill",
        "tier": tier,
        "count": count,
        "verdicts": verdicts,
        "sparkBefore": before_spark,
        "sparkAfter": st["spark"],
        "gained": st["spark"] - before_spark,
        "blockedByIgnite": blocked,
        "newUnlocks": [u["name"] for u in new_ul],
        "attrPointsGained": points,
        "ignitedNow": ignited_now,
    }
    st["log"].append(diff)
    return diff


def op_allocate(ds: dict, st: dict, attr: str, count: int = 1) -> dict:
    """分配自由属性点。"""
    if attr not in ATTR_ORDER:
        return {"op": "allocate", "ok": False, "error": f"未知属性: {attr}"}
    if count > st["attrPoints"]:
        return {"op": "allocate", "ok": False,
                "error": f"自由属性点不足：剩 {st['attrPoints']}，需 {count}"}

    cap = SOFT_CAP_BASE + st["breakthroughs"]
    if st["attrs"][attr] >= cap and "属性突破" not in st["unlocked"]:
        return {"op": "allocate", "ok": False,
                "error": f"{attr} 已达软上限 {cap}，需先使用「属性突破」（45% 解锁）"}

    before = st["attrs"][attr]
    st["attrs"][attr] += count
    st["attrPoints"] -= count
    return {"op": "allocate", "ok": True, "attr": attr, "count": count,
            "before": before, "after": st["attrs"][attr],
            "attrPointsLeft": st["attrPoints"]}


def op_breakthrough(ds: dict, st: dict, attr: str) -> dict:
    """突破软上限 1 点，消耗翻倍。"""
    if "属性突破" not in st["unlocked"]:
        return {"op": "breakthrough", "ok": False, "error": "「属性突破」未解锁（需火花 45%）"}
    if st["attrPoints"] < st["breakthroughCost"]:
        return {"op": "breakthrough", "ok": False,
                "error": f"自由属性点不足：突破需 {st['breakthroughCost']} 点，剩 {st['attrPoints']}"}
    if attr not in ATTR_ORDER:
        return {"op": "breakthrough", "ok": False, "error": f"未知属性: {attr}"}

    st["attrPoints"] -= st["breakthroughCost"]
    before = st["attrs"][attr]
    st["attrs"][attr] += 1
    cost_used = st["breakthroughCost"]
    st["breakthroughCost"] *= 2      # 后续突破消耗翻倍
    st["breakthroughs"] += 1
    return {"op": "breakthrough", "ok": True, "attr": attr,
            "before": before, "after": st["attrs"][attr],
            "costPaid": cost_used, "nextCost": st["breakthroughCost"],
            "softCapNow": SOFT_CAP_BASE + st["breakthroughs"]}


def op_grayline(ds: dict, st: dict, cells: int, reason: str = "") -> dict:
    """灰线扩张。R11：格数单调递增不回退。"""
    prev = st["grayCells"]
    if cells < prev:
        return {"op": "grayline", "ok": False,
                "error": f"违 R11／灰线单调递增：当前 {prev} 格，不能回退到 {cells} 格"}
    st["grayCells"] = cells
    return {"op": "grayline", "ok": True, "before": prev, "after": cells,
            "delta": cells - prev, "reason": reason,
            "note": "越能扛越不像人（R11）"}


def op_structure_tax(ds: dict, st: dict, cells: int = 1) -> dict:
    """R13：五色法力组合额外消耗结构税，灰线加深。"""
    st["taxCells"] += cells
    prev = st["grayCells"]
    st["grayCells"] = prev + cells
    return {"op": "structureTax", "ok": True, "taxCells": st["taxCells"],
            "grayBefore": prev, "grayAfter": st["grayCells"],
            "note": "组合越复杂，灰线增长越快（R13）"}


def op_volume_progress(ds: dict, st: dict, volume: int) -> dict:
    """卷间跃迁：按 §3.5 递增表同步虚空耐受与黑色代偿档位。"""
    table = ((ds.get("planes") or {}).get("toleranceTable")) or []
    row = next((r for r in table if re.search(rf"第?\s*{volume}\s*卷", r.get("volume", ""))), None)
    if not row:
        return {"op": "volumeProgress", "ok": False, "error": f"递增表里没有第 {volume} 卷"}
    prev = {"voidMin": st["voidMin"], "blackMult": st["blackMult"], "volume": st["volume"]}
    st["volume"] = volume
    st["voidMin"] = row["voidMin"]
    st["blackMult"] = row["blackMult"]
    return {"op": "volumeProgress", "ok": True, "before": prev,
            "after": {"voidMin": st["voidMin"], "blackMult": st["blackMult"], "volume": volume},
            "source": row["volume"]}


def op_mana(ds: dict, st: dict, color: str, amount: int) -> dict:
    """法力池存取。五色：白蓝黑红绿。"""
    if color not in st["manaPool"]:
        return {"op": "mana", "ok": False, "error": f"未知法力色: {color}"}
    st["manaPool"][color] += amount
    return {"op": "mana", "ok": True, "color": color, "amount": amount,
            "pool": dict(st["manaPool"])}


def op_ignite(ds: dict, st: dict) -> dict:
    """手动点燃（正常应由火花到 100% 自动触发）。"""
    if st["ignited"]:
        return {"op": "ignite", "ok": False, "error": "已点燃，不可重复"}
    if st["spark"] < 100:
        return {"op": "ignite", "ok": False, "error": f"火花仅 {st['spark']}%，需 100%"}
    st["ignited"] = True
    return {"op": "ignite", "ok": True,
            "note": "火花封顶，力量增长改走「汲取多位面法力」（R8）"}


# ==========================================================================
# 快照 / 渲染
# ==========================================================================

def snapshot(ds: dict, st: dict) -> dict:
    """给 GUI 的完整面板快照。"""
    p = ds.get("panel") or {}
    tiers = get_tiers(ds)
    cap = SOFT_CAP_BASE + st["breakthroughs"]
    return {
        "level": "鹏洛克·位面行走者" if st["ignited"] else "火种期",
        "ignited": st["ignited"],
        "igniteChapter": st["igniteChapter"],
        "spark": st["spark"],
        "sparkState": "已点燃·不再增长" if st["ignited"] else f"火种期 {st['spark']}%",
        "attrs": dict(st["attrs"]),
        "softCap": cap,
        "attrPoints": st["attrPoints"],
        "breakthroughs": st["breakthroughs"],
        "nextBreakthroughCost": st["breakthroughCost"],
        "unlocked": list(st["unlocked"]),
        "nextUnlocks": [
            {"spark": u["spark"], "name": u["name"], "effect": u["effect"], "chapter": u["chapter"]}
            for u in unlock_thresholds(ds) if u["spark"] > st["spark"] and not st["ignited"]
        ][:4],
        "talent": p.get("talent", "铁骨"),
        "grayCells": st["grayCells"],
        "taxCells": st["taxCells"],
        "voidMin": st["voidMin"],
        "blackMult": st["blackMult"],
        "volume": st["volume"],
        "manaPool": dict(st["manaPool"]),
        "planeCoords": st["planeCoords"],
        "tiers": tiers,
        "recentLog": st["log"][-8:][::-1],
    }


def render_panel_text(ds: dict, st: dict) -> str:
    """生成可直接粘进正文的面板文本（逐字符合 §2f 风格）。"""
    s = snapshot(ds, st)
    lines = [f"【{s['level']}】"]
    for k in ATTR_ORDER:
        lines.append(f"{k}：{s['attrs'][k]}")
    lines.append(f"火花：{s['sparkState']}")
    if s["ignited"]:
        lines.append(f"法力池：{_mana_text(s['manaPool'])}")
        lines.append(f"虚空耐受：{s['voidMin']}分钟")
        lines.append(f"代偿：黑×{s['blackMult']}")
    if s["grayCells"]:
        lines.append(f"灰线：{s['grayCells']}格")
    return "\n".join(lines)


def _mana_text(pool: dict) -> str:
    on = [f"{c}×{n}" for c, n in pool.items() if n > 0]
    return "·".join(on) if on else "空"


# ==========================================================================
# 自检
# ==========================================================================

def selfcheck(ds: dict) -> dict:
    """对数据层做完整性体检，GUI 启动时展示。"""
    issues: list[dict] = []
    q = (ds.get("meta") or {}).get("quality") or {}
    if q.get("failed"):
        issues.append({"level": "error", "msg": f"解析阶段有 {q['failed']} 项失败，机扫可能漏规则"})

    panel = ds.get("panel") or {}
    ul = panel.get("unlocks") or []
    thr = [u for u in ul if isinstance(u.get("spark"), int) and 0 <= u["spark"] <= 100]
    if not ul:
        issues.append({"level": "error", "msg": "解锁总表为空"})
    sparks = [u["spark"] for u in thr]
    if sparks != sorted(sparks):
        issues.append({"level": "warn", "msg": "解锁总表未按火花阈值排序"})
    for need in (4, 20, 25, 45, 50, 54, 58, 100):
        if need not in sparks:
            issues.append({"level": "warn", "msg": f"解锁总表缺 {need}% 阈值（§2f 要求）"})

    tiers = get_tiers(ds)
    if not tiers:
        issues.append({"level": "error", "msg": "变异等级谱系为空"})
    else:
        names = [t["tier"] for t in tiers]
        for need in ("零级", "一级", "二级", "三级", "王级"):
            if need not in names:
                issues.append({"level": "warn", "msg": f"谱系缺「{need}」"})

    rules = ds.get("rules") or []
    rids = {r["id"] for r in rules}
    for i in range(1, 16):
        if f"R{i}" not in rids:
            issues.append({"level": "warn", "msg": f"世界规则缺 R{i}"})

    plot = ds.get("plotThreads") or []
    if len(plot) < 20:
        issues.append({"level": "warn", "msg": f"伏笔台账仅 {len(plot)} 条，疑似解析不全"})

    # 活跃线红线：「同时活跃悬念线 ≤ 4」。
    # 注：plot-board 的「推进中」是**全书记账状态**，含跨五卷的长弧
    # （F12 位面污染、情感E1 等），这些不属于「同一时间窗内读者要同时牵挂」的悬念线。
    # 故这里只统计**近期有落点章**的推进中线索，其余归为长弧，单列不报警。
    active = [p for p in plot if p["status"] == "推进中"]
    recent, longarc = [], []
    for p in active:
        chs = [int(c) for c in re.findall(r"第\s*(\d+)\s*章", p.get("statusRaw", ""))]
        chs = [c for c in chs if 91 <= c <= 140]      # 第三卷章段
        (recent if chs else longarc).append(p)
    if len(recent) > 4:
        issues.append({
            "level": "warn",
            "msg": f"第三卷章段内有落点的推进中线索 {len(recent)} 条，超出红线「同时活跃悬念线 ≤ 4」："
                   + "、".join(p["id"] for p in recent),
        })
    if longarc:
        issues.append({
            "level": "info",
            "msg": f"另有 {len(longarc)} 条跨卷长弧处于推进中（不计入同时活跃红线）："
                   + "、".join(p["id"] for p in longarc),
        })
    orphan = [p["id"] for p in plot if p["status"] in ("推进中", "待回收") and not p.get("plantedAt")]
    if orphan:
        issues.append({"level": "info", "msg": f"{len(orphan)} 条待回收伏笔未记录埋设位置: {'、'.join(orphan[:6])}"})

    burned = (ds.get("costArc") or {}).get("burned") or []
    dims = (ds.get("costArc") or {}).get("dimensions") or []
    if dims and len(burned) < 2:
        issues.append({"level": "warn", "msg": "已烧清单条目过少，代价弧台账可能未同步"})

    return {
        "issues": issues,
        "counts": {
            "unlocks": len(ul),
            "unlockThresholds": len(thr),
            "postIgniteUnlocks": len(post_ignite_unlocks(ds)),
            "tiers": len(tiers),
            "bestiary": len((ds.get("creatures") or {}).get("bestiary") or []),
            "rules": len(rules),
            "leakLines": len(ds.get("leakLines") or []),
            "plotThreads": len(plot),
            "timeline": len(ds.get("timeline") or []),
            "characters": len(ds.get("characters") or []),
            "characterCards": len(ds.get("characterCards") or []),
            "cardDisciplineRules": sum(
    int(c.get("disciplineCount") or 0) for c in (ds.get("characterCards") or [])
      ),
            "terms": len(ds.get("terminology") or []),
            "planes": len((ds.get("planes") or {}).get("layers") or []),
        },
        "generatedAt": (ds.get("meta") or {}).get("generatedAt"),
        "sourceRoot": (ds.get("meta") or {}).get("sourceRoot"),
    }


if __name__ == "__main__":
    d = load_dataset()
    st = new_state(d)
    op_kill(d, st, "一级", 8)
    print(render_panel_text(d, st))
    print()
    for i in selfcheck(d)["issues"]:
        print(f"  [{i['level']}] {i['msg']}")
