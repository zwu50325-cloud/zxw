"""页面: 星盘(爱星盘风格, 可操作)。只负责显示, 计算在 core_astro.py / core_wheel.py"""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import core_wheel as cw
from core_astro import HSYS, build_chart
from ui_common import get_birth

b = get_birth()
if "tr_date" not in st.session_state:  # 行运时刻默认取"现在"(按侧边栏的时区)
    _now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=b["tz"])
    st.session_state["tr_date"], st.session_state["tr_time"] = _now.date(), _now.time().replace(second=0, microsecond=0)

c1, c2, c3 = st.columns(3)
hs = c1.selectbox("宫位制", list(HSYS), key="hsys")
step_nat = c2.selectbox("本命盘动画步长", list(cw.STEPS), index=1, key="step_nat")
step_out = c3.selectbox("行运/推运步长", list(cw.STEPS), index=3, key="step_out")
d1, d2 = st.columns(2)
tr_d = d1.date_input("行运/推运时刻：日期", key="tr_date", min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
tr_t = d2.time_input("行运/推运时刻：时间", key="tr_time", step=60)
tdt = datetime.combine(tr_d, tr_t)


@st.cache_data(show_spinner="正在计算星盘…")
def load(dt, lon, lat, tz, hsys):
    return build_chart(dt, lon, lat, tz, hsys)


@st.cache_data(show_spinner="正在计算本命、行运、推运三组动画帧…")
def wheel(dt, tdt, lon, lat, tz, hsys, s_nat, s_out):
    nat = cw.make_frames(dt, lon, lat, tz, hsys, s_nat, 60)
    tr = cw.make_frames(tdt, lon, lat, tz, hsys, s_out, 60)
    pr = cw.make_frames(tdt, lon, lat, tz, hsys, s_out, 60, kind="pr", birth=dt)
    return cw.wheel_html(nat, tr, pr, 60, s_nat, s_out, hsys)


ch = load(b["dt"], b["lon"], b["lat"], b["tz"], hs)

st.caption("上方三个按钮切换：本命盘 / 行运盘（外圈是所选时刻天上的星体）/ 推运盘（次限推运，一日一年）。"
           "拖动时间条或点 ▶ 播放；点击或悬停星体可高亮它的相位。")
components.html(wheel(b["dt"], tdt, b["lon"], b["lat"], b["tz"], hs, step_nat, step_out), height=1500, scrolling=True)
st.caption("行运/推运的相位容许度可在盘上方调整（默认 3°）；推运按出生地计算，不含太阳弧、月返、日返等其他推运法。")

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
