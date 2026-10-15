"""爱星盘风格的星盘页面: 星盘轮盘 + 行星表 + 宫位表 + 相位表 (Streamlit)"""
import math
from datetime import timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import swisseph as swe

SIGNS = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
SGLYPH = "♈♉♊♋♌♍♎♏♐♑♒♓"
ELEM_COLOR = ["#e0553d", "#9a7a3a", "#d4a017", "#3b82c4"]  # 火 土 风 水
ELEM_NAME = ["火", "土", "风", "水"]
MODE_NAME = ["本位", "固定", "变动"]
RULER = ["火星", "金星", "水星", "月亮", "太阳", "水星", "金星", "冥王星", "木星", "土星", "天王星", "海王星"]

BODIES = [("太阳", "☉", swe.SUN), ("月亮", "☽", swe.MOON), ("水星", "☿", swe.MERCURY),
          ("金星", "♀", swe.VENUS), ("火星", "♂", swe.MARS), ("木星", "♃", swe.JUPITER),
          ("土星", "♄", swe.SATURN), ("天王星", "♅", swe.URANUS), ("海王星", "♆", swe.NEPTUNE),
          ("冥王星", "♇", swe.PLUTO), ("凯龙星", "⚷", swe.CHIRON),
          ("北交点", "☊", swe.TRUE_NODE), ("莉莉丝", "⚸", swe.MEAN_APOG)]
MAIN = [b[0] for b in BODIES[:10]]
NO_RETRO = {"北交点", "莉莉丝", "太阳", "月亮"}

DOM = {"太阳": [4], "月亮": [3], "水星": [2, 5], "金星": [1, 6], "火星": [0, 7],
       "木星": [8, 11], "土星": [9, 10], "天王星": [10], "海王星": [11], "冥王星": [7]}
EXALT = {"太阳": 0, "月亮": 1, "水星": 5, "金星": 11, "火星": 9, "木星": 3, "土星": 6}

ASPECTS = [("合", "☌", 0, 8, None), ("六合", "⚹", 60, 5, "#3b82c4"),
           ("刑", "□", 90, 7, "#d94b4b"), ("拱", "△", 120, 7, "#2e9e4d"),
           ("冲", "☍", 180, 8, "#d94b4b")]
HSYS = {"Placidus": "P", "整宫制": "W", "等宫制": "E", "Koch": "K", "Porphyry": "O"}


def dms(x):
    d = x % 30
    return f"{int(d)}°{int((d % 1) * 60):02d}'"


def dignity(name, sign):
    if name in DOM and sign in DOM[name]: return "庙"
    if EXALT.get(name) == sign: return "旺"
    if name in DOM and sign in [(s + 6) % 12 for s in DOM[name]]: return "陷"
    if name in EXALT and sign == (EXALT[name] + 6) % 12: return "弱"
    return ""


def house_of(lon, cusps):
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if (lon - a) % 360 < (b - a) % 360:
            return i + 1
    return 12


def compute(dt, lon, lat, tz, hsys):
    ut = dt - timedelta(hours=tz)
    jd = swe.julday(ut.year, ut.month, ut.day, ut.hour + ut.minute / 60)
    try:
        cusps, ascmc = swe.houses(jd, lat, lon, HSYS[hsys].encode())
    except Exception:
        cusps, ascmc = swe.houses(jd, lat, lon, b"O")
    cusps = list(cusps)[-12:]
    pts = {}
    for name, g, pid in BODIES:
        try:
            xx = swe.calc_ut(jd, pid)[0]
        except Exception:
            continue
        pts[name] = {"glyph": g, "lon": xx[0], "retro": xx[3] < 0 and name not in NO_RETRO}
    if "北交点" in pts:
        pts["南交点"] = {"glyph": "☋", "lon": (pts["北交点"]["lon"] + 180) % 360, "retro": False}
    asc, mc = ascmc[0], ascmc[1]
    sun, moon = pts["太阳"]["lon"], pts["月亮"]["lon"]
    day = house_of(sun, cusps) >= 7
    fort = (asc + moon - sun) % 360 if day else (asc + sun - moon) % 360
    pts["福点"] = {"glyph": "⊗", "lon": fort, "retro": False}
    for n, g, v in [("上升", "AC", asc), ("天顶", "MC", mc)]:
        pts[n] = {"glyph": g, "lon": v, "retro": False}
    for p in pts.values():
        p["house"] = house_of(p["lon"], cusps)
        p["sign"] = int(p["lon"] // 30)
    return pts, cusps, asc, mc, day


def aspects_of(pts):
    names = MAIN + ["上升", "天顶"]
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            d = abs(pts[a]["lon"] - pts[b]["lon"]) % 360
            d = min(d, 360 - d)
            for nm, sym, ang, orb, col in ASPECTS:
                if abs(d - ang) <= orb:
                    out.append((a, b, nm, sym, ang, abs(d - ang), col))
    return out


def spread(items, gap=8):
    items = sorted(items, key=lambda x: x[1])
    disp = [x[1] for x in items]
    for _ in range(40):
        moved = False
        for i in range(len(items)):
            j = (i + 1) % len(items)
            d = (disp[j] - disp[i]) % 360
            if d < gap and len(items) > 1:
                p = (gap - d) / 2
                disp[i] -= p
                disp[j] += p
                moved = True
        if not moved:
            break
    return {items[i][0]: disp[i] % 360 for i in range(len(items))}


def wheel_svg(pts, cusps, asc, asps):
    S, cx, cy = 680, 340, 340
    R0, R1, R2 = 320, 280, 150
    V = "\ufe0e"

    def pos(L, r):
        a = math.radians((L - asc) % 360)
        return cx - r * math.cos(a), cy + r * math.sin(a)

    o = [f'<svg viewBox="0 0 {S} {S}" xmlns="http://www.w3.org/2000/svg" '
         f'style="width:100%;max-width:680px;color:inherit" font-family="\'Segoe UI Symbol\',\'Noto Sans Symbols\',\'Apple Symbols\',sans-serif">']
    # 星座环
    for i in range(12):
        a0, a1 = i * 30, (i + 1) * 30
        x0, y0 = pos(a0, R0); x1, y1 = pos(a1, R0)
        x2, y2 = pos(a1, R1); x3, y3 = pos(a0, R1)
        col = ELEM_COLOR[i % 4]
        o.append(f'<path d="M{x0:.1f},{y0:.1f} A{R0},{R0} 0 0 0 {x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f} '
                 f'A{R1},{R1} 0 0 1 {x3:.1f},{y3:.1f} Z" fill="{col}" fill-opacity=".14" '
                 f'stroke="currentColor" stroke-opacity=".5"/>')
        gx, gy = pos(a0 + 15, (R0 + R1) / 2)
        o.append(f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="26" fill="{col}">{SGLYPH[i]}{V}</text>')
    for r in (R1, R2):
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="currentColor" stroke-opacity=".5"/>')
    # 宫线与宫号
    for i, cu in enumerate(cusps):
        x0, y0 = pos(cu, R2); x1, y1 = pos(cu, R1)
        w = 1.8 if i in (0, 3, 6, 9) else .8
        o.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="currentColor" '
                 f'stroke-opacity=".55" stroke-width="{w}"/>')
        nxt = cusps[(i + 1) % 12]
        mid = cu + ((nxt - cu) % 360) / 2
        tx, ty = pos(mid, R2 + 16)
        o.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="13" fill="currentColor" fill-opacity=".6">{i + 1}</text>')
    # 相位线
    for a, b, nm, sym, ang, orb, col in asps:
        if col is None: continue
        x0, y0 = pos(pts[a]["lon"], R2 - 2); x1, y1 = pos(pts[b]["lon"], R2 - 2)
        o.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{col}" '
                 f'stroke-width="1.3" stroke-opacity="{max(.25, 1 - orb / 8):.2f}"/>')
    # 行星
    show = [n for n in pts if n not in ("上升", "天顶", "南交点", "福点")]
    disp = spread([(n, pts[n]["lon"]) for n in show])
    for n in show:
        L, D = pts[n]["lon"], disp[n]
        x0, y0 = pos(L, R1); x1, y1 = pos(L, R1 - 8)
        o.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="currentColor"/>')
        gx, gy = pos(D, R1 - 34)
        o.append(f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="24" fill="currentColor">{pts[n]["glyph"]}{V}</text>')
        dx, dy = pos(D, R1 - 64)
        r = "ᴿ" if pts[n]["retro"] else ""
        o.append(f'<text x="{dx:.1f}" y="{dy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="11" fill="currentColor" fill-opacity=".8">{dms(L)}{r}</text>')
    # 四轴
    for nm, L in [("AC", asc), ("DC", asc + 180), ("MC", pts["天顶"]["lon"]), ("IC", pts["天顶"]["lon"] + 180)]:
        x, y = pos(L, R0 + 0.1)
        tx, ty = pos(L, R0 + 14)
        o.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="12" font-weight="700" fill="currentColor">{nm}</text>')
    o.append("</svg>")
    return "".join(o)


def render(dt, lon, lat, tz):
    hs = st.selectbox("宫位制", list(HSYS), key="hsys")
    pts, cusps, asc, mc, day = compute(dt, lon, lat, tz, hs)
    asps = aspects_of(pts)
    svg = wheel_svg(pts, cusps, asc, asps)
    components.html(f'<div style="background:#fff;color:#222;border-radius:12px;padding:6px">{svg}</div>',
                    height=720, scrolling=False)

    sun, moon = pts["太阳"]["lon"], pts["月亮"]["lon"]
    ph = (moon - sun) % 360
    phase = ["新月", "盈眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"][int((ph + 22.5) // 45) % 8]
    el = {e: 0 for e in ELEM_NAME}
    md = {m: 0 for m in MODE_NAME}
    for n in MAIN:
        el[ELEM_NAME[pts[n]["sign"] % 4]] += 1
        md[MODE_NAME[pts[n]["sign"] % 3]] += 1
    st.markdown(
        f"**日夜盘**：{'日盘' if day else '夜盘'}　**月相**：{phase}（日月夹角 {ph:.1f}°）  \n"
        f"**四元素**：" + "　".join(f"{k}{v}" for k, v in el.items()) +
        "　**三模式**：" + "　".join(f"{k}{v}" for k, v in md.items()))

    st.subheader("行星位置")
    rows = []
    for n in list(pts):
        p = pts[n]
        if n in ("上升", "天顶"):
            continue
        rows.append({"天体": f"{p['glyph']} {n}", "星座": f"{SGLYPH[p['sign']]} {SIGNS[p['sign']]}",
                     "度数": dms(p["lon"]) + (" R" if p["retro"] else ""),
                     "宫位": p["house"], "尊贵": dignity(n, p["sign"])})
    for n, g in [("上升", "AC"), ("天顶", "MC")]:
        p = pts[n]
        rows.insert(0 if n == "上升" else 1,
                    {"天体": f"{g} {n}", "星座": f"{SGLYPH[p['sign']]} {SIGNS[p['sign']]}",
                     "度数": dms(p["lon"]), "宫位": "", "尊贵": ""})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.subheader("宫位")
    hrows = []
    for i, cu in enumerate(cusps):
        s = int(cu // 30)
        inside = [n for n in pts if pts[n]["house"] == i + 1 and n not in ("上升", "天顶")]
        hrows.append({"宫": i + 1, "宫头": f"{SGLYPH[s]} {SIGNS[s]} {dms(cu)}",
                      "宫主星": RULER[s], "宫内天体": "、".join(inside)})
    st.dataframe(pd.DataFrame(hrows), hide_index=True, use_container_width=True)

    st.subheader("相位表")
    names = MAIN + ["上升", "天顶"]
    grid = pd.DataFrame("", index=names, columns=names)
    for a, b, nm, sym, ang, orb, col in asps:
        grid.loc[b, a] = f"{sym} {int(orb)}°{int((orb % 1) * 60):02d}'"
    st.dataframe(grid, use_container_width=True)
    st.caption("容许度：合/冲 8°，刑/拱 7°，六合 5°。表中显示精确度偏差。")
    st.write(f"共 {len(asps)} 个相位。")
    st.dataframe(pd.DataFrame(
        [{"天体A": a, "相位": f"{sym} {nm}", "天体B": b, "偏差": f"{orb:.2f}°"}
         for a, b, nm, sym, ang, orb, col in sorted(asps, key=lambda x: x[5])]),
        hide_index=True, use_container_width=True)
