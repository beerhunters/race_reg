import os
import json
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from .utils import (
    messages,
    RegistrationForm,
    logger,
    messages,
    config,
    RegistrationForm,
    get_participation_fee_text,
    get_event_date_text,
    get_event_location_text,
)


def register_info_media_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков информации и медиа")

    @dp.message(Command("info"))
    async def show_info(message: Message):
        """Show info to regular users"""
        user_id = message.from_user.id
        logger.info(f"Команда /info от user_id={user_id}")
        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=message.from_user.id,
                    photo=FSInputFile(afisha_path),
                    caption=messages["info_message"].format(
                        fee=get_participation_fee_text(),
                        event_date=get_event_date_text(),
                        event_location=get_event_location_text()
                    ),
                )
                logger.info(
                    f"Афиша отправлена с текстом info_message пользователю user_id={message.from_user.id}"
                )
            else:
                await message.answer(
                    messages["info_message"].format(
                        fee=get_participation_fee_text(),
                        event_date=get_event_date_text(),
                        event_location=get_event_location_text()
                    )
                )
                logger.info(
                    f"Афиша не найдена, отправлен только текст info_message пользователю user_id={message.from_user.id}"
                )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения /info пользователю user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                messages["info_message"].format(
                    fee=get_participation_fee_text(),
                    event_date=get_event_date_text(),
                    event_location=get_event_location_text()
                )
            )

    @dp.message(Command("create_afisha"))
    @dp.callback_query(F.data == "admin_create_afisha")
    async def create_afisha(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда создания афиши от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event

        # Check if afisha already exists
        afisha_path = "/app/images/afisha.jpeg"
        afisha_exists = os.path.exists(afisha_path)

        text = "🖼 <b>Обновить афишу</b>\n\n"

        if afisha_exists:
            try:
                # Get file size and modification time
                file_stat = os.stat(afisha_path)
                file_size = file_stat.st_size / 1024  # KB
                from datetime import datetime

                mod_time = datetime.fromtimestamp(file_stat.st_mtime)

                text += f"📊 <b>Текущая афиша:</b>\n"
                text += f"• Размер: {file_size:.1f} КБ\n"
                text += f"• Обновлена: {mod_time.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"• Путь: {afisha_path}\n\n"
                text += "🔄 Отправьте новое изображение для замены текущей афиши\n"
            except Exception as e:
                text += "📊 Текущая афиша существует\n\n"
                text += "🔄 Отправьте новое изображение для замены\n"
        else:
            text += "📊 Афиша отсутствует\n\n"
            text += "📤 Отправьте изображение для создания афиши\n"

        text += "\n📋 <b>Требования к изображению:</b>\n"
        text += "• Формат: JPG, PNG\n"
        text += "• Рекомендуемый размер: до 10 МБ\n"
        text += "• Будет сохранено как afisha.jpeg\n"
        text += "• Показывается пользователям по команде /info"

        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_afisha_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_afisha_image), F.photo)
    async def process_afisha_image(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        logger.info(f"Получено изображение афиши от user_id={message.from_user.id}")

        try:
            afisha_path = "/app/images/afisha.jpeg"

            # Check if directory exists
            os.makedirs(os.path.dirname(afisha_path), exist_ok=True)

            # Get the largest photo resolution
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)

            # Check file size (Telegram photo limit is usually reasonable, but let's be safe)
            file_size_mb = file.file_size / (1024 * 1024) if file.file_size else 0

            if file.file_size and file.file_size > 20 * 1024 * 1024:  # 20MB limit
                await message.answer("❌ Изображение слишком большое. Максимум 20 МБ.")
                return

            # Download and save the file
            await bot.download_file(file.file_path, afisha_path)
            os.chmod(afisha_path, 0o644)

            # Get file info for confirmation
            file_stat = os.stat(afisha_path)
            final_size_kb = file_stat.st_size / 1024

            text = "✅ <b>Афиша успешно загружена</b>\n\n"
            text += f"📊 <b>Информация о файле:</b>\n"
            text += f"• Размер: {final_size_kb:.1f} КБ\n"
            text += f"• Разрешение: {photo.width}x{photo.height}px\n"
            text += f"• Путь: {afisha_path}\n\n"
            text += "🔄 Афиша обновлена и будет показываться пользователям по команде /info\n\n"
            text += "💡 Для проверки отправьте команду /info"

            await message.answer(text)
            logger.info(
                f"Изображение афиши сохранено в {afisha_path}, размер: {final_size_kb:.1f} КБ"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при сохранении афиши от user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                "❌ Ошибка при сохранении афиши. Проверьте, что отправляете изображение в правильном формате."
            )

        await state.clear()

    @dp.message(StateFilter(RegistrationForm.waiting_for_afisha_image))
    async def process_afisha_non_photo(message: Message, state: FSMContext):
        """Handle non-photo messages in afisha upload mode"""
        await message.answer(
            "❌ Ожидается изображение афиши.\n\n"
            "📤 Отправьте фотографию или изображение\n"
            "🔄 Или используйте команду /cancel для отмены"
        )

    @dp.message(Command("update_sponsor"))
    @dp.callback_query(F.data == "admin_update_sponsor")
    async def update_sponsor(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда обновления спонсоров от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event

        # Check if sponsor image already exists
        sponsor_path = config.get(
            "sponsor_image_path", "/app/images/sponsor_image.jpeg"
        )
        sponsor_exists = os.path.exists(sponsor_path)

        text = "🤝 <b>Обновить спонсорское изображение</b>\n\n"

        if sponsor_exists:
            try:
                # Get file size and modification time
                file_stat = os.stat(sponsor_path)
                file_size = file_stat.st_size / 1024  # KB
                from datetime import datetime

                mod_time = datetime.fromtimestamp(file_stat.st_mtime)

                text += f"📊 <b>Текущее изображение:</b>\n"
                text += f"• Размер: {file_size:.1f} КБ\n"
                text += f"• Обновлено: {mod_time.strftime('%d.%m.%Y %H:%M')}\n"
                text += f"• Путь: {sponsor_path}\n\n"
                text += "🔄 Отправьте новое изображение для замены\n"
            except Exception as e:
                text += "📊 Текущее изображение существует\n\n"
                text += "🔄 Отправьте новое изображение для замены\n"
        else:
            text += "📊 Спонсорское изображение отсутствует\n\n"
            text += "📤 Отправьте изображение спонсоров\n"

        text += "\n📋 <b>Требования к изображению:</b>\n"
        text += "• Формат: JPG, PNG\n"
        text += "• Рекомендуемый размер: до 10 МБ\n"
        text += "• Логотипы спонсоров, баннеры и т.д.\n"
        text += "• Может использоваться в рассылках и уведомлениях"

        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_sponsor_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_sponsor_image), F.photo)
    async def process_sponsor_image(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        logger.info(f"Получено изображение спонсоров от user_id={message.from_user.id}")

        try:
            sponsor_path = config.get(
                "sponsor_image_path", "/app/images/sponsor_image.jpeg"
            )

            # Check if directory exists
            os.makedirs(os.path.dirname(sponsor_path), exist_ok=True)

            # Get the largest photo resolution
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)

            # Check file size
            if file.file_size and file.file_size > 20 * 1024 * 1024:  # 20MB limit
                await message.answer("❌ Изображение слишком большое. Максимум 20 МБ.")
                return

            # Download and save the file
            await bot.download_file(file.file_path, sponsor_path)
            os.chmod(sponsor_path, 0o644)

            # Get file info for confirmation
            file_stat = os.stat(sponsor_path)
            final_size_kb = file_stat.st_size / 1024

            text = "✅ <b>Спонсорское изображение успешно загружено</b>\n\n"
            text += f"📊 <b>Информация о файле:</b>\n"
            text += f"• Размер: {final_size_kb:.1f} КБ\n"
            text += f"• Разрешение: {photo.width}x{photo.height}px\n"
            text += f"• Путь: {sponsor_path}\n\n"
            text += "🔄 Изображение сохранено и может использоваться в рассылках\n\n"
            text += "💡 Используйте команды уведомлений для отправки пользователям"

            await message.answer(text)
            logger.info(
                f"Изображение спонсоров сохранено в {sponsor_path}, размер: {final_size_kb:.1f} КБ"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при сохранении изображения спонсоров от user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                "❌ Ошибка при сохранении изображения спонсоров. Проверьте формат файла."
            )

        await state.clear()

    @dp.message(StateFilter(RegistrationForm.waiting_for_sponsor_image))
    async def process_sponsor_non_photo(message: Message, state: FSMContext):
        """Handle non-photo messages in sponsor upload mode"""
        await message.answer(
            "❌ Ожидается изображение спонсоров.\n\n"
            "📤 Отправьте фотографию или изображение\n"
            "🔄 Или используйте команду /cancel для отмены"
        )

    @dp.message(Command("update_welcome"))
    @dp.callback_query(F.data == "admin_welcome")
    async def update_welcome_message(
        event: [Message, CallbackQuery], state: FSMContext
    ):
        """Update welcome message"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(
            f"Команда обновления приветственного сообщения от user_id={user_id}"
        )

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event

        # Get current welcome message
        current_welcome = messages.get("start_message", "Сообщение не найдено")

        text = f"👋 <b>Обновить приветственное сообщение</b>\n\n"
        text += f"📝 <b>Текущее сообщение:</b>\n"
        text += f"<code>{current_welcome}</code>\n\n"
        text += f"✏️ Отправьте новое приветственное сообщение:\n"
        text += f"• HTML разметка поддерживается\n"
        text += f"• Максимум 4096 символов\n"
        text += f"• Это сообщение показывается по команде /start"

        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_welcome_message)

    @dp.message(RegistrationForm.waiting_for_welcome_message)
    async def process_welcome_message(message: Message, state: FSMContext):
        """Process new welcome message"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        if not message.text:
            await message.answer(
                "❌ Сообщение должно содержать текст. Попробуйте снова:"
            )
            return

        new_welcome = message.text.strip()
        if len(new_welcome) > 4096:
            await message.answer(
                "❌ Сообщение слишком длинное. Максимум 4096 символов. Попробуйте снова:"
            )
            return

        try:
            # Update the messages.json file
            messages_path = "/app/messages.json"

            # Read current messages
            if os.path.exists(messages_path):
                with open(messages_path, "r", encoding="utf-8") as f:
                    current_messages = json.load(f)
            else:
                current_messages = {}

            # Update welcome message
            old_welcome = current_messages.get("start_message", "не установлено")
            current_messages["start_message"] = new_welcome

            # Save updated messages
            with open(messages_path, "w", encoding="utf-8") as f:
                json.dump(current_messages, f, ensure_ascii=False, indent=2)

            # Update the global messages dict
            messages["start_message"] = new_welcome

            text = "✅ <b>Приветственное сообщение обновлено</b>"

            await message.answer(text)
            logger.info(f"Приветственное сообщение обновлено")

        except Exception as e:
            logger.error(f"Ошибка при обновлении приветственного сообщения: {e}")
            await message.answer(
                "❌ Ошибка при сохранении сообщения. Попробуйте снова."
            )

        await state.clear()

    @dp.message(Command("update_info"))
    @dp.callback_query(F.data == "admin_info")
    async def update_info_message(event: [Message, CallbackQuery], state: FSMContext):
        """Update information message"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(
            f"Команда обновления информационного сообщения от user_id={user_id}"
        )

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event

        # Get current info message
        current_info = messages.get("info_message", "Сообщение не найдено")

        text = "ℹ️ <b>Обновить информационное сообщение</b>\n\n"
        text += "📝 <b>Текущее сообщение:</b>\n"
        text += f"<code>{current_info}</code>\n\n"
        text += "✏️ Отправьте новое информационное сообщение:\n"
        text += "• HTML разметка поддерживается\n"
        text += "• Максимум 4096 символов\n"
        text += "• Используйте {fee} для вставки цены участия\n"
        text += "• Это сообщение показывается по команде /info"

        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_info_message)

    @dp.message(RegistrationForm.waiting_for_info_message)
    async def process_info_message(message: Message, state: FSMContext):
        """Process new information message"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        if not message.text:
            await message.answer(
                "❌ Сообщение должно содержать текст. Попробуйте снова:"
            )
            return

        new_info = message.text.strip()
        if len(new_info) > 4096:
            await message.answer(
                "❌ Сообщение слишком длинное. Максимум 4096 символов. Попробуйте снова:"
            )
            return

        try:
            # Update the messages.json file
            messages_path = "/app/messages.json"

            # Read current messages
            if os.path.exists(messages_path):
                with open(messages_path, "r", encoding="utf-8") as f:
                    current_messages = json.load(f)
            else:
                current_messages = {}

            # Update info message
            old_info = current_messages.get("info_message", "не установлено")
            current_messages["info_message"] = new_info

            # Save updated messages
            with open(messages_path, "w", encoding="utf-8") as f:
                json.dump(current_messages, f, ensure_ascii=False, indent=2)

            # Update the global messages dict
            messages["info_message"] = new_info

            text = "✅ <b>Информационное сообщение обновлено</b>\n\n"
            text += "📝 <b>Новое сообщение:</b>\n"
            text += f"<code>{new_info}</code>\n\n"
            text += "🔄 Изменения вступают в силу немедленно.\n"
            text += "💡 Пользователи увидят новое сообщение по команде /info"

            await message.answer(text)
            logger.info(f"Информационное сообщение обновлено")

        except Exception as e:
            logger.error(f"Ошибка при обновлении информационного сообщения: {e}")
            await message.answer(
                "❌ Ошибка при сохранении сообщения. Попробуйте снова."
            )

        await state.clear()

    logger.info("Обработчики информации и медиа зарегистрированы")
