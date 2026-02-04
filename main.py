import os
import time
import asyncio
import logging

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, LinkPreviewOptions

import db
from keyboards import seasons_kb, episodes_kb, admin_menu

# ---------- CONFIG ----------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip() or "0")

if not BOT_TOKEN or ADMIN_ID == 0:
    raise RuntimeError("BOT_TOKEN yoki ADMIN_ID yo‘q. .env faylga qo‘ying.")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

PAGE_SIZE = 30
LPO_OFF = LinkPreviewOptions(is_disabled=True)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ---------- STATES ----------
class AddAnime(StatesGroup):
    title = State()
    year = State()
    country = State()
    language = State()
    genres = State()
    description = State()


class AddEpisode(StatesGroup):
    anime_id = State()
    season_no = State()
    mode = State()  # auto/manual
    episode_no = State()
    waiting_video = State()


class AddSeason(StatesGroup):
    anime_id = State()
    season_no = State()


class LockAnime(StatesGroup):
    anime_id = State()
    mode = State()  # lock/unlock
    code = State()


class EditAnime(StatesGroup):
    anime_id = State()
    field = State()
    value = State()


class EditEpisode(StatesGroup):
    anime_id = State()
    season_no = State()
    episode_no = State()
    action = State()  # caption/file
    new_caption = State()
    waiting_new_video = State()


class PostTemplate(StatesGroup):
    anime_id = State()
    season_no = State()


# ---------- HELPERS ----------
async def show_anime(target: Message | CallbackQuery, anime_id: int):
    a = await db.get_anime(anime_id)
    if not a:
        txt = "Bunday ID topilmadi."
        if isinstance(target, Message):
            return await target.answer(txt)
        return await target.message.answer(txt)

    # Lock bo‘lsa: admin bo‘lmasa ko‘rsatmaymiz
    if a.get("is_locked", 0) == 1 and not is_admin(target.from_user.id):
        txt = "🔒 Bu kontent kod bilan yopilgan. 3 xonali kodni yuboring."
        if isinstance(target, Message):
            return await target.answer(txt)
        return await target.message.answer(txt)

    seasons = await db.list_seasons(anime_id)

    meta = []
    if a.get("year"):
        meta.append(f"📅 Yili: {a['year']}")
    if a.get("country"):
        meta.append(f"🌍 Davlati: {a['country']}")
    if a.get("language"):
        meta.append(f"🗣 Tili: {a['language']}")
    if a.get("genres"):
        meta.append(f"🎭 Janri: {a['genres']}")
    if a.get("description"):
        meta.append(f"\n📝 {a['description']}")

    lock_line = "🔒 Kod bilan yopilgan" if a.get("is_locked", 0) == 1 else "✅ Ochiq"
    txt = (
        f"🎬 <b>{a['title']}</b>\n"
        f"🆔 ID: <code>{a['id']}</code>\n"
        f"{lock_line}\n"
        + "\n".join(meta)
    )

    kb = seasons_kb(anime_id, seasons, is_admin=is_admin(target.from_user.id)) if seasons else None

    if isinstance(target, Message):
        await target.answer(txt, reply_markup=kb, link_preview_options=LPO_OFF)
    else:
        await target.message.edit_text(txt, reply_markup=kb, link_preview_options=LPO_OFF)


async def render_episode_page(call: CallbackQuery, anime_id: int, season_no: int, page: int):
    total = await db.count_episodes(anime_id, season_no)
    offset = page * PAGE_SIZE
    eps = await db.list_episode_numbers(anime_id, season_no, offset=offset, limit=PAGE_SIZE)
    has_prev = page > 0
    has_next = (offset + PAGE_SIZE) < total

    a = await db.get_anime(anime_id)
    title = a["title"] if a else "Media"
    txt = (
        f"🎬 <b>{title}</b>\n"
        f"📺 <b>{season_no}-FASL</b>\n"
        f"Qismlar: {total}\n\n"
        f"Qismni tanlang:"
    )
    kb = episodes_kb(anime_id, season_no, eps, page, has_prev, has_next, is_admin=is_admin(call.from_user.id))
    await call.message.edit_text(txt, reply_markup=kb)


# ---------- PUBLIC ----------
@dp.message(CommandStart())
async def start_cmd(msg: Message):
    await db.upsert_user(msg.from_user.id, int(time.time()))
    args = msg.text.split(maxsplit=1)

    # /start 135
    if len(args) == 2 and args[1].isdigit():
        await show_anime(msg, int(args[1]))
        return

    text = (
        "Salom!\n\n"
        "🔎 Qidirish: <code>/search nom</code>\n"
        "🔓 Agar kontent kod bilan yopilgan bo‘lsa: <b>3 xonali kod</b> yuboring.\n"
    )
    if is_admin(msg.from_user.id):
        text += "\n👑 Admin menyu: <code>/admin</code>\n"
        text += f"🆔 Sizning admin ID: <code>{ADMIN_ID}</code>\n"
    await msg.answer(text)


@dp.message(Command("myid"))
async def myid(msg: Message):
    await msg.answer(f"🆔 Sizning ID: <code>{msg.from_user.id}</code>")


@dp.message(Command("search"))
async def search_cmd(msg: Message):
    q = msg.text.split(maxsplit=1)
    if len(q) < 2:
        return await msg.answer("Qidirish uchun: <code>/search nom</code>")
    items = await db.search_anime(q[1], limit=20)
    if not items:
        return await msg.answer("Hech narsa topilmadi.")
    lines = ["Topilganlar:"]
    for a in items:
        lines.append(f"• <b>{a['title']}</b> — /start <code>{a['id']}</code>")
    await msg.answer("\n".join(lines))


# 3 xonali kod yuborsa — locked anime ochiladi
@dp.message(F.text.regexp(r"^\d{3}$"))
async def unlock_by_code(msg: Message):
    a = await db.get_anime_by_code(msg.text.strip())
    if not a:
        return await msg.answer("❌ Kod xato yoki topilmadi.")
    await show_anime(msg, int(a["id"]))


# ---------- CALLBACKS ----------
@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("back:"))
async def back_to_seasons(call: CallbackQuery):
    _, anime_id = call.data.split(":")
    await show_anime(call, int(anime_id))
    await call.answer()


@dp.callback_query(F.data.startswith("s:"))
async def open_season(call: CallbackQuery):
    _, anime_id, season_no = call.data.split(":")
    await render_episode_page(call, int(anime_id), int(season_no), page=0)
    await call.answer()


@dp.callback_query(F.data.startswith("p:"))
async def paginate(call: CallbackQuery):
    _, anime_id, season_no, page = call.data.split(":")
    await render_episode_page(call, int(anime_id), int(season_no), int(page))
    await call.answer()


@dp.callback_query(F.data.startswith("e:"))
async def send_episode(call: CallbackQuery):
    _, anime_id, season_no, episode_no = call.data.split(":")
    anime_id = int(anime_id)
    season_no = int(season_no)
    episode_no = int(episode_no)

    a = await db.get_anime(anime_id)
    if a and a.get("is_locked", 0) == 1 and not is_admin(call.from_user.id):
        await call.answer("🔒 Kod bilan yopilgan. 3 xonali kod yuboring.", show_alert=True)
        return

    data = await db.get_episode(anime_id, season_no, episode_no)
    if not data:
        await call.answer("Topilmadi.", show_alert=True)
        return

    file_id, cap = data
    title = a["title"] if a else "Media"
    caption = cap or f"🎬 {title}\n📺 {season_no}-FASL • {episode_no}-qism"

    try:
        await call.message.answer_video(file_id, caption=caption)
    except Exception:
        await call.message.answer_document(file_id, caption=caption)

    await call.answer()


# ---------- ADMIN ----------
@dp.message(Command("admin"))
async def admin_cmd(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Kechirasiz, admin emassiz.")
    await msg.answer("Admin menyu:", reply_markup=admin_menu())


@dp.callback_query(F.data == "admin:add_anime")
async def admin_add_anime(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    await state.set_state(AddAnime.title)
    await call.message.answer("🎬 Anime nomini yubor:")
    await call.answer()


@dp.message(AddAnime.title)
async def st_title(msg: Message, state: FSMContext):
    await state.update_data(title=msg.text.strip())
    await state.set_state(AddAnime.year)
    await msg.answer("📅 Yili? (bo‘sh bo‘lsa '-')")


@dp.message(AddAnime.year)
async def st_year(msg: Message, state: FSMContext):
    year = "" if msg.text.strip() == "-" else msg.text.strip()
    await state.update_data(year=year)
    await state.set_state(AddAnime.country)
    await msg.answer("🌍 Davlati? (bo‘sh bo‘lsa '-')")


@dp.message(AddAnime.country)
async def st_country(msg: Message, state: FSMContext):
    country = "" if msg.text.strip() == "-" else msg.text.strip()
    await state.update_data(country=country)
    await state.set_state(AddAnime.language)
    await msg.answer("🗣 Tili? (masalan: O‘zbek tilida, bo‘sh bo‘lsa '-')")


@dp.message(AddAnime.language)
async def st_lang(msg: Message, state: FSMContext):
    lang = "" if msg.text.strip() == "-" else msg.text.strip()
    await state.update_data(language=lang)
    await state.set_state(AddAnime.genres)
    await msg.answer("🎭 Janri? (vergul bilan, bo‘sh bo‘lsa '-')")


@dp.message(AddAnime.genres)
async def st_genres(msg: Message, state: FSMContext):
    genres = "" if msg.text.strip() == "-" else msg.text.strip()
    await state.update_data(genres=genres)
    await state.set_state(AddAnime.description)
    await msg.answer("📝 Qisqa tavsif (xohlasang), bo‘lmasa '-'")


@dp.message(AddAnime.description)
async def st_desc(msg: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if msg.text.strip() == "-" else msg.text.strip()
    anime_id = await db.add_anime(
        title=data["title"],
        year=data.get("year", ""),
        country=data.get("country", ""),
        language=data.get("language", ""),
        genres=data.get("genres", ""),
        description=desc,
    )
    await state.clear()
    me = await bot.get_me()
    deep = f"https://t.me/{me.username}?start={anime_id}"
    await msg.answer(
        f"✅ Saqlandi!\n🆔 Anime ID: <code>{anime_id}</code>\n🔗 Link: {deep}",
        link_preview_options=LPO_OFF,
    )


@dp.callback_query(F.data.startswith("admin:add_season:"))
async def admin_add_season_cb(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    _, _, anime_id = call.data.split(":")
    await state.update_data(anime_id=int(anime_id))
    await state.set_state(AddSeason.season_no)
    await call.message.answer("➕ Qaysi fasl raqamini qo‘shamiz? (masalan 1/2/3)")
    await call.answer()


@dp.message(AddSeason.season_no)
async def add_season_no(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam.")
    data = await state.get_data()
    anime_id = int(data["anime_id"])
    season_no = int(msg.text)
    await db.ensure_season(anime_id, season_no)
    await state.clear()
    await msg.answer(f"✅ Fasl qo‘shildi. /start <code>{anime_id}</code> qilib tekshir.")


@dp.callback_query(F.data == "admin:add_ep")
async def admin_add_ep(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    await state.set_state(AddEpisode.anime_id)
    await call.message.answer("🆔 Qaysi Anime ID ga qism qo‘shamiz? (raqam yubor)")
    await call.answer()


@dp.message(AddEpisode.anime_id)
async def ep_anime_id(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam yubor.")
    anime_id = int(msg.text)
    a = await db.get_anime(anime_id)
    if not a:
        return await msg.answer("Bunday Anime ID topilmadi.")
    await state.update_data(anime_id=anime_id)
    await state.set_state(AddEpisode.season_no)
    await msg.answer("📺 Fasl raqami? (1/2/3...)")


@dp.message(AddEpisode.season_no)
async def ep_season(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam.")
    season_no = int(msg.text)
    data = await state.get_data()
    await db.ensure_season(data["anime_id"], season_no)
    await state.update_data(season_no=season_no)
    await state.set_state(AddEpisode.mode)
    await msg.answer("Raqamlash:\n1) <b>auto</b>\n2) <b>manual</b>\n\nJavob: <code>auto</code> yoki <code>manual</code>")


@dp.message(AddEpisode.mode)
async def ep_mode(msg: Message, state: FSMContext):
    m = msg.text.strip().lower()
    if m not in ("auto", "manual"):
        return await msg.answer("Faqat <code>auto</code> yoki <code>manual</code> yoz.")
    await state.update_data(mode=m)
    if m == "manual":
        await state.set_state(AddEpisode.episode_no)
        return await msg.answer("Nechinchi qism? (raqam)")
    await state.set_state(AddEpisode.waiting_video)
    await msg.answer("🎞 Endi video yubor. (Auto raqam o‘zi qo‘yiladi)")


@dp.message(AddEpisode.episode_no)
async def ep_no(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam.")
    await state.update_data(episode_no=int(msg.text))
    await state.set_state(AddEpisode.waiting_video)
    await msg.answer("🎞 Endi video yubor.")


@dp.message(AddEpisode.waiting_video)
async def ep_video(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return

    file_id = msg.video.file_id if msg.video else (msg.document.file_id if msg.document else None)
    if not file_id:
        return await msg.answer("Video yoki fayl yubor. (Telegram video/doc)")

    data = await state.get_data()
    anime_id = data["anime_id"]
    season_no = data["season_no"]
    mode = data["mode"]

    ep_no_ = await db.next_episode_no(anime_id, season_no) if mode == "auto" else data["episode_no"]

    a = await db.get_anime(anime_id)
    title = a["title"] if a else "Media"
    caption = f"🎬 {title}\n📺 {season_no}-FASL • {ep_no_}-qism"

    await db.add_or_replace_episode(anime_id, season_no, ep_no_, file_id, caption=caption)

    me = await bot.get_me()
    deep = f"https://t.me/{me.username}?start={anime_id}"

    await msg.answer(
        f"✅ Saqlandi: ID <code>{anime_id}</code> | {season_no}-fasl | {ep_no_}-qism\n"
        f"🔗 Link: {deep}\n\n"
        "Auto bo‘lsa: keyingi videoni yuboraver — o‘zi ketma-ket qo‘shadi.",
        link_preview_options=LPO_OFF,
    )


@dp.callback_query(F.data == "admin:lock")
async def lock_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    await state.set_state(LockAnime.anime_id)
    await call.message.answer("🔐 Qaysi Anime ID ni yopamiz/ochamiz? (raqam yubor)")
    await call.answer()


@dp.message(LockAnime.anime_id)
async def lock_anime_id(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam.")
    anime_id = int(msg.text)
    a = await db.get_anime(anime_id)
    if not a:
        return await msg.answer("Topilmadi.")
    await state.update_data(anime_id=anime_id)
    await state.set_state(LockAnime.mode)
    await msg.answer("Rejim:\n<code>lock</code> — yopish\n<code>unlock</code> — ochish")


@dp.message(LockAnime.mode)
async def lock_mode(msg: Message, state: FSMContext):
    m = msg.text.strip().lower()
    if m not in ("lock", "unlock"):
        return await msg.answer("Faqat lock yoki unlock.")
    data = await state.get_data()
    anime_id = int(data["anime_id"])

    if m == "unlock":
        await db.set_anime_lock(anime_id, 0, "")
        await state.clear()
        return await msg.answer("✅ Ochildi (kodsiz).")

    await state.update_data(mode=m)
    await state.set_state(LockAnime.code)
    await msg.answer("3 xonali kod yubor (masalan 739).")


@dp.message(LockAnime.code)
async def lock_code(msg: Message, state: FSMContext):
    code = msg.text.strip()
    if not (code.isdigit() and len(code) == 3):
        return await msg.answer("Kod 3 xonali raqam bo‘lsin. Masalan: 739")
    data = await state.get_data()
    anime_id = int(data["anime_id"])
    await db.set_anime_lock(anime_id, 1, code)
    await state.clear()
    await msg.answer("✅ Yopildi. Endi foydalanuvchi 3 xonali kod yuborsa ochiladi.")


@dp.callback_query(F.data == "admin:edit_anime")
async def edit_anime_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    await state.set_state(EditAnime.anime_id)
    await call.message.answer("✏️ Qaysi Anime ID ni tahrirlaymiz? (raqam yubor)")
    await call.answer()


@dp.message(EditAnime.anime_id)
async def edit_anime_id(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("Faqat raqam.")
    anime_id = int(msg.text)
    a = await db.get_anime(anime_id)
    if not a:
        return await msg.answer("Topilmadi.")
    await state.update_data(anime_id=anime_id)
    await state.set_state(EditAnime.field)
    await msg.answer("Maydon: <code>title</code>/<code>year</code>/<code>country</code>/<code>language</code>/<code>genres</code>/<code>description</code>")


@dp.message(EditAnime.field)
async def edit_anime_field(msg: Message, state: FSMContext):
    field = msg.text.strip()
    if field not in {"title", "year", "country", "language", "genres", "description"}:
        return await msg.answer("Xato maydon.")
    await state.update_data(field=field)
    await state.set_state(EditAnime.value)
    await msg.answer("Yangi qiymatni yubor (bo‘sh qilish uchun '-' yubor):")


@dp.message(EditAnime.value)
async def edit_anime_value(msg: Message, state: FSMContext):
    data = await state.get_data()
    anime_id = int(data["anime_id"])
    field = data["field"]
    value = "" if msg.text.strip() == "-" else msg.text.strip()
    await db.update_anime_field(anime_id, field, value)
    await state.clear()
    await msg.answer(f"✅ Tahrirlandi. /start <code>{anime_id}</code> qilib tekshir.")


@dp.callback_query(F.data == "admin:stats")
async def stats_cb(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Admin emassiz.", show_alert=True)
    s = await db.stats()
    await call.message.answer(
        "📊 Statistika:\n"
        f"👥 Userlar: <b>{s['users']}</b>\n"
        f"🎬 Anime: <b>{s['anime']}</b>\n"
        f"🎞 Epizodlar: <b>{s['episodes']}</b>\n"
    )
    await call.answer()


# ---------- STARTUP ----------
async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())