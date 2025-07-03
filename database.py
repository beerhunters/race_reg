# import datetime
# import sqlite3
# import logging
# import json
# import os
#
# logger = logging.getLogger(__name__)
#
# DB_PATH = "/app/data/race_participants.db"
#
# # Load config
# try:
#     with open("config.json", "r", encoding="utf-8") as f:
#         config = json.load(f)
#     logger.info("Файл config.json успешно загружен")
# except FileNotFoundError:
#     logger.error("Файл config.json не найден")
#     raise
# except json.JSONDecodeError as e:
#     logger.error(f"Ошибка при разборе config.json: {e}")
#     raise
#
# log_level = {
#     "DEBUG": logging.DEBUG,
#     "INFO": logging.INFO,
#     "WARNING": logging.WARNING,
#     "ERROR": logging.ERROR,
#     "CRITICAL": logging.CRITICAL,
# }
# if config.get("log_level") not in log_level:
#     logger.error(
#         f"Недопустимое значение log_level: {config.get('log_level')}. Используется ERROR."
#     )
#     logging.getLogger().setLevel(logging.ERROR)
# else:
#     logging.getLogger().setLevel(log_level[config["log_level"]])
#     logger.info(f"Установлен уровень логирования: {config['log_level']} в database.py")
#
#
# def init_db():
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             # Create participants table
#             cursor.execute(
#                 """
#                 CREATE TABLE IF NOT EXISTS participants (
#                     user_id INTEGER PRIMARY KEY,
#                     username TEXT,
#                     name TEXT,
#                     target_time TEXT,
#                     role TEXT,
#                     reg_date TEXT,
#                     payment_status TEXT
#                 )
#             """
#             )
#             # Create pending_registrations table
#             cursor.execute(
#                 """
#                 CREATE TABLE IF NOT EXISTS pending_registrations (
#                     user_id INTEGER PRIMARY KEY,
#                     timestamp TEXT
#                 )
#             """
#             )
#             conn.commit()
#             logger.info("База данных инициализирована")
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при инициализации базы данных: {e}")
#         raise
#
#
# def add_participant(
#     user_id: int, username: str, name: str, target_time: str, role: str
# ):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 """
#                 INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status)
#                 VALUES (?, ?, ?, ?, ?, ?, ?)
#             """,
#                 (
#                     user_id,
#                     username,
#                     name,
#                     target_time,
#                     role,
#                     datetime.datetime.now().isoformat(),
#                     "pending",
#                 ),
#             )
#             conn.commit()
#             logger.info(f"Участник user_id={user_id} успешно добавлен")
#             return True
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
#         return False
#
#
# def add_pending_registration(user_id: int):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 """
#                 INSERT OR IGNORE INTO pending_registrations (user_id, timestamp)
#                 VALUES (?, ?)
#             """,
#                 (user_id, datetime.datetime.now().isoformat()),
#             )
#             conn.commit()
#             logger.info(
#                 f"Пользователь user_id={user_id} добавлен в pending_registrations"
#             )
#             return True
#     except sqlite3.Error as e:
#         logger.error(
#             f"Ошибка при добавлении user_id={user_id} в pending_registrations: {e}"
#         )
#         return False
#
#
# def get_pending_registrations():
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT user_id FROM pending_registrations")
#             pending = cursor.fetchall()
#             logger.info(f"Получено {len(pending)} записей из pending_registrations")
#             return [row[0] for row in pending]
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при получении pending_registrations: {e}")
#         return []
#
#
# def delete_pending_registration(user_id: int):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 "DELETE FROM pending_registrations WHERE user_id = ?", (user_id,)
#             )
#             conn.commit()
#             logger.info(
#                 f"Пользователь user_id={user_id} удален из pending_registrations"
#             )
#             return True
#     except sqlite3.Error as e:
#         logger.error(
#             f"Ошибка при удалении user_id={user_id} из pending_registrations: {e}"
#         )
#         return False
#
#
# def get_all_participants():
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 "SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants"
#             )
#             participants = cursor.fetchall()
#             logger.info(f"Получено {len(participants)} участников")
#             return participants
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при получении списка участников: {e}")
#         return []
#
#
# def get_participant_count():
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT COUNT(*) FROM participants")
#             count = cursor.fetchone()[0]
#             logger.info(f"Общее количество участников: {count}")
#             return count
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при получении количества участников: {e}")
#         return 0
#
#
# def get_participant_count_by_role(role: str):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT COUNT(*) FROM participants WHERE role = ?", (role,))
#             count = cursor.fetchone()[0]
#             logger.info(f"Количество участников с ролью {role}: {count}")
#             return count
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при получении количества участников с ролью {role}: {e}")
#         return 0
#
#
# def update_payment_status(user_id: int, status: str):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute(
#                 "UPDATE participants SET payment_status = ? WHERE user_id = ?",
#                 (status, user_id),
#             )
#             conn.commit()
#             logger.info(f"Статус оплаты для user_id={user_id} обновлен на {status}")
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при обновлении статуса оплаты для user_id={user_id}: {e}")
#
#
# def delete_participant(user_id: int):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
#             conn.commit()
#             logger.info(f"Участник user_id={user_id} удален")
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при удалении участника user_id={user_id}: {e}")
#
#
# def get_participant_by_user_id(user_id: int):
#     try:
#         with sqlite3.connect(DB_PATH) as conn:
#             cursor = conn.cursor()
#             cursor.execute("SELECT * FROM participants WHERE user_id = ?", (user_id,))
#             participant = cursor.fetchone()
#             if participant:
#                 logger.info(f"Участник user_id={user_id} найден")
#             else:
#                 logger.info(f"Участник user_id={user_id} не найден")
#             return participant
#     except sqlite3.Error as e:
#         logger.error(f"Ошибка при поиске участника user_id={user_id}: {e}")
#         return None
import sqlite3
import logging
import json
import datetime

logger = logging.getLogger(__name__)

DB_PATH = "/app/data/race_participants.db"

# Load config
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
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Create participants table with bib_number
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
            # Create pending_registrations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    user_id INTEGER PRIMARY KEY,
                    timestamp TEXT
                )
            """
            )
            # Add bib_number column to existing participants table if not exists
            cursor.execute(
                """
                PRAGMA table_info(participants)
            """
            )
            columns = [info[1] for info in cursor.fetchall()]
            if "bib_number" not in columns:
                cursor.execute(
                    """
                    ALTER TABLE participants ADD COLUMN bib_number INTEGER
                """
                )
                logger.info("Столбец bib_number добавлен в таблицу participants")
            conn.commit()
            logger.info("База данных инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


def add_participant(
    user_id: int, username: str, name: str, target_time: str, role: str
):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status, bib_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
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
            logger.info(f"Участник user_id={user_id} успешно добавлен")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
        return False


def add_pending_registration(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO pending_registrations (user_id, timestamp)
                VALUES (?, ?)
            """,
                (user_id, datetime.datetime.now().isoformat()),
            )
            conn.commit()
            logger.info(
                f"Пользователь user_id={user_id} добавлен в pending_registrations"
            )
            return True
    except sqlite3.Error as e:
        logger.error(
            f"Ошибка при добавлении user_id={user_id} в pending_registrations: {e}"
        )
        return False


def get_pending_registrations():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM pending_registrations")
            pending = cursor.fetchall()
            logger.info(f"Получено {len(pending)} записей из pending_registrations")
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
                "SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number FROM participants"
            )
            participants = cursor.fetchall()
            logger.info(f"Получено {len(participants)} участников")
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
            logger.info(f"Общее количество участников: {count}")
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
            logger.info(f"Количество участников с ролью {role}: {count}")
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
            logger.info(f"Статус оплаты для user_id={user_id} обновлен на {status}")
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
            if cursor.rowcount == 0:
                logger.warning(
                    f"Участник user_id={user_id} не найден для присвоения номера"
                )
                return False
            conn.commit()
            logger.info(f"Беговой номер {bib_number} присвоен для user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при присвоении номера user_id={user_id}: {e}")
        return False


def delete_participant(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
            conn.commit()
            logger.info(f"Участник user_id={user_id} удален")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении участника user_id={user_id}: {e}")


def get_participant_by_user_id(user_id: int):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM participants WHERE user_id = ?", (user_id,))
            participant = cursor.fetchone()
            if participant:
                logger.info(f"Участник user_id={user_id} найден")
            else:
                logger.info(f"Участник user_id={user_id} не найден")
            return participant
    except sqlite3.Error as e:
        logger.error(f"Ошибка при поиске участника user_id={user_id}: {e}")
        return None
