import json
import sqlite3
import logging
import os
from datetime import datetime

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
                    bib_number TEXT,
                    result TEXT,
                    gender TEXT,
                    category TEXT DEFAULT NULL,
                    cluster TEXT DEFAULT NULL
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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS waitlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    name TEXT NOT NULL,
                    target_time TEXT,
                    role TEXT NOT NULL,
                    gender TEXT,
                    join_date TEXT NOT NULL,
                    status TEXT DEFAULT 'waiting',
                    notified_date TEXT,
                    expire_date TEXT,
                    FOREIGN KEY (user_id) REFERENCES participants (user_id)
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
            
            # Check and add category and cluster columns to participants table
            cursor.execute("PRAGMA table_info(participants)")
            participants_columns = [info[1] for info in cursor.fetchall()]
            if "category" not in participants_columns:
                cursor.execute("ALTER TABLE participants ADD COLUMN category TEXT DEFAULT NULL")
                logger.info("Добавлен столбец category в таблицу participants")
            if "cluster" not in participants_columns:
                cursor.execute("ALTER TABLE participants ADD COLUMN cluster TEXT DEFAULT NULL")
                logger.info("Добавлен столбец cluster в таблицу participants")
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
            
            # Create bot_users table for tracking all users who interacted with bot
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    first_interaction TEXT NOT NULL,
                    last_interaction TEXT NOT NULL
                )
                """
            )
            
            conn.commit()
            logger.info("База данных инициализирована")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise
    
    # Run migration for bib_number to TEXT
    migrate_bib_numbers_to_text()


def migrate_bib_numbers_to_text():
    """
    Migrate bib_number from INTEGER to TEXT to preserve leading zeros.
    This function should be called once after the schema change.
    """
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Check if bib_number column type is already TEXT
            cursor.execute("PRAGMA table_info(participants)")
            columns = cursor.fetchall()
            bib_column = next((col for col in columns if col[1] == 'bib_number'), None)
            
            if bib_column and bib_column[2] == 'INTEGER':
                logger.info("Migrating bib_number from INTEGER to TEXT...")
                
                # Create temporary table with TEXT bib_number
                cursor.execute("""
                    CREATE TABLE participants_temp (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        name TEXT NOT NULL,
                        target_time TEXT,
                        role TEXT NOT NULL,
                        reg_date TEXT NOT NULL,
                        payment_status TEXT DEFAULT 'pending',
                        bib_number TEXT,
                        result TEXT,
                        gender TEXT,
                        category TEXT DEFAULT NULL,
                        cluster TEXT DEFAULT NULL
                    )
                """)
                
                # Copy data, converting bib_number to TEXT with leading zeros preserved
                cursor.execute("""
                    INSERT INTO participants_temp 
                    SELECT user_id, username, name, target_time, role, reg_date, 
                           payment_status, 
                           CASE 
                               WHEN bib_number IS NULL THEN NULL
                               ELSE printf('%03d', bib_number)  -- Format with leading zeros
                           END,
                           result, gender, category, cluster
                    FROM participants
                """)
                
                # Drop old table and rename new one
                cursor.execute("DROP TABLE participants")
                cursor.execute("ALTER TABLE participants_temp RENAME TO participants")
                
                conn.commit()
                logger.info("Successfully migrated bib_number to TEXT with leading zeros preserved")
            else:
                logger.info("bib_number is already TEXT type, no migration needed")
                
    except sqlite3.Error as e:
        logger.error(f"Error during bib_number migration: {e}")
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


def set_bib_number(user_id: int, bib_number: str):
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
    user_id: int, username: str, name: str, target_time: str, role: str, gender: str
):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status, gender)
                VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?)
                """,
                (
                    user_id,
                    username,
                    name,
                    target_time,
                    role,
                    "pending" if role == "runner" else "-",
                    gender,
                ),
            )
            conn.commit()
            logger.info(f"Участник добавлен: {name}, {role}, user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении участника user_id={user_id}: {e}")
        return False


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


def save_race_to_db(race_date: str) -> bool:
    try:
        date_obj = datetime.strptime(race_date, "%d.%m.%Y")
        table_name = f"race_{date_obj.strftime('%d_%m_%Y')}"
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM participants")
        if cursor.fetchone()[0] == 0:
            conn.close()
            return False
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        table_exists = cursor.fetchone() is not None
        if table_exists:
            cursor.execute(f"DROP TABLE {table_name}")
            logger.info(f"Существующая таблица {table_name} удалена перед обновлением")
        cursor.execute(
            f"""
            CREATE TABLE {table_name} (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                target_time TEXT,
                role TEXT,
                registration_date TEXT,
                payment_status TEXT,
                bib_number TEXT,
                result TEXT,
                gender TEXT
            )
        """
        )
        cursor.execute(f"INSERT INTO {table_name} SELECT * FROM participants")
        conn.commit()
        conn.close()
        logger.info(
            f"Данные гонки {'обновлены' if table_exists else 'сохранены'} в таблице {table_name}"
        )
        return True
    except ValueError:
        logger.error(f"Некорректный формат даты: {race_date}")
        return False


def clear_participants() -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM participants")
    success = cursor.rowcount >= 0
    conn.commit()
    conn.close()
    logger.info("Таблица participants очищена")
    return success


def get_past_races():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'race_%'"
    )
    races = [row[0].replace("race_", "").replace("_", ".") for row in cursor.fetchall()]
    conn.close()
    return sorted(races, key=lambda x: datetime.strptime(x, "%d.%m.%Y"), reverse=True)


def get_race_data(race_date: str):
    try:
        date_obj = datetime.strptime(race_date, "%d.%m.%Y")
        table_name = f"race_{date_obj.strftime('%d_%m_%Y')}"
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT user_id, username, name, target_time, role, registration_date, payment_status, bib_number, result, gender, category, cluster FROM {table_name}"
        )
        data = cursor.fetchall()
        conn.close()
        return data
    except ValueError:
        logger.error(f"Некорректный формат даты: {race_date}")


def update_participant_field(user_id: int, field: str, value: str) -> bool:
    """Update a single field for a participant"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE participants SET {field} = ? WHERE user_id = ?",
                (value, user_id),
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Обновлено поле {field} для user_id={user_id}: {value}")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обновлении поля {field} для user_id={user_id}: {e}")
        return False


def create_edit_request(user_id: int, field: str, old_value: str, new_value: str) -> bool:
    """Create an edit request that requires admin approval"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Create edit_requests table if it doesn't exist
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS edit_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    field TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT NOT NULL,
                    request_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (user_id) REFERENCES participants (user_id)
                )
                """
            )
            
            cursor.execute(
                """
                INSERT INTO edit_requests (user_id, field, old_value, new_value, request_date)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (user_id, field, old_value, new_value),
            )
            conn.commit()
            logger.info(f"Создан запрос на изменение {field} для user_id={user_id}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при создании запроса на изменение для user_id={user_id}: {e}")
        return False


def get_pending_edit_requests():
    """Get all pending edit requests"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT er.id, er.user_id, p.name, p.username, er.field, 
                       er.old_value, er.new_value, er.request_date
                FROM edit_requests er
                JOIN participants p ON er.user_id = p.user_id
                WHERE er.status = 'pending'
                ORDER BY er.request_date ASC
                """
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении запросов на изменение: {e}")
        return []


def approve_edit_request(request_id: int) -> bool:
    """Approve an edit request and apply the changes"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Get request details
            cursor.execute(
                "SELECT user_id, field, new_value FROM edit_requests WHERE id = ? AND status = 'pending'",
                (request_id,)
            )
            request_data = cursor.fetchone()
            
            if not request_data:
                logger.warning(f"Запрос на изменение id={request_id} не найден или уже обработан")
                return False
                
            user_id, field, new_value = request_data
            
            # Apply the change
            cursor.execute(
                f"UPDATE participants SET {field} = ? WHERE user_id = ?",
                (new_value, user_id),
            )
            
            # Mark request as approved
            cursor.execute(
                "UPDATE edit_requests SET status = 'approved' WHERE id = ?",
                (request_id,)
            )
            
            conn.commit()
            logger.info(f"Запрос на изменение id={request_id} одобрен и применён")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при одобрении запроса на изменение id={request_id}: {e}")
        return False


def reject_edit_request(request_id: int) -> bool:
    """Reject an edit request"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE edit_requests SET status = 'rejected' WHERE id = ?",
                (request_id,)
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Запрос на изменение id={request_id} отклонён")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при отклонении запроса на изменение id={request_id}: {e}")
        return False


def add_to_waitlist(user_id: int, username: str, name: str, target_time: str, role: str, gender: str) -> bool:
    """Add user to waitlist when regular slots are full"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO waitlist (user_id, username, name, target_time, role, gender, join_date)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (user_id, username, name, target_time, role, gender),
            )
            conn.commit()
            logger.info(f"Пользователь {name} (ID: {user_id}) добавлен в очередь ожидания для роли {role}")
            return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении user_id={user_id} в очередь ожидания: {e}")
        return False


def get_waitlist_by_role(role: str = None):
    """Get waitlist participants, optionally filtered by role"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if role:
                cursor.execute(
                    """
                    SELECT id, user_id, username, name, target_time, role, gender, join_date, status
                    FROM waitlist WHERE role = ? AND status = 'waiting'
                    ORDER BY join_date ASC
                    """,
                    (role,)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, user_id, username, name, target_time, role, gender, join_date, status
                    FROM waitlist WHERE status = 'waiting'
                    ORDER BY role = 'runner' DESC, join_date ASC
                    """
                )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении очереди ожидания: {e}")
        return []


def get_waitlist_position(user_id: int) -> tuple:
    """Get user's position in waitlist and total waiting for their role"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # First get user's role
            cursor.execute(
                "SELECT role FROM waitlist WHERE user_id = ? AND status = 'waiting'",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                return None, None
            
            role = user_data[0]
            
            # Get position in queue for that role
            cursor.execute(
                """
                SELECT COUNT(*) FROM waitlist 
                WHERE role = ? AND status = 'waiting' AND join_date < (
                    SELECT join_date FROM waitlist WHERE user_id = ? AND status = 'waiting'
                )
                """,
                (role, user_id)
            )
            position = cursor.fetchone()[0] + 1  # +1 because COUNT starts from 0
            
            # Get total waiting for that role
            cursor.execute(
                "SELECT COUNT(*) FROM waitlist WHERE role = ? AND status = 'waiting'",
                (role,)
            )
            total_waiting = cursor.fetchone()[0]
            
            return position, total_waiting
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении позиции в очереди для user_id={user_id}: {e}")
        return None, None


def remove_from_waitlist(user_id: int) -> bool:
    """Remove user from waitlist"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM waitlist WHERE user_id = ?", (user_id,)
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Пользователь user_id={user_id} удалён из очереди ожидания")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при удалении user_id={user_id} из очереди ожидания: {e}")
        return False


def notify_waitlist_users(role: str, available_slots: int) -> list:
    """Notify waitlist users about available slots, return list of notified users"""
    from datetime import datetime, timedelta
    
    notified_users = []
    
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Get users from waitlist for this role, ordered by join date
            cursor.execute(
                """
                SELECT user_id, username, name, target_time, role, gender
                FROM waitlist WHERE role = ? AND status = 'waiting'
                ORDER BY join_date ASC
                LIMIT ?
                """,
                (role, available_slots)
            )
            waitlist_users = cursor.fetchall()
            
            # Set expiration time (24 hours from now)
            expire_time = datetime.now() + timedelta(hours=24)
            expire_str = expire_time.strftime("%Y-%m-%d %H:%M:%S")
            
            for user_data in waitlist_users:
                user_id, username, name, target_time, role, gender = user_data
                
                # Mark user as notified with expiration time
                cursor.execute(
                    """
                    UPDATE waitlist 
                    SET status = 'notified', notified_date = datetime('now'), expire_date = ?
                    WHERE user_id = ? AND role = ?
                    """,
                    (expire_str, user_id, role)
                )
                notified_users.append(user_data)
                logger.info(f"Пользователь {name} (ID: {user_id}) уведомлён о доступном месте")
            
            conn.commit()
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при уведомлении очереди ожидания для роли {role}: {e}")
    
    return notified_users


def confirm_waitlist_participation(user_id: int) -> bool:
    """Confirm participation from waitlist and move to participants"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Get user data from waitlist
            cursor.execute(
                """
                SELECT username, name, target_time, role, gender
                FROM waitlist WHERE user_id = ? AND status = 'notified'
                """,
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                logger.warning(f"Пользователь {user_id} не найден в очереди с статусом 'notified'")
                return False
            
            username, name, target_time, role, gender = user_data
            
            # Add to participants
            success = add_participant(user_id, username, name, target_time, role, gender)
            
            if success:
                # Remove from pending_registrations (user becomes participant)
                cursor.execute("DELETE FROM pending_registrations WHERE user_id = ?", (user_id,))
                
                # Remove from waitlist (user becomes participant)
                cursor.execute("DELETE FROM waitlist WHERE user_id = ?", (user_id,))
                
                conn.commit()
                logger.info(f"Пользователь {name} (ID: {user_id}) подтвердил участие из очереди ожидания")
                logger.info(f"Пользователь {user_id} удален из pending_registrations и waitlist")
                return True
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при подтверждении участия из очереди для user_id={user_id}: {e}")
    
    return False


def decline_waitlist_participation(user_id: int) -> bool:
    """Decline participation from waitlist"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Get user data before removing from waitlist
            cursor.execute(
                "SELECT username FROM waitlist WHERE user_id = ? AND status = 'notified'",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if user_data:
                username = user_data[0]
                
                # Remove from waitlist (user declined)
                cursor.execute("DELETE FROM waitlist WHERE user_id = ?", (user_id,))
                
                # Ensure user is in pending_registrations (so they can try again via /start)
                cursor.execute(
                    "INSERT OR IGNORE INTO pending_registrations (user_id, username) VALUES (?, ?)",
                    (user_id, username)
                )
                
                success = True
                logger.info(f"Пользователь user_id={user_id} отклонил участие из очереди ожидания")
                logger.info(f"Пользователь {user_id} удален из waitlist и добавлен в pending")
            else:
                success = False
            
            conn.commit()
            
            return success
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при отклонении участия из очереди для user_id={user_id}: {e}")
        return False


def get_expired_waitlist_notifications() -> list:
    """Get waitlist notifications that have expired"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, username, name, role
                FROM waitlist 
                WHERE status = 'notified' AND expire_date < datetime('now')
                """
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении истекших уведомлений: {e}")
        return []


def expire_waitlist_notifications() -> list:
    """Mark expired notifications as waiting again"""
    expired_users = []
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Get expired users first
            expired_users = get_expired_waitlist_notifications()
            
            # Mark them as waiting again
            cursor.execute(
                """
                UPDATE waitlist 
                SET status = 'waiting', notified_date = NULL, expire_date = NULL
                WHERE status = 'notified' AND expire_date < datetime('now')
                """
            )
            
            conn.commit()
            logger.info(f"Истекло {len(expired_users)} уведомлений очереди ожидания")
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при обработке истекших уведомлений: {e}")
    
    return expired_users


def is_user_in_waitlist(user_id: int) -> bool:
    """Check if user is currently in waitlist"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM waitlist WHERE user_id = ?",
                (user_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0
    except sqlite3.Error as e:
        logger.error(f"Ошибка при проверке пользователя в waitlist: {e}")
        return False


def get_waitlist_by_user_id(user_id: int) -> tuple:
    """Get waitlist entry for specific user"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM waitlist WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении записи waitlist для пользователя {user_id}: {e}")
        return None


# ============================================================================
# RACE ARCHIVE FUNCTIONS
# ============================================================================

def archive_race_data(race_date: str) -> bool:
    """Archive current race data to race_YYYY_MM_DD table and collect all users to bot_users"""
    try:
        # Format table name with date
        table_name = f"race_{race_date.replace('-', '_').replace('.', '_').replace('/', '_')}"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            
            # Create archive table for participants (only registered participants)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    name TEXT NOT NULL,
                    target_time TEXT,
                    role TEXT NOT NULL,
                    reg_date TEXT NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    bib_number TEXT,
                    result TEXT,
                    gender TEXT,
                    category TEXT,
                    cluster TEXT,
                    archive_date TEXT NOT NULL
                )
            """)
            
            # Copy participants data to race archive
            cursor.execute(f"""
                INSERT INTO {table_name} 
                (user_id, username, name, target_time, role, reg_date, payment_status, bib_number, result, gender, category, cluster, archive_date)
                SELECT user_id, username, name, target_time, role, reg_date, payment_status, bib_number, result, gender, category, cluster, ?
                FROM participants
            """, (current_time,))
            
            participants_count = cursor.rowcount
            
            # Collect ALL users from all tables into bot_users
            # 1. From participants
            cursor.execute("""
                INSERT OR REPLACE INTO bot_users (user_id, username, first_name, last_name, first_interaction, last_interaction)
                SELECT user_id, username, name, NULL, reg_date, ?
                FROM participants
            """, (current_time,))
            
            # 2. From pending_registrations
            cursor.execute("""
                INSERT OR REPLACE INTO bot_users (user_id, username, first_name, last_name, first_interaction, last_interaction)
                SELECT user_id, username, name, NULL, ?, ?
                FROM pending_registrations
                WHERE user_id NOT IN (SELECT user_id FROM bot_users)
            """, (current_time, current_time))
            
            # 3. From waitlist
            cursor.execute("""
                INSERT OR REPLACE INTO bot_users (user_id, username, first_name, last_name, first_interaction, last_interaction)
                SELECT user_id, username, name, NULL, join_date, ?
                FROM waitlist
                WHERE user_id NOT IN (SELECT user_id FROM bot_users)
            """, (current_time,))
            
            # Get total users collected
            cursor.execute("SELECT COUNT(*) FROM bot_users")
            total_users = cursor.fetchone()[0]
            
            # Clear main tables (bot_users stays)
            cursor.execute("DELETE FROM participants")
            cursor.execute("DELETE FROM pending_registrations") 
            cursor.execute("DELETE FROM waitlist")
            cursor.execute("DELETE FROM edit_requests")
            
            # Reset auto-increment counters
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('participants', 'pending_registrations', 'waitlist', 'edit_requests')")
            
            conn.commit()
            logger.info(f"Архивированы данные гонки в таблицу {table_name} (участники: {participants_count}). Всего пользователей в bot_users: {total_users}")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при архивировании данных гонки: {e}")
        return False


def get_user_race_history(user_id: int) -> list:
    """Get user's participation history from all race archive tables"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get list of all race archive tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'race_%'
                ORDER BY name DESC
            """)
            
            race_tables = cursor.fetchall()
            user_history = []
            
            for (table_name,) in race_tables:
                try:
                    # First try with archive_date (new format)
                    cursor.execute(f"""
                        SELECT name, target_time, result, bib_number, payment_status, archive_date, reg_date
                        FROM {table_name} 
                        WHERE user_id = ?
                    """, (user_id,))
                    
                    race_data = cursor.fetchone()
                    if race_data:
                        name, target_time, result, bib_number, payment_status, archive_date, reg_date = race_data
                        race_info = {
                            'table_name': table_name,
                            'race_date': table_name.replace('race_', '').replace('_', '-'),
                            'name': name,
                            'target_time': target_time,
                            'result': result,
                            'bib_number': bib_number,
                            'payment_status': payment_status,
                            'archive_date': archive_date,
                            'reg_date': reg_date
                        }
                        user_history.append(race_info)
                        
                except sqlite3.OperationalError:
                    # Fallback for old tables - try minimal required columns
                    try:
                        cursor.execute(f"""
                            SELECT name, target_time, result
                            FROM {table_name} 
                            WHERE user_id = ?
                        """, (user_id,))
                        
                        race_data = cursor.fetchone()
                        if race_data:
                            name, target_time, result = race_data
                            race_info = {
                                'table_name': table_name,
                                'race_date': table_name.replace('race_', '').replace('_', '-'),
                                'name': name,
                                'target_time': target_time,
                                'result': result,
                                'bib_number': None,
                                'payment_status': None,
                                'archive_date': None,
                                'reg_date': None
                            }
                            user_history.append(race_info)
                    except sqlite3.OperationalError as e:
                        logger.warning(f"Не удалось прочитать данные из таблицы {table_name}: {e}")
                        continue
            
            return user_history
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении истории участия пользователя {user_id}: {e}")
        return []


def get_latest_user_result(user_id: int) -> dict:
    """Get user's latest race result from archive tables"""
    history = get_user_race_history(user_id)
    if history:
        return history[0]  # Latest race (sorted DESC)
    return None


def list_race_archives() -> list:
    """List all race archive tables"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'race_%'
                ORDER BY name DESC
            """)
            
            tables = cursor.fetchall()
            return [table[0] for table in tables]
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении списка архивных таблиц: {e}")
        return []


def is_current_event_active() -> bool:
    """Check if current event is active based on registration end date"""
    try:
        reg_end_date = get_setting("reg_end_date")
        if not reg_end_date:
            return False
            
        from datetime import datetime
        from pytz import timezone
        
        end_date = datetime.strptime(reg_end_date, "%H:%M %d.%m.%Y")
        moscow_tz = timezone("Europe/Moscow")
        end_date = moscow_tz.localize(end_date)
        current_time = datetime.now(moscow_tz)
        
        return current_time <= end_date
        
    except (ValueError, Exception) as e:
        logger.error(f"Ошибка при проверке активности события: {e}")
        return False


# ============================================================================
# BOT USERS MANAGEMENT FUNCTIONS
# ============================================================================

def add_or_update_bot_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
    """Add or update user in bot_users table"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if user exists
            cursor.execute("SELECT user_id FROM bot_users WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing user
                cursor.execute("""
                    UPDATE bot_users 
                    SET username = ?, first_name = ?, last_name = ?, last_interaction = ?
                    WHERE user_id = ?
                """, (username, first_name, last_name, current_time, user_id))
            else:
                # Add new user
                cursor.execute("""
                    INSERT INTO bot_users (user_id, username, first_name, last_name, first_interaction, last_interaction)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, current_time, current_time))
            
            conn.commit()
            return True
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при добавлении/обновлении пользователя бота {user_id}: {e}")
        return False


def get_all_bot_users() -> list:
    """Get all users who interacted with bot"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, first_interaction, last_interaction
                FROM bot_users
                ORDER BY last_interaction DESC
            """)
            return cursor.fetchall()
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении списка пользователей бота: {e}")
        return []


def get_historical_participants() -> list:
    """Get all users who participated in any archived race (historical participants)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get list of all race archive tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'race_%'
                ORDER BY name DESC
            """)
            
            race_tables = cursor.fetchall()
            historical_users = set()
            
            for (table_name,) in race_tables:
                try:
                    cursor.execute(f"""
                        SELECT user_id FROM {table_name}
                    """)
                    
                    results = cursor.fetchall()
                    for (user_id,) in results:
                        historical_users.add(user_id)
                        
                except sqlite3.OperationalError as e:
                    logger.error(f"Ошибка при чтении таблицы {table_name}: {e}")
                    continue
            
            return list(historical_users)
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении исторических участников: {e}")
        return []


# ============================================================================
# CATEGORIES AND CLUSTERS MANAGEMENT FUNCTIONS
# ============================================================================

def set_participant_category(user_id: int, category: str) -> bool:
    """Set category for participant"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET category = ? WHERE user_id = ?",
                (category, user_id),
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Установлена категория {category} для user_id={user_id}")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке категории для user_id={user_id}: {e}")
        return False


def set_participant_cluster(user_id: int, cluster: str) -> bool:
    """Set cluster for participant"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE participants SET cluster = ? WHERE user_id = ?",
                (cluster, user_id),
            )
            success = cursor.rowcount > 0
            conn.commit()
            if success:
                logger.info(f"Установлен кластер {cluster} для user_id={user_id}")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке кластера для user_id={user_id}: {e}")
        return False


def get_participants_by_role(role: str = None) -> list:
    """Get all participants by role for cluster assignment"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if role:
                cursor.execute(
                    "SELECT user_id, username, name, target_time, gender, category, cluster FROM participants WHERE role = ? ORDER BY name ASC",
                    (role,)
                )
            else:
                cursor.execute(
                    "SELECT user_id, username, name, target_time, gender, category, cluster FROM participants ORDER BY role = 'runner' DESC, name ASC"
                )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении участников по роли {role}: {e}")
        return []


def get_participants_with_categories() -> list:
    """Get all participants with their categories and clusters for final display"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, username, name, target_time, gender, category, cluster, role, result, bib_number 
                FROM participants 
                ORDER BY role = 'runner' DESC, 
                         CASE category 
                             WHEN 'Элита' THEN 1 
                             WHEN 'Классика' THEN 2 
                             WHEN 'Женский' THEN 3 
                             WHEN 'Команда' THEN 4 
                             ELSE 5 
                         END ASC,
                         CASE cluster 
                             WHEN 'A' THEN 1 
                             WHEN 'B' THEN 2 
                             WHEN 'C' THEN 3 
                             WHEN 'D' THEN 4 
                             WHEN 'E' THEN 5 
                             ELSE 6 
                         END ASC,
                         name ASC
                """
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении участников с категориями: {e}")
        return []


def clear_all_categories() -> bool:
    """Clear all categories for all participants"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE participants SET category = NULL")
            success = cursor.rowcount > 0
            conn.commit()
            logger.info("Очищены все категории участников")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при очистке категорий: {e}")
        return False


def clear_all_clusters() -> bool:
    """Clear all clusters for all participants"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE participants SET cluster = NULL")
            success = cursor.rowcount > 0
            conn.commit()
            logger.info("Очищены все кластеры участников")
            return success
    except sqlite3.Error as e:
        logger.error(f"Ошибка при очистке кластеров: {e}")
        return False
