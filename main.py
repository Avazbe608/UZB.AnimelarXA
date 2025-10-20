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
(DEL_SELECT, DEL_CONFIRM) = range(10,12)

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
        keyboard.append([InlineKeyboardButton(f"🎥 Epizod {ep}", callback_data=f"ep_{title}_{ep}")])
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Oldingi", callback_data=f"ep_page_{title}_{page-1}"))
    if end < len(eps_list):
        nav_buttons.append(InlineKeyboardButton("Keyingi ▶️", callback_data=f"ep_page_{title}_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="page_0")])
    return InlineKeyboardMarkup(keyboard)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Xush kelibsiz! Anime botga xush kelibsiz.\n\n"
        "Buyruqlar:\n"
        "/anime - Animelar ro‘yxati\n"
        "/addanime - Yangi anime qo‘shish (admin)\n"
        "/deleteanime - Anime o‘chirish (admin)"
    )

# --- ANIMELAR RO'YXATI ---
async def anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha anime mavjud emas.")
        return
    await update.message.reply_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(data, 0))

# --- ADD ANIME CONVERSATION ---
async def addanime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Sizda bu buyruqdan foydalanish huquqi yo‘q.")
        return ConversationHandler.END
    await update.message.reply_text("🆕 Yangi anime qo‘shamiz.\n\n1️⃣ Anime nomini kiriting:")
    return TITLE

async def addanime_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text.strip()
    await update.message.reply_text("2️⃣ Anime haqida qisqacha ta’rif yozing:")
    return DESCRIPTION

async def addanime_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text.strip()
    await update.message.reply_text("3️⃣ Rasm URL kiriting (https://...):")
    return IMAGE

async def addanime_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not link.startswith("http"):
        await update.message.reply_text("⚠️ To‘g‘ri rasm linkini kiriting (https://...).")
        return IMAGE
    context.user_data["image"] = link
    await update.message.reply_text("4️⃣ Video URL larni vergul bilan yozing:\nMasalan:\n`https://vid1.mp4, https://vid2.mp4`", parse_mode="Markdown")
    return VIDEOS

async def addanime_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    videos = [v.strip() for v in update.message.text.split(",") if v.strip()]
    if not videos:
        await update.message.reply_text("⚠️ Hech bo‘lmasa 1 ta video kiriting.")
        return VIDEOS
    context.user_data["videos"] = videos
    await update.message.reply_text("5️⃣ Qismlar sonini kiriting:")
    return EPISODES_COUNT

async def addanime_episodes_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["episodes_count"] = update.message.text.strip()
    await update.message.reply_text("6️⃣ Holatini yozing (Tugallangan / Davom etmoqda):")
    return STATUS

async def addanime_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["status"] = update.message.text.strip()
    await update.message.reply_text("7️⃣ Sifatini yozing (1080p, 720p):")
    return QUALITY

async def addanime_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quality"] = update.message.text.strip()
    await update.message.reply_text("8️⃣ Janrlarini yozing (vergul bilan ajratib):")
    return GENRE

async def addanime_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["genre"] = update.message.text.strip()
    await update.message.reply_text("9️⃣ Kanal yoki manbani yozing:")
    return CHANNEL

async def addanime_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["UZB.AnimelarXA_Kanali"] = update.message.text.strip()
    u = context.user_data
    caption = (
        f"🎬 *{u['title']}*\n\n"
        f"📝 {u['description']}\n"
        f"🎞️ Qismlar: {u['episodes_count']}\n"
        f"📺 Holati: {u['status']}\n"
        f"💎 Sifati: {u['quality']}\n"
        f"🎭 Janr: {u['genre']}\n"
        f"📡 Kanal: {u['channel']}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Saqlash", callback_data="confirm_save"),
         InlineKeyboardButton("❌ Bekor qilish", callback_data="confirm_cancel")]
    ]
    await update.message.reply_photo(photo=u["image"], caption=caption, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

async def addanime_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()
    u = context.user_data
    if query.data == "confirm_save":
        data[u["title"]] = {
            "description": u["description"],
            "image": u["image"],
            "episodes": {str(i+1): v for i, v in enumerate(u["videos"])},
            "episodes_count": u["episodes_count"],
            "status": u["status"],
            "quality": u["quality"],
            "genre": u["genre"],
            "channel": u["channel"]
        }
        save_data(data)
        await query.edit_message_caption(caption=f"✅ *{u['title']}* muvaffaqiyatli qo‘shildi!", parse_mode="Markdown")
    else:
        await query.edit_message_caption(caption="❌ Anime qo‘shish bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

async def addanime_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Anime qo‘shish bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

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

# --- CALLBACK HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = load_data()
    data = query.data

    # Anime list page
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text("🎬 Anime tanlang:", reply_markup=get_page_buttons(db, page))
        return

    # Show anime info
    elif data.startswith("show_"):
        title = data[5:]
        anime = db.get(title)
        if anime:
            caption = (
                f"🎬 *{title}*\n\n"
                f"📝 {anime['description']}\n"
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

    # Episode pages
    elif data.startswith("ep_page_"):
        _, _, title, page = data.split("_")
        anime = db.get(title)
        if anime:
            await query.edit_message_reply_markup(reply_markup=get_episode_buttons(anime, title, int(page)))

    # Show episode
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

    # Delete anime
    elif data.startswith("del_"):
        title = data[4:]
        if title in db:
            db.pop(title)
            save_data(db)
            await query.message.reply_text(f"🗑️ *{title}* o‘chirildi!", parse_mode="Markdown")

# --- MAIN ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ConversationHandler for adding anime
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addanime', addanime_start)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_description)],
            IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_image)],
            VIDEOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_videos)],
            EPISODES_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_episodes_count)],
            STATUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_status)],
            QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_quality)],
            GENRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_genre)],
            CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, addanime_channel)],
            CONFIRM: [CallbackQueryHandler(addanime_confirm)]
        },
        fallbacks=[CommandHandler('cancel', addanime_cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("anime", anime_list))
    app.add_handler(CommandHandler("deleteanime", delete_anime))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()
