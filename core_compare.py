"""两套体系的对比计算(纯计算, 不依赖 Streamlit): 特征提取、元素统计、时间扰动"""
from datetime import timedelta

import generate_dataset as gd

PLANET_NAMES = list(gd.PLANETS)
ASPECT_NAMES = list(gd.ASPECTS)
WUXING = "金木水火土"
ELEMENTS = ["火", "土", "风", "水"]
PILLARS = "年月日时"
UNITS = {"小时": timedelta(hours=1), "时辰(2小时)": timedelta(hours=2), "天": timedelta(days=1),
         "月(30天)": timedelta(days=30), "年": timedelta(days=365)}


def features(dt, bazi_dt, lon, lat, tz):
    """返回 (八字特征 dict, 星盘特征 dict)。"""
    gd.LON, gd.LAT, gd.TZ = lon, lat, tz
    return gd.bazi_features(bazi_dt), gd.astro_features(dt)


def planet_rows(a):
    rows = [{"天体": n, "星座": a[f"星盘_{n}_星座"], "星座内度数": round(a[f"星盘_{n}_度数"] % 30, 2),
             "宫位": a[f"星盘_{n}_宫位"]} for n in PLANET_NAMES]
    rows.insert(0, {"天体": "上升", "星座": a["星盘_上升星座"],
                    "星座内度数": round(a["星盘_上升度数"] % 30, 2), "宫位": 1})
    return rows


def element_counts(bazi, astro):
    return {"五行": {w: bazi[f"八字_{w}数"] for w in WUXING},
            "四元素": {e + "象": astro[f"星盘_{e}象数"] for e in ELEMENTS},
            "相位": {k: astro[f"星盘_相位_{k}"] for k in ASPECT_NAMES}}


def _shift(x, y):
    d = abs(x - y) % 360
    return round(min(d, 360 - d), 2)


def perturb(dt, bazi_dt, lon, lat, tz, unit, n):
    """只改变一个时间单位, 返回两套盘各自的变化。"""
    delta = UNITS[unit] * n
    b1, a1 = features(dt, bazi_dt, lon, lat, tz)
    b2, a2 = features(dt + delta, bazi_dt + delta, lon, lat, tz)
    pillars = [(p + "柱", b1[f"八字_{p}柱"], b2[f"八字_{p}柱"]) for p in PILLARS]
    shifts = []
    for name in ["上升"] + PLANET_NAMES:
        key = "星盘_上升度数" if name == "上升" else f"星盘_{name}_度数"
        shifts.append({"天体": name, "位移": _shift(a1[key], a2[key])})
    return {"new_time": dt + delta,
            "changed": [p for p, old, new in pillars if old != new],
            "pillars": pillars, "shifts": shifts}
