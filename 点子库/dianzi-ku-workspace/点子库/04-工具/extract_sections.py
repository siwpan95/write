# -*- coding: utf-8 -*-
"""从原始对话存档中抽取各章正文，清理噪声，生成独立 Markdown 文件。"""
import re
import os

SRC = "/sandbox/workspace/uploads/法则超能力.txt"
OUT = "/sandbox/workspace/output/法则权能设定集"
os.makedirs(OUT, exist_ok=True)

with open(SRC, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")

# 章节定义：(文件名, 标题, 副标题, 起始行(1-based), 结束行(含), None=到文件尾)
SECTIONS = [
    ("01-核心设定-法则权能.md", "核心设定 · 法则权能体系",
     "法则不是知识，而是世界的接口；掌握一条法则，即获得该法则的权能。",
     169, 231),
    ("02-GURPS机制深化.md", "GURPS 4e 机制深化",
     "一条法则 = 一个 Power：来源、焦点、五阶优势组、点数化与法则冲突规则。",
     258, 365),
    ("03-现实世界科学基础.md", "现实世界科学基础",
     "社会物理学、社会算子、信任阈值 τ*=0.68、兰道尔极限、幂律标度为体系提供实证支撑。",
     391, 503),
    ("04-边界理论.md", "边界理论",
     "现实与超凡之间不是一堵墙，而是一系列可被逼近、局部跨越、但永远无法取消的临界条件。",
     561, 599),
    ("05-边界之外的存在-创造主.md", "边界之外的存在 · 创造主",
     "卡巴拉 Ein Sof/Tzimtzum、诺斯替迪缪尔哥斯、洪荒圣人三传统；GURPS 的 Omnilock 与 Aseity。",
     624, 720),
    ("06-完整设定集-总纲.md", "完整设定集 · 总纲",
     "底层架构 → 现实基础 → 边界理论 → 边界之外 → GURPS 点数化 → 叙事整合（全体系一册贯通）。",
     768, 1017),
    ("07-D&D标尺与量级单位.md", "D&D 挑战等级/神力等级与量级单位",
     "CR 0–30、神力等级 0–21+（艾欧）、五阶细分三子阶、FP/KFP/MFP/GFP/TFP/Ω 单位体系。",
     1036, None),
]

# ---------- 噪声清理 ----------
NOISE_LINE = re.compile(
    r"^(已思考（用时.*|搜索到\s*\d+\s*个网页|浏览\s*\d+\s*(个)?页面|"
    r"本回答由 AI 生成.*|查看全部|\d+\s*个网页|CONTENTS|POWERS)\s*$"
)
# 引文尾注：如 相变-57、证伪标准-。、优势-17（排除数值范围 -3至-5、百分比 -20% 等）
CITE_TAIL = re.compile(r"(?<=[^\d+至\-~％%])-\d{1,3}(?=[，。、；：）)\s]|$)")
CITE_DASH = re.compile(r"-(?=[。，、；：）])")
TRAIL_DASH = re.compile(r"-\s*$", re.M)
MATH_JUNK_RUN = re.compile(r"(?:\n[ \t]*[kTln⁡2][ \t]*){3,}")


def clean(text: str) -> str:
    text = text.replace("\r", "")
    text = MATH_JUNK_RUN.sub("", text)          # LaTeX 换行残渣
    text = CITE_TAIL.sub("", text)
    text = CITE_DASH.sub("", text)
    text = TRAIL_DASH.sub("", text)
    return text


def tabs_to_mdtables(text: str) -> str:
    """把连续的制表符行转换为 Markdown 表格。"""
    out, buf = [], []

    def flush():
        if not buf:
            return
        if len(buf) == 1:
            out.append(buf[0])
        else:
            cells = [c.strip() for c in buf[0].split("\t")]
            out.append("| " + " | ".join(cells) + " |")
            out.append("|" + "---|" * len(cells))
            for row in buf[1:]:
                cs = [c.strip() for c in row.split("\t")]
                # 对齐列数
                cs += [""] * (len(cells) - len(cs))
                out.append("| " + " | ".join(cs[:len(cells)]) + " |")
        buf.clear()

    for line in text.split("\n"):
        if "\t" in line and line.count("\t") >= 1 and not line.startswith("    "):
            buf.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


for fname, title, subtitle, start, end in SECTIONS:
    seg = lines[start - 1: end if end else len(lines)]
    # 去掉行内噪声行
    seg = [l for l in seg if not NOISE_LINE.match(l.strip())]
    text = "\n".join(seg)
    text = clean(text)
    text = tabs_to_mdtables(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    header = f"# {title}\n\n> {subtitle}\n\n---\n\n"
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
        f.write(header + text + "\n")
    print(f"{fname}: {len(text)} chars")
