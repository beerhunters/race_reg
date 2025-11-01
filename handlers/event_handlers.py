"""
Event management handlers for creating and managing racing events.
Handles event creation flow with location, date, and pricing setup.
"""

import re
from datetime import datetime
from pytz import timezone

from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from logging_config import get_logger, log
from .utils import messages, RegistrationForm
from .validation import sanitize_input
from database import (
    set_setting,
    get_setting,
    get_participant_count,
    clear_participants,
)

logger = get_logger(__name__)


def create_event_confirmation_keyboard():
    """Create keyboard for event creation confirmation"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_create_event"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_create_event")
            ]
        ]
    )
    return keyboard


async def handle_create_event_command(message: Message, state: FSMContext):
    """Handle /create_event command or callback (admin only)"""
    log.admin_action("create_event_start", message.from_user.id)

    # Check if there are existing participants
    participants_count = get_participant_count()
    if participants_count > 0:
        await message.answer(
            "⚠️ <b>Внимание!</b>\n\n"
            f"В базе данных есть {participants_count} участник(ов).\n"
            "Перед созданием нового события необходимо завершить и заархивировать текущее мероприятие.\n\n"
            "Используйте: <b>🏁 Управление гонкой → Закончить актуальное мероприятие</b>"
        )
        return

    await message.answer(
        messages.get("create_event_start",
            "🎉 <b>Создание нового события</b>\n\n"
            "Давайте настроим новое мероприятие. Я задам вам несколько вопросов.\n\n"
            "📍 <b>Шаг 1/3:</b> Укажите место проведения события\n"
            "(Например: Парк Горького, Москва)"
        )
    )
    await state.set_state(RegistrationForm.waiting_for_create_event_location)


async def handle_event_location_input(message: Message, state: FSMContext):
    """Handle event location input"""
    location = sanitize_input(message.text, 200)

    if not location or len(location) < 3:
        await message.answer(
            messages.get("event_invalid_location",
                "❌ Место проведения должно содержать минимум 3 символа.\n\n"
                "Пожалуйста, введите место проведения снова:"
            )
        )
        return

    # Save location to state
    await state.update_data(event_location=location)

    await message.answer(
        messages.get("create_event_location_prompt",
            "✅ Место проведения: <b>{location}</b>\n\n"
            "📅 <b>Шаг 2/3:</b> Укажите дату и время окончания регистрации\n\n"
            "Формат: <code>ЧЧ:ММ ДД.ММ.ГГГГ</code>\n"
            "Например: <code>23:59 31.12.2024</code>"
        ).format(location=location)
    )
    await state.set_state(RegistrationForm.waiting_for_create_event_date)


async def handle_event_date_input(message: Message, state: FSMContext):
    """Handle event date input"""
    date_input = sanitize_input(message.text, 20)

    # Validate date format (HH:MM DD.MM.YYYY)
    date_pattern = r'^\d{2}:\d{2}\s+\d{2}\.\d{2}\.\d{4}$'
    if not re.match(date_pattern, date_input):
        await message.answer(
            messages.get("event_invalid_date",
                "❌ Неверный формат даты!\n\n"
                "Используйте формат: <code>ЧЧ:ММ ДД.ММ.ГГГГ</code>\n"
                "Например: <code>23:59 31.12.2024</code>\n\n"
                "Попробуйте снова:"
            )
        )
        return

    # Validate that it's a real date and in the future
    try:
        event_datetime = datetime.strptime(date_input, "%H:%M %d.%m.%Y")
        moscow_tz = timezone("Europe/Moscow")
        event_datetime = moscow_tz.localize(event_datetime)
        current_time = datetime.now(moscow_tz)

        if event_datetime <= current_time:
            await message.answer(
                "❌ Дата окончания регистрации должна быть в будущем!\n\n"
                "Пожалуйста, укажите будущую дату:"
            )
            return

    except ValueError:
        await message.answer(
            messages.get("event_invalid_date",
                "❌ Некорректная дата! Проверьте правильность введённой даты.\n\n"
                "Попробуйте снова:"
            )
        )
        return

    # Save registration end date to state
    await state.update_data(reg_end_date=date_input)

    # Calculate event_date as next day after registration ends
    try:
        from datetime import timedelta
        reg_end_datetime = datetime.strptime(date_input, "%H:%M %d.%m.%Y")
        event_datetime = reg_end_datetime + timedelta(days=1)
        event_date_str = event_datetime.strftime("%d %B %Y")
        # Convert month name to Russian
        months_ru = {
            'January': 'января', 'February': 'февраля', 'March': 'марта',
            'April': 'апреля', 'May': 'мая', 'June': 'июня',
            'July': 'июля', 'August': 'августа', 'September': 'сентября',
            'October': 'октября', 'November': 'ноября', 'December': 'декабря'
        }
        for eng, rus in months_ru.items():
            event_date_str = event_date_str.replace(eng, rus)
        await state.update_data(event_date=event_date_str)
    except Exception as e:
        logger.error(f"Ошибка при вычислении даты события: {e}")
        event_date_str = "не определена"

    await message.answer(
        messages.get("create_event_time_prompt",
            "✅ Дата окончания регистрации: <b>{reg_end_date}</b>\n"
            "✅ Дата проведения события: <b>{event_date}</b>\n\n"
            "🕒 <b>Шаг 3/4:</b> Укажите время начала события\n\n"
            "Формат: <code>ЧЧ:ММ</code>\n"
            "Например: <code>14:00</code>"
        ).format(reg_end_date=date_input, event_date=event_date_str)
    )
    await state.set_state(RegistrationForm.waiting_for_create_event_time)


async def handle_event_time_input(message: Message, state: FSMContext):
    """Handle event time input"""
    time_input = sanitize_input(message.text, 10)

    # Validate time format (HH:MM)
    time_pattern = r'^\d{2}:\d{2}$'
    if not re.match(time_pattern, time_input):
        await message.answer(
            messages.get("event_invalid_time",
                "❌ Неверный формат времени!\n\n"
                "Используйте формат: <code>ЧЧ:ММ</code>\n"
                "Например: <code>14:00</code>\n\n"
                "Попробуйте снова:"
            )
        )
        return

    # Validate that it's a valid time
    try:
        hours, minutes = map(int, time_input.split(':'))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError("Invalid time range")
    except ValueError:
        await message.answer(
            messages.get("event_invalid_time",
                "❌ Некорректное время! Часы должны быть от 00 до 23, минуты от 00 до 59.\n\n"
                "Попробуйте снова:"
            )
        )
        return

    # Save time to state
    await state.update_data(event_time=time_input)

    # Get current price from config or settings
    current_price = get_setting("participation_fee")
    if not current_price:
        from .utils import config
        current_price = config.get("participation_fee", 750)

    await message.answer(
        messages.get("create_event_price_prompt",
            "✅ Время начала события: <b>{time}</b>\n\n"
            "💰 <b>Шаг 4/4:</b> Укажите стоимость участия в рублях\n\n"
            "Текущая цена: <b>{current_price} ₽</b>\n"
            "Введите новую цену или отправьте '-' чтобы оставить текущую:"
        ).format(time=time_input, current_price=current_price)
    )
    await state.set_state(RegistrationForm.waiting_for_event_price)


async def handle_event_price_input(message: Message, state: FSMContext):
    """Handle event price input"""
    price_input = sanitize_input(message.text, 10)

    # If user sends '-', keep current price
    if price_input == '-':
        current_price = get_setting("participation_fee")
        if not current_price:
            from .utils import config
            current_price = config.get("participation_fee", 750)
        price = current_price
    else:
        # Validate price (must be a positive number)
        try:
            price = int(price_input)
            if price < 0:
                await message.answer(
                    messages.get("event_invalid_price",
                        "❌ Цена должна быть положительным числом!\n\n"
                        "Введите стоимость участия в рублях:"
                    )
                )
                return
        except ValueError:
            await message.answer(
                messages.get("event_invalid_price",
                    "❌ Цена должна быть числом!\n\n"
                    "Введите стоимость участия в рублях или '-' чтобы оставить текущую:"
                )
            )
            return

    # Save price to state
    await state.update_data(event_price=price)

    # Get all data from state
    data = await state.get_data()
    location = data.get('event_location')
    reg_end_date = data.get('reg_end_date')
    event_date = data.get('event_date')
    event_time = data.get('event_time')

    # Show confirmation
    await message.answer(
        messages.get("create_event_confirmation",
            "📋 <b>Проверьте данные нового события:</b>\n\n"
            "📍 Место проведения: <b>{location}</b>\n"
            "📅 Дата проведения: <b>{event_date}</b>\n"
            "🕒 Время начала: <b>{event_time}</b>\n"
            "📅 Регистрация до: <b>{reg_end_date}</b>\n"
            "💰 Стоимость участия: <b>{price} ₽</b>\n\n"
            "❓ Всё верно? Создаём событие?"
        ).format(location=location, event_date=event_date, event_time=event_time,
                 reg_end_date=reg_end_date, price=price),
        reply_markup=create_event_confirmation_keyboard()
    )
    await state.set_state(RegistrationForm.waiting_for_event_confirmation)


async def handle_confirm_create_event(callback: CallbackQuery, state: FSMContext):
    """Handle event creation confirmation"""
    data = await state.get_data()
    location = data.get('event_location')
    event_date = data.get('event_date')
    event_time = data.get('event_time')
    reg_end_date = data.get('reg_end_date')
    price = data.get('event_price')

    # Save to database
    set_setting("event_location", location)
    set_setting("event_date", event_date)
    set_setting("event_time", event_time)
    set_setting("reg_end_date", reg_end_date)
    set_setting("participation_fee", price)

    log.admin_action("event_created", callback.from_user.id,
                     f"Location: {location}, Date: {event_date}, Time: {event_time}, Reg ends: {reg_end_date}, Price: {price}")

    await callback.message.edit_text(
        messages.get("create_event_success",
            "✅ <b>Событие успешно создано!</b>\n\n"
            "📍 Место: <b>{location}</b>\n"
            "📅 Дата проведения: <b>{event_date}</b>\n"
            "🕒 Время начала: <b>{event_time}</b>\n"
            "📅 Регистрация до: <b>{reg_end_date}</b>\n"
            "💰 Стоимость: <b>{price} ₽</b>\n\n"
            "Теперь пользователи могут регистрироваться на мероприятие! 🎉"
        ).format(location=location, event_date=event_date, event_time=event_time,
                 reg_end_date=reg_end_date, price=price)
    )
    await state.clear()
    await callback.answer("Событие создано!")


async def handle_cancel_create_event(callback: CallbackQuery, state: FSMContext):
    """Handle event creation cancellation"""
    await callback.message.edit_text(
        "❌ Создание события отменено.\n\n"
        "Данные не сохранены."
    )
    await state.clear()
    await callback.answer("Отменено")


def register_event_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Register event management handlers"""

    # Command handler
    dp.message.register(
        handle_create_event_command,
        Command("create_event"),
        F.from_user.id == admin_id
    )

    # Callback handler for button
    async def create_event_callback(callback: CallbackQuery, state: FSMContext):
        await callback.message.delete()
        await handle_create_event_command(callback.message, state)
        await callback.answer()

    dp.callback_query.register(
        create_event_callback,
        F.data == "admin_create_event",
        F.from_user.id == admin_id
    )

    # FSM state handlers
    dp.message.register(
        handle_event_location_input,
        StateFilter(RegistrationForm.waiting_for_create_event_location)
    )

    dp.message.register(
        handle_event_date_input,
        StateFilter(RegistrationForm.waiting_for_create_event_date)
    )

    dp.message.register(
        handle_event_time_input,
        StateFilter(RegistrationForm.waiting_for_create_event_time)
    )

    dp.message.register(
        handle_event_price_input,
        StateFilter(RegistrationForm.waiting_for_event_price)
    )

    # Confirmation callbacks
    dp.callback_query.register(
        handle_confirm_create_event,
        F.data == "confirm_create_event",
        F.from_user.id == admin_id
    )

    dp.callback_query.register(
        handle_cancel_create_event,
        F.data == "cancel_create_event",
        F.from_user.id == admin_id
    )

    logger.info("Обработчики управления событиями зарегистрированы")
