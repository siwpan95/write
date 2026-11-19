#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卷三模板句压缩器（依据 `校验/模板句母题句根治方案.md`）。

把「记账式模板句」按**前一句的语义类型**改写为具体动作／具体账，
而不是机械地换同义词。目标：模板句族每章 ≤ 1 次。

分类依据（从前一句抽取的物证类型）：
  数字类  → 记下一个具体的数
  器物类  → 把物证写进账／或直接呈现物证
  判断类  → 换成一个外部动作
  沉默类  → 保留沉默，改用身体或环境回应
  其他    → 改写为一个不解释的收束动作

⚠️ **换行安全**：本项目的正文文件全部是 CRLF。所有读写都用二进制模式，
   替换时只做「行内字符串替换」，**绝不重组文件结构**（否则会丢内容）。

用法：
  python3 校验/压模板句_卷三.py --dry-run      # 只报告，不改文件
  python3 校验/压模板句_卷三.py --apply          # 实际改写
  python3 校验/压模板句_卷三.py --sample 30     # 抽样预览
  python3 校验/压模板句_卷三.py --verify         # 只做门禁自检
"""
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY = os.path.join(ROOT, "正文")

CHAP_RE = re.compile(r"^# 第 (\d+) 章 (.+)$", re.M)

# 模板句族（限频目标：每章合计 ≤1 次）
TPL = {
    "（他把这一样记下。）": "记",
    "（他把这几样记下。）": "记几",
    "（他把这一样放着。）": "放",
    "（他数自己的心跳。）": "心跳",
}

# 第一轮替换后产生的次级模板句（第二轮继续压，避免"打地鼠"）
TPL2 = [
    "（他走过去，没有碰。）", "（他把这行数写进账。）", "（数字落在纸上，没有多。）",
    "（他记下的是数。）", "（这一行，他数过了。）", "（他把这个数单记一栏。）",
    "（数对上了。他不再数第二遍。）", "（他在账边写下这个数。）",
    "（他没有点头，也没有摇头。）", "（这个判定，他咽下去了。）",
    "（他把手从那上头收回来。）", "（这一条，他认了，不说。）",
    "（他认下，没有说出口。）", "（他看了很久，没有反驳。）",
    "（他把这个数划掉。）", "（这件东西，他归了栏。）", "（他没有动它。）",
    "（他量了量。）", "（东西留在原处，他看了一会儿。）",
    "（他把它归到哪一栏。）", "（那东西还在那里，没有变。）",
    "（他往前走了半步。）", "（他把这件收好。）", "（他往下一件去。）",
    "（他停了一下，又走。）", "（他往下看。）", "（他把这件搁在心里。）",
]

# 母题句（保留，只做位置约束；本脚本不删）
MOTIF = [
    "三个字，十三个笔画。", "他念自己的名。", "念到第二个字，那一竖是断的。",
    "断在嘴里也一样。", "一周没有降下去的印。", "碟里的油是平的。",
    "灶上对数，一笔一笔对。", "账和锅，对得上才算。", "这里的账，是纸。",
    "稀托不住笔尖。", "殿里五盏灯。四亮一暗。",
]

# ── 前句分类 ────────────────────────────────────────────────
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
        return "silent", inner
    if NUM_RE.search(inner):
        return "num", inner
    if any(c in inner for c in OBJ_HINT):
        return "obj", inner
    if any(c in inner for c in JUDGE_HINT):
        return "judge", inner
    return "other", inner


REWRITE = {
    "num": [
        "（他把这行数写进账。）",
        "（数字落在纸上，没有多。）",
        "（他记下的是数。）",
        "（这一行，他数过了。）",
        "（他把这个数单记一栏。）",
        "（数对上了。他不再数第二遍。）",
        "（他在账边写下这个数。）",
        "（他拿笔，在旁边添了一笔。）",
        "（这一栏添上了。）",
        "（他把数抄在纸角上。）",
        "（数落进栏里，纸没有皱。）",
        "（他核过一遍，就收笔。）",
    ],
    "obj": [
        "（这件东西，他归了栏。）",
        "（他没有动它。）",
        "（他量了量。）",
        "（东西留在原处，他看了一会儿。）",
        "（他把它归到哪一栏。）",
        "（他走过去，没有碰。）",
        "（那东西还在那里，没有变。）",
        "（他绕开了半步。）",
        "（他站在那上头，没有弯腰。）",
        "（它压在那儿，一动没动。）",
        "（他把它留在原处。）",
        "（他看的是它，不是旁边。）",
    ],
    "judge": [
        "（他没有点头，也没有摇头。）",
        "（这个判定，他咽下去了。）",
        "（他把手从那上头收回来。）",
        "（这一条，他认了，不说。）",
        "（他认下，没有说出口。）",
        "（他看了很久，没有反驳。）",
        "（他把这个数划掉。）",
        "（他把它推到一边。）",
        "（他停手，没有再动。）",
        "（他把这笔销了。）",
        "（他闭了一下眼。）",
        "（他把这个数挪到下一行。）",
    ],
    "silent": [
        "（那人没有答。他等着。）",
        "（他等着。没有等到。）",
        "（他不再问。）",
        "（安静。）",
        "（他收住话头。）",
        "（他把手放下。）",
        "（他等了一会儿，转身。）",
        "（没有人接话。他也没有。）",
        "（他把话咽回去。）",
        "（他站着，没有动。）",
    ],
    "other": [
        "（他往前走了半步。）",
        "（他把这件收好。）",
        "（他走过去，没有碰。）",
        "（他往下一件去。）",
        "（他停了一下，又走。）",
        "（他往下看。）",
        "（他把这件搁在心里。）",
        "（他换了只手。）",
        "（他往下翻了一页。）",
        "（他抬起头。）",
        "（他把这件放下，转身。）",
        "（他接着往下走。）",
    ],
}


def load_chapters():
    """返回 {章号: (标题, 正文文本, 文件名, 路径)}。"""
    out = {}
    for f in sorted(os.listdir(BODY)):
        if not f.endswith(".md") or f.startswith("_"):
            continue
        p = os.path.join(BODY, f)
        raw = open(p, "rb").read().decode("utf-8")
        parts = CHAP_RE.split(raw)
        for i in range(1, len(parts) - 1, 3):
            n = int(parts[i])
            if 251 <= n <= 375:
                out[n] = (parts[i + 1].strip(), parts[i + 2], f, p)
    return out


def split_lines_keep_eol(text):
    """按行拆分，保留每行原有的换行符。"""
    return re.findall(r"[^\r\n]*\r?\n|[^\r\n]+$", text)


def build_plan(chapters, per_chapter=1, targets=None):
    """返回 {(路径, 章号, 章内行号, 原句, 序号): (类别, 前句)}。"""
    targets = targets or TPL
    plan = {}
    for n in sorted(chapters):
        title, body, f, p = chapters[n]
        lines = split_lines_keep_eol(body)
        idxs = [i for i, L in enumerate(lines) if L.strip() in targets]
        if not idxs:
            continue
        keep = set(idxs[:per_chapter])
        cnt = Counter()
        for i in idxs:
            L = lines[i].strip()
            seq = cnt[L]
            cnt[L] += 1
            if i in keep:
                continue
            prev = ""
            for j in range(i - 1, -1, -1):
                if lines[j].strip():
                    prev = lines[j].strip()
                    break
            kind, inner = classify(prev)
            plan[(p, n, i, L, seq)] = (kind, prev)
    return plan


# 第二轮候选池（对 TPL2 生效）：进一步物证化、动作化
REWRITE2 = {
    "num": [
        "（他在账边补了一个数。）", "（这一栏添上了数。）", "（数落进栏里。）",
        "（他拿笔添了一笔。）", "（他抄在纸角上。）", "（他核过，收笔。）",
        "（数写进账，没多写。）", "（他把数记在下一行。）",
    ],
    "obj": [
        "（他绕开了半步。）", "（它压在那儿，没动。）", "（他把它留在原处。）",
        "（他看的是它，不是旁边。）", "（他站在那上头，没弯腰。）",
        "（它还在那里。）", "（他绕过去。）",
    ],
    "judge": [
        "（他把手收回来。）", "（他把这笔销了。）", "（他停手。）",
        "（他闭了一下眼。）", "（他把它挪到下一行。）", "（他推开了。）",
        "（他没有反驳。）",
    ],
    "silent": [
        "（他等着。）", "（他收住了话头。）", "（他把手放下。）",
        "（没有人接话。）", "（他站着。）", "（他把话咽回去。）",
    ],
    "other": [
        "（他换了只手。）", "（他往下翻了一页。）", "（他抬起头。）",
        "（他转身。）", "（他接着往下走。）", "（他把这一件放下。）",
        "（他往前走。）",
    ],
}


def assign_candidates(plan, table=None):
    used = Counter()
    assign = {}
    for key in sorted(plan, key=lambda k: (k[1], k[2])):
        kind, prev = plan[key]
        cands = (table or REWRITE)[kind]
        pick = min(range(len(cands)), key=lambda j: (used[(kind, j)], j))
        used[(kind, pick)] += 1
        assign[key] = cands[pick]
    return assign


def apply_changes(plan, assign):
    """按文件聚合，逐行做字符串替换（保留原换行符与缩进）。"""
    by_file = {}
    for key in assign:
        p, n, i, L, seq = key
        by_file.setdefault(p, []).append((n, i, L, assign[key]))

    changed = []
    for p, items in by_file.items():
        raw = open(p, "rb").read().decode("utf-8")
        lines = split_lines_keep_eol(raw)
        chap_start = {}
        off = 0
        for L in lines:
            m = re.match(r"^# 第 (\d+) 章 ", L)
            if m:
                chap_start[int(m.group(1))] = off
            off += 1
        for (n, i, L, new) in items:
            base = chap_start.get(n)
            if base is None:
                continue
            gi = base + i
            if gi >= len(lines):
                continue
            cur = lines[gi]
            if cur.strip() != L:
                continue
            m = re.match(r"^([^\r\n]*)(\r?\n?)$", cur)
            content, eol = m.group(1), m.group(2)
            lead = content[:len(content) - len(content.lstrip())]
            lines[gi] = lead + new + eol
        new_raw = "".join(lines)
        if new_raw != raw:
            open(p, "wb").write(new_raw.encode("utf-8"))
            changed.append(os.path.basename(p))
    return changed


def verify():
    chapters = load_chapters()
    tot = 0
    worst = []
    for n in sorted(chapters):
        body = chapters[n][1]
        c = sum(body.count(t) for t in TPL)
        tot += c
        if c > 1:
            worst.append((n, c))
    print(f"模板句族：{tot} 处 / {len(chapters)} 章（目标 ≤125）")
    print(f"超限章（>1 次）：{len(worst)} 章 {worst[:12]}")
    lens = []
    for n in sorted(chapters):
        body = chapters[n][1]
        pure = body.replace("（本章完）", "")
        pure = re.sub(r"^#.*$", "", pure, flags=re.M)
        lens.append((n, len(re.sub(r"\s", "", pure))))
    under = [x for x in lens if x[1] < 2200]
    over = [x for x in lens if x[1] > 3000]
    print(f"<2200：{len(under)} 章 {under[:6]}")
    print(f">3000：{len(over)} 章 {over[:6]}")
    print(f"中位数 {sorted(x[1] for x in lens)[len(lens)//2]}")
    print("\n=== 替换句自身频次（>40 视为新模板）===")
    alltext = "".join(chapters[n][1] for n in chapters)
    for cand in sorted({c for cs in REWRITE.values() for c in cs}):
        c = alltext.count(cand)
        if c > 40:
            print(f"  ×{c}  {cand}")


def main():
    args = sys.argv[1:]
    chapters = load_chapters()
    round2 = "--round2" in args
    if round2:
        plan = build_plan(chapters, per_chapter=0, targets=TPL2)
        assign = assign_candidates(plan, table=REWRITE2)
    else:
        plan = build_plan(chapters)
        assign = assign_candidates(plan)

    if "--verify" in args:
        verify()
        return

    print(f"待改写 {len(assign)} 处")
    print("按前句类型：", dict(Counter(k for k, _ in plan.values())))

    if "--sample" in args:
        m = 30
        for a in args:
            if a.startswith("--sample"):
                try:
                    m = int(a.split("=")[1]) if "=" in a else 30
                except ValueError:
                    m = 30
        print("\n=== 抽样预览 ===")
        items = sorted(assign.items(), key=lambda x: (x[0][1], x[0][2]))
        step = max(1, len(items) // m)
        for idx in range(0, len(items), step):
            key, new = items[idx]
            p, n, i, L, seq = key
            kind, prev = plan[key]
            print(f"[第{n}章/{kind}] {prev}")
            print(f"   − {L}")
            print(f"   + {new}")
        return

    if "--dry-run" in args:
        print("\n(--dry-run，未写文件)")
        return

    changed = apply_changes(plan, assign)
    print(f"\n已改写 {len(changed)} 个批次文件")
    for c in changed:
        print("  ", c)
    print("\n=== 改写后门禁自检 ===")
    verify()


if __name__ == "__main__":
    main()
