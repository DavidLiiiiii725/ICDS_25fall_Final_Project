import requests
import urllib.parse  # [新增] 必须导入这个库用于 URL 编码

OLLAMA_URL = "http://localhost:11434/api/chat"
# MODEL_NAME = "Phi3:mini"
MODEL_NAME = "qwen3:4b"

user_histories = {}  # {user_name: [msg1, msg2, ...]}
user_persona = {}  # {user_name: "system prompt ..."}


def set_persona(user, persona_text):
    user_persona[user] = persona_text


# =============================================================================
#  [新增] AI 图片生成函数
# =============================================================================
def generate_image_url(prompt):
    """
    使用 Pollinations.ai 生成图片。
    它接受 prompt，返回一个可以直接访问图片的 URL。
    """
    try:
        # 1. 对提示词进行 URL 编码 (处理空格、特殊字符等)
        # 例如: "a cute cat" -> "a%20cute%20cat"
        encoded_prompt = urllib.parse.quote(prompt)

        # 2. 构造 API URL
        # Pollinations.ai 的格式: https://image.pollinations.ai/prompt/{prompt}
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"

        # 3. 返回特定前缀的字符串
        # 客户端 (chat_gui.py) 会检测 "IMAGE_URL:" 前缀来决定显示图片而不是文本
        return f"IMAGE_URL:{image_url}"

    except Exception as e:
        return f"Error generating image: {str(e)}"


# =============================================================================
#  AI 对话函数
# =============================================================================
def get_ai_response(user, content):
    history = user_histories.get(user, [])

    system_prompt = user_persona.get(
        user,
        "You are a friendly chatbot in a student chat room."
    )

    messages = [{"role": "system", "content": system_prompt}]
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

    history.append({"role": "user", "content": content})
    history.append({"role": "assistant", "content": reply})
    user_histories[user] = history

    return reply

if __name__ == "__main__":
    print(get_ai_response('','summarize this: my name is david'))