from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from .utils import (
    logger,
    messages,
    RegistrationForm,
    create_edit_profile_keyboard,
    create_gender_keyboard,
    create_edit_confirmation_keyboard,
    create_admin_edit_approval_keyboard,
    create_main_menu_keyboard,
)
from .validation import validate_name, validate_time_format, sanitize_input
from database import (
    get_participant_by_user_id,
    create_edit_request,
    get_pending_edit_requests,
    approve_edit_request,
    reject_edit_request,
)


def format_field_name(field: str) -> str:
    """Format database field name for display"""
    field_names = {
        'name': 'Имя',
        'target_time': 'Целевое время',
        'gender': 'Пол'
    }
    return field_names.get(field, field)


def format_gender_display(gender: str) -> str:
    """Format gender for display"""
    return "Мужской" if gender == "male" else "Женский" if gender == "female" else "Не указан"


async def handle_edit_profile_command(message: Message, state: FSMContext):
    """Handle /edit_profile command"""
    user_id = message.from_user.id
    participant = get_participant_by_user_id(user_id)
    
    if not participant:
        await message.answer(messages["edit_profile_not_registered"], reply_markup=create_main_menu_keyboard())
        return
    
    # participant tuple: (user_id, username, name, target_time, role, reg_date, payment_status, bib_number, result, gender, category, cluster)
    name = participant[2] or "Не указано"
    target_time = participant[3] or "Не указано"
    gender = format_gender_display(participant[9])
    role = "Бегун" if participant[4] == "runner" else "Волонтёр"
    
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
        category = "📂 Не назначена"
    
    # Кластер с эмодзи
    if participant[11]:
        cluster_emoji = {
            "A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴"
        }.get(participant[11], "🎯")
        cluster = f"{cluster_emoji} {participant[11]}"
    else:
        cluster = "🎯 Не назначен"
    
    text = messages["edit_profile_start"].format(
        name=name,
        target_time=target_time,
        gender=gender,
        role=role,
        category=category,
        cluster=cluster
    )
    
    await message.answer(text, reply_markup=create_edit_profile_keyboard())
    await state.set_state(RegistrationForm.waiting_for_edit_field_selection)


async def handle_edit_field_selection(callback: CallbackQuery, state: FSMContext):
    """Handle field selection for editing"""
    user_id = callback.from_user.id
    participant = get_participant_by_user_id(user_id)
    
    if not participant:
        await callback.message.edit_text(messages["edit_profile_not_registered"])
        await state.clear()
        return
    
    await state.update_data(participant=participant)
    
    if callback.data == "edit_name":
        await callback.message.edit_text(messages["edit_name_prompt"])
        await state.set_state(RegistrationForm.waiting_for_new_name)
    elif callback.data == "edit_target_time":
        await callback.message.edit_text(messages["edit_target_time_prompt"])
        await state.set_state(RegistrationForm.waiting_for_new_target_time)
    elif callback.data == "edit_gender":
        await callback.message.edit_text(
            messages["edit_gender_prompt"],
            reply_markup=create_gender_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_new_gender)
    elif callback.data == "cancel_edit":
        await callback.message.edit_text(messages["edit_cancelled"])
        await state.clear()
    
    await callback.answer()


async def handle_new_name_input(message: Message, state: FSMContext):
    """Handle new name input"""
    new_name = sanitize_input(message.text, 50)
    
    is_valid, error_message = validate_name(new_name)
    if not is_valid:
        await message.answer(f"❌ {error_message}", reply_markup=create_main_menu_keyboard())
        return
    
    data = await state.get_data()
    participant = data.get("participant")
    old_name = participant[2]
    
    if new_name == old_name:
        await message.answer(messages["edit_same_value"], reply_markup=create_main_menu_keyboard())
        await state.clear()
        return
    
    await state.update_data(
        field="name",
        field_name="Имя",
        old_value=old_name,
        new_value=new_name,
        new_value_raw=new_name
    )
    
    text = messages["edit_confirmation"].format(
        field_name="Имя",
        old_value=old_name,
        new_value=new_name
    )
    
    await message.answer(text, reply_markup=create_edit_confirmation_keyboard())
    await state.set_state(RegistrationForm.waiting_for_edit_confirmation)


async def handle_new_target_time_input(message: Message, state: FSMContext):
    """Handle new target time input"""
    new_time = sanitize_input(message.text, 10)
    
    is_valid, error_message = validate_time_format(new_time)
    if not is_valid:
        await message.answer(f"❌ {error_message}", reply_markup=create_main_menu_keyboard())
        return
    
    data = await state.get_data()
    participant = data.get("participant")
    old_time = participant[3] or "Не указано"
    
    if new_time == old_time:
        await message.answer(messages["edit_same_value"], reply_markup=create_main_menu_keyboard())
        await state.clear()
        return
    
    await state.update_data(
        field="target_time",
        field_name="Целевое время",
        old_value=old_time,
        new_value=new_time,
        new_value_raw=new_time
    )
    
    text = messages["edit_confirmation"].format(
        field_name="Целевое время",
        old_value=old_time,
        new_value=new_time
    )
    
    await message.answer(text, reply_markup=create_edit_confirmation_keyboard())
    await state.set_state(RegistrationForm.waiting_for_edit_confirmation)


async def handle_new_gender_selection(callback: CallbackQuery, state: FSMContext):
    """Handle new gender selection"""
    if callback.data in ["male", "female"]:
        new_gender = callback.data
        new_gender_display = format_gender_display(new_gender)
        
        data = await state.get_data()
        participant = data.get("participant")
        old_gender = participant[9]
        old_gender_display = format_gender_display(old_gender)
        
        if new_gender == old_gender:
            await callback.message.edit_text(messages["edit_same_value"])
            await state.clear()
            await callback.answer()
            return
        
        await state.update_data(
            field="gender",
            field_name="Пол",
            old_value=old_gender_display,
            new_value=new_gender_display,
            new_value_raw=new_gender
        )
        
        text = messages["edit_confirmation"].format(
            field_name="Пол",
            old_value=old_gender_display,
            new_value=new_gender_display
        )
        
        await callback.message.edit_text(text, reply_markup=create_edit_confirmation_keyboard())
        await state.set_state(RegistrationForm.waiting_for_edit_confirmation)
    
    elif callback.data == "cancel_edit":
        await callback.message.edit_text(messages["edit_cancelled"])
        await state.clear()
    
    await callback.answer()


async def handle_edit_confirmation(callback: CallbackQuery, state: FSMContext, bot: Bot, admin_id: int):
    """Handle edit confirmation"""
    if callback.data == "cancel_edit":
        await callback.message.edit_text("❌ Редактирование отменено.")
        await state.clear()
        await callback.answer()
        return
        
    if callback.data == "confirm_edit":
        data = await state.get_data()
        participant = data.get("participant")
        field = data.get("field")
        field_name = data.get("field_name")
        old_value = data.get("old_value")
        new_value = data.get("new_value")
        new_value_raw = data.get("new_value_raw", new_value)
        
        user_id = callback.from_user.id
        
        # Create edit request
        success = create_edit_request(user_id, field, old_value, new_value_raw)
        
        if success:
            # Notify user
            text = messages["edit_request_created"].format(
                field_name=field_name,
                old_value=old_value,
                new_value=new_value
            )
            await callback.message.edit_text(text)
            
            # Get the latest edit requests to find the one we just created
            edit_requests = get_pending_edit_requests()
            request_data = None
            for req in edit_requests:
                if req[1] == user_id and req[4] == field:  # user_id and field match
                    request_data = req
                    break
            
            if request_data:
                # Notify admin
                request_id, _, name, username, _, old_val, new_val, request_date = request_data
                admin_text = messages["admin_edit_request"].format(
                    name=name,
                    username=username or "нет",
                    user_id=user_id,
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                    request_date=request_date
                )
                
                try:
                    await bot.send_message(
                        admin_id,
                        admin_text,
                        reply_markup=create_admin_edit_approval_keyboard(request_id)
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления администратору: {e}")
        else:
            await callback.message.edit_text(messages["edit_request_error"])
        
        await state.clear()
    
    await callback.answer()


async def handle_admin_edit_approval(callback: CallbackQuery, bot: Bot):
    """Handle admin approval/rejection of edit requests"""
    if callback.data.startswith("approve_edit_"):
        request_id = int(callback.data.replace("approve_edit_", ""))
        
        # Get request data before approval
        requests = get_pending_edit_requests()
        request_data = None
        for req in requests:
            if req[0] == request_id:
                request_data = req
                break
        
        if not request_data:
            await callback.message.edit_text(messages["admin_edit_not_found"])
            await callback.answer()
            return
        
        success = approve_edit_request(request_id)
        
        if success:
            # Notify user
            _, user_id, _, _, field, _, new_value, _ = request_data
            field_name = format_field_name(field)
            
            try:
                await bot.send_message(
                    user_id,
                    messages["edit_request_approved"].format(
                        field_name=field_name,
                        new_value=new_value
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            
            await callback.message.edit_text(messages["admin_edit_approved"])
        else:
            await callback.message.edit_text(messages["admin_edit_not_found"])
    
    elif callback.data.startswith("reject_edit_"):
        request_id = int(callback.data.replace("reject_edit_", ""))
        
        # Get request data before rejection
        requests = get_pending_edit_requests()
        request_data = None
        for req in requests:
            if req[0] == request_id:
                request_data = req
                break
        
        if not request_data:
            await callback.message.edit_text(messages["admin_edit_not_found"])
            await callback.answer()
            return
        
        success = reject_edit_request(request_id)
        
        if success:
            # Notify user
            _, user_id, _, _, field, _, new_value, _ = request_data
            field_name = format_field_name(field)
            
            try:
                await bot.send_message(
                    user_id,
                    messages["edit_request_rejected"].format(
                        field_name=field_name,
                        new_value=new_value
                    )
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            
            await callback.message.edit_text(messages["admin_edit_rejected"])
        else:
            await callback.message.edit_text(messages["admin_edit_not_found"])
    
    await callback.answer()


async def handle_edit_requests_command(message: Message):
    """Handle /edit_requests command (admin only)"""
    edit_requests = get_pending_edit_requests()
    
    if not edit_requests:
        await message.answer(messages["admin_edit_requests_empty"])
        return
    
    text = messages["admin_edit_requests_header"]
    
    for i, (request_id, user_id, name, username, field, old_value, new_value, request_date) in enumerate(edit_requests, 1):
        field_name = format_field_name(field)
        text += f"{i}. <b>{name}</b> (@{username or 'нет'})\n"
        text += f"   • {field_name}: <code>{old_value}</code> → <code>{new_value}</code>\n"
        text += f"   • ID запроса: <code>{request_id}</code>\n"
        text += f"   • Дата: {request_date}\n\n"
    
    await message.answer(text)


def register_profile_edit_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Register profile editing handlers"""
    
    # User commands
    dp.message.register(
        handle_edit_profile_command,
        Command("edit_profile")
    )
    
    # Admin commands
    dp.message.register(
        handle_edit_requests_command,
        Command("edit_requests"),
        F.from_user.id == admin_id
    )
    
    # Field selection
    dp.callback_query.register(
        handle_edit_field_selection,
        StateFilter(RegistrationForm.waiting_for_edit_field_selection)
    )
    
    # Input handlers
    dp.message.register(
        handle_new_name_input,
        StateFilter(RegistrationForm.waiting_for_new_name)
    )
    
    dp.message.register(
        handle_new_target_time_input,
        StateFilter(RegistrationForm.waiting_for_new_target_time)
    )
    
    dp.callback_query.register(
        handle_new_gender_selection,
        StateFilter(RegistrationForm.waiting_for_new_gender)
    )
    
    # Confirmation
    async def edit_confirmation_wrapper(callback: CallbackQuery, state: FSMContext):
        await handle_edit_confirmation(callback, state, bot, admin_id)
    
    dp.callback_query.register(
        edit_confirmation_wrapper,
        StateFilter(RegistrationForm.waiting_for_edit_confirmation)
    )
    
    # Admin approval/rejection
    async def admin_edit_approval_wrapper(callback: CallbackQuery):
        await handle_admin_edit_approval(callback, bot)
    
    dp.callback_query.register(
        admin_edit_approval_wrapper,
        F.data.startswith(("approve_edit_", "reject_edit_"))
    )
    
    
    logger.info("Обработчики редактирования профилей зарегистрированы")