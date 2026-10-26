# -*- coding: utf-8 -*-
"""批次05质检：第103-105章"""
import re, sys

FILES = {
    "103": r"C:\Users\Administrator\Desktop\小说\第三卷\第103章-铁手的账.txt",
    "104": r"C:\Users\Administrator\Desktop\小说\第三卷\第104章-底料.txt",
    "105": r"C:\Users\Administrator\Desktop\小说\第三卷\第105章-在册.txt",
}
WEAK = ["微微", "淡淡", "缓缓", "轻轻", "悄然", "默默", "隐隐", "静静地"]
FORBID = ["仿佛", "似乎", "不由得", "不由自主", "难以言喻", "无法形容", "深深地", "莫名的", "禁不住", "不禁", "心中一凛", "心头一紧", "眼中闪过", "嘴角勾起", "与此同时", "就在此时", "如同", "宛如", "好似", "沉浸"]
KEYS = ["灰", "辐射", "废土", "位面", "沉默"]

total_h = 0
for ch, path in FILES.items():
    text = open(path, encoding="utf-8").read()
    body_lines = [l for l in text.split("\n") if l.strip() and not l.startswith("第") or ch in l]
    # count chars
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_all = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef0-9A-Za-z％]", text))
    # dialogue: inside “”
    dia = re.findall(r"“([^”]*)”", text)
    dia_chars = sum(len(re.findall(r"[\u4e00-\u9fff]", d)) for d in dia)
    dia_pct = dia_chars / han * 100 if han else 0
    # punctuation
    dash = text.count("——")
    excl = text.count("！")
    ell = text.count("……")
    # sentence length CV (exclude title, ===)
    lines = [l.strip() for l in text.split("\n") if l.strip() and l.strip() != "===" and not l.startswith("第一百")]
    sents = []
    for l in lines:
        for s in re.split(r"[。！？]", l):
            s = s.strip()
            if s:
                sents.append(len(re.findall(r"[\u4e00-\u9fff]", s)))
    sents = [s for s in sents if s > 0]
    mean = sum(sents) / len(sents)
    var = sum((s - mean) ** 2 for s in sents) / len(sents)
    cv = (var ** 0.5) / mean if mean else 0
    short_pct = sum(1 for s in sents if s <= 15) / len(sents) * 100
    total_h += han
    print(f"=== 第{ch}章 ===")
    print(f"汉字数: {han} | 含标点字符约: {total_all} | 对白占比: {dia_pct:.1f}% (对白汉字{dia_chars})")
    print(f"句数: {len(sents)} | 平均句长: {mean:.1f} | 错落度CV: {cv:.2f} | 短句占比: {short_pct:.0f}%")
    print(f"破折号: {dash} (≤3) | 感叹号: {excl} (≤2) | 省略号: {ell}")
    for w in WEAK:
        c = text.count(w)
        if c:
            print(f"  弱化副词 {w}: {c} (全章≤3)")
    hits = [w for w in FORBID if w in text]
    if hits:
        print(f"  ⚠禁用词命中: {hits}")
    for k in KEYS:
        c = text.count(k)
        print(f"  '{k}': {c}", end="")
        lim = {"灰": 6, "辐射": 6, "废土": 5, "位面": 6, "沉默": 2}[k]
        print(f" (≤{lim})" + (" ⚠超限" if c > lim else ""))
    # half-width quotes
    if '"' in text or "'" in text:
        print("  ⚠存在半角引号")
    if "不是" in text:
        n_ab = len(re.findall(r"不是[^。，”]{1,12}[，。][^”]{0,4}是", text))
        print(f"  '不是…是…'结构约: {n_ab} (≤1-2/千字区间内即可)")
    print()

print(f"三章合计汉字: {total_h}")
