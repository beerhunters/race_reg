import datetime
import sqlite3
import io
import csv
from aiogram import Dispatcher, Bot, F
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from .utils import logger, messages, config
from database import (
    get_all_participants,
    get_pending_registrations,
    get_participant_count,
    get_participant_count_by_role,
    get_participant_by_user_id,
    update_payment_status,
    set_bib_number,
    delete_participant,
    delete_pending_registration,
)


def register_admin_participant_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков управления участниками")

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
        for index, (user_id, username, name, target_time, role) in enumerate(
            pending_users, 1
        ):
            user_display = (
                f"@{username}"
                if username
                else f"<a href='tg://user?id={user_id}'>{user_id}</a>"
            )
            if name and role:
                role_text = "бегун" if role == "runner" else "волонтёр"
                pending_info = messages["pending_info_registered"].format(
                    index=index,
                    user_display=user_display,
                    user_id=user_id,
                    name=name,
                    role=role_text,
                )
            else:
                pending_info = messages["pending_info_visited"].format(
                    index=index, user_display=user_display, user_id=user_id
                )
            if len(current_chunk) + len(pending_info) > 4000:
                chunks.append(current_chunk)
                current_chunk = pending_list
            current_chunk += pending_info
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
            except TelegramForbiddenError:
                logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                delete_participant(user_id)
                delete_pending_registration(user_id)
                logger.info(
                    f"Пользователь user_id={user_id} удалён из таблиц participants и pending_registrations"
                )
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=messages["admin_blocked_notification"].format(
                            name=participant[2],
                            username=participant[1] or "не указан",
                            user_id=user_id,
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
                except TelegramForbiddenError:
                    logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                    delete_participant(user_id)
                    delete_pending_registration(user_id)
                    logger.info(
                        f"Пользователь user_id={user_id} удалён из таблиц participants и pending_registrations"
                    )
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=participant[2],
                                username=participant[1] or "не указан",
                                user_id=user_id,
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
            success = delete_participant(user_id)
            if success:
                await message.answer(
                    messages["remove_success"].format(name=participant[2])
                )
                try:
                    await bot.send_message(
                        chat_id=user_id, text=messages["remove_user_notification"]
                    )
                    logger.info(
                        f"Уведомление об удалении отправлено пользователю user_id={user_id}"
                    )
                except TelegramForbiddenError:
                    logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
                    delete_participant(user_id)
                    delete_pending_registration(user_id)
                    logger.info(
                        f"Пользователь user_id={user_id} удалён из таблиц participants и pending_registrations"
                    )
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=messages["admin_blocked_notification"].format(
                                name=participant[2],
                                username=participant[1] or "не указан",
                                user_id=user_id,
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
                        f"Ошибка при отправке уведомления об удалении пользователю user_id={user_id}: {e}"
                    )
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
