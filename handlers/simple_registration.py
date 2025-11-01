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

from logging_config import get_logger, log
from .utils import (
    create_main_menu_keyboard,
    messages,
    RegistrationForm,
    config,
    create_gender_keyboard,
    get_participation_fee_text,
    get_event_date_text,
    get_event_location_text,
    get_event_time_text,
)

logger = get_logger(__name__)
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
    get_waitlist_position,
    get_waitlist_by_user_id,
    count_complete_teams,
)


def create_runner_only_keyboard():
    """Создаем клавиатуру только с опцией бегуна"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏃 Бегун", callback_data="role_runner")],
        ]
    )
    return keyboard


def create_start_registration_keyboard():
    """Создаем клавиатуру для начала регистрации"""
    # Check if team mode is enabled
    team_mode_enabled = get_setting("team_mode_enabled")
    team_mode_enabled = int(team_mode_enabled) if team_mode_enabled is not None else 1

    buttons = [
        [
            InlineKeyboardButton(
                text="🏃 Зарегистрироваться как бегун",
                callback_data="start_registration",
            )
        ]
    ]

    # Add team registration button only if team mode is enabled
    if team_mode_enabled == 1:
        buttons.append([
            InlineKeyboardButton(
                text="👥 Зарегистрироваться как команда",
                callback_data="start_team_registration",
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


async def handle_start_command(
    message: Message, state: FSMContext, bot: Bot, admin_id: int
):
    """Обработчик команды /start"""
    # Проверяем, что отправитель не является ботом
    if message.from_user.is_bot:
        logger.warning(
            f"Попытка взаимодействия с ботом: {message.from_user.id} (@{message.from_user.username})"
        )
        return

    user_id = message.from_user.id
    log.command_received("/start", user_id, message.from_user.username)

    # Проверяем наличие реферального кода в команде /start
    if message.text and len(message.text.split()) > 1:
        referral_code = message.text.split()[1]

        # Проверяем, это реферальная ссылка команды или переоформления слота
        if referral_code.startswith("team_"):
            # Обработка реферальной ссылки команды
            await handle_team_referral_start(message, referral_code, bot, admin_id, state)
            return
        else:
            # Обработка обычной реферальной ссылки (переоформление слота)
            from .slot_transfer_handlers import handle_referral_start
            await handle_referral_start(message, referral_code, bot, admin_id, state)
            return

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

    # Проверка активности события (до проверки reg_end_date)
    if not is_current_event_active():
        await message.answer(
            "⚠️ <b>Регистрация на мероприятие пока не открыта</b>\n\n"
            "Следите за обновлениями!",
            reply_markup=create_main_menu_keyboard()
        )
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
                            parse_mode="HTML",
                        )
                        logger.info(
                            f"Сообщение о закрытой регистрации с афишей отправлено user_id={message.from_user.id}"
                        )
                    else:
                        await message.answer(messages["registration_closed"])
                        logger.info(
                            f"Сообщение о закрытой регистрации (без афиши) отправлено user_id={message.from_user.id}"
                        )
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке сообщения о закрытой регистрации: {e}"
                    )
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
        gender = (
            "мужской"
            if participant[9] == "male"
            else "женский" if participant[9] == "female" else "не указан"
        )
        # Категория с эмодзи
        if participant[10]:
            category_emoji = {
                "СуперЭлита": "💎",
                "Элита": "🥇",
                "Классика": "🏃",
                "Женский": "👩",
                "Команда": "👥",
            }.get(participant[10], "📂")
            category = f"{category_emoji} {participant[10]}"
        else:
            category = "📂 не назначена"

        # Кластер с эмодзи
        if participant[11]:
            cluster_emoji = {
                "A": "🅰️",
                "B": "🅱️",
                "C": "🅲",
                "D": "🅳",
                "E": "🅴",
                "F": "🅵",
                "G": "🅶",
            }.get(participant[11], "🎯")
            cluster = f"{cluster_emoji} {participant[11]}"
        else:
            cluster = "🎯 не назначен"

        # Извлекаем информацию о команде
        team_name = participant[12]
        team_invite_code = participant[13]

        # Определяем статус оплаты
        payment_emoji = "✅" if payment_status == "paid" else "⏳"
        payment_text = (
            "оплачено" if payment_status == "paid" else "ожидает подтверждения"
        )

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

        # Создаем клавиатуру с кнопками "Переоформить слот" и "Отменить участие"
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    text="🔄 Переоформить слот", callback_data="slot_transfer"
                )
            ]
        ]

        # Проверяем, нужно ли добавить кнопку "Пригласить друга"
        # Условия: категория "Команда", есть team_invite_code (создатель команды), и второй участник еще не зарегистрировался
        if participant[10] == "Команда" and team_invite_code:
            from database import count_team_members

            team_members_count = count_team_members(team_name)

            if team_members_count < 2:
                # Добавляем информацию о команде в сообщение
                participant_info = (
                    f"✅ <b>Вы уже зарегистрированы!</b>\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {name}\n"
                    f"• Целевое время: {target_time}\n"
                    f"• Пол: {gender}\n"
                    f"• Беговой номер: {bib_number}\n"
                    f"• Категория: {category}\n"
                    f"• Команда: {team_name}\n"
                    f"• Кластер: {cluster}\n\n"
                    f"💰 <b>Статус оплаты:</b> {payment_emoji} {payment_text}\n\n"
                )

                if payment_status != "paid":
                    participant_info += f"💡 Не забудьте произвести оплату участия {get_participation_fee_text()}!\n\n"
                else:
                    participant_info += "🎉 Все готово к старту! Увидимся на мероприятии!\n\n"

                participant_info += "👥 <b>Вы можете пригласить друга в команду!</b>"

                # Создаем реферальную ссылку для приглашения
                bot_username = (await bot.get_me()).username
                invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code}"

                # Добавляем кнопку "Пригласить друга" перед кнопкой "Переоформить слот"
                keyboard_buttons.insert(0, [
                    InlineKeyboardButton(
                        text="👥 Пригласить друга",
                        url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                    )
                ])

        # Добавляем кнопку "Отменить участие" в конец
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="❌ Отменить участие", callback_data="cancel_participation"
            )
        ])

        participant_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(participant_info, reply_markup=participant_keyboard)
        return

    # Проверка нахождения в очереди ожидания
    if is_user_in_waitlist(user_id):
        waitlist_entry = get_waitlist_by_user_id(user_id)

        if waitlist_entry:
            position, total_waiting = get_waitlist_position(user_id)
            name = waitlist_entry[3]  # name at index 3
            role = waitlist_entry[5]  # role at index 5
            role_display = "бегуна" if role == "runner" else "волонтёра"
            status = waitlist_entry[8]  # status at index 8
            team_name = waitlist_entry[11]  # team_name at index 11
            team_invite_code = waitlist_entry[12]  # team_invite_code at index 12

            # Создаем клавиатуру для проверки статуса и отмены участия
            waitlist_keyboard_buttons = []

            # Проверяем, нужно ли добавить кнопку "Пригласить друга" для команды в очереди
            if team_name and team_invite_code:
                from database import count_team_members

                team_members_count = count_team_members(team_name)

                if team_members_count < 2:
                    # Создатель команды в очереди - добавляем кнопку приглашения
                    bot_username = (await bot.get_me()).username
                    invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code}"

                    waitlist_keyboard_buttons.append([
                        InlineKeyboardButton(
                            text="👥 Пригласить друга",
                            url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                        )
                    ])

            waitlist_keyboard_buttons.extend([
                [
                    InlineKeyboardButton(
                        text="📊 Проверить статус",
                        callback_data="check_waitlist_status",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отменить участие",
                        callback_data="cancel_participation",
                    )
                ],
            ])

            waitlist_keyboard = InlineKeyboardMarkup(inline_keyboard=waitlist_keyboard_buttons)

            if status == "notified":
                # Пользователь уведомлен о доступном месте
                message_text = (
                    f"🎉 <b>{name}, для вас освободилось место!</b>\n\n"
                    f"📋 Вы находитесь в очереди ожидания на роль {role_display}.\n"
                    f"📬 Вам было отправлено уведомление о подтверждении участия.\n\n"
                    f"⏰ <b>Важно:</b> У вас есть ограниченное время для подтверждения!\n\n"
                    f"💡 Найдите сообщение с кнопками подтверждения в этом чате."
                )
            else:
                # Обычное ожидание
                message_text = (
                    f"📋 <b>{name}, вы в очереди ожидания!</b>\n\n"
                    f"🔢 <b>Ваша позиция:</b> {position} из {total_waiting}\n"
                    f"👥 <b>Роль:</b> {role_display}\n\n"
                    f"⏳ <b>Ожидайте уведомления о свободном месте.</b>\n"
                    f"Мы автоматически сообщим вам, когда освободится место!\n\n"
                    f"📱 Следите за уведомлениями в этом чате."
                )

                # Добавляем информацию о команде, если пользователь в команде
                if team_name:
                    message_text = (
                        f"📋 <b>{name}, вы в очереди ожидания!</b>\n\n"
                        f"🔢 <b>Ваша позиция:</b> {position} из {total_waiting}\n"
                        f"👥 <b>Роль:</b> {role_display}\n"
                        f"👥 <b>Команда:</b> {team_name}\n\n"
                        f"⏳ <b>Ожидайте уведомления о свободном месте.</b>\n"
                        f"Мы автоматически сообщим вам, когда освободится место!\n\n"
                        f"📱 Следите за уведомлениями в этом чате."
                    )

                    if team_invite_code and team_members_count < 2:
                        message_text += "\n\n👥 <b>Вы можете пригласить друга в команду!</b>"

            await message.answer(message_text, reply_markup=waitlist_keyboard)
            return

    # Добавляем в pending_registrations
    username = message.from_user.username or "не указан"
    success = add_pending_registration(user_id, username)

    if not success:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        return

    # Отправляем стартовое сообщение с афишей если есть
    try:
        start_message = messages["start_message"].format(
            fee=get_participation_fee_text(),
            event_date=get_event_date_text(),
            event_time=get_event_time_text(),
            event_location=get_event_location_text(),
        )

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
                start_message, reply_markup=create_start_registration_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке стартового сообщения: {e}")
        await message.answer(
            messages["start_message"].format(
                fee=get_participation_fee_text(),
                event_date=get_event_date_text(),
                event_time=get_event_time_text(),
                event_location=get_event_location_text(),
            ),
            reply_markup=create_start_registration_keyboard(),
        )


async def handle_start_registration(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала процесса регистрации"""
    user_id = callback.from_user.id

    # Проверяем, есть ли у пользователя история участия
    from database import get_latest_user_result

    latest_result = get_latest_user_result(user_id)

    if latest_result and latest_result.get("name"):
        # Пользователь уже участвовал ранее, используем его имя
        name = latest_result.get("name")
        await state.update_data(name=name, role="runner")

        try:
            # Try to edit as text message first
            await callback.message.edit_text(
                f"👋 Рады видеть вас снова, {name}!\n\n"
                f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
            )
        except Exception:
            # If it fails, it might be a photo message, try editing caption
            try:
                await callback.message.edit_caption(
                    caption=f"👋 Рады видеть вас снова, {name}!\n\n"
                    f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
                )
            except Exception:
                # If both fail, send a new message
                await callback.message.answer(
                    f"👋 Рады видеть вас снова, {name}!\n\n"
                    f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
                )

        await state.set_state(RegistrationForm.waiting_for_target_time)
    else:
        # Новый пользователь, запрашиваем имя
        try:
            # Try to edit as text message first
            await callback.message.edit_text("📝 Введите ваше полное имя:")
        except Exception:
            # If it fails, it might be a photo message, try editing caption
            try:
                await callback.message.edit_caption(
                    caption="📝 Введите ваше полное имя:"
                )
            except Exception:
                # If both fail, send a new message
                await callback.message.answer("📝 Введите ваше полное имя:")

        await state.set_state(RegistrationForm.waiting_for_name)

    await callback.answer()


async def handle_name_input(message: Message, state: FSMContext):
    """Обработчик ввода имени"""
    name = sanitize_input(message.text, 50)

    is_valid, error_message = validate_name(name)
    if not is_valid:
        await message.answer(
            f"❌ {error_message}", reply_markup=create_main_menu_keyboard()
        )
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
        await message.answer(
            f"❌ {error_message}", reply_markup=create_main_menu_keyboard()
        )
        return

    await state.update_data(target_time=target_time)

    # Проверяем, это командная регистрация или обычная
    user_data = await state.get_data()
    is_team_registration = user_data.get("is_team_registration", False)
    is_team_member = user_data.get("is_team_member", False)  # Проверяем, это присоединяющийся участник или создатель

    if is_team_registration and not is_team_member:
        # Создатель команды - запрашиваем название
        await message.answer("👥 Введите название вашей команды:")
        await state.set_state(RegistrationForm.waiting_for_team_name)
    else:
        # Для обычного бегуна или присоединяющегося к команде - запрашиваем пол
        await message.answer("👤 Укажите ваш пол:", reply_markup=create_gender_keyboard())
        await state.set_state(RegistrationForm.waiting_for_gender)


async def handle_gender_selection(
    callback: CallbackQuery, state: FSMContext, bot: Bot, admin_id: int
):
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

                # Создаем клавиатуру с кнопкой для перевода из очереди
                waitlist_admin_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Перевести из листа ожидания",
                                callback_data=f"promote_from_waitlist_{user_id}"
                            )
                        ]
                    ]
                )

                await bot.send_message(admin_id, admin_text, reply_markup=waitlist_admin_keyboard)

            except Exception as e:
                logger.error(
                    f"Ошибка при уведомлении администратора о записи в очередь: {e}"
                )
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
                        caption="🤝 Наши спонсоры",
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
                logger.error(
                    f"Ошибка при уведомлении администратора о регистрации: {e}"
                )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при регистрации. Попробуйте позже."
            )

    await callback.answer()
    await state.clear()


async def handle_cancel_participation_request(
    callback: CallbackQuery, bot: Bot, admin_id: int
):
    """Обработчик запроса на отмену участия - показывает подтверждение"""
    user_id = callback.from_user.id

    # Проверяем, является ли пользователь участником или в очереди
    from database import get_participant_by_user_id, is_user_in_waitlist

    participant = get_participant_by_user_id(user_id)
    in_waitlist = is_user_in_waitlist(user_id)

    if not participant and not in_waitlist:
        await callback.message.edit_text(
            "❌ Вы не зарегистрированы в гонке.",
        )
        await callback.answer()
        return

    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, отменить", callback_data="confirm_cancel_participation"
                ),
                InlineKeyboardButton(
                    text="❌ Нет, остаться",
                    callback_data="decline_cancel_participation",
                ),
            ]
        ]
    )

    await callback.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите отменить участие?</b>\n\n"
        "После отмены вы будете удалены из списка участников и лимит мест будет уменьшен.\n"
        "Вы сможете зарегистрироваться заново через команду /start.",
        reply_markup=confirm_keyboard,
    )
    await callback.answer()


async def handle_confirm_cancel_participation(
    callback: CallbackQuery, bot: Bot, admin_id: int
):
    """Обработчик подтверждения отмены участия"""
    user_id = callback.from_user.id
    username = callback.from_user.username or "не указан"

    from database import cancel_user_participation

    result = cancel_user_participation(user_id)

    if result["success"]:
        user_name = result["user_name"]
        role = result["role"]
        source = result["source"]
        old_limit = result.get("old_limit")
        new_limit = result.get("new_limit")
        team_partner = result.get("team_partner")

        role_display = "бегунов" if role == "runner" else "волонтёров"
        source_display = (
            "участников" if source == "participants" else "очереди ожидания"
        )

        # Сообщение пользователю
        user_message = (
            f"✅ <b>Участие отменено</b>\n\n"
            f"Вы удалены из списка {source_display}.\n"
        )

        user_message += "Вы можете зарегистрироваться заново через команду /start."

        await callback.message.edit_text(user_message)

        # Уведомление админа
        try:
            admin_message = (
                f"⚠️ <b>Отмена участия</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name} (@{username})\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"📋 <b>Роль:</b> {role_display}\n"
                f"📍 <b>Откуда удален:</b> из {source_display.capitalize()}\n"
            )

            if old_limit is not None and new_limit is not None:
                admin_message += (
                    f"📊 <b>Лимит {role_display}:</b> {old_limit} → {new_limit}\n"
                )

            # Добавляем информацию о напарнике по команде если есть
            if team_partner:
                admin_message += (
                    f"\n👥 <b>Напарник по команде:</b> {team_partner['name']} "
                    f"(@{team_partner['username'] or 'нет'}) "
                    f"(ID: <code>{team_partner['user_id']}</code>)\n"
                    f"📍 <b>Статус напарника:</b> {source_display}\n"
                    f"📂 <b>Команда:</b> {team_partner['team_name']}"
                )

            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(
                f"Ошибка при уведомлении администратора об отмене участия: {e}"
            )

        # Уведомляем напарника по команде если он есть
        if team_partner:
            try:
                partner_source_display = (
                    "участников" if team_partner['source'] == "participants" else "очереди ожидания"
                )
                partner_message = (
                    f"⚠️ <b>Изменение в вашей команде</b>\n\n"
                    f"Ваш напарник по команде <b>{user_name}</b> отменил участие и был удален из списка {source_display}.\n\n"
                    f"👥 <b>Команда:</b> {team_partner['team_name']}\n"
                    f"📍 <b>Ваш статус:</b> {partner_source_display}\n\n"
                    f"💡 Вы можете пригласить нового напарника в команду!"
                )

                # Получаем team_invite_code напарника
                partner_team_invite_code = team_partner.get('team_invite_code')

                # Создаем клавиатуру с кнопками
                partner_keyboard_buttons = []

                # Если есть код приглашения - добавляем кнопку "Пригласить друга"
                if partner_team_invite_code:
                    bot_username = (await bot.get_me()).username
                    invite_link = f"https://t.me/{bot_username}?start=team_{partner_team_invite_code}"
                    partner_keyboard_buttons.append([
                        InlineKeyboardButton(
                            text="👥 Пригласить друга",
                            url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_partner['team_name']}' на забеге!"
                        )
                    ])

                # Добавляем кнопку "Главное меню"
                partner_keyboard_buttons.append([
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu"
                    )
                ])

                partner_keyboard = InlineKeyboardMarkup(inline_keyboard=partner_keyboard_buttons)

                await bot.send_message(team_partner['user_id'], partner_message, reply_markup=partner_keyboard)
                logger.info(f"Уведомление о выходе напарника отправлено пользователю {team_partner['user_id']}")
            except TelegramForbiddenError:
                logger.warning(f"Напарник по команде {team_partner['user_id']} заблокировал бот")
            except Exception as e:
                logger.error(f"Ошибка при уведомлении напарника по команде {team_partner['user_id']}: {e}")
    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при отмене участия</b>\n\n{error_message}"
        )

    await callback.answer()


async def handle_decline_cancel_participation(callback: CallbackQuery):
    """Обработчик отказа от отмены участия"""
    await callback.message.edit_text(
        "✅ <b>Отмена участия отменена</b>\n\n"
        "Вы остаётесь в списке участников.\n"
        "Используйте команду /start для просмотра информации о вашей регистрации."
    )
    await callback.answer()


async def handle_team_referral_start(
    message: Message, referral_code: str, bot: Bot, admin_id: int, state: FSMContext
):
    """Обработчик регистрации по реферальной ссылке команды"""
    user_id = message.from_user.id

    # Check if team mode is enabled
    team_mode_enabled = get_setting("team_mode_enabled")
    team_mode_enabled = int(team_mode_enabled) if team_mode_enabled is not None else 1

    if team_mode_enabled == 0:
        await message.answer(
            "❌ <b>Командный режим отключен</b>\n\n"
            "В данный момент регистрация команд недоступна.\n"
            "Вы можете зарегистрироваться только как индивидуальный бегун через /start."
        )
        return

    # Извлекаем код из формата team_CODE
    team_code = referral_code[5:]  # Убираем префикс "team_"

    # Проверяем, существует ли такой код в БД (ищет и в participants, и в waitlist)
    from database import get_participant_by_team_invite_code

    team_creator_data = get_participant_by_team_invite_code(team_code)

    if not team_creator_data:
        await message.answer(
            "❌ <b>Неверная или недействительная ссылка приглашения</b>\n\n"
            "Возможно, ссылка устарела или была использована.\n"
            "Свяжитесь с организатором команды."
        )
        return

    # Проверяем, не зарегистрирован ли пользователь уже
    from database import get_participant_by_user_id

    participant = get_participant_by_user_id(user_id)
    if participant:
        await message.answer(
            "❌ <b>Вы уже зарегистрированы!</b>\n\n"
            "Чтобы присоединиться к команде, сначала отмените свою текущую регистрацию через команду /start."
        )
        return

    # Извлекаем информацию о команде
    creator_user_id, team_name, creator_name, creator_in_waitlist = team_creator_data

    # Проверяем, не была ли уже использована эта ссылка (код может использоваться только один раз)
    # Считаем участников с этим team_name и категорией "Команда"
    from database import count_team_members

    team_members_count = count_team_members(team_name)

    if team_members_count >= 2:
        await message.answer(
            f"❌ <b>Команда уже укомплектована</b>\n\n"
            f"В команде '{team_name}' уже зарегистрировано максимальное количество участников (2).\n"
            f"Попробуйте создать свою команду или свяжитесь с организатором."
        )
        return

    # Сохраняем информацию о команде в состояние и запускаем регистрацию
    await state.update_data(
        team_name=team_name,
        team_invite_code=None,  # Второму участнику не нужен свой код
        is_team_member=True,
        is_team_registration=True,
        creator_in_waitlist=creator_in_waitlist,  # Сохраняем информацию о том, в листе ожидания ли создатель
        creator_user_id=creator_user_id  # Сохраняем ID создателя для уведомления
    )

    # Проверяем, есть ли у пользователя история участия
    from database import get_latest_user_result

    latest_result = get_latest_user_result(user_id)

    status_text = "в списке ожидания" if creator_in_waitlist else "участником"

    if latest_result and latest_result.get("name"):
        # Пользователь уже участвовал ранее
        name = latest_result.get("name")
        await state.update_data(name=name, role="runner")

        await message.answer(
            f"👋 Рады видеть вас снова, {name}!\n\n"
            f"👥 <b>Присоединение к команде '{team_name}'</b>\n"
            f"Создатель команды: {creator_name} ({status_text})\n\n"
            f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
        )
        await state.set_state(RegistrationForm.waiting_for_target_time)
    else:
        # Новый пользователь
        await message.answer(
            f"👥 <b>Присоединение к команде '{team_name}'</b>\n"
            f"Создатель команды: {creator_name} ({status_text})\n\n"
            f"📝 Введите ваше полное имя:"
        )
        await state.set_state(RegistrationForm.waiting_for_name)


async def handle_start_team_registration(callback: CallbackQuery, state: FSMContext):
    """Обработчик начала командной регистрации"""
    user_id = callback.from_user.id

    # Check if team mode is enabled
    team_mode_enabled = get_setting("team_mode_enabled")
    team_mode_enabled = int(team_mode_enabled) if team_mode_enabled is not None else 1

    if team_mode_enabled == 0:
        await callback.message.edit_text(
            "❌ <b>Командный режим отключен</b>\n\n"
            "В данный момент регистрация команд недоступна.\n"
            "Вы можете зарегистрироваться только как индивидуальный бегун."
        )
        await callback.answer()
        return

    # Проверяем, есть ли у пользователя история участия
    from database import get_latest_user_result

    latest_result = get_latest_user_result(user_id)

    if latest_result and latest_result.get("name"):
        # Пользователь уже участвовал ранее, используем его имя
        name = latest_result.get("name")
        await state.update_data(name=name, role="runner", is_team_registration=True)

        try:
            await callback.message.edit_text(
                f"👋 Рады видеть вас снова, {name}!\n\n"
                f"👥 <b>Регистрация команды</b>\n\n"
                f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
            )
        except Exception:
            try:
                await callback.message.edit_caption(
                    caption=f"👋 Рады видеть вас снова, {name}!\n\n"
                    f"👥 <b>Регистрация команды</b>\n\n"
                    f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
                )
            except Exception:
                await callback.message.answer(
                    f"👋 Рады видеть вас снова, {name}!\n\n"
                    f"👥 <b>Регистрация команды</b>\n\n"
                    f"⏰ Введите ваше целевое время прохождения трассы (например, '5:30' или '1:05:30'):"
                )

        await state.set_state(RegistrationForm.waiting_for_target_time)
    else:
        # Новый пользователь, запрашиваем имя
        try:
            await callback.message.edit_text(
                "👥 <b>Регистрация команды</b>\n\n"
                "📝 Введите ваше полное имя:"
            )
        except Exception:
            try:
                await callback.message.edit_caption(
                    caption="👥 <b>Регистрация команды</b>\n\n"
                    "📝 Введите ваше полное имя:"
                )
            except Exception:
                await callback.message.answer(
                    "👥 <b>Регистрация команды</b>\n\n"
                    "📝 Введите ваше полное имя:"
                )

        await state.update_data(is_team_registration=True)
        await state.set_state(RegistrationForm.waiting_for_name)

    await callback.answer()


async def handle_team_name_input(message: Message, state: FSMContext):
    """Обработчик ввода названия команды"""
    team_name = sanitize_input(message.text, 100)

    if not team_name or len(team_name) < 2:
        await message.answer(
            "❌ Название команды должно содержать хотя бы 2 символа. Попробуйте снова:"
        )
        return

    await state.update_data(team_name=team_name)
    await message.answer("👤 Укажите ваш пол:", reply_markup=create_gender_keyboard())
    await state.set_state(RegistrationForm.waiting_for_gender)


async def handle_team_gender_selection(
    callback: CallbackQuery, state: FSMContext, bot: Bot, admin_id: int
):
    """Обработчик выбора пола для команды и завершение регистрации"""
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
    team_name = user_data.get("team_name")
    role = "runner"
    gender = callback.data

    # Проверяем, это присоединяющийся участник или создатель команды
    is_team_member = user_data.get("is_team_member", False)
    creator_in_waitlist = user_data.get("creator_in_waitlist", False)

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

    # Если второй участник присоединяется к команде, обрабатываем его регистрацию в зависимости от статуса создателя
    if is_team_member:
        # Если создатель в waitlist - второй тоже в waitlist
        if creator_in_waitlist:
            # Добавляем второго участника в waitlist
            success = add_to_waitlist(
                user_id, username, name, target_time, role, gender,
                team_name, None  # Второму участнику не нужен код приглашения
            )

            if success:
                user_message = (
                    f"✅ <b>Вы присоединились к команде '{team_name}'!</b>\n\n"
                    f"👥 Создатель команды находится в списке ожидания.\n"
                    f"📋 Вы также добавлены в список ожидания.\n"
                    f"📱 Когда освободится место, вы оба будете переведены в участники!\n\n"
                    f"📂 Категория 'Команда' будет автоматически присвоена.\n\n"
                    f"💡 Используйте /waitlist_status для проверки позиции в очереди."
                )
                await callback.message.edit_text(user_message)

                # Уведомляем админа
                try:
                    from database import get_waitlist_by_role

                    waitlist_count = len(get_waitlist_by_role("runner"))

                    admin_text = (
                        f"📋 <b>Новый пользователь в очереди ожидания (КОМАНДА - 2й участник)</b>\n\n"
                        f"👤 <b>Пользователь:</b> {name} (@{username})\n"
                        f"👥 <b>Название команды:</b> {team_name}\n"
                        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                        f"⏰ <b>Целевое время:</b> {target_time}\n"
                        f"👤 <b>Пол:</b> {'мужской' if gender == 'male' else 'женский'}\n"
                        f"📊 <b>Всего в очереди:</b> {waitlist_count}\n"
                        f"💼 <b>Текущий лимит:</b> {max_runners}\n"
                        f"ℹ️ <b>Создатель команды в waitlist</b>"
                    )

                    waitlist_admin_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Перевести из листа ожидания",
                                    callback_data=f"promote_from_waitlist_{user_id}"
                                )
                            ]
                        ]
                    )

                    await bot.send_message(admin_id, admin_text, reply_markup=waitlist_admin_keyboard)

                except Exception as e:
                    logger.error(
                        f"Ошибка при уведомлении администратора о записи в очередь: {e}"
                    )
            else:
                await callback.message.edit_text(
                    "❌ Ошибка при добавлении в очередь ожидания. Попробуйте позже."
                )

            await callback.answer()
            await state.clear()
            return

        # Если создатель НЕ в waitlist (т.е. в participants) - второй попадает в participants
        else:
            # Добавляем второго участника сразу в participants с командой
            from database import add_participant_with_team

            success = add_participant_with_team(
                user_id, username, name, target_time, role, gender, team_name, None  # Второму участнику не нужен код
            )

            if success:
                # Удаляем из pending_registrations
                delete_pending_registration(user_id)

                # Увеличиваем лимит max_runners на 1, так как второй участник добавлен в обход проверки лимита
                from database import set_setting
                new_max_runners = max_runners + 1
                set_setting("max_runners", new_max_runners)
                logger.info(f"Лимит max_runners увеличен с {max_runners} до {new_max_runners} при добавлении второго участника команды '{team_name}'")

                gender_display = "мужской" if gender == "male" else "женский"

                # Получаем количество полных команд
                complete_teams = count_complete_teams()

                user_message = (
                    f"✅ <b>Вы успешно присоединились к команде!</b>\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {name}\n"
                    f"• Целевое время: {target_time}\n"
                    f"• Пол: {gender_display}\n"
                    f"• Роль: бегун\n"
                    f"• Категория: 👥 Команда\n"
                    f"• Название команды: {team_name}\n\n"
                    f"👥 <b>Полных команд зарегистрировано:</b> {complete_teams}\n\n"
                    f"💰 <b>Важно:</b> Не забудьте произвести оплату участия {get_participation_fee_text()}!\n"
                    f"📱 Свяжитесь с администратором для подтверждения оплаты."
                )
                await callback.message.edit_text(user_message)

                # Отправляем изображение спонсоров если есть
                try:
                    sponsor_image_path = config.get(
                        "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                    )
                    if os.path.exists(sponsor_image_path):
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=FSInputFile(path=sponsor_image_path),
                            caption="🤝 Наши спонсоры",
                        )
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения спонсоров: {e}")

                # Уведомляем администратора
                try:
                    # Пересчитываем количество бегунов после добавления
                    updated_runners = get_participant_count_by_role("runner")

                    admin_message = (
                        f"🆕 <b>Новая регистрация команды (2й участник)!</b>\n\n"
                        f"👤 <b>Участник:</b> {name}\n"
                        f"👥 <b>Название команды:</b> {team_name}\n"
                        f"⏰ <b>Целевое время:</b> {target_time}\n"
                        f"👤 <b>Пол:</b> {gender_display}\n"
                        f"🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n"
                        f"📱 <b>Username:</b> @{username}\n\n"
                        f"🎭 <b>Роль:</b> бегун\n"
                        f"📂 <b>Категория:</b> 👥 Команда (авто)\n"
                        f"💰 <b>Статус оплаты:</b> ожидает подтверждения\n"
                        f"📊 <b>Всего бегунов:</b> {updated_runners}/{new_max_runners}\n"
                        f"📈 <b>Лимит увеличен:</b> {max_runners} → {new_max_runners}\n"
                        f"ℹ️ <b>Создатель команды уже является участником</b>"
                    )

                    await bot.send_message(admin_id, admin_message)

                except Exception as e:
                    logger.error(
                        f"Ошибка при уведомлении администратора о регистрации: {e}"
                    )

                # Уведомляем первого участника команды о регистрации второго
                try:
                    creator_user_id = user_data.get("creator_user_id")
                    if creator_user_id:
                        # Получаем информацию о создателе команды
                        creator_info = get_participant_by_user_id(creator_user_id)
                        if creator_info:
                            creator_name = creator_info[2]
                            creator_notification = (
                                f"🎉 <b>К вашей команде присоединился новый участник!</b>\n\n"
                                f"👥 <b>Команда:</b> {team_name}\n"
                                f"👤 <b>Участник:</b> {name}\n"
                                f"⏰ <b>Целевое время:</b> {target_time}\n"
                                f"👤 <b>Пол:</b> {gender_display}\n\n"
                                f"👥 <b>Полных команд зарегистрировано:</b> {complete_teams}\n\n"
                                f"✅ Ваша команда теперь полностью укомплектована!"
                            )
                            await bot.send_message(creator_user_id, creator_notification)
                            logger.info(f"Уведомление о новом участнике команды отправлено создателю {creator_user_id}")
                        else:
                            logger.warning(f"Не удалось найти информацию о создателе команды {creator_user_id}")
                    else:
                        logger.warning("creator_user_id не найден в состоянии при попытке уведомить создателя команды")
                except TelegramForbiddenError:
                    logger.warning(f"Создатель команды {creator_user_id} заблокировал бот")
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении создателя команды: {e}")
            else:
                await callback.message.edit_text(
                    "❌ Ошибка при регистрации. Попробуйте позже."
                )

            await callback.answer()
            await state.clear()
            return

    if current_runners >= max_runners:
        # Добавляем в очередь ожидания с информацией о команде
        # Проверяем, это создатель команды или присоединяющийся участник
        is_team_member = user_data.get("is_team_member", False)
        team_invite_code_to_save = user_data.get("team_invite_code")

        if not is_team_member:
            # Создатель команды - генерируем уникальный код приглашения
            import secrets
            team_invite_code_to_save = secrets.token_urlsafe(12)
        else:
            # Присоединяющийся участник - код не нужен
            team_invite_code_to_save = None

        success = add_to_waitlist(
            user_id, username, name, target_time, role, gender,
            team_name, team_invite_code_to_save
        )

        if success:
            # Создаем сообщение для пользователя
            if is_team_member:
                user_message = (
                    f"📋 <b>Все слоты для бегунов заняты!</b>\n\n"
                    f"✅ Вы добавлены в очередь ожидания для команды '{team_name}'.\n"
                    f"📱 Уведомим вас, когда освободится место!\n"
                    f"📂 Категория 'Команда' будет автоматически присвоена при добавлении.\n\n"
                    f"💡 Используйте /waitlist_status для проверки позиции в очереди."
                )
            else:
                # Создатель команды - даже в очереди получит код и кнопку приглашения
                bot_username = (await bot.get_me()).username
                invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code_to_save}"

                user_message = (
                    f"📋 <b>Все слоты для бегунов заняты!</b>\n\n"
                    f"✅ Вы добавлены в очередь ожидания для команды '{team_name}'.\n"
                    f"📱 Уведомим вас, когда освободится место!\n"
                    f"📂 Категория 'Команда' будет автоматически присвоена при добавлении.\n\n"
                    f"💡 Используйте /waitlist_status для проверки позиции в очереди."
                )

                # Кнопка для приглашения друга даже в очереди
                invite_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👥 Пригласить друга в команду",
                                url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                            )
                        ]
                    ]
                )
                await callback.message.edit_text(user_message, reply_markup=invite_keyboard)

                # Уведомляем админа
                try:
                    from database import get_waitlist_by_role

                    waitlist_count = len(get_waitlist_by_role("runner"))

                    admin_text = (
                        f"📋 <b>Новый пользователь в очереди ожидания (КОМАНДА)</b>\n\n"
                        f"👤 <b>Пользователь:</b> {name} (@{username})\n"
                        f"👥 <b>Название команды:</b> {team_name}\n"
                        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                        f"⏰ <b>Целевое время:</b> {target_time}\n"
                        f"👤 <b>Пол:</b> {'мужской' if gender == 'male' else 'женский'}\n"
                        f"📊 <b>Всего в очереди:</b> {waitlist_count}\n"
                        f"💼 <b>Текущий лимит:</b> {max_runners}\n"
                        f"🔗 <b>Код приглашения:</b> <code>{team_invite_code_to_save}</code>"
                    )

                    waitlist_admin_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Перевести из листа ожидания",
                                    callback_data=f"promote_from_waitlist_{user_id}"
                                )
                            ]
                        ]
                    )

                    await bot.send_message(admin_id, admin_text, reply_markup=waitlist_admin_keyboard)

                except Exception as e:
                    logger.error(
                        f"Ошибка при уведомлении администратора о записи в очередь: {e}"
                    )

                # Выходим, так как сообщение уже отправлено
                await callback.answer()
                await state.clear()
                return

            await callback.message.edit_text(user_message)

            # Уведомляем админа для присоединившегося участника
            try:
                from database import get_waitlist_by_role

                waitlist_count = len(get_waitlist_by_role("runner"))

                admin_text = (
                    f"📋 <b>Новый пользователь в очереди ожидания (КОМАНДА)</b>\n\n"
                    f"👤 <b>Пользователь:</b> {name} (@{username})\n"
                    f"👥 <b>Название команды:</b> {team_name}\n"
                    f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                    f"⏰ <b>Целевое время:</b> {target_time}\n"
                    f"👤 <b>Пол:</b> {'мужской' if gender == 'male' else 'женский'}\n"
                    f"📊 <b>Всего в очереди:</b> {waitlist_count}\n"
                    f"💼 <b>Текущий лимит:</b> {max_runners}\n"
                )

                waitlist_admin_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Перевести из листа ожидания",
                                callback_data=f"promote_from_waitlist_{user_id}"
                            )
                        ]
                    ]
                )

                await bot.send_message(admin_id, admin_text, reply_markup=waitlist_admin_keyboard)

            except Exception as e:
                logger.error(
                    f"Ошибка при уведомлении администратора о записи в очередь: {e}"
                )
        else:
            await callback.message.edit_text(
                "❌ Ошибка при добавлении в очередь ожидания. Попробуйте позже."
            )
    else:
        # Есть свободные слоты - регистрируем пользователя с командой
        # Проверяем, это создатель команды или присоединяющийся участник
        is_team_member = user_data.get("is_team_member", False)
        team_invite_code = user_data.get("team_invite_code")

        if not is_team_member:
            # Создатель команды - генерируем уникальный код приглашения
            import secrets
            team_invite_code = secrets.token_urlsafe(12)
        else:
            # Присоединяющийся участник - код не нужен
            team_invite_code = None

        # Добавляем участника с категорией "Команда", названием команды и кодом приглашения
        from database import add_participant_with_team

        success = add_participant_with_team(
            user_id, username, name, target_time, role, gender, team_name, team_invite_code
        )

        if success:
            # Удаляем из pending_registrations
            delete_pending_registration(user_id)

            # Уведомление пользователю об успешной регистрации
            gender_display = "мужской" if gender == "male" else "женский"

            if is_team_member:
                # Присоединившийся участник
                success_message = (
                    f"✅ <b>Вы успешно присоединились к команде!</b>\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {name}\n"
                    f"• Целевое время: {target_time}\n"
                    f"• Пол: {gender_display}\n"
                    f"• Роль: бегун\n"
                    f"• Категория: 👥 Команда\n"
                    f"• Название команды: {team_name}\n\n"
                    f"💰 <b>Важно:</b> Не забудьте произвести оплату участия {get_participation_fee_text()}!\n"
                    f"📱 Свяжитесь с администратором для подтверждения оплаты."
                )
                await callback.message.edit_text(success_message)
            else:
                # Создатель команды - показываем кнопку приглашения
                bot_username = (await bot.get_me()).username
                invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code}"

                success_message = (
                    f"✅ <b>Команда зарегистрирована!</b>\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {name}\n"
                    f"• Целевое время: {target_time}\n"
                    f"• Пол: {gender_display}\n"
                    f"• Роль: бегун\n"
                    f"• Категория: 👥 Команда\n"
                    f"• Название команды: {team_name}\n\n"
                    f"💰 <b>Важно:</b> Не забудьте произвести оплату участия {get_participation_fee_text()}!\n"
                    f"📱 Свяжитесь с администратором для подтверждения оплаты."
                )

                # Кнопка для приглашения друга
                invite_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👥 Пригласить друга в команду",
                                url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                            )
                        ]
                    ]
                )

                await callback.message.edit_text(success_message, reply_markup=invite_keyboard)

            # Отправляем изображение спонсоров если есть
            try:
                sponsor_image_path = config.get(
                    "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                )
                if os.path.exists(sponsor_image_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(path=sponsor_image_path),
                        caption="🤝 Наши спонсоры",
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения спонсоров: {e}")

            # Уведомляем администратора
            try:
                admin_message = (
                    f"🆕 <b>Новая регистрация команды!</b>\n\n"
                    f"👤 <b>Участник:</b> {name}\n"
                    f"👥 <b>Название команды:</b> {team_name}\n"
                    f"⏰ <b>Целевое время:</b> {target_time}\n"
                    f"👤 <b>Пол:</b> {gender_display}\n"
                    f"🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n"
                    f"📱 <b>Username:</b> @{username}\n\n"
                    f"🎭 <b>Роль:</b> бегун\n"
                    f"📂 <b>Категория:</b> 👥 Команда (авто)\n"
                    f"💰 <b>Статус оплаты:</b> ожидает подтверждения\n"
                    f"📊 <b>Всего бегунов:</b> {current_runners + 1}/{max_runners}\n"
                    f"🔗 <b>Код приглашения:</b> <code>{team_invite_code}</code>"
                )

                await bot.send_message(admin_id, admin_message)

            except Exception as e:
                logger.error(
                    f"Ошибка при уведомлении администратора о регистрации: {e}"
                )
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

    dp.message.register(start_wrapper, CommandStart())

    # Начало регистрации
    dp.callback_query.register(
        handle_start_registration, F.data == "start_registration"
    )

    # Начало командной регистрации
    dp.callback_query.register(
        handle_start_team_registration, F.data == "start_team_registration"
    )

    # Ввод имени
    dp.message.register(
        handle_name_input, StateFilter(RegistrationForm.waiting_for_name)
    )

    # Ввод времени
    dp.message.register(
        handle_time_input, StateFilter(RegistrationForm.waiting_for_target_time)
    )

    # Ввод названия команды
    dp.message.register(
        handle_team_name_input, StateFilter(RegistrationForm.waiting_for_team_name)
    )

    # Выбор пола и завершение регистрации
    async def gender_wrapper(callback: CallbackQuery, state: FSMContext):
        # Проверяем, это командная регистрация или обычная
        user_data = await state.get_data()
        is_team_registration = user_data.get("is_team_registration", False)

        if is_team_registration:
            await handle_team_gender_selection(callback, state, bot, admin_id)
        else:
            await handle_gender_selection(callback, state, bot, admin_id)

    dp.callback_query.register(
        gender_wrapper, StateFilter(RegistrationForm.waiting_for_gender)
    )

    # Главное меню для пользователей
    async def handle_user_main_menu(callback: CallbackQuery, state: FSMContext):
        """Handle main menu button for regular users - same as /start"""
        # Clear state first
        await state.clear()

        # If it's admin, redirect to admin panel
        if callback.from_user.id == admin_id:
            from .utils import create_admin_commands_keyboard

            await callback.message.edit_text(
                "🔧 <b>Админ-панель</b>\n\nВыберите категорию:",
                reply_markup=create_admin_commands_keyboard(),
            )
            await callback.answer()
            return

        user_id = callback.from_user.id

        # Проверка даты окончания регистрации
        reg_end_date = get_setting("reg_end_date")
        if reg_end_date:
            try:
                from datetime import datetime
                from pytz import timezone
                end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
                moscow_tz = timezone("Europe/Moscow")
                end_date = moscow_tz.localize(end_date)
                current_time = datetime.now(moscow_tz)
                if current_time > end_date:
                    await callback.message.edit_text(messages["registration_closed"])
                    await callback.answer()
                    return
            except ValueError:
                logger.error(f"Некорректный формат reg_end_date: {reg_end_date}")

        # Проверка исторических участников
        from .archive_handlers import handle_historical_participant

        # Если нет активного события, показываем только историю
        if not is_current_event_active():
            # Для callback нужно создать фейковое сообщение
            historical_handled = await handle_historical_participant(user_id, callback.message)
            if historical_handled:
                await callback.answer()
                return
        else:
            # Если есть активное событие, но пользователь не текущий участник,
            # проверяем его историю для персональных сообщений
            participant = get_participant_by_user_id(user_id)
            if not participant and not is_user_in_waitlist(user_id):
                historical_handled = await handle_historical_participant(user_id, callback.message)
                if historical_handled:
                    await callback.answer()
                    return

        # Проверка существующей регистрации
        participant = get_participant_by_user_id(user_id)
        if participant:
            # Пользователь уже зарегистрирован - показываем информацию
            name = participant[2]
            target_time = participant[3] or "не указано"
            role = "бегун" if participant[4] == "runner" else "волонтёр"
            bib_number = f"№ {participant[7]}" if participant[7] else "не присвоен"
            payment_status = participant[6]
            gender = (
                "мужской"
                if participant[9] == "male"
                else "женский" if participant[9] == "female" else "не указан"
            )
            # Категория с эмодзи
            if participant[10]:
                category_emoji = {
                    "СуперЭлита": "💎",
                    "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                }.get(participant[10], "📂")
                category = f"{category_emoji} {participant[10]}"
            else:
                category = "📂 не назначена"

            # Кластер с эмодзи
            if participant[11]:
                cluster_emoji = {
                    "A": "🅰️",
                    "B": "🅱️",
                    "C": "🅲",
                    "D": "🅳",
                    "E": "🅴",
                    "F": "🅵",
                    "G": "🅶",
                }.get(participant[11], "🎯")
                cluster = f"{cluster_emoji} {participant[11]}"
            else:
                cluster = "🎯 не назначен"

            # Извлекаем информацию о команде
            team_name = participant[12]
            team_invite_code = participant[13]

            # Определяем статус оплаты
            payment_emoji = "✅" if payment_status == "paid" else "⏳"
            payment_text = (
                "оплачено" if payment_status == "paid" else "ожидает подтверждения"
            )

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

            # Создаем клавиатуру с кнопками "Переоформить слот" и "Отменить участие"
            keyboard_buttons = [
                [
                    InlineKeyboardButton(
                        text="🔄 Переоформить слот", callback_data="slot_transfer"
                    )
                ]
            ]

            # Проверяем, нужно ли добавить кнопку "Пригласить друга"
            if participant[10] == "Команда" and team_invite_code:
                from database import count_team_members

                team_members_count = count_team_members(team_name)

                if team_members_count < 2:
                    # Добавляем информацию о команде в сообщение
                    participant_info = (
                        f"✅ <b>Вы уже зарегистрированы!</b>\n\n"
                        f"📝 <b>Ваши данные:</b>\n"
                        f"• Имя: {name}\n"
                        f"• Целевое время: {target_time}\n"
                        f"• Пол: {gender}\n"
                        f"• Беговой номер: {bib_number}\n"
                        f"• Категория: {category}\n"
                        f"• Команда: {team_name}\n"
                        f"• Кластер: {cluster}\n\n"
                        f"💰 <b>Статус оплаты:</b> {payment_emoji} {payment_text}\n\n"
                    )

                    if payment_status != "paid":
                        participant_info += f"💡 Не забудьте произвести оплату участия {get_participation_fee_text()}!\n\n"
                    else:
                        participant_info += "🎉 Все готово к старту! Увидимся на мероприятии!\n\n"

                    participant_info += "👥 <b>Вы можете пригласить друга в команду!</b>"

                    # Создаем реферальную ссылку для приглашения
                    bot_username = (await bot.get_me()).username
                    invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code}"

                    # Добавляем кнопку "Пригласить друга" перед кнопкой "Переоформить слот"
                    keyboard_buttons.insert(0, [
                        InlineKeyboardButton(
                            text="👥 Пригласить друга",
                            url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                        )
                    ])

            # Добавляем кнопку "Отменить участие" в конец
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="❌ Отменить участие", callback_data="cancel_participation"
                )
            ])

            participant_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

            await callback.message.edit_text(participant_info, reply_markup=participant_keyboard)
            await callback.answer()
            return

        # Проверка нахождения в очереди ожидания
        if is_user_in_waitlist(user_id):
            waitlist_entry = get_waitlist_by_user_id(user_id)

            if waitlist_entry:
                position, total_waiting = get_waitlist_position(user_id)
                name = waitlist_entry[3]  # name at index 3
                role = waitlist_entry[5]  # role at index 5
                role_display = "бегуна" if role == "runner" else "волонтёра"
                status = waitlist_entry[8]  # status at index 8
                team_name = waitlist_entry[11]  # team_name at index 11
                team_invite_code = waitlist_entry[12]  # team_invite_code at index 12

                # Создаем клавиатуру для проверки статуса и отмены участия
                waitlist_keyboard_buttons = []

                # Проверяем, нужно ли добавить кнопку "Пригласить друга" для команды в очереди
                if team_name and team_invite_code:
                    from database import count_team_members

                    team_members_count = count_team_members(team_name)

                    if team_members_count < 2:
                        # Создатель команды в очереди - добавляем кнопку приглашения
                        bot_username = (await bot.get_me()).username
                        invite_link = f"https://t.me/{bot_username}?start=team_{team_invite_code}"

                        waitlist_keyboard_buttons.append([
                            InlineKeyboardButton(
                                text="👥 Пригласить друга",
                                url=f"https://t.me/share/url?url={invite_link}&text=Присоединяйся к команде '{team_name}' на забеге!"
                            )
                        ])

                waitlist_keyboard_buttons.extend([
                    [
                        InlineKeyboardButton(
                            text="📊 Проверить статус",
                            callback_data="check_waitlist_status",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Отменить участие",
                            callback_data="cancel_participation",
                        )
                    ],
                ])

                waitlist_keyboard = InlineKeyboardMarkup(inline_keyboard=waitlist_keyboard_buttons)

                if status == "notified":
                    # Пользователь уведомлен о доступном месте
                    message_text = (
                        f"🎉 <b>{name}, для вас освободилось место!</b>\n\n"
                        f"📋 Вы находитесь в очереди ожидания на роль {role_display}.\n"
                        f"📬 Вам было отправлено уведомление о подтверждении участия.\n\n"
                        f"⏰ <b>Важно:</b> У вас есть ограниченное время для подтверждения!\n\n"
                        f"💡 Найдите сообщение с кнопками подтверждения в этом чате."
                    )
                else:
                    # Обычное ожидание
                    message_text = (
                        f"📋 <b>{name}, вы в очереди ожидания!</b>\n\n"
                        f"🔢 <b>Ваша позиция:</b> {position} из {total_waiting}\n"
                        f"👥 <b>Роль:</b> {role_display}\n\n"
                        f"⏳ <b>Ожидайте уведомления о свободном месте.</b>\n"
                        f"Мы автоматически сообщим вам, когда освободится место!\n\n"
                        f"📱 Следите за уведомлениями в этом чате."
                    )

                    # Добавляем информацию о команде, если пользователь в команде
                    if team_name:
                        message_text = (
                            f"📋 <b>{name}, вы в очереди ожидания!</b>\n\n"
                            f"🔢 <b>Ваша позиция:</b> {position} из {total_waiting}\n"
                            f"👥 <b>Роль:</b> {role_display}\n"
                            f"👥 <b>Команда:</b> {team_name}\n\n"
                            f"⏳ <b>Ожидайте уведомления о свободном месте.</b>\n"
                            f"Мы автоматически сообщим вам, когда освободится место!\n\n"
                            f"📱 Следите за уведомлениями в этом чате."
                        )

                        if team_invite_code and team_members_count < 2:
                            message_text += "\n\n👥 <b>Вы можете пригласить друга в команду!</b>"

                await callback.message.edit_text(message_text, reply_markup=waitlist_keyboard)
                await callback.answer()
                return

        # Новый пользователь - показываем меню регистрации
        # Добавляем в pending_registrations
        username = callback.from_user.username or "не указан"
        success = add_pending_registration(user_id, username)

        if not success:
            await callback.message.edit_text("Произошла ошибка. Попробуйте позже.")
            await callback.answer()
            return

        # Отправляем стартовое сообщение
        start_message = messages["start_message"].format(
            fee=get_participation_fee_text(),
            event_date=get_event_date_text(),
            event_time=get_event_time_text(),
            event_location=get_event_location_text(),
        )

        await callback.message.edit_text(
            start_message, reply_markup=create_start_registration_keyboard()
        )
        await callback.answer()

    dp.callback_query.register(handle_user_main_menu, F.data == "main_menu")

    # Обработчики отмены участия
    async def cancel_participation_wrapper(callback: CallbackQuery):
        await handle_cancel_participation_request(callback, bot, admin_id)

    dp.callback_query.register(
        cancel_participation_wrapper, F.data == "cancel_participation"
    )

    async def confirm_cancel_wrapper(callback: CallbackQuery):
        await handle_confirm_cancel_participation(callback, bot, admin_id)

    dp.callback_query.register(
        confirm_cancel_wrapper, F.data == "confirm_cancel_participation"
    )

    dp.callback_query.register(
        handle_decline_cancel_participation, F.data == "decline_cancel_participation"
    )

    logger.info("Упрощённые обработчики регистрации зарегистрированы")
