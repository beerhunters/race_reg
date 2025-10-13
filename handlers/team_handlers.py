from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from .utils import logger, RegistrationForm
from database import (
    create_team,
    get_all_teams,
    get_team_by_id,
    get_team_by_member,
    delete_team,
    get_participants_with_team_category,
    get_participant_by_user_id,
    set_team_result,
)


def create_team_management_keyboard():
    """Create keyboard for team management"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Создать команды", callback_data="create_teams")],
            [InlineKeyboardButton(text="📋 Список команд", callback_data="list_teams")],
            [InlineKeyboardButton(text="🏁 Записать результат", callback_data="record_team_result")],
            [InlineKeyboardButton(text="🗑 Удалить команду", callback_data="delete_team_prompt")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )
    return keyboard


def create_team_selection_keyboard(participants: list):
    """Create keyboard for selecting team members"""
    buttons = []
    for user_id, username, name, _, _ in participants:
        display_name = f"{name} (@{username or 'без username'})"
        buttons.append([InlineKeyboardButton(
            text=display_name,
            callback_data=f"select_member_{user_id}"
        )])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_team_creation")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


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
        text += "Здесь вы можете управлять командами категории 'Команда'.\n"
        text += "Результаты команд записываются отдельно от индивидуальных.\n\n"
        text += "Выберите действие:"

        await message.answer(text, reply_markup=create_team_management_keyboard(), parse_mode="HTML")

    @dp.callback_query(F.data == "create_teams")
    async def handle_create_teams(callback: CallbackQuery, state: FSMContext):
        """Handle team creation"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        # Get participants with category 'Команда' who are not in a team yet
        participants = get_participants_with_team_category()

        if len(participants) < 2:
            await callback.message.edit_text(
                "❌ Недостаточно участников с категорией 'Команда' для создания команд.\n"
                "Необходимо минимум 2 участника.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Store participants in state
        await state.update_data(available_participants=participants, selected_members=[])

        text = f"👥 <b>Создание команды</b>\n\n"
        text += f"Доступно участников: {len(participants)}\n\n"
        text += "Выберите первого участника команды:"

        await callback.message.edit_text(
            text,
            reply_markup=create_team_selection_keyboard(participants),
            parse_mode="HTML"
        )
        await state.set_state(RegistrationForm.selecting_team_member1)
        await callback.answer()

    @dp.callback_query(F.data.startswith("select_member_"), RegistrationForm.selecting_team_member1)
    async def handle_select_member1(callback: CallbackQuery, state: FSMContext):
        """Handle selection of first team member"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        user_id = int(callback.data.replace("select_member_", ""))
        data = await state.get_data()
        participants = data.get("available_participants", [])

        # Find selected participant
        selected = None
        remaining = []
        for p in participants:
            if p[0] == user_id:
                selected = p
            else:
                remaining.append(p)

        if not selected:
            await callback.answer("❌ Участник не найден")
            return

        # Store selected member and remaining participants
        await state.update_data(
            selected_members=[user_id],
            available_participants=remaining,
            member1_name=selected[2]
        )

        text = f"👥 <b>Создание команды</b>\n\n"
        text += f"✅ Первый участник: {selected[2]}\n\n"
        text += f"Доступно участников: {len(remaining)}\n\n"
        text += "Выберите второго участника команды:"

        await callback.message.edit_text(
            text,
            reply_markup=create_team_selection_keyboard(remaining),
            parse_mode="HTML"
        )
        await state.set_state(RegistrationForm.selecting_team_member2)
        await callback.answer()

    @dp.callback_query(F.data.startswith("select_member_"), RegistrationForm.selecting_team_member2)
    async def handle_select_member2(callback: CallbackQuery, state: FSMContext):
        """Handle selection of second team member"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        user_id = int(callback.data.replace("select_member_", ""))
        data = await state.get_data()
        selected_members = data.get("selected_members", [])
        member1_id = selected_members[0]
        member1_name = data.get("member1_name", "")

        # Create team
        result = create_team(member1_id, user_id)

        if result["success"]:
            team_name = result["team_name"]
            team_id = result["team_id"]

            # Get both members' info
            member1 = get_participant_by_user_id(member1_id)
            member2 = get_participant_by_user_id(user_id)

            # Notify admin
            admin_text = f"✅ <b>Команда создана!</b>\n\n"
            admin_text += f"🏆 Название: {team_name}\n"
            admin_text += f"🆔 ID команды: {team_id}\n\n"
            admin_text += f"👤 Участник 1: {member1[2]} (ID: {member1_id})\n"
            admin_text += f"👤 Участник 2: {member2[2]} (ID: {user_id})\n"

            await callback.message.edit_text(admin_text, parse_mode="HTML")

            # Notify team members
            member1_text = f"🎉 <b>Вы добавлены в команду!</b>\n\n"
            member1_text += f"🏆 Название команды: {team_name}\n"
            member1_text += f"👥 Ваш напарник: {member2[2]}\n\n"
            member1_text += f"Желаем удачи на гонке!"

            member2_text = f"🎉 <b>Вы добавлены в команду!</b>\n\n"
            member2_text += f"🏆 Название команды: {team_name}\n"
            member2_text += f"👥 Ваш напарник: {member1[2]}\n\n"
            member2_text += f"Желаем удачи на гонке!"

            try:
                await bot.send_message(member1_id, member1_text, parse_mode="HTML")
                logger.info(f"Уведомление о создании команды отправлено участнику {member1[2]} (ID: {member1_id})")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления участнику {member1_id}: {e}")

            try:
                await bot.send_message(user_id, member2_text, parse_mode="HTML")
                logger.info(f"Уведомление о создании команды отправлено участнику {member2[2]} (ID: {user_id})")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления участнику {user_id}: {e}")

        else:
            await callback.message.edit_text(
                f"❌ Ошибка при создании команды:\n{result['error']}",
                parse_mode="HTML"
            )

        await state.clear()
        await callback.answer()

    @dp.callback_query(F.data == "cancel_team_creation")
    async def handle_cancel_team_creation(callback: CallbackQuery, state: FSMContext):
        """Cancel team creation"""
        await callback.message.edit_text("❌ Создание команды отменено.")
        await state.clear()
        await callback.answer()

    @dp.callback_query(F.data == "list_teams")
    async def handle_list_teams(callback: CallbackQuery):
        """List all teams"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        teams = get_all_teams()

        if not teams:
            await callback.message.edit_text(
                "📋 <b>Список команд</b>\n\nКоманд пока нет.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "📋 <b>Список команд</b>\n\n"

        for i, team in enumerate(teams, 1):
            team_id, team_name, result, created_date, member1_id, member1_name, member1_result, member2_id, member2_name, member2_result = team

            text += f"{i}. 🏆 <b>{team_name}</b> (ID: {team_id})\n"
            text += f"   👤 {member1_name} - {member1_result or 'нет результата'}\n"
            text += f"   👤 {member2_name} - {member2_result or 'нет результата'}\n"
            text += f"   🏁 Результат команды: {result or 'нет результата'}\n\n"

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    @dp.callback_query(F.data == "record_team_result")
    async def handle_record_team_result_callback(callback: CallbackQuery, state: FSMContext):
        """Handle record team result button"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        teams = get_all_teams()

        if not teams:
            await callback.message.edit_text(
                "❌ Нет команд для записи результатов.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "🏁 <b>Запись результата команды</b>\n\n"
        text += "Список команд:\n\n"

        for team in teams:
            team_id, team_name, result, _, _, member1_name, member1_result, _, member2_name, member2_result = team
            text += f"• ID: {team_id} - <b>{team_name}</b>\n"
            text += f"  👤 {member1_name}: {member1_result or 'нет результата'}\n"
            text += f"  👤 {member2_name}: {member2_result or 'нет результата'}\n"
            text += f"  🏁 Результат команды: {result or 'нет результата'}\n\n"

        text += "Отправьте сообщение в формате:\n"
        text += "<code>ID_команды результат</code>\n\n"
        text += "Пример: <code>1 12:34</code>"

        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(RegistrationForm.waiting_for_team_result)
        await callback.answer()

    @dp.callback_query(F.data == "delete_team_prompt")
    async def handle_delete_team_prompt(callback: CallbackQuery):
        """Prompt for team ID to delete"""
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Доступ запрещен")
            return

        teams = get_all_teams()

        if not teams:
            await callback.message.edit_text(
                "❌ Нет команд для удаления.",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "🗑 <b>Удаление команды</b>\n\n"
        text += "Список команд:\n\n"

        for team in teams:
            team_id, team_name, _, _, _, member1_name, _, _, member2_name, _ = team
            text += f"• ID: {team_id} - {team_name} ({member1_name} & {member2_name})\n"

        text += "\nОтправьте ID команды для удаления:"

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    @dp.message(Command("set_team_result"))
    async def handle_set_team_result_command(message: Message, state: FSMContext):
        """Handle /set_team_result command"""
        user_id = message.from_user.id
        if user_id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return

        teams = get_all_teams()

        if not teams:
            await message.answer("❌ Нет команд для записи результатов.", parse_mode="HTML")
            return

        text = "🏁 <b>Запись результата команды</b>\n\n"
        text += "Список команд:\n\n"

        for team in teams:
            team_id, team_name, result, _, _, member1_name, member1_result, _, member2_name, member2_result = team
            text += f"• ID: {team_id} - <b>{team_name}</b>\n"
            text += f"  👤 {member1_name}: {member1_result or 'нет результата'}\n"
            text += f"  👤 {member2_name}: {member2_result or 'нет результата'}\n"
            text += f"  🏁 Результат команды: {result or 'нет результата'}\n\n"

        text += "Отправьте сообщение в формате:\n"
        text += "<code>ID_команды результат</code>\n\n"
        text += "Пример: <code>1 12:34</code>"

        await message.answer(text, parse_mode="HTML")
        await state.set_state(RegistrationForm.waiting_for_team_result)

    @dp.message(RegistrationForm.waiting_for_team_result)
    async def handle_team_result_input(message: Message, state: FSMContext):
        """Handle team result input"""
        user_id = message.from_user.id
        if user_id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return

        # Parse input: team_id result
        parts = message.text.strip().split(maxsplit=1)

        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: <code>ID_команды результат</code>", parse_mode="HTML")
            return

        try:
            team_id = int(parts[0])
            result_time = parts[1].strip()
        except ValueError:
            await message.answer("❌ ID команды должен быть числом.", parse_mode="HTML")
            return

        # Validate time format (should be in format like 12:34 or 1:23:45)
        if not result_time.replace(":", "").replace(".", "").isdigit():
            await message.answer("❌ Результат должен быть в формате времени (например, 12:34)", parse_mode="HTML")
            return

        # Get team info
        team = get_team_by_id(team_id)

        if not team:
            await message.answer(f"❌ Команда с ID {team_id} не найдена.", parse_mode="HTML")
            return

        # Set team result
        success = set_team_result(team_id, result_time)

        if success:
            # Get updated team info with member details
            team_data = get_team_by_id(team_id)
            team_id, team_name, _, member1_id, member2_id = team_data

            # Get member info
            member1 = get_participant_by_user_id(member1_id)
            member2 = get_participant_by_user_id(member2_id)

            member1_name = member1[2]
            member2_name = member2[2]
            member1_result = member1[8] or "нет результата"
            member2_result = member2[8] or "нет результата"

            # Notify admin
            admin_text = f"✅ <b>Результат команды записан!</b>\n\n"
            admin_text += f"🏆 Команда: {team_name}\n"
            admin_text += f"🏁 Результат: {result_time}\n\n"
            admin_text += f"👤 {member1_name}: {member1_result}\n"
            admin_text += f"👤 {member2_name}: {member2_result}"

            await message.answer(admin_text, parse_mode="HTML")

            # Notify team members
            member1_text = f"🎉 <b>Результат вашей команды записан!</b>\n\n"
            member1_text += f"🏆 Команда: {team_name}\n"
            member1_text += f"🏁 Результат команды: {result_time}\n\n"
            member1_text += f"👤 Ваш результат: {member1_result}\n"
            member1_text += f"👤 Результат напарника ({member2_name}): {member2_result}\n\n"
            member1_text += f"Поздравляем с завершением гонки! 🎊"

            member2_text = f"🎉 <b>Результат вашей команды записан!</b>\n\n"
            member2_text += f"🏆 Команда: {team_name}\n"
            member2_text += f"🏁 Результат команды: {result_time}\n\n"
            member2_text += f"👤 Ваш результат: {member2_result}\n"
            member2_text += f"👤 Результат напарника ({member1_name}): {member1_result}\n\n"
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
