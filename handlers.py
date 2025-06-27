import json
import datetime
import io
import sqlite3
import logging
import os
import csv
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from database import (
    add_participant,
    get_all_participants,
    get_participant_count,
    get_participant_by_user_id,
    update_payment_status,
    delete_participant,
    get_participant_count_by_role,
)

# Настройка логирования
os.makedirs("/app/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/app/logs/bot.log")],
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


class RegistrationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_role = State()
    waiting_for_target_time = State()


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

    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        logger.info(f"Команда /start от user_id={message.from_user.id}")
        participant = get_participant_by_user_id(message.from_user.id)
        if participant:
            logger.info(
                f"Пользователь user_id={message.from_user.id} уже зарегистрирован"
            )
            name = participant[2]
            target_time = participant[3]
            role = participant[4]
            time_field = target_time if role == "runner" else "Волонтер"
            await message.answer(
                messages["already_registered"].format(
                    name=name, time_field=time_field, role=role
                )
            )
            await state.clear()
            return
        await message.answer(messages["start_message"])
        await state.set_state(RegistrationForm.waiting_for_name)

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
            await state.clear()
            return
        await state.update_data(role=role)
        if role == "runner":
            await callback_query.message.answer(messages["target_time_prompt"])
            await state.set_state(RegistrationForm.waiting_for_target_time)
        else:
            user_data = await state.get_data()
            name = user_data.get("name")
            target_time = ""  # Пустое время для волонтеров
            username = callback_query.from_user.username or "не указан"
            success = add_participant(
                callback_query.from_user.id, username, name, target_time, role
            )
            if success:
                logger.info(
                    f"Успешная регистрация: {name}, {role}, user_id={callback_query.from_user.id}"
                )
                time_field = "Волонтер"
                user_message = messages["registration_success"].format(
                    name=name, time_field=time_field
                )
                await callback_query.message.answer(user_message)
                admin_message = messages["admin_notification"].format(
                    name=name,
                    time_field=time_field,
                    user_id=callback_query.from_user.id,
                    username=username,
                )
                await bot.send_message(chat_id=admin_id, text=admin_message)
                logger.info(
                    f"Сообщения отправлены: пользователю и админу (admin_id={admin_id})"
                )
                participant_count = get_participant_count()
                logger.info(f"Всего участников: {participant_count}")
            else:
                logger.error(
                    f"Ошибка регистрации для user_id={callback_query.from_user.id}"
                )
                await callback_query.message.answer(
                    "Ошибка при регистрации. Попробуйте снова."
                )
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
            time_field = target_time
            user_message = messages["registration_success"].format(
                name=name, time_field=time_field
            )
            await message.answer(user_message)
            admin_message = messages["admin_notification"].format(
                name=name,
                time_field=time_field,
                user_id=message.from_user.id,
                username=username,
            )
            await bot.send_message(chat_id=admin_id, text=admin_message)
            logger.info(
                f"Сообщения отправлены: пользователю и админу (admin_id={admin_id})"
            )
            participant_count = get_participant_count()
            logger.info(f"Всего участников: {participant_count}")
        else:
            logger.error(f"Ошибка регистрации для user_id={message.from_user.id}")
            await message.answer("Ошибка при регистрации. Попробуйте снова.")
        await state.clear()

    @dp.message(Command("participants", "список", "участники"))
    async def show_participants(message: Message):
        logger.info(f"Команда /participants от user_id={message.from_user.id}")
        participants = get_all_participants()
        participant_list = messages["participants_list_header"]
        chunks = []
        current_chunk = participant_list
        for index, (
            user_id,
            username,
            name,
            target_time,
            role,
            reg_date,
            payment_status,
        ) in enumerate(participants, 1):
            date_obj = datetime.datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
            status_emoji = "✅" if payment_status == "paid" else "⏳"
            participant_info = messages["participant_info"].format(
                index=index,
                name=name,
                target_time=target_time,
                role=role,
                date=formatted_date,
                status=status_emoji,
                username=username,
            )
            if len(current_chunk) + len(participant_info) > 4000:
                chunks.append(current_chunk)
                current_chunk = participant_list
            current_chunk += participant_info
        chunks.append(current_chunk)
        for chunk in chunks:
            await message.answer(chunk)

    @dp.message(Command("stats", "статистика"))
    async def show_stats(message: Message):
        logger.info(f"Команда /stats от user_id={message.from_user.id}")
        with sqlite3.connect("/app/data/race_participants.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants")
            total_count = cursor.fetchone()[0]
            cursor.execute(
                'SELECT COUNT(*) FROM participants WHERE payment_status = "paid"'
            )
            paid_count = cursor.fetchone()[0]
            cursor.execute(
                'SELECT COUNT(*) FROM participants WHERE payment_status = "pending"'
            )
            pending_count = cursor.fetchone()[0]
            cursor.execute(
                'SELECT COUNT(*) FROM participants WHERE DATE(reg_date) = DATE("now")'
            )
            today_count = cursor.fetchone()[0]
        stats_message = messages["stats_message"].format(
            total=total_count, paid=paid_count, pending=pending_count, today=today_count
        )
        await message.answer(stats_message)

    @dp.message(Command("paid"))
    async def mark_as_paid(message: Message):
        logger.info(f"Команда /paid от user_id={message.from_user.id}")
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Используйте: /paid <user_id>")
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

    @dp.message(Command("remove"))
    async def remove_participant(message: Message):
        logger.info(f"Команда /remove от user_id={message.from_user.id}")
        parts = message.text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Используйте: /remove <user_id>")
            return
        user_id = int(parts[1])
        participant = get_participant_by_user_id(user_id)
        if participant:
            delete_participant(user_id)
            await message.answer(messages["remove_success"].format(name=participant[2]))
        else:
            await message.answer("Участник не найден.")

    @dp.message(Command("export"))
    async def export_participants(message: Message):
        logger.info(f"Команда /export от user_id={message.from_user.id}")
        participants = get_all_participants()
        output = io.StringIO()
        delimiter = config.get(
            "csv_delimiter", ";"
        )  # Используем точку с запятой по умолчанию
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
        ) in participants:
            writer.writerow(
                [name, target_time, role, reg_date, payment_status, username]
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

    @dp.message()
    async def handle_other_messages(message: Message):
        logger.info(
            f"Неизвестная команда от user_id={message.from_user.id}: {message.text}"
        )
        await message.answer(messages["invalid_command"])

    logger.info("Обработчики успешно зарегистрированы")
