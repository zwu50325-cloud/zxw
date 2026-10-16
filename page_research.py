"""页面: 规律研究 — 展示 bazi_pattern_analysis.py 和 ai_summarize.py 生成的结果
用法: 在本机或 Colab 跑完分析后, 把 report.md、summary.json 和 CSV 文件上传到这里查看。"""
import json
import os

import pandas as pd
import streamlit as st

st.write("这里显示近30年八字规律分析的结果。先运行 `bazi_pattern_analysis.py` 和 `ai_summarize.py`，"
         "再把生成的文件上传到下面。")

LOCAL = "results"  # 如果结果文件夹就在应用目录里, 也会自动读取


def read_local(name):
    p = os.path.join(LOCAL, name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


up = st.file_uploader("上传结果文件(report.md、summary.json、各种 .csv, 可多选)",
                      type=["md", "json", "csv"], accept_multiple_files=True)
files = {f.name: f for f in up or []}

report = files["report.md"].getvalue().decode("utf-8") if "report.md" in files else read_local("report.md")
summary = (json.loads(files["summary.json"].getvalue().decode("utf-8")) if "summary.json" in files
           else (json.loads(read_local("summary.json")) if read_local("summary.json") else None))
csvs = {n: f for n, f in files.items() if n.endswith(".csv")}

tabs = st.tabs(["AI 报告", "统计汇总", "数据表"])
with tabs[0]:
    if report:
        st.markdown(report)
    else:
        st.info("还没有报告。运行 `python ai_summarize.py` 生成 report.md 后上传。")
with tabs[1]:
    if summary:
        for name, content in summary.items():
            with st.expander(name):
                st.json(content)
    else:
        st.info("还没有 summary.json。运行 `python bazi_pattern_analysis.py` 后上传。")
with tabs[2]:
    if csvs:
        pick = st.selectbox("选择数据表", list(csvs))
        st.dataframe(pd.read_csv(csvs[pick]), hide_index=True)
    else:
        st.info("上传 CSV 文件后可在这里查看，例如 ganzhi_by_position.csv、wuxing_patterns.csv。")
