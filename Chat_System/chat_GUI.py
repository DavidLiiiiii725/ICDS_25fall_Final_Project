import tkinter as tk
from tkinter import scrolledtext, messagebox

from textblob.en import sentiment

from chat_client_class import Client
import argparse
import json
import requests
import io
from PIL import Image, ImageTk  # 需要 pip install pillow
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # 需要 pip install vaderSentiment

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


class ChatGUI:
    def __init__(self, master, args):
        self.master = master
        self.args = args
        self.client = Client(args)

        # [Added] Reference for storing image objects to prevent garbage collection
        self.loaded_images = []

        master.title("ICDS Chat System")
        master.geometry("400x300")

        self.login_frame = tk.Frame(master, bg="#f0f2f5")
        self.chat_frame = tk.Frame(master, bg="#f0f2f5")

        self.build_login_screen()
        self.login_frame.pack(fill="both", expand=True)

    # =========================================================================
    #  Screen 1: Login Page
    # =========================================================================
    def build_login_screen(self):
        lbl_title = tk.Label(self.login_frame, text="ICS Chat Login",
                             font=("Helvetica", 20, "bold"), bg="#f0f2f5", fg="#333")
        lbl_title.pack(pady=(50, 20))

        input_frame = tk.Frame(self.login_frame, bg="#f0f2f5")
        input_frame.pack(pady=10)

        lbl_name = tk.Label(input_frame, text="Username:", font=("Arial", 12), bg="#1877f2", fg="white")
        lbl_name.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.entry_name = tk.Entry(input_frame, font=("Arial", 12), bg="#1877f2", fg="white")
        self.entry_name.grid(row=0, column=1, padx=5, pady=5)
        self.entry_name.focus_set()
        self.entry_name.bind("<Return>", self.do_login)

        self.lbl_error = tk.Label(self.login_frame, text="", fg="red", bg="#f0f2f5", font=("Arial", 10))
        self.lbl_error.pack(pady=5)

        btn_login = tk.Button(self.login_frame, text="Join Chat", command=self.do_login,
                              bg="#1877f2", fg="white", font=("Arial", 12, "bold"),
                              width=15, relief="flat")
        btn_login.pack(pady=20)

    def do_login(self, event=None):
        name = self.entry_name.get().strip()
        if not name:
            self.lbl_error.config(text="Please enter a username.")
            return
        try:
            if self.client.socket is None:
                self.client.init_chat()
            self.client.console_input.append(name)
            result = self.client.login()
            if result is True:
                self.switch_to_chat()
            elif result is False:
                self.lbl_error.config(text="Username taken.")
                self.client.system_msg = ''
            else:
                self.lbl_error.config(text="Server not responding.")
        except Exception as e:
            self.lbl_error.config(text=f"Connection Error: {e}")
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
    #  Message Sending Logic (Added /aipic: recognition)
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
        message+='\n'

        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, message, tag)
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    # -------------------------------------------------------------------------
    #  [Modified] Image Display Function
    # -------------------------------------------------------------------------
    def display_image(self, url):
        try:
            # 1. Download image
            # [CRITICAL CHANGE]: Increased timeout from 10 to 30 seconds
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = response.content

            # 2. Process with Pillow
            img = Image.open(io.BytesIO(image_data))

            # 3. Scale image to fit chat window (e.g., max width 300)
            base_width = 300
            w_percent = (base_width / float(img.size[0]))
            h_size = int((float(img.size[1]) * float(w_percent)))
            img = img.resize((base_width, h_size), Image.Resampling.LANCZOS)

            # 4. Convert to Tkinter format
            photo = ImageTk.PhotoImage(img)

            # 5. [Key] Save reference to prevent garbage collection
            self.loaded_images.append(photo)

            # 6. Insert into chat window
            self.chat_history.configure(state='normal')
            self.chat_history.image_create(tk.END, image=photo)
            self.chat_history.insert(tk.END, '\n')  # Newline after image
            self.chat_history.see(tk.END)
            self.chat_history.configure(state='disabled')

        except Exception as e:
            self.display_message(f"[System] Image load failed: {e}\n", 'system')

    # -------------------------------------------------------------------------
    #  [Core] Typewriter Effect Streaming Output
    # -------------------------------------------------------------------------
    def stream_message(self, text, tag, index=0):
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
                # [New] Check for image URL
                # Assuming Server returns format like: "[AI Robot]: IMAGE_URL:https://..."
                if "IMAGE_URL:" in output:
                    try:
                        # Extract the URL part
                        # Format could be "[AI Robot]: IMAGE_URL:http..." or just "IMAGE_URL:http..."
                        parts = output.split("IMAGE_URL:", 1)
                        url = parts[1].strip()

                        self.display_message("[AI Robot] generated an image:\n", 'bot')
                        self.display_image(url)
                    except Exception as e:
                        self.display_message(f"[System] Error parsing image URL: {e}\n", 'system')
                    return  # Image displayed, return directly, skip typewriter logic

                # [Typewriter Logic] Recognize bot text messages
                if "[AI Robot]:" in output:
                    # Split prefix and content. Assuming format is "[AI Robot]: Hello..."
                    parts = output.split("[AI Robot]: ", 1)

                    # 1. Display system message if any
                    if parts[0]:
                        self.display_message(parts[0], 'system')

                    # 2. Immediately display "[AI Robot]: " prefix
                    self.display_message("[AI Robot]: ", 'bot')

                    # 3. Stream the remaining content
                    # Note: Return exits the function, pausing polling, waiting for typewriter animation to finish
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


main()