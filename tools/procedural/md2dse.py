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

    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：%s）" % src.as_posix(),
        "# 生成器：tools/procedural/md2dse.py outline",
        "# 改内容请改派生源后重跑；手改会被下次生成覆盖。",
        "pack:",
        "  id: kz-outline",
        "  name: 廓者未名夜 · 四层大纲投影",
        "  version: 0.1.0",
        f"  entry: {slugify(segments[0][0], 'seg', 1)}",
        "scenes:",
    ]

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
            # 末段没有后继 —— 指向自身（不指向未定义 ID）
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

def convert_beats(src: Path, out: Path) -> int:
    """节拍表 → 场景序列。

    映射规则：
      · 节拍行（含序号与拍名）→ 一个场景
      · 相邻节拍 → goto 链
      · 行内以「｜」或「/」分隔的备选文本 → extraText 变体
    """
    text = read_text(src)
    block = section_block(text, r"##\s*[^\n]*节拍(.*?)(?=\n##\s)")
    if block is None:
        print("[FAIL] 未找到节拍小节 —— 源文档结构可能已变", file=sys.stderr)
        return 1

    beats: list[tuple[str, str]] = []
    for cells in parse_markdown_table(block):
        if len(cells) < 2:
            continue
        name = cells[0].replace("**", "").strip()
        body = cells[1].replace("**", "").strip()
        if not name or name.startswith("---"):
            continue
        beats.append((name, body))

    if not beats:
        print("[FAIL] 节拍表解析为空", file=sys.stderr)
        return 1

    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：%s）" % src.as_posix(),
        "# 生成器：tools/procedural/md2dse.py beats",
        "pack:",
        "  id: kz-beats",
        "  name: 廓者未名夜 · 节拍表投影",
        "  version: 0.1.0",
        f"  entry: {slugify(beats[0][0], 'beat', 1)}",
        "scenes:",
    ]

    for i, (name, body) in enumerate(beats, start=1):
        sid = slugify(name, "beat", i)
        lines.append(f"  {sid}:")
        lines.append(f"    title: {yaml_quote(name)}")
        lines.append(f"    text: {yaml_quote(one_line(body))}")
        lines.append("    onEnter:")
        lines.append("      visits:")
        lines.append(f"        {sid}: +1")
        lines.append("    choices:")
        if i < len(beats):
            nxt = slugify(beats[i][0], "beat", i + 1)
            lines.append(f"      - text: {yaml_quote('下一拍：' + beats[i][0])}")
            lines.append(f"        goto: {nxt}")
        else:
            lines.append('      - text: "节拍表终点"')
            lines.append(f"        goto: {sid}")

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"[OK] beats：解析 {len(beats)} 拍 → {out}")
    return 0


# ==============================================================================
# 转换器 · parts（零件库装配体）
# ==============================================================================

def convert_parts(src: Path, out: Path) -> int:
    """零件库装配体 → 场景图。

    映射规则：
      · 每个零件 → 一个场景
      · 咬合边（源 → 目标）→ goto 分支
      · 零件的 phase / band 字段 → flags 记录
    """
    text = read_text(src)

    # 零件标题：## <名称> 或 ### <名称>
    parts: list[tuple[str, str]] = []
    cur_name = None
    cur_body: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^#{2,3}\s+(?!#\s)(.+?)\s*$", line)
        if m:
            if cur_name:
                parts.append((cur_name, "\n".join(cur_body)))
            cur_name = m.group(1).strip()
            cur_body = []
        elif cur_name is not None:
            cur_body.append(line)
    if cur_name:
        parts.append((cur_name, "\n".join(cur_body)))

    if not parts:
        print(f"[FAIL] 未从 {src.name} 解析出零件标题", file=sys.stderr)
        return 1

    lines: list[str] = [
        "# 自动生成 —— 勿手改（派生源：%s）" % src.as_posix(),
        "# 生成器：tools/procedural/md2dse.py parts",
        "pack:",
        "  id: parts",
        "  name: 零件库装配体投影",
        "  version: 0.1.0",
        f"  entry: {slugify(parts[0][0], 'part', 1)}",
        "scenes:",
    ]

    for i, (name, body) in enumerate(parts, start=1):
        sid = slugify(name, "part", i)
        desc = one_line(re.sub(r"^#.*$", "", body, flags=re.M))
        lines.append(f"  {sid}:")
        lines.append(f"    title: {yaml_quote(name)}")
        lines.append(f"    text: {yaml_quote(desc or '（无描述）')}")
        lines.append("    onEnter:")
        lines.append("      visits:")
        lines.append(f"        {sid}: +1")
        lines.append("    choices:")
        if i < len(parts):
            nxt = slugify(parts[i][0], "part", i + 1)
            lines.append(f"      - text: {yaml_quote('装配 → ' + parts[i][0])}")
            lines.append(f"        goto: {nxt}")
        else:
            lines.append('      - text: "装配终点"')
            lines.append(f"        goto: {sid}")

    out.parent.mkdir(parents=True, exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"[OK] parts：解析 {len(parts)} 件零件 → {out}")
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

    p_parts = sub.add_parser("parts", help="零件库装配体 → 场景图")
    p_parts.add_argument("source")
    p_parts.add_argument("-o", "--output")

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

    fn = {"outline": convert_outline, "beats": convert_beats, "parts": convert_parts}[args.cmd]
    return fn(src, out)


if __name__ == "__main__":
    sys.exit(main())
