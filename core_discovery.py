"""规律发现: 星盘特征 × 八字特征 全面关联扫描(纯计算, 不依赖 Streamlit)

对 core_conditions.build_dataset 生成的表(每行 = 一个出生时刻, 同时有八字特征和星盘特征):
  1. 对每一对 (星盘特征, 八字特征) 算 Cramér's V(已做小样本偏差校正), 0 = 无关, 1 = 完全对应;
  2. 对关联最强的那些, 再做三件事, 判断这个关联"是不是真的直接对应":
     a. 分层控制: 在"同一年柱 / 同一月支 / 同一时支 / 同一月支+时支"里分别重算 V, 如果控制某个变量后 V 大幅下降,
        说明两者的关联是通过这个变量间接产生的(例如两者都随季节变化);
     b. 整日平移基线: 把星盘特征沿时间轴平移整数天, 重算 V, 若 V 几乎不变, 说明关联只来自"一天之内钟点"的结构;
     c. 数该星盘特征在数据里变化了多少段(慢行星几十年才换一次星座, 样本再多也只相当于几十个独立样本);
     d. 给出判断标签。
两套体系都是"出生时间"的确定函数, 它们之间没有因果, 这里找的是"周期和历法的对应关系"。
命令行: python core_discovery.py --csv astro_bazi_rows.csv --out discovery.csv
"""
import argparse
from math import sqrt

import numpy as np
import pandas as pd

import core_conditions as cc

ASTRO = cc.ASTRO_COLS + cc.ASTRO_EXTRA
BAZI = cc.BAZI_COLS + cc.BAZI_EXTRA
# 控制变量: 名称 -> 用来分层的列
CONTROLS = {"年柱": ["年柱"], "月支": ["月令"], "时支": ["时支"], "月支+时支": ["月令", "时支"]}
# 八字特征本身就由控制变量决定时, 不做这个控制(否则 V 必然变 0, 没有意义)
_YEAR = {"年支", "年干", "年柱", "十神_年干", "十神_年支"}
_MONTH = {"月令", "月干", "十神_月干", "十神_月支"}
_HOUR = {"时支", "时干", "十神_时干", "十神_时支"}
SAME_SOURCE = {"年柱": _YEAR, "月支": _MONTH, "时支": _HOUR, "月支+时支": _MONTH | _HOUR}


def encode(df, cols):
    out = {}
    for c in cols:
        codes, uniq = pd.factorize(df[c].astype(str))
        out[c] = (codes.astype(np.int64), len(uniq))
    return out


def v_corr(a, ka, b, kb):
    """Cramér's V(Bergsma 偏差校正)。a、b 是 0..k-1 的整数编码。"""
    n = len(a)
    if ka < 2 or kb < 2 or n < 3:
        return 0.0
    tab = np.bincount(a * kb + b, minlength=ka * kb).reshape(ka, kb).astype(float)
    exp = tab.sum(1, keepdims=True) @ tab.sum(0, keepdims=True) / n
    ok = exp > 0
    phi2 = (((tab - exp) ** 2) / np.where(ok, exp, 1))[ok].sum() / n
    phi2c = max(0.0, phi2 - (ka - 1) * (kb - 1) / (n - 1))
    kac, kbc = ka - (ka - 1) ** 2 / (n - 1), kb - (kb - 1) ** 2 / (n - 1)
    d = min(kac - 1, kbc - 1)
    return sqrt(phi2c / d) if d > 0 else 0.0


def strata(df, cols, min_n=40):
    """按 cols 分层, 返回样本数 >= min_n 的各层的行下标数组。"""
    key = df[cols].astype(str).agg("|".join, axis=1) if len(cols) > 1 else df[cols[0]].astype(str)
    codes, _ = pd.factorize(key)
    order = np.argsort(codes, kind="stable")
    cuts = np.flatnonzero(np.diff(codes[order])) + 1
    return [g for g in np.split(order, cuts) if len(g) >= min_n]


def controlled_v(a, ka, b, kb, groups):
    tot = w = 0
    for g in groups:
        tot += v_corr(a[g], ka, b[g], kb) * len(g)
        w += len(g)
    return tot / w if w else float("nan")


def roll_null_v(a, ka, b, kb, n_perm=40, seed=0):
    """把星盘特征沿时间轴平移整数天(一天 12 行), 重算 V。返回每次的 V。"""
    rng = np.random.default_rng(seed)
    days = len(a) // 12
    lo = min(60, max(days // 4, 1))
    shifts = rng.integers(lo, max(days - lo, lo + 1), size=n_perm) * 12
    return np.array([v_corr(np.roll(a, int(s)), ka, b, kb) for s in shifts])


MIN_RUNS = 100  # 星盘特征在数据里至少要变化这么多次, 结论才有统计意义


def n_runs(a):
    """沿时间轴, 这个特征的取值变化了多少段(= 有效独立样本数的粗略估计)。"""
    return int(1 + (np.diff(a) != 0).sum())


def label(v, ctrl, null99, runs):
    """根据控制结果、变化次数和平移基线给出一句话判断。"""
    explained = [k for k, x in ctrl.items() if x == x and x <= v / 3]
    if explained:
        return "被" + "、".join(explained) + "解释（间接相关）"
    if runs < MIN_RUNS:
        return f"样本太少（该星盘特征在数据里只变化了 {runs} 段，V 很大也不能当作规律）"
    if null99 == null99 and v <= null99 * 1.1:
        return "钟点结构（平移整日后依然存在）"
    return "日期层面的直接对应（重点）"


def run(df, astro_cols=None, bazi_cols=None, top=120, n_perm=40, min_v=0.02, progress=None):
    """返回 DataFrame: 星盘特征, 八字特征, V, 控制后的 V(各控制变量), 平移基线, 判断。按 V 从大到小。"""
    A = [c for c in (astro_cols or ASTRO) if c in df]
    B = [c for c in (bazi_cols or BAZI) if c in df]
    encA, encB = encode(df, A), encode(df, B)
    rows = []
    for i, a in enumerate(A):
        ca_, ka = encA[a]
        for b in B:
            cb_, kb = encB[b]
            rows.append({"星盘特征": a, "八字特征": b, "V": v_corr(ca_, ka, cb_, kb)})
        if progress:
            progress((i + 1) / len(A) * 0.6)
    res = pd.DataFrame(rows).sort_values("V", ascending=False).reset_index(drop=True)
    head = res[res["V"] >= min_v].head(top).copy()
    groups = {k: strata(df, cols) for k, cols in CONTROLS.items()}
    extra = []
    for j, (_, r) in enumerate(head.iterrows()):
        ca_, ka = encA[r["星盘特征"]]
        cb_, kb = encB[r["八字特征"]]
        ctrl = {}
        for k in CONTROLS:
            ctrl[k] = float("nan") if r["八字特征"] in SAME_SOURCE[k] else controlled_v(ca_, ka, cb_, kb, groups[k])
        nul = roll_null_v(ca_, ka, cb_, kb, n_perm)
        null99 = float(np.quantile(nul, .99))
        runs = n_runs(ca_)
        extra.append({"变化段数": runs, **{f"控制{k}后V": ctrl[k] for k in CONTROLS}, "平移基线99%": null99,
                      "判断": label(r["V"], ctrl, null99, runs)})
        if progress:
            progress(0.6 + (j + 1) / max(len(head), 1) * 0.4)
    head = pd.concat([head.reset_index(drop=True), pd.DataFrame(extra)], axis=1)
    return head, res


def crosstab(df, a, b):
    """astro 特征 a(行) × 八字特征 b(列) 的行内占比(%)。"""
    ct = pd.crosstab(df[a].astype(str), df[b].astype(str), normalize="index") * 100
    return ct.round(0).astype(int)


def summary_text(head, n=40):
    """适合复制给别人看的摘要。"""
    lines = []
    for _, r in head.head(n).iterrows():
        c = " ".join(f"{k}={r[f'控制{k}后V']:.2f}" for k in CONTROLS if r[f"控制{k}后V"] == r[f"控制{k}后V"])
        lines.append(f"{r['星盘特征']} ↔ {r['八字特征']} | V={r['V']:.3f} | 变化段数={r['变化段数']} | {r['判断']} | 控制后: {c} | 平移基线99%={r['平移基线99%']:.3f}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="星盘特征 × 八字特征 规律发现")
    ap.add_argument("--csv", required=True, help="core_conditions.py 生成的 astro_bazi_rows.csv(需要是新版, 含相位和月相列)")
    ap.add_argument("--out", default="discovery.csv")
    ap.add_argument("--top", type=int, default=120)
    a = ap.parse_args()
    data = pd.read_csv(a.csv)
    head, allres = run(data, top=a.top, progress=lambda p: print(f"\r进度 {p:.0%}", end="", flush=True))
    head.to_csv(a.out, index=False, encoding="utf-8-sig")
    allres.to_csv(a.out.replace(".csv", "_all.csv"), index=False, encoding="utf-8-sig")
    print(f"\n完成 -> {a.out}（前 {len(head)} 对）和 {a.out.replace('.csv', '_all.csv')}（全部）")
    print(summary_text(head, 30))
