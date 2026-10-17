"""
八字 × 星盘 研究应用 — 入口文件
本地运行: streamlit run app.py   (需要 streamlit >= 1.36)

文件分工:
  core_*.py   纯计算, 不含任何界面代码 (core_bazi 八字 / core_astro 星盘 / core_compare 对比 / core_ai AI)
  ui_common.py 界面公共部分: 侧边栏出生信息、配色、HTML 表格
  page_*.py   每个功能一个页面, 只负责显示
  app.py      本文件: 页面注册和左侧菜单
新增功能 = 写一个 page_xxx.py (需要的话再加 core_xxx.py), 然后在下面的列表里加一行。
"""
import streamlit as st

from ui_common import sidebar

st.set_page_config(page_title="八字 × 星盘", page_icon="🔮", layout="wide")
st.title("🔮 八字 × 星盘 对比")
st.caption("比较两套符号系统的结构。仅供文化与研究参考，不构成预测。")

sidebar()  # 出生信息输入, 所有页面共用

pages = [
    st.Page("page_bazi.py", title="八字排盘", icon="🀄"),
    st.Page("page_astro.py", title="星盘", icon="🪐"),
    st.Page("page_summary.py", title="对比简表", icon="📋"),
    st.Page("page_perturb.py", title="时间扰动", icon="⏱️"),
    st.Page("page_samechars.py", title="同字异位", icon="🔀"),
    st.Page("page_research.py", title="规律研究", icon="🔬"),
    st.Page("page_ai.py", title="AI 解读", icon="🤖"),
]
st.navigation(pages).run()
