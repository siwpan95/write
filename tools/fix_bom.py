#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_bom.py —— 编码归一（UTF-8-SIG + LF）
================================================================================
《工作区规范》§六：文本文件统一 **UTF-8-SIG（带 BOM）**，兼容 Windows 编辑器；
行尾归一为 `\n`。

**只处理本仓新建的 PKM 层与 tools/pkm/、tools/bootstrap.* 文件** ——
不动任何既有正文/设定（那些是历史形成的既有字节形态，按 §六「不批量规范化」处理）。

用法：
  python tools/fix_bom.py            # 归一
  python tools/fix_bom.py --check    # 只体检不修改

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, ".."))

# 归一范围：本次新增的 PKM 层与工具文件
TARGET_DIRS = ["PKM", "tools/pkm"]
TARGET_FILES = ["tools/bootstrap.sh", "tools/bootstrap.ps1",
                "tools/plugins/13-pkm.mjs", "tools/plugins/14-checker-pkm.mjs",
                "tools/checkers/pkm_check.py"]

# 二进制扩展名（不处理）
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".xlsx", ".zip",
          ".svg", ".dxf", ".mp4", ".mp3"}

# **脚本类文件不加 BOM** —— 两种生态各自的惯例：
#   · bash：shebang 行首有 BOM 会导致内核无法识别解释器（`#!` 必须是真首字节）；
#   · Node ESM / PowerShell：BOM 可能引入解析差异。
# 内容类文件（.md / .py）保持 UTF-8-SIG —— 兼容 Windows 编辑器（《工作区规范》§六）。
NO_BOM_EXT = {".sh", ".ps1", ".mjs", ".js", ".yml", ".yaml", ".json"}


def targets() -> list[str]:
    out: list[str] = []
    for d in TARGET_DIRS:
        base = os.path.join(REPO_ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in ("__pycache__", "node_modules")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext in BINARY:
                    continue
                # index.json 是**派生缓存**（不入库），编码无意义 —— 跳过
                if fn == "index.json" and os.path.basename(dirpath) == "PKM":
                    continue
                out.append(os.path.join(dirpath, fn))
    for f in TARGET_FILES:
        p = os.path.join(REPO_ROOT, f)
        if os.path.exists(p):
            out.append(p)
    return sorted(out)


def main(check_only: bool) -> int:
    changed, skipped, bad = [], [], []
    for p in targets():
        try:
            raw = open(p, "rb").read()
        except OSError as e:
            bad.append(f"{p}: 读取失败 {e}")
            continue

        has_bom = raw.startswith(b"\xef\xbb\xbf")
        body = raw[3:] if has_bom else raw
        # 行尾归一：CRLF → LF
        norm = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        ext = os.path.splitext(p)[1].lower()
        want_bom = ext not in NO_BOM_EXT
        need_bom = (not has_bom) if want_bom else has_bom
        need_lf = norm != body

        if not (need_bom or need_lf):
            skipped.append(p)
            continue

        if check_only:
            bad.append(f"{os.path.relpath(p, REPO_ROOT)}: "
                       f"{'缺 BOM' if need_bom and want_bom else ''}"
                       f"{'多 BOM' if not want_bom and has_bom else ''}"
                       f"{'有 CRLF' if need_lf else ''}".strip("："))
            continue

        with open(p, "wb") as f:
            if want_bom:
                f.write(b"\xef\xbb\xbf")
            f.write(norm)
        changed.append(os.path.relpath(p, REPO_ROOT))

    if check_only:
        if bad:
            print(f"编码体检：{len(bad)} 个文件不合规")
            for b in bad:
                print("  ✗", b)
            return 1
        print(f"编码体检：{len(skipped)} 个文件全部合规（UTF-8-SIG + LF）")
        return 0

    print(f"编码归一：已修正 {len(changed)} 个文件，未动 {len(skipped)} 个")
    for c in changed:
        print("  ✓", c)
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
