"""页面: 同年同月、不同日时 — 在"年柱+月柱都不变"的一段时间里, 看星盘的相位什么时候开始、什么时候结束,
同时看八字的日柱、时柱什么时候换, 并解释为什么会这样变。只负责显示, 计算在 core_timeline.py"""
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import core_hours as chh
import core_samechars as sc
import core_timeline as ct
from ui_common import get_birth

b = get_birth()
hsys = st.session_state.get("hsys", "Placidus")

st.write("同一个年柱、月柱之下（约一个月），日和时在不停地变。这里把这段时间铺开：星盘里每个相位什么时候进入、什么时候离开，"
         "对应的八字日柱、时柱什么时候换，再看两者的变化为什么不同步。")

# ---------------- 选时间范围 ----------------
mode = st.radio("时间范围", ["出生时间所在的“年柱+月柱都不变”区间", "自定义起止日期"], horizontal=True)
if mode.startswith("出生"):
    start, end, yp, mp = ct.month_span(b["dt"])
else:
    d1, d2 = st.columns(2)
    a = d1.date_input("开始日期", b["dt"].date(), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
    z = d2.date_input("结束日期（不含）", b["dt"].date() + timedelta(days=30),
                      min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))
    start, end = datetime.combine(a, time(0, 0)), datetime.combine(z, time(0, 0))
    if not (timedelta(days=1) <= end - start <= timedelta(days=62)):
        st.error("范围需要在 1 到 62 天之间。")
        st.stop()
    p0, p1 = sc.pillars_at(start), sc.pillars_at(end - ct.MIN)
    yp, mp = p0[0], p0[1]
    if p0[:2] != p1[:2]:
        st.warning("这段时间跨了不同的年柱或月柱，所以不再是“年月相同”。")

c1, c2, c3 = st.columns(3)
step = c1.selectbox("采样步长（分钟）", [10, 30, 60], help="步长只影响找起止时刻前的粗扫，起止时刻最后都精确到分钟；"
                    "步长越小越不容易漏掉很短的相位。")
names = c2.multiselect("要看相位的天体", ct.BODIES, default=ct.BODIES)
axes = c3.checkbox("包含上升/天顶（变化很快，条目很多）", value=False)
if len(names) < 2 and not axes:
    st.info("至少选两个天体。")
    st.stop()


@st.cache_data(show_spinner="正在逐点计算八字和星盘，并求每个相位的起止时刻…")
def run(s, e, stp, lon, lat, tz, hs, nm, ax):
    return ct.analyze(s, e, stp, lon, lat, tz, hs, list(nm), ax)


R = run(start, end, step, b["lon"], b["lat"], b["tz"], hsys, tuple(names), axes)
S = R["S"]
days = (end - start).total_seconds() / 86400
st.markdown(f"**窗口**：{start:%Y-%m-%d %H:%M} 至 {end:%Y-%m-%d %H:%M}（{days:.1f} 天）　"
            f"**年柱** {yp}　**月柱** {mp}　（整段不变）　**采样点** {len(S['t']):,} 个")


def fmt(df, cols=("开始", "结束", "最接近精确", "时刻", "时柱切换时刻")):
    df = df.copy()
    for c in cols:
        if c in df:
            df[c] = pd.to_datetime(df[c]).dt.strftime("%m-%d %H:%M")
    return df


tabs = st.tabs(["时间轴", "相位起止表", "八字日时变化", "为什么这样变"])

# ================= 时间轴 =================
with tabs[0]:
    focus = st.selectbox("看哪个天体", R["use"], index=R["use"].index("月亮") if "月亮" in R["use"] else 0)
    rows = []
    for _, r in R["bazi_day"].iterrows():
        rows.append({"行": "八字·日柱", "开始": r["开始"], "结束": r["结束"], "内容": r["日柱"], "类型": "八字"})
    for _, r in R["bazi_hour"].iterrows():
        rows.append({"行": "八字·时柱", "开始": r["开始"], "结束": r["结束"], "内容": r["时柱"], "类型": "八字"})
    for _, r in R["seg_sign"][focus].iterrows():
        rows.append({"行": f"{focus}·星座", "开始": r["开始"], "结束": r["结束"], "内容": str(r["值"]), "类型": "星座"})
    if focus in R["seg_house"]:
        for _, r in R["seg_house"][focus].iterrows():
            rows.append({"行": f"{focus}·宫位", "开始": r["开始"], "结束": r["结束"], "内容": f"{r['值']}宫", "类型": "宫位"})
    asp = R["aspects"]
    asp = asp[(asp["天体A"] == focus) | (asp["天体B"] == focus)]
    order_asp = []
    for _, r in asp.iterrows():
        other = r["天体B"] if r["天体A"] == focus else r["天体A"]
        label = f"{other} {r['相位']}"
        if label not in order_asp:
            order_asp.append(label)
        rows.append({"行": label, "开始": r["开始"], "结束": r["结束"], "内容": f"{r['最小偏差(度)']}°", "类型": "相位"})
    order = ["八字·日柱", "八字·时柱", f"{focus}·星座"] + ([f"{focus}·宫位"] if focus in R["seg_house"] else []) + order_asp
    g = pd.DataFrame(rows)
    try:
        import altair as alt
        zoom = alt.selection_interval(bind="scales", encodings=["x"])
        base = alt.Chart(g).encode(
            y=alt.Y("行:N", sort=order, title=None),
            x=alt.X("开始:T", title=None), x2="结束:T",
            color=alt.Color("类型:N", scale=alt.Scale(domain=["八字", "星座", "宫位", "相位"],
                                                     range=["#8a5a2b", "#3b82c4", "#2e9e4d", "#d94b4b"]), legend=None),
            tooltip=["行", "内容", "开始", "结束"])
        gt = g[(g["结束"] - g["开始"]) >= timedelta(hours=8)]
        txt = alt.Chart(gt).mark_text(align="left", dx=3, color="white", fontSize=11).encode(
            y=alt.Y("行:N", sort=order), x="开始:T", text="内容:N")
        st.altair_chart((base.mark_bar(size=14) + txt).add_params(zoom)
                        .properties(height=24 * len(order) + 30), use_container_width=True)
    except ImportError:
        st.dataframe(fmt(g), hide_index=True)
    st.caption(f"横条 = 一段持续的状态。八字 = 日柱、时柱；{focus} = 所在星座、宫位，以及它和其他天体的相位（相位条里写的是该段最小偏差）。"
               "可以用鼠标或手指缩放、拖动时间轴。条的两端都是精确到分钟的起止时刻，贴着窗口边缘的条在窗口外还会继续。")
    if len(asp):
        st.markdown(f"**{focus}** 在这段时间里共出现 **{len(asp)}** 段相位，"
                    f"换星座 {len(R['seg_sign'][focus]) - 1} 次" +
                    (f"，换宫 {len(R['seg_house'][focus]) - 1} 次。" if focus in R["seg_house"] else "。"))

# ================= 相位起止表 =================
with tabs[1]:
    A = R["aspects"]
    f1, f2, f3 = st.columns(3)
    pick_b = f1.multiselect("包含这些天体的相位", R["use"], default=[])
    kinds = sorted(A["相位"].unique())
    pick_k = f2.multiselect("相位类型", kinds, default=kinds)
    full_only = f3.checkbox("只看窗口内完整进出的", value=False)
    sel = A[A["相位"].isin(pick_k)]
    if pick_b:
        sel = sel[sel["天体A"].isin(pick_b) | sel["天体B"].isin(pick_b)]
    if full_only:
        sel = sel[~sel["开始被截断"] & ~sel["结束被截断"]]
    st.write(f"共 {len(sel):,} 段（总计 {len(A):,} 段）。")
    show = fmt(sel).drop(columns=["开始被截断", "结束被截断"])
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.download_button("下载这张表(CSV)", sel.to_csv(index=False).encode("utf-8-sig"),
                       file_name="aspect_intervals.csv", mime="text/csv")
    st.caption("容许度：合/冲 8°，刑/拱 7°，六合 5°。“开始/结束”是进入和离开容许度的时刻；“最接近精确”是采样点里偏差最小的时刻。"
               "开始或结束贴着窗口边缘的，真实时刻在窗口之外。")
    with st.expander("换座时刻"):
        st.dataframe(fmt(R["signs"]), hide_index=True, use_container_width=True)

# ================= 八字日时变化 =================
with tabs[2]:
    st.markdown(f"年柱 **{yp}**、月柱 **{mp}** 整段不变。变的只有日柱和时柱：")
    dday = fmt(R["bazi_day"])
    dday["日主"] = [x[0] for x in R["bazi_day"]["日柱"]]
    dday["日主五行"] = [sc.WX[x[0]] for x in R["bazi_day"]["日柱"]]
    cA, cB = st.columns([1, 1])
    with cA:
        st.markdown(f"**日柱**（{len(R['bazi_day'])} 个）")
        st.dataframe(dday, hide_index=True, use_container_width=True)
    with cB:
        st.markdown(f"**时柱**（{len(R['bazi_hour'])} 个）")
        st.dataframe(fmt(R["bazi_hour"]), hide_index=True, use_container_width=True)
    obs = sorted({r for r in R["bazi_day"]["开始"].iloc[1:]})
    if obs:
        st.caption("本页观察到的换日时刻：" + "、".join(sorted({o.strftime("%H:%M") for o in obs})) +
                   "（由排盘库的规则决定，不是天象）。")

    st.markdown("**每次变化时，完整八字和十神怎么变**")
    cut = sorted(set(R["bazi_day"]["开始"]) | set(R["bazi_hour"]["开始"]))
    seq, prev = [], None
    for t0 in cut:
        p = sc.pillars_at(t0)
        d = sc.describe(p)
        if prev is None:
            changed, kind = 0, "起点"
        else:
            _, changed = sc.diff_flags(prev, d)
            kind = "日柱变" if p[2] != prev["pillars"][2] else "只有时柱变"
        seq.append({"时刻": t0, "八字": d["bazi"], "变化": kind, "十神逐位变化数": changed, "日主": d["day_master"],
                    "日主状态": d["state"], "十神构成": d["tg_comp"],
                    "四柱之间的合冲刑害": chh.rel_text(chh.rel_features(p))})
        prev = d
    sq = pd.DataFrame(seq)
    summ = sq[sq["变化"] != "起点"].groupby("变化")["十神逐位变化数"].agg(["count", "mean", "min", "max"]).round(1)
    summ.columns = ["次数", "平均变化位数", "最少", "最多"]
    st.dataframe(summ, use_container_width=True)
    st.caption("十神是相对日主算的：日柱一换，日主就换，七个位置（年干、月干、时干和四个地支本气）的十神几乎全变；"
               "只有时柱换时，只有时干、时支两个位置的十神变，日主、月令不变。")
    st.dataframe(fmt(sq, ("时刻",)), hide_index=True, use_container_width=True)

# ================= 为什么这样变 =================
with tabs[3]:
    st.subheader("两套系统各靠什么变")
    st.markdown(
        "**八字**：年柱、月柱由节令决定，所以整个窗口不变。日柱是日历上的计数，每天走一格，60 天一轮；"
        "时柱按钟表每 2 小时走一格，时干由日干按五鼠遁推出。八字里所有的变化，都来自“时钟和日历的计数”。\n\n"
        "**星盘**：每个天体按自己的速度在天上走，相位的进入和离开，是两个天体（或天体和上升）的夹角穿过容许度的那一刻。"
        "上升和天顶还随地球自转，约 24 小时转一圈，宫位跟着转。")

    mo = R["motion"].copy()
    st.markdown("**这段时间里各天体动了多少**")
    st.dataframe(mo, hide_index=True, use_container_width=True)
    still = [r["天体"] for _, r in mo.iterrows() if abs(r["净移动(度)"]) < 3 and r["天体"] not in ("上升", "天顶")]
    if still:
        st.caption("几乎不动（不到 3°）的天体：" + "、".join(still) +
                   "。它们互相之间的相位，在整个窗口里基本不变，所以日、时怎么变都影响不了它们。")

    A = R["aspects"]
    whole = A[A["开始被截断"] & A["结束被截断"]]
    fast = {"月亮", "上升", "天顶"}
    short = A[(A["持续(小时)"] < 24) & ~A["开始被截断"] & ~A["结束被截断"]]
    if len(A):
        share = short.apply(lambda r: r["天体A"] in fast or r["天体B"] in fast, axis=1).mean() if len(short) else 0
        st.markdown(f"**相位的稳定程度**：整个窗口都成立的相位 **{len(whole)}** 段；持续不到 1 天、窗口内完整进出的 **{len(short)}** 段，"
                    f"其中涉及月亮或上升/天顶的占 **{share:.0%}**。这说明“日、时不同导致的星盘差异”，主要来自月亮和上升/天顶这几个走得最快的点。")

    st.subheader("八字变化的时刻，和星盘相位的起止对得上吗")
    st.write("八字里，每次日柱或时柱一换，四柱之间的合冲刑害关系（天干合冲、地支六合六冲刑害破）就跟着变。"
             "把这些时刻，和星盘里相位“进入或离开”的时刻比一比：离最近的一次相位起止有多少分钟？再和“把八字变化整体随机平移一段时间”比。")
    if len(R["align"]):
        st.dataframe(R["align"], hide_index=True, use_container_width=True)
        st.caption("比值 = 观测中位距离 ÷ 平移后中位距离。比值明显小于 1、同时 p 很小（例如小于 0.05），才说明八字变化和星盘相位起止有对齐；"
                   "比值接近 1、p 不小，说明对不上，只是碰巧：相位起止很密时，随便取一个时刻，离最近的相位起止也不远。")
    else:
        st.info("这个窗口里的事件太少，无法比较。可以把“要看相位的天体”多选几个。")
    st.caption("为什么多半对不上：八字的关系变化是两个整数周期叠出来的——日干 10 天一轮，日支 12 天一轮，时支 12 个时辰一轮，"
               "日支和月支（年支）的合冲刑害每 12 天重复一遍；而星盘相位的周期是各个天体的轨道周期，月亮和太阳 29.5 天，"
               "月亮和别的行星各不相同。12 天、10 天和这些周期互不是整数倍，所以两边的变化点不会同步。")

    st.subheader("时辰和上升星座的对应")
    st.write("下表：每个时辰里，上升落在各星座的占比（%）。同一天里时辰和上升星座大致对应，但不是一一对应。")
    st.dataframe(R["hour_asc"], use_container_width=True)
    ts = pd.Series(S["t"])
    zhi = pd.Series([p[3][1] for p in S["pil"]])
    asc_sign = pd.Series([ct.ca.SIGNS[int(x // 30) % 12] for x in S["lon"]["上升"]])
    first, last = ts < ts.iloc[0] + timedelta(days=2), ts >= ts.iloc[-1] - timedelta(days=2)
    msgs = []
    for z in "子午":
        m1, m2 = asc_sign[first & (zhi == z)], asc_sign[last & (zhi == z)]
        if len(m1) and len(m2):
            msgs.append(f"{z}时：窗口头两天上升多在**{m1.mode().iloc[0]}**，最后两天多在**{m2.mode().iloc[0]}**")
    if msgs:
        st.markdown("；".join(msgs) + "。")
    st.caption("原因：一个时辰是 2 个钟点，固定不变；上升星座是随地球自转一圈圈经过的，一圈用的是恒星日（比钟表日短约 4 分钟），"
               "所以同一个钟点的上升每天提前约 1°，一个月约提前 30°，也就是一个星座，所以同一个时辰在月初和月末对应的上升星座不同。"
               "另外各星座上升所需的时间长短不一（随纬度和季节变化），时辰边界和换座时刻不会对齐。")
    if len(R["hour_align"]):
        st.markdown("**每次时柱切换时刻，离最近一次上升换座有多少分钟**（0 = 同时发生）")
        st.line_chart(R["hour_align"].set_index("时柱切换时刻")["离最近上升换座(分钟)"])

    st.subheader("日柱和月亮的对应")
    st.dataframe(R["daily"], hide_index=True, use_container_width=True)
    st.caption("日柱 60 天一轮，月亮 27.3 天绕天一圈、29.5 天一个月相周期，三者互相不是整数倍，"
               "所以“某个日柱那天月亮在哪”每个月都会错开，两者之间没有固定的对应。")

    st.info("小结：八字里的日、时变化是等间隔的计数，星盘里的变化是不同速度的天体运动。两者只共用“时间”这一个输入，"
            "变化点本来就不会同步。这里描述的是两套符号系统在时间上的对应关系，不能由此推出任何吉凶或命运的结论。")
