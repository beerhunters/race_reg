"""
Упрощённая логика регистрации:
1. /start -> добавление в pending_registrations
2. Ввод имени
3. Выбор роли (только бегун)
4. Ввод целевого времени
5. Выбор пола
6. Проверка слотов: либо участники, либо очередь ожидания
7. Уведомление об успешной регистрации
"""

import os
from datetime import datetime
from pytz import timezone
from aiogram import Dispatcher, Bot, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from .utils import (
    logger,
    messages,
    config,
    RegistrationForm,
    create_gender_keyboard,
    create_main_menu_keyboard,
    get_participation_fee_text,
    log,
)
from .validation import validate_name, validate_time_format, sanitize_input
from database import (
    get_participant_by_user_id,
    add_pending_registration,
    add_participant,
    get_participant_count_by_role,
    get_setting,
    delete_pending_registration,
    add_to_waitlist,
    is_user_in_waitlist,
    is_current_event_active,
)


def create_runner_only_keyboard():
    """Создаем клавиатуру только с опцией бегуна"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏃 Бегун", callback_data="role_runner"
                )
            ],
        ]
    )
    return keyboard


def create_start_registration_keyboard():
    """Создаем клавиатуру для начала регистрации"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏃 Зарегистрироваться как бегун", callback_data="start_registration"
                )
            ]
        ]
    )
    return keyboard


async def handle_start_command(message: Message, state: FSMContext, bot: Bot, admin_id: int):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    log.command_received("/start", user_id, message.from_user.username)
    
    # Проверка, является ли пользователь администратором
    if user_id == admin_id:
        log.admin_action("start_command_accessed", user_id)
        try:
            from .utils import create_admin_commands_keyboard
            await message.answer(
                messages["admin_commands"],
                reply_markup=create_admin_commands_keyboard(),
            )
        except Exception as e:
            log.notification_sent("admin_commands", user_id, False, str(e))
            await message.answer("🔧 Админ-панель")
        await state.clear()
        return
    
    # Проверка даты окончания регистрации
    reg_end_date = get_setting("reg_end_date")
    if reg_end_date:
        try:
            end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
            moscow_tz = timezone("Europe/Moscow")
            end_date = moscow_tz.localize(end_date)
            current_time = datetime.now(moscow_tz)
            if current_time > end_date:
                afisha_path = "/app/images/afisha.jpeg"
                try:
                    if os.path.exists(afisha_path):
                        await bot.send_photo(
                            chat_id=message.from_user.id,
                            photo=FSInputFile(afisha_path),
                            caption=messages["registration_closed"],
                            parse_mode="HTML"
                        )
                        logger.info(f"Сообщение о закрытой регистрации с афишей отправлено user_id={message.from_user.id}")
                    else:
                        await message.answer(messages["registration_closed"])
                        logger.info(f"Сообщение о закрытой регистрации (без афиши) отправлено user_id={message.from_user.id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения о закрытой регистрации: {e}")
                    await message.answer(messages["registration_closed"])
                return
        except ValueError:
            logger.error(f"Некорректный формат reg_end_date: {reg_end_date}")
    
    # Проверка исторических участников
    from .archive_handlers import handle_historical_participant
    
    # Если нет активного события, показываем только историю
    if not is_current_event_active():
        historical_handled = await handle_historical_participant(user_id, message)
        if historical_handled:
            return
    else:
        # Если есть активное событие, но пользователь не текущий участник,
        # проверяем его историю для персональных сообщений
        participant = get_participant_by_user_id(user_id)
        if not participant and not is_user_in_waitlist(user_id):
            historical_handled = await handle_historical_participant(user_id, message)
            if historical_handled:
                return
    
    # Проверка существующей регистрации
    participant = get_participant_by_user_id(user_id)
    if participant:
        # Пользователь уже зарегистрирован
        name = participant[2]
        target_time = participant[3] or "не указано"
        role = "бегун" if participant[4] == "runner" else "волонтёр"
        bib_number = f"№ {participant[7]}" if participant[7] else "не присвоен"
        payment_status = participant[6]
        gender = "мужской" if participant[9] == "male" else "женский" if participant[9] == "female" else "не указан"
        # Категория с эмодзи
        if participant[10]:
            category_emoji = {
                "Элита": "🥇",
                "Классика": "🏃", 
                "Женский": "👩",
                "Команда": "👥"
            }.get(participant[10], "📂")
            category = f"{category_emoji} {participant[10]}"
        else:
            category = "📂 не назначена"
        
        # Кластер с эмодзи
        if participant[11]:
            cluster_emoji = {
                "A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴"
            }.get(participant[11], "🎯")
            cluster = f"{cluster_emoji} {participant[11]}"
        else:
            cluster = "🎯 не назначен"
        
        # Определяем статус оплаты
        payment_emoji = "✅" if payment_status == "paid" else "⏳"
        payment_text = "оплачено" if payment_status == "paid" else "ожидает подтверждения"
        
        # Создаем информативное сообщение
        participant_info = (
            f"✅ <b>Вы уже зарегистрированы!</b>\n\n"
            f"📝 <b>Ваши данные:</b>\n"
            f"• Имя: {name}\n"
            f"• Целевое время: {target_time}\n"
            f"• Пол: {gender}\n"
            f"• Беговой номер: {bib_number}\n"
            f"• Категория: {category}\n"
            f"• Кластер: {cluster}\n\n"
            f"💰 <b>Статус оплаты:</b> {payment_emoji} {payment_text}\n\n"
        )
        
        if payment_status != "paid":
            participant_info += f"💡 Не забудьте произвести оплату участия {get_participation_fee_text()}!"
        else:
            participant_info += "🎉 Все готово к старту! Увидимся на мероприятии!"
            
        await message.answer(participant_info)
        return
    
    # Проверка нахождения в очереди ожидания
    if is_user_in_waitlist(user_id):
        # Проверяем статус в очереди - если пользователь уже подтвердил участие,
        # то не даем повторно регистрироваться
        from database import get_waitlist_by_user_id
        waitlist_entry = get_waitlist_by_user_id(user_id)
        
        if waitlist_entry and waitlist_entry[9] == 'confirmed':  # status at index 9
            await message.answer(
                "✅ Вы уже подтвердили участие из очереди ожидания!\n\n"
                "⏳ Ожидайте обработки администратором."
            )
            return
        elif waitlist_entry and waitlist_entry[9] in ['waiting', 'notified', 'declined']:
            # Проверяем, есть ли свободные слоты
            max_runners = get_setting("max_runners")
            current_runners = get_participant_count_by_role("runner")
            
            # Ensure we have valid integers for calculation
            try:
                max_runners = int(max_runners) if max_runners is not None else 0
                current_runners = int(current_runners) if current_runners is not None else 0
            except (ValueError, TypeError):
                max_runners = 0
                current_runners = 0
            
            available_slots = max_runners - current_runners if max_runners > 0 else 0
            
            if available_slots > 0:
                # Есть свободные места - предлагаем принять участие
                from .waitlist_handlers import create_participation_confirmation_keyboard
                await message.answer(
                    f"🎉 <b>Отличные новости!</b>\n\n"
                    f"Для вас освободилось место!\n\n"
                    f"📊 Доступно мест: {available_slots} из {max_runners}\n"
                    f"⏰ <b>Хотите принять участие?</b>",
                    reply_markup=create_participation_confirmation_keyboard()
                )
            else:
                # Мест нет - сообщаем о статусе
                await message.answer(
                    "📋 Вы находитесь в очереди ожидания!\n\n"
                    f"📊 Занято мест: {current_runners} из {max_runners}\n"
                    f"⏳ Ожидайте освобождения места.\n\n"
                    f"💡 Используйте /waitlist_status для проверки позиции."
                )
            return
    
    # Добавляем в pending_registrations
    username = message.from_user.username or "не указан"
    success = add_pending_registration(user_id, username)
    
    if not success:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        return
    
    # Отправляем стартовое сообщение с афишей если есть
    try:
        start_message = messages["start_message"].format(fee=get_participation_fee_text())
        
        afisha_path = "/app/images/afisha.jpeg"
        if os.path.exists(afisha_path):
            await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile(path=afisha_path),
                caption=start_message,
                reply_markup=create_start_registration_keyboard(),
            )
        else:
            await message.answer(
                start_message,
                reply_markup=create_start_registration_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке стартового сообщения: {e}")
        await message.answer(
            messages["start_message"].format(fee=get_participation_fee_text()),
            reply_markup=create_start_registration_keyboard()
        )


async def handle_start_registration(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала процесса регистрации"""
    await callback.message.edit_text("📝 Введите ваше полное имя:")
    await state.set_state(RegistrationForm.waiting_for_name)
    await callback.answer()


async def handle_name_input(message: Message, state: FSMContext):
    """Обработчик ввода имени"""
    name = sanitize_input(message.text, 50)
    
    is_valid, error_message = validate_name(name)
    if not is_valid:
        await message.answer(f"❌ {error_message}", reply_markup=create_main_menu_keyboard())
        return
    
    await state.update_data(name=name, role="runner")
    await message.answer(
        "⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
    )
    await state.set_state(RegistrationForm.waiting_for_target_time)




async def handle_time_input(message: Message, state: FSMContext):
    """Обработчик ввода целевого времени"""
    target_time = sanitize_input(message.text, 10)
    
    is_valid, error_message = validate_time_format(target_time)
    if not is_valid:
        await message.answer(f"❌ {error_message}", reply_markup=create_main_menu_keyboard())
        return
    
    await state.update_data(target_time=target_time)
    await message.answer(
        "👤 Укажите ваш пол:",
        reply_markup=create_gender_keyboard()
    )
    await state.set_state(RegistrationForm.waiting_for_gender)


async def handle_gender_selection(callback: CallbackQuery, state: FSMContext, bot: Bot, admin_id: int):
    """Обработчик выбора пола и завершение регистрации"""
    if callback.data not in ["male", "female"]:
        await callback.message.edit_text("❌ Неверный выбор пола.")
        await callback.answer()
        await state.clear()
        return
    
    user_id = callback.from_user.id
    user_data = await state.get_data()
    username = callback.from_user.username or "не указан"
    name = user_data.get("name")
    target_time = user_data.get("target_time")
    role = "runner"
    gender = callback.data
    
    # Проверяем доступные слоты
    max_runners = get_setting("max_runners")
    if max_runners is None:
        await callback.message.edit_text(
            "❌ Ошибка конфигурации. Свяжитесь с администратором."
        )
        await callback.answer()
        await state.clear()
        return
    
    current_runners = get_participant_count_by_role("runner")
    
    # Ensure we have valid integers for comparison
    try:
        max_runners = int(max_runners)
        current_runners = int(current_runners) if current_runners is not None else 0
    except (ValueError, TypeError):
        await callback.message.edit_text(
            "❌ Ошибка конфигурации. Свяжитесь с администратором."
        )
        await callback.answer()
        await state.clear()
        return
    
    if current_runners >= max_runners:
        # Добавляем в очередь ожидания
        success = add_to_waitlist(user_id, username, name, target_time, role, gender)
        
        if success:
            # НЕ удаляем из pending - пользователь остается в pending и waitlist одновременно
            # delete_pending_registration(user_id)  # Убрано согласно новой логике
            
            await callback.message.edit_text(
                f"📋 <b>Все слоты для бегунов заняты!</b>\n\n"
                f"✅ Вы добавлены в очередь ожидания.\n"
                f"📱 Уведомим вас, когда освободится место!\n\n"
                f"💡 Используйте /waitlist_status для проверки позиции в очереди."
            )
            
            # Уведомляем админа
            try:
                from database import get_waitlist_by_role
                waitlist_count = len(get_waitlist_by_role("runner"))
                
                admin_text = (
                    f"📋 <b>Новый пользователь в очереди ожидания</b>\n\n"
                    f"👤 <b>Пользователь:</b> {name} (@{username})\n"
                    f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                    f"⏰ <b>Целевое время:</b> {target_time}\n"
                    f"👤 <b>Пол:</b> {'мужской' if gender == 'male' else 'женский'}\n"
                    f"📊 <b>Всего в очереди:</b> {waitlist_count}\n"
                    f"💼 <b>Текущий лимит:</b> {max_runners}\n"
                )
                
                await bot.send_message(admin_id, admin_text)
                
            except Exception as e:
                logger.error(f"Ошибка при уведомлении администратора о записи в очередь: {e}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка при добавлении в очередь ожидания. Попробуйте позже."
            )
    else:
        # Есть свободные слоты - регистрируем пользователя
        success = add_participant(user_id, username, name, target_time, role, gender)
        
        if success:
            # Удаляем из pending_registrations
            delete_pending_registration(user_id)
            
            # Уведомление пользователю об успешной регистрации
            gender_display = "мужской" if gender == "male" else "женский"
            success_message = (
                f"✅ <b>Регистрация завершена!</b>\n\n"
                f"📝 <b>Ваши данные:</b>\n"
                f"• Имя: {name}\n"
                f"• Целевое время: {target_time}\n"
                f"• Пол: {gender_display}\n"
                f"• Роль: бегун\n\n"
                f"💰 <b>Важно:</b> Не забудьте произвести оплату участия {get_participation_fee_text()}!\n"
                f"📱 Свяжитесь с администратором для подтверждения оплаты."
            )
            
            await callback.message.edit_text(success_message)
            
            # Отправляем изображение спонсоров если есть
            try:
                sponsor_image_path = config.get(
                    "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                )
                if os.path.exists(sponsor_image_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(path=sponsor_image_path),
                        caption="🤝 Наши спонсоры"
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения спонсоров: {e}")
            
            # Уведомляем администратора
            try:
                admin_message = (
                    f"🆕 <b>Новая регистрация!</b>\n\n"
                    f"👤 <b>Участник:</b> {name}\n"
                    f"⏰ <b>Целевое время:</b> {target_time}\n"
                    f"👤 <b>Пол:</b> {gender_display}\n"
                    f"🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n"
                    f"📱 <b>Username:</b> @{username}\n\n"
                    f"🎭 <b>Роль:</b> бегун\n"
                    f"💰 <b>Статус оплаты:</b> ожидает подтверждения\n"
                    f"📊 <b>Всего бегунов:</b> {current_runners + 1}/{max_runners}"
                )
                
                await bot.send_message(admin_id, admin_message)
                
            except Exception as e:
                logger.error(f"Ошибка при уведомлении администратора о регистрации: {e}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка при регистрации. Попробуйте позже."
            )
    
    await callback.answer()
    await state.clear()


def register_simple_registration_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Регистрация упрощённых обработчиков регистрации"""
    
    # Команда /start
    async def start_wrapper(message: Message, state: FSMContext):
        await handle_start_command(message, state, bot, admin_id)
    
    dp.message.register(
        start_wrapper,
        CommandStart()
    )
    
    # Начало регистрации
    dp.callback_query.register(
        handle_start_registration,
        F.data == "start_registration"
    )
    
    # Ввод имени
    dp.message.register(
        handle_name_input,
        StateFilter(RegistrationForm.waiting_for_name)
    )
    
    
    # Ввод времени
    dp.message.register(
        handle_time_input,
        StateFilter(RegistrationForm.waiting_for_target_time)
    )
    
    # Выбор пола и завершение регистрации
    async def gender_wrapper(callback: CallbackQuery, state: FSMContext):
        await handle_gender_selection(callback, state, bot, admin_id)
    
    dp.callback_query.register(
        gender_wrapper,
        StateFilter(RegistrationForm.waiting_for_gender)
    )
    
    # Главное меню для пользователей
    async def handle_user_main_menu(callback: CallbackQuery, state: FSMContext):
        """Handle main menu button for regular users - same as /start"""
        # If it's admin, redirect to admin panel
        if callback.from_user.id == admin_id:
            from .utils import create_admin_commands_keyboard
            await callback.message.edit_text(
                "🔧 <b>Админ-панель</b>\n\nВыберите категорию:",
                reply_markup=create_admin_commands_keyboard(),
            )
            await callback.answer()
            return
            
        await state.clear()
        await handle_start_command(callback.message, state, bot, admin_id)
        await callback.answer()
    
    dp.callback_query.register(
        handle_user_main_menu,
        F.data == "main_menu"
    )
    
    logger.info("Упрощённые обработчики регистрации зарегистрированы")