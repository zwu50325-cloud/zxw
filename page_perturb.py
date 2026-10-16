"""页面: 时间扰动 — 只改变一个时间单位, 看两套盘各自怎么变"""
import pandas as pd
import streamlit as st

from core_compare import UNITS, perturb
from ui_common import get_birth

b = get_birth()
st.write("只改变一个时间单位，看两套盘各自怎么变。")
unit = st.selectbox("改变的单位", list(UNITS))
n = st.slider("改变量", 1, 12, 1)
r = perturb(b["dt"], b["bazi_dt"], b["lon"], b["lat"], b["tz"], unit, n)
st.write(f"新时间：**{r['new_time']:%Y-%m-%d %H:%M}**")

c1, c2 = st.columns(2)
with c1:
    st.subheader("八字变化")
    st.write(f"变化的柱：{'、'.join(r['changed']) or '无'}")
    st.table(pd.DataFrame({"原": [x[1] for x in r["pillars"]], "新": [x[2] for x in r["pillars"]]},
                          index=[x[0] for x in r["pillars"]]))
with c2:
    st.subheader("星盘位移(度)")
    st.dataframe(pd.DataFrame(r["shifts"]), hide_index=True)
