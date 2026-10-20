"""同一天(年柱、月柱、日柱相同)、不同时辰: 时柱和前三柱的联系, 以及对应的星盘差异(纯计算, 不依赖 Streamlit)

八字这一侧的联系分两类:
  1. 硬规则: 时干只由"日干 + 时支"决定(五鼠遁), 年柱、月柱对时柱没有任何影响;
  2. 相互作用: 时干、时支和年/月/日的干支之间的合冲刑害、十神、藏干透出、日主通根、五行多寡。
星盘这一侧: 每个时辰的上升、天顶、各天体落宫; 一天之内哪些相位不变、哪些在变。
"""
from collections import Counter
from datetime import date, datetime, timedelta

import pandas as pd

import core_astro as ca
import core_bazi as cb
from core_bazi import GAN, WX, ZHI, shishen
from core_samechars import BENQI, TEN_GODS, hour_stem, pillars_at

# (名称, 时支, 开始钟点, 结束钟点, 取样分钟数)。早子 00-01, 晚子 23-24 分开看。
SLOTS = [("子时·早", "子", 0, 1, 30), ("丑时", "丑", 1, 3, 150), ("寅时", "寅", 3, 5, 270),
         ("卯时", "卯", 5, 7, 390), ("辰时", "辰", 7, 9, 510), ("巳时", "巳", 9, 11, 630),
         ("午时", "午", 11, 13, 750), ("未时", "未", 13, 15, 870), ("申时", "申", 15, 17, 990),
         ("酉时", "酉", 17, 19, 1110), ("戌时", "戌", 19, 21, 1230), ("亥时", "亥", 21, 23, 1350),
         ("子时·晚", "子", 23, 24, 1410)]
HELP = {"比肩", "劫财", "正印", "偏印"}   # 帮身的十神; 其余(食伤财官杀)算耗身
BODIES = ca.MAIN


# ---------------- 干支之间的关系 ----------------
def gan_rel(a, b):
    if a == b:
        return "同"
    s = frozenset((a, b))
    return "合" if s in cb.GAN_HE else ("冲" if s in cb.GAN_CHONG else "")


def zhi_rel(a, b):
    if a == b:
        return "同·自刑" if a in cb.SELF_XING else "同"
    s = frozenset((a, b))
    out = [n for n, t in (("六合", cb.Z_HE), ("六冲", cb.Z_CHONG), ("相害", cb.Z_HAI),
                          ("相破", cb.Z_PO), ("相刑", cb.Z_XING)) if s in t]
    return "、".join(out)


def ju_with(zs, zhi_idx=3):
    """时支参与组成的三合局/三会局(整局四个地支里必须齐全)。"""
    z = zs[zhi_idx]
    return [f"{t}三合" for t in cb.SANHE_T if z in t and all(x in zs for x in t)] + \
           [f"{t}三会" for t in cb.SANHUI_T if z in t and all(x in zs for x in t)]


REL_PAIRS = ["年月", "年日", "年时", "月日", "月时", "日时"]
_IDX = {"年": 0, "月": 1, "日": 2, "时": 3}
REL_COLS = (["干_" + p for p in REL_PAIRS] + ["支_" + p for p in REL_PAIRS] +
            ["干合数", "干冲数", "支六合数", "支六冲数", "支刑数", "支害数", "支破数", "局"])


def rel_features(gz):
    """四柱之间的天干合冲、地支六合/六冲/刑/害/破、三合三会局。gz = ['庚辰','戊寅','壬子','丙午']。
    返回 {列名: 值}: 每一对柱(年月、年日…)的干关系和支关系, 以及各类关系的个数。"""
    out, cnt = {}, Counter()
    zs = [p[1] for p in gz]
    for p in REL_PAIRS:
        i, j = _IDX[p[0]], _IDX[p[1]]
        g, z = gan_rel(gz[i][0], gz[j][0]), zhi_rel(gz[i][1], gz[j][1])
        out["干_" + p], out["支_" + p] = g or "无", z or "无"
        cnt["干合"] += g == "合"
        cnt["干冲"] += g == "冲"
        for part in z.replace("同·自刑", "同").split("、"):
            cnt[part] += 1
    out.update({"干合数": cnt["干合"], "干冲数": cnt["干冲"], "支六合数": cnt["六合"], "支六冲数": cnt["六冲"],
                "支刑数": cnt["相刑"], "支害数": cnt["相害"], "支破数": cnt["相破"]})
    ju = [t + "三合" for t in cb.SANHE_T if all(x in zs for x in t)] + \
         [t + "三会" for t in cb.SANHUI_T if all(x in zs for x in t)]
    out["局"] = "、".join(ju) or "无"
    return out


def rel_text(rel):
    """把 rel_features 的结果写成一句话, 例如 '日时干冲；日时支六冲'。"""
    return "；".join(f"{k[2:]}{k[0]}{v}" for k, v in rel.items() if k[:2] in ("干_", "支_") and v != "无") or "无"


# ---------------- 一天的十三个时段 ----------------
def day_rows(d, lon, lat, tz, hsys="Placidus", gender=1):
    """d: date。返回 (前三柱, 行列表)。前三柱取当天正午。"""
    ref = pillars_at(datetime(d.year, d.month, d.day, 12, 30))[:3]
    rows = []
    for name, zhi, h0, h1, mid in SLOTS:
        base = datetime(d.year, d.month, d.day)
        t = base + timedelta(minutes=mid)
        ch = cb.build_chart(t, gender)
        P = ch["pillars"]
        gz = [p["gz"] for p in P]
        dg = gz[2][0]
        hides = [[h for h, _ in p["hide"]] for p in P]
        zs = [p[1] for p in gz]
        hg, hz = gz[3][0], gz[3][1]
        tg = {"年干": shishen(dg, gz[0][0]), "月干": shishen(dg, gz[1][0]), "时干": shishen(dg, hg),
              "年支": shishen(dg, BENQI[zs[0]]), "月支": shishen(dg, BENQI[zs[1]]),
              "日支": shishen(dg, BENQI[zs[2]]), "时支": shishen(dg, BENQI[hz])}
        # 日主通根: 哪些地支的藏干里有和日主同五行的干
        roots = [n for n, hs in zip("年月日时", hides) if any(WX[x] == WX[dg] for x in hs)]
        # 时支的藏干有没有"透"到四个天干上; 时干在别的地支藏干里有没有根
        gans = [p[0] for p in gz]
        tou = [f"{x}透于{'年月日时'[i]}干" for x in hides[3] for i in range(4) if gans[i] == x]
        shigan_root = [n for n, hs in zip("年月日", hides[:3]) if hg in hs]
        wx = {w: 0 for w in "金木水火土"}
        for p in gz:
            for ch_ in p:
                wx[WX[ch_]] += 1
        mx = max(wx.values())
        cnt = Counter(tg.values())
        help_n = sum(v for k, v in cnt.items() if k in HELP)
        rows.append({
            "名称": name, "时支": zhi, "钟点": f"{h0:02d}:00–{h1:02d}:00", "t": t, "gz": gz,
            "同前三柱": gz[:3] == ref, "五鼠遁吻合": hg == hour_stem(dg, hz),
            "日主": dg, "十神": tg, "时藏干": hides[3], "时干十神": tg["时干"], "时支十神": tg["时支"],
            "干关系": {n: gan_rel(hg, gans[i]) for i, n in enumerate("年月日")},
            "支关系": {n: zhi_rel(hz, zs[i]) for i, n in enumerate("年月日")},
            "通根": roots, "透干": tou, "时干有根于": shigan_root, "局": ju_with(zs),
            "五行": wx, "最多": "".join(k for k, v in wx.items() if v == mx),
            "缺": "".join(k for k, v in wx.items() if v == 0),
            "帮身": help_n, "耗身": 7 - help_n, "关系": ch["relations"],
            "xingyun": P[3]["xingyun"], "zizuo": P[3]["zizuo"], "nayin": P[3]["nayin"],
            "shensha": P[3]["shensha"],
            "star": _star(d, h0, h1, mid, lon, lat, tz, hsys)})
    return ref, rows


def _star(d, h0, h1, mid, lon, lat, tz, hsys):
    base = datetime(d.year, d.month, d.day)
    t_mid = base + timedelta(minutes=mid)
    t0, t1 = base + timedelta(hours=h0), base + timedelta(hours=h1) - timedelta(minutes=1)
    pts, cusps, asc, mc, day = ca.compute(t_mid, lon, lat, tz, hsys)
    a0 = ca.compute(t0, lon, lat, tz, hsys)[2]
    a1 = ca.compute(t1, lon, lat, tz, hsys)[2]
    fmt = lambda L: f"{ca.SIGNS[int(L // 30) % 12]} {ca.dms(L)}"
    asps = {(a, b, nm) for a, b, nm, sym, ang, orb, col in ca.aspects_of(pts)}
    return {"asc0": fmt(a0), "asc1": fmt(a1), "asc_signs": sorted({int(a0 // 30) % 12, int(a1 // 30) % 12}),
            "mc": fmt(mc), "day": "日盘" if day else "夜盘",
            "house": {b: pts[b]["house"] for b in BODIES},
            "sign": {b: ca.SIGNS[pts[b]["sign"]] for b in BODIES},
            "asp": asps, "asc_lon": asc}


# ---------------- 汇总表 ----------------
def bazi_table(rows):
    out = []
    for r in rows:
        out.append({
            "时辰": r["名称"], "钟点": r["钟点"], "八字": " ".join(r["gz"]),
            "时干十神": r["时干十神"], "时支十神": r["时支十神"], "时支藏干": "".join(r["时藏干"]),
            "时干 vs 年/月/日干": " / ".join(r["干关系"][k] or "—" for k in "年月日"),
            "时支 vs 年/月/日支": " / ".join(r["支关系"][k] or "—" for k in "年月日"),
            "日主通根于": "".join(r["通根"]) or "无", "三合/三会": "、".join(r["局"]) or "—",
            "五行最多": r["最多"], "五行缺": r["缺"] or "—", "帮身:耗身": f"{r['帮身']}:{r['耗身']}",
            "日主在时支": r["xingyun"],
            "与前三柱一致": "是" if r["同前三柱"] else "否", "五鼠遁吻合": "是" if r["五鼠遁吻合"] else "否"})
    return pd.DataFrame(out)


def star_table(rows):
    out = []
    for r in rows:
        s = r["star"]
        row = {"时辰": r["名称"], "钟点": r["钟点"], "上升(开始)": s["asc0"], "上升(结束)": s["asc1"],
               "天顶(取样点)": s["mc"], "日夜盘": s["day"]}
        for b in BODIES:
            row[b] = f"{s['sign'][b]}·{s['house'][b]}宫"
        out.append(row)
    return pd.DataFrame(out)


def house_matrix(rows):
    """行 = 时辰, 列 = 天体, 值 = 所在宫位(数字)。"""
    return pd.DataFrame({b: [r["star"]["house"][b] for r in rows] for b in BODIES},
                        index=[r["名称"] for r in rows])


def aspect_stability(rows):
    """一天各时段里相位的出现情况: 返回 DataFrame(天体A, 相位, 天体B, 出现时段数, 类型)。"""
    n = len(rows)
    cnt = Counter()
    for r in rows:
        cnt.update(r["star"]["asp"])
    axes = {"上升", "天顶"}
    data = []
    for (a, b, nm), c in cnt.items():
        data.append({"天体A": a, "相位": nm, "天体B": b, "出现时段数": c, "共": n,
                     "类型": "涉及上升/天顶" if (a in axes or b in axes) else
                             ("涉及月亮" if "月亮" in (a, b) else "行星间")})
    df = pd.DataFrame(data)
    return df.sort_values(["出现时段数", "类型"], ascending=[False, True]).reset_index(drop=True) if len(df) else df


def sun_house_by_hour(rows):
    return {r["名称"]: r["star"]["house"]["太阳"] for r in rows}


# ---------------- 整年统计: 月支 × 时支 ----------------
def year_table(year, lon, lat, tz, hsys="Placidus"):
    """一年里每一天 12 个时辰(取样 xx:30, 子时取 0:30): 月支、时支、太阳宫、上升座、天顶座。"""
    rows, d = [], date(year, 1, 1)
    while d.year == year:
        for name, zhi, h0, h1, mid in SLOTS[:12]:
            t = datetime(d.year, d.month, d.day) + timedelta(minutes=mid)
            p = pillars_at(t)
            pts, cusps, asc, mc, day = ca.compute(t, lon, lat, tz, hsys)
            rows.append({"月支": p[1][1], "时支": zhi, "太阳宫": pts["太阳"]["house"],
                         "上升座": ca.SIGNS[int(asc // 30) % 12], "天顶座": ca.SIGNS[int(mc // 30) % 12]})
        d += timedelta(days=1)
    return pd.DataFrame(rows)


def year_pivot(df, what):
    """月支 × 时支: 每格里最常见的值及其占比。"""
    order_m = [z for z in "寅卯辰巳午未申酉戌亥子丑"]
    order_h = list(ZHI)
    g = df.groupby(["月支", "时支"])[what].agg(lambda s: (s.mode().iloc[0], s.value_counts(normalize=True).iloc[0]))
    tab = pd.DataFrame("", index=order_m, columns=order_h)
    for (m, h), (v, p) in g.items():
        tab.loc[m, h] = f"{v}宫 {p:.0%}" if what == "太阳宫" else f"{v} {p:.0%}"
    return tab


# ---------------- 验证: 年柱月柱不影响时柱 ----------------
def verify_wushu(d, n=6):
    """从 d 起每隔 10 天取一天(日干相同, 年月日支各不同), 比较当天 12 个时柱是否完全一样。"""
    seqs, labels = [], []
    for k in range(n):
        day = d + timedelta(days=10 * k)
        seq = [pillars_at(datetime(day.year, day.month, day.day) + timedelta(minutes=m))[3]
               for _, _, _, _, m in SLOTS[:12]]
        p = pillars_at(datetime(day.year, day.month, day.day, 12, 30))
        seqs.append(seq)
        labels.append(f"{day} ｜ {' '.join(p[:3])}")
    same = all(s == seqs[0] for s in seqs)
    return pd.DataFrame({"日期｜前三柱": labels, "当天12个时柱": [" ".join(s) for s in seqs]}), same
