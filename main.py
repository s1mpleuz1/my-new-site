import os
import re
import random
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

api_id = 26562792
api_hash = '3e444af1377f77f7b8e34198b095124c'
bot_token = '7093826124:AAGbKwsa5bJaai_kNLdUY3i1nI6nOEwOgsA'

PHONE, CODE, PASSWORD = range(3)

user_clients = {}  # user_id: {phone: TelegramClient}
user_tasks = {}    # user_id: {phone: Task}

emoji_map = {
    'Виноград': '🍇', 'Ананас': '🍍', 'Яблоко': '🍎', 'Клубника': '🍓', 'Арбуз': '🍉',
    'Банан': '🍌', 'Лимон': '🍋', 'Вишня': '🍒', 'Персик': '🍑', 'Манго': '🥭',
    'Груша': '🍐', 'Слива': '🫐', 'Черника': '🫐', 'Гранат': '🧃', 'Апельсин': '🍊',
    'Дыня': '🍈', 'Папайя': '🥭', 'Киви': '🥝', 'Инжир': '🍈', 'Огурец': '🥒',
    'Помидор': '🍅', 'Морковь': '🥕', 'Кукуруза': '🌽', 'Картофель': '🥔',
    'Баклажан': '🍆', 'Перец': '🫑', 'Чеснок': '🧄', 'Лук': '🧅', 'Горошек': '🫛',
    'Брокколи': '🥦', 'Салат': '🥬', 'Капуста': '🥬', 'Тыква': '🎃', 'Мёд': '🍯',
    'Кокос': '🥥', 'Авокадо': '🥑', 'Гриб': '🍄'
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Akkaunt qo‘shish", callback_data="add_account")],
        [InlineKeyboardButton("📋 Akkauntlar ro‘yxati", callback_data="list_accounts")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📍 Tanlang:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "add_account":
        await query.message.reply_text("📱 Telefon raqamingizni kiriting (masalan: +9989XX...):")
        return PHONE

    elif data == "list_accounts":
        await load_sessions(user_id)
        clients = user_clients.get(user_id, {})
        if not clients:
            await query.message.reply_text("❌ Hech qanday ulangan akkaunt yo‘q.")
            return

        for phone, client in clients.items():
            me = await client.get_me()
            keyboard = [
                [
                    InlineKeyboardButton("▶️ Start", callback_data=f"start:{phone}"),
                    InlineKeyboardButton("🛑 Stop", callback_data=f"stop:{phone}"),
                ],
                [InlineKeyboardButton("❌ Logout", callback_data=f"logout:{phone}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                f"👤 {me.first_name} | 📞 {phone} | 🆔 {me.id}",
                reply_markup=reply_markup
            )

    elif data.startswith("start:"):
        phone = data.split(":")[1]
        await start_click_session(query, user_id, phone)

    elif data.startswith("stop:"):
        phone = data.split(":")[1]
        await stop_click_session(query, user_id, phone)

    elif data.startswith("logout:"):
        phone = data.split(":")[1]
        await logout_session(query, user_id, phone)

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        await client.send_code_request(phone)
        context.user_data['client'] = client
        await update.message.reply_text("📩 Kodni kiriting:")
        return CODE
    except Exception as e:
        await update.message.reply_text(f"❌ Kod yuborishda xatolik: {e}")
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    phone = context.user_data['phone']
    client = context.user_data['client']
    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        await update.message.reply_text("🔐 2FA parolini kiriting:")
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ Kod xato: {e}")
        return ConversationHandler.END

    await save_session(update.effective_user.id, phone, client)
    await update.message.reply_text("✅ Muvaffaqiyatli ulanildi! /start orqali menyuga qayting.")
    return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    phone = context.user_data['phone']
    client = context.user_data['client']
    try:
        await client.sign_in(password=password)
    except Exception as e:
        await update.message.reply_text(f"❌ Parol xato: {e}")
        return ConversationHandler.END

    await save_session(update.effective_user.id, phone, client)
    await update.message.reply_text("🔐 Parol to‘g‘ri. ✅ Endi /start orqali menyuga qayting.")
    return ConversationHandler.END

async def save_session(user_id: int, phone: str, client: TelegramClient):
    os.makedirs("sessions", exist_ok=True)
    session_str = client.session.save()
    with open(f"sessions/{user_id}_{phone}.session", "w") as f:
        f.write(session_str)
    if user_id not in user_clients:
        user_clients[user_id] = {}
    user_clients[user_id][phone] = client

async def load_sessions(user_id: int):
    user_clients[user_id] = {}
    if not os.path.exists("sessions"):
        return
    for filename in os.listdir("sessions"):
        if filename.startswith(f"{user_id}_") and filename.endswith(".session"):
            phone = filename.split("_", 1)[1].replace(".session", "")
            with open(f"sessions/{filename}", "r") as f:
                session_str = f.read()
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            await client.connect()
            if await client.is_user_authorized():
                user_clients[user_id][phone] = client

async def remove_session(user_id: int, phone: str):
    if user_id in user_clients and phone in user_clients[user_id]:
        client = user_clients[user_id][phone]
        await client.log_out()
        await client.disconnect()
        del user_clients[user_id][phone]
    path = f"sessions/{user_id}_{phone}.session"
    if os.path.exists(path):
        os.remove(path)

async def start_click_session(query, user_id, phone):
    if user_id not in user_clients or phone not in user_clients[user_id]:
        await query.message.reply_text(f"❌ Akkaunt topilmadi: {phone}")
        return
    if user_id not in user_tasks:
        user_tasks[user_id] = {}
    if phone in user_tasks[user_id]:
        await query.message.reply_text(f"⚠️ Allaqachon ishlayapti: {phone}")
        return
    task = asyncio.create_task(auto_click_loop(user_id, phone))
    user_tasks[user_id][phone] = task
    await query.message.reply_text(f"▶️ Auto Clicker ishga tushdi: {phone}")

async def stop_click_session(query, user_id, phone):
    if user_id in user_tasks and phone in user_tasks[user_id]:
        task = user_tasks[user_id][phone]
        task.cancel()
        del user_tasks[user_id][phone]
        await query.message.reply_text(f"🛑 To‘xtatildi: {phone}")
    else:
        await query.message.reply_text(f"🚫 Ishlamayapti: {phone}")

async def logout_session(query, user_id, phone):
    await stop_click_session(query, user_id, phone)
    await remove_session(user_id, phone)
    await query.message.reply_text(f"✅ Logout qilindi: {phone}")

async def handle_captcha(client):
    async for msg in client.iter_messages('@patrickstarsrobot', limit=10):
        if msg.message and 'нажми на кнопку' in msg.message:
            match = re.search(r'где изображено «(.+?)»', msg.message)
            if match:
                fruit = match.group(1).strip()
                emoji = emoji_map.get(fruit)
                if not emoji:
                    return False
                if msg.buttons:
                    all_buttons = [btn for row in msg.buttons for btn in row]
                    random.shuffle(all_buttons)
                    for btn in all_buttons:
                        await asyncio.sleep(random.uniform(0.5, 1.2))
                        if emoji in btn.text:
                            await btn.click()
                            return True
    return False

async def auto_click_loop(user_id, phone):
    client = user_clients[user_id][phone]
    async with client:
        while True:
            try:
                await client.send_message('@patrickstarsrobot', '/start')
                await asyncio.sleep(random.uniform(2, 4))
                async for msg in client.iter_messages('@patrickstarsrobot', limit=10):
                    if msg.buttons:
                        for row in msg.buttons:
                            for btn in row:
                                if 'Кликер' in btn.text:
                                    await btn.click()
                                    await asyncio.sleep(2)
                                    solved = await handle_captcha(client)
                                    wait = 360 if solved else 1200
                                    await asyncio.sleep(wait)
            except Exception as e:
                print(f"Xatolik foydalanuvchi {user_id} ({phone}): {e}")
                await asyncio.sleep(10)

def main():
    app = Application.builder().token(bot_token).build()
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[]
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
