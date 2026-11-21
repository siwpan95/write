#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dse_check.py —— 叙事内容包校验（dse-core 三道门 → 检查器协议）
================================================================================
把 dse-core 的三道机械门接进 write 仓的 Cordis 闸门：

    dse check      静态：JSON Schema / 悬空跳转 / 图连通性   → ERROR
    dse traverse   动态：真跑引擎，求值条件与效果           → WARN（截断）
    dse coverage   结局覆盖：每个结局须有 traverse(T)/e2e(E) 来源 → ERROR

为什么是「子进程调用 dse CLI」而不是 import dse_core
-----------------------------------------------------
`tools/` 下的**核心内核**（doc_review / pkm / metrics / rules / prose-style）
只用标准库，保证「任何 Python 上都能跑，换机即跑」。
本检查器是**增强层**：它需要 dse-core（PyYAML + jsonschema），
但通过**子进程调用 CLI** 使用 —— 检查器进程本身不 import dse_core，
故核心内核的零依赖纪律**不受影响**，同时闸门拿到了 dse 的校验能力。

用哪个 dse？——**当前解释器自己的那个**
-----------------------------------------
⚠️ 本机实测踩过的坑：PATH 上的 `dse.exe` 可能指向**另一套 Python**
（实测：E 盘 Python314 的 Scripts 目录下那个，而闸门跑在 WorkBuddy 托管的
3.13.12 上）。用错解释器的 dse = 用错版本的引擎 = 行为不可复现。
故此处按 `sys.executable` 推导同目录的 dse.exe / dse 脚本，**不依赖 PATH**。

依赖缺失怎么办？——**报 ERROR，不静默跳过**
---------------------------------------------
廓者未名夜的教训：项目未注册进审校 ⇒ `npm run check` 对它是「SKIP」
而非「通过」—— 日更自动化把「错误 0」当放行线，若检查对象不在扫描
视角内，那条线**根本不成立**。依赖缺失同理：静默跳过 = 闸门失效而
无人知晓。故此处报 ERROR 并给出安装指引。

**只读**：本检查器只跑 dse 的校验命令，不改任何内容包与正文。

作者：WorkBuddy ｜ 2026-11-21
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.normpath(os.path.join(HERE, ".."))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from checker_protocol import emit, run  # noqa: E402

# 内容包工程目录（相对仓根）
DEFAULT_PROJECT = "./dse-content"


# ==============================================================================
# dse 可执行文件定位
# ==============================================================================

def find_dse() -> tuple[str | None, str]:
    """定位**当前解释器**对应的 dse CLI。返回 (路径, 说明)。

    查找顺序：
      1. sys.executable 同级 Scripts 目录下的 dse.exe / dse（Windows）
      2. sys.executable 同目录下的 dse（POSIX 的 bin/）
      3. 退而求其次：PATH 上的 dse（**会告警** —— 可能是另一套 Python）

    绝不使用 `dse_core.__main__` —— 该包没有 __main__，不能 -m 调用。
    """
    import sysconfig

    exe = os.path.basename(sys.executable).lower()
    scripts_dir = sysconfig.get_path("scripts")
    bin_dir = os.path.dirname(sys.executable)

    candidates = []
    if sys.platform == "win32":
        candidates.append(os.path.join(scripts_dir, "dse.exe"))
        candidates.append(os.path.join(bin_dir, "dse.exe"))
    else:
        candidates.append(os.path.join(scripts_dir, "dse"))
        candidates.append(os.path.join(bin_dir, "dse"))

    for c in candidates:
        if os.path.exists(c):
            return c, f"当前解释器（{exe}）同源"

    # PATH 兜底（附告警）
    from shutil import which
    w = which("dse")
    if w:
        return w, "PATH 上的 dse —— **可能与当前解释器不同源**，结果不可复现"

    return None, "未找到 dse CLI"


# ==============================================================================
# 跑 dse 子命令
# ==============================================================================

def run_dse(dse_path: str, args: list[str], cwd: str, timeout: int = 120) -> tuple[int, str, str]:
    """跑一条 dse 命令，返回 (退出码, stdout, stderr)。**永不抛异常。"""
    try:
        p = subprocess.run(
            [dse_path, *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"超时（{timeout}s）"
    except (OSError, subprocess.SubprocessError) as e:
        return 2, "", f"{type(e).__name__}: {e}"


def extract_problems(text: str) -> list[tuple[str, str]]:
    """从 dse 输出里抽出 (位置, 问题描述)。

    dse 的输出形如：
        [check] 发现 1 个问题:
          - #archive 第 1 个选项 -> "nowhere_at_all"
        [dse] 存在未定义的场景跳转:
          - #archive 第 1 个选项 -> "nowhere_at_all"
    """
    problems: list[tuple[str, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("-"):
            continue
        body = s.lstrip("- ").strip()
        if not body:
            continue
        # 拆成「位置」与「描述」：位置以 # 开头，或以「路径: 」形式
        if body.startswith("#"):
            loc, _, desc = body.partition(" ")
            problems.append((loc, desc.strip()))
        else:
            problems.append(("-", body))
    return problems


# ==============================================================================
# 三道门
# ==============================================================================

def gate_check(dse_path: str, project: str, root: str) -> list[dict]:
    """dse check —— 静态门。失败 → ERROR。"""
    findings: list[dict] = []
    code, out, err = run_dse(dse_path, ["check"], cwd=os.path.join(root, project))
    combined = "\n".join(x for x in (out, err) if x)

    if code == 0:
        summary = "通过"
        for line in out.splitlines():
            if "通过" in line:
                summary = line.strip()
        findings.append({
            "severity": "info", "category": "内容包", "code": "DSE-CHECK-OK",
            "file": project, "line": 0, "snippet": "",
            "message": f"dse check 通过：{summary}",
            "suggestion": "—",
        })
        return findings

    if code == 2:
        findings.append({
            "severity": "error", "category": "内容包", "code": "DSE-CHECK-CRASH",
            "file": project, "line": 0, "snippet": err[:300],
            "message": f"dse check 执行异常（退出码 2）：{err[:200] or '未知原因'}",
            "suggestion": "检查 dse-content/dse.yml 的内容包挂载路径",
        })
        return findings

    problems = extract_problems(combined)
    if not problems:
        problems = [("-", combined[:300] or "dse check 失败但无明细输出")]
    for loc, desc in problems:
        findings.append({
            "severity": "error", "category": "内容包", "code": "DSE-CHECK-FAIL",
            "file": f"{project}:{loc}", "line": 0, "snippet": desc[:200],
            "message": f"dse check：{desc}",
            "suggestion": (
                "按 dse-content/docs/内容包规范.md 修："
                "① 条件写在选项级 if（不是 goto 数组项）；② 只用 schema 允许的字段；"
                "③ 场景 ID 须匹配 ASCII 正则；④ 修完跑 tools/procedural/md2dse.py 重新生成"
            ),
        })
    return findings


def gate_traverse(dse_path: str, project: str, root: str) -> list[dict]:
    """dse traverse —— 动态门。截断 → WARN（不是 ERROR：截断是安全收敛，不是结构错误）。"""
    findings: list[dict] = []
    code, out, err = run_dse(dse_path, ["traverse"], cwd=os.path.join(root, project))
    combined = "\n".join(x for x in (out, err) if x)

    if code == 0:
        summary = "通过"
        for line in out.splitlines():
            if "访问场景" in line:
                summary = line.strip()
        findings.append({
            "severity": "info", "category": "内容包", "code": "DSE-TRAVERSE-OK",
            "file": project, "line": 0, "snippet": "",
            "message": f"dse traverse 通过：{summary}",
            "suggestion": "—",
        })
    elif code == 2:
        findings.append({
            "severity": "error", "category": "内容包", "code": "DSE-TRAVERSE-CRASH",
            "file": project, "line": 0, "snippet": err[:300],
            "message": f"dse traverse 执行异常：{err[:200] or '未知原因'}",
            "suggestion": "检查 dse.yml 的 state.initial 是否预声明了全部用到的字段",
        })
    else:
        for loc, desc in extract_problems(combined) or [("-", combined[:300])]:
            findings.append({
                "severity": "error", "category": "内容包", "code": "DSE-TRAVERSE-FAIL",
                "file": f"{project}:{loc}", "line": 0, "snippet": desc[:200],
                "message": f"dse traverse：{desc}",
                "suggestion": "动态遍历失败 —— 悬空跳转或表达式求值出错；跑 `dse check` 交叉定位",
            })

    # 截断是「如实报告」而非失败 —— 但必须显性上报（WARN）
    for line in out.splitlines():
        if "截断" in line:
            findings.append({
                "severity": "warn", "category": "内容包", "code": "DSE-TRAVERSE-TRUNCATED",
                "file": project, "line": 0, "snippet": line.strip()[:200],
                "message": f"dse traverse 截断：{line.strip()}",
                "suggestion": (
                    "分支撞 max-revisit（缺省 3）/ max-steps（缺省 500）上限 —— "
                    "若非预期，检查是否有自循环分支；若是，可调 dse.yml 的 engine.config"
                ),
            })
    return findings


def gate_coverage(dse_path: str, project: str, root: str) -> list[dict]:
    """dse coverage —— 结局覆盖门。缺来源 → ERROR。"""
    findings: list[dict] = []
    code, out, err = run_dse(dse_path, ["coverage"], cwd=os.path.join(root, project))
    combined = "\n".join(x for x in (out, err) if x)

    if code == 0:
        summary = "通过"
        for line in out.splitlines():
            if "结局总数" in line:
                summary = line.strip()
        findings.append({
            "severity": "info", "category": "内容包", "code": "DSE-COVERAGE-OK",
            "file": project, "line": 0, "snippet": "",
            "message": f"dse coverage 通过：{summary}",
            "suggestion": "—",
        })
        return findings

    if code == 2:
        findings.append({
            "severity": "error", "category": "内容包", "code": "DSE-COVERAGE-CRASH",
            "file": project, "line": 0, "snippet": err[:300],
            "message": f"dse coverage 执行异常：{err[:200] or '未知原因'}",
            "suggestion": "检查内容包是否有未定义的场景跳转",
        })
        return findings

    # 逐个结局报
    reported = False
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("✗"):
            reported = True
            name = s.lstrip("✗").split("[")[0].strip()
            findings.append({
                "severity": "error", "category": "内容包", "code": "DSE-COVERAGE-GAP",
                "file": project, "line": 0, "snippet": s[:200],
                "message": f"结局「{name}」没有任何来源（traverse 走不到、也未声明 --e2e）",
                "suggestion": (
                    "二选一：① 给该结局补一条可达路径；"
                    "② 确认它是占位结局并用 `dse coverage --e2e <结局名>` 声明为已覆盖"
                ),
            })
    if not reported:
        for loc, desc in extract_problems(combined) or [("-", combined[:300])]:
            findings.append({
                "severity": "error", "category": "内容包", "code": "DSE-COVERAGE-FAIL",
                "file": f"{project}:{loc}", "line": 0, "snippet": desc[:200],
                "message": f"dse coverage：{desc}",
                "suggestion": "检查内容包是否有未定义的场景跳转",
            })
    return findings


# ==============================================================================
# 主流程
# ==============================================================================

def check(root: str, project: str = DEFAULT_PROJECT) -> list[dict]:
    findings: list[dict] = []

    proj_abs = os.path.normpath(os.path.join(root, project))
    if not os.path.isdir(proj_abs):
        return [{
            "severity": "error", "category": "内容包", "code": "DSE-NO-PROJECT",
            "file": project, "line": 0, "snippet": "",
            "message": f"内容包工程目录不存在：{project}",
            "suggestion": "确认 cordis.yml 的 dse-checker.project 配置",
        }]

    dse_path, origin = find_dse()
    if dse_path is None:
        # 依赖缺失 —— **报 ERROR，不静默跳过**（廓者未名夜的教训）
        return [{
            "severity": "error", "category": "内容包", "code": "DSE-NOT-INSTALLED",
            "file": project, "line": 0, "snippet": "",
            "message": "未找到 dse CLI —— dse-core 未安装或不在当前解释器的 Scripts 目录",
            "suggestion": (
                "执行 `python -m pip install -r requirements.txt`"
                "（或跑 `bash tools/bootstrap.sh` / `tools\\bootstrap.ps1` 一步到位）"
            ),
        }]

    if "PATH" in origin:
        findings.append({
            "severity": "warn", "category": "内容包", "code": "DSE-EXE-ORIGIN",
            "file": project, "line": 0, "snippet": dse_path,
            "message": f"dse CLI 来自 PATH 而非当前解释器：{dse_path}",
            "suggestion": "确认它与当前 Python 同源；否则校验结果不可复现",
        })

    findings += gate_check(dse_path, project, root)
    findings += gate_traverse(dse_path, project, root)
    findings += gate_coverage(dse_path, project, root)
    return findings


if __name__ == "__main__":
    # argv[1] = 仓根，argv[2] = 内容包工程目录（相对仓根）
    # 缺省：仓根取当前目录，工程目录取默认
    root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    project = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROJECT
    code = run("dse", check, root, project)
    sys.exit(code)
