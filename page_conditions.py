"""页面: 按星盘条件看八字 — 选一个星盘条件(例如"月亮在第 1 宫"), 看满足条件的出生时间,
它们的八字有什么特征。只负责显示, 计算在 core_conditions.py"""
import pandas as pd
import streamlit as st

import core_conditions as cc
from ui_common import get_birth

b = get_birth()

st.write("选一个星盘条件，比如“月亮在第 1 宫”，看满足它的所有出生时间，八字的日主、月令、十神、地支等有什么特点。"
         "每个时辰取一个时刻（xx:30，子时取 0:30），出生地用侧边栏的经纬度和时区。")

# ---------------- 数据 ----------------
src = st.radio("数据来源", ["现场计算", "上传已生成的 CSV（core_conditions.py 的输出）"], horizontal=True)
if src == "现场计算":
    y0, y1 = st.slider("年份范围（越长越慢，10 年约 4.4 万行）", 1900, 2100, (2016, 2025))

    @st.cache_data(show_spinner="正在计算每个时刻的八字和星盘，请稍等…")
    def load(a, z, lon, lat, tz):
        return cc.build_dataset(a, z, lon, lat, tz)

    df = load(y0, y1, b["lon"], b["lat"], b["tz"])
else:
    up = st.file_uploader("上传 CSV", type=["csv"])
    if up is None:
        st.info("还没有上传。在 Colab 或本机运行 `python core_conditions.py --y0 1996 --y1 2025` 生成 astro_bazi_rows.csv，再传到这里。")
        st.stop()
    df = pd.read_csv(up)
    miss = [c for c in cc.BAZI_COLS + cc.ASTRO_COLS if c not in df.columns]
    if miss:
        st.error("这个 CSV 缺少列：" + "、".join(miss[:6]) + "…")
        st.stop()
st.caption(f"共 {len(df):,} 个出生时刻（{df['出生时间'].iloc[0][:10]} 至 {df['出生时间'].iloc[-1][:10]}）。")

# ---------------- 条件 ----------------
st.subheader("1. 选星盘条件")
n_cond = st.radio("条件个数", [1, 2], horizontal=True)
conds = []
for i in range(n_cond):
    c1, c2, c3 = st.columns(3)
    body = c1.selectbox(f"条件 {i + 1}：天体", cc.BODIES, key=f"cb{i}")
    kind = c2.selectbox("看什么", ["宫", "座"], format_func=lambda x: "宫位" if x == "宫" else "星座", key=f"ck{i}")
    opts = list(range(1, 13)) if kind == "宫" else ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
                                                       "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"]
    val = c3.selectbox("取值", opts, key=f"cv{i}")
    conds.append((body, kind, val))

mask = cc.make_mask(df, conds)
n1 = int(mask.sum())
st.markdown(f"**{cc.cond_text(conds)}**：{n1:,} 个时刻，占 {n1 / len(df):.1%}。")
if n1 < 100:
    st.warning("满足条件的样本太少（不足 100），下面的比较没有参考价值。请放宽条件或拉长年份范围。")
    st.stop()

# ---------------- 哪些八字特征和这个条件有关 ----------------
st.subheader("2. 哪些八字特征和它有关")


@st.cache_data(show_spinner="正在和随机基线比较…")
def summary(key, m_bytes, n):
    m = np_from(m_bytes, n)
    return cc.feature_summary(df, m, n_perm=100)


def np_from(b_, n):
    import numpy as np
    return np.frombuffer(b_, dtype=bool, count=n)


fs = summary((len(df), str(conds)), mask.tobytes(), len(mask))
show = fs.copy()
for c in ["V", "基线95%", "基线99%"]:
    show[c] = show[c].round(4)
show["V/基线99%"] = show["V/基线99%"].round(2)
st.dataframe(show[["八字特征", "V", "基线99%", "V/基线99%", "解读"]], hide_index=True, use_container_width=True)
st.caption("V（Cramér's V）：0 表示完全无关，越大关系越强。基线 = 把条件标记沿时间轴平移整数天后重新算出的 V，"
           "平移后依然这么大，说明关系来自一天之内的时刻结构，而不是日期规律。"
           "宫位随时刻变化很快，所以和时支、十神_时支等时辰相关特征的关系通常是时刻结构造成的，而不是什么命理规律。")

# ---------------- 某个特征的细节 ----------------
st.subheader("3. 某个八字特征的细节")
feat = st.selectbox("选一个八字特征", list(fs["八字特征"]))
lt = cc.lift_table(df, mask, feat)
view = lt.copy()
for c in ["条件内占比", "总体占比"]:
    view[c] = (view[c] * 100).round(2).astype(str) + "%"
view["倍数"] = view["倍数"].round(2)
view["偏差z"] = view["偏差z"].round(2)
st.dataframe(view, hide_index=True, use_container_width=True)
st.bar_chart(lt.set_index("取值")[["条件内占比", "总体占比"]])
st.caption("倍数 = 条件内占比 ÷ 总体占比，1 表示没有差别。偏差 z：绝对值大于 3 才算明显偏离，"
           "但相邻时刻不是独立样本，z 偏乐观，要以上面和基线的比较为准。")

with st.expander("看这些时刻的八字（前 200 条）"):
    st.dataframe(df.loc[mask, ["出生时间", "八字"] + [f"{x}{k}" for x, k in [(c[0], c[1]) for c in conds]]].head(200),
                 hide_index=True)

# ---------------- 全部条件扫描 ----------------
st.subheader("4. 扫描所有“天体 × 宫位/星座”条件")
st.write("一次性找出和八字特征关系最强的星盘条件。")
if st.button("开始扫描（约 1 分钟）"):
    with st.spinner("扫描中…"):
        sc = cc.scan(df)
    st.session_state["scan_result"] = sc
sc = st.session_state.get("scan_result")
if sc is not None:
    top = sc.head(60).copy()
    top["V"] = top["V"].round(4)
    st.dataframe(top[["条件", "八字特征", "样本数", "V"]], hide_index=True, use_container_width=True)
    st.caption("慢行星（海王星、冥王星等）的星座，几乎等于出生年，所以和年支、年干的 V 接近 1，这是日历结构，不是发现。"
               "挑出感兴趣的行，回到第 1 步选同样的条件，用基线检验。")
