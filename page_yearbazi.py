"""页面: 一年八字 × 相位 — 全年八字怎么变; 每一轮相位从开始到结束对应的八字。计算在 core_year.py / core_yearbazi.py"""
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import core_year as cy
from ui_common import get_birth

b = get_birth()
hsys = st.session_state.get("hsys", "Placidus")

st.write("先看一整年里年柱、月柱、日柱、时柱怎么换；再看每一轮相位（天体对 + 合/六合/刑/拱/冲）从开始到结束的这段时间里，"
         "八字经过了哪些柱、精确那一刻的四柱是什么。")

c1, c2, c3 = st.columns(3)
year = c1.number_input("年份", 1900, 2100, date.today().year, step=1)
step = c2.selectbox("采样步长（小时）", [12, 6], help="起止时刻最后都精确到分钟。")
names = c3.multiselect("天体", cy.BODIES, default=cy.BODIES)
if len(names) < 2:
    st.info("至少选两个天体。")
    st.stop()


@st.cache_data(show_spinner="正在计算全年八字和星象（约一两分钟）…")
def run(y, stp, nat, lon, lat, tz, hs, nm):
    return cy.analyze_with_bazi(datetime(y, 1, 1), 366 if y % 4 == 0 else 365, stp, nat, lon, lat, tz, hs, list(nm))


R = run(int(year), step, b["dt"], b["lon"], b["lat"], b["tz"], hsys, tuple(names))
E = R["ep_bazi"]


def fmt(df):
    df = df.copy()
    for c in ("开始", "结束", "最接近精确"):
        if c in df:
            df[c] = pd.to_datetime(df[c]).dt.strftime("%m-%d %H:%M")
    return df


def gantt(g, order, key="内容", min_days=0.0, h=18):
    try:
        import altair as alt
        zoom = alt.selection_interval(bind="scales", encodings=["x"])
        base = alt.Chart(g).encode(y=alt.Y("行:N", sort=order, title=None), x=alt.X("开始:T", title=None), x2="结束:T",
                                   color=alt.Color(key + ":N", legend=None), tooltip=["行", key, "开始", "结束"])
        gt = g[(g["结束"] - g["开始"]).dt.total_seconds() >= min_days * 86400]
        txt = alt.Chart(gt).mark_text(align="left", dx=3, color="white", fontSize=10).encode(
            y=alt.Y("行:N", sort=order), x="开始:T", text=key + ":N")
        st.altair_chart((base.mark_bar(size=h) + txt).add_params(zoom).properties(height=(h + 8) * len(order) + 30),
                        use_container_width=True)
    except ImportError:
        st.dataframe(fmt(g), hide_index=True)


tabs = st.tabs(["全年八字变化图", "相位对应的八字", "同一时间轴看", "统计检验"])

with tabs[0]:
    seg = R["bazi"]
    rows = []
    for n in ("年柱", "月柱", "日柱"):
        for _, r in seg[n].iterrows():
            rows.append({"行": n, "开始": r["开始"], "结束": r["结束"], "内容": r["干支"]})
    gantt(pd.DataFrame(rows), ["年柱", "月柱", "日柱"], min_days=3, h=22)
    st.caption(f"{year} 年共 {len(seg['月柱'])} 段月柱（换月柱的时刻就是节令）、{len(seg['日柱'])} 个日柱、{len(seg['时柱'])} 个时柱。"
               "可以用鼠标或手指缩放、拖动时间轴；日柱每天一换，放大后才看得清。")
    c = st.columns(2)
    c[0].markdown("**年柱、月柱的换柱时刻（节令）**")
    ym = pd.concat([seg["年柱"].assign(柱="年柱"), seg["月柱"].assign(柱="月柱")]).sort_values("开始")
    c[0].dataframe(fmt(ym[["柱", "干支", "开始", "结束"]]), hide_index=True, use_container_width=True)
    m = c[1].selectbox("看某个月的日柱和时柱", sorted({t.month for t in seg["日柱"]["开始"]}))
    d = seg["日柱"][seg["日柱"]["开始"].dt.month == m]
    c[1].dataframe(fmt(d[["干支", "开始", "结束"]]), hide_index=True, use_container_width=True, height=300)
    day = c[1].selectbox("某一天的十二个时柱", sorted({t.date() for t in seg["时柱"]["开始"] if t.month == m}))
    h = seg["时柱"][(seg["时柱"]["开始"].dt.date == day)]
    c[1].dataframe(fmt(h[["干支", "开始", "结束"]]), hide_index=True, use_container_width=True)

with tabs[1]:
    f1, f2, f3 = st.columns(3)
    pk = f1.multiselect("包含这些天体", R["use"], default=[])
    kinds = sorted(E["相位"].unique())
    kk = f2.multiselect("相位类型", kinds, default=kinds)
    nomoon = f3.checkbox("不看月亮（月亮太多太短）", value=True)
    A = E[E["相位"].isin(kk)]
    if pk:
        A = A[A["天体A"].isin(pk) | A["天体B"].isin(pk)]
    if nomoon:
        A = A[(A["天体A"] != "月亮") & (A["天体B"] != "月亮")]
    cols = ["天体A", "相位", "天体B", "开始", "结束", "精确次数", "最接近精确", "精确时刻四柱",
            "年柱", "月柱(经过)", "日柱(经过)", "时柱(经过)", "跨月柱", "持续日数"]
    st.dataframe(fmt(A[cols]), hide_index=True, use_container_width=True)
    st.download_button("下载(CSV)", A[cols].to_csv(index=False).encode("utf-8-sig"), f"aspects_bazi_{year}.csv", "text/csv")
    st.caption("“精确时刻四柱”= 这一轮里最接近精确那一刻的年月日时；“月柱/日柱/时柱(经过)”= 从开始到结束这段时间八字依次经过的柱。"
               "慢行星的相位持续几个月，会经过一个到几个月柱；月亮的相位只有一天左右，对应一两个日柱和十几个时柱。")
    if len(A):
        st.markdown(f"共 {len(A)} 轮；其中跨月柱的 {int(A['跨月柱'].sum())} 轮，跨年柱的 {int(A['跨年柱'].sum())} 轮。")
        one = st.selectbox("看某一轮的详细对应", [f"{r['天体A']} {r['相位']} {r['天体B']}  {r['开始']:%m-%d %H:%M} → {r['结束']:%m-%d %H:%M}"
                                                  for _, r in A.iterrows()])
        r = A.iloc[[f"{x['天体A']} {x['相位']} {x['天体B']}  {x['开始']:%m-%d %H:%M} → {x['结束']:%m-%d %H:%M}" for _, x in A.iterrows()].index(one)]
        s, e = r["开始"], r["结束"]
        rows = [{"行": "相位", "开始": s, "结束": e, "内容": f"{r['相位']} 偏差{r['最小偏差(度)']}°"}]
        for n in ("月柱", "日柱", "时柱"):
            sg = R["bazi"][n]
            for _, q in sg[(sg["开始"] < e) & (sg["结束"] > s)].iterrows():
                rows.append({"行": n, "开始": max(q["开始"], s), "结束": min(q["结束"], e), "内容": q["干支"]})
        g = pd.DataFrame(rows)
        gantt(g, ["相位", "月柱", "日柱", "时柱"], min_days=0.2 if (e - s).days > 5 else 0.0, h=20)
        st.markdown(f"精确时刻：**{r['最接近精确']:%Y-%m-%d %H:%M}**，四柱 **{r['精确时刻四柱']}**。")

with tabs[2]:
    focus = st.selectbox("看哪个天体的全部相位", R["use"], index=R["use"].index("太阳") if "太阳" in R["use"] else 0)
    m0, m1 = st.slider("月份范围", 1, 12, (1, 3))
    lo = datetime(int(year), m0, 1)
    hi = datetime(int(year) + (m1 == 12), 1 if m1 == 12 else m1 + 1, 1)
    asp = E[((E["天体A"] == focus) | (E["天体B"] == focus)) & (E["结束"] > lo) & (E["开始"] < hi)]
    rows, order = [], ["月柱", "日柱"]
    for n in ("月柱", "日柱"):
        for _, q in R["bazi"][n][(R["bazi"][n]["结束"] > lo) & (R["bazi"][n]["开始"] < hi)].iterrows():
            rows.append({"行": n, "开始": max(q["开始"], lo), "结束": min(q["结束"], hi), "内容": q["干支"]})
    for _, q in asp.iterrows():
        o = q["天体B"] if q["天体A"] == focus else q["天体A"]
        lab = f"{o} {q['相位']}"
        if lab not in order:
            order.append(lab)
        rows.append({"行": lab, "开始": max(q["开始"], lo), "结束": min(q["结束"], hi), "内容": q["精确时刻四柱"].split()[2]})
    gantt(pd.DataFrame(rows), order, min_days=1.5, h=14)
    st.caption("上两行是月柱、日柱；下面每一行是 " + focus + " 和另一个天体的某种相位，条里写的是该相位最接近精确那天的日柱。"
               "时间范围太长时日柱会很密，建议选 1 到 3 个月；月亮的相位只有一天左右，请换成其他天体看。")

with tabs[3]:
    st.markdown("**相位的起止时刻，离最近的“换时柱/换日柱”时刻有多远？**")
    st.dataframe(R["edge"], hide_index=True, use_container_width=True)
    st.caption("如果相位的开始/结束和换柱时刻有对应，平均距离会明显小于随机时刻；“差”落在标准误的两三倍之内，说明没有对应。"
               "换时柱每 120 分钟一次，随机平均约 30 分钟。")
    st.markdown("**相位特征和精确时刻的八字特征有关联吗？**")
    st.dataframe(R["assoc"], hide_index=True, use_container_width=True)
    st.caption("V 是校正后的 Cramér's V，“随机99%上限”是把八字特征随机打乱 200 次的上限；V 没有超过上限，就是和随机无异。"
               "一年的样本只有一千多轮，结论只针对这一年；这里一共检验 12 项，偶尔有一项碰巧超过上限不奇怪，要换几个年份看是否每年都超过才算数。")

st.info("八字和星盘都是出生时间的确定函数，没有因果；这里对照的是两种历法在同一段时间里的变化，不用于吉凶或命运判断。")
