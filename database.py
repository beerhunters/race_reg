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
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS participants (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT NOT NULL,
                    target_time TEXT,
                    role TEXT NOT NULL,
                    reg_date TEXT NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    bib_number INTEGER,
                    result TEXT
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    target_time TEXT,
                    role TEXT
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """
            )
            cursor.execute("PRAGMA table_info(pending_registrations)")
            columns = [info[1] for info in cursor.fetchall()]
            required_columns = ["username", "name", "target_time", "role"]
            for column in required_columns:
                if column not in columns:
                    cursor.execute(
                        f"ALTER TABLE pending_registrations ADD COLUMN {column} TEXT"
                    )
                    logger.info(
                        f"Добавлен столбец {column} в таблицу pending_registrations"
                    )
            cursor.execute(
                "SELECT key FROM settings WHERE key IN ('max_runners', 'max_volunteers')"
            )
            columns = [info[0] for info in cursor.fetchall()]
            expected_columns = ["max_runners", "max_volunteers"]
            missing_columns = [col for col in expected_columns if col not in columns]
            for col in missing_columns:
                cursor.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)", (col, 100)
                )
            conn.commit()
            logger.info("База данных инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def add_pending_registration(
    user_id: int,
    username: str = None,
    name: str = None,
    target_time: str = None,
    role: str = None,
) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO pending_registrations (user_id, username, name, target_time, role) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, name, target_time, role),
            )
            conn.commit()
            logger.info(
                f"Пользователь user_id={user_id} добавлен в pending_registrations"
            )
            return True
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при добавлении в pending_registrations user_id={user_id}: {e}"
        )
        return False


def get_pending_registrations():
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, username, name, target_time, role FROM pending_registrations"
            )
            pending = cursor.fetchall()
            return pending
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении pending_registrations: {e}")
        return []


def delete_pending_registration(user_id: int) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pending_registrations WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            logger.info(
                f"Пользователь user_id={user_id} удален из pending_registrations"
            )
            return True
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при удалении user_id={user_id} из pending_registrations: {e}"
        )
        return False


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


def set_result(user_id: int, result: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET result = ? WHERE user_id = ?",
                (result, user_id),
            )
            success = cursor.rowcount > 0
            conn.commit()
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при записи результата для user_id={user_id}: {e}")
        return False


def delete_participant(user_id: int) -> bool:
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            # Проверяем наличие пользователя
            cursor.execute(
                "SELECT user_id FROM participants WHERE user_id = ?", (user_id,)
            )
            if not cursor.fetchone():
                logger.warning(
                    f"Пользователь user_id={user_id} не найден в participants"
                )
                return False
            # Выполняем удаление
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(
                    f"Пользователь user_id={user_id} успешно удалён из participants"
                )
                return True
            else:
                logger.error(
                    f"Не удалось удалить пользователя user_id={user_id}: rowcount=0"
                )
                return False
    except sqlite3.Error as e:
        logger.error(f"Ошибка SQLite при удалении пользователя user_id={user_id}: {e}")
        return False


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
                    "pending" if role == "runner" else "-",
                ),
            )
            conn.commit()
            logger.info(f"Участник добавлен: {name}, {role}, user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
        return False


# def get_setting(key: str):
#     try:
#         with sqlite3.connect(DB_PATH, timeout=10) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
#             result = cursor.fetchone()
#             return int(result[0]) if result else None
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при получении настройки {key}: {e}")
#         return None
def get_setting(key: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        if result:
            if key == "reg_end_date":
                return result[0]
            return int(result[0]) if result[0].isdigit() else result[0]
        return None
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения настройки {key}: {e}")
        return None
    finally:
        conn.close()


def set_setting(key: str, value):
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
            conn.commit()
            logger.info(f"Настройка {key} установлена в {value}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке настройки {key}: {e}")
        return False
