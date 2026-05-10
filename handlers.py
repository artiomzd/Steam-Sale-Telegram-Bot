# ============================================================
# handlers.py — Все обработчики команд Telegram-бота
# Каждая команда — отдельная async-функция с подробными комментариями
# ============================================================

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID, WHITELIST_ENABLED, WHITELIST, CURRENCIES, DEFAULT_THRESHOLD
from database import (
    get_user,
    create_user,
    set_user_currency,
    set_user_threshold,
    add_tracked_game,
    delete_tracked_game,
    get_user_games,
    get_stats,
)
from steam_api import (
    search_games,
    get_game_details,
    convert_price,
    get_steam_url,
    get_steamdb_url,
)
from checker import check_all_discounts

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# FSM States — состояния машины состояний (для /start онбординга)
# ============================================================
class OnboardingState(StatesGroup):
    choosing_currency = State()  # пользователь выбирает валюту


# ============================================================
# Вспомогательные функции
# ============================================================

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == ADMIN_ID


def is_allowed(user_id: int) -> bool:
    """
    Проверяет доступ к боту с учётом белого списка.
    Если WHITELIST_ENABLED=False — доступ открыт для всех.
    """
    if not WHITELIST_ENABLED:
        return True
    return user_id in WHITELIST or is_admin(user_id)


def make_currency_keyboard() -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру для выбора валюты из CURRENCIES."""
    buttons = []
    for code, (name, symbol, _) in CURRENCIES.items():
        buttons.append(
            InlineKeyboardButton(
                text=f"{symbol} {name} ({code})",
                callback_data=f"currency:{code}",
            )
        )
    # Раскладываем по 2 кнопки в ряд
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================
# /start — Приветствие и выбор валюты
# ============================================================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обработчик /start.
    Если пользователь новый — запускает онбординг (выбор валюты).
    Если уже зарегистрирован — просто приветствует.
    """
    user_id = message.from_user.id

    # Проверяем доступ (белый список)
    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    user = await get_user(user_id)

    if user is None:
        # Новый пользователь — предлагаем выбрать валюту
        await state.set_state(OnboardingState.choosing_currency)
        await message.answer(
            "👋 <b>Добро пожаловать в Steam Sale Bot!</b>\n\n"
            "Я слежу за скидками в Steam и уведомляю, когда цена падает до нужного порога.\n\n"
            "Для начала выберите валюту отображения цен:",
            parse_mode="HTML",
            reply_markup=make_currency_keyboard(),
        )
    else:
        # Уже зарегистрирован — показываем главное меню
        _, symbol, _ = CURRENCIES.get(user["currency"], CURRENCIES["KZT"])
        await message.answer(
            f"👋 С возвращением! Текущая валюта: <b>{user['currency']} {symbol}</b>\n"
            f"Глобальный порог скидки: <b>{user['threshold']}%</b>\n\n"
            "Используй /help для списка команд.",
            parse_mode="HTML",
        )


# ============================================================
# Обработчик выбора валюты (inline кнопка)
# ============================================================
@router.callback_query(F.data.startswith("currency:"), OnboardingState.choosing_currency)
async def callback_currency_select(callback: CallbackQuery, state: FSMContext):
    """
    Срабатывает когда пользователь нажимает кнопку выбора валюты при онбординге.
    Создаёт запись пользователя в БД с выбранной валютой.
    """
    user_id  = callback.from_user.id
    currency = callback.data.split(":")[1]  # извлекаем код валюты из callback_data

    # Создаём запись в БД
    await create_user(user_id, currency)

    _, symbol, _ = CURRENCIES.get(currency, CURRENCIES["KZT"])

    await callback.message.edit_text(
        f"✅ Отлично! Валюта установлена: <b>{currency} {symbol}</b>\n\n"
        f"Глобальный порог скидки по умолчанию: <b>{DEFAULT_THRESHOLD}%</b>\n"
        f"Изменить можно командой /threshold [число]\n\n"
        f"Используй /help для списка всех команд.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ============================================================
# /help — Список команд (динамический для админа)
# ============================================================
@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Показывает список доступных команд.
    Администратор видит дополнительный блок с секретными командами.
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    # Базовые команды для всех пользователей
    text = (
        "📖 <b>Список команд Steam Sale Bot</b>\n\n"
        "/start — Начать работу / сменить валюту\n"
        "/search [название] — Найти игру в Steam\n"
        "/addappid [AppID] [порог%] — Добавить игру в отслеживание\n"
        "    Пример: <code>/addappid 730 50</code>\n"
        "/deleteappid [AppID] — Удалить игру из отслеживания\n"
        "/threshold [число] — Установить порог скидки (по умолчанию 75%)\n"
        "    Пример: <code>/threshold 60</code>\n"
        "/listappid — Список всех отслеживаемых игр\n"
        "/help — Эта справка\n"
    )

    # Дополнительный блок только для администратора
    if is_admin(user_id):
        text += (
            "\n🔐 <b>Команды администратора:</b>\n"
            "/debug_force — Принудительная проверка всех скидок прямо сейчас\n"
            "/stats — Статистика бота (пользователи, игры)\n"
        )

    await message.answer(text, parse_mode="HTML")


# ============================================================
# /search — Поиск игры по названию
# ============================================================
@router.message(Command("search"))
async def cmd_search(message: Message):
    """
    Ищет игры через Steam Store Search API.
    Выводит список с AppID, ценой, скидкой и ссылкой.
    Использование: /search Half-Life
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    # Извлекаем поисковый запрос (всё после команды)
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "❌ Укажите название игры.\n"
            "Пример: <code>/search Counter-Strike</code>",
            parse_mode="HTML",
        )
        return

    query = args[1].strip()

    # Получаем настройки пользователя для конвертации валюты
    user = await get_user(user_id)
    currency = user["currency"] if user else "KZT"

    await message.answer(f"🔍 Ищу: <b>{query}</b>...", parse_mode="HTML")

    results = await search_games(query)

    if not results:
        await message.answer(
            f"😔 По запросу «{query}» ничего не найдено.\n"
            "Попробуй другое название или AppID."
        )
        return

    # Формируем ответ — максимум 5 результатов чтобы не спамить
    lines = [f"🎮 <b>Результаты поиска «{query}»:</b>\n"]

    for i, game in enumerate(results[:5], start=1):
        appid    = game["appid"]
        name     = game["name"]
        discount = game["discount_pct"]
        price    = convert_price(game["price_cents"], currency)
        url      = get_steam_url(appid)

        # Если есть скидка — показываем
        discount_str = f" 🔥 -{discount}%" if discount > 0 else ""

        lines.append(
            f"{i}. <b>{name}</b>\n"
            f"   AppID: <code>{appid}</code> | Цена: {price}{discount_str}\n"
            f"   <a href='{url}'>Страница в Steam</a>\n"
        )

    lines.append("➕ Чтобы добавить в отслеживание: <code>/addappid [AppID]</code>")

    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


# ============================================================
# /addappid — Добавление игры в отслеживание
# ============================================================
@router.message(Command("addappid"))
async def cmd_addappid(message: Message):
    """
    Добавляет игру по AppID в список отслеживания пользователя.
    Опционально можно указать индивидуальный порог скидки.
    Использование: /addappid 730         (использует глобальный порог)
                   /addappid 730 50      (порог 50% для этой игры)
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    # Убеждаемся что пользователь зарегистрирован
    user = await get_user(user_id)
    if user is None:
        await message.answer("Сначала выполни /start для регистрации.")
        return

    args = message.text.split()

    # Валидация аргументов
    if len(args) < 2:
        await message.answer(
            "❌ Укажите AppID игры.\n"
            "Пример: <code>/addappid 730</code> или <code>/addappid 730 50</code>",
            parse_mode="HTML",
        )
        return

    # Парсим AppID
    try:
        appid = int(args[1])
    except ValueError:
        await message.answer("❌ AppID должен быть числом. Например: <code>/addappid 730</code>", parse_mode="HTML")
        return

    # Парсим опциональный порог
    threshold = None
    if len(args) >= 3:
        try:
            threshold = int(args[2])
            if not (1 <= threshold <= 100):
                raise ValueError
        except ValueError:
            await message.answer("❌ Порог скидки должен быть числом от 1 до 100.")
            return

    # Проверяем что игра существует в Steam
    await message.answer(f"⏳ Проверяю AppID <code>{appid}</code>...", parse_mode="HTML")

    details = await get_game_details(appid)
    if details is None:
        await message.answer(
            f"❌ Игра с AppID <code>{appid}</code> не найдена в Steam.\n"
            f"Проверь AppID на <a href='https://store.steampowered.com/'>store.steampowered.com</a>.",
            parse_mode="HTML",
        )
        return

    # Добавляем в БД
    await add_tracked_game(user_id, appid, threshold)

    # Формируем подтверждение
    effective_threshold = threshold if threshold is not None else user["threshold"]
    currency = user["currency"]
    price_str = convert_price(details["price_final"], currency)

    await message.answer(
        f"✅ <b>{details['name']}</b> добавлена в отслеживание!\n\n"
        f"AppID: <code>{appid}</code>\n"
        f"Текущая цена: {price_str} ({details['discount_pct']}% скидка)\n"
        f"Порог уведомления: <b>{effective_threshold}%</b>\n\n"
        f"🔗 <a href='{get_steam_url(appid)}'>Steam</a> | "
        f"<a href='{get_steamdb_url(appid)}'>SteamDB</a>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ============================================================
# /deleteappid — Удаление игры из отслеживания
# ============================================================
@router.message(Command("deleteappid"))
async def cmd_deleteappid(message: Message):
    """
    Удаляет игру из списка отслеживания пользователя.
    Использование: /deleteappid 730
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "❌ Укажите AppID игры.\n"
            "Пример: <code>/deleteappid 730</code>",
            parse_mode="HTML",
        )
        return

    try:
        appid = int(args[1])
    except ValueError:
        await message.answer("❌ AppID должен быть числом.")
        return

    deleted = await delete_tracked_game(user_id, appid)

    if deleted:
        await message.answer(
            f"🗑️ Игра с AppID <code>{appid}</code> удалена из отслеживания.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❓ Игра с AppID <code>{appid}</code> не найдена в вашем списке.",
            parse_mode="HTML",
        )


# ============================================================
# /threshold — Установка глобального порога скидки
# ============================================================
@router.message(Command("threshold"))
async def cmd_threshold(message: Message):
    """
    Устанавливает глобальный порог скидки пользователя.
    Этот порог используется для всех игр без индивидуального порога.
    Использование: /threshold 60
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    user = await get_user(user_id)
    if user is None:
        await message.answer("Сначала выполни /start для регистрации.")
        return

    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            f"📊 Текущий порог скидки: <b>{user['threshold']}%</b>\n\n"
            f"Чтобы изменить: <code>/threshold [число от 1 до 100]</code>\n"
            f"Пример: <code>/threshold 50</code>",
            parse_mode="HTML",
        )
        return

    try:
        new_threshold = int(args[1])
        if not (1 <= new_threshold <= 100):
            raise ValueError
    except ValueError:
        await message.answer("❌ Укажите число от 1 до 100. Пример: <code>/threshold 50</code>", parse_mode="HTML")
        return

    await set_user_threshold(user_id, new_threshold)

    await message.answer(
        f"✅ Глобальный порог скидки установлен: <b>{new_threshold}%</b>\n\n"
        f"Теперь вы будете получать уведомления когда скидка ≥ {new_threshold}%.",
        parse_mode="HTML",
    )


# ============================================================
# /listappid — Список всех отслеживаемых игр
# ============================================================
@router.message(Command("listappid"))
async def cmd_listappid(message: Message):
    """
    Показывает все игры в списке отслеживания пользователя.
    Для каждой игры: название, текущая цена, скидка, пороги, ссылки.
    Делает запросы к Steam API для актуальных данных.
    """
    user_id = message.from_user.id

    if not is_allowed(user_id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    user = await get_user(user_id)
    if user is None:
        await message.answer("Сначала выполни /start для регистрации.")
        return

    games = await get_user_games(user_id)

    if not games:
        await message.answer(
            "📋 Ваш список отслеживания пуст.\n"
            "Добавьте игры командой /addappid [AppID]"
        )
        return

    currency = user["currency"]
    global_threshold = user["threshold"]

    await message.answer(f"⏳ Загружаю данные для {len(games)} игр...")

    lines = [f"📋 <b>Ваши отслеживаемые игры</b> (валюта: {currency}):\n"]

    for i, game_row in enumerate(games, start=1):
        appid          = game_row["appid"]
        game_threshold = game_row["threshold"] if game_row["threshold"] is not None else global_threshold

        # Запрашиваем актуальные данные из Steam
        details = await get_game_details(appid)

        if details is None:
            # Игра могла быть удалена из Steam
            lines.append(
                f"{i}. AppID <code>{appid}</code> — ⚠️ данные недоступны\n"
                f"   Порог: {game_threshold}%\n"
            )
            continue

        name     = details["name"]
        discount = details["discount_pct"]
        price    = convert_price(details["price_final"], currency)

        # Показываем иконку огня если сейчас есть скидка
        discount_str = f"🔥 -{discount}%" if discount > 0 else "без скидки"

        lines.append(
            f"{i}. <b>{name}</b>\n"
            f"   Цена: {price} ({discount_str})\n"
            f"   Порог: <b>{game_threshold}%</b> | AppID: <code>{appid}</code>\n"
            f"   <a href='{get_steam_url(appid)}'>Steam</a> | "
            f"<a href='{get_steamdb_url(appid)}'>SteamDB</a>\n"
        )

    lines.append(f"\n💡 Глобальный порог: <b>{global_threshold}%</b> | Изменить: /threshold")

    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


# ============================================================
# /debug_force — Принудительная проверка (только для админа)
# ============================================================
@router.message(Command("debug_force"))
async def cmd_debug_force(message: Message, bot: Bot):
    """
    Запускает полную проверку скидок прямо сейчас, не дожидаясь планировщика.
    Доступно только администратору.
    """
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return

    await message.answer("🔄 Запускаю принудительную проверку скидок...")

    try:
        await check_all_discounts(bot)
        await message.answer("✅ Проверка завершена! Уведомления отправлены (если были скидки).")
    except Exception as e:
        logger.error(f"Ошибка в debug_force: {e}")
        await message.answer(f"❌ Ошибка при проверке: {e}")


# ============================================================
# /stats — Статистика бота (только для админа)
# ============================================================
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """
    Показывает общую статистику бота.
    Доступно только администратору.
    """
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return

    users_count, games_count = await get_stats()

    await message.answer(
        f"📊 <b>Статистика Steam Sale Bot</b>\n\n"
        f"👥 Пользователей: <b>{users_count}</b>\n"
        f"🎮 Игр в отслеживании: <b>{games_count}</b>\n",
        parse_mode="HTML",
    )
