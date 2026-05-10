# ============================================================
# main.py — Точка входа. Запуск бота и планировщика
# ============================================================

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CHECK_INTERVAL_HOURS, ADMIN_ID
from database import init_db
from handlers import router
from checker import check_all_discounts

# --- Настройка логирования ---
# Выводим в консоль с уровнем INFO
# Для отладки можно поменять на logging.DEBUG
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================
# Главная async-функция запуска
# ============================================================
async def main():
    # 1. Инициализируем базу данных (создаём таблицы если не существуют)
    logger.info("Инициализация базы данных...")
    await init_db()

    # 2. Создаём экземпляр бота с HTML-парсингом по умолчанию
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # 3. Диспетчер с хранилищем состояний в памяти (FSM для онбординга)
    dp = Dispatcher(storage=MemoryStorage())

    # 4. Подключаем роутер с обработчиками команд
    dp.include_router(router)

    # 5. Настраиваем планировщик задач
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Задача: проверять скидки каждые CHECK_INTERVAL_HOURS часов
    # bot передаём через аргумент kwargs
    scheduler.add_job(
        check_all_discounts,
        trigger="interval",
        hours=CHECK_INTERVAL_HOURS,
        kwargs={"bot": bot},
        id="discount_check",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"✅ Планировщик запущен. Проверка каждые {CHECK_INTERVAL_HOURS} ч."
    )

    # 6. Уведомляем администратора что бот стартовал
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🤖 <b>Steam Sale Bot запущен!</b>\n"
            f"Интервал проверки: каждые {CHECK_INTERVAL_HOURS} ч.\n"
            f"/debug_force — принудительная проверка\n"
            f"/stats — статистика",
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить стартовое сообщение админу: {e}")

    # 7. Запускаем polling (бот начинает слушать обновления от Telegram)
    logger.info("🚀 Бот запущен, ожидаю команды...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # При остановке — корректно закрываем сессию
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


# ============================================================
# Точка входа
# ============================================================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C).")
