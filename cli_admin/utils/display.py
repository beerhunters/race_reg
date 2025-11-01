"""
Утилиты для отображения данных в консоли
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import List, Dict, Any, Optional
from datetime import datetime

from cli_admin.config import *
from cli_admin.database import (
    get_participant_count,
    get_participant_count_by_role,
    get_waitlist_by_role,
    get_all_teams,
    count_complete_teams,
    get_setting,
)

console = Console()


def print_success(message: str):
    """Вывести сообщение об успехе"""
    console.print(f"[{COLOR_SUCCESS}]{EMOJI_SUCCESS} {message}[/{COLOR_SUCCESS}]")


def print_error(message: str):
    """Вывести сообщение об ошибке"""
    console.print(f"[{COLOR_ERROR}]{EMOJI_ERROR} {message}[/{COLOR_ERROR}]")


def print_warning(message: str):
    """Вывести предупреждение"""
    console.print(f"[{COLOR_WARNING}]{EMOJI_WARNING} {message}[/{COLOR_WARNING}]")


def print_info(message: str):
    """Вывести информационное сообщение"""
    console.print(f"[{COLOR_INFO}]{EMOJI_INFO} {message}[/{COLOR_INFO}]")


def clear_screen():
    """Очистить экран"""
    console.clear()


def show_header(title: str):
    """Показать заголовок"""
    console.print()
    console.print(Panel(
        f"[bold cyan]{title}[/bold cyan]",
        border_style="blue"
    ))
    console.print()


def show_status():
    """
    Показать текущий статус мероприятия
    """
    clear_screen()

    # Получить данные
    try:
        total_participants = get_participant_count()
        runners = get_participant_count_by_role("runner")
        volunteers = get_participant_count_by_role("volunteer")
        waitlist = len(get_waitlist_by_role())
        teams = len(get_all_teams())
        complete_teams = count_complete_teams()

        max_runners = get_setting("max_runners") or 100
        event_date = get_setting("event_date") or "Не установлена"
        team_mode = get_setting("team_mode_enabled")

        # Подсчет оплаченных
        from cli_admin.database import get_all_participants
        all_p = get_all_participants()
        paid_count = sum(1 for p in all_p if p[6] == 'paid')

    except Exception as e:
        print_error(f"Ошибка при получении статистики: {str(e)}")
        return

    # Создать таблицу статистики
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan", width=30)
    table.add_column(style="green")

    table.add_row(f"{EMOJI_RUNNER} Участников (бегунов):", f"{runners}/{max_runners}")
    table.add_row(f"💳 Оплатили:", f"{paid_count}/{total_participants}")
    table.add_row(f"📋 В листе ожидания:", str(waitlist))
    table.add_row(f"{EMOJI_TEAM} Команд:", f"{teams} ({complete_teams} полных)")
    table.add_row(f"📅 Дата мероприятия:", event_date)
    table.add_row(f"👥 Командный режим:", "✅ Включен" if team_mode == 1 else "❌ Выключен")

    panel = Panel(
        table,
        title="[bold cyan]🍺 Beer Mile - Текущая статистика[/bold cyan]",
        border_style="blue"
    )

    console.print(panel)
    console.print()


def display_participants_table(participants: List[tuple], title: str = "Список участников"):
    """
    Отобразить таблицу участников

    Args:
        participants: Список кортежей участников из БД
        title: Заголовок таблицы
    """
    if not participants:
        print_warning("Участники не найдены")
        return

    table = Table(title=title, show_lines=False)

    table.add_column("ID", style="cyan", width=10)
    table.add_column("Имя", style="green", width=20)
    table.add_column("Username", style="blue", width=15)
    table.add_column("Роль", width=6)
    table.add_column("Оплата", width=8)
    table.add_column("Номер", width=8)
    table.add_column("Дата рег.", width=12)

    for p in participants:
        user_id, username, name, target_time, role, reg_date, payment, bib, *_ = p

        role_emoji = EMOJI_RUNNER if role == "runner" else EMOJI_VOLUNTEER
        payment_emoji = "✅" if payment == "paid" else "❌"

        table.add_row(
            str(user_id),
            name[:18] + "..." if len(name) > 20 else name,
            f"@{username}" if username else "-",
            role_emoji,
            payment_emoji,
            bib or "-",
            reg_date[:10] if reg_date else "-"
        )

    console.print(table)
    console.print(f"\n[cyan]Всего: {len(participants)} участников[/cyan]")


def display_participant_details(participant: tuple):
    """
    Отобразить детальную информацию об участнике

    Args:
        participant: Кортеж с данными участника
    """
    # participants table: user_id, username, name, target_time, role, reg_date, payment_status, bib_number, result, gender, category, cluster
    if len(participant) < 12:
        from cli_admin.utils.display import print_error
        print_error(f"Неверное количество полей участника: {len(participant)}, ожидается 12")
        return

    user_id, username, name, target_time, role, reg_date, payment, bib, result, gender, category, cluster = participant[:12]

    console.print("\n[bold cyan]━━━ Информация об участнике ━━━[/bold cyan]\n")

    console.print(f"  [cyan]Telegram ID:[/cyan] {user_id}")
    console.print(f"  [cyan]Username:[/cyan] @{username or 'не указан'}")
    console.print(f"  [cyan]Имя:[/cyan] {name}")
    console.print(f"  [cyan]Роль:[/cyan] {'Бегун ' + EMOJI_RUNNER if role == 'runner' else 'Волонтер ' + EMOJI_VOLUNTEER}")
    console.print(f"  [cyan]Целевое время:[/cyan] {target_time or '-'}")
    console.print(f"  [cyan]Дата регистрации:[/cyan] {reg_date}")
    console.print(f"  [cyan]Оплата:[/cyan] {'✅ Оплачено' if payment == 'paid' else '❌ Не оплачено'}")
    console.print(f"  [cyan]Стартовый номер:[/cyan] {bib or '-'}")
    console.print(f"  [cyan]Пол:[/cyan] {gender or '-'}")
    console.print(f"  [cyan]Категория:[/cyan] {category or '-'}")
    console.print(f"  [cyan]Кластер:[/cyan] {cluster or '-'}")
    console.print(f"  [cyan]Результат:[/cyan] {result or '-'}")

    console.print("\n[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/cyan]\n")


def display_waitlist_table(waitlist: List[tuple], title: str = "Лист ожидания"):
    """
    Отобразить таблицу листа ожидания

    Args:
        waitlist: Список кортежей из БД
        title: Заголовок таблицы
    """
    if not waitlist:
        print_warning("Лист ожидания пуст")
        return

    table = Table(title=title, show_lines=False)

    table.add_column("#", style="cyan", width=5)
    table.add_column("User ID", style="cyan", width=10)
    table.add_column("Имя", style="green", width=20)
    table.add_column("Роль", width=6)
    table.add_column("Дата добавления", width=12)
    table.add_column("Статус", width=12)

    for idx, w in enumerate(waitlist, 1):
        wl_id, user_id, username, name, target_time, role, gender, join_date, status, *_ = w

        role_emoji = EMOJI_RUNNER if role == "runner" else EMOJI_VOLUNTEER

        status_text = {
            "waiting": "⏳ Ожидает",
            "notified": "🔔 Уведомлен",
            "confirmed": "✅ Подтвержден",
            "declined": "❌ Отклонен"
        }.get(status, status)

        table.add_row(
            str(idx),
            str(user_id),
            name[:18] + "..." if len(name) > 20 else name,
            role_emoji,
            join_date[:10] if join_date else "-",
            status_text
        )

    console.print(table)
    console.print(f"\n[cyan]Всего в очереди: {len(waitlist)}[/cyan]")


def display_teams_table(teams: List[tuple], title: str = "Список команд"):
    """
    Отобразить таблицу команд

    Args:
        teams: Список кортежей команд из БД
        title: Заголовок таблицы
    """
    if not teams:
        print_warning("Команды не найдены")
        return

    table = Table(title=title, show_lines=False)

    table.add_column("ID", style="cyan", width=5)
    table.add_column("Название", style="green", width=25)
    table.add_column("Участник 1", width=12)
    table.add_column("Участник 2", width=12)
    table.add_column("Статус", width=10)
    table.add_column("Результат", width=12)

    for t in teams:
        # teams table: team_id, team_name, member1_id, member2_id, result, created_date
        team_id, team_name, member1_id, member2_id, result, created_date, *_ = t

        member1 = str(member1_id) if member1_id else "-"
        member2 = str(member2_id) if member2_id else "-"

        if member1_id and member2_id:
            status = "✅ Полная"
        elif member1_id or member2_id:
            status = "⏳ Неполная"
        else:
            status = "❌ Пустая"

        table.add_row(
            str(team_id) if team_id else "-",
            str(team_name) if team_name else "-",
            member1,
            member2,
            status,
            str(result) if result else "-"
        )

    console.print(table)
    console.print(f"\n[cyan]Всего команд: {len(teams)}[/cyan]")


def display_settings_table(settings: Dict[str, Any]):
    """
    Отобразить таблицу настроек

    Args:
        settings: Словарь настроек
    """
    table = Table(title="Текущие настройки", show_lines=False)

    table.add_column("Параметр", style="cyan", width=30)
    table.add_column("Значение", style="green", width=40)

    for key, value in settings.items():
        # Форматирование ключа
        key_formatted = key.replace("_", " ").title()

        # Форматирование значения
        if isinstance(value, bool):
            value_formatted = "✅ Включено" if value else "❌ Выключено"
        elif value is None:
            value_formatted = "-"
        else:
            value_formatted = str(value)

        table.add_row(key_formatted, value_formatted)

    console.print(table)


def display_edit_requests_table(requests: List[tuple], title: str = "Запросы на редактирование"):
    """
    Отобразить таблицу запросов на редактирование

    Args:
        requests: Список кортежей запросов из БД
        title: Заголовок таблицы
    """
    if not requests:
        print_warning("Нет pending запросов")
        return

    table = Table(title=title, show_lines=False)

    table.add_column("ID", style="cyan", width=5)
    table.add_column("User ID", style="cyan", width=10)
    table.add_column("Поле", width=12)
    table.add_column("Старое значение", width=15)
    table.add_column("Новое значение", width=15)
    table.add_column("Дата", width=12)

    for r in requests:
        req_id, user_id, field, old_value, new_value, status, request_date = r

        table.add_row(
            str(req_id),
            str(user_id),
            field,
            old_value or "-",
            new_value or "-",
            request_date[:10] if request_date else "-"
        )

    console.print(table)
    console.print(f"\n[cyan]Всего запросов: {len(requests)}[/cyan]")


def show_progress(total: int, description: str = "Processing"):
    """
    Создать прогресс бар

    Args:
        total: Общее количество элементов
        description: Описание процесса

    Returns:
        Progress объект
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )
    return progress


def confirm_action(message: str, default: bool = False) -> bool:
    """
    Запросить подтверждение действия

    Args:
        message: Сообщение для пользователя
        default: Значение по умолчанию

    Returns:
        True если подтверждено, False иначе
    """
    import questionary
    return questionary.confirm(message, default=default).ask()


def prompt_input(message: str, default: str = None) -> str:
    """
    Запросить ввод от пользователя

    Args:
        message: Сообщение для пользователя
        default: Значение по умолчанию

    Returns:
        Введенная строка
    """
    import questionary
    return questionary.text(message, default=default).ask()


def prompt_select(message: str, choices: List[str]) -> str:
    """
    Запросить выбор из списка

    Args:
        message: Сообщение для пользователя
        choices: Список вариантов

    Returns:
        Выбранный вариант
    """
    import questionary
    return questionary.select(message, choices=choices).ask()
