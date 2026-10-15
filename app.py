"""
八字 × 星盘 对比应用
本地运行: streamlit run app.py
需与 generate_dataset.py 放在同一目录
"""
import json
from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

import generate_dataset as gd
import bazi_view
import astro_view

CLAUDE_MODEL = "claude-sonnet-5-5"

CITIES = {  # 名称: (经度, 纬度, 时区)
    "北京": (116.4, 39.9, 8), "上海": (121.5, 31.2, 8),
    "广州": (113.3, 23.1, 8), "深圳": (114.1, 22.5, 8),
    "成都": (104.1, 30.7, 8), "武汉": (114.3, 30.6, 8),
    "西安": (108.9, 34.3, 8), "香港": (114.2, 22.3, 8),
    "台北": (121.5, 25.0, 8), "新加坡": (103.8, 1.35, 8),
    "纽约": (-74.0, 40.7, -5), "伦敦": (-0.1, 51.5, 0),
    "自定义": (116.4, 39.9, 8),
}

st.set_page_config(page_title="八字 × 星盘", page_icon="🔮", layout="wide")
st.title("🔮 八字 × 星盘 对比")
st.caption("比较两套符号系统的结构。仅供文化与研究参考，不构成预测。")

# ---------------- 输入 ----------------
with st.sidebar:
    st.header("出生信息")
    d = st.date_input("出生日期", datetime(1995, 6, 15),
                      min_value=datetime(1900, 1, 1),
                      max_value=datetime(2100, 12, 31))
    t = st.time_input("出生时间", time(12, 0), step=60)
    city = st.selectbox("出生地", list(CITIES))
    lon0, lat0, tz0 = CITIES[city]
    lon = st.number_input("经度 (东正西负)", value=float(lon0), format="%.2f")
    lat = st.number_input("纬度", value=float(lat0), format="%.2f")
    tz = st.number_input("时区 (UTC±)", value=int(tz0), step=1)
    solar = st.checkbox("八字使用真太阳时(按经度修正)", value=False)
    gender = 1 if st.radio("性别(用于排大运)", ["男", "女"], horizontal=True) == "男" else 0

dt = datetime.combine(d, t)
gd.LON, gd.LAT, gd.TZ = lon, lat, tz
bazi_dt = dt + timedelta(minutes=(lon - tz * 15) * 4) if solar else dt


@st.cache_data(show_spinner=False)
def compute(dt_, bazi_dt_, lon_, lat_, tz_):
    gd.LON, gd.LAT, gd.TZ = lon_, lat_, tz_
    return gd.bazi_features(bazi_dt_), gd.astro_features(dt_)


bazi, astro = compute(dt, bazi_dt, lon, lat, tz)
if solar:
    st.info(f"八字所用真太阳时：{bazi_dt:%Y-%m-%d %H:%M}（钟表时间 {dt:%H:%M}）")

PLANET_NAMES = list(gd.PLANETS)


def planet_table(a):
    rows = []
    for n in PLANET_NAMES:
        lon_ = a[f"星盘_{n}_度数"]
        rows.append({"天体": n, "星座": a[f"星盘_{n}_星座"],
                     "星座内度数": round(lon_ % 30, 2),
                     "宫位": a[f"星盘_{n}_宫位"]})
    rows.insert(0, {"天体": "上升", "星座": a["星盘_上升星座"],
                    "星座内度数": round(a["星盘_上升度数"] % 30, 2), "宫位": 1})
    return pd.DataFrame(rows)


tw, ta, tab1, tab2, tab3, tab4 = st.tabs(
    ["八字排盘", "星盘", "简表", "五行 vs 四元素", "时间扰动", "AI 解读"])

with tw:
    bazi_view.render(bazi_dt, gender)
with ta:
    astro_view.render(dt, lon, lat, tz)

# ---------------- 命盘 ----------------
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
        st.dataframe(planet_table(astro), hide_index=True,
                     use_container_width=True)

# ---------------- 元素对比 ----------------
with tab2:
    wx = pd.DataFrame({"数量": [bazi[f"八字_{w}数"] for w in "金木水火土"]},
                      index=list("金木水火土"))
    el_names = ["火", "土", "风", "水"]
    el = pd.DataFrame({"数量": [astro[f"星盘_{e}象数"] for e in el_names]},
                      index=[e + "象" for e in el_names])
    c1, c2 = st.columns(2)
    c1.subheader("八字五行（共 8 个字）")
    c1.bar_chart(wx)
    c2.subheader("星盘四元素（7 颗行星）")
    c2.bar_chart(el)
    st.markdown(
        "**注意**：五行按字的属性计数，四元素按行星所在星座计数，"
        "两者的划分方式和数量基数都不同，名字相近不代表对应。")
    asp = pd.DataFrame({"数量": [astro[f"星盘_相位_{k}"] for k in gd.ASPECTS]},
                       index=list(gd.ASPECTS))
    st.subheader("星盘相位数量")
    st.bar_chart(asp)

# ---------------- 扰动 ----------------
with tab3:
    st.write("只改变一个时间单位，看两套盘各自怎么变。")
    unit = st.selectbox("改变的单位", ["小时", "时辰(2小时)", "天", "月(30天)", "年"])
    n = st.slider("改变量", 1, 12, 1)
    delta = {"小时": timedelta(hours=1), "时辰(2小时)": timedelta(hours=2),
             "天": timedelta(days=1), "月(30天)": timedelta(days=30),
             "年": timedelta(days=365)}[unit] * n
    dt2 = dt + delta
    bdt2 = bazi_dt + delta
    gd.LON, gd.LAT, gd.TZ = lon, lat, tz
    b2, a2 = gd.bazi_features(bdt2), gd.astro_features(dt2)
    st.write(f"新时间：**{dt2:%Y-%m-%d %H:%M}**")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("八字变化")
        changed = [p for p in "年月日时"
                   if bazi[f"八字_{p}柱"] != b2[f"八字_{p}柱"]]
        st.write(f"变化的柱：{'、'.join(p + '柱' for p in changed) or '无'}")
        st.table(pd.DataFrame(
            {"原": [bazi[f"八字_{p}柱"] for p in "年月日时"],
             "新": [b2[f"八字_{p}柱"] for p in "年月日时"]},
            index=[p + "柱" for p in "年月日时"]))
    with c2:
        st.subheader("星盘位移(度)")
        rows = []
        for name in ["上升"] + PLANET_NAMES:
            k = "星盘_上升_度数" if name == "上升" else f"星盘_{name}_度数"
            k = "星盘_上升度数" if name == "上升" else k
            diff = abs(astro[k] - a2[k]) % 360
            rows.append({"天体": name, "位移": round(min(diff, 360 - diff), 2)})
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)

# ---------------- AI 解读 ----------------
with tab4:
    st.write("让 Claude 根据上面的命盘数据，写一份两套体系的相同点和不同点说明。")
    key = st.text_input("Anthropic API Key", type="password",
                        value=st.secrets.get("ANTHROPIC_API_KEY", "")
                        if hasattr(st, "secrets") else "")
    if st.button("生成解读") and key:
        try:
            import anthropic
            payload = {"八字": bazi, "星盘": astro}
            prompt = (
                "下面是同一出生时间排出的八字与西方占星数据(JSON)。"
                "请用中文，分三部分写：1) 两套体系在这张盘里的相似点；"
                "2) 不同点(符号设计、时间敏感度、元素划分方式)；"
                "3) 无法对应的部分。把它们当作文化符号系统来分析，"
                "不要做命运预测，也不要声称有科学预测效力。\n\n"
                + json.dumps(payload, ensure_ascii=False))
            client = anthropic.Anthropic(api_key=key)
            with st.spinner("生成中…"):
                msg = client.messages.create(
                    model=CLAUDE_MODEL, max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}])
            st.markdown(msg.content[0].text)
        except Exception as e:
            st.error(f"调用失败：{e}")
    elif not key:
        st.caption("填入 API Key 后点击按钮。Key 只用于本次请求，不会被保存。")
