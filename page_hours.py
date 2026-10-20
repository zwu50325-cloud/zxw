"""页面: 同日十二时辰 — 年月日三柱相同、只有时柱不同: 时柱和前三柱有什么联系, 对应的星盘怎么不同。
只负责显示, 计算在 core_hours.py"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import core_hours as ch
from ui_common import colored, get_birth, html_table, inject_css

b = get_birth()
inject_css()
hsys = st.session_state.get("hsys", "Placidus")

st.write("同一天里年柱、月柱、日柱都一样，只有时柱不同（一天 12 个时辰，另外把晚子时单列）。"
         "这里看：时柱和前三柱有什么联系；时辰变了，星盘里星体的星座、宫位、相位怎么变。")

src = st.radio("日期来源", ["用侧边栏的出生日期", "手动选日期"], horizontal=True)
d = b["dt"].date() if src.startswith("用") else st.date_input(
    "日期", b["dt"].date(), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31))


@st.cache_data(show_spinner="正在排这一天 13 个时段的八字和星盘…")
def load(day, lon, lat, tz, hs, gender):
    return ch.day_rows(day, lon, lat, tz, hs, gender)


ref, rows = load(d, b["lon"], b["lat"], b["tz"], hsys, b["gender"])
main = rows[:12]  # 十二个时辰; 第 13 行是晚子时

st.markdown(html_table([[f'<span class="big">{colored(p[0])}</span>' for p in ref],
                        [f'<span class="big">{colored(p[1])}</span>' for p in ref]], ["年柱", "月柱", "日柱"]),
            unsafe_allow_html=True)
diff = [r["名称"] for r in rows if not r["同前三柱"]]
if diff:
    st.warning("这一天里，下列时段的前三柱和正午不同（当天正好换节令，或晚子时按规则算作第二天）：" + "、".join(diff) +
               "。表里“与前三柱一致”一列会标出。")

# ================= 1. 硬规则 =================
st.subheader("1. 硬规则：时柱由“日干 + 时支”决定")
dg = ref[2][0]
chain = " ".join(r["gz"][3] for r in main)
st.markdown(
    f"日干是 **{dg}**，按五鼠遁，子时的时干从 **{ch.hour_stem(dg, '子')}** 起，之后天干依次往后排，"
    f"所以这一天 12 个时柱依次是：\n\n**{chain}**\n\n"
    "也就是说：**时干完全由日干决定，年柱、月柱对时柱没有任何影响**；这一天里能变的只有时支（12 选 1），时干跟着时支走。")
bad = [r["名称"] for r in rows if not r["五鼠遁吻合"]]
if bad:
    st.caption("和五鼠遁不吻合的时段：" + "、".join(bad) + "。通常是晚子时，排盘库对晚子时的日柱、时干有自己的处理约定。")
with st.expander("验证：换一批年、月、日支都不同、但日干相同的日子，时柱是否完全一样"):
    vt, same = ch.verify_wushu(d)
    st.dataframe(vt, hide_index=True, use_container_width=True)
    st.markdown("结果：**12 个时柱完全相同**，说明年柱、月柱（以及日支）不影响时柱。" if same else "结果：不完全相同，请把这一行截图发给我。")

# ================= 2. 十二个八字对照 =================
st.subheader("2. 十二个时辰的八字对照")
bt = ch.bazi_table(rows)
st.dataframe(bt, hide_index=True, use_container_width=True)
st.caption("十神相对日主推算，地支取本气。“时干/时支 vs 年/月/日”：合、冲、同、六合、六冲、相害、相破、相刑，“—”表示没有这类关系。"
           "“日主通根于”：日主五行在哪几个地支的藏干里出现。“帮身:耗身”：七个位置（年干、月干、时干、四个地支本气）里，"
           "比劫印（帮身）的个数 : 其余十神（耗身）的个数。")

pick = st.selectbox("看某一个时辰的细节", [r["名称"] + "  " + " ".join(r["gz"]) for r in rows])
r = rows[[r["名称"] + "  " + " ".join(r["gz"]) for r in rows].index(pick)]
st.markdown(html_table([[f'<span class="big">{colored(p[0])}</span>' for p in r["gz"]],
                        [f'<span class="big">{colored(p[1])}</span>' for p in r["gz"]]],
                       ["年柱", "月柱", "日柱", "时柱"]), unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    st.markdown("**十神（相对日主）**")
    st.markdown(html_table([[k, v] for k, v in r["十神"].items()], ["位置", "十神"]), unsafe_allow_html=True)
    st.markdown(f"时柱纳音 **{r['nayin']}**，日主在时支 **{r['xingyun']}**，时柱自坐 **{r['zizuo']}**。"
                + (f"神煞：{'、'.join(r['shensha'])}。" if r["shensha"] else ""))
with c2:
    st.markdown("**时柱和前三柱的联系**")
    items = list(r["关系"])
    if r["透干"]:
        items.append("时支藏干透出：" + "、".join(r["透干"]))
    if r["时干有根于"]:
        items.append("时干在 " + "、".join(r["时干有根于"]) + " 支的藏干里有根")
    st.write("\n".join(f"- {x}" for x in items))

# ================= 3. 联系的规律 =================
st.subheader("3. 十二个时辰里，时柱和前三柱的联系有什么规律")
kinds = ["六合", "六冲", "相害", "相破", "相刑", "同"]
tab = {}
for k in "年月日":
    c = {x: 0 for x in kinds}
    for rr in main:
        for part in rr["支关系"][k].replace("同·自刑", "同、自刑").split("、"):
            if part in c:
                c[part] += 1
    tab[f"时支 vs {k}支"] = c
st.dataframe(pd.DataFrame(tab).T, use_container_width=True)
st.caption("数字 = 这 12 个时辰里，有几个时辰的时支和该柱的地支是这种关系。每个地支恰好有 1 个六合、1 个六冲、1 个相害、1 个相破和它自己，"
           "所以前几列几乎固定为 1；相刑的个数则因地支而异。换句话说，十二个时辰里**恰好各有一个**会和日支（月支、年支）合、冲、害、破，"
           "这是地支的结构，不是这一天的特殊。")
gcount = pd.Series([rr["时干十神"] for rr in main]).value_counts()
st.markdown("**十二个时辰里时干的十神分布**：" + "、".join(f"{k}×{v}" for k, v in gcount.items()) +
            "。十二个时辰只有十个不同的天干，所以有两个天干会出现两次（子丑时的天干会在戌亥时再出现一遍）。")

# ================= 4. 星盘 =================
st.subheader("4. 同一天、不同时辰的星盘")
st.dataframe(ch.star_table(rows), hide_index=True, use_container_width=True)
st.caption("上升（开始/结束）：这个时辰开始和结束时的上升点，一个时辰约 2 小时，上升大约走过一个星座。天体栏是 星座·宫位（取该时辰中点）。")
hm = ch.house_matrix(rows)
st.markdown("**各天体所在宫位随时辰的变化**")
st.dataframe(hm, use_container_width=True)
st.caption("同一天里，慢行星的星座不变，月亮最多换一次星座；变得最明显的是宫位：每过一个时辰，宫位平均往前推 1 宫，"
           "因为宫位是按上升点划分的，而上升点一天转一圈。")

A = ch.aspect_stability(rows)
if len(A):
    n = len(rows)
    full = A[A["出现时段数"] == n]
    part = A[A["出现时段数"] < n]
    kinds_full = full["类型"].value_counts()
    st.markdown(f"**相位**：一天里共出现 {len(A)} 种相位组合；全天 {n} 个时段都存在的有 **{len(full)}** 个"
                f"（{'、'.join(f'{k} {v} 个' for k, v in kinds_full.items())}），只在部分时段出现的有 **{len(part)}** 个。")
    if len(part):
        st.dataframe(part, hide_index=True, use_container_width=True)
    st.caption("行星之间的相位基本全天不变（月亮除外）；会随时辰变的，是月亮的相位和与上升、天顶的相位。")

# ================= 5. 整年统计 =================
st.subheader("5. 时柱和月柱在星盘里怎么联系起来")
st.write("八字里，时柱和月柱互不相干（时干只看日干）。但在星盘里，太阳的宫位、上升和天顶的星座，是由“季节（对应月柱）+ 钟点（对应时支）”共同决定的。"
         "下面把整年每一天的 12 个时辰都算一遍，看每个“月支 × 时支”组合里最常见的值。")
yr = st.number_input("统计的年份", 1900, 2100, value=d.year, step=1)


@st.cache_data(show_spinner="正在算整年 4380 个时刻…")
def year_df(y, lon, lat, tz, hs):
    return ch.year_table(int(y), lon, lat, tz, hs)


ydf = year_df(yr, b["lon"], b["lat"], b["tz"], hsys)
what = st.selectbox("看哪一项", ["太阳宫", "上升座", "天顶座"], format_func=lambda x: {"太阳宫": "太阳所在宫位", "上升座": "上升星座",
                                                                         "天顶座": "天顶星座"}[x])
st.dataframe(ch.year_pivot(ydf, what), use_container_width=True)
st.caption("行 = 月支（寅月起），列 = 时支。每格：最常见的取值和它占该格的比例，比例越接近 100%，说明这个“月支+时支”组合几乎唯一地决定了这一项。"
           "一个月支约 30 天，一个时辰约 2 小时，所以格子里常常还有第二、第三种取值。")

st.info("小结：这一天里，八字的 12 个版本只差在时支（时干跟着日干走），它们和前三柱的联系，是十二地支两两之间固定的合冲害破结构，"
        "以及十神、藏干、通根的组合；星盘里 12 个时辰差在上升点和宫位，而上升点又由“钟点 + 季节”决定。"
        "这些都是两套符号系统各自的构造关系，不能由此推出任何吉凶或命运的结论。")
