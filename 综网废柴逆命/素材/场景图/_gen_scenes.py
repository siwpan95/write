# -*- coding: utf-8 -*-
"""
《综网·废柴逆命》场景平面图生成器
输出：DXF（R12 ASCII，零依赖，任何 CAD 可打开）+ SVG + HTML 预览
单位：毫米（1 图形单位 = 1 mm）
"""
import os, math, html

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------- 图层（名称, ACI 颜色号） ----------
LAYERS = [
    ("FRAME",  8),   # 图框
    ("WALL",   7),   # 墙体 / 边界
    ("FURN",   3),   # 家具 / 设施
    ("FIX",    1),   # 关键固定物
    ("CIR",    5),   # 圆形要素
    ("DASH",   4),   # 虚线 / 抽象边界
    ("DIM",    2),   # 尺寸
    ("TEXT",   7),   # 文字
    ("TITLE",  6),   # 标题栏
]

class Plan:
    def __init__(self, key, title, subtitle, note, w, h):
        self.key, self.title, self.subtitle, self.note = key, title, subtitle, note
        self.W, self.H = w, h          # 内容范围
        self.k = max(w, h) / 42000.0             # 几何尺度系数
        self.kt = min(max(self.k, 0.52), 2.2)     # 文字尺度系数（带上下限，防小图字过小）
        self.m = max(1600, min(5000, w * 0.16))   # 图框边距随图幅
        self.ents = []
    # --- 图元 ---
    def ln(self, x1, y1, x2, y2, layer="WALL"):
        self.ents.append(("LINE", layer, (x1, y1, x2, y2)))
    def rc(self, x, y, w, h, layer="WALL"):
        self.ln(x, y, x + w, y, layer); self.ln(x + w, y, x + w, y + h, layer)
        self.ln(x + w, y + h, x, y + h, layer); self.ln(x, y + h, x, y, layer)
    def dash_rect(self, x, y, w, h, layer="DASH", seg=800, gap=500):
        for (ax, ay, bx, by) in [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]:
            L = math.hypot(bx-ax, by-ay); n = max(1, int(L // (seg + gap)))
            ux, uy = (bx-ax)/L, (by-ay)/L
            for i in range(n + 1):
                s = i * (seg + gap)
                if s >= L: break
                e = min(s + seg, L)
                self.ln(ax+ux*s, ay+uy*s, ax+ux*e, ay+uy*e, layer)
    def ci(self, cx, cy, r, layer="CIR"):
        self.ents.append(("CIRCLE", layer, (cx, cy, r)))
    def tx(self, x, y, t, h=420, layer="TEXT", align="C"):
        self.ents.append(("TEXT", layer, (x, y, t, h * self.kt * 1.55)))
    def dim_h(self, x1, x2, y, t):
        e = 180 * self.kt
        self.ln(x1, y-e, x1, y+e, "DIM"); self.ln(x2, y-e, x2, y+e, "DIM")
        self.ln(x1, y, x2, y, "DIM")
        self.tx((x1+x2)/2, y+e*1.7, t, 380, "DIM")
    def dim_v(self, y1, y2, x, t):
        e = 180 * self.kt
        self.ln(x-e, y1, x+e, y1, "DIM"); self.ln(x-e, y2, x+e, y2, "DIM")
        self.ln(x, y1, x, y2, "DIM")
        self.ents.append(("TEXT", "DIM", (x - e*2.2, (y1+y2)/2, t, 380 * self.kt * 1.55)))

# =====================================================================
# 场景 1 · 评定署大厅（第 01 章）
# =====================================================================
def scene_pingdingshu():
    p = Plan("01_评定署大厅", "评定署大厅 · 平面图", "第 01 章｜成年评定日",
             "依据：七百二十人按编号排成十二列，站在三十六块投屏下面；"
             "评定台需迈上三步，脚底有阵纹；门前是公告墙。",
             30000, 18000)
    W, H, T = 30000, 18000, 400
    # 外墙（双线）
    p.rc(0, 0, W, H, "WALL"); p.rc(T, T, W-2*T, H-2*T, "WALL")
    # 投屏墙：36 块 = 12 列 × 3 行
    x0, pw, gp = 1900, 2000, 200
    for i in range(12):
        x = x0 + i*(pw+gp)
        p.rc(x, H-T-1500, pw, 1500, "FIX")
    p.tx(15000, H - T + 1300, "三十六块投屏（12 列 × 3 行）", 420, "TEXT")
    # 评定台 + 三级台阶
    px, py, pw2, ph = 13000, 10800, 4000, 2000
    for k in range(3):
        p.rc(px-400*(3-k), py-400*(3-k), pw2+800*(3-k), ph+800*(3-k), "FURN")
    p.rc(px, py, pw2, ph, "FIX")
    p.ci(px+pw2/2, py+ph/2, 1200, "CIR")          # 阵纹
    p.tx(px + pw2/2 + 5200, py + ph/2, "评定台", 460, "TEXT")
    p.tx(px + pw2/2 + 5200, py + ph/2 - 1400, "三级台阶 · 台面阵纹 φ2400", 340, "FURN")
    # 队列区：12 列
    for c in range(12):
        cx = 2500 + c*2000
        p.ln(cx, 1500, cx, 9200, "FURN")
    p.rc(1700, 1200, 26600, 8300, "DASH")
    p.tx(15000, 650, "队列区：十二列 × 六十排（七百二十人）", 480, "TEXT")
    # 入口
    p.ln(13500, 0, 13500, T, "WALL"); p.ln(16500, 0, 16500, T, "WALL")
    p.tx(15000, -900, "入口（宽 3000）", 440, "TEXT")
    # 公告墙（厅外）
    p.ln(9000, -3500, 21000, -3500, "FIX"); p.ln(9000, -3500, 9000, -2600, "FIX")
    p.ln(15000, -3500, 15000, -2600, "FIX"); p.ln(21000, -3500, 21000, -2600, "FIX")
    p.tx(15000, -4300, "公告墙（三块屏）", 440, "TEXT")
    # 尺寸
    p.dim_h(0, W, -1800, "30000")
    p.dim_v(0, H, W, "18000")
    return p

# =====================================================================
# 场景 2 · 净场（花芯「狱」）
# =====================================================================
def scene_jingchang():
    p = Plan("02_净场", "净场 · 平面图", "第 02 / 09 / 16 章｜花芯「狱」",
             "依据：一片没有边界的灰；地硬、深灰、无回声；灰白雾一层层垒起；"
             "生命值归零即重置至入口；走 400 步回到原点。",
             46000, 46000)
    C = 23000
    # 抽象边界（虚线）
    p.dash_rect(2000, 2000, 42000, 42000, "DASH")
    p.tx(23000, 43600, "可探测边界 —— 走 400 步回到原点（框外仍是同样的灰）", 620, "DASH")
    # 入口 / 重置点
    p.ci(C, C, 800, "CIR"); p.ci(C, C, 300, "CIR")
    p.tx(C, C - 1600, "入口 / 重置点", 520, "TEXT")
    # 灰犬出现位置
    p.ci(C, C + 5200, 600, "FIX")
    p.tx(C, C + 6300, "灰犬出现位置（先攻固定 12 · 攻击间隔 3.2 s）", 460, "TEXT")
    # 第 18 次站位（主动送死处）
    p.ln(C - 3000, C + 1800, C + 3000, C + 1800, "FURN")
    p.tx(C + 4200, C + 1800, "第 18 次站位（主动承受）", 440, "TEXT")
    # 地面刻痕（第 09 / 16 章）
    p.rc(C + 6200, C + 3200, 3000, 400, "FIX")
    p.tx(C + 7700, C + 4200, "地面刻痕（被磨平的编号）", 460, "TEXT")
    # 400 步环形路径
    r = 9000
    for i in range(48):
        a1, a2 = i*7.5, (i+1)*7.5
        x1, y1 = C + r*math.cos(math.radians(a1)), C + r*math.sin(math.radians(a1))
        x2, y2 = C + r*math.cos(math.radians(a2)), C + r*math.sin(math.radians(a2))
        p.ln(x1, y1, x2, y2, "DASH")
    p.tx(C, C - r - 900, "雾墙实测路径（r ≈ 9000）", 440, "DASH")
    p.dim_h(2000, 44000, 900, "42000")
    return p

# =====================================================================
# 场景 3 · 西市地宫
# =====================================================================
def scene_xishi():
    p = Plan("03_西市地宫", "西市地宫 · 平面图", "副本 0273｜阶层一 D+｜第 05–07 章",
             "依据：旧商业街的地下商场废墟，招牌还在、电源断九年、货架泡水、天花板漏水；"
             "照明不足（视觉检定取劣势）、声音放大十倍；通关条件是抵达最底层结算柜。",
             62000, 40000)
    W, H = 62000, 40000
    p.rc(0, 0, W, H, "WALL")
    # 入口铁盖
    p.ci(31000, 37500, 700, "CIR")
    p.tx(31000, 38600, "入口（跳蚤市场摊位下的铁盖）", 500, "TEXT")
    # 主通道
    p.rc(26500, 6000, 9000, 30000, "FURN")
    p.tx(31000, 33000, "主通道（宽 9000）", 480, "FURN")
    # 两侧店铺
    for i in range(5):
        y = 8000 + i*6000
        p.rc(3000, y, 22000, 5000, "FURN")
        p.rc(37000, y, 22000, 5000, "FURN")
    p.tx(14000, 38200, "商铺区（西侧 · 招牌尚存）", 460, "FURN")
    p.tx(48000, 38200, "商铺区（东侧 · 招牌尚存）", 460, "FURN")
    # 积水区（不规则）
    pts = [(24000, 16000), (38000, 15000), (40000, 19500), (36000, 21000), (25000, 20500), (23500, 18000)]
    for i in range(len(pts)):
        x1, y1 = pts[i]; x2, y2 = pts[(i+1) % len(pts)]
        p.ln(x1, y1, x2, y2, "CIR")
    p.tx(31500, 18000, "积水区（水蛭傀儡 · 惧强光）", 460, "CIR")
    # 岔路：更长的那条
    p.ln(26500, 20000, 12000, 20000, "DASH"); p.ln(12000, 20000, 12000, 13000, "DASH")
    p.tx(15000, 20800, "更长的岔路（他算过：最短的路上有水声）", 420, "DASH")
    # 旧商人
    p.rc(9000, 11000, 5000, 2500, "FIX")
    p.tx(11500, 10200, "旧商人（自称姓周 · 困九年 · 误导角色）", 440, "TEXT")
    # 结算柜
    p.rc(29000, 3000, 3000, 2000, "FIX")
    p.tx(30500, 2200, "★ 结算柜（通关目标）", 520, "FIX")
    p.dim_h(0, W, -1400, "62000")
    p.dim_v(0, H, W + 1400, "40000")
    return p

# =====================================================================
# 场景 4 · 九号站台
# =====================================================================
def scene_jiuhao():
    p = Plan("04_九号站台", "九号站台 · 平面图", "副本 0900｜阶层二 C｜第 14 / 17 章",
             "依据：还在运转的地铁站；列车每 7 分钟进站一次，每进站一次难度升一档；"
             "站台有一台可改写的公告屏（每次只能改一条）；守卫目标＝九名乘客。",
             86000, 20000)
    W, PLAT, TRACK = 80000, 12000, 5000
    # 站台
    p.rc(0, 0, W, PLAT, "WALL")
    # 轨道
    p.rc(0, PLAT, W, TRACK, "FURN")
    p.tx(40000, PLAT + TRACK/2, "轨道区（列车每 7 分钟进站一次）", 620, "FURN")
    for x in range(4000, W, 12000):
        p.ln(x, PLAT + 800, x + 4000, PLAT + TRACK - 800, "FURN")
    # 九个乘客位
    for i in range(9):
        x = 8000 + i*8500
        p.ci(x, 6000, 900, "FIX")
        p.tx(x, 6000, "P%d" % (i + 1), 500, "FIX")
    p.tx(40000, 3400, "九名乘客位（守卫目标 · 五名以上死亡即失败）", 520, "TEXT")
    # 公告屏
    p.rc(36000, PLAT - 700, 8000, 700, "FIX")
    p.tx(40000, 10200, "★ 可改写公告屏（每次只能改一条）", 520, "FIX")
    # 楼梯出口
    p.rc(2000, 0, 5000, 2500, "FURN")
    p.tx(4500, -1600, "楼梯 / 出口", 460, "TEXT")
    # 列车进站方向
    p.ln(74000, 14500, 80000, 14500, "DIM"); p.ln(80000, 14500, 79000, 15500, "DIM")
    p.ln(80000, 14500, 79000, 13500, "DIM")
    p.tx(70000, 16200, "列车进站方向", 460, "DIM")
    p.tx(40000, 8000, "末班车到站后十分钟 ＝ 真实世界（死亡不可逆）", 500, "DASH")
    p.dim_h(0, W, -2200, "80000")
    return p

# =====================================================================
# 场景 5 · 陆沉的家
# =====================================================================
def scene_home():
    p = Plan("05_陆沉的家", "陆沉的家 · 平面图", "第 03 / 04 / 15 章",
             "依据：灰水泥公寓；有厨房（煮面、切葱花）、一张妹妹写作业的桌子；"
             "全书唯一有温度的空间；第 15 章他在序列营的硬板床上把那张纸拿出来看了很久。",
             9000, 7000)
    W, H, T = 8000, 6000, 240
    p.rc(0, 0, W, H, "WALL"); p.rc(T, T, W-2*T, H-2*T, "WALL")
    # 门
    p.ln(3400, 0, 3400, T, "WALL"); p.ln(4300, 0, 4300, T, "WALL")
    p.tx(3850, -700, "门 900", 380, "TEXT")
    # 窗
    p.ln(0, 4200, T, 4200, "WALL"); p.ln(0, 5700, T, 5700, "WALL")
    p.tx(1600, 7150, "窗 1500", 400, "TEXT")
    # 厨房
    p.rc(T, 3600, 2400, 2400-T, "FURN")
    p.rc(500, 4200, 1600, 800, "FIX")
    p.tx(1320, 5350, "厨房 · 灶台", 400, "FURN")
    p.tx(1320, 3150, "（煮面的地方）", 340, "FURN")
    # 桌
    p.rc(4600, 2600, 1200, 800, "FIX")
    p.tx(5200, 2150, "桌（妹妹写作业）", 380, "TEXT")
    # 床
    p.rc(4400, 700, 2000, 1500, "FURN")
    p.tx(5400, 1450, "床", 400, "FURN")
    # 五条规则的纸
    p.ci(1900, 1400, 500, "FIX"); p.tx(1900, 700, "五条规则的纸", 360, "FIX")
    p.dim_h(0, W, -1800, "8000")
    p.dim_v(0, H, -1200, "6000")
    return p

SCENES = [scene_pingdingshu, scene_jingchang, scene_xishi, scene_jiuhao, scene_home]

# =====================================================================
# DXF（R12 ASCII，GBK 编码）
# =====================================================================
def write_dxf(path, p):
    L = []
    def a(c, v): L.append(str(c)); L.append(str(v))
    a(0,"SECTION"); a(2,"HEADER")
    a(9,"$ACADVER"); a(1,"AC1009")
    a(9,"$DWGCODEPAGE"); a(3,"ANSI_936")
    a(9,"$EXTMIN"); a(10,0); a(20,0); a(30,0)
    a(9,"$EXTMAX"); a(10,p.W+20000); a(20,p.H+12000); a(30,0)
    a(0,"ENDSEC")
    a(0,"SECTION"); a(2,"TABLES")
    a(0,"TABLE"); a(2,"LAYER"); a(70,len(LAYERS))
    for nm, col in LAYERS:
        a(0,"LAYER"); a(2,nm); a(70,0); a(62,col); a(6,"CONTINUOUS")
    a(0,"ENDTAB")
    # 文字样式：指向系统自带黑体，保证中文不显示为问号
    a(0,"TABLE"); a(2,"STYLE"); a(70,1)
    a(0,"STYLE"); a(2,"HZ"); a(70,0); a(40,0.0); a(41,1.0); a(50,0.0)
    a(71,0); a(42,1.0); a(3,"simhei.ttf"); a(4,"")
    a(0,"ENDTAB")
    a(0,"ENDSEC")
    a(0,"SECTION"); a(2,"ENTITIES")
    for t, layer, d in p.ents:
        if t == "LINE":
            x1,y1,x2,y2 = d
            a(0,"LINE"); a(8,layer); a(10,x1); a(20,y1); a(30,0.0); a(11,x2); a(21,y2); a(31,0.0)
        elif t == "CIRCLE":
            cx,cy,r = d
            a(0,"CIRCLE"); a(8,layer); a(10,cx); a(20,cy); a(30,0.0); a(40,r)
        elif t == "TEXT":
            x,y,txt,h = d
            a(0,"TEXT"); a(8,layer); a(7,"HZ"); a(10,x); a(20,y); a(30,0.0); a(40,h); a(1,txt)
            a(72,1); a(11,x); a(21,y); a(31,0.0)
    # 图框 + 标题栏（标题栏置于图框外的正下方，避免压图）
    m = p.m
    tw, th = p.W * 0.52, p.W * 0.52 * 0.23
    yb = -m - th - 800
    for (ax, ay, bx, by) in [(-m, yb, p.W+m, yb), (p.W+m, yb, p.W+m, p.H+m),
                             (p.W+m, p.H+m, -m, p.H+m), (-m, p.H+m, -m, yb)]:
        a(0,"LINE"); a(8,"FRAME"); a(10,ax); a(20,ay); a(30,0.0); a(11,bx); a(21,by); a(31,0.0)
    a(0,"LINE"); a(8,"TITLE"); a(10,p.W+m-tw); a(20,yb); a(30,0.0); a(11,p.W+m-tw); a(21,yb+th); a(31,0.0)
    a(0,"LINE"); a(8,"TITLE"); a(10,p.W+m); a(20,yb+th); a(30,0.0); a(11,p.W+m-tw); a(21,yb+th); a(31,0.0)
    sizes = [tw*0.044, tw*0.026, tw*0.019, tw*0.019]
    for i, txt in enumerate([p.title, p.subtitle, "比例 1:100　单位 mm　图层见 LAYER 表", "《综网 · 废柴逆命》场景图"]):
        a(0,"TEXT"); a(8,"TITLE"); a(10,p.W+m-tw+tw*0.04); a(20,yb+th-th*0.22*(i+1)); a(30,0.0)
        a(40, sizes[i]); a(1, txt); a(72,0)
    a(0,"ENDSEC"); a(0,"EOF")
    with open(path, "w", encoding="gbk", errors="replace") as f:
        f.write("\n".join(L) + "\n")

# =====================================================================
# SVG
# =====================================================================
SVG_COLOR = {"FRAME":"#9aa3b2","WALL":"#1f2430","FURN":"#0e9f6e","FIX":"#d94a4a",
             "CIR":"#6d28d9","DASH":"#8b93a7","DIM":"#c98a00","TEXT":"#1f2430","TITLE":"#6d28d9"}
SVG_W = {"FURN":2.0,"FIX":2.4,"CIR":2.0,"DASH":1.4,"DIM":1.2,"FRAME":1.6,"TITLE":1.6,"WALL":2.2,"TEXT":0}

def write_svg(path, p):
    m = p.m
    tw, th = p.W * 0.52, p.W * 0.52 * 0.23
    yb = -m - th - 800                       # 图框下边（标题栏在图框外）
    x0 = -m - 600
    y0 = -600
    w = p.W + 2*m + 1200
    h = (p.H + 2*m + th + 800) + 1200
    k = 1.0
    def Y(y): return (p.H + m) - y          # 翻转
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%f %f %f %f" width="100%%">' % (x0, y0, w, h)]
    s.append('<rect x="%f" y="%f" width="%f" height="%f" fill="#ffffff" stroke="none"/>' % (x0, y0, w, h))
    # 分层排序：细线在下
    order = {"DASH":0,"DIM":1,"FURN":2,"CIR":3,"FIX":4,"WALL":5,"FRAME":6,"TITLE":7,"TEXT":8}
    sw = p.kt * 95.0                    # 线宽随图幅缩放（用户单位）
    for t, layer, d in sorted(p.ents, key=lambda e: order.get(e[1], 3)):
        col = SVG_COLOR.get(layer, "#1f2430")
        if t == "LINE":
            x1,y1,x2,y2 = d
            s.append('<line x1="%f" y1="%f" x2="%f" y2="%f" stroke="%s" stroke-width="%s"/>'
                     % (x1, Y(y1), x2, Y(y2), col, SVG_W.get(layer, 1.6) * sw))
        elif t == "CIRCLE":
            cx,cy,r = d
            s.append('<circle cx="%f" cy="%f" r="%f" fill="none" stroke="%s" stroke-width="%s"/>'
                     % (cx, Y(cy), r, col, SVG_W.get(layer, 2.0) * sw))
        elif t == "TEXT":
            x,y,txt,hh = d
            s.append('<text x="%f" y="%f" font-size="%f" fill="%s" text-anchor="middle" '
                     'font-family="Microsoft YaHei,PingFang SC,sans-serif" dominant-baseline="middle">%s</text>'
                     % (x, Y(y), hh*1.05, col, html.escape(txt)))
    # 图框 + 标题栏（标题栏在图框外正下方）
    s.append('<rect x="%f" y="%f" width="%f" height="%f" fill="none" stroke="%s" stroke-width="%s"/>'
             % (-m, Y(p.H+m), p.W+2*m, (p.H+m)-yb, SVG_COLOR["FRAME"], 1.6*sw))
    tx0, ty0 = p.W+m-tw, yb
    s.append('<rect x="%f" y="%f" width="%f" height="%f" fill="#ffffff" stroke="%s" stroke-width="%s"/>'
             % (tx0, Y(ty0+th), tw, th, SVG_COLOR["TITLE"], 1.6*sw))
    lines = [p.title, p.subtitle, "比例 1:100　单位 mm", "《综网 · 废柴逆命》场景图"]
    sizes = [tw*0.044, tw*0.026, tw*0.019, tw*0.019]
    for i, txt in enumerate(lines):
        s.append('<text x="%f" y="%f" font-size="%f" fill="%s" text-anchor="start" '
                 'font-family="Microsoft YaHei,PingFang SC,sans-serif" dominant-baseline="middle">%s</text>'
                 % (tx0+tw*0.04, Y(ty0+th-th*0.22*(i+1)), sizes[i], SVG_COLOR["TITLE"], html.escape(txt)))
    s.append("</svg>")
    open(path, "w", encoding="utf-8").write("".join(s))

# =====================================================================
# 主流程
# =====================================================================
def main():
    plans = [f() for f in SCENES]
    for p in plans:
        write_dxf(os.path.join(OUT, p.key + ".dxf"), p)
        write_svg(os.path.join(OUT, p.key + ".svg"), p)
        print("生成 %-18s 图元 %4d 个  (%d × %d mm)" % (p.key, len(p.ents), p.W, p.H))

    cards = []
    for p in plans:
        svg = open(os.path.join(OUT, p.key + ".svg"), encoding="utf-8").read()
        cards.append(
            '<section class="card"><div class="hd"><h2>%s</h2><div class="sub">%s</div></div>'
            '<div class="note">%s</div><div class="fig">%s</div>'
            '<div class="dl">源文件：<code>%s.dxf</code>（CAD 可直接打开）　<code>%s.svg</code></div></section>'
            % (html.escape(p.title), html.escape(p.subtitle), html.escape(p.note),
               svg, html.escape(p.key), html.escape(p.key)))

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>综网 · 废柴逆命｜场景平面图</title>
<style>
:root{--bg:#f6f5fa;--panel:#fff;--line:#e3e0ee;--ink:#1f2430;--ink2:#5b6377;--ink3:#8b93a7;--p1:#6d28d9;--p4:#ddd6fe}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:14px/1.7 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif;padding:26px}
h1{font-size:19px;margin-bottom:4px}h1 span{color:var(--p1)}
.top{font-size:12.5px;color:var(--ink3);margin-bottom:20px}
.tools{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--p1);
 border-radius:0 9px 9px 0;padding:12px 16px;font-size:12.5px;color:var(--ink2);margin-bottom:22px}
.tools b{color:var(--p1)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:20px}
.hd{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.hd h2{font-size:15.5px;color:var(--p1)}
.hd .sub{font-size:12px;color:var(--ink3)}
.note{font-size:12.5px;color:var(--ink2);background:#f2effb;border-radius:8px;padding:10px 13px;margin:11px 0 15px}
.fig{background:#fff;border:1px solid var(--line);border-radius:9px;overflow:auto;padding:8px}
.fig svg{display:block;width:100%;height:auto;min-width:560px}
.dl{font-size:11.5px;color:var(--ink3);margin-top:11px}
code{background:#f2effb;padding:1.5px 6px;border-radius:5px;color:var(--p1);font-size:11.5px}
</style></head><body>
<h1>综网 · <span>废柴逆命</span>｜场景平面图</h1>
<div class="top">5 个重要场景 · DXF（R12）+ SVG 双格式 · 单位 mm</div>
<div class="tools">
<b>怎么用</b>：<br>
· 页面里直接看 —— 每张图下方标注了对应的 <code>.dxf</code> / <code>.svg</code> 文件名；<br>
· 进 CAD —— 用 AutoCAD / 中望 / 浩辰 / 天正 打开同目录的 <code>.dxf</code>，可分图层编辑（WALL 墙 / FURN 家具 / FIX 关键物 / CIR 圆形 / DASH 抽象边界 / DIM 尺寸 / TEXT 文字 / TITLE 标题栏）；<br>
· 所有图均为 <b>1:100 出图比例、毫米单位</b>，标题栏已带图名与图号。
</div>
""" + "".join(cards) + """
</body></html>"""
    open(os.path.join(OUT, "场景平面图.html"), "w", encoding="utf-8").write(doc)
    print("\n汇总页：场景平面图.html")

if __name__ == "__main__":
    main()
