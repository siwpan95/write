#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三模板句改写的**收尾工具**：打散新句簇 + 修篇幅。

处理两件机械门禁抓不到、但读者能感到的事：

1. **新句簇**：第一、二轮改写把 1612 处模板句换成了约 30 个新句式，
   每个又聚成 ×40–60 的新簇——这正是"禁具体句式是打地鼠"的教训。
   本工具按**章内位置**（不是全局轮转）分配候选，让同一句式在全书散开。

2. **篇幅**：改写会轻微改变字数，导致 6 章跌破 2200 下限、2 章超 3000 上限。
   本工具做最小幅度调节：
   - 偏短的章 → 把一处模板句还原成长句（恢复原稿的"记账"节奏）；
   - 偏长的章 → 把一处冗长替换句压成短句。

⚠️ 换行安全：正文全是 CRLF。一律二进制读写，只做行内替换，绝不重组结构。

用法：
  python3 校验/收尾_卷三文风.py --dry-run
  python3 校验/收尾_卷三文风.py --apply
"""
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")
CHAP_RE = re.compile(r"^# 第 (\d+) 章 (.+)$", re.M)

# 第二轮候选池（全集，供打散用）
POOL = [
    "（他把这行数写进账。）", "（数字落在纸上，没有多。）", "（他记下的是数。）",
    "（这一行，他数过了。）", "（他把这个数单记一栏。）", "（数对上了。他不再数第二遍。）",
    "（他在账边写下这个数。）", "（他拿笔，在旁边添了一笔。）", "（这一栏添上了。）",
    "（他把数抄在纸角上。）", "（数落进栏里，纸没有皱。）", "（他核过一遍，就收笔。）",
    "（他绕开了半步。）", "（它压在那儿，一动没动。）", "（他把它留在原处。）",
    "（他看的是它，不是旁边。）", "（他站在那上头，没有弯腰。）", "（它还在那里。）",
    "（他绕过去。）", "（他把它挪到下一行。）", "（他推开了。）", "（他停手。）",
    "（他闭了一下眼。）", "（他把手收回来。）", "（他没有反驳。）", "（他认下。）",
    "（他等着。）", "（他收住了话头。）", "（他把手放下。）", "（没有人接话。）",
    "（他站着。）", "（他把话咽回去。）", "（他换了只手。）", "（他往下翻了一页。）",
    "（他抬起头。）", "（他转身。）", "（他接着往下走。）", "（他往前走。）",
    "（他停了半息。）", "（他把这件放下。）", "（他把它挪开。）", "（他退了半步。）",
    "（他站在原处。）", "（他没有动。）", "（他看了一眼。）", "（他重新数了一遍。）",
    "（他拿手指点了一下。）", "（他把这行圈起来。）", "（他在旁边留了空。）",
    "（他把它划掉。）", "（他往前走了半步。）", "（他往下一件去。）", "（他往下看。）",
    "（他把这件收好。）", "（他把这件搁在心里。）", "（他停了一下，又走。）",
]

# ── 语义分组：打散时**只在同组内**轮转，绝不跨组（否则语义错配）──
GROUP_POOL = {
    "num": [
        "（他把这行数写进账。）", "（数字落在纸上，没有多。）", "（他记下的是数。）",
        "（这一行，他数过了。）", "（他把这个数单记一栏。）", "（数对上了。他不再数第二遍。）",
        "（他在账边写下这个数。）", "（他拿笔，在旁边添了一笔。）", "（这一栏添上了。）",
        "（他把数抄在纸角上。）", "（数落进栏里，纸没有皱。）", "（他核过一遍，就收笔。）",
        "（他重新数了一遍。）", "（他拿手指点了一下。）", "（他把这行圈起来。）",
        "（他在旁边留了空。）",
    ],
    "obj": [
        "（他绕开了半步。）", "（它压在那儿，一动没动。）", "（他把它留在原处。）",
        "（他看的是它，不是旁边。）", "（他站在那上头，没有弯腰。）", "（它还在那里。）",
        "（他绕过去。）", "（他把它挪开。）", "（他退了半步。）", "（他站在原处。）",
        "（他没有动。）", "（他看了一眼。）",
    ],
    "judge": [
        "（他把它挪到下一行。）", "（他推开了。）", "（他停手。）", "（他闭了一下眼。）",
        "（他把手收回来。）", "（他没有反驳。）", "（他认下。）", "（他把它划掉。）",
    ],
    "silent": [
        "（他等着。）", "（他收住了话头。）", "（他把手放下。）", "（没有人接话。）",
        "（他站着。）", "（他把话咽回去。）",
    ],
    "other": [
        "（他换了只手。）", "（他往下翻了一页。）", "（他抬起头。）", "（他转身。）",
        "（他接着往下走。）", "（他往前走。）", "（他停了半息。）", "（他把这件放下。）",
        "（他往前走了半步。）", "（他往下一件去。）", "（他往下看。）",
        "（他把这件收好。）", "（他把这件搁在心里。）", "（他停了一下，又走。）",
    ],
}

# 每个 POOL 句归属的语义组（由其在 GROUP_POOL 中的位置决定）
GROUP_OF = {}
for _g, _lst in GROUP_POOL.items():
    for _s in _lst:
        GROUP_OF[_s] = _g

# 用来把偏短章补回去的长句（从原模板句扩写，保留原节奏）
LONG = [
    "（他把这一样记下。他记的是这一样。）",
    "（他把这几样记下。一样一样记。）",
    "（他把这一样放着。放着，不动。）",
    "（他数自己的心跳。数到一百，又从头。）",
]


def split_lines_keep_eol(text):
    return re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", text)


def chap_len(body):
    pure = body.replace("（本章完）", "")
    pure = re.sub(r"^#.*$", "", pure, flags=re.M)
    return len(re.sub(r"\s", "", pure))


def load():
    """{文件路径: [(章号, 标题, 起始行号)]}"""
    files = {}
    for f in sorted(os.listdir(BODY)):
        if not f.startswith("蜀山 卷三") or not f.endswith(".md"):
            continue
        p = os.path.join(BODY, f)
        raw = open(p, "rb").read().decode("utf-8")
        lines = split_lines_keep_eol(raw)
        chap_start = {}
        off = 0
        for L in lines:
            m = re.match(r"^# 第 (\d+) 章 (.+)$", L.strip())
            if m:
                chap_start[int(m.group(1))] = off
            off += 1
        files[p] = (raw, lines, chap_start)
    return files


NUM_RE = re.compile(r"[零一二三四五六七八九十百千万两半]\s*[个道笔盏条张页本斤两寸分厘尺碗盏步根枝遍样次下]")
OBJ_HINT = ("灯", "油", "碟", "碗", "纸", "墨", "笔", "印", "牌", "簿", "册", "灰",
            "沙", "炭", "锅", "灶", "案", "墙", "门", "帘", "柱", "绳", "线", "布",
            "茶", "壶", "柴", "火", "骨", "水", "盖", "泥")
SILENT_HINT = ("不说话", "没有说话", "不开口", "没有开口", "没有答", "不答",
               "没有动", "不动", "沉默", "没出声", "没有声音", "不吭")
JUDGE_HINT = ("算", "对", "错", "是", "不", "没有", "该", "该当")


def classify(prev):
    inner = prev.strip("（）").strip()
    if any(h in inner for h in SILENT_HINT):
        return "silent"
    if NUM_RE.search(inner):
        return "num"
    if any(c in inner for c in OBJ_HINT):
        return "obj"
    if any(c in inner for c in JUDGE_HINT):
        return "judge"
    return "other"


def gather(files):
    """收集所有 POOL 句的落点：{文件路径: [(行号, 句, 前句, 语义组)]}"""
    hits = defaultdict(list)
    for p, (raw, lines, cs) in files.items():
        for i, L in enumerate(lines):
            t = L.strip()
            if t in POOL:
                prev = ""
                for j in range(i - 1, -1, -1):
                    if lines[j].strip():
                        prev = lines[j].strip()
                        break
                hits[p].append((i, t, prev, classify(prev)))
    return hits


def main():
    args = sys.argv[1:]
    files = load()
    hits = gather(files)

    # 当前频次
    alltext = "".join(raw for raw, _, _ in files.values())
    freq = Counter({s: alltext.count(s) for s in POOL})
    print("=== 打散前：新句簇频次 TOP15 ===")
    for s, c in freq.most_common(15):
        print(f"  ×{c:3}  {s}")

    # ── 1. 逐文件打散：同一文件内尽量不重复同一句式 ──
    # 策略：把每个文件的 POOL 命中按行序排列，按 POOL 索引轮转分配，
    #       且优先选**当前全书频次最低**的候选。
    new_assign = {}
    for p, lst in hits.items():
        local_used = Counter()
        cls_rot = Counter()
        for (i, s, prev, grp) in lst:
            # 目标组 = 前一句的语义类型；**不跨组**，杜绝语义错配
            cands = GROUP_POOL[grp]
            picked = None
            for k in range(len(cands)):
                cs = cands[(cls_rot[grp] + k) % len(cands)]
                if local_used[cs] < 2:
                    picked = cs
                    cls_rot[grp] = (cls_rot[grp] + k + 1) % len(cands)
                    break
            if picked is None:
                picked = cands[cls_rot[grp]]
                cls_rot[grp] = (cls_rot[grp] + 1) % len(cands)
            local_used[picked] += 1
            freq[picked] += 1
            new_assign[(p, i, s, grp)] = picked

    print(f"\n待打散 {len(new_assign)} 处")

    # ── 2. 篇幅调节 ──
    # 偏短章（<2210）：把一处 POOL 句还原成 LONG 长句，补 ~8-14 字
    # 偏长章（>2980）：把一处 POOL 句换成更短的写法
    SHORT_FIX = [
        "（他记下。）", "（他停了。）", "（他走。）",
    ]
    len_fix = {}
    for p, (raw, lines, cs) in files.items():
        # 章节正文长度
        for n, base in cs.items():
            # 找该章的结束行
            nxt = [v for k, v in sorted(cs.items()) if k > n]
            end = nxt[0] if nxt else len(lines)
            body = "".join(lines[base:end])
            L = chap_len(body)
            if L < 2210:
                # 在本章找一个 POOL 命中，改成 LONG
                for i in range(base, end):
                    t = lines[i].strip()
                    if t in POOL:
                        len_fix[(p, i, t, "num")] = LONG[(n + i) % len(LONG)]
                        break
            elif L > 2980:
                for i in range(base, end):
                    t = lines[i].strip()
                    if t in POOL:
                        len_fix[(p, i, t, "other")] = SHORT_FIX[(n + i) % len(SHORT_FIX)]
                        break

    print(f"篇幅调节 {len(len_fix)} 处（偏短补长句／偏长压短句）")

    if "--dry-run" in args:
        print("\n(--dry-run，未写文件)")
        return

    # ── 3. 写回 ──
    changed = 0
    for p, (raw, lines, cs) in files.items():
        newlines = list(lines)
        touched = False
        for (pp, i, s, _g), new in list(new_assign.items()) + list(len_fix.items()):
            if pp != p:
                continue
            if i >= len(newlines) or newlines[i].strip() != s:
                continue
            m = re.match(r"^([^\r\n]*)(\r?\n?)$", newlines[i])
            content, eol = m.group(1), m.group(2)
            lead = content[:len(content) - len(content.lstrip())]
            newlines[i] = lead + new + eol
            touched = True
        if touched:
            open(p, "wb").write("".join(newlines).encode("utf-8"))
            changed += 1
    print(f"\n已写入 {changed} 个批次文件")

    # ── 4. 自检 ──
    files2 = load()
    alltext2 = "".join(raw for raw, _, _ in files2.values())
    print("\n=== 打散后频次 TOP12 ===")
    for s, c in Counter({s: alltext2.count(s) for s in POOL}).most_common(12):
        print(f"  ×{c:3}  {s}")
    lens = []
    for p, (raw, lines, cs) in files2.items():
        for n, base in cs.items():
            nxt = [v for k, v in sorted(cs.items()) if k > n]
            end = nxt[0] if nxt else len(lines)
            lens.append((n, chap_len("".join(lines[base:end]))))
    under = [x for x in lens if x[1] < 2200]
    over = [x for x in lens if x[1] > 3000]
    print(f"\n<2200：{len(under)} 章 {under[:8]}")
    print(f">3000：{len(over)} 章 {over[:8]}")
    print(f"中位数 {sorted(x[1] for x in lens)[len(lens)//2]}")


if __name__ == "__main__":
    main()
