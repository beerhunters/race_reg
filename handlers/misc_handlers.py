from aiogram import Dispatcher, Bot
from aiogram.types import Message
from .utils import logger, messages


def register_misc_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков прочих сообщений")

    @dp.message()
    async def handle_other_messages(message: Message):
        logger.info(
            f"Неизвестная команда от user_id={message.from_user.id}: {message.text}"
        )
        await message.answer(messages["invalid_command"])
