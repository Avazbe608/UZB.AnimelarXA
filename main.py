import os
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- Importlar ---
from edit_handlers import (
    handle_text_input,
    handle_episode_actions
)

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable topilmadi!")

ADMIN_ID = 7633032473
DATA_FILE = Path("/data/anime_db.json")
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
PAGE_SIZE = 5
EPISODE_PAGE_SIZE = 12

# --- Ma'lumotlarni saqlash/olish ---
def load_data():
    if not DATA_FILE.exists():
        save_data({})
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        save_data({})
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Paginatsiya funksiyalari ---
def get_page_buttons(data, page=0):
    titles = list(data.keys())
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    keyboard = [[InlineKeyboardButton(t, callback_data=f"show_{t}")] for t in titles[start:end]]
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"page_{page-1}"))
    if end < len(titles):
        nav_buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(keyboard)

def get_episode_buttons(anime, title, page=0):
    eps_list = list(anime.get("episodes", {}).keys())
    keyboard = []
    if not eps_list:
        keyboard.append([InlineKeyboardButton("🎞️ Epizod qo‘shish", callback_data=f"add_ep_{title}")])
    else:
        start = page * EPISODE_PAGE_SIZE
        end = start + EPISODE_PAGE_SIZE
        for ep in eps_list[start:end]:
            keyboard.append([
                InlineKeyboardButton(f"🎥 Epizod {ep}", callback_data=f"ep_{title}_{ep}"),
                InlineKeyboardButton("✏️", callback_data=f"edit_ep_{title}_{ep}"),
                InlineKeyboardButton("🗑️", callback_data=f"del_ep_{title}_{ep}")
            ])
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"ep_page_{title}_{page-1}"))
        if end < len(eps_list):
            nav_buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"ep_page_{title}_{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🎞️ Yangi epizod qo‘shish", callback_data=f"add_ep_{title}")])

    keyboard.append([InlineKeyboardButton("🛠️ Anime ma’lumotlarini tahrirlash", callback_data=f"edit_anime_{title}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="anime_list")])
    return InlineKeyboardMarkup(keyboard)

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xush kelibsiz!\n\nBuyruqlar:\n"
        "/anime - Anime ro‘yxati\n"
        "/addanime - Yangi anime qo‘shish (admin)\n"
        "/deleteanime - Anime o‘chirish (admin)"
    )

# --- Anime ro‘yxati ---
async def anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha anime mavjud emas.")
        return
    await update.message.reply_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(data, 0))

# --- Anime qo‘shish ---
ANIME_FIELDS = ["image", "title", "description", "year", "country", "language", "genre", "watch_link"]

async def addanime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return

    context.user_data["new_anime"] = {f: None for f in ANIME_FIELDS}
    context.user_data["new_anime"]["episodes"] = {}

    keyboard = [
        [InlineKeyboardButton("🖼️ Rasm URL", callback_data="new_image")],
        [InlineKeyboardButton("🏷️ Nomi", callback_data="new_title")],
        [InlineKeyboardButton("📝 Tavsif", callback_data="new_description")],
        [InlineKeyboardButton("📆 Yili", callback_data="new_year")],
        [InlineKeyboardButton("🌍 Davlati", callback_data="new_country")],
        [InlineKeyboardButton("🗣️ Tili", callback_data="new_language")],
        [InlineKeyboardButton("🎭 Janr", callback_data="new_genre")],
        [InlineKeyboardButton("▶️ Tomosha havolasi", callback_data="new_watch_link")],
        [InlineKeyboardButton("🎞️ Epizod qo‘shish", callback_data="new_episodes")],
        [InlineKeyboardButton("✅ Saqlash", callback_data="new_save")]
    ]
    await update.message.reply_text("🆕 Yangi anime yaratish!\nQuyidagi tugmalardan foydalaning:",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

# --- Addanime jarayonlari ---
async def addanime_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "new_episodes":
        context.user_data["adding_episode"] = True
        await query.message.reply_text("🎞️ Epizod raqamini kiriting:")
        return

    if data == "new_save":
        new_anime = context.user_data.get("new_anime", {})
        if not new_anime.get("title"):
            await query.message.reply_text("⚠️ Avvalo anime nomini kiriting!")
            return
        db = load_data()
        db[new_anime["title"]] = new_anime
        save_data(db)
        await query.message.reply_text(f"✅ *{new_anime['title']}* saqlandi!", parse_mode="Markdown")
        context.user_data.clear()
        return

    field = data.replace("new_", "")
    context.user_data["current_field"] = field
    await query.message.reply_text(f"✍️ {field} uchun qiymat kiriting:")

async def handle_new_anime_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Epizod qo‘shish
    if context.user_data.get("adding_episode"):
        if "current_episode" not in context.user_data:
            context.user_data["current_episode"] = update.message.text
            await update.message.reply_text("🔗 Endi shu epizod uchun video URL kiriting:")
        else:
            ep_num = context.user_data["current_episode"]
            ep_link = update.message.text
            context.user_data["new_anime"]["episodes"][ep_num] = ep_link
            context.user_data.pop("current_episode")
            await update.message.reply_text(f"✅ Epizod {ep_num} qo‘shildi! /done bilan tugating.")
        return

    if update.message.text.lower() == "/done":
        context.user_data.pop("adding_episode", None)
        await update.message.reply_text("✅ Epizodlar qo‘shish yakunlandi!")
        return

    # Oddiy maydon
    field = context.user_data.get("current_field")
    if not field:
        return
    context.user_data["new_anime"][field] = update.message.text
    context.user_data["current_field"] = None
    await update.message.reply_text(f"✅ {field} saqlandi!")

# --- Callback tugmalar ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_data()
    data = query.data

    if data == "anime_list":
        await query.edit_message_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(db, 0))
        return

    if data.startswith("show_"):
        title = data[5:]
        anime = db.get(title)
        if anime:
            caption = (
                f"🎬 *{title}*\n\n"
                f"📝 {anime.get('description','Tavsif yo‘q')}\n"
                f"🎭 {anime.get('genre','?')}\n"
                f"📆 {anime.get('year','?')} | 🌍 {anime.get('country','?')} | 🗣️ {anime.get('language','?')}\n"
                f"▶️ [Tomosha qilish]({anime.get('watch_link','')})"
            )
            await query.message.reply_photo(
                photo=anime.get("image",""),
                caption=caption,
                parse_mode="Markdown",
                reply_markup=get_episode_buttons(anime, title)
            )

    elif data.startswith("edit_anime_"):
        title = data.replace("edit_anime_", "")
        context.user_data["edit_title"] = title
        keyboard = [
            [InlineKeyboardButton("🖼️ Rasm", callback_data="edit_field_image")],
            [InlineKeyboardButton("📝 Tavsif", callback_data="edit_field_description")],
            [InlineKeyboardButton("📆 Yil", callback_data="edit_field_year")],
            [InlineKeyboardButton("🌍 Davlat", callback_data="edit_field_country")],
            [InlineKeyboardButton("🗣️ Til", callback_data="edit_field_language")],
            [InlineKeyboardButton("🎭 Janr", callback_data="edit_field_genre")],
            [InlineKeyboardButton("▶️ Tomosha havolasi", callback_data="edit_field_watch_link")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"show_{title}")]
        ]
        await query.message.reply_text(f"🛠️ *{title}* ma’lumotlarini tahrirlash:", parse_mode="Markdown",
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("edit_field_"):
        field = data.replace("edit_field_", "")
        context.user_data["editing_field"] = field
        await query.message.reply_text(f"✏️ {field} uchun yangi qiymat kiriting:")

    # 🔹 Epizod tugmalari
    elif data.startswith(("add_ep_", "edit_ep_", "del_ep_", "ep_")):
        await handle_episode_actions(update, context)

# --- Delete anime ---
async def delete_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hech qanday anime yo‘q.")
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=f"del_{t}")] for t in data.keys()]
    await update.message.reply_text("🗑️ O‘chirish uchun anime tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- RUN ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("anime", anime_list))
    app.add_handler(CommandHandler("addanime", addanime_start))
    app.add_handler(CommandHandler("deleteanime", delete_anime))
    app.add_handler(CallbackQueryHandler(addanime_buttons, pattern="^new_"))
    app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CallbackQueryHandler(handle_episode_actions, pattern="^(add_ep_|edit_ep_|del_ep_|ep_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_anime_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()