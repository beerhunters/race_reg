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

    @dp.callback_query(F.data == "admin_export_users")
    async def export_all_users(callback_query: CallbackQuery, state: FSMContext):
        """Export all users from database to CSV"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        logger.info(f"Команда экспорта пользователей от user_id={user_id}")
        await callback_query.message.delete()

        try:
            import io
            import csv
            import sqlite3
            from datetime import datetime
            import pytz
            from aiogram.types import BufferedInputFile

            delimiter = config.get("csv_delimiter", ";")
            output = io.StringIO()

            writer = csv.writer(
                output,
                lineterminator="\n",
                delimiter=delimiter,
                quoting=csv.QUOTE_MINIMAL,
            )

            # Helper function to format dates
            def format_date(date_str):
                if not date_str:
                    return "—"
                try:
                    # Parse ISO format date
                    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    # Convert to Moscow timezone
                    moscow_tz = pytz.timezone('Europe/Moscow')
                    dt_moscow = dt.astimezone(moscow_tz)
                    return dt_moscow.strftime('%d.%m.%Y %H:%M:%S')
                except:
                    return str(date_str)

            total_count = 0

            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()

                # 1. Export participants table
                writer.writerow(["=== УЧАСТНИКИ (PARTICIPANTS) ==="])
                writer.writerow([])
                writer.writerow([
                    "User ID",
                    "Username",
                    "Имя",
                    "Целевое время",
                    "Роль",
                    "Дата регистрации",
                    "Статус оплаты",
                    "Беговой номер",
                    "Результат",
                    "Пол",
                    "Категория",
                    "Кластер"
                ])

                cursor.execute("""
                    SELECT user_id, username, name, target_time, role, reg_date,
                           payment_status, bib_number, result, gender, category, cluster
                    FROM participants
                    ORDER BY reg_date
                """)
                participants = cursor.fetchall()

                for p in participants:
                    writer.writerow([
                        p[0],  # user_id
                        p[1] or "—",  # username
                        p[2] or "—",  # name
                        p[3] or "—",  # target_time
                        p[4] or "—",  # role
                        format_date(p[5]),  # reg_date
                        p[6] or "—",  # payment_status
                        p[7] or "—",  # bib_number
                        p[8] or "—",  # result
                        p[9] or "—",  # gender
                        p[10] or "—",  # category
                        p[11] or "—",  # cluster
                    ])
                    total_count += 1

                writer.writerow([])
                writer.writerow([])

                # 2. Export pending registrations
                writer.writerow(["=== НЕЗАВЕРШЕННЫЕ РЕГИСТРАЦИИ (PENDING_REGISTRATIONS) ==="])
                writer.writerow([])
                writer.writerow([
                    "User ID",
                    "Username",
                    "Имя",
                    "Целевое время",
                    "Роль"
                ])

                cursor.execute("""
                    SELECT user_id, username, name, target_time, role
                    FROM pending_registrations
                    ORDER BY user_id
                """)
                pending = cursor.fetchall()

                for p in pending:
                    writer.writerow([
                        p[0],  # user_id
                        p[1] or "—",  # username
                        p[2] or "—",  # name
                        p[3] or "—",  # target_time
                        p[4] or "—",  # role
                    ])
                    total_count += 1

                writer.writerow([])
                writer.writerow([])

                # 3. Export waitlist
                writer.writerow(["=== ЛИСТ ОЖИДАНИЯ (WAITLIST) ==="])
                writer.writerow([])
                writer.writerow([
                    "ID",
                    "User ID",
                    "Username",
                    "Имя",
                    "Целевое время",
                    "Роль",
                    "Пол",
                    "Дата присоединения",
                    "Статус"
                ])

                cursor.execute("""
                    SELECT id, user_id, username, name, target_time, role,
                           gender, join_date, status
                    FROM waitlist
                    ORDER BY join_date
                """)
                waitlist = cursor.fetchall()

                for w in waitlist:
                    writer.writerow([
                        w[0],  # id
                        w[1],  # user_id
                        w[2] or "—",  # username
                        w[3] or "—",  # name
                        w[4] or "—",  # target_time
                        w[5] or "—",  # role
                        w[6] or "—",  # gender
                        format_date(w[7]),  # join_date
                        w[8] or "—",  # status
                    ])
                    total_count += 1

                writer.writerow([])
                writer.writerow([])

                # 4. Export bot users
                writer.writerow(["=== ВСЕ ПОЛЬЗОВАТЕЛИ БОТА (BOT_USERS) ==="])
                writer.writerow([])
                writer.writerow([
                    "User ID",
                    "Username",
                    "Имя",
                    "Фамилия",
                    "Первое взаимодействие",
                    "Последнее взаимодействие"
                ])

                cursor.execute("""
                    SELECT user_id, username, first_name, last_name,
                           first_interaction, last_interaction
                    FROM bot_users
                    ORDER BY first_interaction
                """)
                bot_users = cursor.fetchall()

                for u in bot_users:
                    writer.writerow([
                        u[0],  # user_id
                        u[1] or "—",  # username
                        u[2] or "—",  # first_name
                        u[3] or "—",  # last_name
                        format_date(u[4]),  # first_interaction
                        format_date(u[5]),  # last_interaction
                    ])

                writer.writerow([])
                writer.writerow([])

                # 5. Export teams if table exists
                try:
                    cursor.execute("""
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name='teams'
                    """)
                    if cursor.fetchone():
                        writer.writerow(["=== КОМАНДЫ (TEAMS) ==="])
                        writer.writerow([])
                        writer.writerow([
                            "ID",
                            "Участник 1 (User ID)",
                            "Участник 2 (User ID)",
                            "Результат",
                            "Дата создания"
                        ])

                        cursor.execute("""
                            SELECT id, member1_id, member2_id, result, created_at
                            FROM teams
                            ORDER BY created_at
                        """)
                        teams = cursor.fetchall()

                        for t in teams:
                            writer.writerow([
                                t[0],  # id
                                t[1] or "—",  # member1_id
                                t[2] or "—",  # member2_id
                                t[3] or "—",  # result
                                format_date(t[4]),  # created_at
                            ])
                            total_count += 1

                        writer.writerow([])
                        writer.writerow([])
                except:
                    pass  # Table doesn't exist

            csv_content = output.getvalue()
            output.close()

            # Generate timestamp for filename
            moscow_timezone = pytz.timezone("Europe/Moscow")
            moscow_now = datetime.now(moscow_timezone)
            timestamp = moscow_now.strftime("%Y%m%d_%H%M%S")
            filename = f"all_users_{timestamp}.csv"

            logger.info(
                f"CSV-файл пользователей сформирован, размер: {len(csv_content)} символов"
            )

            csv_bytes = csv_content.encode("utf-8-sig")
            await callback_query.message.answer_document(
                document=BufferedInputFile(csv_bytes, filename=filename)
            )

            # Statistics message
            stats_text = "✅ <b>Экспорт пользователей завершён</b>\n\n"
            stats_text += f"📊 <b>Экспортировано записей:</b>\n"
            stats_text += f"• Участников: {len(participants)}\n"
            stats_text += f"• Незавершённых регистраций: {len(pending)}\n"
            stats_text += f"• В листе ожидания: {len(waitlist)}\n"
            stats_text += f"• Всего пользователей бота: {len(bot_users)}\n"
            stats_text += f"\n📁 Файл содержит все таблицы БД с разделением по категориям"

            await callback_query.message.answer(stats_text)
            logger.info(
                f"CSV-файл пользователей успешно отправлен для user_id={user_id}"
            )

        except Exception as e:
            logger.error(f"Ошибка при экспорте пользователей: {e}")
            await callback_query.message.answer(
                "❌ Произошла ошибка при экспорте пользователей. Проверьте логи."
            )

        await callback_query.answer()

    logger.info("Обработчики информации и медиа зарегистрированы")
