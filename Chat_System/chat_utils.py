import socket
import time

# use local loop back address by default
CHAT_IP = '127.0.0.1'
# CHAT_IP = socket.gethostbyname(socket.gethostname())
# CHAT_IP = ''#socket.gethostbyname(socket.gethostname())

CHAT_PORT = 1112
SERVER = (CHAT_IP, CHAT_PORT)

menu = ("\n++++ Choose one of the following commands\n \
        time: calendar time in the system\n \
        who: to find out who else are there\n \
        c _peer_: to connect to the _peer_ and chat\n \
        ? _term_: to search your chat logs where _term_ appears\n \
        p _#_: to get number <#> sonnet\n \
        q: to leave the chat system\n \
        bye: to leave the group chat\n \
        @bot _text_: to send text to chatbot\n \
        /aipic: to generate picture\n \
        /summary: to summarize your chat logs\n \
        /keyword: to summerize keywords in you chat\n"
        )

S_OFFLINE   = 0
S_CONNECTED = 1
S_LOGGEDIN  = 2
S_CHATTING  = 3

SIZE_SPEC = 5

CHAT_WAIT = 0.2

def print_state(state):
    print('**** State *****::::: ')
    if state == S_OFFLINE:
        print('Offline')
    elif state == S_CONNECTED:
        print('Connected')
    elif state == S_LOGGEDIN:
        print('Logged in')
    elif state == S_CHATTING:
        print('Chatting')
    else:
        print('Error: wrong state')

def mysend(s, msg):
    #append size to message and send it
    msg = ('0' * SIZE_SPEC + str(len(msg)))[-SIZE_SPEC:] + str(msg)
    msg = msg.encode()
    total_sent = 0
    while total_sent < len(msg) :
        sent = s.send(msg[total_sent:])
        if sent==0:
            print('server disconnected')
            break
        total_sent += sent

def myrecv(s):
    #receive size first
    '''
    size = ''
    while len(size) < SIZE_SPEC:
        text = s.recv(SIZE_SPEC - len(size)).decode()
        if not text:
            print('disconnected')
            return('')
        size += text
    size = int(size)
    '''
    size_data = b''
    while len(size_data) < SIZE_SPEC:
        text = s.recv(SIZE_SPEC - len(size_data))
        if not text:
            print('disconnected')
            return ('')
        size_data += text
    try:
        # 先解码长度头，再转int
        size = int(size_data.decode())
    except ValueError:
        print('Invalid header received')
        return ''

    #now receive message
    '''
    msg = ''
    while len(msg) < size:
        text = s.recv(size-len(msg)).decode()
        #修正：应该判断 if text == '': 或者 if not text:。
        if text == '':
            print('disconnected')
            break
        msg += text
    #print ('received '+message)
    return (msg)
    '''
    # 2. 接收消息体
    msg_b = b''
    while len(msg_b) < size:
        # 注意：这里只接收 bytes，不 decode
        chunk = s.recv(size - len(msg_b))
        if not chunk:
            print('disconnected')
            return ''  # 或者抛出异常，取决于你的上层逻辑
        msg_b += chunk

    # 3. 接收完毕后，一次性解码
    try:
        msg = msg_b.decode()
    except UnicodeDecodeError:
        print('Decoding error')
        return ''

    return msg

def text_proc(text, user):
    ctime = time.strftime('%d.%m.%y,%H:%M', time.localtime())
    return('(' + ctime + ') ' + user + ' : ' + text) # message goes directly to screen
