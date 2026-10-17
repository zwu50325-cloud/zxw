"""同字异位(纯计算, 不依赖 Streamlit)
给定一个八字, 找出"用字相同、位置不同"的所有八字, 对比日主/月令/十神, 并反推它们真实对应的出生时间。

做法:
  1. 把 4 个天干、4 个地支分别全排列, 得到所有可能的四柱排列
  2. 过滤: 每柱阴阳要配对; 月干要符合五虎遁; 时干要符合五鼠遁
  3. 对剩下的每个排列, 在指定年份范围内反推真实日期(年柱对应的年份 -> 月支对应的节气月 -> 日柱 -> 时辰)
  4. 每个反推结果都用 lunar-python 重新排一遍八字验证, 不一致的丢弃
时辰内取点为 xx:30(子时取 0:30, 不含晚子时), 与规律分析所用数据一致。
"""
from collections import Counter
from datetime import date, datetime, timedelta
from functools import lru_cache
from itertools import permutations

from lunar_python import Solar

from core_bazi import GAN, GEN, KE, WX, YANG, ZHI, shishen

JIAZI = [GAN[i % 10] + ZHI[i % 12] for i in range(60)]
BENQI = dict(zip(ZHI, "癸己甲乙戊丙丁己庚辛戊壬"))  # 地支本气藏干, 与 bazi_pattern_analysis.py 一致
TEN_GODS = ["比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"]
POS7 = ["年干", "月干", "时干", "年支", "月支", "日支", "时支"]
HOUR = {z: 2 * i for i, z in enumerate(ZHI)}  # 子0 丑2 寅4 ... 亥22, 再取 :30
# 每个月支对应的公历扫描起点(比该节气最早可能日期早约2天), 向后扫 40 天
MONTH_START = {"寅": (2, 1), "卯": (3, 3), "辰": (4, 2), "巳": (5, 3), "午": (6, 3), "未": (7, 4),
               "申": (8, 5), "酉": (9, 5), "戌": (10, 6), "亥": (11, 5), "子": (12, 4), "丑": (1, 1)}


# ---------------- 解析与规则 ----------------
def parse_bazi(text):
    """'庚辰 戊寅 壬子 丙午' 或连写 -> (['庚辰','戊寅','壬子','丙午'], '') ; 失败 -> (None, 原因)"""
    s = "".join(ch for ch in text if ch in GAN or ch in ZHI)
    if len(s) != 8:
        return None, "需要 8 个字(四柱干支), 例如：庚辰 戊寅 壬子 丙午"
    pillars = [s[0:2], s[2:4], s[4:6], s[6:8]]
    for p in pillars:
        if p[0] not in GAN or p[1] not in ZHI:
            return None, f"“{p}”不是“天干+地支”的写法, 请按 年柱 月柱 日柱 时柱 的顺序输入"
    return pillars, ""


def parity_ok(p):
    return GAN.index(p[0]) % 2 == ZHI.index(p[1]) % 2


def month_stem(year_stem, month_branch):
    """五虎遁: 由年干和月支推月干"""
    start = [2, 4, 6, 8, 0][GAN.index(year_stem) % 5]
    return GAN[(start + (ZHI.index(month_branch) - 2) % 12) % 10]


def hour_stem(day_stem, hour_branch):
    """五鼠遁: 由日干和时支推时干"""
    return GAN[((GAN.index(day_stem) % 5) * 2 + ZHI.index(hour_branch)) % 10]


def rules_ok(p):
    return (all(parity_ok(x) for x in p)
            and p[1][0] == month_stem(p[0][0], p[1][1])
            and p[3][0] == hour_stem(p[2][0], p[3][1]))


def arrangements(pillars):
    """用这 8 个字能排出的所有不同四柱(含原八字): 天干全排列 x 地支全排列"""
    stems = [p[0] for p in pillars]
    branches = [p[1] for p in pillars]
    return [[s[i] + b[i] for i in range(4)]
            for s in sorted(set(permutations(stems))) for b in sorted(set(permutations(branches)))]


# ---------------- 反推日期 ----------------
def pillars_at(t):
    ec = Solar.fromYmdHms(t.year, t.month, t.day, t.hour, t.minute, 0).getLunar().getEightChar()
    return [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]


@lru_cache(maxsize=1)
def _day_ref():
    p = pillars_at(datetime(2000, 1, 1, 12, 30))[2]
    return date(2000, 1, 1).toordinal(), JIAZI.index(p)


def _day_idx(d):
    o, i = _day_ref()
    return (i + d.toordinal() - o) % 60


def find_dates(pillars, y0=1900, y1=2100):
    """在 y0~y1 年内, 找出排出该四柱的所有出生时间(每个时辰取 xx:30)。每个结果都经 lunar-python 重新验证。"""
    yp, mp, dp, hp = pillars
    iy, idy = JIAZI.index(yp), JIAZI.index(dp)
    m0, d0 = MONTH_START[mp[1]]
    out = []
    for y in range(y0 - 1, y1 + 1):
        if (y - 4) % 60 != iy:  # 年柱对应的(立春后)年份
            continue
        start = date(y + 1 if mp[1] == "丑" else y, m0, d0)  # 丑月在下一个公历年的 1 月
        for k in range(40):
            d = start + timedelta(days=k)
            if _day_idx(d) != idy:
                continue
            t = datetime(d.year, d.month, d.day, HOUR[hp[1]], 30)
            if pillars_at(t) == list(pillars) and y0 <= t.year <= y1:
                out.append(t)
            break  # 40 天窗口内日柱最多出现一次
    return out


# ---------------- 特征对比 ----------------
def wangxiang(el, ling):
    """五行 el 相对月令五行 ling 的旺相休囚死"""
    if el == ling:
        return "旺"
    if GEN[ling] == el:
        return "相"
    if GEN[el] == ling:
        return "休"
    if KE[el] == ling:
        return "囚"
    return "死"


def describe(p):
    dg = p[2][0]
    ling = p[1][1]
    tg = {"年干": shishen(dg, p[0][0]), "月干": shishen(dg, p[1][0]), "时干": shishen(dg, p[3][0]),
          "年支": shishen(dg, BENQI[p[0][1]]), "月支": shishen(dg, BENQI[p[1][1]]),
          "日支": shishen(dg, BENQI[p[2][1]]), "时支": shishen(dg, BENQI[p[3][1]])}
    cnt = Counter(tg.values())
    comp = " ".join(f"{g}×{cnt[g]}" if cnt[g] > 1 else g for g in TEN_GODS if cnt[g])
    return {"bazi": " ".join(p), "pillars": list(p), "day_master": dg, "dm_wuxing": WX[dg],
            "yinyang": "阳" if dg in YANG else "阴", "ling": ling, "ling_wuxing": WX[ling],
            "state": wangxiang(WX[dg], WX[ling]), "tengod": tg, "tg_comp": comp}


def diff_flags(orig, o):
    flags = []
    if o["day_master"] != orig["day_master"]:
        flags.append("日主")
    if o["ling"] != orig["ling"]:
        flags.append("月令")
    if o["state"] != orig["state"]:
        flags.append("日主状态")
    if o["tg_comp"] != orig["tg_comp"]:
        flags.append("十神构成")
    return flags, sum(o["tengod"][k] != orig["tengod"][k] for k in POS7)


def search(pillars, y0=1900, y1=2100):
    """返回 {'funnel':…, 'items':[原八字在最前, 其余按差异多少排序], 'nodate':[规则合格但范围内无日期的八字]}"""
    orig = list(pillars)
    allarr = arrangements(orig)
    parity = [a for a in allarr if all(parity_ok(p) for p in a)]
    ruled = [a for a in parity if rules_ok(a)]
    od = describe(orig)
    items, nodate = [], []
    for a in ruled:
        ds = find_dates(a, y0, y1)
        if ds or a == orig:
            d = describe(a)
            flags, npos = diff_flags(od, d)
            items.append({**d, "is_orig": a == orig, "valid": True, "diff": flags, "pos_diff": npos, "dates": ds})
        else:
            nodate.append(" ".join(a))
    if orig not in ruled:  # 原八字本身不符合历法规则
        items.append({**od, "is_orig": True, "valid": False, "diff": [], "pos_diff": 0, "dates": []})
    items.sort(key=lambda it: (not it["is_orig"], -len(it["diff"]), -it["pos_diff"], it["bazi"]))
    return {"funnel": {"total": len(allarr), "parity": len(parity), "rules": len(ruled),
                       "with_dates": sum(1 for it in items if it["dates"]),
                       "dates": sum(len(it["dates"]) for it in items)},
            "items": items, "nodate": nodate}


def shichen_name(t):
    return ZHI[((t.hour + 1) // 2) % 12] + "时"


# ---------------- 星盘简要 ----------------
def astro_brief(t, lon, lat, tz, hsys="Placidus"):
    """某个出生时间的星盘概要(太阳/月亮/上升/日夜盘/月相)。时间按当地钟表时间, 时区取固定的 UTC+tz。"""
    import core_astro as ca
    pts, cusps, asc, mc, day = ca.compute(t, lon, lat, tz, hsys)
    f = ca.chart_facts(pts, day)

    def sg(name):
        p = pts[name]
        return f"{ca.SIGNS[p['sign']]} {ca.dms(p['lon'])}"
    return {"太阳": sg("太阳"), "月亮": sg("月亮"), "上升": sg("上升"),
            "日夜": "日盘" if day else "夜盘", "月相": f["phase"]}
