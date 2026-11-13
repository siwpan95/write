#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_check.py —— 模板包自检适配器（→ 检查器协议）
================================================================================
`通用模板包/tools/check_package.py` 打印的是**人读报告**，不是协议 JSON。
本适配器把它包成仓根 cordis 编排层认识的协议格式，使「模板包有问题」
也能进同一份汇总报告。

做法：**不改原脚本**（它是包级资产，有自己的 sha256 与 MANIFEST 保护），
而是**捕获其 stdout/stderr**并解析计数行，转成协议 findings。

用法：
  python tools/checkers/package_check.py
  → stdout 一个 JSON 对象（见 tools/checker_protocol.py）
"""
from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from checker_protocol import emit, fail  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def find_script() -> Path | None:
    for cand in (REPO_ROOT / "通用模板包" / "tools" / "check_package.py",
                 REPO_ROOT / "tools" / "check_package.py"):
        if cand.exists():
            return cand
    return None


def main() -> int:
    script = find_script()
    if script is None:
        return emit("package", [{
            "severity": "error", "category": "执行", "code": "CHECKER-MISSING",
            "file": "通用模板包/tools/check_package.py", "line": 0, "snippet": "",
            "message": "找不到 check_package.py",
            "suggestion": "确认模板包目录存在",
        }], summary="模板包自检脚本不存在")

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(script.parent.parent)],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(script.parent.parent))
    except Exception as e:
        return fail("package", e)

    out = proc.stdout or ""
    err = proc.stderr or ""
    combined = out + "\n" + err

    m_err = re.search(r"ERROR\s+(\d+)", combined)
    m_warn = re.search(r"WARN\s+(\d+)", combined)
    err_count = int(m_err.group(1)) if m_err else 0
    warn_count = int(m_warn.group(1)) if m_warn else 0

    findings = []
    # 把原报告里的逐条 × 行也抽出来，带上定位
    for line in combined.split("\n"):
        s = line.strip()
        if s.startswith("× "):
            findings.append({
                "severity": "error", "category": "结构", "code": "PACKAGE-ERROR",
                "file": "通用模板包", "line": 0, "snippet": s[2:][:160],
                "message": s[2:],
                "suggestion": "按 check_package.py 的 C1–C8 口径修复",
            })
        elif s.startswith("· "):
            findings.append({
                "severity": "warn", "category": "结构", "code": "PACKAGE-WARN",
                "file": "通用模板包", "line": 0, "snippet": s[2:][:160],
                "message": s[2:],
                "suggestion": "逐条确认是否为已知豁免",
            })

    # 若逐条解析为空（报告格式变化），至少把计数报出来
    if not findings and (err_count or warn_count):
        findings.append({
            "severity": "error" if err_count else "warn",
            "category": "结构",
            "code": "PACKAGE-ERROR" if err_count else "PACKAGE-WARN",
            "file": "通用模板包", "line": 0, "snippet": combined[-200:],
            "message": f"模板包自检：ERROR {err_count} ／ WARN {warn_count}",
            "suggestion": "直接跑 check_package.py 看逐条明细",
        })

    artifacts = []
    report = script.parent.parent / "校验报告.txt"
    if report.exists():
        artifacts.append({"kind": "report", "path": str(report),
                          "bytes": report.stat().st_size})

    return emit("package", findings,
                summary=f"模板包自检：ERROR {err_count} ／ WARN {warn_count}",
                artifacts=artifacts,
                meta={"exitCode": proc.returncode, "raw": combined[-4000:]})


if __name__ == "__main__":
    sys.exit(main())
