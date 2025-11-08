import os
import json
from pathlib import Path
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Token Koyeb environment variable’da saqlanadi
ADMIN_ID = 7633032473  # O'z holicha qoldi
DATA_FILE = Path("/data/anime_db.json")
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# --- Yordamchi funksiyalar ---
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Anime ro‘yxati", callback_data="list_anime")],
        [InlineKeyboardButton("➕ Yangi anime qo‘shish", callback_data="add_anime")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Salom! Quyidagilardan birini tanlang 👇", reply_markup=reply_markup)

# --- Anime ro‘yxati ---
def get_page_buttons(page, total_pages):
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{page+1}"))
    return buttons

async def show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page=1):
    data = load_data()
    items = list(data.items())
    if not items:
        await update.callback_query.message.reply_text("Hozircha hech qanday anime yo‘q 😢")
        return

    per_page = 5
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    start_index = (page - 1) * per_page
    end_index = start_index + per_page

    text = "🎬 *Anime ro‘yxati:*\n\n"
    for code, anime in items[start_index:end_index]:
        text += f"🎞️ *{anime['nomi']}*\nKod: `{code}`\nYil: {anime['yili']}\nJanr: {anime['janri']}\n\n"

    keyboard = []
    for code, anime in items[start_index:end_index]:
        keyboard.append([InlineKeyboardButton(f"🔍 {anime['nomi']}", callback_data=f"view_{code}")])
    if total_pages > 1:
        keyboard.append(get_page_buttons(page, total_pages))

    await update.callback_query.message.reply_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Anime qo‘shish ---
ADD_FIELDS = ["nomi", "yili", "janri", "tili", "davlati", "rasm", "havola", "tavsif"]
ADD_STATE = range(len(ADD_FIELDS))

async def add_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        if query.from_user.id != ADMIN_ID:
            await query.answer("Faqat admin qo‘sha oladi ❌", show_alert=True)
            return
        await query.message.reply_text("➕ Yangi anime nomini kiriting:")
    context.user_data["new_anime"] = {}
    context.user_data["add_step"] = 0
    return ADD_STATE[0]

async def add_anime_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data["add_step"]
    field = ADD_FIELDS[step]
    context.user_data["new_anime"][field] = update.message.text
    context.user_data["add_step"] += 1

    if context.user_data["add_step"] < len(ADD_FIELDS):
        next_field = ADD_FIELDS[context.user_data["add_step"]]
        await update.message.reply_text(f"{next_field.capitalize()}ni kiriting:")
        return ADD_STATE[context.user_data["add_step"]]
    else:
        data = load_data()
        code = str(len(data) + 1).zfill(3)
        data[code] = context.user_data["new_anime"]
        data[code]["epizodlar"] = []
        save_data(data)
        await update.message.reply_text(f"✅ Yangi anime qo‘shildi!\nKOD: `{code}`", parse_mode="Markdown")
        return ConversationHandler.END

# --- Anime ko‘rish ---
async def view_anime(update: Update, context: ContextTypes.DEFAULT_TYPE, code):
    data = load_data()
    anime = data.get(code)
    if not anime:
        await update.callback_query.answer("Topilmadi ❌", show_alert=True)
        return

    text = (
        f"🎞️ *{anime['nomi']}*\n"
        f"🗓 Yil: {anime['yili']}\n"
        f"🏷 Janr: {anime['janri']}\n"
        f"🌐 Til: {anime['tili']}\n"
        f"🇯🇵 Davlat: {anime['davlati']}\n"
        f"🔗 [Ko‘rish havolasi]({anime['havola']})\n"
        f"📖 {anime['tavsif']}"
    )

    keyboard = [
        [InlineKeyboardButton("🎞️ Epizodlar", callback_data=f"episodes_{code}")],
    ]
    if update.callback_query.from_user.id == ADMIN_ID:
        keyboard.append([
            InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_{code}"),
            InlineKeyboardButton("🗑️ O‘chirish", callback_data=f"delete_{code}")
        ])
    await update.callback_query.message.reply_photo(
        photo=anime["rasm"], caption=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Epizodlar ---
async def show_episodes(update: Update, context: ContextTypes.DEFAULT_TYPE, code):
    data = load_data()
    anime = data.get(code)
    if not anime:
        await update.callback_query.answer("Anime topilmadi", show_alert=True)
        return

    eps = anime.get("epizodlar", [])
    if not eps:
        text = "🎞️ Epizodlar hali qo‘shilmagan."
    else:
        text = "🎞️ *Epizodlar:*\n\n" + "\n".join(
            [f"{i+1}. {e}" for i, e in enumerate(eps)]
        )

    keyboard = []
    if update.callback_query.from_user.id == ADMIN_ID:
        keyboard = [[
            InlineKeyboardButton("➕ Epizod qo‘shish", callback_data=f"add_ep_{code}")
        ]]
    await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.split("_")[2]
    context.user_data["add_ep_code"] = code
    await query.message.reply_text("Yangi epizod havolasini kiriting:")
    return 100

async def save_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data["add_ep_code"]
    data = load_data()
    anime = data.get(code)
    if not anime:
        await update.message.reply_text("Anime topilmadi ❌")
        return ConversationHandler.END
    anime["epizodlar"].append(update.message.text)
    save_data(data)
    await update.message.reply_text("✅ Epizod qo‘shildi!")
    return ConversationHandler.END

# --- Tahrirlash ---
async def edit_anime(update: Update, context: ContextTypes.DEFAULT_TYPE, code):
    data = load_data()
    anime = data.get(code)
    if not anime:
        await update.callback_query.answer("Topilmadi")
        return

    buttons = [
        [InlineKeyboardButton("📝 Nom", callback_data=f"edit_field_{code}_nomi")],
        [InlineKeyboardButton("📅 Yil", callback_data=f"edit_field_{code}_yili")],
        [InlineKeyboardButton("🏷 Janr", callback_data=f"edit_field_{code}_janri")],
        [InlineKeyboardButton("🌐 Til", callback_data=f"edit_field_{code}_tili")],
        [InlineKeyboardButton("🇯🇵 Davlat", callback_data=f"edit_field_{code}_davlati")],
        [InlineKeyboardButton("🖼 Rasm", callback_data=f"edit_field_{code}_rasm")],
        [InlineKeyboardButton("🔗 Havola", callback_data=f"edit_field_{code}_havola")],
        [InlineKeyboardButton("📖 Tavsif", callback_data=f"edit_field_{code}_tavsif")]
    ]
    await update.callback_query.message.reply_text("Qaysi qismni tahrirlaysiz?", reply_markup=InlineKeyboardMarkup(buttons))

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, _, code, field = update.callback_query.data.split("_", 3)
    context.user_data["edit_code"] = code
    context.user_data["edit_field"] = field
    await update.callback_query.message.reply_text(f"Yangi {field} qiymatini kiriting:")
    return 200

async def save_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = context.user_data["edit_code"]
    field = context.user_data["edit_field"]
    data = load_data()
    anime = data.get(code)
    if not anime:
        await update.message.reply_text("Anime topilmadi")
        return ConversationHandler.END
    anime[field] = update.message.text
    save_data(data)
    await update.message.reply_text(f"✅ {field} yangilandi!")
    return ConversationHandler.END

# --- O‘chirish ---
async def delete_anime(update: Update, context: ContextTypes.DEFAULT_TYPE, code):
    data = load_data()
    if code in data:
        del data[code]
        save_data(data)
        await update.callback_query.message.reply_text("🗑️ Anime o‘chirildi!")
    else:
        await update.callback_query.answer("Topilmadi")

# --- Callback handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("list_anime"):
        await show_anime_list(update, context)
    elif data.startswith("add_anime"):
        return await add_anime_start(update, context)
    elif data.startswith("view_"):
        await view_anime(update, context, data.split("_")[1])
    elif data.startswith("episodes_"):
        await show_episodes(update, context, data.split("_")[1])
    elif data.startswith("add_ep_"):
        return await add_episode(update, context)
    elif data.startswith("edit_") and "field" not in data:
        await edit_anime(update, context, data.split("_")[1])
    elif data.startswith("edit_field_"):
        return await edit_field(update, context)
    elif data.startswith("delete_"):
        await delete_anime(update, context, data.split("_")[1])
    elif data.startswith("page_"):
        await show_anime_list(update, context, int(data.split("_")[1]))

# --- Kod orqali topish ---
async def handle_anime_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    data = load_data()
    if code in data:
        fake_query = type("obj", (object,), {"data": f"view_{code}", "message": update.message, "from_user": update.message.from_user})
        await view_anime(fake_query, context, code)
    else:
        await update.message.reply_text("❌ Bunday koddagi anime topilmadi.")

# --- Asosiy ishga tushirish ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_anime_start, pattern="^add_anime$")],
        states={i: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_anime_step)] for i in ADD_STATE},
        fallbacks=[],
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_field, pattern="^edit_field_")],
        states={200: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_field)]},
        fallbacks=[],
    )

    ep_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_episode, pattern="^add_ep_")],
        states={100: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_episode)]},
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^\d{3}$"), handle_anime_code))
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(ep_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()