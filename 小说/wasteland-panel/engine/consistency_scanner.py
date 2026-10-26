#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consistency_scanner.py — 一致性核查机扫

按 `一致性核查/世界观设定标尺.md` 的可判定规则，对章节草稿跑机扫：

  · R1-R15  物理规则（条件 → 结果）
  · 信息权限红线（防提前泄底）
  · 术语锁定表（错写词命中）
  · 位面名白名单（未登记的位面名）
  · 火花数值前后一致 / 灰线单调性
  · 官方专有名词禁入（万智牌 / DND）
  · 去 AI 味句式（扩写规范 §6.2）

输出：违例清单，每条带 ruleId / severity / 原文定位（行号+片段）/ 建议修法。

零三方依赖：正则 + 有限状态机。
"""

from __future__ import annotations

import re
from typing import Any

# --------------------------------------------------------------------------
# 违例等级
# --------------------------------------------------------------------------

SEV_ERROR = "error"    # 硬冲突，必须改
SEV_WARN = "warn"      # 疑似风险，建议核
SEV_INFO = "info"      # 提醒

# 外部作品专有名词（world-bible §8：正文禁出现）
FORBIDDEN_PROPER = [
    "万智牌", "Magic: The Gathering", "艾泽拉斯", "艾薇洞窟", "吉备直", "赞迪",
    "多明纳里亚", "伊曼olitics", "克诺斯", "泰瑞达", "欧洛里", "阿芒霖",
    "索齐密尔", "巴拉顿", "DND", "D&D", "龙与地下城", "奇幻冒险",
    "planeswalker", "Planeswalker", "Spark", "blind eternities", "Blind Eternities",
]

# 主角穿越前的「前世记忆」专有名词：第 1-2 章写前世时可出现，
# 属设定内合法引用（主角是网文读者/游戏同人文作者），但**不可用于位面/力量体系命名**。
PAST_LIFE_TERMS = {
    "万智牌": "前世记忆（万智牌同人游戏/外挂）",
    "鹏洛克": "本书 canonical 译名，合法",
    "鹏洛客": "万智牌官方旧译，正文禁用（见事实基线 §6）",
    "火花": "本书核心资源，合法",
    "旅法师": "力量体系名，合法",
}

# AI 味句式（扩写规范 §6.2）
AI_PATTERNS = [
    (r"不是[^。！？]{1,20}，而是[^。！？]{1,20}", "机器对偶结构「不是…而是…」", "拆成两句，或只留后半句"),
    (r"(仿佛|宛如|似乎|好像)", "模糊化副词", "每 1000 字不超过 2 次；改用直陈"),
    (r"(他知道，他明白，他清楚)", "解释性旁白排比", "删掉，用动作表达"),
    (r"^(这一刻|那一刻)[，,]", "情绪脚手架开头", "直接写动作"),
    (r"(他之所以[^。]{1,40}，是因为)", "说教式因果解释", "删因果解释，只留行为"),
    (r"(深深地|无尽的|浓浓的)", "过度形容词稀释信息密度", "换具体度量"),
    (r"(阴风阵阵|荒芜凄凉|血流成河|尸横遍野)", "四字格套路", "保留 1 个，其余删"),
    (r"(缓缓地|静静地|默默地)", "每段开头副词化", "删副词，直接给动词"),
    (r"死尸|血肉横飞|脑浆|断肢", "高风险血腥词表", "改写为「遗骸 / 那具东西 / 壳 / 闷响 / 铁锈味」"),
    (r"恐怖分子|邪教", "敏感标签", "弱化为「教派 / 那伙人 / 灰袍」"),
    (r"自杀|自尽", "自伤词表", "改写为「抵命 / 同归于尽 / 没打算回来」"),
]

# 面板判定文本（§2f 要求逐字一致）
CANON_VERDICTS = [
    "异族·坠影级（S+）",
]


# --------------------------------------------------------------------------
# 定位辅助
# --------------------------------------------------------------------------

def _snippet(text: str, pos: int, span: int = 26) -> str:
    a = max(0, pos - span)
    b = min(len(text), pos + span)
    s = text[a:b].replace("\n", "⏎")
    return ("…" if a > 0 else "") + s + ("…" if b < len(text) else "")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# --------------------------------------------------------------------------
# 单条规则检查
# --------------------------------------------------------------------------

def _add(out: list, rule: str, sev: str, msg: str, text: str, pos: int, fix: str = "") -> None:
    out.append({
        "rule": rule,
        "severity": sev,
        "message": msg,
        "line": _line_of(text, pos),
        "snippet": _snippet(text, pos),
        "fix": fix,
    })


def check_grayline_monotonic(text: str) -> list[dict]:
    """R11：灰线格数必须单调递增。扫全文所有「N格」并检查是否出现回退。"""
    out: list[dict] = []
    hits = [(m.start(), int(m.group(1))) for m in re.finditer(r"(\d{1,3})\s*格", text)]
    if len(hits) < 2:
        return out
    prev_pos, prev = hits[0]
    for pos, cur in hits[1:]:
        if cur < prev:
            _add(out, "R11 灰线单调递增", SEV_ERROR,
                 f"灰线格数回退：{prev} 格 → {cur} 格（灰线只能单调递增，不可回退）",
                 text, pos, f"检查上下文；若为回忆/旧伤需在正文点明，否则改为 {prev}→{cur} 的合理跃迁")
        prev, prev_pos = cur, pos
    return out


def check_spark_consistency(text: str) -> list[dict]:
    """火花百分比前后一致：同章内出现明显倒退即报警。"""
    out: list[dict] = []
    hits = [(m.start(), int(m.group(1))) for m in re.finditer(r"火花[^。！？]{0,12}?(\d{1,3})\s*%", text)]
    hits += [(m.start(), int(m.group(1))) for m in re.finditer(r"(\d{1,3})\s*%[^。！？]{0,6}?火花", text)]
    if len(hits) < 2:
        return out
    prev = max(hits, key=lambda h: h[0])
    for pos, cur in hits:
        if cur < prev[1] - 0 and pos > prev[0]:
            _add(out, "R5/R8 火花一致", SEV_ERROR,
                 f"火花倒退：{prev[1]}% → {cur}%（火花只能累积；点燃后不再增长）",
                 text, pos, "改为累积值，或明确写「已点燃·不再增长」")
        if pos > prev[0]:
            prev = (pos, cur)
    return out


def check_ignite_after_100(text: str) -> list[dict]:
    """R8：火花超 100%，或点燃后仍显示百分比 → 违例。"""
    out: list[dict] = []
    for m in re.finditer(r"火花[^。！？]{0,10}?(\d{2,3})\s*%", text):
        val = int(m.group(1))
        if val > 100:
            _add(out, "R8 点燃后不再增长", SEV_ERROR,
                 f"火花 {val}% 超过 100% 上限", text, m.start(),
                 "火花 100% 即点燃封顶，之后改走法力路径")
    # 点燃后面板应显示「已点燃」，若同时出现 0% 则自相矛盾
    if "已点燃" in text:
        # 只在「同一行/同一段」内找 0% 火花，避免跨段误报
        for m in re.finditer(r"【[^】]{0,20}火花[^】]{0,20}】", text):
            seg = m.group(0)
            if "已点燃" not in seg and re.search(r"火花\s*[:：]\s*0\s*%", seg):
                _add(out, "R8 点燃后不再增长", SEV_ERROR,
                     f"已点燃后同一面板仍显示 0%：{seg}", text, m.start(),
                     "点燃后显示「已点燃·不再增长」，不再显示百分比")
    return out


def check_info_leak(ds: dict, text: str, chapter: int) -> list[dict]:
    """信息权限红线：某章说出本属后章的真相 → 泄底。

    **关键：必须区分语境。** 本书主角是网文读者/游戏同人文作者，
    「鹏洛克」「火花」「旅法师」等词出现在**前世回忆**里是合法引用
    （第 1-2 章写他写外挂、看旅法师故事），不是泄底。

    只有当这些词出现在**穿越后的当下语境**（无前世标记词共现）才算泄底。
    """
    out: list[dict] = []

    # 前世语境标记：命中任一即视为闪回，不报泄底
    PAST_MARKERS = (
        "前世", "上辈子", "上一世", "这辈子之前", "猝死", "加班", "社畜",
        "码农", "万智牌", "同人游戏", "外挂", "编译器", "键盘", "办公室",
    )

    def in_past_context(text: str, pos: int, window: int = 220) -> bool:
        a = max(0, pos - window)
        b = min(len(text), pos + window)
        seg = text[a:b]
        return any(mk in seg for mk in PAST_MARKERS)

    for line in ds.get("leakLines") or []:
        floor = line.get("minChapter") or 0
        # 「不得早于第 37 章后」＝第 37 章**可以**写。
        # 解析出的 minChapter 已含章号，故此处用 >= 放行当章。
        if not floor or chapter >= floor:
            continue
        truth = line["truth"]
        keys = [k for k in re.findall(r"[一-龥A-Za-z0-9]{2,}", truth)
                if k not in ("实验体", "来历")]
        keys = keys[:4] or [truth[:4]]
        for k in keys:
            for m in re.finditer(re.escape(k), text):
                if in_past_context(text, m.start()):
                    continue      # 闪回合法，跳过
                _add(out, "信息权限红线", SEV_ERROR,
                     f"「{truth}」不得早于 {line['notBefore']}（当前第 {chapter} 章）",
                     text, m.start(),
                     f"删除或改写为角色当下可知的信息；真相落点 {line['notBefore']}")
                break
    return out


def check_terminology(ds: dict, text: str) -> list[dict]:
    """术语锁定表：错写词命中。

    注意：错写词常常是正确词的**子串**（「成河」⊂「魏成河」、
    「阿云」⊂无关、「老周头」⊂「老周」）。若正文已出现正确的完整写法，
    则该处不算错写——只有当错写词出现在**正确词未出现**的位置才报。
    """
    out: list[dict] = []
    for t in ds.get("terminology") or []:
        correct = t["name"]
        for w in t.get("forbidden") or []:
            if not w or len(w) < 2:
                continue
            for m in re.finditer(re.escape(w), text):
                # 若该位置属于正确词的内部（如「魏成河」中的「成河」），跳过
                span = correct
                for sm in re.finditer(re.escape(span), text):
                    if sm.start() <= m.start() and m.end() <= sm.end():
                        break
                else:
                    _add(out, f"术语锁定·{correct}", SEV_WARN,
                         f"「{w}」是错写，正确为「{correct}」",
                         text, m.start(), f"改为「{correct}」")
                    break   # 同一错写词只报一次
    return out


def check_plane_whitelist(ds: dict, text: str) -> list[dict]:
    """位面名白名单：正文出现未在 §3.5 登记的位面名 → 违例。

    难点：中文里「界/海/墟/境/野/渊/域」是常用字，「这个世界」「所有世界」
    会被后缀正则误抓。这里用三道闸过滤：
      ① 普通词黑名单（常见搭配）
      ② 候选词必须不在「世界/境界/领域」这类通用词尾部
      ③ 只保留长度 2-3 字且**不以「界」结尾的普通词**不被误伤——
         实际做法是维护一份高频误伤词集合做精确排除。
    """
    out: list[dict] = []
    allowed = set()
    for l in (ds.get("planes") or {}).get("layers") or []:
        allowed.add(l["name"])
    for c in (ds.get("planes") or {}).get("colorPlanes") or []:
        if c.get("name"):
            allowed.add(c["name"])

    # 高频误伤：这些词尾常接「界/海/境/域」但不是位面专名
    common = {
        "世界", "境界", "领域", "范围", "界限", "差异", "隔界", "跨界",
        "人海", "苦海", "四海", "林海", "火海", "海洋", "热海", "血海",
        "境地", "环境", "处境", "境界", "境外", "域内", "域外", "上域",
        "绝境", "逆境", "困境", "处境", "野地", "旷野", "原野", "田野",
    }

    suffix = r"[界海墟境野渊域]"
    cands = set(re.findall(rf"([一-龥]{{2,3}}{suffix})", text))
    for c in sorted(cands):
        if c in allowed or c in common:
            continue
        # 若候选包含常见词作为子串（如"射的环境"含"环境"），跳过
        if any(w in c for w in ("世界", "环境", "境界", "领域", "范围", "状况", "局面")):
            continue
        # 「域」「界」结尾且长度≥3 的，极可能是「…的世界」这类短语
        if c[-1] in "界域" and len(c) >= 3:
            continue
        # 候选首字是常见修饰词（深/无/…）时，多为形容词短语而非专名
        if c[0] in "深无太虚空有无巨微小新旧破残缺满空寂幽暗白黑红蓝绿灰":
            # 若「X」本身是已登记位面名则放行，否则视为修饰语误伤
            if c[1:] in allowed:
                continue
        m = re.search(re.escape(c), text)
        _add(out, "位面名白名单", SEV_WARN,
             f"「{c}」未在 world-bible §3.5 登记", text, m.start() if m else 0,
             f"先回 §3.5 登记；或改用已登记名（{'、'.join(sorted(allowed)[:6])}…）")
    return out


def check_void_travel(ds: dict, text: str) -> list[dict]:
    """R10：非鹏洛克禁入黑暗虚空 —— 不可带人穿越。"""
    out: list[dict] = []
    for m in re.finditer(r"(带|拉着|领着|扶着)[^。！？]{0,6}(普通|凡人|没有火花|未点燃)[^。！？]{0,10}(穿越|进入|踏入)[^。！？]{0,8}(虚空|乙太)", text):
        _add(out, "R10 非鹏洛克禁入", SEV_ERROR,
             "普通人不可穿越黑暗虚空（非鹏洛克一次呼吸内被撕裂）",
             text, m.start(), "改为独自穿越，或让对方为鹏洛克")
    for m in re.finditer(r"(虚空|乙太)[^。！？]{0,10}(耐受|停留|待)[^。！？]{0,6}(\d+)\s*(分钟|分)", text):
        pass  # 耐受数值由 selfcheck 跨卷校验覆盖，此处不重复报
    return out


def check_forbidden_proper(text: str) -> list[dict]:
    """禁外部作品专有名词。

    区分两类：
      · 前世记忆类（万智牌等）—— 主角是网文读者，第 1-2 章写前世时属合法引用，
        降为 info 提醒「仅限前世场景，位面/力量体系命名不可用」；
      · 其他外部专名 —— error。
    """
    out: list[dict] = []
    for w in FORBIDDEN_PROPER:
        m = re.search(re.escape(w), text, re.I)
        if not m:
            continue
        if w in PAST_LIFE_TERMS:
            _add(out, "前世记忆引用", SEV_INFO,
                 f"「{w}」属前世记忆范畴：{PAST_LIFE_TERMS[w]}",
                 text, m.start(),
                 "仅可在前世/回忆/主角内心语境使用；不可用于锈界位面名与力量体系命名")
        else:
            _add(out, "禁外部专有名词", SEV_ERROR,
                 f"出现外部作品专有名词「{w}」", text, m.start(),
                 "替换为本书术语（鹏洛克 / 火花 / 乙太 / 五色法力 / 位面）")
    return out


def check_ai_phrasing(text: str) -> list[dict]:
    out: list[dict] = []
    words = len(re.sub(r"\s", "", text))
    if words < 500:
        return out
    for pat, label, fix in AI_PATTERNS:
        ms = list(re.finditer(pat, text, re.M))
        if not ms:
            continue
        if label == "模糊化副词":
            if len(ms) > max(2, words // 500):
                for m in ms[:3]:
                    _add(out, "去AI味 §6.2", SEV_INFO,
                         f"{label}（全章 {len(ms)} 处，超频）", text, m.start(), fix)
                continue
        if label == "四字格套路" and len(ms) == 1:
            continue   # 保留 1 个
        for m in ms[:3]:
            _add(out, "去AI味 §6.2", SEV_WARN if label in _AI_HIGH else SEV_INFO,
                 label, text, m.start(), fix)
    # 破折号密度
    dashes = len(re.findall(r"——", text))
    if dashes > 3:
        pos = text.find("——")
        _add(out, "去AI味 §6.2", SEV_WARN,
             f"破折号 {dashes} 处（每章 ≤ 3 处）", text, pos if pos >= 0 else 0,
             "拆句或改用句号停顿")
    return out


_AI_HIGH = {"机器对偶结构「不是…而是…」", "情绪脚手架开头", "说教式因果解释", "高风险血腥词表"}


def check_canon_verdict(text: str) -> list[dict]:
    """面板判定文本须逐字一致（如「异族·坠影级（S+）」）。"""
    out: list[dict] = []
    for wrong in re.findall(r"异族[·・]\s*坠影级[^）\s]{0,4}", text):
        if wrong.replace(" ", "") not in [v.replace(" ", "") for v in CANON_VERDICTS]:
            m = re.search(re.escape(wrong), text)
            _add(out, "面板判定文本", SEV_WARN,
                 f"判定文本「{wrong}」与 §2f 逐字不一致", text, m.start() if m else 0,
                 "应为「异族·坠影级（S+）」")
    return out


def check_new_setting_budget(text: str) -> list[dict]:
    """新设定每章 ≤ 2 条（world-bible §8）。粗略统计专名首现密度。"""
    out: list[dict] = []
    cands = re.findall(r"[一-龥]{2,3}(?=[\s，。：、！？])", text)
    return out


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

def scan(ds: dict, text: str, chapter: int = 999) -> dict:
    """对章节草稿跑全套机扫。chapter 缺省 999（视为最新章，不触发泄底红线）。"""
    if not text.strip():
        return {"ok": False, "error": "章节内容为空"}

    issues: list[dict] = []
    for fn in (
        lambda: check_grayline_monotonic(text),
        lambda: check_spark_consistency(text),
        lambda: check_ignite_after_100(text),
        lambda: check_info_leak(ds, text, chapter),
        lambda: check_terminology(ds, text),
        lambda: check_plane_whitelist(ds, text),
        lambda: check_void_travel(ds, text),
        lambda: check_forbidden_proper(text),
        lambda: check_ai_phrasing(text),
        lambda: check_canon_verdict(text),
    ):
        try:
            issues.extend(fn())
        except Exception as e:            # 单条规则挂掉不能拖垮整轮
            issues.append({
                "rule": "机扫内部错误", "severity": SEV_INFO,
                "message": f"规则执行异常：{e}", "line": 0, "snippet": "", "fix": "检查规则实现",
            })

    # 去重（同 rule + 同 line + 同 message）
    seen = set()
    uniq = []
    for i in issues:
        k = (i["rule"], i["line"], i["message"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(i)

    uniq.sort(key=lambda i: ({"error": 0, "warn": 1, "info": 2}[i["severity"]], i["line"]))

    words = len(re.sub(r"\s", "", text))
    return {
        "ok": True,
        "chapter": chapter,
        "words": words,
        "total": len(uniq),
        "error": sum(1 for i in uniq if i["severity"] == SEV_ERROR),
        "warn": sum(1 for i in uniq if i["severity"] == SEV_WARN),
        "info": sum(1 for i in uniq if i["severity"] == SEV_INFO),
        "issues": uniq,
        "verdict": ("PASS" if not any(i["severity"] == SEV_ERROR for i in uniq)
                    else "FAIL"),
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    ds = json.loads((Path(__file__).parent / "data" / "dataset.json").read_text(encoding="utf-8"))
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    body = src.read_text(encoding="utf-8") if src else "火花 4%……火花 2%。异族·坠影级S+。不是疼，是麻。鹏洛克。"
    r = scan(ds, body, chapter=5)
    print(f"字数 {r['words']} · 违例 {r['total']} "
          f"(error {r['error']} / warn {r['warn']} / info {r['info']}) → {r['verdict']}")
    for i in r["issues"]:
        print(f"  [{i['severity']:5}] {i['rule']} L{i['line']}: {i['message']}")
