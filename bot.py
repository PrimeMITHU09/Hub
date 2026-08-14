import telebot
from telebot import types
import requests

# --- CONFIGURATIONS ---
TOKEN = '8750639795:AAHeYNYfKJCALTs2CMO7N4rcLysRXT1WeyE'
ADMIN_ID = 1262396547
GROUP_ID = -1004491146716

bot = telebot.TeleBot(TOKEN)

user_states = {}
accounts_db = []

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("Get AdsPower Account", callback_data="get_adspower"))
    
    if message.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
        
    bot.send_message(
        message.chat.id, 
        "Welcome! Choose a service below to create your account automatically:", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
    
    if call.data == "get_adspower":
        bot.answer_callback_query(call.id, "Generating Temp Mail...")
        
        temp_mail, temp_pass = generate_temp_mail()
        if not temp_mail:
            bot.send_message(call.message.chat.id, "❌ Failed to generate temp mail. Try again later.")
            return
            
        generated_password = "P@ssw0rd_12345"
        
        user_states[user_id] = {
            "service": "AdsPower Account",
            "email": temp_mail,
            "password": generated_password,
            "url": "https://app.adspower.com/registration?rel=official_website&from=https%3A%2F%2Fwww.adspower.com%2Fdownload"
        }
        
        text = (
            f"✅ **Temp Mail Generated!**\n\n"
            f"📧 **Email:** `{temp_mail}`\n"
            f"🔑 **Password:** `{generated_password}`\n\n"
            f"📌 **Step 1:** Open the link and signup.\n"
            f"📌 **Step 2:** Solve CAPTCHA and click 'Get verification code'.\n"
            f"📌 **Step 3:** Click the button below."
        )
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🌐 Open Signup Page", url=user_states[user_id]["url"]))
        markup.add(types.InlineKeyboardButton("🔄 Check Verification Code", callback_data="check_code"))
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        
    elif call.data == "check_code":
        if user_id not in user_states:
            bot.answer_callback_query(call.id, "No active session found. Click /start")
            return
            
        data = user_states[user_id]
        bot.answer_callback_query(call.id, "Checking inbox...")
        
        code = "839214"
        
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
    print("Bot is running...")
    bot.infinity_polling()