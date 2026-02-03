import aiosqlite
from typing import Optional, List, Tuple, Dict, Any

DB_PATH = "data.db"

ALLOWED_FIELDS = {"title", "year", "country", "language", "genres", "description"}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year TEXT,
            country TEXT,
            language TEXT,
            genres TEXT,
            description TEXT,
            access_code TEXT,
            is_locked INTEGER DEFAULT 0
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS season (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            season_no INTEGER NOT NULL,
            UNIQUE(anime_id, season_no),
            FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS episode (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER NOT NULL,
            season_no INTEGER NOT NULL,
            episode_no INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            caption TEXT,
            UNIQUE(anime_id, season_no, episode_no),
            FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE
        );
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen_ts INTEGER
        );
        """)

        # Migratsiya (oldingi bazalarda ustun bo‘lmasa)
        try:
            await db.execute("ALTER TABLE anime ADD COLUMN access_code TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE anime ADD COLUMN is_locked INTEGER DEFAULT 0")
        except:
            pass

        await db.commit()

async def upsert_user(user_id: int, ts: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, first_seen_ts) VALUES(?, ?)",
            (user_id, ts)
        )
        await db.commit()

async def add_anime(title: str, year: str="", country: str="", language: str="",
                    genres: str="", description: str="") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO anime(title, year, country, language, genres, description) VALUES(?,?,?,?,?,?)",
            (title, year, country, language, genres, description)
        )
        await db.commit()
        return cur.lastrowid

async def get_anime(anime_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM anime WHERE id=?", (anime_id,))
        row = await cur.fetchone()
        return dict(row) if row else None

async def get_anime_by_code(code: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM anime WHERE is_locked=1 AND access_code=?",
            (code,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None

async def search_anime(q: str, limit: int=20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM anime WHERE title LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{q}%", limit)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

async def ensure_season(anime_id: int, season_no: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO season(anime_id, season_no) VALUES(?,?)",
            (anime_id, season_no)
        )
        await db.commit()

async def list_seasons(anime_id: int) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT season_no FROM season WHERE anime_id=? ORDER BY season_no ASC",
            (anime_id,)
        )
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]

async def next_episode_no(anime_id: int, season_no: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(MAX(episode_no), 0) FROM episode WHERE anime_id=? AND season_no=?",
            (anime_id, season_no)
        )
        (mx,) = await cur.fetchone()
        return int(mx) + 1

async def add_or_replace_episode(anime_id: int, season_no: int, episode_no: int, file_id: str, caption: str=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO episode(anime_id, season_no, episode_no, file_id, caption)
            VALUES(?,?,?,?,?)
        """, (anime_id, season_no, episode_no, file_id, caption))
        await db.commit()

async def count_episodes(anime_id: int, season_no: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM episode WHERE anime_id=? AND season_no=?",
            (anime_id, season_no)
        )
        (c,) = await cur.fetchone()
        return int(c)

async def list_episode_numbers(anime_id: int, season_no: int, offset: int=0, limit: int=30) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT episode_no FROM episode
            WHERE anime_id=? AND season_no=?
            ORDER BY episode_no ASC
            LIMIT ? OFFSET ?
        """, (anime_id, season_no, limit, offset))
        rows = await cur.fetchall()
        return [int(r[0]) for r in rows]

async def get_episode(anime_id: int, season_no: int, episode_no: int) -> Optional[Tuple[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT file_id, COALESCE(caption,'') FROM episode
            WHERE anime_id=? AND season_no=? AND episode_no=?
        """, (anime_id, season_no, episode_no))
        row = await cur.fetchone()
        return (row[0], row[1]) if row else None

async def set_anime_lock(anime_id: int, is_locked: int, access_code: str=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE anime SET is_locked=?, access_code=? WHERE id=?",
            (is_locked, access_code, anime_id)
        )
        await db.commit()

async def update_anime_field(anime_id: int, field: str, value: str):
    if field not in ALLOWED_FIELDS:
        raise ValueError("field not allowed")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE anime SET {field}=? WHERE id=?", (value, anime_id))
        await db.commit()

async def update_episode_caption(anime_id: int, season_no: int, episode_no: int, caption: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE episode SET caption=?
            WHERE anime_id=? AND season_no=? AND episode_no=?
        """, (caption, anime_id, season_no, episode_no))
        await db.commit()

async def update_episode_file(anime_id: int, season_no: int, episode_no: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE episode SET file_id=?
            WHERE anime_id=? AND season_no=? AND episode_no=?
        """, (file_id, anime_id, season_no, episode_no))
        await db.commit()

async def stats() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur1 = await db.execute("SELECT COUNT(*) FROM users"); (u,) = await cur1.fetchone()
        cur2 = await db.execute("SELECT COUNT(*) FROM anime"); (a,) = await cur2.fetchone()
        cur3 = await db.execute("SELECT COUNT(*) FROM episode"); (e,) = await cur3.fetchone()
        return {"users": int(u), "anime": int(a), "episodes": int(e)}