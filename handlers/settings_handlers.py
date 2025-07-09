from datetime import datetime

from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from pytz import timezone

from .utils import logger, messages, RegistrationForm
from database import (
    get_setting,
    set_setting,
    get_participant_count_by_role,
    get_pending_registrations,
    delete_pending_registration,
)


def register_settings_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков настроек")

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
        old_max_runners = get_setting("max_runners")
        if old_max_runners is None:
            logger.error("Не найдена настройка max_runners в базе данных")
            await message.answer("Ошибка конфигурации. Свяжитесь с администратором.")
            return
        current_runners = get_participant_count_by_role("runner")
        if new_max_runners < old_max_runners:
            if new_max_runners < current_runners:
                logger.warning(
                    f"Попытка установить лимит бегунов ({new_max_runners}) меньше текущего числа бегунов ({current_runners})"
                )
                await message.answer(
                    messages["edit_runners_too_low"].format(
                        current=current_runners, requested=new_max_runners
                    )
                )
                return
        success = set_setting("max_runners", new_max_runners)
        if success:
            logger.info(
                f"Лимит бегунов изменен с {old_max_runners} на {new_max_runners}"
            )
            await message.answer(
                messages["edit_runners_success"].format(
                    old=old_max_runners, new=new_max_runners
                )
            )
            if new_max_runners > old_max_runners:
                available_slots = new_max_runners - current_runners
                if available_slots > 0:
                    pending_users = get_pending_registrations()
                    for user_id, username, name, target_time, role in pending_users:
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
                        except TelegramForbiddenError:
                            logger.warning(
                                f"Пользователь user_id={user_id} заблокировал бот"
                            )
                            delete_pending_registration(user_id)
                            logger.info(
                                f"Пользователь user_id={user_id} удалён из таблицы pending_registrations"
                            )
                            name = name or "неизвестно"
                            username = username or "не указан"
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
                            logger.error(
                                f"Ошибка при отправке уведомления пользователю user_id={user_id}: {e}"
                            )
        else:
            logger.error("Ошибка при обновлении настройки max_runners")
            await message.answer(
                "Ошибка при изменении лимита бегунов. Попробуйте снова."
            )

    @dp.message(Command("set_reg_end_date"))
    async def set_reg_end_date(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            await message.answer(messages["set_reg_end_date_access_denied"])
            return
        await message.answer(messages["set_reg_end_date_prompt"])
        await state.set_state(RegistrationForm.waiting_for_reg_end_date)

    @dp.message(RegistrationForm.waiting_for_reg_end_date)
    async def process_reg_end_date(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            await message.answer(messages["set_reg_end_date_access_denied"])
            await state.clear()
            return
        date_text = message.text.strip()
        try:
            end_date = datetime.strptime(date_text, "%H:%M %d.%m.%Y")
            moscow_tz = timezone("Europe/Moscow")
            end_date = moscow_tz.localize(end_date)
            current_time = datetime.now(moscow_tz)
            if end_date < current_time:
                await message.answer(messages["set_reg_end_date_invalid"])
                return
            set_setting("reg_end_date", date_text)
            await message.answer(
                messages["set_reg_end_date_success"].format(date=date_text)
            )
            logger.info(f"Дата и время окончания регистрации установлены: {date_text}")
        except ValueError:
            await message.answer(messages["set_reg_end_date_invalid_format"])
            await state.clear()
        await state.clear()
