"""页面: 对比简表 — 八字与星盘的概览, 以及五行 vs 四元素"""
import pandas as pd
import streamlit as st

from core_compare import element_counts, features, planet_rows
from ui_common import get_birth

b = get_birth()


@st.cache_data(show_spinner=False)
def load(dt, bazi_dt, lon, lat, tz):
    return features(dt, bazi_dt, lon, lat, tz)


bazi, astro = load(b["dt"], b["bazi_dt"], b["lon"], b["lat"], b["tz"])
tab1, tab2 = st.tabs(["简表", "五行 vs 四元素"])

with tab1:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("八字")
        st.table(pd.DataFrame(
            {"年柱": [bazi["八字_年柱"], bazi["八字_十神_年干"]],
             "月柱": [bazi["八字_月柱"], bazi["八字_十神_月干"]],
             "日柱": [bazi["八字_日柱"], "日主"],
             "时柱": [bazi["八字_时柱"], bazi["八字_十神_时干"]]},
            index=["干支", "天干十神"]))
        st.write(f"日主：**{bazi['八字_日主']}**（{bazi['八字_日主五行']}）")
    with c2:
        st.subheader("星盘")
        st.dataframe(pd.DataFrame(planet_rows(astro)), hide_index=True)

with tab2:
    cnt = element_counts(bazi, astro)
    c1, c2 = st.columns(2)
    c1.subheader("八字五行（共 8 个字）")
    c1.bar_chart(pd.DataFrame({"数量": cnt["五行"]}))
    c2.subheader("星盘四元素（7 颗行星）")
    c2.bar_chart(pd.DataFrame({"数量": cnt["四元素"]}))
    st.markdown("**注意**：五行按字的属性计数，四元素按行星所在星座计数，"
                "两者的划分方式和数量基数都不同，名字相近不代表对应。")
    st.subheader("星盘相位数量")
    st.bar_chart(pd.DataFrame({"数量": cnt["相位"]}))
