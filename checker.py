# ============================================================
# checker.py — Логика проверки скидок и отправки уведомлений
# Вызывается планировщиком каждые CHECK_INTERVAL_HOURS часов
# ============================================================

import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config import ENABLE_BANNERS
from database import get_all_users_with_games
from steam_api import get_game_details, convert_price, get_steam_url, get_steamdb_url

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Основная функция проверки — перебирает всех пользователей
# и все их игры, запрашивает Steam API, сравнивает скидки.
# bot — экземпляр aiogram.Bot для отправки сообщений
# ------------------------------------------------------------
async def check_all_discounts(bot: Bot):
    logger.info("🔍 Запуск проверки скидок...")

    rows = await get_all_users_with_games()

    if not rows:
        logger.info("Нет отслеживаемых игр — пропускаем проверку.")
        return

    # Кэш запросов к Steam API: appid -> данные
    # Чтобы не делать повторные запросы если игру трекают несколько юзеров
    cache: dict[int, dict | None] = {}

    for row in rows:
        user_id       = row["user_id"]
        currency      = row["currency"]
        user_threshold = row["user_threshold"]
        appid         = row["appid"]
        # Индивидуальный порог игры; если NULL — берём порог пользователя
        game_threshold = row["game_threshold"] if row["game_threshold"] is not None else user_threshold

        # Берём из кэша или делаем запрос к Steam
        if appid not in cache:
            cache[appid] = await get_game_details(appid)

        details = cache[appid]

        # Если Steam не вернул данные — пропускаем
        if details is None:
            logger.warning(f"Нет данных для appid={appid}, пропускаем.")
            continue

        discount = details["discount_pct"]

        # Сравниваем скидку с порогом
        if discount >= game_threshold:
            logger.info(
                f"🎯 Скидка {discount}% >= порог {game_threshold}% "
                f"для appid={appid}, отправляем уведомление user_id={user_id}"
            )
            await send_discount_notification(
                bot=bot,
                user_id=user_id,
                details=details,
                currency=currency,
                threshold=game_threshold,
            )
        else:
            logger.debug(
                f"appid={appid}: скидка {discount}% < порог {game_threshold}%, пропускаем."
            )

    logger.info("✅ Проверка скидок завершена.")


# ------------------------------------------------------------
# Формирование и отправка уведомления о скидке пользователю
# bot       — экземпляр aiogram.Bot
# user_id   — Telegram ID получателя
# details   — словарь с данными игры из steam_api.get_game_details()
# currency  — валюта для отображения цены
# threshold — порог, который сработал (для контекста)
# ------------------------------------------------------------
async def send_discount_notification(
    bot: Bot,
    user_id: int,
    details: dict,
    currency: str,
    threshold: int,
):
    appid    = details["appid"]
    name     = details["name"]
    discount = details["discount_pct"]
    original = convert_price(details["price_original"], currency)
    final    = convert_price(details["price_final"],    currency)
    steam_url   = get_steam_url(appid)
    steamdb_url = get_steamdb_url(appid)

    # Формируем текст уведомления — КАПС, жирный, эмодзи 🚨
    text = (
        f"🚨 <b>СКИДКА {discount}%!</b> 🚨\n\n"
        f"🎮 <b>{name.upper()}</b>\n\n"
        f"💸 Старая цена: <s>{original}</s>\n"
        f"✅ Новая цена: <b>{final}</b>\n"
        f"🔥 Скидка: <b>-{discount}%</b> (порог: {threshold}%)\n\n"
        f"🛒 <a href='{steam_url}'>Купить в Steam</a>\n"
        f"📊 <a href='{steamdb_url}'>История цен на SteamDB</a>"
    )

    try:
        if ENABLE_BANNERS and details.get("header_image"):
            # Отправляем баннер + текст как подпись
            await bot.send_photo(
                chat_id=user_id,
                photo=details["header_image"],
                caption=text,
                parse_mode="HTML",
            )
        else:
            # Только текст без баннера
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )

    except TelegramForbiddenError:
        # Пользователь заблокировал бота — просто логируем
        logger.warning(f"user_id={user_id} заблокировал бота, пропускаем.")

    except TelegramBadRequest as e:
        logger.error(f"Ошибка Telegram API при отправке user_id={user_id}: {e}")

    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке уведомления user_id={user_id}: {e}")
