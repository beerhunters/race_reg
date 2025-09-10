from datetime import datetime

from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from pytz import timezone

from .utils import logger, messages, RegistrationForm
from .validation import validate_participant_limit, sanitize_input
from database import (
    get_setting,
    set_setting,
    get_participant_count_by_role,
    get_pending_registrations,
    delete_pending_registration,
)


def register_settings_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков настроек")

    async def edit_runners(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда изменения лимита участников от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event
        
        # Get current stats
        current_runners = get_participant_count_by_role("runner")
        current_max = get_setting("max_runners")
        
        text = "🔢 <b>Изменить лимит участников</b>\n\n"
        text += f"📊 <b>Текущая статистика:</b>\n"
        text += f"• Лимит бегунов: {current_max}\n"
        text += f"• Зарегистрировано: {current_runners}\n"
        text += f"• Свободных мест: {current_max - current_runners}\n\n"
        
        # Check waitlist
        waitlist_data = []
        try:
            from database import get_waitlist_by_role
            waitlist_data = get_waitlist_by_role()
        except:
            pass
        
        if waitlist_data:
            text += f"⏳ В очереди ожидания: {len(waitlist_data)}\n\n"
        
        text += "✏️ Введите новый лимит участников:\n"
        text += f"• Минимум: {current_runners} (не менее уже зарегистрированных)\n"
        text += "• Рекомендуемый максимум: 100\n"
        text += "• При увеличении лимита автоматически обработается очередь ожидания"
        
        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_runners)

    @dp.message(RegistrationForm.waiting_for_runners)
    async def process_edit_runners(message: Message, state: FSMContext):
        user_input = sanitize_input(message.text, 10)
        
        try:
            new_max_runners = int(user_input)
        except ValueError:
            await message.answer("❌ Лимит должен быть числом.")
            return
        
        current_runners = get_participant_count_by_role("runner")
        is_valid, error_message = validate_participant_limit(new_max_runners, current_runners)
        
        if not is_valid:
            await message.answer(f"❌ {error_message}")
            return
        
        old_max_runners = get_setting("max_runners")
        if old_max_runners is None:
            logger.error("Не найдена настройка max_runners в базе данных")
            await message.answer("Ошибка конфигурации. Свяжитесь с администратором.")
            return
        success = set_setting("max_runners", new_max_runners)
        if success:
            text = "✅ <b>Лимит участников изменён</b>\n\n"
            text += f"📊 <b>Изменения:</b>\n"
            text += f"• Старый лимит: {old_max_runners}\n"
            text += f"• Новый лимит: {new_max_runners}\n"
            text += f"• Зарегистрировано: {current_runners}\n"
            text += f"• Свободных мест: {new_max_runners - current_runners}\n"
            
            if new_max_runners > old_max_runners:
                added_slots = new_max_runners - old_max_runners
                text += f"• Добавлено мест: +{added_slots}\n\n"
                text += "🔄 Обрабатываю очередь ожидания..."
                await message.answer(text)
                
                # Process waitlist for newly available slots
                try:
                    from .waitlist_handlers import check_and_process_waitlist
                    processed_count = await check_and_process_waitlist(bot, admin_id, "runner")
                    if processed_count > 0:
                        await message.answer(
                            f"✅ Из очереди ожидания переведено {processed_count} участников."
                        )
                    else:
                        await message.answer("ℹ️ Очередь ожидания пуста или все уведомления уже отправлены.")
                except Exception as e:
                    logger.error(f"Ошибка при обработке очереди ожидания: {e}")
                    await message.answer("⚠️ Лимит изменён, но возникла ошибка при обработке очереди ожидания.")
            elif new_max_runners < old_max_runners:
                removed_slots = old_max_runners - new_max_runners
                text += f"• Убрано мест: -{removed_slots}\n\n"
                text += "⚠️ Внимание: уже зарегистрированные участники остаются в системе."
                await message.answer(text)
            else:
                text += "\n💡 Лимит остался прежним."
                await message.answer(text)
                
            logger.info(f"Лимит бегунов изменен с {old_max_runners} на {new_max_runners}")
                
        else:
            logger.error("Ошибка при обновлении настройки max_runners")
            await message.answer("❌ Ошибка при изменении лимита участников. Попробуйте снова.")
            
        await state.clear()

    @dp.message(Command("edit_runners"))
    async def cmd_edit_runners(message: Message, state: FSMContext):
        await edit_runners(message, state)

    @dp.callback_query(F.data == "admin_edit_runners")
    async def callback_edit_runners(callback_query: CallbackQuery, state: FSMContext):
        await edit_runners(callback_query, state)

    @dp.message(Command("set_reg_end_date"))
    @dp.callback_query(F.data == "admin_set_reg_end_date")
    async def set_reg_end_date(event: [Message, CallbackQuery], state: FSMContext):
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда установки даты окончания регистрации от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event
            
        # Get current end date
        current_end_date = get_setting("reg_end_date")
        
        text = "📅 <b>Установить дату окончания регистрации</b>\n\n"
        
        if current_end_date:
            text += f"📊 Текущая дата: {current_end_date}\n\n"
        else:
            text += "📊 Дата окончания не установлена\n\n"
            
        # Show current Moscow time
        moscow_tz = timezone("Europe/Moscow")
        current_time = datetime.now(moscow_tz)
        text += f"🕐 Текущее время (МСК): {current_time.strftime('%H:%M %d.%m.%Y')}\n\n"
        
        text += "✏️ Введите дату и время окончания регистрации:\n"
        text += "• Формат: <code>ЧЧ:ММ ДД.ММ.ГГГГ</code>\n"
        text += "• Пример: <code>23:59 31.12.2025</code>\n"
        text += "• Время указывается по московскому часовому поясу\n"
        text += "• Дата должна быть в будущем"
        
        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_reg_end_date)

    @dp.message(RegistrationForm.waiting_for_reg_end_date)
    async def process_reg_end_date(message: Message, state: FSMContext):
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return
            
        date_text = sanitize_input(message.text, 20).strip()
        
        try:
            # Parse the date
            end_date = datetime.strptime(date_text, "%H:%M %d.%m.%Y")
            moscow_tz = timezone("Europe/Moscow")
            end_date = moscow_tz.localize(end_date)
            current_time = datetime.now(moscow_tz)
            
            # Check if date is in the future
            if end_date <= current_time:
                time_diff = (current_time - end_date).total_seconds() / 60
                await message.answer(
                    f"❌ Указанная дата уже прошла на {int(time_diff)} минут.\n\n"
                    f"Укажите дату в будущем. Текущее время: {current_time.strftime('%H:%M %d.%m.%Y')}"
                )
                return
            
            # Get old date for comparison
            old_date = get_setting("reg_end_date")
            
            # Save new date
            success = set_setting("reg_end_date", date_text)
            
            if success:
                text = "✅ <b>Дата окончания регистрации установлена</b>\n\n"
                
                if old_date:
                    text += f"📊 Старая дата: {old_date}\n"
                
                text += f"📅 Новая дата: <b>{date_text}</b>\n"
                text += f"🕐 Московское время (МСК)\n\n"
                
                # Calculate time until deadline
                time_left = end_date - current_time
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                text += f"⏰ До окончания регистрации:\n"
                if days > 0:
                    text += f"• {days} дней\n"
                if hours > 0 or days > 0:
                    text += f"• {hours} часов\n"
                text += f"• {minutes} минут"
                
                await message.answer(text)
                logger.info(f"Дата окончания регистрации установлена: {date_text}")
            else:
                await message.answer("❌ Ошибка при сохранении даты. Попробуйте снова.")
                
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты.\n\n"
                "Используйте формат: <code>ЧЧ:ММ ДД.ММ.ГГГГ</code>\n"
                "Пример: <code>23:59 31.12.2025</code>"
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке даты окончания регистрации: {e}")
            await message.answer("❌ Произошла ошибка при обработке даты. Попробуйте снова.")
            
        await state.clear()

    @dp.message(Command("set_price"))
    @dp.callback_query(F.data == "admin_set_price")
    async def set_participation_price(event: [Message, CallbackQuery], state: FSMContext):
        """Set participation price"""
        user_id = event.from_user.id
        if user_id != admin_id:
            await event.answer("❌ Доступ запрещен")
            return
        logger.info(f"Команда изменения цены участия от user_id={user_id}")
        
        if isinstance(event, CallbackQuery):
            await event.message.delete()
            message = event.message
            await event.answer()
        else:
            await event.delete()
            message = event
        
        # Get current price
        current_price = get_setting("participation_price")
        if current_price is None:
            current_price = "не установлена"
        
        text = "💰 <b>Изменить цену участия</b>\n\n"
        text += f"📊 Текущая цена: {current_price}\n\n"
        text += "✏️ Введите новую цену участия в рублях:\n"
        text += "• Только число (например: 1500)\n"
        text += "• Или 0 для бесплатного участия\n"
        text += "• Цена будет сохранена в базе данных"
        
        await message.answer(text)
        await state.set_state(RegistrationForm.waiting_for_price)

    @dp.message(RegistrationForm.waiting_for_price)
    async def process_participation_price(message: Message, state: FSMContext):
        """Process new participation price"""
        if message.from_user.id != admin_id:
            await message.answer("❌ Доступ запрещен")
            await state.clear()
            return
        
        price_text = sanitize_input(message.text, 10).strip()
        
        try:
            new_price = int(price_text)
            if new_price < 0:
                await message.answer("❌ Цена не может быть отрицательной. Попробуйте снова:")
                return
        except ValueError:
            await message.answer("❌ Цена должна быть числом (например: 1500). Попробуйте снова:")
            return
        
        # Get old price for logging
        old_price = get_setting("participation_price")
        old_price_str = str(old_price) if old_price is not None else "не установлена"
        
        # Save new price
        success = set_setting("participation_price", new_price)
        
        if success:
            if new_price == 0:
                price_text = "бесплатно"
            else:
                price_text = f"{new_price} руб."
            
            text = "✅ <b>Цена участия изменена</b>\n\n"
            text += f"📊 Старая цена: {old_price_str}\n"
            text += f"💰 Новая цена: {price_text}\n\n"
            text += "🔄 Изменения вступают в силу немедленно для новых регистраций."
            
            await message.answer(text)
            logger.info(f"Цена участия изменена с '{old_price_str}' на '{new_price}' руб.")
        else:
            await message.answer("❌ Ошибка при сохранении цены. Попробуйте снова.")
            logger.error("Ошибка при обновлении настройки participation_price")
        
        await state.clear()

    logger.info("Обработчики настроек зарегистрированы")
