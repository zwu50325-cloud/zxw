"""一年里八字怎么变, 以及每一轮相位(从开始到结束)对应的八字(纯计算, 不依赖 Streamlit)

  year_segments(start, end): 年柱、月柱、日柱、时柱各自的连续区段(换柱时刻精确到分钟)
  pillars_lookup(seg): 返回 f(t) -> 该时刻的四柱, 用区段表查询, 比重新排盘快
  attach_bazi(episodes, seg): 给 core_year.episodes 的每一轮相位加上它覆盖的八字
  edge_alignment / association: 相位的起止和换柱时刻有没有对应、相位和八字有没有关联(带随机基线)
"""
from datetime import timedelta

import numpy as np
import pandas as pd

import core_timeline as ct
from core_samechars import pillars_at

NAMES = ["年柱", "月柱", "日柱", "时柱"]


def year_segments(start, end, step_min=60):
    """返回 {柱名: DataFrame(开始, 结束, 干支)}。先每 step_min 分钟采样, 变化处二分到分钟。"""
    ts, pil = [], []
    t = start
    while t < end:
        ts.append(t)
        pil.append(pillars_at(t))
        t += timedelta(minutes=step_min)
    out = {}
    for k, name in enumerate(NAMES):
        f = lambda tt, k=k: pillars_at(tt)[k]
        rows, i0 = [], 0
        for i in range(1, len(ts) + 1):
            if i == len(ts) or pil[i][k] != pil[i0][k]:
                s = ts[0] if i0 == 0 else ct.bisect_state(f, ts[i0 - 1], ts[i0])
                e = end if i == len(ts) else ct.bisect_state(f, ts[i - 1], ts[i])
                rows.append({"开始": s, "结束": e, "干支": pil[i0][k]})
                i0 = i
        out[name] = pd.DataFrame(rows)
    return out


def pillars_lookup(seg):
    starts = {n: seg[n]["开始"].values.astype("datetime64[m]") for n in NAMES}
    vals = {n: seg[n]["干支"].values for n in NAMES}

    def at(t):
        x = np.datetime64(t, "m")
        return [vals[n][max(int(np.searchsorted(starts[n], x, side="right")) - 1, 0)] for n in NAMES]
    return at


def _between(seg_df, s, e):
    """区段表里与 [s, e] 有重叠的干支(按时间顺序)。"""
    m = (seg_df["开始"] <= e) & (seg_df["结束"] > s)
    return list(seg_df.loc[m, "干支"])


def _compact(v, limit=4):
    if len(v) <= limit:
        return "→".join(v)
    return f"{v[0]}→…→{v[-1]}（{len(v)}个）"


def attach_bazi(ep, seg):
    at = pillars_lookup(seg)
    rows = []
    for _, r in ep.iterrows():
        s, e, x = r["开始"], r["结束"], r["最接近精确"]
        span_days = (e - s).total_seconds() / 86400
        yp, mp, dp, hp = (_between(seg[n], s, e) for n in NAMES)
        ex = at(x)
        rows.append({
            "精确时刻四柱": " ".join(ex), "年柱": _compact(list(dict.fromkeys(yp))),
            "月柱(经过)": _compact(mp), "日柱(经过)": _compact(dp),
            "时柱(经过)": _compact(hp, 13) if span_days <= 2 else f"{len(hp)}个时辰",
            "跨月柱": len(mp) > 1, "跨年柱": len(set(yp)) > 1, "持续日数": round(span_days, 1),
            "_月支": ex[1][1], "_日干": ex[2][0], "_日支": ex[2][1], "_时支": ex[3][1]})
    return pd.concat([ep.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def _dist_to(times_min, edges_min):
    """每个时间(分钟数)到最近的边界(分钟数)的距离。"""
    i = np.clip(np.searchsorted(edges_min, times_min), 1, len(edges_min) - 1)
    return np.minimum(np.abs(times_min - edges_min[i - 1]), np.abs(edges_min[i] - times_min))


def edge_alignment(ep, seg, start, end, n_rand=3000, seed=0):
    """相位的开始/结束/最接近精确时刻, 距离最近的"换时柱/换日柱"时刻平均多少分钟; 对比随机时刻。"""
    rng = np.random.default_rng(seed)
    t0 = np.datetime64(start, "m")
    to_min = lambda col: ((pd.to_datetime(col).values.astype("datetime64[m]") - t0).astype(float))
    span = (np.datetime64(end, "m") - t0).astype(float)
    rows = []
    for pname in ("时柱", "日柱"):
        edges = to_min(seg[pname]["开始"])[1:]
        rand = _dist_to(rng.uniform(0, span, n_rand), edges)
        for col, lab in (("开始", "开始"), ("结束", "结束"), ("最接近精确", "最接近精确")):
            m = (ep["开始"] > start) & (ep["结束"] < end) if col != "最接近精确" else slice(None)
            d = _dist_to(to_min(ep.loc[m, col]), edges)
            rows.append({"换柱类型": pname, "相位的": lab, "样本数": len(d), "平均距离(分钟)": round(float(d.mean()), 1),
                         "随机时刻平均(分钟)": round(float(rand.mean()), 1),
                         "差(分钟)": round(float(d.mean() - rand.mean()), 1),
                         "标准误(分钟)": round(float(rand.std() / np.sqrt(max(len(d), 1))), 1)})
    return pd.DataFrame(rows)


def association(epb, n_perm=200, seed=0):
    """相位特征 × 精确时刻的八字特征 的 Cramér's V(已校正), 和打乱后的 99% 随机上限。"""
    import core_discovery as cd
    rng = np.random.default_rng(seed)
    d = epb.copy()
    d["相位种类"] = d["相位"]
    d["天体对"] = d["天体A"] + "-" + d["天体B"]
    d["涉及天体"] = np.where(d["天体A"] == "月亮", d["天体B"], d["天体A"])
    d["含月亮"] = (d["天体A"] == "月亮") | (d["天体B"] == "月亮")
    X = ["相位种类", "涉及天体", "含月亮"]
    Y = ["_月支", "_日干", "_日支", "_时支"]
    rows = []
    for x in X:
        a, ka = pd.factorize(d[x])[0], d[x].nunique()
        for y in Y:
            b, kb = pd.factorize(d[y])[0], d[y].nunique()
            v = cd.v_corr(a, ka, b, kb)
            nul = [cd.v_corr(a, ka, rng.permutation(b), kb) for _ in range(n_perm)]
            hi = float(np.quantile(nul, .99))
            rows.append({"相位特征": x, "八字特征(精确时刻)": y[1:], "V": round(v, 3), "随机99%上限": round(hi, 3),
                         "结论": "高于随机" if v > hi else "与随机无异"})
    return pd.DataFrame(rows)
