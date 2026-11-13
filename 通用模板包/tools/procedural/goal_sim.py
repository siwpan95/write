#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标驱动场景模拟 · goal_sim.py（v3.12，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.3（第 4 代：TALE-SPIN 微缩）
用途：给角色配目标/位置/持有物与障碍，程序按固定规则推演事件链——
      "情节是角色撞出来的"。事件日志供人工改编为 02 的 L4 章纲一句话
      或 10 的节拍候选；代价与情感动机必须人补。
纪律：只产事件候选、不产正文；每条事件须人工补"代价 + 动机"后才能入纲。

内置演示局：拾荒者小满想修好水泵（需要：扳手、密封圈），废墟里有
巡机者（障碍）与野狗（障碍），同伴有自备目标。规则循环至目标达成或轮数耗尽。
用法：
  python tools/procedural/goal_sim.py                  # 跑内置演示局
  python tools/procedural/goal_sim.py --max-turns 12   # 调最大轮数
退出码：0 成功。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# —— 演示局配置（实际使用时改成你自己的表；这是 13 区域包素材的合法来源） ——
PLACES = {
    "废弃泵站":  {"items": ["水泵"]},
    "维修铺":    {"items": ["扳手"]},
    "翻倒货柜":  {"items": ["密封圈"]},
    "锈原小道":  {"items": []},
    "营地":      {"items": ["干粮"]},
}
ACTORS = {
    "小满": {"at": "废弃泵站", "goal": ("修复", "水泵", ["扳手", "密封圈"]), "has": [], "alive": True},
    "阿砾": {"at": "营地", "goal": ("送交", "干粮", ["干粮"]), "has": ["干粮"], "alive": True},
}
OBSTACLES = {  # 障碍 = 占着物品或不让人通过的对手
    "巡机者": {"at": "维修铺", "guards": "扳手"},
    "野狗群": {"at": "翻倒货柜", "guards": "密封圈"},
}
# 阻力表：角色 vs 障碍 的胜率（0~1）。改这里 = 改戏剧阻力，其余不动。
ODDS = {("小满", "巡机者"): 0.6, ("小满", "野狗群"): 0.7}


class Sim:
    def __init__(self, max_turns):
        self.max_turns = max_turns
        self.log = []

    def emit(self, turn, text):
        self.log.append("T%02d %s" % (turn, text))

    def route_to(self, actor, place, turn):
        """直线寻路（演示局地图是全连通的；实局可换成邻接表）。"""
        if ACTORS[actor]["at"] != place:
            ACTORS[actor]["at"] = place
            self.emit(turn, "%s 移动到 %s" % (actor, place))

    def try_goal(self, actor, turn, rng):
        st = ACTORS[actor]
        verb, obj, needs = st["goal"]
        missing = [x for x in needs if x not in st["has"]]
        if not missing:
            # 物件齐了 → 回到目标物件所在地执行目标
            home = next((p for p, v in PLACES.items() if obj in v["items"]), st["at"])
            if st["at"] != home:
                self.route_to(actor, home, turn)
            PLACES[home]["items"].remove(obj)
            st["goal"] = None
            self.emit(turn, "%s 达成目标（%s %s），事件闭合" % (actor, verb, obj))
            return True
        need = missing[0]
        # 找物件在哪
        where = next((p for p, v in PLACES.items() if need in v["items"]), None)
        if where is None:
            self.emit(turn, "%s 找不到 %s，目标受阻" % (actor, need))
            st["goal"] = None
            return False
        self.route_to(actor, where, turn)
        # 有守卫 → 按阻力表对抗
        guard = next((g for g, o in OBSTACLES.items() if o["at"] == where and o["guards"] == need), None)
        if guard:
            if rng.random() < ODDS.get((actor, guard), 0.5):
                self.emit(turn, "%s 在 %s 对抗 %s，胜，取得 %s（注意：代价待人工补）" % (actor, where, guard, need))
                st["has"].append(need)
                PLACES[where]["items"].remove(need)
            else:
                self.emit(turn, "%s 在 %s 被击退，负伤未取得 %s（代价已自动成立）" % (actor, where, need))
            return False
        PLACES[where]["items"].remove(need)
        st["has"].append(need)
        self.emit(turn, "%s 在 %s 取得 %s" % (actor, where, need))
        return False


def run(seed=1, max_turns=10):
    import random
    rng = random.Random(seed)
    sim = Sim(max_turns)
    for turn in range(1, max_turns + 1):
        done = True
        for actor in ACTORS:
            st = ACTORS[actor]
            if st["alive"] and st["goal"]:
                done = False
                sim.try_goal(actor, turn, rng)
        if done:
            break
    return sim.log


def main():
    ap = argparse.ArgumentParser(description="目标驱动场景模拟（事件候选层，禁止直接进正文）")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=10)
    args = ap.parse_args()

    log = run(args.seed, args.max_turns)
    print("目标驱动场景模拟 · 演示局 · seed=%d（可复现）" % args.seed)
    print("-" * 52)
    for line in log:
        print("  " + line)
    print("-" * 52)
    print("验收门（18 §三.3）：① 事件链因果闭合 ② 每事件人工补代价与情感动机后才入 02/10")
    print("                      ③ 不得跳过 15 拍定位直接成文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
