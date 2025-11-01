"""
Команды управления настройками
"""

import typer
from rich.console import Console

from cli_admin.database import get_setting, set_setting
from cli_admin.utils.display import (
    display_settings_table,
    print_success,
    print_error,
    print_info,
)

app = typer.Typer(help="⚙️ Управление настройками мероприятия")
console = Console()


SETTINGS_KEYS = [
    "max_runners",
    "team_mode_enabled",
    "registration_end_date",
    "event_date",
    "participation_fee",
    "event_location",
    "auto_backup_enabled",
]


@app.command("list")
def list_settings():
    """
    📋 Просмотреть все настройки
    """
    try:
        settings = {}

        for key in SETTINGS_KEYS:
            value = get_setting(key)
            settings[key] = value

        display_settings_table(settings)

    except Exception as e:
        print_error(f"Ошибка при получении настроек: {str(e)}")
        raise typer.Exit(1)


@app.command("get")
def get(key: str = typer.Argument(..., help="Ключ настройки")):
    """
    🔍 Получить значение настройки
    """
    try:
        value = get_setting(key)

        if value is None:
            print_error(f"Настройка '{key}' не найдена")
            raise typer.Exit(1)

        print_info(f"{key} = {value}")

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Ключ настройки"),
    value: str = typer.Argument(..., help="Значение"),
):
    """
    ✏️ Установить значение настройки
    """
    try:
        success = set_setting(key, value)

        if success:
            print_success(f"Настройка '{key}' установлена в '{value}'")
        else:
            print_error("Ошибка при установке настройки")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("toggle")
def toggle(key: str = typer.Argument(..., help="Ключ настройки для переключения")):
    """
    🔄 Переключить булеву настройку (0 <-> 1)
    """
    try:
        current = get_setting(key)

        if current is None:
            print_error(f"Настройка '{key}' не найдена")
            raise typer.Exit(1)

        # Переключить
        try:
            current_int = int(current)
            new_value = 0 if current_int == 1 else 1
        except ValueError:
            print_error(f"Настройка '{key}' не является булевой")
            raise typer.Exit(1)

        success = set_setting(key, str(new_value))

        if success:
            status = "включено" if new_value == 1 else "выключено"
            print_success(f"Настройка '{key}' {status}")
        else:
            print_error("Ошибка при переключении настройки")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)
