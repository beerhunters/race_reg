import sqlite3
import datetime
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/app/logs/bot.log")],
)
logger = logging.getLogger(__name__)

DB_PATH = "/app/data/race_participants.db"


def init_db():
    logger.info(f"Инициализация базы данных по пути: {DB_PATH}")
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                target_time TEXT,
                role TEXT,
                reg_date TEXT,
                payment_status TEXT
            )"""
            )
            conn.commit()
            logger.info("База данных успешно инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise


def add_participant(
    user_id: int, username: str, name: str, target_time: str, role: str
):
    logger.info(f"Добавление участника: user_id={user_id}, name={name}, role={role}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    role,
                    datetime.datetime.now().isoformat(),
                    "pending",
                ),
            )
            conn.commit()
            logger.info("Участник успешно добавлен")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении участника: {e}")
        return False


def get_all_participants():
    logger.info("Получение списка всех участников")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants"
            )
            participants = cursor.fetchall()
            logger.info(f"Получено {len(participants)} участников")
            return participants
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении участников: {e}")
        return []


def get_participant_count():
    logger.info("Получение общего количества участников")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants")
            count = cursor.fetchone()[0]
            logger.info(f"Количество участников: {count}")
            return count
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении количества участников: {e}")
        return 0


def get_participant_count_by_role(role: str):
    logger.info(f"Получение количества участников с ролью: {role}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants WHERE role = ?", (role,))
            count = cursor.fetchone()[0]
            logger.info(f"Количество участников с ролью {role}: {count}")
            return count
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении количества участников с ролью {role}: {e}")
        return 0


def update_payment_status(user_id: int, status: str):
    logger.info(f"Обновление статуса оплаты для user_id={user_id} на {status}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET payment_status = ? WHERE user_id = ?",
                (status, user_id),
            )
            conn.commit()
            logger.info("Статус оплаты обновлен")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении статуса оплаты: {e}")


def delete_participant(user_id: int):
    logger.info(f"Удаление участника с user_id={user_id}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info("Участник успешно удален")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении участника: {e}")


def get_participant_by_user_id(user_id: int):
    logger.info(f"Получение участника с user_id={user_id}")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants WHERE user_id = ?",
                (user_id,),
            )
            participant = cursor.fetchone()
            logger.info(f"Участник найден: {participant}")
            return participant
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении участника: {e}")
        return None
