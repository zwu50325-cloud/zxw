"""问真八字风格的完整排盘页面 (Streamlit)"""
from itertools import combinations
import streamlit as st
from lunar_python import Solar

GAN, ZHI = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
WX = dict(zip(GAN + ZHI, "木木火火土土金金水水" + "水土木木土火火土金金土水"))
YANG = set("甲丙戊庚壬子寅辰午申戌")
COLOR = {"木": "#2e9e4d", "火": "#d83b3b", "土": "#a9783a", "金": "#c9961a", "水": "#2f72c9"}
GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
CS = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CS_OFF = dict(zip("甲丙戊庚壬乙丁己辛癸", [1, 10, 10, 7, 4, 6, 9, 9, 0, 3]))


def shishen(dg, g):
    a, b = WX[dg], WX[g]
    same = (dg in YANG) == (g in YANG)
    if a == b:
        return "比肩" if same else "劫财"
    if GEN[a] == b:
        return "食神" if same else "伤官"
    if KE[a] == b:
        return "偏财" if same else "正财"
    if KE[b] == a:
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"


def di_shi(gan, zhi):
    i = ZHI.index(zhi)
    k = (CS_OFF[gan] + (i if GAN.index(gan) % 2 == 0 else -i)) % 12
    return CS[k]


def c(ch, size=None):
    s = f"font-size:{size}px;" if size else ""
    return f'<span style="color:{COLOR[WX[ch]]};{s}">{ch}</span>'


# ---------------- 神煞 ----------------
TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "寅午"}
TAIJI = {"甲": "子午", "乙": "子午", "丙": "卯酉", "丁": "卯酉", "戊": "辰戌丑未",
         "己": "辰戌丑未", "庚": "寅亥", "辛": "寅亥", "壬": "巳申", "癸": "巳申"}
WENCHANG = dict(zip(GAN, "巳午申酉申酉亥子寅卯"))
LU = dict(zip(GAN, "寅卯巳午巳午申酉亥子"))
YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
HONGYAN = dict(zip(GAN, "午午寅未辰辰戌酉子申"))
SANHE = {"申子辰": {"桃花": "酉", "驿马": "寅", "华盖": "辰", "将星": "子"},
         "寅午戌": {"桃花": "卯", "驿马": "申", "华盖": "戌", "将星": "午"},
         "巳酉丑": {"桃花": "午", "驿马": "亥", "华盖": "丑", "将星": "酉"},
         "亥卯未": {"桃花": "子", "驿马": "巳", "华盖": "未", "将星": "卯"}}
TIANDE = dict(zip(ZHI, "巳庚丁申壬辛亥甲癸寅丙乙"))
YUEDE = {"寅午戌": "丙", "申子辰": "壬", "亥卯未": "甲", "巳酉丑": "庚"}
GUGUA = {"亥子丑": ("寅", "戌"), "寅卯辰": ("巳", "丑"),
         "巳午未": ("申", "辰"), "申酉戌": ("亥", "未")}
KUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}


def shensha(gz):
    dg, yg, yz, dz, mz = gz[2][0], gz[0][0], gz[0][1], gz[2][1], gz[1][1]
    out = []
    for i, p in enumerate(gz):
        g, z, s = p[0], p[1], set()
        for src in {dg, yg}:
            if z in TIANYI[src]: s.add("天乙贵人")
            if z in TAIJI[src]: s.add("太极贵人")
        if z == WENCHANG[dg]: s.add("文昌")
        if z == LU[dg]: s.add("禄神")
        if YANGREN.get(dg) == z: s.add("羊刃")
        if z == HONGYAN[dg]: s.add("红艳")
        for src in {yz, dz}:
            for key, d in SANHE.items():
                if src in key:
                    s.update(n for n, t in d.items() if t == z)
        for key, (gu, gua) in GUGUA.items():
            if yz in key:
                if z == gu: s.add("孤辰")
                if z == gua: s.add("寡宿")
        if TIANDE[mz] in (g, z): s.add("天德")
        for key, t in YUEDE.items():
            if mz in key and g == t: s.add("月德")
        if i == 2 and p in KUIGANG: s.add("魁罡")
        out.append(sorted(s))
    return out


# ---------------- 刑冲合害 ----------------
def _pairs(s): return {frozenset(x) for x in s.split()}
GAN_HE, GAN_CHONG = _pairs("甲己 乙庚 丙辛 丁壬 戊癸"), _pairs("甲庚 乙辛 丙壬 丁癸")
Z_HE, Z_CHONG = _pairs("子丑 寅亥 卯戌 辰酉 巳申 午未"), _pairs("子午 丑未 寅申 卯酉 辰戌 巳亥")
Z_HAI, Z_PO = _pairs("子未 丑午 寅巳 卯辰 申亥 酉戌"), _pairs("子酉 卯午 辰丑 未戌 寅亥 巳申")
Z_XING = _pairs("子卯 寅巳 巳申 寅申 丑戌 戌未 丑未")
SELF_XING = set("辰午酉亥")
SANHE_T = ["申子辰", "寅午戌", "巳酉丑", "亥卯未"]
SANHUI_T = ["寅卯辰", "巳午未", "申酉戌", "亥子丑"]


def relations(gz):
    n, out = "年月日时", []
    gs, zs = [p[0] for p in gz], [p[1] for p in gz]
    for i, j in combinations(range(4), 2):
        for tbl, name, arr, suf in [(GAN_HE, "相合", gs, "干"), (GAN_CHONG, "相冲", gs, "干"),
                                    (Z_HE, "六合", zs, "支"), (Z_CHONG, "六冲", zs, "支"),
                                    (Z_HAI, "相害", zs, "支"), (Z_PO, "相破", zs, "支"),
                                    (Z_XING, "相刑", zs, "支")]:
            if frozenset((arr[i], arr[j])) in tbl:
                out.append(f"{n[i]}{suf}{arr[i]} {n[j]}{suf}{arr[j]}：{name}")
        if zs[i] == zs[j] and zs[i] in SELF_XING:
            out.append(f"{n[i]}支{zs[i]} {n[j]}支{zs[j]}：自刑")
    for t in SANHE_T:
        if all(x in zs for x in t): out.append(f"{t}：三合局")
    for t in SANHUI_T:
        if all(x in zs for x in t): out.append(f"{t}：三会局")
    return out or ["无明显合冲刑害"]


# ---------------- 渲染 ----------------
CSS = """<style>
table.bz{border-collapse:collapse;width:100%;text-align:center;font-size:14px}
table.bz td,table.bz th{border:1px solid rgba(128,128,128,.35);padding:6px 4px}
table.bz th{background:rgba(128,128,128,.12);font-weight:600}
.sm{font-size:12px;opacity:.8}.big{font-size:30px;font-weight:700}
.wrap{overflow-x:auto}</style>"""


def table(rows, head=None):
    h = "".join(f"<th>{x}</th>" for x in head) if head else ""
    body = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table class="bz">{"<tr>"+h+"</tr>" if h else ""}{body}</table></div>'


def render(bdt, gender):
    solar = Solar.fromYmdHms(bdt.year, bdt.month, bdt.day, bdt.hour, bdt.minute, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    gz = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
    dg = gz[2][0]
    hides = [ec.getYearHideGan(), ec.getMonthHideGan(), ec.getDayHideGan(), ec.getTimeHideGan()]
    nayin = [ec.getYearNaYin(), ec.getMonthNaYin(), ec.getDayNaYin(), ec.getTimeNaYin()]
    kong = [ec.getYearXunKong(), ec.getMonthXunKong(), ec.getDayXunKong(), ec.getTimeXunKong()]
    ss_list = shensha(gz)

    st.markdown(CSS, unsafe_allow_html=True)
    st.subheader("基本信息")
    jie_prev, jie_next = lunar.getPrevJie(), lunar.getNextJie()
    st.markdown(
        f"**公历**：{solar.toYmdHms()}　**农历**：{lunar.toString()}　**生肖**：{lunar.getYearShengXiaoExact()}  \n"
        f"**性别**：{'男(乾造)' if gender == 1 else '女(坤造)'}　**日主**：{c(dg)}（{WX[dg]}，{'阳' if dg in YANG else '阴'}）  \n"
        f"**节令**：{jie_prev.getName()} {jie_prev.getSolar().toYmdHms()} → "
        f"{jie_next.getName()} {jie_next.getSolar().toYmdHms()}",
        unsafe_allow_html=True)

    st.subheader("四柱")
    rows = [
        ["主星"] + [shishen(dg, p[0]) if i != 2 else ("元男" if gender == 1 else "元女") for i, p in enumerate(gz)],
        ["天干"] + [f'<span class="big">{c(p[0])}</span>' for p in gz],
        ["地支"] + [f'<span class="big">{c(p[1])}</span>' for p in gz],
        ["藏干"] + ["<br>".join(f"{c(h)} <span class='sm'>{shishen(dg, h)}</span>" for h in hs) for hs in hides],
        ["星运"] + [di_shi(dg, p[1]) for p in gz],
        ["自坐"] + [di_shi(p[0], p[1]) for p in gz],
        ["空亡"] + kong,
        ["纳音"] + nayin,
        ["神煞"] + ["<br>".join(x) or "—" for x in ss_list],
    ]
    st.markdown(table(rows, ["", "年柱", "月柱", "日柱", "时柱"]), unsafe_allow_html=True)

    st.subheader("命宫 · 胎元 · 五行")
    st.markdown(
        f"**胎元**：{ec.getTaiYuan()}（{ec.getTaiYuanNaYin()}）　**胎息**：{ec.getTaiXi()}　"
        f"**命宫**：{ec.getMingGong()}　**身宫**：{ec.getShenGong()}")
    plain = {w: 0 for w in "金木水火土"}
    full = dict(plain)
    for p, hs in zip(gz, hides):
        for ch in p: plain[WX[ch]] += 1
        full[WX[p[1]]] += 1
        full[WX[p[0]]] += 1
        for h in hs: full[WX[h]] += 0.5
    st.markdown(table([["仅八字"] + [plain[w] for w in "金木水火土"],
                       ["含藏干(藏干计0.5)"] + [full[w] for w in "金木水火土"]],
                      ["", "金", "木", "水", "火", "土"]),
                unsafe_allow_html=True)

    st.subheader("刑冲合害")
    for r in relations(gz): st.write("· " + r)

    # ---- 大运流年 ----
    st.subheader("大运")
    yun = ec.getYun(gender)
    st.write(f"出生后 {yun.getStartYear()} 年 {yun.getStartMonth()} 个月 {yun.getStartDay()} 天起运，"
             f"起运日期 {yun.getStartSolar().toYmd()}")
    dys = [d for d in yun.getDaYun(10) if d.getGanZhi()]
    head = [f"{d.getStartAge()}岁<br><span class='sm'>{d.getStartYear()}</span>" for d in dys]
    st.markdown(table([
        [shishen(dg, d.getGanZhi()[0]) for d in dys],
        [f'<span class="big" style="font-size:22px">{c(d.getGanZhi()[0])}{c(d.getGanZhi()[1])}</span>' for d in dys],
        [di_shi(dg, d.getGanZhi()[1]) for d in dys],
    ], head), unsafe_allow_html=True)

    labels = [f"{d.getGanZhi()}（{d.getStartAge()}-{d.getEndAge()}岁，{d.getStartYear()}-{d.getEndYear()}）" for d in dys]
    pick = st.selectbox("查看该大运的流年", labels)
    dy = dys[labels.index(pick)]
    lns = dy.getLiuNian()
    st.markdown(table([
        [f"{l.getYear()}<br><span class='sm'>{l.getAge()}岁</span>" for l in lns],
        [f'<span style="font-size:20px">{c(l.getGanZhi()[0])}{c(l.getGanZhi()[1])}</span>' for l in lns],
        [shishen(dg, l.getGanZhi()[0]) for l in lns],
        [di_shi(dg, l.getGanZhi()[1]) for l in lns],
    ], None), unsafe_allow_html=True)
    st.caption("行依次为：年份/虚岁、流年干支、天干十神、星运。")
    try:
        xys = yun.getDaYun(1)[0].getXiaoYun()
        st.markdown("**小运**：" + "　".join(f"{x.getYear()}年{x.getAge()}岁 {x.getGanZhi()}" for x in xys))
    except Exception:
        pass
