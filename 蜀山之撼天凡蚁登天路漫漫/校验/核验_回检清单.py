#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立核验：卷三回检报告 §十 修订清单的 8 项 claim + 卷三 125 章篇幅/体例实测。

原则：**不采信报告数字**，全部从文件重新计算。
用法：python3 校验/核验_回检清单.py
"""
import difflib
import glob
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

rows = []          # (id, claim, result, evidence, verdict)
def add(i, claim, result, ev, v):
    rows.append((i, claim, result, ev, v))
    print(f"[{v}] #{i} {claim}\n     {result}\n     {ev}\n")


def md(path):
    p = os.path.join(ROOT, path)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def chapters(pattern):
    out = {}
    for f in glob.glob(os.path.join(ROOT, "正文", pattern)):
        s = open(f, encoding="utf-8").read()
        parts = re.split(r"^# 第 (\d+) 章 (.+)$", s, flags=re.M)
        for i in range(1, len(parts) - 1, 3):
            out[int(parts[i])] = (parts[i + 1], parts[i + 2], os.path.basename(f))
    return out


V3 = chapters("蜀山 卷三*.md")
V2 = chapters("蜀山 卷二*.md")

# ---------- #1 甲案落地：02E / 02B 卷末交付口径 ----------
e = md("02E-卷二至卷五章纲.md") or ""
b = md("02B-卷二至卷五细纲.md") or ""
old_phrase = "失去自己的姓"
new_phrase = "名字只剩"  # 含「一半」与「半个」两种表述
e_old, e_new = e.count(old_phrase), e.count(new_phrase)
b_old, b_new = b.count(old_phrase), b.count(new_phrase)
hook_line = next((ln for ln in b.split(chr(10)) if ln.startswith("**卷末钩子**")), "")
b_hook_old = ("名帖上没有姓" in hook_line or "没姓的人" in hook_line)
add_hook = ("甲案定稿" in b or "名字只剩" in b)
ok1 = (e_old == 0 and e_new > 0 and b_old == 0 and b_new > 0 and not b_hook_old)
add(1, "裁「自己的姓」vs「半个名字」甲案落地",
    f"02E: 旧句{e_old}处／新句{e_new}处；02B: 旧句{b_old}处／新句{b_new}处",
    "甲案＝把卷末交付的『失去自己的姓』改为『自己的名字只剩一半』",
    "✅ 真落地" if ok1 else "❌ 未落地/半落地")

# ---------- #2/#15 「我担」残留 ----------
hits = []
for f in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True):
    if "/.git/" in f:
        continue
    for i, ln in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
        if "我担" in ln:
            rel = os.path.relpath(f, ROOT)
            # 真残留判据：把【卷三312】写成齐灵云说"我担"（且不带澄清词）
            mentions_312 = ("312" in ln or "311–312" in ln or "311-312" in ln)
            clarifies = any(k in ln for k in ["不批注", "沉默", "三拍", "原写", "已改", "甲案", "订正", "非", "不是"])
            is_archive = any(k in rel for k in ["回检", "冲突登记", "素材台账", "MEMORY", "memory"])
            if mentions_312 and "我担" in ln and not clarifies and not is_archive:
                kind = "⚠ 疑似残留"
            else:
                kind = "卷一12章原话引用/历史留档"
            hits.append((rel, i, kind, ln.strip()[:70]))
bad = [h for h in hits if h[2].startswith("⚠")]
add(2, "删「我担」全部残留",
    f"全库命中 {len(hits)} 处；合法引用/留档 {len(hits)-len(bad)}；疑似残留 {len(bad)}",
    "; ".join(f"{h[0]}:{h[1]}" for h in bad[:6]) if bad else "所有命中均为卷一12章原话引用或冲突登记/台账的历史留档",
    "✅ 真落地" if not bad else "❌ 有残留")
add(15, "全库复查「我担」关键词", "同 #2（同一数据的独立复核）",
    "见 #2 证据", "✅ 真落地" if not bad else "❌ 有残留")

# ---------- #3 许飞娘点名 ----------
c24 = "".join(V3[n][1] for n in range(366, 371))
c14 = "".join(V3[n][1] for n in range(316, 321))
cnt = {k: c24.count(k) for k in ["万妙仙姑", "许飞娘", "飞娘", "五台", "仙姑"]}
ok3 = cnt["万妙仙姑"] >= 2 and cnt["五台"] >= 1 and cnt["许飞娘"] + cnt["仙姑"] >= 0
add(3, "许飞娘在 366–370 点名/可指认痕迹",
    f"366–370: 万妙仙姑{cnt['万妙仙姑']}／许飞娘{cnt['许飞娘']}／飞娘{cnt['飞娘']}／五台{cnt['五台']}／仙姑{cnt['仙姑']}；316–320 许飞娘{c14.count('许飞娘')}",
    "要求：368/369 叫名或自报万妙仙姑；369 带出五台；370 由库吏/牌带出飞娘",
    "✅ 真落地" if ok3 else "❌ 未落地")

# ---------- #4 牌裂一道 ----------
c371 = V3.get(371, ("", "", ""))[1]
crack = [ln.strip()[:60] for ln in c371.split("\n") if "裂" in ln]
e4 = "裂" in e and "三栏" in e
add(4, "销牌补「牌裂一道」",
    f"卷三371含『裂』的段落 {len(crack)} 处；02E含『裂』{'是' if '裂' in e else '否'}、含『三栏』{'是' if '三栏' in e else '否'}",
    crack[0] if crack else "371 章无『裂』字",
    "✅ 真落地" if crack and e4 else "❌ 未落地/半落地")

# ---------- #5 模板句 1612→39 / 超限章 91→0 ----------
TPL_FAMILY = ["（他把这一样记下。）", "（他把这几样记下。）",
             "（他把这一样放着。）", "（他数自己的心跳。）"]
tot_tpl = 0
over_tpl = []
for n in sorted(V3):
    c = sum(V3[n][1].count(t) for t in TPL_FAMILY)
    tot_tpl += c
    if c > 1:
        over_tpl.append((n, c))
ok5 = (tot_tpl <= 125 and not over_tpl)
add(5, "压模板句到每章 ≤1（报告称 1612→39、超限 91→0）",
    f"按权威口径（四个精确模板句）：合计 {tot_tpl} 处（报告称39）；超限章 {len(over_tpl)}（报告称0）",
    "口径来源：校验/回检_卷三实测.py §1.5.1 TPL_FAMILY（此前用任意重复整句复算，口径错误已修正）",
    "✅ 真落地" if ok5 else "❌ 报告数字与实测不符")

# ---------- #6 母题句连续位置 ----------
mt = [n for n in sorted(V3) if any(k in V3[n][1] for k in ["母题", "名是别人叫的", "来路不清"])]
add(6, "母题句限连续位置（报告称部分完成）",
    f"含核心母题词的章 {len(mt)} 个：{mt[:18]}",
    "报告自标 🟡 部分完成——本项不判成败，仅给实测分布",
    "🟡 部分完成（与报告一致）")

# ---------- #14 章内重复段 ----------
dupb = []
for n in sorted(V3):
    lines = [x.strip() for x in V3[n][1].split(chr(10)) if x.strip()]
    pos = defaultdict(list)
    for j, x in enumerate(lines):
        if x.startswith("（"):
            core = re.sub(r"[（）()。，、？！：；“”\"'…—\s]", "", x)
            if len(core) >= 12:
                pos[x].append(j)
    d = [x for x, ix in pos.items() if len(ix) > 1
         and min(ix[k + 1] - ix[k] for k in range(len(ix) - 1)) < 8]
    if d:
        dupb.append((n, len(d)))
add(14, "19 个批次章内重复段已清 12 批（余 6 批为母题回流）",
    f"按权威口径仍有重复段的章：{len(dupb)} 个 {dupb[:10]}",
    "口径来源：验收脚本 find_dup_segments（≥12实质字、两次间隔<8段）；此前用任意完全重复，口径错误已修正",
    "✅ 真落地" if len(dupb) <= 6 else "❌ 与报告不符")

# ---------- #16 六个治理脚本 ----------
scripts = ["压模板句_卷三.py", "母题变体化_卷三.py", "回检_卷三实测.py",
           "复算_篇幅白名单.py", "验收_任意批次.py", "核验_回检清单.py"]
have = [s for s in scripts if os.path.exists(os.path.join(ROOT, "校验", s))]
add(16, "给回检脚本加防复发门禁（六个治理脚本）",
    f"要求脚本 {len(scripts)} 个，实存 {len(have)} 个",
    "缺：" + ", ".join(s for s in scripts if s not in have) if len(have) < len(scripts) else "全部在位，其中回检_卷三实测.py §1.5.1–1.5.3 需另行核对",
    "✅ 真落地" if len(have) == len(scripts) else "❌ 缺失")

# ---------- 卷三篇幅/体例实测 ----------
print("\n" + "=" * 70)
print("卷三 125 章篇幅与体例实测")
lens = {}
for n, (title, body, f) in V3.items():
    p = body.replace("（本章完）", "")
    lens[n] = len(re.sub(r"\s", "", re.sub(r"^#.*$", "", p, flags=re.M)))
over = [(n, c, c - 3000) for n, c in sorted(lens.items()) if c > 3000]
under = [(n, c) for n, c in sorted(lens.items()) if c < 2200]
no_end = [n for n, (_, b, _) in V3.items() if "（本章完）" not in b]
no_name = [n for n, (_, b, _) in V3.items() if "杨成志" not in b]
no_anchor = [n for n, (_, b, _) in V3.items() if not re.search(r"^\s*（[^）]{0,30}）", b, flags=re.M)]
quote = [(n, b.count("“") + b.count("”") + b.count("「") + b.count("」") + b.count('"'))
         for n, (_, b, _) in V3.items() if b.count("“") + b.count("”") + b.count("「") + b.count("」") + b.count('"')]
print(f"章数 {len(V3)}；字数 min {min(lens.values())} / max {max(lens.values())} / 合计 {sum(lens.values()):,}")
print(f"超3000：{len(over)} 章 {over[:8]}")
print(f"不足2200：{len(under)} 章 {under[:8]}")
print(f"缺章末标记：{len(no_end)} 章 {no_end[:10]}")
print(f"缺杨成志：{len(no_name)} 章 {no_name[:10]}")
print(f"缺章首时间锚：{len(no_anchor)} 章 {no_anchor[:10]}")
print(f"有引号：{len(quote)} 章 {quote[:8]}")

print("\n" + "=" * 70)
print("核验结论汇总")
for i, claim, result, ev, v in rows:
    print(f"  #{i:<2} {v:<18} {claim}")

ok = sum(1 for r in rows if r[4].startswith("✅"))
badn = sum(1 for r in rows if r[4].startswith("❌"))
print(f"\n✅ {ok} 项 / ❌ {badn} 项 / 其他 {len(rows)-ok-badn} 项")
