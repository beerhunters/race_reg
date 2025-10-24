#!/usr/bin/env python3
"""
Beer Mile Admin CLI Tool
Консольное приложение для администрирования Beer Mile Registration Bot

Usage:
    beermile interactive          # Интерактивный режим
    beermile status               # Показать текущий статус
    beermile participants list    # Список участников
    beermile settings list        # Список настроек
    ... и другие команды
"""

import typer
import sys
from pathlib import Path

# Добавить родительскую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel

from cli_admin import __version__
from cli_admin.database import init_db
from cli_admin.config import DB_PATH
from cli_admin.utils.display import show_status, print_error
from cli_admin.commands import participants, settings, waitlist, teams, stats

# Создать главное приложение
app = typer.Typer(
    name="beermile",
    help="🍺 Beer Mile Admin CLI - Управление мероприятием через консоль",
    add_completion=True,
    rich_markup_mode="rich",
)

console = Console()


# Регистрация подкоманд
app.add_typer(participants.app, name="participants")
app.add_typer(settings.app, name="settings")
app.add_typer(waitlist.app, name="waitlist")
app.add_typer(teams.app, name="teams")
app.add_typer(stats.app, name="stats")


@app.command()
def interactive():
    """
    🎮 Запустить интерактивный режим с меню
    """
    try:
        from cli_admin.interactive.menus import main_menu
        main_menu()
    except ImportError:
        print_error("Интерактивный режим не доступен. Установите зависимости: pip install questionary")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Выход из интерактивного режима[/yellow]")
    except Exception as e:
        print_error(f"Ошибка в интерактивном режиме: {str(e)}")
        raise typer.Exit(1)


@app.command()
def status():
    """
    📊 Показать текущий статус мероприятия
    """
    try:
        show_status()
    except Exception as e:
        print_error(f"Ошибка при получении статуса: {str(e)}")
        raise typer.Exit(1)


@app.command()
def version():
    """
    📌 Показать версию приложения
    """
    console.print(Panel(
        f"[bold cyan]Beer Mile Admin CLI[/bold cyan]\n"
        f"Version: [green]{__version__}[/green]\n"
        f"Python: [blue]{sys.version.split()[0]}[/blue]",
        border_style="blue"
    ))


@app.callback()
def main(
    db_path: str = typer.Option(
        DB_PATH,
        "--db",
        "-d",
        help="Путь к файлу базы данных",
        envvar="BEERMILE_DB_PATH"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Подробный вывод"
    )
):
    """
    🍺 Beer Mile Admin CLI

    Консольное приложение для управления Beer Mile Registration Bot

    \b
    Примеры использования:
        beermile interactive                          # Интерактивное меню
        beermile status                               # Текущий статус
        beermile participants list                    # Список участников
        beermile participants get 123456789           # Информация об участнике
        beermile participants mark-paid 123456789     # Отметить как оплаченный
        beermile settings list                        # Список настроек
        beermile settings set max_runners 150         # Изменить настройку
        beermile waitlist list                        # Лист ожидания
        beermile teams list                           # Список команд
        beermile stats overview                       # Общая статистика

    \b
    Для получения помощи по конкретной команде:
        beermile participants --help
        beermile settings --help
    """
    # Сохранить путь к БД глобально
    import cli_admin.config as config
    config.DB_PATH = db_path

    # Инициализировать БД
    try:
        init_db()
    except Exception as e:
        if verbose:
            print_error(f"Ошибка при инициализации БД: {str(e)}")
            console.print_exception()
        else:
            print_error(f"Ошибка при инициализации БД: {str(e)}")
        raise typer.Exit(1)


def cli():
    """Entry point для установленного пакета"""
    app()


if __name__ == "__main__":
    app()
