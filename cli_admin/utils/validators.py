"""
Валидаторы для ввода данных
"""

import re
from datetime import datetime
from typing import Optional


def validate_telegram_id(user_id: str) -> tuple[bool, Optional[int], Optional[str]]:
    """
    Валидация Telegram ID

    Args:
        user_id: Строка с ID

    Returns:
        (is_valid, parsed_id, error_message)
    """
    try:
        parsed_id = int(user_id)
        if parsed_id <= 0:
            return False, None, "Telegram ID должен быть положительным числом"
        return True, parsed_id, None
    except ValueError:
        return False, None, "Telegram ID должен быть числом"


def validate_phone(phone: str) -> tuple[bool, Optional[str]]:
    """
    Валидация номера телефона

    Args:
        phone: Строка с номером

    Returns:
        (is_valid, error_message)
    """
    # Убираем все пробелы и дефисы
    cleaned = phone.replace(" ", "").replace("-", "")

    # Проверяем формат
    pattern = r'^\+?\d{10,15}$'
    if not re.match(pattern, cleaned):
        return False, "Неверный формат телефона (должно быть 10-15 цифр)"

    return True, None


def validate_date(date_str: str, format_str: str = "%Y-%m-%d") -> tuple[bool, Optional[datetime], Optional[str]]:
    """
    Валидация даты

    Args:
        date_str: Строка с датой
        format_str: Формат даты

    Returns:
        (is_valid, parsed_date, error_message)
    """
    try:
        parsed_date = datetime.strptime(date_str, format_str)
        return True, parsed_date, None
    except ValueError:
        return False, None, f"Неверный формат даты (ожидается {format_str})"


def validate_time(time_str: str) -> tuple[bool, Optional[str]]:
    """
    Валидация целевого времени (формат MM:SS или M:SS)

    Args:
        time_str: Строка со временем

    Returns:
        (is_valid, error_message)
    """
    pattern = r'^\d{1,2}:\d{2}$'
    if not re.match(pattern, time_str):
        return False, "Неверный формат времени (должно быть MM:SS)"

    parts = time_str.split(":")
    minutes = int(parts[0])
    seconds = int(parts[1])

    if seconds >= 60:
        return False, "Секунды должны быть меньше 60"

    if minutes > 30:
        return False, "Время выглядит нереалистично (более 30 минут)"

    return True, None


def validate_bib_number(bib: str) -> tuple[bool, Optional[str]]:
    """
    Валидация стартового номера

    Args:
        bib: Строка с номером

    Returns:
        (is_valid, error_message)
    """
    if not bib:
        return False, "Номер не может быть пустым"

    if len(bib) > 10:
        return False, "Номер слишком длинный"

    return True, None


def validate_positive_int(value: str, field_name: str = "Значение") -> tuple[bool, Optional[int], Optional[str]]:
    """
    Валидация положительного целого числа

    Args:
        value: Строка со значением
        field_name: Название поля для сообщения об ошибке

    Returns:
        (is_valid, parsed_value, error_message)
    """
    try:
        parsed_value = int(value)
        if parsed_value <= 0:
            return False, None, f"{field_name} должно быть положительным числом"
        return True, parsed_value, None
    except ValueError:
        return False, None, f"{field_name} должно быть числом"


def validate_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Валидация имени

    Args:
        name: Строка с именем

    Returns:
        (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Имя не может быть пустым"

    if len(name) < 2:
        return False, "Имя слишком короткое"

    if len(name) > 200:
        return False, "Имя слишком длинное"

    return True, None


def validate_role(role: str) -> tuple[bool, Optional[str]]:
    """
    Валидация роли участника

    Args:
        role: Строка с ролью

    Returns:
        (is_valid, error_message)
    """
    valid_roles = ["runner", "volunteer"]

    if role not in valid_roles:
        return False, f"Роль должна быть одной из: {', '.join(valid_roles)}"

    return True, None


def validate_payment_status(status: str) -> tuple[bool, Optional[str]]:
    """
    Валидация статуса оплаты

    Args:
        status: Строка со статусом

    Returns:
        (is_valid, error_message)
    """
    valid_statuses = ["paid", "pending", "unpaid"]

    if status not in valid_statuses:
        return False, f"Статус должен быть одним из: {', '.join(valid_statuses)}"

    return True, None


def validate_gender(gender: str) -> tuple[bool, Optional[str]]:
    """
    Валидация пола

    Args:
        gender: Строка с полом

    Returns:
        (is_valid, error_message)
    """
    valid_genders = ["M", "F", "male", "female", "м", "ж"]

    if gender.lower() not in [g.lower() for g in valid_genders]:
        return False, "Пол должен быть M или F"

    return True, None
