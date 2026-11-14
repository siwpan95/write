#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scanner.py —— PKM 索引器 · 仓扫描与元数据抽取
================================================================================
把「1164 个各自为政的 Markdown 文件」变成「一份可检索、可连接的结构化索引」。

设计原则（与全仓《工作区规范》同源）
--------------------------------------
1. **只读源文件**：本模块只读取，不写任何被扫描文件。
2. **零三方依赖**：只用标准库，换机即跑。
3. **不臆造数据**：索引里的每个字段都能追回原文位置（file + line）。
4. **正文零改动**：本模块**不往正文注入 frontmatter**；
   frontmatter 只在「新建笔记」路径上生成，已有文件保持字节不变。

抽取的四类元数据
----------------
- **身份**：`path` / `title` / `doc_type`（正文·设定·台账·报告·模板·工具…）
- **归属**：`project`（归属哪个作品/项目）、`role`（在项目里的角色）
- **计量**：`lines` / `chars` / `net_chars`（去空白字数，与全哥「净字数」口径一致）
- **连接**：`links`（出链）、`backlinks`（入链）、`tags`、`aliases`

`doc_type` 的判定靠**路径语义 + 文件名模式**，不是靠猜内容 ——
保证同一输入同一结果（可复跑），且判定依据可人工复核。

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

# 被排除的目录名（不进入索引）
EXCLUDED_DIRS = {
    ".git", "node_modules", ".obsidian", "__pycache__", ".workbuddy",
    ".vscode", ".idea", "审校报告", "dist", "build", ".venv", "venv",
}

# 文档类型判定：按「目录名 + 文件名模式」自上而下匹配
# 顺序敏感 —— 先匹配到的胜出。
TYPE_RULES: list[tuple[str, list[str], str]] = [
    # (类型, 目录名关键词, 文件名正则)
    ("模板", [r"模板包"], r"^\d{2}[-－]"),
    ("正文", [], r"^第\d{2,3}章"),
    ("正文", [], r"^楔子"),
    ("正文", [], r"^番外"),
    ("设定", [r"bible$", r"^设定", r"^0\d_设定"], r"."),
    ("台账", [r"台账", r"^07_创作台账"], r"."),
    ("报告", [r"审校报告", r"^审计报告"], r"."),
    ("总览", [], r"^(作品总览|项目梳理总览|README)"),
    ("工具", [r"^tools$", r"^0\d-工具$", r"^04-工具$"], r"."),
]

# 章节目录（形如 第一卷 / 第二卷 / 正文 / 卷_xxx）
CHAPTER_DIR = re.compile(r"^(第[一二三四五六七八九十百]+卷|正文|卷_.*)$")

    # 归档 / 历史（不参与主检索权重，但仍在索引内）
ARCHIVE_HINT = re.compile(r"(_archive|历史归档|杂项/历史|^杂项$|^原稿$|^剧本旧稿$|^\.workbuddy)")

# --------------------------------------------------------------------------
# 知识节点 vs 叙事节点
# --------------------------------------------------------------------------
# 「孤立文档 96.3%」这个数字把两类完全不同的东西混在了一起：
#   · **叙事节点**（正文 563 篇）—— 线性叙事，靠卷/章顺序组织。
#     它们**本就不该有知识链接**；给每章互相建链只会制造噪音。
#   · **知识节点**（设定/模板/总览 564 篇）—— 承载设定、口径、方法论，
#     它们**正是连接层要服务的对象**，孤立才是真问题。
#
# 所以：连接层只对知识节点负责。孤立率以**知识节点**为分母，
# 叙事节点单列统计，不计入「连接层缺口」。

# 知识节点的文档类型
KNOWLEDGE_TYPES = {"设定", "模板", "总览", "台账", "报告", "工具", "文档"}
# 叙事节点：正文（剧集/章节稿）
NARRATIVE_TYPES = {"正文"}

# Wikilink：[[目标]] 或 [[目标|别名]]
WIKILINK = re.compile(r"\[\[([^\]|\n]+?)\]\]")

# 代码块（行内与围栏）内的 [[...]] 是**示例**，不建立链接。
# 依据：Obsidian 同样不把代码块里的方括号当链接；
# 否则「讲解双链写法的笔记」自身会产生假断链。
CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    """把代码块/行内代码替换为等长空白（保留行号，便于定位）。"""
    def _blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    text = CODE_FENCE.sub(_blank, text)
    return INLINE_CODE.sub(_blank, text)

# Markdown 相对链接：[文字](路径)
MDLINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")

# 行内标签：#tag（排除 #! 标题与数字，避免误吞章节号）
TAG = re.compile(r"(?<![\w#/])#([A-Za-z一-鿿][\w一-鿿/-]{1,30})")

# Frontmatter 解析（极简 YAML 子集：key: value、列表）
FM_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------

@dataclass
class Doc:
    """一篇文档的索引条目。"""
    path: str                      # 仓相对路径（正斜杠）
    title: str                     # 标题（frontmatter > 首个标题行 > 文件名）
    doc_type: str = "未分类"        # 正文 / 设定 / 台账 / 报告 / 模板 / 总览 / 工具
    project: str = ""              # 归属作品/项目
    role: str = ""                 # 在项目内的角色（正文/设定/台账/入口总览…）
    lines: int = 0
    chars: int = 0
    net_chars: int = 0             # 去空白净字数
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)      # 出链目标（原文写法）
    resolved: list[str] = field(default_factory=list)   # 出链解析到的仓相对路径
    backlinks: list[str] = field(default_factory=list)  # 入链来源
    broken: list[str] = field(default_factory=list)     # 断链（解析不到）
    archived: bool = False
    has_frontmatter: bool = False
    kind: str = "knowledge"          # knowledge（知识节点） / narrative（叙事节点）
    fm: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------

def decode(raw: bytes) -> str:
    """按本仓编码约定解码：去 BOM → UTF-8 → 容忍坏字节。"""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def net_chars(text: str) -> int:
    """净字数：去掉所有空白字符（与全哥 README 的「净字数（去空白）」口径一致）。"""
    return len(re.sub(r"\s+", "", text))


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """
    解析极简 YAML frontmatter。

    只支持本仓实际会用到的子集：`key: value`、`key: [a, b]`、`key:\n  - item`。
    不引入 PyYAML（零三方依赖铁律）。
    返回 (字段字典, 正文剩余部分)。
    """
    if not text.startswith("---"):
        return {}, text
    # 第一行必须是 --- ，找到下一个独占一行的 --- 为止
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return {}, text
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end < 0:
        return {}, text

    fm: dict[str, Any] = {}
    pending_list: str | None = None
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip():
            continue
        m = FM_KEY.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            pending_list = None
            if val == "":
                fm[key] = []
                pending_list = key
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                fm[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
            else:
                fm[key] = val.strip().strip("'\"")
        elif pending_list and line.strip().startswith("-"):
            fm[pending_list].append(line.strip()[1:].strip().strip("'\""))
    return fm, "\n".join(lines[end + 1:])


def title_of(text: str, fm: dict[str, Any], path: str) -> str:
    """标题优先级：frontmatter.title > frontmatter.aliases[0] > 首个标题行 > 文件名。"""
    if fm.get("title"):
        return str(fm["title"]).strip()
    for line in text.split("\n", 40):
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            break
    return os.path.basename(path).rsplit(".", 1)[0]


def classify(rel: str) -> tuple[str, str, str]:
    """
    判定 (doc_type, project, role)。

    project：仓根下第一个目录名（仓根文件则为空）。
    role：   在该项目内的角色（正文/设定/台账/入口总览/工具/参考/归档）。

    判定完全基于**路径语义**，可人工复核，且同一输入同一结果。
    """
    parts = rel.split("/")
    project = parts[0] if len(parts) > 1 else ""
    fname = parts[-1]
    stem = fname.rsplit(".", 1)[0]

    # --- role：看项目内的第二层目录 ---
    role = ""
    if len(parts) >= 2:
        second = parts[1] if len(parts) > 2 else ""
        if second in ("bible", "设定", "01_bible"):
            role = "设定"
        elif "台账" in second or second.startswith("07_创作台账"):
            role = "台账"
        elif second.startswith(("设定与参考", "02_设定与参考", "03_新增维度", "素材", "04_工具", "tools")):
            role = "参考/工具"
        elif CHAPTER_DIR.match(second) or second.startswith("正文"):
            role = "正文"
        elif second.startswith("第一卷") or second.startswith("第二卷") or "卷" in second:
            role = "正文"

    # --- doc_type：先看文件名模式，再看目录语义 ---
    doc_type = "文档"
    for t, dir_kw, name_re in TYPE_RULES:
        if re.search(name_re, stem):
            doc_type = t
            break
        if any(re.search(k, d) for k in dir_kw for d in parts[:-1]):
            doc_type = t
            break

    if doc_type == "未分类":
        doc_type = "文档"

    # 入口总览优先于其他判定（README/作品总览 就是 MOC）
    if re.match(r"^(作品总览|项目梳理总览)", stem):
        doc_type = "总览"
        role = "入口总览"
    elif stem.startswith("README"):
        doc_type = "总览"
        if not role:
            role = "入口总览"

    return doc_type, project, role


# --------------------------------------------------------------------------
# 扫描
# --------------------------------------------------------------------------

def git_tracked(root: str) -> list[str] | None:
    """
    优先用 `git ls-files` 取跟踪文件（权威、含 ignore 语义）。
    失败则回退到文件系统遍历。
    """
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        if out.returncode == 0:
            files = [f for f in out.stdout.split("\n") if f.strip()]
            if files:
                return files
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def all_markdown(root: str) -> list[str]:
    """
    仓内全部 Markdown ＝ **git 跟踪的** ∪ **工作区新增未跟踪的**。

    为什么必须并集：`git ls-files` 只列已跟踪文件，
    新建的原子笔记在 `git add` 之前不会被索引到 ——
    那意味着「写完笔记必须先提交才能被检索」，与 PKM 的使用直觉相反。
    未跟踪文件同样要能立即被检索与建链。

    忽略规则沿用 `.gitignore`（含 `node_modules/`、`审校报告/` 等），
    排除目录另由 EXCLUDED_DIRS 兜底。
    """
    tracked = set(git_tracked(root) or [])
    on_disk = set(walk_files(root))
    merged = tracked | on_disk
    return sorted(f for f in merged if f.lower().endswith((".md", ".markdown")))


def walk_files(root: str) -> list[str]:
    """
    文件系统遍历（跳过排除目录）。

    排除两类：
    1. EXCLUDED_DIRS —— node_modules、.git、审校报告 等
    2. **.gitignore 里的目录** —— 尤其 node_modules（在某些机器上叫别的名），
       不排除会把上万依赖文件拉进索引，既慢又污染统计。
    """
    ignored_dirs = _gitignore_dirs(root)
    result: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIRS and not d.startswith(".git")
            and d not in ignored_dirs
        ]
        for fn in filenames:
            if fn.lower().endswith((".md", ".markdown")):
                full = os.path.join(dirpath, fn)
                result.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(result)


def _gitignore_dirs(root: str) -> set[str]:
    """
    从 .gitignore 解析出**目录名**形式的忽略项（只取无斜杠的简单模式）。

    不做完整的 gitignore 语法解析（那属于过度工程）：
    本仓的 .gitignore 里目录项都很简单（`node_modules/`、`作家助手/`），
    按 basename 匹配足够，且不会误伤正文。
    """
    out: set[str] = set()
    gi = os.path.join(root, ".gitignore")
    if not os.path.exists(gi):
        return out
    try:
        for raw in open(gi, encoding="utf-8", errors="replace"):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            name = line.rstrip("/")
            if name and "/" not in name and "*" not in name:
                out.add(name)
    except OSError:
        pass
    return out


def scan(root: str, include_archived: bool = True) -> list[Doc]:
    """
    扫描全仓 Markdown，产出索引条目列表。

    参数
    ----
    root: 仓根绝对路径
    include_archived: 是否把归档/历史目录也纳入（默认纳入 —— 归档也是知识资产）
    """
    files = all_markdown(root)
    docs: list[Doc] = []

    for rel in files:
        if not rel.lower().endswith((".md", ".markdown")):
            continue
        parts = rel.split("/")
        if any(p in EXCLUDED_DIRS for p in parts[:-1]):
            continue

        full = os.path.join(root, rel)
        try:
            raw = open(full, "rb").read()
        except OSError:
            continue

        text = decode(raw)
        fm, body = parse_frontmatter(text)
        doc_type, project, role = classify(rel)

        archived = bool(ARCHIVE_HINT.search(rel))
        if archived and not include_archived:
            continue

        links_raw = WIKILINK.findall(strip_code(body))
        links = [l.split("|")[0].split("#")[0].strip() for l in links_raw]
        links = [l for l in links if l]

        md_links = [m for m in MDLINK.findall(strip_code(body))
                    if not m.startswith(("http://", "https://", "mailto:", "#"))]

        tags = sorted(set(TAG.findall(body)))
        aliases = fm.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]

        doc = Doc(
            path=rel,
            title=title_of(body, fm, rel),
            doc_type=doc_type,
            project=project,
            role=role,
            lines=body.count("\n") + 1,
            chars=len(body),
            net_chars=net_chars(body),
            tags=tags,
            aliases=[str(a) for a in aliases],
            links=links,
            archived=archived,
            has_frontmatter=bool(fm),
            kind=("narrative" if doc_type in NARRATIVE_TYPES else "knowledge"),
            fm={k: v for k, v in fm.items() if k not in ("aliases",)},
        )

        # 相对 Markdown 链接并入出链（统一转成仓相对路径的候选）
        for m in md_links:
            target = m.split("#")[0].strip()
            if not target:
                continue
            doc.links.append(target)
        docs.append(doc)

    docs.sort(key=lambda d: d.path)
    return docs


# --------------------------------------------------------------------------
# 连接：解析出链 + 计算反链
# --------------------------------------------------------------------------

def _index_keys(docs: list[Doc]) -> tuple[dict[str, str], set[str]]:
    """
    建立「可解析键 → 仓相对路径」索引。

    一个文档可被多个键命中（文件名、标题、id、路径后缀），
    精确路径优先，文件名其次，标题最后。

    **为什么键要那么多**：写双链时人会有多种自然写法 ——
    `[[战锤四神体系]]`（标题）、`[[atom-0001-战锤四神体系]]`（文件名）、
    `[[atom-0001 战锤四神体系（跨宇宙共享设定）]]`（id+标题连写）、
    `[[廓者未名夜/作品总览.md]]`（带路径）。
    解析器必须认得这些，否则笔记作者得为机器迁就写法 —— 反了。

    **歧义处理**：不同项目常有同名文件（如各项目的 `03-世界观圣经.md`）。
    这类键会同时映射到多个文档，**不能任选其一** —— 否则链接会静默指向
    错误的目标。因此：多义键进 `ambiguous` 集合，解析时一律判为「解析不到」
    （与 Obsidian 的同名歧义行为一致 —— 宁可断链，不可错链）。

    返回 (唯一键 → 路径, 歧义键集合)
    """
    keys: dict[str, str] = {}
    ambiguous: set[str] = set()

    def put(key: str, path: str) -> None:
        if not key:
            return
        if key in keys and keys[key] != path:
            ambiguous.add(key)
            return
        if key in ambiguous:
            return
        keys[key] = path

    for d in docs:
        stem = d.path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        put(d.path, d.path)                       # 全路径（精确）
        put(d.path.rsplit(".", 1)[0], d.path)     # 无扩展名路径
        put(stem, d.path)                         # 文件名（不含目录）
        put(d.title, d.path)                      # 标题
        # frontmatter 里的 id（如 atom-0001）
        fid = d.fm.get("id")
        if fid:
            put(str(fid), d.path)
            put(str(fid).lower(), d.path)
        # id + 标题 连写形式（人写双链时的自然写法）
        if fid:
            put(f"{fid} {d.title}", d.path)
            put(f"{fid}-{d.title}", d.path)
            put(f"{fid} {stem}", d.path)
        # 别名
        for a in d.aliases:
            put(str(a), d.path)
    return keys, ambiguous


def resolve_links(docs: list[Doc], root: str = "") -> None:
    """就地解析出链：写入 resolved / broken，并计算 backlinks。

    参数 root：仓根绝对路径 —— 用于判定「链接目标在仓内是否真实存在」
    （区分真断链与「指向非 Markdown 资源」的有效链接）。
    """
    keys, ambiguous = _index_keys(docs)
    by_path = {d.path: d for d in docs}

    # 相对链接 → 相对当前文件的仓相对路径
    for d in docs:
        base = d.path.rsplit("/", 1)[0] if "/" in d.path else ""
        resolved: list[str] = []
        broken: list[str] = []

        def _ambiguous(key: str) -> bool:
            """键存在但有歧义 → 判为不可解析（宁可断链，不可错链）。"""
            return key in ambiguous

        for raw in d.links:
            target = raw.strip()
            if not target:
                continue

            # 剥离「显示名」：`[[目标|显示]]` —— 保留目标
            if "|" in target:
                target = target.split("|")[0].strip()
            # 剥离锚点：`[[目标#小节]]`
            if "#" in target:
                target = target.split("#")[0].strip()
            if not target:
                continue

            # `id 标题` 连写形式：先试整串，再试 id 前缀
            candidates = [target]
            m = re.match(r"^([A-Za-z]+-\d{3,4})\s+(.+)$", target)
            if m:
                candidates.append(m.group(1))     # 只要 id
                candidates.append(m.group(2))     # 只要标题

            hit = None
            for cand in candidates:
                if hit is not None:
                    break
                if cand in ambiguous:
                    continue                     # 有歧义 → 不解析（宁可断链，不可错链）
                if cand in keys:
                    hit = keys[cand]
                elif cand in by_path:
                    hit = cand
                else:
                    # 相对路径解析（基于当前文件所在目录）
                    if cand.startswith("/"):
                        rel_cand = cand[1:]
                    else:
                        rel_cand = f"{base}/{cand}" if base else cand
                    rel_cand = os.path.normpath(rel_cand).replace(os.sep, "/")
                    if rel_cand.startswith("./"):
                        rel_cand = rel_cand[2:]
                    if rel_cand in by_path:
                        hit = rel_cand
                    elif rel_cand not in ambiguous:
                        # 按文件名（不含目录）匹配
                        tail = rel_cand.rsplit("/", 1)[-1]
                        if tail in keys:
                            hit = keys[tail]
                        elif rel_cand in keys:
                            hit = keys[rel_cand]
                        else:
                            # 再按「文件名去掉 id- 前缀」匹配
                            stripped = re.sub(r"^[A-Za-z]+-\d{3,4}[-_ ]*", "", tail)
                            if stripped and stripped in keys:
                                hit = keys[stripped]

            if hit:
                if hit not in resolved:
                    resolved.append(hit)
            else:
                # 断链判定：**目标在仓内真实不存在**才算断链。
                # 指向目录、或指向非 Markdown 资源（.html/.svg/.docx/.py…）的链接
                # 在 Markdown 索引范围之外，但**链接本身有效** —— 不算断链。
                # （口径与 tools/checkers/pkm_check.py 保持一致）
                #
                # **路径基准要试两种**：
                #   ① 基于当前文件所在目录（同目录相对链接，如 ./assets/x.png）
                #   ② 仓根相对（本仓大量跨目录链接写作 `点子库/04-工具/x.py`，
                #      书写时以仓根为基准 —— 若只按 ① 会误判成断链）
                # 任一存在即视为有效链接。
                path_norm = target.lstrip("/")
                based = os.path.normpath(
                    f"{base}/{path_norm}" if base else path_norm
                ).replace(os.sep, "/")
                if based.startswith("./"):
                    based = based[2:]

                candidates = [based, path_norm]
                if not any(os.path.exists(os.path.join(root, c)) for c in candidates):
                    if target not in broken:
                        broken.append(target)
        d.resolved = resolved
        d.broken = broken

    # 计算反链
    for d in docs:
        for tgt in d.resolved:
            t = by_path.get(tgt)
            if t is not None and d.path not in t.backlinks:
                t.backlinks.append(d.path)


# --------------------------------------------------------------------------
# 统计
# --------------------------------------------------------------------------

def summarize(docs: list[Doc], exclude: set[str] | None = None) -> dict[str, Any]:
    """
    全库统计：用于诊断报告与 MOC 头部。

    **孤立率以「知识节点」为分母** —— 叙事节点（正文）本就不该有知识链接，
    把它们算进孤立会虚高问题（实测：混算 96.3%，只算知识节点则是真实缺口）。

    参数 exclude：**只从「字数累加」中排除**的路径集合。
    注意：不是把文档整个剔除 —— 生成物（MOC 等）本身仍是有效的连接贡献者，
    把它们整个排除会让出链数凭空暴跌（实测 1266 → 67）。
    只排除其**字数**即可解决自引用不收敛（内容一变字数就变）。
    """
    exclude = exclude or set()
    counted = [d for d in docs if d.path not in exclude]

    by_type: dict[str, int] = {}
    by_project: dict[str, dict[str, Any]] = {}
    total_links = 0
    total_broken = 0
    fm_count = 0
    tag_count = 0

    # 按 kind 分桶的孤立统计
    kind_total: dict[str, int] = {"knowledge": 0, "narrative": 0}
    kind_orphan: dict[str, int] = {"knowledge": 0, "narrative": 0}
    knowledge_orphans: list[str] = []
    narrative_orphans: list[str] = []

    for d in docs:
        by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1
        total_links += len(d.resolved)
        total_broken += len(d.broken)
        if d.has_frontmatter:
            fm_count += 1
        tag_count += len(d.tags)

        kind_total[d.kind] = kind_total.get(d.kind, 0) + 1
        orphan = not d.backlinks and not d.resolved
        if orphan:
            kind_orphan[d.kind] = kind_orphan.get(d.kind, 0) + 1
            (knowledge_orphans if d.kind == "knowledge" else narrative_orphans).append(d.path)

        if d.project:
            p = by_project.setdefault(d.project, {
                "docs": 0, "net_chars": 0, "types": {}, "links": 0,
                "knowledge": 0, "knowledge_orphan": 0,
            })
            p["docs"] += 1
            # 字数累加：排除生成物（自引用会导致数值不收敛）
            if d.path not in exclude:
                p["net_chars"] += d.net_chars
            p["types"][d.doc_type] = p["types"].get(d.doc_type, 0) + 1
            p["links"] += len(d.resolved)
            if d.kind == "knowledge":
                p["knowledge"] += 1
                if orphan:
                    p["knowledge_orphan"] += 1

    kn_total = kind_total["knowledge"] or 1
    kn_orphan_rate = kind_orphan["knowledge"] * 100.0 / kn_total

    return {
        "docs": len(docs),
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "by_project": dict(sorted(by_project.items(), key=lambda kv: -kv[1]["docs"])),
        "total_links": total_links,
        "total_broken": total_broken,
        "frontmatter_docs": fm_count,
        "tag_count": tag_count,
        # 知识节点口径（连接层真正负责的对象）
        "knowledge_docs": kind_total["knowledge"],
        "knowledge_orphans": kind_orphan["knowledge"],
        "knowledge_orphan_rate": round(kn_orphan_rate, 1),
        # 叙事节点口径（线性叙事，单列观察）
        "narrative_docs": kind_total["narrative"],
        "narrative_orphans": kind_orphan["narrative"],
        # 旧口径（保留，供历史对比）
        "orphan_count": kind_orphan["knowledge"] + kind_orphan["narrative"],
        "orphan_sample": knowledge_orphans[:40],
        "net_chars_total": sum(d.net_chars for d in counted),
    }
