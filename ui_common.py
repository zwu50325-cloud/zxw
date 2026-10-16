"""界面公共部分: 侧边栏出生信息、配色、HTML 表格。所有页面共用。"""
from datetime import datetime, time, timedelta

import streamlit as st

from core_bazi import WX

CITIES = {  # 名称: (经度, 纬度, 时区)
    "北京": (116.4, 39.9, 8), "上海": (121.5, 31.2, 8),
    "广州": (113.3, 23.1, 8), "深圳": (114.1, 22.5, 8),
    "成都": (104.1, 30.7, 8), "武汉": (114.3, 30.6, 8),
    "西安": (108.9, 34.3, 8), "香港": (114.2, 22.3, 8),
    "台北": (121.5, 25.0, 8), "新加坡": (103.8, 1.35, 8),
    "纽约": (-74.0, 40.7, -5), "伦敦": (-0.1, 51.5, 0),
    "自定义": (116.4, 39.9, 8),
}
COLOR = {"木": "#2e9e4d", "火": "#d83b3b", "土": "#a9783a", "金": "#c9961a", "水": "#2f72c9"}
CSS = """<style>
table.bz{border-collapse:collapse;width:100%;text-align:center;font-size:14px}
table.bz td,table.bz th{border:1px solid rgba(128,128,128,.35);padding:6px 4px}
table.bz th{background:rgba(128,128,128,.12);font-weight:600}
.sm{font-size:12px;opacity:.8}.big{font-size:30px;font-weight:700}
.wrap{overflow-x:auto}</style>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def colored(ch, size=None):
    s = f"font-size:{size}px;" if size else ""
    return f'<span style="color:{COLOR[WX[ch]]};{s}">{ch}</span>'


def html_table(rows, head=None):
    h = "".join(f"<th>{x}</th>" for x in head) if head else ""
    body = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table class="bz">{"<tr>" + h + "</tr>" if h else ""}{body}</table></div>'


def sidebar():
    """在侧边栏显示出生信息输入, 结果存进 st.session_state['birth'], 所有页面共用。"""
    with st.sidebar:
        st.header("出生信息")
        d = st.date_input("出生日期", datetime(1995, 6, 15),
                          min_value=datetime(1900, 1, 1), max_value=datetime(2100, 12, 31))
        t = st.time_input("出生时间", time(12, 0), step=60)
        city = st.selectbox("出生地", list(CITIES))
        lon0, lat0, tz0 = CITIES[city]
        lon = st.number_input("经度 (东正西负)", value=float(lon0), format="%.2f")
        lat = st.number_input("纬度", value=float(lat0), format="%.2f")
        tz = st.number_input("时区 (UTC±)", value=int(tz0), step=1)
        solar = st.checkbox("八字使用真太阳时(按经度修正)", value=False)
        gender = 1 if st.radio("性别(用于排大运)", ["男", "女"], horizontal=True) == "男" else 0
    dt = datetime.combine(d, t)
    bazi_dt = dt + timedelta(minutes=(lon - tz * 15) * 4) if solar else dt
    birth = {"dt": dt, "bazi_dt": bazi_dt, "lon": lon, "lat": lat, "tz": tz,
             "solar": solar, "gender": gender}
    st.session_state["birth"] = birth
    return birth


def get_birth():
    """页面里调用, 拿到侧边栏填写的出生信息。"""
    return st.session_state.get("birth") or sidebar()
