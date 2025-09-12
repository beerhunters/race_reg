import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.enums import ParseMode

# Импортируем централизованную систему логирования
from logging_config import get_logger, log, setup_telegram_logging

from database import init_db
from handlers.backup_handlers import start_automatic_backups, stop_automatic_backups
from handler_register import register_all_handlers

# Получаем логгер для main модуля
logger = get_logger(__name__)

# Логирование запуска приложения
log.system_event("Application startup", "Starting beermile registration bot")

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
except KeyError as e:
    log.system_event("Environment variable missing", f"Missing: {e}")
    raise

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


async def main():
    log.bot_startup("Initializing beermile registration bot")
    
    # Setup Telegram logging - подключаем бота к системе логирования для отправки ошибок в группу
    setup_telegram_logging(bot)
    
    init_db()
    register_all_handlers(dp, bot, ADMIN_ID)
    
    # Start automatic backups
    await start_automatic_backups(bot, ADMIN_ID)
    
    await bot.set_my_commands(
        [
            BotCommand(command="/start", description="Run, drink, repeat!"),
            BotCommand(command="/info", description="Информация"),
            BotCommand(command="/edit_profile", description="Редактировать профиль"),
            BotCommand(command="/waitlist_status", description="Позиция в очереди"),
        ]
    )
    
    try:
        await dp.start_polling(bot)
    finally:
        # Stop automatic backups on shutdown
        await stop_automatic_backups()


if __name__ == "__main__":
    asyncio.run(main())
