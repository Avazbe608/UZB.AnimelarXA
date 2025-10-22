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

# --- Anime ma'lumotlarini tahrirlash ---
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    text = update.message.text

    # Epizod tahrirlash jarayoni
    if context.user_data.get("adding_new_episode") or context.user_data.get("editing_episode"):
        await handle_episode_text(update, context)
        return

    # Anime maydonini tahrirlash
    if "editing_field" in context.user_data and "edit_title" in context.user_data:
        title = context.user_data["edit_title"]
        field = context.user_data["editing_field"]
        db[title][field] = text
        save_data(db)
        await update.message.reply_text(f"✅ *{title}* uchun {field} yangilandi!", parse_mode="Markdown")
        context.user_data.clear()

# --- Epizod tahrirlash va qo‘shish ---
async def handle_episode_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    text = update.message.text

    # ➕ Yangi epizod qo‘shish
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
            context.user_data.clear()

    # ✏️ Epizod tahrirlash
    elif context.user_data.get("editing_episode"):
        title = context.user_data["edit_ep_title"]
        ep = context.user_data["edit_ep_number"]
        db[title]["episodes"][ep] = text
        save_data(db)
        await update.message.reply_text(f"✏️ {title} - {ep}-epizod yangilandi!")
        context.user_data.clear()

# --- Epizod tugmalari orqali ishlash ---
async def handle_episode_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    db = load_data()

    # ➕ Epizod qo‘shish
    if data.startswith("add_ep_"):
        title = data.replace("add_ep_", "")
        context.user_data["add_ep_title"] = title
        context.user_data["adding_new_episode"] = True
        await query.message.reply_text(f"🎞️ {title} uchun epizod raqamini kiriting:")

    # ✏️ Epizod tahrirlash
    elif data.startswith("edit_ep_"):
        _, title, ep = data.split("_", 2)
        context.user_data.update({
            "edit_ep_title": title,
            "edit_ep_number": ep,
            "editing_episode": True
        })
        await query.message.reply_text(f"✏️ Epizod {ep} uchun yangi URL kiriting:")

    # 🗑️ Epizod o‘chirish
    elif data.startswith("del_ep_"):
        _, title, ep = data.split("_", 2)
        if ep in db[title]["episodes"]:
            del db[title]["episodes"][ep]
            save_data(db)
            await query.message.reply_text(f"🗑️ {title} - {ep}-epizod o‘chirildi!")

    # 🎬 Epizodni ko‘rsatish
    elif data.startswith("ep_"):
        _, title, ep = data.split("_", 2)
        if title in db and ep in db[title]["episodes"]:
            await query.message.reply_video(
                video=db[title]["episodes"][ep],
                caption=f"🎬 {title} - Epizod {ep}",
                parse_mode="Markdown"
            )

# --- 3 xonali kod orqali anime chiqarish ---
async def handle_anime_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or len(text) != 3:
        return  # faqat 3 xonali kodlarni qabul qiladi

    code = text
    db = load_data()
    # Kod bo‘yicha mos anime topish
    anime = None
    for title, data in db.items():
        if data.get("code") == code:
            anime = {title: data}
            break

    if not anime:
        await update.message.reply_text("❌ Bunday kod bo‘yicha anime topilmadi.")
        return

    # Anime ma’lumotini chiqarish
    for title, data in anime.items():
        caption = (
            f"🎬 *{title}*\n\n"
            f"📝 {data.get('description','Tavsif yo‘q')}\n"
            f"🎭 {data.get('genre','?')}\n"
            f"📆 {data.get('year','?')} | 🌍 {data.get('country','?')} | 🗣️ {data.get('language','?')}\n"
            f"▶️ [Tomosha qilish]({data.get('watch_link','')})"
        )
        eps = data.get("episodes", {})
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

        await update.message.reply_photo(
            photo=data.get("image",""),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )