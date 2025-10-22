import os
import json
import random
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7633032473  # <-- O'zingizning Telegram ID
DATA_FILE = Path("/data/anime_db.json")
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

from edit_handlers import handle_text_input  # ✅ Tahrirlash faylini chaqiramiz


# --- Yordamchi funksiyalar ---
def load_data():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎞 Anime qo‘shish", callback_data="add_anime")],
        [InlineKeyboardButton("📜 Barcha animelar", callback_data="list_anime")],
        [InlineKeyboardButton("🛠 Tahrirlash", callback_data="edit_anime")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Salom! Anime botga xush kelibsiz!", reply_markup=reply_markup)


# --- Tugmalar ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    db = load_data()

    if data == "add_anime":
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
            return
        await query.edit_message_text("🆕 Yangi anime nomini kiriting:")
        context.user_data["adding_anime"] = True

    elif data == "list_anime":
        if not db:
            await query.edit_message_text("📂 Hozircha anime bazasi bo‘sh.")
            return
        text = "📜 *Barcha animelar:*\n\n"
        for title, info in db.items():
            text += f"🎬 {title} — Kod: `{info.get('code', '---')}`\n"
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "edit_anime":
        if query.from_user.id != ADMIN_ID:
            await query.edit_message_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
            return
        if not db:
            await query.edit_message_text("📂 Hozircha anime bazasi bo‘sh.")
            return
        keyboard = [
            [InlineKeyboardButton(title, callback_data=f"edit_{title}")]
            for title in db.keys()
        ]
        await query.edit_message_text("✏️ Tahrirlamoqchi bo‘lgan animeni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("edit_"):
        title = data.replace("edit_", "")
        info = db.get(title, {})
        desc = info.get("description", "Tavsif yo‘q")
        keyboard = [
            [InlineKeyboardButton("📝 Tavsifni o‘zgartirish", callback_data=f"edit_desc_{title}")],
            [InlineKeyboardButton("🎥 Epizod qo‘shish", callback_data=f"add_ep_{title}")]
        ]
        await query.edit_message_text(f"🎬 {title}\n\n{desc}", reply_markup=InlineKeyboardMarkup(keyboard))


# --- Kod orqali anime izlash funksiyasi ---
async def handle_code_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi 3 xonali kod yuborganda anime topish"""
    db = load_data()
    text = update.message.text.strip()

    # faqat 3 xonali raqam bo‘lsa
    if not text.isdigit() or len(text) != 3:
        return  # boshqa matnlar uchun hech narsa qilmaydi

    found = None
    for title, info in db.items():
        if str(info.get("code")) == text:
            found = (title, info)
            break

    if not found:
        await update.message.reply_text("❌ Bu kod bo‘yicha anime topilmadi.")
        return

    title, info = found
    desc = info.get("description", "Tavsif mavjud emas.")
    await update.message.reply_text(
        f"🎬 *{title}*\n\n{desc}\n\nKod: `{text}`",
        parse_mode="Markdown"
    )


# --- Anime qo‘shish bosqichi (admin) ---
async def handle_add_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin yangi anime qo‘shadi"""
    db = load_data()
    text = update.message.text.strip()

    if "adding_anime" in context.user_data:
        title = text
        context.user_data.clear()
        await update.message.reply_text("🖋 Tavsifni kiriting:")
        context.user_data["adding_desc_for"] = title

    elif "adding_desc_for" in context.user_data:
        title = context.user_data["adding_desc_for"]
        desc = text
        db[title] = {
            "description": desc,
            "episodes": {},
            "code": random.randint(100, 999)  # ✅ Har bir anime uchun 3 xonali kod
        }
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text(f"✅ *{title}* bazaga qo‘shildi!\nKod: `{db[title]['code']}`", parse_mode="Markdown")


# --- App run ---
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code_search))  # ✅ Kod izlash
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_anime))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))   # ✅ Tahrirlash faylidan

    application.run_polling()


if __name__ == "__main__":
    main()