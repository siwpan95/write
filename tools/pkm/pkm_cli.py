#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pkm_cli.py —— PKM 索引器 · 统一命令行入口
================================================================================
子命令
------
  build     扫描全仓 → 重建索引缓存 + 图谱 + MOC
  search    全文检索（中文二元组切分，零三方依赖）
  links     查某文档的出链 / 入链
  graph     输出图谱统计（JSON）
  doctor    环境自检

退出码：0 正常 ／ 1 有问题 ／ 2 协议或参数故障
（与全仓检查器协议一致，便于进 CI 与闸门。）

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from graph import (  # noqa: E402
    build_graph, is_generated, load_project_links, render_broken, render_moc,
    render_orphans, render_project_moc, write_graph, write_text,
)
from indexer import build_index, search, write_index  # noqa: E402


def _root(args: list[str]) -> str:
    """仓根：优先 --root，其次第一个位置参数，最后取脚本上级目录。"""
    if "--root" in args:
        i = args.index("--root")
        if i + 1 < len(args):
            return os.path.abspath(args[i + 1])
    for a in args:
        if not a.startswith("-") and os.path.isdir(a):
            return os.path.abspath(a)
    return os.path.abspath(os.path.join(HERE, "..", ".."))


def _out(root: str, name: str) -> str:
    return os.path.join(root, "PKM", name)


def cmd_build(args: list[str]) -> int:
    """
    重建全部产物。

    **两阶段（自举收敛）**
    ------------------
    项目级 MOC 是**自己也要被索引**的知识节点 —— 第一轮扫描时它还不存在，
    所以第一轮生成的 MOC 不会被计入图谱。必须再跑一轮才能收敛：

        第一轮：扫描 → 生成 MOC（MOC 尚不存在）
        第二轮：重扫（含 MOC）→ 重生成 MOC → 图谱/清单收敛

    故此处**固定跑两轮**并以第二轮结果为准 —— 保证「同一输入同一结果」，
    避免出现「跑一次和跑两次结果不同」的非确定性。
    """
    root = _root(args)
    print(f"[pkm] 仓根：{root}", file=sys.stderr)

    # ---------- 第一轮：生成项目 MOC（骨架） ----------
    g1 = build_graph(root)
    moc_count = _write_project_mocs(root, g1)
    print(f"[pkm] 项目 MOC（第一轮）：{moc_count} 份", file=sys.stderr)

    # ---------- 第二轮：重扫（含 MOC）→ 重生成 → 收敛 ----------
    g = build_graph(root)
    moc_count = _write_project_mocs(root, g)
    print(f"[pkm] 项目 MOC（第二轮，收敛）：{moc_count} 份", file=sys.stderr)

    gp, gsize = write_graph(g, _out(root, "graph.json"))
    print(f"[pkm] 图谱（入库）：{gp}（{gsize} 字节）", file=sys.stderr)

    mp, msize = write_text(render_moc(g), _out(root, "MOC-全库.md"))
    print(f"[pkm] MOC：{mp}（{msize} 字节）", file=sys.stderr)

    op, osize = write_text(render_orphans(g), _out(root, "孤立文档清单.md"))
    print(f"[pkm] 孤立清单：{op}（{osize} 字节）", file=sys.stderr)

    bp, bsize = write_text(render_broken(g), _out(root, "断链清单.md"))
    print(f"[pkm] 断链清单：{bp}（{bsize} 字节）", file=sys.stderr)

    # 索引放最后：此时 MOC 已就位，索引内容与图谱一致
    idx = build_index(root)
    ip, isize = write_index(idx, _out(root, "index.json"))
    print(f"[pkm] 索引缓存：{ip}（{isize} 字节）", file=sys.stderr)

    s = g["summary"]
    print(json.dumps({
        "ok": True,
        "docs": s["docs"],
        "links": s["total_links"],
        "broken": s["total_broken"],
        "knowledge_docs": s["knowledge_docs"],
        "knowledge_orphans": s["knowledge_orphans"],
        "knowledge_orphan_rate": s["knowledge_orphan_rate"],
        "narrative_orphans": s["narrative_orphans"],
        "frontmatter": s["frontmatter_docs"],
    }, ensure_ascii=False))
    return 0


def _write_project_mocs(root: str, graph: dict) -> int:
    """为每个项目生成一份 MOC（LYT 枢纽节点），返回生成份数。"""
    moc_dir = os.path.join(root, "PKM", "01-MOC")
    os.makedirs(moc_dir, exist_ok=True)

    by_project: dict[str, list] = {}
    for n in graph["nodes"]:
        if n["project"] and n["project"] != "PKM":
            by_project.setdefault(n["project"], []).append(n)
        elif n["project"] == "PKM":
            # PKM 自身也要一份 MOC —— 否则它自己的产物（元数据清单、
            # 孤立清单、断链清单）会成为孤立节点。
            by_project.setdefault("PKM-知识连接层", []).append(n)

    # 项目级统计（MOC 头部用）—— **排除生成物**：
    # MOC 自身的字数会随内容变化，若计入则数值永不收敛（实测差 11 字）。
    proj_stats = {
        p: {"net_chars": sum(x.get("net_chars", 0) for x in v
                             if not is_generated(x["path"]))}
        for p, v in by_project.items()
    }

    count = 0
    proj_links = load_project_links(root)
    for proj, nodes in sorted(by_project.items()):
        text = render_project_moc(proj, nodes, proj_stats[proj], root=root,
                                  links=proj_links.get(proj, []))
        write_text(text, os.path.join(moc_dir, f"MOC-{proj}.md"))
        count += 1
    return count


def _positional(args: list[str], skip_values: set[str]) -> list[str]:
    """
    取出位置参数（排除选项及其取值）。

    `--limit 3` 里的 "3" 是 **--limit 的取值**，不是查询词 ——
    必须成对跳过，否则查询会变成 "战锤四神 3"，污染检索。
    """
    out: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in skip_values:
            i += 2          # 跳过选项与其取值
            continue
        if a.startswith("-"):
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def cmd_search(args: list[str]) -> int:
    """全文检索。"""
    root = _root(args)
    # 选项取值一律成对跳过
    query = " ".join(_positional(args, {"--query", "--project", "--type", "--limit", "--root"}))
    if not query and "--query" in args:
        query = args[args.index("--query") + 1]
    if not query:
        print("用法：pkm_cli.py search <关键词> [--root 路径]", file=sys.stderr)
        return 2

    idx_path = _out(root, "index.json")
    if not os.path.exists(idx_path):
        print(f"[pkm] 索引不存在，先跑 build：{idx_path}", file=sys.stderr)
        return 2
    with open(idx_path, encoding="utf-8-sig") as f:
        idx = json.load(f)

    project = ""
    if "--project" in args:
        project = args[args.index("--project") + 1]
    doc_type = ""
    if "--type" in args:
        doc_type = args[args.index("--type") + 1]
    limit = 20
    if "--limit" in args:
        try:
            limit = int(args[args.index("--limit") + 1])
        except ValueError:
            pass

    res = search(idx, query, limit=limit, project=project, doc_type=doc_type)
    # 结构化输出（JSON Lines）——供 Cordis 侧稳定解析，
    # 不靠正则去猜人读格式的列宽
    for r in res:
        print(json.dumps(r, ensure_ascii=False))
    print(f"命中 {len(res)} 条（查询：{query}）", file=sys.stderr)
    return 0 if res else 1


def cmd_links(args: list[str]) -> int:
    """查某文档的出链 / 入链。"""
    root = _root(args)
    target = ""
    pos = _positional(args, {"--root"})
    if pos:
        target = pos[0]
    if not target:
        print("用法：pkm_cli.py links <文档路径>", file=sys.stderr)
        return 2

    gpath = _out(root, "graph.json")
    if not os.path.exists(gpath):
        print(f"[pkm] 图谱不存在，先跑 build：{gpath}", file=sys.stderr)
        return 2
    with open(gpath, encoding="utf-8-sig") as f:
        g = json.load(f)

    # 支持传 basename 匹配
    node = None
    for n in g["nodes"]:
        if n["path"] == target or n["path"].endswith(target):
            node = n
            break
    if node is None:
        print(f"[pkm] 找不到文档：{target}", file=sys.stderr)
        return 1

    print(f"# {node['title']}")
    print(f"路径：{node['path']}")
    print(f"类型：{node['type']} ／ 项目：{node['project']} ／ 角色：{node['role']}")
    print(f"净字数：{node['net_chars']}")
    print(f"\n出链（{len(node['out'])}）：")
    for o in node["out"]:
        print(f"  → {o}")
    print(f"\n入链（{len(node['in'])}）：")
    for i in node["in"]:
        print(f"  ← {i}")
    if node["broken"]:
        print(f"\n断链（{len(node['broken'])}）：")
        for b in node["broken"]:
            print(f"  ✗ {b}")
    return 0


def cmd_graph(args: list[str]) -> int:
    """输出图谱统计。"""
    root = _root(args)
    gpath = _out(root, "graph.json")
    if not os.path.exists(gpath):
        print(f"[pkm] 图谱不存在，先跑 build：{gpath}", file=sys.stderr)
        return 2
    with open(gpath, encoding="utf-8-sig") as f:
        g = json.load(f)
    print(json.dumps(g["summary"], ensure_ascii=False, indent=1))
    return 0


def cmd_doctor(args: list[str]) -> int:
    """环境自检。"""
    root = _root(args)
    bad = 0
    print(f"仓根：{root}")
    print(f"Python：{sys.executable}")
    if not os.path.isdir(root):
        print("  ✗ 仓根不存在")
        bad += 1
    for name in ("index.json", "graph.json", "MOC-全库.md"):
        p = _out(root, name)
        exists = os.path.exists(p)
        size = os.path.getsize(p) if exists else 0
        print(f"  {'✓' if exists else '✗'} {name}（{size} 字节）")
        if not exists:
            bad += 1
    print(f"环境自检：{'全部正常' if not bad else f'{bad} 项异常'}")
    return 1 if bad else 0


COMMANDS = {
    "build": cmd_build,
    "search": cmd_search,
    "links": cmd_links,
    "graph": cmd_graph,
    "doctor": cmd_doctor,
}


def main(argv: list[str]) -> int:
    if not argv:
        print("用法：pkm_cli.py <build|search|links|graph|doctor> [参数]", file=sys.stderr)
        return 2
    cmd = argv[0]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"未知命令：{cmd}（可用：{' / '.join(COMMANDS)}）", file=sys.stderr)
        return 2
    try:
        return fn(argv[1:])
    except Exception as exc:  # noqa: BLE001
        print(f"[pkm] 执行异常：{type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
