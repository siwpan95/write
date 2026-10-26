import re, io, itertools

files = [
    r"C:\Users\Administrator\Desktop\小说\第三卷\第97章-钥匙.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第98章-雨.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第99章-爬.txt",
]

forbidden = ["仿佛","宛如","好似","恰似","似乎","不由得","不由自主","不禁","微微","缓缓","静静地","悄然","默默","隐隐","淡淡","忽然间","猛然","一瞬间","刹那间","与此同时","然而","故而","总而言之","不难看出","值得注意","某种程度上","深深地","莫名的","难以言喻","眼中闪过","心头一紧","嘴角勾起","沉声道","映入眼帘","此时此刻"]

texts = {}
report = []
total = 0
for fp in files:
    with io.open(fp, "r", encoding="utf-8-sig") as f:
        text = f.read()
    if text.startswith("\ufeff"):
        print(f"WARN BOM: {fp}")
        text = text[1:]
    texts[fp] = text
    name = fp.replace("\\", "/").split("/")[-1]
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    title_line = text.split("\n", 1)[0]
    han_body = han - len(re.findall(r"[\u4e00-\u9fff]", title_line))
    total += han_body
    qchars = 0
    for ln in text.split("\n"):
        for m in re.findall(r"\u201c([^\u201d\u201c]*)\u201d", ln):
            qchars += len(m)
    nonspace = len(re.sub(r"\s", "", text))
    dia_pct = qchars / nonspace * 100
    dashes = text.count("——")
    ell = text.count("……")
    excl = text.count("！")
    terms = {t: text.count(t) for t in ["灰","辐射","废土","位面","虚空","沉默","整个","瞬间"]}
    hits = [w for w in forbidden if w in text]
    nb = len(re.findall(r"不是[^。，？\n]{1,20}而是", text))
    paras = [l for l in text.split("\n") if l.strip() and l.strip() != "===" and not l.startswith("第九十")]
    plens = [len(re.sub(r"\s", "", p)) for p in paras]
    over200 = [p for p in plens if p > 200]
    weak = sum(text.count(w) for w in ["微微","淡淡","缓缓","轻轻","悄然","默默","隐隐"])
    half_quote = text.count('"')
    half_comma = text.count(",")
    report.append(f"{name}: 汉字正文={han_body}, 对话占比={dia_pct:.1f}%, 破折号={dashes}, 省略号={ell}, 感叹号={excl}, 不是而是={nb}, 限用词freq={terms}, 禁用词命中={hits}, 弱化副词={weak}, 超长段(>200)={len(over200)}, 半角引号={half_quote}, 半角逗号={half_comma}")

def ngrams(s, n=12):
    s = re.sub(r"\s", "", s)
    return {s[i:i+n] for i in range(len(s)-n+1)}

prevs = {
    r"C:\Users\Administrator\Desktop\小说\第三卷\第93章-蓝与白.txt": "第93章(旧)",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第94章-秤.txt": "第94章(旧)",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第95章-冷库.txt": "第95章(旧)",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第96章-点二.txt": "第96章(旧)",
}
for fp, nm in prevs.items():
    with io.open(fp, "r", encoding="utf-8") as f:
        texts[fp] = f.read()
names = {fp: fp.replace("\\","/").split("/")[-1] for fp in list(files) + list(prevs.keys())}
dups = []
for a, b in itertools.combinations(list(texts.keys()), 2):
    common = ngrams(texts[a]) & ngrams(texts[b])
    if common:
        dups.append(f"{names.get(a,a)} <-> {names.get(b,b)}: {sorted(common)[:5]} ({len(common)} 处)")

print("\n".join(report))
print(f"本批合计汉字: {total}")
print("--- 12字逐字重复跨文件检查(含93-96章) ---")
print("\n".join(dups) if dups else "无")
