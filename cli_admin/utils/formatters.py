"""
Форматирование данных для отображения
"""

from datetime import datetime
from typing import Optional
import pytz


def format_date(date_str: str, format_out: str = "%d.%m.%Y") -> str:
    """
    Форматировать дату

    Args:
        date_str: Строка с датой
        format_out: Формат вывода

    Returns:
        Отформатированная дата
    """
    if not date_str:
        return "-"

    try:
        # Попробовать разные форматы
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime(format_out)
            except ValueError:
                continue

        return date_str  # Вернуть как есть если не удалось распарсить
    except Exception:
        return date_str


def format_datetime(dt_str: str, format_out: str = "%d.%m.%Y %H:%M") -> str:
    """
    Форматировать дату и время

    Args:
        dt_str: Строка с датой и временем
        format_out: Формат вывода

    Returns:
        Отформатированная дата и время
    """
    return format_date(dt_str, format_out)


def format_phone(phone: str) -> str:
    """
    Форматировать номер телефона

    Args:
        phone: Номер телефона

    Returns:
        Отформатированный номер
    """
    if not phone:
        return "-"

    # Убрать все кроме цифр и +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

    if not cleaned:
        return "-"

    # Форматировать российский номер
    if cleaned.startswith('+7') or cleaned.startswith('7'):
        if cleaned.startswith('+7'):
            cleaned = cleaned[2:]
        elif cleaned.startswith('7'):
            cleaned = cleaned[1:]

        if len(cleaned) == 10:
            return f"+7 ({cleaned[0:3]}) {cleaned[3:6]}-{cleaned[6:8]}-{cleaned[8:10]}"

    return phone


def format_payment_status(status: str) -> str:
    """
    Форматировать статус оплаты

    Args:
        status: Статус оплаты

    Returns:
        Отформатированный статус с эмодзи
    """
    status_map = {
        "paid": "✅ Оплачено",
        "pending": "⏳ Ожидает",
        "unpaid": "❌ Не оплачено"
    }
    return status_map.get(status, status)


def format_role(role: str) -> str:
    """
    Форматировать роль

    Args:
        role: Роль участника

    Returns:
        Отформатированная роль с эмодзи
    """
    role_map = {
        "runner": "🏃 Бегун",
        "volunteer": "🤝 Волонтер"
    }
    return role_map.get(role, role)


def format_gender(gender: str) -> str:
    """
    Форматировать пол

    Args:
        gender: Пол

    Returns:
        Отформатированный пол
    """
    if not gender:
        return "-"

    gender_lower = gender.lower()

    if gender_lower in ["m", "male", "м", "мужской"]:
        return "👨 Мужской"
    elif gender_lower in ["f", "female", "ж", "женский"]:
        return "👩 Женский"

    return gender


def format_bool(value: any) -> str:
    """
    Форматировать булево значение

    Args:
        value: Булево или int значение

    Returns:
        Отформатированное значение
    """
    if isinstance(value, bool):
        return "✅ Да" if value else "❌ Нет"
    elif isinstance(value, int):
        return "✅ Да" if value == 1 else "❌ Нет"
    elif isinstance(value, str):
        if value.lower() in ["true", "yes", "да", "1"]:
            return "✅ Да"
        else:
            return "❌ Нет"

    return str(value)


def format_time(seconds: Optional[float]) -> str:
    """
    Форматировать время в секундах в MM:SS

    Args:
        seconds: Время в секундах

    Returns:
        Отформатированное время
    """
    if seconds is None:
        return "-"

    try:
        seconds = float(seconds)
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return str(seconds)


def format_result(result: str) -> str:
    """
    Форматировать результат забега

    Args:
        result: Результат

    Returns:
        Отформатированный результат
    """
    if not result or result == "-":
        return "-"

    # Попробовать распарсить как секунды
    try:
        seconds = float(result)
        return format_time(seconds)
    except ValueError:
        return result


def truncate_string(s: str, length: int = 50, suffix: str = "...") -> str:
    """
    Обрезать строку до заданной длины

    Args:
        s: Строка
        length: Максимальная длина
        suffix: Суффикс для обрезанной строки

    Returns:
        Обрезанная строка
    """
    if not s:
        return ""

    if len(s) <= length:
        return s

    return s[:length - len(suffix)] + suffix


def format_moscow_time(dt_str: str) -> str:
    """
    Форматировать время в московский часовой пояс

    Args:
        dt_str: Строка с датой/временем

    Returns:
        Отформатированное время с MSK
    """
    if not dt_str:
        return "-"

    try:
        # Попробовать распарсить
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(dt_str, fmt)
                # Предполагаем что время уже в MSK
                moscow_tz = pytz.timezone('Europe/Moscow')
                dt_msk = moscow_tz.localize(dt)
                return dt_msk.strftime("%d.%m.%Y %H:%M MSK")
            except ValueError:
                continue

        return dt_str
    except Exception:
        return dt_str


def format_file_size(size_bytes: int) -> str:
    """
    Форматировать размер файла

    Args:
        size_bytes: Размер в байтах

    Returns:
        Отформатированный размер
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
