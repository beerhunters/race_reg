"""
Команды управления листом ожидания
"""

import typer
from typing import Optional

from cli_admin.database import (
    get_waitlist_by_role,
    promote_waitlist_user_by_id,
    demote_participant_to_waitlist,
    remove_from_waitlist,
    get_waitlist_position,
)
from cli_admin.utils.display import (
    display_waitlist_table,
    print_success,
    print_error,
    print_info,
    confirm_action,
)

app = typer.Typer(help="📋 Управление листом ожидания")


@app.command("list")
def list_waitlist(
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Фильтр по роли (runner/volunteer)"),
):
    """
    📋 Просмотреть лист ожидания
    """
    try:
        waitlist = get_waitlist_by_role(role)

        if not waitlist:
            print_info("Лист ожидания пуст")
            return

        display_waitlist_table(waitlist)

    except Exception as e:
        print_error(f"Ошибка при получении листа ожидания: {str(e)}")
        raise typer.Exit(1)


@app.command("promote")
def promote(user_id: int = typer.Argument(..., help="Telegram ID пользователя из waitlist")):
    """
    ⬆️ Перевести пользователя из waitlist в участники
    """
    try:
        result = promote_waitlist_user_by_id(user_id)

        if result.get("success"):
            print_success(result.get("message", "Пользователь переведен в участники"))
        else:
            print_error(result.get("message", "Ошибка при переводе"))
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("demote")
def demote(user_id: int = typer.Argument(..., help="Telegram ID участника")):
    """
    ⬇️ Вернуть участника обратно в waitlist
    """
    try:
        result = demote_participant_to_waitlist(user_id)

        if result.get("success"):
            print_success(result.get("message", "Участник возвращен в waitlist"))
        else:
            print_error(result.get("message", "Ошибка при возврате"))
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("remove")
def remove(
    user_id: int = typer.Argument(..., help="Telegram ID пользователя"),
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
):
    """
    ❌ Удалить пользователя из листа ожидания
    """
    try:
        if not force:
            if not confirm_action(f"Удалить пользователя {user_id} из листа ожидания?"):
                print_info("Отменено")
                return

        success = remove_from_waitlist(user_id)

        if success:
            print_success(f"Пользователь {user_id} удален из листа ожидания")
        else:
            print_error("Ошибка при удалении")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("position")
def check_position(user_id: int = typer.Argument(..., help="Telegram ID пользователя")):
    """
    🔍 Проверить позицию в очереди
    """
    try:
        position, total = get_waitlist_position(user_id)

        if position is None:
            print_error(f"Пользователь {user_id} не найден в листе ожидания")
            raise typer.Exit(1)

        print_info(f"Позиция пользователя {user_id}: {position} из {total}")

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)
