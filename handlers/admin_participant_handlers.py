import datetime
import sqlite3
import io
import csv
import pytz
from datetime import datetime
from aiogram import Dispatcher, Bot, F
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    Message,
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from .utils import (
    messages,
    RegistrationForm,
    logger,
    messages,
    config,
    RegistrationForm,
    create_gender_keyboard,
    create_protocol_keyboard,
    create_bib_assignment_keyboard,
    create_bib_notification_confirmation_keyboard,
    create_back_keyboard,
    create_admin_commands_keyboard,
)
from .validation import (
    validate_user_id,
    validate_result_format,
    sanitize_input,
)
from database import (
    get_all_participants,
    get_pending_registrations,
    get_participant_count,
    get_participant_count_by_role,
    get_participant_by_user_id,
    update_payment_status,
    set_bib_number,
    delete_participant,
    delete_pending_registration,
    cleanup_blocked_user,
    get_race_data,
    get_past_races,
    save_race_to_db,
    set_result,
    clear_participants,
    get_participants_by_role,
    promote_waitlist_user_by_id,
    get_waitlist_by_user_id,
    demote_participant_to_waitlist,
)


def format_date_to_moscow(date_str, format_str="%Y-%m-%d %H:%M:%S MSK"):
    """Convert ISO date string to Moscow time with custom formatting"""
    if not date_str:
        return "—"
    try:
        if "T" in date_str:  # ISO format
            # Parse as UTC and convert to Moscow time
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            utc_timezone = pytz.timezone("UTC")
            moscow_timezone = pytz.timezone("Europe/Moscow")

            if dt.tzinfo is None:
                dt = utc_timezone.localize(dt)

            moscow_dt = dt.astimezone(moscow_timezone)
            return moscow_dt.strftime(format_str)
        else:
            return date_str  # Already formatted
    except Exception as e:
        logger.warning(f"Ошибка конвертации даты {date_str}: {e}")
        return date_str


def register_admin_participant_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков управления участниками")

    # Admin category handlers
    @dp.callback_query(F.data == "category_participants")
    async def handle_participants_category(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_participants_category_keyboard

        await callback.message.edit_text(
            "👥 <b>Управление участниками</b>\n\nВыберите действие:",
            reply_markup=create_participants_category_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "category_race")
    async def handle_race_category(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_race_category_keyboard

        await callback.message.edit_text(
            "🏁 <b>Управление гонкой</b>\n\nВыберите действие:",
            reply_markup=create_race_category_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "category_notifications")
    async def handle_notifications_category(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_notifications_category_keyboard

        await callback.message.edit_text(
            "📢 <b>Управление уведомлениями</b>\n\nВыберите действие:",
            reply_markup=create_notifications_category_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "main_menu")
    async def handle_main_menu(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_admin_commands_keyboard

        await callback.message.edit_text(
            "🔧 <b>Админ-панель</b>\n\nВыберите категорию:",
            reply_markup=create_admin_commands_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "admin_menu")
    async def handle_admin_menu(callback: CallbackQuery):
        """Handle admin menu button - return to main admin panel"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        await callback.message.edit_text(
            "🔧 <b>Админ-панель</b>\n\nВыберите категорию:",
            reply_markup=create_admin_commands_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "category_settings")
    async def handle_settings_category(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_settings_category_keyboard

        await callback.message.edit_text(
            "⚙️ <b>Настройки системы</b>\n\nВыберите действие:",
            reply_markup=create_settings_category_keyboard(),
        )
        await callback.answer()

    @dp.callback_query(F.data == "category_media")
    async def handle_media_category(callback: CallbackQuery):
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        from .utils import create_media_category_keyboard

        await callback.message.edit_text(
            "🎨 <b>Управление медиа</b>\n\nВыберите действие:",
            reply_markup=create_media_category_keyboard(),
        )
        await callback.answer()

    async def show_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["set_reg_end_date_access_denied"])
            return
        logger.info(f"Команда /participants от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        participants = get_all_participants()
        if not participants:
            await message.answer(
                "👥 <b>Список участников пуст</b>\n\nНикто еще не зарегистрировался."
            )
            return

        # Build beautiful participant list
        text = "👥 <b>Список участников</b>\n\n"
        runners = []
        volunteers = []

        for participant in participants:
            (
                user_id_p,
                username,
                name,
                target_time,
                role,
                reg_date,
                payment_status,
                bib_number,
                result,
                gender,
                category,
                cluster,
            ) = participant

            # Format payment status
            if role == "runner":
                payment_emoji = "✅" if payment_status == "paid" else "❌"
                payment_text = "Оплачено" if payment_status == "paid" else "Не оплачено"
                payment_info = f"{payment_emoji} {payment_text}"
            else:
                payment_info = "—"

            # Format bib number
            bib_info = f"№{bib_number}" if bib_number else "—"

            # Format username
            username_info = f"@{username}" if username else "—"

            # Format target time
            time_info = target_time if target_time else "—"

            # Format category and cluster
            category_info = ""
            if category:
                category_emoji = {
                    "СуперЭлита": "💎",
                "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                }.get(category, "📂")
                category_info += f"📂 Категория: {category_emoji} {category}\n"

            cluster_info = ""
            if cluster:
                cluster_emoji = {"A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴", "F": "🅵", "G": "🅶"}.get(
                    cluster, "🎯"
                )
                cluster_info += f"🎯 Кластер: {cluster_emoji} {cluster}\n"

            participant_line = (
                f"<b>{name}</b>\n"
                f"🆔 ID: <code>{user_id_p}</code>\n"
                f"📱 TG: {username_info}\n"
                f"⏰ Время: {time_info}\n"
                f"💰 Оплата: {payment_info}\n"
                f"🏷 Номер: {bib_info}\n"
                f"{category_info}"
                f"{cluster_info}"
            )

            if role == "runner":
                runners.append(participant_line)
            else:
                volunteers.append(participant_line)

        # Add runners section
        if runners:
            text += f"🏃 <b>Бегуны ({len(runners)}):</b>\n\n"
            for i, runner in enumerate(runners, 1):
                text += f"{i}. {runner}\n"

        # Add volunteers section
        if volunteers:
            text += f"🙌 <b>Волонтёры ({len(volunteers)}):</b>\n\n"
            for i, volunteer in enumerate(volunteers, 1):
                text += f"{i}. {volunteer}\n"

        # Split long messages
        if len(text) > 4000:
            chunks = []
            if runners:
                chunk1 = f"👥 <b>Список участников</b>\n\n🏃 <b>Бегуны ({len(runners)}):</b>\n\n"
                for i, runner in enumerate(runners, 1):
                    if len(chunk1 + f"{i}. {runner}\n") > 4000:
                        chunks.append(chunk1.rstrip())
                        chunk1 = f"🏃 <b>Бегуны (продолжение):</b>\n\n{i}. {runner}\n"
                    else:
                        chunk1 += f"{i}. {runner}\n"
                chunks.append(chunk1.rstrip())

            if volunteers:
                chunk2 = f"🙌 <b>Волонтёры ({len(volunteers)}):</b>\n\n"
                for i, volunteer in enumerate(volunteers, 1):
                    if len(chunk2 + f"{i}. {volunteer}\n") > 4000:
                        chunks.append(chunk2.rstrip())
                        chunk2 = (
                            f"🙌 <b>Волонтёры (продолжение):</b>\n\n{i}. {volunteer}\n"
                        )
                    else:
                        chunk2 += f"{i}. {volunteer}\n"
                chunks.append(chunk2.rstrip())

            for chunk in chunks:
                await message.answer(chunk)
        else:
            await message.answer(text)

        if isinstance(event, CallbackQuery):
            await event.answer()

    @dp.message(Command("participants", "список", "участники"))
    async def cmd_show_participants(message: Message):
        await show_participants(message)

    @dp.callback_query(F.data == "admin_participants")
    async def callback_show_participants(callback_query: CallbackQuery):
        await show_participants(callback_query)

    async def show_pending_registrations(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["pending_access_denied"])
            return
        logger.info(f"Команда /pending от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        # Get counts for pending and waitlist
        pending_users = get_pending_registrations()

        # Get waitlist count
        from database import get_waitlist_by_role

        waitlist_data = get_waitlist_by_role()

        text = "⏳ <b>Незавершенные регистрации</b>\n\n"

        # Summary
        text += f"📊 <b>Статистика:</b>\n"
        text += f"• Pending регистрации: {len(pending_users)}\n"
        text += f"• В очереди ожидания: {len(waitlist_data)}\n\n"

        # Pending registrations detail
        if pending_users:
            text += f"📋 <b>Pending регистрации ({len(pending_users)}):</b>\n\n"
            for i, (user_id_p, username, name, target_time, role) in enumerate(
                pending_users, 1
            ):
                username_info = f"@{username}" if username else "—"
                name_info = name if name else "—"
                role_info = "бегун" if role == "runner" else "волонтёр" if role else "—"

                text += (
                    f"{i}. ID: <code>{user_id_p}</code>\n"
                    f"   TG: {username_info}\n"
                    f"   Имя: {name_info}\n"
                    f"   Роль: {role_info}\n\n"
                )

        # Waitlist detail
        if waitlist_data:
            text += f"📋 <b>Очередь ожидания ({len(waitlist_data)}):</b>\n\n"
            for i, entry in enumerate(waitlist_data, 1):
                (
                    _,
                    user_id_w,
                    username_w,
                    name_w,
                    target_time_w,
                    role_w,
                    gender_w,
                    join_date,
                    status,
                ) = entry
                username_info = f"@{username_w}" if username_w else "—"
                status_info = {
                    "waiting": "⏳ Ожидает",
                    "notified": "🔔 Уведомлен",
                    "confirmed": "✅ Подтвержден",
                    "declined": "❌ Отклонен",
                }.get(status, status)

                text += (
                    f"{i}. <b>{name_w}</b>\n"
                    f"   ID: <code>{user_id_w}</code>\n"
                    f"   TG: {username_info}\n"
                    f"   Статус: {status_info}\n"
                    f"   Дата: {join_date[:10] if join_date else '—'}\n\n"
                )

        if not pending_users and not waitlist_data:
            text += "✅ Все регистрации завершены, очередь ожидания пуста."

        # Split if too long
        if len(text) > 4000:
            chunks = []
            current = f"⏳ <b>Незавершенные регистрации</b>\n\n📊 <b>Статистика:</b>\n• Pending регистрации: {len(pending_users)}\n• В очереди ожидания: {len(waitlist_data)}\n\n"

            if pending_users:
                pending_part = (
                    f"📋 <b>Pending регистрации ({len(pending_users)}):</b>\n\n"
                )
                for i, (user_id_p, username, name, target_time, role) in enumerate(
                    pending_users, 1
                ):
                    username_info = f"@{username}" if username else "—"
                    name_info = name if name else "—"
                    role_info = (
                        "бегун" if role == "runner" else "волонтёр" if role else "—"
                    )

                    entry = (
                        f"{i}. ID: <code>{user_id_p}</code>\n"
                        f"   TG: {username_info}\n"
                        f"   Имя: {name_info}\n"
                        f"   Роль: {role_info}\n\n"
                    )

                    if len(current + pending_part + entry) > 4000:
                        chunks.append(current + pending_part.rstrip())
                        current = ""
                        pending_part = f"📋 <b>Pending (продолжение):</b>\n\n{entry}"
                    else:
                        pending_part += entry

                current += pending_part

            if waitlist_data:
                waitlist_part = (
                    f"📋 <b>Очередь ожидания ({len(waitlist_data)}):</b>\n\n"
                )
                for i, entry in enumerate(waitlist_data, 1):
                    (
                        _,
                        user_id_w,
                        username_w,
                        name_w,
                        target_time_w,
                        role_w,
                        gender_w,
                        join_date,
                        status,
                    ) = entry
                    username_info = f"@{username_w}" if username_w else "—"
                    status_info = {
                        "waiting": "⏳ Ожидает",
                        "notified": "🔔 Уведомлен",
                        "confirmed": "✅ Подтвержден",
                        "declined": "❌ Отклонен",
                    }.get(status, status)

                    w_entry = (
                        f"{i}. <b>{name_w}</b>\n"
                        f"   ID: <code>{user_id_w}</code>\n"
                        f"   TG: {username_info}\n"
                        f"   Статус: {status_info}\n"
                        f"   Дата: {join_date[:10] if join_date else '—'}\n\n"
                    )

                    if len(current + waitlist_part + w_entry) > 4000:
                        chunks.append(current + waitlist_part.rstrip())
                        current = ""
                        waitlist_part = f"📋 <b>Очередь (продолжение):</b>\n\n{w_entry}"
                    else:
                        waitlist_part += w_entry

                current += waitlist_part

            if current.strip():
                chunks.append(current.rstrip())

            for chunk in chunks:
                await message.answer(chunk)
        else:
            await message.answer(text)

    @dp.message(Command("pending"))
    async def cmd_show_pending_registrations(message: Message):
        await show_pending_registrations(message)

    @dp.callback_query(F.data == "admin_pending")
    async def callback_show_pending_registrations(callback_query: CallbackQuery):
        await show_pending_registrations(callback_query)

    async def show_stats(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["pending_access_denied"])
            return
        logger.info(f"Команда /stats от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()

                # Get counts
                cursor.execute(
                    "SELECT COUNT(*) FROM participants WHERE payment_status = 'paid'"
                )
                paid_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM participants WHERE role = 'runner'"
                )
                runner_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM participants WHERE role = 'volunteer'"
                )
                volunteer_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM pending_registrations")
                pending_reg_count = cursor.fetchone()[0]

                # Get settings
                cursor.execute("SELECT value FROM settings WHERE key = 'max_runners'")
                max_runners_result = cursor.fetchone()
                max_runners = int(max_runners_result[0]) if max_runners_result else 0

                cursor.execute("SELECT value FROM settings WHERE key = 'reg_end_date'")
                reg_end_date_result = cursor.fetchone()
                reg_end_date = (
                    reg_end_date_result[0] if reg_end_date_result else "не установлена"
                )

                # Get waitlist count
                from database import get_waitlist_by_role

                waitlist_data = get_waitlist_by_role()
                waitlist_count = len(waitlist_data)

            # Build beautiful statistics message
            text = "📊 <b>Статистика регистрации</b>\n\n"

            # Registration deadline
            text += f"📅 <b>Дата окончания регистрации:</b>\n{reg_end_date}\n\n"

            # Slots and registration stats
            text += f"🎯 <b>Слоты и регистрация:</b>\n"
            text += f"• Максимум бегунов: {max_runners}\n"
            text += f"• Зарегистрировано бегунов: {runner_count}\n"
            text += f"• Доступных слотов: {max_runners - runner_count}\n"
            text += f"• Зарегистрировано волонтёров: {volunteer_count}\n"
            text += f"• Всего участников: {runner_count + volunteer_count}\n\n"

            # Payment statistics
            text += f"💰 <b>Статистика оплаты:</b>\n"
            text += f"• Оплатили: {paid_count}\n"
            text += f"• Не оплатили: {runner_count - paid_count}\n"
            if runner_count > 0:
                payment_percentage = round((paid_count / runner_count) * 100, 1)
                text += f"• Процент оплаты: {payment_percentage}%\n\n"
            else:
                text += f"• Процент оплаты: 0%\n\n"

            # Queue statistics
            text += f"⏳ <b>Очереди и pending:</b>\n"
            text += f"• Незавершённых регистраций: {pending_reg_count}\n"
            text += f"• В очереди ожидания: {waitlist_count}\n\n"

            # Registration status - check date first, then limits
            status_emoji = ""
            status_text = ""
            
            # Check if registration period has ended
            registration_closed_by_date = False
            if reg_end_date != "не установлена":
                try:
                    from datetime import datetime
                    from pytz import timezone
                    
                    end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
                    moscow_tz = timezone("Europe/Moscow")
                    end_date = moscow_tz.localize(end_date)
                    current_time = datetime.now(moscow_tz)
                    registration_closed_by_date = current_time > end_date
                except Exception as e:
                    logger.warning(f"Ошибка при проверке даты окончания регистрации: {e}")
            
            # Determine status based on date and limits
            if registration_closed_by_date:
                status_emoji = "🔴"
                status_text = "Регистрация закрыта (время вышло)"
            elif runner_count >= max_runners:
                status_emoji = "🔴" 
                status_text = "Регистрация закрыта (достигнут лимит)"
            elif waitlist_count > 0:
                status_emoji = "🟡"
                status_text = "Есть очередь ожидания"
            else:
                status_emoji = "🟢"
                status_text = "Регистрация открыта"
            
            text += f"{status_emoji} <b>Статус:</b> {status_text}\n"

            await message.answer(text)

        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await message.answer(
                "❌ Ошибка при получении статистики. Попробуйте снова."
            )
        except Exception as e:
            logger.error(f"Общая ошибка в show_stats: {e}")
            await message.answer("❌ Произошла ошибка при формировании статистики.")

    @dp.message(Command("stats", "статистика"))
    async def cmd_show_stats(message: Message):
        await show_stats(message)

    @dp.callback_query(F.data == "admin_stats")
    async def callback_show_stats(callback_query: CallbackQuery):
        await show_stats(callback_query)

    async def mark_as_paid(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["paid_access_denied"])
            return
        logger.info(f"Команда /paid от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_paid_ID"])
        await state.set_state(RegistrationForm.waiting_for_paid_id)

    @dp.message(RegistrationForm.waiting_for_paid_id)
    async def process_mark_as_paid(message: Message, state: FSMContext):
        user_input = sanitize_input(message.text, 20)

        is_valid, error_message = validate_user_id(user_input)
        if not is_valid:
            await message.answer(f"❌ {error_message}")
            return

        user_id = int(user_input)
        participant = get_participant_by_user_id(user_id)
        if participant:
            update_payment_status(user_id, "paid")
            await message.answer(messages["paid_success"].format(name=participant[2]))
            try:
                await bot.send_message(
                    chat_id=user_id, text=messages["payment_confirmed"]
                )
                logger.info(
                    f"Уведомление об оплате отправлено пользователю user_id={user_id}"
                )
            except TelegramForbiddenError:
                logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                cleanup_blocked_user(user_id)
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=participant[2],
                            username=participant[1] or "не указан",
                            user_id=user_id,
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
                logger.error(
                    f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                )
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("paid"))
    async def cmd_mark_as_paid(message: Message, state: FSMContext):
        await mark_as_paid(message, state)

    @dp.callback_query(F.data == "admin_paid")
    async def callback_mark_as_paid(callback_query: CallbackQuery, state: FSMContext):
        await mark_as_paid(callback_query, state)

    async def set_bib(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["set_bib_access_denied"])
            return
        logger.info(f"Команда /set_bib от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_bib_ID"])
        await state.set_state(RegistrationForm.waiting_for_bib)

    @dp.message(RegistrationForm.waiting_for_bib)
    async def process_set_bib(message: Message, state: FSMContext):
        user_input = sanitize_input(message.text, 30)
        parts = user_input.split()

        if len(parts) != 2:
            await message.answer(messages["set_bib_usage"])
            return

        # Validate user ID
        is_valid, error_message = validate_user_id(parts[0])
        if not is_valid:
            await message.answer(
                f"❌ Неверный ID пользователя: {error_message}",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return

        user_id = int(parts[0])

        # Handle bib number - preserve leading zeros as string
        bib_number = parts[1].strip()

        # Validate that bib number contains only digits
        if not bib_number.isdigit():
            await message.answer(
                "❌ Номер должен содержать только цифры.",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return

        # Get existing bib numbers to check for duplicates
        all_participants = get_all_participants()
        existing_bibs = [
            p[7] for p in all_participants if p[7] is not None
        ]  # bib_number is at index 7

        # Check for duplicate bib numbers
        if bib_number in existing_bibs:
            await message.answer(
                f"❌ Номер {bib_number} уже присвоен другому участнику.",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return
        participant = get_participant_by_user_id(user_id)
        if participant:
            success = set_bib_number(user_id, bib_number)
            if success:
                await message.answer(
                    messages["set_bib_success"].format(
                        name=participant[2], bib_number=bib_number
                    )
                )
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=messages["bib_number_assigned"].format(
                            bib_number=bib_number
                        ),
                    )
                    logger.info(
                        f"Уведомление о присвоении номера {bib_number} отправлено пользователю user_id={user_id}"
                    )
                except TelegramForbiddenError:
                    logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                    cleanup_blocked_user(user_id)
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=participant[2],
                                username=participant[1] or "не указан",
                                user_id=user_id,
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
                    logger.error(
                        f"Ошибка при отправке уведомления о номере пользователю user_id={user_id}: {e}"
                    )
            else:
                await message.answer("Ошибка при присвоении номера. Попробуйте снова.")
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("set_bib"))
    async def cmd_set_bib(message: Message, state: FSMContext):
        await set_bib(message, state)

    @dp.callback_query(F.data == "admin_set_bib")
    async def callback_set_bib(callback_query: CallbackQuery, state: FSMContext):
        await start_sequential_bib_assignment(callback_query, state)

    async def remove_participant(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["remove_access_denied"])
            return
        logger.info(f"Команда /remove_participant от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_for_remove_id"])
        await state.set_state(RegistrationForm.waiting_for_remove_id)

    @dp.message(RegistrationForm.waiting_for_remove_id)
    async def process_remove_participant(message: Message, state: FSMContext):
        user_input = sanitize_input(message.text, 20)

        is_valid, error_message = validate_user_id(user_input)
        if not is_valid:
            await message.answer(f"❌ {error_message}")
            return

        user_id = int(user_input)
        participant = get_participant_by_user_id(user_id)

        if participant:
            participant_role = participant[4]  # role is at index 4
            success = delete_participant(user_id)

            if success:
                await message.answer(
                    messages["remove_success"].format(name=participant[2])
                )

                # Process waitlist after removing participant
                try:
                    from .waitlist_handlers import check_and_process_waitlist

                    await check_and_process_waitlist(bot, admin_id, participant_role)
                except Exception as e:
                    logger.error(f"Ошибка при обработке очереди ожидания: {e}")
                try:
                    await bot.send_message(
                        chat_id=user_id, text=messages["remove_user_notification"]
                    )
                    logger.info(
                        f"Уведомление об удалении отправлено пользователю user_id={user_id}"
                    )
                except TelegramForbiddenError:
                    logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                    cleanup_blocked_user(user_id)
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=participant[2],
                                username=participant[1] or "не указан",
                                user_id=user_id,
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
                    logger.error(
                        f"Ошибка при отправке уведомления об удалении пользователю user_id={user_id}: {e}"
                    )
            else:
                await message.answer("Ошибка при удалении участника. Попробуйте снова.")
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("remove"))
    async def cmd_remove(message: Message, state: FSMContext):
        await remove_participant(message, state)

    @dp.callback_query(F.data == "admin_remove")
    async def callback_remove(callback_query: CallbackQuery, state: FSMContext):
        await remove_participant(callback_query, state)

    async def promote_from_waitlist(event: [Message, CallbackQuery], state: FSMContext):
        """Promote user from waitlist to participants by user ID"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен. Эта команда только для администратора.")
            return
            
        logger.info(f"Команда /promote_from_waitlist от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        # Extract user_id from command text
        command_text = event.text if hasattr(event, 'text') and event.text else ""
        
        if not command_text or len(command_text.split()) < 2:
            await message.answer(
                "❌ <b>Использование:</b> /promote_from_waitlist ID_пользователя\n\n"
                "<b>Пример:</b> /promote_from_waitlist 123456789\n\n"
                "Эта команда переведет пользователя из очереди ожидания в участники "
                "и автоматически увеличит лимит участников."
            )
            return

        try:
            target_user_id = int(command_text.split()[1])
        except (ValueError, IndexError):
            await message.answer("❌ Некорректный ID пользователя. Укажите числовой ID.")
            return

        # Check if user exists in waitlist
        waitlist_user = get_waitlist_by_user_id(target_user_id)
        if not waitlist_user:
            await message.answer(f"❌ Пользователь с ID <code>{target_user_id}</code> не найден в очереди ожидания.")
            return

        # Get user name from waitlist for display
        user_name = waitlist_user[3]  # name is at index 3
        user_role = waitlist_user[5]  # role is at index 5
        
        # Promote user
        result = promote_waitlist_user_by_id(target_user_id)
        
        if result["success"]:
            role_display = "бегунов" if user_role == "runner" else "волонтёров"
            success_message = (
                f"✅ <b>Пользователь добавлен в участники!</b>\n\n"
                f"👤 <b>Имя:</b> {result['user_name']}\n"
                f"🆔 <b>ID:</b> <code>{result['user_id']}</code>\n"
                f"👥 <b>Роль:</b> {user_role}\n\n"
                f"📊 <b>Лимит {role_display}:</b> {result['old_limit']} → {result['new_limit']}\n\n"
                f"Пользователь переведен из очереди ожидания в список участников. "
                f"Лимит автоматически увеличен."
            )
            await message.answer(success_message)
            
            # Notify the user
            try:
                await bot.send_message(
                    target_user_id,
                    f"🎉 <b>Отличные новости!</b>\n\n"
                    f"Вы переведены из очереди ожидания в список участников!\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {result['user_name']}\n"
                    f"• Роль: {user_role}\n\n"
                    f"💰 Не забудьте произвести оплату участия, если требуется!"
                )
                logger.info(f"Уведомление о переводе отправлено пользователю {target_user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
                
        else:
            error_message = f"❌ <b>Ошибка при переводе пользователя:</b>\n\n{result['error']}"
            await message.answer(error_message)

    @dp.message(Command("promote_from_waitlist"))
    async def cmd_promote_from_waitlist(message: Message, state: FSMContext):
        await promote_from_waitlist(message, state)

    async def demote_to_waitlist(event: [Message, CallbackQuery], state: FSMContext):
        """Move participant to waitlist by user ID"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен. Эта команда только для администратора.")
            return
            
        logger.info(f"Команда /demote_to_waitlist от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        # Extract user_id from command text
        command_text = event.text if hasattr(event, 'text') and event.text else ""
        
        if not command_text or len(command_text.split()) < 2:
            await message.answer(
                "❌ <b>Использование:</b> /demote_to_waitlist ID_пользователя\n\n"
                "<b>Пример:</b> /demote_to_waitlist 123456789\n\n"
                "Эта команда переведет участника в очередь ожидания "
                "и автоматически уменьшит лимит участников."
            )
            return

        try:
            target_user_id = int(command_text.split()[1])
        except (ValueError, IndexError):
            await message.answer("❌ Некорректный ID пользователя. Укажите числовой ID.")
            return

        # Check if user exists in participants
        participant = get_participant_by_user_id(target_user_id)
        if not participant:
            await message.answer(f"❌ Пользователь с ID <code>{target_user_id}</code> не найден в списке участников.")
            return

        # Get user name from participants for display
        user_name = participant[2]  # name is at index 2
        user_role = participant[4]  # role is at index 4
        
        # Demote user
        result = demote_participant_to_waitlist(target_user_id)
        
        if result["success"]:
            role_display = "бегунов" if user_role == "runner" else "волонтёров"
            success_message = (
                f"✅ <b>Пользователь переведен в очередь ожидания!</b>\n\n"
                f"👤 <b>Имя:</b> {result['user_name']}\n"
                f"🆔 <b>ID:</b> <code>{result['user_id']}</code>\n"
                f"👥 <b>Роль:</b> {user_role}\n\n"
                f"📊 <b>Лимит {role_display}:</b> {result['old_limit']} → {result['new_limit']}\n\n"
                f"Пользователь переведен из списка участников в очередь ожидания. "
                f"Лимит автоматически уменьшен."
            )
            await message.answer(success_message)
            
            # Notify the user
            try:
                await bot.send_message(
                    target_user_id,
                    f"📋 <b>Изменение статуса участия</b>\n\n"
                    f"Вы переведены в очередь ожидания.\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {result['user_name']}\n"
                    f"• Роль: {user_role}\n\n"
                    f"💡 Мы уведомим вас, когда снова освободится место!"
                )
                logger.info(f"Уведомление о переводе в очередь отправлено пользователю {target_user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
                
        else:
            error_message = f"❌ <b>Ошибка при переводе пользователя:</b>\n\n{result['error']}"
            await message.answer(error_message)

    @dp.message(Command("demote_to_waitlist"))
    async def cmd_demote_to_waitlist(message: Message, state: FSMContext):
        await demote_to_waitlist(message, state)

    @dp.callback_query(F.data == "admin_promote_from_waitlist")
    async def callback_promote_from_waitlist(callback_query: CallbackQuery, state: FSMContext):
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return
            
        await callback_query.message.edit_text(
            "⬆️ <b>Перевод из очереди ожидания</b>\n\n"
            "Введите ID пользователя, которого нужно перевести из очереди ожидания в участники:\n\n"
            "💡 ID можно найти в списке очереди ожидания (/waitlist)",
            reply_markup=create_back_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_promote_id)
        await callback_query.answer()

    @dp.message(RegistrationForm.waiting_for_promote_id)
    async def process_promote_id(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            return

        await message.delete()
        
        try:
            target_user_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Некорректный ID пользователя. Укажите числовой ID.")
            return

        # Check if user exists in waitlist
        waitlist_user = get_waitlist_by_user_id(target_user_id)
        if not waitlist_user:
            await message.answer(
                f"❌ Пользователь с ID <code>{target_user_id}</code> не найден в очереди ожидания.\n\n"
                "Проверьте ID в списке очереди ожидания (/waitlist).",
                reply_markup=create_back_keyboard()
            )
            return

        # Get user name from waitlist for display
        user_name = waitlist_user[3]  # name is at index 3
        user_role = waitlist_user[5]  # role is at index 5
        
        # Promote user
        result = promote_waitlist_user_by_id(target_user_id)
        
        if result["success"]:
            role_display = "бегунов" if user_role == "runner" else "волонтёров"
            success_message = (
                f"✅ <b>Пользователь добавлен в участники!</b>\n\n"
                f"👤 <b>Имя:</b> {result['user_name']}\n"
                f"🆔 <b>ID:</b> <code>{result['user_id']}</code>\n"
                f"👥 <b>Роль:</b> {user_role}\n\n"
                f"📊 <b>Лимит {role_display}:</b> {result['old_limit']} → {result['new_limit']}\n\n"
                f"Пользователь переведен из очереди ожидания в список участников. "
                f"Лимит автоматически увеличен."
            )
            await message.answer(success_message, reply_markup=create_back_keyboard())
            
            # Notify the user
            try:
                await bot.send_message(
                    target_user_id,
                    f"🎉 <b>Отличные новости!</b>\n\n"
                    f"Вы переведены из очереди ожидания в список участников!\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {result['user_name']}\n"
                    f"• Роль: {user_role}\n\n"
                    f"💰 Не забудьте произвести оплату участия, если требуется!"
                )
                logger.info(f"Уведомление о переводе отправлено пользователю {target_user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
                
        else:
            error_message = f"❌ <b>Ошибка при переводе пользователя:</b>\n\n{result['error']}"
            await message.answer(error_message, reply_markup=create_back_keyboard())

        await state.clear()

    @dp.callback_query(F.data == "admin_demote_to_waitlist")
    async def callback_demote_to_waitlist(callback_query: CallbackQuery, state: FSMContext):
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return
            
        await callback_query.message.edit_text(
            "⬇️ <b>Перевод в очередь ожидания</b>\n\n"
            "Введите ID участника, которого нужно перевести в очередь ожидания:\n\n"
            "💡 ID можно найти в списке участников (/participants)",
            reply_markup=create_back_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_demote_id)
        await callback_query.answer()

    @dp.message(RegistrationForm.waiting_for_demote_id)
    async def process_demote_id(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            return

        await message.delete()
        
        try:
            target_user_id = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Некорректный ID пользователя. Укажите числовой ID.")
            return

        # Check if user exists in participants
        participant = get_participant_by_user_id(target_user_id)
        if not participant:
            await message.answer(
                f"❌ Пользователь с ID <code>{target_user_id}</code> не найден в списке участников.\n\n"
                "Проверьте ID в списке участников (/participants).",
                reply_markup=create_back_keyboard()
            )
            return

        # Get user name from participants for display
        user_name = participant[2]  # name is at index 2
        user_role = participant[4]  # role is at index 4
        
        # Demote user
        result = demote_participant_to_waitlist(target_user_id)
        
        if result["success"]:
            role_display = "бегунов" if user_role == "runner" else "волонтёров"
            success_message = (
                f"✅ <b>Пользователь переведен в очередь ожидания!</b>\n\n"
                f"👤 <b>Имя:</b> {result['user_name']}\n"
                f"🆔 <b>ID:</b> <code>{result['user_id']}</code>\n"
                f"👥 <b>Роль:</b> {user_role}\n\n"
                f"📊 <b>Лимит {role_display}:</b> {result['old_limit']} → {result['new_limit']}\n\n"
                f"Пользователь переведен из списка участников в очередь ожидания. "
                f"Лимит автоматически уменьшен."
            )
            await message.answer(success_message, reply_markup=create_back_keyboard())
            
            # Notify the user
            try:
                await bot.send_message(
                    target_user_id,
                    f"📋 <b>Изменение статуса участия</b>\n\n"
                    f"Вы переведены в очередь ожидания.\n\n"
                    f"📝 <b>Ваши данные:</b>\n"
                    f"• Имя: {result['user_name']}\n"
                    f"• Роль: {user_role}\n\n"
                    f"💡 Мы уведомим вас, когда снова освободится место!"
                )
                logger.info(f"Уведомление о переводе в очередь отправлено пользователю {target_user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
                
        else:
            error_message = f"❌ <b>Ошибка при переводе пользователя:</b>\n\n{result['error']}"
            await message.answer(error_message, reply_markup=create_back_keyboard())

        await state.clear()

    async def export_participants(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["export_access_denied"])
            return
        logger.info(f"Команда /export от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        try:
            delimiter = config.get("csv_delimiter", ";")
            output = io.StringIO()

            # Use global function for date formatting

            # Export all tables to one CSV file
            writer = csv.writer(
                output,
                lineterminator="\n",
                delimiter=delimiter,
                quoting=csv.QUOTE_MINIMAL,
            )

            # 1. Participants table
            writer.writerow(["=== УЧАСТНИКИ ==="])
            writer.writerow(
                [
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
                    "Кластер",
                ]
            )

            participants = get_all_participants()
            for participant in participants:
                (
                    user_id_p,
                    username,
                    name,
                    target_time,
                    role,
                    reg_date,
                    payment_status,
                    bib_number,
                    result,
                    gender,
                    category,
                    cluster,
                ) = participant
                writer.writerow(
                    [
                        user_id_p,
                        username or "—",
                        name,
                        target_time or "—",
                        role,
                        format_date_to_moscow(reg_date),
                        payment_status,
                        bib_number or "—",
                        result or "—",
                        gender or "—",
                        category or "—",
                        cluster or "—",
                    ]
                )

            writer.writerow([])  # Empty row separator

            # 2. Pending registrations table
            writer.writerow(["=== НЕЗАВЕРШЕННЫЕ РЕГИСТРАЦИИ ==="])
            writer.writerow(["User ID", "Username", "Имя", "Целевое время", "Роль"])

            pending_users = get_pending_registrations()
            for pending in pending_users:
                user_id_p, username, name, target_time, role = pending
                writer.writerow(
                    [
                        user_id_p,
                        username or "—",
                        name or "—",
                        target_time or "—",
                        role or "—",
                    ]
                )

            writer.writerow([])  # Empty row separator

            # 3. Waitlist table
            writer.writerow(["=== ОЧЕРЕДЬ ОЖИДАНИЯ ==="])
            writer.writerow(
                [
                    "ID",
                    "User ID",
                    "Username",
                    "Имя",
                    "Целевое время",
                    "Роль",
                    "Пол",
                    "Дата присоединения",
                    "Статус",
                ]
            )

            from database import get_waitlist_by_role

            waitlist_data = get_waitlist_by_role()
            for waitlist_entry in waitlist_data:
                (
                    id_w,
                    user_id_w,
                    username_w,
                    name_w,
                    target_time_w,
                    role_w,
                    gender_w,
                    join_date,
                    status,
                ) = waitlist_entry
                writer.writerow(
                    [
                        id_w,
                        user_id_w,
                        username_w or "—",
                        name_w or "—",
                        target_time_w or "—",
                        role_w or "—",
                        gender_w or "—",
                        format_date_to_moscow(join_date),
                        status or "—",
                    ]
                )

            writer.writerow([])  # Empty row separator

            # 4. Settings table
            writer.writerow(["=== НАСТРОЙКИ ==="])
            writer.writerow(["Ключ", "Значение"])

            try:
                with sqlite3.connect(
                    "/app/data/race_participants.db", timeout=10
                ) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT key, value FROM settings")
                    settings = cursor.fetchall()
                    for key, value in settings:
                        writer.writerow([key, value])
            except sqlite3.Error as e:
                logger.error(f"Ошибка при получении настроек: {e}")
                writer.writerow(["Ошибка", f"Не удалось получить настройки: {e}"])

            writer.writerow([])  # Empty row separator

            # 5. Bot users table
            writer.writerow(["=== ПОЛЬЗОВАТЕЛИ БОТА ==="])
            writer.writerow(
                [
                    "User ID",
                    "Username",
                    "Имя",
                    "Фамилия",
                    "Первое взаимодействие",
                    "Последнее взаимодействие",
                ]
            )

            try:
                from database import get_all_bot_users

                bot_users = get_all_bot_users()
                for bot_user in bot_users:
                    if len(bot_user) >= 6:
                        (
                            user_id_b,
                            username_b,
                            first_name,
                            last_name,
                            first_interaction,
                            last_interaction,
                        ) = bot_user
                        # Format dates
                        first_date = format_date_to_moscow(first_interaction)
                        last_date = format_date_to_moscow(last_interaction)
                        writer.writerow(
                            [
                                user_id_b,
                                username_b or "—",
                                first_name or "—",
                                last_name or "—",
                                first_date,
                                last_date,
                            ]
                        )
                    else:
                        logger.warning(
                            f"Некорректный формат данных пользователя: {bot_user}"
                        )
            except Exception as e:
                logger.error(f"Ошибка при получении пользователей бота: {e}")
                writer.writerow(
                    [
                        "Ошибка",
                        f"Не удалось получить пользователей: {e}",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

            csv_content = output.getvalue()
            output.close()

            # Generate timestamp for filename (Moscow time)
            moscow_timezone = pytz.timezone("Europe/Moscow")
            moscow_now = datetime.now(moscow_timezone)
            timestamp = moscow_now.strftime("%Y%m%d_%H%M%S")
            filename = f"beer_mile_export_{timestamp}.csv"

            logger.info(
                f"CSV-файл сформирован, размер: {len(csv_content)} символов, разделитель: {delimiter}"
            )

            csv_bytes = csv_content.encode("utf-8-sig")
            await message.answer_document(
                document=BufferedInputFile(csv_bytes, filename=filename)
            )

            # Statistics message
            stats_text = f"✅ <b>Экспорт завершён</b>\n\n"
            stats_text += f"📊 Экспортировано данных:\n"
            stats_text += f"• Участников: {len(participants)}\n"
            stats_text += f"• Незавершённых регистраций: {len(pending_users)}\n"
            stats_text += f"• В очереди ожидания: {len(waitlist_data)}\n"
            try:
                from database import get_all_bot_users

                bot_users = get_all_bot_users()
                stats_text += f"• Пользователей бота: {len(bot_users)}\n"
            except:
                stats_text += f"• Пользователей бота: н/д\n"

            await message.answer(stats_text)
            logger.info(
                f"CSV-файл успешно отправлен для user_id={message.from_user.id}"
            )

        except Exception as e:
            logger.error(f"Ошибка при экспорте данных: {e}")
            await message.answer(
                "❌ Произошла ошибка при экспорте данных. Проверьте логи."
            )

    @dp.message(Command("export"))
    async def cmd_export_participants(message: Message, state: FSMContext):
        await export_participants(message, state)

    @dp.callback_query(F.data == "admin_export")
    async def callback_export_participants(
        callback_query: CallbackQuery, state: FSMContext
    ):
        await export_participants(callback_query, state)

    async def record_results(event: [Message, CallbackQuery], state: FSMContext):
        """Start the results recording process"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда записи результатов от user_id={user_id}")

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event

        # Get all runners with bib numbers
        participants = get_all_participants()
        runners = [
            p for p in participants if p[4] == "runner" and p[7] is not None
        ]  # role and bib_number

        if not runners:
            await message.answer(
                "❌ Нет бегунов с присвоенными номерами для записи результатов.",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return

        # Sort runners by bib number for easier management
        runners.sort(key=lambda x: str(x[7]))  # Sort by bib_number as string

        # Store data in FSM context
        await state.update_data(runners=runners, current_index=0, results={})

        # Show first participant
        await show_next_participant_for_result(
            message, state, runners[0], 0, len(runners)
        )
        await state.set_state(RegistrationForm.waiting_for_participant_result)

    async def show_next_participant_for_result(
        message: Message, state: FSMContext, participant, index, total
    ):
        """Show current participant for result input"""
        (
            user_id_p,
            username,
            name,
            target_time,
            role,
            reg_date,
            payment_status,
            bib_number,
            result,
            gender,
            category,
            cluster,
        ) = participant

        text = f"📝 <b>Запись результатов</b> ({index + 1}/{total})\n\n"
        text += f"👤 <b>{name}</b>\n"
        text += f"🏷 Номер: {bib_number}\n"
        text += f"🆔 ID: <code>{user_id_p}</code>\n"
        text += f"📱 TG: @{username}" if username else "📱 TG: —"
        text += (
            f"\n⏰ Целевое время: {target_time}"
            if target_time
            else "\n⏰ Целевое время: —"
        )

        if result:
            text += f"\n🏃 Текущий результат: {result}"

        text += f"\n\n💬 Введите результат для <b>{name}</b>:"
        text += f"\n• Формат времени: <code>ММ:СС</code> (например: 08:45)"
        text += f"\n• Или используйте кнопки ниже"

        from .utils import create_result_input_keyboard

        await message.answer(text, reply_markup=create_result_input_keyboard())

    @dp.message(RegistrationForm.waiting_for_participant_result)
    async def process_participant_result(message: Message, state: FSMContext):
        """Process individual participant result"""
        result_input = sanitize_input(message.text, 20).strip()

        data = await state.get_data()
        runners = data.get("runners", [])
        current_index = data.get("current_index", 0)
        results = data.get("results", {})

        if current_index >= len(runners):
            await message.answer("❌ Ошибка: индекс участника вышел за границы.")
            await state.clear()
            return

        current_participant = runners[current_index]
        user_id_p = current_participant[0]
        name = current_participant[2]
        bib_number = current_participant[7]

        # Process result input
        if result_input.lower() == "skip":
            logger.info(f"Пропущен результат для участника {name} (ID: {user_id_p})")
        elif result_input.upper() == "DNF":
            results[user_id_p] = "DNF"
            logger.info(f"Записан DNF для участника {name} (ID: {user_id_p})")
        else:
            # Validate result format
            is_valid, error_msg = validate_result_format(result_input)
            if not is_valid:
                await message.answer(
                    f"❌ {error_msg}\n\nПовторите ввод для <b>{name}</b>:",
                    reply_markup=create_back_keyboard("admin_menu"),
                )
                return

            results[user_id_p] = result_input
            logger.info(
                f"Записан результат {result_input} для участника {name} (ID: {user_id_p})"
            )

        # Move to next participant
        current_index += 1

        if current_index < len(runners):
            # Show next participant
            await state.update_data(current_index=current_index, results=results)
            next_participant = runners[current_index]
            await show_next_participant_for_result(
                message, state, next_participant, current_index, len(runners)
            )
        else:
            # All participants processed, show summary and ask for notification
            await show_results_summary(message, state, runners, results)

    @dp.callback_query(
        F.data == "result_skip", RegistrationForm.waiting_for_participant_result
    )
    async def process_skip_result(callback_query: CallbackQuery, state: FSMContext):
        """Process skip button for participant result"""
        await callback_query.answer()
        await callback_query.message.delete()

        data = await state.get_data()
        runners = data.get("runners", [])
        current_index = data.get("current_index", 0)
        results = data.get("results", {})

        if current_index >= len(runners):
            await callback_query.message.answer(
                "❌ Ошибка: индекс участника вышел за границы."
            )
            await state.clear()
            return

        current_participant = runners[current_index]
        user_id_p = current_participant[0]
        name = current_participant[2]

        logger.info(f"Пропущен результат для участника {name} (ID: {user_id_p})")

        # Move to next participant
        current_index += 1

        if current_index < len(runners):
            # Show next participant
            await state.update_data(current_index=current_index, results=results)
            next_participant = runners[current_index]
            await show_next_participant_for_result(
                callback_query.message,
                state,
                next_participant,
                current_index,
                len(runners),
            )
        else:
            # All participants processed, show summary and ask for notification
            await show_results_summary(callback_query.message, state, runners, results)

    @dp.callback_query(
        F.data == "result_dnf", RegistrationForm.waiting_for_participant_result
    )
    async def process_dnf_result(callback_query: CallbackQuery, state: FSMContext):
        """Process DNF button for participant result"""
        await callback_query.answer()
        await callback_query.message.delete()

        data = await state.get_data()
        runners = data.get("runners", [])
        current_index = data.get("current_index", 0)
        results = data.get("results", {})

        if current_index >= len(runners):
            await callback_query.message.answer(
                "❌ Ошибка: индекс участника вышел за границы."
            )
            await state.clear()
            return

        current_participant = runners[current_index]
        user_id_p = current_participant[0]
        name = current_participant[2]

        results[user_id_p] = "DNF"
        logger.info(f"Записан DNF для участника {name} (ID: {user_id_p})")

        # Move to next participant
        current_index += 1

        if current_index < len(runners):
            # Show next participant
            await state.update_data(current_index=current_index, results=results)
            next_participant = runners[current_index]
            await show_next_participant_for_result(
                callback_query.message,
                state,
                next_participant,
                current_index,
                len(runners),
            )
        else:
            # All participants processed, show summary and ask for notification
            await show_results_summary(callback_query.message, state, runners, results)

    async def show_results_summary(
        message: Message, state: FSMContext, runners, results
    ):
        """Show summary of all results and ask for mass notification"""
        text = "📊 <b>Итоги записи результатов</b>\n\n"

        recorded_count = 0
        dnf_count = 0
        skipped_count = 0

        for participant in runners:
            user_id_p = participant[0]
            name = participant[2]
            bib_number = participant[7]

            if user_id_p in results:
                result = results[user_id_p]
                if result == "DNF":
                    text += f"🏷 {bib_number} - <b>{name}</b>: DNF\n"
                    dnf_count += 1
                else:
                    text += f"🏷 {bib_number} - <b>{name}</b>: {result}\n"
                    recorded_count += 1
            else:
                text += f"🏷 {bib_number} - <b>{name}</b>: пропущен\n"
                skipped_count += 1

        text += f"\n📈 <b>Статистика:</b>\n"
        text += f"• Результатов записано: {recorded_count}\n"
        text += f"• DNF: {dnf_count}\n"
        text += f"• Пропущено: {skipped_count}\n"
        text += f"• Всего участников: {len(runners)}\n"

        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, отправить всем", callback_data="send_results_yes"
                    ),
                    InlineKeyboardButton(
                        text="❌ Нет, только сохранить", callback_data="send_results_no"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Отменить все", callback_data="cancel_results"
                    )
                ],
            ]
        )

        text += f"\n💬 <b>Отправить результаты всем участникам?</b>"

        await message.answer(text, reply_markup=keyboard)
        await state.set_state(RegistrationForm.waiting_for_results_send_confirmation)

    @dp.callback_query(
        F.data.in_(["send_results_yes", "send_results_no", "cancel_results"]),
        RegistrationForm.waiting_for_results_send_confirmation,
    )
    async def process_results_confirmation(callback: CallbackQuery, state: FSMContext):
        """Process the confirmation for sending results"""
        action = callback.data
        await callback.message.delete()

        data = await state.get_data()
        runners = data.get("runners", [])
        results = data.get("results", {})

        if action == "cancel_results":
            await callback.message.answer("❌ Запись результатов отменена.")
            await state.clear()
            await callback.answer()
            return

        # Save results to database
        saved_count = 0
        for user_id_p, result in results.items():
            try:
                success = set_result(user_id_p, result)
                if success:
                    saved_count += 1
                    logger.info(
                        f"Результат сохранён в БД для user_id={user_id_p}: {result}"
                    )
                else:
                    logger.error(
                        f"Ошибка сохранения результата для user_id={user_id_p}"
                    )
            except Exception as e:
                logger.error(
                    f"Исключение при сохранении результата для user_id={user_id_p}: {e}"
                )

        status_text = f"💾 <b>Результаты сохранены</b>\n\n"
        status_text += f"✅ Успешно сохранено: {saved_count}/{len(results)}\n"

        if action == "send_results_yes":
            # Send notifications to all participants
            await callback.message.answer(
                status_text + "📤 Отправляю уведомления участникам..."
            )

            sent_count = 0
            blocked_count = 0

            for participant in runners:
                user_id_p = participant[0]
                name = participant[2]
                bib_number = participant[7]

                if user_id_p in results:
                    result = results[user_id_p]

                    # Create beautiful result message
                    result_text = f"🏃 <b>Ваш результат в Пивном Квартале!</b>\n\n"
                    result_text += f"👤 <b>{name}</b>\n"
                    result_text += f"🏷 Номер: {bib_number}\n"

                    if result == "DNF":
                        result_text += f"🏁 Результат: DNF (не финишировал)\n\n"
                        result_text += f"💪 Не расстраивайтесь! Главное - участие!"
                    else:
                        result_text += f"🏁 Результат: <b>{result}</b>\n\n"
                        result_text += f"🎉 Поздравляем с финишем!"

                    result_text += f"\n\nБлагодарим за участие в Пивном Квартале! 🍺"

                    try:
                        await bot.send_message(chat_id=user_id_p, text=result_text)
                        sent_count += 1
                        logger.info(
                            f"Результат отправлен участнику {name} (ID: {user_id_p})"
                        )
                    except TelegramForbiddenError:
                        logger.warning(
                            f"Участник {name} (ID: {user_id_p}) заблокировал бота"
                        )
                        blocked_count += 1
                    except Exception as e:
                        logger.error(
                            f"Ошибка отправки результата участнику {name} (ID: {user_id_p}): {e}"
                        )
                        blocked_count += 1

            final_text = f"📧 <b>Рассылка завершена</b>\n\n"
            final_text += f"✅ Отправлено уведомлений: {sent_count}\n"
            final_text += f"❌ Не доставлено: {blocked_count}\n"
            final_text += f"📊 Всего результатов: {len(results)}\n"

            await callback.message.answer(final_text)
        else:
            await callback.message.answer(
                status_text + "📝 Результаты сохранены без отправки уведомлений."
            )

        await state.clear()
        await callback.answer()

    @dp.message(Command("results", "результаты"))
    async def cmd_record_results(message: Message, state: FSMContext):
        await record_results(message, state)

    @dp.callback_query(F.data == "admin_results")
    async def callback_record_results(callback: CallbackQuery, state: FSMContext):
        await record_results(callback, state)

    async def save_race(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["save_race_access_denied"])
            return
        logger.info(f"Команда /save_race от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["save_race_prompt"])
        await state.set_state(RegistrationForm.waiting_for_race_date)
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def process_save_race(message: Message, state: FSMContext):
        race_date = message.text.strip()
        try:
            date_obj = datetime.datetime.strptime(race_date, "%d.%m.%Y")
            table_name = f"race_{date_obj.strftime('%d_%m_%Y')}"
            conn = sqlite3.connect("/app/data/race_participants.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            table_exists = cursor.fetchone() is not None
            conn.close()
            success = save_race_to_db(race_date)
            if success:
                action = "обновлены" if table_exists else "сохранены"
                await message.answer(
                    messages["save_race_success"].format(date=race_date, action=action)
                )
                logger.info(f"Гонка {action} для даты {race_date}")
            else:
                await message.answer(messages["save_race_empty"])
                logger.info(
                    f"Не удалось сохранить гонку для даты {race_date}: таблица participants пуста"
                )
        except ValueError:
            await message.answer(messages["save_race_invalid_format"])
            logger.error(f"Некорректный формат даты для /save_race: {race_date}")
        await state.clear()

    async def clear_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["clear_participants_access_denied"])
            return
        logger.info(f"Команда /clear_participants от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        success = clear_participants()
        if success:
            await message.answer(messages["clear_participants_success"])
            logger.info("Таблица participants успешно очищена")
        else:
            await message.answer(messages["clear_participants_error"])
            logger.error("Ошибка при очистке таблицы participants")
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def past_races(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["past_races_access_denied"])
            return
        logger.info(f"Команда /past_races от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        races = get_past_races()
        if not races:
            await message.answer(messages["past_races_empty"])
            if isinstance(event, CallbackQuery):
                await event.answer()
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=date, callback_data=f"past_race_{date}")]
                for date in races
            ]
        )
        await message.answer(messages["past_races_prompt"], reply_markup=keyboard)
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def show_past_race(callback_query: CallbackQuery):
        race_date = callback_query.data.replace("past_race_", "")
        logger.info(
            f"Запрос данных гонки {race_date} от user_id={callback_query.from_user.id}"
        )
        await callback_query.message.delete()
        participants = get_race_data(race_date)
        if not participants:
            await callback_query.message.answer(
                messages["past_race_not_found"].format(date=race_date)
            )
            await callback_query.answer()
            return

        # Filter only runners and create list with parsed results for sorting
        runners = []
        for (
            user_id,
            username,
            name,
            target_time,
            role,
            reg_date,
            payment_status,
            bib_number,
            result,
            gender,
            category,
            cluster,
        ) in participants:
            if role == "runner":
                # Parse result for sorting (convert time to seconds, DNF goes to end)
                sort_key = 999999  # Default for DNF or no result
                if result and result.upper() not in ["DNF", "НЕ УКАЗАН", "НЕТ"]:
                    try:
                        # Parse time format like "0:07:21" or "7:21"
                        if ":" in result:
                            time_parts = result.split(":")
                            if len(time_parts) == 3:  # H:MM:SS
                                hours, minutes, seconds = map(int, time_parts)
                                sort_key = hours * 3600 + minutes * 60 + seconds
                            elif len(time_parts) == 2:  # MM:SS
                                minutes, seconds = map(int, time_parts)
                                sort_key = minutes * 60 + seconds
                    except:
                        pass  # Keep default DNF sort key

                runners.append(
                    (
                        sort_key,
                        user_id,
                        username,
                        name,
                        target_time,
                        reg_date,
                        payment_status,
                        bib_number,
                        result,
                        gender,
                        category,
                        cluster,
                    )
                )

        # Sort by result (faster times first, DNF last)
        runners.sort(key=lambda x: x[0])

        # Format output
        header = f"🏃‍♂️ <b>Результаты гонки {race_date}</b>\n\n"

        chunks = []
        current_chunk = header

        for position, (
            _,
            user_id,
            username,
            name,
            target_time,
            reg_date,
            payment_status,
            bib_number,
            result,
            gender,
            category,
            cluster,
        ) in enumerate(runners, 1):

            # Format result display
            if result and result.upper() not in ["НЕ УКАЗАН", "НЕТ"]:
                result_display = result
            else:
                result_display = "DNF"

            # Format bib number
            bib_display = f"№{bib_number}" if bib_number else "—"

            # Format gender
            gender_emoji = (
                "👨"
                if gender == "М" or gender == "male"
                else "👩" if gender == "Ж" or gender == "female" else "👤"
            )

            # Format category and cluster
            category_display = f" ({category})" if category else ""

            # Create participant line
            participant_line = (
                f"{position}. {gender_emoji} <b>{name}</b> — {result_display}\n"
                f"   {bib_display} • @{username or 'нет'}{category_display}\n\n"
            )

            # Check if we need to split into chunks
            if len(current_chunk) + len(participant_line) > 4000:
                chunks.append(current_chunk)
                current_chunk = header + participant_line
            else:
                current_chunk += participant_line

        # Add final chunk
        if current_chunk != header:
            chunks.append(current_chunk)

        # Add summary
        total_runners = len(runners)
        finished_runners = len(
            [
                r
                for r in runners
                if r[8] and r[8].upper() not in ["DNF", "НЕ УКАЗАН", "НЕТ"]
            ]
        )

        summary = f"📊 <b>Итого:</b> {finished_runners}/{total_runners} финишировали"

        # Add summary to last chunk or create new one
        if chunks:
            if len(chunks[-1]) + len(summary) > 4000:
                chunks.append(f"🏃‍♂️ <b>Результаты гонки {race_date}</b>\n\n{summary}")
            else:
                chunks[-1] += f"\n{summary}"
        else:
            chunks = [
                f"🏃‍♂️ <b>Результаты гонки {race_date}</b>\n\nНет участников-бегунов."
            ]

        # Send all chunks
        for chunk in chunks:
            await callback_query.message.answer(chunk)
        await callback_query.answer()

    @dp.message(Command("save_race"))
    async def cmd_save_race(message: Message, state: FSMContext):
        await save_race(message, state)

    @dp.callback_query(F.data == "admin_save_race")
    async def callback_save_race(callback_query: CallbackQuery, state: FSMContext):
        await save_race(callback_query, state)

    @dp.message(RegistrationForm.waiting_for_race_date)
    async def process_save_race_message(message: Message, state: FSMContext):
        await process_save_race(message, state)

    @dp.message(Command("clear_participants"))
    async def cmd_clear_participants(message: Message):
        await clear_participants(message)

    @dp.callback_query(F.data == "admin_clear_participants")
    async def callback_clear_participants(callback_query: CallbackQuery):
        await clear_participants(callback_query)

    @dp.message(Command("past_races"))
    async def cmd_past_races(message: Message, state: FSMContext):
        await past_races(message, state)

    @dp.callback_query(F.data == "admin_past_races")
    async def callback_past_races(callback_query: CallbackQuery, state: FSMContext):
        await past_races(callback_query, state)

    @dp.callback_query(F.data.startswith("past_race_"))
    async def callback_show_past_race(callback_query: CallbackQuery):
        await show_past_race(callback_query)

    async def show_protocol(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["protocol_access_denied"])
            return
        logger.info(f"Команда /protocol от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(
            messages["protocol_prompt"], reply_markup=create_protocol_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_protocol_type)
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def process_protocol_type(callback_query: CallbackQuery, state: FSMContext):
        await callback_query.message.delete()
        action = callback_query.data
        await state.update_data(protocol_type=action)
        if action == "protocol_all":
            await show_full_protocol(callback_query)
        elif action == "protocol_by_gender":
            await callback_query.message.answer(
                messages["gender_prompt"], reply_markup=create_gender_keyboard()
            )
            await state.set_state(RegistrationForm.waiting_for_gender_protocol)
        elif action == "protocol_by_category":
            await show_category_protocol(callback_query)
        await callback_query.answer()

    async def show_full_protocol(event: [Message, CallbackQuery]):
        """Show full protocol of current event (from participants table)"""
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                # Get all runners from current participants table with all info
                cursor.execute(
                    """
                    SELECT user_id, username, name, target_time, bib_number, result, gender, reg_date, payment_status
                    FROM participants 
                    WHERE role = 'runner' 
                    ORDER BY 
                        CASE WHEN result = 'DNF' THEN 1 ELSE 0 END,
                        CASE WHEN result IS NULL OR result = '' THEN 1 ELSE 0 END,
                        result
                """
                )
                runners = cursor.fetchall()

        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении данных протокола: {e}")
            await event.message.answer("❌ Ошибка при получении данных протокола.")
            return

        if not runners:
            await event.message.answer(
                "🏆 <b>Протокол актуальной гонки</b>\n\n📋 Пока нет участников с результатами."
            )
            return

        def time_to_seconds(time_str):
            """Convert time string to seconds for sorting"""
            if not time_str or time_str.upper() == "DNF":
                return float("inf")
            try:
                parts = time_str.split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                return float("inf")
            except:
                return float("inf")

        # Separate runners with results and without
        runners_with_results = []
        runners_without_results = []

        for runner in runners:
            (
                user_id,
                username,
                name,
                target_time,
                bib_number,
                result,
                gender,
                reg_date,
                payment_status,
            ) = runner
            if result and result.strip():
                runners_with_results.append(runner)
            else:
                runners_without_results.append(runner)

        # Sort runners with results by time
        runners_with_results.sort(
            key=lambda x: time_to_seconds(x[5])
        )  # result is at index 5

        # Build protocol message
        text = "🏆 <b>Протокол актуальной гонки</b>\n\n"

        # Show finishers first
        if runners_with_results:
            text += f"🏁 <b>Финишировавшие ({len(runners_with_results)}):</b>\n\n"

            place = 1
            for runner in runners_with_results:
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    bib_number,
                    result,
                    gender,
                    reg_date,
                    payment_status,
                ) = runner

                # Skip DNF for place counting
                if result and result.upper() != "DNF":
                    medal_emoji = ""
                    if place == 1:
                        medal_emoji = "🥇 "
                    elif place == 2:
                        medal_emoji = "🥈 "
                    elif place == 3:
                        medal_emoji = "🥉 "

                    text += f"{medal_emoji}<b>{place}. {name}</b>\n"
                    text += f"   🏷 Номер: {bib_number or '—'}\n"
                    text += f"   ⏰ Результат: <b>{result}</b>\n"
                    text += f"   🎯 Цель: {target_time or '—'}\n"
                    if username:
                        text += f"   📱 @{username}\n"
                    text += f"   👤 {gender or '—'}\n\n"
                    place += 1
                else:
                    # DNF participants
                    text += f"❌ <b>DNF - {name}</b>\n"
                    text += f"   🏷 Номер: {bib_number or '—'}\n"
                    if username:
                        text += f"   📱 @{username}\n"
                    text += f"   👤 {gender or '—'}\n\n"

        # Show runners without results
        if runners_without_results:
            text += f"⏳ <b>Без результатов ({len(runners_without_results)}):</b>\n\n"

            for runner in runners_without_results:
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    bib_number,
                    result,
                    gender,
                    reg_date,
                    payment_status,
                ) = runner

                text += f"🏃 <b>{name}</b>\n"
                text += f"   🏷 Номер: {bib_number or '—'}\n"
                text += f"   🎯 Цель: {target_time or '—'}\n"
                if username:
                    text += f"   📱 @{username}\n"
                text += f"   👤 {gender or '—'}\n\n"

        # Add summary stats
        total_registered = len(runners_with_results) + len(runners_without_results)
        finished_count = len(
            [r for r in runners_with_results if r[5] and r[5].upper() != "DNF"]
        )
        dnf_count = len(
            [r for r in runners_with_results if r[5] and r[5].upper() == "DNF"]
        )

        text += f"📊 <b>Статистика:</b>\n"
        text += f"• Зарегистрировано: {total_registered}\n"
        text += f"• Финишировало: {finished_count}\n"
        text += f"• DNF: {dnf_count}\n"
        text += f"• Без результатов: {len(runners_without_results)}\n"

        # Split long messages
        if len(text) > 4000:
            chunks = []
            lines = text.split("\n")
            current_chunk = "🏆 <b>Протокол актуальной гонки</b>\n\n"

            for line in lines[2:]:  # Skip header
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = "🏆 <b>Протокол (продолжение)</b>\n\n" + line + "\n"
                else:
                    current_chunk += line + "\n"

            if current_chunk.strip():
                chunks.append(current_chunk.rstrip())

            for chunk in chunks:
                await event.message.answer(chunk)
        else:
            await event.message.answer(text)

    async def process_gender_protocol(callback_query: CallbackQuery, state: FSMContext):
        """Show protocol by gender with beautiful formatting"""
        gender = callback_query.data
        await callback_query.message.delete()

        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                # Get all runners of specific gender from current participants table
                cursor.execute(
                    """
                    SELECT user_id, username, name, target_time, bib_number, result, reg_date, payment_status
                    FROM participants 
                    WHERE gender = ? AND role = 'runner'
                    ORDER BY 
                        CASE WHEN result = 'DNF' THEN 1 ELSE 0 END,
                        CASE WHEN result IS NULL OR result = '' THEN 1 ELSE 0 END,
                        result
                """,
                    (gender,),
                )
                runners = cursor.fetchall()

        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении данных протокола по полу: {e}")
            await callback_query.message.answer(
                "❌ Ошибка при получении данных протокола."
            )
            await state.clear()
            await callback_query.answer()
            return

        gender_name = "мужчины" if gender == "male" else "женщины"
        gender_emoji = "👨" if gender == "male" else "👩"

        if not runners:
            await callback_query.message.answer(
                f"🏆 <b>Протокол актуальной гонки</b>\n\n{gender_emoji} <b>{gender_name.title()}</b>\n\n📋 Участников не найдено."
            )
            await state.clear()
            await callback_query.answer()
            return

        def time_to_seconds(time_str):
            """Convert time string to seconds for sorting"""
            if not time_str or time_str.upper() == "DNF":
                return float("inf")
            try:
                parts = time_str.split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                return float("inf")
            except:
                return float("inf")

        # Separate runners with results and without
        runners_with_results = []
        runners_without_results = []

        for runner in runners:
            (
                user_id,
                username,
                name,
                target_time,
                bib_number,
                result,
                reg_date,
                payment_status,
            ) = runner
            if result and result.strip():
                runners_with_results.append(runner)
            else:
                runners_without_results.append(runner)

        # Sort runners with results by time
        runners_with_results.sort(
            key=lambda x: time_to_seconds(x[5])
        )  # result is at index 5

        # Build protocol message
        text = f"🏆 <b>Протокол актуальной гонки</b>\n\n{gender_emoji} <b>{gender_name.title()}</b>\n\n"

        # Show finishers first
        if runners_with_results:
            text += f"🏁 <b>Финишировали ({len(runners_with_results)}):</b>\n\n"

            place = 1
            for runner in runners_with_results:
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    bib_number,
                    result,
                    reg_date,
                    payment_status,
                ) = runner

                # Skip DNF for place counting
                if result and result.upper() != "DNF":
                    medal_emoji = ""
                    if place == 1:
                        medal_emoji = "🥇 "
                    elif place == 2:
                        medal_emoji = "🥈 "
                    elif place == 3:
                        medal_emoji = "🥉 "

                    text += f"{medal_emoji}<b>{place}. {name}</b>\n"
                    text += f"   🏷 Номер: {bib_number or '—'}\n"
                    text += f"   ⏰ Результат: <b>{result}</b>\n"
                    text += f"   🎯 Цель: {target_time or '—'}\n"
                    if username:
                        text += f"   📱 @{username}\n"
                    text += "\n"
                    place += 1
                else:
                    # DNF participants
                    text += f"❌ <b>DNF - {name}</b>\n"
                    text += f"   🏷 Номер: {bib_number or '—'}\n"
                    if username:
                        text += f"   📱 @{username}\n"
                    text += "\n"

        # Show runners without results
        if runners_without_results:
            text += f"⏳ <b>Без результатов ({len(runners_without_results)}):</b>\n\n"

            for runner in runners_without_results:
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    bib_number,
                    result,
                    reg_date,
                    payment_status,
                ) = runner

                text += f"🏃 <b>{name}</b>\n"
                text += f"   🏷 Номер: {bib_number or '—'}\n"
                text += f"   🎯 Цель: {target_time or '—'}\n"
                if username:
                    text += f"   📱 @{username}\n"
                text += "\n"

        # Add summary stats
        total_registered = len(runners_with_results) + len(runners_without_results)
        finished_count = len(
            [r for r in runners_with_results if r[5] and r[5].upper() != "DNF"]
        )
        dnf_count = len(
            [r for r in runners_with_results if r[5] and r[5].upper() == "DNF"]
        )

        text += f"📊 <b>Статистика {gender_name}:</b>\n"
        text += f"• Зарегистрировано: {total_registered}\n"
        text += f"• Финишировало: {finished_count}\n"
        text += f"• DNF: {dnf_count}\n"
        text += f"• Без результатов: {len(runners_without_results)}\n"

        # Split long messages
        if len(text) > 4000:
            chunks = []
            lines = text.split("\n")
            current_chunk = f"🏆 <b>Протокол актуальной гонки</b>\n\n{gender_emoji} <b>{gender_name.title()}</b>\n\n"

            for line in lines[3:]:  # Skip header
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = (
                        f"🏆 <b>Протокол {gender_name} (продолжение)</b>\n\n"
                        + line
                        + "\n"
                    )
                else:
                    current_chunk += line + "\n"

            if current_chunk.strip():
                chunks.append(current_chunk.rstrip())

            for chunk in chunks:
                await callback_query.message.answer(chunk)
        else:
            await callback_query.message.answer(text)

        await state.clear()
        await callback_query.answer()

    @dp.message(Command("protocol"))
    async def cmd_protocol(message: Message, state: FSMContext):
        await show_protocol(message, state)

    @dp.callback_query(F.data == "admin_protocol")
    async def callback_protocol(callback_query: CallbackQuery, state: FSMContext):
        await show_protocol(callback_query, state)

    @dp.callback_query(RegistrationForm.waiting_for_protocol_type)
    async def callback_process_protocol_type(
        callback_query: CallbackQuery, state: FSMContext
    ):
        await process_protocol_type(callback_query, state)

    @dp.callback_query(RegistrationForm.waiting_for_gender_protocol)
    async def callback_process_gender_protocol(
        callback_query: CallbackQuery, state: FSMContext
    ):
        await process_gender_protocol(callback_query, state)

    @dp.callback_query(F.data == "admin_waitlist")
    async def callback_admin_waitlist(callback: CallbackQuery):
        """Handle admin waitlist button"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        await callback.message.delete()

        # Import and use the waitlist function
        from .waitlist_handlers import handle_admin_waitlist_command

        await handle_admin_waitlist_command(callback.message)
        await callback.answer()

    @dp.callback_query(F.data == "admin_notify_participants")
    async def callback_notify_participants(callback: CallbackQuery, state: FSMContext):
        """Handle notify participants button - custom message to all participants"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        await callback.message.delete()

        participants = get_all_participants()
        if not participants:
            await callback.message.answer(
                "📢 <b>Уведомить участников</b>\n\n❌ Нет зарегистрированных участников для уведомления."
            )
            await callback.answer()
            return

        text = "📢 <b>Уведомить участников</b>\n\n"
        text += f"👥 Найдено участников: {len(participants)}\n\n"
        text += (
            "✏️ Введите текст сообщения для отправки всем зарегистрированным участникам:"
        )

        await callback.message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_notify_participants_message)
        await callback.answer()

    # Add state for notify participants
    @dp.message(RegistrationForm.waiting_for_notify_participants_message)
    async def process_notify_participants_message(message: Message, state: FSMContext):
        """Process custom message for participants notification"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        notify_text = message.text.strip() if message.text else ""
        if not notify_text:
            await message.answer("❌ Сообщение не может быть пустым. Попробуйте снова:")
            return

        if len(notify_text) > 4096:
            await message.answer(
                "❌ Сообщение слишком длинное. Максимум 4096 символов. Попробуйте снова:"
            )
            return

        await message.answer(
            "📤 <b>Отправка уведомлений...</b>\n\nОтправляю сообщения всем участникам..."
        )

        participants = get_all_participants()
        success_count = 0
        blocked_count = 0

        for participant in participants:
            user_id_p = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"

            try:
                await bot.send_message(
                    chat_id=user_id_p, text=notify_text, parse_mode="HTML"
                )
                success_count += 1
                logger.info(
                    f"Кастомное уведомление отправлено участнику {name} (ID: {user_id_p})"
                )

            except TelegramForbiddenError:
                logger.warning(f"Участник {name} (ID: {user_id_p}) заблокировал бота")
                blocked_count += 1

                # Optionally remove blocked users
                try:
                    delete_participant(user_id_p)
                    delete_pending_registration(user_id_p)
                    logger.info(f"Участник {name} (ID: {user_id_p}) удален из БД")

                    # Notify admin about blocked user
                    await bot.send_message(
                        chat_id=admin_id,
                        text=f"🚫 <b>Пользователь заблокировал бота</b>\n\n"
                        f"👤 Имя: {name}\n"
                        f"📱 Username: @{username}\n"
                        f"🆔 ID: <code>{user_id_p}</code>\n\n"
                        f"Пользователь удален из базы данных.",
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка при обработке заблокированного пользователя {user_id_p}: {e}"
                    )

            except Exception as e:
                logger.error(
                    f"Ошибка отправки кастомного уведомления участнику {name} (ID: {user_id_p}): {e}"
                )
                blocked_count += 1

        # Send summary
        result_text = f"✅ <b>Рассылка завершена</b>\n\n"
        result_text += f"📊 <b>Статистика:</b>\n"
        result_text += f"• Успешно отправлено: {success_count}\n"
        result_text += f"• Не доставлено: {blocked_count}\n"
        result_text += f"• Всего участников: {len(participants)}\n"

        await message.answer(result_text)
        await state.clear()
        logger.info(
            f"Кастомная рассылка завершена: {success_count}/{len(participants)} успешно"
        )

    async def start_sequential_bib_assignment(
        event: [Message, CallbackQuery], state: FSMContext
    ):
        """Start sequential bib number assignment process"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return

        # Get all participants (runners only for bib assignment)
        participants = get_participants_by_role("runner")

        if not participants:
            await event.answer("❌ Нет участников для присвоения номеров")
            return

        # Store participants list in state data
        await state.update_data(
            participants=participants, current_index=0, assignment_type="bib"
        )

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            await event.answer()

        # Show first participant
        await show_participant_for_bib_assignment(
            event.message if isinstance(event, CallbackQuery) else event, state, bot
        )

    async def show_participant_for_bib_assignment(
        message: Message, state: FSMContext, bot: Bot
    ):
        """Show current participant for bib number assignment"""
        data = await state.get_data()
        participants = data.get("participants", [])
        current_index = data.get("current_index", 0)

        if current_index >= len(participants):
            # Assignment complete, show summary
            await show_bib_assignment_summary(message, state, participants)
            return

        participant = participants[current_index]
        user_id, username, name, target_time, gender, category, cluster = participant

        # Get existing bib number if any
        try:
            from database import get_participant_by_user_id

            full_participant = get_participant_by_user_id(user_id)
            current_bib = (
                full_participant[7]
                if full_participant and len(full_participant) > 7
                else None
            )
        except:
            current_bib = None

        # Build participant info
        text = (
            f"🏷 <b>Присвоение номеров ({current_index + 1}/{len(participants)})</b>\n\n"
        )
        text += f"👤 <b>{name}</b>\n"
        text += f"🆔 ID: <code>{user_id}</code>\n"
        if username:
            text += f"👤 Username: @{username}\n"
        if target_time:
            text += f"⏱️ Целевое время: {target_time}\n"
        if gender:
            text += f"👤 Пол: {gender}\n"
        if category:
            category_emoji = {
                "СуперЭлита": "💎",
                "Элита": "🥇",
                "Классика": "🏃",
                "Женский": "👩",
                "Команда": "👥",
            }.get(category, "📂")
            text += f"📂 Категория: {category_emoji} {category}\n"
        if cluster:
            cluster_emoji = {"A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴", "F": "🅵", "G": "🅶"}.get(
                cluster, "🎯"
            )
            text += f"🎯 Кластер: {cluster_emoji} {cluster}\n"

        if current_bib:
            text += f"🏷 Текущий номер: <b>{current_bib}</b>\n"

        text += "\n🏷 <b>Введите беговой номер или нажмите 'Пропустить':</b>\n"
        text += "• Только цифры (например: 001, 42, 123)\n"
        text += "• Ведущие нули будут сохранены"

        await message.answer(text, reply_markup=create_bib_assignment_keyboard())
        await state.set_state(RegistrationForm.waiting_for_bib_assignment)

    @dp.message(RegistrationForm.waiting_for_bib_assignment)
    async def process_bib_assignment(message: Message, state: FSMContext):
        """Process bib number input for current participant"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return

        data = await state.get_data()
        participants = data.get("participants", [])
        current_index = data.get("current_index", 0)

        if current_index >= len(participants):
            await message.answer("❌ Ошибка: участник не найден")
            await state.clear()
            return

        participant = participants[current_index]
        user_id = participant[0]
        name = participant[2]

        # Get and validate bib number
        bib_input = message.text.strip()

        if not bib_input.isdigit():
            await message.answer(
                "❌ Номер должен содержать только цифры. Попробуйте снова:"
            )
            return

        # Check for duplicate bib numbers
        all_participants = get_all_participants()
        existing_bibs = [
            p[7] for p in all_participants if p[7] is not None and p[0] != user_id
        ]

        if bib_input in existing_bibs:
            await message.answer(
                f"❌ Номер {bib_input} уже используется другим участником. Введите другой номер:"
            )
            return

        # Set bib number
        success = set_bib_number(user_id, bib_input)

        if success:
            await message.answer(f"✅ Номер {bib_input} присвоен участнику {name}")
            logger.info(f"Номер {bib_input} присвоен участнику {name} (ID: {user_id})")
        else:
            await message.answer(f"❌ Ошибка при присвоении номера участнику {name}")
            logger.error(
                f"Ошибка при присвоении номера {bib_input} участнику {name} (ID: {user_id})"
            )

        # Move to next participant
        await state.update_data(current_index=current_index + 1)
        await show_participant_for_bib_assignment(message, state, bot)

    @dp.callback_query(F.data == "bib_skip")
    async def skip_bib_assignment(callback_query: CallbackQuery, state: FSMContext):
        """Skip bib assignment for current participant"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        data = await state.get_data()
        current_index = data.get("current_index", 0)

        # Move to next participant
        await state.update_data(current_index=current_index + 1)
        await callback_query.message.delete()
        await show_participant_for_bib_assignment(callback_query.message, state, bot)

    async def show_bib_assignment_summary(
        message: Message, state: FSMContext, participants: list
    ):
        """Show summary of bib assignment process"""
        # Count assigned bib numbers
        assigned_count = 0
        unassigned_participants = []

        for participant in participants:
            user_id = participant[0]
            name = participant[2]

            try:
                from database import get_participant_by_user_id

                full_participant = get_participant_by_user_id(user_id)
                has_bib = (
                    full_participant
                    and len(full_participant) > 7
                    and full_participant[7] is not None
                )

                if has_bib:
                    assigned_count += 1
                else:
                    unassigned_participants.append(name)
            except:
                unassigned_participants.append(name)

        text = "✅ <b>Присвоение номеров завершено!</b>\n\n"
        text += f"📊 <b>Статистика:</b>\n"
        text += f"• Всего участников: {len(participants)}\n"
        text += f"• Присвоено номеров: {assigned_count}\n"
        text += f"• Без номеров: {len(unassigned_participants)}\n"

        if unassigned_participants:
            text += f"\n❓ <b>Участники без номеров:</b>\n"
            for name in unassigned_participants[:10]:  # Show max 10 names
                text += f"• {name}\n"

            if len(unassigned_participants) > 10:
                text += f"• ... и ещё {len(unassigned_participants) - 10}\n"

        # Offer to send notifications if any numbers were assigned
        if assigned_count > 0:
            text += f"\n📢 <b>Уведомить участников о присвоенных номерах?</b>\n"
            text += (
                f"Будет отправлено {assigned_count} уведомлений участникам с номерами."
            )

            await message.answer(
                text, reply_markup=create_bib_notification_confirmation_keyboard()
            )
        else:
            text += (
                f"\n💡 Вы можете повторить процесс для назначения пропущенных номеров"
            )
            await message.answer(text)

        await state.clear()

    @dp.callback_query(F.data == "confirm_bib_notify")
    async def confirm_bib_notification(callback_query: CallbackQuery):
        """Send bib number notifications to participants"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()
        await callback_query.message.delete()
        await send_bib_notifications(callback_query.message, bot)

    @dp.callback_query(F.data == "cancel_bib_notify")
    async def cancel_bib_notification(callback_query: CallbackQuery):
        """Cancel bib number notifications"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer("Рассылка отменена")
        await callback_query.message.edit_text(
            "✅ Присвоение номеров завершено.\n\n"
            "💡 Вы можете отправить уведомления позже через кнопку 'Уведомить о номерах' в меню участников."
        )

    @dp.callback_query(F.data == "admin_notify_bibs")
    async def manual_bib_notification(callback_query: CallbackQuery):
        """Manually trigger bib number notifications"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()
        await callback_query.message.delete()
        await send_bib_notifications(callback_query.message, bot)

    async def send_bib_notifications(message: Message, bot: Bot):
        """Send bib number notifications to all participants with assigned numbers"""
        try:
            # Get all participants with bib numbers
            all_participants = get_all_participants()
            participants_with_bibs = [
                p for p in all_participants if p[7] is not None
            ]  # bib_number field

            if not participants_with_bibs:
                await message.answer(
                    "❌ <b>Нет участников с присвоенными номерами</b>\n\n"
                    "Сначала присвойте номера участникам через команду 'Присвоить номер'."
                )
                return

            success_count = 0
            error_count = 0

            status_message = await message.answer(
                "📢 <b>Рассылаю уведомления о номерах...</b>"
            )

            for participant in participants_with_bibs:
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    role,
                    reg_date,
                    payment_status,
                    bib_number,
                    result,
                    gender,
                    category,
                    cluster,
                ) = participant

                try:
                    # Build notification message
                    msg_text = "🏷 <b>Ваш беговой номер</b>\n\n"
                    msg_text += f"👤 Привет, <b>{name}</b>!\n\n"
                    msg_text += f"🏷 <b>Ваш номер для забега: {bib_number}</b>\n\n"

                    # Add category/cluster info if available
                    if category:
                        category_emoji = {
                            "СуперЭлита": "💎",
                "Элита": "🥇",
                            "Классика": "🏃",
                            "Женский": "👩",
                            "Команда": "👥",
                        }.get(category, "📂")
                        msg_text += f"📂 Категория: {category_emoji} {category}\n"

                    if cluster:
                        cluster_emoji = {
                            "A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴", "F": "🅵", "G": "🅶",
                        }.get(cluster, "🎯")
                        msg_text += f"🎯 Стартовый кластер: {cluster_emoji} {cluster}\n"

                    msg_text += "\n🏃‍♀️ <b>Важно:</b>\n"
                    msg_text += "• Запомните свой номер\n"
                    msg_text += "• Возьмите номер на старте\n"
                    msg_text += "• Не передавайте номер другим\n\n"
                    msg_text += "🎯 Увидимся на старте!"

                    await bot.send_message(user_id, msg_text)
                    success_count += 1
                    logger.info(
                        f"Уведомление о номере {bib_number} отправлено {name} (ID: {user_id})"
                    )

                except Exception as e:
                    logger.error(
                        f"Ошибка отправки уведомления о номере участнику {name} (ID: {user_id}): {e}"
                    )
                    error_count += 1

            # Send summary
            await status_message.edit_text(
                "✅ <b>Рассылка уведомлений о номерах завершена</b>\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Успешно отправлено: {success_count}\n"
                f"• Ошибки доставки: {error_count}\n"
                f"• Всего участников с номерами: {len(participants_with_bibs)}\n\n"
                f"💡 Участники получили информацию о своих номерах, категориях и кластерах"
            )

            logger.info(
                f"Рассылка номеров завершена: {success_count}/{len(participants_with_bibs)} успешно"
            )

        except Exception as e:
            logger.error(f"Ошибка при рассылке уведомлений о номерах: {e}")
            await message.answer(
                "❌ <b>Ошибка при рассылке уведомлений</b>\n\n"
                "Проверьте логи для получения подробной информации."
            )

    async def show_category_protocol(event: [Message, CallbackQuery]):
        """Show protocol grouped by categories"""
        try:
            from database import get_participants_with_categories

            participants = get_participants_with_categories()
            runners = [
                p for p in participants if p[7] == "runner" and p[8]
            ]  # role == runner and has result

            if not runners:
                await event.message.answer(
                    "❌ Нет участников с результатами для протокола по категориям"
                )
                return

            # Check if we have categories
            has_categories = any(p[5] for p in runners)  # category field
            if not has_categories:
                await event.message.answer(
                    "❌ Участники не имеют назначенных категорий"
                )
                return

            # Group by categories
            categories = {}
            for runner in runners:
                category = runner[5] or "Без категории"
                if category not in categories:
                    categories[category] = []
                categories[category].append(runner)

            # Generate protocol
            protocol_text = "🏆 <b>ПРОТОКОЛ ПО КАТЕГОРИЯМ</b>\n\n"

            category_order = [
                "Элита",
                "Классика",
                "Женский",
                "Команда",
                "Без категории",
            ]
            for cat_name in category_order:
                if cat_name not in categories:
                    continue

                cat_runners = categories[cat_name]
                if not cat_runners:
                    continue

                category_emoji = {
                    "СуперЭлита": "💎",
                "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                    "Без категории": "❓",
                }.get(cat_name, "📂")

                protocol_text += f"{category_emoji} <b>{cat_name.upper()}</b>\n"
                protocol_text += "-" * 25 + "\n"

                # Sort by result (DNF last, then by time)
                def sort_key(p):
                    result = p[8]  # result field
                    if result == "DNF":
                        return (2, 0)  # DNF goes last
                    elif result is None or result == "":
                        return (3, 0)  # No result goes after DNF
                    else:
                        try:
                            # Convert MM:SS to seconds for sorting
                            if ":" in str(result):
                                minutes, seconds = map(int, str(result).split(":"))
                                return (0, minutes * 60 + seconds)
                            else:
                                return (1, float(result))
                        except:
                            return (3, 0)

                sorted_runners = sorted(cat_runners, key=sort_key)

                # Separate runners by result type
                finishers = []
                dnf_runners = []
                no_result_runners = []

                for runner in sorted_runners:
                    result = runner[8] or ""
                    if result == "DNF":
                        dnf_runners.append(runner)
                    elif result == "" or result == "—":
                        no_result_runners.append(runner)
                    else:
                        finishers.append(runner)

                # Display finishers with places
                place = 1
                for runner in finishers:
                    name = runner[2]
                    result = runner[8]
                    bib_number = runner[9] if len(runner) > 9 else None

                    protocol_text += f"   {place}. {name}"
                    if bib_number:
                        protocol_text += f" (№{bib_number})"
                    protocol_text += f" - {result}\n"
                    place += 1

                # Display DNF runners at the end
                for runner in dnf_runners:
                    name = runner[2]
                    bib_number = runner[9] if len(runner) > 9 else None

                    protocol_text += f"   DNF. {name}"
                    if bib_number:
                        protocol_text += f" (№{bib_number})"
                    protocol_text += " - DNF\n"

                # Display runners without results
                for runner in no_result_runners:
                    name = runner[2]
                    bib_number = runner[9] if len(runner) > 9 else None

                    protocol_text += f"   —. {name}"
                    if bib_number:
                        protocol_text += f" (№{bib_number})"
                    protocol_text += " - —\n"

                protocol_text += "\n"

            # Send protocol in chunks if too long
            if len(protocol_text) > 4000:
                chunks = []
                lines = protocol_text.split("\n")
                current_chunk = ""

                for line in lines:
                    if len(current_chunk + line + "\n") > 4000:
                        chunks.append(current_chunk)
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"

                if current_chunk:
                    chunks.append(current_chunk)

                for chunk in chunks:
                    await event.message.answer(chunk)
            else:
                await event.message.answer(protocol_text)

        except Exception as e:
            logger.error(f"Ошибка при формировании протокола по категориям: {e}")
            await event.message.answer("❌ Произошла ошибка при формировании протокола")

    logger.info("Обработчики администрирования участников зарегистрированы")
