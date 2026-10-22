"""页面: 规律流水线 — 发现集找 → 验证集复验 → 解释库归因 → 登记 → 报告。计算在 core_pipeline.py"""
import pandas as pd
import streamlit as st

import core_conditions as cc
import core_discovery as cd
import core_pipeline as cp
from ui_common import get_birth

b = get_birth()
st.write("把数据按年份分成两半：前半（发现集）里找关联，后半（验证集）里复验。只有两边都出现、不被其他变量解释、"
         "也没有天文/历法原因的，才算“待解释的直接对应”。每次运行结果都会登记，反复出现才更可信。")

src = st.radio("数据来源", ["现场计算", "上传 CSV（core_conditions.py 的新版输出）"], horizontal=True)
if src == "现场计算":
    y0, y1 = st.slider("年份范围", 1900, 2100, (2000, 2025))

    @st.cache_data(show_spinner="正在计算每个时刻的八字和星盘…")
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
        st.error("这个 CSV 是旧版，缺少列（例如 " + "、".join(miss[:4]) + "…），请用新版重新生成。")
        st.stop()
st.caption(f"共 {len(df):,} 个出生时刻。")

c1, c2 = st.columns(2)
auto = c1.checkbox("分界年份取中间", True)
yrs = df["出生时间"].astype(str).str[:4].astype(int)
split = None if auto else c1.slider("发现集到哪一年为止", int(yrs.min()) + 2, int(yrs.max()) - 2, int((yrs.min() + yrs.max()) // 2))
top = c2.slider("检验前多少对", 40, 300, 120, step=20)

if st.button("运行流水线"):
    bar = st.progress(0.0)
    try:
        res = cp.run_pipeline(df, split, top, progress=lambda p: bar.progress(min(p, 1.0)))
    except ValueError as e:
        st.error(str(e))
        st.stop()
    bar.empty()
    st.session_state["pipe"] = res
    st.session_state["registry"] = cp.update_registry(st.session_state.get("registry"), res["findings"], res["meta"])
res = st.session_state.get("pipe")
if res is None:
    st.stop()
f, m = res["findings"], res["meta"]
st.success(f"发现集 {m['发现集']}；验证集 {m['验证集']}；扫描 {m['扫描对数']:,} 对，检验 {m['检验对数']} 对。")
st.bar_chart(f["类别"].value_counts())

cats = list(f["类别"].unique())
pick = st.multiselect("只看这些类别", cats, default=[c for c in cats if c.startswith("★")] or cats)
show = f[f["类别"].isin(pick)].copy()
for c in [c for c in show.columns if c.startswith("V") or c.startswith("控制") or c == "平移基线99%"]:
    show[c] = show[c].round(3)
st.dataframe(show, hide_index=True, use_container_width=True)

rep = cp.report_md(res)
with st.expander("报告（Markdown）", expanded=True):
    st.markdown(rep)
d1, d2, d3 = st.columns(3)
d1.download_button("报告 .md", rep.encode("utf-8"), "report.md")
d2.download_button("结果 .csv", f.to_csv(index=False).encode("utf-8-sig"), "findings.csv", "text/csv")
d3.download_button("给 AI 的摘要 .json", cp.summary_for_ai(res).encode("utf-8"), "summary_for_ai.json")

reg = st.session_state.get("registry")
if reg is not None and len(reg):
    st.subheader("登记表：多次运行里的复现情况")
    st.dataframe(cp.registry_summary(reg), hide_index=True, use_container_width=True)
    st.download_button("下载登记表", reg.to_csv(index=False).encode("utf-8-sig"), "registry.csv", "text/csv")
    st.caption("换不同的年份范围、分界年份再运行几次，复现次数高的才值得继续研究。登记表只存在当前会话，请下载保存，下次上传合并。")

st.info("八字和星盘都是出生时间的确定函数，没有因果。这里的结果只是历法周期与天体周期的对应，不用于吉凶或命运判断。")
