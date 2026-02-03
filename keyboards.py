from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def seasons_kb(anime_id: int, seasons: list[int], is_admin: bool=False) -> InlineKeyboardMarkup:
    rows = []
    for s in seasons:
        rows.append([InlineKeyboardButton(text=f"{s}-FASL", callback_data=f"s:{anime_id}:{s}")])
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Fasl qo‘shish", callback_data=f"admin:add_season:{anime_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def episodes_kb(anime_id: int, season_no: int, eps: list[int], page: int, has_prev: bool, has_next: bool, is_admin: bool=False) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, ep in enumerate(eps, 1):
        row.append(InlineKeyboardButton(text=str(ep), callback_data=f"e:{anime_id}:{season_no}:{ep}"))
        if i % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"p:{anime_id}:{season_no}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}", callback_data="noop"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"p:{anime_id}:{season_no}:{page+1}"))
    rows.append(nav)

    if is_admin:
        rows.append([InlineKeyboardButton(text="✏️ Epizodni tahrirlash", callback_data=f"admin:edit_ep:{anime_id}:{season_no}")])

    rows.append([InlineKeyboardButton(text="⬅️ Fasllar", callback_data=f"back:{anime_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Anime qo‘shish", callback_data="admin:add_anime")],
        [InlineKeyboardButton(text="🎞 Qism qo‘shish (tez)", callback_data="admin:add_ep")],
        [InlineKeyboardButton(text="✏️ Anime tahrirlash", callback_data="admin:edit_anime")],
        [InlineKeyboardButton(text="🔐 Kod bilan yopish", callback_data="admin:lock")],
        [InlineKeyboardButton(text="📢 Post shabloni", callback_data="admin:post")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats")]
    ])