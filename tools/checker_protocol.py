#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
checker_protocol.py —— 检查器 JSON 协议（Python 侧）
================================================================================
仓根 cordis 编排层（`tools/`）调用各 Python 检查器的**统一契约**。

设计原则
--------
1. **Python 内核保持零三方依赖**：本仓 49 个 .py 全部只用标准库，
   换机即跑（《工作区规范》§一「文件多为文本素材，无构建链路」的延伸原则）。
   协议只用 `json` + `sys`，不引入任何依赖。
2. **编排归 cordis**：插件负责「何时跑、跑哪些、怎么汇总」，
   Python 只负责「跑一个检查器、吐结构化结果」。
3. **退出码分级**：0=通过 / 1=有 ERROR / 2=执行异常（协议层故障）。
   cordis 侧据此决定是否阻断流水线。

协议（stdout 是一个 JSON 对象）
------------------------------
{
  "checker":  "doc-review",          # 检查器 id
  "ok":       true,                  # 是否通过（无 ERROR）
  "severity": "error",               # 本次最严重档：error/warn/info/none
  "summary":  "一句话结论",           # 给人看
  "counts":   {"error": 3, "warn": 10, "info": 5},
  "findings": [                      # 逐条发现
    {"severity":"error","category":"时间矛盾","code":"TIME-REG",
     "file":"...","line":20,"snippet":"...","message":"...","suggestion":"..."}
  ],
  "artifacts": [                     # 产出物路径（报告文件等）
    {"kind":"report","path":"...","bytes":1234}
  ],
  "meta":      {...}                 # 检查器自定义附加信息
}

**stdout 只放这一个 JSON 对象**；日志/诊断一律写 stderr。
（与 cordis-py 的 Logger 纪律同源：stdout 是数据通道，混进日志会破坏管道消费。）

作者：WorkBuddy ｜ 2026-11-13
"""
from __future__ import annotations

import json
import sys
import traceback
from typing import Any

SEV_ORDER = {"none": 0, "info": 1, "warn": 2, "error": 3}
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


def worst(findings: list[dict]) -> str:
    """取全部发现里最严重的一档。"""
    worst_sev = "none"
    for f in findings:
        s = f.get("severity", "info")
        if SEV_ORDER.get(s, 1) > SEV_ORDER.get(worst_sev, 0):
            worst_sev = s
    return worst_sev


def emit(checker: str, findings: list[dict], summary: str = "",
         artifacts: list[dict] | None = None, meta: dict | None = None) -> int:
    """按协议输出结果并返回退出码。"""
    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
    payload = {
        "checker": checker,
        "ok": counts["error"] == 0,
        "severity": worst(findings),
        "summary": summary or f"{counts['error']} error / {counts['warn']} warn / {counts['info']} info",
        "counts": counts,
        "findings": findings,
        "artifacts": artifacts or [],
        "meta": meta or {},
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=1))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return EXIT_FINDINGS if counts["error"] else EXIT_OK


def fail(checker: str, exc: BaseException, tb: str | None = None) -> int:
    """协议层故障：stderr 留栈，stdout 吐一个空结果，退出码 2。"""
    sys.stderr.write(f"[{checker}] 执行异常：{type(exc).__name__}: {exc}\n")
    if tb:
        sys.stderr.write(tb)
    payload = {
        "checker": checker, "ok": False, "severity": "error",
        "summary": f"执行异常：{type(exc).__name__}: {exc}",
        "counts": {"error": 1, "warn": 0, "info": 0},
        "findings": [{
            "severity": "error", "category": "执行", "code": "CHECKER-CRASH",
            "file": "-", "line": 0, "snippet": "",
            "message": f"{type(exc).__name__}: {exc}",
            "suggestion": "检查器自身缺陷，请报 issue",
        }],
        "artifacts": [], "meta": {"crashed": True},
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=1))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return EXIT_ERROR


def run(checker: str, fn, *args, **kwargs) -> int:
    """包裹一次检查器执行：异常一律转成协议输出，不让 traceback 泄漏到 stdout。"""
    try:
        result = fn(*args, **kwargs)
    except BaseException as exc:                          # noqa: BLE001
        return fail(checker, exc, traceback.format_exc())
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        # fn 自行 emit 过
        return EXIT_OK
    return emit(checker, result or [])
