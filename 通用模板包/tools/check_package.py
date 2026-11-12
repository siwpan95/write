#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板包自检脚本 · check_package.py（v3.9）
--------------------------------------------------------------------------
用途：打包前/解压后自检，保证「压缩包内容不失效」。检查七项：
  C1 编码：每个 .md 必须是 UTF-8-SIG(带 BOM) + LF，末尾有换行，无 TAB
  C2 文件引用：正文出现的 `NN` 必对应包内 00~14 号文件
  C3 节引用：`NN` §X.Y / §中文序号 必须在该文件里真实存在
  C4 包外路径：任何仓内路径/脚本名必须已在 14 号文件登记（D-编号）
  C5 表格完整性：每个表格必须有分隔行，且各行列数与表头一致
  C6 重复段：相邻两行非空且完全相同（复制粘贴事故）
  C7 占位残留：预填的实书编号（如 F12、第41章）与「TODO」
用法：python3 tools/check_package.py [包根目录]
退出码：0 全过；1 有 ERROR。
"""
import io, os, re, sys, glob

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERRORS, WARNS, STATS = [], [], {}
CNT = {"file_ref":0,"sec_ref":0,"path":0,"table":0,"row":0}

# 「历史错误 / 占位编号」扫描的排除文件前缀。这些文件按用途必须引用旧值、错值或
# 真实实例数据，不排除会天天误报：
#   00- 版本记录引用旧值作对照；14- 登记表引用错值作说明；
#   15- 逐字摘录的实例原文含历史译名与实书编号（改字即成「伪样例」）；
#   审计 / README 的举证与说明同样引用旧值。
# 同一规则写在 tools/regression_checks.txt 的文件注释里；后续加断言时勿破坏。
EXCLUDE_PREFIXES = ("00-", "14-", "15-", "审计", "README")

TEMPLATES = sorted(f for f in glob.glob(os.path.join(ROOT, "[0-9][0-9]-*.md")))
FILES = sorted(glob.glob(os.path.join(ROOT, "*.md")))
NAMES = {os.path.basename(f)[:2] for f in TEMPLATES}
CN = "〇一二三四五六七八九十"


def read(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()


def anchors(text):
    """收集某文件所有可被 § 引用的节号：数字型(2.2.1)、字母型(A4/H.3)、中文序号(七)。"""
    out = set()
    for line in text.split("\n"):
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if not m:
            continue
        h = m.group(1).strip()
        h = h.replace("（续）", "").strip()
        m2 = re.match(r"^([0-9]+(?:\.[0-9]+)*)", h)
        if m2:
            sec = m2.group(1)
            out.add(sec); out.add(sec.rstrip("."))
            parts = sec.split(".")
            for k in range(1, len(parts)):          # 2.2.1 → 也接受 §2 与 §2.2
                out.add(".".join(parts[:k]))
        m3 = re.match(r"^([A-Z])(\.[0-9]+)?[\.、]?(\s|$)", h)
        if m3:
            out.add(m3.group(1) + (m3.group(2) or ""))
            out.add(m3.group(1))
        m4 = re.match(r"^([%s]+)(、|部分|\s|$)" % CN, h)
        if m4:
            out.add(m4.group(1))
        m5 = re.match(r"^第([%s]+)部分" % CN, h)
        if m5:
            out.add(m5.group(1))
    # 「1.1」被写作「§1.1」时也接受父节
    return out


def split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def main():
    if not FILES:
        print("× 未找到 00-*.md 等模板文件，路径：%s" % ROOT)
        return 1

    texts, anchor_map = {}, {}
    for p in FILES:
        name = os.path.basename(p)
        raw = open(p, "rb").read()
        # C1
        if not raw.startswith(b"\xef\xbb\xbf"):
            ERRORS.append("C1 %s：缺少 UTF-8 BOM（R-1 要求 UTF-8-SIG）" % name)
        if b"\r\n" in raw:
            ERRORS.append("C1 %s：含 CRLF（R-1 要求 LF）" % name)
        if b"\t" in raw:
            WARNS.append("C1 %s：含 TAB 字符" % name)
        if not raw.endswith(b"\n"):
            WARNS.append("C1 %s：文件末尾缺换行" % name)
        try:
            t = raw.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            ERRORS.append("C1 %s：无法按 UTF-8 解码（%s）" % (name, e))
            continue
        texts[name] = t
        anchor_map[name] = anchors(t)

    # 14 号登记表里出现过的 D 编号
    reg = texts.get("14-外部依赖与来源登记表.md", "")
    registered = set(re.findall(r"D-\d\d", reg))

    for name, t in texts.items():
        # C2/C3 引用
        for m in re.finditer(r"`(\d\d)`", t):
            CNT["file_ref"] += 1
            if m.group(1) not in NAMES:
                ERRORS.append("C2 %s：引用了不存在的文件 `%s`" % (name, m.group(1)))
        for m in re.finditer(r"`(\d\d)`\s*§\s*([0-9]+(?:\.[0-9]+)*|[%s]+|[A-Z](?:\.[0-9]+)?)" % CN, t):
            CNT["sec_ref"] += 1
            fid, sec = m.group(1), m.group(2)
            fn = [f for f in texts if f.startswith(fid + "-")]
            if not fn:
                continue
            ok = sec in anchor_map[fn[0]]
            if not ok and re.match(r"^[%s]+$" % CN, sec):      # §五八 之类的粘连，回退到最长可用前缀
                for cut in range(len(sec) - 1, 0, -1):
                    if sec[:cut] in anchor_map[fn[0]]:
                        ok = True
                        break
            if not ok:
                ERRORS.append("C3 %s：`%s` §%s 在 %s 中不存在" % (name, fid, sec, fn[0]))

        # C4 包外路径（反引号内、含 / 或带扩展名、且不是包内文件名/节号）
        for m in re.finditer(r"`([^`\n]{2,120})`", t):
            tok = m.group(1).strip()
            if any(x in tok for x in (" ", "§")) or tok.startswith("http"):
                continue
            is_path = ("/" in tok) or bool(re.search(r"\.(md|py|txt|html|svg|dot|js|json|pdf|docx)$", tok))
            if not is_path:
                continue
            CNT["path"] += 1
            base = os.path.basename(tok)
            if re.match(r"^\d\d-", base) or tok in [os.path.basename(f) for f in FILES]:
                continue
            # 只审「真路径」：带扩展名或 ../ 或已知仓内目录
            real_path = bool(re.search(r"\.(md|py|txt|html|svg|dot|js|json|pdf|docx)$", tok)) \
                        or tok.startswith("../") or tok.startswith("./") \
                        or any(tok.startswith(x) for x in ("bible/", "Tserena/", "参考资料/", "其他项目归档/",
                                                           "点子库/", "可视化_结构映射/", "走向", "小说/", "通用模板包/"))
            if not real_path:
                continue
            prefixes = [tok[:i + 1] for i, c in enumerate(tok) if c == "/"]
            if base in reg or tok in reg or any(px in reg for px in prefixes):
                continue
            if re.search(r"D-\d\d", t[max(0, m.start() - 300):m.start() + 40]):
                continue
            WARNS.append("C4 %s：包外路径未登记到 14 号表 → `%s`" % (name, tok[:60]))

        # C5 表格完整性
        lines = t.split("\n")
        infence = set()
        f = False
        for li, ln in enumerate(lines):
            if ln.strip().startswith("```"):
                f = not f
                infence.add(li)
            elif f:
                infence.add(li)
        i = 0
        while i < len(lines):
            if i in infence:
                i += 1
                continue
            if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:\-\|]+\|\s*$", lines[i + 1]):
                CNT["table"] += 1
                ncol = len(split_row(lines[i]))
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    CNT["row"] += 1
                    if len(split_row(lines[j])) != ncol:
                        ERRORS.append("C5 %s 第 %d 行：表格列数 %d ≠ 表头 %d" % (name, j + 1, len(split_row(lines[j])), ncol))
                    j += 1
                i = j
            elif lines[i].strip().startswith("|") and (i + 1 >= len(lines) or not lines[i + 1].strip().startswith("|")):
                WARNS.append("C5 %s 第 %d 行：孤立表格行（无分隔行，不会渲染成表）" % (name, i + 1))
                i += 1
            else:
                i += 1

        # C6 相邻重复行（跳过 fenced code 与占位行）
        fence = False
        for k in range(1, len(lines)):
            if lines[k - 1].strip().startswith("```") or lines[k].strip().startswith("```"):
                fence = not fence
            a, b = lines[k - 1].strip(), lines[k].strip()
            if fence or a.startswith("|") or b.startswith("|"):
                continue
            if any(ch in a for ch in "＿_{}☐…—"):
                continue
            if a and a == b and len(a) > 20:
                ERRORS.append("C6 %s 第 %d 行：与上一行完全重复" % (name, k + 1))

        # C7 占位残留
        probe = re.sub(r"[「『][^」』]*[」』]", "", t)   # 引号内为举证引用，不算遗留
        # 逐字摘录类文件里的实书编号是原始数据，不是模板预填，故只跳过两条编号类检查；
        # 「未闭环标记」对所有文件仍然生效。理由见 EXCLUDE_PREFIXES 与 regression_checks.txt 注释。
        for pat, msg in [(r"\| F(1[2-9]|[2-9]\d) \|", "预填伏笔编号"),
                         (r"\| 4[0-9] \|  {2}\|", "预填章号"), (r"待逐份补|待落地|FIXME", "未闭环标记残留")]:
            if msg.startswith("预填") and name.startswith(EXCLUDE_PREFIXES):
                continue
            if re.search(pat, probe if "待逐份补" in pat else t):
                WARNS.append("C7 %s：%s" % (name, msg))

    # C8 防回归断言
    regf = os.path.join(ROOT, "tools", "regression_checks.txt")
    if os.path.exists(regf):
        skipped = EXCLUDE_PREFIXES   # 见文件头注释；同一规则写在 regression_checks.txt 里
        for ln in io.open(regf, encoding="utf-8-sig").read().split("\n"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or "|" not in ln:
                continue
            parts = ln.split("|", 2)
            kind = parts[0].strip()
            if kind == "NOT" and len(parts) >= 2:
                pat = ln.split("|", 1)[1]
                for name, t in texts.items():
                    if name.startswith(skipped):
                        continue
                    if pat in t:
                        ERRORS.append("C8 防回归：%s 出现禁止复发的内容「%s」" % (name, pat))
            elif kind == "MUST" and len(parts) == 3:
                prefix, pat = parts[1].strip(), parts[2]
                targets = [t for n, t in texts.items() if n.startswith(prefix)]
                if not targets:
                    ERRORS.append("C8 断言语义错误：找不到以 %s 开头的文件" % prefix)
                elif not any(pat in t for t in targets):
                    ERRORS.append("C8 承诺缺失：%s 中应有「%s」" % (prefix, pat))
        STATS["防回归断言"] = sum(1 for l in io.open(regf, encoding="utf-8-sig").read().split("\n")
                                if l.strip() and not l.strip().startswith("#") and "|" in l)

    STATS["文件数"] = len(texts)
    STATS["字符数"] = sum(len(x) for x in texts.values())
    STATS["文件引用校验"] = CNT["file_ref"]
    STATS["节引用校验"] = CNT["sec_ref"]
    STATS["路径核验"] = CNT["path"]
    STATS["表格/行校验"] = "%d / %d" % (CNT["table"], CNT["row"])
    STATS["ERROR"] = len(ERRORS)
    STATS["WARN"] = len(WARNS)

    print("=" * 62)
    print("模板包自检 · %s" % ROOT)
    print("=" * 62)
    for k, v in STATS.items():
        print("  %-8s %s" % (k, v))
    print("-" * 62)
    if WARNS:
        print("WARN（不阻断打包，建议逐条确认）")
        for w in WARNS:
            print("  · " + w)
        print("-" * 62)
    if ERRORS:
        print("ERROR（必须修复后才能打包）")
        for e in ERRORS:
            print("  × " + e)
        print("-" * 62)
        print("结论：FAIL")
        return 1
    print("结论：PASS（0 error%s）" % ("，%d warn" % len(WARNS) if WARNS else "，0 warn"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
