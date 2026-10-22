"""页面: 一年星象 — 星体走过的星座、宫位, 以及所有托勒密相位, 并检验其中的规律。计算在 core_year.py"""
from datetime import date, datetime, time

import pandas as pd
import streamlit as st

import core_astro as ca
import core_year as cy
from ui_common import get_birth

b = get_birth()
hsys = st.session_state.get("hsys", "Placidus")

st.write("选一年，看十个天体这一年走过哪些星座、哪些宫（宫位以侧边栏出生时间的本命盘为准，即行运过宫），"
         "以及它们彼此之间所有的合、六合、刑、拱、冲，并检验其中有哪些规律。")

c1, c2, c3 = st.columns(3)
year = c1.number_input("年份", 1900, 2100, date.today().year, step=1)
step = c2.selectbox("采样步长（小时）", [6, 12, 3], help="起止时刻最后都会精确到分钟；步长小一些不容易漏掉月亮的短相位，但更慢。")
names = c3.multiselect("天体", cy.BODIES, default=cy.BODIES)
if len(names) < 2:
    st.info("至少选两个天体。")
    st.stop()


@st.cache_data(show_spinner="正在计算这一年的星座、宫位和相位（约半分钟）…")
def run(y, stp, nat, lon, lat, tz, hs, nm):
    return cy.analyze(datetime(y, 1, 1), 366 if y % 4 == 0 else 365, stp, nat, lon, lat, tz, hs, list(nm))


R = run(int(year), step, b["dt"], b["lon"], b["lat"], b["tz"], hsys, tuple(names))
st.caption(f"{year} 年 1 月 1 日至 12 月 31 日；本命盘宫头取自 {b['dt']:%Y-%m-%d %H:%M}（{hsys}）。"
           f"共 {len(R['aspects'])} 段相位，合并逆行造成的反复进出后是 {len(R['episodes'])} 轮。")


def fmt(df):
    df = df.copy()
    for c in ("开始", "结束", "最接近精确", "时刻"):
        if c in df:
            df[c] = pd.to_datetime(df[c]).dt.strftime("%m-%d %H:%M")
    return df


tabs = st.tabs(["规律（自动归纳）", "星座", "宫位", "相位", "理论预期对照"])

with tabs[0]:
    for o in R["obs"]:
        st.markdown("- " + o)
    st.markdown("**换座与换宫次数**")
    st.dataframe(R["motion"], hide_index=True, use_container_width=True)
    ep = R["episodes"]
    if len(ep):
        ep2 = ep.assign(月=pd.to_datetime(ep["最接近精确"]).dt.month)
        st.markdown("**每月相位轮数（按最接近精确的月份）**")
        st.bar_chart(ep2.groupby("月").size())
        pair = ep.groupby(["天体A", "天体B"]).size().unstack(fill_value=0)
        st.markdown("**每一对天体这一年共有几轮相位**")
        st.dataframe(pair, use_container_width=True)
    st.caption("这些都是天体轨道周期的几何结果：快的天体（月亮、水星、金星、太阳）相位多而短，慢的天体（木星以外）相位少而长，"
               "逆行会让同一个相位在几个月里精确三次。")

with tabs[1]:
    focus = st.selectbox("星座时间轴", ["全部"] + R["use"])
    rows = []
    for n in R["use"]:
        if focus in ("全部", n):
            for _, r in R["seg_sign"][n].iterrows():
                rows.append({"行": n, "开始": r["开始"], "结束": r["结束"], "内容": r["值"]})
    g = pd.DataFrame(rows)
    try:
        import altair as alt
        zoom = alt.selection_interval(bind="scales", encodings=["x"])
        base = alt.Chart(g).encode(y=alt.Y("行:N", sort=R["use"], title=None), x=alt.X("开始:T", title=None), x2="结束:T",
                                   color=alt.Color("内容:N", legend=None), tooltip=["行", "内容", "开始", "结束"])
        gt = g[(g["结束"] - g["开始"]).dt.days >= 12]
        txt = alt.Chart(gt).mark_text(align="left", dx=3, color="white", fontSize=11).encode(
            y=alt.Y("行:N", sort=R["use"]), x="开始:T", text="内容:N")
        st.altair_chart((base.mark_bar(size=16) + txt).add_params(zoom).properties(height=26 * g["行"].nunique() + 30),
                        use_container_width=True)
    except ImportError:
        st.dataframe(fmt(g), hide_index=True)
    st.markdown("**进入新星座的时刻**")
    st.dataframe(fmt(R["signs"]), hide_index=True, use_container_width=True)

with tabs[2]:
    rows = []
    for n in R["use"]:
        for _, r in R["seg_house"][n].iterrows():
            rows.append({"行": n, "开始": r["开始"], "结束": r["结束"], "内容": f"{r['值']}宫"})
    g = pd.DataFrame(rows)
    try:
        import altair as alt
        zoom = alt.selection_interval(bind="scales", encodings=["x"])
        base = alt.Chart(g).encode(y=alt.Y("行:N", sort=R["use"], title=None), x=alt.X("开始:T", title=None), x2="结束:T",
                                   color=alt.Color("内容:N", legend=None), tooltip=["行", "内容", "开始", "结束"])
        gt = g[(g["结束"] - g["开始"]).dt.days >= 12]
        txt = alt.Chart(gt).mark_text(align="left", dx=3, color="white", fontSize=11).encode(
            y=alt.Y("行:N", sort=R["use"]), x="开始:T", text="内容:N")
        st.altair_chart((base.mark_bar(size=16) + txt).add_params(zoom).properties(height=26 * len(R["use"]) + 30),
                        use_container_width=True)
    except ImportError:
        st.dataframe(fmt(g), hide_index=True)
    st.markdown("**进入新宫位的时刻**")
    st.dataframe(fmt(R["houses"]), hide_index=True, use_container_width=True)
    st.caption("宫位按本命盘的宫头划分，所以这里是行运过宫；换一个出生时间，同样的天体轨迹会落进不同的宫。")

with tabs[3]:
    f1, f2, f3 = st.columns(3)
    pk = f1.multiselect("包含这些天体", R["use"], default=[])
    kinds = sorted(R["episodes"]["相位"].unique()) if len(R["episodes"]) else []
    kk = f2.multiselect("相位类型", kinds, default=kinds)
    view = f3.radio("显示", ["合并后的轮", "每次进出"], horizontal=True)
    A = R["episodes"] if view == "合并后的轮" else R["aspects"]
    A = A[A["相位"].isin(kk)]
    if pk:
        A = A[A["天体A"].isin(pk) | A["天体B"].isin(pk)]
    st.dataframe(fmt(A), hide_index=True, use_container_width=True)
    st.download_button("下载相位表(CSV)", A.to_csv(index=False).encode("utf-8-sig"), f"aspects_{year}.csv", "text/csv")
    st.caption("“轮” = 同一对天体的同一种相位，因逆行反复进出时合并成一轮；“精确次数”是这一轮里进出的次数（逆行时常为 3）。")

with tabs[4]:
    st.write("每一对天体这一年相对走了多少圈，就该各经过合、冲各一次、六合、刑、拱各两次（正反两侧）。下表对比理论预期和实际出现的轮数；"
             "差一两轮是年初年末被截断，或者逆行把几次合并成一轮。")
    st.dataframe(R["expected"], hide_index=True, use_container_width=True)

st.info("这里的相位和过宫只是天体几何位置的记录，不用于预测吉凶；八字与星盘的对照请用“规律流水线”。")
