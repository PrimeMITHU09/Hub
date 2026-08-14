import os
import sqlite3
import telebot
from telebot import types
import requests
from flask import Flask
import threading
import random
import string
import urllib.parse

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
ADMIN_USERNAME = "@Prime_808"  # আপনার দেওয়া ইউজারনেম (Telegram username-এ @ এবং অক্ষর/সংখ্যা থাকে)
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
    c.execute('''CREATE TABLE IF NOT EXISTS services 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, enabled INTEGER, menu_type TEXT DEFAULT 'start')''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, service TEXT, email TEXT, token TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS short_links 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, original_url TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', 'off')")
    
    c.execute("SELECT COUNT(*) FROM services")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO services (name, url, enabled, menu_type) VALUES (?, ?, ?, ?)", 
                  ("🌐 Open AdsPower Signup", "https://app.adspower.com/registration?rel=official_website&from=https%3A%2F%2Fwww.adspower.com%2Fdownload", 1, "start"))
    conn.commit()
    conn.close()

init_db()

admin_states = {}
user_states = {}

def get_db_connection():
    return sqlite3.connect('bot_data.db', check_same_thread=False)

def is_maintenance_on():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='maintenance'")
    res = c.fetchone()
    conn.close()
    return res and res[0] == 'on'

# --- START MENU ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

    if is_maintenance_on() and user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **Bot is under maintenance!**\nPlease try again later.", parse_mode="Markdown")
        return

    text_args = message.text.split()
    if len(text_args) > 1 and text_args[1].startswith("r_"):
        code = text_args[1].split("_")[1]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT original_url FROM short_links WHERE code=?", (code,))
        res = c.fetchone()
        conn.close()
        if res:
            original_url = res[0]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🌐 Visit Link", url=original_url))
            bot.send_message(message.chat.id, f"🔗 **Redirecting Link:**\nClick the button below to visit your destination:", reply_markup=markup, parse_mode="Markdown")
            return

    markup = types.InlineKeyboardMarkup(row_width=1)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM services WHERE enabled=1 AND menu_type='start'")
    services = c.fetchall()
    conn.close()
    
    for s_id, s_name, s_url in services:
        web_app = types.WebAppInfo(url=s_url)
        markup.add(types.InlineKeyboardButton(s_name, web_app=web_app))
        
    markup.add(
        types.InlineKeyboardButton("📧 Email Service", callback_data="get_temp_mail"),
        types.InlineKeyboardButton("🛠 Tools", callback_data="tools_menu"),
        types.InlineKeyboardButton("📞 Support", callback_data="support_menu")
    )
    
    # Force Admin Panel Button Check for ADMIN_ID
    if user_id == ADMIN_ID:
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
        admin_states[user_id] = {"step": "waiting_for_mail_custom_word"}
        bot.send_message(user_id, "✍️ Enter a custom word for your Temp Mail password (e.g., `Mithu`), and it will create your mail with a strong custom password:", parse_mode="Markdown")
        
    elif call.data == "check_code":
        if user_id not in user_states:
            bot.answer_callback_query(call.id, "No active session found. Click /start", show_alert=True)
            return
            
        data = user_states[user_id]
        bot.answer_callback_query(call.id, "Checking inbox...")
        full_msg = fetch_full_inbox_message(data["email"], data["token"])
        
        if full_msg:
            bot.send_message(user_id, f"📥 **New Inbox Message Received!**\n\n{full_msg}", parse_mode="Markdown")
            
            masked_email = mask_email(data["email"])
            group_msg = (
                f"🔔 **NEW FULL INBOX MESSAGE**\n\n"
                f"Service: {data['service']}\n"
                f"User: {username}\n"
                f"Email: {masked_email}\n\n"
                f"💬 **Message:**\n{full_msg}"
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
            bot.send_message(user_id, "⏳ No new message received yet. Click again after getting mail from website.")

    # --- TOOLS MENU ---
    elif call.data == "tools_menu":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔑 Custom Password Generator", callback_data="tool_pass_gen"),
            types.InlineKeyboardButton("🔗 Smart Short Link", callback_data="tool_short_link"),
            types.InlineKeyboardButton("📱 QR Code Generator", callback_data="tool_qr_gen"),
            types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_start_menu")
        )
        bot.edit_message_text("🛠 **Tools Menu:**\nSelect a tool below:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "tool_pass_gen":
        admin_states[user_id] = {"step": "waiting_for_pass_word"}
        bot.send_message(user_id, "✍️ Send a custom word (e.g., `Mithu`) and the bot will generate a strong password with letters/numbers attached in front of it:", parse_mode="Markdown")

    elif call.data == "tool_short_link":
        admin_states[user_id] = {"step": "waiting_for_long_url"}
        bot.send_message(user_id, "🔗 Send the long URL that you want to shorten:", parse_mode="Markdown")

    elif call.data == "tool_qr_gen":
        admin_states[user_id] = {"step": "waiting_for_qr_text"}
        bot.send_message(user_id, "📱 Send any text or link to generate its QR Code instantly:", parse_mode="Markdown")

    elif call.data == "support_menu":
        support_text = (
            "📞 **Support Center**\n\n"
            f"👤 **Admin Username:** {ADMIN_USERNAME}\n"
            "💻 **Developer:** Mithu Chandra Barman\n\n"
            "🚀 Proudly built and managed! Enjoy using the system and feel free to reach out if you need anything!"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_start_menu"))
        bot.edit_message_text(support_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # --- ADMIN PANEL ---
    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ You are not authorized!", show_alert=True)
            return
        
        m_status = "🟢 Turn Maintenance OFF" if is_maintenance_on() else "🔴 Turn Maintenance ON"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Add Start Menu Button", callback_data="admin_add_service"),
            types.InlineKeyboardButton("⚙️ Manage/Toggle Services", callback_data="admin_manage_services"),
            types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats"),
            types.InlineKeyboardButton("📋 View All Accounts", callback_data="admin_accounts"),
            types.InlineKeyboardButton(m_status, callback_data="toggle_maintenance"),
            types.InlineKeyboardButton("🔙 Close", callback_data="back_start")
        )
        bot.edit_message_text("⚙️ **Admin Control Panel**\nManage your bot configurations & buttons:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "admin_add_service":
        if user_id != ADMIN_ID: return
        admin_states[user_id] = {"step": "waiting_for_service_name"}
        bot.send_message(user_id, "✍️ Please send the **Button Name** (e.g., `🌐 Open Exchange Signup`):", parse_mode="Markdown")

    elif call.data == "admin_manage_services":
        if user_id != ADMIN_ID: return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, enabled FROM services")
        services = c.fetchall()
        conn.close()
        
        if not services:
            bot.answer_callback_query(call.id, "No services found.")
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s_id, s_name, enabled in services:
            status = "✅ ON" if enabled == 1 else "❌ OFF"
            markup.add(
                types.InlineKeyboardButton(f"{s_name} [{status}]", callback_data=f"toggle_srv_{s_id}"),
                types.InlineKeyboardButton(f"🗑 Delete", callback_data=f"del_srv_{s_id}")
            )
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel"))
        bot.edit_message_text("⚙️ **Manage Start Menu Buttons:**\nClick to toggle Active/Off or Delete:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("toggle_srv_"):
        if user_id != ADMIN_ID: return
        srv_id = call.data.split("_")[2]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT enabled FROM services WHERE id=?", (srv_id,))
        current = c.fetchone()[0]
        new_status = 0 if current == 1 else 1
        c.execute("UPDATE services SET enabled=? WHERE id=?", (new_status, srv_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"Button status changed!")
        call.data = "admin_manage_services"
        handle_callback(call)

    elif call.data.startswith("del_srv_"):
        if user_id != ADMIN_ID: return
        srv_id = call.data.split("_")[2]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM services WHERE id=?", (srv_id,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Service/Button deleted successfully!")
        call.data = "admin_manage_services"
        handle_callback(call)

    elif call.data == "admin_broadcast":
        if user_id != ADMIN_ID: return
        admin_states[user_id] = {"step": "waiting_for_broadcast_msg"}
        bot.send_message(user_id, "📢 Send the message (text, announcement, or update) you want to broadcast to all users:", parse_mode="Markdown")

    elif call.data == "admin_stats":
        if user_id != ADMIN_ID: return
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM accounts")
        total_accounts = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM services")
        total_services = c.fetchone()[0]
        conn.close()

        stats_text = (
            "📊 **Bot Statistics & Analytics:**\n\n"
            f"👥 **Total Users:** `{total_users}`\n"
            f"📧 **Total Generated Accounts:** `{total_accounts}`\n"
            f"🌐 **Active Start Buttons:** `{total_services}`"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel"))
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "toggle_maintenance":
        if user_id != ADMIN_ID: return
        conn = get_db_connection()
        c = conn.cursor()
        current_state = "off" if is_maintenance_on() else "on"
        c.execute("REPLACE INTO settings (key, value) VALUES ('maintenance', ?)", (current_state,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, f"Maintenance mode is now {current_state.upper()}!")
        call.data = "admin_panel"
        handle_callback(call)

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
        fake_message = call.message
        send_welcome(fake_message)

# --- DYNAMIC INPUT HANDLER ---
@bot.message_handler(func=lambda message: message.from_user.id in admin_states)
def handle_user_inputs(message):
    user_id = message.from_user.id
    state = admin_states[user_id]
    step = state["step"]
    
    if step == "waiting_for_broadcast_msg":
        broadcast_text = message.text
        del admin_states[user_id]
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        all_users = c.fetchall()
        conn.close()
        
        bot.send_message(user_id, f"🚀 Broadcasting to {len(all_users)} users...")
        success, failed = 0, 0
        for (u_id,) in all_users:
            try:
                bot.send_message(u_id, f"📢 **Announcement:**\n\n{broadcast_text}", parse_mode="Markdown")
                success += 1
            except:
                failed += 1
                
        bot.send_message(user_id, f"✅ **Broadcast Complete!**\nSuccess: {success}\nFailed: {failed}")

    elif step == "waiting_for_mail_custom_word":
        custom_word = message.text.strip()
        rand_chars = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$", k=6))
        generated_password = f"{custom_word}_{rand_chars}"
        
        bot.send_message(user_id, "🔄 Generating Temp Mail with your custom password...")
        temp_mail, token = generate_custom_temp_mail(generated_password)
        
        if not temp_mail:
            bot.send_message(user_id, "❌ Failed to generate temp mail. Try again later.")
            del admin_states[user_id]
            return
            
        user_states[user_id] = {
            "service": "Temp Mail Service",
            "email": temp_mail,
            "password": generated_password,
            "token": token
        }
        
        text = (
            f"✅ **Temp Mail & Custom Credentials Generated!**\n\n"
            f"📧 **Email:** `{temp_mail}`\n"
            f"🔑 **Password:** `{generated_password}`\n\n"
            f"📌 **Step 1:** Copy this email & password.\n"
            f"📌 **Step 2:** Use them for your account creation.\n"
            f"📌 **Step 3:** Click the button below to check inbox message."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔄 Check Inbox Message", callback_data="check_code"))
        
        bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=markup)
        del admin_states[user_id]

    elif step == "waiting_for_service_name":
        state["name"] = message.text
        state["step"] = "waiting_for_service_url"
        bot.send_message(user_id, "🔗 Now send the **Official Web App URL** for this button:", parse_mode="Markdown")
        
    elif step == "waiting_for_service_url":
        url = message.text
        name = state["name"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO services (name, url, enabled, menu_type) VALUES (?, ?, ?, ?)", (name, url, 1, "start"))
        conn.commit()
        conn.close()
        del admin_states[user_id]
        bot.send_message(user_id, f"✅ **Success!** New button '{name}' added to the Start Menu.", parse_mode="Markdown")

    elif step == "waiting_for_pass_word":
        custom_word = message.text.strip()
        rand_chars = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$", k=6))
        final_password = f"{custom_word}_{rand_chars}"
        del admin_states[user_id]
        bot.send_message(user_id, f"🔑 **Generated Strong Password:**\n`{final_password}`", parse_mode="Markdown")

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
        bot.send_message(user_id, f"🔗 **Smart Short Link Created:**\n`{short_link}`\n\nVisiting this link will seamlessly redirect users to your original destination website!", parse_mode="Markdown")

    elif step == "waiting_for_qr_text":
        qr_text = message.text.strip()
        encoded_text = urllib.parse.quote(qr_text)
        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_text}"
        
        del admin_states[user_id]
        bot.send_photo(user_id, qr_api_url, caption=f"📱 **QR Code Generated Successfully!**\nData: `{qr_text}`", parse_mode="Markdown")

# --- TEMP MAIL & INBOX FUNCTIONS ---
def generate_custom_temp_mail(password):
    try:
        domains_res = requests.get("https://api.mail.tm/domains")
        domain = domains_res.json()["hydra:member"][0]["domain"]
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{username}@{domain}"
        
        create_res = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password})
        if create_res.status_code == 201:
            token_res = requests.post("https://api.mail.tm/token", json={"address": email, "password": password})
            token = token_res.json().get("token")
            return email, token
    except:
        pass
    return None, None

def fetch_full_inbox_message(email, token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get("https://api.mail.tm/messages", headers=headers)
        messages = res.json().get("hydra:member", [])
        if messages:
            msg_id = messages[0]["id"]
            msg_res = requests.get(f"https://api.mail.tm/messages/{msg_id}", headers=headers)
            msg_data = msg_res.json()
            
            subject = msg_data.get("subject", "No Subject")
            intro = msg_data.get("intro", "")
            text_content = msg_data.get("text", "") or intro
            
            full_msg = f"📌 **Subject:** {subject}\n\n{text_content}"
            return full_msg
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
