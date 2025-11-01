"""
Race archive system handlers for the beer mile registration bot.
Handles archiving race data and historical participant management.
"""

import re
import sqlite3
from datetime import datetime

from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from logging_config import get_logger
from .validation import sanitize_input
from .utils import messages, RegistrationForm
from database import (
    archive_race_data,
    get_user_race_history,
    get_latest_user_result,
    list_race_archives,
    is_current_event_active,
    get_participant_count_by_role,
    DB_PATH,
)

logger = get_logger(__name__)


async def handle_archive_race_command(message: Message, state: FSMContext):
    """Handle /archive_race command (admin only)"""
    await message.answer(messages["archive_race_prompt"])
    await state.set_state(RegistrationForm.waiting_for_archive_date)


async def handle_archive_date_input(message: Message, state: FSMContext):
    """Handle archive date input from admin"""
    date_input = sanitize_input(message.text, 20)
    
    # Validate date format (YYYY-MM-DD)
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, date_input):
        await message.answer(messages["archive_race_invalid_date"])
        return
    
    try:
        # Validate that it's a real date
        datetime.strptime(date_input, '%Y-%m-%d')
    except ValueError:
        await message.answer(messages["archive_race_invalid_date"])
        return
    
    # Get counts for reporting BEFORE archiving
    participants_count = get_participant_count_by_role("runner")
    
    # Perform archiving
    success = archive_race_data(date_input)
    
    if success: 
        
        # Get total users count from bot_users table
        from database import get_all_bot_users
        total_users = len(get_all_bot_users())
        
        formatted_date = date_input.replace('-', '_')
        
        await message.answer(
            messages["archive_race_success"].format(
                date=formatted_date,
                participants_count=participants_count,
                total_users=total_users
            )
        )
        logger.info(f"Администратор {message.from_user.id} заархивировал данные гонки на дату {date_input}")
    else:
        await message.answer(messages["archive_race_error"])
    
    await state.clear()


async def handle_list_archives_command(message: Message):
    """Handle /list_archives command (admin only)"""
    archives = list_race_archives()

    if not archives:
        await message.answer("📂 Архивных гонок не найдено.")
        return

    text = "📂 <b>Архивные гонки:</b>\n\n"
    for i, archive_name in enumerate(archives, 1):
        race_date = archive_name.replace('race_', '').replace('_', '-')
        text += f"{i}. {race_date}\n"

    await message.answer(text)


def create_finish_event_confirmation_keyboard():
    """Create keyboard for finish event confirmation"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить архивирование", callback_data="confirm_finish_event"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_finish_event")
            ]
        ]
    )
    return keyboard


async def handle_finish_event_command(message: Message, state: FSMContext):
    """Handle finish event command - new name for archive_race (admin only)"""
    from database import get_setting

    # Get current event date
    reg_end_date = get_setting("reg_end_date")

    if not reg_end_date:
        await message.answer(
            "⚠️ <b>Нет активного события</b>\n\n"
            "Дата окончания регистрации не установлена. Невозможно завершить мероприятие."
        )
        return

    # Get counts for reporting
    participants_count = get_participant_count_by_role("runner")

    if participants_count == 0:
        await message.answer(
            "⚠️ <b>Нет участников для архивирования</b>\n\n"
            "В базе данных нет зарегистрированных участников."
        )
        return

    # Show confirmation with statistics
    runners_count = get_participant_count_by_role("runner")

    # Count paid runners using direct SQL query
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM participants WHERE role = 'runner' AND payment_status = 'paid'")
        paid_count = cursor.fetchone()[0]

    await message.answer(
        messages.get("finish_event_confirmation",
            "🏁 <b>Завершение актуального мероприятия</b>\n\n"
            "📅 Дата события: <b>{date}</b>\n\n"
            "📊 <b>Статистика:</b>\n"
            "👥 Всего участников: <b>{total}</b>\n"
            "🏃 Бегунов: <b>{runners}</b>\n"
            "💳 Оплативших: <b>{paid}/{runners}</b>\n\n"
            "⚠️ <b>Внимание!</b>\n"
            "После архивирования:\n"
            "• Данные участников будут сохранены в архивную таблицу\n"
            "• Текущая таблица участников будет очищена\n"
            "• Событие будет завершено\n\n"
            "Продолжить?"
        ).format(date=reg_end_date, total=participants_count, runners=runners_count, paid=paid_count),
        reply_markup=create_finish_event_confirmation_keyboard()
    )
    await state.set_state(RegistrationForm.waiting_for_finish_event_confirmation)


async def handle_confirm_finish_event(callback: CallbackQuery, state: FSMContext):
    """Handle finish event confirmation"""
    from database import get_setting, set_setting

    # Get event date
    reg_end_date = get_setting("reg_end_date")

    if not reg_end_date:
        await callback.message.edit_text(
            "❌ Ошибка: дата окончания регистрации не найдена."
        )
        await state.clear()
        return

    # Get counts for reporting BEFORE archiving
    participants_count = get_participant_count_by_role("runner")

    # Perform archiving - convert date format from "HH:MM DD.MM.YYYY" to "YYYY-MM-DD"
    try:
        from datetime import datetime
        date_obj = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
        archive_date = date_obj.strftime("%Y-%m-%d")
    except ValueError:
        await callback.message.edit_text(
            f"❌ Ошибка при обработке даты: {reg_end_date}"
        )
        await state.clear()
        return

    success = archive_race_data(archive_date)

    if success:
        # Get total users count from bot_users table
        from database import get_all_bot_users
        total_users = len(get_all_bot_users())

        formatted_date = archive_date.replace('-', '_')

        # Clear reg_end_date setting to mark event as finished
        set_setting("reg_end_date", "")

        await callback.message.edit_text(
            messages.get("finish_event_success",
                "✅ <b>Мероприятие успешно завершено!</b>\n\n"
                "📂 Создан архив: <code>race_{date}</code>\n"
                "👥 Заархивировано участников: <b>{count}</b>\n"
                "📊 Всего пользователей бота: <b>{total_users}</b>\n\n"
                "Таблица участников очищена.\n"
                "Теперь можно создать новое событие! ➕"
            ).format(date=formatted_date, count=participants_count, total_users=total_users)
        )
        logger.info(f"Администратор завершил мероприятие, заархивировано {participants_count} участников")
    else:
        await callback.message.edit_text(
            messages.get("archive_race_error",
                "❌ Ошибка при архивировании мероприятия.\n\n"
                "Проверьте логи для подробной информации."
            )
        )

    await state.clear()
    await callback.answer("Готово!")


async def handle_cancel_finish_event(callback: CallbackQuery, state: FSMContext):
    """Handle finish event cancellation"""
    await callback.message.edit_text(
        "❌ Завершение мероприятия отменено.\n\n"
        "Данные участников сохранены."
    )
    await state.clear()
    await callback.answer("Отменено")


def create_historical_participant_keyboard():
    """Create keyboard for historical participants"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["register_new_event_button"], 
                    callback_data="start_registration"
                )
            ]
        ]
    )
    return keyboard


async def handle_historical_participant(user_id: int, message: Message):
    """Handle start command for users with historical participation"""
    # Check if user is historical participant (exists in any archived race table)
    from database import get_historical_participants
    historical_user_ids = get_historical_participants()
    
    if user_id not in historical_user_ids:
        return False  # Not a historical participant, proceed with normal flow
    
    # Get latest race data for this user
    latest_result = get_latest_user_result(user_id)
    
    if not latest_result:
        return False  # No data found, proceed with normal flow
    
    is_active_event = is_current_event_active()
    result_text = latest_result.get('result', 'не указан')
    race_date = latest_result.get('race_date', 'неизвестно')
    
    # Show historical participant message regardless of result
    if is_active_event:
        if result_text and result_text not in ['не указан', '', None]:
            text = messages["historical_participant_current_event"].format(
                result=result_text,
                race_date=race_date
            )
        else:
            text = messages["historical_participant_no_result"].format(
                race_date=race_date
            )
        await message.answer(text, reply_markup=create_historical_participant_keyboard())
    else:
        if result_text and result_text not in ['не указан', '', None]:
            text = messages["historical_participant_no_event"].format(
                result=result_text,
                race_date=race_date
            )
        else:
            text = messages["historical_participant_no_event"].format(
                result="участие зафиксировано",
                race_date=race_date
            )
        await message.answer(text)
    
    return True  # Historical data processed


def register_archive_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Register archive handlers"""

    # Admin commands - old archive_race (kept for compatibility)
    dp.message.register(
        handle_archive_race_command,
        Command("archive_race"),
        F.from_user.id == admin_id
    )

    # New finish_event command
    dp.message.register(
        handle_finish_event_command,
        Command("finish_event"),
        F.from_user.id == admin_id
    )

    dp.message.register(
        handle_list_archives_command,
        Command("list_archives"),
        F.from_user.id == admin_id
    )

    # Admin callback buttons - old archive_race
    async def admin_archive_race_callback(callback: CallbackQuery, state: FSMContext):
        await handle_archive_race_command(callback.message, state)
        await callback.answer()

    # New finish_event callback
    async def admin_finish_event_callback(callback: CallbackQuery, state: FSMContext):
        await callback.message.delete()
        await handle_finish_event_command(callback.message, state)
        await callback.answer()

    async def admin_list_archives_callback(callback: CallbackQuery):
        await handle_list_archives_command(callback.message)
        await callback.answer()

    dp.callback_query.register(
        admin_archive_race_callback,
        F.data == "admin_archive_race",
        F.from_user.id == admin_id
    )

    dp.callback_query.register(
        admin_finish_event_callback,
        F.data == "admin_finish_event",
        F.from_user.id == admin_id
    )

    dp.callback_query.register(
        admin_list_archives_callback,
        F.data == "admin_list_archives",
        F.from_user.id == admin_id
    )

    # Archive date input (old flow)
    dp.message.register(
        handle_archive_date_input,
        StateFilter(RegistrationForm.waiting_for_archive_date)
    )

    # Finish event confirmation callbacks
    dp.callback_query.register(
        handle_confirm_finish_event,
        F.data == "confirm_finish_event",
        F.from_user.id == admin_id
    )

    dp.callback_query.register(
        handle_cancel_finish_event,
        F.data == "cancel_finish_event",
        F.from_user.id == admin_id
    )

    logger.info("Обработчики архивирования зарегистрированы")