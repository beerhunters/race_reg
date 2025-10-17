"""
Waitlist system handlers for the beer mile registration bot.
Handles automatic notifications when slots become available.
"""

from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from logging_config import get_logger

logger = get_logger(__name__)
from handlers.utils import get_participation_fee_text
from database import (
    get_waitlist_by_role,
    get_waitlist_position,
    remove_from_waitlist,
    notify_waitlist_users,
    confirm_waitlist_participation,
    decline_waitlist_participation,
    is_user_in_waitlist,
    delete_participant,
    delete_pending_registration,
    get_participant_count_by_role,
    get_setting,
    cleanup_blocked_user,
    get_waitlist_by_user_id,
    promote_waitlist_user_by_id,
)


def create_waitlist_keyboard():
    """Create keyboard for waitlist management"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Остаться в очереди", callback_data="stay_in_waitlist"
                ),
                InlineKeyboardButton(
                    text="❌ Покинуть очередь", callback_data="leave_waitlist"
                ),
            ],
        ]
    )
    return keyboard


def create_participation_confirmation_keyboard():
    """Create keyboard for participation confirmation"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, участвую!", callback_data="confirm_participation"
                ),
                InlineKeyboardButton(
                    text="❌ Не могу участвовать", callback_data="decline_participation"
                ),
            ],
        ]
    )
    return keyboard


async def handle_waitlist_status_command(message: Message):
    """Handle /waitlist_status command - show availability or user status"""
    user_id = message.from_user.id

    # Сначала проверяем, не является ли пользователь уже участником
    from database import (
        get_participant_by_user_id,
        get_participant_count_by_role,
        get_setting,
    )

    participant = get_participant_by_user_id(user_id)

    if participant:
        name = participant[2]
        payment_status = participant[6]
        payment_emoji = "✅" if payment_status == "paid" else "⏳"
        payment_text = (
            "оплачено" if payment_status == "paid" else "ожидает подтверждения"
        )

        await message.answer(
            f"✅ <b>Вы уже участник мероприятия!</b>\n\n"
            f"📝 Имя: {name}\n"
            f"💰 Оплата: {payment_emoji} {payment_text}\n\n"
            f"💡 Используйте /start для просмотра полной информации."
        )
        return

    # Проверяем доступность мест
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

    # Если пользователь в очереди ожидания
    if is_user_in_waitlist(user_id):
        position, total_waiting = get_waitlist_position(user_id)

        if position is None:
            await message.answer(
                "❌ Произошла ошибка при получении информации об очереди."
            )
            return

        # Get waitlist data to determine role
        waitlist_data = get_waitlist_by_role()
        user_data = None
        for entry in waitlist_data:
            if entry[1] == user_id:  # user_id is at index 1
                user_data = entry
                break

        if not user_data:
            await message.answer("❌ Не удалось найти вас в очереди ожидания.")
            return

        role = user_data[5]  # role is at index 5
        role_display = "бегун" if role == "runner" else "волонтёров"

        text = (
            f"📊 <b>Ваша позиция в очереди ожидания:</b>\n\n"
            f"🔢 <b>Позиция:</b> {position} из {total_waiting}\n"
            f"👥 <b>Роль:</b> {role_display}\n"
            f"📅 <b>Дата присоединения:</b> {user_data[7][:10]}\n\n"  # join_date at index 7
            f"💡 Вы получите уведомление, когда освободится место!"
        )

        await message.answer(text, reply_markup=create_waitlist_keyboard())
        return

    # Если пользователь не участник и не в очереди - показываем общую информацию о доступности
    if available_slots > 0:
        await message.answer(
            f"🎉 <b>Есть свободные места!</b>\n\n"
            f"📊 Доступно мест: {available_slots} из {max_runners}\n"
            f"📋 В очереди ожидания: {len(get_waitlist_by_role('runner'))}\n\n"
            f"💡 Используйте /start для регистрации!"
        )
    else:
        waitlist_count = len(get_waitlist_by_role("runner"))
        await message.answer(
            f"⏳ <b>Все места заняты</b>\n\n"
            f"📊 Занято мест: {current_runners} из {max_runners}\n"
            f"📋 В очереди ожидания: {waitlist_count}\n\n"
            f"💡 Используйте /start для записи в очередь ожидания!"
        )


async def handle_waitlist_callback(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Handle waitlist management callbacks"""
    user_id = callback.from_user.id

    if callback.data == "stay_in_waitlist":
        try:
            await callback.message.edit_text(
                "✅ Вы остались в очереди ожидания. Уведомим вас, когда освободится место!"
            )
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(
                "✅ Вы остались в очереди ожидания. Уведомим вас, когда освободится место!"
            )

    elif callback.data == "leave_waitlist":
        success = remove_from_waitlist(user_id)

        if success:
            try:
                await callback.message.edit_text(
                    "❌ Вы покинули очередь ожидания. "
                    "Для повторной регистрации используйте /start."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "❌ Вы покинули очередь ожидания. "
                    "Для повторной регистрации используйте /start."
                )

            # Notify admin
            try:
                username = callback.from_user.username or "нет"
                await bot.send_message(
                    admin_id,
                    f"📤 Пользователь @{username} (ID: <code>{user_id}</code>) покинул очередь ожидания.",
                )
            except Exception as e:
                logger.error(f"Ошибка при уведомлении администратора: {e}")
        else:
            try:
                await callback.message.edit_text(
                    "❌ Произошла ошибка при удалении из очереди. Попробуйте позже."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "❌ Произошла ошибка при удалении из очереди. Попробуйте позже."
                )

    await callback.answer()


async def handle_participation_confirmation(
    callback: CallbackQuery, bot: Bot, admin_id: int
):
    """Handle participation confirmation from waitlist"""
    user_id = callback.from_user.id

    if callback.data == "confirm_participation":
        success = confirm_waitlist_participation(user_id)

        if success:
            try:
                await callback.message.edit_text(
                    "✅ <b>Участие подтверждено!</b>\n\n"
                    "Вы были переведены из очереди ожидания в список участников.\n"
                    f"💰 Не забудьте произвести оплату участия {get_participation_fee_text()}!\n\n"
                    "📱 Свяжитесь с администратором для подтверждения оплаты."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "✅ <b>Участие подтверждено!</b>\n\n"
                    "Вы были переведены из очереди ожидания в список участников.\n"
                    f"💰 Не забудьте произвести оплату участия {get_participation_fee_text()}!\n\n"
                    "📱 Свяжитесь с администратором для подтверждения оплаты."
                )

            # Notify admin about confirmation
            try:
                # Get user data from database to send notification
                from database import get_participant_by_user_id

                participant = get_participant_by_user_id(user_id)

                if participant:
                    name = participant[2]
                    target_time = participant[3]
                    username = callback.from_user.username or "нет"

                    admin_text = (
                        f"✅ <b>Подтверждение из очереди ожидания</b>\n\n"
                        f"👤 <b>Участник:</b> {name}\n"
                        f"⏰ <b>Целевое время:</b> {target_time}\n"
                        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                        f"📱 <b>Username:</b> @{username}\n\n"
                        f"💰 <b>Статус оплаты:</b> ожидает подтверждения"
                    )

                    await bot.send_message(admin_id, admin_text)

            except Exception as e:
                logger.error(
                    f"Ошибка при уведомлении администратора о подтверждении: {e}"
                )
        else:
            try:
                await callback.message.edit_text(
                    "❌ Произошла ошибка при подтверждении участия. "
                    "Возможно, место уже занято другим участником."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "❌ Произошла ошибка при подтверждении участия. "
                    "Возможно, место уже занято другим участником."
                )

    elif callback.data == "decline_participation":
        success = decline_waitlist_participation(user_id)

        if success:
            try:
                await callback.message.edit_text(
                    "❌ <b>Участие отклонено</b>\n\n"
                    "Вы остались в очереди ожидания. "
                    "Мы уведомим вас, когда освободится следующее место."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "❌ <b>Участие отклонено</b>\n\n"
                    "Вы остались в очереди ожидания. "
                    "Мы уведомим вас, когда освободится следующее место."
                )

            # Check if we can notify next person in queue
            try:
                await check_and_process_waitlist(bot, admin_id, "runner")
            except Exception as e:
                logger.error(f"Ошибка при обработке очереди после отклонения: {e}")
        else:
            try:
                await callback.message.edit_text(
                    "❌ Произошла ошибка при обработке вашего ответа. Попробуйте позже."
                )
            except TelegramBadRequest as e:
                logger.warning(f"Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(
                    "❌ Произошла ошибка при обработке вашего ответа. Попробуйте позже."
                )

    await callback.answer()


async def handle_check_waitlist_status(
    callback: CallbackQuery, bot: Bot, admin_id: int
):
    """Handle check waitlist status callback"""
    user_id = callback.from_user.id

    if not is_user_in_waitlist(user_id):
        try:
            await callback.message.edit_text(
                "❌ Вы не находитесь в очереди ожидания.\n\n"
                "Используйте /start для регистрации."
            )
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(
                "❌ Вы не находитесь в очереди ожидания.\n\n"
                "Используйте /start для регистрации."
            )
        await callback.answer()
        return

    # Get waitlist info
    waitlist_entry = get_waitlist_by_user_id(user_id)
    if waitlist_entry:
        position, total_waiting = get_waitlist_position(user_id)
        name = waitlist_entry[3]  # name at index 3
        role = waitlist_entry[5]  # role at index 5
        role_display = "бегуна" if role == "runner" else "волонтёра"
        status = waitlist_entry[8]  # status at index 8
        created_at = waitlist_entry[7]  # created_at at index 7

        # Format date
        try:
            from datetime import datetime

            date_obj = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = created_at

        # Create keyboard
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        status_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Обновить статус", callback_data="check_waitlist_status"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Покинуть очередь", callback_data="leave_waitlist"
                    )
                ],
            ]
        )

        # Status message
        status_emoji = {
            "waiting": "⏳",
            "notified": "📬",
            "confirmed": "✅",
            "declined": "❌",
        }.get(status, "❓")

        status_text = {
            "waiting": "ожидание",
            "notified": "уведомлен о месте",
            "confirmed": "подтвержден",
            "declined": "отклонен",
        }.get(status, "неизвестно")

        message_text = (
            f"📊 <b>Статус в очереди ожидания</b>\n\n"
            f"👤 <b>Имя:</b> {name}\n"
            f"🔢 <b>Позиция:</b> {position} из {total_waiting}\n"
            f"👥 <b>Роль:</b> {role_display}\n"
            f"📅 <b>Дата регистрации:</b> {formatted_date}\n"
            f"📊 <b>Статус:</b> {status_emoji} {status_text}\n\n"
        )

        if status == "notified":
            message_text += (
                f"🎉 <b>Для вас освободилось место!</b>\n"
                f"Найдите сообщение с кнопками подтверждения."
            )
        elif status == "waiting":
            message_text += (
                f"⏳ <b>Ожидайте уведомления.</b>\n"
                f"Мы сообщим, когда освободится место."
            )
        elif status == "confirmed":
            message_text += (
                f"✅ <b>Участие подтверждено!</b>\n"
                f"Ожидайте обработки администратором."
            )

        try:
            await callback.message.edit_text(message_text, reply_markup=status_keyboard)
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            await callback.message.answer(message_text, reply_markup=status_keyboard)

    await callback.answer("📊 Статус обновлен")


async def handle_admin_waitlist_command(message: Message):
    """Handle /waitlist command (admin only)"""
    waitlist_data = get_waitlist_by_role()

    if not waitlist_data:
        await message.answer("✅ Очередь ожидания пуста.")
        return

    text = "📋 <b>Очередь ожидания:</b>\n\n"

    runners = []
    volunteers = []

    for entry in waitlist_data:
        _, user_id, username, name, target_time, role, gender, join_date, _ = entry
        entry_text = (
            f"• <b>{name}</b> (@{username or 'нет'})\n"
            f"  ID: <code>{user_id}</code>\n"
            f"  Время: {target_time or 'не указано'}\n"
            f"  Дата: {join_date[:10]}\n"
        )

        if role == "runner":
            runners.append(entry_text)
        else:
            volunteers.append(entry_text)

    if runners:
        text += f"🏃 <b>Бегуны ({len(runners)}):</b>\n"
        text += "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(runners))
        text += "\n\n"

    if volunteers:
        text += f"🙌 <b>Волонтёры ({len(volunteers)}):</b>\n"
        text += "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(volunteers))

    # Split message if too long
    if len(text) > 4000:
        chunks = []
        current_chunk = "📋 <b>Очередь ожидания:</b>\n\n"

        for line in text.split("\n\n")[1:]:  # Skip header
            if len(current_chunk + line + "\n\n") > 4000:
                chunks.append(current_chunk.rstrip())
                current_chunk = line + "\n\n"
            else:
                current_chunk += line + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.rstrip())

        for chunk in chunks:
            await message.answer(chunk)
    else:
        await message.answer(text)


async def notify_waitlist_availability(bot: Bot, notified_users: list):
    """Notify users about available slots with confirmation request"""
    for user_data in notified_users:
        user_id, username, name, target_time, role, gender = user_data

        role_display = "бегуна" if role == "runner" else "волонтёра"
        text = (
            f"🎉 <b>Отличные новости!</b>\n\n"
            f"Для вас освободилось место в роли {role_display}!\n\n"
            f"📝 <b>Ваши данные:</b>\n"
            f"• Имя: {name}\n"
            f"• Целевое время: {target_time or 'не указано'}\n"
            f"• Роль: {role_display}\n\n"
            f"⏰ <b>У вас есть 24 часа для подтверждения участия!</b>\n\n"
        )

        if role == "runner":
            text += f"💰 При подтверждении не забудьте произвести оплату участия {get_participation_fee_text()}."

        try:
            await bot.send_message(
                user_id, text, reply_markup=create_participation_confirmation_keyboard()
            )
            logger.info(
                f"Уведомление о доступном месте отправлено пользователю {user_id}"
            )
        except TelegramForbiddenError:
            logger.warning(
                f"Пользователь {user_id} заблокировал бот, удаляем из всех таблиц"
            )
            cleanup_blocked_user(user_id)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")


async def check_and_process_waitlist(bot: Bot, admin_id: int, role: str):
    """Check if there are available slots and notify waitlist users"""
    max_count = get_setting(f"max_{role}s")  # max_runners or max_volunteers
    current_count = get_participant_count_by_role(role)

    if max_count is None:
        logger.error(f"Не найдена настройка max_{role}s")
        return 0

    # Ensure max_count is a valid integer
    try:
        max_count = int(max_count)
    except (ValueError, TypeError):
        logger.error(f"Некорректное значение max_{role}s: {max_count}")
        return 0

    # Ensure current_count is a valid integer
    if current_count is None:
        current_count = 0

    available_slots = max_count - current_count

    if available_slots > 0:
        notified_users = notify_waitlist_users(role, available_slots)

        if notified_users:
            await notify_waitlist_availability(bot, notified_users)

            # Notify admin
            role_display = "бегунов" if role == "runner" else "волонтёров"
            admin_text = (
                f"📢 <b>Уведомления очереди ожидания</b>\n\n"
                f"Отправлены уведомления о доступных местах для {role_display}: {len(notified_users)}\n"
                f"⏰ Время на подтверждение: 24 часа\n\n"
            )

            for user_data in notified_users:
                _, username, name, _, _, _ = user_data
                admin_text += f"• {name} (@{username or 'нет'})\n"

            try:
                await bot.send_message(admin_id, admin_text)
            except Exception as e:
                logger.error(
                    f"Ошибка при уведомлении администратора об отправке уведомлений: {e}"
                )

            return len(notified_users)

    return 0


async def handle_promote_from_waitlist(
    callback: CallbackQuery, bot: Bot, admin_id: int
):
    """Обработчик перевода пользователя из очереди ожидания в участники"""
    # Извлекаем user_id из callback_data
    user_id = int(callback.data.split("_")[3])

    # Получаем данные пользователя из очереди
    waitlist_entry = get_waitlist_by_user_id(user_id)

    if not waitlist_entry:
        await callback.message.edit_text(
            "❌ <b>Ошибка!</b>\n\n" "Пользователь не найден в очереди ожидания."
        )
        await callback.answer()
        return

    # Извлекаем данные (waitlist имеет 11 полей: id, user_id, username, name, target_time, role, gender, join_date, status, notified_date, expire_date)
    (
        _,
        _,
        username,
        name,
        target_time,
        role,
        gender,
        join_date,
        status,
        notified_date,
        expire_date,
    ) = waitlist_entry

    # Переводим пользователя с автоматическим увеличением лимита
    result = promote_waitlist_user_by_id(user_id)

    if result["success"]:
        user_name = result["user_name"]
        role = result["role"]
        old_limit = result["old_limit"]
        new_limit = result["new_limit"]

        role_display = "бегун" if role == "runner" else "волонтёров"
        gender_display = "мужской" if gender == "male" else "женский"

        await callback.message.edit_text(
            f"✅ <b>Пользователь переведён из очереди!</b>\n\n"
            f"👤 <b>Участник:</b> {user_name} (@{username})\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"⏰ <b>Целевое время:</b> {target_time}\n"
            f"👤 <b>Пол:</b> {gender_display}\n"
            f"🎭 <b>Роль:</b> {role_display}\n\n"
            f"📊 <b>Лимит {role_display}:</b> {old_limit} → {new_limit}"
        )

        # Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Вы были переведены из очереди ожидания в список участников!\n\n"
                f"📝 <b>Ваши данные:</b>\n"
                f"• Имя: {name}\n"
                f"• Целевое время: {target_time}\n"
                f"• Роль: {role_display}\n\n"
                f"💰 <b>Важно:</b> Не забудьте произвести оплату участия {get_participation_fee_text()}!\n"
                f"📱 Свяжитесь с администратором для подтверждения оплаты.\n\n"
                f"Используйте /start для просмотра полной информации о вашей регистрации.",
            )
        except TelegramForbiddenError:
            logger.warning(f"Пользователь {user_id} заблокировал бот")
            await callback.message.answer(
                f"⚠️ Внимание: пользователь заблокировал бот, уведомление не доставлено."
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении пользователя {user_id}: {e}")
    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при переводе!</b>\n\n" f"{error_message}"
        )

    await callback.answer()


def register_waitlist_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Register waitlist handlers"""

    # User commands
    dp.message.register(handle_waitlist_status_command, Command("waitlist_status"))

    # Admin commands
    dp.message.register(
        handle_admin_waitlist_command, Command("waitlist"), F.from_user.id == admin_id
    )

    # Callbacks
    async def waitlist_callback_wrapper(callback: CallbackQuery):
        await handle_waitlist_callback(callback, bot, admin_id)

    async def participation_callback_wrapper(callback: CallbackQuery):
        await handle_participation_confirmation(callback, bot, admin_id)

    async def check_status_callback_wrapper(callback: CallbackQuery):
        await handle_check_waitlist_status(callback, bot, admin_id)

    dp.callback_query.register(
        waitlist_callback_wrapper, F.data.in_(["stay_in_waitlist", "leave_waitlist"])
    )

    # Participation confirmation callbacks
    dp.callback_query.register(
        participation_callback_wrapper,
        F.data.in_(["confirm_participation", "decline_participation"]),
    )

    # Check status callback
    dp.callback_query.register(
        check_status_callback_wrapper, F.data == "check_waitlist_status"
    )

    # Promote from waitlist callback (admin only)
    async def promote_from_waitlist_wrapper(callback: CallbackQuery):
        await handle_promote_from_waitlist(callback, bot, admin_id)

    dp.callback_query.register(
        promote_from_waitlist_wrapper, F.data.startswith("promote_from_waitlist_")
    )

    logger.info("Обработчики очереди ожидания зарегистрированы")
