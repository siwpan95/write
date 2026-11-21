#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2dse.py —— Markdown 规划文档 → dse-core 内容包转换器
================================================================================
把 write 仓的**规划层文档**（四层大纲 / 节拍表 / 零件库）转成
dse-core 可执行、可校验的 YAML 场景图。

为什么需要它
------------
write 仓的规划文档（`02-大纲四层` / `10-节拍表` / 零件库装配体）已经是
高度结构化的 Markdown —— 有明确的分段、状态标记、字段约定。dse-core 的
`check` / `traverse` / `coverage` 三道门能机械验证「结构是否自洽、
分支是否可达、结局是否有来源」。转换器是把**文字规划**接进**机器校验**
的那座桥。

三条硬约束（源自实测，见 dse-content/docs/内容包规范.md）
-----------------------------------------------------------
1. **YAML 重复 key 静默吞掉前一个** —— 用自定义 Loader 检测，命中即报错。
2. **场景 ID 限 ASCII 正则** —— 中文段落名映射为稳定 slug。
3. **schema 全局 additionalProperties:false** —— 生成字段严格对齐 schema。

**核心内核纪律**：本脚本**只用标准库**（yaml 由 PyYAML 提供，但仅在
`--check` 模式用；生成路径不依赖 yaml 库 —— 直接手写 YAML 文本，
避免缩进/转义陷阱，且生成结果可逐字节 diff）。

用法
----
    python tools/procedural/md2dse.py outline <源md> [-o 输出yml]
    python tools/procedural/md2dse.py beats   <源md> [-o 输出yml]
    python tools/procedural/md2dse.py parts   <源md> [-o 输出yml]
    python tools/procedural/md2dse.py --check <yml>...      # 重复键/schema 体检

退出码：0 成功 ／ 1 有 ERROR

作者：WorkBuddy ｜ 2026-11-21
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

# ── 场景 ID 正则（dse-core scene.schema.json 的 Scene id 约束） ────────────
SCENE_ID_RE = re.compile(r"^[a-z][a-z0-9]*([-_][a-z0-9]+)*(\.[a-z0-9]+([-_][a-z0-9]+)*)*$")


# ==============================================================================
# 通用工具
# ==============================================================================

def read_text(path: Path) -> str:
    """读文件，显式 UTF-8（Windows 默认编码不是 UTF-8，必须显式指定）。"""
    try:
        return io.open(path, encoding="utf-8").read()
    except FileNotFoundError:
        raise SystemExit(f"[FAIL] 源文件不存在：{path}")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"[FAIL] 源文件不是合法 UTF-8：{path}（{exc}）")


def slugify(name: str, prefix: str, index: int) -> str:
    """中文/混合标题 → ASCII 场景 ID（铁律 4）。

    规则：
      · 保留 ASCII 字母数字与 - / _，其余转 -
      · 全中文名退化为纯序号（seg-01），保证稳定且可排序
      · 结果必须匹配 SCENE_ID_RE，否则抛错（不静默产出非法 ID）
    """
    ascii_part = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    ascii_part = re.sub(r"-{2,}", "-", ascii_part)
    sid = f"{prefix}-{index:02d}" + (f"-{ascii_part}" if ascii_part else "")
    if not SCENE_ID_RE.match(sid):
        raise SystemExit(f"[FAIL] 生成的场景 ID 不合法：{sid!r}（源名 {name!r}）")
    return sid


def yaml_quote(text: str) -> str:
    """安全的 YAML 双引号字符串。

    dse-core 的 text/title 会被当作模板渲染（{path} 插值），
    所以必须转义 YAML 层面会出事的字符：
      · 反斜杠 → 双写（否则 \\n 会被当成换行）
      · 双引号 → 转义
      · 换行 → 折行缩进（YAML 双引号可跨行）
    """
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in out:
        # 多行 → 折行缩进形式
        lines = out.split("\n")
        return "\n" + "\n".join(f"      {ln}".rstrip() for ln in lines)
    return f'"{out}"'


def one_line(text: str, limit: int = 300) -> str:
    """压成单行（用于 text 字段），超长截断。"""
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) > limit:
        t = t[:limit].rstrip() + "…"
    return t


def parse_markdown_table(block: str) -> list[list[str]]:
    """解析 Markdown 表格 → 单元格二维列表（自动跳过表头与分隔行）。"""
    rows: list[list[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # 分隔行（|---|---|）
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    if rows:
        # 去掉表头（第一行）
        rows = rows[1:]
    return rows


def section_block(text: str, pattern: str) -> str | None:
    """按正则标题切出小节正文（到下一个同级/更高级标题为止）。"""
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else None


# ==============================================================================
# 转换器 · outline（四层大纲的主线段）
# ==============================================================================

def convert_outline(src: Path, out: Path) -> int:
    """四层大纲 → 场景链。

    映射规则：
      · 主线表格每段 = 一个场景（seg-NN）
      · 段间推进 = goto 下一个场景
      · 状态标记（已写 / 待写）= 分支结局（written / pending）
      · 段描述 → 场景 text
    """
    text = read_text(src)

    block = section_block(text, r"###\s*2\.1\s*主线(.*?)(?=\n###\s|\n##\s)")
    if block is None:
        print("[FAIL] 未找到「2.1 主线」小节 —— 源文档结构可能已变", file=sys.stderr)
        return 1

    segments: list[tuple[str, str, str]] = []
    for cells in parse_markdown_table(block):
        if len(cells) < 3:
            continue
        name = cells[0].replace("**", "").strip()
        desc = cells[1].replace("**", "").strip()
        status = cells[2].replace("**", "").strip()
        if not name or name.startswith("---"):
            continue
        segments.append((name, desc, status))

    if not segments:
        print("[FAIL] 主线表格解析为空", file=sys.stderr)
        return 1

    # 自带 index 场景：让本包**自成一个入口**（可与其它包并存于同一工程，
    # 由顶层 index.yml 汇总）。否则包内场景会因不可达而触发 check 的 WARN。
    idx_sid = "kz-index"
    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：%s）" % src.as_posix(),
        "# 生成器：tools/procedural/md2dse.py outline",
        "# 改内容请改派生源后重跑；手改会被下次生成覆盖。",
        "pack:",
        "  id: kz-outline",
        "  name: 廓者未名夜 · 四层大纲投影",
        "  version: 0.1.0",
        f"  entry: {idx_sid}",
        "scenes:",
        f"  {idx_sid}:",
        f"    title: {yaml_quote('《廓者：未名夜》· 四层大纲主线')}",
        f"    text: {yaml_quote('主线 %d 段。已写段与待写段各有一条分支结局。' % len(segments))}",
        f"    onEnter:",
        f"      visits:",
        f"        {idx_sid}: +1",
        f"    choices:",
    ]
    for i, (name, _desc, status) in enumerate(segments, start=1):
        sid = slugify(name, "seg", i)
        mark = "已写" if status.startswith("已写") else "待写"
        lines.append(f"      - text: {yaml_quote(f'{i}. {name}（{mark}）')}")
        lines.append(f"        goto: {sid}")

    for i, (name, desc, status) in enumerate(segments, start=1):
        sid = slugify(name, "seg", i)
        written = status.startswith("已写")
        lines.append(f"  {sid}:")
        lines.append(f"    title: {yaml_quote(name)}")
        lines.append(f"    text: {yaml_quote(one_line(desc))}")
        lines.append("    onEnter:")
        lines.append("      visits:")
        lines.append(f"        {sid}: +1")
        lines.append("      seg_index: +1")
        lines.append("    choices:")
        if i < len(segments):
            nxt = slugify(segments[i][0], "seg", i + 1)
            lines.append(f"      - text: {yaml_quote('推进到 ' + segments[i][0])}")
            lines.append(f"        goto: {nxt}")
        else:
            # 末段没有后继 —— 指向自身（**不能指 index**：
            #   实测指 index 会让路径组合爆炸，traverse 撞 180s 超时；
            #   自环虽报一条「重访截断」WARN，但收敛快、路径可控 —— 正确权衡）
            lines.append(f'      - text: "本线终结"')
            lines.append(f"        goto: {sid}")
        # ⚠️ 只生成**状态实际对应**的那一个分支结局。
        # 若同时生成 written/pending 两个分支，则二者互斥 —— 只有一个可达，
        # 另一个会被 dse coverage 判为「没有任何来源」而报 ERROR。
        # 互斥分支不是本内容包要表达的结构（互斥选项用选项级 if 表达）。
        kind = "written" if written else "pending"
        label = "已写线" if written else "待写线"
        ktext = "该段已落笔，结局待续写。" if written else "该段尚未开笔，是主线留白。"
        lines.append(f"      - text: {yaml_quote('分支：' + label)}")
        lines.append(f"        goto: {sid}-{kind}")
        lines.append(f"  {sid}-{kind}:")
        lines.append(f"    title: {yaml_quote(name + ' · ' + label)}")
        lines.append(f"    text: {yaml_quote(ktext)}")

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    print(f"[OK] outline：解析 {len(segments)} 段 → {out}")
    for i, (name, _d, status) in enumerate(segments, start=1):
        print(f"     {i:2d}. {name:24s} → {slugify(name, 'seg', i):24s} [{status[:14]}]")
    return 0


# ==============================================================================
# 转换器 · beats（节拍表）
# ==============================================================================

def convert_beats(src: Path, out: Path, pack_id: str = "kz-beats") -> int:
    """节拍表 → 场景序列。

    映射规则（按真实四列表：拍 / 名称 / 本书落点 / 卷）：
      · 名称    → 场景 title
      · 本书落点 → 场景 text（**信息主体**，不能丢）
      · 卷      → `onEnter` 的标记（人读，不进条件）
      · 相邻拍  → goto 链
      · 自带 `<prefix>-beat-index` 场景 → 可由顶层 index 汇总

    `pack_id` 可配（v3.18.7）：多作品并存时需唯一 ID，否则后者覆盖前者。
    默认值 `kz-beats` 及其 index 场景 ID `beat-index` 保持不变（向后兼容）。
    """
    text = read_text(src)
    # 定位「15 拍 → 卷框架」那张表（1.1 全书级节拍表）
    block = section_block(text, r"###\s*1\.1\s*全书级节拍表(.*?)(?=\n###\s|\n##\s)")
    if block is None:
        print("[FAIL] 未找到「1.1 全书级节拍表」小节 —— 源文档结构可能已变", file=sys.stderr)
        return 1

    beats: list[tuple[str, str, str]] = []   # (拍号, 名称, 落点)
    for cells in parse_markdown_table(block):
        if len(cells) < 3:
            continue
        seq = cells[0].replace("**", "").strip()
        if not seq.isdigit():
            continue
        name = cells[1].replace("**", "").strip()
        body = cells[2].replace("**", "").strip()
        if not name or not body:
            continue
        beats.append((seq, name, body))

    if not beats:
        print("[FAIL] 节拍表解析为空", file=sys.stderr)
        return 1

    # index 场景 ID 随 pack_id 派生：默认 kz-beats → beat-index（兼容旧包）；
    # 其它包（如 ccz-beats）→ ccz-beat-index，避免跨包同 ID 互相覆盖。
    idx_sid = "beat-index" if pack_id == "kz-beats" else pack_id.replace("-beats", "") + "-beat-index"
    pack_name = "廓者未名夜 · 节拍表投影" if pack_id == "kz-beats" else (pack_id.replace("-", " ") + " · 节拍表投影")
    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：%s）" % src.as_posix(),
        "# 生成器：tools/procedural/md2dse.py beats",
        "pack:",
        f"  id: {pack_id}",
        f"  name: {yaml_quote(pack_name)}",
        "  version: 0.1.0",
        f"  entry: {idx_sid}",
        "scenes:",
        f"  {idx_sid}:",
        f"    title: {yaml_quote('《廓者：未名夜》· 全书 15 拍')}",
        f"    text: {yaml_quote('节拍表投影：%d 拍。节拍定位由人判，本图只校验结构。' % len(beats))}",
        f"    onEnter:",
        f"      visits:",
        f"        {idx_sid}: +1",
        f"    choices:",
    ]
    for seq, name, _body in beats:
        sid = slugify(name, "beat", int(seq))
        lines.append(f"      - text: {yaml_quote(f'{seq}. {name}')}")
        lines.append(f"        goto: {sid}")

    for i, (seq, name, body) in enumerate(beats, start=1):
        sid = slugify(name, "beat", int(seq))
        lines.append(f"  {sid}:")
        lines.append(f"    title: {yaml_quote(name)}")
        lines.append(f"    text: {yaml_quote(one_line(body))}")
        lines.append("    onEnter:")
        lines.append("      visits:")
        lines.append(f"        {sid}: +1")
        lines.append("    choices:")
        if i < len(beats):
            nseq, nname, _nb = beats[i]
            nxt = slugify(nname, "beat", int(nseq))
            lines.append(f"      - text: {yaml_quote('下一拍：' + nname)}")
            lines.append(f"        goto: {nxt}")
        else:
            lines.append(f'      - text: "节拍表终点"')
            lines.append(f"        goto: {sid}")

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"[OK] beats：解析 {len(beats)} 拍 → {out}")
    for seq, name, _body in beats:
        print(f"     {seq:>2s}. {name}")
    return 0


# ==============================================================================
# 转换器 · parts（零件库装配体）
# ==============================================================================

def convert_parts(src: Path, out: Path) -> int:
    """零件库零件卡 → 咬合邻接图。

    映射规则（**语义正确性优先**）：
      · 每个零件 → 一个场景
      · 咬合边（A 可与 B 咬合）→ A 场景提供「引入 B」的 goto 选项
      · 互斥零件 → **不生成**跳转（互斥意味着不能同时装，不是路径）
      · 判定件／元件（装配角色 = 判定／元）→ **不产生咬合边**
        （与 零件库/build_edges.py 同口径，否则会出现「度数 0 却称可咬任何件」的矛盾）

    ⚠️ **咬合图不是剧情图**：它表达「哪些件能拼在一起」，
    不是「主角从 A 走到 B」。故 goto 的语义是「引入同场邻接件」。
    dse traverse 在此图上验证的是**咬合连通性**（有没有孤立件），
    剧情路径的可达性由 `assembly` 模式验证。

    解析口径与 零件库/build_edges.py **保持一致**（同一套正则）——
    两处口径分叉会让「索引说能咬、图里咬不上」。
    """
    card_files = ["02-制度型零件.md", "03-机制型零件.md",
                  "04-地理与资源型零件.md", "05-历史与接口型零件.md"]
    cards: dict[str, str] = {}          # pid -> 名称
    bodies: dict[str, str] = {}        # pid -> 卡正文
    roles: dict[str, str] = {}         # pid -> 装配角色
    raw_edges: dict[str, set[str]] = {}   # pid -> 单侧登记的咬合件
    mutex: dict[str, set[str]] = {}

    for cf in card_files:
        cp = src / cf
        if not cp.exists():
            continue
        text = read_text(cp)
        parts = re.split(r"^## `(WB-[A-Z]+-\d{4})`[^\n]*$", text, flags=re.M)
        for i in range(1, len(parts) - 1, 2):
            pid, body = parts[i], parts[i + 1]
            m = re.search(r"\| 零件名 \| (.+?) \|", body)
            cards[pid] = m.group(1).strip() if m else pid
            bodies[pid] = body
            r = re.search(r"\| 装配角色 \| \*\*(\S+?)\*\*", body)
            roles[pid] = r.group(1) if r else "参与"
            e = re.search(r"\| 可咬合零件 \| (.+?) \|", body)
            if e and roles[pid] not in META_ROLES:
                for x in re.findall(r"WB-[A-Z]+-\d{4}", e.group(1)):
                    if x != pid:
                        raw_edges.setdefault(pid, set()).add(x)
            mx = re.search(r"\| 互斥零件 \| (.+?) \|", body)
            if mx:
                for x in re.findall(r"WB-[A-Z]+-\d{4}", mx.group(1)):
                    if x != pid:
                        mutex.setdefault(pid, set()).add(x)

    if not cards:
        print(f"[FAIL] {src} 下未解析出零件卡（{', '.join(card_files)}）", file=sys.stderr)
        return 1

    # 对称闭包（与 build_edges.py 同法：单侧登记补全）
    sym: dict[str, set[str]] = {n: set(raw_edges.get(n, set())) for n in cards}
    for a, bs in raw_edges.items():
        for b in bs:
            if a not in sym.get(b, set()):
                sym[b].add(a)

    # 场景 ID：零件 ID 本身即合法 ASCII（WB-XXX-NNNN）
    def pid_sid(pid: str) -> str:
        return pid.lower().replace("-", "-")

    # 一个零件的邻接件太多（记录即存在 度数 18）⇒ goto 全列会让场景爆炸。
    # 折中：**按度数封顶**，超出部分记为 INFO（在 text 里注明），
    # 保证图仍可遍历，同时不丢「它咬合很多」这个事实。
    MAX_DEG = 8

    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：零件库/02~05-*.md）",
        "# 生成器：tools/procedural/md2dse.py parts",
        "# 改内容请改零件卡后重跑；手改会被下次生成覆盖。",
        "# 语义：咬合邻接图（goto = 引入同场邻接件），**不是剧情路径**。",
        "pack:",
        "  id: parts-graph",
        "  name: 零件库咬合邻接图",
        "  version: 0.1.0",
    ]

    # 装配体入口映射：成员件 → 所属装配体
    # 语义：**咬合图是入口，装配链挂在咬合边上** ——
    #   选了某零件 → 可以进入包含它的装配体 → 走装配路径。
    # 两个内容包（parts-graph / parts-assembly）由此连通，
    # entry 只需落在零件图上。
    asm_of_part: dict[str, list[str]] = {}
    asm_dir = src / "装配体"
    if asm_dir.is_dir():
        for af in sorted(asm_dir.glob("ASM-*.md")):
            atext = read_text(af)
            aid_m = ASM_ID_RE.search(atext)
            aid = aid_m.group(1) if aid_m else af.stem
            short = asm_short_id(aid)
            mblock = section_block(atext, r"###\s*2\.2\s*成员件与角色(.*?)(?=\n###\s|\n##\s)")
            for row in _asm_member_rows(mblock or ""):
                asm_of_part.setdefault(row["pid"], []).append(short)

    ordered = sorted(cards)
    # entry ＝ **枢纽场景**（零件总览）。
    # ⚠️ 为什么需要枢纽：咬合边不是 goto（见下方说明），零件之间没有互达边；
    #   若 entry 直接指向某个零件，则只有「该零件所属装配体」可达，
    #   其余 27 件零件与另外 5 个装配体全部不可达（实测：可达结局只有 5/10）。
    #   枢纽场景列出全部零件 → 遍历可达全部，且用法也更自然
    #   （先看有什么零件，再选一个深入）。
    hub_sid = "hub"
    lines.append(f"  entry: {hub_sid}")
    lines.append("scenes:")
    lines.append(f"  {hub_sid}:")
    lines.append(f"    title: {yaml_quote('零件库 · 总览（%d 件）' % len(cards))}")
    lines.append(f"    text: {yaml_quote('跨项目可复用世界零件。每件可进入其所属装配体走装配路径；咬合关系见各件说明与 14-咬合索引。')}")
    lines.append("    onEnter:")
    lines.append("      visits:")
    lines.append(f"        {hub_sid}: +1")
    lines.append("    choices:")
    for pid in ordered:
        lines.append(f"      - text: {yaml_quote(cards[pid])}")
        lines.append(f"        goto: {pid_sid(pid)}")

    for pid in ordered:
        sid = pid_sid(pid)
        nb = sym.get(pid, set())
        deg = len(nb)
        meta = bodies.get(pid, "")
        band = ""
        bm = re.search(r"\| band \| (.+?) \|", meta)
        if bm:
            band = one_line(bm.group(1), 60)
        phase = ""
        pm = re.search(r"\| phase \| (.+?) \|", meta)
        if pm:
            phase = one_line(pm.group(1), 60)
        desc = f"{cards[pid]}（{pid}）"
        if band:
            desc += f"｜band: {band}"
        if phase:
            desc += f"｜phase: {phase}"
        if roles.get(pid) in META_ROLES:
            desc += f"｜**{roles[pid]}件**（不产生咬合边）"

        # ⚠️ 先把 desc 组装完整，再写 text —— **text 必须在 choices 之前**
        #    （YAML 里 choices 是序列，text 插在序列中间会解析失败；
        #     实测踩坑：ParserError "expected <block end>, but found '<block sequence start>'"）
        if nb:
            # ⚠️ **咬合边不生成 goto**（实测踩坑，代价 5 分钟超时）：
            #   咬合是**对称闭包**（无向图），若每个邻接件都成一个 goto 选项，
            #   dse traverse 的 DFS 会在 79 节点的图上组合爆炸 —— 实测跑 5 分钟
            #   未结束，被迫中断。
            #   语义上也对：**咬合是静态结构，不是剧情路径**（goto = 可走的边）。
            #   故邻接件写进 `text`（人读 + 机器可查），goto 只留给**装配体入口**。
            #   咬合连通性由 零件库/check_parts.py 与 build_edges.py 判定，
            #   那才是纯图论该待的地方。
            nb_desc = "、".join(
                f"{cards.get(p, p)}（{p}）" for p in sorted(nb)[:MAX_DEG])
            if deg > MAX_DEG:
                nb_desc += f" ……另有 {deg - MAX_DEG} 件（见 14-咬合索引）"
            desc += f"｜可咬合 {deg} 件：{nb_desc}"
        else:
            desc += f"｜可咬合 0 件（{roles.get(pid, '参与')}件）"

        lines.append(f"  {sid}:")
        lines.append(f"    title: {yaml_quote(cards[pid])}")
        lines.append(f"    text: {yaml_quote(desc)}")
        lines.append("    onEnter:")
        lines.append("      visits:")
        lines.append(f"        {sid}: +1")
        lines.append("    choices:")

        # 装配体入口（若有）
        for short in asm_of_part.get(pid, []):
            lines.append(f"      - text: {yaml_quote('进入装配体 ' + short.upper())}")
            lines.append(f"        goto: {short}-step0")

        if not nb:
            lines.append(f'      - text: "（无咬合件 —— {roles.get(pid, "参与")}）"')
            lines.append(f"        goto: {hub_sid}")
        else:
            # 唯一可走的边：**回枢纽**（不指自身 —— 自环会让 traverse 撞
            # max-revisit 上限，每个零件都刷一条「重访超限」截断 WARN，29 条噪音
            # 掩盖真信号；实测改为回枢纽后截断归零）
            lines.append(f'      - text: "（本件可咬合 {deg} 件 —— 见上）"')
            lines.append(f"        goto: {hub_sid}")

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")

    total_edges = sum(len(v) for v in sym.values()) // 2
    isolated = [p for p in ordered if not sym.get(p)]
    print(f"[OK] parts：解析 {len(cards)} 件零件 / {total_edges} 对咬合边 → {out}")
    print(f"     咬合连通分量外节点（无咬合件）：{len(isolated)}"
          + (f" —— {[cards[p] for p in isolated]}" if isolated else ""))
    return 0


# ==============================================================================
# 转换器 · assembly（零件库装配体）
# ==============================================================================

# 装配体的八量（财势名位时秘身信）—— dse 状态字段名直接用中文单字
QTY_CHARS = "财势名位时秘身信"

# 八量 → ASCII 状态字段名。
# ⚠️ **必须映射成 ASCII**：dse-core 的 Effects schema 限定键名为
#    `^[A-Za-z_$][\w$]*$`（且禁 __proto__/constructor/prototype —— 防原型污染），
#    中文键名会被 check 直接拒。实测踩坑：写 `名` / `位` 即报
#    "'名' does not match ..."。
# 命名规则：拼音首字母 + 量序号，避免 `势`/`时` 同音撞名。
QTY_ASCII = {
    "财": "cai",
    "势": "shi_p",
    "名": "ming",
    "位": "wei",
    "时": "shi_t",
    "秘": "mi",
    "身": "shen",
    "信": "xin",
}

# 装配角色：判定件与元件**不产生咬合边**（与 零件库/build_edges.py 同口径）
META_ROLES = ("判定", "元")


def asm_short_id(asm_id: str) -> str:
    """装配体 ID → 场景 ID 前缀。**parts 与 assembly 两个模式必须一致**，
    否则咬合图的「进入装配体」选项会指向不存在的场景。"""
    return asm_id.replace("ASM-", "").lower()


def pid_sid(pid: str) -> str:
    """零件 ID → 场景 ID（零件 ID 本身即合法 ASCII）。"""
    return pid.lower()

# 装配体文件头字段
ASM_ID_RE = re.compile(r"\| 1 \| `装配ID` \| `([^`]+)` \|")
ASM_TOPIC_RE = re.compile(r"\| 2 \| `课题` \| \*\*(.+?)\*\*（")
ASM_GRAN_RE = re.compile(r"\| 粒度 \| (.+?) \|")
ASM_DRIVER_RE = re.compile(r"###\s*2\.3\s*驱动量\s*\n+\s*\*\*`([^`]+)`\*\*")


def _asm_member_rows(block: str) -> list[dict]:
    """解析「成员件与角色」表 → [{seq, pid, band, phase, role}]。"""
    rows = []
    for cells in parse_markdown_table(block):
        if len(cells) < 5:
            continue
        seq = cells[0].strip()
        m = re.search(r"WB-[A-Z]+-\d{4}", cells[1])
        if not m:
            continue
        rows.append({
            "seq": seq,
            "pid": m.group(0),
            "band": cells[2].strip().replace("*", ""),
            "phase": cells[3].strip().replace("*", ""),
            "role": cells[4].strip().replace("*", ""),
        })
    return rows


def _asm_delta_rows(block: str) -> list[dict]:
    """解析「Δ 序列」表 → [{step, pid, phase, delta, qty: {名: 值}}]。

    表头列是**该装配体实际推进的量**（子集，非固定八量）——
    故列名从表头动态取，不能写死。
    """
    lines = [l for l in block.splitlines() if l.strip().startswith("|")]
    if len(lines) < 3:
        return []
    # 表头
    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    try:
        qty_start = header.index("Δ") + 1
    except ValueError:
        return []
    qty_cols = header[qty_start:]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < qty_start:
            continue
        step = cells[0].strip()
        if not step.isdigit():
            continue
        pid = ""
        pm = re.search(r"WB-[A-Z]+-\d{4}", cells[1])
        if pm:
            pid = pm.group(0)
        vals = {}
        for j, q in enumerate(qty_cols):
            if qty_start + j >= len(cells):
                break
            raw = cells[qty_start + j].strip().replace("*", "").replace("−", "-")
            try:
                vals[q] = int(raw)
            except ValueError:
                pass
        rows.append({
            "step": int(step),
            "pid": pid,
            "phase": cells[2].strip().replace("*", ""),
            "delta": cells[3].strip(),
            "qty": vals,
        })
    return rows


def convert_assembly(src_dir: Path, out: Path) -> int:
    """零件库装配体 → dse 场景链（装配路径）。

    映射规则（**语义正确性优先**）：
      · 一个装配体 = 一条**装配链**（不是零件全景图）
      · Δ 序列的每一**步** = 一个场景
      · 该步的量变化 = `do`（数值加减，dse 语义与 Δ 一致）
      · 步序 = `goto` 链
      · 装配后状态 = 结局场景
      · 粒度（卷级／站区级）= 分支条件（互斥装配体不得同时装）

    ⚠️ **不把咬合边当 goto**：咬合边是「哪些件能拼在一起」，
    不是剧情路径。当 goto 会产出**伪剧情**。咬合关系由
    `零件库/check_assembly.py` 判定，dse 这边只管装配路径的可达性。
    """
    asm_dir = src_dir / "装配体"
    if not asm_dir.is_dir():
        print(f"[FAIL] 装配体目录不存在：{asm_dir}", file=sys.stderr)
        return 1

    files = sorted(asm_dir.glob("ASM-*.md"))
    if not files:
        print(f"[FAIL] {asm_dir} 下没有 ASM-*.md", file=sys.stderr)
        return 1

    # 零件 ID → 名称（用于场景标题）
    names: dict[str, str] = {}
    for card in ["02-制度型零件.md", "03-机制型零件.md",
                 "04-地理与资源型零件.md", "05-历史与接口型零件.md"]:
        cp = src_dir / card
        if not cp.exists():
            continue
        text = read_text(cp)
        for m in re.finditer(r"^## `(WB-[A-Z]+-\d{4})`\s*(.+?)\s*$", text, re.M):
            names[m.group(1)] = m.group(2).strip()

    head: list[str] = [
        "# 自动生成 —— 勿手改（派生源：零件库/装配体/ASM-*.md）",
        "# 生成器：tools/procedural/md2dse.py assembly",
        "# 改内容请改装配体后重跑；手改会被下次生成覆盖。",
        "pack:",
        "  id: parts-assembly",
        "  name: 零件库装配体投影",
        "  version: 0.1.0",
    ]
    body: list[str] = []

    entries: list[str] = []
    total_steps = 0
    for fp in files:
        text = read_text(fp)
        mid = ASM_ID_RE.search(text)
        asm_id = mid.group(1) if mid else fp.stem
        short = asm_id.replace("ASM-", "").lower()

        topic_m = ASM_TOPIC_RE.search(text)
        topic = one_line(topic_m.group(1)) if topic_m else asm_id
        gran_m = ASM_GRAN_RE.search(text)
        gran = gran_m.group(1).strip() if gran_m else "未知"
        drv_m = ASM_DRIVER_RE.search(text)
        driver = drv_m.group(1) if drv_m else ""

        # 成员表
        mem_block = section_block(text, r"###\s*2\.2\s*成员件与角色(.*?)(?=\n###\s|\n##\s)")
        members = _asm_member_rows(mem_block or "")
        # Δ 序列
        delta_block = section_block(text, r"##\s*四、Δ\s*序列(.*?)(?=\n##\s)")
        deltas = _asm_delta_rows(delta_block or "")
        steps = [d for d in deltas if d["step"] > 0]

        if not steps:
            print(f"[WARN] {fp.name}：未解析到 Δ 序列步骤，跳过", file=sys.stderr)
            continue

        entries.append(short)
        total_steps += len(steps)

        # ⚠️ `scenes:` **只能出现一次**（写在循环外）。
        #    YAML 重复键会被**静默吞值**（前一个被后一个覆盖）——
        #    实测踩坑：写在循环里导致 10 个 `scenes:`，只剩最后一个装配体的
        #    场景，dse check 却「通过」（6 场景 / 可达 0），错得很隐蔽。
        body.append(f"  {short}-step0:")
        body.append(f"    title: {yaml_quote(asm_id + ' · 装配起点')}")
        body.append(f"    text: {yaml_quote(topic)}")
        body.append("    onEnter:")
        body.append("      visits:")
        body.append(f"        {short}: +1")
        body.append("    choices:")
        body.append(f"      - text: {yaml_quote('开始装配（粒度：' + gran + '）')}")
        body.append(f"        goto: {short}-step1")

        for idx, d in enumerate(steps, start=1):
            sid = f"{short}-step{idx}"
            pid = d["pid"]
            pname = names.get(pid, pid)
            step_no = d["step"]
            scene_title = f"{asm_id} 步{step_no}：{pname}"
            body.append(f"  {sid}:")
            body.append(f"    title: {yaml_quote(scene_title)}")
            body.append(f"    text: {yaml_quote(one_line(d['delta']))}")
            body.append("    onEnter:")
            body.append("      visits:")
            body.append(f"        {sid}: +1")
            # Δ → onEnter（**场景级效果**；`do` 是选项级字段，schema 不认 ——
            # 实测踩坑：写成 do 被 dse check 以 additionalProperties 拒绝）
            deltas_map = {}
            for q, v in d["qty"].items():
                if q in QTY_CHARS:
                    deltas_map[q] = v
            if deltas_map:
                for q, v in deltas_map.items():
                    body.append(f"      {QTY_ASCII.get(q, q)}: {v:+d}")
            body.append("    choices:")
            if idx < len(steps):
                nxt = f"{short}-step{idx + 1}"
                next_step = steps[idx]["step"]
                next_pid = steps[idx]["pid"]
                label = f"推进到步 {next_step}（{next_pid}）"
                body.append(f"      - text: {yaml_quote(label)}")
                body.append(f"        goto: {nxt}")
            else:
                body.append('      - text: "装配完成"')
                body.append(f"        goto: {short}-done")

        # 结局：装配后状态
        body.append(f"  {short}-done:")
        body.append(f"    title: {yaml_quote(asm_id + ' · 装配完成')}")
        final = ", ".join(f"{q} = {v}" for q, v in (steps[-1]["qty"].items() if steps else []))
        body.append(f"    text: {yaml_quote((('装配后状态：' + final + '。') if final else '装配完成。') + ('驱动量 ' + driver + '。' if driver else ''))}")

    if not entries:
        print("[FAIL] 没有解析出任何装配体", file=sys.stderr)
        return 1

    # 自带 index 场景：列出全部装配体，让本包自成一个入口
    # （由顶层 index.yml 汇总；否则装配体 2~10 不可达）。
    aidx = "asm-index"
    index_block = [
        f"  {aidx}:",
        f"    title: {yaml_quote('零件库 · 装配体总览')}",
        f"    text: {yaml_quote('%d 个装配体 / %d 个装配步。每个装配体是一条装配路径。' % (len(entries), total_steps))}",
        f"    onEnter:",
        f"      visits:",
        f"        {aidx}: +1",
        f"    choices:",
    ]
    for e in entries:
        index_block.append(f"      - text: {yaml_quote('装配体 ' + e.upper())}")
        index_block.append(f"        goto: {e}-step0")

    # pack 段（head）与 scenes 段（body）分开构造。
    # ⚠️ `scenes:` 只能出现一次 —— YAML 重复键会被静默吞值。
    out_lines = head + [f"  entry: {aidx}", "scenes:"] + index_block + body

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(out_lines) + "\n")

    print(f"[OK] assembly：解析 {len(entries)} 个装配体 / {total_steps} 个装配步 → {out}")
    for e in entries:
        print(f"     {e}")
    return 0


# ==============================================================================
# 自检 · 重复键检测（铁律 3）
# ==============================================================================

def check_duplicate_keys(path: Path) -> list[str]:
    """检测 YAML 重复键（PyYAML 默认静默吞掉前一个，此处显式报错）。

    用 yaml.compose() 拿节点树，手工比对同一 mapping 内的重复键。
    若环境无 PyYAML，则退回**文本级**启发式检测（同层同名 key）。
    """
    problems: list[str] = []
    text = io.open(path, encoding="utf-8").read()

    try:
        import yaml  # type: ignore
    except ImportError:
        return _check_dupe_textual(text, path)

    try:
        node = yaml.compose(text)
    except Exception as exc:                       # noqa: BLE001
        return [f"{path}: YAML 解析失败：{exc}"]

    def walk(n, trail: str) -> None:
        if isinstance(n, yaml.MappingNode):
            seen: dict[str, int] = {}
            for k, _v in n.value:
                key = getattr(k, "value", None)
                if not isinstance(key, str):
                    continue
                if key in seen:
                    problems.append(
                        f"{path}: 重复键 `{key}`（第 {seen[key]} 行与第 {k.start_mark.line + 1} 行）"
                    )
                else:
                    seen[key] = k.start_mark.line + 1
            for k, v in n.value:
                walk(v, trail)
        elif isinstance(n, yaml.SequenceNode):
            for item in n.value:
                walk(item, trail)

    walk(node, "")
    return problems


def _check_dupe_textual(text: str, path: Path) -> list[str]:
    """无 PyYAML 时的文本级兜底：同缩进层出现同名 key 即报警。"""
    problems: list[str] = []
    stack: list[tuple[int, str]] = []      # (indent, key)
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        m = re.match(r"^\s*([A-Za-z_$][\w$.-]*)\s*:", line)
        if not m:
            continue
        key = m.group(1)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        for _ind, k in stack:
            if k == key:
                problems.append(f"{path}: 疑似重复键 `{key}`（第 {lineno} 行）")
                break
        if not line.rstrip().endswith(":"):
            stack.append((indent, key))
    return problems


# ==============================================================================
# 自检 · schema 体检（铁律 2）
# ==============================================================================

def check_schema(path: Path) -> list[str]:
    """校验内容包是否符合 dse-core 的 scene.schema.json 关键约束。

    只查**能本地判定**的部分（不依赖 dse-core 本身）：
      · scene id 是否匹配 ASCII 正则
      · Choice 是否只用了 schema 允许的 5 个字段
      · goto 数组项是否只用了 to / weight
    """
    problems: list[str] = []
    try:
        import yaml  # type: ignore
    except ImportError:
        return [f"{path}: 未装 PyYAML，跳过 schema 体检（pip install pyyaml）"]

    try:
        data = yaml.safe_load(io.open(path, encoding="utf-8"))
    except Exception as exc:                       # noqa: BLE001
        return [f"{path}: YAML 解析失败：{exc}"]
    if not isinstance(data, dict):
        return [f"{path}: 顶层不是 mapping"]

    scenes = data.get("scenes")
    if not isinstance(scenes, dict):
        return [f"{path}: 缺少 scenes 段"]

    CHOICE_KEYS = {"text", "if", "once", "do", "goto"}
    GOTO_ITEM_KEYS = {"to", "weight"}

    for sid, sc in scenes.items():
        if not SCENE_ID_RE.match(str(sid)):
            problems.append(f"{path}: 场景 ID 不合法：{sid!r}")
        if not isinstance(sc, dict):
            problems.append(f"{path}: 场景 {sid} 不是 mapping")
            continue
        for idx, ch in enumerate(sc.get("choices") or []):
            if not isinstance(ch, dict):
                problems.append(f"{path}: {sid} 第 {idx + 1} 个选项不是 mapping")
                continue
            extra = set(ch.keys()) - CHOICE_KEYS
            if extra:
                problems.append(
                    f"{path}: {sid} 第 {idx + 1} 个选项含非法字段 {sorted(extra)}"
                    f"（schema 只允许 {sorted(CHOICE_KEYS)}）"
                )
            g = ch.get("goto")
            if isinstance(g, list):
                for j, item in enumerate(g):
                    if isinstance(item, dict):
                        iextra = set(item.keys()) - GOTO_ITEM_KEYS
                        if iextra:
                            problems.append(
                                f"{path}: {sid} 第 {idx + 1} 个选项的 goto 第 {j + 1} 项"
                                f"含非法字段 {sorted(iextra)}（只允许 {sorted(GOTO_ITEM_KEYS)}）"
                            )
    return problems


# ==============================================================================
# CLI
# ==============================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="md2dse.py",
        description="Markdown 规划文档 → dse-core 内容包转换器",
    )
    # 用子命令而非「位置参数 + --check 标志」：
    # argparse 在位置参数与可选标志混排时，会把标志后的第一个位置参数
    # 错误地分配给第一个位置参数（本仓实测踩过：--check 后的路径被当成 mode）。
    # 子命令形式无此歧义。
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_out = sub.add_parser("outline", help="四层大纲主线 → 场景链")
    p_out.add_argument("source")
    p_out.add_argument("-o", "--output")

    p_beats = sub.add_parser("beats", help="节拍表 → 场景序列")
    p_beats.add_argument("source")
    p_beats.add_argument("-o", "--output")
    p_beats.add_argument("--pack-id", default="kz-beats",
                         help="内容包 ID（多作品并存须唯一；默认 kz-beats 兼容旧包）")

    p_parts = sub.add_parser("parts", help="零件库装配体 → 装配路径场景链")
    p_parts.add_argument("source", help="零件库目录（含 装配体/ 与 0X-*.md）")
    p_parts.add_argument("-o", "--output")

    p_asm = sub.add_parser("assembly", help="零件库装配体 → 装配路径场景链")
    p_asm.add_argument("source", help="零件库目录（含 装配体/ 与 0X-*.md）")
    p_asm.add_argument("-o", "--output")

    p_check = sub.add_parser("check", help="自检：重复键 + schema 体检")
    p_check.add_argument("source", help="YAML 路径（多个用逗号分隔）")

    args = ap.parse_args(argv)

    if args.cmd == "check":
        if not args.source:
            print("[FAIL] check 模式需要给出至少一个 YAML 路径", file=sys.stderr)
            return 1
        targets = [t.strip() for t in args.source.split(",") if t.strip()]
        problems: list[str] = []
        for p in targets:
            path = Path(p)
            if not path.exists():
                problems.append(f"{path}: 文件不存在")
                continue
            problems += check_duplicate_keys(path)
            problems += check_schema(path)
        if problems:
            print(f"[FAIL] 发现 {len(problems)} 个问题：", file=sys.stderr)
            for p in problems:
                print(f"   - {p}", file=sys.stderr)
            return 1
        print(f"[OK] {len(targets)} 个内容包体检通过（重复键 / schema）")
        return 0

    if not args.source:
        print("[FAIL] 需要给出源 Markdown 路径", file=sys.stderr)
        return 1
    src = Path(args.source)
    out = Path(args.output) if args.output else src.with_suffix(".yml")

    fn = {"outline": convert_outline, "beats": convert_beats,
          "parts": convert_parts, "assembly": convert_assembly}[args.cmd]
    if args.cmd == "beats":
        return fn(src, out, args.pack_id)
    return fn(src, out)


if __name__ == "__main__":
    sys.exit(main())
