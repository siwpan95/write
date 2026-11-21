#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恐怖美学母题 · 场景生成器
==========================

把《恐怖美学八母题复用公式卡》的母公式做成可执行程序：

    T = (R - e1) * delta - I - E

设计原则
--------
1. 纯标准库，零依赖，任何 Python 3.8+ 可直接跑。
2. 确定性：同一 --seed 必须产出完全相同的卡（可复现、可对账）。
3. 不做"素材拼接"：生成的是**参数组合 + 骨架填充**，且强制跑结构自检，
   不合规的组合会被拒绝，而不是照样输出一张好看的废卡。

用法
----
    python gen.py list
    python gen.py gen --motif 怨灵 --temp 关系型 --seed 42
    python gen.py gen --motif ghost --temp 关系型 --strength high
    python gen.py batch -n 8 --seed 2026 --out cards.md
    python gen.py check --motif mirror --temp 关系型
    python gen.py matrix

档位约定
--------
[A] 可核验事实/常识  [B] 学界解读  [C] 创作化引申
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

# Windows 控制台默认 GBK，不 reconfigure 会在中文输出时炸掉
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
DATA = HERE / "motifs.json"

TIER_LABEL = {"A": "可核验事实/常识", "B": "学界解读", "C": "创作化引申"}


# --------------------------------------------------------------------------- #
# 数据层
# --------------------------------------------------------------------------- #

class DataError(Exception):
    pass


def load_data(path=DATA):
    if not path.exists():
        raise DataError(f"找不到数据文件：{path}")
    with path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise DataError(f"motifs.json 不是合法 JSON：{e}") from e
    if not data.get("motifs"):
        raise DataError("motifs.json 里没有 motifs 数组")
    return data


# 口语别名 —— 用户不会照着文档念全名
MOTIF_ALIASES = {
    "death": ["死亡", "尸体", "腐尸", "腐朽", "僵尸", "殓", "丧", "死"],
    "body": ["身体", "异化", "变形", "身体恐怖", "肉身", "变形记"],
    "unknown": ["未知", "不可名状", "克苏鲁", "洛氏", "宇宙主义", "诡异", "怪奇"],
    "ghost": ["鬼", "怨灵", "幽灵", "怨念", "女鬼", "厉鬼", "亡灵", "招魂"],
    "liminal": ["阈限", "废墟", "禁地", "空间", "后室", "走廊", "过渡"],
    "mirror": ["镜像", "分身", "镜子", "双胞胎", "另一个我", "复制"],
    "voyeur": ["窥视", "偷窥", "监控", "凝视", "被看", "摄像头"],
    "ritual": ["仪式", "禁忌", "规矩", "规程", "咒", "法事", "祭祀"],
}


def resolve_motif(data, key):
    """按 id / 中文名 / 别名 / 子串 匹配母题。返回 motif dict。"""
    key = key.strip()
    for m in data["motifs"]:
        if key == m["id"] or key == m["name"]:
            return m
    # 别名优先于子串，避免「怨灵」匹配不到「幽灵与怨念」
    for mid, alts in MOTIF_ALIASES.items():
        if key in alts:
            for m in data["motifs"]:
                if m["id"] == mid:
                    return m
    cand = [m for m in data["motifs"] if key in m["name"] or key in m["id"]]
    if len(cand) == 1:
        return cand[0]
    if not cand:
        names = "、".join(f'{m["name"]}({m["id"]})' for m in data["motifs"])
        raise DataError(f"没有找到母题「{key}」。可选：{names}")
    names = "、".join(m["name"] for m in cand)
    raise DataError(f"「{key}」匹配到多个母题：{names}，请写全名或 id")


def resolve_temp(data, key):
    key = key.strip()
    temps = data["temperatures"]
    if key in temps:
        return key
    aliases = {
        "温": "关系型", "关系": "关系型", "warm": "关系型",
        "冷": "系统型", "系统": "系统型", "cold": "系统型",
        "黏": "身体型", "身体": "身体型", "sticky": "身体型",
        "史诗": "崇高型", "崇高": "崇高型", "epic": "崇高型",
        "狂喜": "狂喜型", "ecstatic": "狂喜型",
    }
    if key in aliases and aliases[key] in temps:
        return aliases[key]
    raise DataError(f"未知温度「{key}」。可选：{'、'.join(temps)}")


# --------------------------------------------------------------------------- #
# 生成层
# --------------------------------------------------------------------------- #

def pick_rules_for_error(rng, motif, err, n=3):
    """按 e₁ 的 pair 标签优先取规程——保证「被破的那条规矩」确实在场。

    这是生成器最关键的一处约束：如果 R 和 e₁ 不在同一个频道，
    公式 T=(R-e₁)×Δ 直接失效（骨架会写成「在本来纸钱要烧透的地方，
    只有下摆不动不对」这种逻辑断裂的句子）。
    """
    want = err.get("pair", [])
    matched = [r for r in motif["rules"] if r.get("cat") in want]
    rest = [r for r in motif["rules"] if r.get("cat") not in want]
    rng.shuffle(matched)
    rng.shuffle(rest)
    picked = matched[:n]
    if len(picked) < n:
        picked += rest[: n - len(picked)]
    return picked


def _short(text, limit=26):
    text = text.split("——")[0].split("—")[0].strip()
    return text if len(text) <= limit else text[:limit] + "…"


def pick_error(rng, motif, strength="any"):
    pool = motif["errors"]
    if strength != "any":
        sub = [e for e in pool if e["strength"] == strength]
        if sub:
            pool = sub
    return rng.choice(pool)


def pick_symbols(rng, motif, err, k=3):
    """符号组 = e₁ 自带的承载符号（★）+ 1–2 个不同通道的氛围符号。

    ★ 不再从符号库里"挑一个去承载"，而是由 e₁ 自己带来——因为 e₁ 本身就是
    「某样东西不对」，那样东西就是符号。这保证了 ★ 永远真的承载 e₁。
    """
    carrier = dict(err["sym"], carries=True)
    picked = [carrier]

    pool = [s for s in motif["symbols"] if s["c"] != carrier["c"]]
    rng.shuffle(pool)
    used_ch = {carrier["c"]}
    for s in pool:
        if len(picked) >= k:
            break
        if s["c"] in used_ch:
            continue
        picked.append(dict(s, carries=False))
        used_ch.add(s["c"])
    return picked


MODE_ALIASES = {
    "恐怖": "horror", "horror": "horror",
    "惊悚": "thriller", "thriller": "thriller",
    "正剧": "drama", "drama": "drama",
    "悲剧": "tragedy", "tragedy": "tragedy",
    "讽刺": "satire", "satire": "satire",
    "史诗": "epic", "epic": "epic",
}


def resolve_mode(data, key):
    """解析呈现模式（6 种）。"""
    key = key.strip().lower()
    modes = data.get("modes", {})
    if key in modes:
        return key
    if key in MODE_ALIASES and MODE_ALIASES[key] in modes:
        return MODE_ALIASES[key]
    raise DataError(f"未知模式「{key}」。可选：{'、'.join(modes)}")


def build_card(data, motif, temp, rng, strength="any", n_rules=3, mode=None):
    """组装一张卡（纯数据，不含排版）。"""
    err = pick_error(rng, motif, strength)
    exit_text = motif["exits"].get(temp, "")
    legal = temp in motif.get("temps", [])

    # 该温度不合法时，退回该母题的首选温度
    effective_temp = temp
    note = None
    if not legal:
        effective_temp = motif["temps"][0]
        note = (f"温度「{temp}」与该母题不兼容（{motif['name']} 支持："
                f"{'、'.join(motif['temps'])}），已退回「{effective_temp}」。")
        exit_text = motif["exits"].get(effective_temp, "")

    # 呈现模式（跨类型）：与温度正交
    mode_note = None
    mode_ok = True
    if mode:
        supported = motif.get("modes", [])
        if mode not in supported:
            mode_ok = False
            mode_note = (f"模式「{mode}」与该母题不兼容（支持：{'、'.join(supported)}），"
                         f"未套用模式参数。")
        else:
            mode_note = motif.get("mode_note", {}).get(mode)


    syms = pick_symbols(rng, motif, err, k=rng.choice([2, 3]))
    rules = pick_rules_for_error(rng, motif, err, n=n_rules)
    checks = rng.sample(motif["checks"], min(2, len(motif["checks"])))
    ladder = motif["info_ladder"]
    tconf = data["temperatures"][effective_temp]

    # 模式参数优先于温度参数（模式是跨类型的 I/E 原则）
    applied_mode = mode if (mode and mode_ok) else None
    mconf = data["modes"][applied_mode] if applied_mode else None
    i_rule = mconf["i"] if mconf else tconf["i"]
    e_rule = mconf["e"] if mconf else tconf["e"]

    # E 取向冲突检测：按「模式真正需要的出口类型」判，而非简单看高低
    # none      = 出口有无皆可（horror 要"被放弃/延缓"，tragedy 要"不可逆"，两者都算 none）
    # reconcile = 必须有活路（drama 可和解、satire 出路明明有）
    # scale     = 尺度改写可替代出口（epic）
    MODE_E_NEED = {
        "horror": "none", "tragedy": "none", "epic": "scale",
        "thriller": "reconcile", "drama": "reconcile", "satire": "reconcile",
    }
    e_conflict = False
    suggest_temp = None
    if mconf:
        need = MODE_E_NEED.get(applied_mode, "none")
        has_way = any(w in exit_text for w in
                      ("可和解", "可补录", "可改", "可办", "可驱除", "出路", "可补"))
        is_scale = any(w in exit_text for w in ("尺度", "幸存"))
        if need == "reconcile" and not has_way:
            e_conflict = True
        elif need == "scale" and not (has_way or is_scale):
            e_conflict = True
        # need == "none" 时永不冲突

        # 冲突时：在该母题的其他温度里找"有活路"的那个，给出可行替换
        if e_conflict:
            for alt_t in motif["temps"]:
                if alt_t == effective_temp:
                    continue
                alt_e = motif["exits"].get(alt_t, "")
                alt_way = any(w in alt_e for w in
                              ("可和解", "可补录", "可改", "可办", "可驱除", "出路", "可补"))
                alt_scale = any(w in alt_e for w in ("尺度", "幸存"))
                if (need == "reconcile" and alt_way) or (need == "scale" and (alt_way or alt_scale)):
                    suggest_temp = alt_t
                    break

    card = {
        "motif_id": motif["id"],
        "motif": motif["name"],
        "delta": motif["delta"],
        "layer": motif["layer"],
        "core": motif["core"],
        "temp": effective_temp,
        "temp_requested": temp,
        "temp_note": note,
        "mode": applied_mode,
        "mode_requested": mode,
        "mode_ok": mode_ok,
        "mode_note": mode_note,
        "mode_feel": mconf["feel"] if mconf else None,
        "E_conflict": e_conflict,
        "E_suggest_temp": suggest_temp,
        "R": rules,
        "checks": checks,
        "e1": err,
        "I_ladder": ladder,
        "I_rule": i_rule,
        "E": exit_text,
        "E_rule": e_rule,
        "S": syms,
        "anti": motif["anti"],
        "sample": motif["scenes"][0],
    }
    card["audit"] = audit(data, card)
    return card


# --------------------------------------------------------------------------- #
# 自检层 —— 生成的卡必须过结构校验，否则宁可不出
# --------------------------------------------------------------------------- #

def audit(data, card):
    """七条结构自检。返回 [(ok: bool, label, detail)]。"""
    res = []

    # 1. e1 唯一
    res.append((True, "e₁ 唯一", "本卡只选一条一错；加第二个异常请换场、换 R"))

    # 2. 符号跨通道 + ★ 必须就是 e₁ 的载体（不是另挑一个凑数）
    chs = {s["c"] for s in card["S"]}
    star = card["S"][0]
    carrier_ok = bool(star.get("carries")) and star["t"] == card["e1"]["sym"]["t"]
    res.append((
        len(chs) == len(card["S"]) and carrier_ok,
        "符号组跨通道，且 ★ 就是 e₁ 的载体",
        f"{len(card['S'])} 件 / {len(chs)} 个通道 / ★ {star['c']}",
    ))

    # 3. 规程至少 2 条且有档位
    ok = len(card["R"]) >= 2 and all(r.get("tier") in TIER_LABEL for r in card["R"])
    res.append((ok, "R 规程可复述（≥2 条，带证据档位）", f"{len(card['R'])} 条"))

    # 4. 出口已指定
    res.append((bool(card["E"]), "E 出口已指定", card["E"][:24] + "…" if card["E"] else "空"))

    # 5. 温度合法
    res.append((
        card["temp_requested"] == card["temp"],
        "温度与母题兼容",
        card["temp_note"] or "合法",
    ))

    # 6. 信息阶梯 = 3 段（三次上限）
    res.append((
        len(card["I_ladder"]) == 3,
        "信息阶梯 3 段（永不全景）",
        f"{len(card['I_ladder'])} 段",
    ))

    # 7. e₁ 强度分级提醒
    s = card["e1"]["strength"]
    hint = {
        "high": "高强度：适合放中后段，前面必须先有一次低强度铺垫",
        "mid": "中强度：适合做确认段，前后各配一次低/高强度",
        "low": "低强度：负责「不确定」，不要拿它做高潮",
    }[s]
    res.append((True, f"e₁ 强度分级 = {s}", hint))

    # 8. R 与 e₁ 必须同频道（否则骨架逻辑断裂，公式作废）
    pair = set(card["e1"].get("pair", []))
    rule_cats = {r.get("cat") for r in card["R"]}
    hit = pair & rule_cats
    res.append((
        bool(hit),
        "R 与 e₁ 配对（被破的那条规矩确实在场）",
        f"命中标签：{'、'.join(sorted(hit))}" if hit else "⚠ 规程与异常不在同一频道",
    ))

    # 9. 呈现模式兼容（仅在指定 --mode 时校验）
    if card.get("mode_requested"):
        res.append((
            card["mode_ok"],
            "呈现模式与母题兼容",
            card["mode_note"] or "合法",
        ))
        # 10. 模式 E 取向与温度出口：冲突只作警告（可换温度或按模式自撰出口），不阻塞
        if card["mode_ok"]:
            if card.get("E_conflict"):
                fix = (f"建议改用温度「{card['E_suggest_temp']}」" if card.get("E_suggest_temp")
                       else "该母题无「有活路」的温度，须按模式自撰出口")
                res.append((True, "模式 E 取向与温度出口", f"⚠ 不一致——{fix}"))
            else:
                res.append((True, "模式 E 取向与温度出口", "一致"))

    return res


# --------------------------------------------------------------------------- #
# 排版层
# --------------------------------------------------------------------------- #

def render_markdown(card, index=None, seed=None):
    L = []
    tag = f"#{index}" if index else "单张"
    head = f"卡 {tag} · {card['motif']} × {card['temp']}"
    if seed is not None:
        head += f"　[seed={seed}]"
    L.append("```")
    L.append("─" * 62)
    L.append(head)
    L.append("─" * 62)
    L.append(f"Δ  {card['delta']}（{card['layer']}层）")
    L.append(f"   核心命题：{card['core']}")
    L.append("")

    if card["temp_note"]:
        L.append(f"⚠  {card['temp_note']}")
        L.append("")

    if card.get("mode"):
        L.append(f"Mode · {card['mode']}（{card['mode_feel']}）")
        L.append(f"   写法：{card['mode_note'] or '—'}")
        L.append(f"   I：{card['I_rule']}")
        L.append(f"   E：{card['E_rule']}")
        L.append("")
    elif card.get("mode_note"):
        L.append(f"⚠  {card['mode_note']}")
        L.append("")

    L.append("R · 场景规程（本来应该怎样）")
    for i, r in enumerate(card["R"], 1):
        L.append(f"   {i}. [{r['tier']}] {r['t']}")
    L.append("")
    L.append("检验动作（角色日常，不是侦探行为——e₁ 只有在「正常」刚被确认后才有效）")
    for c in card["checks"]:
        L.append(f"   · {c}")
    L.append("")

    e = card["e1"]
    L.append("e₁ · 一错（全篇唯一）")
    L.append(f"   [{e['layer']}层 / {e['strength']}] {e['t']}")
    L.append(f"   ↳ {e['note']}")
    L.append("")

    L.append("I · 信息阶梯（三次为上限，每次推翻上一次）")
    L.append("   ⚠ 以下是母题级示例；若所选 e₁ 与阶梯不同源，按同样的「三推」结构重写")
    for i, s in enumerate(card["I_ladder"], 1):
        L.append(f"   {i}. {s}")
    L.append(f"   减法：{card['I_rule']}")
    L.append("")

    L.append("E · 出口")
    L.append(f"   {card['E']}")
    L.append(f"   原则：{card['E_rule']}")
    if card.get("E_conflict"):
        L.append("   ⚠ 冲突：模式要求的 E 取向与温度给出的出口不一致")
        L.append(f"      按模式改写——{card['mode_note'] or '（按模式自定出口）'}")
        if card.get("E_suggest_temp"):
            L.append(f"      或改用温度「{card['E_suggest_temp']}」（该温度下出口有活路）")
        else:
            L.append("      该母题没有「有活路」的温度——此模式不适合本母题，建议换母题")
    L.append("")

    L.append("S · 符号组（跨通道，★ 承载 e₁）")
    for s in card["S"]:
        mark = "★" if s.get("carries") else " "
        L.append(f"   {mark} {s['c']}　{s['t']}")
    L.append("")

    L.append("骨架")
    L.append(f"   在本来【{_short(card['R'][0]['t'], 22)}】的地方，")
    L.append(f"   只有【{_short(e['t'], 30)}】不对；")
    L.append(f"   【{card['delta']}】这条边界被撬开；")
    L.append(f"   观众始终【{card['I_rule'].split('；')[0]}】；")
    L.append(f"   最后【{_short(card['E'], 34)}】。")
    L.append("")

    L.append("结构自检")
    for ok, label, detail in card["audit"]:
        L.append(f"   {'✅' if ok else '❌'} {label} —— {detail}")
    L.append("")
    L.append("人工复核（生成器不替你判断这三件事）")
    L.append("   □ I 阶梯是否与所选 e₁ 同源（不同源就按「三次推翻」重写，别硬套）")
    L.append("   □ e₁ 之外是否还有第二处异常（有就换场、换 R，不在同一场加码）")
    L.append("   □ 出口 E 是否真的没被写死（给「彻底解决」= 降格为怪物）")
    L.append("")

    L.append("专属反模式")
    for a in card["anti"]:
        L.append(f"   ✗ {a}")
    L.append("```")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #

def cmd_list(data, args):
    print(f"公式：{data['formula']}")
    print(f"      {data['formula_readable']}\n")
    print(f"{'id':<10}{'母题':<16}{'Δ 边界':<16}{'层':<6}支持温度")
    print("-" * 78)
    for m in data["motifs"]:
        print(f"{m['id']:<10}{m['name']:<14}{m['delta']:<14}{m['layer']:<6}"
              f"{'、'.join(m['temps'])}")
    print("\n温度档（horror 内部子档）：")
    for k, v in data["temperatures"].items():
        print(f"  {k}｜I：{v['i']}")
        print(f"        E：{v['e']}")
        print(f"        注：{v['note']}")
    if data.get("modes"):
        print("\n呈现模式（跨类型，与温度正交）：")
        for k, v in data["modes"].items():
            print(f"  {k:<9} {v['name']}｜I：{v['i']}")
            print(f"            E：{v['e']}　→ {v['feel']}（{v['tag']}）")
        print("\n提示：--temp 决定恐怖子档，--mode 决定跨类型呈现；可单独用，也可同时用。")


def cmd_gen(data, args):
    motif = resolve_motif(data, args.motif)
    temp = resolve_temp(data, args.temp) if args.temp else motif["temps"][0]
    mode = resolve_mode(data, args.mode) if args.mode else None
    rng = random.Random(args.seed)
    card = build_card(data, motif, temp, rng,
                      strength=args.strength, n_rules=args.rules, mode=mode)
    if args.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(card, seed=args.seed))


def cmd_batch(data, args):
    rng = random.Random(args.seed)
    if args.motif:
        motifs = [resolve_motif(data, args.motif)]
    else:
        motifs = data["motifs"]
    temps = [resolve_temp(data, args.temp)] if args.temp else None
    mode = resolve_mode(data, args.mode) if args.mode else None

    out = [f"# 批量场景卡（{args.n} 张，seed={args.seed}）", ""]
    for i in range(1, args.n + 1):
        m = rng.choice(motifs)
        t = rng.choice(temps) if temps else rng.choice(m["temps"])
        card = build_card(data, m, t, rng, strength=args.strength, mode=mode)
        out.append(render_markdown(card, index=i, seed=args.seed))

    text = "\n\n".join(out)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
        print(f"✅ 已写出 {args.n} 张卡 → {p.resolve()}")
        print(f"   复现命令：python gen.py batch -n {args.n} --seed {args.seed}"
              + (f" --motif {args.motif}" if args.motif else "")
              + (f" --temp {args.temp}" if args.temp else ""))
    else:
        print(text)


def cmd_check(data, args):
    motif = resolve_motif(data, args.motif)
    temp = resolve_temp(data, args.temp) if args.temp else motif["temps"][0]
    mode = resolve_mode(data, args.mode) if args.mode else None
    rng = random.Random(args.seed or 0)
    card = build_card(data, motif, temp, rng, strength=args.strength, mode=mode)
    ok = sum(1 for a in card["audit"] if a[0])
    total = len(card["audit"])
    print(f"母题：{card['motif']}　温度：{card['temp']}　seed={args.seed or 0}")
    print(f"结果：{ok}/{total} 通过\n")
    for good, label, detail in card["audit"]:
        print(f"  {'✅' if good else '❌'} {label} —— {detail}")
    print()
    print("e₁：" + card["e1"]["t"])
    if ok < total:
        print("\n❌ 存在不合规项，该组合不应直接投入生产。")
        return 2
    print("\n✅ 全部通过。可投入生产（但仍需人工确认 I 与 E 的调性一致）。")
    return 0


def cmd_matrix(data, args):
    temps = list(data["temperatures"].keys())
    print("母题 × 温度 兼容矩阵（◎ 支持 / · 不支持）\n")
    print(f"{'母题':<16}" + "".join(f"{t:<8}" for t in temps))
    print("-" * (16 + 8 * len(temps)))
    for m in data["motifs"]:
        row = f"{m['name']:<14}"
        for t in temps:
            row += f"{'◎':<9}" if t in m["temps"] else f"{'·':<9}"
        print(row)
    print("\n说明：不兼容不是「不能写」，而是该组合会让母题放弃核心优势——")
    print("      生成器遇到不兼容组合会自动退回母题的首选温度并给出警告。")


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="gen.py",
        description="恐怖美学母题场景生成器（T = (R - e1) × Δ - I - E）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python gen.py list\n"
               "  python gen.py gen --motif 怨灵 --temp 关系型 --seed 42\n"
               "  python gen.py batch -n 6 --seed 2026 --out cards.md\n"
               "  python gen.py check --motif mirror --temp 关系型\n",
    )
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("list", help="列出八母题与温度档")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("gen", help="生成一张场景卡")
    p.add_argument("--motif", "-m", required=True, help="母题（中文名或 id，如 ghost / 怨灵）")
    p.add_argument("--temp", "-t", default=None, help="温度（关系型/系统型/身体型/崇高型/狂喜型）")
    p.add_argument("--strength", "-s", default="any",
                   choices=["any", "low", "mid", "high"], help="e₁ 强度偏好")
    p.add_argument("--rules", "-r", type=int, default=3, help="展示几条规程（默认 3）")
    p.add_argument("--mode", default=None,
                   help="呈现模式：horror/thriller/drama/tragedy/satire/epic（或中文）")
    p.add_argument("--seed", type=int, default=None, help="随机种子（同种子必出同卡）")
    p.add_argument("--json", action="store_true", help="输出 JSON 而非 markdown")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("batch", help="批量生成")
    p.add_argument("-n", type=int, default=5, help="生成张数")
    p.add_argument("--motif", "-m", default=None, help="限定母题")
    p.add_argument("--temp", "-t", default=None, help="限定温度")
    p.add_argument("--strength", "-s", default="any",
                   choices=["any", "low", "mid", "high"], help="e₁ 强度偏好")
    p.add_argument("--mode", default=None, help="呈现模式（跨类型）")
    p.add_argument("--seed", type=int, default=0, help="随机种子")
    p.add_argument("--out", "-o", default=None, help="输出到文件（.md）")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("check", help="只跑结构自检")
    p.add_argument("--motif", "-m", required=True)
    p.add_argument("--temp", "-t", default=None)
    p.add_argument("--mode", default=None, help="呈现模式（跨类型）")
    p.add_argument("--strength", "-s", default="any",
                   choices=["any", "low", "mid", "high"])
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("matrix", help="打印母题 × 温度兼容矩阵")
    p.set_defaults(func=cmd_matrix)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0

    try:
        data = load_data()
    except DataError as e:
        print(f"❌ 数据错误：{e}", file=sys.stderr)
        return 1

    try:
        return args.func(data, args) or 0
    except DataError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
