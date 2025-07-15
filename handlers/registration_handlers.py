import os
import re
from datetime import datetime
from pytz import timezone

from aiogram import Dispatcher, Bot, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
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
    add_participant,
    get_participant_by_user_id,
    add_pending_registration,
    delete_pending_registration,
    get_setting,
    get_participant_count_by_role,
    get_participant_count,
)


def register_registration_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    def create_admin_commands_keyboard():
        commands = [
            ("participants", "📋 Список участников"),
            ("pending", "⏳ Незавершённые регистрации"),
            ("stats", "📊 Статистика"),
            ("paid", "💳 Подтвердить оплату"),
            ("set_bib", "🏷 Присвоить номер"),
            ("remove", "🗑 Удалить участника"),
            ("export", "📤 Экспорт данных"),
            ("info", "ℹ️ Информация о забеге"),
            ("create_afisha", "🖼 Обновить афишу"),
            ("update_sponsor", "🎯 Обновить спонсора"),
            ("edit_runners", "🏃 Изменить лимит"),
            ("set_reg_end_date", "⏰ Установить дату"),
            ("notify_all", "📢 Уведомить всех"),
            ("notify_with_text", "✉️ Кастомное уведомление"),
            ("notify_unpaid", "💸 Уведомить неоплативших"),
            ("save_race", "💾 Сохранить гонку"),
            ("clear_participants", "🗑 Очистить участников"),
            ("past_races", "📜 Прошедшие гонки"),
            ("notify_results", "🏅 Отправить результаты"),
            ("top_winners", "🏆 Тройка лучших"),
            ("protocol", "📝 Протокол"),
            ("main_menu", "🏠 Главное меню"),
        ]
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    text="Управление участниками", callback_data="category_participants"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Управление гонкой", callback_data="category_race"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Уведомления и результаты",
                    callback_data="category_notifications",
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    def create_participants_category_keyboard():
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    text="📋 Список участников", callback_data="admin_participants"
                ),
                InlineKeyboardButton(
                    text="⏳ Незавершённые регистрации", callback_data="admin_pending"
                ),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(
                    text="💳 Подтвердить оплату", callback_data="admin_paid"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Присвоить номер", callback_data="admin_set_bib"
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить участника", callback_data="admin_remove"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📤 Экспорт данных", callback_data="admin_export"
                ),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    def create_race_category_keyboard():
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    text="ℹ️ Информация о забеге", callback_data="admin_info"
                ),
                InlineKeyboardButton(
                    text="🖼 Обновить афишу", callback_data="admin_create_afisha"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Обновить спонсора", callback_data="admin_update_sponsor"
                ),
                InlineKeyboardButton(
                    text="🏃 Изменить лимит", callback_data="admin_edit_runners"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Установить дату", callback_data="admin_set_reg_end_date"
                ),
                InlineKeyboardButton(
                    text="💾 Сохранить гонку", callback_data="admin_save_race"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Очистить участников",
                    callback_data="admin_clear_participants",
                ),
                InlineKeyboardButton(
                    text="📜 Прошедшие гонки", callback_data="admin_past_races"
                ),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    def create_notifications_category_keyboard():
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    text="📢 Уведомить всех", callback_data="admin_notify_all"
                ),
                InlineKeyboardButton(
                    text="✉️ Кастомное уведомление",
                    callback_data="admin_notify_with_text",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💸 Уведомить неоплативших",
                    callback_data="admin_notify_unpaid",
                ),
                InlineKeyboardButton(
                    text="🏅 Отправить результаты", callback_data="admin_notify_results"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📝 Протокол", callback_data="admin_protocol"
                ),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    logger.info("Регистрация обработчиков регистрации")

    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        logger.info(f"Команда /start от user_id={message.from_user.id}")
        if message.from_user.id == admin_id:
            logger.info(
                f"Пользователь user_id={message.from_user.id} является администратором"
            )
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
                logger.info(
                    f"admin_commands отправлено без parse_mode пользователю user_id={message.from_user.id}"
                )
            await state.clear()
            return
        participant = get_participant_by_user_id(message.from_user.id)
        if participant:
            logger.info(
                f"Пользователь user_id={message.from_user.id} уже зарегистрирован"
            )
            name = participant[2]
            target_time = participant[3]
            role = participant[4]
            bib_number = participant[7] if participant[7] is not None else "не присвоен"
            time_field = (
                f"Целевое время: {target_time}" if role == "runner" else "Вы волонтер"
            )
            await message.answer(
                messages["already_registered"].format(
                    name=name, time_field=time_field, role=role, bib_number=bib_number
                )
            )
            await state.clear()
            return
        success = add_pending_registration(
            message.from_user.id, username=message.from_user.username
        )
        if not success:
            logger.error(
                f"Ошибка при сохранении user_id={message.from_user.id} в pending_registrations"
            )
            await message.answer("Ошибка при начале регистрации. Попробуйте снова.")
            await state.clear()
            return
        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=message.from_user.id,
                    photo=FSInputFile(afisha_path),
                    caption=messages["start_message"],
                    reply_markup=create_register_keyboard(),
                    parse_mode="HTML",
                )
                logger.info(
                    f"Афиша отправлена с текстом start_message и кнопкой регистрации пользователю user_id={message.from_user.id}"
                )
            else:
                await message.answer(
                    messages["start_message"],
                    reply_markup=create_register_keyboard(),
                    parse_mode="HTML",
                )
                logger.info(
                    f"Афиша не найдена, отправлен текст start_message с кнопкой регистрации пользователю user_id={message.from_user.id}"
                )
        except TelegramBadRequest as e:
            logger.error(
                f"Ошибка при отправке сообщения /start пользователю user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                messages["start_message"],
                reply_markup=create_register_keyboard(),
                parse_mode="HTML",
            )

    @dp.callback_query(F.data == "start_registration")
    async def process_start_registration(callback_query, state: FSMContext):
        logger.info(
            f"Нажата кнопка 'Регистрация' от user_id={callback_query.from_user.id}"
        )
        reg_end_date = get_setting("reg_end_date")
        if reg_end_date:
            try:
                end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
                moscow_tz = timezone("Europe/Moscow")
                end_date = moscow_tz.localize(end_date)
                current_time = datetime.now(moscow_tz)
                if current_time > end_date:
                    logger.info(
                        f"Попытка регистрации после окончания: user_id={callback_query.from_user.id}"
                    )
                    await callback_query.message.answer(messages["registration_closed"])
                    await callback_query.message.delete()
                    return
            except ValueError:
                logger.error(
                    f"Некорректный формат даты окончания регистрации: {reg_end_date}"
                )
        await callback_query.message.answer("Пожалуйста, введите ваше имя.")
        await state.set_state(RegistrationForm.waiting_for_name)
        await callback_query.answer()

    @dp.message(StateFilter(RegistrationForm.waiting_for_name))
    async def process_name(message: Message, state: FSMContext):
        name = message.text.strip()
        logger.info(f"Получено имя: {name} от user_id={message.from_user.id}")
        await state.update_data(name=name)
        await message.answer(
            messages["role_prompt"], reply_markup=create_role_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_role)

    @dp.callback_query(StateFilter(RegistrationForm.waiting_for_role))
    async def process_role(callback_query, state: FSMContext):
        logger.info(f"Обработка выбора роли от user_id={callback_query.from_user.id}")
        if callback_query.data not in ["role_runner", "role_volunteer"]:
            logger.warning(f"Неверный выбор роли: {callback_query.data}")
            await callback_query.message.answer("Неверный выбор роли.")
            await callback_query.answer()
            await state.clear()
            return
        role = "runner" if callback_query.data == "role_runner" else "volunteer"
        logger.info(f"Выбрана роль: {role} для user_id={callback_query.from_user.id}")
        max_count = (
            get_setting("max_runners")
            if role == "runner"
            else get_setting("max_volunteers")
        )
        if max_count is None:
            logger.error(f"Не найдена настройка max_{role}s в базе данных")
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
            logger.info(f"Лимит для роли {role} достигнут: {current_count}/{max_count}")
            success = add_pending_registration(
                callback_query.from_user.id,
                username=username,
                name=name,
                target_time=user_data.get("target_time", ""),
                role=role,
            )
            if not success:
                logger.error(
                    f"Ошибка при сохранении user_id={callback_query.from_user.id} в pending_registrations"
                )
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
                    logger.info(
                        f"Уведомление о превышении лимита бегунов отправлено администратору (admin_id={admin_id})"
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                    )
            await callback_query.answer()
            await state.clear()
            return
        await state.update_data(role=role)
        if role == "runner":
            await callback_query.message.answer(messages["target_time_prompt"])
            await state.set_state(RegistrationForm.waiting_for_target_time)
            await callback_query.answer()
        else:
            success = add_participant(
                callback_query.from_user.id, username, name, "", role, ""
            )
            if success:
                logger.info(
                    f"Успешная регистрация: {name}, {role}, user_id={callback_query.from_user.id}"
                )
                time_field = "💪🏼 Вы волонтер"
                extra_info = ""
                time_field = "💪🏼 " + time_field.split(" ")[2].capitalize()
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
                    await bot.send_message(chat_id=admin_id, text=admin_message)
                    logger.info(
                        f"Уведомление администратору (admin_id={admin_id}) отправлено"
                    )
                except TelegramBadRequest as e:
                    logger.error(
                        f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                    )
                try:
                    image_path = config.get(
                        "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                    )
                    if os.path.exists(image_path):
                        await bot.send_photo(
                            chat_id=callback_query.from_user.id,
                            photo=FSInputFile(image_path),
                            caption=messages["sponsor_message"],
                        )
                        logger.info(
                            f"Сообщение со спонсорами отправлено пользователю user_id={callback_query.from_user.id}"
                        )
                    else:
                        logger.warning(
                            f"Файл {image_path} не найден, отправляется только текст спонсоров"
                        )
                        await callback_query.message.answer(messages["sponsor_message"])
                except TelegramForbiddenError:
                    logger.warning(
                        f"Пользователь user_id={callback_query.from_user.id} заблокировал бот"
                    )
                    delete_pending_registration(callback_query.from_user.id)
                    logger.info(
                        f"Пользователь user_id={callback_query.from_user.id} удалён из таблицы pending_registrations"
                    )
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=name,
                                username=username,
                                user_id=callback_query.from_user.id,
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
                        f"Ошибка при отправке сообщения со спонсорами пользователю user_id={callback_query.from_user.id}: {e}"
                    )
                    await callback_query.message.answer(messages["sponsor_message"])
                logger.info(
                    f"Сообщения отправлены: пользователю и админу (admin_id={admin_id})"
                )
                participant_count = get_participant_count()
                logger.info(f"Всего участников: {participant_count}")
                delete_pending_registration(callback_query.from_user.id)
            else:
                logger.error(
                    f"Ошибка регистрации для user_id={callback_query.from_user.id}"
                )
                await callback_query.message.answer(
                    "Ошибка при регистрации. Попробуйте снова."
                )
            await callback_query.answer()
            await state.clear()

    @dp.message(StateFilter(RegistrationForm.waiting_for_target_time))
    async def process_target_time(message: Message, state: FSMContext):
        target_time = message.text.strip()
        if not target_time:
            await message.answer(
                "Целевое время не может быть пустым. Введите ваше целевое время прохождения трасс(например, '5:30' или '1:05:30'):"
            )
            return
        time_pattern = re.compile(r"^(?:\d{1,2}:)?[0-5]?\d:[0-5]\d$")
        if not time_pattern.match(target_time):
            await message.answer(
                "Некорректный формат времени. Введите время в формате 'M:SS' или 'H:MM:SS' (например, '5:30' или '1:05:30'):"
            )
            return
        await state.update_data(target_time=target_time)
        await message.answer(
            messages["gender_prompt"], reply_markup=create_gender_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_gender)

    @dp.callback_query(StateFilter(RegistrationForm.waiting_for_gender))
    async def process_gender(callback_query: CallbackQuery, state: FSMContext):
        gender = callback_query.data
        await callback_query.message.delete()
        user_id = callback_query.from_user.id
        user_data = await state.get_data()
        name = user_data.get("name")
        role = user_data.get("role")
        target_time = user_data.get("target_time")
        username = callback_query.from_user.username or "не указан"
        success = add_participant(
            user_id,
            username,
            name,
            target_time,
            role,
            gender,
        )
        if success:
            logger.info(
                f"Успешная регистрация: {name}, {role}, user_id={callback_query.from_user.id}"
            )
            time_field = f"Целевое время: {target_time}"
            extra_info = "💰 Ожидается оплата.\nПосле поступления оплаты вы получите подтверждение участия."
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
                await bot.send_message(chat_id=admin_id, text=admin_message)
                logger.info(
                    f"Уведомление администратору (admin_id={admin_id}) отправлено"
                )
            except TelegramBadRequest as e:
                logger.error(
                    f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                )
            try:
                image_path = config.get(
                    "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                )
                if os.path.exists(image_path):
                    await bot.send_photo(
                        chat_id=callback_query.from_user.id,
                        photo=FSInputFile(image_path),
                        caption=messages["sponsor_message"],
                    )
                    logger.info(
                        f"Сообщение со спонсорами отправлено пользователю user_id={callback_query.from_user.id}"
                    )
                else:
                    logger.warning(
                        f"Файл {image_path} не найден, отправляется только текст спонсоров"
                    )
                    await callback_query.message.answer(messages["sponsor_message"])
            except TelegramForbiddenError:
                logger.warning(
                    f"Пользователь user_id={callback_query.from_user.id} заблокировал бот"
                )
                delete_pending_registration(callback_query.from_user.id)
                logger.info(
                    f"Пользователь user_id={callback_query.from_user.id} удалён из таблицы pending_registrations"
                )
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=name,
                            username=username,
                            user_id=callback_query.from_user.id,
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
                    f"Ошибка при отправке сообщения со спонсорами пользователю user_id={callback_query.from_user.id}: {e}"
                )
                await callback_query.answer(messages["sponsor_message"])
            logger.info(
                f"Сообщения отправлены: пользователю и админу (admin_id={admin_id})"
            )
            participant_count = get_participant_count()
            logger.info(f"Всего участников: {participant_count}")
            delete_pending_registration(callback_query.from_user.id)
        else:
            logger.error(
                f"Ошибка регистрации для user_id={callback_query.from_user.id}"
            )
            await callback_query.message.answer(
                "Ошибка при регистрации. Попробуйте снова."
            )
        await state.clear()

    @dp.callback_query(F.data.in_(["confirm_participation", "decline_participation"]))
    async def process_participation_response(callback_query, state: FSMContext):
        logger.info(
            f"Обработка ответа на участие от user_id={callback_query.from_user.id}"
        )
        participant = get_participant_by_user_id(callback_query.from_user.id)
        if not participant:
            logger.warning(
                f"Пользователь user_id={callback_query.from_user.id} не найден в participants"
            )
            await callback_query.message.answer("Вы не зарегистрированы.")
            await callback_query.answer()
            try:
                await callback_query.message.delete()
                logger.info(
                    f"Сообщение с кнопками удалено для user_id={callback_query.from_user.id}"
                )
            except TelegramBadRequest as e:
                logger.warning(
                    f"Не удалось удалить сообщение для user_id={callback_query.from_user.id}: {e}"
                )
            return
        name = participant[2]
        role = participant[4]
        payment_status = participant[6]
        username = callback_query.from_user.username or "не указан"
        if callback_query.data == "confirm_participation":
            if role == "volunteer":
                await callback_query.message.answer(
                    messages.get(
                        "volunteer_confirm_message",
                        "Спасибо за подтверждение участия в качестве волонтёра!",
                    )
                )
                logger.info(
                    f"Пользователь {name} (user_id={callback_query.from_user.id}) подтвердил участие как волонтёр"
                )
                admin_message = messages.get(
                    "admin_volunteer_confirm_notification",
                    "Пользователь {name} (@{username}) подтвердил участие как волонтёр.",
                ).format(name=name, username=username)
            else:
                if payment_status == "paid":
                    await callback_query.message.answer(
                        messages["confirm_paid_message"]
                    )
                    logger.info(
                        f"Пользователь {name} (user_id={callback_query.from_user.id}) подтвердил участие, оплата подтверждена"
                    )
                    admin_message = messages["admin_confirm_notification"].format(
                        name=name, username=username, payment_status="оплачено"
                    )
                else:
                    await callback_query.message.answer(
                        messages["confirm_pending_message"]
                    )
                    logger.info(
                        f"Пользователь {name} (user_id={callback_query.from_user.id}) подтвердил участие, но оплата не подтверждена"
                    )
                    admin_message = messages["admin_confirm_notification"].format(
                        name=name, username=username, payment_status="не оплачено"
                    )
            try:
                await bot.send_message(chat_id=admin_id, text=admin_message)
                logger.info(
                    f"Уведомление администратору (admin_id={admin_id}) отправлено"
                )
            except TelegramBadRequest as e:
                logger.error(
                    f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                )
        elif callback_query.data == "decline_participation":
            await callback_query.message.answer(messages["decline_message"])
            logger.info(
                f"Пользователь {name} (user_id={callback_query.from_user.id}) отказался от участия"
            )
            admin_message = messages["admin_decline_notification"].format(name=name)
            try:
                await bot.send_message(chat_id=admin_id, text=admin_message)
                logger.info(
                    f"Уведомление администратору (admin_id={admin_id}) отправлено"
                )
            except TelegramBadRequest as e:
                logger.error(
                    f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                )
        try:
            await callback_query.message.delete()
            logger.info(
                f"Сообщение с кнопками удалено для user_id={callback_query.from_user.id}"
            )
        except TelegramBadRequest as e:
            logger.warning(
                f"Не удалось удалить сообщение для user_id={callback_query.from_user.id}: {e}"
            )
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
        await callback_query.message.answer(
            messages["admin_commands"], reply_markup=create_admin_commands_keyboard()
        )
        await callback_query.answer()
