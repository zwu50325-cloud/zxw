"""八字计算(纯计算, 不依赖 Streamlit): 十神、长生、神煞、刑冲合害、大运流年
界面代码只调用 build_chart() 拿结果, 不在页面里做计算。"""
from itertools import combinations

from lunar_python import Solar

GAN, ZHI = "甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"
WX = dict(zip(GAN + ZHI, "木木火火土土金金水水" + "水土木木土火火土金金土水"))
YANG = set("甲丙戊庚壬子寅辰午申戌")
GEN = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
CS = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CS_OFF = dict(zip("甲丙戊庚壬乙丁己辛癸", [1, 10, 10, 7, 4, 6, 9, 9, 0, 3]))
WUXING_ORDER = "金木水火土"


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


# ---------------- 排盘主函数 ----------------
def build_chart(bdt, gender):
    """bdt: 用于排八字的 datetime(已按需换算真太阳时); gender: 1 男, 0 女。
    返回只含基本数据类型的 dict, 方便缓存和在任意界面显示。"""
    solar = Solar.fromYmdHms(bdt.year, bdt.month, bdt.day, bdt.hour, bdt.minute, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    gz = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
    dg = gz[2][0]
    hides = [list(ec.getYearHideGan()), list(ec.getMonthHideGan()),
             list(ec.getDayHideGan()), list(ec.getTimeHideGan())]
    nayin = [ec.getYearNaYin(), ec.getMonthNaYin(), ec.getDayNaYin(), ec.getTimeNaYin()]
    kong = [ec.getYearXunKong(), ec.getMonthXunKong(), ec.getDayXunKong(), ec.getTimeXunKong()]
    ss = shensha(gz)

    names = ["年柱", "月柱", "日柱", "时柱"]
    pillars = []
    for i, p in enumerate(gz):
        pillars.append({
            "name": names[i], "gz": p, "gan": p[0], "zhi": p[1],
            "zhuxing": shishen(dg, p[0]) if i != 2 else ("元男" if gender == 1 else "元女"),
            "hide": [(h, shishen(dg, h)) for h in hides[i]],
            "xingyun": di_shi(dg, p[1]), "zizuo": di_shi(p[0], p[1]),
            "kong": kong[i], "nayin": nayin[i], "shensha": ss[i]})

    plain = {w: 0 for w in WUXING_ORDER}
    full = dict(plain)
    for p, hs in zip(gz, hides):
        for ch in p:
            plain[WX[ch]] += 1
        full[WX[p[1]]] += 1
        full[WX[p[0]]] += 1
        for h in hs:
            full[WX[h]] += 0.5

    jp, jn = lunar.getPrevJie(), lunar.getNextJie()
    yun = ec.getYun(gender)
    dayun = []
    for d in yun.getDaYun(10):
        if not d.getGanZhi():
            continue
        g = d.getGanZhi()
        dayun.append({
            "ganzhi": g, "start_age": d.getStartAge(), "end_age": d.getEndAge(),
            "start_year": d.getStartYear(), "end_year": d.getEndYear(),
            "shishen": shishen(dg, g[0]), "changsheng": di_shi(dg, g[1]),
            "liunian": [{"year": l.getYear(), "age": l.getAge(), "ganzhi": l.getGanZhi(),
                         "shishen": shishen(dg, l.getGanZhi()[0]),
                         "changsheng": di_shi(dg, l.getGanZhi()[1])} for l in d.getLiuNian()]})
    try:
        xiaoyun = [{"year": x.getYear(), "age": x.getAge(), "ganzhi": x.getGanZhi()}
                   for x in yun.getDaYun(1)[0].getXiaoYun()]
    except Exception:
        xiaoyun = []

    return {
        "gender": gender, "day_master": dg,
        "day_master_wuxing": WX[dg], "day_master_yinyang": "阳" if dg in YANG else "阴",
        "solar": solar.toYmdHms(), "lunar": lunar.toString(),
        "shengxiao": lunar.getYearShengXiaoExact(),
        "jie_prev": f"{jp.getName()} {jp.getSolar().toYmdHms()}",
        "jie_next": f"{jn.getName()} {jn.getSolar().toYmdHms()}",
        "pillars": pillars,
        "taiyuan": f"{ec.getTaiYuan()}（{ec.getTaiYuanNaYin()}）", "taixi": ec.getTaiXi(),
        "minggong": ec.getMingGong(), "shengong": ec.getShenGong(),
        "wuxing_plain": plain, "wuxing_full": full,
        "relations": relations(gz),
        "yun": {"start_year": yun.getStartYear(), "start_month": yun.getStartMonth(),
                "start_day": yun.getStartDay(), "start_date": yun.getStartSolar().toYmd()},
        "dayun": dayun, "xiaoyun": xiaoyun,
    }
