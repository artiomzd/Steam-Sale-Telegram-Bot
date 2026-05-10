# ============================================================
# steam_api.py — Все запросы к Steam Store API через aiohttp
# Поиск игр, получение деталей, конвертация валют
# ============================================================

import aiohttp
import logging
from config import GLOBAL_STEAM_REGION, CURRENCIES

logger = logging.getLogger(__name__)

# Базовый URL Steam Store API
STEAM_STORE_API = "https://store.steampowered.com/api"

# Базовый URL поиска Steam
STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"


# ------------------------------------------------------------
# Конвертация цены из тенге (KZT) в выбранную валюту пользователя
# Использует фиксированные коэффициенты из config.py
# price_kzt — цена в тенге (целое число, как отдаёт Steam API × 100)
# currency  — код валюты пользователя ('RUB', 'USD' и т.д.)
# Возвращает строку вида "1 250 ₽"
# ------------------------------------------------------------
def convert_price(price_kzt_cents: int, currency: str) -> str:
    """
    Steam API возвращает цену в «центах» валюты региона.
    Для KZ это тиыны (1 тенге = 100 тиын).
    Сначала переводим в тенге, потом конвертируем.
    """
    if price_kzt_cents == 0:
        return "Бесплатно"

    price_kzt = price_kzt_cents / 100.0  # из тиынов в тенге

    # Берём коэффициент конвертации из конфига
    _, symbol, rate = CURRENCIES.get(currency, CURRENCIES["KZT"])

    converted = price_kzt * rate

    # Форматируем: убираем копейки для крупных сумм, оставляем для мелких
    if converted >= 10:
        formatted = f"{converted:,.0f}".replace(",", " ")
    else:
        formatted = f"{converted:.2f}"

    return f"{formatted} {symbol}"


# ------------------------------------------------------------
# Поиск игр по названию через Steam Store Search API
# query   — строка поиска (название игры)
# region  — регион для цен (по умолчанию из конфига)
# Возвращает список словарей с полями:
#   appid, name, price_cents, discount_pct, currency_code
# ------------------------------------------------------------
async def search_games(query: str, region: str = GLOBAL_STEAM_REGION) -> list[dict]:
    params = {
        "term": query,
        "l": "russian",          # язык результатов
        "cc": region,            # код страны для цен
        "count": 10,             # максимум результатов
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                STEAM_SEARCH_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Steam Search API вернул статус {resp.status}")
                    return []

                data = await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка запроса к Steam Search API: {e}")
            return []

    items = data.get("items", [])
    results = []

    for item in items:
        price_info = item.get("price", {})

        results.append({
            "appid":        item.get("id"),
            "name":         item.get("name", "Неизвестно"),
            # final — финальная цена в «центах» валюты региона
            "price_cents":  price_info.get("final", 0),
            # discount — скидка в процентах (0 если нет акции)
            "discount_pct": price_info.get("discount_percent", 0),
            # currency из ответа API (например 'KZT')
            "currency_code": price_info.get("currency", "KZT"),
        })

    return results


# ------------------------------------------------------------
# Получить подробные данные об игре по AppID
# appid  — числовой Steam App ID
# region — регион для цен
# Возвращает словарь с полями игры или None если игра не найдена
# ------------------------------------------------------------
async def get_game_details(appid: int, region: str = GLOBAL_STEAM_REGION) -> dict | None:
    params = {
        "appids": appid,
        "cc": region,              # код страны
        "l": "russian",           # язык описания
        "filters": "price_overview,basic,header_image",  # только нужные поля
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{STEAM_STORE_API}/appdetails",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Steam AppDetails API вернул статус {resp.status} для appid={appid}")
                    return None

                data = await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка запроса к Steam AppDetails API: {e}")
            return None

    app_data = data.get(str(appid), {})

    # Steam API возвращает {"success": false} если игра не найдена
    if not app_data.get("success", False):
        logger.warning(f"AppID {appid} не найден в Steam API")
        return None

    info = app_data.get("data", {})
    price_overview = info.get("price_overview", {})

    return {
        "appid":          appid,
        "name":           info.get("name", f"App {appid}"),
        # initial — цена до скидки в «центах»
        "price_original": price_overview.get("initial", 0),
        # final — цена после скидки
        "price_final":    price_overview.get("final", 0),
        # discount_percent — скидка в %
        "discount_pct":   price_overview.get("discount_percent", 0),
        # header_image — URL обложки (баннера) игры
        "header_image":   info.get("header_image", ""),
        # is_free — бесплатная ли игра
        "is_free":        info.get("is_free", False),
    }


# ------------------------------------------------------------
# Вспомогательная функция: получить URL страницы игры в Steam
# ------------------------------------------------------------
def get_steam_url(appid: int) -> str:
    return f"https://store.steampowered.com/app/{appid}/"


# ------------------------------------------------------------
# Вспомогательная функция: получить URL страницы игры на SteamDB
# ------------------------------------------------------------
def get_steamdb_url(appid: int) -> str:
    return f"https://steamdb.info/app/{appid}/"
