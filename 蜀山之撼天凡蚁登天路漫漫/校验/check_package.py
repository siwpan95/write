#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《蜀山佚卷》实填包自检脚本：只读，不改文件。输出 校验/校验报告.txt。"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "校验", "校验报告.txt")

REQUIRED = (
    ["README.md", "00-总档与SOP.md", "07-附录-实例索引.md"]
    + [f"{i:02d}" for i in (1, 2, 3, 4, 5, 6, 8, 9)]
    + ["09"]
    + [str(i) for i in range(10, 15)]
    + [str(i) for i in range(16, 20)]
)
REQUIRED = sorted(set(REQUIRED))

SAMPLE_DRIFT = ["烬地", "废土旅法师", "奇门遁甲", "【本书范例】", "魏成河"]
OUTSIDE = ["/uploads/", "D:\\", "../", ".sources", "包外，见 `14`"]

errors, warns, lines = [], [], []


def add(kind, msg):
    (errors if kind == "E" else warns).append(msg)
    lines.append(f"[{kind}] {msg}")


def md_files():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("模板原件", "校验")]
        for f in files:
            if f.endswith(".md"):
                out.append(os.path.join(base, f))
    return sorted(out)


def main():
    # 1 文件齐备
    found = {os.path.basename(p) for p in md_files()}
    for i in range(1, 20):
        pref = f"{i:02d}-"
        hits = [n for n in found if n.startswith(pref)]
        if i == 15:
            lines.append("[i] 15-填法样例集：模板维护资料，按规范不分发（已登记）")
            continue
        if not hits:
            add("E", f"缺少 {pref}*.md")
    for must in ("README.md", "00-总档与SOP.md"):
        if must not in found:
            add("E", f"缺少 {must}")

    # 2 占位符 / 样本倒灌 / 包外路径
    for p in md_files():
        rel = os.path.relpath(p, ROOT)
        try:
            text = open(p, encoding="utf-8").read()
        except UnicodeDecodeError:
            add("E", f"{rel} 非 UTF-8 编码")
            continue
        n_blank = text.count("＿＿")
        if n_blank:
            if rel.startswith("17-") and n_blank <= 2:
                add("i", f"{rel} 含 {n_blank} 处 ＿＿（引文占位，白名单）")
            else:
                add("E", f"{rel} 残留占位符 ＿＿ × {n_blank}")
        for w in SAMPLE_DRIFT:
            if w in text:
                add("E", f"{rel} 出现模板样本倒灌词：{w}")
        for w in OUTSIDE:
            if w in text:
                add("E", f"{rel} 出现包外路径/未改写引用：{w}")
        if not text.startswith("# "):
            add("W", f"{rel} 首行不是一级标题")
        if "模板 · v3" in text or "本份模板 · 变更记录" in text:
            add("W", f"{rel} 似残留模板变更记录")

    # 3 编号域
    p13 = os.path.join(ROOT, "13-世界先行与地图叙事.md")
    if os.path.exists(p13):
        t = open(p13, encoding="utf-8").read()
        bad = re.findall(r"`F-0[1-5]`", t)
        if bad:
            add("E", f"13 号文件仍有与事实编号撞号的势力编号：{len(bad)} 处")
        if "FAC-01" not in t:
            add("W", "13 号文件未见 FAC-01，势力编号可能未统一")
    p19 = os.path.join(ROOT, "19-供给过剩与资产经营.md")
    if os.path.exists(p19):
        t = open(p19, encoding="utf-8").read()
        if re.search(r"`S-0\d`", t):
            add("E", "19 号文件仍有与检索来源撞号的 S-0x")
        if "PL-01" not in t:
            add("W", "19 号文件未见 PL-01，平台事实编号可能未统一")

    # 4 章号口径（v2.1 修正）
    # 历史：v1→v2 迁移期曾用「全文字符串匹配『第 178 章』即报错」的临时规则，
    # 该规则生成于 2026-11-15，早于卷二正文落稿（11-17），把卷二合法的
    # 第 178 章（对应原著第 211 回）误判为失效章号。改为按章号域精确校验。
    #
    # 合法章号域：
    #   主体连载区  1–225   （卷一 1–125 / 卷二 126–225）
    #   卷六结局场  726–750（10A-卷六结局场节拍.md）
    VALID_RANGES = [(1, 225), (726, 750)]
    # 文件名直接标注章号的，视为“章节实体文件”，跳过正文内引用校验
    chap_re = re.compile(r"^# 第 (\d+) 章")
    for p in md_files():
        rel = os.path.relpath(p, ROOT)
        t = open(p, encoding="utf-8").read()
        # 只校验正文文件的章节标题行；文档中的章节引用（如“第 178 章”）合法
        for line in t.splitlines():
            m = chap_re.match(line)
            if not m:
                continue
            n = int(m.group(1))
            if not any(lo <= n <= hi for lo, hi in VALID_RANGES):
                add("E", f"{rel} 章节标题章号 {n} 越界（合法域 1–225 / 726–750）")


    # 6 v2 主角改判专项：旧主角/旧书名/旧卷问题句必须清零
    for w in ["沈砚", "《蜀山佚卷》", "我替谁写", "我从哪来", "我替哪一边写", "冷幽默低配比", "半文半白的减法"]:
        for p2 in md_files():
            rel = os.path.relpath(p2, ROOT)
            if w in open(p2, encoding="utf-8").read():
                add("E", f"{rel} 残留 v1 旧表述：{w}")
    # 主角名应出现在核心分册
    for name in ["01-立项定位.md", "02-大纲四层.md", "04-人物卡.md", "10-节拍表与黄金三章.md", "13-世界先行与地图叙事.md"]:
        p2 = os.path.join(ROOT, name)
        if os.path.exists(p2) and "杨成志" not in open(p2, encoding="utf-8").read():
            add("E", f"{name} 未出现主角名（应为杨成志）")

    # 7 MANIFEST 覆盖率与哈希（2026-11-18 追加）
    # 起因：MANIFEST 曾在正文加"蜀山 "前缀后未同步，导致 15 条路径失效、
    # 2 条哈希过期、28 个文件未收录——整体形同虚设，而 README §四 教的
    # `sha256sum -c` 自验一直在骗人。此项专门兜住该缺口。
    man_path = os.path.join(ROOT, "校验", "MANIFEST.sha256")
    if os.path.exists(man_path):
        man = {}
        for raw in open(man_path, encoding="utf-8"):
            raw = raw.rstrip("\n")
            if not raw.strip() or raw.startswith("#"):
                continue
            m = re.match(r"^([0-9a-f]{64})\s+(.*?)\s*$", raw)
            if m:
                man[m.group(2).lstrip("./")] = m.group(1)
            else:
                add("E", f"MANIFEST.sha256 有 1 行格式不合规：{raw[:60]}")
        # 实际文件（排除校验/ 自身与备份）
        actual = {}
        for r, _d, fs in os.walk(ROOT):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), ROOT).replace("\\", "/")
                if rel.startswith("校验/"):
                    continue
                if ".bak-" in rel:
                    continue
                actual[rel] = os.path.join(r, f)
        missing = sorted(set(actual) - set(man))
        ghost = sorted(set(man) - set(actual))
        for p in missing:
            add("E", f"MANIFEST 未收录：{p}")
        for p in ghost:
            add("E", f"MANIFEST 条目无对应文件：{p}")
        for p, h in man.items():
            if p in actual:
                d = hashlib.sha256(open(actual[p], "rb").read()).hexdigest()
                if d != h:
                    add("E", f"MANIFEST 哈希不符：{p}")
    else:
        add("E", "缺少 校验/MANIFEST.sha256")

    # 5 统计
    total_bytes = sum(os.path.getsize(p) for p in md_files())
    lines.append("")
    lines.append(f"[i] 扫描 Markdown：{len(md_files())} 份；合计 {total_bytes/1024:.0f} KB")
    lines.append(f"[i] error = {len(errors)}；warn = {len(warns)}")
    verdict = "PASS：可分发" if not errors else "FAIL：须修复后重跑"
    lines.append(f"[i] 结论：{verdict}")

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("《蜀山佚卷》实填包 · 自动校验报告\n")
        f.write("生成时间：2026-11-15\n")
        f.write("=" * 56 + "\n")
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
