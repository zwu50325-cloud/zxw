"""页面: 星盘(爱星盘风格)。只负责显示, 计算在 core_astro.py"""
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core_astro import HSYS, build_chart
from ui_common import get_birth

b = get_birth()
hs = st.selectbox("宫位制", list(HSYS), key="hsys")


@st.cache_data(show_spinner=False)
def load(dt, lon, lat, tz, hsys):
    return build_chart(dt, lon, lat, tz, hsys)


ch = load(b["dt"], b["lon"], b["lat"], b["tz"], hs)

components.html(
    f'<div style="background:#fff;color:#222;border-radius:12px;padding:6px">{ch["svg"]}</div>',
    height=720, scrolling=False)

f = ch["facts"]
st.markdown(
    f"**日夜盘**：{'日盘' if f['day'] else '夜盘'}　**月相**：{f['phase']}（日月夹角 {f['angle']:.1f}°）  \n"
    f"**四元素**：" + "　".join(f"{k}{v}" for k, v in f["elements"].items()) +
    "　**三模式**：" + "　".join(f"{k}{v}" for k, v in f["modes"].items()))

st.subheader("行星位置")
st.dataframe(pd.DataFrame(ch["planets"]), hide_index=True)

st.subheader("宫位")
st.dataframe(pd.DataFrame(ch["houses"]), hide_index=True)

st.subheader("相位表")
g = ch["aspect_grid"]
grid = pd.DataFrame("", index=g["names"], columns=g["names"])
for (row, col), txt in g["cells"].items():
    grid.loc[row, col] = txt
st.dataframe(grid)
st.caption("容许度：合/冲 8°，刑/拱 7°，六合 5°。表中显示精确度偏差。")
st.write(f"共 {len(ch['aspect_rows'])} 个相位。")
st.dataframe(pd.DataFrame(ch["aspect_rows"]), hide_index=True)
