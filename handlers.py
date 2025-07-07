import json
import datetime
import io
import csv
import sqlite3
import logging
import logging.handlers
import os
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest
from database import (
    add_participant,
    get_all_participants,
    get_participant_count,
    get_participant_by_user_id,
    update_payment_status,
    delete_participant,
    get_participant_count_by_role,
    add_pending_registration,
    get_pending_registrations,
    delete_pending_registration,
    set_bib_number,
)


class CustomRotatingFileHandler(logging.handlers.BaseRotatingHandler):
    def __init__(self, filename, maxBytes, encoding=None):
        super().__init__(filename, mode="a", encoding=encoding)
        self.maxBytes = maxBytes
        self.backup_file = f"{filename}.1"

    def shouldRollover(self, record):
        if (
            os.path.exists(self.baseFilename)
            and os.path.getsize(self.baseFilename) > self.maxBytes
        ):
            return True
        return False

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if os.path.exists(self.baseFilename):
            if os.path.exists(self.backup_file):
                os.remove(self.backup_file)
            os.rename(self.baseFilename, self.backup_file)
        self.stream = self._open()


os.makedirs("/app/logs", exist_ok=True)
log_level = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        CustomRotatingFileHandler("/app/logs/bot.log", maxBytes=10 * 1024 * 1024),
    ],
)
logger = logging.getLogger(__name__)

try:
    with open("messages.json", "r", encoding="utf-8") as f:
        messages = json.load(f)
    logger.info("Файл messages.json успешно загружен")
except FileNotFoundError:
    logger.error("Файл messages.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе messages.json: {e}")
    raise

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Файл config.json успешно загружен")
except FileNotFoundError:
    logger.error("Файл config.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе config.json: {e}")
    raise

if config.get("log_level") not in log_level:
    logger.error(
        f"Недопустимое значение log_level: {config.get('log_level')}. Используется ERROR."
    )
    logging.getLogger().setLevel(logging.ERROR)
else:
    logging.getLogger().setLevel(log_level[config["log_level"]])
    logger.info(f"Установлен уровень логирования: {config['log_level']}")


class RegistrationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_role = State()
    waiting_for_target_time = State()
    waiting_for_info_message = State()
    waiting_for_afisha_image = State()
    waiting_for_sponsor_image = State()
    processed = State()


def register_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков в Dispatcher")

    def create_role_keyboard():
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=messages["role_runner"], callback_data="role_runner"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=messages["role_volunteer"], callback_data="role_volunteer"
                    )
                ],
            ]
        )
        return keyboard

    def create_register_keyboard():
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=messages["register_button"],
                        callback_data="start_registration",
                    )
                ]
            ]
        )
        return keyboard

    def create_confirmation_keyboard():
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=messages["confirm_button"],
                        callback_data="confirm_participation",
                    ),
                    InlineKeyboardButton(
                        text=messages["decline_button"],
                        callback_data="decline_participation",
                    ),
                ]
            ]
        )
        return keyboard

    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        logger.info(f"Команда /start от user_id={message.from_user.id}")
        if message.from_user.id == admin_id:
            logger.info(
                f"Пользователь user_id={message.from_user.id} является администратором"
            )
            logger.debug(f"Отправка admin_commands: {messages['admin_commands']}")
            try:
                await message.answer(messages["admin_commands"])
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
        success = add_pending_registration(message.from_user.id)
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
        except Exception as e:
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
        await callback_query.message.answer("Пожалуйста, введите ваше имя.")
        await state.set_state(RegistrationForm.waiting_for_name)
        await callback_query.answer()

    @dp.message(Command("notify_all"))
    async def notify_all_participants(message: Message):
        logger.info(f"Команда /notify_all от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /notify_all запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["notify_all_access_denied"])
            return
        participants = get_all_participants()
        if not participants:
            logger.info("Нет зарегистрированных участников для уведомления")
            await message.answer(messages["notify_all_no_participants"])
            return
        afisha_path = "/app/images/afisha.jpeg"
        success_count = 0
        for participant in participants:
            user_id = participant[0]
            try:
                if os.path.exists(afisha_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(afisha_path),
                        caption=messages["notify_all_message"],
                        reply_markup=create_confirmation_keyboard(),
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=messages["notify_all_message"],
                        reply_markup=create_confirmation_keyboard(),
                        parse_mode="HTML",
                    )
                logger.info(f"Уведомление отправлено пользователю user_id={user_id}")
                success_count += 1
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                )
        await message.answer(messages["notify_all_success"].format(count=success_count))
        logger.info(f"Уведомления отправлены {success_count} участникам")

    @dp.callback_query(F.data.in_(["confirm_participation", "decline_participation"]))
    async def process_participation_response(callback_query, state: FSMContext):
        logger.info(
            f"Обработка ответа на участие от user_id={callback_query.from_user.id}"
        )
        user_id = callback_query.from_user.id
        logger.info(f"Обработка ответа на участие от user_id={user_id}")
        if await state.get_state() == "processed":
            logger.warning(f"Повторный запрос от user_id={user_id}, игнорируется")
            await callback_query.answer("Запрос уже обработан.")
            return
        await state.set_state("processed")
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
            else:  # role == "runner"
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
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                )

        elif callback_query.data == "decline_participation":
            success = delete_participant(callback_query.from_user.id)
            if success:
                pending_success = add_pending_registration(callback_query.from_user.id)
                if pending_success:
                    logger.info(
                        f"Пользователь user_id={callback_query.from_user.id} добавлен в pending_registrations"
                    )
                else:
                    logger.warning(
                        f"Не удалось добавить пользователя user_id={callback_query.from_user.id} в pending_registrations"
                    )
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
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке уведомления администратору (admin_id={admin_id}): {e}"
                    )
            else:
                logger.error(
                    f"Не удалось удалить пользователя user_id={callback_query.from_user.id} из participants"
                )
                await callback_query.message.answer(
                    "Ошибка при обработке отказа. Попробуйте снова."
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

    @dp.message(StateFilter(RegistrationForm.waiting_for_name))
    async def process_name(message: Message, state: FSMContext):
        name = message.text.strip()
        logger.info(f"Получено имя: {name} от user_id={message.from_user.id}")
        await state.update_data(name=name)
        await message.answer(
            messages["role_prompt"], reply_markup=create_role_keyboard()
        )
        await state.set_state(RegistrationForm.waiting_for_role)

    @dp.message(Command("delete_afisha"))
    async def delete_afisha(message: Message):
        logger.info(f"Команда /delete_afisha от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /delete_afisha запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["delete_afisha_access_denied"])
            return
        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                os.remove(afisha_path)
                logger.info(f"Афиша удалена: {afisha_path}")
                await message.answer(messages["delete_afisha_success"])
            else:
                logger.info(f"Афиша не найдена: {afisha_path}")
                await message.answer(messages["delete_afisha_not_found"])
        except Exception as e:
            logger.error(
                f"Ошибка при удалении афиши для user_id={message.from_user.id}: {e}"
            )
            await message.answer("Ошибка при удалении афиши. Попробуйте снова.")

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
            config["max_runners"] if role == "runner" else config["max_volunteers"]
        )
        current_count = get_participant_count_by_role(role)
        if current_count >= max_count:
            logger.info(f"Лимит для роли {role} достигнут: {current_count}/{max_count}")
            await callback_query.message.answer(messages[f"limit_exceeded_{role}"])
            if role == "runner":
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_limit_exceeded_notification"].format(
                            max_runners=max_count,
                            user_id=callback_query.from_user.id,
                            username=callback_query.from_user.username or "не указан",
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
            user_data = await state.get_data()
            name = user_data.get("name")
            target_time = ""
            username = callback_query.from_user.username or "не указан"
            success = add_participant(
                callback_query.from_user.id, username, name, target_time, role
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
                await bot.send_message(chat_id=admin_id, text=admin_message)
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
                except Exception as e:
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
        logger.info(
            f"Получено целевое время: {target_time} от user_id={message.from_user.id}"
        )
        user_data = await state.get_data()
        name = user_data.get("name")
        role = user_data.get("role")
        username = message.from_user.username or "не указан"
        success = add_participant(
            message.from_user.id, username, name, target_time, role
        )
        if success:
            logger.info(
                f"Успешная регистрация: {name}, {role}, user_id={message.from_user.id}"
            )
            time_field = f"Целевое время: {target_time}"
            extra_info = "💰 Ожидается оплата.\nПосле поступления оплаты вы получите подтверждение участия."
            user_message = messages["registration_success"].format(
                name=name, time_field=time_field, extra_info=extra_info
            )
            await message.answer(user_message)
            admin_message = messages["admin_notification"].format(
                name=name,
                time_field=time_field,
                user_id=message.from_user.id,
                username=username,
                extra_info=extra_info,
            )
            await bot.send_message(chat_id=admin_id, text=admin_message)
            try:
                image_path = config.get(
                    "sponsor_image_path", "/app/images/sponsor_image.jpeg"
                )
                if os.path.exists(image_path):
                    await bot.send_photo(
                        chat_id=message.from_user.id,
                        photo=FSInputFile(image_path),
                        caption=messages["sponsor_message"],
                    )
                    logger.info(
                        f"Сообщение со спонсорами отправлено пользователю user_id={message.from_user.id}"
                    )
                else:
                    logger.warning(
                        f"Файл {image_path} не найден, отправляется только текст спонсоров"
                    )
                    await message.answer(messages["sponsor_message"])
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке сообщения со спонсорами пользователю user_id={message.from_user.id}: {e}"
                )
                await message.answer(messages["sponsor_message"])
            logger.info(
                f"Сообщения отправлены: пользователю и админу (admin_id={admin_id})"
            )
            participant_count = get_participant_count()
            logger.info(f"Всего участников: {participant_count}")
            delete_pending_registration(message.from_user.id)
        else:
            logger.error(f"Ошибка регистрации для user_id={message.from_user.id}")
            await message.answer("Ошибка при регистрации. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("participants", "список", "участники"))
    async def show_participants(message: Message):
        logger.info(f"Команда /participants от user_id={message.from_user.id}")
        participants = get_all_participants()
        participant_list = (
            messages["participants_list_header"] + messages["runners_header"]
        )
        chunks = []
        current_chunk = participant_list
        last_role = None
        for index, (
            user_id,
            username,
            name,
            target_time,
            role,
            reg_date,
            payment_status,
            bib_number,
        ) in enumerate(participants, 1):
            if role != last_role and role == "volunteer":
                if len(current_chunk) + len(messages["volunteers_header"]) > 4000:
                    chunks.append(current_chunk)
                    current_chunk = (
                        messages["participants_list_header"]
                        + messages["volunteers_header"]
                    )
                else:
                    current_chunk += messages["volunteers_header"]
            last_role = role
            date_obj = datetime.datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
            bib_field = f"№{bib_number}" if bib_number is not None else "№ не присвоен"
            if role == "runner":
                status_emoji = "✅" if payment_status == "paid" else "⏳"
                participant_info = messages["participant_info"].format(
                    index=index,
                    user_id=user_id,
                    name=name,
                    target_time=target_time,
                    role=role,
                    date=formatted_date,
                    status=status_emoji,
                    username=username,
                    bib_number=bib_field,
                )
            else:
                participant_info = messages["participant_info_volunteer"].format(
                    index=index,
                    user_id=user_id,
                    name=name,
                    target_time=target_time,
                    role=role,
                    date=formatted_date,
                    username=username,
                    bib_number=bib_field,
                )
            if len(current_chunk) + len(participant_info) > 4000:
                chunks.append(current_chunk)
                current_chunk = messages["participants_list_header"]
                if role == "volunteer":
                    current_chunk += messages["volunteers_header"]
                else:
                    current_chunk += messages["runners_header"]
            current_chunk += participant_info
        chunks.append(current_chunk)
        for chunk in chunks:
            await message.answer(chunk)

    @dp.message(Command("pending"))
    async def show_pending_registrations(message: Message):
        logger.info(f"Команда /pending от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /pending запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["pending_access_denied"])
            return
        pending_users = get_pending_registrations()
        if not pending_users:
            await message.answer(messages["pending_empty"])
            logger.info("Список pending_registrations пуст")
            return
        pending_list = messages["pending_list_header"]
        chunks = []
        current_chunk = pending_list
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                for index, user_id in enumerate(pending_users, 1):
                    cursor.execute(
                        "SELECT username FROM participants WHERE user_id = ?",
                        (user_id,),
                    )
                    result = cursor.fetchone()
                    username = result[0] if result and result[0] else None
                    user_display = (
                        f"@{username}"
                        if username
                        else f"<a href='tg://user?id={user_id}'>{user_id}</a>"
                    )
                    pending_info = messages["pending_info"].format(
                        index=index, user_display=user_display, user_id=user_id
                    )
                    if len(current_chunk) + len(pending_info) > 4000:
                        chunks.append(current_chunk)
                        current_chunk = pending_list
                    current_chunk += pending_info
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении pending_registrations: {e}")
            await message.answer("Ошибка при получении списка. Попробуйте снова.")
            return
        chunks.append(current_chunk)
        for chunk in chunks:
            await message.answer(chunk, parse_mode="HTML")

    @dp.message(Command("stats", "статистика"))
    async def show_stats(message: Message):
        logger.info(f"Команда /stats от user_id={message.from_user.id}")
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
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
            stats_message = messages["stats_message"].format(
                paid=paid_count,
                runners=runner_count,
                volunteers=volunteer_count,
                pending_reg=pending_reg_count,
            )
            await message.answer(stats_message)
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            await message.answer("Ошибка при получении статистики. Попробуйте снова.")

    @dp.message(Command("paid"))
    async def mark_as_paid(message: Message):
        logger.info(f"Команда /paid от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /paid запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["paid_access_denied"])
            return
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(messages["paid_usage"])
            return
        user_id = int(parts[1])
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
            except Exception as e:
                logger.error(
                    f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                )
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("set_bib"))
    async def set_bib(message: Message):
        logger.info(f"Команда /set_bib от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /set_bib запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["set_bib_access_denied"])
            return
        parts = message.text.split()
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await message.answer(messages["set_bib_usage"])
            return
        user_id = int(parts[1])
        bib_number = int(parts[2])
        if bib_number <= 0:
            await message.answer(messages["set_bib_invalid"])
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
                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке уведомления о номере пользователю user_id={user_id}: {e}"
                    )
            else:
                await message.answer("Ошибка при присвоении номера. Попробуйте снова.")
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("remove"))
    async def remove_participant(message: Message):
        logger.info(f"Команда /remove от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /remove запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["remove_access_denied"])
            return
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(messages["remove_usage"])
            return
        user_id = int(parts[1])
        participant = get_participant_by_user_id(user_id)
        if participant:
            name = participant[2]
            success = delete_participant(user_id)
            if success:
                await message.answer(messages["remove_success"].format(name=name))
            else:
                await message.answer("Ошибка при удалении участника. Попробуйте снова.")
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("export"))
    async def export_participants(message: Message):
        logger.info(f"Команда /export от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /export запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["export_access_denied"])
            return
        participants = get_all_participants()
        output = io.StringIO()
        delimiter = config.get("csv_delimiter", ";")
        writer = csv.writer(
            output, lineterminator="\n", delimiter=delimiter, quoting=csv.QUOTE_MINIMAL
        )
        writer.writerow(
            [
                "Имя",
                "Целевое время",
                "Роль",
                "Дата регистрации",
                "Статус оплаты",
                "Username",
                "Беговой номер",
            ]
        )
        for (
            user_id,
            username,
            name,
            target_time,
            role,
            reg_date,
            payment_status,
            bib_number,
        ) in participants:
            writer.writerow(
                [
                    name,
                    target_time,
                    role,
                    reg_date,
                    payment_status,
                    username,
                    bib_number or "",
                ]
            )
        csv_content = output.getvalue()
        output.close()
        logger.info(
            f"CSV-файл сформирован, размер: {len(csv_content)} символов, разделитель: {delimiter}"
        )
        await message.answer(messages["export_message"])
        csv_bytes = csv_content.encode("utf-8-sig")
        await message.answer_document(
            document=BufferedInputFile(csv_bytes, filename="participants.csv")
        )
        logger.info(f"CSV-файл успешно отправлен для user_id={message.from_user.id}")

    @dp.message(Command("info"))
    async def show_info(message: Message):
        logger.info(f"Команда /info от user_id={message.from_user.id}")
        afisha_path = "/app/images/afisha.jpeg"
        try:
            if os.path.exists(afisha_path):
                await bot.send_photo(
                    chat_id=message.from_user.id,
                    photo=FSInputFile(afisha_path),
                    caption=messages["info_message"],
                )
                logger.info(
                    f"Афиша отправлена с текстом info_message пользователю user_id={message.from_user.id}"
                )
            else:
                await message.answer(messages["info_message"])
                logger.info(
                    f"Афиша не найдена, отправлен только текст info_message пользователю user_id={message.from_user.id}"
                )
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения /info пользователю user_id={message.from_user.id}: {e}"
            )
            await message.answer(messages["info_message"])

    @dp.message(Command("info_create"))
    async def info_create(message: Message, state: FSMContext):
        logger.info(f"Команда /info_create от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /info_create запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["info_create_access_denied"])
            return
        await message.answer(messages["info_create_prompt"])
        await state.set_state(RegistrationForm.waiting_for_info_message)

    @dp.message(StateFilter(RegistrationForm.waiting_for_info_message))
    async def process_info_message(message: Message, state: FSMContext):
        logger.info(f"Получен новый текст для /info от user_id={message.from_user.id}")
        new_info_message = message.text.strip()
        try:
            global messages
            messages["info_message"] = new_info_message
            with open("messages.json", "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            logger.info("Файл messages.json успешно обновлен с новым info_message")
            await message.answer(messages["info_create_success"])
        except Exception as e:
            logger.error(f"Ошибка при обновлении messages.json: {e}")
            await message.answer("Ошибка при сохранении информации. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("create_afisha"))
    async def create_afisha(message: Message, state: FSMContext):
        logger.info(f"Команда /create_afisha от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /create_afisha запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["create_afisha_access_denied"])
            return
        await message.answer(messages["create_afisha_prompt"])
        await state.set_state(RegistrationForm.waiting_for_afisha_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_afisha_image), F.photo)
    async def process_afisha_image(message: Message, state: FSMContext):
        logger.info(f"Получено изображение афиши от user_id={message.from_user.id}")
        try:
            afisha_path = "/app/images/afisha.jpeg"
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            await bot.download_file(file_path, afisha_path)
            os.chmod(afisha_path, 0o644)
            logger.info(f"Изображение афиши сохранено в {afisha_path}")
            await message.answer(messages["create_afisha_success"])
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении афиши от user_id={message.from_user.id}: {e}"
            )
            await message.answer("Ошибка при сохранении афиши. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("update_sponsor"))
    async def update_sponsor(message: Message, state: FSMContext):
        logger.info(f"Команда /update_sponsor от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /update_sponsor запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["update_sponsor_access_denied"])
            return
        await message.answer(messages["update_sponsor_prompt"])
        await state.set_state(RegistrationForm.waiting_for_sponsor_image)

    @dp.message(StateFilter(RegistrationForm.waiting_for_sponsor_image), F.photo)
    async def process_sponsor_image(message: Message, state: FSMContext):
        logger.info(f"Получено изображение спонсоров от user_id={message.from_user.id}")
        try:
            sponsor_path = config.get(
                "sponsor_image_path", "/app/images/sponsor_image.jpeg"
            )
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            await bot.download_file(file_path, sponsor_path)
            os.chmod(sponsor_path, 0o644)
            logger.info(f"Изображение спонсоров сохранено в {sponsor_path}")
            await message.answer(messages["update_sponsor_success"])
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении изображения спонсоров от user_id={message.from_user.id}: {e}"
            )
            await message.answer(
                "Ошибка при сохранении изображения спонсоров. Попробуйте снова."
            )
        await state.clear()

    @dp.message(Command("edit_runners"))
    async def edit_runners(message: Message):
        logger.info(f"Команда /edit_runners от user_id={message.from_user.id}")
        if message.from_user.id != admin_id:
            logger.warning(
                f"Доступ к /edit_runners запрещен для user_id={message.from_user.id}"
            )
            await message.answer(messages["edit_runners_access_denied"])
            return
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer(messages["edit_runners_usage"])
            return
        new_max_runners = int(parts[1])
        if new_max_runners < 0:
            await message.answer(messages["edit_runners_invalid"])
            return
        old_max_runners = config["max_runners"]
        config["max_runners"] = new_max_runners
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(
                f"Лимит бегунов изменен с {old_max_runners} на {new_max_runners}"
            )
            await message.answer(
                messages["edit_runners_success"].format(
                    old=old_max_runners, new=new_max_runners
                )
            )
            if new_max_runners > old_max_runners:
                current_runners = get_participant_count_by_role("runner")
                available_slots = new_max_runners - current_runners
                if available_slots > 0:
                    pending_users = get_pending_registrations()
                    for user_id in pending_users:
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=messages["new_slots_notification"].format(
                                    slots=available_slots
                                ),
                            )
                            logger.info(
                                f"Уведомление о новых слотах ({available_slots}) отправлено пользователю user_id={user_id}"
                            )
                            delete_pending_registration(user_id)
                        except Exception as e:
                            logger.error(
                                f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении config.json: {e}")
            await message.answer(
                "Ошибка при изменении лимита бегунов. Попробуйте снова."
            )

    @dp.message()
    async def handle_other_messages(message: Message):
        logger.info(
            f"Неизвестная команда от user_id={message.from_user.id}: {message.text}"
        )
        await message.answer(messages["invalid_command"])

    logger.info("Обработчики успешно зарегистрированы")
