"""页面: AI 解读 — 让 Claude 对比这张盘里两套体系的相同点和不同点"""
import streamlit as st

from core_ai import explain
from core_compare import features
from ui_common import get_birth

b = get_birth()


def default_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:  # 没有配置 secrets 时
        return ""


st.write("让 Claude 根据当前命盘数据，写一份两套体系的相同点和不同点说明。")
key = st.text_input("Anthropic API Key", type="password", value=default_key())
if st.button("生成解读") and key:
    try:
        bazi, astro = features(b["dt"], b["bazi_dt"], b["lon"], b["lat"], b["tz"])
        with st.spinner("生成中…"):
            text = explain(bazi, astro, key)
        st.markdown(text)
    except Exception as e:
        st.error(f"调用失败：{e}")
elif not key:
    st.caption("填入 API Key 后点击按钮。Key 只用于本次请求，不会被保存。")
