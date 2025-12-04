import requests
import json

def ask_ollama(prompt):
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "Phi3:mini",   # 确保你已经 ollama pull llama3 了
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    resp = requests.post(url, json=payload)

    # 先看一下 HTTP 状态码
    print("Status code:", resp.status_code)

    data = resp.json()

    # 调试用：看看 Ollama 实际返回什么结构
    print("Raw JSON:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # 按照 Ollama /api/chat 的格式，核心回复在 data["message"]["content"]
    print("\nAI:", data["message"]["content"])

if __name__ == "__main__":
    ask_ollama("用一句话介绍一下你自己")
