"""
Data validation utilities for the beer mile registration bot.
Centralized validation functions with improved error handling.
"""

import re
from typing import Optional, Tuple


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def validate_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate participant name with comprehensive checks.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not name:
        return False, "Имя не может быть пустым."
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "Имя должно содержать минимум 2 символа."
    
    if len(name) > 50:
        return False, "Имя не может быть длиннее 50 символов."
    
    # Allow letters (including Cyrillic), numbers, spaces, hyphens, and apostrophes
    pattern = r'^[a-zA-Zа-яА-ЯёЁ0-9\s\-\'\.]+$'
    if not re.match(pattern, name):
        return False, "Имя может содержать только буквы, цифры, пробелы, дефисы и апострофы."
    
    # Check for excessive consecutive spaces or special characters
    if re.search(r'\s{3,}', name):
        return False, "Имя не может содержать более двух пробелов подряд."
    
    if re.search(r'[-\'\.]{2,}', name):
        return False, "Специальные символы не могут повторяться."
    
    # Name shouldn't start or end with special characters
    if re.match(r'^[-\'\.\s]', name) or re.search(r'[-\'\.\s]$', name):
        return False, "Имя не может начинаться или заканчиваться специальными символами или пробелами."
    
    return True, None


def validate_time_format(time_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate time format with support for MM:SS and H:MM:SS formats.
    Also validates logical constraints (e.g., minutes/seconds < 60).
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not time_str:
        return False, "Время не может быть пустым."
    
    time_str = time_str.strip()
    
    # Pattern for MM:SS (e.g., 7:30, 25:45)
    pattern_mmss = r'^([0-9]{1,2}):([0-5][0-9])$'
    # Pattern for H:MM:SS (e.g., 1:05:30)
    pattern_hmmss = r'^([0-9]{1,2}):([0-5][0-9]):([0-5][0-9])$'
    
    match_mmss = re.match(pattern_mmss, time_str)
    match_hmmss = re.match(pattern_hmmss, time_str)
    
    if match_mmss:
        minutes = int(match_mmss.group(1))
        seconds = int(match_mmss.group(2))
        
        # Reasonable constraints for beer mile (typically 4-20 minutes)
        if minutes > 59:
            return False, "Минуты не могут быть больше 59."
        
        if minutes < 1:
            return False, "Время должно быть больше 1 минуты."
        
        if minutes > 30:
            return False, "Время не может быть больше 30 минут для пивной мили."
        
        return True, None
    
    elif match_hmmss:
        hours = int(match_hmmss.group(1))
        minutes = int(match_hmmss.group(2))
        seconds = int(match_hmmss.group(3))
        
        if hours > 2:
            return False, "Время не может быть больше 2 часов."
        
        if hours == 0 and minutes < 4:
            return False, "Время должно быть больше 4 минут."
        
        return True, None
    
    else:
        return False, "Неверный формат времени. Используйте MM:SS (например, 7:30) или H:MM:SS (например, 1:05:30)."


def validate_participant_limit(limit: int, current_count: int = 0) -> Tuple[bool, Optional[str]]:
    """
    Validate participant limits with reasonable constraints.
    
    Args:
        limit: Proposed limit
        current_count: Current number of participants
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if limit < 1:
        return False, "Лимит участников должен быть больше 0."
    
    if limit > 500:
        return False, "Лимит участников не может быть больше 500."
    
    if limit < current_count:
        return False, f"Нельзя установить лимит ({limit}) меньше текущего числа участников ({current_count})."
    
    return True, None


def validate_bib_number(bib_number: str, existing_bibs: list = None) -> Tuple[bool, Optional[str]]:
    """
    Validate bib number with uniqueness check.
    
    Args:
        bib_number: Proposed bib number (as string to preserve leading zeros)
        existing_bibs: List of already assigned bib numbers
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not bib_number.isdigit():
        return False, "Номер должен содержать только цифры."
    
    bib_int = int(bib_number)
    if bib_int < 1:
        return False, "Номер должен быть больше 0."
    
    if bib_int > 9999:
        return False, "Номер не может быть больше 9999."
    
    if existing_bibs and bib_number in existing_bibs:
        return False, f"Номер {bib_number} уже занят."
    
    return True, None


def validate_user_id(user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Telegram user ID.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        uid = int(user_id)
        if uid <= 0:
            return False, "ID пользователя должен быть положительным числом."
        if uid > 999999999999:  # Telegram user IDs are typically much smaller
            return False, "Недействительный ID пользователя."
        return True, None
    except ValueError:
        return False, "ID пользователя должен быть числом."


def sanitize_input(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize user input by removing dangerous characters and limiting length.
    
    Args:
        input_str: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not input_str:
        return ""
    
    # Remove null bytes and other control characters
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', input_str)
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_result_format(result: str) -> Tuple[bool, Optional[str]]:
    """
    Validate race result format (MM:SS time format only).
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not result:
        return False, "Результат не может быть пустым."
    
    result = result.strip()
    
    # Pattern for MM:SS format only (e.g., 7:30, 25:45)
    pattern_mmss = r'^([0-9]{1,2}):([0-5][0-9])$'
    match_mmss = re.match(pattern_mmss, result)
    
    if match_mmss:
        minutes = int(match_mmss.group(1))
        seconds = int(match_mmss.group(2))
        
        # Reasonable constraints for beer mile (typically 4-20 minutes)
        if minutes < 4:
            return False, "Время должно быть больше 4 минут (4:00)."
        
        if minutes > 30:
            return False, "Время не может быть больше 30 минут для пивной мили."
        
        return True, None
    else:
        return False, "Неверный формат времени. Используйте формат ММ:СС (например, 7:30)."


def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format (optional feature for future use).
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not phone:
        return False, "Номер телефона не может быть пустым."
    
    phone = re.sub(r'[^\d+]', '', phone)  # Remove all non-digit characters except +
    
    # Russian phone number patterns
    patterns = [
        r'^\+7\d{10}$',      # +7xxxxxxxxxx
        r'^8\d{10}$',        # 8xxxxxxxxxx
        r'^7\d{10}$',        # 7xxxxxxxxxx
    ]
    
    for pattern in patterns:
        if re.match(pattern, phone):
            return True, None
    
    return False, "Неверный формат номера телефона. Используйте формат +7XXXXXXXXXX или 8XXXXXXXXXX."


def validate_message_length(message: str, max_length: int = 4000) -> Tuple[bool, Optional[str]]:
    """
    Validate message length for Telegram limits.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not message:
        return False, "Сообщение не может быть пустым."
    
    if len(message) > max_length:
        return False, f"Сообщение не может быть длиннее {max_length} символов."
    
    return True, None