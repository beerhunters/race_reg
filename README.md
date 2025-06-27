# Beer Mile Registration Bot

Телеграм-бот для регистрации участников и волонтеров на гонку.

## Быстрый старт

### Запуск через Docker
1. Установите [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).
2. Создайте файл `.env` с переменными окружения:
   ```env
   BOT_TOKEN=ваш_токен
   ADMIN_ID=123456789
   ```
3. Запустите бота:
   ```bash
   docker-compose up -d
   ```

### Запуск без Docker
1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Задайте переменные окружения:
   ```bash
   export BOT_TOKEN=ваш_токен
   export ADMIN_ID=123456789
   ```
3. Запустите бота:
   ```bash
   python main.py
   ```

## Переменные окружения
- `BOT_TOKEN` — токен вашего Telegram-бота.
- `ADMIN_ID` — Telegram ID администратора (целое число).

## Конфигурация
- **messages.json**: Содержит все текстовые сообщения бота. Редактируйте для изменения текстов.
- **config.json**: Настройки лимитов участников (`max_runners`) и волонтеров (`max_volunteers`).

## Структура проекта
- `main.py`: Точка входа для запуска бота.
- `handlers.py`: Обработчики команд и сообщений.
- `database.py`: Функции для работы с SQLite базой данных.
- `messages.json`: Тексты сообщений.
- `config.json`: Настройки лимитов.
- `race_participants.db`: SQLite база данных.

## Требования
- Python 3.8+
- aiogram 3.4.1
- python-dotenv
- Docker (для запуска через контейнер)