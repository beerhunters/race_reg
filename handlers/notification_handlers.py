import sqlite3
import os
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from .utils import (
    logger,
    messages,
    config,
    RegistrationForm,
    create_confirmation_keyboard,
)
from database import (
    get_all_participants,
    delete_participant,
    delete_pending_registration,
)


def register_notification_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков уведомлений")

    @dp.message(Command("notify_all"))
    @dp.callback_query(F.data == "admin_notify_all")
    async def notify_all_participants(event: [Message, CallbackQuery]):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_all_access_denied"])
            return
        logger.info(f"Команда /notify_all от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        participants = get_all_participants()
        if not participants:
            logger.info("Нет зарегистрированных участников для уведомления")
            await message.answer(messages["notify_all_no_participants"])
            return
        afisha_path = "/app/images/afisha.jpeg"
        success_count = 0
        for participant in participants:
            user_id = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"
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
                            name=name, username=username, user_id=user_id
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
                if "chat not found" in str(e).lower():
                    logger.warning(
                        f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                    )
                else:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                    )
        await message.answer(messages["notify_all_success"].format(count=success_count))
        logger.info(f"Уведомления отправлены {success_count} участникам")

    @dp.message(Command("notify_with_text"))
    @dp.callback_query(F.data == "admin_notify_with_text")
    async def notify_with_text(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_with_text_access_denied"])
            return
        logger.info(f"Команда /notify_with_text от user_id={user_id}")
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
        else:
            await event.delete()
            message = event
        participants = get_all_participants()
        if not participants:
            logger.info("Нет зарегистрированных участников для уведомления")
            await message.answer(messages["notify_with_text_no_participants"])
            return
        await message.answer(messages["notify_with_text_prompt"])
        await state.set_state(RegistrationForm.waiting_for_notify_with_text_message)

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_with_text_message))
    async def process_notify_with_text_message(message: Message, state: FSMContext):
        logger.info(
            f"Получен текст рассылки для /notify_with_text от user_id={message.from_user.id}"
        )
        notify_text = message.text.strip()
        if len(notify_text) > 4096:
            logger.warning(
                f"Текст рассылки слишком длинный: {len(notify_text)} символов"
            )
            await message.answer("Текст слишком длинный. Максимум 4096 символов.")
            await state.clear()
            return
        await state.update_data(notify_text=notify_text)
        await message.answer(messages["notify_with_text_photo_prompt"])
        await state.set_state(RegistrationForm.waiting_for_notify_with_text_photo)

    @dp.message(
        StateFilter(RegistrationForm.waiting_for_notify_with_text_photo), F.photo
    )
    async def process_notify_with_text_photo(message: Message, state: FSMContext):
        logger.info(
            f"Получено изображение для /notify_with_text от user_id={message.from_user.id}"
        )
        user_data = await state.get_data()
        notify_text = user_data.get("notify_text")
        participants = get_all_participants()
        success_count = 0
        try:
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_path = file.file_path
            temp_photo_path = "/app/images/temp_notify_photo.jpeg"
            await bot.download_file(file_path, temp_photo_path)
            os.chmod(temp_photo_path, 0o644)
            logger.info(f"Изображение сохранено временно в {temp_photo_path}")
            for participant in participants:
                user_id = participant[0]
                name = participant[2]
                username = participant[1] or "не указан"
                try:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(temp_photo_path),
                        caption=notify_text,
                        parse_mode="HTML",
                    )
                    logger.info(
                        f"Уведомление с фото отправлено пользователю user_id={user_id}"
                    )
                    success_count += 1
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
                                name=name, username=username, user_id=user_id
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
                    if "chat not found" in str(e).lower():
                        logger.warning(
                            f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                        )
                    else:
                        logger.error(
                            f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                        )
            os.remove(temp_photo_path)
            logger.info(f"Временное изображение {temp_photo_path} удалено")
        except Exception as e:
            logger.error(
                f"Ошибка при сохранении изображения для /notify_with_text: {e}"
            )
            await message.answer("Ошибка при сохранении изображения. Попробуйте снова.")
            await state.clear()
            return
        await message.answer(
            messages["notify_with_text_success"].format(count=success_count)
        )
        logger.info(f"Уведомления отправлены {success_count} участникам")
        await state.clear()

    @dp.message(
        StateFilter(RegistrationForm.waiting_for_notify_with_text_photo),
        Command("skip"),
    )
    async def process_notify_with_text_skip_photo(message: Message, state: FSMContext):
        logger.info(
            f"Пропущено изображение для /notify_with_text от user_id={message.from_user.id}"
        )
        user_data = await state.get_data()
        notify_text = user_data.get("notify_text")
        participants = get_all_participants()
        success_count = 0
        for participant in participants:
            user_id = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"
            try:
                await bot.send_message(
                    chat_id=user_id, text=notify_text, parse_mode="HTML"
                )
                logger.info(
                    f"Уведомление без фото отправлено пользователю user_id={user_id}"
                )
                success_count += 1
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
                            name=name, username=username, user_id=user_id
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
                if "chat not found" in str(e).lower():
                    logger.warning(
                        f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                    )
                else:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                    )
        await message.answer(
            messages["notify_with_text_success"].format(count=success_count)
        )
        logger.info(f"Уведомления отправлены {success_count} участникам")
        await state.clear()

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_with_text_photo))
    async def process_notify_with_text_invalid(message: Message, state: FSMContext):
        logger.info(
            f"Некорректный ввод в состоянии waiting_for_notify_with_text_photo от user_id={message.from_user.id}"
        )
        await message.answer(
            "Пожалуйста, отправьте фото или используйте /skip, чтобы пропустить."
        )

    @dp.message(Command("notify_unpaid"))
    @dp.callback_query(F.data == "admin_notify_unpaid")
    async def notify_unpaid_participants(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer(messages["notify_unpaid_access_denied"])
            return
        logger.info(f"Команда /notify_unpaid от user_id={user_id}")
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
                    "SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number "
                    "FROM participants WHERE payment_status = 'pending' AND role = 'runner'"
                )
                unpaid_participants = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка неоплативших участников: {e}")
            await message.answer(
                "Ошибка при получении списка участников. Попробуйте снова."
            )
            return
        if not unpaid_participants:
            logger.info("Нет участников с неоплаченным статусом")
            await message.answer(messages["notify_unpaid_no_participants"])
            return
        await message.answer(messages["notify_unpaid_prompt"])
        await state.set_state(RegistrationForm.waiting_for_notify_unpaid_message)

    @dp.message(StateFilter(RegistrationForm.waiting_for_notify_unpaid_message))
    async def process_notify_unpaid_message(message: Message, state: FSMContext):
        logger.info(
            f"Получен текст рассылки для /notify_unpaid от user_id={message.from_user.id}"
        )
        notify_text = message.text.strip()
        if len(notify_text) > 4096:
            logger.warning(
                f"Текст рассылки слишком длинный: {len(notify_text)} символов"
            )
            await message.answer("Текст слишком длинный. Максимум 4096 символов.")
            await state.clear()
            return
        try:
            with sqlite3.connect("/app/data/race_participants.db", timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number "
                    "FROM participants WHERE payment_status = 'pending' AND role = 'runner'"
                )
                unpaid_participants = cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении списка неоплативших участников: {e}")
            await message.answer("Ошибка при отправке уведомлений. Попробуйте снова.")
            await state.clear()
            return
        success_count = 0
        afisha_path = "/app/images/afisha.jpeg"
        for participant in unpaid_participants:
            user_id = participant[0]
            name = participant[2]
            username = participant[1] or "не указан"
            try:
                if os.path.exists(afisha_path):
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile(afisha_path),
                        caption=notify_text,
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id, text=notify_text, parse_mode="HTML"
                    )
                logger.info(
                    f"Уведомление отправлено неоплатившему пользователю user_id={user_id}"
                )
                success_count += 1
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
                            name=name, username=username, user_id=user_id
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
                if "chat not found" in str(e).lower():
                    logger.warning(
                        f"Чат с пользователем user_id={user_id} не найден, уведомление пропущено"
                    )
                else:
                    logger.error(
                        f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                    )
        await message.answer(
            messages["notify_unpaid_success"].format(count=success_count)
        )
        logger.info(f"Уведомления отправлены {success_count} неоплатившим участникам")
        await state.clear()
