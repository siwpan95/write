#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consistency_check.py —— 项目结构一致性扫描适配器（→ 检查器协议）
================================================================================
项目自带的 `点子库/04-工具/audit_consistency.py` 做章号 / 字数 / 标点 / 重复扫描，
但它：① 打印人读报告；② **路径写死在自身目录下**（只扫点子库）；
③ 不遵守协议。

本适配器：
  · **不改原脚本**（它是项目资产，纳入版本库）；
  · 以子进程方式跑它，捕获输出并转成协议 findings；
  · 支持 `--project-root` 指定要扫的项目根（默认点子库）。

用法：
  python tools/checkers/consistency_check.py --project-root 点子库
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker_protocol import emit, fail  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SCANNER = REPO_ROOT / "点子库" / "04-工具" / "audit_consistency.py"


def main() -> int:
    ap = argparse.ArgumentParser(description="项目结构一致性扫描适配器")
    ap.add_argument("--project-root", default="点子库",
                    help="项目根（相对仓根）；扫描器按此目录的 02-正文 扫描")
    ap.add_argument("--scanner", default=str(DEFAULT_SCANNER),
                    help="扫描器脚本路径")
    args = ap.parse_args()

    scanner = Path(args.scanner)
    if not scanner.is_absolute():
        scanner = REPO_ROOT / scanner
    if not scanner.exists():
        return emit("consistency", [{
            "severity": "error", "category": "执行", "code": "CHECKER-MISSING",
            "file": str(scanner), "line": 0, "snippet": "",
            "message": "找不到一致性扫描脚本",
            "suggestion": "检查 --scanner 参数",
        }], summary="一致性扫描脚本不存在")

    proj_root = (REPO_ROOT / args.project_root).resolve()
    if not proj_root.exists():
        return emit("consistency", [{
            "severity": "error", "category": "执行", "code": "NO-PROJECT",
            "file": str(proj_root), "line": 0, "snippet": "",
            "message": f"项目根不存在：{args.project_root}",
            "suggestion": "检查 --project-root 参数",
        }], summary="项目根不存在")

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        # 扫描器按「自身所在目录」定位 02-正文，故 cwd 设为脚本的上级（04-工具 的父）
        proc = subprocess.run(
            [sys.executable, str(scanner)],
            capture_output=True, text=True, encoding="utf-8", env=env,
            cwd=str(scanner.parent.parent))
    except Exception as e:
        return fail("consistency", e)

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    findings = []
    for line in combined.split("\n"):
        s = line.strip()
        if not s.startswith("!"):
            continue
        # 形如：! 01-第一章-第十三条 缺章末标记: ---
        body = s[1:].strip()
        m = re.match(r"^(\S+)\s+(.*)$", body)
        if not m:
            continue
        name, msg = m.group(1), m.group(2)
        findings.append({
            "severity": "warn", "category": "结构", "code": "CONSISTENCY",
            "file": name, "line": 0, "snippet": msg[:160],
            "message": msg,
            "suggestion": "核对章号/章名/尾标是否与本项目体例一致",
        })

    m_anom = re.search(r"结构异常\s+(\d+)", combined)
    m_chars = re.search(r"净字数\s+(\d+)", combined)
    return emit("consistency", findings,
                summary=f"{args.project_root}：结构异常 {m_anom.group(1) if m_anom else len(findings)} 条"
                        f" ／ 净字数 {m_chars.group(1) if m_chars else '?'}",
                meta={"projectRoot": args.project_root,
                      "exitCode": proc.returncode,
                      "raw": combined[-3000:]})


if __name__ == "__main__":
    sys.exit(main())
