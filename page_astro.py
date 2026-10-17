"""页面: 星盘(爱星盘风格, 可操作)。只负责显示, 计算在 core_astro.py / core_wheel.py"""
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import core_wheel as cw
from core_astro import HSYS, build_chart
from ui_common import get_birth

b = get_birth()
c1, c2 = st.columns(2)
hs = c1.selectbox("宫位制", list(HSYS), key="hsys")
step = c2.selectbox("动画的时间步长（盘面前后各 60 步）", list(cw.STEPS), index=1, key="wheel_step")


@st.cache_data(show_spinner="正在计算星盘…")
def load(dt, lon, lat, tz, hsys):
    return build_chart(dt, lon, lat, tz, hsys)


@st.cache_data(show_spinner="正在计算动画帧…")
def wheel(dt, lon, lat, tz, hsys, step):
    frames = cw.make_frames(dt, lon, lat, tz, hsys, step, half=60)
    return cw.wheel_html(frames, 60, step, hsys)


ch = load(b["dt"], b["lon"], b["lat"], b["tz"], hs)

st.caption("拖动时间条或点 ▶ 播放，星体、上升和宫位会随时间移动；点击或悬停星体可高亮它的相位。")
components.html(wheel(b["dt"], b["lon"], b["lat"], b["tz"], hs, step), height=980, scrolling=True)

st.subheader("出生时刻的数据")
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
st.caption("容许度：合/冲 8°，刑/拱 7°，六合 5°。表中显示精确度偏差。上升与天顶之间不计相位。")
st.write(f"共 {len(ch['aspect_rows'])} 个相位。")
st.dataframe(pd.DataFrame(ch["aspect_rows"]), hide_index=True)
