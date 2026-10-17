"""页面: 同字异位查看器 — 输入一个八字, 列出所有用字相同、位置不同的八字,
对比日主/月令/十神, 并给出它们对应的出生时间和星盘。只负责显示, 计算在 core_samechars.py"""
import pandas as pd
import streamlit as st

import core_samechars as sc
from ui_common import colored, get_birth, html_table, inject_css

b = get_birth()
inject_css()

st.write("输入一个八字，列出所有“用字相同、位置不同”的八字，对比它们的日主、月令、十神，"
         "并给出对应的出生时间和星盘。")

mode = st.radio("八字来源", ["用侧边栏的出生信息", "手动输入八字"], horizontal=True)
default = " ".join(sc.pillars_at(b["bazi_dt"]))
text = default if mode == "用侧边栏的出生信息" else st.text_input(
    "输入八字（按 年柱 月柱 日柱 时柱 的顺序）", value=default)
y0, y1 = st.slider("搜索的年份范围", 1700, 2300, (1900, 2100))

pillars, err = sc.parse_bazi(text)
if err:
    st.error(err)
    st.stop()


@st.cache_data(show_spinner="正在搜索…")
def run_search(pl, a, z):
    return sc.search(list(pl), a, z)


@st.cache_data(show_spinner="正在计算星盘…")
def star_rows(pairs, lon, lat, tz):
    """pairs: ((八字, ISO时间), ...)"""
    from datetime import datetime
    rows = []
    for bazi, iso in pairs:
        t = datetime.fromisoformat(iso)
        rows.append({"八字": bazi, "出生时间": t.strftime("%Y-%m-%d %H:%M"),
                     "时辰": sc.shichen_name(t), **sc.astro_brief(t, lon, lat, tz)})
    return rows


res = run_search(tuple(pillars), y0, y1)
items, f = res["items"], res["funnel"]
orig = next(it for it in items if it["is_orig"])

if not orig["valid"]:
    st.warning("你输入的这个八字不符合历法规则（阴阳配对、五虎遁或五鼠遁不成立），现实中不会出现。"
               "下面列出的是用这些字能排出的合法八字。")

st.markdown(
    f"**筛选过程**：这 8 个字共能排出 {f['total']} 种不同的四柱排列 → 阴阳配对合格 {f['parity']} 种 → "
    f"符合五虎遁、五鼠遁 {f['rules']} 种 → {y0}–{y1} 年间有真实出生时间的 {f['with_dates']} 种"
    f"（共 {f['dates']} 个时辰）。")

others = [it for it in items if not it["is_orig"]]
if others:
    n = len(others)
    cnt = {k: sum(1 for it in others if k in it["diff"]) for k in ["日主", "月令", "日主状态", "十神构成"]}
    st.markdown(f"**与原八字相比（其余 {n} 种）**：日主不同 {cnt['日主']} 种，月令不同 {cnt['月令']} 种，"
                f"日主状态不同 {cnt['日主状态']} 种，十神构成不同 {cnt['十神构成']} 种。")
else:
    st.info("在这个年份范围内，没有找到用字相同、位置不同的合法八字。可以把年份范围放宽再试。")

# ---------------- 对比表 ----------------
st.subheader("对比表")
rows = []
for i, it in enumerate(items):
    rows.append({"序号": "原" if it["is_orig"] else i, "八字": it["bazi"],
                 "日主": f"{it['day_master']}（{it['dm_wuxing']}·{it['yinyang']}）",
                 "月令": f"{it['ling']}（{it['ling_wuxing']}）", "日主状态": it["state"],
                 "十神构成": it["tg_comp"],
                 "与原八字不同": "—" if it["is_orig"] else ("、".join(it["diff"]) or "无"),
                 "十神逐位不同数": "" if it["is_orig"] else it["pos_diff"],
                 "出生时间数": len(it["dates"])})
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.caption("日主状态 = 日主五行相对月令五行的旺相休囚死。十神按日主推算，地支取本气。"
           "十神逐位不同数：年干、月干、时干和四个地支共 7 个位置里，十神与原八字不同的个数。")

# ---------------- 逐个查看 ----------------
st.subheader("逐个查看")
labels = [it["bazi"] + ("（原）" if it["is_orig"] else "") for it in items]
pick = items[labels.index(st.selectbox("选择一个八字", labels))]
st.markdown(html_table(
    [[f'<span class="big">{colored(p[0])}</span>' for p in pick["pillars"]],
     [f'<span class="big">{colored(p[1])}</span>' for p in pick["pillars"]]],
    ["年柱", "月柱", "日柱", "时柱"]), unsafe_allow_html=True)
st.markdown(f"日主 **{pick['day_master']}**（{pick['dm_wuxing']}·{pick['yinyang']}）　"
            f"月令 **{pick['ling']}**（{pick['ling_wuxing']}）　日主状态 **{pick['state']}**")
trows = []
for k in sc.POS7:
    a, c = orig["tengod"][k], pick["tengod"][k]
    trows.append([k, a, c, "◀ 不同" if (a != c and not pick["is_orig"]) else ""])
st.markdown(html_table(trows, ["位置", "原八字的十神", "该八字的十神", ""]), unsafe_allow_html=True)

# ---------------- 出生时间与星盘 ----------------
st.subheader("对应的出生时间与星盘")
pairs = tuple((it["bazi"], t.isoformat()) for it in items for t in it["dates"])
if pairs:
    only = st.checkbox("只看上面选中的这个八字", value=False)
    srows = star_rows(pairs, b["lon"], b["lat"], b["tz"])
    if only:
        srows = [r for r in srows if r["八字"] == pick["bazi"]]
    df = pd.DataFrame(srows)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("下载这张表(CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="samechars_dates.csv", mime="text/csv")
else:
    st.info("没有可显示的出生时间。")
st.caption("星盘按侧边栏的出生地经纬度计算，时区固定为侧边栏所选的 UTC 偏移，没有考虑历史上的时区变更和夏令时。"
           "八字按钟表时间排，没有换算真太阳时。时辰内取 xx:30（子时取 0:30），不含晚子时。")

if res["nodate"]:
    with st.expander(f"符合历法规则、但 {y0}–{y1} 年间没有对应出生时间的排列（{len(res['nodate'])} 种）"):
        st.write("、".join(res["nodate"]))
