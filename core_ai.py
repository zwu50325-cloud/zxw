"""调用 Claude 生成解读(不依赖 Streamlit)"""
import json

CLAUDE_MODEL = "claude-sonnet-5-5"


def build_prompt(bazi, astro):
    return ("下面是同一出生时间排出的八字与西方占星数据(JSON)。"
            "请用中文，分三部分写：1) 两套体系在这张盘里的相似点；"
            "2) 不同点(符号设计、时间敏感度、元素划分方式)；"
            "3) 无法对应的部分。把它们当作文化符号系统来分析，"
            "不要做命运预测，也不要声称有科学预测效力。\n\n"
            + json.dumps({"八字": bazi, "星盘": astro}, ensure_ascii=False))


def explain(bazi, astro, api_key, model=CLAUDE_MODEL, max_tokens=1500):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(model=model, max_tokens=max_tokens,
                                 messages=[{"role": "user", "content": build_prompt(bazi, astro)}])
    return msg.content[0].text
