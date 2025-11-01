"""
Интерактивные меню для CLI
"""

import questionary
from rich.console import Console
from rich.panel import Panel

from cli_admin.utils.display import show_status, clear_screen
from cli_admin.commands import participants, settings, waitlist, teams, stats

console = Console()


def main_menu():
    """
    Главное интерактивное меню
    """
    while True:
        try:
            clear_screen()
            show_status()

            choice = questionary.select(
                "🍺 Beer Mile Admin - Главное меню",
                choices=[
                    "👥 Управление участниками",
                    "⚙️ Настройки мероприятия",
                    "📋 Лист ожидания",
                    "🏆 Управление командами",
                    "📊 Статистика и аналитика",
                    questionary.Separator(),
                    "❌ Выход"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "❌ Выход":
                console.print("\n[yellow]До свидания! 👋[/yellow]\n")
                break
            elif choice == "👥 Управление участниками":
                participants_menu()
            elif choice == "⚙️ Настройки мероприятия":
                settings_menu()
            elif choice == "📋 Лист ожидания":
                waitlist_menu()
            elif choice == "🏆 Управление командами":
                teams_menu()
            elif choice == "📊 Статистика и аналитика":
                stats_menu()

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Выход...[/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def participants_menu():
    """
    Меню управления участниками
    """
    while True:
        try:
            clear_screen()
            console.print(Panel(
                "[bold cyan]👥 Управление участниками[/bold cyan]",
                border_style="blue"
            ))
            console.print()

            choice = questionary.select(
                "Выберите действие:",
                choices=[
                    "📋 Просмотреть всех участников",
                    "🔍 Найти участника",
                    "💳 Отметить оплату",
                    "🔢 Присвоить стартовый номер",
                    "✏️ Редактировать участника",
                    "❌ Удалить участника",
                    questionary.Separator(),
                    "⬅️ Назад"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "⬅️ Назад":
                break
            elif choice == "📋 Просмотреть всех участников":
                view_all_participants()
            elif choice == "🔍 Найти участника":
                find_participant()
            elif choice == "💳 Отметить оплату":
                mark_payment()
            elif choice == "🔢 Присвоить стартовый номер":
                assign_bib_number()
            elif choice == "✏️ Редактировать участника":
                edit_participant()
            elif choice == "❌ Удалить участника":
                delete_participant()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def settings_menu():
    """
    Меню настроек
    """
    while True:
        try:
            clear_screen()
            console.print(Panel(
                "[bold cyan]⚙️ Настройки мероприятия[/bold cyan]",
                border_style="blue"
            ))
            console.print()

            # Показать текущие настройки
            from cli_admin.database import get_setting

            max_runners = get_setting("max_runners") or "100"
            event_date = get_setting("event_date") or "Не установлена"
            team_mode = get_setting("team_mode_enabled")
            team_mode_text = "✅ Включен" if team_mode == "1" or team_mode == 1 else "❌ Выключен"

            console.print(f"[cyan]Текущие настройки:[/cyan]")
            console.print(f"  • Макс. бегунов: [green]{max_runners}[/green]")
            console.print(f"  • Дата мероприятия: [green]{event_date}[/green]")
            console.print(f"  • Командный режим: {team_mode_text}")
            console.print()

            choice = questionary.select(
                "Выберите действие:",
                choices=[
                    "📋 Просмотреть все настройки",
                    "✏️ Изменить настройку",
                    "🔄 Переключить командный режим",
                    questionary.Separator(),
                    "⬅️ Назад"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "⬅️ Назад":
                break
            elif choice == "📋 Просмотреть все настройки":
                view_all_settings()
            elif choice == "✏️ Изменить настройку":
                edit_setting()
            elif choice == "🔄 Переключить командный режим":
                toggle_team_mode()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def waitlist_menu():
    """
    Меню листа ожидания
    """
    while True:
        try:
            clear_screen()
            console.print(Panel(
                "[bold cyan]📋 Управление листом ожидания[/bold cyan]",
                border_style="blue"
            ))
            console.print()

            choice = questionary.select(
                "Выберите действие:",
                choices=[
                    "📋 Просмотреть весь лист ожидания",
                    "⬆️ Перевести в участники",
                    "⬇️ Вернуть в waitlist",
                    "🔍 Проверить позицию",
                    questionary.Separator(),
                    "⬅️ Назад"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "⬅️ Назад":
                break
            elif choice == "📋 Просмотреть весь лист ожидания":
                view_waitlist()
            elif choice == "⬆️ Перевести в участники":
                promote_from_waitlist()
            elif choice == "⬇️ Вернуть в waitlist":
                demote_to_waitlist()
            elif choice == "🔍 Проверить позицию":
                check_waitlist_position()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def teams_menu():
    """
    Меню команд
    """
    while True:
        try:
            clear_screen()
            console.print(Panel(
                "[bold cyan]🏆 Управление командами[/bold cyan]",
                border_style="blue"
            ))
            console.print()

            choice = questionary.select(
                "Выберите действие:",
                choices=[
                    "📋 Просмотреть все команды",
                    "🔍 Найти команду",
                    "🏁 Установить результат",
                    "❌ Удалить команду",
                    questionary.Separator(),
                    "⬅️ Назад"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "⬅️ Назад":
                break
            elif choice == "📋 Просмотреть все команды":
                view_all_teams()
            elif choice == "🔍 Найти команду":
                find_team()
            elif choice == "🏁 Установить результат":
                set_team_result()
            elif choice == "❌ Удалить команду":
                delete_team()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def stats_menu():
    """
    Меню статистики
    """
    while True:
        try:
            clear_screen()
            console.print(Panel(
                "[bold cyan]📊 Статистика и аналитика[/bold cyan]",
                border_style="blue"
            ))
            console.print()

            choice = questionary.select(
                "Выберите действие:",
                choices=[
                    "📈 Общая статистика",
                    "💰 Статистика оплат",
                    "🏆 Статистика команд",
                    questionary.Separator(),
                    "⬅️ Назад"
                ],
                use_shortcuts=True,
                qmark="",
                pointer="►"
            ).ask()

            if choice == "⬅️ Назад":
                break
            elif choice == "📈 Общая статистика":
                show_overview_stats()
            elif choice == "💰 Статистика оплат":
                show_payment_stats()
            elif choice == "🏆 Статистика команд":
                show_teams_stats()

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Ошибка: {str(e)}[/red]\n")
            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


# Вспомогательные функции для действий

def view_all_participants():
    """Просмотр всех участников"""
    from cli_admin.database import get_all_participants
    from cli_admin.utils.display import display_participants_table

    participants = get_all_participants()
    console.print()
    display_participants_table(participants)
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def find_participant():
    """Поиск участника"""
    user_id = questionary.text("Введите Telegram ID участника:").ask()

    if user_id:
        from cli_admin.database import get_participant_by_user_id
        from cli_admin.utils.display import display_participant_details, print_error

        try:
            participant = get_participant_by_user_id(int(user_id))
            if participant:
                display_participant_details(participant)
            else:
                print_error(f"Участник с ID {user_id} не найден")
        except ValueError:
            print_error("Неверный формат ID")

        questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def mark_payment():
    """Отметить оплату"""
    user_id = questionary.text("Введите Telegram ID участника:").ask()

    if user_id:
        from cli_admin.database import update_payment_status
        from cli_admin.utils.display import print_success, print_error

        try:
            success = update_payment_status(int(user_id), "paid")
            if success:
                print_success(f"Участник {user_id} отмечен как оплативший")
            else:
                print_error("Ошибка при обновлении статуса")
        except ValueError:
            print_error("Неверный формат ID")

        questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def assign_bib_number():
    """Присвоить стартовый номер"""
    user_id = questionary.text("Введите Telegram ID участника:").ask()
    if not user_id:
        return

    bib_number = questionary.text("Введите стартовый номер:").ask()
    if not bib_number:
        return

    from cli_admin.database import set_bib_number
    from cli_admin.utils.display import print_success, print_error

    try:
        success = set_bib_number(int(user_id), bib_number)
        if success:
            print_success(f"Номер {bib_number} присвоен участнику {user_id}")
        else:
            print_error("Ошибка при присвоении номера")
    except ValueError:
        print_error("Неверный формат ID")

    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def edit_participant():
    """Редактировать участника"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def delete_participant():
    """Удалить участника"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def view_all_settings():
    """Просмотр всех настроек"""
    from cli_admin.commands.settings import SETTINGS_KEYS
    from cli_admin.database import get_setting
    from cli_admin.utils.display import display_settings_table

    settings = {}
    for key in SETTINGS_KEYS:
        settings[key] = get_setting(key)

    console.print()
    display_settings_table(settings)
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def edit_setting():
    """Изменить настройку"""
    from cli_admin.commands.settings import SETTINGS_KEYS

    key = questionary.select(
        "Выберите настройку для изменения:",
        choices=SETTINGS_KEYS
    ).ask()

    if key:
        value = questionary.text(f"Введите новое значение для '{key}':").ask()

        if value:
            from cli_admin.database import set_setting
            from cli_admin.utils.display import print_success, print_error

            success = set_setting(key, value)
            if success:
                print_success(f"Настройка '{key}' установлена в '{value}'")
            else:
                print_error("Ошибка при установке настройки")

            questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def toggle_team_mode():
    """Переключить командный режим"""
    from cli_admin.database import get_setting, set_setting
    from cli_admin.utils.display import print_success

    current = get_setting("team_mode_enabled")
    new_value = "0" if current == "1" or current == 1 else "1"

    set_setting("team_mode_enabled", new_value)
    status = "включен" if new_value == "1" else "выключен"
    print_success(f"Командный режим {status}")

    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def view_waitlist():
    """Просмотр листа ожидания"""
    from cli_admin.database import get_waitlist_by_role
    from cli_admin.utils.display import display_waitlist_table

    waitlist = get_waitlist_by_role()
    console.print()
    display_waitlist_table(waitlist)
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def promote_from_waitlist():
    """Перевести из waitlist в участники"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def demote_to_waitlist():
    """Вернуть в waitlist"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def check_waitlist_position():
    """Проверить позицию в waitlist"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def view_all_teams():
    """Просмотр всех команд"""
    from cli_admin.database import get_all_teams
    from cli_admin.utils.display import display_teams_table

    teams = get_all_teams()
    console.print()
    display_teams_table(teams)
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def find_team():
    """Найти команду"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def set_team_result():
    """Установить результат команды"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def delete_team():
    """Удалить команду"""
    console.print("[yellow]Функция в разработке[/yellow]")
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def show_overview_stats():
    """Общая статистика"""
    from cli_admin.commands.stats import overview

    console.print()
    overview()
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def show_payment_stats():
    """Статистика оплат"""
    from cli_admin.commands.stats import payment_stats

    console.print()
    payment_stats()
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()


def show_teams_stats():
    """Статистика команд"""
    from cli_admin.commands.stats import teams_stats

    console.print()
    teams_stats()
    console.print()
    questionary.press_any_key_to_continue("Нажмите любую клавишу для продолжения...").ask()
