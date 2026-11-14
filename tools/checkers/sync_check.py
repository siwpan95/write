#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_check.py —— 三端同步状态检查（适配器）
================================================================================
本仓的 git 远端有**两个**（Gitee `origin` ＋ GitHub `github`）。
「提交了」不等于「推送了」，也不等于「两端都推了」——
GitHub 直连在部分网络下被阻断，会静默造成**单端落后**。

本检查器把「双端是否同步」变成**可校验的事实**，而不是靠人记。

判定口径
--------
- **ERROR**：某个可达远端的 master 与本地 HEAD 不一致 → 远端落后，提交没推上去。
- **WARN**：某个远端**不可达**（网络阻断）→ 无法确认其状态。
  这不是「失败」，但必须显性上报 —— 静默落后是比报错更糟的结果。
- **INFO**：各远端的 HEAD 摘要（人读）。

**只读**：本检查器只执行 `git ls-remote`（读远端引用），不推送、不改文件。

作者：WorkBuddy ｜ 2026-11-13
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

# 远端名 → 说明
REMOTES = {
    "origin": "Gitee（主）",
    "github": "GitHub（镜像）",
}
BRANCH = "master"


def git(args: list[str], cwd: str, timeout: int = 25) -> tuple[int, str, str]:
    """跑 git 命令，返回 (退出码, stdout, stderr)。**永不抛异常。"""
    try:
        p = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"超时（{timeout}s）"
    except (OSError, subprocess.SubprocessError) as e:
        return 2, "", f"{type(e).__name__}: {e}"


def check(root: str) -> list[dict]:
    findings: list[dict] = []

    code, head, _ = git(["rev-parse", "HEAD"], root)
    if code != 0:
        return [{
            "severity": "error", "category": "同步", "code": "SYNC-NO-HEAD",
            "file": "-", "line": 0, "snippet": "",
            "message": "无法读取本地 HEAD",
            "suggestion": "确认当前目录是 git 仓库",
        }]
    local = head

    code, branch, _ = git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    cur_branch = branch or BRANCH

    for remote, label in REMOTES.items():
        rc, out, err = git(["ls-remote", remote, f"refs/heads/{BRANCH}"], root)
        if rc != 0:
            findings.append({
                "severity": "warn", "category": "同步", "code": "SYNC-REMOTE-UNREACHABLE",
                "file": f"remote:{remote}", "line": 0, "snippet": "",
                "message": f"{remote}（{label}）不可达：{err or '未知原因'}",
                "suggestion": (
                    "GitHub 直连在部分网络下被阻断 —— "
                    "该远端状态无法确认，可能已落后；恢复网络后执行 `git push github master`"
                    if remote == "github" else
                    "检查网络或远程配置（git remote -v）"
                ),
            })
            continue

        remote_sha = out.split()[0] if out else ""
        if remote_sha and remote_sha != local:
            # ⚠️ sha 不同 ≠ 远端落后。可能是：远端落后／本地落后／历史分叉。
            # 与 tools/bootstrap.* 第 5 步同口径：先判关系再给建议。
            # 若远端对象本地没有，merge-base 无法判定 ——
            # **分不清就别乱判**，报「无法确认」并提示 fetch。
            obj_ok = git(["cat-file", "-e", f"{remote_sha}^{{commit}}"], root)[0] == 0
            if not obj_ok:
                findings.append({
                    "severity": "warn", "category": "同步",
                    "code": "SYNC-UNKNOWN-STATE",
                    "file": f"remote:{remote}", "line": 0, "snippet": "",
                    "message": (
                        f"{remote}（{label}）与本地 sha 不同，且本地无该提交对象，"
                        f"**无法判定谁领先**（远端 {remote_sha[:7]} ／ 本地 {local[:7]}）"
                    ),
                    "suggestion": (
                        f"先 `git fetch {remote}` 再跑本检查；"
                        "若确认本地已是最新，用 `git push --force-with-lease` 前先备份远端旧历史"
                    ),
                })
                continue

            remote_is_ancestor = git(
                ["merge-base", "--is-ancestor", remote_sha, local], root)[0] == 0
            local_is_ancestor = git(
                ["merge-base", "--is-ancestor", local, remote_sha], root)[0] == 0

            if remote_is_ancestor:
                # 远端落后本地：本地含远端提交，但尚未推送
                n = git(["rev-list", "--count", f"{remote_sha}..{local}"], root)[1] or "?"
                findings.append({
                    "severity": "error", "category": "同步", "code": "SYNC-REMOTE-BEHIND",
                    "file": f"remote:{remote}", "line": 0, "snippet": "",
                    "message": (
                        f"{remote}（{label}）落后本地 {n} 个提交"
                        f"（远端 {remote_sha[:7]} ／ 本地 {local[:7]}）"
                    ),
                    "suggestion": f"执行 `git push {remote} {cur_branch}`",
                })
            elif local_is_ancestor:
                # 本地落后远端：远端有并行工作线
                n = git(["rev-list", "--count", f"{local}..{remote_sha}"], root)[1] or "?"
                findings.append({
                    "severity": "error", "category": "同步", "code": "SYNC-LOCAL-BEHIND",
                    "file": f"remote:{remote}", "line": 0, "snippet": "",
                    "message": (
                        f"本地落后 {remote}（{label}）{n} 个提交"
                        f"（远端 {remote_sha[:7]} ／ 本地 {local[:7]}）"
                    ),
                    "suggestion": (
                        f"远端有并行工作线：先 `git fetch {remote}`，"
                        f"再 `git pull --rebase {remote} {cur_branch}`；"
                        "rebase 后须重建入库产物（npm run pkm:build）"
                    ),
                })
            else:
                findings.append({
                    "severity": "error", "category": "同步", "code": "SYNC-DIVERGED",
                    "file": f"remote:{remote}", "line": 0, "snippet": "",
                    "message": (
                        f"{remote}（{label}）与本地**历史分叉**"
                        f"（远端 {remote_sha[:7]} ／ 本地 {local[:7]}）"
                    ),
                    "suggestion": (
                        f"先备份远端旧历史（`git branch backup/... {remote}/{cur_branch}`），"
                        "确认内容等价后用 `git push --force-with-lease`；"
                        "**不要盲目 git pull**（会拉回旧历史造成二次分叉）"
                    ),
                })
        else:
            findings.append({
                "severity": "info", "category": "同步", "code": "SYNC-IN-SYNC",
                "file": f"remote:{remote}", "line": 0, "snippet": "",
                "message": f"{remote}（{label}）已同步 @ {local[:7]}",
                "suggestion": "—",
            })

    return findings


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    code = run("sync", check, os.path.abspath(root))
    sys.exit(code)
