"""一年里的星象: 星体走过的星座、宫位, 以及星体之间所有托勒密相位(纯计算, 不依赖 Streamlit)

  - 星座: 每个天体什么时候换星座(含逆行退回); 
  - 宫位: 以一张固定的本命盘的宫头为准(行运过宫), 每个天体什么时候进入哪一宫;
  - 相位: 合、六合、刑、拱、冲 五种托勒密相位, 每一对天体的每一轮: 进入/离开容许度的时刻和最接近精确的时刻;
  - 规律检验: 相位"轮数"和理论预期(相对运动圈数)对照、逆行造成的三次精确、不可能出现的相位等。
起止时刻先按步长采样, 再二分到分钟。复用 core_timeline 的函数。
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import core_astro as ca
import core_timeline as ct

BODIES = ca.MAIN
ANG_NAME = {nm: ang for nm, sym, ang, orb in ct.ASP}


class NatalChart(ct.Chart):
    """天体位置随时间算, 宫位固定用本命盘的宫头。"""

    def __init__(self, lon, lat, tz, hsys, cusps):
        super().__init__(lon, lat, tz, hsys)
        self.cusps = cusps
        self._done = set()

    def at(self, t):
        pts = super().at(t)
        if t not in self._done:
            for p in pts.values():
                p["house"] = ca.house_of(p["lon"], self.cusps)
            self._done.add(t)
        return pts


def sample_year(start, end, step_h, ch, names):
    times, lons, houses = [], {n: [] for n in names}, {n: [] for n in names}
    t = start
    while t < end:
        pts = ch.at(t)
        times.append(t)
        for n in names:
            lons[n].append(pts[n]["lon"])
            houses[n].append(pts[n]["house"])
        t += timedelta(hours=step_h)
    return {"t": times, "pil": [None] * len(times), "lon": {n: np.array(v) for n, v in lons.items()},
            "house": {n: np.array(v) for n, v in houses.items()}, "chart": ch,
            "start": start, "end": end, "step": step_h * 60, "names": list(names)}


DEV_MAX = 22   # 两次精确之间偏离目标角度超过这个度数, 就不是同一次逆行来回, 而是新的一轮


def episodes(asp, S):
    """把同一对天体、同一种相位的多段合成"一轮": 只合并因逆行而在目标角度附近来回进出的。
    判据: 两次精确之间, 两天体的夹角偏离目标角度始终不超过 DEV_MAX 度。"""
    cols = ["天体A", "相位", "天体B", "开始", "结束", "精确次数", "最小偏差(度)", "最接近精确"]
    if not len(asp):
        return pd.DataFrame(columns=cols)
    step_s, n = S["step"] * 60.0, len(S["t"])
    idx = lambda t: min(max(int(round((t - S["t"][0]).total_seconds() / step_s)), 0), n - 1)

    def max_dev(a, b, ang, t1, t2):
        i, j = sorted((idx(t1), idx(t2)))
        d = np.abs(S["lon"][a][i:j + 1] - S["lon"][b][i:j + 1]) % 360
        d = np.minimum(d, 360 - d)
        return float(np.abs(d - ang).max())

    rows = []
    for (a, p, b), g in asp.sort_values("最接近精确").groupby(["天体A", "相位", "天体B"]):
        ang = ANG_NAME[p.split(" ", 1)[1]]
        no_merge = "太阳" in (a, b) and bool({a, b} & {"水星", "金星"})
        cur = None
        for _, r in g.iterrows():
            if cur is not None and not no_merge and max_dev(a, b, ang, cur["_last"], r["最接近精确"]) <= DEV_MAX:
                cur["开始"], cur["结束"] = min(cur["开始"], r["开始"]), max(cur["结束"], r["结束"])
                cur["精确次数"] += 1
                cur["_last"] = r["最接近精确"]
                if r["最小偏差(度)"] < cur["最小偏差(度)"]:
                    cur["最小偏差(度)"], cur["最接近精确"] = r["最小偏差(度)"], r["最接近精确"]
            else:
                if cur is not None:
                    rows.append(cur)
                cur = {"天体A": a, "相位": p, "天体B": b, "开始": r["开始"], "结束": r["结束"], "精确次数": 1,
                       "最小偏差(度)": r["最小偏差(度)"], "最接近精确": r["最接近精确"], "_last": r["最接近精确"]}
        rows.append(cur)
    return pd.DataFrame(rows).drop(columns="_last").sort_values("开始").reset_index(drop=True)


def expected_table(S, names, ep):
    """每一对天体: 这一年相对走了多少圈 -> 每种相位理论上该出现几轮, 和实际对比。"""
    rows = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            rel = S["lon"][a] - S["lon"][b]
            step = (np.diff(rel) + 180) % 360 - 180
            cyc = float(step.sum()) / 360                 # 净相对圈数(有符号)
            tot = float(np.abs(step).sum()) / 360         # 含逆行来回的总路程
            row = {"天体A": a, "天体B": b, "相对净圈数": round(cyc, 2), "相对总路程(圈)": round(tot, 2)}
            for nm, sym, ang, orb in ct.ASP:
                exp = abs(cyc) * (1 if ang in (0, 180) else 2)
                n_ep = int(((ep["天体A"] == a) & (ep["天体B"] == b) & (ep["相位"] == f"{sym} {nm}")).sum()) if len(ep) else 0
                row[f"{nm}·预期"] = round(exp, 1)
                row[f"{nm}·实际"] = n_ep
            rows.append(row)
    return pd.DataFrame(rows)


def observations(R):
    """自动归纳几条规律(都是可验证的陈述)。"""
    S, names, ep, asp = R["S"], R["use"], R["episodes"], R["aspects"]
    out = []
    n_sign = {n: len(R["seg_sign"][n]) - 1 for n in names}
    stay = [n for n in names if n_sign[n] == 0]
    if stay:
        out.append(f"这一年里始终没有换星座的：{'、'.join(stay)}。换座次数从多到少："
                   + "，".join(f"{n} {n_sign[n]}" for n in sorted(names, key=lambda x: -n_sign[x])) + "。")
    retro = []
    for n in names:
        step = (np.diff(S["lon"][n]) + 180) % 360 - 180
        if (step < 0).any():
            retro.append(f"{n} 逆行约 {round(float((step < 0).sum()) * S['step'] / 1440)} 天")
    if retro:
        out.append("逆行：" + "；".join(retro) + "。")
    multi = ep[ep["精确次数"] > 1] if len(ep) else ep
    if len(multi):
        top = multi["天体A"].str.cat(multi["天体B"], sep="-").value_counts().head(4)
        out.append(f"有 {len(multi)} 轮相位因为逆行而反复进出（同一轮里精确了 2 次以上），"
                   f"最多的天体对：{'、'.join(f'{k}（{v} 轮）' for k, v in top.items())}。")
    if len(ep):
        cnt = ep.groupby("天体A").size().add(ep.groupby("天体B").size(), fill_value=0).astype(int).sort_values(ascending=False)
        out.append("参与相位轮数最多的天体：" + "、".join(f"{k} {v}" for k, v in cnt.head(4).items())
                   + "；最少：" + "、".join(f"{k} {v}" for k, v in cnt.tail(3).items()) + "。")
        pair_kinds = set(zip(ep["天体A"], ep["天体B"], ep["相位"]))
        for x, y in (("水星", "太阳"), ("金星", "太阳")):
            if x in names and y in names:
                ks = {p for a, b, p in pair_kinds if {a, b} == {x, y}}
                out.append(f"{x}与{y}这一年出现的相位只有：{'、'.join(sorted(ks)) or '无'}"
                           f"（{x}离太阳最远约 {28 if x == '水星' else 47}°，所以只能成合，成不了刑/拱/冲）。")
        mo = ep[(ep["天体A"] == "月亮") | (ep["天体B"] == "月亮")]
        if len(mo):
            out.append(f"月亮约 27.3 天绕一圈，一年里和每个天体的每种相位都出现十几次，共 {len(mo)} 轮，占全部相位轮数的 {len(mo) / len(ep):.0%}。")
    return out


def analyze(start, days, step_h, natal_dt, lon, lat, tz, hsys, names):
    cusps = ca.compute(natal_dt, lon, lat, tz, hsys)[1]
    ch = NatalChart(lon, lat, tz, hsys, cusps)
    end = start + timedelta(days=days)
    names = list(names)
    S = sample_year(start, end, step_h, ch, names)
    R = {"S": S, "use": names, "cusps": cusps,
         "seg_sign": {n: ct._segments(S, n, "sign") for n in names},
         "seg_house": {n: ct._segments(S, n, "house") for n in names},
         "aspects": ct.aspect_events(S, names)}
    R["signs"] = ct.sign_events(R["seg_sign"])
    hs = []
    for n, seg in R["seg_house"].items():
        for _, r in seg.iloc[1:].iterrows():
            hs.append({"天体": n, "时刻": r["开始"], "进入": f"{r['值']}宫"})
    R["houses"] = pd.DataFrame(hs, columns=["天体", "时刻", "进入"]).sort_values("时刻").reset_index(drop=True)
    R["motion"] = ct.motion_table(S, names)
    R["episodes"] = episodes(R["aspects"], S)
    R["expected"] = expected_table(S, names, R["episodes"])
    R["obs"] = observations(R)
    S["chart"] = None
    return R


def analyze_with_bazi(start, days, step_h, natal_dt, lon, lat, tz, hsys, names):
    """analyze + 全年八字区段 + 每一轮相位对应的八字 + 起止与换柱的对照 + 关联检验。"""
    import core_yearbazi as yb
    R = analyze(start, days, step_h, natal_dt, lon, lat, tz, hsys, names)
    end = start + timedelta(days=days)
    R["bazi"] = yb.year_segments(start, end)
    R["ep_bazi"] = yb.attach_bazi(R["episodes"], R["bazi"])
    R["edge"] = yb.edge_alignment(R["episodes"], R["bazi"], start, end)
    R["assoc"] = yb.association(R["ep_bazi"])
    return R
