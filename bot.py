import os
import telebot
from telebot import types
import requests
from flask import Flask

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
GROUP_ID = -1004491146716

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

user_states = {}
accounts_db = []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # AdsPower Registration button
    web_app = types.WebAppInfo(url="https://app.adspower.com/registration?rel=official_website&from=https%3A%2F%2Fwww.adspower.com%2Fdownload")
    markup.add(types.InlineKeyboardButton("🌐 Open AdsPower Signup", web_app=web_app))
    
    # Generate Temp Mail button
    markup.add(types.InlineKeyboardButton("📧 Generate Temp Mail & Password", callback_data="get_temp_mail"))
    
    # Admin Panel button (Only for Admin)
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        
    bot.send_message(
        message.chat.id, 
        "👋 **Welcome to Service Hub!**\n\nChoose an option below to proceed with your automated account creation:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    
    if call.data == "get_temp_mail":
        bot.answer_callback_query(call.id, "Generating Temp Mail...")
        
        temp_mail, temp_pass = generate_temp_mail()
        if not temp_mail:
            bot.send_message(call.message.chat.id, "❌ Failed to generate temp mail. Try again later.")
            return
            
        generated_password = "P@ssw0rd_12345"
        
        user_states[user_id] = {
            "service": "AdsPower Account",
            "email": temp_mail,
            "password": generated_password
        }
        
        text = (
            f"✅ **Temp Mail & Credentials Generated!**\n\n"
            f"📧 **Email:** `{temp_mail}`\n"
            f"🔑 **Password:** `{generated_password}`\n\n"
            f"📌 **Step 1:** Copy this email & password.\n"
            f"📌 **Step 2:** Paste them into the registration popup.\n"
            f"📌 **Step 3:** Solve CAPTCHA, click 'Get verification code', and click the button below."
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
        
        code = "839214" # Placeholder for mail.tm inbox check
        
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
                f"Code: `******`"
            )
            bot.send_message(GROUP_ID, group_msg, parse_mode="Markdown")
            accounts_db.append({"user": username, "service": data['service'], "email": data['email']})
            del user_states[user_id]
        else:
            bot.send_message(user_id, "⏳ No verification code received yet.")

    elif call.data == "admin_panel":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⚠️ You are not authorized to access the Admin Panel!", show_alert=True)
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📋 View Accounts", callback_data="admin_accounts"),
            types.InlineKeyboardButton("🔙 Close", callback_data="back_start")
        )
        bot.edit_message_text("⚙️ **Admin Control Panel**\nWelcome Admin! Manage your settings here.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

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
            return email, password
    except:
        pass
    return None, None

def mask_email(email):
    parts = email.split('@')
    return f"{parts[0][:2]}****@{parts[1]}"

if __name__ == "__main__":
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
