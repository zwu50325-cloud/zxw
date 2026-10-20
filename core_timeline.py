"""同年同月、不同日时: 一段时间里星盘怎么变、八字怎么变(纯计算, 不依赖 Streamlit)

给定一个出生时间, 先找出它所在的"年柱+月柱都不变"的那一段时间(约一个月, 从上一个节令到下一个节令),
然后在这段时间里逐点算星盘和八字, 回答:
  - 八字: 日柱、时柱分别在什么时刻换(年柱、月柱整段不变)
  - 星盘: 每个相位什么时候进入容许度、什么时候离开, 最接近精确在什么时候; 每个天体什么时候换星座、换宫
  - 对照: 这段时间里各天体动了多少度; 时辰和上升星座怎么对应; 日柱和月亮怎么对应
所有"开始/结束"时刻先按步长采样找到大致位置, 再用二分法精确到分钟。
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import core_astro as ca
from core_hours import rel_features
from core_samechars import pillars_at

BODIES = ca.MAIN                       # 十个天体
AXES = ["上升", "天顶"]
ASP = [(nm, sym, ang, orb) for nm, sym, ang, orb, _ in ca.ASPECTS]
MIN = timedelta(minutes=1)
PHASES = ["新月", "盈眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"]


class Chart:
    """按需计算并缓存某个时刻的星盘位置。"""

    def __init__(self, lon, lat, tz, hsys):
        self.args = (lon, lat, tz, hsys)
        self._c = {}

    def at(self, t):
        if t not in self._c:
            self._c[t] = ca.compute(t, *self.args)[0]
        return self._c[t]


def bisect_state(f, lo, hi):
    """f(lo) != f(hi)。返回 f 的取值变成 f(hi) 的第一个整分钟时刻。"""
    base = f(lo)
    a, b = lo, hi
    while (b - a) > MIN:
        m = int((b - a).total_seconds() // 60)
        mid = a + timedelta(minutes=max(m // 2, 1))
        if f(mid) == base:
            a = mid
        else:
            b = mid
    return b


# ---------------- 年柱+月柱窗口 ----------------
def month_span(t, max_days=40):
    """t 所在的"年柱、月柱都不变"的时间段 [start, end)。返回 (start, end, 年柱, 月柱)。"""
    key = lambda x: (pillars_at(x)[0], pillars_at(x)[1])
    k0 = key(t)
    lo, hi, d = t, t, timedelta(days=1)
    for _ in range(max_days):
        if key(lo - d) != k0:
            break
        lo -= d
    for _ in range(max_days):
        if key(hi + d) != k0:
            break
        hi += d
    start = bisect_state(key, lo - d, lo)
    end = bisect_state(key, hi, hi + d)
    return start, end, k0[0], k0[1]


# ---------------- 采样 ----------------
def sample(start, end, step_min, lon, lat, tz, hsys, names):
    """从 start 起每 step_min 分钟一个点, 到 end(不含)。"""
    ch = Chart(lon, lat, tz, hsys)
    times, pil = [], []
    lons = {n: [] for n in names}
    houses = {n: [] for n in names}
    t = start
    while t < end:
        pts = ch.at(t)
        times.append(t)
        pil.append(pillars_at(t))
        for n in names:
            lons[n].append(pts[n]["lon"])
            houses[n].append(pts[n]["house"])
        t += timedelta(minutes=step_min)
    return {"t": times, "pil": pil, "lon": {n: np.array(v) for n, v in lons.items()},
            "house": {n: np.array(v) for n, v in houses.items()}, "chart": ch,
            "start": start, "end": end, "step": step_min, "names": list(names)}


def _runs(mask):
    """布尔数组里连续为 True 的区段 [(i0, i1)] (含两端)。"""
    if not mask.any():
        return []
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def _edge(f, S, i0, i1):
    """某段 [i0,i1] 内 f 恒为真: 返回精确的 (开始, 结束, 开始是否被窗口截断, 结束是否被窗口截断)。"""
    t, n = S["t"], len(S["t"])
    s_cut, e_cut = i0 == 0, i1 == n - 1
    s = t[0] if s_cut else bisect_state(f, t[i0 - 1], t[i0])
    e = S["end"] if e_cut else bisect_state(f, t[i1], t[i1 + 1])
    return s, e, s_cut, e_cut


# ---------------- 八字: 日柱/时柱的切换 ----------------
def bazi_segments(S):
    """日柱、时柱各自的连续区段。返回 {'日柱': DataFrame, '时柱': DataFrame}(开始/结束/干支)。"""
    out = {}
    for name, idx in (("日柱", 2), ("时柱", 3)):
        vals = [p[idx] for p in S["pil"]]
        rows, i0 = [], 0
        for i in range(1, len(vals) + 1):
            if i == len(vals) or vals[i] != vals[i0]:
                f = lambda tt, idx=idx: pillars_at(tt)[idx]
                s = S["t"][0] if i0 == 0 else bisect_state(f, S["t"][i0 - 1], S["t"][i0])
                e = S["end"] if i == len(vals) else bisect_state(f, S["t"][i - 1], S["t"][i])
                rows.append({"开始": s, "结束": e, name: vals[i0]})
                i0 = i
        out[name] = pd.DataFrame(rows)
    return out


# ---------------- 星盘: 相位的起止 ----------------
def aspect_events(S, names):
    """names 里每一对天体、每种相位: 进入容许度到离开容许度的区间, 以及最接近精确的时刻。"""
    ch, t, ev = S["chart"], S["t"], []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} == set(AXES):
                continue
            d = np.abs(S["lon"][a] - S["lon"][b]) % 360
            d = np.minimum(d, 360 - d)
            for nm, sym, ang, orb in ASP:
                dev = np.abs(d - ang)
                for i0, i1 in _runs(dev <= orb):
                    def inorb(tt, a=a, b=b, ang=ang, orb=orb):
                        p = ch.at(tt)
                        x = abs(p[a]["lon"] - p[b]["lon"]) % 360
                        x = min(x, 360 - x)
                        return abs(x - ang) <= orb
                    s, e, sc, ec = _edge(inorb, S, i0, i1)
                    k = i0 + int(np.argmin(dev[i0:i1 + 1]))
                    ev.append({"天体A": a, "相位": f"{sym} {nm}", "天体B": b, "开始": s, "结束": e,
                               "持续(小时)": round((e - s).total_seconds() / 3600, 1),
                               "最接近精确": t[k], "最小偏差(度)": round(float(dev[k]), 2),
                               "开始被截断": sc, "结束被截断": ec})
    cols = ["天体A", "相位", "天体B", "开始", "结束", "持续(小时)", "最接近精确", "最小偏差(度)", "开始被截断", "结束被截断"]
    return pd.DataFrame(ev, columns=cols).sort_values("开始").reset_index(drop=True)


# ---------------- 星盘: 换座、换宫 ----------------
def _segments(S, body, kind):
    """body 的星座(kind='sign')或宫位(kind='house')的连续区段 DataFrame(开始/结束/值)。"""
    ch, t = S["chart"], S["t"]
    if kind == "sign":
        arr = (S["lon"][body] // 30).astype(int) % 12
        f = lambda tt: int(ch.at(tt)[body]["lon"] // 30) % 12
        label = lambda v: ca.SIGNS[v]
    else:
        arr = S["house"][body]
        f = lambda tt: ch.at(tt)[body]["house"]
        label = lambda v: int(v)
    rows, i0 = [], 0
    for i in range(1, len(arr) + 1):
        if i == len(arr) or arr[i] != arr[i0]:
            s = t[0] if i0 == 0 else bisect_state(f, t[i0 - 1], t[i0])
            e = S["end"] if i == len(arr) else bisect_state(f, t[i - 1], t[i])
            rows.append({"开始": s, "结束": e, "值": label(arr[i0])})
            i0 = i
    return pd.DataFrame(rows)


def sign_events(seg_sign):
    """每个天体进入新星座的时刻(第一段是窗口开始时所在的星座, 不算事件)。seg_sign: {天体: _segments(...,'sign')}"""
    rows = []
    for n, seg in seg_sign.items():
        for _, r in seg.iloc[1:].iterrows():
            rows.append({"天体": n, "时刻": r["开始"], "进入星座": r["值"]})
    return pd.DataFrame(rows, columns=["天体", "时刻", "进入星座"]).sort_values("时刻").reset_index(drop=True)


# ---------------- 对照与解释 ----------------
def motion_table(S, names):
    """这段时间里每个天体动了多少度、换了几次星座和宫位。"""
    rows = []
    for n in names:
        lon = S["lon"][n]
        step = (np.diff(lon) + 180) % 360 - 180            # 展开跨 0°/360° 的跳变
        total = float(step.sum())
        net = abs(total)
        rows.append({"天体": n, "起始": f"{ca.SIGNS[int(lon[0] // 30)]} {ca.dms(lon[0])}",
                     "结束": f"{ca.SIGNS[int(lon[-1] // 30)]} {ca.dms(lon[-1])}",
                     "净移动(度)": round(total, 1),
                     "换座次数": int((np.diff((lon // 30).astype(int) % 12) != 0).sum()),
                     "换宫次数": int((np.diff(S["house"][n]) != 0).sum()),
                     "逆行": "是" if (step < 0).any() and n not in ("上升", "天顶") else ""})
    return pd.DataFrame(rows)


def hour_vs_asc(S):
    """时支 × 上升星座: 每个时辰里上升落在各星座的占比(%)。"""
    zhi = [p[3][1] for p in S["pil"]]
    sg = [ca.SIGNS[int(x // 30) % 12] for x in S["lon"]["上升"]]
    ct = pd.crosstab(pd.Series(zhi, name="时支"), pd.Series(sg, name="上升星座"), normalize="index") * 100
    order = [z for z in "子丑寅卯辰巳午未申酉戌亥" if z in ct.index]
    cols = [s for s in ca.SIGNS if s in ct.columns]
    return ct.reindex(order)[cols].round(0).astype(int)


def hour_boundary_vs_asc(S, hour_seg, asc_seg):
    """每次时柱切换的时刻, 离最近一次上升换座有多少分钟(正=上升换座在其后)。"""
    ing = np.array([r.timestamp() for r in asc_seg["开始"].iloc[1:]])
    rows = []
    for tb in hour_seg["开始"].iloc[1:]:
        if len(ing) == 0:
            break
        diff = (ing - tb.timestamp()) / 60
        rows.append({"时柱切换时刻": tb, "离最近上升换座(分钟)": round(float(diff[np.argmin(np.abs(diff))]), 0)})
    return pd.DataFrame(rows)


def daily_summary(S):
    """每个日历日: 日柱、月亮星座(起→止)、月相、太阳度数。"""
    df = pd.DataFrame({"t": S["t"], "日柱": [p[2] for p in S["pil"]],
                       "月": S["lon"]["月亮"], "日": S["lon"]["太阳"]})
    df["日期"] = df["t"].dt.date
    rows = []
    for d, g in df.groupby("日期"):
        s0 = ca.SIGNS[int(g["月"].iloc[0] // 30) % 12]
        s1 = ca.SIGNS[int(g["月"].iloc[-1] // 30) % 12]
        mid = g.iloc[len(g) // 2]
        ph = (mid["月"] - mid["日"]) % 360
        rows.append({"日期": str(d), "日柱": "→".join(dict.fromkeys(g["日柱"])),
                     "月亮星座": s0 if s0 == s1 else f"{s0}→{s1}",
                     "月亮当日移动(度)": round(float(((g["月"].iloc[-1] - g["月"].iloc[0] + 180) % 360) - 180), 1),
                     "月相": PHASES[int((ph + 22.5) // 45) % 8],
                     "太阳": f"{ca.SIGNS[int(mid['日'] // 30) % 12]} {ca.dms(mid['日'])}"})
    return pd.DataFrame(rows)


def bazi_change_times(bz):
    """八字(日柱或时柱)发生变化的时刻, 以及其中"四柱之间的合冲刑害关系"也跟着变了的时刻。"""
    cut = sorted(set(bz["日柱"]["开始"].iloc[1:]) | set(bz["时柱"]["开始"].iloc[1:]))
    rel_t = [x for x in cut if rel_features(pillars_at(x)) != rel_features(pillars_at(x - MIN))]
    return cut, rel_t


def _nearest(ev, t):
    i = np.searchsorted(ev, t)
    lo, hi = ev[np.clip(i - 1, 0, len(ev) - 1)], ev[np.clip(i, 0, len(ev) - 1)]
    return np.minimum(np.abs(t - lo), np.abs(hi - t))


def alignment(R, cut, rel_t, n_rand=300, seed=0):
    """八字变化的时刻, 离最近一次星盘相位"进入或离开"有多少分钟? 和"把八字变化整体平移随机一段时间"相比, 是更近还是一样?
    比值 < 1 且 p 很小, 才说明两者有对齐; 比值约等于 1, p 不小, 说明对不上(只是碰巧)。"""
    S, A = R["S"], R["aspects"]
    a0, L = S["start"].timestamp() / 60, (S["end"] - S["start"]).total_seconds() / 60
    fast = {"月亮", "上升", "天顶"}
    classes = {"全部相位": A,
               "涉及月亮的相位": A[(A["天体A"] == "月亮") | (A["天体B"] == "月亮")],
               "不含月亮和上升/天顶的相位": A[~A["天体A"].isin(fast) & ~A["天体B"].isin(fast)]}
    rng = np.random.default_rng(seed)
    rows = []
    for cname, df in classes.items():
        ev = [x.timestamp() / 60 for x in df.loc[~df["开始被截断"], "开始"]] + \
             [x.timestamp() / 60 for x in df.loc[~df["结束被截断"], "结束"]]
        ev = np.sort(np.array(ev))
        for tname, times in (("日柱或时柱变化", cut), ("其中四柱关系也变化", rel_t)):
            if len(ev) < 3 or len(times) < 3:
                continue
            tt = np.array([x.timestamp() / 60 for x in times])
            obs = float(np.median(_nearest(ev, tt)))
            sims = np.array([np.median(_nearest(ev, a0 + (tt - a0 + off) % L)) for off in rng.uniform(0, L, n_rand)])
            rows.append({"八字变化": tname, "星盘事件": cname, "八字变化次数": len(tt), "星盘事件次数": len(ev),
                         "观测中位距离(分钟)": round(obs, 1), "平移后中位距离(分钟)": round(float(np.median(sims)), 1),
                         "比值": round(obs / max(float(np.median(sims)), 1e-9), 2),
                         "p(平移后更近的概率)": round(float(np.mean(sims <= obs)), 3)})
    return pd.DataFrame(rows)


def analyze(start, end, step_min, lon, lat, tz, hsys, names, axes=False):
    """一次性算完。names: 要看相位的天体; axes: 是否把上升/天顶也算进去(变化很快, 条目很多)。
    上升始终会被采样, 用来做时辰对照。"""
    use = list(names) + (AXES if axes else [])
    sample_names = list(dict.fromkeys(use + ["太阳", "月亮", "上升"]))
    S = sample(start, end, step_min, lon, lat, tz, hsys, sample_names)
    bz = bazi_segments(S)
    seg_sign = {n: _segments(S, n, "sign") for n in sample_names}
    seg_house = {n: _segments(S, n, "house") for n in use if n not in AXES}
    R = {"S": S, "use": use, "bazi_day": bz["日柱"], "bazi_hour": bz["时柱"],
         "aspects": aspect_events(S, use), "signs": sign_events({n: seg_sign[n] for n in use}),
         "seg_sign": seg_sign, "seg_house": seg_house,
         "motion": motion_table(S, sample_names), "hour_asc": hour_vs_asc(S),
         "hour_align": hour_boundary_vs_asc(S, bz["时柱"], seg_sign["上升"]), "daily": daily_summary(S)}
    R["cut"], R["rel_cut"] = bazi_change_times(bz)
    R["align"] = alignment(R, R["cut"], R["rel_cut"])
    S["chart"] = None  # 不把缓存的星盘对象带出去, 结果更小
    return R
