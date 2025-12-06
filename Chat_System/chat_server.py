import time
import socket
import select
import sys
import json
import threading
import pickle
from chat_utils import *

# === 引入辅助模块 ===
try:
    import chat_group
except ImportError:
    class Group:
        def __init__(self): self.members = {}

        def join(self, name): self.members[name] = []

        def is_member(self, name): return name in self.members

        def leave(self, name):
            if name in self.members: del self.members[name]

        def find_group_members(self, name): return []

        def connect(self, me, peer): pass

        def disconnect(self, me): pass

        def list_all(self): return ""

        def list_me(self, me): return [me]


    chat_group = type('obj', (object,), {'Group': Group})

try:
    from indexer import Indexer
except ImportError:
    class Indexer:
        def __init__(self, name): self.name = name

        def add_msg_and_index(self, msg): pass

        def search(self, term): return []

# === 引入 Bot Agent 的所有功能 ===
from bot_agent import get_ai_response, generate_image_url, generate_summary, generate_keywords


# ==============================================================================
# Sonnet Class
# ==============================================================================
class Sonnet:
    def __init__(self):
        self.index = 0
        self.sonnets = [
            ["The frolic architecture of the snow", "Assembled and disassembled when the wind",
             "Sits in a frolic temper on the ground"],
            ["Shall I compare thee to a summer's day?", "Thou art more lovely and more temperate"],
            ["Rough winds do shake the darling buds of May", "And summer's lease hath all too short a date"]
        ]

    def get_poem(self, idx):
        if 0 <= idx < len(self.sonnets):
            return self.sonnets[idx]
        return ["Unknown Sonnet"]


# ==============================================================================
# Server class
# ==============================================================================
class Server:
    def __init__(self):
        self.new_clients = []
        self.logged_name2sock = {}
        self.logged_sock2name = {}
        self.all_sockets = []
        self.group = chat_group.Group()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(SERVER)
        self.server.listen(5)
        self.all_sockets.append(self.server)
        self.indices = {}
        self.sonnet = Sonnet()

        # 用于存储群组聊天记录缓冲区，用于 NLP 分析
        self.chat_history_buffer = {}

    def new_client(self, sock):
        print('new client...')
        sock.setblocking(0)
        self.all_sockets.append(sock)
        self.new_clients.append(sock)

    def login(self, sock):
        try:
            msg = json.loads(myrecv(sock))
            if len(msg) > 0:
                if msg["action"] == "login":
                    name = msg["name"]
                    if self.group.is_member(name) != True:
                        self.new_clients.remove(sock)
                        self.logged_name2sock[name] = sock
                        self.logged_sock2name[sock] = name

                        if name not in self.indices.keys():
                            try:
                                self.indices[name] = Indexer(name)
                            except:
                                pass

                        print(name + ' logged in')
                        self.group.join(name)
                        mysend(sock, json.dumps({"action": "login", "status": "ok"}))
                    else:
                        mysend(sock, json.dumps({"action": "login", "status": "duplicate"}))
                        print(name + ' duplicate login attempt')
                else:
                    print('wrong code received')
            else:
                self.logout(sock)
        except Exception as e:
            print(f"Login Error: {e}")
            self.all_sockets.remove(sock)

    def logout(self, sock):
        try:
            name = self.logged_sock2name[sock]
            try:
                pickle.dump(self.indices[name], open(name + '.idx', 'wb'))
            except:
                pass
            del self.indices[name]
            del self.logged_name2sock[name]
            del self.logged_sock2name[sock]
            self.all_sockets.remove(sock)
            self.group.leave(name)
            sock.close()
        except:
            pass

    def handle_msg(self, from_sock):
        try:
            msg_str = myrecv(from_sock)
            if len(msg_str) > 0:
                msg = json.loads(msg_str)

                # --- CONNECT ---
                if msg["action"] == "connect":
                    to_name = msg["target"]
                    from_name = self.logged_sock2name[from_sock]
                    if to_name == from_name:
                        msg = json.dumps({"action": "connect", "status": "self"})
                    elif self.group.is_member(to_name):
                        to_sock = self.logged_name2sock[to_name]
                        self.group.connect(from_name, to_name)
                        the_guys = self.group.list_me(from_name)
                        msg = json.dumps({"action": "connect", "status": "success"})
                        for g in the_guys[1:]:
                            to_sock = self.logged_name2sock[g]
                            mysend(to_sock, json.dumps({"action": "connect", "status": "request", "from": from_name}))
                    else:
                        msg = json.dumps({"action": "connect", "status": "no-user"})
                    mysend(from_sock, msg)

                # --- EXCHANGE (主要聊天逻辑) ---
                elif msg["action"] == "exchange":
                    from_name = self.logged_sock2name[from_sock]
                    the_guys = self.group.list_me(from_name)
                    text_content = msg["message"]

                    # [1. 记录聊天历史]
                    group_key = tuple(sorted(the_guys))
                    if group_key not in self.chat_history_buffer:
                        self.chat_history_buffer[group_key] = []

                    self.chat_history_buffer[group_key].append(f"{from_name}: {text_content}")
                    if len(self.chat_history_buffer[group_key]) > 50:
                        self.chat_history_buffer[group_key].pop(0)

                    # [2. NLP 指令检测]
                    if text_content.startswith("/summary") or text_content.startswith("/keyword"):
                        print(f"[Server] NLP Processing for {from_name}...")
                        history_text = "\n".join(self.chat_history_buffer.get(group_key, []))

                        def run_nlp_task(command, context_text, target_group):
                            try:
                                result = ""
                                prefix = ""
                                if command.startswith("/summary"):
                                    prefix = "[📝 Chat Summary]\n"
                                    result = generate_summary(context_text)
                                elif command.startswith("/keyword"):
                                    prefix = "[🔑 Key Topics]\n"
                                    result = generate_keywords(context_text)

                                response = json.dumps({
                                    "action": "exchange",
                                    "from": "[AI Assistant]",
                                    "message": prefix + result
                                })

                                for member in target_group:
                                    if member in self.logged_name2sock:
                                        sock = self.logged_name2sock[member]
                                        mysend(sock, response)

                                print(f"[Server] NLP result sent to group.")
                            except Exception as e:
                                print(f"[Server Error] NLP Task: {e}")

                        t = threading.Thread(target=run_nlp_task, args=(text_content, history_text, the_guys))
                        t.daemon = True
                        t.start()

                    else:
                        # [3. 普通消息转发 - 修复双重显示]
                        for g in the_guys:
                            # [关键修改] 如果 g 是发送者自己，跳过发送
                            # 因为发送者的客户端已经本地回显了消息
                            if g == from_name:
                                continue

                            to_sock = self.logged_name2sock[g]
                            if g in self.indices:
                                self.indices[g].add_msg_and_index(text_content)

                            mysend(to_sock, json.dumps({
                                "action": "exchange",
                                "from": msg["from"],
                                "message": text_content
                            }))

                # --- BOT ASK (AI 聊天/图片) ---
                elif msg["action"] == "bot_ask":
                    from_name = self.logged_sock2name[from_sock]
                    question = msg.get("message", "")
                    print(f"[Server] {from_name} asking Bot: {question}")

                    in_group = len(self.group.list_me(from_name)) > 1

                    if in_group:
                        # 广播问题，但不发给提问者自己
                        people = self.group.list_me(from_name)
                        for ppl in people:
                            if ppl != from_name:
                                to_sock = self.logged_name2sock[ppl]
                                mysend(to_sock, json.dumps({
                                    "action": "exchange",
                                    "from": f"[{from_name}]",
                                    "message": f"@bot {question}"
                                }))

                    def run_ai_task(sock, user, prompt, is_group):
                        try:
                            if prompt.startswith("/aipic"):
                                real_prompt = prompt[6:].strip()
                                if real_prompt.startswith(":"): real_prompt = real_prompt[1:].strip()
                                reply = generate_image_url(real_prompt)
                            else:
                                reply = get_ai_response(user, prompt)

                            if is_group:
                                response = json.dumps({
                                    "action": "exchange",
                                    "from": "[AI Robot]",
                                    "message": reply
                                })
                                group_members = self.group.list_me(user)
                                for g in group_members:
                                    if g in self.logged_name2sock:
                                        mysend(self.logged_name2sock[g], response)
                            else:
                                response = json.dumps({
                                    "action": "bot_res",
                                    "status": "success",
                                    "message": reply
                                })
                                mysend(sock, response)

                        except Exception as e:
                            print(f"AI Task Error: {e}")

                    t = threading.Thread(target=run_ai_task, args=(from_sock, from_name, question, in_group))
                    t.daemon = True
                    t.start()

                # --- LIST ---
                elif msg["action"] == "list":
                    msg = self.group.list_all()
                    mysend(from_sock, json.dumps({"action": "list", "results": msg}))

                # --- POEM ---
                elif msg["action"] == "poem":
                    poem_indx = int(msg["target"])
                    poem = self.sonnet.get_poem(poem_indx)
                    poem = '\n'.join(poem).strip()
                    mysend(from_sock, json.dumps({"action": "poem", "results": poem}))

                # --- TIME ---
                elif msg["action"] == "time":
                    ctime = time.strftime('%d.%m.%y,%H:%M', time.localtime())
                    mysend(from_sock, json.dumps({"action": "time", "results": ctime}))

                # --- SEARCH ---
                elif msg["action"] == "search":
                    term = msg["target"]
                    from_name = self.logged_sock2name[from_sock]
                    search_rslt = ""
                    if from_name in self.indices:
                        search_rslt = '\n'.join([x[-1] for x in self.indices[from_name].search(term)])
                    mysend(from_sock, json.dumps({"action": "search", "results": search_rslt}))

                # --- DISCONNECT ---
                elif msg["action"] == "disconnect":
                    from_name = self.logged_sock2name[from_sock]
                    the_guys = self.group.list_me(from_name)
                    self.group.disconnect(from_name)
                    the_guys.remove(from_name)
                    if len(the_guys) == 1:
                        g = the_guys.pop()
                        to_sock = self.logged_name2sock[g]
                        mysend(to_sock, json.dumps({"action": "disconnect"}))
            else:
                self.logout(from_sock)
        except Exception as e:
            print(f"Handle Msg Error: {e}")
            self.logout(from_sock)

    def run(self):
        print('starting server...')
        while (1):
            read, write, error = select.select(self.all_sockets, [], [])
            for logc in list(self.logged_name2sock.values()):
                if logc in read:
                    self.handle_msg(logc)
            for newc in self.new_clients[:]:
                if newc in read:
                    self.login(newc)
            if self.server in read:
                sock, address = self.server.accept()
                self.new_client(sock)


def main():
    server = Server()
    server.run()


if __name__ == "__main__":
    main()