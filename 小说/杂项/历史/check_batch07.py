# -*- coding: utf-8 -*-
"""批次07质检：第109-111章"""
import re, itertools

FILES = [
    r"C:\Users\Administrator\Desktop\小说\第三卷\第109章-借来的手.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第110章-出卖.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第111章-枯索野.txt",
]
WEAK = ["微微", "淡淡", "缓缓", "轻轻", "悄然", "默默", "隐隐", "静静地"]
FORBID = ["仿佛", "似乎", "不由得", "不由自主", "难以言喻", "无法形容", "深深地",
          "莫名的", "禁不住", "不禁", "心中一凛", "心头一紧", "眼中闪过",
          "嘴角勾起", "与此同时", "就在此时", "如同", "宛如", "好似", "沉浸",
          "忽然间", "猛然", "空气中弥漫", "整个世界都", "不是由于", "之所以"]
KEYS = ["灰", "辐射", "废土", "位面", "沉默"]

texts = []
total = 0
print("=== 逐章指标 ===")
for p in FILES:
    t = open(p, encoding="utf-8").read()
    texts.append((p, t))
    han = len(re.findall(r"[\u4e00-\u9fff]", t))
    total += han
    dia = re.findall(r"“([^”]*)”", t)
    dc = sum(len(re.findall(r"[\u4e00-\u9fff]", d)) for d in dia)
    lines = [l.strip() for l in t.split("\n")
             if l.strip() and l.strip() != "===" and not re.match(r"^第[一二三四五六七八九十百]+章", l)
             and l.strip() != "---"]
    sents = []
    for l in lines:
        for s in re.split(r"[。！？]", l):
            s = s.strip()
            if s:
                n = len(re.findall(r"[\u4e00-\u9fff]", s))
                if n:
                    sents.append(n)
    mean = sum(sents) / len(sents)
    var = sum((s - mean) ** 2 for s in sents) / len(sents)
    cv = (var ** 0.5) / mean if mean else 0
    shortpct = sum(1 for s in sents if s <= 15) / len(sents) * 100
    longpar = [l for l in lines if len(re.findall(r"[\u4e00-\u9fff]", l)) > 200]
    print(f"\n{p.split(chr(92))[-1]}")
    print(f"  汉字 {han} | 对白 {dc/han*100:.1f}% | CV {cv:.3f} | 短句 {shortpct:.0f}% | 均句长 {mean:.1f}")
    print(f"  破折号 {t.count('——')} | 感叹号 {t.count('！')} | 省略号 {t.count('……')} | 半角引号 {t.count(chr(34))}")
    print(f"  >200字段落 {len(longpar)} | 不是 {t.count('不是')} | 禁用词 {[k for k in FORBID if t.count(k)]} | 弱化副词 {[k for k in WEAK if t.count(k)]}")
    print(f"  词频 " + " ".join(f"{k}:{t.count(k)}" for k in KEYS))
    # 感官
    sens = {"听": len(re.findall(r"声|响|听|音", t)), "触": len(re.findall(r"凉|冷|硬|软|黏|痛|烫|粗|滑", t)),
            "味": len(re.findall(r"咸|甜|酸|苦|辣|涩|汤|吃|喝", t)), "嗅": len(re.findall(r"味", t))}
    print(f"  感官 {sens}")

print(f"\n三章汉字合计 {total}")

# 跨章/同章 >=12 字逐字重复
print("\n=== 12字重复（同章+跨章）===")
hits = 0
for path, t in texts:
    han_seq = re.findall(r"[\u4e00-\u9fff]+", t)
    flat = "".join(han_seq)
    seen = {}
    for i in range(len(flat) - 11):
        g = flat[i:i + 12]
        if g in seen:
            print(f"  [同章] {path[-12:]} {g} @{seen[g]}/{i}")
            hits += 1
        else:
            seen[g] = i
for (pa, a), (pb, b) in itertools.combinations(texts, 2):
    fa = "".join(re.findall(r"[\u4e00-\u9fff]+", a))
    fb = "".join(re.findall(r"[\u4e00-\u9fff]+", b))
    for i in range(len(fa) - 11):
        g = fa[i:i + 12]
        if g in fb:
            print(f"  [跨章] {pa[-12:]}x{pb[-12:]} {g}")
            hits += 1
print(f"  合计 {hits} 处")
