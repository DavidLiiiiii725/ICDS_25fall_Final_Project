import tkinter as tk
from tkinter import scrolledtext, messagebox
from chat_client_class import Client
import argparse
import json
import requests
import io
import threading  # [必须] 导入 threading 模块以支持后台下载
from better_profanity import profanity  # [修改] 引入专业脏话过滤库 (需要 pip install better_profanity)
from PIL import Image, ImageTk  # 需要 pip install pillow

# [User Custom Imports] 保留你的自定义引用
from textblob.en import sentiment
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # 需要 pip install vaderSentiment

# =============================================================================
#  Configuration Area
# =============================================================================
# Common Emoji List
EMOJI_LIST = [
    "😀", "😂", "🤣", "😉", "😍", "😒", "😭", "😡",
    "💩", "🤡", "👻", "👽", "🤖", "👍", "👎", "🤝",
    "🙏", "💪", "❤️", "💔", "🎉", "🔥", "✨", "🚀",
    "👀", "🧠", "🍎", "☕", "⚽", "🎵", "💡", "📢"
]

# [新增] 指令说明文本
MENU_TEXT = """++++ Choose one of the following commands
time: calendar time in the system
who: to find out who else are there
c _peer_: to connect to the _peer_ and chat
p _#_: to get number <#> sonnet
q: to leave the chat system
bye: to leave the group chat
@bot _text_: to send text to chatbot
/aipic: to generate picture
/summary: to summarize your chat logs
/keyword: to summarize keywords in your chat"""


class ChatGUI:
    def __init__(self, master, args):
        self.master = master
        self.args = args
        self.client = Client(args)

        # [Added] Reference for storing image objects to prevent garbage collection
        self.loaded_images = []

        # [新增] 模式状态标记
        self.youth_mode = False
        self.senior_mode = False
        self.online_timer = None  # 用于存储30分钟提醒的定时器ID

        # [新增] 可视化计时器相关变量
        self.visual_timer_job = None
        self.youth_seconds = 0

        # [新增] 初始化脏话过滤库
        profanity.load_censor_words()

        master.title("ICDS Chat System")
        master.geometry("400x300")

        # 使用 grid 布局来让 login_frame 居中
        self.login_frame = tk.Frame(master, bg="#f0f2f5")
        self.chat_frame = tk.Frame(master, bg="#f0f2f5")

        self.build_login_screen()
        self.login_frame.pack(fill="both", expand=True)

    # =========================================================================
    #  Screen 1: Login Page (美化版 - 卡片式设计)
    # =========================================================================
    def build_login_screen(self):
        # 清空之前的布局
        for widget in self.login_frame.winfo_children():
            widget.destroy()

        # 配置 grid 权重以实现居中
        self.login_frame.grid_rowconfigure(0, weight=1)
        self.login_frame.grid_columnconfigure(0, weight=1)

        # === 1. 白色卡片容器 ===
        # 在灰色背景上放一个白色 Frame，以此实现“卡片”效果
        card_frame = tk.Frame(self.login_frame, bg="white", padx=40, pady=40)
        # 加上 relief 和 borderwidth 模拟轻微阴影/边框效果
        card_frame.configure(relief="flat", borderwidth=0)
        # 居中放置
        card_frame.grid(row=0, column=0)

        # === 2. 标题区域 ===
        lbl_icon = tk.Label(card_frame, text="💬", font=("Segoe UI Emoji", 40), bg="white", fg="#1877f2")
        lbl_icon.pack(pady=(0, 10))

        lbl_title = tk.Label(card_frame, text="Welcome Back", font=("Helvetica", 20, "bold"), bg="white", fg="#333")
        lbl_title.pack(pady=(0, 5))

        lbl_subtitle = tk.Label(card_frame, text="Sign in to your account", font=("Arial", 10), bg="white", fg="#777")
        lbl_subtitle.pack(pady=(0, 25))

        # === 3. 输入区域 ===
        # 创建一个 LabelFrame 或者 Frame 来包含输入框，增加内边距
        input_container = tk.Frame(card_frame, bg="white")
        input_container.pack(fill="x", pady=10)

        lbl_name = tk.Label(input_container, text="Username", font=("Arial", 10, "bold"), bg="white", fg="#555")
        lbl_name.pack(anchor="w", pady=(0, 5))

        # 美化输入框：去掉默认的立体边框，使用 solid 边框
        self.entry_name = tk.Entry(input_container, font=("Arial", 12), bg="#f9f9f9", fg="#333",
                                   relief="flat", highlightthickness=1, highlightbackground="#ddd",
                                   highlightcolor="#1877f2")
        self.entry_name.pack(fill="x", ipady=8)  # ipady 增加高度
        self.entry_name.focus_set()
        self.entry_name.bind("<Return>", self.do_login)

        # 错误提示 (默认隐藏)
        self.lbl_error = tk.Label(card_frame, text="", fg="#e74c3c", bg="white", font=("Arial", 9))
        self.lbl_error.pack(pady=(5, 10))

        # === 4. 登录按钮 ===
        # 使用 flat 样式和自定义颜色
        btn_login = tk.Button(card_frame, text="Sign In", command=self.do_login,
                              bg="#1877f2", fg="white", font=("Arial", 11, "bold"),
                              relief="flat", cursor="hand2")
        btn_login.pack(fill="x", ipady=5, pady=10)

        # 添加简单的鼠标悬停效果
        def on_enter(e):
            btn_login.config(bg="#155db2")  # 深蓝色

        def on_leave(e):
            btn_login.config(bg="#1877f2")  # 原色

        btn_login.bind("<Enter>", on_enter)
        btn_login.bind("<Leave>", on_leave)

        # 底部版权
        lbl_footer = tk.Label(card_frame, text="Powered by ICDS Chat", font=("Arial", 8), bg="white", fg="#aaa")
        lbl_footer.pack(pady=(20, 0))

    def do_login(self, event=None):
        name = self.entry_name.get().strip()
        if not name:
            self.lbl_error.config(text="⚠ Username cannot be empty")
            return
        try:
            if self.client.socket is None:
                self.client.init_chat()
            self.client.console_input.append(name)
            result = self.client.login()
            if result is True:
                self.switch_to_chat()
            elif result is False:
                self.lbl_error.config(text="⚠ Username already taken")
                self.client.system_msg = ''
            else:
                self.lbl_error.config(text="⚠ Server not responding")
        except Exception as e:
            self.lbl_error.config(text=f"⚠ Connection Error: {e}")
            self.client.socket = None

    # =========================================================================
    #  Screen 2: Chat Page
    # =========================================================================
    def switch_to_chat(self):
        self.login_frame.pack_forget()
        self.master.geometry("600x600")  # Adjust size slightly to display image
        self.master.resizable(True, True)
        self.master.configure(bg="#2c3e50")
        self.build_chat_screen()
        self.chat_frame.pack(fill="both", expand=True)
        self.update_chat_window()

    def build_chat_screen(self):
        # [修改] 顶部工具栏，放置模式按钮和指令按钮
        top_tool_frame = tk.Frame(self.chat_frame, bg="#34495e", height=40)
        top_tool_frame.pack(side=tk.TOP, fill=tk.X)

        # Youth Mode Button (最右侧)
        self.btn_youth = tk.Button(top_tool_frame, text="Youth Mode", command=self.toggle_youth_mode,
                                   bg="#2ecc71", fg="white", font=("Arial", 9, "bold"), relief="flat")
        self.btn_youth.pack(side=tk.RIGHT, padx=5, pady=5)

        # Senior Mode Button (青年模式左侧)
        self.btn_senior = tk.Button(top_tool_frame, text="Senior Mode", command=self.toggle_senior_mode,
                                    bg="#e67e22", fg="white", font=("Arial", 9, "bold"), relief="flat")
        self.btn_senior.pack(side=tk.RIGHT, padx=5, pady=5)

        # [新增] Commands Button (老年模式左侧)
        # 点击后弹出一个窗口显示指令，这样不占用主界面空间
        self.btn_help = tk.Button(top_tool_frame, text="📄 Commands", command=self.show_help_dialog,
                                  bg="#9b59b6", fg="white", font=("Arial", 9, "bold"), relief="flat")
        self.btn_help.pack(side=tk.RIGHT, padx=5, pady=5)

        # Online Timer Label (Visible only in Youth Mode)
        self.lbl_timer = tk.Label(top_tool_frame, text="", bg="#34495e", fg="#f1c40f", font=("Arial", 10, "bold"))
        self.lbl_timer.pack(side=tk.RIGHT, padx=10, pady=5)

        # Chat History Area (Set Emoji font support)
        self.chat_history = scrolledtext.ScrolledText(self.chat_frame, state='disabled',
                                                      font=("Segoe UI Emoji", 10), bg="white", fg="black")
        self.chat_history.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Style tag configuration
        self.chat_history.tag_config('me', foreground='blue', font=("Arial", 10, "bold"))
        self.chat_history.tag_config('system', foreground='green', font=("Arial", 10, "italic"))
        self.chat_history.tag_config('peer', foreground='red')
        # Bot message is purple
        self.chat_history.tag_config('bot', foreground='#8e44ad', font=("Arial", 10, "bold"))

        bottom_frame = tk.Frame(self.chat_frame, bg="#34495e", height=50)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.input_entry = tk.Entry(bottom_frame, font=("Segoe UI Emoji", 12), bg="white", relief="flat")
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.input_entry.bind("<Return>", self.send_message)
        self.input_entry.focus_set()

        # [Send Button]
        send_btn = tk.Button(bottom_frame, text="SEND", command=self.send_message,
                             bg="#2980b9", fg="white", font=("Arial", 10, "bold"), relief="flat")
        send_btn.pack(side=tk.RIGHT, padx=10, pady=10)

        # [Emoji Button]
        emoji_btn = tk.Button(bottom_frame, text="😀", command=self.open_emoji_panel,
                              bg="#f39c12", fg="white", font=("Segoe UI Emoji", 12), relief="flat")
        emoji_btn.pack(side=tk.RIGHT, padx=5, pady=10)

        self.display_message(f"Welcome {self.client.get_name()}!\n", 'system')

    # [新增] 显示指令的弹窗函数
    def show_help_dialog(self):
        help_window = tk.Toplevel(self.master)
        help_window.title("Available Commands")
        help_window.geometry("400x350")
        help_window.configure(bg="white")

        # 标题
        lbl_h_title = tk.Label(help_window, text="Commands List", font=("Arial", 14, "bold"), bg="white", fg="#333")
        lbl_h_title.pack(pady=10)

        # 文本区域
        txt_help = tk.Text(help_window, font=("Consolas", 10), bg="#f9f9f9", relief="flat", wrap="word", height=15)
        txt_help.pack(padx=20, pady=10, fill="both", expand=True)
        txt_help.insert("1.0", MENU_TEXT)
        txt_help.configure(state="disabled")  # 只读

        # 关闭按钮
        btn_close = tk.Button(help_window, text="Close", command=help_window.destroy,
                              bg="#95a5a6", fg="white", relief="flat")
        btn_close.pack(pady=10)

    # -------------------------------------------------------------------------
    #  Mode Toggle Logic
    # -------------------------------------------------------------------------
    def toggle_youth_mode(self):
        self.youth_mode = not self.youth_mode
        if self.youth_mode:
            self.btn_youth.config(bg="#27ae60", text="Youth Mode (ON)")
            self.display_message("[System] Youth Mode Enabled: Profanity filter on, 30min break reminder set.",
                                 'system')

            # 启动 30 分钟弹窗提醒
            self.start_break_timer()

            # [新增] 启动右上角可视计时器
            self.youth_seconds = 0
            self.update_visual_timer()
        else:
            self.btn_youth.config(bg="#2ecc71", text="Youth Mode")
            self.display_message("[System] Youth Mode Disabled.", 'system')

            # 停止提醒
            self.stop_break_timer()

            # [新增] 停止并隐藏可视计时器
            if self.visual_timer_job:
                self.master.after_cancel(self.visual_timer_job)
                self.visual_timer_job = None
            self.lbl_timer.config(text="")

    def toggle_senior_mode(self):
        self.senior_mode = not self.senior_mode
        if self.senior_mode:
            self.btn_senior.config(bg="#d35400", text="Senior Mode (ON)")
            self.display_message("[System] Senior Mode Enabled: Large text in chat box.", 'system')
            self.apply_fonts(large=True)
        else:
            self.btn_senior.config(bg="#e67e22", text="Senior Mode")
            self.display_message("[System] Senior Mode Disabled.", 'system')
            self.apply_fonts(large=False)

    def apply_fonts(self, large=False):
        # 调整字体大小
        text_size = 18 if large else 10
        tag_size = 18 if large else 10

        # 仅更新聊天记录框字体，保留输入框原有布局
        self.chat_history.configure(font=("Segoe UI Emoji", text_size))

        # 更新标签配置
        self.chat_history.tag_config('me', font=("Arial", tag_size, "bold"))
        self.chat_history.tag_config('system', font=("Arial", tag_size, "italic"))
        self.chat_history.tag_config('bot', font=("Arial", tag_size, "bold"))
        self.chat_history.tag_config('peer', font=("Arial", tag_size, "bold"))

    # -------------------------------------------------------------------------
    #  Profanity Filter & Timer Logic
    # -------------------------------------------------------------------------
    def filter_text(self, text):
        if not self.youth_mode:
            return text
        # [修改] 使用 better_profanity 进行过滤
        return profanity.censor(text)

    def start_break_timer(self):
        # 每30分钟 (30 * 60 * 1000 ms) 触发一次
        self.stop_break_timer()  # 防止重复开启
        self.online_timer = self.master.after(30 * 60 * 1000, self.break_reminder)

    def stop_break_timer(self):
        if self.online_timer:
            self.master.after_cancel(self.online_timer)
            self.online_timer = None

    def break_reminder(self):
        if self.youth_mode:
            self.display_message("--------------------------------------------------", 'system')
            self.display_message("You've been online for a long time—take a break!", 'system')
            self.display_message("--------------------------------------------------", 'system')
            # 重新开始计时，实现循环提醒
            self.start_break_timer()

    def update_visual_timer(self):
        """每秒更新右上角的在线时间"""
        if self.youth_mode:
            # 格式化时间 HH:MM:SS
            m, s = divmod(self.youth_seconds, 60)
            h, m = divmod(m, 60)
            self.lbl_timer.config(text=f"Online: {h:02d}:{m:02d}:{s:02d}")

            self.youth_seconds += 1
            # 安排下一秒更新
            self.visual_timer_job = self.master.after(1000, self.update_visual_timer)

    # -------------------------------------------------------------------------
    #  Emoji Functionality
    # -------------------------------------------------------------------------
    def open_emoji_panel(self):
        panel = tk.Toplevel(self.master)
        panel.title("Pick an Emoji")
        panel.geometry("300x250")
        panel.configure(bg="#f0f2f5")

        cols = 6
        for i, emoji in enumerate(EMOJI_LIST):
            btn = tk.Button(panel, text=emoji, font=("Segoe UI Emoji", 15),
                            relief="flat", bg="white",
                            command=lambda e=emoji: self.add_emoji(e))
            btn.grid(row=i // cols, column=i % cols, padx=3, pady=3, sticky="nsew")

        for i in range(cols):
            panel.grid_columnconfigure(i, weight=1)

    def add_emoji(self, emoji):
        self.input_entry.insert(tk.END, emoji)

    # -------------------------------------------------------------------------
    #  Message Sending Logic
    # -------------------------------------------------------------------------
    def send_message(self, event=None):
        msg = self.input_entry.get()

        if not msg:
            return

        # [Modified] Recognize @bot and /aipic:
        if msg.startswith("@bot") or msg.startswith("/aipic:"):
            # If it's /aipic:, send the complete command to the server for parsing
            if msg.startswith("/aipic:"):
                question = msg  # Send the complete "/aipic: prompt"
                display_text = f"[Me] AI Gen: {msg[7:]}\n"
            else:
                question = msg[4:].strip()  # Remove @bot
                display_text = f"[Me] @Bot: {question}\n"

            if len(question) > 0:
                self.display_message(display_text, 'me')
                try:
                    self.client.send_bot_ask(question)
                except Exception as e:
                    self.display_message(f"[System]: Send Error {e}\n", 'system')
        else:
            # [User Custom Logic - Commented Out]
            """# detect the emotion level of the text
            analyzer = SentimentIntensityAnalyzer()
            sentiment = analyzer.polarity_scores(msg)['compound']
            emotion = ''
            if sentiment <= -0.05:
                emotion = "[😡 negative]"
            elif -0.05 < sentiment < 0.05:
                emotion = "[😉 neutral]"
            elif sentiment > 0.05:
                emotion = "[😍 positive]"
            else:
                pass
            msg += ' ' + emotion"""
            self.display_message(f"[Me]: {msg}\n", 'me')
            self.client.console_input.append(msg)

        self.input_entry.delete(0, tk.END)
        if msg == 'q':
            self.master.quit()

    def display_message(self, message, tag=None):
        # [新增] 应用脏话过滤
        message = self.filter_text(message)

        message += '\n'
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, message, tag)
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    # -------------------------------------------------------------------------
    #  Threaded Image Download
    # -------------------------------------------------------------------------
    def insert_image_to_chat(self, photo, url):
        """
        辅助函数：在主线程中将图片对象插入到聊天记录。
        """
        try:
            # 保存引用，防止被垃圾回收
            self.loaded_images.append(photo)

            # 插入图片和换行
            self.chat_history.configure(state='normal')
            self.chat_history.image_create(tk.END, image=photo)
            self.chat_history.insert(tk.END, '\n')
            self.chat_history.see(tk.END)
            self.chat_history.configure(state='disabled')

            # 插入完成后，恢复消息轮询
            self.update_chat_window()
        except Exception as e:
            self.display_message(f"[System] Error inserting image into GUI: {e}\n", 'system')

    def download_and_display_image(self, url):
        """
        在后台线程中运行：下载和处理图片，避免阻塞 GUI。
        """
        try:
            # 1. 下载图片 (阻塞操作，但现在在后台线程中)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = response.content

            # 2. 使用 Pillow 处理
            img = Image.open(io.BytesIO(image_data))

            # 3. 缩放图片适应窗口
            base_width = 300
            w_percent = (base_width / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)

            # 4. 转换为 Tkinter 格式
            photo = ImageTk.PhotoImage(img)

            # 5. 将更新 UI 的任务调度回主线程
            self.master.after(0, self.insert_image_to_chat, photo, url)

        except Exception as e:
            error_msg = f"[System] Image load failed: {e}\n"
            # 调度错误消息显示
            self.master.after(0, self.display_message, error_msg, 'system')
            # 即使出错，也要恢复轮询
            self.master.after(100, self.update_chat_window)

    def display_image_async(self, url):
        """
        启动一个新线程来下载图片。
        """
        # 立即显示加载提示
        self.display_message("[AI Robot] is generating image, please wait...\n", 'bot')

        # 启动后台线程
        thread = threading.Thread(target=self.download_and_display_image, args=(url,))
        thread.daemon = True
        thread.start()

    # -------------------------------------------------------------------------
    #  [Core] Typewriter Effect Streaming Output
    # -------------------------------------------------------------------------
    def stream_message(self, text, tag, index=0):
        # [新增] 即使是流式输出，也需要过滤内容 (如果是 Youth Mode)
        if index == 0:
            text = self.filter_text(text)

        if index < len(text):
            self.chat_history.configure(state='normal')
            self.chat_history.insert(tk.END, text[index], tag)
            self.chat_history.see(tk.END)
            self.chat_history.configure(state='disabled')

            # Set typing speed: 30ms per character
            self.master.after(30, self.stream_message, text, tag, index + 1)
        else:
            # Typing finished, resume normal message polling
            self.update_chat_window()

    def update_chat_window(self):
        try:
            output = self.client.process()
            if output:
                # [Modified] Check for image URL
                if "IMAGE_URL:" in output:
                    try:
                        # Extract the URL part
                        parts = output.split("IMAGE_URL:", 1)
                        url = parts[1].strip()

                        # 调用异步显示函数
                        self.display_image_async(url)
                    except Exception as e:
                        self.display_message(f"[System] Error parsing image URL: {e}\n", 'system')
                        # 如果解析失败，手动恢复轮询
                        self.master.after(100, self.update_chat_window)
                    return  # 暂时停止轮询，等待图片下载完成

                # [Typewriter Logic] Recognize bot text messages
                if "[AI Robot]:" in output:
                    # Split prefix and content
                    parts = output.split("[AI Robot]: ", 1)

                    # 1. Display system message if any
                    if parts[0]:
                        self.display_message(parts[0], 'system')

                    # 2. Immediately display "[AI Robot]: " prefix
                    self.display_message("[AI Robot]: ", 'bot')

                    # 3. Stream the remaining content
                    self.stream_message(parts[1], 'bot')
                    return

                elif "System" in output:
                    self.display_message(output, 'system')
                else:
                    self.display_message(output)
        except Exception as e:
            print(f"Error: {e}")

        # Normal polling
        self.master.after(100, self.update_chat_window)


def main():
    parser = argparse.ArgumentParser(description='chat client argument')
    parser.add_argument('-d', type=str, default=None, help='server IP addr')
    args = parser.parse_args()

    root = tk.Tk()
    app = ChatGUI(root, args)
    root.mainloop()


if __name__ == '__main__':
    main()