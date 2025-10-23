from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from .utils import logger, RegistrationForm
from database import (
    get_participant_by_user_id,
    get_teams_from_participants,
    set_result,
)


def create_team_management_keyboard():
    """Create keyboard for team management"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список команд", callback_data="list_teams")],
            [InlineKeyboardButton(text="🏁 Записать результат", callback_data="record_team_result")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )
    return keyboard


def register_team_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Register team management handlers"""

    @dp.message(Command("teams"))
    async def teams_command(message: Message):
        """Handle /teams command"""
        user_id = message.from_user.id
        if user_id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return

        text = "🏆 <b>Управление командами</b>\n\n"
        text += "Здесь вы можете управлять командами категории 'Команда'.\n\n"
        text += "Выберите действие:"

        await message.answer(text, reply_markup=create_team_management_keyboard(), parse_mode="HTML")

    @dp.callback_query(F.data == "list_teams")
    async def handle_list_teams(callback: CallbackQuery):
        """List all teams from participants table"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        teams = get_teams_from_participants()

        if not teams:
            await callback.message.edit_text(
                "📋 <b>Список команд</b>\n\nКоманд пока нет.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "📋 <b>Список команд</b>\n\n"

        for i, team in enumerate(teams, 1):
            team_name, member1_id, member1_name, member1_username, member2_id, member2_name, member2_username = team

            text += f"{i}. <b>{team_name}</b>\n"
            text += f"   • {member1_name} (@{member1_username or 'нет username'})\n"
            text += f"   • {member2_name} (@{member2_username or 'нет username'})\n\n"

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    @dp.callback_query(F.data == "record_team_result")
    async def handle_record_team_result_callback(callback: CallbackQuery, state: FSMContext):
        """Handle record team result button"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        teams = get_teams_from_participants()

        if not teams:
            await callback.message.edit_text(
                "❌ Нет команд для записи результатов.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "🏁 <b>Запись результата команды</b>\n\n"
        text += "Список команд:\n\n"

        for i, team in enumerate(teams, 1):
            team_name, member1_id, member1_name, member1_username, member2_id, member2_name, member2_username = team

            # Get current results for members
            member1_info = get_participant_by_user_id(member1_id)
            member2_info = get_participant_by_user_id(member2_id)
            member1_result = member1_info[8] if member1_info else None
            member2_result = member2_info[8] if member2_info else None

            text += f"{i}. <b>{team_name}</b>\n"
            text += f"   • {member1_name} (@{member1_username or 'нет username'}): {member1_result or 'нет результата'}\n"
            text += f"   • {member2_name} (@{member2_username or 'нет username'}): {member2_result or 'нет результата'}\n\n"

        text += "Отправьте сообщение в формате:\n"
        text += "<code>название_команды результат</code>\n\n"
        text += "Пример: <code>Team Alpha 12:34</code>"

        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(RegistrationForm.waiting_for_team_result)
        await callback.answer()

    @dp.message(RegistrationForm.waiting_for_team_result)
    async def handle_team_result_input(message: Message, state: FSMContext):
        """Handle team result input"""
        user_id = message.from_user.id
        if user_id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return

        # Parse input: team_name result
        parts = message.text.strip().split(maxsplit=1)

        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: <code>название_команды результат</code>", parse_mode="HTML")
            return

        team_name_input = parts[0].strip()
        result_time = parts[1].strip()

        # Validate time format (should be in format like 12:34 or 1:23:45)
        if not result_time.replace(":", "").replace(".", "").isdigit():
            await message.answer("❌ Результат должен быть в формате времени (например, 12:34)", parse_mode="HTML")
            return

        # Find team by name
        teams = get_teams_from_participants()
        team_found = None

        for team in teams:
            team_name, member1_id, member1_name, member1_username, member2_id, member2_name, member2_username = team
            if team_name.lower() == team_name_input.lower():
                team_found = team
                break

        if not team_found:
            await message.answer(f"❌ Команда с названием '{team_name_input}' не найдена.", parse_mode="HTML")
            return

        team_name, member1_id, member1_name, member1_username, member2_id, member2_name, member2_username = team_found

        # Set result for both team members
        success1 = set_result(member1_id, result_time)
        success2 = set_result(member2_id, result_time)

        if success1 and success2:
            # Notify admin
            admin_text = f"✅ <b>Результат команды записан!</b>\n\n"
            admin_text += f"🏆 Команда: {team_name}\n"
            admin_text += f"🏁 Результат: {result_time}\n\n"
            admin_text += f"👤 {member1_name} (@{member1_username or 'нет username'}): {result_time}\n"
            admin_text += f"👤 {member2_name} (@{member2_username or 'нет username'}): {result_time}"

            await message.answer(admin_text, parse_mode="HTML")

            # Notify team members
            member1_text = f"🎉 <b>Результат вашей команды записан!</b>\n\n"
            member1_text += f"🏆 Команда: {team_name}\n"
            member1_text += f"🏁 Результат команды: {result_time}\n\n"
            member1_text += f"👤 Ваш результат: {result_time}\n"
            member1_text += f"👤 Результат напарника ({member2_name}): {result_time}\n\n"
            member1_text += f"Поздравляем с завершением гонки! 🎊"

            member2_text = f"🎉 <b>Результат вашей команды записан!</b>\n\n"
            member2_text += f"🏆 Команда: {team_name}\n"
            member2_text += f"🏁 Результат команды: {result_time}\n\n"
            member2_text += f"👤 Ваш результат: {result_time}\n"
            member2_text += f"👤 Результат напарника ({member1_name}): {result_time}\n\n"
            member2_text += f"Поздравляем с завершением гонки! 🎊"

            try:
                await bot.send_message(member1_id, member1_text, parse_mode="HTML")
                logger.info(f"Уведомление о результате команды отправлено участнику {member1_name} (ID: {member1_id})")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления участнику {member1_id}: {e}")

            try:
                await bot.send_message(member2_id, member2_text, parse_mode="HTML")
                logger.info(f"Уведомление о результате команды отправлено участнику {member2_name} (ID: {member2_id})")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления участнику {member2_id}: {e}")

        else:
            await message.answer(f"❌ Ошибка при записи результата команды.", parse_mode="HTML")

        await state.clear()

    logger.info("Обработчики команд зарегистрированы")
