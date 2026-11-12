# -*- coding: utf-8 -*-
"""《法则权能》单文件 TXT 合集生成器 · 作家助手导入版（2026-11-12 改）

用途
----
作家助手导入只支持 txt / word，逐章手动导入太慢，故出合订版。
旧版把「说明头 + 202 行目录 + ════ 分隔线 + 中文数字章名 + 章首索引卡台账
+ 8 篇设定资料」混进同一文本，导入器按「第N章」切章时会把目录项当成章节、
把无章号的资料并进相邻章，章序因此错乱。

本版按仓内真实导出物「其他项目归档/战锤42：拔智齿-第一卷 鲜衣怒马少年时.txt」
（作家助手导出的正文）逐项对齐：
  · 书名/卷名单独一行（参考：第一卷 鲜衣怒马少年时）
  · 每章一行「第N章 标题」，阿拉伯数字，行首无缩进，章间不留空行
  · 正文每段以两个全角空格「　　」缩进，全文不出现空行、分隔线、Markdown 残留
  · 元信息头 / 目录 / 装饰线一律不进正文（工作区规范.md §六：正文文件只含标题行 + 纯正文）

章号规则
--------
  · 序章 → 第0章（仅为让平台单独切出一章；导入后可改名为「序章」）
  · 第一~一百九十三章 → 第1章~第193章，与原书章号一一对应（已核验严格连续）
  · 8 篇非章节资料（路径树 / 分支短章 / 支线 POV 集 ×5 / 索引卡）默认不并入；
    --include-appendix 可把它们按原顺序追加为末尾「第194章 附录 …」~「第201章 附录 …」，
    章号仍严格递增，不干扰主线。

用法
----
  python build_txt_collection.py                         # 重建 02-正文/法则权能-正文合集.txt（BOM + LF）
  python build_txt_collection.py --include-appendix     # 末尾追加 8 篇资料为附录章
  python build_txt_collection.py --mapping              # 只打印 导入章号 ↔ 原书章号 ↔ 源文件 对照
  python build_txt_collection.py --reading --out X.txt  # 生成带目录的阅读版（需显式给路径）
  python build_txt_collection.py --crlf --out X.txt     # 输出 CRLF / 无 BOM 的平台交换副本（对齐参考导出物）

--crlf 产物为平台交换用副本，请勿提交入库；复跑默认参数即可还原入库版（UTF-8-SIG + LF）。
脚本路径基于自身位置推导，不含硬编码绝对路径，可随仓移动。
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "02-正文"))
DEFAULT_OUT = os.path.join(SRC, "法则权能-正文合集.txt")
BOOK_TITLE = "法则权能"
INDENT = "\u3000\u3000"
BOM = bytes([0xEF, 0xBB, 0xBF])
BAR = "═" * 40
RULE = "—" * 12

CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}
CN_CHARS = "零〇一二三四五六七八九十百千两"


def cn2num(s):
    """中文数字（一~一百九十三）转阿拉伯数字。"""
    total, cur = 0, 0
    for ch in s:
        if ch in CN_DIGIT:
            cur = CN_DIGIT[ch]
        elif ch in CN_UNIT:
            total += (cur or 1) * CN_UNIT[ch]
            cur = 0
    return total + cur


def collect():
    """按文件名数字前缀收集 02-正文 下全部 .md（排除 README 与自身产物）。"""
    entries = []
    for name in os.listdir(SRC):
        if not name.endswith(".md") or name == "README-创作说明.md":
            continue
        m = re.match(r"^(\d+)-", name)
        if not m:
            continue
        path = os.path.join(SRC, name)
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().split("\n")
        entries.append((int(m.group(1)), name, lines))
    entries.sort(key=lambda x: x[0])
    return entries


def first_heading(lines):
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("#"):
            return i, re.sub(r"^#+\s*", "", ln.strip()).replace("**", "").strip()
    return -1, ""


def split_label(text):
    """「第一百章 · 复习」→ ('第一百章', '复习')；「序章 · 膜」→ ('序章', '膜')。"""
    parts = [p.strip() for p in re.split(r"\s*[·・]\s*", text) if p.strip()]
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def classify(label):
    if label.startswith("序章"):
        return "prologue"
    if re.match(r"^第[" + CN_CHARS + r"]+章$", label):
        return "chapter"
    return "appendix"


def chapter_number(label, kind):
    if kind == "prologue":
        return 0
    return cn2num(re.match(r"^第([" + CN_CHARS + r"]+)章$", label).group(1))


def is_struct(t):
    """结构行：空行 / 水平线 / Markdown 标题 / 代码块围栏。"""
    if not t:
        return True
    if t in ("---", "***", "___"):
        return True
    if re.match(r"^#{1,6}(\s|$)", t):
        return True
    if t.startswith("```"):
        return True
    return False


def plain_text(ln):
    """把一行 Markdown 正文还原为纯文本；不改写措辞，只去格式标记。"""
    s = ln.rstrip("\r\n")
    s = re.sub(r"^>\s?", "", s.lstrip())
    s = re.sub(r"^-\s+\[[ xX]\]\s*", "", s)   # 台账勾选框
    s = s.replace("**", "")
    return s.strip()


def body_lines(lines, heading_idx):
    """生成一章的全角缩进段落；整体剔除章首「## 本章索引卡」台账块。"""
    body = []
    in_card = False
    for ln in lines[heading_idx + 1:]:
        t = ln.strip()
        if t == "## 本章索引卡":
            in_card = True
            continue
        if in_card:
            # 台账块以水平线或下一个 Markdown 标题结束；两者本身也不输出
            if t == "---" or re.match(r"^#{1,6}(\s|$)", t):
                in_card = False
            continue
        if is_struct(t):
            continue
        s = plain_text(ln)
        if s:
            body.append(INDENT + s)
    return body


def build_chapters(include_appendix):
    chapters, appendix = [], []
    for num, name, lines in collect():
        hidx, text = first_heading(lines)
        label, sub = split_label(text)
        kind = classify(label)
        if kind == "appendix":
            appendix.append((num, name, label, sub, lines, hidx))
            continue
        n = chapter_number(label, kind)
        head = "第%d章 %s" % (n, (label + " " + sub).strip() if kind == "prologue" else sub)
        chapters.append((n, name, head, body_lines(lines, hidx)))
    if include_appendix:
        for seq, (num, name, label, sub, lines, hidx) in enumerate(appendix, 1):
            n = 193 + seq
            head = "第%d章 附录 %s" % (n, (label + " " + sub).strip())
            chapters.append((n, name, head, body_lines(lines, hidx)))
    return chapters, appendix


def self_check(chapters, out_lines):
    """生成后自检，避免「只看输出就断言没问题」。"""
    heads = [l for l in out_lines if re.match(r"^第\d+章 ", l)]
    nums = [int(re.match(r"^第(\d+)章 ", l).group(1)) for l in heads]
    assert len(heads) == len(chapters), "章节标题行数与篇数不符"
    assert nums == list(range(nums[0], nums[0] + len(nums))), "章号未严格连续递增：%s" % nums[:12]
    assert all(n >= 0 for n in nums), "出现负章号"
    assert out_lines[0] == BOOK_TITLE, "首行不是书名行"
    bad = [(i, l[:40]) for i, l in enumerate(out_lines[1:], 2)
           if not l.startswith(INDENT) and not re.match(r"^第\d+章 ", l)]
    assert not bad, "存在非章节、非缩进的行：%s" % bad[:5]
    assert all(len(c[3]) > 0 for c in chapters), "存在空正文的章节"
    forbidden = [l for l in out_lines if "【目录】" in l or "════" in l or l.startswith("· ")]
    assert not forbidden, "目录/装饰线残留：%s" % forbidden[:3]
    # 如实登记残留风险：正文段落以「第X章」起头时，个别平台的分章正则可能连缩进一起扫。
    # 这里不改写原文（禁止造伪样例），只把命中行报出来供人工确认。
    risky = [l for l in out_lines[1:]
             if re.match(r"^\u3000\u3000第[0-9" + CN_CHARS + r"]+\s*章", l)]
    return nums, risky


def write_out(path, lines, crlf):
    if crlf:
        data = ("\r\n".join(lines)).encode("utf-8")   # 无 BOM、无末尾换行，对齐参考导出物
    else:
        data = BOM + ("\n".join(lines) + "\n").encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def build_reading(entries):
    """可选：重建带目录与分隔线的阅读版（不入库，需 --out）。"""
    def fmt(ln):
        s = ln.rstrip("\r\n")
        if s.strip() == "---":
            return RULE
        if s.startswith(">"):
            return INDENT + re.sub(r"^>\s?", "", s).replace("**", "")
        if s.startswith("#"):
            mm = re.match(r"^(#+)\s*(.*)$", s)
            return mm.group(2).replace("**", "") if len(mm.group(1)) == 1 else "· " + mm.group(2).replace("**", "")
        return s.replace("**", "")

    items = []
    for num, name, lines in entries:
        hidx, text = first_heading(lines)
        body = [fmt(ln) for ln in lines[hidx + 1:]]
        while body and body[0] == "":
            body.pop(0)
        while body and body[-1] == "":
            body.pop()
        items.append((name, text, body))

    out = ["《法则权能》正文合集", "单文件 TXT 版", "",
           "合并自「点子库 / 02-正文」目录，共 %d 篇（阅读版）。" % len(items),
           "生成日期：2026-11-12。阅读版仅供人读，导入作家助手请用默认导入版。", "", "【目录】"]
    out += ["· " + t for _, t, _ in items]
    out.append("")
    for _, title, body in items:
        out += ["", BAR, title, BAR, ""]
        prev = False
        for ln in body:
            if ln == "":
                if prev:
                    continue
                prev = True
            else:
                prev = False
            out.append(ln)
    return out


def main():
    ap = argparse.ArgumentParser(description="《法则权能》作家助手导入版 TXT 生成器")
    ap.add_argument("--include-appendix", action="store_true", help="把 8 篇设定/支线资料追加为末尾附录章")
    ap.add_argument("--reading", action="store_true", help="生成带目录的阅读版（须配合 --out）")
    ap.add_argument("--mapping", action="store_true", help="只打印章号对照，不写文件")
    ap.add_argument("--crlf", action="store_true", help="输出 CRLF / 无 BOM 的平台交换副本（须配合 --out）")
    ap.add_argument("--out", default=None, help="自定义输出路径")
    args = ap.parse_args()

    entries = collect()
    chapters, appendix = build_chapters(args.include_appendix)

    if args.mapping:
        print("| 导入章号 | 原书章名 | 源文件 |")
        print("|---|---|---|")
        for n, name, head, body in chapters:
            print("| %s | %s | `%s` |" % (head.split(" ")[0], head.split(" ", 1)[1], name))
        print("\n未并入导入版的资料（%d 篇，可用 --include-appendix 追加）：" % len(appendix))
        for num, name, label, sub, _, _ in appendix:
            print("  %s  %s" % (name, label))
        return

    if args.reading:
        if not args.out:
            sys.exit("--reading 必须配合 --out 指定路径，避免在仓内留下重复大文件")
        lines = build_reading(entries)
        size = write_out(args.out, lines, args.crlf)
        print("阅读版输出：%s（%d 篇，%d 字节）" % (args.out, len(entries), size))
        return

    if args.crlf and not args.out:
        sys.exit("--crlf 必须配合 --out：平台交换副本不覆盖入库版，避免污染版本库")

    lines = [BOOK_TITLE]
    for n, name, head, body in chapters:
        lines.append(head)
        lines.extend(body)
    nums, risky = self_check(chapters, lines)

    out = args.out or DEFAULT_OUT
    size = write_out(out, lines, args.crlf)
    print("输出文件：%s" % out)
    print("章节数：%d（第%d章 ~ 第%d章，严格连续）" % (len(chapters), nums[0], nums[-1]))
    print("正文段落数：%d" % sum(len(c[3]) for c in chapters))
    print("未并入资料：%d 篇%s" % (len(appendix), "（已追加为附录章）" if args.include_appendix else "（默认排除）"))
    print("疑似误切风险行（缩进段以「第X章」起头）：%d 处" % len(risky))
    for l in risky[:5]:
        print("   " + l[:64])
    print("输出字节：%d" % size)
    print("自检：PASS（章节标题 / 章号连续 / 全角缩进 / 每章非空 / 无目录装饰线）")


if __name__ == "__main__":
    main()
