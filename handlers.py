from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import json
import datetime
from database import (
    add_participant,
    get_all_participants,
    get_participant_count,
    get_participant_by_user_id,
    update_payment_status,
    delete_participant,
    get_participant_count_by_role,
)

with open("messages.json", "r", encoding="utf-8") as f:
    messages = json.load(f)
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


class RegistrationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_target_time = State()
    waiting_for_role = State()


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
    await message.answer(messages["start_message"])
    await state.set_state(RegistrationForm.waiting_for_name)


@dp.message(StateFilter(RegistrationForm.waiting_for_name))
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer(messages["target_time_prompt"])
    await state.set_state(RegistrationForm.waiting_for_target_time)


@dp.message(StateFilter(RegistrationForm.waiting_for_target_time))
async def process_target_time(message: Message, state: FSMContext):
    target_time = message.text.strip()
    await state.update_data(target_time=target_time)
    await message.answer(messages["role_prompt"], reply_markup=create_role_keyboard())
    await state.set_state(RegistrationForm.waiting_for_role)


@dp.callback_query(StateFilter(RegistrationForm.waiting_for_role))
async def process_role(callback_query, state: FSMContext):
    role = "runner" if callback_query.data == "role_runner" else "volunteer"
    max_count = config["max_runners"] if role == "runner" else config["max_volunteers"]
    current_count = get_participant_count_by_role(role)
    if current_count >= max_count:
        await callback_query.message.answer(messages[f"limit_exceeded_{role}"])
        await state.clear()
        return
    user_data = await state.get_data()
    name = user_data.get("name")
    target_time = user_data.get("target_time")
    username = callback_query.from_user.username or "не указан"
    success = add_participant(
        callback_query.from_user.id, username, name, target_time, role
    )
    if success:
        await callback_query.message.answer(
            messages["registration_success"].format(
                name=name, target_time=target_time, role=role
            )
        )
        await callback_query.message.answer(messages["sponsor_message"])
        participant_count = get_participant_count()
        admin_message = f"Новый участник: {name}, Целевое время: {target_time}, Роль: {role}, Username: @{username}\nВсего участников: {participant_count}"
        await bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    await state.clear()


@dp.message(Command("participants", "список", "участники"))
async def show_participants(message: Message):
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
    conn = sqlite3.connect("race_participants.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM participants")
    total_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM participants WHERE payment_status = "paid"')
    paid_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM participants WHERE payment_status = "pending"')
    pending_count = cursor.fetchone()[0]
    cursor.execute(
        'SELECT COUNT(*) FROM participants WHERE DATE(reg_date) = DATE("now")'
    )
    today_count = cursor.fetchone()[0]
    conn.close()
    stats_message = messages["stats_message"].format(
        total=total_count, paid=paid_count, pending=pending_count, today=today_count
    )
    await message.answer(stats_message)


@dp.message(Command("paid"))
async def mark_as_paid(message: Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используйте: /paid <user_id>")
        return
    user_id = int(parts[1])
    participant = get_participant_by_user_id(user_id)
    if participant:
        update_payment_status(user_id, "paid")
        await message.answer(messages["paid_success"].format(name=participant[2]))
    else:
        await message.answer("Участник не найден.")


@dp.message(Command("remove"))
async def remove_participant(message: Message):
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
    participants = get_all_participants()
    csv_content = "Имя,Целевое время,Роль,Дата регистрации,Статус оплаты,Username\n"
    for (
        user_id,
        username,
        name,
        target_time,
        role,
        reg_date,
        payment_status,
    ) in participants:
        csv_content += (
            f"{name},{target_time},{role},{reg_date},{payment_status},{username}\n"
        )
    await message.answer(messages["export_message"])
    await message.answer_document(
        document=InputFile(io.StringIO(csv_content), filename="participants.csv")
    )


@dp.message()
async def handle_other_messages(message: Message):
    await message.answer(messages["invalid_command"])
