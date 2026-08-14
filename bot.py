import os
import sqlite3
import telebot
from telebot import types
import requests
from flask import Flask
import threading
import re
import random
import string
import base64
import urllib.parse

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
GROUP_ID = -1004491146716

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    c = conn.cursor()
    # Services table for dynamic buttons/links
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, enabled INTEGER)''')
    # Accounts table for persistent mail tokens & records
    c.execute('''CREATE TABLE IF NOT EXISTS accounts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, service TEXT, email TEXT, token TEXT)''')
    # Short links table
    c.execute('''CREATE TABLE IF NOT EXISTS short_links 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, original_url TEXT)''')
    
    # Insert default AdsPower service if table is empty
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO services (name, url, enabled) VALUES (?, ?, ?)", 
                  ("🌐 Open AdsPower Signup", "https://app.adspower.com/registration?rel=official_website&from=https%3A%2F%2Fwww.adspower.com%2Fdownload", 1))
    conn.commit()
    conn.close()

init_db()

admin_states = {}
user_states = {}

def get_db_connection():
    return sqlite3.connect('bot_data.db', check_same_thread=False)

# --- START MENU ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Load dynamic services from DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM services WHERE enabled=1")
    services = c.fetchall()
    conn.close()
    
    for s_id, s_name, s_url in services:
        web_app = types.WebAppInfo(url=s_url)
        markup.add(types.InlineKeyboardButton(s_name, web_app=web_app))
        
    # Required Static Buttons
    markup.add(
        types.InlineKeyboardButton("📧 Email Service", callback_data="get_temp_mail"),
        types.InlineKeyboardButton("🛠 Tools", callback_data="tools_menu"),
        types.InlineKeyboardButton("📞 Support", url="https://t.me/your_support_username")
    )
    
    # Admin Panel Button
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        
    bot.send_message(
        message.chat.id, 
        "👋 **Welcome to Service Hub!**\n\nChoose an option below to proceed:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    
    if call.data == "get_temp_mail":
        bot.answer_callback_query(call.id, "Generating Temp Mail...")
        temp_mail, temp_pass, token = generate_temp_mail()
        if not temp_mail:
            bot.send_message(call.message.chat.id, "❌ Failed to generate temp mail. Try again later.")
            return
            
        generated_password = "P@ssw0rd_12345"
        user_states[user_id] = {
            "service": "Temp Mail Service",
            "email": temp_mail,
            "password": generated_password,
            "token": token
        }
        
        text = (
            f"✅ **Temp Mail & Credentials Generated!**\n\n"
            f"📧 **Email:** `{temp_mail}`\n"
            f"🔑 **Password:** `{generated_password}`\n\n"
            f"📌 **Step 1:** Copy this email & password.\n"
            f"📌 **Step 2:** Use them for your account creation.\n"
            f"📌 **Step 3:** Click the button below to check verification code."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔄 Check Verification Code", callback_data="check_code"))
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "check_code":
        if user_id not in user_states:
            bot.answer_callback_query(call.id, "No active session found. Click /start", show_alert=True)
            return
            
        data = user_states[user_id]
        bot.answer_callback_query(call.id, "Checking inbox...")
        code = fetch_verification_code(data["email"], data["token"])
        
        if code:
            bot.send_message(user_id, f"🔐 **Verification Code Found!**\n\nCode: `{code}`\n\n🎉 Process completed.", parse_mode="Markdown")
            
            masked_email = mask_email(data["email"])
            group_msg = (
                f"🔔 **NEW VERIFICATION**\n\n"
                f"Service: {data['service']}\n"
                f"User: {username}\n"
                f"Email: {masked_email}\n"
                f"Code: `{code}`"
            )
            bot.send_message(GROUP_ID, group_msg, parse_mode="Markdown")
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("INSERT INTO accounts (user, service, email, token) VALUES (?, ?, ?, ?)",
                      (username, data['service'], data['email'], data['token']))
            conn.commit()
            conn.close()
            del user_states[user_id]
        else:
            bot.send_message(user_id, "⏳ No verification code received yet. Click again after getting code from website.")

    # --- TOOLS MENU ---
    elif call.data == "tools_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔑 Custom Password Generator", callback_data="tool_pass_gen"),
            types.InlineKeyboardButton("🔗 Smart Short Link", callback_data="tool_short_link"),
            types.InlineKeyboardButton("🔠 Base64 Encoder/Decoder", callback_data="tool_base64"),
            types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_start_menu")
        )
        bot.edit_message_text("🛠 **Tools Menu:**\nSelect a tool below:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "tool_pass_gen":
        admin_states[user_id] = {"step": "waiting_for_pass_word"}
        bot.send_message(user_id, "✍️ Send a custom word (e.g., `Mithu`) and the bot will generate a strong password with letters/numbers attached in front of it:", parse_mode="Markdown")

    elif call.data == "tool_short_link":
        admin_states[user_id] = {"step": "waiting_for_long_url"}
        bot.send_message(user_id, "🔗 Send the long URL that you want to shorten:", parse_mode="Markdown")

    elif call.data == "tool_base64":
        admin_states[user_id] = {"step": "waiting_for_base64_text"}
        bot.send_message(user_id, "🔠 Send any text to encode/decode:", parse_mode="Markdown")

    # --- ADMIN PANEL ---
    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ You are not authorized!", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add New Service", callback_data="admin_add_service"),
            types.InlineKeyboardButton("🗑 Remove Service", callback_data="admin_rem_service"),
            types.InlineKeyboardButton("📋 View All Accounts", callback_data="admin_accounts"),
            types.InlineKeyboardButton("🔙 Close", callback_data="back_start")
        )
        bot.edit_message_text("⚙️ **Admin Control Panel**\nManage your bot configurations:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "admin_add_service":
        if user_id != ADMIN_ID: return
        admin_states[user_id] = {"step": "waiting_for_service_name"}
        bot.send_message(user_id, "✍️ Please send the **Name** of the new service (e.g., `🌐 Open Bybit Signup`):", parse_mode="Markdown")

    elif call.data == "admin_rem_service":
        if user_id != ADMIN_ID: return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, name FROM services")
        services = c.fetchall()
        conn.close()
        
        if not services:
            bot.answer_callback_query(call.id, "No services found to remove.")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s_id, s_name in services:
            markup.add(types.InlineKeyboardButton(f"❌ Remove: {s_name}", callback_data=f"del_srv_{s_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel"))
        bot.edit_message_text("🗑 **Select a service to remove:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("del_srv_"):
        if user_id != ADMIN_ID: return
        srv_id = call.data.split("_")[2]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM services WHERE id=?", (srv_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Service removed successfully!")
        bot.edit_message_text("✅ Service deleted. Click /start to refresh.", call.message.chat.id, call.message.message_id)

    elif call.data == "admin_accounts":
        if user_id != ADMIN_ID: return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT user, service, email FROM accounts ORDER BY id DESC LIMIT 15")
        accounts = c.fetchall()
        conn.close()
        
        acc_text = "📋 **Recent Created Accounts:**\n\n"
        if not accounts:
            acc_text += "No accounts recorded yet."
        else:
            for acc in accounts:
                acc_text += f"👤 {acc[0]} | 🛠 {acc[1]} | 📧 {acc[2]}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel"))
        bot.edit_message_text(acc_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "back_start":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
            
    elif call.data == "back_start_menu":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        # Trigger start message view again
        fake_message = call.message
        send_welcome(fake_message)

# --- DYNAMIC INPUT HANDLER (Tools & Admin) ---
@bot.message_handler(func=lambda message: message.from_user.id in admin_states)
def handle_user_inputs(message):
    user_id = message.from_user.id
    state = admin_states[user_id]
    step = state["step"]
    
    # Admin Service Add steps
    if step == "waiting_for_service_name":
        state["name"] = message.text
        state["step"] = "waiting_for_service_url"
        bot.send_message(user_id, "🔗 Now send the **Official Web App URL** for this service:", parse_mode="Markdown")
        
    elif step == "waiting_for_service_url":
        url = message.text
        name = state["name"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO services (name, url, enabled) VALUES (?, ?, ?)", (name, url, 1))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(user_id, f"✅ **Success!** New service '{name}' added to the Start Menu.", parse_mode="Markdown")

    # Tool: Password Generator
    elif step == "waiting_for_pass_word":
        custom_word = message.text.strip()
        rand_chars = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$", k=6))
        final_password = f"{custom_word}_{rand_chars}"
        del admin_states[user_id]
        bot.send_message(user_id, f"🔑 **Generated Strong Password:**\n`{final_password}`", parse_mode="Markdown")

    # Tool: Smart Short Link
    elif step == "waiting_for_long_url":
        long_url = message.text.strip()
        short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO short_links (code, original_url) VALUES (?, ?)", (short_code, long_url))
        conn.commit()
        conn.close()
        
        bot_username = bot.get_me().username
        short_link = f"https://t.me/{bot_username}?start=r_{short_code}"
        
        del admin_states[user_id]
        bot.send_message(user_id, f"🔗 **Smart Short Link Created:**\n`{short_link}`", parse_mode="Markdown")

# --- TEMP MAIL & OTP FUNCTIONS ---
def generate_temp_mail():
    try:
        domains_res = requests.get("https://api.mail.tm/domains")
        domain = domains_res.json()["hydra:member"][0]["domain"]
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{username}@{domain}"
        password = "Password123!"
        
        create_res = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password})
        if create_res.status_code == 201:
            token_res = requests.post("https://api.mail.tm/token", json={"address": email, "password": password})
            token = token_res.json().get("token")
            return email, password, token
    except:
        pass
    return None, None, None

def fetch_verification_code(email, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get("https://api.mail.tm/messages", headers=headers)
        messages = res.json().get("hydra:member", [])
        if messages:
            msg_id = messages[0]["id"]
            msg_res = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers)
            content = msg_res.json().get("text", "") or msg_res.json().get("intro", "")
            subject = msg_res.json().get("subject", "")
            full_text = content + " " + subject
            codes = re.findall(r'\b\d{4,6}\b', full_text)
            if codes:
                return codes[-1]
    except:
        pass
    return None

def mask_email(email):
    parts = email.split('@')
    return f"{parts[0][:2]}****@{parts[1]}"

if __name__ == "__main__":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
