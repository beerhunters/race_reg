import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
import os
from dotenv import load_dotenv

load_dotenv()

# Настройки бота
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
except KeyError as e:
    raise RuntimeError(f"Не найдена переменная окружения: {e}")

# Создаем экземпляры бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Определяем состояния для FSM (машина состояний)
class RegistrationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_target_time = State()


# Функции для работы с базой данных
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            name TEXT NOT NULL,
            target_time TEXT NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payment_status TEXT DEFAULT 'pending'
        )
    ''')
    
    conn.commit()
    conn.close()


def add_participant(user_id: int, username: str, name: str, target_time: str):
    """Добавление участника в базу данных"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO participants 
            (user_id, username, name, target_time, registration_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, name, target_time, datetime.now()))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка при добавлении участника: {e}")
        return False
    finally:
        conn.close()


def get_all_participants():
    """Получение списка всех участников"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT name, target_time, registration_date, payment_status, username
            FROM participants 
            ORDER BY registration_date DESC
        ''')
        
        participants = cursor.fetchall()
        return participants
    except Exception as e:
        print(f"Ошибка при получении участников: {e}")
        return []
    finally:
        conn.close()


def get_participant_count():
    """Получение количества участников"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM participants')
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        print(f"Ошибка при подсчете участников: {e}")
        return 0
    finally:
        conn.close()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await message.answer(
        "Добро пожаловать в систему регистрации на гонку! 🏁\n\n"
        "Для регистрации введите ваше имя:"
    )
    await state.set_state(RegistrationForm.waiting_for_name)


@dp.message(StateFilter(RegistrationForm.waiting_for_name))
async def process_name(message: Message, state: FSMContext):
    """Обработчик ввода имени"""
    name = message.text.strip()
    
    # Проверяем, что имя не пустое
    if not name:
        await message.answer("Пожалуйста, введите корректное имя:")
        return
    
    # Сохраняем имя в состоянии
    await state.update_data(name=name)
    
    await message.answer(
        f"Отлично, {name}! 👋\n\n"
        "Теперь укажите ваше целевое время прохождения гонки (например: 1:30:45 или 90 минут):"
    )
    await state.set_state(RegistrationForm.waiting_for_target_time)


@dp.message(StateFilter(RegistrationForm.waiting_for_target_time))
async def process_target_time(message: Message, state: FSMContext):
    """Обработчик ввода целевого времени"""
    target_time = message.text.strip()
    
    # Проверяем, что время не пустое
    if not target_time:
        await message.answer("Пожалуйста, введите корректное целевое время:")
        return
    
    # Получаем сохраненные данные
    user_data = await state.get_data()
    name = user_data.get('name')
    
    # Очищаем состояние
    await state.clear()
    
    # Сохраняем участника в базу данных
    username = message.from_user.username or "не указан"
    success = add_participant(
        user_id=message.from_user.id,
        username=username,
        name=name,
        target_time=target_time
    )
    
    if success:
        # Отправляем подтверждение пользователю
        await message.answer(
            f"✅ Регистрация завершена!\n\n"
            f"📝 Ваши данные:\n"
            f"• Имя: {name}\n"
            f"• Целевое время: {target_time}\n\n"
            f"💰 Ожидается оплата.\n"
            f"После поступления оплаты вы получите подтверждение участия."
        )
        
        # Отправляем информацию администратору
        try:
            participant_count = get_participant_count()
            admin_message = (
                f"🆕 Новая регистрация на гонку!\n\n"
                f"👤 Участник: {name}\n"
                f"🎯 Целевое время: {target_time}\n"
                f"🆔 ID пользователя: {message.from_user.id}\n"
                f"📱 Username: @{username}\n"
                f"📊 Всего участников: {participant_count}\n\n"
                f"⏳ Ожидается оплата..."
            )
            
            await bot.send_message(chat_id=ADMIN_ID, text=admin_message)
            
        except Exception as e:
            print(f"Ошибка при отправке сообщения администратору: {e}")
    else:
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
        )


@dp.message(Command("participants", "список", "участники"))
async def show_participants(message: Message):
    """Показать список всех участников"""
    # Проверяем, является ли пользователь администратором
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    participants = get_all_participants()
    
    if not participants:
        await message.answer("📋 Список участников пуст.")
        return
    
    # Формируем список участников
    participant_list = "🏁 **СПИСОК УЧАСТНИКОВ ГОНКИ**\n\n"
    
    for i, (name, target_time, reg_date, payment_status, username) in enumerate(participants, 1):
        # Форматируем дату
        try:
            date_obj = datetime.fromisoformat(reg_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_date = reg_date
        
        # Эмодзи для статуса оплаты
        status_emoji = "✅" if payment_status == "paid" else "⏳"
        
        participant_list += (
            f"{i}. **{name}**\n"
            f"   🎯 Цель: {target_time}\n"
            f"   📱 @{username}\n"
            f"   📅 {formatted_date}\n"
            f"   {status_emoji} {payment_status}\n\n"
        )
    
    participant_list += f"📊 **Всего участников: {len(participants)}**"
    
    # Telegram имеет ограничение на длину сообщения (4096 символов)
    if len(participant_list) > 4000:
        # Разбиваем на части
        chunks = []
        current_chunk = "🏁 **СПИСОК УЧАСТНИКОВ ГОНКИ**\n\n"
        
        for i, (name, target_time, reg_date, payment_status, username) in enumerate(participants, 1):
            try:
                date_obj = datetime.fromisoformat(reg_date.replace('Z', '+00:00'))
                formatted_date = date_obj.strftime("%d.%m.%Y %H:%M")
            except:
                formatted_date = reg_date
            
            status_emoji = "✅" if payment_status == "paid" else "⏳"
            
            participant_info = (
                f"{i}. **{name}**\n"
                f"   🎯 Цель: {target_time}\n"
                f"   📱 @{username}\n"
                f"   📅 {formatted_date}\n"
                f"   {status_emoji} {payment_status}\n\n"
            )
            
            if len(current_chunk + participant_info) > 3900:
                chunks.append(current_chunk)
                current_chunk = participant_info
            else:
                current_chunk += participant_info
        
        if current_chunk:
            current_chunk += f"📊 **Всего участников: {len(participants)}**"
            chunks.append(current_chunk)
        
        # Отправляем по частям
        for chunk in chunks:
            await message.answer(chunk, parse_mode="Markdown")
    else:
        await message.answer(participant_list, parse_mode="Markdown")


@dp.message()
async def handle_other_messages(message: Message):
    """Обработчик всех остальных сообщений"""
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "🤖 **Команды бота:**\n\n"
            "👥 **Для всех:**\n"
            "• /start - начать регистрацию\n\n"
            "🔧 **Для администратора:**\n"
            "• /participants - список участников\n"
            "• /stats - статистика участников\n"
            "• /paid USER_ID - отметить как оплатившего\n"
            "• /remove USER_ID - удалить участника\n"
            "• /export - экспорт в CSV",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "Доступные команды:\n"
            "• /start - начать регистрацию на гонку"
        )


# Добавьте эти функции и команды в основной файл бота

def update_payment_status(user_id: int, status: str):
    """Обновление статуса оплаты участника"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE participants 
            SET payment_status = ? 
            WHERE user_id = ?
        ''', (status, user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Ошибка при обновлении статуса оплаты: {e}")
        return False
    finally:
        conn.close()


def delete_participant(user_id: int):
    """Удаление участника из базы данных"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM participants WHERE user_id = ?', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Ошибка при удалении участника: {e}")
        return False
    finally:
        conn.close()


def get_participant_by_user_id(user_id: int):
    """Получение информации об участнике по user_id"""
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT user_id, username, name, target_time, registration_date, payment_status
            FROM participants 
            WHERE user_id = ?
        ''', (user_id,))
        
        participant = cursor.fetchone()
        return participant
    except Exception as e:
        print(f"Ошибка при получении участника: {e}")
        return None
    finally:
        conn.close()


# Добавьте эти обработчики команд в основной файл:

@dp.message(Command("stats", "статистика"))
async def show_stats(message: Message):
    """Показать статистику участников"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    
    try:
        # Общее количество участников
        cursor.execute('SELECT COUNT(*) FROM participants')
        total_count = cursor.fetchone()[0]
        
        # Количество оплативших
        cursor.execute('SELECT COUNT(*) FROM participants WHERE payment_status = "paid"')
        paid_count = cursor.fetchone()[0]
        
        # Количество ожидающих оплату
        cursor.execute('SELECT COUNT(*) FROM participants WHERE payment_status = "pending"')
        pending_count = cursor.fetchone()[0]
        
        # Последние регистрации (за сегодня)
        cursor.execute('''
            SELECT COUNT(*) FROM participants 
            WHERE DATE(registration_date) = DATE('now')
        ''')
        today_count = cursor.fetchone()[0]
        
        stats_message = (
            f"📊 **СТАТИСТИКА УЧАСТНИКОВ**\n\n"
            f"👥 Всего участников: **{total_count}**\n"
            f"✅ Оплатили: **{paid_count}**\n"
            f"⏳ Ожидают оплаты: **{pending_count}**\n"
            f"📅 Зарегистрировались сегодня: **{today_count}**\n"
        )
        
        await message.answer(stats_message, parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики: {e}")
    finally:
        conn.close()


@dp.message(Command("paid"))
async def mark_as_paid(message: Message):
    """Отметить участника как оплатившего"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    # Ожидаем формат: /paid USER_ID
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: /paid USER_ID")
            return
        
        user_id = int(parts[1])
        
        # Проверяем, существует ли участник
        participant = get_participant_by_user_id(user_id)
        if not participant:
            await message.answer(f"❌ Участник с ID {user_id} не найден.")
            return
        
        # Обновляем статус оплаты
        if update_payment_status(user_id, "paid"):
            await message.answer(f"✅ Участник {participant[2]} (ID: {user_id}) отмечен как оплативший.")
            
            # Уведомляем участника
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="✅ Ваша оплата подтверждена! Вы успешно зарегистрированы на гонку. До встречи на старте! 🏁"
                )
            except:
                pass  # Если не удалось отправить уведомление пользователю
        else:
            await message.answer("❌ Ошибка при обновлении статуса оплаты.")
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("remove"))
async def remove_participant(message: Message):
    """Удалить участника"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: /remove USER_ID")
            return
        
        user_id = int(parts[1])
        
        # Получаем информацию об участнике перед удалением
        participant = get_participant_by_user_id(user_id)
        if not participant:
            await message.answer(f"❌ Участник с ID {user_id} не найден.")
            return
        
        # Удаляем участника
        if delete_participant(user_id):
            await message.answer(f"✅ Участник {participant[2]} (ID: {user_id}) удален из списка.")
        else:
            await message.answer("❌ Ошибка при удалении участника.")
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("export"))
async def export_participants(message: Message):
    """Экспорт списка участников в CSV"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    participants = get_all_participants()
    
    if not participants:
        await message.answer("📋 Список участников пуст.")
        return
    
    # Создаем CSV данные
    csv_content = "Имя,Целевое время,Дата регистрации,Статус оплаты,Username\n"
    
    for name, target_time, reg_date, payment_status, username in participants:
        csv_content += f'"{name}","{target_time}","{reg_date}","{payment_status}","@{username}"\n'
    
    # Сохраняем во временный файл
    with open('participants_export.csv', 'w', encoding='utf-8') as f:
        f.write(csv_content)
    
    # Отправляем файл
    try:
        with open('participants_export.csv', 'rb') as f:
            await bot.send_document(
                chat_id=message.chat.id,
                document=f,
                caption=f"📊 Экспорт участников гонки\nВсего участников: {len(participants)}"
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке файла: {e}")
    finally:
        # Удаляем временный файл
        try:
            os.remove('participants_export.csv')
        except:
            pass

async def main():
    """Основная функция запуска бота"""
    print("Инициализация базы данных...")
    init_db()
    
    print("Бот запускается...")
    try:
        # Удаляем старые обновления и запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())