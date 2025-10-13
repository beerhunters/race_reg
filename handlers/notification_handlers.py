import re
import sqlite3
import os
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from .utils import (
    messages,
    RegistrationForm,
    logger,
    messages,
    config,
    RegistrationForm,
    create_confirmation_keyboard,
    get_participation_fee_text,
    get_event_date_text,
    get_event_location_text,
)
from database import (
    get_all_participants,
    get_pending_registrations,
    get_all_bot_users,
    cleanup_blocked_user,
    delete_participant,
    delete_pending_registration,
    set_result,
    get_participant_by_user_id,
)


async def get_users_by_audience(audience_type):
    """Get user lists based on audience type"""
    user_lists = {
        "participants": [],
        "pending": [],
        "waitlist": [],
        "archives": [],
        "bot_users": []
    }
    
    if audience_type in ["participants", "all"]:
        participants = get_all_participants()
        user_lists["participants"] = [(p[0], p[1], p[2]) for p in participants]  # user_id, username, name
    
    if audience_type in ["pending", "all"]:
        pending = get_pending_registrations()  
        user_lists["pending"] = [(p[0], p[1], p[2]) for p in pending if len(p) >= 3]  # user_id, username, name
    
    if audience_type in ["waitlist", "all"]:
        from database import get_waitlist_by_role
        waitlist = get_waitlist_by_role()
        user_lists["waitlist"] = [(w[1], w[2], w[3]) for w in waitlist]  # user_id, username, name
    
    if audience_type in ["archives", "all"]:
        # Get users from archived tables
        try:
            from database import get_historical_participants
            historical_users = get_historical_participants()
            
            # Get details for historical participants
            archive_users = []
            bot_users = get_all_bot_users()
            bot_users_dict = {u[0]: (u[1], f"{u[2] or ''} {u[3] or ''}".strip()) for u in bot_users if len(u) >= 4}
            
            for user_id in historical_users:
                if user_id in bot_users_dict:
                    username, name = bot_users_dict[user_id]
                    archive_users.append((user_id, username, name))
            
            user_lists["archives"] = archive_users
        except Exception as e:
            logger.error(f"Ошибка получения архивных пользователей: {e}")
    
    # Add bot_users for "all" audience type
    if audience_type == "all":
        try:
            bot_users = get_all_bot_users()
            
            # Get all existing user_ids from other categories to avoid duplicates
            existing_user_ids = set()
            for category, users in user_lists.items():
                if category != "bot_users":
                    existing_user_ids.update([user[0] for user in users])
            
            # Add unique bot users
            unique_bot_users = []
            for bot_user in bot_users:
                if len(bot_user) >= 4:
                    user_id, username, first_name, last_name = bot_user[0], bot_user[1], bot_user[2], bot_user[3]
                    if user_id not in existing_user_ids:
                        name = f"{first_name or ''} {last_name or ''}".strip() or "Без имени"
                        unique_bot_users.append((user_id, username, name))
            
            user_lists["bot_users"] = unique_bot_users
        except Exception as e:
            logger.error(f"Ошибка получения пользователей из bot_users: {e}")
    
    return user_lists


def get_audience_name(audience_type):
    """Get human-readable audience name"""
    names = {
        "participants": "Участники",
        "pending": "Pending регистрации",
        "waitlist": "Очередь ожидания", 
        "archives": "Из архивов",
        "all": "Все группы"
    }
    return names.get(audience_type, audience_type)


def get_category_name(category):
    """Get human-readable category name"""
    names = {
        "participants": "Участники",
        "pending": "Pending",
        "waitlist": "Очередь ожидания",
        "archives": "Архивы",
        "bot_users": "Остальные пользователи"
    }
    return names.get(category, category)


def register_notification_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков уведомлений")

    @dp.message(Command("notify_all"))
    @dp.callback_query(F.data == "admin_notify_all")
    async def notify_all_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_all_access_denied"])
            return
        logger.info(f"Команда /notify_all от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        participants = get_all_participants()
        if not participants:
            logger.info("Нет зарегистрированных участников для уведомления")
            await message.answer(messages["notify_all_no_participants"])
            return
        afisha_path = "/app/images/afisha.jpeg"
        success_count = 0
        for participant in participants:
            user_id = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"
            try:
                if os.path.exists(afisha_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(afisha_path),
                        caption=messages["notify_all_message"].format(
                            fee=get_participation_fee_text(),
                            event_date=get_event_date_text(),
                            event_location=get_event_location_text()
                        ),
                        reply_markup=create_confirmation_keyboard(),
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=messages["notify_all_message"].format(
                            fee=get_participation_fee_text(),
                            event_date=get_event_date_text(),
                            event_location=get_event_location_text()
                        ),
                        reply_markup=create_confirmation_keyboard(),
                        parse_mode="HTML",
                    )
                logger.info(f"Уведомление отправлено пользователю user_id={user_id}")
                success_count += 1
            except TelegramForbiddenError:
                logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                cleanup_blocked_user(user_id)
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=name, username=username, user_id=user_id
                        ),
                    )
                    logger.info(
                        f"Уведомление администратору (admin_id={admin_id}) о блокировке отправлено"
                    )
                except Exception as admin_e:
                    logger.error(
                        f"Ошибка при отправке уведомления администратору: {admin_e}"
                    )
            except TelegramBadRequest as e:
                if "chat not found" in str(e).lower():
                    logger.warning(
                        f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                    )
                else:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                    )
        await message.answer(messages["notify_all_success"].format(count=success_count))
        logger.info(f"Уведомления отправлены {success_count} участникам")

    @dp.message(Command("notify_with_text"))
    @dp.callback_query(F.data == "admin_notify_with_text")
    async def notify_with_text(event: [Message, CallbackQuery], state: FSMContext):
        """Start notification with text/photo - first choose audience"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда /notify_with_text от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event
            
        from .utils import create_notify_audience_keyboard
        
        text = "✏️ <b>Уведомить с текстом/фото</b>\n\n"
        text += "📋 Выберите аудиторию для отправки:\n\n"
        text += "👥 <b>Участники</b> - зарегистрированные участники\n"
        text += "⏳ <b>Pending</b> - незавершенные регистрации\n"  
        text += "📋 <b>Очередь ожидания</b> - пользователи в waitlist\n"
        text += "📂 <b>Из архивов</b> - участники прошлых гонок\n"
        text += "🌍 <b>Все группы</b> - все вышеперечисленные\n"
        
        await message.answer(text, reply_markup=create_notify_audience_keyboard())
        await state.set_state(RegistrationForm.waiting_for_notify_audience_selection)

    @dp.callback_query(F.data.startswith("audience_"), RegistrationForm.waiting_for_notify_audience_selection)
    async def process_audience_selection(callback: CallbackQuery, state: FSMContext):
        """Process audience selection for notifications"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return
            
        audience_type = callback.data.replace("audience_", "")
        await callback.message.delete()
        
        # Get user lists based on selection
        user_lists = await get_users_by_audience(audience_type)
        total_users = sum(len(users) for users in user_lists.values())
        
        if total_users == 0:
            await callback.message.answer(
                f"❌ <b>Нет пользователей в выбранной категории</b>\n\n"
                f"Выбранная аудитория: {get_audience_name(audience_type)}"
            )
            await state.clear()
            await callback.answer()
            return
        
        # Store audience info in state
        await state.update_data(
            audience_type=audience_type,
            user_lists=user_lists,
            total_users=total_users
        )
        
        # Show stats and ask for message
        stats_text = f"✏️ <b>Уведомить с текстом/фото</b>\n\n"
        stats_text += f"🎯 <b>Аудитория:</b> {get_audience_name(audience_type)}\n\n"
        stats_text += f"📊 <b>Статистика получателей:</b>\n"
        
        for category, users in user_lists.items():
            if users:
                stats_text += f"• {get_category_name(category)}: {len(users)}\n"
        
        stats_text += f"• <b>Всего:</b> {total_users}\n\n"
        stats_text += "✏️ Введите текст сообщения:"
        
        await callback.message.answer(stats_text)
        await state.set_state(RegistrationForm.waiting_for_notify_advanced_message)
        await callback.answer()

    @dp.callback_query(F.data == "cancel_notify")
    async def cancel_notification(callback: CallbackQuery, state: FSMContext):
        """Cancel notification process"""
        await callback.message.delete()
        await callback.message.answer("❌ Отправка уведомлений отменена.")
        await state.clear()
        await callback.answer()

    @dp.message(RegistrationForm.waiting_for_notify_advanced_message)
    async def process_advanced_message_text(message: Message, state: FSMContext):
        """Process text for advanced notification"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return
            
        if not message.text:
            await message.answer("❌ Сообщение должно содержать текст. Попробуйте снова:")
            return
            
        notify_text = message.text.strip()
        if len(notify_text) > 4096:
            await message.answer("❌ Сообщение слишком длинное. Максимум 4096 символов. Попробуйте снова:")
            return
        
        # Save text to state
        await state.update_data(notify_text=notify_text)
        
        # Ask about photos
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📷 Да, добавить фото", callback_data="add_photos_yes"),
                    InlineKeyboardButton(text="📝 Нет, только текст", callback_data="add_photos_no"),
                ],
                [
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_notify"),
                ],
            ]
        )
        
        text = "✅ <b>Текст сохранен</b>\n\n"
        text += "📷 <b>Добавить фотографии к сообщению?</b>\n\n"
        text += "Вы можете добавить до 10 фотографий, которые будут отправлены вместе с текстом."
        
        await message.answer(text, reply_markup=keyboard)

    @dp.callback_query(F.data == "add_photos_yes")
    async def request_photos(callback: CallbackQuery, state: FSMContext):
        """Request photos for notification"""
        await callback.message.delete()
        
        # Initialize photos list
        await state.update_data(photos=[])
        
        text = "📷 <b>Загрузка фотографий</b>\n\n"
        text += "📤 Отправьте фотографии для уведомления (до 10 штук)\n\n"
        text += "📋 <b>Как загрузить:</b>\n"
        text += "• Отправляйте по одной фотографии\n"
        text += "• Можно отправить несколько подряд\n"
        text += "• Максимум 10 фотографий\n\n"
        text += "✅ После загрузки всех фото нажмите кнопку \"Готово\"\n"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Готово, отправить", callback_data="photos_done"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_notify"),
                ],
            ]
        )
        
        await callback.message.answer(text, reply_markup=keyboard)
        await state.set_state(RegistrationForm.waiting_for_notify_advanced_photo)
        await callback.answer()

    @dp.callback_query(F.data == "add_photos_no")
    async def send_text_only_notification(callback: CallbackQuery, state: FSMContext):
        """Send notification with text only"""
        await callback.answer()  # Отвечаем сразу, чтобы избежать timeout
        await callback.message.delete()
        await send_advanced_notification(callback.message, state, with_photos=False)

    @dp.message(RegistrationForm.waiting_for_notify_advanced_photo, F.photo)
    async def process_notification_photo(message: Message, state: FSMContext):
        """Process uploaded photos for notification"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return
            
        data = await state.get_data()
        photos = data.get('photos', [])
        
        if len(photos) >= 10:
            await message.answer("❌ Максимум 10 фотографий. Нажмите \"Готово\" для отправки.")
            return
        
        # Get the largest photo size
        photo = message.photo[-1]
        photos.append({
            'file_id': photo.file_id,
            'file_unique_id': photo.file_unique_id
        })
        
        await state.update_data(photos=photos)
        
        # Just silently accept the photo without any status messages
        # The user will see their uploaded photos and the original instruction message remains
        
        if len(photos) >= 10:
            # Only when 10 photos reached, show status message
            await message.answer(f"✅ Фото {len(photos)}/10 загружено")
            
            # Then show completion message with buttons  
            text = "📷 Загружено максимальное количество фото. Нажмите \"Готово\" для отправки."
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Готово, отправить", callback_data="photos_done"),
                        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_notify"),
                    ],
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)

    @dp.message(RegistrationForm.waiting_for_notify_advanced_photo)
    async def handle_non_photo_in_photo_mode(message: Message, state: FSMContext):
        """Handle non-photo messages in photo upload mode"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return
            
        await message.answer(
            "📷 Ожидается загрузка фотографий.\n\n"
            "• Отправьте фотографию для добавления к уведомлению\n"
            "• Или нажмите \"Готово\" для отправки уже загруженных фото\n"
            "• Или \"Отмена\" для прекращения процесса"
        )

    @dp.callback_query(F.data == "photos_done")
    async def send_photos_notification(callback: CallbackQuery, state: FSMContext):
        """Send notification with photos"""
        await callback.answer()  # Отвечаем сразу, чтобы избежать timeout
        await callback.message.delete()
        
        data = await state.get_data()
        photos = data.get('photos', [])
        
        if not photos:
            await callback.message.answer("❌ Не загружено ни одного фото. Отменяю отправку.")
            await state.clear()
            return
            
        await send_advanced_notification(callback.message, state, with_photos=True)

    async def send_advanced_notification(message: Message, state: FSMContext, with_photos=False):
        """Send advanced notification to selected audience"""
        data = await state.get_data()
        notify_text = data.get('notify_text', '')
        user_lists = data.get('user_lists', {})
        audience_type = data.get('audience_type', '')
        photos = data.get('photos', []) if with_photos else []
        
        if with_photos:
            status_text = f"📤 <b>Отправка уведомлений с фото...</b>\n\n"
            status_text += f"📷 Фотографий: {len(photos)}\n"
        else:
            status_text = f"📤 <b>Отправка текстовых уведомлений...</b>\n\n"
            
        status_text += f"🎯 Аудитория: {get_audience_name(audience_type)}\n"
        status_text += f"👥 Получателей: {sum(len(users) for users in user_lists.values())}\n\n"
        status_text += "Отправляю сообщения..."
        
        await message.answer(status_text)
        
        success_count = 0
        blocked_count = 0
        total_sent = 0
        
        # Send to all user categories
        for category, users in user_lists.items():
            if not users:
                continue
                
            for user_id, username, name in users:
                try:
                    if with_photos and photos:
                        # Prepare media group
                        from aiogram.types import InputMediaPhoto
                        media = []
                        
                        # First photo with caption
                        media.append(InputMediaPhoto(
                            media=photos[0]['file_id'],
                            caption=notify_text,
                            parse_mode="HTML"
                        ))
                        
                        # Other photos without caption
                        for photo in photos[1:]:
                            media.append(InputMediaPhoto(media=photo['file_id']))
                        
                        await bot.send_media_group(chat_id=user_id, media=media)
                    else:
                        # Send text only
                        await bot.send_message(
                            chat_id=user_id,
                            text=notify_text,
                            parse_mode="HTML"
                        )
                    
                    success_count += 1
                    logger.info(f"Расширенное уведомление отправлено пользователю {name or 'Unknown'} (ID: {user_id}) из категории {category}")
                    
                except Exception as e:
                    logger.warning(f"Ошибка отправки пользователю {name or 'Unknown'} (ID: {user_id}): {e}")
                    blocked_count += 1
                
                total_sent += 1
        
        # Send final statistics
        result_text = f"✅ <b>Рассылка завершена</b>\n\n"
        result_text += f"📊 <b>Статистика:</b>\n"
        
        for category, users in user_lists.items():
            if users:
                result_text += f"• {get_category_name(category)}: {len(users)}\n"
        
        result_text += f"\n📈 <b>Результат отправки:</b>\n"
        result_text += f"• ✅ Успешно: {success_count}\n"
        result_text += f"• ❌ Не доставлено: {blocked_count}\n"
        result_text += f"• 📊 Всего: {total_sent}\n"
        
        if with_photos:
            result_text += f"• 📷 Фотографий: {len(photos)}\n"
        
        await message.answer(result_text)
        await state.clear()
        logger.info(f"Расширенная рассылка завершена: {success_count}/{total_sent} успешно, фото: {len(photos) if with_photos else 0}")



    @dp.message(Command("notify_unpaid"))
    @dp.callback_query(F.data == "admin_notify_unpaid")
    async def notify_unpaid_participants(
        event: [Message, CallbackQuery], state: FSMContext
    ):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_unpaid_access_denied"])
            return
        logger.info(f"Команда /notify_unpaid от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number "
                    "FROM participants WHERE payment_status = 'pending' AND role = 'runner'"
                )
                unpaid_participants = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка неоплативших участников: {e}")
            await message.answer(
                "Ошибка при получении списка участников. Попробуйте снова."
            )
            return
        if not unpaid_participants:
            logger.info("Нет участников с неоплаченным статусом")
            await message.answer(messages["notify_unpaid_no_participants"])
            return
        await message.answer(messages["notify_unpaid_prompt"])
        await state.set_state(RegistrationForm.waiting_for_notify_unpaid_message)

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_unpaid_message))
    async def process_notify_unpaid_message(message: Message, state: FSMContext):
        logger.info(
            f"Получен текст рассылки для /notify_unpaid от user_id={message.from_user.id}"
        )
        notify_text = message.text.strip()
        if len(notify_text) > 4096:
            logger.warning(
                f"Текст рассылки слишком длинный: {len(notify_text)} символов"
            )
            await message.answer("Текст слишком длинный. Максимум 4096 символов.")
            await state.clear()
            return
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number "
                    "FROM participants WHERE payment_status = 'pending' AND role = 'runner'"
                )
                unpaid_participants = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка неоплативших участников: {e}")
            await message.answer("Ошибка при отправке уведомлений. Попробуйте снова.")
            await state.clear()
            return
        success_count = 0
        afisha_path = "/app/images/afisha.jpeg"
        for participant in unpaid_participants:
            user_id = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"
            try:
                if os.path.exists(afisha_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(afisha_path),
                        caption=notify_text,
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id, text=notify_text, parse_mode="HTML"
                    )
                logger.info(
                    f"Уведомление отправлено неоплатившему пользователю user_id={user_id}"
                )
                success_count += 1
            except TelegramForbiddenError:
                logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                cleanup_blocked_user(user_id)
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=name, username=username, user_id=user_id
                        ),
                    )
                    logger.info(
                        f"Уведомление администратору (admin_id={admin_id}) о блокировке отправлено"
                    )
                except Exception as admin_e:
                    logger.error(
                        f"Ошибка при отправке уведомления администратору: {admin_e}"
                    )
            except TelegramBadRequest as e:
                if "chat not found" in str(e).lower():
                    logger.warning(
                        f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                    )
                else:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                    )
        await message.answer(
            messages["notify_unpaid_success"].format(count=success_count)
        )
        logger.info(f"Уведомления отправлены {success_count} неоплатившим участникам")
        await state.clear()

    @dp.message(Command("notify_results"))
    @dp.callback_query(F.data == "admin_notify_results")
    async def notify_results(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_results_access_denied"])
            return
        logger.info(f"Команда /notify_results от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["notify_results_prompt"])
        await state.set_state(RegistrationForm.waiting_for_result)
        if isinstance(event, CallbackQuery):
            await event.answer()

    @dp.message(StateFilter(RegistrationForm.waiting_for_result))
    async def process_result_input(message: Message, state: FSMContext):
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer(messages["notify_results_usage"])
            return
        try:
            user_id = int(parts[0])
            result_input = parts[1].lower()
            participant = get_participant_by_user_id(user_id)
            if not participant or participant[4] != "runner":
                await message.answer(messages["notify_results_user_not_found"])
                return
            name = participant[2]
            username = participant[1] or "не указан"
            bib_number = participant[7] if participant[7] is not None else "не присвоен"
            # Validate result format
            if result_input == "dnf":
                result = "DNF"
            elif re.match(r"^\d+:[0-5]\d$", result_input):
                minutes, seconds = map(int, result_input.split(":"))
                result = f"0:{minutes:02d}:{seconds:02d}"
            else:
                await message.answer(messages["notify_results_invalid_format"])
                return
            success = set_result(user_id, result)
            if not success:
                await message.answer(
                    f"Ошибка записи результата для {name} (ID: <code>{user_id}</code>)."
                )
                return
            try:
                await bot.send_message(
                    user_id,
                    messages["result_notification"].format(
                        name=name, bib_number=bib_number, result=result
                    ),
                )
                logger.info(f"Результат отправлен user_id={user_id}: {result}")
                await message.answer(
                    messages["notify_results_success_single"].format(
                        name=name, user_id=user_id, username=username, result=result
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка отправки результата user_id={user_id}: {e}")
                await message.answer(
                    f"🚫 Не удалось отправить результат пользователю {name} (ID: <code>{user_id}</code>, @{username})"
                )
        except ValueError:
            await message.answer(messages["notify_results_usage"])

    async def notify_all_interacted(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_all_interacted_access_denied"])
            return
        logger.info(f"Команда /notify_all_interacted от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["notify_all_interacted_prompt"])
        await state.set_state(
            RegistrationForm.waiting_for_notify_all_interacted_message
        )
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def process_notify_all_interacted_message(
        message: Message, state: FSMContext
    ):
        notify_text = message.text.strip()
        await state.update_data(notify_text=notify_text, photos=[])
        await message.answer(messages["notify_all_interacted_photo_prompt"])
        await state.set_state(RegistrationForm.waiting_for_notify_all_interacted_photo)

    async def process_notify_all_interacted_photo(message: Message, state: FSMContext):
        user_data = await state.get_data()
        photos = user_data.get("photos", [])
        if len(photos) >= 10:
            await message.answer(messages["notify_all_interacted_photo_limit"])
            return
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = file.file_path
        temp_photo_path = (
            f"/app/images/temp_notify_all_interacted_photo_{len(photos)}.jpeg"
        )
        await bot.download_file(file_path, temp_photo_path)
        photos.append(temp_photo_path)
        await state.update_data(photos=photos)
        await message.answer(
            messages["notify_all_interacted_photo_added"].format(count=len(photos))
        )
        if len(photos) < 10:
            await message.answer(messages["notify_all_interacted_photo_prompt"])
        else:
            await send_all_interacted_notifications(message, state)

    async def process_notify_all_interacted_skip_photo(
        message: Message, state: FSMContext
    ):
        await send_all_interacted_notifications(message, state)

    async def send_all_interacted_notifications(message: Message, state: FSMContext):
        user_data = await state.get_data()
        notify_text = user_data.get("notify_text")
        photos = user_data.get("photos", [])
        conn = sqlite3.connect("/app/data/race_participants.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, name FROM participants")
        participants = cursor.fetchall()
        cursor.execute("SELECT user_id, username, name FROM pending_registrations")
        pending = cursor.fetchall()
        conn.close()
        all_users = list(
            set(
                [(p[0], p[1], p[2]) for p in participants]
                + [(p[0], p[1], p[2]) for p in pending]
            )
        )
        if not all_users:
            await message.answer(messages["notify_all_interacted_no_users"])
            await state.clear()
            return
        success_count = 0
        for user_id, username, name in all_users:
            username = username or "не указан"
            name = name or "неизвестно"
            try:
                if photos:
                    media = [
                        InputMediaPhoto(
                            media=FSInputFile(photos[0]), caption=notify_text
                        )
                    ]
                    for photo_path in photos[1:]:
                        media.append(InputMediaPhoto(media=FSInputFile(photo_path)))
                    await bot.send_media_group(chat_id=user_id, media=media)
                else:
                    await bot.send_message(chat_id=user_id, text=notify_text)
                success_count += 1
                logger.info(f"Уведомление отправлено user_id={user_id}")
            except Exception as e:
                if "blocked" in str(e).lower():
                    delete_participant(user_id)
                    delete_pending_registration(user_id)
                    await message.answer(
                        messages["admin_blocked_notification"].format(
                            name=name, username=username, user_id=user_id
                        )
                    )
                    logger.info(
                        f"Пользователь user_id={user_id} удалён из баз данных, так как заблокировал бота"
                    )
                else:
                    logger.error(f"Ошибка отправки уведомления user_id={user_id}: {e}")
                    await message.answer(
                        f"🚫 Не удалось отправить уведомление пользователю {name} (ID: <code>{user_id}</code>, @{username})"
                    )
        for photo_path in photos:
            if os.path.exists(photo_path):
                os.remove(photo_path)
        await message.answer(
            messages["notify_all_interacted_success"].format(count=success_count)
        )
        await state.clear()

    async def process_notify_all_interacted_invalid(
        message: Message, state: FSMContext
    ):
        await message.answer(messages["notify_all_interacted_photo_prompt"])

    @dp.message(Command("notify_all_interacted"))
    async def cmd_notify_all_interacted(message: Message, state: FSMContext):
        await notify_all_interacted(message, state)

    @dp.callback_query(F.data == "admin_notify_all_interacted")
    async def callback_notify_all_interacted(
        callback_query: CallbackQuery, state: FSMContext
    ):
        await notify_all_interacted(callback_query, state)

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_all_interacted_message))
    async def process_notify_all_interacted_message_handler(
        message: Message, state: FSMContext
    ):
        await process_notify_all_interacted_message(message, state)

    @dp.message(
        StateFilter(RegistrationForm.waiting_for_notify_all_interacted_photo), F.photo
    )
    async def process_notify_all_interacted_photo_handler(
        message: Message, state: FSMContext
    ):
        await process_notify_all_interacted_photo(message, state)

    @dp.message(
        StateFilter(RegistrationForm.waiting_for_notify_all_interacted_photo),
        Command("skip"),
    )
    async def process_notify_all_interacted_skip_photo_handler(
        message: Message, state: FSMContext
    ):
        await process_notify_all_interacted_skip_photo(message, state)

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_all_interacted_photo))
    async def process_notify_all_interacted_invalid_handler(
        message: Message, state: FSMContext
    ):
        await process_notify_all_interacted_invalid(message, state)

    # Request participation confirmation handler
    @dp.callback_query(F.data == "admin_request_confirmation")
    async def request_participation_confirmation(callback: CallbackQuery):
        """Send participation confirmation request to unpaid participants"""
        user_id = callback.from_user.id
        if user_id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return
        
        logger.info(f"Запрос подтверждения участия от admin_id={user_id}")
        
        await callback.message.delete()
        await callback.answer()
        
        # Get unpaid participants
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, name FROM participants "
                    "WHERE payment_status = 'pending' AND role = 'runner'"
                )
                unpaid_participants = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка неоплативших участников: {e}")
            await callback.message.answer(
                "❌ Ошибка при получении списка участников. Попробуйте снова."
            )
            return
        
        if not unpaid_participants:
            logger.info("Нет неоплативших участников для запроса подтверждения")
            await callback.message.answer(
                "ℹ️ Нет неоплативших участников для запроса подтверждения."
            )
            return
        
        # Send confirmation requests
        success_count = 0
        failed_count = 0
        
        status_msg = await callback.message.answer(
            f"📤 Отправка запросов подтверждения...\n"
            f"👥 Получателей: {len(unpaid_participants)}"
        )
        
        from .utils import create_participation_confirmation_keyboard
        
        for user_id_p, username, name in unpaid_participants:
            try:
                confirmation_text = (
                    f"✅ <b>Подтверждение участия</b>\n\n"
                    f"Здравствуйте, <b>{name}</b>!\n\n"
                    f"Мы хотим уточнить ваше участие в мероприятии.\n"
                    f"Пожалуйста, подтвердите, планируете ли вы принять участие?\n\n"
                    f"💡 Если вы не уверены или изменились ваши планы, сообщите нам."
                )
                
                keyboard = create_participation_confirmation_keyboard(user_id_p)
                
                await bot.send_message(
                    chat_id=user_id_p,
                    text=confirmation_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                
                success_count += 1
                logger.info(f"Запрос подтверждения отправлен участнику {name} (ID: {user_id_p})")
                
            except TelegramForbiddenError:
                logger.warning(f"Пользователь {name} (ID: {user_id_p}) заблокировал бот")
                failed_count += 1
                cleanup_blocked_user(user_id_p)
            except Exception as e:
                logger.error(f"Ошибка отправки запроса участнику {name} (ID: {user_id_p}): {e}")
                failed_count += 1
        
        # Send result summary
        result_text = (
            f"✅ <b>Запросы подтверждения отправлены</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Успешно: {success_count}\n"
            f"• Не доставлено: {failed_count}\n"
            f"• Всего: {len(unpaid_participants)}\n\n"
            f"💡 Участники получат уведомление с кнопками \"Да\" и \"Нет\".\n"
            f"Вы получите уведомление об их ответах."
        )
        
        await callback.message.answer(result_text, parse_mode="HTML")
        logger.info(f"Запросы подтверждения отправлены: {success_count}/{len(unpaid_participants)}")
    
    # Handle YES confirmation
    @dp.callback_query(F.data.startswith("confirm_participation_yes_"))
    async def handle_confirmation_yes(callback: CallbackQuery):
        """Handle YES confirmation from participant"""
        try:
            user_id = int(callback.data.replace("confirm_participation_yes_", ""))
        except ValueError:
            await callback.answer("❌ Ошибка обработки")
            return
        
        # Get participant info
        participant = get_participant_by_user_id(user_id)
        if not participant:
            await callback.answer("❌ Участник не найден")
            return
        
        name = participant[2]
        username = participant[1] or "не указан"
        
        # Update message for user
        await callback.message.edit_text(
            f"✅ <b>Спасибо за подтверждение!</b>\n\n"
            f"Мы ждем вас на мероприятии, <b>{name}</b>!\n\n"
            f"💡 Не забудьте произвести оплату участия {get_participation_fee_text()}",
            parse_mode="HTML"
        )
        
        # Notify admin
        admin_text = (
            f"✅ <b>Подтверждение участия получено</b>\n\n"
            f"👤 <b>Участник:</b> {name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>Username:</b> @{username}\n\n"
            f"Участник подтвердил свое участие в мероприятии."
        )
        
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            logger.info(f"Участник {name} (ID: {user_id}) подтвердил участие")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
        
        await callback.answer("✅ Подтверждение отправлено")
    
    # Handle NO confirmation
    @dp.callback_query(F.data.startswith("confirm_participation_no_"))
    async def handle_confirmation_no(callback: CallbackQuery):
        """Handle NO confirmation from participant - remove from participants, add to pending"""
        try:
            user_id = int(callback.data.replace("confirm_participation_no_", ""))
        except ValueError:
            await callback.answer("❌ Ошибка обработки")
            return
        
        # Get participant info before deletion
        participant = get_participant_by_user_id(user_id)
        if not participant:
            await callback.answer("❌ Участник не найден")
            return
        
        username = participant[1] or "не указан"
        name = participant[2]
        target_time = participant[3]
        role = participant[4]
        
        # Delete from participants
        success_delete = delete_participant(user_id)
        
        if not success_delete:
            await callback.answer("❌ Ошибка при обработке отказа")
            logger.error(f"Не удалось удалить участника {name} (ID: {user_id})")
            return
        
        # Add to pending registrations
        from database import add_pending_registration
        success_pending = add_pending_registration(
            user_id=user_id,
            username=username,
            name=name,
            target_time=target_time,
            role=role
        )
        
        if not success_pending:
            logger.warning(f"Не удалось добавить {name} (ID: {user_id}) в pending после отказа")
        
        # Update message for user
        await callback.message.edit_text(
            f"📝 <b>Спасибо за ответ</b>\n\n"
            f"Жаль, что вы не сможете принять участие, <b>{name}</b>.\n\n"
            f"💡 Если ваши планы изменятся, вы всегда можете зарегистрироваться снова командой /start",
            parse_mode="HTML"
        )
        
        # Notify admin
        admin_text = (
            f"❌ <b>Отказ от участия</b>\n\n"
            f"👤 <b>Участник:</b> {name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>Username:</b> @{username}\n\n"
            f"⚠️ Участник отказался от участия.\n"
            f"✅ Удален из списка участников\n"
            f"📝 Добавлен в незавершенные регистрации"
        )
        
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
            logger.info(f"Участник {name} (ID: {user_id}) отказался от участия и удален")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")
        
        await callback.answer("✅ Отказ обработан")

    logger.info("Обработчики уведомлений зарегистрированы")
