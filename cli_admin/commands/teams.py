"""
Команды управления командами
"""

import typer

from cli_admin.database import (
    get_all_teams,
    get_team_by_id,
    delete_team,
    set_team_result,
    count_complete_teams,
    clear_all_teams,
)
from cli_admin.utils.display import (
    display_teams_table,
    print_success,
    print_error,
    print_info,
    confirm_action,
)

app = typer.Typer(help="🏆 Управление командами")


@app.command("list")
def list_teams():
    """
    📋 Просмотреть все команды
    """
    try:
        teams = get_all_teams()

        if not teams:
            print_info("Команды не найдены")
            return

        display_teams_table(teams)

        # Статистика
        complete = count_complete_teams()
        print_info(f"Полных команд: {complete}/{len(teams)}")

    except Exception as e:
        print_error(f"Ошибка при получении команд: {str(e)}")
        raise typer.Exit(1)


@app.command("get")
def get_team(team_id: int = typer.Argument(..., help="ID команды")):
    """
    🔍 Получить информацию о команде
    """
    try:
        team = get_team_by_id(team_id)

        if not team:
            print_error(f"Команда с ID {team_id} не найдена")
            raise typer.Exit(1)

        # teams table: team_id, team_name, member1_id, member2_id, result, created_date
        team_id, team_name, member1_id, member2_id, result, created_date, *_ = team

        print_info(f"\nКоманда ID: {team_id}")
        print_info(f"Название: {team_name}")
        print_info(f"Участник 1: {member1_id or '-'}")
        print_info(f"Участник 2: {member2_id or '-'}")
        print_info(f"Результат: {result or '-'}")
        print_info(f"Дата создания: {created_date or '-'}\n")

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set-result")
def set_result(
    team_id: int = typer.Argument(..., help="ID команды"),
    result: str = typer.Argument(..., help="Результат команды"),
):
    """
    🏁 Установить результат команды
    """
    try:
        success = set_team_result(team_id, result)

        if success:
            print_success(f"Результат команды {team_id} установлен: {result}")
        else:
            print_error("Ошибка при установке результата")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("delete")
def delete(
    team_id: int = typer.Argument(..., help="ID команды"),
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
):
    """
    ❌ Удалить команду
    """
    try:
        if not force:
            if not confirm_action(f"Удалить команду {team_id}?"):
                print_info("Отменено")
                return

        success = delete_team(team_id)

        if success:
            print_success(f"Команда {team_id} удалена")
        else:
            print_error("Ошибка при удалении команды")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("clear-all")
def clear_all(confirm: bool = typer.Option(False, "--confirm", help="Подтвердить очистку")):
    """
    🧹 Очистить все команды
    """
    try:
        if not confirm:
            if not confirm_action("⚠️ Вы уверены, что хотите удалить ВСЕ команды?"):
                print_info("Отменено")
                return

        success = clear_all_teams()

        if success:
            print_success("Все команды удалены")
        else:
            print_error("Ошибка при очистке команд")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)
