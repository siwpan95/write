import re, sys, io

files = [
    r"C:\Users\Administrator\Desktop\小说\第三卷\第91章-灰线.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第92章-第一课.txt",
    r"C:\Users\Administrator\Desktop\小说\第三卷\第93章-蓝与白.txt",
]

forbidden = ["仿佛","宛如","好似","恰似","似乎","不由得","不由自主","不禁","微微","缓缓","静静地","悄然","默默","隐隐","淡淡","忽然间","猛然","一瞬间","刹那间","与此同时","然而","故而","总而言之","不难看出","值得注意","某种程度上","深深地","莫名的","难以言喻","眼中闪过","心头一紧","嘴角勾起","沉声道","映入眼帘","此时此刻"]

texts = {}
report = []
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
    # dialogue: proper per-line pairing
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
    report.append(f"{name}: 汉字正文={han_body}, 对话占比={dia_pct:.1f}%, 破折号={dashes}, 省略号={ell}, 感叹号={excl}, 不是而是={nb}, 限用词freq={terms}, 禁用词命中={hits}, 弱化副词总数={weak}, 超长段(>200)={len(over200)}")

# 12-gram cross-dup check among the three files + vol2 ch90
import itertools
def ngrams(s, n=12):
    s = re.sub(r"\s", "", s)
    return {s[i:i+n] for i in range(len(s)-n+1)}
extra = r"C:\Users\Administrator\Desktop\小说\第二卷\第90章-第二个光点.txt"
with io.open(extra, "r", encoding="utf-8") as f:
    texts["_ch90"] = f.read()
names = {fp: fp.replace("\\","/").split("/")[-1] for fp in files}
names["_ch90"] = "第90章(旧)"
keys = list(texts.keys())
dups = []
for a, b in itertools.combinations(keys, 2):
    common = ngrams(texts[a]) & ngrams(texts[b])
    if common:
        dups.append(f"{names.get(a,a)} <-> {names.get(b,b)}: {sorted(common)[:5]} ({len(common)} 处)")

print("\n".join(report))
print("--- 12字逐字重复跨文件检查 ---")
print("\n".join(dups) if dups else "无")
