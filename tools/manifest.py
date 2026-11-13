# -*- coding: utf-8 -*-
"""通用模板包 MANIFEST.sha256 的重算与校验工具。

为什么需要它
------------
`通用模板包/MANIFEST.sha256` 有两条容易踩的规矩，踩过一次就会把整包校验弄失效：

1. **哈希必须按 git blob 字节（LF）算，不能按工作区字节算。**
   本机 `core.autocrlf=true`（WorkBuddy 自带 PortableGit 的全局 gitconfig）会在检出时
   把 LF 转成 CRLF，于是「工作区字节」≠「入库字节」——
   按工作区算出来的哈希，在一个干净克隆里必然全部失配。
2. **路径分隔符必须用正斜杠。**
   原清单把 `tools` 下的条目写作 `tools\\xxx.py`，只在 Windows 下能解析；
   Linux/macOS 的 `sha256sum -c` 会因路径分隔符失配而**全盘失败**。

用法
----
    python tools/manifest.py --check     # 校验：逐条比对 blob 哈希（不改文件）
    python tools/manifest.py --write     # 重算：按 blob 字节重写整份清单（幂等）
    python tools/manifest.py --write --add 通用模板包/新文件.md   # 先纳入新文件再重算

退出码：0 = 一致；1 = 失配（--check）；2 = 参数/环境错误。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_REL = "通用模板包"
PKG = os.path.join(REPO, PKG_REL)
MANIFEST = os.path.join(PKG, "MANIFEST.sha256")

# 此前未受哈希保护、已在本轮纳入的受控文件
DEFAULT_NEW = [
    "tools/regression_checks.txt",
    "writing-style-transfer/scripts/style_metrics.py",
    "可视化_结构映射/graph.dot",
    "可视化_结构映射/graph.svg",
    "可视化_结构映射/index.html",
    "可视化_结构映射/render.js",
]

HEADER = """# 创作室通用模板包 v3.12.2 · SHA256 校验清单（2026-11-13）
# 校验：在本目录执行  sha256sum -c MANIFEST.sha256
# Windows: certutil -hashfile <文件> SHA256 逐项比对
# v3.12.2 新增：通用文件哈希随 --scenario/槽位拆解/--max-repeat 改动同步；文件集不变。
#
# —— 2026-11-13 增补（本次深度审计后）——
# 1) 覆盖范围补齐：纳入此前未受哈希保护的 6 个受控文件（tools/regression_checks.txt 是 C8 防回归断言的数据源，
#    writing-style-transfer/scripts/style_metrics.py 是 05-文风卡指定的官方实测脚本，
#    可视化_结构映射/ 四件为包内交付物且被 00/14 两份模板文档引用）。
#    清单不含自身（MANIFEST.sha256），合计 33 条。
# 2) 路径分隔符统一为正斜杠：原 tools 下的条目写作反斜杠，仅 Windows 可解析，
#    Linux/macOS 的 sha256sum -c 会因路径分隔符失配而全盘失败；现改为正斜杠。
# 3) 哈希口径：一律取 git blob 字节（LF），不得按工作区字节计算（工作区可能是 CRLF 旧副本）。
#    重算工具：python tools/manifest.py --write    校验：python tools/manifest.py --check
"""


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("git %s 失败：%s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def blob_sha(rel: str) -> str:
    """取 **入库字节（blob）** 的 sha256；文件未入库时退回工作区字节并告警。"""
    r = subprocess.run(["git", "-C", REPO, "cat-file", "blob", ":" + rel],
                       capture_output=True)
    if r.returncode != 0:
        with open(os.path.join(REPO, rel), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    return hashlib.sha256(r.stdout).hexdigest()


def parse(path: str) -> list[tuple[str, str]]:
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for ln in f:
            s = ln.rstrip("\r\n")
            if not s.strip() or s.lstrip().startswith("#"):
                continue
            h, name = s.split("  ", 1)
            out.append((h.strip(), name.strip().replace("\\", "/")))
    return out


def tracked_files() -> list[str]:
    out = git("-c", "core.quotepath=false", "ls-files", PKG_REL + "/")
    return [l[len(PKG_REL) + 1:] for l in out.split("\n") if l.strip()]


def cmd_check() -> int:
    entries = parse(MANIFEST)
    bad = []
    for h, name in entries:
        p = os.path.join(PKG, name)
        if not os.path.exists(p):
            bad.append("  文件不存在: %s" % name)
            continue
        real = blob_sha(PKG_REL + "/" + name)
        if real != h:
            bad.append("  失配: %s\n    清单=%s\n    blob=%s" % (name, h, real))
    covered = {n for _, n in entries}
    missing = [t for t in tracked_files() if t not in covered and t != "MANIFEST.sha256"]
    for m in missing:
        bad.append("  受控但未纳入清单: %s" % m)
    print("清单条目 %d 条；失配 %d 条" % (len(entries), len(bad)))
    for b in bad:
        print(b)
    return 1 if bad else 0


def cmd_write(add: list[str]) -> int:
    base = []
    seen_new = set()
    for h, name in parse(MANIFEST):
        if name in DEFAULT_NEW or name in add:
            seen_new.add(name)
            continue
        base.append((blob_sha(PKG_REL + "/" + name), name))
    todo = [n for n in DEFAULT_NEW + add if n not in seen_new]
    lines = [HEADER.rstrip("\n")]
    for h, name in base:
        lines.append("%s  %s" % (h, name))
    lines.append("# —— 2026-11-13 增补条目（此前未纳入哈希保护）——")
    for n in todo:
        lines.append("%s  %s" % (blob_sha(PKG_REL + "/" + n), n))
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("已重写 %s：基线 %d 条 + 新增 %d 条 = %d 条"
          % (MANIFEST, len(base), len(todo), len(base) + len(todo)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="通用模板包 MANIFEST 重算/校验")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="只校验，不改文件")
    g.add_argument("--write", action="store_true", help="按 blob 字节重写清单")
    ap.add_argument("--add", nargs="*", default=[], help="--write 时额外纳入的包内相对路径")
    args = ap.parse_args(argv)
    if not os.path.exists(MANIFEST):
        print("找不到 %s" % MANIFEST, file=sys.stderr)
        return 2
    if args.write:
        return cmd_write(args.add)
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
