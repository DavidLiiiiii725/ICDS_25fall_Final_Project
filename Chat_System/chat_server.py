import time
import socket
import select
import sys
import json
import threading
import pickle

from sumy.summarizers.text_rank import TextRankSummarizer

import bot_agent
from chat_utils import *
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import indexer_good
import jieba.analyse
try:
    # import nltk
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer

    # nltk.download('punkt')
except: pass
# === 引入辅助模块 ===
# 通常 Group 类在 chat_group.py 中
try:
    import chat_group
except ImportError:
    # 如果找不到文件，定义一个简单的 Group 桩代码防止报错
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

# 通常 Indexer 类在 indexer.py 中
try:
    from indexer import Indexer
except ImportError:
    # 桩代码
    class Indexer:
        def __init__(self, name): self.name = name

        def add_msg_and_index(self, msg): pass

        def search(self, term): return []

# === 引入 Bot Agent ===
# [修改] 引入 generate_image_url 以支持画图功能
from bot_agent import get_ai_response, generate_image_url


# ==============================================================================
# Sonnet Class (通常定义在 server 文件中，用于诗歌功能)
# ==============================================================================
class Sonnet:
    def __init__(self):
        self.index = 0
        self.sonnets = indexer_good.PIndex("AllSonnets.txt")

    def get_poem(self, idx):
        if 0 <= idx <= 109 :
            return self.sonnets.get_poem(idx)
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
        # [修复] 使用正确的模块引用
        self.group = chat_group.Group()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(SERVER)
        self.server.listen(5)
        self.all_sockets.append(self.server)
        self.indices = {}
        # [修复] 实例化本地定义的 Sonnet
        self.sonnet = Sonnet()

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

                        # [修复] 使用 Indexer 类
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
            # 尝试保存历史，如果报错则忽略
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

                # --- EXCHANGE ---
                elif msg["action"] == "exchange":
                    from_name = self.logged_sock2name[from_sock]
                    the_guys = self.group.list_me(from_name)
                    # said2 = text_proc(msg["message"], from_name) # text_proc may rely on external logic
                    # 简化处理，直接使用 msg
                    said2 = msg["message"]
                    flag, grp_idx = self.group.find_group(from_name)
                    #加入历史对话
                    if flag:
                        self.group.grp_msg[grp_idx].append(said2)
                    # detect the emotion level of the text
                    analyzer = SentimentIntensityAnalyzer()
                    sentiment = analyzer.polarity_scores(said2)['compound']
                    emotion = ''
                    if sentiment <= -0.05:
                        emotion = "[😡 Negative]"
                    elif -0.05 < sentiment < 0.05:
                        emotion = "[😐 Neutral]"
                    elif sentiment > 0.05:
                        emotion = "[😊 Positive]"
                    else:
                        pass
                    said2 += ' ' + emotion


                    if from_name in self.indices:
                        self.indices[from_name].add_msg_and_index(said2)

                    for g in the_guys[1:]:
                        to_sock = self.logged_name2sock[g]
                        if g in self.indices:
                            self.indices[g].add_msg_and_index(said2)
                        # mysend(to_sock,json.dumps({"action": "exchange", "from": msg["from"], "message": msg["message"]}))
                        mysend(to_sock,
                               json.dumps({"action": "exchange", "from": msg["from"], "message": said2}))

                    #总结关键词
                    print(said2)
                    if '/keyword' in said2[0:8]:
                        text = ''''''
                        for g in self.group.grp_msg[grp_idx]:
                            text += g+'\n'
                        tags = jieba.analyse.extract_tags(text,topK=5)
                        keywds = ' '.join(tags)
                        for g in the_guys[:]:
                            to_sock = self.logged_name2sock[g]
                            if g in self.indices:
                                self.indices[g].add_msg_and_index(said2)
                            # mysend(to_sock,json.dumps({"action": "exchange", "from": msg["from"], "message": msg["message"]}))
                            mysend(to_sock,
                                   json.dumps({"action": "exchange", "from": '[Summary]', "message": keywds}))

                    #总结全文
                    if '/summary' in said2[0:8]:
                        text = ''''''
                        for g in self.group.grp_msg[grp_idx]:
                            text += g+'\n'
                        parsers = PlaintextParser.from_string(text, Tokenizer('english'))
                        summarizer = TextRankSummarizer ()
                        reply = summarizer(text,sentences_count=3)

                        for g in the_guys[:]:
                            to_sock = self.logged_name2sock[g]
                            if g in self.indices:
                                self.indices[g].add_msg_and_index(said2)
                            # mysend(to_sock,json.dumps({"action": "exchange", "from": msg["from"], "message": msg["message"]}))
                            mysend(to_sock,
                                   json.dumps({"action": "exchange", "from": '[AI Robot]: ', "message": reply}))



                # --- [BOT ASK] (AI功能) ---
                elif msg["action"] == "bot_ask":
                    from_name = self.logged_sock2name[from_sock]
                    question = msg.get("message", "")
                    print(f"[Server] {from_name} asking Bot: {question}")

                    # 检查用户是否在群组中 (list_me 返回列表长度 > 1 表示有其他人或已连接)
                    # 注意：list_me 默认包含自己，所以 len > 1 意味着已经连接了 peer
                    if len(self.group.list_me(from_name)) > 1:
                        # === 群聊模式 ===

                        # 1. 广播用户的问题给群里其他人
                        people = self.group.list_me(from_name)
                        for ppl in people:
                            if ppl != from_name:
                                to_sock = self.logged_name2sock[ppl]
                                mysend(to_sock, json.dumps({
                                    "action": "exchange",
                                    "from": '[' + from_name + ']',
                                    "message": '@bot ' + question
                                }))

                        # 2. 定义后台任务处理 AI 回复
                        def run_ai_task_group(user, prompt):
                            try:
                                # [修改] 检测画图指令
                                if prompt.startswith("/aipic"):
                                    real_prompt = prompt[7:].strip()
                                    reply = generate_image_url(real_prompt)
                                else:
                                    reply = get_ai_response(user, prompt)

                                # 将回复广播给群组中的所有成员
                                group_members = self.group.list_me(user)
                                response = json.dumps({
                                    "action": "exchange",  # 群聊中使用 exchange
                                    "from": "[AI Robot]: ",  # 发送者显示为 [AI Robot]:
                                    "message": reply
                                })
                                for g in group_members:
                                    if g in self.logged_name2sock:
                                        to_sock = self.logged_name2sock[g]
                                        mysend(to_sock, response)
                                print(f"[Server] AI replied to group of {user}")
                            except Exception as e:
                                print(f"[Server Error] AI task failed: {e}")
                                # 错误只发给请求者
                                err_resp = json.dumps(
                                    {"action": "exchange", "from": "[AI Robot]: ", "message": "Error: Bot is busy."})
                                mysend(from_sock, err_resp)

                        t = threading.Thread(target=run_ai_task_group, args=(from_name, question))
                        t.daemon = True
                        t.start()

                    else:
                        # === 单人/Bot 聊天模式 ===
                        def run_ai_task_single(sock, user, prompt):
                            try:
                                # [修改] 检测画图指令
                                if prompt.startswith("/aipic:"):
                                    real_prompt = prompt[7:].strip()
                                    reply = generate_image_url(real_prompt)
                                else:
                                    reply = get_ai_response(user, prompt)

                                response = json.dumps({
                                    "action": "bot_res",  # 单聊使用 bot_res，客户端会显示为紫色 [AI Robot]
                                    "status": "success",
                                    "message": reply
                                })
                                mysend(sock, response)
                                print(f"[Server] AI replied to {user}")
                            except Exception as e:
                                print(f"[Server Error] AI task failed: {e}")
                                err_resp = json.dumps({"action": "bot_res", "message": "Error: Bot is busy."})
                                mysend(sock, err_resp)

                        t = threading.Thread(target=run_ai_task_single, args=(from_sock, from_name, question))
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
                    if from_name in self.indices:
                        search_rslt = '\n'.join([x[-1] for x in self.indices[from_name].search(term)])
                    else:
                        search_rslt = ""
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