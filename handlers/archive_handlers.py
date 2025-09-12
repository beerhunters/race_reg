"""
Race archive system handlers for the beer mile registration bot.
Handles archiving race data and historical participant management.
"""

import re
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
    participants_count = get_participant_count_by_role("runner") + get_participant_count_by_role("volunteer")
    
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
    
    # Admin commands
    dp.message.register(
        handle_archive_race_command,
        Command("archive_race"),
        F.from_user.id == admin_id
    )
    
    dp.message.register(
        handle_list_archives_command,
        Command("list_archives"),
        F.from_user.id == admin_id
    )
    
    # Admin callback buttons
    async def admin_archive_race_callback(callback: CallbackQuery, state: FSMContext):
        await handle_archive_race_command(callback.message, state)
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
        admin_list_archives_callback,
        F.data == "admin_list_archives",
        F.from_user.id == admin_id
    )
    
    # Archive date input
    dp.message.register(
        handle_archive_date_input,
        StateFilter(RegistrationForm.waiting_for_archive_date)
    )
    
    logger.info("Обработчики архивирования зарегистрированы")