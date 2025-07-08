import os
import json
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from .utils import logger, messages, config, RegistrationForm


def register_info_media_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков информации и медиа")

    @dp.message(Command("info"))
    async def show_info(message: Message):
        logger.info(f"Команда /info от user_id={message.from_user.id}")
        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=message.from_user.id,
                    photo=FSInputFile(afisha_path),
                    caption=messages["info_message"],
                )
                logger.info(
                    f"Афиша отправлена с текстом info_message пользователю user_id={message.from_user.id}"
                )
            else:
                await message.answer(messages["info_message"])
                logger.info(
                    f"Афиша не найдена, отправлен только текст info_message пользователю user_id={message.from_user.id}"
                )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения /info пользователю user_id={message.from_user.id}: {e}"
            )
            await message.answer(messages["info_message"])

    @dp.message(Command("info_create"))
    async def info_create(message: Message, state: FSMContext):
        logger.info(f"Команда /info_create от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /info_create запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["info_create_access_denied"])
            return
        await message.answer(messages["info_create_prompt"])
        await state.set_state(RegistrationForm.waiting_for_info_message)

    @dp.message(StateFilter(RegistrationForm.waiting_for_info_message))
    async def process_info_message(message: Message, state: FSMContext):
        logger.info(f"Получен новый текст для /info от user_id={message.from_user.id}")
        new_info_message = message.text.strip()
        try:
            global messages
            messages["info_message"] = new_info_message
            with open("messages.json", "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            logger.info("Файл messages.json успешно обновлен с новым info_message")
            await message.answer(messages["info_create_success"])
        except Exception as e:
            logger.error(f"Ошибка при обновлении messages.json: {e}")
            await message.answer("Ошибка при сохранении информации. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("create_afisha"))
    async def create_afisha(message: Message, state: FSMContext):
        logger.info(f"Команда /create_afisha от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /create_afisha запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["create_afisha_access_denied"])
            return
        await message.answer(messages["create_afisha_prompt"])
        await state.set_state(RegistrationForm.waiting_for_afisha_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_afisha_image), F.photo)
    async def process_afisha_image(message: Message, state: FSMContext):
        logger.info(f"Получено изображение афиши от user_id={message.from_user.id}")
        try:
            afisha_path = "/app/images/afisha.jpeg"
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            await bot.download_file(file_path, afisha_path)
            os.chmod(afisha_path, 0o644)
            logger.info(f"Изображение афиши сохранено в {afisha_path}")
            await message.answer(messages["create_afisha_success"])
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении афиши от user_id={message.from_user.id}: {e}"
            )
            await message.answer("Ошибка при сохранении афиши. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("update_sponsor"))
    async def update_sponsor(message: Message, state: FSMContext):
        logger.info(f"Команда /update_sponsor от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /update_sponsor запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["update_sponsor_access_denied"])
            return
        await message.answer(messages["update_sponsor_prompt"])
        await state.set_state(RegistrationForm.waiting_for_sponsor_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_sponsor_image), F.photo)
    async def process_sponsor_image(message: Message, state: FSMContext):
        logger.info(f"Получено изображение спонсоров от user_id={message.from_user.id}")
        try:
            sponsor_path = config.get(
                "sponsor_image_path", "/app/images/sponsor_image.jpeg"
            )
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            await bot.download_file(file_path, sponsor_path)
            os.chmod(sponsor_path, 0o644)
            logger.info(f"Изображение спонсоров сохранено в {sponsor_path}")
            await message.answer(messages["update_sponsor_success"])
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении изображения спонсоров от user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                "Ошибка при сохранении изображения спонсоров. Попробуйте снова."
            )
        await state.clear()
