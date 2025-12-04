import time
import socket
import select
import sys
import json
from chat_utils import *
import client_state_machine as csm
import threading


class Client:
    def __init__(self, args):
        self.peer = ''
        self.console_input = []
        self.state = S_OFFLINE
        self.system_msg = ''
        self.local_msg = ''
        self.peer_msg = ''
        self.args = args
        self.name = ''
        self.socket = None

    def quit(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def get_name(self):
        return self.name

    def init_chat(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        svr = SERVER if self.args.d == None else (self.args.d, CHAT_PORT)
        self.socket.connect(svr)
        self.sm = csm.ClientSM(self.socket)
        reading_thread = threading.Thread(target=self.read_input)
        reading_thread.daemon = True
        reading_thread.start()

    def shutdown_chat(self):
        return

    def send(self, msg):
        mysend(self.socket, msg)

    def recv(self):
        return myrecv(self.socket)

    def get_msgs(self):
        read, write, error = select.select([self.socket], [], [], 0)
        my_msg = ''
        peer_msg = ''

        # 1. 处理来自服务器的信息
        if self.socket in read:
            peer_msg = self.recv()

        # 2. 处理来自 console / GUI 的信息
        if len(self.console_input) > 0:
            my_msg = self.console_input.pop(0)

        return my_msg, peer_msg

    def output(self):
        if len(self.system_msg) > 0:
            print(self.system_msg)
            self.system_msg = ''

    def login(self):
        my_msg, peer_msg = self.get_msgs()
        if len(my_msg) > 0:
            self.name = my_msg
            msg = json.dumps({"action": "login", "name": self.name})
            self.send(msg)
            response = json.loads(self.recv())
            if response["status"] == 'ok':
                self.state = S_LOGGEDIN
                self.sm.set_state(S_LOGGEDIN)
                self.sm.set_myname(self.name)
                self.print_instructions()
                return (True)
            elif response["status"] == 'duplicate':
                self.system_msg += 'Duplicate username, try again'
                return False
        else:
            return (False)

    def read_input(self):
        while True:
            text = sys.stdin.readline()[:-1]
            self.console_input.append(text)

    def print_instructions(self):
        self.system_msg += menu

    # =========================================================================
    #  GUI 核心逻辑
    # =========================================================================

    def send_bot_ask(self, question):
        """
        [新增] 专门用于发送机器人请求的方法
        使用 self.send() 确保通过 mysend 添加正确的协议头
        """
        msg = json.dumps({"action": "bot_ask", "message": question})
        self.send(msg)

    def process(self):
        """
        这个方法会被 GUI 定时器不断调用。
        它相当于原有 while 循环中的一次迭代。
        """
        # 登录阶段
        if self.state == S_OFFLINE:
            if self.login() == True:
                self.system_msg += 'Welcome, ' + self.get_name() + '!\n'

        # 正常聊天阶段
        else:
            self.proc()

        # 将 system_msg 返回给 GUI 显示，并清空 buffer
        output_text = self.system_msg
        self.system_msg = ''
        return output_text

    def proc(self):
        """
        核心处理逻辑
        """
        my_msg, peer_msg = self.get_msgs()

        # ==========================================================
        # [关键修改] 在这里拦截 Bot 的消息
        # 避免传给 State Machine (因为 SM 不认识 bot_res)
        # ==========================================================
        if len(peer_msg) > 0:
            try:
                msg_json = json.loads(peer_msg)
                if msg_json.get("action") == "bot_res":
                    # 直接格式化消息放入 buffer，不经过 SM
                    self.system_msg += "[AI Robot]: " + msg_json["message"] + "\n"
                    # 清空 peer_msg，防止状态机重复处理
                    peer_msg = ""
            except Exception as e:
                # 可能是普通聊天消息或者 JSON 解析失败，交给 SM 处理
                pass

        # 正常的聊天逻辑交给状态机
        self.system_msg += self.sm.proc(my_msg, peer_msg)

    # 保留原有的 run_chat 以兼容命令行模式
    def run_chat(self):
        self.init_chat()
        self.system_msg += 'Welcome to ICS chat\n'
        self.system_msg += 'Please enter your name: '
        self.output()
        while self.login() != True:
            self.output()
        self.system_msg += 'Welcome, ' + self.get_name() + '!'
        self.output()
        while self.sm.get_state() != S_OFFLINE:
            self.proc()
            self.output()
            time.sleep(CHAT_WAIT)
        self.quit()