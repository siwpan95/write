#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
目标驱动场景模拟 · goal_sim.py（v3.12.2，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.3（第 4 代：TALE-SPIN 微缩）
用途：给角色配目标/位置/持有物与障碍，程序按固定规则推演事件链——
      "情节是角色撞出来的"。事件日志供人工改编为 02 的 L4 章纲一句话
      或 10 的节拍候选；代价与情感动机必须人补。
纪律：只产事件候选、不产正文；每条事件须人工补"代价 + 动机"后才能入纲。

场景配置（--scenario 传入 JSON；缺省用内置演示局）：
  {
    "places":   {"维修铺": {"items": ["扳手"]}, ...},
    "actors":   {"小满": {"at": "废弃泵站", "goal": ["修复", "水泵", ["扳手", "密封圈"]],
                          "has": []}},
    "obstacles": {"巡机者": {"at": "维修铺", "guards": "扳手"}},
    "odds":     {"小满|巡机者": 0.6}
  }
  - 寻路按全连通处理（实局可换邻接表）；obstacles 的守卫名须是 actors 外的角色。
用法：
  python tools/procedural/goal_sim.py                          # 内置演示局
  python tools/procedural/goal_sim.py --scenario my.json --seed 3 --max-turns 12
退出码：0 成功；1 场景配置错误。
"""
import argparse
import json
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# —— 内置演示局（拾荒者修水泵） ——
DEMO = {
    "places": {
        "废弃泵站": {"items": ["水泵"]},
        "维修铺":   {"items": ["扳手"]},
        "翻倒货柜": {"items": ["密封圈"]},
        "锈原小道": {"items": []},
        "营地":     {"items": ["干粮"]},
    },
    "actors": {
        "小满": {"at": "废弃泵站", "goal": ["修复", "水泵", ["扳手", "密封圈"]], "has": []},
        "阿砾": {"at": "营地", "goal": ["送交", "干粮", ["干粮"]], "has": ["干粮"]},
    },
    "obstacles": {
        "巡机者": {"at": "维修铺", "guards": "扳手"},
        "野狗群": {"at": "翻倒货柜", "guards": "密封圈"},
    },
    "odds": {"小满|巡机者": 0.6, "小满|野狗群": 0.7},
}


class Sim:
    def __init__(self, scenario, max_turns):
        self.places = {p: list(v["items"]) for p, v in scenario["places"].items()}
        self.actors = {a: {"at": v["at"], "goal": list(v["goal"]), "has": list(v["has"])}
                       for a, v in scenario["actors"].items()}
        self.obstacles = scenario.get("obstacles", {})
        self.odds = scenario.get("odds", {})
        self.max_turns = max_turns
        self.log = []

    def emit(self, turn, text):
        self.log.append("T%02d %s" % (turn, text))

    def route_to(self, actor, place, turn):
        """直线寻路（场景地图按全连通处理；实局可换邻接表）。"""
        if self.actors[actor]["at"] != place:
            self.actors[actor]["at"] = place
            self.emit(turn, "%s 移动到 %s" % (actor, place))

    def try_goal(self, actor, turn, rng):
        st = self.actors[actor]
        verb, obj, needs = st["goal"][0], st["goal"][1], list(st["goal"][2])
        missing = [x for x in needs if x not in st["has"]]
        if not missing:
            # 物件齐了 → 回到目标物件所在地执行目标
            home = next((p for p, v in self.places.items() if obj in v), st["at"])
            if st["at"] != home:
                self.route_to(actor, home, turn)
            if obj in self.places.get(home, []):
                self.places[home].remove(obj)
            st["goal"] = None
            self.emit(turn, "%s 达成目标（%s %s），事件闭合" % (actor, verb, obj))
            return True
        need = missing[0]
        where = next((p for p, v in self.places.items() if need in v), None)
        if where is None:
            self.emit(turn, "%s 找不到 %s，目标受阻" % (actor, need))
            st["goal"] = None
            return False
        self.route_to(actor, where, turn)
        guard = next((g for g, o in self.obstacles.items()
                      if o["at"] == where and o["guards"] == need), None)
        if guard:
            if rng.random() < self.odds.get("%s|%s" % (actor, guard), 0.5):
                self.emit(turn, "%s 在 %s 对抗 %s，胜，取得 %s（注意：代价待人工补）"
                          % (actor, where, guard, need))
                st["has"].append(need)
                self.places[where].remove(need)
            else:
                self.emit(turn, "%s 在 %s 被击退，负伤未取得 %s（代价已自动成立）"
                          % (actor, where, need))
            return False
        self.places[where].remove(need)
        st["has"].append(need)
        self.emit(turn, "%s 在 %s 取得 %s" % (actor, where, need))
        return False

    def run(self, seed):
        rng = random.Random(seed)
        for turn in range(1, self.max_turns + 1):
            done = True
            for actor in self.actors:
                st = self.actors[actor]
                if st["goal"]:
                    done = False
                    self.try_goal(actor, turn, rng)
            if done:
                break
        return self.log


def validate(scenario):
    for key in ("places", "actors"):
        if key not in scenario:
            return "场景缺少 %s 键" % key
    for a, v in scenario["actors"].items():
        if len(v.get("goal", [])) != 3:
            return "角色 %s 的 goal 须为 [动词, 目标物, [所需材料]]" % a
        if v["at"] not in scenario["places"]:
            return "角色 %s 的起点 %s 不在 places 中" % (a, v["at"])
    for g, o in scenario.get("obstacles", {}).items():
        if o["at"] not in scenario["places"]:
            return "障碍 %s 的位置 %s 不在 places 中" % (g, o["at"])
    return None


def main():
    ap = argparse.ArgumentParser(description="目标驱动场景模拟（事件候选层，禁止直接进正文）")
    ap.add_argument("--scenario", help="场景 JSON 文件；缺省用内置演示局")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-turns", type=int, default=10)
    args = ap.parse_args()

    if args.scenario:
        with open(args.scenario, "r", encoding="utf-8-sig") as f:
            scenario = json.load(f)
        label = args.scenario
    else:
        scenario = DEMO
        label = "内置演示局"
    err = validate(scenario)
    if err:
        print("场景配置错误：%s" % err)
        return 1

    log = Sim(scenario, args.max_turns).run(args.seed)
    print("目标驱动场景模拟 · %s · seed=%d max-turns=%d（可复现）" % (label, args.seed, args.max_turns))
    print("-" * 52)
    for line in log:
        print("  " + line)
    print("-" * 52)
    print("验收门（18 §三.3）：① 事件链因果闭合 ② 每事件人工补代价与情感动机后才入 02/10")
    print("                      ③ 不得跳过 15 拍定位直接成文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
