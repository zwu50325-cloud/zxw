"""按星盘条件看八字(纯计算, 不依赖 Streamlit)
问题: 满足某个星盘条件(例如"月亮在 1 宫")的出生时间, 它们的八字有什么特征?
做法:
  1. build_dataset: 给每个出生时间同时算出八字特征和星盘特征(每个时辰取 xx:30, 子时取 0:30)
  2. 选出满足条件的行, 和全部行比: 某个八字特征的某个取值, 在条件内占比多少、总体占比多少(倍数)
  3. 用"效应大小(Cramér's V)"衡量这个星盘条件和这个八字特征有多相关, 再和"随机平移基线"比较
     (把条件标记沿时间轴平移整数天, 重新算 V。平移保留了"一天之内的时辰结构"和条件成片出现的特点,
      但打乱了它和具体日期、节气的对应, 所以能分辨"和日期有关"和"只是时刻结构/碰巧")
命令行: python core_conditions.py --y0 1996 --y1 2025 --out astro_bazi_rows.csv
"""
import argparse
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from lunar_python import Solar

import core_astro as ca
from core_bazi import WX, shishen
from core_samechars import BENQI, HOUR, POS7, TEN_GODS, wangxiang

BODIES = ca.MAIN  # 太阳 月亮 水星 金星 火星 木星 土星 天王星 海王星 冥王星
BAZI_COLS = ["日主", "日主五行", "月令", "年支", "日支", "时支", "日主状态", "最多五行", "最多十神"] + \
            ["十神_" + k for k in POS7]
ASTRO_COLS = [f"{b}宫" for b in BODIES] + [f"{b}座" for b in BODIES] + ["上升座", "天顶座", "日夜盘"]
# 规律发现用的额外列: 天体两两之间的相位(合/六合/刑/拱/冲/无)、月相; 八字的年干、月干、时干、年柱、日柱
ASPECT_COLS = [f"相位_{a}_{b}" for i, a in enumerate(BODIES) for b in BODIES[i + 1:]]
ASTRO_EXTRA = ["月相"] + ASPECT_COLS
BAZI_EXTRA = ["年干", "月干", "时干", "年柱", "日柱"]
PHASES = ["新月", "盈眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"]


# ---------------- 生成数据 ----------------
def _top(counter, keys):
    mx = max(counter[k] for k in keys)
    best = [k for k in keys if counter[k] == mx]
    return best[0] if len(best) == 1 else "并列"


def row_for(t, lon, lat, tz, hsys="Placidus"):
    ec = Solar.fromYmdHms(t.year, t.month, t.day, t.hour, t.minute, 0).getLunar().getEightChar()
    y, m, d, h = ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()
    dg, ling = d[0], m[1]
    tg = {"年干": shishen(dg, y[0]), "月干": shishen(dg, m[0]), "时干": shishen(dg, h[0]),
          "年支": shishen(dg, BENQI[y[1]]), "月支": shishen(dg, BENQI[m[1]]),
          "日支": shishen(dg, BENQI[d[1]]), "时支": shishen(dg, BENQI[h[1]])}
    wx = {w: 0 for w in "金木水火土"}
    for ch in y + m + d + h:
        wx[WX[ch]] += 1
    tgc = {g: 0 for g in TEN_GODS}
    for g in tg.values():
        tgc[g] += 1
    row = {"出生时间": t.strftime("%Y-%m-%d %H:%M"), "八字": f"{y} {m} {d} {h}",
           "日主": dg, "日主五行": WX[dg], "月令": ling, "年支": y[1], "日支": d[1], "时支": h[1],
           "日主状态": wangxiang(WX[dg], WX[ling]),
           "最多五行": _top(wx, "金木水火土"), "最多十神": _top(tgc, TEN_GODS)}
    for k in POS7:
        row["十神_" + k] = tg[k]
    row.update({"年干": y[0], "月干": m[0], "时干": h[0], "年柱": y, "日柱": d})
    pts, cusps, asc, mc, day = ca.compute(t, lon, lat, tz, hsys)
    for b in BODIES:
        if b in pts:
            row[f"{b}宫"] = pts[b]["house"]
            row[f"{b}座"] = ca.SIGNS[pts[b]["sign"]]
    row["上升座"] = ca.SIGNS[int(asc // 30)]
    row["天顶座"] = ca.SIGNS[int(mc // 30)]
    row["日夜盘"] = "日盘" if day else "夜盘"
    lon_ = {b: pts[b]["lon"] for b in BODIES if b in pts}
    for i, a in enumerate(BODIES):
        for b in BODIES[i + 1:]:
            val = "无"
            if a in lon_ and b in lon_:
                gap = abs(lon_[a] - lon_[b]) % 360
                gap = min(gap, 360 - gap)
                for nm, _sym, ang, orb, _col in ca.ASPECTS:
                    if abs(gap - ang) <= orb:
                        val = nm
                        break
            row[f"相位_{a}_{b}"] = val
    ph = (pts["月亮"]["lon"] - pts["太阳"]["lon"]) % 360
    row["月相"] = PHASES[int((ph + 22.5) // 45) % 8]
    return row


def build_dataset(y0, y1, lon=116.4, lat=39.9, tz=8, hsys="Placidus", progress=None):
    """y0~y1 年(含)内, 每天 12 个时辰各取一个时刻(xx:30; 子时取 0:30, 不含晚子时)。按时间排序。"""
    rows, d, end = [], date(y0, 1, 1), date(y1, 12, 31)
    total = (end - d).days + 1
    i = 0
    while d <= end:
        for z_hour in range(0, 24, 2):
            rows.append(row_for(datetime(d.year, d.month, d.day, z_hour, 30), lon, lat, tz, hsys))
        d += timedelta(days=1)
        i += 1
        if progress and i % 50 == 0:
            progress(i / total)
    return pd.DataFrame(rows)


# ---------------- 条件与统计 ----------------
def make_mask(df, conds):
    """conds: [(天体, '宫'|'座', 值), ...] 全部满足(且)。"""
    m = np.ones(len(df), dtype=bool)
    for body, kind, val in conds:
        col = f"{body}{kind}"
        m &= (df[col].astype(str) == str(val)).to_numpy()
    return m


def cond_text(conds):
    return " 且 ".join(f"{b}在{'第'+str(v)+'宫' if k == '宫' else v+'座'}" for b, k, v in conds) or "全部"


def lift_table(df, mask, col):
    """某个八字特征: 每个取值 条件内占比 / 总体占比 / 倍数 / 标准化偏差(大约 |z|>3 才算明显)。"""
    n, n1 = len(df), int(mask.sum())
    tot = df[col].value_counts()
    sel = df.loc[mask, col].value_counts().reindex(tot.index).fillna(0)
    p = tot / n
    exp = n1 * p
    z = (sel - exp) / np.sqrt(np.maximum(exp * (1 - p), 1e-9))
    out = pd.DataFrame({"取值": tot.index, "条件内次数": sel.values.astype(int),
                        "条件内占比": (sel / max(n1, 1)).values, "总体占比": p.values,
                        "倍数": ((sel / max(n1, 1)) / p).values, "偏差z": z.values})
    return out.sort_values("偏差z", key=lambda s: -s.abs()).reset_index(drop=True)


def cramers_v(mask, codes, k):
    """二分类(条件内/外) 对 k 类特征的 Cramér's V。codes 是 0..k-1 的整数数组。"""
    n = len(codes)
    n1 = int(mask.sum())
    if n1 == 0 or n1 == n:
        return 0.0
    tot = np.bincount(codes, minlength=k).astype(float)
    a = np.bincount(codes[mask], minlength=k).astype(float)
    e1, e0 = n1 * tot / n, (n - n1) * tot / n
    ok = tot > 0
    chi = (((a - e1) ** 2 / np.where(e1 > 0, e1, 1))[ok].sum()
           + (((tot - a) - e0) ** 2 / np.where(e0 > 0, e0, 1))[ok].sum())
    return float(np.sqrt(chi / n))


def encode(df, cols):
    out = {}
    for c in cols:
        codes, uniq = pd.factorize(df[c].astype(str))
        out[c] = (codes, len(uniq))
    return out


def roll_null(mask, codes, k, n_perm=100, seed=0):
    """把条件标记沿时间轴随机平移 n_perm 次(每次平移整数天, 一天 12 行), 返回每次的 V。
    整天平移保留了"一天之内的时辰结构"和"条件在时间上成片出现"的特点, 只打乱日期和八字的对应。"""
    rng = np.random.default_rng(seed)
    days = len(mask) // 12
    lo = min(60, max(days // 4, 1))                      # 至少平移约 60 天
    hi = max(days - lo, lo + 1)
    shifts = rng.integers(lo, hi, size=n_perm) * 12
    return np.array([cramers_v(np.roll(mask, int(s)), codes, k) for s in shifts])


def feature_summary(df, mask, cols=None, n_perm=100):
    """每个八字特征: V、整天平移基线的 95%/99% 分位数、是否超出 99% 基线、一句话解读。"""
    cols = cols or BAZI_COLS
    enc = encode(df, cols)
    rows = []
    for c in cols:
        codes, k = enc[c]
        v = cramers_v(mask, codes, k)
        nul = roll_null(mask, codes, k, n_perm)
        q95, q99 = np.quantile(nul, [.95, .99])
        rows.append({"八字特征": c, "V": v, "基线95%": q95, "基线99%": q99,
                     "V/基线99%": v / q99 if q99 > 0 else np.inf, "超出基线": v > q99,
                     "解读": ("明显超出基线: 和日期有关" if v > q99 else
                            ("有关系, 但平移日期后依然存在: 多半是一天之内时刻的结构关系" if q99 >= 0.05 else
                             "和基线无差别: 看不出关系"))})
    return pd.DataFrame(rows).sort_values("V/基线99%", ascending=False).reset_index(drop=True)


def scan(df, cols=None, bodies=None, kinds=("宫", "座")):
    """扫描所有 星体×宫位(或星座) 单条件, 每个条件对每个八字特征算 V。只返回 V 的表(不含基线, 基线用 feature_summary 再验证)。"""
    cols = cols or BAZI_COLS
    enc = encode(df, cols)
    rows = []
    for b in bodies or BODIES:
        for kind in kinds:
            col = f"{b}{kind}"
            if col not in df:
                continue
            for val in sorted(df[col].astype(str).unique(), key=lambda x: (len(x), x)):
                mask = (df[col].astype(str) == val).to_numpy()
                if mask.sum() < 50:
                    continue
                for c in cols:
                    codes, k = enc[c]
                    rows.append({"条件": cond_text([(b, kind, val)]), "天体": b, "类型": kind, "值": val,
                                 "样本数": int(mask.sum()), "八字特征": c, "V": cramers_v(mask, codes, k)})
    return pd.DataFrame(rows).sort_values("V", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成 八字+星盘 对照数据(每行一个出生时刻)")
    ap.add_argument("--y0", type=int, default=1996)
    ap.add_argument("--y1", type=int, default=2025)
    ap.add_argument("--lon", type=float, default=116.4)
    ap.add_argument("--lat", type=float, default=39.9)
    ap.add_argument("--tz", type=float, default=8)
    ap.add_argument("--out", default="astro_bazi_rows.csv")
    a = ap.parse_args()
    data = build_dataset(a.y0, a.y1, a.lon, a.lat, a.tz,
                         progress=lambda p: print(f"\r进度 {p:.0%}", end="", flush=True))
    data.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"\n完成: {len(data)} 行 -> {a.out}")
