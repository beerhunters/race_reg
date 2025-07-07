import json
import sqlite3
import logging
import os

logger = logging.getLogger(__name__)
DB_PATH = "/app/data/race_participants.db"

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Файл config.json успешно загружен")
except FileNotFoundError:
    logger.error("Файл config.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе config.json: {e}")
    raise


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    try:
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
                    payment_status TEXT,
                    bib_number INTEGER
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    user_id INTEGER PRIMARY KEY
                )
            """
            )
            conn.commit()
            cursor.execute("PRAGMA table_info(participants)")
            columns = [info[1] for info in cursor.fetchall()]
            expected_columns = [
                "user_id",
                "username",
                "name",
                "target_time",
                "role",
                "reg_date",
                "payment_status",
                "bib_number",
            ]
            if columns != expected_columns:
                logger.error(
                    f"Структура таблицы participants не соответствует ожидаемой: {columns}"
                )
                raise ValueError("Неверная структура таблицы participants")
            logger.info("База данных успешно инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def add_pending_registration(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO pending_registrations (user_id) VALUES (?)",
                (user_id,),
            )
            conn.commit()
            logger.info(f"Добавлена незавершённая регистрация для user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при добавлении в pending_registrations для user_id={user_id}: {e}"
        )
        return False


def get_pending_registrations():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM pending_registrations")
            pending = cursor.fetchall()
            return [row[0] for row in pending]
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении pending_registrations: {e}")
        return []


def delete_pending_registration(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pending_registrations WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            logger.info(f"Удалена незавершённая регистрация для user_id={user_id}")
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при удалении pending_registrations для user_id={user_id}: {e}"
        )


def get_all_participants():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM participants ORDER BY role = 'runner' DESC, reg_date ASC"
            )
            participants = cursor.fetchall()
            return participants
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении списка участников: {e}")
        return []


def get_participant_count():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants")
            count = cursor.fetchone()[0]
            return count
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении количества участников: {e}")
        return 0


def get_participant_count_by_role(role: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM participants WHERE role = ?", (role,))
            count = cursor.fetchone()[0]
            return count
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении количества участников с ролью {role}: {e}")
        return 0


def update_payment_status(user_id: int, status: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET payment_status = ? WHERE user_id = ?",
                (status, user_id),
            )
            conn.commit()
            logger.info(f"Статус оплаты обновлён для user_id={user_id}: {status}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении статуса оплаты для user_id={user_id}: {e}")


def set_bib_number(user_id: int, bib_number: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET bib_number = ? WHERE user_id = ?",
                (bib_number, user_id),
            )
            conn.commit()
            logger.info(f"Беговой номер {bib_number} установлен для user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке бегового номера для user_id={user_id}: {e}")
        return False


def delete_participant(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"Участник удалён: user_id={user_id}")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении участника user_id={user_id}: {e}")


def get_participant_by_user_id(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM participants WHERE user_id = ?", (user_id,))
            participant = cursor.fetchone()
            return participant
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении участника user_id={user_id}: {e}")
        return None


def add_participant(
    user_id: int, username: str, name: str, target_time: str, role: str
):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status)
                VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
                """,
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    role,
                    "pending" if role == "runner" else "paid",
                ),
            )
            conn.commit()
            logger.info(f"Участник добавлен: {name}, {role}, user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
        return False
