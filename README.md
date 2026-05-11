# 🎮 Steam Sale Bot

Telegram-бот для мониторинга скидок в Steam. Отслеживает нужные игры и уведомляет, когда скидка достигает вашего порога.

---

## ⚡ Быстрый старт

```bash
git clone https://github.com/artiomzd/Steam-Sale-Telegram-Bot
cd Steam-Sale-Telegram-Bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
nano .env          # вставьте BOT_TOKEN и ADMIN_ID
python3 main.py
```

> Для работы в фоне (после закрытия SSH) используйте `screen` или `tmux`:
> ```bash
> screen -S steambot
> python3 main.py
> # Ctrl+A, D — отключиться, бот продолжает работать
> # screen -r steambot — вернуться
> ```

---

## ⚙️ Настройка `.env`

Скопируйте `env.example` в `.env` и заполните:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | Ваш Telegram ID (узнать у [@userinfobot](https://t.me/userinfobot)) |
| `CHECK_INTERVAL_HOURS` | Интервал проверки скидок (по умолчанию `12`) |
| `GLOBAL_STEAM_REGION` | Регион Steam: `kz`, `us`, `de`, `tr`... (по умолчанию `kz`) |
| `WHITELIST_ENABLED` | `true` — только вы, `false` — все пользователи |
| `ENABLE_BANNERS` | `true` — показывать обложки игр в уведомлениях |

---

## 💬 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Начало работы и выбор валюты |
| `/currency` | Сменить валюту в любой момент |
| `/search [название]` | Поиск игры в Steam |
| `/addappid [AppID] [порог%]` | Добавить игру в отслеживание |
| `/deleteappid [AppID]` | Удалить игру из отслеживания |
| `/threshold [число]` | Установить глобальный порог скидки |
| `/listappid` | Список отслеживаемых игр |
| `/help` | Справка по командам |

**Команды администратора** (скрыты от пользователей):

| Команда | Описание |
|---|---|
| `/debug_force` | Принудительная проверка скидок прямо сейчас |
| `/stats` | Статистика: пользователи и игры |

---

## 🌍 Поддерживаемые валюты

`KZT` ₸ · `RUB` ₽ · `USD` $ · `EUR` € · `UAH` ₴

---

## 📄 Лицензия
MIT :D

MIT
