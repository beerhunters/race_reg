import os
import re
import sqlite3
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
    create_role_keyboard,
    create_register_keyboard,
    create_gender_keyboard,
)
from database import (
    get_participant_by_user_id,
    add_pending_registration,
    add_participant,
    get_participant_count,
    get_participant_count_by_role,
    get_setting,
    get_past_races,
    delete_pending_registration,
    delete_participant,
)


def register_registration_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    def create_admin_commands_keyboard():
        commands = [
            InlineKeyboardButton(
                text="👥 Участники", callback_data="category_participants"
            ),
            InlineKeyboardButton(
                text="🏁 Управление гонкой", callback_data="category_race"
            ),
            InlineKeyboardButton(
                text="📢 Уведомления", callback_data="category_notifications"
            ),
        ]
        # return InlineKeyboardMarkup(inline_keyboard=[commands])
        return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])

    def create_participants_category_keyboard():
        commands = [
            InlineKeyboardButton(
                text="Список участников", callback_data="admin_participants"
            ),
            InlineKeyboardButton(
                text="Незавершённые регистрации", callback_data="admin_pending"
            ),
            InlineKeyboardButton(text="Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="Подтвердить оплату", callback_data="admin_paid"),
            InlineKeyboardButton(text="Присвоить номер", callback_data="admin_set_bib"),
            InlineKeyboardButton(
                text="Удалить участника", callback_data="admin_remove"
            ),
            InlineKeyboardButton(text="Экспорт в CSV", callback_data="admin_export"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        ]
        return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])

    def create_race_category_keyboard():
        commands = [
            InlineKeyboardButton(
                text="Информация о забеге", callback_data="admin_info"
            ),
            InlineKeyboardButton(
                text="Обновить информацию", callback_data="admin_info_create"
            ),
            InlineKeyboardButton(
                text="Загрузить афишу", callback_data="admin_create_afisha"
            ),
            InlineKeyboardButton(
                text="Обновить спонсоров", callback_data="admin_update_sponsor"
            ),
            InlineKeyboardButton(
                text="Удалить афишу", callback_data="admin_delete_afisha"
            ),
            InlineKeyboardButton(
                text="Изменить слоты бегунов", callback_data="admin_edit_runners"
            ),
            InlineKeyboardButton(
                text="Дата окончания регистрации",
                callback_data="admin_set_reg_end_date",
            ),
            InlineKeyboardButton(text="Протокол", callback_data="admin_protocol"),
            InlineKeyboardButton(
                text="Сохранить гонку", callback_data="admin_save_race"
            ),
            InlineKeyboardButton(
                text="Очистить участников", callback_data="admin_clear_participants"
            ),
            InlineKeyboardButton(
                text="Прошлые гонки", callback_data="admin_past_races"
            ),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        ]
        return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])

    def create_notifications_category_keyboard():
        commands = [
            InlineKeyboardButton(
                text="Уведомить всех участников", callback_data="admin_notify_all"
            ),
            InlineKeyboardButton(
                text="Кастомное уведомление", callback_data="admin_notify_with_text"
            ),
            InlineKeyboardButton(
                text="Уведомить неоплативших", callback_data="admin_notify_unpaid"
            ),
            InlineKeyboardButton(
                text="Уведомить всех, кто взаимодействовал",
                callback_data="admin_notify_all_interacted",
            ),
            InlineKeyboardButton(
                text="Записать результат", callback_data="admin_notify_results"
            ),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
        ]
        return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])

    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        user_id = message.from_user.id
        logger.info(f"Команда /start от user_id={user_id}")
        await message.delete()

        # Проверка, является ли пользователь администратором
        if user_id == admin_id:
            logger.info(f"Пользователь user_id={user_id} является администратором")
            try:
                await message.answer(
                    messages["admin_commands"],
                    reply_markup=create_admin_commands_keyboard(),
                )
            except TelegramBadRequest as e:
                logger.error(
                    f"Ошибка TelegramBadRequest при отправке admin_commands: {e}"
                )
                await message.answer(messages["admin_commands"], parse_mode=None)
            await state.clear()
            return

        # Проверка текущей регистрации
        participant = get_participant_by_user_id(user_id)
        past_races = get_past_races()
        past_result = None
        past_race_date = None
        is_in_past_race = False

        # Проверка, есть ли пользователь в таблицах race_*
        if past_races:
            conn = sqlite3.connect("/app/data/race_participants.db")
            cursor = conn.cursor()
            for race_date in past_races:
                table_name = f"race_{race_date.replace('.', '_')}"
                cursor.execute(
                    f"SELECT result FROM {table_name} WHERE user_id = ? AND role = 'runner'",
                    (user_id,),
                )
                result = cursor.fetchone()
                if result:
                    is_in_past_race = True
                    if result[0]:
                        past_result = result[0]
                        past_race_date = race_date
                        break
            conn.close()

        # Проверка регистрации в текущей гонке
        if participant:
            name = participant[2]
            target_time = participant[3]
            role = "бегун" if participant[4] == "runner" else "волонтёр"
            bib_number = participant[7] if participant[7] is not None else "не присвоен"
            time_field = (
                f"Целевое время: {target_time}"
                if target_time and role == "бегун"
                else "💪🏼 Вы волонтёр"
            )
            extra_info = (
                "Вы участник Актуальной гонки\n\n"
                if get_participant_count() > 0
                else ""
            )
            if past_result and past_race_date:
                extra_info += f"Ваше время на гонке {past_race_date}: {past_result}\n"
            # Если пользователь в participants и race_*, кнопка регистрации не отображается
            reply_markup = None if is_in_past_race else create_register_keyboard()
            await message.answer(
                messages["already_registered"].format(
                    name=name, time_field=time_field, role=role, bib_number=bib_number
                )
                + f"\n{extra_info}",
                reply_markup=reply_markup,
            )
            await state.clear()
            return

        # Проверка, был ли пользователь в прошлых гонках, если текущая гонка не активна
        if (
            not participant
            and past_result
            and past_race_date
            and get_participant_count() == 0
        ):
            name = message.from_user.full_name or "неизвестно"
            role = "бегун"
            await message.answer(
                messages["already_registered"].format(
                    name=name,
                    time_field=f"Ваше время на гонке {past_race_date}: {past_result}",
                    role=role,
                    bib_number="не присвоен",
                )
                + f"\nВы участник гонки {past_race_date}\n",
                reply_markup=create_register_keyboard(),
            )
            await state.clear()
            return

        # Если пользователь новый, добавляем в pending_registrations
        success = add_pending_registration(
            user_id=user_id,
            username=message.from_user.username,
            name=message.from_user.full_name,
        )
        if not success:
            logger.error(
                f"Ошибка добавления в pending_registrations для user_id={user_id}"
            )
            await message.answer(messages["invalid_command"])
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
                    await message.answer(messages["registration_closed"])
                    await state.clear()
                    return
            except ValueError:
                logger.error(f"Некорректный формат reg_end_date: {reg_end_date}")
                await message.answer(messages["invalid_command"])
                await state.clear()
                return

        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=FSInputFile(path=afisha_path),
                    caption=messages["start_message"],
                    reply_markup=create_register_keyboard(),
                )
            else:
                await message.answer(
                    messages["start_message"],
                    reply_markup=create_register_keyboard(),
                )
        except TelegramBadRequest as e:
            logger.error(
                f"Ошибка при отправке сообщения /start пользователю user_id={user_id}: {e}"
            )
            await message.answer(
                messages["start_message"],
                reply_markup=create_register_keyboard(),
            )

    @dp.callback_query(F.data == "start_registration")
    async def process_start_registration(
        callback_query: CallbackQuery, state: FSMContext
    ):
        user_id = callback_query.from_user.id
        logger.info(f"Callback start_registration от user_id={user_id}")
        await callback_query.message.delete()

        # Проверка даты окончания регистрации
        reg_end_date = get_setting("reg_end_date")
        if reg_end_date:
            try:
                end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
                moscow_tz = timezone("Europe/Moscow")
                end_date = moscow_tz.localize(end_date)
                current_time = datetime.now(moscow_tz)
                if current_time > end_date:
                    await callback_query.message.answer(messages["registration_closed"])
                    await callback_query.answer()
                    return
            except ValueError:
                logger.error(f"Некорректный формат reg_end_date: {reg_end_date}")
                await callback_query.message.answer(messages["invalid_command"])
                await callback_query.answer()
                return

        # Проверка, есть ли пользователь в participants или race_*
        participant = get_participant_by_user_id(user_id)
        past_races = get_past_races()
        previous_name = None
        if participant:
            previous_name = participant[2]
        else:
            conn = sqlite3.connect("/app/data/race_participants.db")
            cursor = conn.cursor()
            for race_date in past_races:
                table_name = f"race_{race_date.replace('.', '_')}"
                cursor.execute(
                    f"SELECT name FROM {table_name} WHERE user_id = ?", (user_id,)
                )
                result = cursor.fetchone()
                if result:
                    previous_name = result[0]
                    break
            conn.close()

        # Если имя уже есть, пропускаем ввод имени
        if previous_name:
            await state.update_data(name=previous_name)
            await callback_query.message.answer(
                messages["role_prompt"], reply_markup=create_role_keyboard()
            )
            await state.set_state(RegistrationForm.waiting_for_role)
        else:
            await callback_query.message.answer("Пожалуйста, введите ваше имя.")
            await state.set_state(RegistrationForm.waiting_for_name)
        await callback_query.answer()

    @dp.message(StateFilter(RegistrationForm.waiting_for_name))
    async def process_name(message: Message, state: FSMContext):
        name = message.text.strip()
        if not name:
            await message.answer("Пожалуйста, введите ваше имя.")
            return
        await state.update_data(name=name)
        await message.answer(
            messages["role_prompt"], reply_markup=create_role_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_role)

    @dp.callback_query(StateFilter(RegistrationForm.waiting_for_role))
    async def process_role(callback_query: CallbackQuery, state: FSMContext):
        if callback_query.data not in ["role_runner", "role_volunteer"]:
            await callback_query.message.answer("Неверный выбор роли.")
            await callback_query.answer()
            await state.clear()
            return
        role = "runner" if callback_query.data == "role_runner" else "volunteer"
        max_count = (
            get_setting("max_runners")
            if role == "runner"
            else get_setting("max_volunteers")
        )
        if max_count is None:
            await callback_query.message.answer(
                "Ошибка конфигурации. Свяжитесь с администратором."
            )
            await callback_query.answer()
            await state.clear()
            return
        current_count = get_participant_count_by_role(role)
        user_data = await state.get_data()
        name = user_data.get("name")
        username = callback_query.from_user.username or "не указан"
        if current_count >= max_count:
            success = add_pending_registration(
                user_id=callback_query.from_user.id,
                username=username,
                name=name,
                target_time=user_data.get("target_time", ""),
                role=role,
            )
            if not success:
                await callback_query.message.answer(
                    "Ошибка при записи в очередь ожидания. Попробуйте снова."
                )
                await callback_query.answer()
                await state.clear()
                return
            await callback_query.message.answer(messages[f"limit_exceeded_{role}"])
            if role == "runner":
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_limit_exceeded_notification"].format(
                            max_runners=max_count,
                            user_id=callback_query.from_user.id,
                            username=username,
                        ),
                    )
                except TelegramBadRequest as e:
                    logger.error(f"Ошибка при отправке уведомления администратору: {e}")
            await callback_query.answer()
            await state.clear()
            return
        await state.update_data(role=role)
        if role == "runner":
            await callback_query.message.answer(messages["target_time_prompt"])
            await state.set_state(RegistrationForm.waiting_for_target_time)
        else:
            success = add_participant(
                user_id=callback_query.from_user.id,
                username=username,
                name=name,
                target_time="",
                role=role,
                gender="",
            )
            if success:
                time_field = "💪🏼 Вы волонтёр"
                extra_info = ""
                user_message = messages["registration_success"].format(
                    name=name, time_field=time_field, extra_info=extra_info
                )
                await callback_query.message.answer(user_message)
                admin_message = messages["admin_notification"].format(
                    name=name,
                    time_field=time_field,
                    user_id=callback_query.from_user.id,
                    username=username,
                    extra_info=extra_info,
                )
                try:
                    image_path = config.get(
                        "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                    )
                    if os.path.exists(image_path):
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=FSInputFile(path=image_path),
                            caption=admin_message,
                        )
                    else:
                        await bot.send_message(chat_id=admin_id, text=admin_message)
                except TelegramBadRequest as e:
                    logger.error(f"Ошибка при отправке уведомления администратору: {e}")
                try:
                    if os.path.exists(image_path):
                        await bot.send_photo(
                            chat_id=callback_query.from_user.id,
                            photo=FSInputFile(path=image_path),
                            caption=messages["sponsor_message"],
                        )
                    else:
                        await callback_query.message.answer(messages["sponsor_message"])
                except TelegramForbiddenError:
                    logger.warning(
                        f"Пользователь user_id={callback_query.from_user.id} заблокировал бот"
                    )
                    delete_pending_registration(callback_query.from_user.id)
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=name,
                                username=username,
                                user_id=callback_query.from_user.id,
                            ),
                        )
                    except TelegramBadRequest as e:
                        logger.error(
                            f"Ошибка при отправке уведомления администратору: {e}"
                        )
                except TelegramBadRequest as e:
                    logger.error(f"Ошибка при отправке сообщения со спонсорами: {e}")
                    await callback_query.message.answer(messages["sponsor_message"])
                delete_pending_registration(callback_query.from_user.id)
            else:
                await callback_query.message.answer(
                    "Ошибка при регистрации. Попробуйте снова."
                )
            await state.clear()
        await callback_query.answer()

    @dp.message(StateFilter(RegistrationForm.waiting_for_target_time))
    async def process_target_time(message: Message, state: FSMContext):
        target_time = message.text.strip()
        time_pattern = re.compile(r"^(?:\d{1,2}:)?[0-5]?\d:[0-5]\d$")
        if not time_pattern.match(target_time):
            await message.answer(messages["target_time_prompt"])
            return
        await state.update_data(target_time=target_time)
        await message.answer(
            messages["gender_prompt"], reply_markup=create_gender_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_gender)

    @dp.callback_query(StateFilter(RegistrationForm.waiting_for_gender))
    async def process_gender(callback_query: CallbackQuery, state: FSMContext):
        gender = callback_query.data
        user_id = callback_query.from_user.id
        user_data = await state.get_data()
        name = user_data.get("name")
        role = user_data.get("role")
        target_time = user_data.get("target_time")
        username = callback_query.from_user.username or "не указан"
        success = add_participant(
            user_id=user_id,
            username=username,
            name=name,
            target_time=target_time,
            role=role,
            gender=gender,
        )
        if success:
            await callback_query.message.delete()
            time_field = f"Целевое время: {target_time}"
            extra_info = "💰 Ожидается оплата.\nПосле поступления оплаты вы получите подтверждение участия."
            await callback_query.message.answer(
                messages["registration_success"].format(
                    name=name, time_field=time_field, extra_info=extra_info
                )
            )
            admin_message = messages["admin_notification"].format(
                name=name,
                time_field=time_field,
                user_id=user_id,
                username=username,
                extra_info=extra_info,
            )
            try:
                image_path = config.get(
                    "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                )
                await bot.send_message(chat_id=admin_id, text=admin_message)
            except TelegramBadRequest as e:
                logger.error(f"Ошибка при отправке уведомления администратору: {e}")
            try:
                if os.path.exists(image_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(path=image_path),
                        caption=messages["sponsor_message"],
                    )
                else:
                    await callback_query.message.answer(messages["sponsor_message"])
            except TelegramForbiddenError:
                logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                delete_pending_registration(user_id)
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=name, username=username, user_id=user_id
                        ),
                    )
                except TelegramBadRequest as e:
                    logger.error(f"Ошибка при отправке уведомления администратору: {e}")
            except TelegramBadRequest as e:
                logger.error(f"Ошибка при отправке сообщения со спонсорами: {e}")
                await callback_query.message.answer(messages["sponsor_message"])
            delete_pending_registration(user_id)
            await state.clear()
        else:
            await callback_query.message.delete()
            await callback_query.message.answer(
                "Ошибка при регистрации. Попробуйте снова."
            )
        await callback_query.answer()

    @dp.callback_query(F.data.in_(["confirm_participation", "decline_participation"]))
    async def process_participation_response(
        callback_query: CallbackQuery, state: FSMContext
    ):
        user_id = callback_query.from_user.id
        participant = get_participant_by_user_id(user_id)
        if not participant:
            await callback_query.message.delete()
            await callback_query.message.answer("Вы не зарегистрированы.")
            await callback_query.answer()
            return
        name = participant[2]
        role = participant[4]
        payment_status = participant[6]
        username = callback_query.from_user.username or "не указан"
        await callback_query.message.delete()
        if callback_query.data == "confirm_participation":
            if role == "volunteer":
                await callback_query.message.answer(
                    messages["volunteer_confirm_message"]
                )
                admin_message = messages["admin_volunteer_confirm_notification"].format(
                    name=name, username=username
                )
            else:
                if payment_status == "paid":
                    await callback_query.message.answer(
                        messages["confirm_paid_message"]
                    )
                else:
                    await callback_query.message.answer(
                        messages["confirm_pending_message"]
                    )
                admin_message = messages["admin_confirm_notification"].format(
                    name=name,
                    username=username,
                    payment_status=(
                        "оплачено" if payment_status == "paid" else "не оплачено"
                    ),
                )
            try:
                await bot.send_message(chat_id=admin_id, text=admin_message)
            except TelegramBadRequest as e:
                logger.error(f"Ошибка при отправке уведомления администратору: {e}")
        else:
            success = delete_participant(user_id)
            if success:
                await callback_query.message.answer(messages["decline_message"])
                admin_message = messages["admin_decline_notification"].format(name=name)
                try:
                    await bot.send_message(chat_id=admin_id, text=admin_message)
                except TelegramBadRequest as e:
                    logger.error(f"Ошибка при отправке уведомления администратору: {e}")
            else:
                await callback_query.message.answer("Ошибка при отказе от участия.")
        await callback_query.answer()
        await state.clear()

    @dp.callback_query(F.data == "category_participants")
    async def show_participants_category(callback_query: CallbackQuery):
        await callback_query.message.delete()
        await callback_query.message.answer(
            "Управление участниками:",
            reply_markup=create_participants_category_keyboard(),
        )
        await callback_query.answer()

    @dp.callback_query(F.data == "category_race")
    async def show_race_category(callback_query: CallbackQuery):
        await callback_query.message.delete()
        await callback_query.message.answer(
            "Управление гонкой:", reply_markup=create_race_category_keyboard()
        )
        await callback_query.answer()

    @dp.callback_query(F.data == "category_notifications")
    async def show_notifications_category(callback_query: CallbackQuery):
        await callback_query.message.delete()
        await callback_query.message.answer(
            "Уведомления и результаты:",
            reply_markup=create_notifications_category_keyboard(),
        )
        await callback_query.answer()

    @dp.callback_query(F.data == "main_menu")
    async def show_main_menu(callback_query: CallbackQuery):
        await callback_query.message.delete()
        if callback_query.from_user.id == admin_id:
            await callback_query.message.answer(
                messages["admin_commands"],
                reply_markup=create_admin_commands_keyboard(),
            )
        else:
            afisha_path = "/app/images/afisha.jpeg"
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=callback_query.from_user.id,
                    photo=FSInputFile(path=afisha_path),
                    caption=messages["start_message"],
                    reply_markup=create_register_keyboard(),
                )
            else:
                await callback_query.message.answer(
                    messages["start_message"], reply_markup=create_register_keyboard()
                )
        await callback_query.answer()
