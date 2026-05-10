# 🎮 Steam Sale Bot

Telegram-бот для мониторинга скидок в Steam. Бот запрашивает цены через казахстанский регион (обходя ограничения РФ), отслеживает нужные игры и уведомляет когда скидка достигает вашего порога.

---

## 📦 Структура проекта

```
steam_bot/
├── main.py          # Точка входа, запуск бота и планировщика
├── config.py        # Все настройки (токен, регион, интервал)
├── database.py      # Работа с SQLite через aiosqlite
├── steam_api.py     # Запросы к Steam Store API
├── handlers.py      # Обработчики команд Telegram
├── checker.py       # Логика проверки скидок и отправки уведомлений
├── requirements.txt # Зависимости Python
└── steam_bot.db     # База данных (создаётся автоматически)
```

---

## 🖥️ Установка на сервер (Ubuntu / Debian)

### Шаг 1 — Обновить систему

```bash
sudo apt update && sudo apt upgrade -y
```

---

### Шаг 2 — Установить Python 3.11+

Проверяем версию Python:
```bash
python3 --version
```

Если версия ниже 3.11 — устанавливаем свежую:

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-distutils
```

Проверяем:
```bash
python3.11 --version
# Python 3.11.x
```

---

### Шаг 3 — Установить `screen`

`screen` — утилита, которая держит процесс запущенным **после закрытия SSH-сессии**. Бот продолжает работать в фоне.

```bash
sudo apt install -y screen
```

> **Альтернатива:** `tmux` — более современная замена screen.  
> Установка: `sudo apt install -y tmux`  
> Запуск сессии: `tmux new -s steambot`  
> Отключиться: `Ctrl+B`, затем `D`  
> Вернуться: `tmux attach -t steambot`

---

### Шаг 4 — Скачать код

Клонируем репозиторий (или загружаем файлы вручную через `scp` / FTP):

```bash
git clone https://github.com/artiomzd/Steam-Sale-Telegram-Bot
cd Steam-Sale-Telegram-Bot
```

---

### Шаг 5 — Создать виртуальное окружение

Виртуальное окружение изолирует зависимости бота от системного Python.

```bash
python3.11 -m venv venv
```

Активировать окружение:
```bash
source venv/bin/activate
```

После активации приглашение консоли изменится на `(venv) user@server:~$`

---

### Шаг 6 — Установить зависимости

```bash
pip install -r requirements.txt
```

Это установит:
| Библиотека | Для чего |
|---|---|
| `aiogram 3.x` | Telegram Bot API фреймворк |
| `aiosqlite` | Асинхронная работа с SQLite |
| `aiohttp` | HTTP-запросы к Steam API |
| `apscheduler` | Планировщик задач (проверка каждые N часов) |

---

### Шаг 7 — Настроить бота через `.env`

Токен и другие настройки хранятся в файле `.env` — он **не попадает в Git** (добавлен в `.gitignore`).

Создаём `.env` из шаблона:

```bash
cp .env.example .env
nano .env
```

Заполняем обязательные поля:

```dotenv
BOT_TOKEN=123456789:ABCdef...   # Токен от @BotFather
ADMIN_ID=868847332              # Ваш Telegram ID (узнать у @userinfobot)
```

Остальное можно оставить как есть или поменять по вкусу:

```dotenv
CHECK_INTERVAL_HOURS=12     # Как часто проверять скидки
GLOBAL_STEAM_REGION=kz      # Регион Steam (kz, us, de, tr...)
WHITELIST_ENABLED=false     # true = только вы, false = все
ENABLE_BANNERS=true         # Показывать обложки игр в уведомлениях
```

Сохранить: `Ctrl+O`, Enter, `Ctrl+X`

> ⚠️ **Никогда не коммить `.env` в Git.** Файл `.gitignore` уже настроен правильно — `.env` туда включён.

---

### Шаг 8 — Запустить бота через screen

#### Создаём новую screen-сессию с именем `steambot`:

```bash
screen -S steambot
```

#### Активируем виртуальное окружение (если ещё не активировано):

```bash
cd ~/steam-sale-bot
source venv/bin/activate
```

#### Запускаем бота:

```bash
python main.py
```

Вы увидите что-то вроде:
```
2024-01-15 12:00:00 [INFO] Инициализация базы данных...
2024-01-15 12:00:00 [INFO] ✅ Планировщик запущен. Проверка каждые 12 ч.
2024-01-15 12:00:00 [INFO] 🚀 Бот запущен, ожидаю команды...
```

#### Отключаемся от screen, оставляя бота работать:

Нажмите `Ctrl+A`, затем `D` (detach).

Вы вернётесь в обычную консоль. Бот продолжает работать в фоне.

---

## 🔧 Управление screen-сессией

| Команда | Действие |
|---|---|
| `screen -S steambot` | Создать новую сессию с именем steambot |
| `screen -ls` | Список всех активных сессий |
| `screen -r steambot` | Вернуться в сессию steambot |
| `Ctrl+A`, затем `D` | Отключиться от сессии (бот продолжает работать) |
| `Ctrl+C` | Остановить бота (внутри сессии) |
| `screen -X -S steambot quit` | Убить сессию целиком |

---

## 🔁 Автозапуск после перезагрузки сервера (опционально)

Чтобы бот запускался автоматически при ребуте, используем `systemd`.

Создаём файл службы:

```bash
sudo nano /etc/systemd/system/steambot.service
```

Содержимое (замените `ВАШ_ЮЗЕР` и путь):

```ini
[Unit]
Description=Steam Sale Telegram Bot
After=network.target

[Service]
Type=simple
User=ВАШ_ЮЗЕР
WorkingDirectory=/home/ВАШ_ЮЗЕР/steam-sale-bot
ExecStart=/home/ВАШ_ЮЗЕР/steam-sale-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активируем и запускаем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable steambot
sudo systemctl start steambot
```

Проверяем статус:

```bash
sudo systemctl status steambot
```

Логи:
```bash
journalctl -u steambot -f
```

---

## 💬 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Начало работы, выбор валюты |
| `/search [название]` | Поиск игры в Steam |
| `/addappid [AppID] [порог%]` | Добавить игру в отслеживание |
| `/deleteappid [AppID]` | Удалить игру |
| `/threshold [число]` | Установить глобальный порог скидки |
| `/listappid` | Список всех отслеживаемых игр |
| `/help` | Справка по командам |

### Команды администратора (скрыты от обычных пользователей)

| Команда | Описание |
|---|---|
| `/debug_force` | Принудительная проверка прямо сейчас |
| `/stats` | Статистика: пользователи и игры |

---

## 🌍 Поддерживаемые валюты

| Код | Валюта | Символ |
|---|---|---|
| KZT | Казахстанский тенге | ₸ |
| RUB | Российский рубль | ₽ |
| USD | Доллар США | $ |
| EUR | Евро | € |
| UAH | Украинская гривна | ₴ |

> Курсы конвертации задаются в `config.py` → `CURRENCIES`.  
> Для актуальных курсов можно подключить внешний API (например, exchangerate.host).

---

## 🛠️ Обновление бота

```bash
# Возвращаемся в сессию
screen -r steambot

# Останавливаем бота
Ctrl+C

# Обновляем код
git pull

# Если добавились новые зависимости
pip install -r requirements.txt

# Запускаем снова
python main.py

# Отключаемся
Ctrl+A, D
```

---

## ❓ Частые проблемы

**Бот не отвечает после перезапуска SSH**  
→ Убедитесь что запускали через `screen`. Проверьте: `screen -ls`

**`ModuleNotFoundError`**  
→ Виртуальное окружение не активировано. Выполните: `source venv/bin/activate`

**Steam API не отдаёт цены**  
→ Steam иногда возвращает пустой `price_overview` для free-to-play игр или DLC. Это нормально.

**Бот не находит игру по AppID**  
→ Проверьте AppID на [store.steampowered.com](https://store.steampowered.com). AppID есть в URL страницы игры.

---

## 📄 Лицензия

MIT — используйте свободно.
