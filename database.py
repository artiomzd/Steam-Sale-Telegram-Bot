# ============================================================
# database.py — Все операции с SQLite через aiosqlite
# Инициализация таблиц, CRUD для users и tracked_games
# ============================================================

import aiosqlite
from config import DB_PATH, DEFAULT_THRESHOLD


# ------------------------------------------------------------
# Инициализация базы данных
# Создаёт таблицы, если они ещё не существуют
# ------------------------------------------------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица пользователей:
        # - user_id       : Telegram ID
        # - currency      : выбранная валюта (например 'RUB', 'USD')
        # - threshold     : глобальный порог скидки (%) для этого юзера
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                currency  TEXT    NOT NULL DEFAULT 'KZT',
                threshold INTEGER NOT NULL DEFAULT 75
            )
        """)

        # Таблица отслеживаемых игр:
        # - id             : автоинкрементный первичный ключ
        # - user_id        : ссылка на users.user_id
        # - appid          : Steam App ID игры
        # - threshold      : индивидуальный порог скидки для этой игры
        #                    (NULL = использовать глобальный порог юзера)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracked_games (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                appid     INTEGER NOT NULL,
                threshold INTEGER,
                UNIQUE(user_id, appid),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


# ------------------------------------------------------------
# Получить пользователя по его Telegram ID
# Возвращает строку (user_id, currency, threshold) или None
# ------------------------------------------------------------
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone()


# ------------------------------------------------------------
# Создать нового пользователя с дефолтными параметрами
# Если пользователь уже существует — ничего не делает (INSERT OR IGNORE)
# ------------------------------------------------------------
async def create_user(user_id: int, currency: str = "KZT"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, currency, threshold) VALUES (?, ?, ?)",
            (user_id, currency, DEFAULT_THRESHOLD),
        )
        await db.commit()


# ------------------------------------------------------------
# Обновить валюту пользователя
# ------------------------------------------------------------
async def set_user_currency(user_id: int, currency: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET currency = ? WHERE user_id = ?",
            (currency, user_id),
        )
        await db.commit()


# ------------------------------------------------------------
# Обновить глобальный порог скидки пользователя
# ------------------------------------------------------------
async def set_user_threshold(user_id: int, threshold: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET threshold = ? WHERE user_id = ?",
            (threshold, user_id),
        )
        await db.commit()


# ------------------------------------------------------------
# Добавить игру в список отслеживания
# Если игра уже добавлена — обновляет порог (INSERT OR REPLACE)
# threshold=None означает «использовать глобальный порог юзера»
# ------------------------------------------------------------
async def add_tracked_game(user_id: int, appid: int, threshold: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO tracked_games (user_id, appid, threshold)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, appid) DO UPDATE SET threshold = excluded.threshold
            """,
            (user_id, appid, threshold),
        )
        await db.commit()


# ------------------------------------------------------------
# Удалить игру из отслеживания по AppID для конкретного пользователя
# Возвращает True если запись была удалена, False если не найдена
# ------------------------------------------------------------
async def delete_tracked_game(user_id: int, appid: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_games WHERE user_id = ? AND appid = ?",
            (user_id, appid),
        )
        await db.commit()
        return cursor.rowcount > 0


# ------------------------------------------------------------
# Получить список всех отслеживаемых игр пользователя
# Возвращает список строк (appid, threshold)
# ------------------------------------------------------------
async def get_user_games(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT appid, threshold FROM tracked_games WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


# ------------------------------------------------------------
# Получить всех пользователей вместе с их играми
# Используется в планировщике для массовой проверки
# Возвращает список строк (user_id, currency, user_threshold, appid, game_threshold)
# ------------------------------------------------------------
async def get_all_users_with_games():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT u.user_id, u.currency, u.threshold AS user_threshold,
                   tg.appid,  tg.threshold AS game_threshold
            FROM users u
            JOIN tracked_games tg ON u.user_id = tg.user_id
            """
        ) as cursor:
            return await cursor.fetchall()


# ------------------------------------------------------------
# Статистика для админа
# Возвращает (кол-во уникальных юзеров, кол-во записей в tracked_games)
# ------------------------------------------------------------
async def get_stats() -> tuple[int, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            (users_count,) = await cur.fetchone()
        async with db.execute("SELECT COUNT(*) FROM tracked_games") as cur:
            (games_count,) = await cur.fetchone()
    return users_count, games_count
