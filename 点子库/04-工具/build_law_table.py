# -*- coding: utf-8 -*-
"""生成《法则权能-法则总表.xlsx》"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook()

# ---------- 样式 ----------
HEAD_FILL = PatternFill("solid", fgColor="2F5597")
HEAD_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10)
TITLE_FONT = Font(name="微软雅黑", size=14, bold=True, color="2F5597")
NOTE_FONT = Font(name="微软雅黑", size=10, italic=True, color="666666")
BOLD_FONT = Font(name="微软雅黑", size=10, bold=True)
THIN = Side(style="thin", color="BBBBBB")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")

SHEET_COLORS = {
    "表A-数学逻辑层": "FFF2CC",
    "表B-信息层": "DEEBF7",
    "表C-物理层": "E2EFDA",
    "表D-生命层": "FCE4D6",
    "表E-心理经济层": "EDEDED",
    "表F-社会层": "E4DFEC",
}

LAW_HEADERS = ["法则", "谱层", "五阶链 窥→引→织→改→合", "FP量级", "代价", "克制关系"]

LAW_DATA = {
    "表A-数学逻辑层": [
        ["哥德尔不完备", "数学/逻辑", "找规则裂缝→自指悖论→不可判定域→\"真不可证\"强制生效→系统外真理", "32 FP ⇝ 10⁶ TFP（入门右移3档）", "永远无法自证合法性", "克制一切封闭法域"],
        ["康托尔对角线", "数学/逻辑", "察觉名单之外→对角线逃逸→不可数领域→抬高层级→成为不可数", "16 FP ⇝ 10⁶ TFP（右移2档）", "永远有更高一层，无法登顶", "被\"层级锚定\"类克制"],
        ["停机问题", "数学/逻辑", "预感无果→无限循环牢笼→不可判定区→判定失效→预测永不收敛", "16 FP ⇝ 10⁶ TFP（右移2档）", "自身行动亦无法被预测/规划", "反克：预言、因果类"],
    ],
    "表B-信息层": [
        ["香农信息熵", "信息", "量化不确定性→注入噪声→加密信道/信息茧房→改写信道容量→成为信道", "8 FP ⇝ 10⁶ TFP（改法起FP消耗×社会温度）", "记忆被噪声逐比特侵蚀", "克制一切共识类；被物理类反克"],
        ["（兰道尔极限）", "信息", "——非权能，是代价机制", "每擦除1比特社会信息结算FP", "—", "—"],
    ],
    "表C-物理层": [
        ["万有引力", "物理", "测重→拉拽→重力场→改方向→引力奇点", "0.5 FP ⇝ 10⁶ TFP", "身体渐成奇点", "被契约/权力合法性锁死"],
        ["能量守恒", "物理", "感知能流→抽空动能→能量循环场→挪用记账→成为能量账本", "4 FP ⇝ 10⁶ TFP", "守恒反噬：挪用必在最坏时刻偿还", "无（唯一无解代价的法则）"],
        ["熵增", "物理", "感知混乱→加速热寂→局部秩序→逆熵→时间箭头", "8 FP ⇝ 10⁶ TFP", "自身加速老化", "被内稳态/中心法则对冲"],
        ["牛顿第三定律", "物理", "感知反噬→反弹伤害→转移作用力→设定反作用对象→强制因果反噬", "4 FP ⇝ 10⁶ TFP", "一切作用必反作用于己", "克制：一切直接攻击"],
        ["惯性定律", "物理", "保持动量→消除惯性→赋予/剥夺惯性→静止即永恒", "4 FP ⇝ 10⁶ TFP", "自身动量难改变（固执化）", "与光速/因果视界共鸣"],
        ["最小作用量", "物理", "预判路径→优化行动→改写事件路径→世界走你选的最优解", "16 FP ⇝ 10⁶ TFP", "走不上最优解的路全部废弃", "被墨菲克制（概率偏转针对\"计划\"本身）"],
        ["量子叠加", "物理", "概率直觉→隧穿→叠加分身→选择观测结果→多世界并行", "8 FP ⇝ 10⁶ TFP", "每次坍缩损失一个\"可能的自己\"", "被泡利不相容锁死"],
        ["不确定性原理", "物理", "知无法兼测→制导模糊→测不准域→抬高不确定下限→成为概率云", "8 FP ⇝ 10⁶ TFP", "自身位置/目的永不明确", "克制：一切精密瞄准"],
        ["泡利不相容", "物理", "识别不可叠加→禁止共位/共职→一人一位领域→改写同一性→成为唯一性", "16 FP ⇝ 10⁶ TFP", "绝对孤独（任何同类不得与你相同）", "克制量子叠加"],
        ["光速/因果视界", "物理", "感知钟慢→局部减速→因果视界→改写光锥→成为光锥", "32 FP ⇝ 10⁶ TFP（右移1档）", "与外界时间脱钩→社会法则对其恒定减效", "被共识类环境压制"],
        ["电磁力", "物理", "感知场→放电→操控电磁谱→改写耦合→光/场化身", "4 FP ⇝ 10⁶ TFP", "神经信号与场混淆（感官过载）", "被信息噪声干扰（信号即信息）"],
    ],
    "表D-生命层": [
        ["中心法则", "生命", "读遗传信息→开关性状→可遗传改写→逆转信息流→成为生命模板", "16 FP ⇝ 10⁶ TFP", "复制品都不是你（个体性消解）", "克制：一切不可遗传的强化"],
        ["自然选择", "生命", "看适应度→施加选择压→造选择环境→改写\"适应\"→成为选择压", "32 FP ⇝ 10⁶ TFP", "必须永远被选择，停止适应即消亡", "与马太同构共鸣（代价共享）"],
        ["内稳态", "生命", "读平衡偏离→调节回稳→稳态域→改写平衡点→成为稳态", "8 FP ⇝ 10⁶ TFP", "绝对稳态即死亡（化为雕像）", "对冲熵增；被熵增压制"],
        ["进化稳定策略(ESS)", "生命", "看稳定解→植入扰动→锁定均衡→改写均衡→成为均衡", "16 FP ⇝ 10⁶ TFP", "永远不能变通", "与羊群同构共鸣"],
        ["最优觅食", "生命", "感知收益递减→边际扰动→斑块调度→改写性价比→成为效率", "8 FP ⇝ 10⁶ TFP", "无法容忍低效（见冗余即清除）", "与二八同构共鸣"],
    ],
    "表E-心理经济层": [
        ["损失厌恶", "心理/经济", "看谁在怕失去→放大损失→恐惧场→改写价值曲线→成为\"失去\"", "8 FP ⇝ 10⁶ TFP", "对自身无效（最不识己失）", "克制：财富/交换类"],
        ["认知失调", "心理/经济", "察觉信念裂缝→制造不适→自我说服网→改写一致性需求→成为自洽引力", "16 FP ⇝ 10⁶ TFP", "自身信念必须永恒自洽（无法悔改）", "反克：哥德尔（悖论即裂缝）"],
        ["锚定效应", "心理/经济", "看第一印象→植入锚点→锚定场→改写参照系→成为标准", "4 FP ⇝ 10⁶ TFP", "自身只按首个锚点认知世界", "与手表定律共鸣"],
        ["供需法则", "心理/经济", "看价格信号→边际扰动→构建市场→改写弹性→成为市场", "8 FP ⇝ 10⁶ TFP", "一切获得皆标价（含情感）", "与交换/二八共鸣"],
        ["格雷欣法则", "心理/经济", "察觉劣币化→推动劣币→良币退出→改写价值判据→成为贬值", "8 FP ⇝ 10⁶ TFP", "自身价值持续缓慢流失", "被信任法则对冲；与熵增同构共鸣"],
    ],
    "表F-社会层": [
        ["信任", "社会", "辨谎→建立信任→信任网络→重写背叛成本→成为共识", "0.5 FP ⇝ 10⁶ TFP", "共识化：失去个人好恶", "对冲格雷欣；被信息噪声反克"],
        ["权力", "社会", "看结构→威慑→联盟→重写合法性→言出法随", "0.5 FP ⇝ 10⁶ TFP", "只能以\"角色\"存在", "克制个体物理高阶者"],
        ["交换", "社会", "看价值流→促成交易→债务网→改写等价→资源再分配", "0.5 FP ⇝ 10⁶ TFP", "万物皆可计价（不可无偿）", "被损失厌恶克制"],
        ["契约", "社会", "看违约→口头约束→自动执行→条款重写→因果契约", "0.5 FP ⇝ 10⁶ TFP", "自身被一切承诺锁死", "克制物理高阶；被改法物理撕毁"],
        ["法律", "社会", "找漏洞→程序正义→判例影响→立法→言出法随(辖内)", "4 FP ⇝ 10⁶ TFP", "永远活在自己立的法下", "被哥德尔克制（系统必有不可证漏洞）"],
        ["羊群/从众", "社会", "感知情绪→引导转向→流行趋势→改写从众方向→成为领头羊", "0.5 FP ⇝ 10⁶ TFP", "失去独立判断", "与ESS同构共鸣"],
        ["破窗", "社会", "感知失序→引发连锁→修复/制造→定义文明边界→秩序化身", "0.5 FP ⇝ 10⁶ TFP", "眼中永有破窗（强迫修补/破坏）", "与内稳态对冲"],
        ["马太效应", "社会", "看累积优势→添一点→富者愈富回路→改写累积速率→成为累积", "4 FP ⇝ 10⁶ TFP", "弱者境遇感同身受（反向侵蚀）", "与自然选择同构共鸣"],
        ["木桶定律", "社会", "找短板→压长板→短板组织→改写短板规则→成为短板", "4 FP ⇝ 10⁶ TFP", "团队上限永远=你的水平", "被二八对冲"],
        ["彼得原理", "社会", "看错位→推动晋升→不胜任堆积→改写晋升判据→成为顶点", "4 FP ⇝ 10⁶ TFP", "永处不胜任之位", "被权力法则对冲"],
        ["手表定律", "社会", "察觉多标准→植入第二把尺→标准战争→改写唯一标准→成为标准", "4 FP ⇝ 10⁶ TFP", "自身认知里永存两把尺", "与锚定共鸣"],
        ["墨菲定律", "社会", "预感风险→概率偏转→坏事必然→改写可能性→厄运化身", "8 FP ⇝ 10⁶ TFP", "幸运永远绕开你", "克制一切精密计划（含最小作用量）"],
        ["二八定律", "社会", "找关键20%→资源集中→重分配→让少数决定多数→成为关键少数", "4 FP ⇝ 10⁶ TFP", "80%的自己沦为次要", "与最优觅食同构共鸣"],
        ["帕金森定律", "社会", "感知官僚膨胀→压缩/加速流程→重构组织时间→工作填满时间→时间本身", "4 FP ⇝ 10⁶ TFP", "自身时间永远被任务填满", "与惯性共鸣"],
        ["互惠法则", "社会", "感知亏欠→强制回报→互惠网络→善意即债务→人情本体", "0.5 FP ⇝ 10⁶ TFP", "收受即负债，无法白得", "与契约共鸣；被交换改写"],
    ],
}

WIDTHS = [16, 10, 52, 30, 30, 30]


def write_table(ws, title, rows, start_row=1):
    ws.cell(row=start_row, column=1, value=title).font = TITLE_FONT
    r = start_row + 1
    for c, h in enumerate(LAW_HEADERS, 1):
        cell = ws.cell(row=r, column=c, value=h)
        cell.font = HEAD_FONT
        cell.fill = HEAD_FILL
        cell.alignment = CENTER
        cell.border = BORDER
    r += 1
    for row in rows:
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.font = BOLD_FONT if c == 1 else BODY_FONT
            cell.alignment = WRAP
            cell.border = BORDER
        r += 1
    return r + 1


# ---------- Sheet 1：总表（全部法则合并在一页，便于筛选） ----------
ws = wb.active
ws.title = "总表"
ws.cell(row=1, column=1, value="法则权能体系 · 法则总表").font = Font(name="微软雅黑", size=16, bold=True, color="2F5597")
note = ('量级标注：起点 ⇝ 天花板（取子阶中值）。标准曲线：窥初0.5FP → 引中4–32KFP → 织中8–32MFP → 改中10–100GFP → 合高10⁴–10⁶TFP。'
        'Ω＝不可度量（边界级专属，任何法则的合法者都到不了）。五阶：窥法→引法→织法→改法→合法。')
ws.cell(row=2, column=1, value=note).font = NOTE_FONT
ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=6)
ws.row_dimensions[2].height = 42
ws.cell(row=2, column=1).alignment = WRAP

r = 4
for c, h in enumerate(LAW_HEADERS, 1):
    cell = ws.cell(row=r, column=c, value=h)
    cell.font = HEAD_FONT
    cell.fill = HEAD_FILL
    cell.alignment = CENTER
    cell.border = BORDER
r += 1
all_rows = [row for rows in LAW_DATA.values() for row in rows]
for row in all_rows:
    for c, v in enumerate(row, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = BOLD_FONT if c == 1 else BODY_FONT
        cell.alignment = WRAP
        cell.border = BORDER
    r += 1
for i, w in enumerate(WIDTHS, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A5"
ws.auto_filter.ref = f"A4:F{r-1}"

# ---------- 分层 Sheet ----------
for name, rows in LAW_DATA.items():
    ws = wb.create_sheet(name)
    start = write_table(ws, name, rows)
    # 附注
    for i, w in enumerate(WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if name == "表F-社会层":
        ws.cell(row=start, column=1, value="注：社会层起点最低，天花板受网络密度调制 ×0.1–×10（孤立 −3~−5 档，密集 +3~+5 档）。").font = NOTE_FONT

# ---------- Sheet：附注与共鸣对 ----------
ws = wb.create_sheet("附注-共鸣对")
ws.cell(row=1, column=1, value="附注 · 同构共鸣对与量级规则").font = TITLE_FONT
notes = [
    "1. 同构共鸣对（成对掌握时代价共享、效果叠加）——全谱系仅有的六对安全双法则组合：",
    "    ① 自然选择 ↔ 马太效应",
    "    ② 进化稳定策略(ESS) ↔ 羊群效应",
    "    ③ 最优觅食 ↔ 二八定律",
    "    ④ 熵增 ↔ 格雷欣法则",
    "    ⑤ 锚定效应 ↔ 手表定律",
    "    ⑥ 互惠法则 ↔ 契约",
    "2. 任何法则的\"合法\"天花板都是 10⁶ TFP，不存在 Ω；Ω 只属于边界级（神上神力/创造主）。",
    "3. 物理侧量级为线性叠加；社会侧量级须乘网络密度系数（孤立 −3~−5 档，密集 +3~+5 档）。",
    "4. 单位换算：1 FP = 1 个标准现实世界普通成年人 ≈ CR 1/16；1 宅男 = 0.5 鹅 = 0.5 FP；1 鹅 = 1 FP；",
    "   1 KFP = 10³ FP；1 MFP = 10⁶ FP；1 GFP = 10⁹ FP；1 TFP = 10¹² FP。",
]
for i, t in enumerate(notes, 3):
    ws.cell(row=i, column=1, value=t).font = BODY_FONT
ws.column_dimensions["A"].width = 100

# ---------- Sheet：五阶对照标尺 ----------
ws = wb.create_sheet("五阶-CR-FP对照")
headers = ["阶位", "子阶", "D&D CR/神力", "FP量级", "关键特征"]
data = [
    ["窥法", "初", "CR 1/8–1/4", "0.5–4 FP", "模糊感知"],
    ["窥法", "中", "CR 1/2–1", "8–16 FP", "法则类型识别"],
    ["窥法", "高", "CR 2–5", "32–256 FP", "定量感知+临界感知"],
    ["引法", "初", "CR 3–6", "256 FP–4 KFP", "小范围瞬时影响"],
    ["引法", "中", "CR 6–10", "4–32 KFP", "中范围短时影响"],
    ["引法", "高", "CR 10–15", "32 KFP–1 MFP", "接近织法门槛"],
    ["织法", "初", "CR 15–18", "1–8 MFP", "自维持小结构"],
    ["织法", "中", "CR 18–21", "8–32 MFP", "中等结构+相变放大"],
    ["织法", "高", "CR 21–25", "32 MFP–1 GFP", "跨越 τ*=0.68"],
    ["改法", "初", "CR 25–28", "1–10 GFP", "局部参数改写"],
    ["改法", "中", "CR 28–30", "10–100 GFP", "多参数协同改写"],
    ["改法", "高", "CR 30+", "100 GFP–1 TFP", "触及边界条件"],
    ["合法", "初", "神力 1–5", "1–100 TFP", "法则节点"],
    ["合法", "中", "神力 6–15", "100–10⁴ TFP", "法则区域中心"],
    ["合法", "高", "神力 16–20", "10⁴–10⁶ TFP", "法则具身化"],
    ["合法", "极", "无", "不可换算", "合法者不能达到神上神力"],
    ["边界之外", "—", "神力 21+", "Ω（不可度量）", "创造主/艾欧"],
]
ws.cell(row=1, column=1, value="五阶 × D&D CR × FP量级 对照表").font = TITLE_FONT
for c, h in enumerate(headers, 1):
    cell = ws.cell(row=3, column=c, value=h)
    cell.font = HEAD_FONT
    cell.fill = HEAD_FILL
    cell.alignment = CENTER
    cell.border = BORDER
for i, row in enumerate(data, 4):
    for c, v in enumerate(row, 1):
        cell = ws.cell(row=i, column=c, value=v)
        cell.font = BOLD_FONT if c == 1 else BODY_FONT
        cell.alignment = WRAP
        cell.border = BORDER
for i, w in enumerate([12, 8, 16, 22, 32], 1):
    ws.column_dimensions[get_column_letter(i)].width = w

out = "/sandbox/workspace/output/法则权能-法则总表.xlsx"
wb.save(out)
print("saved:", out)
