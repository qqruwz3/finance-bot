import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sqlite3
import telebot
from telebot import types

# 1. Мини-веб-сервер для Render (занимает порт, чтобы сервис не выдавал ошибку)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# 2. Код вашего финансового бота
TOKEN = '8566395295:AAHdElzCClxH_XxveYdN1DJ8XhmD0MXwQWo'
bot = telebot.TeleBot(TOKEN)

def init_db():
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            comment TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_balance(user_id):
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, amount FROM transactions WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    balance = 0
    for row in rows:
        t_type, amount = row
        if t_type == 'income':
            balance += amount
        elif t_type == 'expense':
            balance -= amount
    return balance

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_balance = types.KeyboardButton('💰 Баланс')
    btn_history = types.KeyboardButton('📜 История трат')
    btn_add = types.KeyboardButton('➕ Добавить доход')
    btn_sub = types.KeyboardButton('➖ Списать расход')
    markup.add(btn_balance, btn_history, btn_add, btn_sub)
    bot.send_message(message.chat.id, 'Привет! Я твой бот-финансист. Выбери нужное действие:', reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == '💰 Баланс')
def show_balance(message):
    balance = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f'💵 **Действующий баланс накоплений:** `{balance:.2f} руб.`', parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '📜 История трат')
def show_history(message):
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()
    cursor.execute('SELECT type, amount, comment, date FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 5', (message.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, 'У вас пока нет записанных операций.')
        return
        
    response = '📜 **Последние 5 операций:**\n\n'
    for row in rows:
        t_type, amount, comment, date = row
        sign = '➕' if t_type == 'income' else '➖'
        response += f'{sign} **{amount} руб.** — {comment if comment else "Без описания"} _({date})_\n'
        
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

user_states = {}

@bot.message_handler(func=lambda msg: msg.text in ['➕ Добавить доход', '➖ Списать расход'])
def ask_amount(message):
    action = 'income' if message.text == '➕ Добавить доход' else 'expense'
    user_states[message.from_user.id] = {'action': action}
    bot.send_message(message.chat.id, 'Введите сумму и комментарий через пробел (например: `5000 Зарплата`):', parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and 'action' in user_states[msg.from_user.id])
def save_transaction(message):
    user_id = message.from_user.id
    state = user_states.pop(user_id)
    action = state['action']
    
    try:
        parts = message.text.split(maxsplit=1)
        amount = float(parts[0].replace(',', '.'))
        comment = parts[1] if len(parts) > 1 else ''
        
        conn = sqlite3.connect('finance.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO transactions (user_id, type, amount, comment) VALUES (?, ?, ?, ?)', 
                       (user_id, action, amount, comment))
        conn.commit()
        conn.close()
        
        word = 'добавлен' if action == 'income' else 'списан'
        bot.send_message(message.chat.id, f'✅ Успешно {word}: **{amount} руб.** ({comment})', parse_mode='Markdown')
    except ValueError:
        bot.send_message(message.chat.id, '❌ Неверный формат. Введите сумму числом (например: `1500 Продукты`).', parse_mode='Markdown')

print('Бот и веб-сервер запущены...')
bot.infinity_polling()
