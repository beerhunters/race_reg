import asyncio
import logging.handlers
import os
import json
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.enums import ParseMode

from database import init_db
from handlers.backup_handlers import start_automatic_backups, stop_automatic_backups

from handler_register import register_all_handlers


# Import logging setup from handlers.utils
from handlers.utils import logger, log_level, log

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    log.system_event("Config loaded", "config.json loaded successfully")
except FileNotFoundError:
    log.system_event("Config loading failed", "config.json not found")
    raise
except json.JSONDecodeError as e:
    log.system_event("Config loading failed", f"JSON decode error: {e}")
    raise

if config.get("log_level") not in log_level:
    log.validation_error("log_level", config.get("log_level"), "Invalid log level, using ERROR")
    logging.getLogger().setLevel(logging.ERROR)
else:
    logging.getLogger().setLevel(log_level[config["log_level"]])
    log.system_event("Log level set", f"Level: {config['log_level']}")

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
except KeyError as e:
    log.system_event("Environment variable missing", f"Missing: {e}")
    raise

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


async def main():
    log.system_event("Bot startup")
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
