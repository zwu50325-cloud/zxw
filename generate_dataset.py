"""
生成八字 + 星盘对照数据集
安装: pip install lunar-python pyswisseph pandas
用法: python generate_dataset.py
"""
from datetime import datetime, timedelta
import pandas as pd
import swisseph as swe
from lunar_python import Solar

# ===== 配置 =====
START = datetime(1990, 1, 1, 0, 0)
END = datetime(1999, 12, 31, 23, 0)
STEP = timedelta(hours=1)
TZ = 8                      # 时区 (北京时间 UTC+8)
LON, LAT = 116.4, 39.9      # 出生地经纬度 (默认北京)
OUT = "bazi_astro.csv"

# ===== 常量 =====
WUXING = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
          "庚": "金", "辛": "金", "壬": "水", "癸": "水",
          "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
          "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}
SIGNS = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
         "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
ELEMENTS = ["火", "土", "风", "水"]  # 星座序号 % 4
PLANETS = {"日": swe.SUN, "月": swe.MOON, "水": swe.MERCURY, "金": swe.VENUS,
           "火": swe.MARS, "木": swe.JUPITER, "土": swe.SATURN,
           "天王": swe.URANUS, "海王": swe.NEPTUNE, "冥王": swe.PLUTO}
ASPECTS = {"合": 0, "六合": 60, "刑": 90, "拱": 120, "冲": 180}
ORB = 6


def bazi_features(dt):
    s = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
    ec = s.getLunar().getEightChar()
    pillars = {"年": ec.getYear(), "月": ec.getMonth(),
               "日": ec.getDay(), "时": ec.getTime()}
    row = {f"八字_{k}柱": v for k, v in pillars.items()}
    row["八字_日主"] = ec.getDayGan()
    row["八字_日主五行"] = WUXING[ec.getDayGan()]
    row["八字_十神_年干"] = ec.getYearShiShenGan()
    row["八字_十神_月干"] = ec.getMonthShiShenGan()
    row["八字_十神_时干"] = ec.getTimeShiShenGan()
    counts = {w: 0 for w in "金木水火土"}
    for p in pillars.values():
        for ch in p:
            counts[WUXING[ch]] += 1
    for w, c in counts.items():
        row[f"八字_{w}数"] = c
    return row


def house_of(lon, cusps):
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if (lon - a) % 360 < (b - a) % 360:
            return i + 1
    return 12


def astro_features(dt):
    ut = dt - timedelta(hours=TZ)
    jd = swe.julday(ut.year, ut.month, ut.day,
                    ut.hour + ut.minute / 60)
    cusps, ascmc = swe.houses(jd, LAT, LON, b"P")  # Placidus
    row = {"星盘_上升度数": round(ascmc[0], 2),
           "星盘_上升星座": SIGNS[int(ascmc[0] // 30)],
           "星盘_中天度数": round(ascmc[1], 2)}
    lons = {}
    elem_count = {e: 0 for e in ELEMENTS}
    for name, pid in PLANETS.items():
        lon = swe.calc_ut(jd, pid)[0][0]
        lons[name] = lon
        sign = int(lon // 30)
        row[f"星盘_{name}_度数"] = round(lon, 2)
        row[f"星盘_{name}_星座"] = SIGNS[sign]
        row[f"星盘_{name}_宫位"] = house_of(lon, cusps)
        if name in ("日", "月", "水", "金", "火", "木", "土"):
            elem_count[ELEMENTS[sign % 4]] += 1
    for e, c in elem_count.items():
        row[f"星盘_{e}象数"] = c
    # 相位统计
    asp_count = {k: 0 for k in ASPECTS}
    names = list(lons)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = abs(lons[names[i]] - lons[names[j]]) % 360
            d = min(d, 360 - d)
            for k, ang in ASPECTS.items():
                if abs(d - ang) <= ORB:
                    asp_count[k] += 1
    for k, c in asp_count.items():
        row[f"星盘_相位_{k}"] = c
    return row


def main():
    rows, t = [], START
    while t <= END:
        row = {"出生时间": t.strftime("%Y-%m-%d %H:%M")}
        row.update(bazi_features(t))
        row.update(astro_features(t))
        rows.append(row)
        t += STEP
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"完成: {len(df)} 行, {df.shape[1]} 列 -> {OUT}")


if __name__ == "__main__":
    main()
