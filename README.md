# Beer Mile Registration Bot

Телеграм-бот для регистрации участников на гонку.

## Быстрый старт

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. В файле `main.py` замените `YOUR_BOT_TOKEN_HERE` на токен вашего бота, а также укажите свой Telegram ID в `ADMIN_ID`.
3. Запустите бота:
   ```bash
   python main.py
   ```

## Переменные окружения

Перед запуском необходимо задать переменные окружения:

- `BOT_TOKEN` — токен вашего Telegram-бота
- `ADMIN_ID` — Telegram ID администратора (целое число)

Пример запуска:

```bash
export BOT_TOKEN=ваш_токен
export ADMIN_ID=123456789
python main.py
```

## Требования
- Python 3.8+
- aiogram 3.x 