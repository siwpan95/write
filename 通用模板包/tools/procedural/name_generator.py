#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命名工厂 · name_generator.py（v3.18.4，随包脚本）
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

# 词表辅助：空格分词。
# v3.18.4 扩容说明：person 的 name_head / name_tail **仍是单字**
# （_make 的槽位拆解按 given[0]/given[1:] 切片，词组会拆错位）；
# 其余槽位（姓/机构/地名/兽/器物）改为词组池 —— 搜索到的意象词多为多音节，
# 且这些槽位的 breakdown 直接打印整串，不受切片影响。
def words(s):
    return s.split()


# 字素库：键 = 槽位，值 = 候选字/词。新增流派时在此扩库（加一个 profile），不改算法。
#
# v3.18.4 扩容（2026-11-21）：两套 profile 的全部 12 槽位均扩大候选池。
# 素材来自联网检索，逐条登记于 通用模板包/14-外部依赖与来源登记表.md §十二
# （S-11~S-14，含访问日期与级别）。**只扩候选池，不改 _make / generate 算法，
# 不增删 profile**。扩库后同 seed 输出会变化，属预期（非回归）。
LEXICON_XUANHUAN = {
    # 姓：单姓 + 复姓（复姓是仙侠辨识度的重要来源）。
    # 原版把「百里/东方」用 list() 拆成单字 —— 本次改 words() 后正确保留。
    "surname": words(
        "李 王 张 刘 陈 杨 赵 黄 周 吴 萧 秦 楚 燕 韩 墨 洛 苏 叶 云 风 林 百里 东方 "
        "徐 孙 马 朱 胡 郭 何 高 罗 郑 梁 谢 宋 唐 许 邓 冯 曹 彭 曾 董 袁 蔡 蒋 余 "
        "杜 程 魏 吕 丁 任 沈 姚 卢 钟 姜 崔 谭 廖 范 汪 陆 金 石 戴 贾 韦 夏 邱 侯 "
        "邹 熊 孟 白 江 闫 薛 尹 雷 黎 史 陶 贺 毛 郝 顾 龚 邵 万 段 严 武 康 孔 汤 牧 施 "
        "上官 欧阳 司马 慕容 诸葛 夏侯 皇甫 尉迟 长孙 宇文 轩辕 令狐 澹台 公孙 "
        "南宫 西门 司徒 司空 独孤 东郭 南门 呼延 羊舌 微生 梁丘 左丘 东门 北堂"
    ),
    # 名头/名尾保持**单字**（见文件头说明）；取自仙侠意象字与网文高频收尾字池。
    "name_head": words(
        "云 风 雪 月 星 辰 天 玄 荒 废 烬 焰 霜 雷 砂 锈 骨 铁 血 刃 "
        "凌 尘 霄 渊 逸 墨 羽 澈 虚 冥 傲 冷 寒 青 凡 宁 默 宣 轩 沉 断 归 "
        "苍 紫 赤 珩 朔 戈 白 清 寂 幽 微 澜 琼 瑶 空 灵"
    ),
    "name_tail": words(
        "轩 澜 歌 行 舟 野 辰 溪 灼 原 折 遥 辞 "
        "白 朔 岳 戈 烬 宁 秋 棠 微 绾 鸢 禾 瑶 澄 珩 影 韵 曦 灵 萱 芷 璃 卿 真 君 寒 尘"
    ),
    # 机构头：意象词（天象/地理/哲学/虚实四系）+ 原单字。
    "sect_prefix": words(
        "金 木 水 火 土 日 月 星 玄 天 剑 云 雷 灰 烬 锈 蚀 残 "
        "九霄 星陨 月蚀 烈阳 紫微 天雷 璇玑 荧惑 太阴 青冥 赤霄 白虹 玄霜 黄泉 碧落 "
        "青云 丹霞 万剑 焚天 寒冰 苍梧 沉星 断岳 归墟 无极 太虚 两仪 三才 四象 五行 "
        "六合 七杀 八卦 九宫 十方 无相 无念 绝情 忘忧 听雪 摘星 问道 铸剑 天机 御兽 "
        "血煞 万毒 天工 符箓 天衍 神意 风清 灵兽 神农 玄阴 天师 云烟 仙霞 天心 "
        "玉女 飘渺 天道 凌云 诛神 天煞 潜龙 龙虎 剑侍 灵剑 照阳 黄枫 万妖 落日 "
        "寒风 碧云 灵宝 紫金 凤仪 赤血 浩天 镇魔 天策 衔月 归一 玄武 无心 鉴宝 天涯"
    ),
    "sect_suffix": words(
        "宗 门 派 阁 殿 山 庄 谷 宫 会 盟 司 教 坊 堂 塔 轩 府 观 洞 院 寺 城 楼 窟 垒 台 阙"
    ),
    # 地名头：地理意象词（方位+地貌 / 意象+域 / 据点）。
    # ⚠️ 只用**虚构意象组合**，不直接取真实山脉、河流、省份、景点名（来源 S-14 红线）。
    "place_head": words(
        "坠星 裂谷 锈原 霜井 烬海 灰崖 白垩 荒墟 残碑 风蚀 "
        "临川 望海 雁回 渡云 青梧 霜落 赤沙 幽澜 东陆 西荒 南泽 北原 中州 无尽 乱石 "
        "九霄 归墟 苍梧 蓬莱 瀛洲 方丈 青要 赤水 白帝 黑石 朱雀 玄武 青龙 白虎 "
        "黄泉 断魂 绝情 无妄 昆仑 星陨 月蚀 烈阳 紫微 天雷 璇玑 荧惑 太阴 青冥 "
        "赤霄 白虹 玄霜 碧落 焚天 沉星 断岳 葬剑 叩天"
    ),
    "place_tail": words(
        "原 谷 海 崖 城 关 镇 渡 驿 林 泽 墟 台 津 坊 川 域 岛 山 岭 峡 渊 宫 寺 观 洞 庄"
    ),
    "beast_head": words(
        "霜 焰 灰 骨 纹 眼 棘 鳞 裂 齿 蚀 影 鸦 血 沙 行 "
        "玄冥 赤练 青羽 幽寒 苍墨 夜影 铁铜 石枯 朽毒 瘴煞 魇魅 妖魔 寒霜 烈焰 "
        "灰烬 枯骨 血影 沙行"
    ),
    "beast_core": words(
        "狼 蛟 蟒 鸦 蜥 蛛 隼 犀 鹿 蜴 虎 豹 熊 雕 鸢 蛇 鼍 龟 鹤 狐 狸 猿 罴 "
        "鲲 鹏 凰 麒 麟 饕餮 穷奇 梼杌 混沌"
    ),
    "beast_tail": words("兽 王 母 群 幼 头 子 爷 君 主 将 后"),
    # 器物头：材质+功效词组（原版 list() 把「碎星/焚天」拆成单字，本次保留整词）。
    "artifact_head": words(
        "碎星 焚天 引雷 缚魂 渡厄 寒渊 衔烛 紫金 青莲 碧落 飞鸿 紫电 寂灭 无垠 "
        "太阿 纯钧 湛卢 赤霄 龙渊 血饮 噬魂 黄泉 骨殇 怨离 青索 紫郢 南明 天河 "
        "菩提 金刚 须弥 乾坤 星河 九霄 璇玑 玄铁 天蚕 龙鳞 凤凰 麒麟"
    ),
    "artifact_tail": words(
        "剑 戟 钟 镜 灯 匣 环 碑 链 笛 葫芦 丹 珠 靴 鞭 符 刀 枪 弓 琴 伞 甲 衣 "
        "铠 戒 佩 簪 钗 坠 杵 杖 扇 印 铃 鼎 幡"
    ),
}

# 现实向 profile（v3.12.1 经点子库《法则权能》实践反哺增设；v3.18.4 扩容）：
# person=常见真实姓名；sect=基层机构；place=街巷/小区；beast=市井绰号；artifact=日常旧物。
# 实践教训：现实向的"头槽位"必须用**词组**而非单字组合（单字组合会产出"国水""厂路"类断词）；
# 故全部用 words()。person 的 name_head/name_tail 仍是单字（拆解口径同上）。
LEXICON_REALITY = {
    "surname": words(
        "李 王 张 刘 陈 杨 赵 黄 周 吴 郑 冯 蒋 沈 韩 朱 秦 许 何 吕 施 孔 曹 严 "
        "徐 孙 马 胡 郭 高 罗 梁 谢 宋 唐 邓 彭 曾 董 袁 蔡 余 杜 程 魏 丁 任 卢 "
        "钟 姜 崔 谭 陆 范 汪 石 金 戴 贾 韦 夏 邱 侯 邹 熊 孟 白 江 闫 薛 尹 雷 "
        "黎 史 陶 贺 毛 顾 龚 邵 万 段 武 康 汤"
    ),
    "name_head": words(
        "建 志 国 文 秀 英 桂 兰 明 磊 强 静 燕 雪 梅 海 江 永 清 雨 桐 若 "
        "伟 芳 娜 敏 慧 丽 华 平 刚 健 世 玉 立 德 春 秋 小 大 中 心 爱 凤 龙 飞 莉"
    ),
    "name_tail": words(
        "平 军 华 明 芳 红 梅 林 生 祥 斌 慧 婷 晨 宇 泽 安 然 "
        "国 建 强 莉 萍 娟 涛 超 波 辉 鹏 玲 珍 凤 鑫 淼 森 焱 霞 云 燕"
    ),
    "sect_prefix": words(
        "城南 江北 市桥 桥东 永安 定国 光明 朝阳 胜利 红星 工农 团结 "
        "城东 城西 新村 老街 河东 河西 铁路 供电 供水 环卫 税务 工商 邮政 电信 "
        "街道 社区 居委会 村委会 向阳 红旗 东风 解放"
    ),
    "sect_suffix": words(
        "派出所 水管站 供电所 储蓄所 废品站 夜校 托儿所 门诊部 校对室 广播站 "
        "居委会 村委会 工作站 服务所 管理所 办公室 分局 大队 中队 银行 邮局 学校"
    ),
    "place_head": words(
        "永安 朝阳 向荣 临江 纺织 机务 铁路 老教工 印刷厂 河埠 "
        "老城 东关 西关 南门 北门 河堤 桥头 巷口 菜场 车站 码头 仓库 操场 礼堂 "
        "邮电 新华 向阳 红旗 东风 解放"
    ),
    "place_tail": words(
        "巷 路 弄 街 小区 家属院 里 宿舍 新村 胡同 大院 楼 排 栋 号 条 里弄 院 区 街坊"
    ),
    "beast_head": words(
        "哑巴 瘸子 老抠 夜猫子 算盘 影子 快嘴 "
        "老张 老王 小李 阿黄 大头 二狗 三愣 四眼 王麻子 张铁嘴 老烟枪 酒鬼 "
        "半仙 算命的 打铁的 卖菜的"
    ),
    "beast_core": words(
        "张 李 王 陈 赵 孙 钱 周 吴 郑 冯 蒋 沈 韩 杨 朱 秦 尤 许"
    ),
    "beast_tail": words("头 子 爷 儿 鬼 精 货 种"),
    "artifact_head": words(
        "铁皮 牛皮 漆面 黄铜 搪瓷 红木 上弦 掉漆 "
        "铝制 塑料 竹编 藤编 玻璃 陶瓷 木质 铸铁 老式 旧式 怀表 座钟 手摇 发条"
    ),
    "artifact_tail": words(
        "盒 锁 票 本 钟 壶 灯 尺 夹 罐 缸 碗 盆 锅 勺 剪 针 线 绳 布 包 袋 箱 "
        "柜 桌 椅 凳 扇 镜 表 铃 哨"
    ),
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
