import requests
import urllib.parse  # 必须导入，用于处理图片生成的 URL 编码

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "Phi3:mini"

user_histories = {}
user_persona = {}


def set_persona(user, persona_text):
    user_persona[user] = persona_text


# =============================================================================
#  AI 图片生成函数
# =============================================================================
def generate_image_url(prompt):
    """
    使用 Pollinations.ai 生成图片。
    它接受 prompt，返回一个可以直接访问图片的 URL。
    """
    try:
        # 对提示词进行 URL 编码 (处理空格、特殊字符等)
        encoded_prompt = urllib.parse.quote(prompt)

        # 构造 API URL
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"

        # 返回特定前缀的字符串，客户端会识别这个前缀并显示图片
        return f"IMAGE_URL:{image_url}"
    except Exception as e:
        return f"Error generating image: {str(e)}"


# =============================================================================
#  [新增] NLP 功能：总结与关键词 (复用 Ollama)
# =============================================================================
def generate_summary(chat_history_text):
    """让 AI 总结聊天记录"""
    system_prompt = "You are a helpful assistant. Please summarize the following chat logs concisely in English."
    user_prompt = f"Chat logs:\n{chat_history_text}\n\nSummary:"
    return _call_ollama(system_prompt, user_prompt)


def generate_keywords(chat_history_text):
    """让 AI 提取关键词"""
    system_prompt = "You are a keyword extractor. Identify top 5 key topics or entities from the chat logs. Output only the keywords separated by commas."
    user_prompt = f"Chat logs:\n{chat_history_text}\n\nKeywords:"
    return _call_ollama(system_prompt, user_prompt)


def _call_ollama(sys_prompt, user_msg):
    """辅助函数：统一调用 Ollama，处理异常"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            "stream": False
        })
        if resp.status_code == 200:
            return resp.json()["message"]["content"]
        else:
            return "Error: LLM service unavailable."
    except Exception as e:
        return f"Error calling AI: {e}"


# =============================================================================
#  普通 AI 对话函数
# =============================================================================
def get_ai_response(user, content):
    history = user_histories.get(user, [])

    # 获取用户设定的人格，如果没有则使用默认值
    system_prompt = user_persona.get(
        user,
        "You are a friendly chatbot in a student chat room."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # 加入最近 10 条历史，保持上下文
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": content})

    try:
        # 发送请求给 Ollama
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False
        })

        # 检查请求是否成功
        if resp.status_code == 200:
            data = resp.json()
            reply = data["message"]["content"]
        else:
            reply = f"[Error] Ollama returned status {resp.status_code}. Is model '{MODEL_NAME}' available?"

    except Exception as e:
        return f"[Error] Connection to Ollama failed: {e}"

    # 更新历史记录
    history.append({"role": "user", "content": content})
    history.append({"role": "assistant", "content": reply})
    user_histories[user] = history

    return reply


if __name__ == "__main__":
    # 测试代码
    print("Testing AI Response...")
    print(get_ai_response('test_user', 'Hello!'))
    print("\nTesting Summary...")
    print(generate_summary("User1: Hi\nUser2: Hello, how are you?\nUser1: I am good, working on my python project."))