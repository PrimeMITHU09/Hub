import os
import sqlite3
import telebot
from telebot import types
import requests
from flask import Flask
import threading

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    # Services table
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY, name TEXT, url TEXT, enabled INTEGER)''')
    # Accounts table
    c.execute('''CREATE TABLE IF NOT EXISTS accounts 
                 (id INTEGER PRIMARY KEY, user TEXT, email TEXT, token TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_services():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM services WHERE enabled=1")
    services = c.fetchall()
    conn.close()
    return services

# --- BOT LOGIC ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Load dynamic services
    services = get_services()
    for s in services:
        web_app = types.WebAppInfo(url=s[2])
        markup.add(types.InlineKeyboardButton(s[1], web_app=web_app))
        
    # Static buttons
    markup.add(
        types.InlineKeyboardButton("📧 Email Service", callback_data="get_temp_mail"),
        types.InlineKeyboardButton("🛠 Tools", callback_data="tools"),
        types.InlineKeyboardButton("📞 Support", url="https://t.me/your_support_username")
    )
    
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        
    bot.send_message(message.chat.id, "👋 Welcome! Choose an option:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "admin_panel":
        if call.from_user.id != ADMIN_ID: return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Service", callback_data="add_service"),
            types.InlineKeyboardButton("🗑 Remove Service", callback_data="rem_service"),
            types.InlineKeyboardButton("📋 View All Accounts", callback_data="view_acc"),
            types.InlineKeyboardButton("🔙 Back", callback_data="back_home")
        )
        bot.edit_message_text("⚙️ Admin Control Panel", call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    # ... (এখানে অন্যান্য হ্যান্ডলার যেমন add_service, view_acc এর লজিক বসবে)
    # আমি পরের ধাপে ফুল ডাইনামিক অ্যাডমিন কন্ট্রোল এবং ডেটাবেস অপারেশনসহ ফাইল দিচ্ছি।
