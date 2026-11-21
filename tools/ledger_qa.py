#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_qa.py —— 连载台账问答工具（v3.18，仓级工具）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.5 槽位五（LLM 混合流水线）
          + 06-连载护航模板.md §7.1 台账
用途：把 `06` 连载护航台账的条目灌进可学习记忆库，得到**台账问答**能力——
      「S9 埋在哪一章？」「第十章的结论行填了什么？」「本卷埋了哪些伏笔？」

为什么需要它（补 PKM 的一个缺口）
-------------------------------
`PKM` 检索层能回答「**哪些文档**命中了关键词」，但回答不了「**答案是什么、
散落在几处**」。本工具补的就是这一段：**条目级精确回放**。

借鉴 peasy-ai 的机制，但**不直接用 AITrainer**（借鉴记账见 通用模板包/14 §十一 D-19）
-----------------------------------------------------------------------------
peasy-ai 1.0.1 的 `easy_ai.trpg.trainer.AITrainer` 提供「事件 → 问答对 → 记忆库 →
精确回放」的机制，这套机制值得借鉴。但它的**问法是 TRPG 硬编码的**
（"XX检定是什么结果" / "XX技能有什么用"），与网文台账语义对不上；
且台账事件的类型（伏笔埋设、字数结算、结论行填写、重复提示…）是本仓特有的。

故此处：**取机制**（事件 → 学习 → 可问答 → 可持久化），
     **换事件语义**（本仓台账事件），**换问法模板**（本仓问答句式）。
AICore 本身**零三方依赖**（纯标准库），故本工具在核心内核环境下也能跑。

用法：
  # 1) 灌台账（JSON Lines：每行一条台账记录）
  python tools/ledger_qa.py learn <台账.jsonl> [--state 台账记忆.json]

  # 2) 问
  python tools/ledger_qa.py ask "S9 埋在哪一章" [--state 台账记忆.json]

  # 3) 批量问（每行一个问句）
  python tools/ledger_qa.py ask-batch <questions.txt> [--state 台账记忆.json]

  # 4) 看已学条目
  python tools/ledger_qa.py list [--state 台账记忆.json]

台账记录格式（JSON Lines，每行一条）：
  {"kind": "foreshadow", "id": "S9", "where": "第 07 章",
   "text": "制度记得住表、记不住人"}
  {"kind": "summary",   "id": "10", "where": "第 10 章",
   "text": "归档单被判「回复不完整」⇒ 退回重办，复核人另行指派"}
  {"kind": "warn",      "id": "W-03", "where": "第 08 章",
   "text": "「一股」出现 3 次，超阈值"}

**纪律**：本工具**只读台账、只写自己的记忆文件**，不改正文、不改台账。
问答是**条目级精确回放**，不是理解 —— 问不在台账里的问题会明确说「不知道」，
不会编造（这是 peasy-ai 的可学习记忆 + 兜底话术的固有行为，实测确认）。

作者：WorkBuddy ｜ 2026-11-21
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

# ── peasy-ai AICore 定位（零三方依赖，核心内核环境下可用） ──────────────────
def load_aicore():
    """载入 easy_ai.AICore；若环境无 peasy-ai 则给出明确指引。

    ⚠️ **静音 peasy-ai 的 INFO 日志**（实测踩坑）：它初始化时打
    「日志系统初始化完成」等 INFO，与本工具的答案一起写到 stdout —
    `ledger_qa.py ask "..." | jq` 之类的管道会被日志污染。
    数据通道必须纯净：答案走 stdout，诊断走 stderr（同 checker_protocol）。
    """
    import logging
    logging.disable(logging.INFO)

    try:
        from easy_ai import AICore
        return AICore
    except ImportError:
        print(
            "[FAIL] 未找到 peasy-ai（easy_ai）。\n"
            "       安装：python -m pip install peasy-ai==1.0.1\n"
            "       或按 requirements.txt 一次装齐。",
            file=sys.stderr,
        )
        raise SystemExit(1)


# ── 台账事件 → 问答句式（本仓语义，非 TRPG） ───────────────────────────────
# 每种 kind 一组问法模板。{id} 是槽位填充。
# 刻意**不复用** peasy-ai 的 TRPG 问法（"XX检定是什么结果"等）——
# 那是跑团语义，与连载台账对不上。
#
# ⚠️ 模板必须覆盖**自然问法的多种措辞**（实测踩坑）：
#   存 "周立 是谁"（带空格）→ 问 "周立是谁"（无空格）**匹配不上**，
#   AICore 的记忆匹配要求高相似度，空格差异即失配。
#   故每条模板都给出紧凑/松散两种写法，并在 learn 时**两种都存**。
QUESTION_TEMPLATES = {
    "foreshadow": [
        "{id}埋在哪一章", "{id} 埋在哪一章",
        "{id}是什么伏笔", "{id} 是什么伏笔",
        "伏笔{id}在哪埋的", "伏笔 {id} 在哪埋的",
        "{id}埋在哪", "{id} 在哪",
    ],
    "summary": [
        "{id}这章发生了什么", "{id} 这章发生了什么",
        "{id}章的摘要", "{id} 章的摘要",
        "第{id}章讲了什么", "第 {id} 章讲了什么",
        "{id}章写了什么", "{id} 章写了什么",
    ],
    "warn": [
        "{id}是什么问题", "{id} 是什么问题",
        "{id}在哪出现的", "{id} 在哪出现的",
        "{id}是什么警告", "{id} 是什么警告",
    ],
    "char": [
        "{id}的人物设定", "{id} 的人物设定",
        "{id}是谁", "{id} 是谁",
        "{id}是什么人", "{id} 是什么人",
    ],
    "fact": [
        "{id}是什么设定", "{id} 是什么设定",
        "{id}的口径", "{id} 的口径",
        "{id}的设定是什么", "{id} 的设定是什么",
    ],
    # v3.18.3 增补（对接《廓者》06-连载护航的真实台账）
    "timeline": [
        "{id}是什么时候", "{id} 是什么时候",
        "{id}发生了什么", "{id} 发生了什么",
        "{id}锚点", "{id} 锚点",
    ],
    "thread": [
        "{id}这条线", "{id} 这条线",
        "{id}什么时候收束", "{id} 什么时候收束",
        "{id}是什么线", "{id} 是什么线",
    ],
    "chapter": [
        "第{id}章写了什么", "第 {id} 章写了什么",
        "{id}章的台账", "{id} 章的台账",
        "{id}章埋了什么", "{id} 章埋了什么",
    ],
}

DEFAULT_STATE = "./.workbuddy/ledger_qa_memory.json"


def learn_from_ledger(ai, ledger_path: str, state_path: str) -> int:
    """读台账（JSON Lines）→ 灌进 AICore 记忆 → 持久化。"""
    if not os.path.exists(ledger_path):
        print(f"[FAIL] 台账文件不存在：{ledger_path}", file=sys.stderr)
        return 1

    n = 0
    kinds: dict[str, int] = {}
    with io.open(ledger_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[WARN] 第 {lineno} 行不是合法 JSON，跳过：{exc}", file=sys.stderr)
                continue

            kind = rec.get("kind", "fact")
            rid = str(rec.get("id", "")).strip()
            text = str(rec.get("text", "")).strip()
            where = str(rec.get("where", "")).strip()
            if not text:
                continue

            # 回答正文：文本 + 出处（出处是台账的命门 —— 「答案在哪」比「答案是什么」更难）
            answer = f"{text}（{where}）" if where else text
            for q in QUESTION_TEMPLATES.get(kind, QUESTION_TEMPLATES["fact"]):
                ai.learn(q.format(id=rid), answer)

            n += 1
            kinds[kind] = kinds.get(kind, 0) + 1

    ai.save(state_path)
    print(f"[OK] 已学 {n} 条台账条目 → {state_path}")
    for k, v in sorted(kinds.items()):
        print(f"     {k}: {v}")
    print(f"[INFO] 记忆条数：{ai.memory_count}")
    return 0


def ask(ai, question: str) -> str:
    """问一条。

    ⚠️ **不编造**：AICore 匹配不到时返回兜底话术（「这个话题很有意思…」
    「不太确定该怎么回应…」等**多条**，来自 rules／马尔科夫／兜底链多个来源），
    对台账工具而言那是**误导** —— 用户会以为「台账里真没这条」还是「工具坏了」。

    判据用 `search_memory()`（返回匹配到的记忆 key 列表，命中则非空），
    **不靠猜回答文本的长短或内容** —— 实测踩坑：初版按「答案含『（』」判断，
    而 `where` 为空的条目答案不含括号，会被误判成「没找到」。
    """
    hits = ai.search_memory(question)
    if not hits:
        return (f"台账里没有这一条的记录（问法：{question}）。\n"
                f"        若是台账里确实有，请换一种问法，或用 "
                f"`ledger_qa.py learn` 补录该条目（带 kind/id/where/text）。")
    return ai.respond(question)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ledger_qa.py", description="连载台账问答工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_learn = sub.add_parser("learn", help="灌台账条目")
    p_learn.add_argument("ledger", help="台账 JSON Lines 路径")
    p_learn.add_argument("--state", default=DEFAULT_STATE, help="记忆文件路径")

    p_ask = sub.add_parser("ask", help="问一条")
    p_ask.add_argument("question")
    p_ask.add_argument("--state", default=DEFAULT_STATE)

    p_batch = sub.add_parser("ask-batch", help="批量问（每行一问）")
    p_batch.add_argument("questions")
    p_batch.add_argument("--state", default=DEFAULT_STATE)

    p_list = sub.add_parser("list", help="列出已学条目数")
    p_list.add_argument("--state", default=DEFAULT_STATE)

    args = ap.parse_args(argv)
    AICore = load_aicore()

    if args.cmd == "learn":
        ai = AICore()
        return learn_from_ledger(ai, args.ledger, args.state)

    # 其余命令：先载入已有记忆
    if not os.path.exists(args.state):
        print(f"[FAIL] 记忆文件不存在：{args.state}\n"
              f"       先灌台账：python tools/ledger_qa.py learn <台账.jsonl>",
              file=sys.stderr)
        return 1
    ai = AICore()
    ai.load(args.state)

    if args.cmd == "ask":
        print(ask(ai, args.question))
        return 0

    if args.cmd == "ask-batch":
        with io.open(args.questions, encoding="utf-8") as f:
            for line in f:
                q = line.strip()
                if not q or q.startswith("//"):
                    continue
                print(f"Q: {q}")
                print(f"A: {ask(ai, q)}\n")
        return 0

    if args.cmd == "list":
        print(f"记忆条数：{ai.memory_count}")
        print(f"匹配器：{ai.matchers_info}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
