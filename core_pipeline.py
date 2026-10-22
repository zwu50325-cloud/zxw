"""规律发现流水线(纯计算, 不依赖 Streamlit): 发现 → 复验 → 解释 → 登记 → 报告

把已有的数据生成(core_conditions)和关联扫描(core_discovery)串成一条可以反复跑的流水线:
  1. 拆分: 按年份把数据分成"发现集"(前半)和"验证集"(后半)。规律只在发现集里找, 在验证集里复验;
  2. 发现: 在发现集上做全面关联扫描(含分层控制、平移基线、变化段数);
  3. 复验: 对关联最强的那些, 在验证集上重算 V, 判断"复现 / 减弱 / 未复现";
  4. 解释: 用"天文与历法对应库"给已知的结构关系配上原因, 没有命中的标为待查;
  5. 登记: 每次运行的结果追加进登记表, 以后多次运行里反复出现的才算数;
  6. 报告: 生成一份 Markdown 报告, 也可以把摘要交给 AI 写成更完整的解读。
命令行: python core_pipeline.py --csv astro_bazi_rows.csv --out results
"""
import argparse
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

import core_discovery as cd

# ---------------- 天文与历法对应库(已知的结构关系) ----------------
SLOW = ("木星", "土星", "天王星", "海王星", "冥王星")
YEAR_F = {"年支", "年干", "年柱", "十神_年干", "十神_年支"}
MONTH_F = {"月令", "月干", "十神_月干", "十神_月支"}
HOUR_F = {"时支", "时干", "十神_时干", "十神_时支"}
DAY_F = {"日柱", "日支", "日主", "日主五行"}


def _slow_in(a):
    return any(p in a for p in SLOW)


def _rel_has(b, ch):
    """干_年月 / 支_日时 这类关系特征, 名字里的柱字是否包含 ch。"""
    return b[:2] in ("干_", "支_") and ch in b[2:]


KB = [
    (lambda a, b: a.startswith("太阳座") and (b in MONTH_F or b == "日主状态"),
     "月令按太阳在黄道上的位置分段（从黄经 315° 即立春起每 30° 一个），星座从 0° 起每 30° 一个，两者错开 15°，"
     "所以每个月支横跨两个太阳星座。"),
    (lambda a, b: (a.startswith("水星座") or a.startswith("金星座")) and b in MONTH_F,
     "水星离太阳最远约 28°、金星约 47°，它们的星座总在太阳星座附近，所以也跟着季节（月令）走。"),
    (lambda a, b: a.startswith("相位_水星_") or a.startswith("相位_金星_") and "太阳" in a,
     "水星、金星离太阳的角距有上限（约 28°、47°），所以它们和太阳之间只可能成合相。"),
    (lambda a, b: _slow_in(a) and (b in YEAR_F or _rel_has(b, "年")),
     "木星约 11.86 年、土星约 29.46 年绕天一圈，5 圈约 59.3 年、2 圈约 58.9 年，都接近 60 年干支一轮；"
     "天王星、海王星、冥王星几十年到上百年才换一次星座，在数据里只是在标记年代。"),
    (lambda a, b: (a.endswith("宫") or a in ("上升座", "天顶座", "日夜盘")) and (b in HOUR_F or _rel_has(b, "时")),
     "宫位、上升、天顶由地球自转决定，一天转一圈，所以和时辰（时支、时干）强相关；同一钟点的上升每天提前约 1°，"
     "所以又随季节（月令）变化。"),
    (lambda a, b: a in ("月相",) and b in DAY_F,
     "日柱 60 天一轮，约 2.03 个朔望月（29.53 天），同一个日柱隔 60 天，月相只差约 11.5°，每个周期往后错一点。"),
    (lambda a, b: a.startswith("相位_") and not any(x in a for x in ("月亮", "水星", "金星", "太阳", "火星")) and b in YEAR_F,
     "慢行星之间的相位由几十年一轮的轨道周期决定，数据里只相当于标记年代。"),
]


def explain(a, b):
    for pred, text in KB:
        try:
            if pred(a, b):
                return text
        except Exception:
            continue
    return ""


# ---------------- 拆分、复验 ----------------
def split_by_year(df, split_year=None):
    """前半年份 -> 发现集, 后半年份 -> 验证集。返回 (发现集, 验证集, 分界年份)。"""
    yr = df["出生时间"].astype(str).str[:4].astype(int)
    lo, hi = int(yr.min()), int(yr.max())
    cut = split_year if split_year is not None else lo + (hi - lo) // 2
    return df[yr <= cut].reset_index(drop=True), df[yr > cut].reset_index(drop=True), cut


def validate(df_val, head, strong=0.5, weak=0.02):
    """在验证集上重算 V。复现: V>=max(0.05, 发现集V*strong); 减弱: V>=weak; 否则未复现。"""
    A = sorted(set(head["星盘特征"]))
    B = sorted(set(head["八字特征"]))
    eA, eB = cd.encode(df_val, A), cd.encode(df_val, B)
    out = []
    for _, r in head.iterrows():
        a, ka = eA[r["星盘特征"]]
        b, kb = eB[r["八字特征"]]
        v = cd.v_corr(a, ka, b, kb)
        runs = cd.n_runs(a)
        if runs < cd.MIN_RUNS:
            st = "验证集样本太少"
        elif v >= max(0.05, r["V"] * strong):
            st = "复现"
        elif v >= weak:
            st = "减弱"
        else:
            st = "未复现"
        out.append({"V验证": v, "验证集变化段数": runs, "复验": st})
    return pd.DataFrame(out)


def classify(r):
    """把每个候选放进一个类别。"""
    if r["解释库"]:
        return "已知结构（有天文/历法解释）"
    j = r["判断"]
    if j.startswith("被"):
        return "被其他变量间接解释"
    if j.startswith("样本太少"):
        return "样本太少"
    if j.startswith("钟点结构"):
        return "钟点结构"
    return "★ 已复现的直接对应" if r["复验"] == "复现" else "待查：发现集有，验证集没有"


def run_pipeline(df, split_year=None, top=120, n_perm=40, progress=None):
    """返回 dict: findings(DataFrame), meta(dict), n_pairs。"""
    disc, val, cut = split_by_year(df, split_year)
    if len(disc) < 12 * 365 * 2 or len(val) < 12 * 365 * 2:
        raise ValueError(f"拆分后两边至少各要 2 年的数据（现在发现集 {len(disc)} 行、验证集 {len(val)} 行）。请加长年份范围。")
    head, allres = cd.run(disc, top=top, n_perm=n_perm, progress=(lambda p: progress(p * 0.9)) if progress else None)
    v = validate(val, head)
    f = pd.concat([head.reset_index(drop=True), v], axis=1)
    f.insert(0, "编号", range(1, len(f) + 1))
    f["解释库"] = [explain(a, b) for a, b in zip(f["星盘特征"], f["八字特征"])]
    f["类别"] = f.apply(classify, axis=1)
    f = f.rename(columns={"V": "V发现"})
    meta = {"时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "数据范围": f"{df['出生时间'].iloc[0][:4]}–{df['出生时间'].iloc[-1][:4]}",
            "发现集": f"{disc['出生时间'].iloc[0][:4]}–{cut}（{len(disc):,} 行）",
            "验证集": f"{cut + 1}–{val['出生时间'].iloc[-1][:4]}（{len(val):,} 行）",
            "扫描对数": int(len(allres)), "检验对数": int(len(f))}
    if progress:
        progress(1.0)
    return {"findings": f, "meta": meta, "n_pairs": len(allres)}


# ---------------- 登记表 ----------------
def update_registry(registry, findings, meta):
    """把本次结果追加进登记表(DataFrame 或 None), 返回新的登记表。多次运行里反复出现的才更可信。"""
    new = findings[["星盘特征", "八字特征", "V发现", "V验证", "复验", "类别"]].copy()
    new.insert(0, "运行时间", meta["时间"])
    new.insert(1, "数据范围", meta["数据范围"])
    return new if registry is None or len(registry) == 0 else pd.concat([registry, new], ignore_index=True)


def registry_summary(reg):
    """每个 (星盘特征, 八字特征) 被检验几次、复现几次。"""
    g = reg.groupby(["星盘特征", "八字特征"])
    return pd.DataFrame({"检验次数": g.size(), "复现次数": g["复验"].apply(lambda s: int((s == "复现").sum())),
                         "最近类别": g["类别"].last()}).reset_index().sort_values(["复现次数", "检验次数"], ascending=False)


# ---------------- 报告 ----------------
def report_md(res):
    f, m = res["findings"], res["meta"]
    n_star = int((f["类别"] == "★ 已复现的直接对应").sum())
    lines = [f"# 规律发现报告（{m['时间']}）", "",
             f"- 数据：{m['数据范围']}；发现集 {m['发现集']}；验证集 {m['验证集']}",
             f"- 扫描了 {m['扫描对数']:,} 对（星盘特征 × 八字特征），对关联最强的 {m['检验对数']} 对做了分层控制、平移基线和验证集复验。",
             f"- 结果分类：" + "；".join(f"{k} {v} 对" for k, v in f["类别"].value_counts().items()), ""]
    lines.append("## ★ 已复现的直接对应（需要重点解释）")
    star = f[f["类别"] == "★ 已复现的直接对应"]
    if len(star):
        for _, r in star.head(30).iterrows():
            lines.append(f"- {r['星盘特征']} ↔ {r['八字特征']}：发现集 V={r['V发现']:.3f}，验证集 V={r['V验证']:.3f}，"
                         f"该星盘特征变化 {r['变化段数']} 段")
    else:
        lines.append("- 没有。所有强关联要么已有天文/历法解释，要么被其他变量间接解释，要么样本不足，要么在验证集里消失。")
    lines += ["", "## 已知结构（有天文/历法解释）"]
    kn = f[f["类别"].str.startswith("已知结构")]
    for text, g in kn.groupby("解释库"):
        ex = "、".join(f"{a}↔{b}" for a, b in zip(g["星盘特征"].head(3), g["八字特征"].head(3)))
        lines.append(f"- {text}（{len(g)} 对，例如 {ex}）")
    lines += ["", "## 待查：发现集有、验证集没有"]
    wait = f[f["类别"].str.startswith("待查")]
    for _, r in wait.head(20).iterrows():
        lines.append(f"- {r['星盘特征']} ↔ {r['八字特征']}：发现集 V={r['V发现']:.3f}，验证集 V={r['V验证']:.3f}（{r['复验']}）")
    if not len(wait):
        lines.append("- 无")
    lines += ["", "## 说明",
              "- 八字和星盘都是出生时间的确定函数，两者没有因果，这里找到的只是历法周期与天体运动周期之间的对应。",
              "- 同时检验了很多对组合，总会有一些碰巧偏高；只有发现集和验证集都出现、并且不被其他变量解释的，才值得继续研究。",
              "- 本报告不涉及吉凶或命运的判断。"]
    return "\n".join(lines)


def summary_for_ai(res, n=40):
    """适合交给 AI 写解读的摘要(JSON 文本)。"""
    f = res["findings"]
    cols = ["编号", "星盘特征", "八字特征", "V发现", "V验证", "复验", "变化段数", "判断", "类别", "解释库"]
    rows = f[cols].head(n).round(3).to_dict("records")
    return json.dumps({"meta": res["meta"], "类别统计": f["类别"].value_counts().to_dict(), "候选": rows},
                      ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="规律发现流水线: 发现 → 复验 → 解释 → 登记 → 报告")
    ap.add_argument("--csv", required=True, help="core_conditions.py 生成的 astro_bazi_rows.csv(新版)")
    ap.add_argument("--out", default="results")
    ap.add_argument("--split-year", type=int, default=None, help="发现集到哪一年为止(默认取中间)")
    ap.add_argument("--top", type=int, default=120)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    data = pd.read_csv(a.csv)
    res = run_pipeline(data, a.split_year, a.top, progress=lambda p: print(f"\r进度 {p:.0%}", end="", flush=True))
    res["findings"].to_csv(os.path.join(a.out, "findings.csv"), index=False, encoding="utf-8-sig")
    open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write(report_md(res))
    open(os.path.join(a.out, "summary_for_ai.json"), "w", encoding="utf-8").write(summary_for_ai(res))
    reg_path = os.path.join(a.out, "registry.csv")
    reg = pd.read_csv(reg_path) if os.path.exists(reg_path) else None
    update_registry(reg, res["findings"], res["meta"]).to_csv(reg_path, index=False, encoding="utf-8-sig")
    print(f"\n完成: {a.out}/findings.csv、report.md、summary_for_ai.json、registry.csv")
    print(report_md(res)[:2500])
