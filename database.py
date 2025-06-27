import sqlite3
import logging
import os
import json

logger = logging.getLogger(__name__)
DB_PATH = "/app/data/race_participants.db"

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Файл config.json успешно загружен в database.py")
except FileNotFoundError:
    logger.error("Файл config.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе config.json: {e}")
    raise

log_level = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
if config.get("log_level") not in log_level:
    logger.error(
        f"Недопустимое значение log_level: {config.get('log_level')}. Используется ERROR."
    )
    logging.getLogger().setLevel(logging.ERROR)
else:
    logging.getLogger().setLevel(log_level[config["log_level"]])
    logger.info(f"Установлен уровень логирования: {config['log_level']} в database.py")


def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        logger.debug(f"Проверка/создание директории: {os.path.dirname(DB_PATH)}")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS participants (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    target_time TEXT,
                    role TEXT,
                    reg_date TEXT,
                    payment_status TEXT
                )
            """
            )
            conn.commit()
            logger.info("База данных инициализирована успешно")
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при создании таблицы participants: {e}")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при инициализации базы данных: {e}")
        raise


def get_all_participants():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants"
            )
            participants = cursor.fetchall()
            logger.debug(f"Получено {len(participants)} участников")
            return participants
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении всех участников: {e}")
        raise


def get_participant_count():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants")
            count = cursor.fetchone()[0]
            logger.debug(f"Количество участников: {count}")
            return count
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении количества участников: {e}")
        raise


def get_participant_count_by_role(role: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants WHERE role = ?", (role,))
            count = cursor.fetchone()[0]
            logger.debug(f"Количество участников с ролью {role}: {count}")
            return count
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении количества участников с ролью {role}: {e}")
        raise


def add_participant(
    user_id: int, username: str, name: str, target_time: str, role: str
):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status)
                VALUES (?, ?, ?, ?, ?, datetime('now'), 'pending')
            """,
                (user_id, username, name, target_time, role),
            )
            conn.commit()
            logger.info(f"Участник user_id={user_id} успешно добавлен")
            return True
    except sqlite3.IntegrityError:
        logger.error(f"Пользователь user_id={user_id} уже зарегистрирован")
        return False
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
        raise


def update_payment_status(user_id: int, status: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET payment_status = ? WHERE user_id = ?",
                (status, user_id),
            )
            conn.commit()
            logger.info(f"Статус оплаты обновлен для user_id={user_id}: {status}")
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при обновлении статуса оплаты для user_id={user_id}: {e}")
        raise


def delete_participant(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"Участник user_id={user_id} удален")
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при удалении участника user_id={user_id}: {e}")
        raise


def get_participant_by_user_id(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM participants WHERE user_id = ?", (user_id,))
            participant = cursor.fetchone()
            logger.debug(f"Получены данные участника user_id={user_id}: {participant}")
            return participant
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении участника user_id={user_id}: {e}")
        raise
