import datetime
import sqlite3
def init_db():
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS participants (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT,
        target_time TEXT,
        role TEXT,
        reg_date TEXT,
        payment_status TEXT
    )''')
    conn.commit()
    conn.close()
def add_participant(user_id: int, username: str, name: str, target_time: str, role: str):
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO participants (user_id, username, name, target_time, role, reg_date, payment_status) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (user_id, username, name, target_time, role, datetime.datetime.now().isoformat(), 'pending'))
    conn.commit()
    conn.close()
    return True
def get_all_participants():
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants')
    participants = cursor.fetchall()
    conn.close()
    return participants
def get_participant_count():
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM participants')
    count = cursor.fetchone()[0]
    conn.close()
    return count
def get_participant_count_by_role(role: str):
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM participants WHERE role = ?', (role,))
    count = cursor.fetchone()[0]
    conn.close()
    return count
def update_payment_status(user_id: int, status: str):
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE participants SET payment_status = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()
def delete_participant(user_id: int):
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM participants WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
def get_participant_by_user_id(user_id: int):
    conn = sqlite3.connect('race_participants.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, name, target_time, role, reg_date, payment_status FROM participants WHERE user_id = ?', (user_id,))
    participant = cursor.fetchone()
    conn.close()
    return participant