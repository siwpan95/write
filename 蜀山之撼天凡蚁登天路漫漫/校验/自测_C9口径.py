#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C9（416–420）额外一致性自检：验收脚本之外的口径项。

用法：python3 校验/自测_C9口径.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "正文/蜀山 卷四 416–420｜C9 印.md"
P = os.path.join(ROOT, REL)

# 指令点名的额外禁用词（验收脚本未覆盖的那部分）
EXTRA_BAD = ["状态", "信息", "用户", "配置", "版本", "指标", "流程",
             "才是全部", "才成", "才是根", "才是人", "图标", "打工人",
             "躺平", "社死", "降维", "CPU", "PUA", "流量", "热搜", "二次元"]

# 红线/口径关键词（应当出现，且不该出现的东西）
MUST_HAVE = {
    416: ["两指"],
    417: [],
    418: [],
    419: [],
    420: [],
}
MUST_NOT = {
    "应焚": "「应焚」二字属于 C10 第 421 章口径，本批不得提前出现",
    "写成": "「写成」易与 423 主动伤人混淆，本批不应出现",
    "第三个字": "卷三 375「我冷」是两字口径的延伸，本批不得出现",
}


def chapters(text):
    parts = re.split(r"^# 第 (\d+) 章 (.+)$", text, flags=re.M)
    out = []
    for i in range(1, len(parts) - 1, 3):
        out.append((int(parts[i]), parts[i + 1].strip(), parts[i + 2]))
    return out


def main():
    if not os.path.exists(P):
        print("[E] 正文文件不存在:", REL)
        return 1
    text = open(P, encoding="utf-8").read()
    chs = chapters(text)
    errs = 0

    print("=== 章号与标题 ===")
    expect = {416: "两指", 417: "我不信", 418: "我去问", 419: "她认了", 420: "为你好"}
    if [c[0] for c in chs] != list(range(416, 421)):
        print("[E] 章号序列错误:", [c[0] for c in chs])
        errs += 1
    for num, title, body in chs:
        if expect.get(num) != title:
            print(f"[E] {num} 标题应为「{expect.get(num)}」，实为「{title}」")
            errs += 1

    print("\n=== 逐章指标 ===")
    for num, title, body in chs:
        pure = re.sub(r"^#.*$", "", body, flags=re.M).replace("（本章完）", "")
        n = len(re.sub(r"\s", "", pure))
        par = len([x for x in body.split("\n") if x.strip().startswith("（")])
        y = body.count("杨成志")
        q = sum(body.count(x) for x in ["“", "”", "「", "」", '"'])
        bad = [w for w in EXTRA_BAD if w in body]
        bare = [x for x in body.split("\n") if x.strip() and not x.strip().startswith("（")
                and not x.strip().startswith("#")]
        head = next((x for x in body.split("\n") if x.strip()), "")
        tail = body.rstrip().split("\n")[-1].strip()
        e = []
        if not (2200 <= n <= 3000):
            e.append(f"字数 {n}")
        if par < 80:
            e.append(f"括号段 {par}")
        if not (2 <= y <= 7):
            e.append(f"杨成志 {y} 次")
        if q:
            e.append(f"引号 {q}")
        if bad:
            e.append(f"额外禁词 {bad}")
        if bare:
            e.append(f"裸行 {len(bare)} 处（例：{bare[0][:16]}）")
        if not re.match(r"^（.*月.*，.*时。.*）$", head.strip()):
            e.append(f"章首时间锚异常：{head[:24]}")
        if tail != "（本章完）":
            e.append(f"章末标记异常：{tail[:16]}")
        if e:
            errs += 1
            print(f"  {num} {title:6} {n:5}字 括号段{par:4} 杨{y:2} 引号{q}  [E] {'; '.join(e)}")
        else:
            print(f"  {num} {title:6} {n:5}字 括号段{par:4} 杨{y:2} 引号{q}  OK")

    print("\n=== 全批红线 ===")
    for w, why in MUST_NOT.items():
        if w in text:
            print(f"[E] 出现「{w}」：{why}")
            errs += 1
    # 不许赢过「有传」的人：她占上风的三处必须成立
    # 419 钩子「我是为你好」：允许语义等价的措辞变体（本作人物说话常为长句铺陈）
    for kw, label in [("是我凿的", "419 她亲口认「是我凿的」"),
                      ("为你好", "419 钩子「我是为你好」（允许措辞变体）"),
                      ("活不成", "420「那一行留着，你就活不成」")]:
        if kw not in text:
            print(f"[E] 缺关键落点：{label}（关键词「{kw}」未出现）")
            errs += 1
    # 420 名分：欠她第三次
    if not re.search(r"欠.{0,4}第三", text):
        print("[E] 420 名分「欠她第三次」未落地（未见「欠…第三」）")
        errs += 1
    # 不许出现胜利口吻
    for w in ["赢了", "他赢", "胜了"]:
        if w in text:
            print(f"[W] 出现疑似胜利口吻「{w}」，人工确认红线")
    # 主角状态：无墨不得写字
    for num, title, body in chs:
        if re.search(r"他(拿|取|蘸)(起)?(自己的)?笔", body) or "他写下" in body or "他写了" in body:
            print(f"[E] {num} 疑似主角执笔写字（红线：本批他无墨无笔）")
            errs += 1

    print("\n=== 时间锚序列 ===")
    anchors = []
    for num, title, body in chs:
        first = next((x.strip() for x in body.split("\n") if x.strip()), "")
        m = re.search(r"（(.+?)，(.+?)。", first)
        anchors.append((num, m.group(1) if m else "?", m.group(2) if m else "?"))
    for a in anchors:
        print(f"  {a[0]} {a[1]} {a[2]}")

    print("\n" + "=" * 60)
    print(f"C9 口径自检: {'PASS' if errs == 0 else f'FAIL {errs} 项'}")
    return 0 if errs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
