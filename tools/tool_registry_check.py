#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tool_registry_check.py —— 工具资产登记门禁（2026-11-23 新增）

用途：把 tools/TOOLS_MAP.md 作为机器可读的权威表，扫描全仓脚本与之比对：
  E1 未登记：磁盘有脚本、地图无登记 → ERROR（新脚本没进台账）
  E2 已删除：地图有登记、磁盘无脚本 → ERROR（删脚本没更新台账）
  E3 分类漂移：地图某段的脚本数量与段标题声明不符 → ERROR
  W1 地图缺失：TOOLS_MAP.md 不存在 → ERROR

退出码：0 全过 / 1 有 ERROR。零三方依赖，换机即跑。

口径：与 TOOLS_MAP.md 同——本机快照，换机/新增脚本后须复跑本脚本确认。
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, 'tools', 'TOOLS_MAP.md')
EXTS = ('.py', '.sh', '.mjs', '.ps1')
SKIP_DIRS = {'node_modules', '__pycache__', '.git'}


def scan_scripts():
    """机械扫描全仓脚本，返回相对路径集合。"""
    out = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(EXTS):
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace('\\', '/')
                out.add(rel)
    return out


def parse_registry():
    """从 TOOLS_MAP.md 解析登记的脚本路径集合。
    登记行格式：| `path/to/script.py` | A | ... |"""
    reg = set()
    if not os.path.isfile(MAP):
        return reg, False
    with io.open(MAP, 'r', encoding='utf-8-sig') as f:
        text = f.read()
    for m in re.finditer(r'^\|\s*`([^`]+?\.(?:py|sh|mjs|ps1))`\s*\|', text, re.M):
        reg.add(m.group(1))
    return reg, True


def main():
    disk = scan_scripts()
    reg, exists = parse_registry()
    errors = []

    if not exists:
        print('ERROR: tools/TOOLS_MAP.md 不存在——请先建立工具地图')
        return 1

    unreg = sorted(disk - reg)
    stale = sorted(reg - disk)

    if unreg:
        errors.append('E1 未登记脚本 %d 个（新脚本必须进 tools/TOOLS_MAP.md）：' % len(unreg))
        for p in unreg:
            errors.append('    + ' + p)
    if stale:
        errors.append('E2 已删除但仍在台账 %d 个（删脚本须同步地图）：' % len(stale))
        for p in stale:
            errors.append('    - ' + p)

    # E3：地图里"### xxx — N 个"声明与各段实际登记条数核对
    with io.open(MAP, 'r', encoding='utf-8-sig') as f:
        lines = f.read().splitlines()
    cur = None
    declared = {}
    counted = {}
    for ln in lines:
        m = re.match(r'^### (.+?) — (\d+) 个 · ([A-D/]+) 类', ln)
        if m:
            cur = m.group(1)
            declared[cur] = int(m.group(2))
            counted[cur] = 0
            continue
        if cur and re.match(r'^\|\s*`[^`]+?\.(?:py|sh|mjs|ps1)`\s*\|', ln):
            counted[cur] += 1
    for k in declared:
        if declared[k] != counted.get(k, 0):
            errors.append('E3 分类段数量漂移：%s 声明 %d，实登 %d' % (k, declared[k], counted.get(k, 0)))

    print('=' * 60)
    print('工具资产登记门禁 · tool_registry_check.py')
    print('=' * 60)
    print('  磁盘脚本数  ', len(disk))
    print('  地图登记数  ', len(reg))
    print('  分类段数    ', len(declared))
    print('-' * 60)
    if errors:
        for e in errors:
            print('  ' + e)
        print('-' * 60)
        print('结论：FAIL（%d 条）' % len(errors))
        return 1
    print('结论：PASS（磁盘 %d = 登记 %d，无未登记/无残留）' % (len(disk), len(reg)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
