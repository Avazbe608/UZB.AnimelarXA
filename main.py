import os
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 7633032473  # <-- O'zingizning Telegram ID
DATA_FILE = Path("/data/anime_db.json")  # Persistent Volume
PAGE_SIZE = 5
EPISODE_PAGE_SIZE = 12

# --- BOSQICHLAR ---
(TITLE, DESCRIPTION, IMAGE, VIDEOS, EPISODES_COUNT, STATUS, QUALITY, GENRE, CHANNEL, CONFIRM) = range(10)

# --- FUNKSIYALAR ---
def load_data():
    if not DATA_FILE.exists():
        save_data({})
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Backup
    with open("/data/backup_anime_db.json", "w", encoding="utf-8") as backup:
        json.dump(data, backup, ensure_ascii=False, indent=2)

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
    eps_list = list(anime["episodes"].keys())
    start = page * EPISODE_PAGE_SIZE
    end = start + EPISODE_PAGE_SIZE
    keyboard = []
    for ep in eps_list[start:end]:
        keyboard.append([
            InlineKeyboardButton(f"🎥 Epizod {ep} ✏️", callback_data=f"edit_episode_{title}_{ep}"),
            InlineKeyboardButton("🗑️", callback_data=f"del_episode_{title}_{ep}")
        ])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"ep_page_{title}_{page-1}"))
    if end < len(eps_list):
        nav_buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"ep_page_{title}_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data=f"show_{title}")])
    return InlineKeyboardMarkup(keyboard)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xush kelibsiz! Anime botga xush kelibsiz.\n\n"
        "Buyruqlar:\n"
        "/anime - Animelar ro‘yxati\n"
        "/addanime - Yangi anime qo‘shish (admin)\n"
        "/deleteanime - Anime o‘chirish (admin)\n"
        "/editanime - Anime tahrirlash (admin)"
    )

# --- ANIMELAR RO'YXATI ---
async def anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha anime mavjud emas.")
        return
    await update.message.reply_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(data, 0))

# --- ADD ANIME CONVERSATION --- 
# --- ANIME YARATISH ---
ANIME_FIELDS = ["image", "title", "year", "country", "language", "genre", "episodes", "watch_link"]

async def addanime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return
    
    context.user_data["new_anime"] = {f: None for f in ANIME_FIELDS}
    
    keyboard = [
        [InlineKeyboardButton("🖼️ Rasm qo‘shish", callback_data="new_image")],
        [InlineKeyboardButton("🏷️ Nomi", callback_data="new_title")],
        [InlineKeyboardButton("📆 Yili", callback_data="new_year")],
        [InlineKeyboardButton("🌍 Davlati", callback_data="new_country")],
        [InlineKeyboardButton("🗣️ Tili", callback_data="new_language")],
        [InlineKeyboardButton("🎭 Janr", callback_data="new_genre")],
        [InlineKeyboardButton("🎞️ Qismlar qo‘shish", callback_data="new_episodes")],
        [InlineKeyboardButton("▶️ Tomosha qilish havolasi", callback_data="new_watch_link")],
        [InlineKeyboardButton("✅ Saqlash", callback_data="new_save")]
    ]
    
    await update.message.reply_text(
        "🆕 Yangi anime yaratish!\nQuyidagi tugmalardan kerakli ma’lumotlarni kiriting:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# --- ADD ANIME CALLBACKLAR ---
async def addanime_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if "new_" not in data:
        return
    
    anime_data = context.user_data.get("new_anime", {})

    # Ma'lumot kiritish uchun
    if data != "new_save":
        field = data.replace("new_", "")
        context.user_data["current_field"] = field
        await query.message.reply_text(f"✍️ {field} uchun qiymat kiriting:")
        return

    # Saqlash
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


# --- KIRITILGAN MA'LUMOTLARNI QABUL QILISH ---
async def handle_new_anime_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("current_field")
    if not field:
        return

    value = update.message.text
    context.user_data["new_anime"][field] = value
    context.user_data["current_field"] = None

    await update.message.reply_text(f"✅ {field} saqlandi!")
# ... addanime_start, addanime_title, addanime_description, addanime_image, addanime_videos, addanime_episodes_count,
# addanime_status, addanime_quality, addanime_genre, addanime_channel, addanime_confirm, addanime_cancel ...

# --- DELETE ANIME ---
async def delete_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha anime mavjud emas.")
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=f"del_{t}")] for t in data.keys()]
    await update.message.reply_text("🗑️ O‘chirish uchun anime tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- EDIT ANIME (YANNGI FUNKSIYA) ---
async def edit_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha anime mavjud emas.")
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=f"edit_select_{t}")] for t in data.keys()]
    await update.message.reply_text("✏️ Tahrirlash uchun anime tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- CALLBACK HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_data()
    data = query.data

    # --- Pagination ---
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(db, page))
        return

    # --- Show anime info ---
    elif data.startswith("show_"):
        title = data[5:]
        anime = db.get(title)
        if anime:
            caption = (
                f"🎬 *{title}*\n\n"
                f"📝 {anime.get('description', 'Tavsif yo‘q')}\n"
                f"🎞️ Qismlar: {anime.get('episodes_count','?')}\n"
                f"📺 Holati: {anime.get('status','?')}\n"
                f"💎 Sifati: {anime.get('quality','?')}\n"
                f"🎭 Janr: {anime.get('genre','?')}\n"
                f"📡 Kanal: {anime.get('channel','?')}"
            )
            await query.message.reply_photo(
                photo=anime["image"],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=get_episode_buttons(anime, title, page=0)
            )

    # --- Episode pages ---
    elif data.startswith("ep_page_"):
        _, _, title, page = data.split("_")
        anime = db.get(title)
        if anime:
            await query.edit_message_reply_markup(reply_markup=get_episode_buttons(anime, title, int(page)))

    # --- Show episode ---
    elif data.startswith("ep_"):
        _, title, ep = data.split("_")
        anime = db.get(title)
        if anime and ep in anime["episodes"]:
            caption = (
                f"🎬 *{title}* - Epizod {ep}\n"
                f"🎞️ Qismlar soni: {anime.get('episodes_count','?')}\n"
                f"📡 Kanal: {anime.get('channel','?')}"
            )
            await query.message.reply_video(
                video=anime["episodes"][ep],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Yuklab olish", url=anime["episodes"][ep])],
                    [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"show_{title}")]
                ])
            )

    # --- Delete anime ---
    elif data.startswith("del_"):
        title = data[4:]
        if title in db:
            db.pop(title)
            save_data(db)
            await query.message.reply_text(f"🗑️ *{title}* o‘chirildi!", parse_mode="Markdown")

    # --- EDIT ANIME --- (inline tahrirlash)
    elif data.startswith("edit_select_"):
        title = data.replace("edit_select_", "")
        anime = db.get(title)
        if not anime:
            await query.message.reply_text("Anime topilmadi!")
            return
        context.user_data["edit_anime"] = title
        keyboard = [
            [InlineKeyboardButton("Nomni tahrirlash", callback_data="edit_field_name")],
            [InlineKeyboardButton("Rasm URL-ni tahrirlash", callback_data="edit_field_image")],
            [InlineKeyboardButton("Janrni tahrirlash", callback_data="edit_field_genre")],
            [InlineKeyboardButton("Qo‘shish epizod", callback_data="edit_add_episode")],
            [InlineKeyboardButton("Epizodlarni tahrirlash/o‘chirish", callback_data="edit_episodes")]
        ]
        await query.message.reply_photo(
            photo=anime["image"],
            caption=f"✏️ *{title}* ma’lumotlari",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # --- Add / Edit Epizod / Fields handled in handle_message ---
    elif data.startswith("edit_field_"):
        field = data.replace("edit_field_", "")
        pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addanime", addanime_start))
    app.add_handler(CallbackQueryHandler(addanime_buttons, pattern="^new_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_anime_input))
    app.add_handler(CommandHandler("anime", anime_list))
    app.add_handler(CommandHandler("deleteanime", delete_anime))
    app.add_handler(CommandHandler("editanime", edit_anime_start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot ishga tushdi!")
    app.run_polling()