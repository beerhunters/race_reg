import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from database import init_db
import handlers

# Настройка логирования
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/app/logs/bot.log")],
)
logger = logging.getLogger(__name__)

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
except KeyError as e:
    logger.error(f"Переменная окружения {e} не задана")
    raise
except ValueError as e:
    logger.error(f"Неверный формат ADMIN_ID: {e}")
    raise

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


async def main():
    logger.info("Инициализация базы данных")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise
    logger.info("Регистрация обработчиков")
    handlers.register_handlers(dp, bot, ADMIN_ID)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Run, drink, repeat!"),
        ]
    )
    logger.info("Запуск бота")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise


if __name__ == "__main__":
    logger.info("Старт приложения")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
