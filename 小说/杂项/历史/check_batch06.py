# -*- coding: utf-8 -*-
"""批次06质检：第106-108章"""
import re, glob

FILES = {
    "106": r"C:\Users\Administrator\Desktop\小说\第三卷\第106章-名字.txt",
    "107": r"C:\Users\Administrator\Desktop\小说\第三卷\第107章-北.txt",
    "108": r"C:\Users\Administrator\Desktop\小说\第三卷\第108章-门后.txt",
}
WEAK = ["微微", "淡淡", "缓缓", "轻轻", "悄然", "默默", "隐隐", "静静地"]
FORBID = ["仿佛", "似乎", "不由得", "不由自主", "难以言喻", "无法形容", "深深地", "莫名的", "禁不住", "不禁", "心中一凛", "心头一紧", "眼中闪过", "嘴角勾起", "与此同时", "就在此时", "如同", "宛如", "好似", "沉浸", "忽然间", "猛然"]
KEYS = ["灰", "辐射", "废土", "位面", "沉默"]

total_h = 0
texts = {}
for ch, path in FILES.items():
    text = open(path, encoding="utf-8").read()
    texts[ch] = text
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_all = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef0-9A-Za-z％]", text))
    dia = re.findall(r"“([^”]*)”", text)
    dia_chars = sum(len(re.findall(r"[\u4e00-\u9fff]", d)) for d in dia)
    dia_pct = dia_chars / han * 100 if han else 0
    dash = text.count("——")
    excl = text.count("！")
    ell = text.count("……")
    lines = [l.strip() for l in text.split("\n") if l.strip() and l.strip() != "===" and not re.match(r"^第[一二三四五六七八九十百]+章", l)]
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
    long_par = [l for l in lines if len(re.findall(r"[\u4e00-\u9fff]", l)) > 200]
    total_h += han
    print(f"=== 第{ch}章 ===")
    print(f"汉字数: {han} | 含标点字符约: {total_all} | 对白占比: {dia_pct:.1f}% (对白汉字{dia_chars})")
    print(f"句数: {len(sents)} | 平均句长: {mean:.1f} | 错落度CV: {cv:.2f} | 短句占比: {short_pct:.0f}% | >200字段: {len(long_par)}")
    print(f"破折号: {dash} (≤3) | 感叹号: {excl} (≤2) | 省略号: {ell}")
    for w in WEAK:
        c = text.count(w)
        if c:
            print(f"  弱化副词 {w}: {c}")
    hits = [w for w in FORBID if w in text]
    if hits:
        print(f"  ⚠禁用词命中: {hits}")
    for k in KEYS:
        c = text.count(k)
        lim = {"灰": 6, "辐射": 6, "废土": 5, "位面": 6, "沉默": 2}[k]
        flag = " ⚠超限" if c > lim else ""
        print(f"  '{k}': {c} (≤{lim}){flag}", end="; ")
    print()
    if '"' in text or "'" in text:
        print("  ⚠存在半角引号")
    n_ab = len(re.findall(r"不是[^。，？”]{1,12}[，。][^”]{0,4}是", text))
    print(f"  '不是…是…'结构约: {n_ab}")
    print()

print(f"三章合计汉字: {total_h}")

# 12字滑窗跨章查重：本批 vs 全书既有章节
def han_str(s):
    return "".join(re.findall(r"[\u4e00-\u9fff]", s))

all_prev = []
for pat in [r"C:\Users\Administrator\Desktop\小说\第一卷\*.txt", r"C:\Users\Administrator\Desktop\小说\第二卷\*.txt", r"C:\Users\Administrator\Desktop\小说\第三卷\*.txt"]:
    all_prev += [p for p in glob.glob(pat) if p not in FILES.values()]

prev_blobs = {}
for p in all_prev:
    prev_blobs[p] = han_str(open(p, encoding="utf-8").read())

def window12(s):
    return {s[i:i+12] for i in range(len(s) - 11)}

print("\n=== 12字逐字重复检查（本批 vs 既有全书 + 本批内部） ===")
for ch, text in texts.items():
    h = han_str(text)
    ws = window12(h)
    dup_total = 0
    for p, blob in prev_blobs.items():
        dups = ws & window12(blob)
        if dups:
            dup_total += len(dups)
            for d in list(dups)[:3]:
                print(f"  第{ch}章 ↔ {p.splitlines() and p.split(chr(92))[-1]}: “{d}”")
    print(f"  第{ch}章 vs 既有章节: {dup_total} 处")

w106, w107, w108 = (window12(han_str(texts[c])) for c in ("106", "107", "108"))
print(f"  106↔107: {len(w106 & w107)} 处 | 106↔108: {len(w106 & w108)} 处 | 107↔108: {len(w107 & w108)} 处")
