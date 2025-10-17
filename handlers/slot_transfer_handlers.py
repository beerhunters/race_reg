"""
Обработчики для переоформления слота участника
"""

import os
from urllib.parse import quote
from aiogram import Dispatcher, Bot, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from logging_config import get_logger
from database import (
    create_slot_transfer_request,
    get_slot_transfer_by_code,
    register_new_user_for_transfer,
    approve_slot_transfer,
    reject_slot_transfer,
    get_pending_slot_transfers,
    cancel_slot_transfer_request,
    get_participant_by_user_id,
)

logger = get_logger(__name__)


class SlotTransferForm(StatesGroup):
    """Состояния для процесса переоформления слота"""
    waiting_for_confirmation = State()


async def handle_slot_transfer_request(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Обработчик запроса на переоформление слота"""
    user_id = callback.from_user.id

    # Проверяем, что пользователь является участником
    participant = get_participant_by_user_id(user_id)
    if not participant:
        await callback.message.edit_text(
            "❌ Только зарегистрированные участники могут переоформить слот."
        )
        await callback.answer()
        return

    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, переоформить",
                    callback_data="confirm_slot_transfer"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_slot_transfer_request"
                ),
            ]
        ]
    )

    await callback.message.edit_text(
        "🔄 <b>Переоформление слота</b>\n\n"
        "⚠️ <b>Внимание!</b>\n"
        "После подтверждения будет создана реферальная ссылка, которую вы сможете отправить новому участнику.\n"
        "После регистрации нового участника по ссылке, администратор должен будет подтвердить переоформление.\n\n"
        "Вы уверены, что хотите продолжить?",
        reply_markup=confirm_keyboard
    )
    await callback.answer()


async def handle_confirm_slot_transfer(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Обработчик подтверждения переоформления слота"""
    user_id = callback.from_user.id
    username = callback.from_user.username or "не указан"

    # Проверяем наличие активного запроса
    from database import get_slot_transfer_by_code
    import sqlite3

    try:
        # Проверяем, есть ли уже активный запрос
        from database import DB_PATH
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, referral_code, status FROM slot_transfers
                WHERE original_user_id = ? AND status IN ('pending', 'awaiting_approval')
                """,
                (user_id,)
            )
            existing_request = cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при проверке существующего запроса: {e}")
        existing_request = None

    if existing_request:
        # У пользователя уже есть активный запрос
        request_id, ref_code, status = existing_request

        status_text = "ожидает регистрации нового участника" if status == "pending" else "ожидает подтверждения администратора"

        # Создаем клавиатуру с выбором
        choice_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗑 Отменить старый запрос",
                        callback_data=f"cancel_old_transfer_{request_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Оставить как есть",
                        callback_data="keep_old_transfer"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"⚠️ <b>У вас уже есть активный запрос на переоформление!</b>\n\n"
            f"🔑 <b>Код:</b> <code>{ref_code}</code>\n"
            f"📊 <b>Статус:</b> {status_text}\n\n"
            f"Хотите отменить старый запрос и создать новый?",
            reply_markup=choice_keyboard
        )
        await callback.answer()
        return

    # Создаем запрос на переоформление
    result = create_slot_transfer_request(user_id)

    if result["success"]:
        referral_code = result["referral_code"]
        user_name = result["user_name"]

        # Получаем имя бота для формирования ссылки
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        # Формируем реферальную ссылку
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"

        # Текст для отправки новому участнику
        share_text = "Привет! Передаю тебе слот на участие в Пивном Квартале. Регистрируйся по этой ссылке:"

        # Формируем полное сообщение с правильным кодированием для URL
        full_message = f"{share_text}\n{referral_link}"
        encoded_message = quote(full_message, safe='')

        # Сообщение пользователю с кнопкой "Поделиться"
        share_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Поделиться ссылкой",
                        url=f"https://t.me/share/url?url={encoded_message}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"✅ <b>Реферальная ссылка создана!</b>\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"📱 <b>Отправьте новому участнику следующее сообщение:</b>\n"
            f"<i>{share_text}</i>\n"
            f"<code>{referral_link}</code>\n\n"
            f"После регистрации нового участника администратор получит уведомление для подтверждения переоформления.\n\n"
            f"💡 <i>Используйте кнопку ниже для быстрой отправки</i>",
            reply_markup=share_keyboard
        )

        # Уведомляем админа
        try:
            admin_message = (
                f"🔄 <b>Создан запрос на переоформление слота</b>\n\n"
                f"👤 <b>Участник:</b> {user_name} (@{username})\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"🔑 <b>Код переоформления:</b> <code>{referral_code}</code>\n\n"
                f"⏳ Ожидается регистрация нового участника по реферальной ссылке."
            )
            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Ошибка при уведомлении администратора о запросе переоформления: {e}")

    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при создании запроса</b>\n\n{error_message}"
        )

    await callback.answer()


async def handle_cancel_slot_transfer_request(callback: CallbackQuery):
    """Обработчик отмены запроса на переоформление"""
    await callback.message.edit_text(
        "✅ <b>Запрос на переоформление отменен</b>\n\n"
        "Вы остаетесь в списке участников.\n"
        "Используйте команду /start для просмотра информации о вашей регистрации."
    )
    await callback.answer()


async def handle_cancel_old_transfer(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Обработчик отмены старого запроса и создания нового"""
    user_id = callback.from_user.id
    username = callback.from_user.username or "не указан"

    # Извлекаем request_id из callback_data
    request_id = int(callback.data.split("_")[3])

    # Удаляем старый запрос
    import sqlite3
    from database import DB_PATH

    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM slot_transfers WHERE id = ?", (request_id,))
            conn.commit()
            logger.info(f"Старый запрос на переоформление (ID: {request_id}) отменен пользователем {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении старого запроса: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка при отмене старого запроса</b>\n\n"
            "Попробуйте еще раз или свяжитесь с администратором."
        )
        await callback.answer()
        return

    # Создаем новый запрос на переоформление
    result = create_slot_transfer_request(user_id)

    if result["success"]:
        referral_code = result["referral_code"]
        user_name = result["user_name"]

        # Получаем имя бота для формирования ссылки
        bot_info = await bot.get_me()
        bot_username = bot_info.username

        # Формируем реферальную ссылку
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"

        # Текст для отправки новому участнику
        share_text = "Привет! Передаю тебе слот на участие в Пивном Квартале. Регистрируйся по этой ссылке:"

        # Формируем полное сообщение с правильным кодированием для URL
        full_message = f"{share_text}\n{referral_link}"
        from urllib.parse import quote
        encoded_message = quote(full_message, safe='')

        # Сообщение пользователю с кнопкой "Поделиться"
        share_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Поделиться ссылкой",
                        url=f"https://t.me/share/url?url={encoded_message}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"✅ <b>Новая реферальная ссылка создана!</b>\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"📱 <b>Отправьте новому участнику следующее сообщение:</b>\n"
            f"<i>{share_text}</i>\n"
            f"<code>{referral_link}</code>\n\n"
            f"После регистрации нового участника администратор получит уведомление для подтверждения переоформления.\n\n"
            f"💡 <i>Используйте кнопку ниже для быстрой отправки</i>",
            reply_markup=share_keyboard
        )

        # Уведомляем админа
        try:
            admin_message = (
                f"🔄 <b>Создан новый запрос на переоформление слота</b>\n"
                f"<i>(старый запрос был отменен пользователем)</i>\n\n"
                f"👤 <b>Участник:</b> {user_name} (@{username})\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"🔑 <b>Код переоформления:</b> <code>{referral_code}</code>\n\n"
                f"⏳ Ожидается регистрация нового участника по реферальной ссылке."
            )
            await bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Ошибка при уведомлении администратора о запросе переоформления: {e}")

    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при создании запроса</b>\n\n{error_message}"
        )

    await callback.answer()


async def handle_keep_old_transfer(callback: CallbackQuery):
    """Обработчик отказа от отмены старого запроса"""
    await callback.message.edit_text(
        "✅ <b>Оставлен существующий запрос</b>\n\n"
        "Ваш активный запрос на переоформление остается в силе.\n"
        "Используйте команду /start для просмотра информации о вашей регистрации."
    )
    await callback.answer()


async def handle_referral_start(message: Message, referral_code: str, bot: Bot, admin_id: int, state: FSMContext):
    """Обработчик перехода по реферальной ссылке"""
    user_id = message.from_user.id
    username = message.from_user.username or "не указан"

    # Проверяем, что пользователь не является участником
    participant = get_participant_by_user_id(user_id)
    if participant:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Вы уже зарегистрированы как участник.\n"
            "Эта ссылка предназначена для новых участников."
        )
        return

    # Получаем данные о переоформлении
    transfer_data = get_slot_transfer_by_code(referral_code)

    if not transfer_data:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Неверная реферальная ссылка или срок действия ссылки истек."
        )
        return

    (transfer_id, original_user_id, original_username, original_name,
     new_user_id, new_username, new_name, ref_code, request_date, status) = transfer_data

    # Проверяем статус переоформления
    if status != "pending":
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Эта ссылка уже была использована или переоформление было отменено."
        )
        return

    # Проверяем, что это не тот же пользователь
    if user_id == original_user_id:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Вы не можете переоформить слот на себя."
        )
        return

    # Запрашиваем имя нового участника
    await message.answer(
        f"👋 <b>Добро пожаловать!</b>\n\n"
        f"🔄 Вы переходите по ссылке для переоформления слота от участника <b>{original_name}</b>.\n\n"
        f"📝 <b>Пожалуйста, введите ваше полное имя:</b>"
    )

    # Сохраняем transfer_id в состоянии
    await state.update_data(transfer_id=transfer_id, original_name=original_name)
    await state.set_state(SlotTransferForm.waiting_for_confirmation)


async def handle_new_participant_name(message: Message, state: FSMContext, bot: Bot, admin_id: int):
    """Обработчик ввода имени нового участника"""
    user_id = message.from_user.id
    username = message.from_user.username or "не указан"
    new_name = message.text.strip()

    # Валидация имени
    if len(new_name) < 2 or len(new_name) > 50:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Имя должно содержать от 2 до 50 символов.\n"
            "Пожалуйста, введите ваше полное имя:"
        )
        return

    # Получаем данные из состояния
    user_data = await state.get_data()
    transfer_id = user_data.get("transfer_id")
    original_name = user_data.get("original_name")

    # Регистрируем нового пользователя для переоформления
    success = register_new_user_for_transfer(transfer_id, user_id, username, new_name)

    if success:
        await message.answer(
            f"✅ <b>Заявка отправлена!</b>\n\n"
            f"📋 <b>Ваше имя:</b> {new_name}\n\n"
            f"⏳ Ваша заявка на переоформление слота от участника <b>{original_name}</b> отправлена администратору.\n"
            f"Ожидайте подтверждения!"
        )

        # Уведомляем админа
        try:
            # Получаем данные о переоформлении
            from database import get_participant_by_user_id

            original_participant = get_participant_by_user_id(
                get_slot_transfer_by_code(
                    get_pending_slot_transfers()[0][7] if get_pending_slot_transfers() else ""
                )[1] if get_pending_slot_transfers() else 0
            )

            admin_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"approve_transfer_{transfer_id}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"reject_transfer_{transfer_id}"
                        ),
                    ]
                ]
            )

            admin_message = (
                f"🔄 <b>Запрос на подтверждение переоформления слота</b>\n\n"
                f"👤 <b>Оригинальный участник:</b> {original_name}\n"
                f"👤 <b>Новый участник:</b> {new_name} (@{username})\n"
                f"🆔 <b>ID нового участника:</b> <code>{user_id}</code>\n\n"
                f"❓ <b>Подтвердить переоформление?</b>"
            )

            await bot.send_message(admin_id, admin_message, reply_markup=admin_keyboard)
        except Exception as e:
            logger.error(f"Ошибка при уведомлении администратора о новом участнике: {e}")

    else:
        await message.answer(
            "❌ <b>Ошибка при регистрации!</b>\n\n"
            "Попробуйте еще раз или свяжитесь с администратором."
        )

    await state.clear()


async def handle_admin_approve_transfer(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Обработчик подтверждения переоформления администратором"""
    # Извлекаем transfer_id из callback_data
    transfer_id = int(callback.data.split("_")[2])

    result = approve_slot_transfer(transfer_id)

    if result["success"]:
        original_user_id = result["original_user_id"]
        original_name = result["original_name"]
        new_user_id = result["new_user_id"]
        new_name = result["new_name"]
        role = result["role"]

        await callback.message.edit_text(
            f"✅ <b>Переоформление слота подтверждено!</b>\n\n"
            f"👤 <b>Оригинальный участник:</b> {original_name} (ID: {original_user_id})\n"
            f"👤 <b>Новый участник:</b> {new_name} (ID: {new_user_id})\n"
            f"🎭 <b>Роль:</b> {role}\n\n"
            f"✅ Оригинальный участник удален, новый участник добавлен в базу."
        )

        # Уведомляем оригинального участника
        try:
            await bot.send_message(
                original_user_id,
                f"✅ <b>Переоформление слота завершено!</b>\n\n"
                f"Ваш слот был успешно переоформлен на участника <b>{new_name}</b>.\n"
                f"Спасибо за участие!"
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении оригинального участника: {e}")

        # Уведомляем нового участника
        try:
            await bot.send_message(
                new_user_id,
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Ваша регистрация подтверждена!\n"
                f"Вы успешно заняли слот участника <b>{original_name}</b>.\n\n"
                f"💰 <b>Важно:</b> Не забудьте произвести оплату участия!\n"
                f"Используйте команду /start для просмотра информации о вашей регистрации."
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении нового участника: {e}")

    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при подтверждении переоформления</b>\n\n{error_message}"
        )

    await callback.answer()


async def handle_admin_reject_transfer(callback: CallbackQuery, bot: Bot, admin_id: int):
    """Обработчик отклонения переоформления администратором"""
    # Извлекаем transfer_id из callback_data
    transfer_id = int(callback.data.split("_")[2])

    result = reject_slot_transfer(transfer_id)

    if result["success"]:
        original_user_id = result["original_user_id"]
        original_name = result["original_name"]
        new_user_id = result["new_user_id"]
        new_name = result["new_name"]

        await callback.message.edit_text(
            f"❌ <b>Переоформление слота отклонено!</b>\n\n"
            f"👤 <b>Оригинальный участник:</b> {original_name} (ID: {original_user_id})\n"
            f"👤 <b>Новый участник:</b> {new_name} (ID: {new_user_id})\n\n"
            f"Оригинальный участник остается в списке участников."
        )

        # Уведомляем оригинального участника
        try:
            await bot.send_message(
                original_user_id,
                f"❌ <b>Переоформление слота отклонено</b>\n\n"
                f"Ваш запрос на переоформление слота был отклонен администратором.\n"
                f"Вы остаетесь в списке участников."
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении оригинального участника: {e}")

        # Уведомляем нового участника
        try:
            await bot.send_message(
                new_user_id,
                f"❌ <b>Регистрация отклонена</b>\n\n"
                f"К сожалению, ваша заявка на переоформление слота была отклонена администратором.\n"
                f"Вы можете попробовать зарегистрироваться заново через команду /start."
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении нового участника: {e}")

    else:
        error_message = result.get("error", "Неизвестная ошибка")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при отклонении переоформления</b>\n\n{error_message}"
        )

    await callback.answer()


def register_slot_transfer_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    """Регистрация обработчиков переоформления слота"""

    # Запрос на переоформление слота
    async def slot_transfer_request_wrapper(callback: CallbackQuery):
        await handle_slot_transfer_request(callback, bot, admin_id)

    dp.callback_query.register(
        slot_transfer_request_wrapper,
        F.data == "slot_transfer"
    )

    # Подтверждение переоформления
    async def confirm_slot_transfer_wrapper(callback: CallbackQuery):
        await handle_confirm_slot_transfer(callback, bot, admin_id)

    dp.callback_query.register(
        confirm_slot_transfer_wrapper,
        F.data == "confirm_slot_transfer"
    )

    # Отмена запроса на переоформление
    dp.callback_query.register(
        handle_cancel_slot_transfer_request,
        F.data == "cancel_slot_transfer_request"
    )

    # Отмена старого запроса и создание нового
    async def cancel_old_transfer_wrapper(callback: CallbackQuery):
        await handle_cancel_old_transfer(callback, bot, admin_id)

    dp.callback_query.register(
        cancel_old_transfer_wrapper,
        F.data.startswith("cancel_old_transfer_")
    )

    # Оставить старый запрос
    dp.callback_query.register(
        handle_keep_old_transfer,
        F.data == "keep_old_transfer"
    )

    # Ввод имени нового участника
    async def new_participant_name_wrapper(message: Message, state: FSMContext):
        await handle_new_participant_name(message, state, bot, admin_id)

    dp.message.register(
        new_participant_name_wrapper,
        SlotTransferForm.waiting_for_confirmation
    )

    # Подтверждение переоформления администратором
    async def admin_approve_wrapper(callback: CallbackQuery):
        await handle_admin_approve_transfer(callback, bot, admin_id)

    dp.callback_query.register(
        admin_approve_wrapper,
        F.data.startswith("approve_transfer_")
    )

    # Отклонение переоформления администратором
    async def admin_reject_wrapper(callback: CallbackQuery):
        await handle_admin_reject_transfer(callback, bot, admin_id)

    dp.callback_query.register(
        admin_reject_wrapper,
        F.data.startswith("reject_transfer_")
    )

    logger.info("Обработчики переоформления слота зарегистрированы")
