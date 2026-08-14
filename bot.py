import os
import telebot
from telebot import types
import requests
from flask import Flask, render_template_string, request, jsonify

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
GROUP_ID = -1004491146716

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Temporary in-memory storage for web app communication
web_sessions = {}

# --- HTML TEMPLATE FOR MINI APP ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AdsPower Auto Registration</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #fff; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 25px; border-radius: 12px; width: 100%; max-width: 400px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        h2 { text-align: center; color: #38bdf8; margin-bottom: 20px; }
        .input-group { margin-bottom: 15px; }
        label { display: block; font-size: 14px; margin-bottom: 5px; color: #cbd5e1; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #475569; background: #0f172a; color: #fff; border-radius: 6px; box-sizing: border-box; }
        .checkbox-group { display: flex; align-items: center; margin-bottom: 20px; font-size: 14px; }
        .checkbox-group input { margin-right: 10px; width: 18px; height: 18px; }
        .btn { width: 100%; background: #0284c7; color: white; border: none; padding: 12px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; }
        .btn:hover { background: #0369a1; }
        .copy-hint { font-size: 12px; color: #94a3b8; text-align: center; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>AdsPower Auto Setup</h2>
        <form id="regForm" action="https://app.adspower.com/registration" method="GET" target="_blank">
            <div class="input-group">
                <label>Email Address</label>
                <input type="text" id="email" name="email" value="{{ email }}" readonly>
            </div>
            <div class="input-group">
                <label>Password</label>
                <input type="password" id="password" name="password" value="{{ password }}" readonly>
            </div>
            <div class="input-group">
                <label>Referral Code</label>
                <input type="text" id="ref" name="ref" value="ytregister" readonly>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="terms" checked required>
                <label for="terms" style="margin-bottom:0;">I have read and agree to Terms of Use</label>
            </div>
            <button type="submit" class="btn" onclick="notifyUser()">Proceed to Signup & CAPTCHA</button>
        </form>
        <div class="copy-hint">Clicking proceed will open AdsPower with your pre-filled credentials.</div>
    </div>
    <script>
        function notifyUser() {
            // Optional trigger back to bot if needed
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return "Bot & Web App is running successfully!"

@app.route('/register-page')
def register_page():
    user_id = request.args.get('user_id')
    if user_id and int(user_id) in user_states:
        data = user_states[int(user_id)]
        return render_template_string(HTML_TEMPLATE, email=data['email'], password=data['password'])
    return "Session expired or invalid user! Please open from the Telegram bot."

user_states = {}
accounts_db = []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📧 Generate Temp Mail & Auto-Fill Form", callback_data="get_temp_mail"))
    
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        
    bot.send_message(
        message.chat.id, 
        "👋 **Welcome to Service Hub!**\n\nClick below to generate your temp mail and open the auto-fill setup page:", 
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
            "service": "AdsPower Account",
            "email": temp_mail,
            "password": generated_password,
            "token": token
        }
        
        # Get your Render app's primary URL automatically or replace with your domain
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://hub-cigm.onrender.com")
        webapp_url = f"{render_url}/register-page?user_id={user_id}"
        
        web_app = types.WebAppInfo(url=webapp_url)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🚀 Open Auto-Fill Form", web_app=web_app))
        markup.add(types.InlineKeyboardButton("🔄 Check Verification Code", callback_data="check_code"))
        
        text = (
            f"✅ **Temp Mail & Credentials Ready!**\n\n"
            f"📧 **Email:** `{temp_mail}`\n"
            f"🔑 **Password:** `{generated_password}`\n\n"
            f"📌 Click **'Open Auto-Fill Form'** below to open your custom clean setup panel inside Telegram!"
        )
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "check_code":
        if user_id not in user_states:
            bot.answer_callback_query(call.id, "No active session found. Click /start", show_alert=True)
            return
            
        data = user_states[user_id]
        bot.answer_callback_query(call.id, "Checking inbox...")
        
        code = fetch_verification_code(data["email"], data["token"])
        
        if code:
            bot.send_message(
                user_id,
                f"🔐 **Verification Code Found!**\n\n"
                f"Code: `{code}`\n\n"
                f"🎉 Account setup completed.",
                parse_mode="Markdown"
            )
            
            masked_email = mask_email(data["email"])
            group_msg = (
                f"🔔 **NEW MAIL**\n\n"
                f"Service: {data['service']}\n"
                f"User: {username}\n"
                f"Email: {masked_email}\n"
                f"Code: `{code}`"
            )
            bot.send_message(GROUP_ID, group_msg, parse_mode="Markdown")
            accounts_db.append({"user": username, "service": data['service'], "email": data['email']})
            del user_states[user_id]
        else:
            bot.send_message(user_id, "⏳ No verification code received yet. Complete the registration and click again.")

    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ You are not authorized!", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 View Accounts", callback_data="admin_accounts"),
            types.InlineKeyboardButton("🔙 Close", callback_data="back_start")
        )
        bot.edit_message_text("⚙️ **Admin Control Panel**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "admin_accounts":
        if user_id != ADMIN_ID:
            return
        acc_text = "📋 **Recent Created Accounts:**\n\n"
        if not accounts_db:
            acc_text += "No accounts created yet."
        else:
            for acc in accounts_db[-10:]:
                acc_text += f"👤 {acc['user']} | 🛠 {acc['service']} | 📧 {acc['email']}\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_panel"))
        bot.edit_message_text(acc_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "back_start":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

def generate_temp_mail():
    try:
        domains_res = requests.get("https://api.mail.tm/domains")
        domain = domains_res.json()["hydra:member"][0]["domain"]
        import random, string
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
            
            import re
            codes = re.findall(r'\b\d{4,6}\b', content)
            if codes:
                return codes[0]
    except:
        pass
    return None

def mask_email(email):
    parts = email.split('@')
    return f"{parts[0][:2]}****@{parts[1]}"

if __name__ == "__main__":
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
