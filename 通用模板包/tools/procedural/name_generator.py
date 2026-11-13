#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命名工厂 · name_generator.py（v3.12，随包脚本）
--------------------------------------------------------------------------
对应模板：18-程序化创作与算法脚本模板.md §三.1（第 2 代：音节文法 + 去重）
用途：批量生成玄幻/废土风格的备选专名（人名/势力/地名/怪物/功法），供
      03 世界观圣经、04 人物卡、13 区域包 的素材层使用。
纪律：只产素材、不产正文；产出必须逐条人工过审并与其他文件查重后才能编号入库。

用法：
  python tools/procedural/name_generator.py --kind person --n 10 --seed 42
  python tools/procedural/name_generator.py --kind beast  --n 5  --seed 7
  python tools/procedural/name_generator.py --demo        # 演示各类型样例
参数：
  --kind  person|sect|place|beast|artifact（默认 person）
  --n     生成数量（默认 10）
  --seed  随机种子；同种子同结果（可复现性要求，见 18 §五 第 3 步）
退出码：0 成功。
"""
import argparse
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 字素库：键 = 槽位，值 = 候选字。新增流派时在此扩库（加一个 profile），不改算法。
LEXICON_XUANHUAN = {
    "surname": list("李王张刘陈杨赵黄周吴萧秦楚燕韩墨洛苏叶云风林百里东方"),
    "name_head": list("云风雪月星辰天玄荒废烬焰霜雷砂锈骨铁血刃"),
    "name_tail": list("轩澜歌行舟野辰溪灼原折遥辞"),
    "sect_prefix": list("金木水火土日月星玄天剑云雷灰烬锈蚀残"),
    "sect_suffix": list("宗门派阁殿山庄谷宫会盟司"),
    "place_head": list("坠星裂谷锈原霜井烬海灰崖白垩荒墟残碑风蚀"),
    "place_tail": list("原谷海崖城关镇渡驿林泽墟台"),
    "beast_head": list("霜焰灰骨纹眼棘鳞裂齿蚀影鸦血沙行"),
    "beast_core": list("狼蛟蟒鸦蜥蛛隼犀鹿蜴"),
    "beast_tail": list("兽王母群幼"),
    "artifact_head": list("碎星焚天引雷缚魂渡厄寒渊衔烛"),
    "artifact_tail": list("剑戟钟镜灯匣环碑链笛"),
}

# 现实向 profile（v3.12.1 经点子库《法则权能》实践反哺增设）：
# person=常见真实姓名；sect=基层机构；place=街巷/小区；beast=市井绰号；artifact=日常旧物。
# 实践教训：现实向的"头槽位"必须用**词组**而非单字组合（单字组合会产出"国水""厂路"类断词）；
# 修正用 words() 而非 list(字符串)。
def words(s):
    return s.split()

LEXICON_REALITY = {
    "surname": list("李王张刘陈杨赵黄周吴郑冯蒋沈韩杨朱秦许何吕施孔曹严"),
    "name_head": list("建志国文秀英桂兰明磊强静燕雪梅海江永清雨桐若"),
    "name_tail": list("平军华明芳红梅林生祥斌慧婷晨宇泽安然"),
    "sect_prefix": words("城南 江北 市桥 桥东 永安 定国 光明 朝阳 胜利 红星 工农 团结"),
    "sect_suffix": words("派出所 水管站 供电所 储蓄所 废品站 夜校 托儿所 门诊部 校对室 广播站"),
    "place_head": words("永安 朝阳 向荣 临江 纺织 机务 铁路 老教工 印刷厂 河埠"),
    "place_tail": words("巷 路 弄 街 小区 家属院 里 宿舍 新村"),
    "beast_head": words("哑巴 瘸子 老抠 夜猫子 算盘 影子 快嘴"),
    "beast_core": list("张李王陈赵孙钱周"),
    "beast_tail": words("头 子 爷"),
    "artifact_head": words("铁皮 牛皮 漆面 黄铜 搪瓷 红木 上弦 掉漆"),
    "artifact_tail": words("盒 锁 票 本 钟 壶 灯 尺 夹"),
}

PROFILES = {"xuanhuan": LEXICON_XUANHUAN, "reality": LEXICON_REALITY}

# 语义冲突黑名单：字素组合可能产生歧义或平台风险词，命中即重抽。
BLACKLIST = (" administrative", "涩", "政")


def _make(kind, rng, lex):
    """返回 (名字, 槽位拆解)——拆解供人工过审时定向改字（v3.12.2 实践反哺）。"""
    if kind == "person":
        surname = rng.choice(lex["surname"])
        given = rng.choice(lex["name_head"]) + rng.choice(lex["name_tail"])
        if rng.random() < 0.25:                     # 少数单名
            given = rng.choice(lex["name_head"])
            return surname + given, "姓=%s 单名=%s" % (surname, given)
        return surname + given, "姓=%s 名头=%s 名尾=%s" % (surname, given[0], given[1:])
    if kind == "sect":
        head, tail = rng.choice(lex["sect_prefix"]), rng.choice(lex["sect_suffix"])
        return head + tail, "机构头=%s 机构尾=%s" % (head, tail)
    if kind == "place":
        head, tail = rng.choice(lex["place_head"]), rng.choice(lex["place_tail"])
        return head + tail, "地名头=%s 地名尾=%s" % (head, tail)
    if kind == "beast":
        head, core = rng.choice(lex["beast_head"]), rng.choice(lex["beast_core"])
        core_out = core
        note = "绰号头=%s 核心=%s" % (head, core)
        if rng.random() < 0.4:
            tail = rng.choice(lex["beast_tail"])
            core_out += tail
            note += " 尾缀=%s" % tail
        return head + core_out, note
    if kind == "artifact":
        head, tail = rng.choice(lex["artifact_head"]), rng.choice(lex["artifact_tail"])
        return head + tail, "物件头=%s 物件尾=%s" % (head, tail)
    raise ValueError("未知类型：%s" % kind)


def generate(kind, n, seed, profile="xuanhuan"):
    """生成 n 个不重样的名字；返回 [(名字, 构造说明)]。固定种子可复现。"""
    lex = PROFILES[profile]
    rng = random.Random(seed)
    seen, out = set(), []
    guard = 0
    while len(out) < n and guard < n * 200:
        guard += 1
        name, breakdown = _make(kind, rng, lex)
        if name in seen:
            continue
        if any(b in name for b in BLACKLIST):
            continue
        seen.add(name)
        out.append((name, breakdown))
    if len(out) < n:
        print("  [警告] 字素库组合不足：仅产出 %d/%d，请扩 LEXICON" % (len(out), n))
    return out


def main():
    ap = argparse.ArgumentParser(description="命名工厂（素材层，禁止直接进正文）")
    ap.add_argument("--kind", default="person",
                    choices=["person", "sect", "place", "beast", "artifact"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--profile", default="xuanhuan", choices=sorted(PROFILES),
                    help="字素库风格：xuanhuan=玄幻向，reality=现实向（市井/机构/旧物）")
    ap.add_argument("--demo", action="store_true", help="各类型各出 3 个演示")
    args = ap.parse_args()

    if args.demo:
        for k in ("person", "sect", "place", "beast", "artifact"):
            names = generate(k, 3, args.seed, args.profile)
            print("[%s] %s" % (k, "、".join(n for n, _ in names)))
        print("\n提示：加 --kind/--n/--seed/--profile 定向生成；产出须人工过审并查重（18 §三.1）。")
        return 0

    names = generate(args.kind, args.n, args.seed, args.profile)
    print("命名工厂 · kind=%s n=%d seed=%d profile=%s（可复现）" % (args.kind, args.n, args.seed, args.profile))
    for name, note in names:
        print("  %-10s %s" % (name, note))
    print("\n验收门（18 §三.1）：重名率 0 / 抽 10 个人工判读违和≤1 / 与 03·04 专名查重 / 歧义黑名单过滤。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
