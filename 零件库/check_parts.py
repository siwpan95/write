#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_parts.py —— 零件卡 v2.0 字段格式校验

定位：**只判「机器能不能读懂这张卡」，不判「这张卡好不好」。**
内容质量（压力是否成立、有没有伪量化）仍需人工过六门，见 00 §三。

用法：
    python 零件库/check_parts.py             # 校验 + 摘要
    python 零件库/check_parts.py --strict    # 有 ERROR 时退出码 1（可直接进门禁）

判定分三级：
    ERROR  字段缺失／取值非法／四段不全 —— 卡不可被程序调用
    WARN   规范允许但需登记的变体（如事件型 REQ、band 档位与 recover 不符）—— 可调用，但要在卡内注明
    INFO   统计口径（状态门槛型 vs 事件触发型）

校验项（对应 00 §四 五组 21 项）：
    1  零件ID 由二级标题 `WB-<类型>-<四位>` 提供
    2  20 个表字段齐全（调用记录除外——未调用者本就没有）
    3  抽象层 = L2
    4  双标签 "A × B"，两侧均为合法枚举
    5  内核层 含 基础层/玩法层
    6  参数可换度 ∈ 高/中/低
    7  band 含 **L1-L4** + target: + recover:；target 用八量或写「无」（元零件/诊断工具）
    8  phase 含 设/压/翻/竭 至少一个
    9  rule 四段齐全；Δ 引用八量 ≤2 个；ELSE 非空
    10 施压时序 以 立刻/累积/待触发 开头
    11 行程激活差异 ≥2 个不同的读取视角（探针名／「读到」／行程线皆可）
    12 可咬合零件 至少 1 个 WB- ID，或明写「元零件」
    13 落地接口 含四类枚举之一
    14 压力机制 至少落到 权限／代价／矛盾 之一（规范 §五 B 的真正要求）
    15 不可申诉之物：内核层=基础层 或 双标签含「施压」时必填
"""
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CARD_FILES = [
    "02-制度型零件.md",
    "03-机制型零件.md",
    "04-地理与资源型零件.md",
    "05-历史与接口型零件.md",
]

TYPE_ENUM = {"制度", "机制", "经济", "历史", "地理", "信息", "器物", "组织·势力", "技术·规则", "文化·信仰"}
FUNC_ENUM = {"施压", "阻碍", "揭示", "交易", "催化", "诱惑", "供给"}
QTY = ["财", "势", "名", "位", "时", "秘", "身", "信"]
PROBES = ["逃亡者", "执法者", "投机者", "学习者", "本地人", "外来者", "记录者", "被记录者"]
IFACE_ENUM = ["地理邻接", "制度隶属", "历史旧账", "资源依赖"]
ROLE_ENUM = {"参与", "判定", "元"}
MUTEX_COND = ["前提取消", "效果抵消", "处置互斥", "载体争用"]
LEVER = ["权限", "代价", "矛盾"]
ID_RE = re.compile(r"^## `(WB-[A-Z]+-\d{4})`")

FIELDS = [
    "零件名", "卡面版本", "抽象层", "来源登记", "借用方式", "借用范围", "双标签", "一句话定义",
    "内核层", "参数可换度", "可咬合零件", "落地接口", "压力机制", "band", "phase",
    "rule", "行程激活差异", "不可申诉之物", "施压时序", "适配基线",
    "装配角色", "互斥零件",
]
OPTIONAL = ["调用记录"]
CARD_VERSION_RE = re.compile(r"^v\d+\.\d+$")


def clean(s):
    return s.replace("`", "").replace("**", "").strip()


def split_cards(text):
    cards, cur_id, cur = [], None, []
    for line in text.splitlines():
        m = ID_RE.match(line)
        if m:
            if cur_id:
                cards.append((cur_id, "\n".join(cur)))
            cur_id, cur = m.group(1), []
        elif cur_id is not None:
            if line.startswith("## ") and not ID_RE.match(line):
                cards.append((cur_id, "\n".join(cur)))
                cur_id, cur = None, []
            else:
                cur.append(line)
    if cur_id:
        cards.append((cur_id, "\n".join(cur)))
    return cards


def parse_fields(body):
    out = {}
    for line in body.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key = clean(cells[0])
        if (key in FIELDS or key in OPTIONAL) and key not in out:
            out[key] = "|".join(cells[1:]).strip()
    return out


def check(cid, f):
    errs, warns, infos = [], [], []
    ctype = cid.split("-")[1]
    if ctype not in {"INST", "MECH", "ECON", "GEO", "HIST", "ART", "INFO", "IFACE"}:
        errs.append(f"ID 类型段非法: {ctype}")

    missing = [x for x in FIELDS if not f.get(x)]
    if missing:
        errs.append("缺字段: " + "、".join(missing))

    if f.get("抽象层") and "L2" not in f["抽象层"]:
        errs.append(f"抽象层非 L2: {clean(f['抽象层'])[:20]}")

    tag = clean(f.get("双标签", ""))
    if tag:
        if "×" not in tag:
            errs.append("双标签缺 ×")
        else:
            for grp in tag.split("／"):
                if "×" not in grp:
                    continue
                a, b = [clean(x) for x in grp.split("×", 1)]
                if a not in TYPE_ENUM:
                    errs.append(f"类型标签非法: {a}")
                if b.split("／")[0].strip() not in FUNC_ENUM:
                    errs.append(f"功能标签非法: {b}")

    layer = f.get("内核层", "")
    if layer and not ("基础层" in layer or "玩法层" in layer):
        errs.append("内核层未写 基础层/玩法层")

    deg = f.get("参数可换度", "")
    if deg and not any(k in deg for k in ("高", "中", "低")):
        errs.append("参数可换度未写 高/中/低")

    band = f.get("band", "")
    lv = None
    if band:
        m = re.search(r"\*\*(L[1-4])\*\*", band)
        if not m:
            errs.append("band 缺 **L1-L4** 档")
        else:
            lv = m.group(1)
        if "target" not in band:
            errs.append("band 缺 target")
        if "recover" not in band:
            errs.append("band 缺 recover")
        if "target" in band and "recover" in band:
            m2 = re.search(r"target[:：]\s*([^｜|]+)", clean(band))
            tgt = m2.group(1).strip() if m2 else ""
            if not (any(q in tgt for q in QTY) or tgt.startswith("无")):
                errs.append(f"band.target 既非八量也非「无」: {tgt[:12]}")
            rec = band.split("recover", 1)[1]
            if lv in ("L1", "L2") and "不可逆" in rec:
                warns.append(f"band 档位 {lv} 却写 recover 不可逆（应 L3/L4）")
            if lv in ("L3", "L4") and ("条件" in rec and "不可逆" not in rec):
                warns.append(f"band 档位 {lv} 却写 recover 条件（应 L2 左右）")

    phase = f.get("phase", "")
    if phase and not any(k in phase for k in ("设", "压", "翻", "竭")):
        errs.append("phase 无 设/压/翻/竭")

    rule = f.get("rule", "")
    req_mode = "未判"
    if rule:
        for seg in ("REQ", "EFF", "Δ", "ELSE"):
            if not re.search(seg + r"[:：]", rule):
                errs.append(f"rule 缺 {seg} 段")
        if re.search(r"ELSE[:：]", rule):
            tail = re.split(r"ELSE[:：]", rule, maxsplit=1)[1].strip()
            if not tail:
                errs.append("ELSE 留空（应显式写「无」）")
        if re.search(r"Δ[:：]", rule):
            dseg = re.split(r"Δ[:：]", rule, maxsplit=1)[1]
            dseg = re.split(r"ELSE[:：]", dseg, maxsplit=1)[0]
            used = [q for q in QTY if q in dseg]
            if len(used) > 2:
                errs.append(f"Δ 引用 {len(used)} 个量（上限 2）: {''.join(used)}")
        if re.search(r"REQ[:：]", rule):
            rseg = re.split(r"REQ[:：]", rule, maxsplit=1)[1].split("EFF")[0]
            if any(q in rseg for q in QTY):
                req_mode = "状态门槛"
            else:
                req_mode = "事件触发"
                infos.append("REQ 为事件触发型（不筛人，对进入者一律生效）")

    seq = clean(f.get("施压时序", ""))
    if seq and not any(seq.startswith(k) for k in ("立刻", "累积", "待触发")):
        errs.append(f"施压时序取值非法: {seq[:16]}")

    probe = f.get("行程激活差异", "")
    bite = f.get("可咬合零件", "")
    # 元件／判定件：判定工具或元零件，二者都不产生咬合边
    is_meta = ("元零件" in bite) or ("判定工具" in bite)
    if probe and not is_meta:
        hit = {p for p in PROBES if p in probe}
        n_read = probe.count("读到")
        n_line = len(re.findall(r"[^\s；;]*线（", probe))
        if max(len(hit), n_read, n_line) < 2:
            errs.append(f"行程激活差异视角不足（探针 {len(hit)}／读到 {n_read}／线 {n_line}）")
        elif len(hit) < 2:
            infos.append("行程激活差异用自定义视角（规范允许，卡内已注明）")
    elif is_meta and probe and not any(p in probe for p in PROBES):
        infos.append("元零件：激活视角随被验对象而定（无固定探针）")

    if bite and not (re.search(r"WB-[A-Z]+-\d{4}", bite) or is_meta):
        errs.append("可咬合零件 无 WB- ID，也未注明「元零件」")

    iface = f.get("落地接口", "")
    if iface and not any(k in iface for k in IFACE_ENUM):
        errs.append("落地接口 无四类枚举")

    press = f.get("压力机制", "")
    if press and not any(k in press for k in LEVER):
        errs.append("压力机制 未落到 权限／代价／矛盾 任何一项")

    must = ("基础层" in layer) or ("施压" in tag)
    if must and not f.get("不可申诉之物"):
        errs.append("内核层=基础层 或 含施压，但 不可申诉之物 为空")

    # ---- A 组（v2.3）：卡面版本 ----
    cv_raw = clean(f.get("卡面版本", ""))
    cv = re.match(r"v\d+\.\d+", cv_raw)
    if not cv:
        errs.append("卡面版本 缺 `vX.Y` 格式（如 v2.3）")

    # ---- F 组（v2.2）：装配角色 / 互斥零件 ----
    role_raw = clean(f.get("装配角色", ""))
    role = ""
    if role_raw:
        m = re.search(r"(参与|判定|元)", role_raw)
        if not m:
            errs.append("装配角色 取值非法（应为 参与／判定／元）")
        else:
            role = m.group(1)

    mutex_raw = f.get("互斥零件", "")
    mutex_ids = []
    if mutex_raw and clean(mutex_raw) != "无":
        for mm in re.finditer(r"(WB-[A-Z]+-\d{4})`?（`([^`]+)`）", mutex_raw):
            other, cond = mm.group(1), mm.group(2)
            mutex_ids.append(other)
            if cond not in MUTEX_COND:
                errs.append(f"互斥条件类型非法: {cond}（应 {'／'.join(MUTEX_COND)}）")
        if not mutex_ids:
            errs.append("互斥零件 未按 `ID`（`条件类型`）格式书写，且未写「无」")
        if cid in mutex_ids:
            errs.append("互斥零件 指向自己")
        # 判定／元件不进装配体，无从与谁拆台
        if role in ("判定", "元") and mutex_ids:
            errs.append(f"装配角色={role} 的件不进入装配体，不应有互斥零件")

    # 判定／元件不得列具体 ID 作为咬合对象
    # 判据：文本须明确声明「不产生咬合边」或注明「元零件／判定工具」，
    # 而非「文本里是否出现 ID」——正文明写"服务于 X"是使用关系，不是装配关系。
    if role in ("判定", "元"):
        bite_txt = f.get("可咬合零件", "")
        declared_meta = ("元零件" in bite_txt) or ("判定工具" in bite_txt)
        declared_noedge = ("不产生咬合边" in bite_txt) or ("不列入任何装配体成员清单" in bite_txt) \
            or ("不是咬合边" in bite_txt)
        if not (declared_meta or declared_noedge):
            errs.append(f"装配角色={role} 的件，「可咬合零件」须注明「元零件」或「判定工具」"
                        "并声明不产生咬合边")
        # 若已声明不产生咬合边，则不应在行首以「ID 名称（条件类型）」形式列出咬合对象
        if declared_noedge and re.match(r"^\s*`WB-[A-Z]+-\d{4}`", bite_txt):
            errs.append(f"装配角色={role} 的件不得以 ID 列表形式登记咬合对象（它不产生咬合边）")
    elif role == "参与" and not re.search(r"WB-[A-Z]+-\d{4}", f.get("可咬合零件", "")):
        warns.append("装配角色=参与 但「可咬合零件」未列具体 ID（须确认确无邻接）")

    return errs, warns, infos, req_mode, role, mutex_ids


def main():
    strict = "--strict" in sys.argv
    verbose = "--verbose" in sys.argv
    total, bad, all_issues = 0, 0, []
    modes = {"状态门槛": 0, "事件触发": 0, "未判": 0}
    n_info = 0
    seen = {}
    # 跨卡数据：咬合边（单侧登记）与互斥边（单侧登记）
    bite_edges = {}   # cid -> set(other)
    mutex_edges = {}  # cid -> set(other)
    roles = {}        # cid -> role
    for name in CARD_FILES:
        p = BASE / name
        if not p.exists():
            all_issues.append((name, ["文件不存在"], [], []))
            bad += 1
            continue
        for cid, body in split_cards(p.read_text(encoding="utf-8")):
            total += 1
            seen[cid] = seen.get(cid, 0) + 1
            f = parse_fields(body)
            errs, warns, info, mode, role, mutex_ids = check(cid, f)
            modes[mode] = modes.get(mode, 0) + 1
            n_info += len(info)
            roles[cid] = role
            bite_edges[cid] = set(re.findall(r"WB-[A-Z]+-\d{4}", f.get("可咬合零件", "")))
            mutex_edges[cid] = set(mutex_ids)
            if errs or warns or (verbose and info):
                all_issues.append((cid, errs, warns, info))
            if errs:
                bad += 1

    # ---- 跨卡校验（v2.2 F 组）----
    all_ids = set(seen)
    cross_info = []
    for cid, ms in mutex_edges.items():
        for other in ms:
            if other not in all_ids:
                all_issues.append((cid, [f"互斥零件指向不存在的件: {other}"], [], []))
                bad += 1
            # 接口相容 ≠ 装配相容：两表可交叠，但值得点名
            if other in bite_edges.get(cid, set()) or cid in bite_edges.get(other, set()):
                cross_info.append(f"{cid} ⊗ {other}：接口相容但装配互斥（同场会拆台）")

    nwarn = sum(1 for _, e, w, _ in all_issues if not e and w)
    print(f"零件卡校验：共 {total} 件｜ERROR {bad}｜WARN {nwarn}｜INFO {n_info}")
    print(f"REQ 口径：状态门槛 {modes['状态门槛']}（筛人）／事件触发 {modes['事件触发']}（不筛人）")
    n_role = {}
    for r in roles.values():
        n_role[r] = n_role.get(r, 0) + 1
    print(f"装配角色：参与 {n_role.get('参与', 0)}／判定 {n_role.get('判定', 0)}／元 {n_role.get('元', 0)}")
    n_mutex = sum(len(v) for v in mutex_edges.values())
    print(f"互斥边：单侧登记 {n_mutex} 条｜对称后 {sum(len(v) for v in mutex_edges.values()) // 2} 对"
          if n_mutex else "互斥边：0 条")
    if cross_info:
        print(f"接口相容但装配互斥（装配时重点检查）{len(cross_info)} 对：")
        for x in cross_info:
            print("  " + x)
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        print("  重复 ID：" + "、".join(dup))
    for cid, errs, warns, info in all_issues:
        print(f"\n[{cid}]")
        for e in errs:
            print("  ERROR " + e)
        for w in warns:
            print("  WARN  " + w)
        for i in info:
            print("  INFO  " + i)
    if bad == 0:
        print("\n结论：全部卡可被机器读取（≠ 压力成立；那要过 00 §三六门与实战调用）。")
    return 1 if (bad and strict) else 0


if __name__ == "__main__":
    sys.exit(main())
