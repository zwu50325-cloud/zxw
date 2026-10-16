"""页面: 八字排盘(问真八字风格)。只负责显示, 计算在 core_bazi.py"""
import streamlit as st

from core_bazi import WUXING_ORDER, build_chart
from ui_common import colored as c
from ui_common import get_birth, html_table, inject_css

b = get_birth()


@st.cache_data(show_spinner=False)
def load(bdt, gender):
    return build_chart(bdt, gender)


ch = load(b["bazi_dt"], b["gender"])
P = ch["pillars"]
dg = ch["day_master"]
inject_css()

if b["solar"]:
    st.info(f"八字所用真太阳时：{b['bazi_dt']:%Y-%m-%d %H:%M}（钟表时间 {b['dt']:%H:%M}）")

st.subheader("基本信息")
st.markdown(
    f"**公历**：{ch['solar']}　**农历**：{ch['lunar']}　**生肖**：{ch['shengxiao']}  \n"
    f"**性别**：{'男(乾造)' if ch['gender'] == 1 else '女(坤造)'}　"
    f"**日主**：{c(dg)}（{ch['day_master_wuxing']}，{ch['day_master_yinyang']}）  \n"
    f"**节令**：{ch['jie_prev']} → {ch['jie_next']}",
    unsafe_allow_html=True)

st.subheader("四柱")
rows = [
    ["主星"] + [p["zhuxing"] for p in P],
    ["天干"] + [f'<span class="big">{c(p["gan"])}</span>' for p in P],
    ["地支"] + [f'<span class="big">{c(p["zhi"])}</span>' for p in P],
    ["藏干"] + ["<br>".join(f"{c(h)} <span class='sm'>{s}</span>" for h, s in p["hide"]) for p in P],
    ["星运"] + [p["xingyun"] for p in P],
    ["自坐"] + [p["zizuo"] for p in P],
    ["空亡"] + [p["kong"] for p in P],
    ["纳音"] + [p["nayin"] for p in P],
    ["神煞"] + ["<br>".join(p["shensha"]) or "—" for p in P],
]
st.markdown(html_table(rows, ["", "年柱", "月柱", "日柱", "时柱"]), unsafe_allow_html=True)

st.subheader("命宫 · 胎元 · 五行")
st.markdown(f"**胎元**：{ch['taiyuan']}　**胎息**：{ch['taixi']}　"
            f"**命宫**：{ch['minggong']}　**身宫**：{ch['shengong']}")
st.markdown(html_table(
    [["仅八字"] + [ch["wuxing_plain"][w] for w in WUXING_ORDER],
     ["含藏干(藏干计0.5)"] + [ch["wuxing_full"][w] for w in WUXING_ORDER]],
    [""] + list(WUXING_ORDER)), unsafe_allow_html=True)

st.subheader("刑冲合害")
for r in ch["relations"]:
    st.write("· " + r)

st.subheader("大运")
y = ch["yun"]
st.write(f"出生后 {y['start_year']} 年 {y['start_month']} 个月 {y['start_day']} 天起运，起运日期 {y['start_date']}")
dys = ch["dayun"]
head = [f"{d['start_age']}岁<br><span class='sm'>{d['start_year']}</span>" for d in dys]
st.markdown(html_table([
    [d["shishen"] for d in dys],
    [f'<span class="big" style="font-size:22px">{c(d["ganzhi"][0])}{c(d["ganzhi"][1])}</span>' for d in dys],
    [d["changsheng"] for d in dys],
], head), unsafe_allow_html=True)

labels = [f"{d['ganzhi']}（{d['start_age']}-{d['end_age']}岁，{d['start_year']}-{d['end_year']}）" for d in dys]
pick = st.selectbox("查看该大运的流年", labels)
lns = dys[labels.index(pick)]["liunian"]
st.markdown(html_table([
    [f"{l['year']}<br><span class='sm'>{l['age']}岁</span>" for l in lns],
    [f'<span style="font-size:20px">{c(l["ganzhi"][0])}{c(l["ganzhi"][1])}</span>' for l in lns],
    [l["shishen"] for l in lns],
    [l["changsheng"] for l in lns],
]), unsafe_allow_html=True)
st.caption("行依次为：年份/虚岁、流年干支、天干十神、星运。")
if ch["xiaoyun"]:
    st.markdown("**小运**：" + "　".join(f"{x['year']}年{x['age']}岁 {x['ganzhi']}" for x in ch["xiaoyun"]))
