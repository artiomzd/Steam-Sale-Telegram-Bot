# ============================================================
# config.py — Читает настройки из .env файла
# Секреты (токен, admin ID) никогда не хранятся в коде
# ============================================================

import os
from dotenv import load_dotenv

# Загружаем переменные из .env в os.environ
# override=False — не перезаписывает если переменная уже задана в системе
load_dotenv(override=False)


# --- Обязательные параметры ---
# Если они не заданы — бот упадёт сразу с понятной ошибкой

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Проверь файл .env")

_admin_raw = os.getenv("ADMIN_ID")
if not _admin_raw:
    raise ValueError("❌ ADMIN_ID не задан! Проверь файл .env")
ADMIN_ID = int(_admin_raw)


# --- Опциональные параметры (со значениями по умолчанию) ---

# Интервал проверки скидок в часах
CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "12"))

# Регион Steam для запросов
GLOBAL_STEAM_REGION = os.getenv("GLOBAL_STEAM_REGION", "kz")

# Белый список пользователей
WHITELIST_ENABLED = os.getenv("WHITELIST_ENABLED", "false").lower() == "true"

# Список разрешённых ID (если WHITELIST_ENABLED=True)
WHITELIST = [ADMIN_ID]

# Показывать баннеры в уведомлениях
ENABLE_BANNERS = os.getenv("ENABLE_BANNERS", "true").lower() == "true"

# Путь к файлу SQLite
DB_PATH = os.getenv("DB_PATH", "steam_bot.db")

# Порог скидки по умолчанию
DEFAULT_THRESHOLD = int(os.getenv("DEFAULT_THRESHOLD", "75"))


# --- Курсы валют (фиксированные коэффициенты к KZT) ---
# Структура: код -> (название, символ, коэффициент_от_KZT)
CURRENCIES = {
    "KZT": ("Казахстанский тенге", "₸",  1.0),
    "RUB": ("Российский рубль",    "₽",  0.21),
    "USD": ("Доллар США",          "$",  0.0022),
    "EUR": ("Евро",                "€",  0.0020),
    "UAH": ("Украинская гривна",   "₴",  0.090),
}
