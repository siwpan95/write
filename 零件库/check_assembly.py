#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_assembly.py —— 装配级校验（v2.8，G2+G9+G10-13+17号P3）。

定位：**只判「这一套装配合不合法」，不判「这套装配好不好」。**
质量（压力是否成立）仍需人工六门＋白盒，见 `00` §六。

用法：
    python check_assembly.py                    # 校验装配体/ASM-*.md
    python check_assembly.py --verbose          # 打印 INFO
    python check_assembly.py --coverage         # 输出组合覆盖台账数据
    python check_assembly.py --strict           # 有 ERROR 时退出码 1

检查项（对应 00 §十一 12.5）：
 1 成员两两互斥（条件敏感：读条件描述，不只读 ID 对）
 2 必含件缺失  3 哑火件  4 同 target 相邻  5 同 phase 相邻
 6 L4 数量/相邻（同族配套降级 WARN）  7 连续 L3+ 无休止
 8 装配体无驱动量或元件混入成员  9 驱动量与 Δ 对齐(INFO)  10 ELSE 全负向导致无解
11 可达性（仅状态门槛型 6 件严格 BFS；事件触发型只标「未判定」）
12 dynamics 摘要（实际触发顺序／首见底量／峰值位置）与硬瓶颈登记
13 健康度（交互密度／低度件，只报 INFO）
14 差异性预算（刻意的反常，只报 INFO，**不改 1–13 的判定**——00 §十一 12.7）
"""
import io
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ASMDIR = os.path.join(HERE, "装配体")
CARD_FILES = ["02-制度型零件.md", "03-机制型零件.md",
              "04-地理与资源型零件.md", "05-历史与接口型零件.md"]

QTY = ["财", "势", "名", "位", "时", "秘", "身", "信"]
PHASES = ["设", "压", "翻", "竭"]

# 同族配套：这些对即使同为 L4 且相邻，也只报 WARN（不报 ERROR）
# 依据：00 §五 G.2「同族配套不算互斥」；B2 卷一实测
SAME_FAMILY = {
    frozenset(("WB-INST-0001", "WB-INFO-0017")),  # 记录即存在 / 划名机制（减法线）
}

# 条件敏感互斥：某些互斥对只在特定条件成立时才触发。
# 条件描述在零件卡里，脚本须能读到「同一份」这类限定词。
# key = frozenset((a,b)), value = 触发所需的关键限定词（出现在装配体正文即视为触发）
CONDITIONAL_MUTEX = {
    frozenset(("WB-ECON-0022", "WB-ECON-0012")): {
        "限定词": "同一份",
        "说明": "同一份「名」不能既当计价单位又当担保物；两份不同的名不触发（B2 卷三实测）",
    },
}


def clean(s):
    return s.replace("`", "").replace("**", "").strip()


# ---------------------------------------------------------------- 卡片解析
def load_cards():
    """返回 cid -> {name, role, band, phase, target, req, else_text, bite_ids, mutex}"""
    info = {}
    for fname in CARD_FILES:
        p = os.path.join(HERE, fname)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding="utf-8").read()
        parts = re.split(r"^## `(WB-[A-Z]+-\d{4})`[^\n]*$", s, flags=re.M)
        for i in range(1, len(parts) - 1, 2):
            cid, body = parts[i], parts[i + 1]
            fields = {}
            for ln in body.splitlines():
                ln = ln.strip()
                if not (ln.startswith("|") and ln.endswith("|")):
                    continue
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if len(cells) >= 2:
                    fields[clean(cells[0])] = "|".join(cells[1:]).strip()
            m = re.search(r"\*\*(L[1-4])\*\*", fields.get("band", ""))
            band = m.group(1) if m else ""
            t = re.search(r"target[:：]\s*([^｜|]+)", clean(fields.get("band", "")))
            target = t.group(1).strip() if t else ""
            ph = fields.get("phase", "")
            phases = [p for p in PHASES if p in ph]
            rule = fields.get("rule", "")
            req = re.split(r"REQ[:：]", rule, maxsplit=1)[1].split("EFF")[0].strip() if "REQ" in rule else ""
            els = re.split(r"ELSE[:：]", rule, maxsplit=1)[1].strip() if "ELSE" in rule else ""
            role = ""
            rm = re.search(r"(参与|判定|元)", clean(fields.get("装配角色", "")))
            if rm:
                role = rm.group(1)
            info[cid] = {
                "name": clean(fields.get("零件名", "")),
                "role": role,
                "band": band,
                "target": target,
                "phases": phases,
                "req": req,
                "else": els,
                "bite_ids": set(re.findall(r"WB-[A-Z]+-\d{4}", fields.get("可咬合零件", ""))),
                "mutex_ids": set(re.findall(r"WB-[A-Z]+-\d{4}", fields.get("互斥零件", ""))),
            }
    return info


# ---------------------------------------------------------------- 装配体解析
def field(body, key):
    """装配体字段表为三列：`| 1 | `装配ID` | 值 |`；也兼容两列 `| 装配ID | 值 |`。"""
    k = re.escape(key)
    # 三列：| 序号 | `字段` | 值 |
    m = re.search(r"^\|\s*\d+\s*\|\s*`?" + k + r"`?\s*\|(.+?)\|\s*$", body, flags=re.M)
    if m:
        return m.group(1).strip()
    # 两列：| `字段` | 值 |
    m = re.search(r"^\|\s*`?" + k + r"`?\s*\|(.+?)\|\s*$", body, flags=re.M)
    return m.group(1).strip() if m else ""


def load_assemblies():
    out = []
    if not os.path.isdir(ASMDIR):
        return out
    for fn in sorted(os.listdir(ASMDIR)):
        if not (fn.startswith("ASM-") and fn.endswith(".md")):
            continue
        p = os.path.join(ASMDIR, fn)
        body = io.open(p, encoding="utf-8").read()
        # 成员件：从 §2.2「成员件与角色」表读全称。
        # 只取表格行（以 | 开头且含 WB- ID）里的件；说明段里提到的判定件不算成员。
        m22 = re.search(r"^###\s*2\.2\s*成员件与角色[^\n]*\n(.*?)(?=^###\s*2\.3|\Z)",
                        body, flags=re.M | re.S)
        members = []
        phases_by_member = {}
        if m22:
            for ln in m22.group(1).splitlines():
                if not ln.strip().startswith("|"):
                    continue
                ids = re.findall(r"WB-[A-Z]+-\d{4}", ln)
                if not ids:
                    continue
                cid = ids[0]
                if cid not in members:
                    members.append(cid)
                # 序位表第 3 列是 phase（设／压／翻／竭）——按文中首次出现位置取，
                # 不按 PHASES 列表顺序（否则「翻（原压）」会被误判为「压」）
                ph_pos = [(ln.find(p), p) for p in PHASES if p in ln]
                if ph_pos:
                    phases_by_member[cid] = min(ph_pos)[1]
        members = list(dict.fromkeys(members))
        # 驱动量：从 §2.3 标题下第一行加粗量名
        drv = ""
        m = re.search(r"^###\s*2\.3\s*驱动量[^\n]*\n+([^\n]+)", body, flags=re.M)
        if m:
            d = re.search(r"\*\*([^*]+)\*\*", m.group(1))
            drv = clean(d.group(1)) if d else ""
        out.append({
            "file": fn,
            "aid": clean(field(body, "装配ID")),
            "topic": clean(field(body, "课题")),
            "members": members,
            "member_phases": phases_by_member,
            "driver": drv,
            "phase_order": [p for p in PHASES if p in field(body, "序位")],
            "body": body,
        })
    return out


# ---------------------------------------------------------------- 检查
def check_assembly(a, cards):
    errs, warns, infos = [], [], []
    members = a["members"]
    body = a["body"]

    # 8 成员角色：判定件/元件不得混入
    for cid in members:
        if cards.get(cid, {}).get("role") in ("判定", "元"):
            errs.append(f"成员 {cid} 的装配角色={cards[cid]['role']}，不得进装配体成员清单")

    # 8b 驱动量
    if not a["driver"]:
        errs.append("缺驱动量（Venture 要求一个 State 值驱动）")
    if not (2 <= len(members) <= 4):
        warns.append(f"成员数 {len(members)}，Venture 建议 2–4 件")

    # 1 互斥（条件敏感）
    for i, x in enumerate(members):
        for y in members[i + 1:]:
            pair = frozenset((x, y))
            cond = CONDITIONAL_MUTEX.get(pair)
            if not cond:
                # 无条件的登记互斥：从卡片表读
                if y in cards.get(x, {}).get("mutex_ids", set()) or x in cards.get(y, {}).get("mutex_ids", set()):
                    errs.append(f"互斥对同场：{x} ⊗ {y}")
                continue
            # 条件互斥：装配体正文须显式说明「不是同一份」才放行
            if cond["限定词"] in body and ("不同" in body or "不是同一份" in body):
                infos.append(f"{x} ⊗ {y}：条件互斥（限定「{cond['限定词']}」），"
                             f"装配体已声明被押者与计价者对象不同——不触发，放行")
            else:
                errs.append(f"条件互斥未消解：{x} ⊗ {y}——{cond['说明']}")

    # 2 必含件缺失：落地接口写了另一零件 ID（极简：检查卡片可咬合中是否有使能标注且不在成员）
    for cid in members:
        for dep in cards.get(cid, {}).get("bite_ids", set()):
            if dep not in members and cards.get(dep, {}).get("role") in ("判定", "元"):
                continue  # 判定/元件不是必含件
            # 只对本卡 REQ 里显式写了「在册／在案」的做严格检查（避免误报）
            if "在册" in cards.get(cid, {}).get("req", "") and dep == "WB-INST-0001" and dep not in members:
                errs.append(f"{cid} 的 REQ 依赖「在册」，但必含件 WB-INST-0001 不在装配体")

    # 3 哑火件：REQ 里的量条件与初态八量对照（初态从 §2.4 表读，简化：只看是否有明确不满足）
    init = {}
    for ln in body.splitlines():
        m = re.match(r"^\|\s*\*\*?([财势名位时秘身信])\*\*?\s*\|\s*(-?\d+)", ln)
        if m:
            init[m.group(1)] = int(m.group(2))
    for cid in members:
        req = cards.get(cid, {}).get("req", "")
        for q, op, val in re.findall(r"([财势名位时秘身信])\s*([<>≤≥=]+)\s*(-?\d+)", req):
            if q not in init:
                continue
            v, n = init[q], int(val)
            bad = (op in ("<", "≤") and v >= n and op == "<") or \
                  (op == "≤" and v > n) or (op == ">" and v <= n) or \
                  (op == "≥" and v < n) or (op == "=" and v != n)
            if bad:
                errs.append(f"哑火件 {cid}：REQ「{q}{op}{val}」与初态 {q}={v} 冲突")
                break

    # 4/5 target 与 phase 相邻
    # phase 判据：用本装配体序位表实际标注的相位（member_phases），
    # 不取零件卡的多值 phase 集合——同一件在不同装配体可按不同相位用（如 HIST-0026 卷三改「翻」）
    mp = a.get("member_phases", {})
    for i in range(1, len(members)):
        a1, a2 = cards.get(members[i - 1], {}), cards.get(members[i], {})
        if a1.get("target") and a1.get("target") == a2.get("target"):
            warns.append(f"相邻同 target：{a1['target']}（{members[i-1]}→{members[i]}）")
        p1, p2 = mp.get(members[i - 1], ""), mp.get(members[i], "")
        if p1 and p1 == p2:
            warns.append(f"相邻同 phase：{p1}（{members[i-1]}→{members[i]}）")

    # 6 L4 数量与相邻
    l4 = [cid for cid in members if cards.get(cid, {}).get("band") == "L4"]
    if len(l4) > 2:
        errs.append(f"L4 数量 {len(l4)} > 2（违反 13 §8.1 跨体系纪律）")
    if len(l4) == 2:
        idx = [members.index(x) for x in l4]
        if abs(idx[0] - idx[1]) == 1:
            if frozenset(l4) in SAME_FAMILY:
                warns.append(f"L4 相邻但属同族配套：{l4[0]} ⊗ {l4[1]}——报 WARN 不报 ERROR")
            else:
                errs.append(f"L4 相邻且非同族配套：{l4[0]} ⊗ {l4[1]}")

    # 7 连续 2 个 L3+ 后无休止
    run = 0
    for cid in members:
        b = cards.get(cid, {}).get("band", "")
        if b in ("L3", "L4"):
            run += 1
            if run >= 2:
                warns.append(f"连续 2 个 L3+（止于 {cid}），须插 L1 或休止段")
        else:
            run = 0

    # 9 驱动量与 Δ 对齐
    if a["driver"] and a["driver"] in QTY:
        hit = sum(1 for cid in members if a["driver"] in cards.get(cid, {}).get("target", ""))
        if hit and hit < len(members):
            infos.append(f"驱动量 {a['driver']} 只出现在 {hit}/{len(members)} 件的 target 中——对齐度偏低（只报告不判错）")

    # 10 ELSE 全负向
    if members:
        all_neg = all(
            ("无" not in cards.get(cid, {}).get("else", "")) and
            ("停摆" in cards.get(cid, {}).get("else", "") or "反噬" in cards.get(cid, {}).get("else", ""))
            for cid in members
        )
        if all_neg:
            errs.append("所有成员的 ELSE 均为负向且无活路——主角可能无解（B5 可达性前置）")

    # 11 可达性（G10）：仅状态门槛型严格 BFS，事件触发型标未判定
    state_gated = [cid for cid in members if any(
        q in cards.get(cid, {}).get("req", "") for q in QTY)]
    event_driven = [cid for cid in members if cid not in state_gated]
    if state_gated:
        # 用装配体初态八量做一步可达性推演（不建完整 BFS——本库样本小，
        # 且事件触发型不可枚举，完整 BFS 会给出虚假确定性）
        unsatisfied = []
        for cid in state_gated:
            req = cards.get(cid, {}).get("req", "")
            for q, op, val in re.findall(r"([财势名位时秘身信])\s*([<>≤≥=]+)\s*(-?\d+)", req):
                if q not in init:
                    continue  # 初态缺此量 → 不判（避免虚假确定性）
                v, n = init[q], int(val)
                ok = ((op == "<" and v < n) or (op == "≤" and v <= n) or
                      (op == ">" and v > n) or (op == "≥" and v >= n) or
                      (op == "=" and v == n))
                if not ok:
                    unsatisfied.append(f"{cid}: {q}{op}{val}（初 {q}={v}）")
        deadlock = bool(unsatisfied)
        verdict = ("不可达（状态门槛在初态即不满足）：" + "；".join(unsatisfied)) if deadlock \
            else "至少一步可达"
        infos.append(f"可达性：状态门槛型 {len(state_gated)} 件严格判定＝{verdict}；"
                     f"事件触发型 {len(event_driven)} 件＝未判定（不可严格规划，须随机采样坏状态）")
        if deadlock:
            errs.append("装配无解：状态门槛型零件的 REQ 在初态即不满足")

    # 12 dynamics 与硬瓶颈（G11/G13）：检查装配体是否回填了实值（非「待 B5 回填」）
    dyn = field(a["body"], "dynamics 记录")
    if not dyn or "待 B5" in dyn or "待回填" in dyn:
        warns.append("dynamics 记录未回填（实际触发顺序／首见底量／峰值位置）")
    # 硬瓶颈：装配体正文若显式声明解法数=1，须同时写瓶颈出口
    if "解法数" in a["body"] and "1（硬瓶颈）" in a["body"] and "瓶颈出口" not in a["body"]:
        errs.append("声明了硬瓶颈（解法数=1）但未写瓶颈出口")
    # 解法数「缺口」：诚实登记缺件，属带洞装配体，报 INFO 不报 ERROR
    if "解法数" in a["body"] and "缺口" in field(a["body"], "解法数"):
        infos.append("解法数登记为「缺口」——带洞装配体（缺件已登记，非本装配体写错）")

    # 14 差异性预算（v2.8 / 17号 P3）：刻意的反常是声明，不是豁免。
    # 只报 INFO，**不改任何 ERROR/WARN 判定**——否则 linter 从「判合法」滑向「判好坏」。
    anomaly = field(a["body"], "本卷刻意的反常")
    if anomaly and "无" not in anomaly[:4]:
        infos.append(f"差异性预算：本卷登记刻意的反常——{anomaly[:80]}"
                     "（声明不豁免，合法性检查照常执行）")

    # 15 健康度（G12）：孤岛件与交互密度
    bite_deg = {cid: len(c.get("bite_ids", set())) for cid, c in cards.items()
                if c.get("role") not in ("判定", "元")}
    islands = [cid for cid in members if bite_deg.get(cid, 0) < 2]
    if islands:
        infos.append(f"健康度：咬合度<2 的成员：{', '.join(islands)}——"
                     "不等于违规，但按乘法判据应关注其交互面")
    n_member = len(members)
    max_pairs = n_member * (n_member - 1) // 2
    real_edges = 0
    for i, x in enumerate(members):
        for y in members[i + 1:]:
            if y in cards.get(x, {}).get("bite_ids", set()) or x in cards.get(y, {}).get("bite_ids", set()):
                real_edges += 1
    density = real_edges / max_pairs if max_pairs else 0
    infos.append(f"健康度：交互密度 {real_edges}/{max_pairs}＝{density:.0%}"
                 "（S² 乘法判据：3 件全互咬＝100%）")

    return errs, warns, infos
def coverage(assemblies, cards):
    """2-way 覆盖：统计属性维度（band × phase × target × 功能角色）的组合覆盖。"""
    seen = set()
    total = 0
    for a in assemblies:
        for cid in a["members"]:
            c = cards.get(cid, {})
            key = (c.get("band", ""), tuple(c.get("phases", [])), c.get("target", ""), c.get("role", ""))
            seen.add(key)
            total += 1
    # 全部可能组合（仅统计实际出现的属性值的笛卡尔积上界）
    bands = sorted({cards.get(c, {}).get("band", "") for a in assemblies for c in a["members"] if c in cards})
    roles = sorted({cards.get(c, {}).get("role", "") for a in assemblies for c in a["members"] if c in cards})
    universe = len(bands) * len(PHASES) * len(QTY) * len(roles)
    return {
        "装配体数": len(assemblies),
        "成员出现次数": total,
        "已覆盖属性组合": len(seen),
        "2way 全空间上界": universe,
        "覆盖率": f"{len(seen) / universe * 100:.1f}%" if universe else "n/a",
    }


# ---------------------------------------------------------------- main
def main():
    strict = "--strict" in sys.argv
    verbose = "--verbose" in sys.argv
    cov_only = "--coverage" in sys.argv

    cards = load_cards()
    assemblies = load_assemblies()
    if not assemblies:
        print("未找到装配体（装配体/ASM-*.md）")
        return 2

    cov = coverage(assemblies, cards)
    if cov_only:
        print("=== 组合覆盖度（2-way，covering array 思路）===")
        for k, v in cov.items():
            print(f"{k}: {v}")
        return 0

    total_err = total_warn = total_info = 0
    for a in assemblies:
        errs, warns, infos = check_assembly(a, cards)
        total_err += len(errs); total_warn += len(warns); total_info += len(infos)
        print(f"\n[{a['aid']}] {a['topic']}（{a['file']}）")
        print(f"  成员 {len(a['members'])} 件｜驱动量 {a['driver'] or '未声明'}")
        for e in errs: print("  ERROR " + e)
        for w in warns: print("  WARN  " + w)
        if verbose:
            for i in infos: print("  INFO  " + i)
        elif infos:
            print(f"  INFO  {len(infos)} 条（--verbose 展开）")

    print(f"\n合计：装配体 {len(assemblies)}｜ERROR {total_err}｜WARN {total_warn}｜INFO {total_info}")
    print(f"组合覆盖：已覆盖 {cov['已覆盖属性组合']} 种属性组合／上界 {cov['2way 全空间上界']}"
          f"（{cov['覆盖率']}，2-way）")
    print("说明：本脚本只判装配合法性，不判装配质量（见 00 §十一 12.5）")
    return 1 if (strict and total_err) else 0


if __name__ == "__main__":
    sys.exit(main())
