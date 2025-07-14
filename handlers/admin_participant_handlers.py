import datetime
import sqlite3
import io
import csv
import pytz
from aiogram import Dispatcher, Bot, F
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    Message,
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from .utils import logger, messages, config, RegistrationForm
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
    get_race_data,
    get_past_races,
    save_race_to_db,
)


def register_admin_participant_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков управления участниками")

    async def show_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["set_reg_end_date_access_denied"])
            return
        logger.info(f"Команда /participants от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        participants = get_all_participants()
        if not participants:
            await message.answer(messages["pending_empty"])
            return
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
            result,
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
            utc_timezone = pytz.timezone("UTC")
            moscow_timezone = pytz.timezone("Europe/Moscow")
            date_obj = date_obj.replace(tzinfo=utc_timezone).astimezone(moscow_timezone)
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
                    username=username or "не указан",
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
                    username=username or "не указан",
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
        if isinstance(event, CallbackQuery):
            await event.answer()

    @dp.message(Command("participants", "список", "участники"))
    async def cmd_show_participants(message: Message):
        await show_participants(message)

    @dp.callback_query(F.data == "admin_participants")
    async def callback_show_participants(callback_query: CallbackQuery):
        await show_participants(callback_query)

    async def show_pending_registrations(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["pending_access_denied"])
            return
        logger.info(f"Команда /pending от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
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

    @dp.message(Command("pending"))
    async def cmd_show_pending_registrations(message: Message):
        await show_pending_registrations(message)

    @dp.callback_query(F.data == "admin_pending")
    async def callback_show_pending_registrations(callback_query: CallbackQuery):
        await show_pending_registrations(callback_query)

    async def show_stats(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["pending_access_denied"])
            return
        logger.info(f"Команда /stats от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
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

    @dp.message(Command("stats", "статистика"))
    async def cmd_show_stats(message: Message):
        await show_stats(message)

    @dp.callback_query(F.data == "admin_stats")
    async def callback_show_stats(callback_query: CallbackQuery):
        await show_stats(callback_query)

    async def mark_as_paid(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["paid_access_denied"])
            return
        logger.info(f"Команда /paid от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_paid_ID"])
        await state.set_state(RegistrationForm.waiting_for_paid_id)

    @dp.message(RegistrationForm.waiting_for_paid_id)
    async def process_mark_as_paid(message: Message, state: FSMContext):
        user_id = int(message.text)
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

    @dp.message(Command("paid"))
    async def cmd_mark_as_paid(message: Message, state: FSMContext):
        await mark_as_paid(message, state)

    @dp.callback_query(F.data == "admin_paid")
    async def callback_mark_as_paid(callback_query: CallbackQuery, state: FSMContext):
        await mark_as_paid(callback_query, state)

    # @dp.message(Command("set_bib"))
    # async def set_bib(message: Message):
    #     logger.info(f"Команда /set_bib от user_id={message.from_user.id}")
    #     if message.from_user.id != admin_id:
    #         logger.warning(
    #             f"Доступ к /set_bib запрещен для user_id={message.from_user.id}"
    #         )
    #         await message.answer(messages["set_bib_access_denied"])
    #         return
    #     parts = message.text.split()
    #     if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
    #         await message.answer(messages["set_bib_usage"])
    #         return
    #     user_id = int(parts[1])
    #     bib_number = int(parts[2])
    #     if bib_number <= 0:
    #         await message.answer(messages["set_bib_invalid"])
    #         return
    #     participant = get_participant_by_user_id(user_id)
    #     if participant:
    #         success = set_bib_number(user_id, bib_number)
    #         if success:
    #             await message.answer(
    #                 messages["set_bib_success"].format(
    #                     name=participant[2], bib_number=bib_number
    #                 )
    #             )
    #             try:
    #                 await bot.send_message(
    #                     chat_id=user_id,
    #                     text=messages["bib_number_assigned"].format(
    #                         bib_number=bib_number
    #                     ),
    #                 )
    #                 logger.info(
    #                     f"Уведомление о присвоении номера {bib_number} отправлено пользователю user_id={user_id}"
    #                 )
    #             except TelegramForbiddenError:
    #                 logger.warning(f"Пользователь user_id={user_id} заблокировал бот")
    #                 delete_participant(user_id)
    #                 delete_pending_registration(user_id)
    #                 logger.info(
    #                     f"Пользователь user_id={user_id} удалён из таблиц participants и pending_registrations"
    #                 )
    #                 try:
    #                     await bot.send_message(
    #                         chat_id=admin_id,
    #                         text=messages["admin_blocked_notification"].format(
    #                             name=participant[2],
    #                             username=participant[1] or "не указан",
    #                             user_id=user_id,
    #                         ),
    #                     )
    #                     logger.info(
    #                         f"Уведомление администратору (admin_id={admin_id}) о блокировке отправлено"
    #                     )
    #                 except Exception as admin_e:
    #                     logger.error(
    #                         f"Ошибка при отправке уведомления администратору: {admin_e}"
    #                     )
    #             except TelegramBadRequest as e:
    #                 logger.error(
    #                     f"Ошибка при отправке уведомления о номере пользователю user_id={user_id}: {e}"
    #                 )
    #         else:
    #             await message.answer("Ошибка при присвоении номера. Попробуйте снова.")
    #     else:
    #         await message.answer("Участник не найден.")
    async def set_bib(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["set_bib_access_denied"])
            return
        logger.info(f"Команда /set_bib от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_bib_ID"])
        await state.set_state(RegistrationForm.waiting_for_bib)

    @dp.message(RegistrationForm.waiting_for_bib)
    async def process_set_bib(message: Message, state: FSMContext):
        parts = message.text.split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            await message.answer(messages["set_bib_usage"])
            return
        user_id = int(parts[0])
        bib_number = int(parts[1])
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

    @dp.message(Command("set_bib"))
    async def cmd_set_bib(message: Message, state: FSMContext):
        await set_bib(message, state)

    @dp.callback_query(F.data == "admin_set_bib")
    async def callback_set_bib(callback_query: CallbackQuery, state: FSMContext):
        await set_bib(callback_query, state)

    async def remove_participant(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["remove_access_denied"])
            return
        logger.info(f"Команда /remove_participant от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["wait_for_remove_id"])
        await state.set_state(RegistrationForm.waiting_for_remove_id)

    @dp.message(RegistrationForm.waiting_for_remove_id)
    async def process_remove_participant(message: Message, state: FSMContext):
        user_id = int(message.text)
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

    @dp.message(Command("remove"))
    async def cmd_remove(message: Message, state: FSMContext):
        await remove_participant(message, state)

    @dp.callback_query(F.data == "admin_remove")
    async def callback_remove(callback_query: CallbackQuery, state: FSMContext):
        await remove_participant(callback_query, state)

    async def export_participants(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["export_access_denied"])
            return
        logger.info(f"Команда /export от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
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
                "Результат",
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
            result,
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
                    result or "",
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

    @dp.message(Command("export"))
    async def cmd_export_participants(message: Message, state: FSMContext):
        await export_participants(message, state)

    @dp.callback_query(F.data == "admin_export")
    async def callback_export_participants(
        callback_query: CallbackQuery, state: FSMContext
    ):
        await export_participants(callback_query, state)

    async def show_top_winners(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["top_winners_access_denied"])
            return
        logger.info(f"Команда /top_winners от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        conn = sqlite3.connect("/app/data/race_participants.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, name, bib_number, result FROM participants WHERE role = 'runner' AND result IS NOT NULL AND result != 'DNF'"
        )
        runners = cursor.fetchall()
        conn.close()
        if not runners:
            await message.answer(messages["top_winners_empty"])
            return

        # Convert times to seconds for sorting
        def time_to_seconds(time_str):
            try:
                parts = time_str.split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                return float("inf")
            except:
                return float("inf")

        sorted_runners = sorted(runners, key=lambda x: time_to_seconds(x[4]))[:3]
        top_winners = messages["top_winners_header"]
        for place, (user_id, username, name, bib_number, result) in enumerate(
            sorted_runners, 1
        ):
            bib_field = f"{bib_number}" if bib_number is not None else "не присвоен"
            top_winners += messages["top_winners_info"].format(
                place=place,
                name=name,
                username=username or "не указан",
                bib_number=bib_field,
                result=result,
            )
        await message.answer(top_winners)
        if isinstance(event, CallbackQuery):
            await event.answer()

    @dp.message(Command("top_winners"))
    async def cmd_top_winners(message: Message):
        await show_top_winners(message)

    @dp.callback_query(F.data == "admin_top_winners")
    async def callback_top_winners(callback_query: CallbackQuery):
        await show_top_winners(callback_query)

    async def save_race(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["save_race_access_denied"])
            return
        logger.info(f"Команда /save_race от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        await message.answer(messages["save_race_prompt"])
        await state.set_state(RegistrationForm.waiting_for_race_date)
        if isinstance(event, CallbackQuery):
            await event.answer()

    # async def process_save_race(message: Message, state: FSMContext):
    #     race_date = message.text.strip()
    #     try:
    #         datetime.datetime.strptime(race_date, "%d.%m.%Y")
    #         success = save_race_to_db(race_date)
    #         if success:
    #             await message.answer(
    #                 messages["save_race_success"].format(date=race_date)
    #             )
    #             logger.info(f"Гонка сохранена для даты {race_date}")
    #         else:
    #             await message.answer(messages["save_race_empty"])
    #             logger.info(
    #                 f"Не удалось сохранить гонку для даты {race_date}: таблица participants пуста"
    #             )
    #     except ValueError:
    #         await message.answer(messages["save_race_invalid_format"])
    #         logger.error(f"Некорректный формат даты для /save_race: {race_date}")
    #     await state.clear()
    async def process_save_race(message: Message, state: FSMContext):
        race_date = message.text.strip()
        try:
            date_obj = datetime.datetime.strptime(race_date, "%d.%m.%Y")
            table_name = f"race_{date_obj.strftime('%d_%m_%Y')}"
            conn = sqlite3.connect("/app/data/race_participants.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            table_exists = cursor.fetchone() is not None
            conn.close()
            success = save_race_to_db(race_date)
            if success:
                action = "обновлены" if table_exists else "сохранены"
                await message.answer(
                    messages["save_race_success"].format(date=race_date, action=action)
                )
                logger.info(f"Гонка {action} для даты {race_date}")
            else:
                await message.answer(messages["save_race_empty"])
                logger.info(
                    f"Не удалось сохранить гонку для даты {race_date}: таблица participants пуста"
                )
        except ValueError:
            await message.answer(messages["save_race_invalid_format"])
            logger.error(f"Некорректный формат даты для /save_race: {race_date}")
        await state.clear()

    async def clear_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["clear_participants_access_denied"])
            return
        logger.info(f"Команда /clear_participants от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        success = clear_participants()
        if success:
            await message.answer(messages["clear_participants_success"])
            logger.info("Таблица participants успешно очищена")
        else:
            await message.answer(messages["clear_participants_error"])
            logger.error("Ошибка при очистке таблицы participants")
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def past_races(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["past_races_access_denied"])
            return
        logger.info(f"Команда /past_races от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        races = get_past_races()
        if not races:
            await message.answer(messages["past_races_empty"])
            if isinstance(event, CallbackQuery):
                await event.answer()
            return
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=date, callback_data=f"past_race_{date}")]
                for date in races
            ]
        )
        await message.answer(messages["past_races_prompt"], reply_markup=keyboard)
        if isinstance(event, CallbackQuery):
            await event.answer()

    async def show_past_race(callback_query: CallbackQuery):
        race_date = callback_query.data.replace("past_race_", "")
        logger.info(
            f"Запрос данных гонки {race_date} от user_id={callback_query.from_user.id}"
        )
        await callback_query.message.delete()
        participants = get_race_data(race_date)
        if not participants:
            await callback_query.message.answer(
                messages["past_race_not_found"].format(date=race_date)
            )
            await callback_query.answer()
            return
        participant_list = messages["past_race_header"].format(date=race_date)
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
            result,
        ) in enumerate(participants, 1):
            if role != last_role and role == "volunteer":
                if len(current_chunk) + len(messages["volunteers_header"]) > 4000:
                    chunks.append(current_chunk)
                    current_chunk = (
                        messages["past_race_header"].format(date=race_date)
                        + messages["volunteers_header"]
                    )
                else:
                    current_chunk += messages["volunteers_header"]
            last_role = role
            date_obj = datetime.datetime.fromisoformat(reg_date.replace("Z", "+00:00"))
            utc_timezone = pytz.timezone("UTC")
            moscow_timezone = pytz.timezone("Europe/Moscow")
            date_obj = date_obj.replace(tzinfo=utc_timezone).astimezone(moscow_timezone)
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
            bib_field = f"№{bib_number}" if bib_number is not None else "не присвоен"
            result_field = result if result is not None else "не указан"
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
                    username=username or "не указан",
                    bib_number=bib_field,
                    result=result_field,
                )
            else:
                participant_info = messages["participant_info_volunteer"].format(
                    index=index,
                    user_id=user_id,
                    name=name,
                    date=formatted_date,
                    username=username or "не указан",
                )
            if len(current_chunk) + len(participant_info) > 4000:
                chunks.append(current_chunk)
                current_chunk = messages["past_race_header"].format(date=race_date)
                if role == "volunteer":
                    current_chunk += messages["volunteers_header"]
                else:
                    current_chunk += messages["runners_header"]
            current_chunk += participant_info
        chunks.append(current_chunk)
        for chunk in chunks:
            await callback_query.message.answer(chunk)
        await callback_query.answer()

    @dp.message(Command("save_race"))
    async def cmd_save_race(message: Message, state: FSMContext):
        await save_race(message, state)

    @dp.callback_query(F.data == "admin_save_race")
    async def callback_save_race(callback_query: CallbackQuery, state: FSMContext):
        await save_race(callback_query, state)

    @dp.message(RegistrationForm.waiting_for_race_date)
    async def process_save_race_message(message: Message, state: FSMContext):
        await process_save_race(message, state)

    @dp.message(Command("clear_participants"))
    async def cmd_clear_participants(message: Message):
        await clear_participants(message)

    @dp.callback_query(F.data == "admin_clear_participants")
    async def callback_clear_participants(callback_query: CallbackQuery):
        await clear_participants(callback_query)

    @dp.message(Command("past_races"))
    async def cmd_past_races(message: Message, state: FSMContext):
        await past_races(message, state)

    @dp.callback_query(F.data == "admin_past_races")
    async def callback_past_races(callback_query: CallbackQuery, state: FSMContext):
        await past_races(callback_query, state)

    @dp.callback_query(F.data.startswith("past_race_"))
    async def callback_show_past_race(callback_query: CallbackQuery):
        await show_past_race(callback_query)
