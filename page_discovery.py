"""页面: 规律发现 — 星盘特征(星体落座、落宫、相位、月相…) × 八字特征 的全面关联扫描。
只负责显示, 计算在 core_discovery.py / core_conditions.py"""
import pandas as pd
import streamlit as st

import core_conditions as cc
import core_discovery as cd
from ui_common import get_birth

b = get_birth()

st.write("把每个出生时刻的星盘特征（各星体的星座、宫位、两两相位、月相、上升/天顶星座）和八字特征（干支、十神、月令、日主状态…）放在一起，"
         "找出关联最强的组合，并判断这个关联是“真的直接对应”，还是“被某个共同因素带出来的”。")

src = st.radio("数据来源", ["现场计算", "上传已生成的 CSV（core_conditions.py 的新版输出）"], horizontal=True)
if src == "现场计算":
    y0, y1 = st.slider("年份范围", 1900, 2100, (2006, 2025))
    st.caption("慢行星（木星、土星…）要几十年的数据才看得出和年柱的关系；年份范围越长越慢，20 年约 8.8 万行，需要几分钟。"
               "想看 30 年，建议在 Colab 里运行 `python core_conditions.py --y0 1996 --y1 2025`，再上传 CSV。")

    @st.cache_data(show_spinner="正在计算每个时刻的八字和星盘，请稍等…")
    def load(a, z, lon, lat, tz):
        return cc.build_dataset(a, z, lon, lat, tz)

    df = load(y0, y1, b["lon"], b["lat"], b["tz"])
else:
    up = st.file_uploader("上传 CSV", type=["csv"])
    if up is None:
        st.info("还没有上传。")
        st.stop()
    df = pd.read_csv(up)
    miss = [c for c in cd.ASTRO + cd.BAZI if c not in df.columns]
    if miss:
        st.error("这个 CSV 是旧版，缺少相位、月相等列（例如 " + "、".join(miss[:4]) + "…）。请用新版 core_conditions.py 重新生成。")
        st.stop()
st.caption(f"共 {len(df):,} 个出生时刻（{df['出生时间'].iloc[0][:10]} 至 {df['出生时间'].iloc[-1][:10]}）。")

c1, c2 = st.columns(2)
top = c1.slider("对关联最强的前多少对做进一步检验", 40, 300, 120, step=20)
perm = c2.slider("平移基线的重复次数", 20, 100, 40, step=10)

if st.button("开始扫描"):
    bar = st.progress(0.0)
    head, allres = cd.run(df, top=top, n_perm=perm, progress=lambda p: bar.progress(min(p, 1.0)))
    bar.empty()
    st.session_state["disc"] = (head, allres, len(df))
res = st.session_state.get("disc")
if res is None:
    st.stop()
head, allres, n = res
st.success(f"扫描了 {len(allres):,} 对（星盘特征 × 八字特征），下面是关联最强的 {len(head)} 对。")

tags = sorted({("样本太少" if t.startswith("样本太少") else t) for t in head["判断"]})
tag_of = head["判断"].map(lambda t: "样本太少" if t.startswith("样本太少") else t)
pick = st.multiselect("只看这些判断", tags, default=[t for t in tags if t.startswith("日期层面")] or tags)
show = head[tag_of.isin(pick)].copy()
for c in [c for c in show.columns if c.endswith("V") or c == "V" or c == "平移基线99%"]:
    show[c] = show[c].round(3)
st.dataframe(show, hide_index=True, use_container_width=True)
st.download_button("下载全部结果(CSV)", head.to_csv(index=False).encode("utf-8-sig"),
                   file_name="discovery.csv", mime="text/csv")
st.caption("V（Cramér's V，已校正小样本偏差）：0 无关，1 完全对应。“控制X后V”：只在同一个X里比较时的V，明显变小（小于原来的三分之一）"
           "说明原来的关联是通过X间接产生的。“变化段数”：这个星盘特征在数据里换了多少次取值，决定了有效样本有多少。"
           "判断一栏里，“日期层面的直接对应”才是重点关注的；“钟点结构”多半来自一天之内上升点的转动；“样本太少”不能当作规律。")

with st.expander("复制给 Claude 分析的摘要"):
    st.text_area("摘要", cd.summary_text(head, 40), height=300)

st.subheader("看某一对的细节")
r = st.selectbox("选一对", [f"{x['星盘特征']} ↔ {x['八字特征']}（V={x['V']:.3f}）" for _, x in head.iterrows()])
row = head.iloc[[f"{x['星盘特征']} ↔ {x['八字特征']}（V={x['V']:.3f}）" for _, x in head.iterrows()].index(r)]
st.markdown(f"**{row['判断']}**")
ct = cd.crosstab(df, row["星盘特征"], row["八字特征"])
if ct.shape[0] > 60 or ct.shape[1] > 60:
    st.info("取值太多，只显示前 40 行、40 列。")
st.dataframe(ct.iloc[:40, :40], use_container_width=True)
st.caption("表里每一行是星盘特征的一个取值，每格是该取值下，八字特征取各个值的占比（%）。接近 100/（列数）说明无偏好。")

st.info("两套体系都是“出生时间”的确定函数，它们之间没有因果。这里找到的任何关联，说的都是历法周期和天体运动周期的对应，"
        "不能由此推出吉凶或命运的结论。")
