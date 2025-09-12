from aiogram import Dispatcher, Bot
from aiogram.types import Message
from logging_config import get_logger
from .utils import messages, create_main_menu_keyboard

logger = get_logger(__name__)


def register_misc_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков прочих сообщений")

    @dp.message()
    async def handle_other_messages(message: Message):
        logger.info(
            f"Неизвестная команда от user_id={message.from_user.id}: {message.text}"
        )
        await message.answer(messages["invalid_command"], reply_markup=create_main_menu_keyboard())
