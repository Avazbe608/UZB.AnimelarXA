# edit_handlers.py
import json
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

DATA_FILE = Path("/data/anime_db.json")

# --- Ma'lumotlar bilan ishlash ---
def load_data():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Anime tahrirlash matni ---
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    text = update.message.text

    if context.user_data.get("adding_new_episode") or context.user_data.get("editing_episode"):
        await handle_episode_text(update, context)
        return

    if "editing_field" in context.user_data and "edit_title" in context.user_data:
        title = context.user_data["edit_title"]
        field = context.user_data["editing_field"]
        db[title][field] = text
        save_data(db)
        await update.message.reply_text(f"✅ *{title}* uchun {field} yangilandi!", parse_mode="Markdown")
        await show_anime_by_title(update, title)
        context.user_data.clear()


# --- Epizod bilan ishlash ---
async def handle_episode_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    text = update.message.text

    if context.user_data.get("adding_new_episode"):
        title = context.user_data["add_ep_title"]
        if "current_add_ep" not in context.user_data:
            context.user_data["current_add_ep"] = text
            await update.message.reply_text("🔗 Endi video URL kiriting:")
        else:
            ep = context.user_data["current_add_ep"]
            db[title]["episodes"][ep] = text
            save_data(db)
            await update.message.reply_text(f"✅ {title} - {ep}-epizod qo‘shildi!")
            await show_anime_by_title(update, title)
            context.user_data.clear()

    elif context.user_data.get("editing_episode"):
        title = context.user_data["edit_ep_title"]
        ep = context.user_data["edit_ep_number"]
        db[title]["episodes"][ep] = text
        save_data(db)
        await update.message.reply_text(f"✏️ {title} - {ep}-epizod yangilandi!")
        await show_anime_by_title(update, title)
        context.user_data.clear()


# --- Epizod tugmalari ---
async def handle_episode_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    db = load_data()

    if data.startswith("add_ep_"):
        title = data.replace("add_ep_", "")
        context.user_data["add_ep_title"] = title
        context.user_data["adding_new_episode"] = True
        await query.message.reply_text(f"🎞️ {title} uchun epizod raqamini kiriting:")

    elif data.startswith("edit_ep_"):
        _, title, ep = data.split("_", 2)
        context.user_data.update({
            "edit_ep_title": title,
            "edit_ep_number": ep,
            "editing_episode": True
        })
        await query.message.reply_text(f"✏️ Epizod {ep} uchun yangi URL kiriting:")

    elif data.startswith("del_ep_"):
        _, title, ep = data.split("_", 2)
        if ep in db[title]["episodes"]:
            del db[title]["episodes"][ep]
            save_data(db)
            await query.message.reply_text(f"🗑️ {title} - {ep}-epizod o‘chirildi!")
            await show_anime_by_title(update, title)

    elif data.startswith("ep_"):
        _, title, ep = data.split("_", 2)
        if title in db and ep in db[title]["episodes"]:
            await query.message.reply_video(
                video=db[title]["episodes"][ep],
                caption=f"🎬 {title} - Epizod {ep}",
                parse_mode="Markdown"
            )


# --- Anime chiqishi ---
async def show_anime_by_title(update: Update, title: str):
    db = load_data()
    if title not in db:
        await update.message.reply_text("❌ Bunday anime topilmadi.")
        return

    anime = db[title]

    caption = (
        f"🎬 *{title}*\n\n"
        f"📝 {anime.get('description','Tavsif yo‘q')}\n"
        f"🎭 {anime.get('genre','?')}\n"
        f"📆 {anime.get('year','?')} | 🌍 {anime.get('country','?')} | 🗣️ {anime.get('language','?')}\n"
        f"▶️ [Tomosha qilish]({anime.get('watch_link','')})"
    )

    eps = anime.get("episodes", {})
    keyboard = []
    if eps:
        for ep in eps.keys():
            keyboard.append([
                InlineKeyboardButton(f"🎥 Epizod {ep}", callback_data=f"ep_{title}_{ep}"),
                InlineKeyboardButton("✏️", callback_data=f"edit_ep_{title}_{ep}"),
                InlineKeyboardButton("🗑️", callback_data=f"del_ep_{title}_{ep}")
            ])
    keyboard.append([InlineKeyboardButton("➕ Epizod qo‘shish", callback_data=f"add_ep_{title}")])
    keyboard.append([InlineKeyboardButton("🛠️ Anime ma’lumotlarini tahrirlash", callback_data=f"edit_anime_{title}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="anime_list")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_photo(
        photo=anime.get("image", ""),
        caption=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# --- 3 xonali kod orqali anime chiqarish ---
async def handle_anime_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    if not user_input.isdigit() or len(user_input) != 3:
        return
    db = load_data()
    for anime in db.values():
        if anime.get("code") == user_input:
            await show_anime_by_title(update, anime["title"])
            return