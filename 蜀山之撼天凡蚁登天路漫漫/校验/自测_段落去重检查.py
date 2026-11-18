#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证验收脚本的「章内段落去重」检查项确实能抓到重复段。

**直接复用 验收_V2-C21至C25.py 里的判定函数**，避免两处逻辑漂移
（上一版自测与验收各写一份阈值，结果自测失准——这本身就是教训）。

用法：python3 校验/自测_段落去重检查.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "校验"))

from importlib import import_module  # noqa: E402

acc = import_module("验收_V2-C21至C25".replace("-", "_")) if False else None

# 模块名含中文与连字符，用文件路径直接加载
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "acc", os.path.join(ROOT, "校验", "验收_V2-C21至C25.py"))
acc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acc)


def main():
    ok = True

    # 1. 真实章节：应全部为 0 重复
    f = os.path.join(ROOT, "正文/蜀山 卷二 226–230｜C21 用一次.md")
    t = open(f, encoding="utf-8").read()
    parts = re.split(r"^# 第 (\d+) 章 (.+)$", t, flags=re.M)
    print("== 真实章节（C21）==")
    for i in range(1, len(parts) - 1, 3):
        d = acc.find_dup_segments(parts[i + 2])
        print(f"  第{parts[i]}章 重复段 {len(d)}")
        if d:
            ok = False

    # 2. 人造样本：叙述段重复应能检出
    print("\n== 人造样本 A：叙述段重复（应检出）==")
    sample = "\n".join([
        "（他数了一遍，二十七个印子，一步也没有乱。）",
        "（他数了一遍，二十七个印子，一步也没有乱。）",
        "（这是第三行，不重复。）",
    ])
    d = acc.find_dup_segments(sample)
    print(f"  检出 {len(d)} 处：{d}")
    if not d:
        print("  ✗ 检查项失效！人造重复叙述段没被抓到")
        ok = False
    else:
        print("  ✓ 检查项有效")

    # 3. 对白行重复应不算——本书的对话回环是刻意手法
    print("\n== 人造样本 B：对白行重复（应判 0，避免误报）==")
    dlg = "\n".join([
        "老弟子说，往南是海。",
        "老弟子说，往南是海。",
        "老弟子说，往南十二天，是海。",
    ])
    d2 = acc.find_dup_segments(dlg)
    print(f"  检出 {len(d2)} 处（应为 0）")
    if d2:
        print("  ✗ 误报：对白回环被当成重复段")
        ok = False

    # 4. 短叙述重复应不算
    print("\n== 人造样本 C：短叙述重复（应判 0，避免误报）==")
    short = "\n".join(["（嗯。）", "（嗯。）", "（他没答。）", "（他没答。）"])
    d3 = acc.find_dup_segments(short)
    print(f"  检出 {len(d3)} 处（应为 0）")
    if d3:
        ok = False

    # 5. 相邻复制（间隔 <8 段）应被判为机械复制
    print("\n== 人造样本 D：相邻机械复制（应检出）==")
    line = "（他数了一遍，二十七个印子，一步也没有乱。）"
    near = "\n".join([line, "（中间隔一行。）", "（再隔一行。）", line])
    d4 = acc.find_dup_segments(near)
    print(f"  检出 {len(d4)} 处（应为 1）")
    if not d4:
        print("  ✗ 相邻机械复制没被抓到")
        ok = False

    # 6. 间隔 ≥8 段的复现应不算（刻意回环）
    print("\n== 人造样本 E：间隔复现（应判 0，刻意回环）==")
    far = "\n".join([line] + [f"（填充第{i}段，内容不同，用来拉开间隔。）" for i in range(1, 11)] + [line])
    d5 = acc.find_dup_segments(far)
    print(f"  检出 {len(d5)} 处（应为 0）")
    if d5:
        print("  ✗ 刻意回环被误判")
        ok = False

    print("\n结论：" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
